"""Canonical, deterministic serialization of a Stage4Result, for the
cross-process determinism check (Gate C4) -- same purpose and same shape
as serialize_stage1/2/3.py before it. Not the JSONL artifact format; see
stage4_artifacts.py for that.
"""

import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage4 import Stage4Result, run_stage4


def _residue_out(entries):
    return [
        {
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }
        for r in sorted(entries, key=lambda r: (r.locations, r.defeating_construct, r.what))
    ]


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


def build_canonical_structure(result: Stage4Result) -> Dict[str, Any]:
    sheets_out = []
    for s in result.schema.sheets:
        sheets_out.append(
            {
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
                "columns": [
                    {
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
                                "governingFormulaRow1": sr.governing_formula_row1,
                                "gapRows": sr.gap_rows,
                            }
                            for sr in c.spill_runs
                        ],
                    }
                    for c in s.columns
                ],
            }
        )

    return {
        "captureDate": result.capture.capture_date,
        "schema": {
            "stampCaptureDate": result.schema.stamp.capture_date,
            "stampToolCommit": result.schema.stamp.tool_commit,
            "reliabilityCondition": result.schema.reliability_condition,
            "residue": _residue_out(result.schema.residue),
            "sheets": sheets_out,
        },
        "sheetVerdictCounts": {f"{k[0]}|{k[1]}": v for k, v in sorted(result.sheet_verdict_counts.items())},
        "columnLabelStateCounts": {k: v for k, v in sorted(result.column_label_state_counts.items())},
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        print(
            "usage: python -m sheet_derivation.serialize_stage4 <capture_directory> <output_path> "
            "[app_export_html]",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv[0], argv[1]
    app_export_html = argv[2] if len(argv) == 3 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage4(formulas_path, values_path, app_export_html_path=app_export_html)
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
