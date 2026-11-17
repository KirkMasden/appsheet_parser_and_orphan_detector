"""Writes Stage 6's JSON Lines artifact and its flat CSV projection from a
Stage6Result -- the same `kind`-tagged-line convention stages 3 to 5 set.

`stage6_formula_checkup.jsonl` (authoritative) holds, in this order:

  - one `kind: "meta"` line: the artifact's stamp (capture date, tool
    commit), its reliability condition stated once, whether
    `appsheet_tables.csv` was found, the counts by tier and grade, and
    `present` (false when the app-side results are absent, in which case
    nothing else but the residue-free meta line is written);
  - one `kind: "column"` line per examined column, including the columns
    where everything agrees, so that the absence of a finding can be
    checked;
  - one `kind: "not-examined"` line per column that has a stored formula
    and could not be paired with a sheet column, with the reason;
  - the `kind: "residue"` lines.

`stage6_formula_checkup.csv` is DERIVED and regenerable: one row per
examined column with the flat fields only. The per-group formulas, the
uncompared cells and the notes are one-to-many and stay in the JSONL.
Nothing is truncated in either file.
"""

import os
from typing import Any, Dict, Iterable, Tuple

from .jsonl_io import write_csv, write_jsonl
from .stage6 import (
    GRADE_LIKELY,
    GRADE_POSSIBLE,
    TIER_MINOR,
    TIER_NOT_A_PROBLEM,
    TIER_RAISED,
    TIER_RUN_PROBLEM,
    CheckupArtifact,
    ColumnFinding,
    SITUATION_NAMES,
    Stage6Result,
    format_row_ranges,
)

JSONL_NAME = "stage6_formula_checkup.jsonl"
CSV_NAME = "stage6_formula_checkup.csv"


def tier_counts(checkup: CheckupArtifact) -> Dict[str, Any]:
    """Counts of the examined columns by tier, with the raised ones also by
    grade. Every examined column is in exactly one tier. A column marked
    intended (its declaration still matches) is counted in intendedCount and
    NOT in raised, raisedLikely, raisedPossible or minor; `examined` still
    counts it."""
    counts = {
        "examined": len(checkup.findings),
        "intendedCount": 0,
        "raised": 0,
        "raisedLikely": 0,
        "raisedPossible": 0,
        "minor": 0,
        "notAProblem": 0,
        "runProblem": 0,
    }
    for f in checkup.findings:
        if f.intended is not None:
            counts["intendedCount"] += 1
        elif f.tier == TIER_RAISED:
            counts["raised"] += 1
            if f.grade == GRADE_LIKELY:
                counts["raisedLikely"] += 1
            elif f.grade == GRADE_POSSIBLE:
                counts["raisedPossible"] += 1
        elif f.tier == TIER_MINOR:
            counts["minor"] += 1
        elif f.tier == TIER_NOT_A_PROBLEM:
            counts["notAProblem"] += 1
        elif f.tier == TIER_RUN_PROBLEM:
            counts["runProblem"] += 1
    return counts


def _residue_lines(residue) -> Iterable[Dict[str, Any]]:
    for r in residue:
        yield {
            "kind": "residue",
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }


def _group_out(g) -> Dict[str, Any]:
    return {
        "rowCount": len(g.rows),
        "rows": format_row_ranges(g.rows),
        "representativeRow": g.representative_row,
        "rawSheetFormula": g.raw_formula,
        "convertedText": g.converted,
        "canonicalConverted": g.canonical,
        "byConvention": list(g.by_convention),
        "note": g.note,
    }


def _mark_out(mark):
    return None if mark is None else {"dateDeclared": mark.date_declared, "note": mark.note}


def intended_meta(checkup: CheckupArtifact) -> Dict[str, Any]:
    """What became of the intended-items record in this run."""
    return {
        "appName": checkup.app_name,
        "intendedRecord": {
            "state": checkup.record_state,
            "file": checkup.record_file,
            "note": checkup.record_note,
        },
        "intendedLapsed": [
            {"table": t, "column": c, "dateDeclared": d, "note": n} for t, c, d, n in checkup.lapsed_entries
        ],
        "intendedNotApplied": [
            {"table": t, "column": c, "dateDeclared": d, "reason": r} for t, c, d, r in checkup.not_applied_entries
        ],
        "orphanEntryCount": checkup.orphan_entry_count,
    }


def column_line(f: ColumnFinding) -> Dict[str, Any]:
    return {
        "kind": "column",
        "table": f.table,
        "column": f.column,
        "tab": f.tab,
        "sheetColumn": f.sheet_column,
        "labelState": f.label_state,
        "labelText": f.label_text,
        "headerRow1": f.header_row1,
        "headerSource": f.header_source,
        "headerVerdict": f.header_verdict,
        "rowBasisUncertain": f.row_basis_uncertain,
        "updateModeAsExported": f.update_mode,
        "addsAllowed": f.adds_allowed,
        "editsAllowed": f.edits_allowed,
        "tableAllows": f.allows,
        "settingBasis": f.setting_basis,
        "settingAssumed": f.setting_assumed,
        "rowBasis": f.row_basis,
        "rowBasisDetail": f.row_basis_detail,
        "keyColumn": f.key_column,
        "keySheetColumn": f.key_sheet_column,
        "countedRowCount": len(f.counted_rows),
        "countedRows": format_row_ranges(f.counted_rows),
        "storedFormula": f.stored_formula,
        "storedState": f.stored_state,
        "matchingRowCount": len(f.matching_rows),
        "matchingRows": format_row_ranges(f.matching_rows),
        "differingRowCount": sum(len(g.rows) for g in f.differing_groups),
        "differingGroups": [_group_out(g) for g in f.differing_groups],
        "placeholderRowCount": len(f.placeholder_rows),
        "placeholderRows": format_row_ranges(f.placeholder_rows),
        "noFormulaRowCount": len(f.no_formula_rows),
        "noFormulaRows": format_row_ranges(f.no_formula_rows),
        "uncomparedRowCount": len(f.uncompared),
        "uncompared": [
            {"row": u.row, "cell": u.cell, "reason": u.reason, "rawSheetFormula": u.raw_formula}
            for u in f.uncompared
        ],
        "formulaRowCount": f.formula_row_count,
        "valueOnlyRowCount": f.value_only_row_count,
        "blankRowCount": f.blank_row_count,
        "byConvention": list(f.by_convention),
        "situation": f.situation,
        "situationName": SITUATION_NAMES[f.situation],
        "tier": f.tier,
        "grade": f.grade,
        "rank": f.rank,
        "finding": f.finding,
        "advice": f.advice,
        "notes": list(f.notes),
        "intended": _mark_out(f.intended),
        "intendedLapsed": _mark_out(f.lapsed),
    }


def _checkup_lines(checkup: CheckupArtifact) -> Iterable[Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "kind": "meta",
        "artifact": "appsheet_formula_checkup",
        "present": checkup.present,
        "captureDate": checkup.stamp.capture_date,
        "toolCommit": checkup.stamp.tool_commit,
        "reliabilityCondition": checkup.reliability_condition,
        "absentReason": checkup.absent_reason,
        "csvProjection": f"{CSV_NAME} (DERIVED, regenerable; this JSONL file is authoritative)",
        "appsideParseDir": checkup.appside_parse_dir,
        "appsheetTablesCsvFound": checkup.tables_csv_found,
        "appsheetTablesCsvNote": checkup.tables_csv_note,
        "inputFileHashes": {name: digest for name, digest in checkup.input_file_hashes},
        "notExaminedCount": len(checkup.not_examined),
        "residueCount": len(checkup.residue),
    }
    meta.update(intended_meta(checkup))
    meta.update(tier_counts(checkup))
    yield meta
    for f in checkup.findings:
        yield column_line(f)
    for n in checkup.not_examined:
        yield {
            "kind": "not-examined",
            "table": n.table,
            "column": n.column,
            "tab": n.tab,
            "sheetColumn": n.sheet_column,
            "storedFormula": n.stored_formula,
            "reason": n.reason,
        }
    yield from _residue_lines(checkup.residue)


_CSV_FIELDS: Tuple[str, ...] = (
    "table", "column", "tab", "sheetColumn", "updateModeAsExported", "addsAllowed", "editsAllowed",
    "settingAssumed", "rowBasis", "countedRowCount", "matchingRowCount", "differingRowCount",
    "noFormulaRowCount", "uncomparedRowCount", "situation", "tier", "grade", "rank", "intended",
    "byConvention", "storedFormula", "finding", "advice",
)


def _csv_rows(checkup: CheckupArtifact) -> Iterable[Dict[str, Any]]:
    for f in checkup.findings:
        line = column_line(f)
        row = {k: line[k] for k in _CSV_FIELDS if k not in ("byConvention", "grade", "rank", "updateModeAsExported", "intended")}
        row["intended"] = "yes" if f.intended is not None else ("lapsed declaration" if f.lapsed is not None else "")
        row["updateModeAsExported"] = "" if f.update_mode is None else f.update_mode
        row["grade"] = "" if f.grade is None else f.grade
        row["rank"] = "" if f.rank is None else f.rank
        row["byConvention"] = " | ".join(f.by_convention)
        yield {k: row[k] for k in _CSV_FIELDS}
    for n in checkup.not_examined:
        row = {k: "" for k in _CSV_FIELDS}
        row.update(
            {
                "table": n.table, "column": n.column, "tab": n.tab or "", "sheetColumn": n.sheet_column or "",
                "situation": "not examined", "storedFormula": n.stored_formula, "finding": n.reason,
            }
        )
        yield row


def write_stage6_artifacts(result: Stage6Result, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "checkup": os.path.join(output_dir, JSONL_NAME),
        "checkup_csv": os.path.join(output_dir, CSV_NAME),
        "summary": os.path.join(output_dir, "stage6_formula_checkup_summary.json"),
    }
    write_jsonl(paths["checkup"], _checkup_lines(result.checkup))
    write_csv(paths["checkup_csv"], _CSV_FIELDS, _csv_rows(result.checkup))
    from .stage6_summary import build_summary, write_summary  # here: stage6_summary imports this module

    write_summary(paths["summary"], build_summary(result))
    return paths
