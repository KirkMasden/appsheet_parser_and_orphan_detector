"""Canonical, deterministic serialization of a Stage5Result, for the
cross-process determinism check (Gate C4) -- same purpose and shape as
serialize_stage1-4.py. Not the JSONL artifact format; see
stage5_artifacts.py for that. Runs the join in ABSENT mode (no app-side
parse directory) so this check needs no private data -- the join logic
itself is exercised by the real-capture stage 5 gate script instead,
outside this repository.
"""

import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage5 import Stage5Result, run_stage5


def build_canonical_structure(result: Stage5Result) -> Dict[str, Any]:
    join = result.join
    tables_out = []
    for t in join.tables:
        tables_out.append(
            {
                "table": t.table,
                "tableState": t.table_state,
                "matchedTab": t.matched_tab,
                "tabSource": t.tab_source,
                "sourceWorksheet": t.source_worksheet,
                "headerVerdict": t.header_verdict,
                "headerSource": t.header_source,
                "columns": [
                    {
                        "column": c.column, "isVirtual": c.is_virtual, "state": c.state,
                        "matchedLabelText": c.matched_label_text,
                        "nearMissCandidates": list(c.near_miss_candidates),
                    }
                    for c in t.column_results
                ],
                "labels": [
                    {
                        "sheetColumn": l.sheet_column, "labelText": l.label_text, "state": l.state,
                        "matchedAppColumn": l.matched_app_column,
                        "nearMissCandidates": list(l.near_miss_candidates),
                    }
                    for l in t.label_results
                ],
            }
        )
    return {
        "present": join.present,
        "tabPairing": join.tab_pairing,
        "tables": tables_out,
        "diagnosticCount": len(join.diagnostics),
        "residue": [
            {"what": r.what, "locations": list(r.locations), "defeatingConstruct": r.defeating_construct,
             "consequence": r.consequence}
            for r in sorted(join.residue, key=lambda r: (r.locations, r.defeating_construct, r.what))
        ],
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3, 4):
        print(
            "usage: python -m sheet_derivation.serialize_stage5 <capture_directory> <output_path> "
            "[appside_parse_dir] [app_export_html]",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv[0], argv[1]
    appside_parse_dir = argv[2] if len(argv) >= 3 else None
    app_export_html = argv[3] if len(argv) == 4 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage5(
        formulas_path, values_path, appside_parse_dir=appside_parse_dir, app_export_html_path=app_export_html
    )
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
