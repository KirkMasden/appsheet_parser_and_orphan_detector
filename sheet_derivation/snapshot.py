"""Reports what a workspace apps/<snapshot>/ directory actually holds.

The workspace's input layout (see README.md) is deliberately FLAT: one
directory per snapshot, holding all six prepared files undifferentiated --

    apps/<snapshot>/
        Application Documentation.html
        actions.txt
        views1.txt
        views2.txt
        <spreadsheet name>_formulas_<timestamp>.json
        <spreadsheet name>_values_<timestamp>.json

The last two are recognized by the same pattern discover_capture_files()
in loader.py uses (FORMULAS_GLOB_PATTERN/VALUES_GLOB_PATTERN, imported
from there rather than restated here) -- sheet_capture.gs's own real
output names them this way, and a literal `formulas.json`/`values.json`
still matches too, so neither this module nor a user has to rename
anything the capture script actually wrote.

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
import fnmatch
import os
import sys
from dataclasses import dataclass
from typing import Tuple

from .loader import FORMULAS_GLOB_PATTERN, VALUES_GLOB_PATTERN

APP_SIDE_FILES: Tuple[str, ...] = (
    "Application Documentation.html",
    "actions.txt",
    "views1.txt",
    "views2.txt",
)
# Two logical slots, not two fixed filenames -- each is recognized by
# glob pattern (see FORMULAS_GLOB_PATTERN/VALUES_GLOB_PATTERN's own
# docstring in loader.py), the same pattern discover_capture_files() uses,
# so a folder this module calls complete is one the stages can actually
# load.
CAPTURE_SLOT_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("formulas", FORMULAS_GLOB_PATTERN),
    ("values", VALUES_GLOB_PATTERN),
)


@dataclass(frozen=True)
class CaptureSlotResult:
    """One capture slot ('formulas' or 'values'), matched by glob pattern
    against the snapshot directory's own entries -- never against the
    filesystem directly (unlike discover_capture_files()), since this
    module already has the one `os.listdir()` it needs and matching
    in-memory keeps this a pure function of that one listing."""

    label: str
    pattern: str
    matches: Tuple[str, ...]

    @property
    def state(self) -> str:
        """'missing' (0 matches), 'found' (exactly 1), or 'ambiguous' (2+)
        -- three states, not a found/missing boolean, because 2+ matches
        is a real, distinct problem a user must resolve by hand (delete or
        rename all but one) and is not safe to silently treat as either
        found or missing."""
        if not self.matches:
            return "missing"
        if len(self.matches) == 1:
            return "found"
        return "ambiguous"


@dataclass(frozen=True)
class SnapshotContents:
    snapshot_dir: str
    app_side_found: Tuple[str, ...]
    app_side_missing: Tuple[str, ...]
    capture_slots: Tuple[CaptureSlotResult, ...]
    unrecognized: Tuple[str, ...]

    @property
    def app_side_complete(self) -> bool:
        return not self.app_side_missing

    @property
    def capture_complete(self) -> bool:
        return all(slot.state == "found" for slot in self.capture_slots)

    @property
    def capture_ambiguous(self) -> bool:
        return any(slot.state == "ambiguous" for slot in self.capture_slots)


def inspect_snapshot(snapshot_dir: str) -> SnapshotContents:
    """Lists `snapshot_dir` (one level, no recursion -- the layout is flat
    by design) and sorts every entry into exactly one of: a recognized
    app-side file, a match against one of the two capture slot patterns,
    or unrecognized. Missing files are reported by name (or, for a
    capture slot, by the pattern that found nothing), not merely by an
    incomplete-count -- and a pattern matching more than one file is
    reported as its own state, never silently resolved to one file."""
    entries = sorted(os.listdir(snapshot_dir))
    entries_set = set(entries)
    app_side_found = tuple(f for f in APP_SIDE_FILES if f in entries_set)
    app_side_missing = tuple(f for f in APP_SIDE_FILES if f not in entries_set)

    capture_slots = tuple(
        CaptureSlotResult(label, pattern, tuple(sorted(fnmatch.filter(entries, pattern))))
        for label, pattern in CAPTURE_SLOT_PATTERNS
    )
    recognized_capture = set()
    for slot in capture_slots:
        recognized_capture.update(slot.matches)

    unrecognized = tuple(
        sorted(f for f in entries if f not in frozenset(APP_SIDE_FILES) and f not in recognized_capture)
    )
    return SnapshotContents(
        snapshot_dir=snapshot_dir,
        app_side_found=app_side_found,
        app_side_missing=app_side_missing,
        capture_slots=capture_slots,
        unrecognized=unrecognized,
    )


def format_report(contents: SnapshotContents) -> str:
    lines = [f"snapshot directory: {contents.snapshot_dir}", ""]

    lines.append(f"app-side files: {len(contents.app_side_found)}/{len(APP_SIDE_FILES)} found")
    for f in APP_SIDE_FILES:
        status = "found" if f in contents.app_side_found else "MISSING"
        lines.append(f"  - {f}: {status}")

    found_slots = sum(1 for slot in contents.capture_slots if slot.state == "found")
    lines.append(f"capture files: {found_slots}/{len(contents.capture_slots)} found")
    for slot in contents.capture_slots:
        if slot.state == "found":
            lines.append(f"  - {slot.label}: found ({slot.matches[0]})")
        elif slot.state == "missing":
            lines.append(f"  - {slot.label}: MISSING (no file matching {slot.pattern!r} -- "
                         f"go find the capture script's {slot.label} output and add it here)")
        else:
            lines.append(f"  - {slot.label}: AMBIGUOUS ({len(slot.matches)} files match "
                         f"{slot.pattern!r}, and only one is allowed): {list(slot.matches)}")

    if contents.unrecognized:
        lines.append(f"present but not recognized: {len(contents.unrecognized)}")
        for f in contents.unrecognized:
            lines.append(f"  - {f}")
    else:
        lines.append("present but not recognized: none")

    lines.append("")
    if contents.capture_ambiguous:
        for slot in contents.capture_slots:
            if slot.state == "ambiguous":
                lines.append(
                    f"AMBIGUOUS: more than one file matches the {slot.label} pattern "
                    f"({slot.pattern!r}) -- remove or rename all but one before running "
                    f"the stages, which refuse rather than guess which one you meant: "
                    f"{list(slot.matches)}"
                )
    elif contents.app_side_complete and contents.capture_complete:
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
