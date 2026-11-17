"""Reports what a workspace input folder (apps/<name>/) actually holds,
and whether its app export and its capture belong together.

The workspace's input layout (see README.md) is deliberately FLAT: one
folder per set of files to be parsed, holding all six prepared files
undifferentiated --

    apps/<name>/
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
files), but it has one real cost: a folder holding four files looks, at a
glance, exactly like a folder holding all six -- a missing half is
otherwise invisible. This module says plainly what it found and what it
did not, so that gap surfaces immediately rather than downstream as a
confusing failure (or, worse, no failure at all).

A folder can also hold all six files and still be wrong: an export from
one app beside a capture of an unrelated workbook, or beside .txt files
pasted from another app. When the export is present, this module runs the
pairing check (pairing.py): the worksheet names the export gives for its
Google tables against the capture's sheet names -- the same comparison
run.py makes -- and, here only, the view and action names in the three
.txt files against the export's (run.py reads none of those files). It
warns when some names are missing, and exits with status 3 when none of
the worksheet names, or almost none of a .txt file's names, are present,
unless --allow-mismatch is given. That check reads the export, one
capture file and the .txt files; everything else here is the directory
listing only. Nothing here writes anything.
"""

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

from .loader import FORMULAS_GLOB_PATTERN, VALUES_GLOB_PATTERN
from .pairing import (
    OVERRIDE_OPTION,
    PairingResult,
    check_pairing,
    check_txt_pairing,
    find_capture_file_for_sheet_names,
    format_pairing,
    format_txt_pairing,
)

APP_SIDE_FILES: Tuple[str, ...] = (
    "Application Documentation.html",
    "actions.txt",
    "views1.txt",
    "views2.txt",
)
# An optional app-side file: written by hand, listing the actions the user's
# bots call (see CLAUDE.md). Recognized, and reported as found or "not found
# (optional)", but never counted in the required totals and never a reason
# for the folder to be called incomplete.
OPTIONAL_APP_SIDE_FILES: Tuple[str, ...] = ("bot_actions.txt",)
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
    against the input folder's own entries -- never against the
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
    optional_found: Tuple[str, ...] = ()
    optional_missing: Tuple[str, ...] = ()

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

    optional_found = tuple(f for f in OPTIONAL_APP_SIDE_FILES if f in entries_set)
    optional_missing = tuple(f for f in OPTIONAL_APP_SIDE_FILES if f not in entries_set)
    known = frozenset(APP_SIDE_FILES) | frozenset(OPTIONAL_APP_SIDE_FILES)
    unrecognized = tuple(sorted(f for f in entries if f not in known and f not in recognized_capture))
    return SnapshotContents(
        snapshot_dir=snapshot_dir,
        app_side_found=app_side_found,
        app_side_missing=app_side_missing,
        capture_slots=capture_slots,
        unrecognized=unrecognized,
        optional_found=optional_found,
        optional_missing=optional_missing,
    )


def format_report(contents: SnapshotContents) -> str:
    lines = [f"input folder: {contents.snapshot_dir}", ""]

    lines.append(f"app-side files: {len(contents.app_side_found)}/{len(APP_SIDE_FILES)} found")
    for f in APP_SIDE_FILES:
        status = "found" if f in contents.app_side_found else "MISSING"
        lines.append(f"  - {f}: {status}")

    for f in OPTIONAL_APP_SIDE_FILES:
        lines.append(f"optional: {f}: " + ("found" if f in contents.optional_found else "not found (optional)"))

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
            "sheet_derivation's own stages can still run against this folder, "
            "but there is no app-side data to join against (stage 5) or parse "
            "with master_parser_and_orphan_detector.py."
        )
    elif contents.app_side_complete and not contents.capture_complete:
        lines.append(
            "App-side export only: the sheet capture is incomplete or absent -- "
            "master_parser_and_orphan_detector.py can still run against this "
            "folder, but sheet_derivation's stages have no capture to read."
        )
    else:
        lines.append("Neither half is complete.")

    return "\n".join(lines)


EXIT_PAIRING_STOPPED = 3


def pairing_for(contents: SnapshotContents) -> Optional[PairingResult]:
    """The pairing check for this folder, or None when there is nothing to
    pair: no export, or no single capture file to read sheet names from
    (both already reported by format_report)."""
    if "Application Documentation.html" not in contents.app_side_found:
        return None
    capture_path = find_capture_file_for_sheet_names(contents.snapshot_dir)
    if capture_path is None:
        return None
    return check_pairing(contents.snapshot_dir, capture_path=capture_path)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        prog="python -m sheet_derivation.snapshot",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("snapshot_dir", metavar="input_folder", help="An apps/<name>/ folder to inspect.")
    parser.add_argument(
        OVERRIDE_OPTION,
        action="store_true",
        help=(
            "Report a complete mismatch between the export's worksheet names and the capture's "
            "sheet names as a warning instead of stopping. Use only when you are certain the "
            "export and the capture belong together."
        ),
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(args.snapshot_dir):
        print(f"error: not a directory: {args.snapshot_dir}", file=sys.stderr)
        return 2

    contents = inspect_snapshot(args.snapshot_dir)
    print(format_report(contents))

    pairing = pairing_for(contents)
    txt_results = (
        check_txt_pairing(contents.snapshot_dir)
        if "Application Documentation.html" in contents.app_side_found else []
    )
    if pairing is None and not txt_results:
        return 0
    print("")
    stops = False
    if pairing is not None:
        for line in format_pairing(pairing, allow_mismatch=args.allow_mismatch):
            print(line)
        stops = stops or pairing.stops
    for result in txt_results:
        for line in format_txt_pairing(result, allow_mismatch=args.allow_mismatch):
            print(line)
        stops = stops or result.stops
    if stops and not args.allow_mismatch:
        return EXIT_PAIRING_STOPPED
    return 0


if __name__ == "__main__":
    sys.exit(main())
