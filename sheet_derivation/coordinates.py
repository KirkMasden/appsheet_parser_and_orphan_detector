"""A1-address conversion and a (sheet, row, column) -> formula/value model.

Column-letter conversion is not length-limited to two letters -- it handles
any length, since the design only attests "reaches AW" for this one
capture (design section 3.2: a measured fact about one workbook is never a
license to assume it as a rule).
"""

import re
from typing import Any, Optional, Tuple

from .loader import Capture

_ADDRESS_RE = re.compile(r"^([A-Za-z]+)([0-9]+)$")


def col_to_letters(col0: int) -> str:
    """0-indexed column number to A1 column letters (A, ..., Z, AA, ..., AW, ...)."""
    if col0 < 0:
        raise ValueError(f"column index must be non-negative, got {col0}")
    n = col0 + 1
    letters = []
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def letters_to_col(letters: str) -> int:
    """A1 column letters to a 0-indexed column number. Case-insensitive."""
    if not letters or not letters.isalpha():
        raise ValueError(f"not a valid column-letter string: {letters!r}")
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def cell_address(row0: int, col0: int) -> str:
    """0-indexed (row, column) to an A1 cell address, e.g. (0, 48) -> 'AW1'."""
    if row0 < 0:
        raise ValueError(f"row index must be non-negative, got {row0}")
    return f"{col_to_letters(col0)}{row0 + 1}"


def parse_cell_address(address: str) -> Tuple[int, int]:
    """An A1 cell address to 0-indexed (row, column). Inverse of cell_address."""
    match = _ADDRESS_RE.match(address.strip())
    if not match:
        raise ValueError(f"not a valid A1 cell address: {address!r}")
    letters, digits = match.groups()
    row0 = int(digits) - 1
    if row0 < 0:
        raise ValueError(f"not a valid A1 cell address (row must be >= 1): {address!r}")
    return row0, letters_to_col(letters)


class CoordinateModel:
    """Maps (sheet, row, column) to formula and value, and to/from A1 addresses.

    Bounds are checked against each sheet's own declared dimensions -- which
    load_capture's third gate has already proven match the actual array
    shapes -- so an out-of-range request fails with a specific message
    rather than a bare IndexError.
    """

    def __init__(self, capture: Capture):
        self._capture = capture

    def _check_bounds(self, sheet_name: str, row0: int, col0: int) -> None:
        sheet = self._capture.formula_sheet(sheet_name)
        if not (0 <= row0 < sheet.row_count) or not (0 <= col0 < sheet.column_count):
            raise IndexError(
                f"({row0}, {col0}) is out of bounds for sheet {sheet_name!r}, "
                f"which is {sheet.row_count} rows x {sheet.column_count} columns"
            )

    def formula_at(self, sheet_name: str, row0: int, col0: int) -> str:
        self._check_bounds(sheet_name, row0, col0)
        return self._capture.formula_sheet(sheet_name).formulas[row0][col0]

    def value_at(self, sheet_name: str, row0: int, col0: int) -> Any:
        self._check_bounds(sheet_name, row0, col0)
        return self._capture.value_sheet(sheet_name).values[row0][col0]

    def formula_at_address(self, sheet_name: str, address: str) -> str:
        row0, col0 = parse_cell_address(address)
        return self.formula_at(sheet_name, row0, col0)

    def value_at_address(self, sheet_name: str, address: str) -> Any:
        row0, col0 = parse_cell_address(address)
        return self.value_at(sheet_name, row0, col0)

    @staticmethod
    def address(row0: int, col0: int) -> str:
        return cell_address(row0, col0)

    @staticmethod
    def coords(address: str) -> Tuple[int, int]:
        return parse_cell_address(address)
