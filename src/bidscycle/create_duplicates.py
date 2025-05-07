#!/usr/bin/env python3
"""
bidscycle.create_duplicates
===========================

Rename every file that matches a set of BIDS‑entity filters to

    <stem>__dup-XX<ext>

 • Matching side‑car *.json* files are renamed in lock‑step.
 • The corresponding *sub‑…_scans.tsv* is patched so its **filename**
  column always points to the new path.
 • One DataLad commit records the change when *commit_msg* is supplied
  (and *datalad* is importable).

Logging
-------
Importers configure the root or module‐specific logger; this file merely
emits **DEBUG** (fine‑grained), **INFO** (summary), and **WARNING**
messages.
"""

from __future__ import annotations

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
__all__ = ["create_duplicates"]

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _parse_entities(items: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for kv in items:
        k, v = kv.split("=", 1)
        out[k] = [x.strip() for x in v.split(",") if x.strip()]
    return out


def _next_free_number(seen: set[int]) -> int:
    """Return the lowest positive integer not in *seen* (1‑based)."""
    n = 1
    while n in seen:
        n += 1
    return n

def _dup_path(src: Path, num: int) -> Path:
    """
    Return <stem>__dup-XX<all_suffixes>, where <all_suffixes> could be
    ".nii.gz", ".json", ".tsv.gz", …
    """
    full_ext = "".join(src.suffixes)          # ".nii.gz"
    stem = src.name[: -len(full_ext)]         # strip that whole tail
    new_name = f"{stem}__dup-{num:02d}{full_ext}"
    return src.with_name(new_name)

def _full_ext(p: Path) -> str:
    """Return the complete extension chain ('.nii.gz', '.tar.bz2', …)."""
    return "".join(p.suffixes)

def _is_nifti(p: Path) -> bool:
    """True for .nii or .nii.gz (compressed)."""
    return _full_ext(p).startswith(".nii")

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
def create_duplicates(
    *,
    dataset: Path,
    filters: List[str],
    commit_msg: str | None = None,
    dry_run: bool = False,
    use_datalad: bool = True,
) -> List[Path]:
    """
    Parameters
    ----------
    dataset
        Root of the BIDS dataset.
    filters
        List like ['subject=01', 'run=2,3', 'suffix=T1w'].
    commit_msg
        If given, ``datalad.save`` records the renames.
    dry_run
        Report but do not touch the filesystem.
    use_datalad
        Disable DataLad even if *commit_msg* is provided.

    Returns
    -------
    List[Path]
        The *new* paths of all renamed files (NIfTI + JSON).
    """
    layout = BIDSLayout(dataset, validate=False)
    ents = _parse_entities(filters)
    matches = sorted(layout.get(**ents, return_type="obj"), key=lambda f: f.path)

    if not matches:
        lgr.warning("No files matched the provided filters %s", filters)
        return []

    lgr.info("Matched %d file(s) with filters %s", len(matches), filters)

    # counters per session dir → numbering restarts within each session
    counters: Dict[Path, set[int]] = defaultdict(set)  # {session_dir: {used_ints}}
    rename_pairs: List[Tuple[Path, Path]] = []         # list of (old_path, new_path)

    # ------------------ build rename plan ---------------------------------- #
    for f in matches:
        src_nifti = Path(f.path)
        session_dir = src_nifti.parents[2]

        num = _next_free_number(counters[session_dir])
        counters[session_dir].add(num)

        dst_nifti = _dup_path(src_nifti, num)
        rename_pairs.append((src_nifti, dst_nifti))

        json_path = _json_sidecar(src_nifti)
        if json_path.exists():
            rename_pairs.append((json_path, _dup_path(json_path, num)))
    # ------------------ execute renames ------------------------------------ #
    new_files: List[Path] = []
    for old, new in rename_pairs:
        new_files.append(new)
        rel_old = old.relative_to(dataset)
        rel_new = new.relative_to(dataset)

        if dry_run:
            lgr.info("[DRY‑RUN] would rename %s → %s", rel_old, rel_new)
            continue

        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        lgr.debug("renamed %s → %s", rel_old, rel_new)

    # ------------------ patch scans.tsv ------------------------------------ #
    tsv_updates: Dict[Path, Dict[str, str]] = defaultdict(dict)

    for old, new in rename_pairs:
        if not _is_nifti(old):
            continue                                     # skip JSON etc.

        session_dir = old.parents[1]                     # …/sub-XX/ses-YY
        rel_old = old.relative_to(session_dir).as_posix()
        rel_new = new.relative_to(session_dir).as_posix()
        tsv_path = next(session_dir.glob("*_scans.tsv"), None)
        if tsv_path:
            tsv_updates[tsv_path][rel_old] = rel_new

    for tsv_path, repl in tsv_updates.items():
        if dry_run:
            for o, n in repl.items():
                lgr.info("[DRY‑RUN] would patch %s : %s → %s",
                         tsv_path.relative_to(dataset), o, n)
            continue

        lgr.debug("patching %s", tsv_path.relative_to(dataset))
        with tsv_path.open(newline="") as fin, tempfile.NamedTemporaryFile(
            "w", delete=False, newline="", dir=str(tsv_path.parent)
        ) as fout:
            rdr = csv.reader(fin, delimiter="\t")
            wtr = csv.writer(fout, delimiter="\t", lineterminator="\n")

            header = next(rdr)
            filename_idx = header.index("filename")
            wtr.writerow(header)

            for row in rdr:
                row[filename_idx] = repl.get(row[filename_idx], row[filename_idx])
                wtr.writerow(row)

        shutil.move(fout.name, tsv_path)

    # ------------------ provenance ----------------------------------------- #
    if (
        commit_msg
        and not dry_run
        and use_datalad
        and HAVE_DATALAD
        and new_files
    ):
        lgr.info("Saving changes to DataLad with message: %s", commit_msg)
        dl.Dataset(str(dataset)).save(message=commit_msg)

    # ------------------ summary -------------------------------------------- #
    if dry_run:
        lgr.info("Would rename %d file(s) (plus side‑cars)", len(rename_pairs))
        lgr.info("Would patch %d scans.tsv files", len(tsv_updates))
    else:
        lgr.info("Renamed %d file(s) (plus side‑cars)", len(rename_pairs))
        lgr.info("Patched %d scans.tsv files", len(tsv_updates))

    return new_files
