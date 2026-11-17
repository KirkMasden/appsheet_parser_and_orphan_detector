"""The short, machine-readable summary of the formula checkup (formula
checkup build stage 5): `stage6_formula_checkup_summary.json`, written by
stage6_artifacts.write_stage6_artifacts beside the full output.

It is built from the same Stage6Result the JSONL is written from. It never
recomputes a finding, never reads a file, and never reads the JSONL back;
it only selects, groups and orders what stage 6 already states. It is
DERIVED from the checkup and regenerable; the JSONL is authoritative. It is
small on purpose: no formula texts and no per-row lists beyond the short
row ranges the artifact already carries.

It holds what the AI needs to give the post-parse sketch without opening
the JSONL. It contains no sketch wording: the statements in it are the
checkup's own (per column, as stage 6 writes them) and one short factual
statement per group of minor findings.

How the tiers map onto the sketch (for orientation; the wording is not
written here): `raised` findings are raised, with their grade; `minor`
findings get one line suggesting the user confirm they are intended; "not a
problem" is not mentioned (only counted); `runProblems` belong to the line
about problems with the run; intended items are counted and listed under
`intended`, not among the findings; orphan entries are stored here so the
AI can apply them without opening the record file.
"""

import json
from typing import Any, Dict, List

from .stage6 import (
    KIND_EDITS_ONLY,
    KIND_NEITHER,
    S2A,
    S2B,
    S1,
    S3,
    SITUATION_NAMES,
    TIER_MINOR,
    TIER_RAISED,
    TIER_RUN_PROBLEM,
    ColumnFinding,
    Stage6Result,
    format_row_ranges,
)
from .stage6_artifacts import JSONL_NAME, tier_counts

SUMMARY_NAME = "stage6_formula_checkup_summary.json"
SUMMARY_FORMAT = 1


def _rows_that_matter(f: ColumnFinding) -> str:
    """The non-matching rows for S2A and S2B, the formula rows for S1,
    none otherwise -- as one range string, from what stage 6 recorded."""
    if f.situation in (S2A, S2B):
        rows = [r for g in f.differing_groups for r in g.rows] + list(f.no_formula_rows)
        return format_row_ranges(rows)
    if f.situation == S1:
        return format_row_ranges([r for g in f.differing_groups for r in g.rows] + [u.row for u in f.uncompared])
    return ""


def _lapsed(f: ColumnFinding):
    return None if f.lapsed is None else {"dateDeclared": f.lapsed.date_declared, "note": f.lapsed.note}


def _raised_item(f: ColumnFinding) -> Dict[str, Any]:
    return {
        "rank": f.rank,
        "table": f.table,
        "column": f.column,
        "tab": f.tab,
        "sheetColumn": f.sheet_column,
        "situation": f.situation,
        "grade": f.grade,
        "rows": _rows_that_matter(f),
        "declarationLapsed": _lapsed(f),
        "finding": f.finding,
        "advice": f.advice,
    }


_ALLOWS_TEXT = {
    KIND_NEITHER: "the table allows neither adds nor edits",
    KIND_EDITS_ONLY: (
        "the table allows edits but not adds, and an edit did not write a stored formula back in the "
        "2026-11-14 observation"
    ),
}

_SITUATION_TEXT = {
    S2A: "the stored formulas differ from the sheet's formulas",
    S2B: "the stored formulas differ from the sheet's formulas in a few rows",
    S3: "the app stores formulas that the sheet no longer holds",
}


def _minor_statement(situation: str, allows: str, assumed: bool) -> str:
    """One short factual statement for a group of minor findings. Minor
    findings arise only where the table does not allow adds, so `allows` is
    edits-only or neither."""
    text = (
        f"{_SITUATION_TEXT.get(situation, SITUATION_NAMES[situation])}; "
        f"{_ALLOWS_TEXT.get(allows, 'see each column')}, so this causes no trouble now"
    )
    if assumed:
        text += " (the table's update setting was assumed, not read)"
    return text


def _group(findings: List[ColumnFinding], key) -> List[List[ColumnFinding]]:
    """Groups in order of first appearance; the input order is the order
    that decides ties, so it must already be the order stage 6 ranks in."""
    groups: Dict[Any, List[ColumnFinding]] = {}
    for f in findings:
        groups.setdefault(key(f), []).append(f)
    return list(groups.values())


def write_summary(path: str, summary: Dict[str, Any]) -> None:
    """Indented, key order as built (it is the order a reader wants), one
    trailing newline; the same summary always gives the same bytes."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def build_summary(result: Stage6Result) -> Dict[str, Any]:
    checkup = result.checkup
    counts = tier_counts(checkup)
    summary: Dict[str, Any] = {
        "kind": "formula-checkup-summary",
        "format": SUMMARY_FORMAT,
        "derivedFrom": (
            f"{JSONL_NAME}, written by the same run; this file is DERIVED and regenerable, and that file "
            "is authoritative. It holds no formula texts."
        ),
        "present": checkup.present,
        "absentReason": checkup.absent_reason,
        "appName": checkup.app_name,
        "captureDate": checkup.stamp.capture_date,
        "toolCommit": checkup.stamp.tool_commit,
        "appsheetTablesCsv": {"found": checkup.tables_csv_found, "note": checkup.tables_csv_note},
        "intendedRecord": {"state": checkup.record_state, "file": checkup.record_file, "note": checkup.record_note},
        "counts": {
            "examined": counts["examined"],
            "raised": counts["raised"],
            "raisedLikely": counts["raisedLikely"],
            "raisedPossible": counts["raisedPossible"],
            "minor": counts["minor"],
            "notAProblem": counts["notAProblem"],
            "runProblem": counts["runProblem"],
            "notExamined": len(checkup.not_examined),
            "intended": counts["intendedCount"],
            "lapsedDeclarations": len(checkup.lapsed_entries),
            "notAppliedEntries": len(checkup.not_applied_entries),
            "orphanEntries": checkup.orphan_entry_count,
        },
    }

    live = [f for f in checkup.findings if f.intended is None]  # a matched declaration is not a finding

    raised = sorted((f for f in live if f.tier == TIER_RAISED), key=lambda f: f.rank)
    summary["raised"] = [_raised_item(f) for f in raised]
    summary["raisedGroups"] = [
        {
            "table": g[0].table,
            "situation": g[0].situation,
            "situationName": SITUATION_NAMES[g[0].situation],
            "grade": g[0].grade,
            "tableAllows": g[0].allows,
            "count": len(g),
            "bestRank": g[0].rank,
            "columns": [f.column for f in g],
        }
        for g in _group(raised, lambda f: (f.table, f.situation, f.grade))
    ]

    # Minor findings keep stage 6's own order (table, sheet column position, column name);
    # groups are ordered by table, then situation.
    minor = [f for f in live if f.tier == TIER_MINOR]
    minor_groups = _group(minor, lambda f: (f.table, f.situation))
    minor_groups.sort(key=lambda g: (g[0].table, g[0].situation))
    summary["minor"] = [
        {
            "table": g[0].table,
            "situation": g[0].situation,
            "situationName": SITUATION_NAMES[g[0].situation],
            "count": len(g),
            "columns": [f.column for f in g],
            "updateMode": g[0].update_mode,
            "tableAllows": g[0].allows,
            "settingAssumed": g[0].setting_assumed,
            "declarationLapsed": [f.column for f in g if f.lapsed is not None],
            "statement": _minor_statement(g[0].situation, g[0].allows, g[0].setting_assumed),
        }
        for g in minor_groups
    ]

    summary["runProblems"] = [
        {
            "table": f.table,
            "column": f.column,
            "reason": "; ".join(sorted({u.reason for u in f.uncompared})),
        }
        for f in live if f.tier == TIER_RUN_PROBLEM
    ]
    summary["notExamined"] = [
        {"table": n.table, "column": n.column, "reason": n.reason} for n in checkup.not_examined
    ]
    summary["intended"] = [
        {
            "table": f.table,
            "column": f.column,
            "situation": f.situation,
            "tier": f.tier,
            "grade": f.grade,
            "dateDeclared": f.intended.date_declared,
            "note": f.intended.note,
        }
        for f in checkup.findings if f.intended is not None
    ]
    summary["lapsed"] = [
        {"table": t, "column": c, "dateDeclared": d, "note": n} for t, c, d, n in checkup.lapsed_entries
    ]
    summary["notApplied"] = [
        {"table": t, "column": c, "dateDeclared": d, "reason": r} for t, c, d, r in checkup.not_applied_entries
    ]
    summary["orphanEntries"] = [
        {"orphanKind": k, "name": n, "dateDeclared": d, "note": note} for k, n, d, note in checkup.orphan_entries
    ]
    return summary
