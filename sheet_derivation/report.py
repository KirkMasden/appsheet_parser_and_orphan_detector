"""Stage-0's own verification report: the per-sheet table, reproduced exactly.

This is not one of the five artifacts (design section 4) -- it exists only
so stage 0's done-when can be checked: does this loader reproduce the
probe report's Section 2 table, cell for cell, from the same capture. It
carries no residue and no stamp, because it is not an artifact.

Formats no formula or value text, so the "no truncation, anywhere, ever"
rule (design constraint, stage-0 item 7) does not need to be exercised
here to be honored here -- it will be exercised in the artifacts, not in
this table.
"""

from typing import Tuple

from .counts import SheetCounts, WorkbookTotals


def format_per_sheet_table(all_counts: Tuple[SheetCounts, ...], totals: WorkbookTotals) -> str:
    lines = [
        "| sheetName | rowCount | columnCount | total cells | non-empty formulas | "
        "fill rate % | non-empty values | frozenRows | frozenColumns |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in all_counts:
        lines.append(
            f"| {c.sheet_name} | {c.row_count} | {c.column_count} | "
            f"{c.total_cells:,} | {c.non_empty_formulas:,} | "
            f"{c.fill_rate_percent:.2f} | {c.non_empty_values:,} | "
            f"{c.frozen_rows} | {c.frozen_columns} |"
        )
    lines.append(
        f"| **TOTAL** | | | **{totals.total_cells:,}** | "
        f"**{totals.total_non_empty_formulas:,}** | **{totals.fill_rate_percent:.2f}** | "
        f"**{totals.total_non_empty_values:,}** | | |"
    )
    return "\n".join(lines)
