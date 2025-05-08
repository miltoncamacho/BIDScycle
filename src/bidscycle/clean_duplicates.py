#!/usr/bin/env python3
"""
bidscycle.clean_duplicates
===========================

Remove duplicate files from a BIDS dataset.
This module provides functions to remove duplicate files from a BIDS
dataset, including the ability to switch or use duplicates, and clean up
the dataset by removing duplicates and updating the corresponding TSV
files.

The functions in this module are designed to work with BIDS datasets and
are intended to be used in conjunction with the DataLad library for
version control and dataset management.

Logging
-------
Importers configure the root or module‐specific logger; this file merely
emits **DEBUG** (fine‑grained), **INFO** (summary), and **WARNING**
messages.
"""

from __future__ import annotations

import re
import csv
import logging
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from bids import BIDSLayout

try:
    import datalad.api as dl

    HAVE_DATALAD = True
except ModuleNotFoundError:
    HAVE_DATALAD = False

lgr = logging.getLogger(__name__)
__all__ = ["clean_duplicates"]


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


# Parse filter strings into a dictionary
def _parse_entities(items: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for kv in items:
        k, v = kv.split("=", 1)
        out[k] = [x.strip() for x in v.split(",") if x.strip()]
    return out


# Get the full extension of a file (e.g., nii.gz)
def _full_ext(p: Path) -> str:
    """Return the complete extension chain ('.nii.gz', '.tar.bz2', …)."""
    return "".join(p.suffixes)


# Check if the file is a NIfTI file (i.e., .nii or .nii.gz)
def _is_nifti(p: Path) -> bool:
    """True for .nii or .nii.gz (compressed)."""
    return _full_ext(p).startswith(".nii")


# Get the sidecar JSON file for a NIfTI file
def _json_sidecar(src: Path) -> Path:
    """
    Return the side‑car JSON path for a NIfTI file, handling both
    '.nii' and '.nii.gz'.
    """
    stem = src.name[: -len("".join(src.suffixes))]  # remove full ext
    return src.with_name(f"{stem}.json")


# --------------------------------------------------------------------------- #
# main worker                                                                 #
# --------------------------------------------------------------------------- #


# Remove duplicate files from a BIDS dataset
def clean_duplicates(
    *,
    dataset: Path,
    filters: List[str],
    keep_pattern: str = None,  # e.g., "__dup-01" to keep only that variant
    commit_msg: str | None = None,
    dry_run: bool = False,
    use_datalad: bool = True,
) -> List[Path]:
    """
    Remove duplicate files with __dup-XX pattern, keeping one specified pattern if provided.

    Parameters
    ----------
    dataset
        Root of the BIDS dataset.
    filters
        List like ['subject=01', 'run=2,3', 'suffix=T1w'] to limit scope.
    keep_pattern
        If specified (e.g., "__dup-01"), duplicate files with this pattern will be kept.
        If None, no duplicates are kept.
    commit_msg
        If given, ``datalad.save`` records the deletions.
    dry_run
        Report but do not touch the filesystem.
    use_datalad
        Disable DataLad even if *commit_msg* is provided.

    Returns
    -------
    List[Path]
        Paths of all removed files.
    """

    layout = BIDSLayout(dataset, validate=False)

    # First, identify all files with __dup-XX pattern
    dup_pattern = re.compile(r"__dup-\d\d")

    # Start with all matching files from the filters
    base_files = layout.get(**_parse_entities(filters), return_type="filename")

    # ------------------ build rename plan ---------------------------------- #
    # Find all files with the dup pattern that match our base criteria
    all_files = []
    for base_file in base_files:
        base_path = Path(base_file)
        parent_dir = base_path.parent

        # Extract the stem before any extension
        stem = base_path.name.split('.')[0]
        base_stem = re.split(r"__dup-\d\d", stem)[0] if dup_pattern.search(stem) else stem

        # Find all files that match this base stem plus any dup pattern
        for f in parent_dir.glob(f"{base_stem}*"):
            if dup_pattern.search(f.name):
                all_files.append(f)

    # Filter files to keep or remove
    files_to_remove = []
    for file_path in all_files:
        match = dup_pattern.search(file_path.name)
        # lgr.info("match: %s", match)
        if match:
            current_pattern = match.group(0)
            if keep_pattern is None or current_pattern not in keep_pattern:
                files_to_remove.append(file_path)

                # Also add JSON sidecar if this is a NIfTI file
                if _is_nifti(file_path):
                    json_path = _json_sidecar(file_path)
                    if json_path.exists() and json_path not in files_to_remove:
                        files_to_remove.append(json_path)

    if not files_to_remove:
        lgr.warning("No duplicate files found matching the filters %s and keep_pattern %s", filters, keep_pattern)
        return []

    lgr.info("Found %d file(s) to remove with filters %s", len(files_to_remove), filters)

    # Track scans.tsv updates needed
    tsv_updates = defaultdict(dict)

    # ------------------ execute renames ------------------------------------ #
    removed_files = []
    for file_path in files_to_remove:
        if _is_nifti(file_path):
            # Update scans.tsv entries
            session_dir = file_path.parents[1]  # .../sub-XX/ses-YY
            rel_path = file_path.relative_to(session_dir).as_posix()
            tsv_path = next(session_dir.glob("*_scans.tsv"), None)

            if tsv_path:
                # Mark this file for removal from the TSV
                tsv_updates[tsv_path][rel_path] = None

        rel_path = file_path.relative_to(dataset)
        if dry_run:
            lgr.info("[DRY-RUN] Would remove %s", rel_path)
            removed_files.append(file_path)
        else:
            if file_path.exists():
                file_path.unlink()
                removed_files.append(file_path)
                lgr.debug("Removed %s", rel_path)

    # ------------------ patch scans.tsv ------------------------------------ #
    for tsv_path, removals in tsv_updates.items():
        if dry_run:
            for path in removals:
                lgr.info("[DRY-RUN] Would remove entry %s from %s",
                         path, tsv_path.relative_to(dataset))
            continue

        lgr.debug("Updating %s", tsv_path.relative_to(dataset))

        with tsv_path.open(newline="") as fin, tempfile.NamedTemporaryFile(
            "w", delete=False, newline="", dir=str(tsv_path.parent)
        ) as fout:
            rdr = csv.reader(fin, delimiter="\t")
            wtr = csv.writer(fout, delimiter="\t", lineterminator="\n")

            header = next(rdr)
            filename_idx = header.index("filename")
            wtr.writerow(header)

            for row in rdr:
                # Skip rows for files we've removed
                if row[filename_idx] not in removals:
                    wtr.writerow(row)

        shutil.move(fout.name, tsv_path)

    # ------------------ provenance ----------------------------------------- #
    if (
        commit_msg
        and not dry_run
        and use_datalad
        and HAVE_DATALAD
        and removed_files
    ):
        lgr.info("Saving changes to DataLad with message: %s", commit_msg)
        dl.Dataset(str(dataset)).save(message=commit_msg)

    # ------------------ summary -------------------------------------------- #
    if dry_run:
        lgr.info("Would remove %d file(s)", len(removed_files))
        lgr.info("Would patch %d scans.tsv files", len(tsv_updates))
    else:
        lgr.info("Removed %d file(s) (plus side‑cars)", len(removed_files))
        lgr.info("Patched %d scans.tsv files", len(tsv_updates))

    return removed_files
