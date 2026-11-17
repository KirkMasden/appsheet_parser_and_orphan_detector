"""Stage 6: the formula checkup's per-column comparison and judgment
(formula checkup build stage 3).

For each app column that is filled by a spreadsheet formula, or whose sheet
column holds formulas, this stage compares what the sheet holds with the
formula AppSheet stores for the column, names the situation, and judges
whether it can cause trouble given what the table is allowed to do.

READS, NEVER RECOMPUTES. The table-to-tab pairing and the label lookup
(matched app column -> sheet column) come from stage 5's join; the header
row of each tab comes from stage 4's schema (reached through the stage 5
result); the formulas and values come from the capture, through loader.py;
the stored formulas, keys and virtual flags come from `appsheet_columns.csv`
and the update settings from `appsheet_tables.csv` (both read by
appside_formulas.py, which leaves stage 5's reader untouched). Every formula
comparison is made by r1c1.py (`compare_formulas`); this module contains no
comparer of its own, and groups differing formulas only by the canonical
text r1c1.py itself returns.

ONLY READS. It never changes the app, the sheet, the capture or any
existing output folder.

THE CHECKUP IS ONLY AS GOOD AS ITS INPUTS: it rests on the app-side parse
and the capture belonging to the same version of the app (stage 5's
provenance block records what is known about that), and on stage 4's header
row for each tab. See the reliability condition written into the artifact.

Rules implemented here come from the plan with its three addenda (Addendum
2, decision 4, for which rows count) and the build prompt of 2026-11-17;
the judgment table is kept in one place, JUDGMENT_TABLE, so it can be
adjusted.
"""

import dataclasses
import os
import sys
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .appside_formulas import (
    AppFormulaColumn,
    discover_appside_tables_csv,
    load_appside_formula_columns,
    load_appside_tables,
)
from .appside_parse import AppSideParseError, discover_appside_columns_csv, hash_file
from .artifact import ArtifactBase
from .coordinates import col_to_letters, letters_to_col
from .counts import is_nonempty
from .loader import discover_capture_files
from .r1c1 import (
    PLACEHOLDER_STORED_TEXT,
    VERDICT_DIFFERS,
    VERDICT_PLACEHOLDER,
    VERDICT_SAME,
    compare_formulas,
    unattested,
)
from .residue import ResidueEntry, build_stamp
from .stage4 import HEADER_SOURCE_DECLARED, HEADER_VERDICT_IDENTIFIED
from .stage5 import (
    COLUMN_STATE_EXACT_MATCH,
    COLUMN_STATE_HEADER_NOT_IDENTIFIED,
    COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED,
    COLUMN_STATE_TABLE_NO_TAB,
    COLUMN_STATE_UNMATCHED,
    COLUMN_STATE_WHITESPACE_NEAR_MISS,
    LABEL_STATE_EXACT_MATCH,
    LABEL_STATE_REPEATED,
    LABEL_STATE_WHITESPACE_NEAR_MISS,
    Stage5Result,
    TableJoinEntry,
    run_stage5,
)

# ---------------------------------------------------------------------------
# Situations
# ---------------------------------------------------------------------------

S1 = "S1"  # sheet formulas, nothing stored
S2A = "S2A"  # stored formula differs, Case A
S2B = "S2B"  # stored formula differs, Case B
S3 = "S3"  # stored formula, none in the sheet
S4 = "S4"  # placeholder stored
S5 = "S5"  # empty table
S6 = "S6"  # everything agrees
COULD_NOT_COMPARE = "could-not-compare"

SITUATION_NAMES = {
    S1: "sheet formulas, nothing stored",
    S2A: "stored formula differs (Case A)",
    S2B: "stored formula differs (Case B)",
    S3: "stored formula, none in the sheet",
    S4: "placeholder stored",
    S5: "empty table",
    S6: "everything agrees",
    COULD_NOT_COMPARE: "could not compare",
}

# ---------------------------------------------------------------------------
# What the table allows
# ---------------------------------------------------------------------------

KIND_ADDS = "adds"  # the table allows adds, whether or not it allows edits
KIND_EDITS_ONLY = "edits-only"  # allows edits but not adds
KIND_NEITHER = "neither"  # allows neither adds nor edits

# The eight values AppSheet documents for "Are updates allowed?", each with
# (adds allowed, edits allowed).
UPDATE_MODES: Dict[str, Tuple[bool, bool]] = {
    "ALL_CHANGES": (True, True),
    "ADDS_ONLY": (True, False),
    "ADDS_AND_UPDATES": (True, True),
    "ADDS_AND_DELETES": (True, False),
    "UPDATES_ONLY": (False, True),
    "UPDATES_AND_DELETES": (False, True),
    "DELETES_ONLY": (False, False),
    "READ_ONLY": (False, False),
}

SETTING_EXPORTED = "exported value"
SETTING_ASSUMED_EMPTY = "assumed: the setting is empty"
SETTING_ASSUMED_UNRECOGNIZED = "assumed: the setting is not one of the eight known values (it may be an expression)"
SETTING_ASSUMED_NOT_LISTED = "assumed: the table is not listed in appsheet_tables.csv"
SETTING_ASSUMED_NO_FILE = "assumed: appsheet_tables.csv is absent (a parse made before 2026-11-10)"

TABLES_CSV_ABSENT_NOTE = (
    "appsheet_tables.csv is absent (a parse made before 2026-11-10), so every table is treated as "
    "allowing both adds and edits; every judgment below that depends on what a table allows rests on "
    "that assumption"
)

# ---------------------------------------------------------------------------
# The judgment table. Tiers: "raised" (the sketch raises it), "minor" (the
# sketch gives it one "I noticed that..." line), "not a problem" (full output
# only), plus "run problem" for a column that could not be compared at all.
# Grades, for raised findings only: "likely" or "possible" -- how sure, not
# how serious. `priority` orders the raised findings (1 ranks highest); the
# build prompt names only that S1 with adds ranks highest, the rest of the
# order is this table's own choice and is easy to change here.
# ---------------------------------------------------------------------------

TIER_RAISED = "raised"
TIER_MINOR = "minor"
TIER_NOT_A_PROBLEM = "not a problem"
TIER_RUN_PROBLEM = "run problem"

GRADE_LIKELY = "likely"
GRADE_POSSIBLE = "possible"


@dataclass(frozen=True)
class Judgment:
    tier: str
    grade: Optional[str]
    priority: Optional[int]  # only for raised findings; 1 ranks highest


# (kind, situation) -> Judgment
JUDGMENT_TABLE: Dict[Tuple[str, str], Judgment] = {
    # The table allows adds (whether or not it allows edits).
    (KIND_ADDS, S1): Judgment(TIER_RAISED, GRADE_LIKELY, 1),
    (KIND_ADDS, S2A): Judgment(TIER_RAISED, GRADE_LIKELY, 2),
    (KIND_ADDS, S3): Judgment(TIER_RAISED, GRADE_LIKELY, 3),
    (KIND_ADDS, S2B): Judgment(TIER_RAISED, GRADE_LIKELY, 4),
    (KIND_ADDS, S4): Judgment(TIER_RAISED, GRADE_POSSIBLE, 6),
    (KIND_ADDS, S5): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_ADDS, S6): Judgment(TIER_NOT_A_PROBLEM, None, None),
    # The table allows edits but not adds.
    (KIND_EDITS_ONLY, S1): Judgment(TIER_RAISED, GRADE_POSSIBLE, 5),
    (KIND_EDITS_ONLY, S2A): Judgment(TIER_MINOR, None, None),
    (KIND_EDITS_ONLY, S2B): Judgment(TIER_MINOR, None, None),
    (KIND_EDITS_ONLY, S3): Judgment(TIER_MINOR, None, None),
    (KIND_EDITS_ONLY, S4): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_EDITS_ONLY, S5): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_EDITS_ONLY, S6): Judgment(TIER_NOT_A_PROBLEM, None, None),
    # The table allows neither adds nor edits.
    (KIND_NEITHER, S1): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_NEITHER, S2A): Judgment(TIER_MINOR, None, None),
    (KIND_NEITHER, S2B): Judgment(TIER_MINOR, None, None),
    (KIND_NEITHER, S3): Judgment(TIER_MINOR, None, None),
    (KIND_NEITHER, S4): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_NEITHER, S5): Judgment(TIER_NOT_A_PROBLEM, None, None),
    (KIND_NEITHER, S6): Judgment(TIER_NOT_A_PROBLEM, None, None),
}

# "Could not compare" is judged the same way under every kind of setting.
RUN_PROBLEM_JUDGMENT = Judgment(TIER_RUN_PROBLEM, None, None)

# ---------------------------------------------------------------------------
# Row bases
# ---------------------------------------------------------------------------

ROW_BASIS_KEY = "key"
ROW_BASIS_ANY_PAIRED = "any-paired-column"

STORED_EMPTY = "empty"
STORED_PLACEHOLDER = "placeholder"
STORED_FORMULA = "formula"

# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DifferingGroup:
    """Counted rows whose sheet formulas convert to the same canonical text
    and differ from the stored formula (or, when nothing is stored, simply
    hold a formula). `raw_formula` and `converted` are those of
    `representative_row`, the first row of the group."""

    canonical: str
    rows: Tuple[int, ...]
    representative_row: int
    raw_formula: str
    converted: Optional[str]
    by_convention: Tuple[str, ...]
    note: str


@dataclass(frozen=True)
class UncomparedCell:
    row: int
    cell: str
    reason: str
    raw_formula: str


@dataclass(frozen=True)
class ColumnFinding:
    table: str
    column: str
    tab: str
    sheet_column: str
    label_state: str  # the join's state for the app column: exact-match / whitespace-near-miss
    label_text: str
    header_row1: int
    header_source: Optional[str]
    header_verdict: Optional[str]
    row_basis_uncertain: bool
    update_mode: Optional[str]  # as exported; None when the table has no setting to read
    adds_allowed: bool
    edits_allowed: bool
    setting_basis: str
    setting_assumed: bool
    row_basis: str  # ROW_BASIS_*
    row_basis_detail: str
    key_column: Optional[str]
    key_sheet_column: Optional[str]
    counted_rows: Tuple[int, ...]
    stored_formula: str
    stored_state: str
    matching_rows: Tuple[int, ...]
    differing_groups: Tuple[DifferingGroup, ...]
    placeholder_rows: Tuple[int, ...]  # counted rows holding a formula while the placeholder is stored
    no_formula_rows: Tuple[int, ...]
    uncompared: Tuple[UncomparedCell, ...]
    formula_row_count: int  # counted rows holding any formula, compared or not
    value_only_row_count: int  # counted rows with a value and no formula
    blank_row_count: int  # counted rows with neither
    by_convention: Tuple[str, ...]
    situation: str
    allows: str  # KIND_*: what the table's setting allows
    tier: str
    grade: Optional[str]
    rank: Optional[int]
    finding: str
    advice: str
    notes: Tuple[str, ...]


@dataclass(frozen=True)
class NotExaminedColumn:
    table: str
    column: str
    stored_formula: str
    reason: str
    tab: Optional[str]
    sheet_column: Optional[str]


@dataclass(frozen=True)
class CheckupArtifact(ArtifactBase):
    present: bool
    absent_reason: Optional[str]
    tables_csv_found: Optional[bool]
    tables_csv_note: Optional[str]
    appside_parse_dir: Optional[str]
    input_file_hashes: Tuple[Tuple[str, str], ...]
    findings: Tuple[ColumnFinding, ...]
    not_examined: Tuple[NotExaminedColumn, ...]


@dataclass(frozen=True)
class Stage6Result:
    stage5: Optional[Stage5Result]
    checkup: CheckupArtifact


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def format_row_ranges(rows) -> str:
    """Row numbers as compact, lossless ranges: (2,3,4,6) -> '2-4, 6'. An
    empty collection gives ''."""
    ordered = sorted(set(rows))
    parts: List[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        parts.append(str(ordered[i]) if i == j else f"{ordered[i]}-{ordered[j]}")
        i = j + 1
    return ", ".join(parts)


def interpret_update_mode(
    table: str, tables_csv: Optional[Dict[str, str]]
) -> Tuple[Optional[str], bool, bool, str, bool]:
    """(update_mode as exported or None, adds allowed, edits allowed,
    basis text, assumed). An empty, unrecognized or expression-valued
    setting, a table missing from the file, and a missing file are all
    treated as allowing both, and the basis says which."""
    if tables_csv is None:
        return None, True, True, SETTING_ASSUMED_NO_FILE, True
    if table not in tables_csv:
        return None, True, True, SETTING_ASSUMED_NOT_LISTED, True
    raw = tables_csv[table]
    stripped = raw.strip()
    if stripped == "":
        return raw, True, True, SETTING_ASSUMED_EMPTY, True
    if stripped in UPDATE_MODES:
        adds, edits = UPDATE_MODES[stripped]
        return raw, adds, edits, SETTING_EXPORTED, False
    return raw, True, True, SETTING_ASSUMED_UNRECOGNIZED, True


def setting_kind(adds_allowed: bool, edits_allowed: bool) -> str:
    if adds_allowed:
        return KIND_ADDS
    if edits_allowed:
        return KIND_EDITS_ONLY
    return KIND_NEITHER


def _stored_state(stored: str) -> str:
    if stored.strip() == "":
        return STORED_EMPTY
    if stored == PLACEHOLDER_STORED_TEXT:
        return STORED_PLACEHOLDER
    return STORED_FORMULA


# ---------------------------------------------------------------------------
# Pairing an app column with its sheet column (reads stage 5's join)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pairing:
    sheet_column: Optional[str]
    label_state: Optional[str]
    label_text: Optional[str]
    reason: Optional[str]  # why there is no pairing; None when paired


def _pair_app_column(entry: TableJoinEntry, app_column: str) -> _Pairing:
    """The sheet column behind `app_column`, through the join's labels
    (the join's own `matched_sheet_column` is never filled). Only a clean
    pairing is returned: an exact match, or a whitespace near-miss with
    one candidate on each side."""
    results = [c for c in entry.column_results if c.column == app_column]
    if not results:
        return _Pairing(None, None, None, "the app column is not in stage 5's join")
    cr = results[0]
    if cr.state == COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED:
        return _Pairing(None, None, None, "the column is virtual, so it has no sheet column")
    if cr.state == COLUMN_STATE_TABLE_NO_TAB:
        return _Pairing(None, None, None, "the table has no tab in the capture (a native table, or a worksheet the capture lacks)")
    if cr.state == COLUMN_STATE_HEADER_NOT_IDENTIFIED:
        return _Pairing(
            None, None, None,
            "the header row of the table's tab was not identified (stage 4 verdict "
            f"{entry.header_verdict!r}), so the sheet column cannot be located and the row basis is uncertain",
        )
    if cr.state == COLUMN_STATE_UNMATCHED:
        if any(l.label_text == app_column and l.state == LABEL_STATE_REPEATED for l in entry.label_results):
            return _Pairing(None, None, None, "the column's name is a header label repeated within the tab, so the sheet column is ambiguous")
        return _Pairing(None, None, None, "no header label of the tab matches the column's name")
    if cr.state == COLUMN_STATE_EXACT_MATCH:
        labels = [
            l for l in entry.label_results
            if l.matched_app_column == app_column and l.state == LABEL_STATE_EXACT_MATCH
        ]
        if len(labels) != 1:
            return _Pairing(None, None, None, f"the join gives {len(labels)} header labels for this column, not exactly one")
        return _Pairing(labels[0].sheet_column, COLUMN_STATE_EXACT_MATCH, labels[0].label_text, None)
    if cr.state == COLUMN_STATE_WHITESPACE_NEAR_MISS:
        if len(cr.near_miss_candidates) != 1:
            return _Pairing(
                None, None, None,
                f"the column's name matches {len(cr.near_miss_candidates)} header labels after whitespace is collapsed, so no single sheet column is chosen",
            )
        text = cr.near_miss_candidates[0]
        labels = [
            l for l in entry.label_results
            if l.label_text == text and l.state == LABEL_STATE_WHITESPACE_NEAR_MISS
            and app_column in l.near_miss_candidates
        ]
        if len(labels) != 1 or len(labels[0].near_miss_candidates) != 1:
            return _Pairing(
                None, None, None,
                "the header label that nearly matches this column also nearly matches another app column, so no single sheet column is chosen",
            )
        return _Pairing(labels[0].sheet_column, COLUMN_STATE_WHITESPACE_NEAR_MISS, labels[0].label_text, None)
    return _Pairing(None, None, None, f"the join's state for this column ({cr.state!r}) is not one this stage pairs")


# ---------------------------------------------------------------------------
# Text of the findings
# ---------------------------------------------------------------------------

_DATE_NOTE = "2026-11-14"


def _plural(n: int, one: str, many: Optional[str] = None) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many if many is not None else one + 's'}"


def _group_phrases(groups: Tuple[DifferingGroup, ...], no_formula_rows: Tuple[int, ...]) -> List[str]:
    phrases = []
    for g in groups:
        phrases.append(f"{_plural(len(g.rows), 'row')} ({format_row_ranges(g.rows)}) with a different formula")
    if no_formula_rows:
        phrases.append(f"{_plural(len(no_formula_rows), 'row')} ({format_row_ranges(no_formula_rows)}) with no formula")
    return phrases


def _compose(
    situation: str,
    kind: str,
    counted: int,
    matching: Tuple[int, ...],
    groups: Tuple[DifferingGroup, ...],
    no_formula_rows: Tuple[int, ...],
    formula_row_count: int,
    formula_rows: Tuple[int, ...],
    value_only: int,
    blank: int,
    uncompared: Tuple[UncomparedCell, ...],
) -> Tuple[str, str]:
    """(finding, advice) in plain English for a situation under a kind of
    setting. Both may be empty strings."""
    n = counted
    if situation == COULD_NOT_COMPARE:
        reasons = sorted({u.reason for u in uncompared})
        return (
            f"None of the {_plural(len(uncompared), 'formula cell')} in this column could be compared with "
            f"the stored formula ({'; '.join(reasons)}), so no judgment was made.",
            "",
        )
    if situation == S1:
        finding = (
            f"The sheet column holds a formula in {formula_row_count} of the {n} counted rows "
            f"({format_row_ranges(formula_rows)}), but the app stores no formula for this column."
        )
        if kind == KIND_ADDS:
            advice = (
                "Rows the app adds will not get the formula, and a third-party report says a new row can erase it. "
                "If the formula is meant to apply to new rows, make the formulas in the column agree and then "
                "regenerate the table in the AppSheet editor so that the app stores it (AppSheet stores a "
                "column's formula only when every cell agrees)."
            )
        elif kind == KIND_EDITS_ONLY:
            advice = (
                "The table allows edits but not adds. AppSheet does not know this column as a formula column, so "
                "an edit to such a row might write the computed value over the formula. This is an untested inference."
            )
        else:
            advice = "The table allows neither adds nor edits, so the app does not write to these rows."
        return finding, advice
    if situation in (S2A, S2B):
        m = len(matching)
        others = ", and ".join(_group_phrases(groups, no_formula_rows))
        if situation == S2A:
            head = f"The stored formula matches {m} of the {n} counted rows"
            if m == 0:
                head = f"The stored formula matches none of the {n} counted rows"
            finding = f"{head}. The other counted rows have: {others}."
        else:
            finding = (
                f"The stored formula matches {m} of the {n} counted rows, more than any one group of the other "
                f"rows. The rows that do not match are: {others}."
            )
        if kind == KIND_ADDS and situation == S2A:
            advice = (
                "New rows the app adds get the stored formula, which is out of date for the rows that differ. "
                "Advice: regenerate the table in the AppSheet editor so that the stored formula is refreshed from the sheet."
            )
        elif kind == KIND_ADDS:
            advice = (
                "Adding rows causes no trouble, since new rows get the normal formula. Advice: make the odd rows "
                "match the rest before regenerating the table, because AppSheet stores a column's formula only "
                "when every cell agrees; regenerating first could leave the column with no stored formula (a risk, "
                "not a certainty)."
            )
        elif kind == KIND_EDITS_ONLY:
            advice = (
                f"The table allows edits but not adds. An observation of {_DATE_NOTE} found that an edit did not "
                "write a stored formula back, so this causes no trouble now."
            )
        else:
            advice = (
                "The table allows neither adds nor edits, so this causes no trouble now; you may want to confirm "
                "that the difference is intended."
            )
        return finding, advice
    if situation == S3:
        finding = (
            f"The app stores a formula for this column, but none of the {n} counted rows holds a formula "
            f"in the sheet ({_plural(value_only, 'row')} hold a plain value, {_plural(blank, 'row')} hold nothing)."
        )
        if kind == KIND_ADDS:
            advice = (
                "New rows the app adds get a formula the sheet no longer uses (often a sign that the table was "
                "not regenerated after the formulas were removed). Advice: regenerate the table, or put the "
                "formula back in the sheet if it is still wanted."
            )
        elif kind == KIND_EDITS_ONLY:
            advice = (
                f"The table allows edits but not adds. An observation of {_DATE_NOTE} found that an edit did not "
                "write a stored formula back, so this causes no trouble now."
            )
        else:
            advice = (
                "The table allows neither adds nor edits, so this causes no trouble now; you may want to confirm "
                "that it is intended."
            )
        return finding, advice
    if situation == S4:
        finding = (
            f"The app stores the placeholder text {PLACEHOLDER_STORED_TEXT} for this column. In the {n} counted "
            f"rows the sheet column holds a formula in {formula_row_count}, a plain value and no formula in "
            f"{value_only}, and nothing in {blank}."
        )
        if kind == KIND_ADDS:
            advice = (
                "One third-party report describes a new row writing the placeholder text into the sheet and "
                "breaking a spill. This checkup makes no claim about whether a spill fills this column."
            )
        elif kind == KIND_EDITS_ONLY:
            advice = (
                f"Observations of {_DATE_NOTE} found that edits leave such columns alone, so this is not a "
                "problem for a table that allows edits but not adds."
            )
        else:
            advice = ""
        return finding, advice
    if situation == S5:
        return (
            "The table is empty: no row counts, so nothing could be compared.",
            "AppSheet keeps a formula for this column. Regenerating the table while it is empty may lose that formula.",
        )
    if situation == S6:
        return f"Every counted row ({n}) matches the stored formula.", ""
    raise ValueError(f"unknown situation {situation!r}")


# ---------------------------------------------------------------------------
# One column
# ---------------------------------------------------------------------------


def _judge(kind: str, situation: str) -> Judgment:
    if situation == COULD_NOT_COMPARE:
        return RUN_PROBLEM_JUDGMENT
    return JUDGMENT_TABLE[(kind, situation)]


def _examine_column(
    *,
    table: str,
    app_column: AppFormulaColumn,
    pairing: _Pairing,
    tab: str,
    header_row1: int,
    header_source: Optional[str],
    header_verdict: Optional[str],
    row_basis_uncertain: bool,
    formula_rows_grid,
    value_rows_grid,
    row_count: int,
    row_basis: str,
    row_basis_detail: str,
    key_column: Optional[str],
    key_sheet_column: Optional[str],
    basis_rows: frozenset,
    update_mode: Optional[str],
    adds_allowed: bool,
    edits_allowed: bool,
    setting_basis: str,
    setting_assumed: bool,
) -> Optional[ColumnFinding]:
    """Examines one paired column. Returns None when the column has neither
    a formula below the header row nor a stored formula (not examined by
    the prompt's own criteria, and so not listed either)."""
    col0 = letters_to_col(pairing.sheet_column)
    col1 = col0 + 1
    stored = app_column.spreadsheet_formula
    stored_state = _stored_state(stored)

    formula_rows_below = [
        r for r in range(header_row1 + 1, row_count + 1) if is_nonempty(formula_rows_grid[r - 1][col0])
    ]
    if not formula_rows_below and stored_state == STORED_EMPTY:
        return None

    counted = sorted(set(basis_rows) | set(formula_rows_below))

    matching: List[int] = []
    groups: "OrderedDict[str, List[Tuple[int, object]]]" = OrderedDict()
    placeholder_rows: List[int] = []
    no_formula: List[int] = []
    uncompared: List[UncomparedCell] = []
    formula_row_list: List[int] = []
    flags = set()
    value_only = 0
    blank = 0
    for r in counted:
        f = formula_rows_grid[r - 1][col0]
        if not is_nonempty(f):
            no_formula.append(r)
            if is_nonempty(value_rows_grid[r - 1][col0]):
                value_only += 1
            else:
                blank += 1
            continue
        formula_row_list.append(r)
        result = compare_formulas(f, r, col1, stored)
        if result.verdict == VERDICT_SAME:
            matching.append(r)
            flags.update(result.by_convention)
        elif result.verdict == VERDICT_DIFFERS:
            groups.setdefault(result.compared_sheet, []).append((r, result))
            flags.update(result.by_convention)
        elif result.verdict == VERDICT_PLACEHOLDER:
            placeholder_rows.append(r)
        else:
            uncompared.append(
                UncomparedCell(row=r, cell=f"{col_to_letters(col0)}{r}", reason=result.reason or "", raw_formula=f)
            )

    group_records = tuple(
        DifferingGroup(
            canonical=canonical,
            rows=tuple(r for r, _ in members),
            representative_row=members[0][0],
            raw_formula=members[0][1].sheet_formula,
            converted=members[0][1].converted,
            by_convention=tuple(members[0][1].by_convention),
            note=members[0][1].note,
        )
        for canonical, members in groups.items()
    )

    n = len(counted)
    compared = len(matching) + sum(len(g.rows) for g in group_records)
    nonmatch = sum(len(g.rows) for g in group_records) + len(no_formula)

    if stored_state == STORED_EMPTY:
        situation = S1  # the column was only examined because a formula exists below the header
    elif n == 0:
        situation = S5
    elif stored_state == STORED_PLACEHOLDER:
        situation = S4
    elif not formula_row_list:
        situation = S3
    elif compared == 0:
        situation = COULD_NOT_COMPARE
    elif nonmatch == 0:
        situation = S6
    else:
        biggest_other = max([len(g.rows) for g in group_records] + [len(no_formula)])
        situation = S2B if len(matching) > biggest_other else S2A

    kind = setting_kind(adds_allowed, edits_allowed)
    judgment = _judge(kind, situation)
    finding, advice = _compose(
        situation, kind, n, tuple(matching), group_records, tuple(no_formula), len(formula_row_list),
        tuple(formula_row_list), value_only, blank, tuple(uncompared),
    )

    notes: List[str] = []
    if row_basis == ROW_BASIS_KEY:
        notes.append(f"Row basis: {row_basis_detail}")
    else:
        notes.append(f"Row basis: the key-based row set was unavailable ({row_basis_detail}); a row was counted when it held any value or formula in any of the table's paired sheet columns, or a formula in this column.")
    if setting_assumed:
        notes.append(
            f"The table's update setting was treated as allowing both adds and edits ({setting_basis[len('assumed: '):]})."
        )
    if row_basis_uncertain:
        notes.append("The row basis is uncertain: stage 4 did not identify this tab's header row, so which rows lie below it is not established.")
    if header_source == HEADER_SOURCE_DECLARED:
        notes.append("The header row of this tab is DECLARED by the maintainer, not measured.")
    if uncompared and situation == S1:
        notes.append(
            f"{_plural(len(uncompared), 'formula cell')} could not be converted to R1C1 "
            f"({'; '.join(sorted({u.reason for u in uncompared}))}); {'it counts' if len(uncompared) == 1 else 'they count'} "
            "as a formula but is not grouped with the others."
        )
    elif uncompared and situation != COULD_NOT_COMPARE:
        notes.append(
            f"{_plural(len(uncompared), 'formula cell')} could not be compared "
            f"({'; '.join(sorted({u.reason for u in uncompared}))}) and {'is' if len(uncompared) == 1 else 'are'} "
            "left out of the judgment."
        )
    if situation not in (S1, S5, S6, COULD_NOT_COMPARE) and any(g.note for g in group_records):
        for g in group_records:
            if g.note:
                notes.append(f"{'Row' if len(g.rows) == 1 else 'Rows'} {format_row_ranges(g.rows)}: {g.note}.")
    return ColumnFinding(
        table=table,
        column=app_column.column_name,
        tab=tab,
        sheet_column=pairing.sheet_column,
        label_state=pairing.label_state,
        label_text=pairing.label_text,
        header_row1=header_row1,
        header_source=header_source,
        header_verdict=header_verdict,
        row_basis_uncertain=row_basis_uncertain,
        update_mode=update_mode,
        adds_allowed=adds_allowed,
        edits_allowed=edits_allowed,
        setting_basis=setting_basis,
        setting_assumed=setting_assumed,
        row_basis=row_basis,
        row_basis_detail=row_basis_detail,
        key_column=key_column,
        key_sheet_column=key_sheet_column,
        counted_rows=tuple(counted),
        stored_formula=stored,
        stored_state=stored_state,
        matching_rows=tuple(matching),
        differing_groups=group_records,
        placeholder_rows=tuple(placeholder_rows),
        no_formula_rows=tuple(no_formula),
        uncompared=tuple(uncompared),
        formula_row_count=len(formula_row_list),
        value_only_row_count=value_only,
        blank_row_count=blank,
        by_convention=unattested(flags),
        situation=situation,
        allows=kind,
        tier=judgment.tier,
        grade=judgment.grade,
        rank=None,  # filled in once every column is judged
        finding=finding,
        advice=advice,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# The whole checkup
# ---------------------------------------------------------------------------

_RELIABILITY_CONDITION = (
    "Every finding in this artifact rests on four things this stage reads and does not re-derive. (1) The "
    "app-side parse and the capture must belong to the same version of the app: a stored formula or a "
    "table setting from one version set against a sheet from another produces findings that look valid and "
    "are not (stage 5's provenance block records what is known about that). (2) Stage 5's pairing of each "
    "app column with a sheet column through the header labels, which on a tab whose header row stage 4 chose "
    "from the app's column names is partly true by construction. (3) Stage 4's header row for each tab: rows "
    "are counted below it, so a wrong header row changes which rows count. (4) The comparison of r1c1.py, "
    "which ignores the case of function names and whitespace outside string literals, compares nothing it "
    "does not recognize (named ranges, array literals and the like are reported as not compared, never "
    "guessed), and spells some reference forms by convention rather than from AppSheet's own stored text: a "
    "difference that involves such a form is marked, because it might be one of spelling rather than of "
    "formula. Which rows count is decided by the table's key where the key is a paired sheet column, and "
    "otherwise by any value or formula in the table's paired sheet columns; the finding names the basis "
    "used. What a table's update setting allows says what the table allows in general, not what the app's "
    "views and actions actually do, and an empty, unrecognized or missing setting is treated as allowing both "
    "adds and edits. The judgments (which situation can cause trouble under which setting) are the maintainer's "
    "rules, recorded in one table in stage6.py; several rest on a third-party report or on untested inference "
    "and are graded 'possible' for that reason. A column filled by a formula that spills down from one cell is "
    "outside what this stage examines, and is not distinguished from a column with plain values. "
    "Whatever the capture and the app-side parse did not record, such as other workbooks, bots and bound "
    "scripts that write to the sheet, is outside the checkup. This artifact describes the app-side parse and "
    "the capture as they stood at the times in the stage 5 provenance block, not as either stands now."
)


def _absent(reason: str, capture_date: str = "absent") -> CheckupArtifact:
    return CheckupArtifact(
        stamp=build_stamp(capture_date),
        reliability_condition=(
            f"This artifact is ABSENT: {reason}. The formula checkup needs the app-side results and must be "
            f"reported absent, not skipped silently, without them. No column finding is stated by this "
            f"artifact while it is absent. " + _RELIABILITY_CONDITION
        ),
        residue=(),
        present=False,
        absent_reason=reason,
        tables_csv_found=None,
        tables_csv_note=None,
        appside_parse_dir=None,
        input_file_hashes=(),
        findings=(),
        not_examined=(),
    )


def run_stage6(
    formulas_path: str,
    values_path: str,
    appside_parse_dir: Optional[str] = None,
    app_export_html_path: Optional[str] = None,
    declarations_path: Optional[str] = None,
    stage5_result: Optional[Stage5Result] = None,
) -> Stage6Result:
    """Runs the checkup. `stage5_result`, when given, is used as it is (run.py
    passes the result of the stage 5 it has just run); otherwise stage 5 is
    run here with the same arguments."""
    if stage5_result is None:
        if appside_parse_dir is None:
            return Stage6Result(stage5=None, checkup=_absent("no app-side parse directory was given"))
        stage5_result = run_stage5(
            formulas_path, values_path, appside_parse_dir=appside_parse_dir,
            app_export_html_path=app_export_html_path, declarations_path=declarations_path,
        )

    join = stage5_result.join
    if not join.present or stage5_result.capture is None or stage5_result.stage4 is None:
        return Stage6Result(
            stage5=stage5_result,
            checkup=_absent("stage 5's join is ABSENT, so there is no table-to-tab pairing or header label to read"),
        )

    if appside_parse_dir is None and join.provenance is not None:
        appside_parse_dir = join.provenance.appside_parse_dir
    if appside_parse_dir is None:
        return Stage6Result(
            stage5=stage5_result,
            checkup=_absent("no app-side parse directory is known", join.stamp.capture_date),
        )
    try:
        columns_csv_path = discover_appside_columns_csv(appside_parse_dir)
        app_columns = load_appside_formula_columns(columns_csv_path)
    except AppSideParseError as exc:
        return Stage6Result(
            stage5=stage5_result, checkup=_absent(f"the app-side columns file could not be read: {exc}", join.stamp.capture_date),
        )
    if not app_columns.spreadsheet_formula_field_present:
        return Stage6Result(
            stage5=stage5_result,
            checkup=_absent(
                "appsheet_columns.csv carries no 'spreadsheet_formula' field, so what the app stores for each "
                "column is unknown and no column can be compared or called 'nothing stored'",
                join.stamp.capture_date,
            ),
        )

    tables_csv_path = discover_appside_tables_csv(appside_parse_dir)
    tables_csv: Optional[Dict[str, str]] = None
    tables_csv_note: str
    if tables_csv_path is None:
        tables_csv_note = TABLES_CSV_ABSENT_NOTE
    else:
        try:
            tables_csv = load_appside_tables(tables_csv_path).by_table()
            tables_csv_note = "appsheet_tables.csv was found and read"
        except AppSideParseError as exc:
            tables_csv = None
            tables_csv_path = None
            tables_csv_note = f"appsheet_tables.csv could not be read ({exc}); " + TABLES_CSV_ABSENT_NOTE

    capture = stage5_result.capture
    sheets_by_name = {s.sheet: s for s in stage5_result.stage4.schema.sheets}

    findings: List[ColumnFinding] = []
    not_examined: List[NotExaminedColumn] = []
    residue: List[ResidueEntry] = []

    for entry in join.tables:
        table_columns = app_columns.columns_for_table(entry.table)
        if not table_columns:
            continue
        update_mode, adds_allowed, edits_allowed, setting_basis, setting_assumed = interpret_update_mode(entry.table, tables_csv)

        pairings = {c.column_name: _pair_app_column(entry, c.column_name) for c in table_columns}

        schema_sheet = sheets_by_name.get(entry.matched_tab) if entry.matched_tab is not None else None
        header = schema_sheet.header_detection if schema_sheet is not None else None
        header_row1 = header.header_row1 if header is not None else None
        row_basis_uncertain = (
            header is not None
            and not (header.verdict == HEADER_VERDICT_IDENTIFIED or header.source == HEADER_SOURCE_DECLARED)
        )

        fs = capture.formula_sheet(entry.matched_tab) if schema_sheet is not None else None
        vs = capture.value_sheet(entry.matched_tab) if schema_sheet is not None else None

        # The row sets are the same for every column of the table, so they
        # are built once. Rows below the header row only.
        key_columns = [c for c in table_columns if c.is_key]
        key_column: Optional[str] = None
        key_sheet_column: Optional[str] = None
        key_rows: Optional[frozenset] = None
        any_rows: Optional[frozenset] = None
        row_basis = ROW_BASIS_ANY_PAIRED
        row_basis_detail = ""
        usable = (
            fs is not None and header_row1 is not None
            and all(
                p.sheet_column is None or letters_to_col(p.sheet_column) < fs.column_count
                for p in pairings.values()
            )
        )
        if usable:
            if not app_columns.key_field_present:
                row_basis_detail = "appsheet_columns.csv carries no 'key' field"
            elif len(key_columns) == 0:
                row_basis_detail = "the table has no column with key = Yes in appsheet_columns.csv"
            elif len(key_columns) > 1:
                row_basis_detail = (
                    "the table has more than one column with key = Yes ("
                    + ", ".join(repr(c.column_name) for c in key_columns) + ")"
                )
            else:
                key_column = key_columns[0].column_name
                kp = pairings[key_column]
                if kp.sheet_column is None:
                    row_basis_detail = f"the key column {key_column!r} is not paired with a sheet column ({kp.reason})"
                else:
                    key_sheet_column = kp.sheet_column
            paired_cols = sorted({letters_to_col(p.sheet_column) for p in pairings.values() if p.sheet_column is not None})
            first_row = header_row1 + 1
            if key_sheet_column is not None:
                kc = letters_to_col(key_sheet_column)
                key_rows = frozenset(r for r in range(first_row, fs.row_count + 1) if is_nonempty(vs.values[r - 1][kc]))
                row_basis = ROW_BASIS_KEY
                row_basis_detail = (
                    f"the key column {key_column!r} (sheet column {key_sheet_column}): a row counts when its key cell has a value"
                )
            else:
                any_rows = frozenset(
                    r for r in range(first_row, fs.row_count + 1)
                    if any(is_nonempty(vs.values[r - 1][c]) or is_nonempty(fs.formulas[r - 1][c]) for c in paired_cols)
                )
            basis_rows = key_rows if row_basis == ROW_BASIS_KEY else any_rows
        else:
            basis_rows = frozenset()

        for c in table_columns:
            p = pairings[c.column_name]
            stored_state = _stored_state(c.spreadsheet_formula)
            if p.sheet_column is None or not usable:
                if stored_state != STORED_EMPTY:
                    reason = p.reason
                    if reason is None:
                        if header_row1 is None:
                            reason = "stage 4 gives no header row for the tab"
                        else:
                            reason = "the paired sheet column lies outside the captured area of the tab"
                    not_examined.append(
                        NotExaminedColumn(
                            table=entry.table, column=c.column_name, stored_formula=c.spreadsheet_formula,
                            reason=reason, tab=entry.matched_tab, sheet_column=p.sheet_column,
                        )
                    )
                continue
            finding = _examine_column(
                table=entry.table, app_column=c, pairing=p, tab=entry.matched_tab, header_row1=header_row1,
                header_source=header.source, header_verdict=header.verdict,
                row_basis_uncertain=row_basis_uncertain,
                formula_rows_grid=fs.formulas, value_rows_grid=vs.values, row_count=fs.row_count,
                row_basis=row_basis, row_basis_detail=row_basis_detail,
                key_column=key_column, key_sheet_column=key_sheet_column, basis_rows=basis_rows,
                update_mode=update_mode, adds_allowed=adds_allowed, edits_allowed=edits_allowed,
                setting_basis=setting_basis, setting_assumed=setting_assumed,
            )
            if finding is not None:
                findings.append(finding)

    # Order: by table, then sheet column position, then app column name.
    findings.sort(key=lambda f: (f.table, letters_to_col(f.sheet_column), f.column))
    not_examined.sort(key=lambda n: (n.table, n.column))

    # Rank the raised findings.
    raised = [
        f for f in findings if f.tier == TIER_RAISED
    ]
    raised.sort(key=lambda f: (JUDGMENT_TABLE[(f.allows, f.situation)].priority, f.table, letters_to_col(f.sheet_column), f.column))
    ranks = {(f.table, f.column): i + 1 for i, f in enumerate(raised)}
    findings = [
        dataclasses.replace(f, rank=ranks[(f.table, f.column)]) if f.tier == TIER_RAISED else f
        for f in findings
    ]

    for f in findings:
        if f.uncompared:
            by_reason: Dict[str, List[str]] = {}
            for u in f.uncompared:
                by_reason.setdefault(u.reason, []).append(f"{f.tab}!{u.cell}")
            for reason in sorted(by_reason):
                if f.situation == S1:
                    what = (
                        f"{_plural(len(by_reason[reason]), 'formula cell')} in column {f.column!r} of table "
                        f"{f.table!r} could not be converted to R1C1"
                    )
                    consequence = "these cells still count as formulas, but are not grouped with the column's other formulas"
                else:
                    what = (
                        f"{_plural(len(by_reason[reason]), 'formula cell')} in column {f.column!r} of table "
                        f"{f.table!r} could not be converted for comparison with the stored formula"
                    )
                    consequence = (
                        "these cells are left out of the column's judgment; whether they match the stored "
                        "formula is not established"
                        + ("; with no cell compared, the column is a run problem, not a finding"
                           if f.situation == COULD_NOT_COMPARE else "")
                    )
                residue.append(
                    ResidueEntry(
                        what=what,
                        locations=tuple(by_reason[reason]),
                        defeating_construct=reason,
                        consequence=consequence,
                    )
                )

    hashes: List[Tuple[str, str]] = [
        (os.path.basename(columns_csv_path), hash_file(columns_csv_path)),
    ]
    if tables_csv_path is not None:
        hashes.append((os.path.basename(tables_csv_path), hash_file(tables_csv_path)))

    checkup = CheckupArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=_RELIABILITY_CONDITION,
        residue=tuple(residue),
        present=True,
        absent_reason=None,
        tables_csv_found=tables_csv_path is not None,
        tables_csv_note=tables_csv_note,
        appside_parse_dir=appside_parse_dir,
        input_file_hashes=tuple(hashes),
        findings=tuple(findings),
        not_examined=tuple(not_examined),
    )
    return Stage6Result(stage5=stage5_result, checkup=checkup)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2, 3, 4):
        print(
            "usage: python -m sheet_derivation.stage6 <capture_directory> "
            "[appside_parse_dir] [app_export_html] [declarations.json]",
            file=sys.stderr,
        )
        return 2
    capture_dir = argv[0]
    appside_parse_dir = argv[1] if len(argv) >= 2 else None
    app_export_html = argv[2] if len(argv) >= 3 else None
    declarations_path = argv[3] if len(argv) >= 4 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage6(formulas_path, values_path, appside_parse_dir, app_export_html, declarations_path)
    checkup = result.checkup
    print(f"present: {checkup.present}")
    if not checkup.present:
        print(f"absent: {checkup.absent_reason}")
        return 0
    print(f"appsheet_tables.csv: {checkup.tables_csv_note}")
    print(f"examined columns: {len(checkup.findings)}")
    print(f"not examined: {len(checkup.not_examined)}")
    tiers: Dict[str, int] = {}
    for f in checkup.findings:
        tiers[f.tier] = tiers.get(f.tier, 0) + 1
    print(f"tiers: {tiers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
