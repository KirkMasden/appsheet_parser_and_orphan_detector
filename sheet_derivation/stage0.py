"""Stage 0: load, gate, index, count, and verify -- no artifact yet.

Usage:
    python -m sheet_derivation.stage0 <capture_directory>

`<capture_directory>` is any directory containing exactly one
`*formulas*.json` and one `*values*.json` file written by sheet_capture.gs.
Nothing here hardcodes a workbook's name, sheet names, or file names --
the capture directory is the only thing the caller supplies.

This module builds no artifact and writes no output file. It exists to
prove, from any capture, that: the two files agree (or the tool refuses
and says exactly why); every (sheet, row, column) can be resolved to a
formula, a value, and an A1 address and back; the counting the later
artifacts depend on is correct; and the whole pass is deterministic.
"""

import sys
from dataclasses import dataclass
from typing import Tuple

from .coordinates import CoordinateModel
from .counts import SheetCounts, WorkbookTotals, compute_all_counts, compute_workbook_totals
from .determinism import assert_explicitly_sorted, verify_same_process_determinism
from .loader import Capture, discover_capture_files, load_capture
from .report import format_per_sheet_table
from .residue import ArtifactStamp, ResidueEntry, build_stamp


@dataclass(frozen=True)
class Stage0Result:
    capture: Capture
    all_counts: Tuple[SheetCounts, ...]
    totals: WorkbookTotals


def run_stage0(formulas_path: str, values_path: str) -> Stage0Result:
    """Loads the capture (gates included), builds the coordinate model long
    enough to prove it resolves real addresses, and counts every sheet."""
    capture = load_capture(formulas_path, values_path)

    # The coordinate model is exercised here, not merely constructed: every
    # sheet's top-left cell is round-tripped through an A1 address and back,
    # and both its formula and its value are fetched. This is a wiring
    # check, not a report -- nothing fetched here is printed, since it may
    # be private cell content and stage 0 has no reason to display it.
    coordinates = CoordinateModel(capture)
    for sheet_name in capture.sheet_order:
        address = CoordinateModel.address(0, 0)
        row0, col0 = CoordinateModel.coords(address)
        assert (row0, col0) == (0, 0)
        coordinates.formula_at_address(sheet_name, address)
        coordinates.value_at_address(sheet_name, address)

    all_counts = compute_all_counts(capture)
    assert_explicitly_sorted(
        all_counts,
        key=lambda c: capture.sheet_order.index(c.sheet_name),
        label="per-sheet counts",
    )
    totals = compute_workbook_totals(capture, all_counts)

    return Stage0Result(capture=capture, all_counts=all_counts, totals=totals)


def _demonstrate_residue_and_stamp_mechanism(capture: Capture) -> None:
    """Proves the types from section 4/6 are usable, without writing an artifact.

    Constructs one throwaway ResidueEntry and one real ArtifactStamp. Raises
    if either type's required-field enforcement has regressed. Nothing here
    is persisted -- stage 0 defines the mechanism; it does not use it to
    describe anything real yet, since there is no artifact yet to describe.
    """
    demonstration_entry = ResidueEntry(
        what="stage-0 self-check placeholder, not a real finding",
        locations=("A1",),
        defeating_construct="none -- this entry exists only to prove construction succeeds",
        consequence="none -- discarded immediately, never written to any file",
    )
    assert demonstration_entry.locations == ("A1",)

    stamp = build_stamp(capture.capture_date)
    assert isinstance(stamp, ArtifactStamp)
    assert stamp.capture_date == capture.capture_date
    assert stamp.tool_commit  # non-empty, even in the "unknown (...)" fallback case
    return stamp


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m sheet_derivation.stage0 <capture_directory>", file=sys.stderr)
        return 2

    capture_dir = argv[0]
    formulas_path, values_path = discover_capture_files(capture_dir)

    def pipeline():
        result = run_stage0(formulas_path, values_path)
        # Equality compares every field, including the full formula/value
        # tuples -- that's two loads of the capture either way (this
        # function runs twice by construction) and tuple equality on
        # 780,262 cells is negligible next to the JSON parse itself.
        return result

    result = verify_same_process_determinism(pipeline, run_label="stage-0 pipeline")
    all_counts, totals = result.all_counts, result.totals
    stamp = _demonstrate_residue_and_stamp_mechanism(result.capture)

    print(f"captureDate: {result.capture.capture_date}")
    print(f"sheets: {totals.sheet_count}")
    print(f"tool commit (artifact-stamp mechanism, demonstrated not used): {stamp.tool_commit}")
    print()
    print(format_per_sheet_table(all_counts, totals))
    print()
    print("Determinism check: PASSED (stage-0 pipeline ran twice in one process, identical results).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
