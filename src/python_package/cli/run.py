from __future__ import annotations

import argparse
import logging
import os
import json
import importlib.resources as pkg_resources
import pathlib as Path
import coloredlogs
import sys
import importlib.util
from ..switch_duplicate import switch_duplicate
from ..use_duplicate import use_duplicate
from ..clean_duplicates import clean_duplicates
from ..remove_duplicates import remove_duplicates
from concurrent.futures import ThreadPoolExecutor  # for background thread

lgr = logging.getLogger(__name__)

def parse_args():

    p = argparse.ArgumentParser(description="bidscycle - BIDS renaming of duplicate BIDS scans ")
    p.add_argument("command",
                    help="""
                        Command to run:
                        - switch_duplicate: start the MWL server
                        - use_duplicate: query the MWL db
                        - clean_duplicates: run tests for MWL
                    """,
                    choices=["switch_duplicate", "use_duplicate", "clean_duplicates"],
                    )

    p.add_argument("--subject", "-sub", type=str, help="Subject ID")
    p.add_argument("--session", "-ses", type=str, help="Session ID")
    p.add_argument("--acquisition", "-acq", type=str, help="Acquisition ID")
    p.add_argument("--run", "-run", type=int, help="Run ID")
    p.add_argument("--label", "-lbl", type=str, help="Bids Label")
    p.add_argument("--dublicates", "-dup", type=lambda x: [i.strip() for i in x.split(',') if i.strip()], help="BIDS duplicate number(s) as a comma-separated list or a single value")
    p.add_argument("--nodatalad", help="Don't use Datalad", action="store_true")
    p.add_argument("--verbose", "-v", help="Verbose", default=False, action="store_true")

    return p.parse_args()

def main() -> None:
    args = parse_args()

    DEBUG = bool(os.environ.get("DEBUG", False))
    DEBUG = args.verbose or DEBUG
    level = logging.DEBUG if DEBUG else logging.INFO
    coloredlogs.install(level=level)

    if (args.command == "remove_duplicates"):
        remove_duplicates(subject=args.subject,
                          session=args.session,
                          acquisition=args.acquisition,
                          run=args.run,
                          label=args.label,
                          duplicates=args.dublicates,
                          dry_run=args.dry_run,
                          commit_msg=args.commit_msg,
                          keep_pattern=args.keep_pattern,
                          nodatalad=args.nodatalad,
                          verbose=args.verbose
        )

    if (args.command == "switch_duplicate"):
        switch_duplicate(subject=args.subject,
            session=args.session,
            acquisition=args.acquisition,
            run=args.run,
            label=args.label,
            duplicate=args.dublicate,
            nodatalad=args.nodatalad,
            verbose=args.verbose

        )

    if (args.command == "use_duplicate"):
        use_duplicate(
            subject=args.subject,
            session=args.session,
            acquisition=args.acquisition,
            run=args.run,
            label=args.label,
            duplicate=args.dublicate,
            nodatalad=args.nodatalad,
            verbose=args.verbose
        )

    if (args.command == "clean_duplicates"):

        clean_duplicates(
            subject=args.subject,
            session=args.session,
            label=args.label,
            duplicate=args.dublicate,
            nodatalad=args.nodatalad,
            verbose=args.verbose
        )


if __name__ == "__main__":
    main()
