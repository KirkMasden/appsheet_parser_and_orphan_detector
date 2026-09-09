"""Canonical, deterministic serialization of a Stage2Result, for the
cross-process determinism check (Gate C4) -- same purpose and same shape
as serialize.py/serialize_stage0.py/serialize_stage1.py before it.
"""

import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage2 import Stage2Result, run_stage2


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


def build_canonical_structure(result: Stage2Result) -> Dict[str, Any]:
    edges_out = [
        {
            "sourceSheet": e.source_sheet,
            "sourceColumn": e.source_column,
            "targetSheet": e.target_sheet,
            "targetColumn": e.target_column,
            "patterns": list(e.patterns),
            "cells": list(e.cells),
        }
        for e in result.graph.edges
    ]

    dangling_out = [
        {
            "name": d.name,
            "classification": d.classification,
            "occurrences": [
                {"cell": o.cell, "rawFormula": o.raw_formula, "evaluatedValue": o.evaluated_value}
                for o in d.occurrences
            ],
        }
        for d in result.dangling.entries
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
        "graph": {
            "stampCaptureDate": result.graph.stamp.capture_date,
            "stampToolCommit": result.graph.stamp.tool_commit,
            "reliabilityCondition": result.graph.reliability_condition,
            "residue": _residue_out(result.graph.residue),
            "edges": edges_out,
        },
        "dangling": {
            "stampCaptureDate": result.dangling.stamp.capture_date,
            "stampToolCommit": result.dangling.stamp.tool_commit,
            "reliabilityCondition": result.dangling.reliability_condition,
            "residue": _residue_out(result.dangling.residue),
            "entries": dangling_out,
        },
        "accounting": accounting_out,
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(
            "usage: python -m sheet_derivation.serialize_stage2 <capture_directory> <output_path>",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage2(formulas_path, values_path)
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
