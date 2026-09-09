"""The value query (design section 9, Shape B): an address in, a value
out, over the captured values file -- the mechanism section 7's AI
investigation stage needs to be operable at all, and the one the formula
inventory (stage 3) needs so a pattern's raw instance can be traced back
to real values, not just a real cell address.

Scope, stated plainly because it is easy to overreach here: this module
RESOLVES ADDRESSES ONLY. It does not evaluate formulas, does not follow a
reference chain (that is stage 2's one-hop resolution, used only for the
IMPORTRANGE/QUERY residue refinement, and even that stops at one hop), and
does not interpret what a spilling formula's result "means". Given one
address, it reports that cell's own formula and value, and -- only when
the address names a cell holding a formula -- the STRUCTURAL extent of any
apparent spill: how far down the same column, and how far right along the
same row, consecutive cells hold a value with no formula of their own.

That structural test is a heuristic, not an evaluation, and this module
says so rather than pretending otherwise: a value manually typed into the
cell immediately below an unrelated formula, with no formula of its own,
is indistinguishable from a genuine spilled cell by this test alone. This
is exactly design section 3.2's own instruction for the spill-versus-
cell-filled distinction -- measure what can be measured, and report the
rest as undetermined, never resolved by assumption. Whether an apparent
spill's extent is "real" is for the reader (or the AI investigation stage
of section 7) to judge from the raw capture; this module measures the
gap and stops.

Nothing here may name a sheet (design section 3.2): every rule below is a
general property of A1 addressing and of what "spill" can structurally
mean in a spreadsheet, not a fact about one workbook.
"""

from dataclasses import dataclass
from typing import Any, Optional

from .coordinates import CoordinateModel, col_to_letters, parse_cell_address
from .counts import is_nonempty
from .loader import Capture


class UnknownSheetError(KeyError):
    """Raised when an address names a sheet not present in this capture."""


@dataclass(frozen=True)
class SpillExtent:
    """The structural extent measured from a spill-origin cell.

    `down_to_row1` / `right_to_column`: the furthest row (1-based) / column
    (letters) reached by an unbroken run of value-with-no-own-formula
    cells extending down the origin's own column, or right along the
    origin's own row, respectively. Either may equal the origin's own
    row/column when no extension was found in that direction -- a spill
    origin can extend in only one direction, or (rarely, for a
    single-cell array result) in neither.
    """

    down_to_row1: int
    right_to_column: str
    note: str


@dataclass(frozen=True)
class AddressQueryResult:
    sheet: str
    address: str
    formula: Optional[str]
    value: Any
    is_spill_origin: bool
    spill_extent: Optional[SpillExtent]


_STRUCTURAL_NOTE = (
    "Structural measurement only: an unbroken run of cells holding a value "
    "and no formula of their own, extending down this cell's column and "
    "right along this cell's row. This is not a confirmation that a spill "
    "produced these values -- a manually-entered value adjacent to an "
    "unrelated formula would measure identically. Report the extent as "
    "measured; judging whether it reflects a real spill is left to the reader."
)


def _measure_down(capture: Capture, sheet_name: str, row0: int, col0: int) -> int:
    """Returns the 0-indexed row of the furthest cell, strictly below
    (row0, col0), reachable by an unbroken run of value-present/
    formula-absent cells in the same column. Returns row0 itself if the
    very next row does not qualify (no downward extension)."""
    fs = capture.formula_sheet(sheet_name)
    vs = capture.value_sheet(sheet_name)
    r = row0 + 1
    last = row0
    while r < fs.row_count:
        if is_nonempty(vs.values[r][col0]) and not is_nonempty(fs.formulas[r][col0]):
            last = r
            r += 1
        else:
            break
    return last


def _measure_right(capture: Capture, sheet_name: str, row0: int, col0: int) -> int:
    """Mirror of `_measure_down`, extending rightward along the same row."""
    fs = capture.formula_sheet(sheet_name)
    vs = capture.value_sheet(sheet_name)
    c = col0 + 1
    last = col0
    while c < fs.column_count:
        if is_nonempty(vs.values[row0][c]) and not is_nonempty(fs.formulas[row0][c]):
            last = c
            c += 1
        else:
            break
    return last


def query_address(capture: Capture, sheet_name: str, address: str) -> AddressQueryResult:
    """Resolves one address against the capture: its own formula and
    value, and -- only if it holds a formula -- the structural spill
    extent measured from it (see module docstring for exactly what that
    does and does not establish).

    Raises UnknownSheetError if `sheet_name` matches no captured sheet, and
    IndexError (via CoordinateModel) if `address` is out of that sheet's
    declared bounds -- this module resolves addresses, it does not guess
    at ones the capture never declared.
    """
    if sheet_name not in capture.sheet_order:
        raise UnknownSheetError(
            f"{sheet_name!r} matches no sheet in this capture; captured sheets are {list(capture.sheet_order)}"
        )
    coords = CoordinateModel(capture)
    row0, col0 = parse_cell_address(address)
    formula_raw = coords.formula_at(sheet_name, row0, col0)
    value = coords.value_at(sheet_name, row0, col0)
    formula = formula_raw if is_nonempty(formula_raw) else None

    is_spill_origin = False
    spill_extent = None
    if formula is not None:
        down_row0 = _measure_down(capture, sheet_name, row0, col0)
        right_col0 = _measure_right(capture, sheet_name, row0, col0)
        is_spill_origin = down_row0 > row0 or right_col0 > col0
        if is_spill_origin:
            spill_extent = SpillExtent(
                down_to_row1=down_row0 + 1,
                right_to_column=col_to_letters(right_col0),
                note=_STRUCTURAL_NOTE,
            )

    return AddressQueryResult(
        sheet=sheet_name,
        address=CoordinateModel.address(row0, col0),
        formula=formula,
        value=value,
        is_spill_origin=is_spill_origin,
        spill_extent=spill_extent,
    )
