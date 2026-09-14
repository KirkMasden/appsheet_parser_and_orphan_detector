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
(stage3_artifacts.py/stage4_artifacts.py/stage5_artifacts.py) for the
writing, unchanged, in the same way the untracked gate-check scripts
already do.

Stages 0, 1, and 2 have no artifact writer today -- there is no
stage2_artifacts.py (see stage2.py's own module docstring for why building
one is a separate piece of work, not attempted here). They still run when
selected, because stage 3 depends on stage 0/1's work and every later
stage depends on stage 3's, but they write nothing; this module says so on
each run rather than passing over them silently.
"""

import argparse
import os
import sys

from .loader import discover_capture_files
from .stage0 import run_stage0
from .stage1 import run_stage1
from .stage2 import run_stage2
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
        help="Directory holding the app-side parse's appsheet_columns.csv. Read by stage 5. Optional.",
    )
    parser.add_argument(
        "--app-export-html",
        default=None,
        help="Path to the app's HTML documentation export. Read by stage 5 for provenance. Optional.",
    )
    parser.add_argument(
        "--declarations",
        default=None,
        help="Path to a declarations JSON file. Read by stages 4 and 5. Optional.",
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
            run_stage2(formulas_path, values_path)
            print("stage 2: ran; produces no artifact file (no stage2_artifacts.py exists yet)")

        elif stage == 3:
            result = run_stage3(formulas_path, values_path)
            paths = write_stage3_artifacts(result, args.output_dir)
            print("stage 3: wrote")
            for path in paths.values():
                print(f"  {path}")

        elif stage == 4:
            result = run_stage4(formulas_path, values_path, args.declarations)
            paths = write_stage4_artifacts(result, args.output_dir)
            print("stage 4: wrote")
            for path in paths.values():
                print(f"  {path}")

        elif stage == 5:
            result = run_stage5(
                formulas_path,
                values_path,
                appside_parse_dir=args.appside_parse_dir,
                app_export_html_path=args.app_export_html,
                declarations_path=args.declarations,
            )
            paths = write_stage5_artifacts(result, args.output_dir)
            print("stage 5: wrote")
            for path in paths.values():
                print(f"  {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
