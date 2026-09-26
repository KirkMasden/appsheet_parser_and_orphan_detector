"""Writes Stage 4's JSON Lines schema artifact and its flat CSV
projections from a Stage4Result -- same convention stage3_artifacts.py
set: a `kind` field distinguishes meta / content / residue lines within
one self-contained JSONL file, and CSV is only generated for the parts
genuinely flat enough to project.

Two CSV projections, not one -- stage 4 has two distinct flat
populations, sheets and columns, where stage 3 had only one:

  - `stage4_sheet_summary.csv`: one row per sheet. Every field on a
    SheetSchemaEntry is scalar EXCEPT named ranges / data validations /
    conditional format rules / protected ranges (nested, one-to-many) and
    duplicate_labels / columns (one-to-many) -- those stay JSONL-only;
    everything else, including the header-detection verdict, its source,
    and its confidence, is one value per sheet.
  - `stage4_column_summary.csv`: one row per column, mirroring stage 3's
    own column_summary.csv but adding the header-label state and value.
    A column's spill runs remain one-to-many and stay JSONL-only, exactly
    as stage 3 already decided.
"""

import os
from typing import Any, Dict, Iterable, Tuple

from .jsonl_io import write_csv, write_jsonl
from .stage4 import SchemaArtifact, Stage4Result


def _residue_lines(residue) -> Iterable[Dict[str, Any]]:
    for r in residue:
        yield {
            "kind": "residue",
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }


def _header_detection_out(hd) -> Dict[str, Any]:
    return {
        "source": hd.source,
        "verdict": hd.verdict,
        "headerRow1": hd.header_row1,
        "confidence": hd.confidence,
        "evidence": {
            "positiveSignalColumns": list(hd.evidence.positive_signal_columns),
            "negativeSignalColumns": list(hd.evidence.negative_signal_columns),
            "informativeColumnCount": hd.evidence.informative_column_count,
            "totalColumnCount": hd.evidence.total_column_count,
            "note": hd.evidence.note,
        },
        "appColumnNames": _app_names_out(hd.app_names),
    }


def _app_names_out(an) -> Any:
    if an is None:
        return None
    return {
        "status": an.status,
        "table": an.table,
        "bestRow1": an.best_row1,
        "namesTotal": an.names_total,
        "exactMatches": an.exact_matches,
        "nearMisses": an.near_misses,
        "ruleVerdict": an.rule_verdict,
        "ruleHeaderRow1": an.rule_header_row1,
        "disagreesWithRule": an.disagrees_with_rule,
        "note": an.note,
    }


def _column_out(c) -> Dict[str, Any]:
    return {
        "column": c.column,
        "headerLabel": {"state": c.header_label.state, "value": c.header_label.value},
        "formulaCount": c.formula_count,
        "valueCount": c.value_count,
        "distinctPatternCount": c.distinct_pattern_count,
        "classification": c.classification,
        "spillRuns": [
            {
                "rowStart1": sr.row_start1,
                "rowEnd1": sr.row_end1,
                "valueCount": sr.value_count,
                "governingFormulaRow1": sr.governing_formula_row1,
                "gapRows": sr.gap_rows,
            }
            for sr in c.spill_runs
        ],
    }


def _schema_lines(schema: SchemaArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "schema",
        "captureDate": schema.stamp.capture_date,
        "toolCommit": schema.stamp.tool_commit,
        "reliabilityCondition": schema.reliability_condition,
        "sheetCount": len(schema.sheets),
        "residueCount": len(schema.residue),
    }
    for s in schema.sheets:
        yield {
            "kind": "sheet",
            "sheet": s.sheet,
            "declaredRowCount": s.declared_row_count,
            "declaredColumnCount": s.declared_column_count,
            "highestRowWithFormula": s.highest_row_with_formula,
            "highestColumnWithFormula": s.highest_column_with_formula,
            "highestRowWithValue": s.highest_row_with_value,
            "highestColumnWithValue": s.highest_column_with_value,
            "frozenRows": s.frozen_rows,
            "frozenColumns": s.frozen_columns,
            "namedRanges": list(s.named_ranges),
            "dataValidations": list(s.data_validations),
            "conditionalFormatRules": list(s.conditional_format_rules),
            "protectedRanges": list(s.protected_ranges),
            "headerDetection": _header_detection_out(s.header_detection),
            "duplicateLabels": [
                {"labelValue": d.label_value, "columns": list(d.columns)} for d in s.duplicate_labels
            ],
            "columns": [_column_out(c) for c in s.columns],
        }
    yield from _residue_lines(schema.residue)


def _sheet_summary_rows(schema: SchemaArtifact) -> Iterable[Dict[str, Any]]:
    for s in schema.sheets:
        hd = s.header_detection
        yield {
            "sheet": s.sheet,
            "declaredRowCount": s.declared_row_count,
            "declaredColumnCount": s.declared_column_count,
            "highestRowWithFormula": s.highest_row_with_formula if s.highest_row_with_formula is not None else "",
            "highestColumnWithFormula": s.highest_column_with_formula or "",
            "highestRowWithValue": s.highest_row_with_value if s.highest_row_with_value is not None else "",
            "highestColumnWithValue": s.highest_column_with_value or "",
            "frozenRows": s.frozen_rows,
            "frozenColumns": s.frozen_columns,
            "headerSource": hd.source,
            "headerVerdict": hd.verdict,
            "headerRow1": hd.header_row1 if hd.header_row1 is not None else "",
            "headerConfidence": hd.confidence if hd.confidence is not None else "",
            "duplicateLabelCount": len(s.duplicate_labels),
            "namedRangeCount": len(s.named_ranges),
            "dataValidationCount": len(s.data_validations),
            "conditionalFormatRuleCount": len(s.conditional_format_rules),
            "protectedRangeCount": len(s.protected_ranges),
            "appNamesStatus": hd.app_names.status if hd.app_names is not None else "",
            "appNamesTable": (hd.app_names.table or "") if hd.app_names is not None else "",
            "appNamesMatched": hd.app_names.matched if hd.app_names is not None and hd.app_names.names_total else "",
            "appNamesTotal": hd.app_names.names_total if hd.app_names is not None and hd.app_names.names_total else "",
            "appNamesDisagreesWithRule": (
                ("Yes" if hd.app_names.disagrees_with_rule else "No")
                if hd.app_names is not None and hd.app_names.status == "decided" else ""
            ),
        }


_SHEET_SUMMARY_FIELDS: Tuple[str, ...] = (
    "sheet", "declaredRowCount", "declaredColumnCount", "highestRowWithFormula", "highestColumnWithFormula",
    "highestRowWithValue", "highestColumnWithValue", "frozenRows", "frozenColumns", "headerSource",
    "headerVerdict", "headerRow1", "headerConfidence", "duplicateLabelCount", "namedRangeCount",
    "dataValidationCount", "conditionalFormatRuleCount", "protectedRangeCount",
    "appNamesStatus", "appNamesTable", "appNamesMatched", "appNamesTotal", "appNamesDisagreesWithRule",
)


def _column_summary_rows(schema: SchemaArtifact) -> Iterable[Dict[str, Any]]:
    for s in schema.sheets:
        for c in s.columns:
            yield {
                "sheet": s.sheet,
                "column": c.column,
                "headerLabelState": c.header_label.state,
                "headerLabelValue": c.header_label.value if c.header_label.value is not None else "",
                "formulaCount": c.formula_count,
                "valueCount": c.value_count,
                "distinctPatternCount": c.distinct_pattern_count,
                "classification": c.classification,
                "spillRunCount": len(c.spill_runs),
            }


_COLUMN_SUMMARY_FIELDS: Tuple[str, ...] = (
    "sheet", "column", "headerLabelState", "headerLabelValue", "formulaCount", "valueCount",
    "distinctPatternCount", "classification", "spillRunCount",
)


def write_stage4_artifacts(result: Stage4Result, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "schema": os.path.join(output_dir, "stage4_schema.jsonl"),
        "sheet_summary_csv": os.path.join(output_dir, "stage4_sheet_summary.csv"),
        "column_summary_csv": os.path.join(output_dir, "stage4_column_summary.csv"),
    }
    write_jsonl(paths["schema"], _schema_lines(result.schema))
    write_csv(paths["sheet_summary_csv"], _SHEET_SUMMARY_FIELDS, _sheet_summary_rows(result.schema))
    write_csv(paths["column_summary_csv"], _COLUMN_SUMMARY_FIELDS, _column_summary_rows(result.schema))
    return paths
