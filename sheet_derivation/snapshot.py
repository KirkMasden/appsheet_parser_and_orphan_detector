"""Reports what a workspace apps/<snapshot>/ directory actually holds.

The workspace's input layout (see README.md) is deliberately FLAT: one
directory per snapshot, holding all six prepared files undifferentiated --

    apps/<snapshot>/
        Application Documentation.html
        actions.txt
        views1.txt
        views2.txt
        formulas.json
        values.json

Flat is the right shape for the step a human does by hand (gathering the
files), but it has one real cost: a directory holding four files looks,
at a glance, exactly like a directory holding all six -- a missing half
is otherwise invisible. This module's only job is to say plainly what it
found and what it did not, so that gap surfaces immediately rather than
downstream as a confusing failure (or, worse, no failure at all: nothing
else in this project's own tooling reads all six files together, so a
half-empty snapshot can otherwise go unnoticed indefinitely).

Nothing here reads file CONTENT and nothing here writes anything --
existence and filename recognition only. Computing anything about what a
file contains is a job for the parsers/stages that actually read it.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Tuple

APP_SIDE_FILES: Tuple[str, ...] = (
    "Application Documentation.html",
    "actions.txt",
    "views1.txt",
    "views2.txt",
)
CAPTURE_FILES: Tuple[str, ...] = (
    "formulas.json",
    "values.json",
)
KNOWN_FILES = frozenset(APP_SIDE_FILES) | frozenset(CAPTURE_FILES)


@dataclass(frozen=True)
class SnapshotContents:
    snapshot_dir: str
    app_side_found: Tuple[str, ...]
    app_side_missing: Tuple[str, ...]
    capture_found: Tuple[str, ...]
    capture_missing: Tuple[str, ...]
    unrecognized: Tuple[str, ...]

    @property
    def app_side_complete(self) -> bool:
        return not self.app_side_missing

    @property
    def capture_complete(self) -> bool:
        return not self.capture_missing


def inspect_snapshot(snapshot_dir: str) -> SnapshotContents:
    """Lists `snapshot_dir` (one level, no recursion -- the layout is flat
    by design) and sorts every entry into exactly one of: a recognized
    app-side file, a recognized capture file, or unrecognized. Missing
    files are reported by name, not merely by an incomplete-count."""
    entries = set(os.listdir(snapshot_dir))
    app_side_found = tuple(f for f in APP_SIDE_FILES if f in entries)
    app_side_missing = tuple(f for f in APP_SIDE_FILES if f not in entries)
    capture_found = tuple(f for f in CAPTURE_FILES if f in entries)
    capture_missing = tuple(f for f in CAPTURE_FILES if f not in entries)
    unrecognized = tuple(sorted(f for f in entries if f not in KNOWN_FILES))
    return SnapshotContents(
        snapshot_dir=snapshot_dir,
        app_side_found=app_side_found,
        app_side_missing=app_side_missing,
        capture_found=capture_found,
        capture_missing=capture_missing,
        unrecognized=unrecognized,
    )


def format_report(contents: SnapshotContents) -> str:
    lines = [f"snapshot directory: {contents.snapshot_dir}", ""]

    lines.append(f"app-side files: {len(contents.app_side_found)}/{len(APP_SIDE_FILES)} found")
    for f in APP_SIDE_FILES:
        status = "found" if f in contents.app_side_found else "MISSING"
        lines.append(f"  - {f}: {status}")

    lines.append(f"capture files: {len(contents.capture_found)}/{len(CAPTURE_FILES)} found")
    for f in CAPTURE_FILES:
        status = "found" if f in contents.capture_found else "MISSING"
        lines.append(f"  - {f}: {status}")

    if contents.unrecognized:
        lines.append(f"present but not recognized: {len(contents.unrecognized)}")
        for f in contents.unrecognized:
            lines.append(f"  - {f}")
    else:
        lines.append("present but not recognized: none")

    lines.append("")
    if contents.app_side_complete and contents.capture_complete:
        lines.append("Complete: both the app-side export and the sheet capture are present.")
    elif contents.capture_complete and not contents.app_side_complete:
        lines.append(
            "Sheet capture only: the app-side export is incomplete or absent -- "
            "sheet_derivation's own stages can still run against this snapshot, "
            "but there is no app-side data to join against (stage 5) or parse "
            "with master_parser_and_orphan_detector.py."
        )
    elif contents.app_side_complete and not contents.capture_complete:
        lines.append(
            "App-side export only: the sheet capture is incomplete or absent -- "
            "master_parser_and_orphan_detector.py can still run against this "
            "snapshot, but sheet_derivation's stages have no capture to read."
        )
    else:
        lines.append("Neither half is complete.")

    return "\n".join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        prog="python -m sheet_derivation.snapshot",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("snapshot_dir", help="An apps/<snapshot>/ directory to inspect.")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.snapshot_dir):
        print(f"error: not a directory: {args.snapshot_dir}", file=sys.stderr)
        return 2

    contents = inspect_snapshot(args.snapshot_dir)
    print(format_report(contents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
