"""Counting infrastructure for the accounting invariant later stages enforce.

Stage 0 only builds the counters -- per sheet and workbook-wide, non-empty
formulas and non-empty values. The assertion this exists for ("patterns
matched plus residue entries sum to the formula count") is a later stage's
job, once there are patterns and residue entries to sum.

A cell counts as non-empty using the same rule throughout this tool: not
None and not the empty string. This is the rule the probe report used
(section 2) and the done-when table this module must reproduce depends on
it holding exactly.
"""

from dataclasses import dataclass
from typing import Tuple

from .loader import Capture


def is_nonempty(value) -> bool:
    return value is not None and value != ""


@dataclass(frozen=True)
class SheetCounts:
    """One sheet's structural counts, needed to reproduce the probe's Section 2 table."""

    sheet_name: str
    row_count: int
    column_count: int
    total_cells: int
    non_empty_formulas: int
    non_empty_values: int
    frozen_rows: int
    frozen_columns: int

    @property
    def fill_rate_percent(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.non_empty_formulas / self.total_cells * 100


@dataclass(frozen=True)
class WorkbookTotals:
    sheet_count: int
    total_cells: int
    total_non_empty_formulas: int
    total_non_empty_values: int
    capture_date: str

    @property
    def fill_rate_percent(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.total_non_empty_formulas / self.total_cells * 100


def compute_sheet_counts(capture: Capture, sheet_name: str) -> SheetCounts:
    formula_sheet = capture.formula_sheet(sheet_name)
    value_sheet = capture.value_sheet(sheet_name)

    non_empty_formulas = sum(
        1 for row in formula_sheet.formulas for cell in row if is_nonempty(cell)
    )
    non_empty_values = sum(
        1 for row in value_sheet.values for cell in row if is_nonempty(cell)
    )

    return SheetCounts(
        sheet_name=sheet_name,
        row_count=formula_sheet.row_count,
        column_count=formula_sheet.column_count,
        total_cells=formula_sheet.row_count * formula_sheet.column_count,
        non_empty_formulas=non_empty_formulas,
        non_empty_values=non_empty_values,
        frozen_rows=formula_sheet.frozen_rows,
        frozen_columns=formula_sheet.frozen_columns,
    )


def compute_all_counts(capture: Capture) -> Tuple[SheetCounts, ...]:
    """Every sheet's counts, in capture order.

    Capture order -- each sheet's explicit position in the formulas file's
    `sheets` array -- is the sort key here, not sheet-name alphabetical
    order and not dict/set iteration: gate 2 has already proven the values
    file agrees on that same order, so it is a property of the input, not
    an arbitrary choice made while emitting the collection.
    """
    return tuple(compute_sheet_counts(capture, name) for name in capture.sheet_order)


def compute_workbook_totals(capture: Capture, all_counts: Tuple[SheetCounts, ...] = None) -> WorkbookTotals:
    if all_counts is None:
        all_counts = compute_all_counts(capture)
    return WorkbookTotals(
        sheet_count=len(all_counts),
        total_cells=sum(c.total_cells for c in all_counts),
        total_non_empty_formulas=sum(c.non_empty_formulas for c in all_counts),
        total_non_empty_values=sum(c.non_empty_values for c in all_counts),
        capture_date=capture.capture_date,
    )
