"""Canonical, deterministic serialization of a Stage1Result, for the
cross-process determinism check (Gate C4) -- same purpose and same shape
as serialize.py/serialize_stage0.py for Stage 0.

Stage1Result stores several plain dicts (pattern text -> PatternInfo,
sheet name -> Counter, ...). Dict/Counter *equality* does not depend on
insertion order, which is why the in-process check
(verify_same_process_determinism) already passes without this module.
What it cannot catch is insertion order itself varying between two
process launches with different PYTHONHASHSEED -- a set/dict-iteration
defect can be perfectly stable within one run and differ on the next.
Catching that requires serializing to an explicitly sorted, canonical
form and comparing bytes from two separate subprocess launches, which is
what this module's output feeds.
"""

import json
import sys
from typing import Any, Dict

from .loader import discover_capture_files
from .serialize import write_canonical_json
from .stage1 import Stage1Result, function_vocabulary, run_stage1


def build_canonical_structure(result: Stage1Result) -> Dict[str, Any]:
    """Every collection Stage 1 produces, explicitly sorted: patterns by
    their own text, per-sheet pattern counters by (sheet order, pattern
    text), the A-to-B split map by pattern text with its split set sorted,
    and the token census by kind name. Nothing here relies on dict or set
    iteration order to already be stable."""
    capture = result.capture

    def pattern_dict_to_list(patterns: Dict[str, Any]):
        return [
            {
                "pattern": pat,
                "instanceCount": info.instance_count,
                "firstSheet": info.first_sheet,
                "firstRow0": info.first_row0,
                "firstCol0": info.first_col0,
                "firstRaw": info.first_raw,
            }
            for pat, info in sorted(patterns.items(), key=lambda kv: kv[0])
        ]

    per_sheet_counts_out = [
        {
            "sheetName": c.sheet_name,
            "nonEmptyFormulas": c.non_empty_formulas,
            "distinctPatternsGateA": c.distinct_patterns_gate_a,
            "distinctPatternsGateB": c.distinct_patterns_gate_b,
        }
        for c in result.per_sheet_counts
    ]

    def per_sheet_pattern_counter_out(per_sheet_counter):
        out = []
        for sheet_name in capture.sheet_order:
            counter = per_sheet_counter.get(sheet_name, {})
            out.append(
                {
                    "sheetName": sheet_name,
                    "patterns": [
                        {"pattern": pat, "count": cnt}
                        for pat, cnt in sorted(counter.items(), key=lambda kv: kv[0])
                    ],
                }
            )
        return out

    a_to_b_split_out = [
        {"gateAPattern": a_pat, "gateBPatterns": sorted(b_pats)}
        for a_pat, b_pats in sorted(result.a_to_b_split.items(), key=lambda kv: kv[0])
    ]

    return {
        "captureDate": capture.capture_date,
        "totalNonEmptyFormulas": result.total_nonempty_formulas,
        "totalDistinctPatternsGateA": result.total_distinct_patterns_gate_a,
        "totalDistinctPatternsGateB": result.total_distinct_patterns_gate_b,
        "perSheetCounts": per_sheet_counts_out,
        "gateAPatterns": pattern_dict_to_list(result.gate_a_patterns),
        "gateBPatterns": pattern_dict_to_list(result.gate_b_patterns),
        "perSheetGateAPatternCounts": per_sheet_pattern_counter_out(result.per_sheet_gate_a_pattern_counts),
        "perSheetGateBPatternCounts": per_sheet_pattern_counter_out(result.per_sheet_gate_b_pattern_counts),
        "aToBSplit": a_to_b_split_out,
        "tokenKindTotals": {k: result.token_kind_totals[k] for k in sorted(result.token_kind_totals)},
        "unknownTokenExamples": [list(ex) for ex in result.unknown_token_examples],
        "functionVocabularyGateA": {
            k: v for k, v in sorted(function_vocabulary(result, use_gate_a=True).items())
        },
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(
            "usage: python -m sheet_derivation.serialize_stage1 <capture_directory> <output_path>",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage1(formulas_path, values_path)
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
