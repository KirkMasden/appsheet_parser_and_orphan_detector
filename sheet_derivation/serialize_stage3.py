"""Canonical, deterministic serialization of a Stage3Result, for the
cross-process determinism check (Gate C4) -- same purpose and same shape
as serialize_stage1.py/serialize_stage2.py before it.

This is NOT the JSON Lines artifact format (design section 4's "Output
format, decided 2026-09-09") -- it is one canonical JSON document used
only to compare two separate process launches byte-for-byte. The actual
JSONL/CSV artifacts are written by stage3_artifacts.py.
"""

import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage3 import Stage3Result, run_stage3


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


def build_canonical_structure(result: Stage3Result) -> Dict[str, Any]:
    patterns_out = [
        {
            "pattern": p.pattern_text,
            "instanceCount": p.instance_count,
            "rawInstance": p.raw_instance,
            "locations": [
                {"sheet": l.sheet, "column": l.column, "rowStart1": l.row_start1, "rowEnd1": l.row_end1}
                for l in p.locations
            ],
            "columnProfiles": [
                {
                    "sheet": cp.sheet,
                    "column": cp.column,
                    "distinctPatternCount": cp.distinct_pattern_count,
                    "classification": cp.classification,
                    "totalFormulaCount": cp.total_formula_count,
                    "totalValueCount": cp.total_value_count,
                    "thisPatternInstanceCount": cp.this_pattern_instance_count,
                    "thisPatternShare": cp.this_pattern_share,
                }
                for cp in p.column_profiles
            ],
        }
        for p in result.inventory.patterns
    ]

    columns_out = [
        {
            "sheet": c.sheet,
            "column": c.column,
            "totalFormulaCount": c.total_formula_count,
            "totalValueCount": c.total_value_count,
            "distinctPatternCount": c.distinct_pattern_count,
            "classification": c.classification,
            "patterns": [
                {"pattern": ps.pattern_text, "instanceCount": ps.instance_count, "share": ps.share}
                for ps in c.patterns
            ],
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
        for c in result.column_profiles.columns
    ]

    accounting_out = [
        {
            "sheetName": a.sheet_name,
            "nonEmptyFormulas": a.non_empty_formulas,
            "matchedFormulas": a.matched_formulas,
            "residueFormulas": a.residue_formulas,
        }
        for a in result.accounting
    ]

    return {
        "captureDate": result.capture.capture_date,
        "inventory": {
            "stampCaptureDate": result.inventory.stamp.capture_date,
            "stampToolCommit": result.inventory.stamp.tool_commit,
            "reliabilityCondition": result.inventory.reliability_condition,
            "residue": _residue_out(result.inventory.residue),
            "patterns": patterns_out,
        },
        "columnProfiles": {
            "stampCaptureDate": result.column_profiles.stamp.capture_date,
            "stampToolCommit": result.column_profiles.stamp.tool_commit,
            "reliabilityCondition": result.column_profiles.reliability_condition,
            "residue": _residue_out(result.column_profiles.residue),
            "columns": columns_out,
        },
        "accounting": accounting_out,
        "spillRunTotal": result.spill_run_total,
        "spillRunResidueCount": result.spill_run_residue_count,
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(
            "usage: python -m sheet_derivation.serialize_stage3 <capture_directory> <output_path>",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage3(formulas_path, values_path)
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
