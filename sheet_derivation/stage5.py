"""Stage 5: the AppSheet-to-sheet join (design section 4.4).

READS STAGE 4'S SCHEMA, NEVER RECOMPUTES IT. Header verdicts, header
labels, and duplicate-label findings all come from calling
`stage4.run_stage4` and reading its `SchemaArtifact` -- this module
contains no header-detection logic of its own. This is the same
convention every earlier stage follows (stage 4 calls stage 3, stage 3
re-tokenizes rather than importing stage 1's pattern set, and so on):
calling the canonical prior-stage function and reading its result is not
"recomputing what it already states", it is how a fresh, independent
pass stays exactly as trustworthy as the stage before it.

NOTHING ON THE SHEET SIDE IS EVER DERIVED FROM THE APP SIDE (design
section 4.4's own rejected-proposal note, 2026-09-09). This module never
writes back into a `stage4.Stage4Result` or a `stage3.Stage3Result`, never
calls `stage4.run_stage4` with different arguments than a plain caller
would, and the one place it reads sheet-side text the schema itself
withholds (the "undetermined diagnostic" below) is walled off from the
join's own accounting on purpose -- see that section's own docstring.

NEVER READS `appsheet_views.csv`. Six of its fields (`data_source`,
`source_table`, `category`, `position`, `view_type`, `ref_parent`)
originate in `views1.txt`/`views2.txt`, browser paste captures subject to
the documented whitespace-collapse defect (`STATUS.md`, 2026-09-06).
`appside_parse.py` reads `appsheet_columns.csv` only, which is entirely
HTML-derived. This is a constraint on the implementation, not a finding
to re-derive per run: the workbook this tool was built against happens to
show zero instances of that defect, so a violation of this rule would
pass every gate here and only fail on a workbook that has one.

TWO PLACES THIS MODULE'S BEHAVIOUR IS AHEAD OF THE DESIGN DOCUMENT'S
PROSE, per this build's own instruction (built to the code, not to the
prose; the discrepancy is reported, the document is not edited here):

  1. Design section 4.2 describes a three-state header-label field. Stage
     4 as built produces five (`stage4.LABEL_STATE_LABELED` plus four
     "why there is no label" states, one of them -- `spill-origin-not-
     label` -- added after the whole-row-veto correction of 2026-09-09).
     This module consumes all five: only `LABELED` columns ever become a
     "header label" the join can match against; the other four
     contribute an app-side match attempt of "no label to match" and no
     label-side entry at all.
  2. Design section 4.2's prose still describes one sheet's row 1 as data
     because its FILTER formulas spill downward -- true, per stage 4's
     own measurement, of a MINORITY of that sheet's columns, and that
     sheet now measures IDENTIFIED overall. The measurement supersedes
     the prose; this module trusts stage 4's verdict, not the prose.

THE JOIN, BOTH DIRECTIONS, AND WHY BOTH ARE BUILT. Design section 4.4:
"AppSheet column to header cell", and its own list of states implies the
reverse question too ("a header label repeated within a tab" is a fact
about the LABEL, not about any one column). This module computes both
directions independently: every app-side column gets exactly one
column-match state, and every stage-4-identified header LABEL (a column
whose own `header_label.state == LABELED`) gets exactly one label-match
state. Only the label direction is a statement about the sheet itself --
a column direction can only ever say "does an app definition, built
independently, happen to name something also present here", which is why
both are reported and neither is collapsed into the other.
"""

import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .appside_parse import (
    AppColumn,
    AppIdentity,
    AppSideColumns,
    AppSideParseError,
    discover_appside_columns_csv,
    extract_app_identity,
    hash_file,
    load_appside_columns,
)
from .artifact import ArtifactBase
from .coordinates import letters_to_col
from .counts import is_nonempty
from .loader import Capture, discover_capture_files, load_capture
from .residue import ResidueEntry, build_stamp
from .stage4 import (
    HEADER_SOURCE_DECLARED,
    HEADER_VERDICT_IDENTIFIED,
    LABEL_STATE_LABELED,
    Stage4Result,
    run_stage4,
)

# ---------------------------------------------------------------------------
# Match states
# ---------------------------------------------------------------------------

TABLE_STATE_MATCHED = "matched"
TABLE_STATE_NO_TAB = "table-matching-no-tab"

COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED = "no-sheet-column-expected"  # virtual
COLUMN_STATE_HEADER_NOT_IDENTIFIED = "tab-header-not-identified"
COLUMN_STATE_TABLE_NO_TAB = "table-matching-no-tab"
COLUMN_STATE_EXACT_MATCH = "exact-match"
COLUMN_STATE_WHITESPACE_NEAR_MISS = "whitespace-near-miss"
COLUMN_STATE_UNMATCHED = "unmatched"

LABEL_STATE_REPEATED = "label-repeated-within-tab"
LABEL_STATE_EXACT_MATCH = "exact-match"
LABEL_STATE_WHITESPACE_NEAR_MISS = "whitespace-near-miss"
LABEL_STATE_UNMATCHED = "unmatched"

_WHITESPACE_RUN_RE = re.compile(r"\s+")


def normalize_whitespace(s: str) -> str:
    """Collapse every run of whitespace to one space and strip the ends.
    The one and only normalization this module ever applies, and it is
    applied only for the whitespace-near-miss check -- never used to
    replace, repair, or stand in for a raw string anywhere in the output."""
    return _WHITESPACE_RUN_RE.sub(" ", s).strip()


# ---------------------------------------------------------------------------
# Per-item results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnMatchResult:
    table: str
    column: str
    is_virtual: Optional[bool]
    state: str
    matched_sheet_column: Optional[str] = None
    matched_label_text: Optional[str] = None
    near_miss_candidates: Tuple[str, ...] = ()  # raw label texts, 2+ means a collision


@dataclass(frozen=True)
class LabelMatchResult:
    table: str
    sheet: str
    sheet_column: str
    label_text: str
    state: str
    matched_app_column: Optional[str] = None
    near_miss_candidates: Tuple[str, ...] = ()  # raw app-column names, 2+ means a collision


@dataclass(frozen=True)
class TableJoinEntry:
    table: str
    table_state: str  # TABLE_STATE_MATCHED / TABLE_STATE_NO_TAB
    matched_tab: Optional[str]
    header_verdict: Optional[str]
    header_source: Optional[str]
    column_results: Tuple[ColumnMatchResult, ...]
    label_results: Tuple[LabelMatchResult, ...]


@dataclass(frozen=True)
class UndeterminedDiagnosticEntry:
    """A DIAGNOSTIC, not a join result -- see this module's own docstring
    and this dataclass's own note. Every column this entry names still
    carries `COLUMN_STATE_HEADER_NOT_IDENTIFIED` in the join proper; this
    is additional, clearly-separated information, read from the raw
    capture (never from stage 4, which correctly withholds label text for
    a verdict it did not reach), and it is never fed back into anything."""

    table: str
    tab: str
    header_verdict: str
    candidate_row1: int  # always 1 -- the only row measured detection ever examines
    app_column_count: int
    app_columns_found: Tuple[str, ...]  # exact or whitespace-near-miss
    app_columns_not_found: Tuple[str, ...]
    row1_nonempty_count: int
    row1_exact_matches: Tuple[str, ...]
    row1_near_misses: Tuple[Tuple[str, str], ...]  # (row1 raw text, app column raw text)
    row1_unmatched: Tuple[str, ...]


@dataclass(frozen=True)
class AppIdentityOut:
    og_title: Optional[str]
    version: Optional[str]
    default_app_folder: Optional[str]
    html_mtime_iso: Optional[str]


@dataclass(frozen=True)
class Stage5Provenance:
    """What no parse directory or capture states about itself, stamped
    here instead of guessed. `input_file_hashes` covers every file this
    stage itself opens: the two capture files and the app-side columns
    CSV, plus the export HTML if one was supplied."""

    appside_parse_dir: Optional[str]
    app_identity: AppIdentityOut
    input_file_hashes: Dict[str, str]
    capture_date: str
    export_to_capture_gap_days: Optional[float]


@dataclass(frozen=True)
class JoinArtifact(ArtifactBase):
    present: bool
    provenance: Optional[Stage5Provenance]
    virtual_field_present: Optional[bool]
    tables: Tuple[TableJoinEntry, ...]
    diagnostics: Tuple[UndeterminedDiagnosticEntry, ...]


@dataclass(frozen=True)
class Stage5Result:
    capture: Optional[Capture]
    stage4: Optional[Stage4Result]
    join: JoinArtifact
    column_state_counts: Dict[str, int]
    label_state_counts: Dict[str, int]


# ---------------------------------------------------------------------------
# The matching core
# ---------------------------------------------------------------------------

def _find_whitespace_matches(query: str, candidates_by_normalized: Dict[str, List[str]]) -> Tuple[str, ...]:
    """Every DISTINCT raw candidate string whose own normalized form
    equals `query`'s normalized form -- excluding any candidate that is
    already an exact (un-normalized) match, since exact match is checked
    first and takes precedence. 2+ results means a genuine whitespace
    collision (two different raw strings collapsing to the same thing),
    reported as such rather than picked between."""
    key = normalize_whitespace(query)
    return tuple(c for c in candidates_by_normalized.get(key, []) if c != query)


def _build_normalized_index(raw_strings) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    seen = set()
    for s in raw_strings:
        if s in seen:
            continue
        seen.add(s)
        index.setdefault(normalize_whitespace(s), []).append(s)
    return index


def _match_one(query: str, exact_set: set, normalized_index: Dict[str, List[str]]) -> Tuple[str, Tuple[str, ...]]:
    """Returns (state_suffix, candidates) where state_suffix is 'exact',
    'near-miss', or 'unmatched', and candidates names what it matched
    (one name for an exact or clean near-miss, 2+ for a collision)."""
    if query in exact_set:
        return "exact", (query,)
    near = _find_whitespace_matches(query, normalized_index)
    if near:
        return "near-miss", near
    return "unmatched", ()


def _join_one_table(
    table: str,
    app_columns: Tuple[AppColumn, ...],
    schema_sheet,  # stage4.SheetSchemaEntry, or None if no tab matched
    virtual_field_present: bool,
) -> TableJoinEntry:
    if schema_sheet is None:
        column_results = tuple(
            ColumnMatchResult(
                table=table, column=c.column_name, is_virtual=c.is_virtual,
                state=COLUMN_STATE_TABLE_NO_TAB,
            )
            for c in app_columns
        )
        return TableJoinEntry(
            table=table, table_state=TABLE_STATE_NO_TAB, matched_tab=None,
            header_verdict=None, header_source=None,
            column_results=column_results, label_results=(),
        )

    header = schema_sheet.header_detection
    header_identified = header.verdict == HEADER_VERDICT_IDENTIFIED or header.source == HEADER_SOURCE_DECLARED

    if not header_identified:
        column_results = tuple(
            ColumnMatchResult(
                table=table, column=c.column_name, is_virtual=c.is_virtual,
                state=COLUMN_STATE_HEADER_NOT_IDENTIFIED,
            )
            for c in app_columns
        )
        return TableJoinEntry(
            table=table, table_state=TABLE_STATE_MATCHED, matched_tab=schema_sheet.sheet,
            header_verdict=header.verdict, header_source=header.source,
            column_results=column_results, label_results=(),
        )

    # Header identified: build the label set from stage 4's own LABELED
    # columns only -- the other four label states carry no text to match.
    labeled_columns = [c for c in schema_sheet.columns if c.header_label.state == LABEL_STATE_LABELED]
    label_texts = [c.header_label.value for c in labeled_columns]
    text_counts = Counter(label_texts)
    repeated_texts = {t for t, n in text_counts.items() if n > 1}

    app_column_names = [c.column_name for c in app_columns]
    app_exact_set = set(app_column_names)
    app_normalized_index = _build_normalized_index(app_column_names)

    non_repeated_label_texts = [t for t in label_texts if t not in repeated_texts]
    label_exact_set = set(non_repeated_label_texts)
    label_normalized_index = _build_normalized_index(non_repeated_label_texts)

    column_results = []
    for c in app_columns:
        if c.is_virtual:
            column_results.append(
                ColumnMatchResult(
                    table=table, column=c.column_name, is_virtual=True,
                    state=COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED,
                )
            )
            continue
        if c.column_name in repeated_texts:
            column_results.append(
                ColumnMatchResult(
                    table=table, column=c.column_name, is_virtual=c.is_virtual,
                    state=COLUMN_STATE_UNMATCHED,
                    near_miss_candidates=(),
                )
            )
            # A column whose name equals a label repeated within the tab is
            # genuinely ambiguous -- which physical column does it name? Not
            # resolved here; reported UNMATCHED at the column level, and the
            # ambiguity itself is fully reported on the label side below,
            # once per repeated column, per the design's own "report
            # ambiguity, resolve nothing" rule.
            continue
        kind, candidates = _match_one(c.column_name, label_exact_set, label_normalized_index)
        if kind == "exact":
            column_results.append(
                ColumnMatchResult(
                    table=table, column=c.column_name, is_virtual=c.is_virtual,
                    state=COLUMN_STATE_EXACT_MATCH, matched_label_text=candidates[0],
                )
            )
        elif kind == "near-miss":
            column_results.append(
                ColumnMatchResult(
                    table=table, column=c.column_name, is_virtual=c.is_virtual,
                    state=COLUMN_STATE_WHITESPACE_NEAR_MISS, near_miss_candidates=candidates,
                )
            )
        else:
            column_results.append(
                ColumnMatchResult(
                    table=table, column=c.column_name, is_virtual=c.is_virtual,
                    state=COLUMN_STATE_UNMATCHED,
                )
            )

    label_results = []
    for lc in labeled_columns:
        text = lc.header_label.value
        if text in repeated_texts:
            label_results.append(
                LabelMatchResult(
                    table=table, sheet=schema_sheet.sheet, sheet_column=lc.column,
                    label_text=text, state=LABEL_STATE_REPEATED,
                )
            )
            continue
        kind, candidates = _match_one(text, app_exact_set, app_normalized_index)
        if kind == "exact":
            label_results.append(
                LabelMatchResult(
                    table=table, sheet=schema_sheet.sheet, sheet_column=lc.column,
                    label_text=text, state=LABEL_STATE_EXACT_MATCH, matched_app_column=candidates[0],
                )
            )
        elif kind == "near-miss":
            label_results.append(
                LabelMatchResult(
                    table=table, sheet=schema_sheet.sheet, sheet_column=lc.column,
                    label_text=text, state=LABEL_STATE_WHITESPACE_NEAR_MISS, near_miss_candidates=candidates,
                )
            )
        else:
            label_results.append(
                LabelMatchResult(
                    table=table, sheet=schema_sheet.sheet, sheet_column=lc.column,
                    label_text=text, state=LABEL_STATE_UNMATCHED,
                )
            )

    return TableJoinEntry(
        table=table, table_state=TABLE_STATE_MATCHED, matched_tab=schema_sheet.sheet,
        header_verdict=header.verdict, header_source=header.source,
        column_results=tuple(column_results), label_results=tuple(label_results),
    )


# ---------------------------------------------------------------------------
# The undetermined diagnostic -- walled off from the join's own accounting.
#
# Reads row 1's raw evaluated values directly from the CAPTURE, never from
# stage 4's schema, because stage 4 correctly withholds label text for a
# verdict it did not reach -- there is nothing to read there. This is new
# work for THIS stage (a fresh look at the raw capture), not a
# recomputation of anything stage 4 states, and its own result is never
# written back into a Stage4Result or used to change `header_verdict`
# anywhere in this module. Section 4.4's rejected-proposal note (2026-09-09)
# governs this boundary explicitly: reporting agreement is measurement;
# changing a verdict on the strength of it would be exactly the
# comparing-a-thing-against-itself the design forbids.
# ---------------------------------------------------------------------------

def _undetermined_diagnostic(
    table: str, tab: str, header_verdict: str, capture: Capture, app_columns: Tuple[AppColumn, ...],
) -> UndeterminedDiagnosticEntry:
    vs = capture.value_sheet(tab)
    row1 = vs.values[0] if vs.values else ()
    row1_text_values = [v for v in row1 if isinstance(v, str) and is_nonempty(v)]

    app_column_names = [c.column_name for c in app_columns]
    app_exact_set = set(app_column_names)
    app_normalized_index = _build_normalized_index(app_column_names)

    row1_exact_set = set(row1_text_values)
    row1_normalized_index = _build_normalized_index(row1_text_values)

    app_found, app_not_found = [], []
    for name in app_column_names:
        kind, _ = _match_one(name, row1_exact_set, row1_normalized_index)
        (app_found if kind != "unmatched" else app_not_found).append(name)

    row1_exact, row1_near, row1_unmatched = [], [], []
    for text in row1_text_values:
        kind, candidates = _match_one(text, app_exact_set, app_normalized_index)
        if kind == "exact":
            row1_exact.append(text)
        elif kind == "near-miss":
            for cand in candidates:
                row1_near.append((text, cand))
        else:
            row1_unmatched.append(text)

    return UndeterminedDiagnosticEntry(
        table=table, tab=tab, header_verdict=header_verdict, candidate_row1=1,
        app_column_count=len(app_columns),
        app_columns_found=tuple(app_found), app_columns_not_found=tuple(app_not_found),
        row1_nonempty_count=len(row1_text_values),
        row1_exact_matches=tuple(row1_exact), row1_near_misses=tuple(row1_near),
        row1_unmatched=tuple(row1_unmatched),
    )


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

_STALENESS_NOTE = (
    "This artifact describes the app-side parse and the sheet-side capture as they stood at "
    "the times named in this artifact's own provenance block, not as either stands now. A "
    "later parse or capture producing different findings is not evidence that this tool has "
    "broken. Read the provenance block before treating any finding, or its absence, as current."
)


def _absent_join(reason: str) -> JoinArtifact:
    return JoinArtifact(
        stamp=build_stamp("absent"),
        reliability_condition=(
            f"This artifact is ABSENT: {reason}. Design section 4.4 states this artifact "
            f"requires the app-side parse and must be reported absent, not skipped silently, "
            f"without one. No table, column, or header finding is stated by this artifact "
            f"while it is absent."
        ),
        residue=(),
        present=False,
        provenance=None,
        virtual_field_present=None,
        tables=(),
        diagnostics=(),
    )


def run_stage5(
    formulas_path: str,
    values_path: str,
    appside_parse_dir: Optional[str] = None,
    app_export_html_path: Optional[str] = None,
    declarations_path: Optional[str] = None,
) -> Stage5Result:
    if appside_parse_dir is None:
        join = _absent_join("no app-side parse directory was given")
        return Stage5Result(capture=None, stage4=None, join=join, column_state_counts={}, label_state_counts={})

    try:
        columns_csv_path = discover_appside_columns_csv(appside_parse_dir)
        appside = load_appside_columns(columns_csv_path)
    except AppSideParseError as exc:
        join = _absent_join(str(exc))
        return Stage5Result(capture=None, stage4=None, join=join, column_state_counts={}, label_state_counts={})

    capture = load_capture(formulas_path, values_path)
    stage4_result = run_stage4(formulas_path, values_path, declarations_path)
    sheets_by_name = {s.sheet: s for s in stage4_result.schema.sheets}

    tables: List[TableJoinEntry] = []
    diagnostics: List[UndeterminedDiagnosticEntry] = []
    for table in appside.table_names:
        app_columns = appside.columns_for_table(table)
        schema_sheet = sheets_by_name.get(table)
        entry = _join_one_table(table, app_columns, schema_sheet, appside.virtual_field_present)
        tables.append(entry)
        if schema_sheet is not None:
            header = schema_sheet.header_detection
            header_identified = header.verdict == HEADER_VERDICT_IDENTIFIED or header.source == HEADER_SOURCE_DECLARED
            if not header_identified and header.source != HEADER_SOURCE_DECLARED:
                diagnostics.append(
                    _undetermined_diagnostic(table, schema_sheet.sheet, header.verdict, capture, app_columns)
                )

    residue: List[ResidueEntry] = []
    if not appside.virtual_field_present:
        residue.append(
            ResidueEntry(
                what=f"{os.path.basename(columns_csv_path)} carries no 'is_virtual' field at all",
                locations=(appside.source_path,),
                defeating_construct="missing is_virtual column",
                consequence=(
                    "every unmatched app column is left in the plain 'unmatched' state rather than "
                    "distinguished as 'no sheet column expected' -- whether any of them are virtual "
                    "columns with no sheet-side counterpart at all is not established here; virtuality "
                    "was never inferred from a formula field or from the absence of a header match"
                ),
            )
        )
    for entry in tables:
        for cr in entry.column_results:
            if cr.state == COLUMN_STATE_WHITESPACE_NEAR_MISS and len(cr.near_miss_candidates) > 1:
                residue.append(
                    ResidueEntry(
                        what=(
                            f"app column {entry.table}!{cr.column!r} normalizes to the same whitespace-"
                            f"collapsed form as {len(cr.near_miss_candidates)} distinct header labels: "
                            f"{cr.near_miss_candidates!r}"
                        ),
                        locations=(f"{entry.table}!{cr.column}",),
                        defeating_construct="whitespace-collapse collision",
                        consequence=(
                            "no single label is chosen as the match; inspect the raw strings directly "
                            "and decide by hand which, if any, is the intended counterpart"
                        ),
                    )
                )
        for lr in entry.label_results:
            if lr.state == LABEL_STATE_WHITESPACE_NEAR_MISS and len(lr.near_miss_candidates) > 1:
                residue.append(
                    ResidueEntry(
                        what=(
                            f"header label {entry.matched_tab}!{lr.sheet_column} ({lr.label_text!r}) "
                            f"normalizes to the same whitespace-collapsed form as {len(lr.near_miss_candidates)} "
                            f"distinct app columns: {lr.near_miss_candidates!r}"
                        ),
                        locations=(f"{entry.matched_tab}!{lr.sheet_column}",),
                        defeating_construct="whitespace-collapse collision",
                        consequence=(
                            "no single app column is chosen as the match; inspect the raw strings "
                            "directly and decide by hand which, if any, is the intended counterpart"
                        ),
                    )
                )
    for diag in diagnostics:
        residue.append(
            ResidueEntry(
                what=(
                    f"{diag.table}'s matched tab {diag.tab!r} has header verdict {diag.header_verdict!r} "
                    f"(not identified) -- {len(diag.app_columns_found)} of {diag.app_column_count} app "
                    f"column(s) were found, verbatim or after whitespace-collapse, among row 1's own "
                    f"evaluated values, as a diagnostic only"
                ),
                locations=(f"{diag.tab}!A1",),
                defeating_construct="tab header row not identified by stage 4",
                consequence=(
                    "every column of this table is reported "
                    f"'{COLUMN_STATE_HEADER_NOT_IDENTIFIED}' in the join proper, not matched against any "
                    "header label -- stage 4's own verdict is not overridden by this diagnostic's "
                    "agreement. Consult stage 4's own reliability condition for why the header is "
                    "undetermined, and this artifact's diagnostics section for the raw text agreement"
                ),
            )
        )

    # Content hashes of every file this stage itself opens.
    input_file_hashes = {
        os.path.basename(formulas_path): hash_file(formulas_path),
        os.path.basename(values_path): hash_file(values_path),
        os.path.basename(columns_csv_path): hash_file(columns_csv_path),
    }
    identity = extract_app_identity(app_export_html_path)
    if app_export_html_path is not None:
        input_file_hashes[os.path.basename(app_export_html_path)] = hash_file(app_export_html_path)

    export_gap_days = None
    if identity.html_mtime_iso is not None:
        export_dt = datetime.fromisoformat(identity.html_mtime_iso)
        capture_dt = datetime.fromisoformat(capture.capture_date.replace("Z", "+00:00"))
        export_gap_days = (capture_dt - export_dt).total_seconds() / 86400.0

    provenance = Stage5Provenance(
        appside_parse_dir=appside_parse_dir,
        app_identity=AppIdentityOut(
            og_title=identity.og_title, version=identity.version,
            default_app_folder=identity.default_app_folder, html_mtime_iso=identity.html_mtime_iso,
        ),
        input_file_hashes=input_file_hashes,
        capture_date=capture.capture_date,
        export_to_capture_gap_days=export_gap_days,
    )

    column_state_counts = Counter(cr.state for t in tables for cr in t.column_results)
    label_state_counts = Counter(lr.state for t in tables for lr in t.label_results)

    total_columns = sum(column_state_counts.values())
    expected_total_columns = len(appside.columns)
    if total_columns != expected_total_columns:
        raise AssertionError(
            f"column accounting failed to partition every app column exactly once: "
            f"{total_columns} != {expected_total_columns}"
        )
    total_labels = sum(label_state_counts.values())
    expected_total_labels = sum(
        1 for t in tables for lr in t.label_results
    )
    if total_labels != expected_total_labels:
        raise AssertionError("label accounting failed to partition every header label exactly once")

    reliability_condition = (
        "Every EXACT-MATCH and WHITESPACE-NEAR-MISS finding in this artifact rests on the app-side "
        "columns file naming the correct table/column identity for the app version it was parsed "
        "from, and on stage 4's own header-detection verdict for the matched tab, neither of which "
        "this stage re-derives or verifies against the other -- see this artifact's own provenance "
        "block for whether the two inputs are even likely to be the same version of anything. A "
        "table or column state of 'unmatched' means no counterpart was found by exact match or by "
        "whitespace-collapse; it does not mean one does not exist under some other transformation "
        "this stage does not attempt (case-folding, punctuation normalization, and so on -- none "
        "are applied here). The whitespace-near-miss check collapses runs of whitespace and strips "
        "leading/trailing whitespace only; it never repairs, resolves, or substitutes a normalized "
        "form for a raw one anywhere in this artifact -- both raw strings are always carried "
        "verbatim. Virtuality is read directly from the app-side columns file's own 'is_virtual' "
        "field when present; where that field is absent, no unmatched column is ever inferred "
        "virtual, and this is stated as residue rather than silently leaving the field blank. The "
        "undetermined-tab diagnostics in this artifact are NOT part of the join: they read row 1's "
        "raw evaluated values directly from the capture for a tab whose header stage 4 did not "
        "identify, report agreement or disagreement as a measurement, and never change the "
        "COLUMN_STATE_HEADER_NOT_IDENTIFIED state those same columns carry in the join proper -- "
        "nothing on the sheet side is derived from the app side anywhere in this artifact, per "
        "design section 4.4's own 2026-09-09 rejection of that proposal. " + _STALENESS_NOTE
    )

    join = JoinArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=reliability_condition,
        residue=tuple(residue),
        present=True,
        provenance=provenance,
        virtual_field_present=appside.virtual_field_present,
        tables=tuple(sorted(tables, key=lambda t: t.table)),
        diagnostics=tuple(sorted(diagnostics, key=lambda d: d.table)),
    )

    return Stage5Result(
        capture=capture, stage4=stage4_result, join=join,
        column_state_counts=dict(column_state_counts), label_state_counts=dict(label_state_counts),
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2, 3, 4):
        print(
            "usage: python -m sheet_derivation.stage5 <capture_directory> "
            "[appside_parse_dir] [app_export_html] [declarations.json]",
            file=sys.stderr,
        )
        return 2

    capture_dir = argv[0]
    appside_parse_dir = argv[1] if len(argv) >= 2 else None
    app_export_html = argv[2] if len(argv) >= 3 else None
    declarations_path = argv[3] if len(argv) >= 4 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage5(formulas_path, values_path, appside_parse_dir, app_export_html, declarations_path)

    print(f"present: {result.join.present}")
    if result.join.present:
        print(f"tables: {len(result.join.tables)}")
        print(f"column state counts: {result.column_state_counts}")
        print(f"label state counts: {result.label_state_counts}")
        print(f"diagnostics: {len(result.join.diagnostics)}")
        print(f"residue entries: {len(result.join.residue)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
