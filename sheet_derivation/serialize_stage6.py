"""Canonical, deterministic serialization of a Stage6Result, for the
cross-process determinism check -- same purpose and shape as
serialize_stage1-5.py. Not the JSONL artifact format; see
stage6_artifacts.py for that.

Everything is written as plain lists in the order the result already
holds, and sets are never iterated unsorted, so this serialization is
itself part of what the cross-process check verifies.
"""

import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage6 import Stage6Result, run_stage6
from .stage6_artifacts import column_line, intended_meta, tier_counts


def build_canonical_structure(result: Stage6Result) -> Dict[str, Any]:
    checkup = result.checkup
    return {
        "present": checkup.present,
        "absentReason": checkup.absent_reason,
        "appsheetTablesCsvFound": checkup.tables_csv_found,
        "appsheetTablesCsvNote": checkup.tables_csv_note,
        "counts": tier_counts(checkup),
        "intended": intended_meta(checkup),
        "columns": [column_line(f) for f in checkup.findings],
        "notExamined": [
            {
                "table": n.table, "column": n.column, "tab": n.tab, "sheetColumn": n.sheet_column,
                "storedFormula": n.stored_formula, "reason": n.reason,
            }
            for n in checkup.not_examined
        ],
        "residue": [
            {"what": r.what, "locations": list(r.locations), "defeatingConstruct": r.defeating_construct,
             "consequence": r.consequence}
            for r in sorted(checkup.residue, key=lambda r: (r.locations, r.defeating_construct, r.what))
        ],
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3, 4, 5):
        print(
            "usage: python -m sheet_derivation.serialize_stage6 <capture_directory> <output_path> "
            "[appside_parse_dir] [app_export_html] [intended_dir]",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv[0], argv[1]
    appside_parse_dir = argv[2] if len(argv) >= 3 else None
    app_export_html = argv[3] if len(argv) >= 4 else None
    intended_dir = argv[4] if len(argv) == 5 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage6(
        formulas_path, values_path, appside_parse_dir=appside_parse_dir, app_export_html_path=app_export_html,
        intended_dir=intended_dir,
    )
    write_canonical_json(output_path, build_canonical_structure(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
