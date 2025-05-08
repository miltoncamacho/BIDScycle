#!/usr/bin/env python3
# src/bidscycle/cli/run.py
"""
Command‑line interface for the *bidscycle* toolkit.

Usage examples
--------------
# duplicate every T1w of sub‑03, appending “__dup-N.nii.gz”, and commit
bidscycle create-duplicates /data/bids \
    -f subject=03 -f suffix=T1w        \
    --duplicates N                     \
    --commit-msg "Added duplicates"

# activate duplicate 02 for a specific functional run
bidscycle switch-duplicate /data/bids \
    --subject 01 --session 1a --run 02 --duplicate 02

# remove obsolete duplicates of sub‑01
bidscycle clean-duplicates /data/bids --subject 01
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import coloredlogs

#  library functions
from bidscycle.create_duplicates import create_duplicates
from bidscycle.switch_duplicate import switch_duplicate
# from bidscycle.clean_duplicates import clean_duplicates


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _install_logging(verbosity: int) -> None:
    """Map -v /-vv /-vvv to WARNING / INFO / DEBUG."""
    level = (
        logging.WARNING
        if verbosity == 0
        else logging.INFO
        if verbosity == 1
        else logging.DEBUG
    )
    coloredlogs.install(level=level, fmt="%(levelname)s │ %(message)s")


def _csv(value: str) -> list[str]:
    """Convert `a,b,c` → ['a','b','c'] (strip blanks)."""
    return [v.strip() for v in value.split(",") if v.strip()]


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bidscycle",
        description="Renaming, selecting and cleaning duplicate BIDS scans",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # --------------------------- create‑duplicates -------------------------- #
    dup = sub.add_parser(
        "create-duplicates",
        help="Duplicate files that match entity filters",
    )
    dup.add_argument("dataset", type=Path, help="Root of the BIDS dataset")
    dup.add_argument("-f", "--filter", action="append", required=True, metavar="entity=value[,value2]", help="Repeatable BIDS entity filter (e.g. -f subject=01 -f session=01 -f run=1,3 -f task=rest)")
    dup.add_argument("--commit-msg", "-c", help="If given, DataLad will save the new files")
    dup.add_argument("--dry-run", action="store_true", help="Show what would change but do not change anything")
    dup.add_argument("--no-datalad", action="store_true", help="Skip DataLad save step")
    dup.add_argument("-v", "--verbose", action="count", default=0, help="Increase log level")
    dup.set_defaults(func=_cmd_create_duplicates)

    # --------------------------- switch‑duplicate --------------------------- #
    sw = sub.add_parser(
        "switch-duplicate",
        help="Activate/deactivate one duplicate scan (rename in place)",
    )
    sw.add_argument("dataset", type=Path, help="Root of the BIDS dataset")
    sw.add_argument("-f", "--filter", action="append", required=True, metavar="entity=value[,value2]", help="Repeatable BIDS entity filter (e.g. -f subject=01 -f session=01 -f run=1,3 -f task=rest)")
    sw.add_argument("--commit-msg", "-c", help="If given, DataLad will save the new files")
    sw.add_argument("--dry-run", action="store_true", help="Show what would change but do not change anything")
    sw.add_argument("--no-datalad", action="store_true")
    sw.add_argument("-v", "--verbose", action="count", default=0)
    sw.set_defaults(func=_cmd_switch_duplicate)

    # --------------------------- clean‑duplicates --------------------------- #
    cl = sub.add_parser(
        "clean-duplicates",
        help="Remove obsolete duplicate scans",
    )
    cl.add_argument("dataset", type=Path, help="Root of the BIDS dataset")
    cl.add_argument("-f", "--filter", action="append", required=True, metavar="entity=value[,value2]", help="Repeatable BIDS entity filter (e.g. -f subject=01 -f session=01 -f run=1,3 -f task=rest)")
    cl.add_argument("--duplicate", "-d", required=True)
    cl.add_argument("--commit-msg", "-c", help="If given, DataLad will save the new files")
    cl.add_argument("--dry-run", action="store_true", help="Show what would change but do not change anything")
    cl.add_argument("--no-datalad", action="store_true")
    cl.add_argument("-v", "--verbose", action="count", default=0)
    cl.set_defaults(func=_cmd_clean_duplicates)

    return p


# --------------------------------------------------------------------------- #
# dispatchers                                                                 #
# --------------------------------------------------------------------------- #
def _cmd_create_duplicates(args: argparse.Namespace) -> None:
    _install_logging(args.verbose)
    create_duplicates(
        dataset=args.dataset,
        filters=args.filter,
        commit_msg=args.commit_msg,
        dry_run=args.dry_run,
        use_datalad=not args.no_datalad,
    )


def _cmd_switch_duplicate(args: argparse.Namespace) -> None:
    _install_logging(args.verbose)
    switch_duplicate(
        dataset=args.dataset,
        filters=args.filter,
        commit_msg=args.commit_msg,
        dry_run=args.dry_run,
        use_datalad=not args.no_datalad,
    )


def _cmd_clean_duplicates(args: argparse.Namespace) -> None:
    _install_logging(args.verbose)
    clean_duplicates(
        dataset=args.dataset,
        subject=args.subject,
        session=args.session,
        label=args.label,
        duplicate=args.duplicate,
        use_datalad=not args.no_datalad,
    )


# --------------------------------------------------------------------------- #
# entry point                                                                 #
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
