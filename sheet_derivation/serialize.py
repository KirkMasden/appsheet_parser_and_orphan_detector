"""Canonical, deterministic serialization of a Stage0Result, for the
cross-process determinism check.

The in-process check (determinism.py) catches unstable iteration order
within one interpreter. It cannot catch instability that only shows up
BETWEEN processes, because CPython randomizes string hashing per
interpreter launch (PYTHONHASHSEED) unless pinned -- a set-ordering defect
can be perfectly stable inside one run and differ on the next. Catching
that requires comparing output from two separate process launches with
different hash seeds, which is what this module's output feeds.

Everything here writes plain lists in an explicitly chosen order (capture
order for sheets, row-major order for cells) -- never a bare dict.items()
or set iteration -- so this serialization is itself part of what the
cross-process check is verifying, not exempt from it.
"""

import json
from typing import Any, Dict

from .stage0 import Stage0Result


def build_canonical_structure(result: Stage0Result) -> Dict[str, Any]:
    """Every collection Stage 0 produces, in one deterministically-ordered
    structure: the full capture (per sheet, in capture order, including
    the complete formulas/numberFormats/values arrays -- no truncation and
    no reduction to only non-empty cells, since a reduction is itself a
    place a silent ordering defect could hide), the per-sheet counts, and
    the workbook totals.
    """
    capture = result.capture

    sheets_out = []
    for name in capture.sheet_order:
        fs = capture.formula_sheet(name)
        vs = capture.value_sheet(name)
        sheets_out.append(
            {
                "sheetName": fs.sheet_name,
                "rowCount": fs.row_count,
                "columnCount": fs.column_count,
                "frozenRows": fs.frozen_rows,
                "frozenColumns": fs.frozen_columns,
                "namedRanges": list(fs.named_ranges),
                "dataValidations": list(fs.data_validations),
                "conditionalFormatRules": list(fs.conditional_format_rules),
                "protectedRanges": list(fs.protected_ranges),
                "formulas": [list(row) for row in fs.formulas],
                "numberFormats": [list(row) for row in fs.number_formats],
                "values": [list(row) for row in vs.values],
            }
        )

    counts_out = []
    for c in result.all_counts:
        counts_out.append(
            {
                "sheetName": c.sheet_name,
                "rowCount": c.row_count,
                "columnCount": c.column_count,
                "totalCells": c.total_cells,
                "nonEmptyFormulas": c.non_empty_formulas,
                "nonEmptyValues": c.non_empty_values,
                "frozenRows": c.frozen_rows,
                "frozenColumns": c.frozen_columns,
                "fillRatePercent": c.fill_rate_percent,
            }
        )

    totals = result.totals
    totals_out = {
        "sheetCount": totals.sheet_count,
        "totalCells": totals.total_cells,
        "totalNonEmptyFormulas": totals.total_non_empty_formulas,
        "totalNonEmptyValues": totals.total_non_empty_values,
        "captureDate": totals.capture_date,
        "fillRatePercent": totals.fill_rate_percent,
    }

    return {
        "captureDate": capture.capture_date,
        "spreadsheetName": capture.spreadsheet_name,
        "triggerIds": list(capture.trigger_ids),
        "sheetOrder": list(capture.sheet_order),
        "sheets": sheets_out,
        "counts": counts_out,
        "totals": totals_out,
    }


def write_canonical_json(path: str, structure: Dict[str, Any]) -> None:
    """Writes `structure` in a fixed, minimal-whitespace form so that two
    files holding identical data are also identical bytes -- no incidental
    formatting difference can masquerade as, or hide, a real one."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(structure, fh, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
