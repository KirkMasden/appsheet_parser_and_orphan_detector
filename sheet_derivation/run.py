"""User-facing entry point: runs sheet-derivation stages 0-5 against a
capture and writes each stage's own artifacts to disk.

Invoked as:

    python -m sheet_derivation.run <capture_dir> <output_dir> [options]

Before this module existed, write_stage3_artifacts/write_stage4_artifacts/
write_stage5_artifacts (stage3_artifacts.py/stage4_artifacts.py/
stage5_artifacts.py) had no caller anywhere in this repository -- their
only callers were gate-check scripts living outside the repo, untracked,
plus tests writing to throwaway temp directories. Running `python -m
sheet_derivation.stage3 <capture_dir>` printed a summary to stdout and
wrote no file. A user who only has this repository could not produce the
sheet-side artifacts at all.

This module fixes exactly that. It computes nothing itself: it calls the
existing run_stageN functions (stage0.py through stage5.py) for the
computation and the existing write_stageN_artifacts functions
(stage2_artifacts.py/stage3_artifacts.py/stage4_artifacts.py/
stage5_artifacts.py) for the writing, unchanged, in the same way the
untracked gate-check scripts already do.

Stages 0 and 1 have no artifact writer -- neither produces a standalone
artifact of its own (see their own module docstrings). They still run
when selected, because every later stage depends on their work, but they
write nothing; this module says so on each run rather than passing over
them silently.

Before any stage runs, the export/capture pairing check (pairing.py)
compares the worksheet names the app's HTML export gives for its Google
tables with the capture's sheet names, and stops the run when none of
them match, unless --allow-mismatch is given.

Stage 5 needs the app-side results. When --appside-parse-dir is not
given and the output folder follows the documented layout
(output/<name>/sheet, with output/<name>/app beside it), the app-side
results are taken from that app folder, and a line says so. When none
can be found, a WARNING says the join will be ABSENT and how to fix it
-- an ABSENT join is never written without one. Likewise, when
--app-export-html is not given, the export is taken from the input
folder, where Application Documentation.html sits beside the capture.
"""

import argparse
import os
import sys

from .appside_parse import AppSideParseError, discover_appside_columns_csv
from .loader import discover_capture_files
from .pairing import OVERRIDE_OPTION, check_pairing, find_export_html, format_pairing
from .stage0 import run_stage0
from .stage1 import run_stage1
from .stage2 import run_stage2
from .stage2_artifacts import write_stage2_artifacts
from .stage3 import run_stage3
from .stage3_artifacts import write_stage3_artifacts
from .stage4 import run_stage4
from .stage4_artifacts import write_stage4_artifacts
from .stage5 import run_stage5
from .stage5_artifacts import write_stage5_artifacts

ALL_STAGES = (0, 1, 2, 3, 4, 5)


def _parse_stages(raw: str):
    """'3,4,5' -> (3, 4, 5); always returned in ascending order regardless
    of the order written, since later stages depend on earlier ones.
    Raises ValueError, naming the bad token, on anything not an integer in
    range(0, 6)."""
    stages = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            stage = int(token)
        except ValueError:
            raise ValueError(f"not an integer: {token!r}")
        if stage not in ALL_STAGES:
            raise ValueError(f"not a known stage (0-5): {stage}")
        stages.add(stage)
    if not stages:
        raise ValueError("no stages given")
    return tuple(sorted(stages))


EXIT_PAIRING_STOPPED = 3


def find_appside_results_beside(output_dir: str):
    """The documented layout's app-side folder for `output_dir`:
    `<parent>/app` when `output_dir` is itself named `sheet` and that app
    folder holds `appsheet_columns.csv`. None otherwise -- no other
    location is guessed."""
    out = os.path.abspath(output_dir)
    if os.path.basename(out) != "sheet":
        return None
    candidate = os.path.join(os.path.dirname(out), "app")
    try:
        discover_appside_columns_csv(candidate)
    except AppSideParseError:
        return None
    return candidate


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        prog="python -m sheet_derivation.run",
        description=(
            "Runs sheet-derivation stages 0-5 against a capture and writes "
            "each stage's own JSONL/CSV artifacts to disk."
        ),
    )
    parser.add_argument(
        "capture_dir",
        help="Directory holding the capture's *formulas*.json and *values*.json files.",
    )
    parser.add_argument(
        "output_dir",
        help="Directory to write stage artifacts into. Created if it does not exist.",
    )
    parser.add_argument(
        "--stages",
        default="0,1,2,3,4,5",
        help="Comma-separated subset of stages to run, e.g. '3,4,5'. Default: all stages, 0 through 5.",
    )
    parser.add_argument(
        "--appside-parse-dir",
        default=None,
        help=(
            "Directory holding the app-side parse's appsheet_columns.csv. Read by stage 5. Optional: "
            "when omitted and the output folder is output/<name>/sheet, output/<name>/app is used "
            "if it holds app-side results."
        ),
    )
    parser.add_argument(
        "--app-export-html",
        default=None,
        help=(
            "Path to the app's HTML documentation export. Read by the pairing check and by stage 5 "
            "(worksheet names, provenance). Optional: when omitted, the capture directory's own "
            "Application Documentation.html is used if present."
        ),
    )
    parser.add_argument(
        "--declarations",
        default=None,
        help="Path to a declarations JSON file. Read by stages 4 and 5. Optional.",
    )
    parser.add_argument(
        OVERRIDE_OPTION,
        action="store_true",
        help=(
            "Continue even when none of the worksheet names in the app's export appear in the "
            "capture. Use only when you are certain the export and the capture belong together."
        ),
    )
    args = parser.parse_args(argv)

    try:
        stages = _parse_stages(args.stages)
    except ValueError as exc:
        print(f"error: --stages: {exc}", file=sys.stderr)
        return 2

    print(f"capture directory: {args.capture_dir}")
    print(f"output directory: {args.output_dir}")

    formulas_path, values_path = discover_capture_files(args.capture_dir)

    app_export_html = args.app_export_html
    if app_export_html is None:
        app_export_html = find_export_html(args.capture_dir)
        if app_export_html is not None:
            print(f"app export: using {app_export_html} (found in the capture directory)")

    pairing = check_pairing(args.capture_dir, export_path=app_export_html, capture_path=values_path)
    for line in format_pairing(pairing, allow_mismatch=args.allow_mismatch):
        print(line, file=sys.stderr if pairing.stops and not args.allow_mismatch else sys.stdout)
    if pairing.stops and not args.allow_mismatch:
        return EXIT_PAIRING_STOPPED

    appside_parse_dir = args.appside_parse_dir
    if 5 in stages and appside_parse_dir is None:
        appside_parse_dir = find_appside_results_beside(args.output_dir)
        if appside_parse_dir is not None:
            print(f"app-side results: using {appside_parse_dir} (found beside the output folder)")
        else:
            print(
                "WARNING: no app-side results found, so stage 5's join will be ABSENT (its CSVs "
                "will hold headers only). To fix: parse the app first so that its results are in "
                "the 'app' folder beside this 'sheet' output folder (output/<name>/app next to "
                "output/<name>/sheet), or pass --appside-parse-dir <folder holding "
                "appsheet_columns.csv>.",
                file=sys.stderr,
            )
    # write_stageN_artifacts each create output_dir themselves, but a run
    # restricted to --stages 0,1,2 (no artifact writer) would otherwise
    # never create it, contradicting this entry point's own contract.
    os.makedirs(args.output_dir, exist_ok=True)

    for stage in stages:
        print(f"stage {stage}: running...")

        if stage == 0:
            run_stage0(formulas_path, values_path)
            print("stage 0: ran; produces no artifact file")

        elif stage == 1:
            run_stage1(formulas_path, values_path)
            print("stage 1: ran; produces no artifact file")

        elif stage == 2:
            result = run_stage2(formulas_path, values_path)
            paths = write_stage2_artifacts(result, args.output_dir)
            print("stage 2: wrote")
            for path in paths.values():
                print(f"  {path}")

        elif stage == 3:
            result = run_stage3(formulas_path, values_path)
            paths = write_stage3_artifacts(result, args.output_dir)
            print("stage 3: wrote")
            for path in paths.values():
                print(f"  {path}")

        elif stage == 4:
            result = run_stage4(
                formulas_path, values_path, args.declarations, app_export_html_path=app_export_html
            )
            paths = write_stage4_artifacts(result, args.output_dir)
            print("stage 4: wrote")
            for path in paths.values():
                print(f"  {path}")

        elif stage == 5:
            result = run_stage5(
                formulas_path,
                values_path,
                appside_parse_dir=appside_parse_dir,
                app_export_html_path=app_export_html,
                declarations_path=args.declarations,
            )
            paths = write_stage5_artifacts(result, args.output_dir)
            print("stage 5: wrote")
            for path in paths.values():
                print(f"  {path}")
            if result.join.present:
                print(f"stage 5: table-to-tab pairing {result.join.tab_pairing}")
            else:
                print(
                    f"WARNING: stage 5's join is ABSENT: {result.join.reliability_condition}",
                    file=sys.stderr,
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
