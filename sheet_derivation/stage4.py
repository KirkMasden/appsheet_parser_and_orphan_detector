"""Stage 4: the schema file (design section 4.2) -- per-sheet structural
facts, header-row detection against the rule design section 4.2 now
states, and per-column facts, most of the latter read from Stage 3's own
column-profile artifact rather than recomputed here.

RE-DERIVES NOTHING STAGE 3 ALREADY PRODUCES. Formula count, non-empty
value count, pattern classification, and the spill assessment are all
read from `stage3.run_stage3`'s `ColumnProfileArtifact`; this module's own
single pass over the capture computes only what no earlier stage does --
the allocated-versus-used extent per sheet, and header detection.

HEADER DETECTION IS THE NEW WORK HERE, and the rule below is exactly the
one design section 4.2 states, not the superseded one ("reject any row 1
containing a formula") the design explicitly names as wrong. Two
measurements, both already available from the capture/value model this
tool already has, decide it -- per COLUMN first, then rolled up into one
verdict for row 1 of each sheet. No other row is ever considered a header
candidate.

  - THE POSITIVE SIGNAL: row 1's evaluated value in a column differs in
    TYPE from the dominant type of that column's own evaluated values
    beneath it (row 2 onward). A formula that evaluates to a constant
    string is, once evaluated, indistinguishable from a typed string --
    exactly the reason the values file exists alongside the formulas
    file, and exactly why this signal is read from the VALUES file only,
    never from whether a cell holds a formula.
  - THE NEGATIVE SIGNAL: row 1's cell in a column is a spill origin (per
    `query.py`'s own structural measurement) whose measured downward
    extent reaches past row 1 in that same column. A cell that spills
    into the rows beneath it cannot simultaneously be an independent
    label for those rows -- the column's "body" and its "label" are the
    same spilled array. This is deliberately scoped to DOWNWARD extent
    only, matching design section 4.2's own words ("governing the column
    beneath them") -- a purely rightward spill from row 1 is a different
    phenomenon `query.py` can also detect, but it is not what section 4.2
    asks this stage to check, and reaching for it anyway would be exactly
    the kind of workbook-shaped tuning section 3.2 forbids.

THE NEGATIVE SIGNAL DISQUALIFIES THE COLUMN, NOT THE ROW (corrected
2026-09-09, after the first version of this rule shipped a whole-row veto
that a real capture showed to be too strong -- Collate, where 5 of 50
columns spill and the other 45 hold plain typed labels including both of
this workbook's duplicate-label pairs, and the veto called the entire row
data). A spilling column is excluded from the row's own verdict entirely
-- it can be neither positive nor negative evidence for the REST of the
row, because whether IT is a label is already settled (it is not: see the
new SPILL_ORIGIN label state below). The row's verdict is then formed
from whichever columns remain, using the majority threshold below. The
one case a per-column exclusion cannot avoid: if EVERY column in the row
is a spill origin, nothing remains to judge the row by, and the row
itself is confidently data -- this is the only surviving case of
`not-identified-confident`, and it now means "unanimous", not "any one
column".

THE POSITIVE SIGNAL NEEDS A THRESHOLD TO BECOME A VERDICT (corrected
2026-09-09, after a real capture showed several sheets called
`identified` on one mismatching column out of twenty or more -- a
confidence of 0.087, not a judgment). `HEADER_POSITIVE_SIGNAL_THRESHOLD`
below is a plain majority (more than half) of the informative,
non-excluded columns showing the mismatch -- not fitted to any workbook's
own numbers, but the ordinary meaning of "the row's columns generally
look like labels": a collective judgment is a majority position, not one
vote out of many. Confidence below the threshold is still reported (the
measurement is not hidden), but the verdict in that case is UNDETERMINED,
never IDENTIFIED -- an important distinction design section 3.2 draws
elsewhere between a MEASUREMENT (reported as measured, no threshold
applied, e.g. the spill gap in stage3.py) and a VERDICT (a decision this
tool commits to, which does need one). Where this threshold turns a sheet
a maintainer would recognize as headed into UNDETERMINED, that is the
threshold's honest cost, not a bug -- the declarations file is the
remedy, and the artifact says so.

Row 1 is examined column by column; nothing here requires uniformity
across the surviving columns (design's own attested case: a header row
can hold formula cells among its labels, provided those cells do not
spill).

NOTHING HERE IS TUNED TO ANY WORKBOOK. The two measurements above, the
per-column exclusion, the majority threshold, and the resulting
three-way verdict (identified / not-identified-confident / undetermined)
are fixed rules applied uniformly to every sheet; no sheet name, column
name, or expected count appears anywhere in this module or in its tests.
Workbook-specific comparison -- including whether this rule gets the
Vertical and Current sheets right -- lives in a throwaway script outside
this repository.
"""

import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .artifact import ArtifactBase
from .coordinates import cell_address, col_to_letters, letters_to_col
from .counts import is_nonempty
from .declarations import Declarations, load_declarations
from .loader import Capture, discover_capture_files, load_capture
from .query import query_address
from .residue import ResidueEntry, build_stamp
from .stage3 import CLASSIFICATION_NO_FORMULA, ColumnProfileEntry, SpillRun, run_stage3
from .tokenizer import ERROR_LITERALS

HEADER_SOURCE_MEASURED = "measured"
HEADER_SOURCE_DECLARED = "declared"

HEADER_VERDICT_IDENTIFIED = "identified"
HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT = "not-identified-confident"
HEADER_VERDICT_UNDETERMINED = "undetermined"

LABEL_STATE_LABELED = "labeled"
LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER = "no-label-in-identified-header"
LABEL_STATE_UNKNOWN_HEADER_NOT_IDENTIFIED = "unknown-header-not-identified"
LABEL_STATE_NONE_NO_HEADER_IN_SHEET = "none-no-header-in-sheet"
# The fourth reason a column may lack a label (added 2026-09-09, alongside
# the three design section 4.2 names): this column's own row-1 cell is a
# spill origin, so it cannot be a label regardless of what the rest of the
# row's verdict is -- see this module's own docstring on why the spill
# signal now disqualifies the column, not the row.
LABEL_STATE_SPILL_ORIGIN_NOT_LABEL = "spill-origin-not-label"

_LABEL_STATES = (
    LABEL_STATE_LABELED,
    LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER,
    LABEL_STATE_UNKNOWN_HEADER_NOT_IDENTIFIED,
    LABEL_STATE_NONE_NO_HEADER_IN_SHEET,
    LABEL_STATE_SPILL_ORIGIN_NOT_LABEL,
)

# A plain majority: MORE than half of the informative, non-excluded
# columns must show the positive signal before this stage commits to an
# IDENTIFIED verdict. Chosen for the reasoning stated in this module's own
# docstring (a verdict is a collective judgment, not one vote among many),
# not by searching for a number that makes any particular workbook look
# right -- see this module's docstring and the reliability condition
# `run_stage4` builds for the same reasoning stated again, in the artifact
# itself, per this build's own instruction.
HEADER_POSITIVE_SIGNAL_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Type classification over evaluated values -- general rules about JSON
# value shapes, not about any one workbook's data.
# ---------------------------------------------------------------------------

def value_type_category(value: Any) -> Optional[str]:
    """None/empty-string is not a type -- excluded (returns None) so it
    never counts as either a match or a mismatch. Booleans are checked
    before numerics since `bool` is a subclass of `int` in Python. A
    string matching one of the tokenizer's own closed-vocabulary error
    literals is its own category, distinct from ordinary text, since
    Google Sheets itself distinguishes them."""
    if not is_nonempty(value):
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        return "error" if value in ERROR_LITERALS else "text"
    return "other"


def _dominant_type(categories: List[str]) -> Optional[str]:
    """The most common category in `categories`; None if empty. Ties are
    broken alphabetically for determinism -- an arbitrary but fixed and
    documented rule, never one that favours a particular workbook's data."""
    if not categories:
        return None
    counts = Counter(categories)
    top = max(counts.values())
    return sorted(k for k, v in counts.items() if v == top)[0]


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HeaderEvidence:
    positive_signal_columns: Tuple[str, ...]
    negative_signal_columns: Tuple[str, ...]
    informative_column_count: int
    total_column_count: int
    note: str


@dataclass(frozen=True)
class HeaderDetection:
    source: str
    verdict: str
    header_row1: Optional[int]
    confidence: Optional[float]
    evidence: HeaderEvidence

    def __post_init__(self):
        if self.source not in (HEADER_SOURCE_MEASURED, HEADER_SOURCE_DECLARED):
            raise ValueError(f"unknown header detection source: {self.source!r}")
        if self.verdict not in (
            HEADER_VERDICT_IDENTIFIED, HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT, HEADER_VERDICT_UNDETERMINED,
        ):
            raise ValueError(f"unknown header detection verdict: {self.verdict!r}")


def detect_header(capture: Capture, sheet_name: str) -> HeaderDetection:
    """Measured detection only -- a declared override, when present, is
    applied by the caller and never runs this at all (design section 8:
    the field is marked DECLARED, not a hybrid of declared and measured)."""
    fs = capture.formula_sheet(sheet_name)
    vs = capture.value_sheet(sheet_name)

    if fs.row_count == 0 or fs.column_count == 0:
        evidence = HeaderEvidence((), (), 0, fs.column_count, "sheet has no rows or no columns to examine")
        return HeaderDetection(HEADER_SOURCE_MEASURED, HEADER_VERDICT_UNDETERMINED, None, None, evidence)

    positive_columns: List[str] = []
    negative_columns: List[str] = []  # spill-disqualified columns, excluded from the vote below
    informative_count = 0

    for col0 in range(fs.column_count):
        col_letters = col_to_letters(col0)

        is_spilling = False
        if is_nonempty(fs.formulas[0][col0]):
            result = query_address(capture, sheet_name, cell_address(0, col0))
            if result.spill_extent is not None and result.spill_extent.down_to_row1 > 1:
                is_spilling = True

        if is_spilling:
            negative_columns.append(col_letters)
            continue  # excluded entirely: neither positive nor negative evidence for the REST of the row

        row1_value = vs.values[0][col0]
        row1_type = value_type_category(row1_value)
        body_categories = [
            value_type_category(vs.values[r][col0]) for r in range(1, fs.row_count)
        ]
        body_categories = [c for c in body_categories if c is not None]
        body_type = _dominant_type(body_categories)
        if row1_type is not None and body_type is not None:
            informative_count += 1
            if row1_type != body_type:
                positive_columns.append(col_letters)

    positive_columns.sort(key=letters_to_col)
    negative_columns.sort(key=letters_to_col)

    if len(negative_columns) == fs.column_count:
        # Every column is a spill origin -- nothing remains to judge the
        # row by, and the row itself is confidently data. The only
        # surviving case of not-identified-confident: unanimous, not "any
        # one column" (see this module's own docstring on why the veto
        # moved from the row to the column).
        note = (
            f"every column in row 1 ({fs.column_count}) is a spill origin whose measured extent reaches "
            f"beyond row 1 -- nothing remains to judge the row by, so the whole row is data, not labels"
        )
        evidence = HeaderEvidence((), tuple(negative_columns), 0, fs.column_count, note)
        return HeaderDetection(HEADER_SOURCE_MEASURED, HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT, None, 1.0, evidence)

    excluded_clause = (
        f"; {len(negative_columns)} column(s) excluded as spill origins" if negative_columns else ""
    )

    if informative_count == 0:
        note = (
            f"none of the {fs.column_count - len(negative_columns)} non-excluded column(s) were "
            f"informative for the type-mismatch check{excluded_clause}"
        )
        evidence = HeaderEvidence((), tuple(negative_columns), 0, fs.column_count, note)
        return HeaderDetection(HEADER_SOURCE_MEASURED, HEADER_VERDICT_UNDETERMINED, None, None, evidence)

    fraction = len(positive_columns) / informative_count
    evidence = HeaderEvidence(tuple(positive_columns), tuple(negative_columns), informative_count, fs.column_count, "")

    if fraction > HEADER_POSITIVE_SIGNAL_THRESHOLD:
        note = (
            f"{len(positive_columns)} of {informative_count} non-excluded informative column(s) "
            f"({fraction:.1%}) show row 1's evaluated type differing from the dominant type of that "
            f"column's own values beneath it, clearing the {HEADER_POSITIVE_SIGNAL_THRESHOLD:.0%} majority "
            f"threshold{excluded_clause}"
        )
        evidence = HeaderEvidence(tuple(positive_columns), tuple(negative_columns), informative_count, fs.column_count, note)
        return HeaderDetection(HEADER_SOURCE_MEASURED, HEADER_VERDICT_IDENTIFIED, 1, fraction, evidence)

    note = (
        f"{len(positive_columns)} of {informative_count} non-excluded informative column(s) "
        f"({fraction:.1%}) show the type-mismatch signal -- at or below the "
        f"{HEADER_POSITIVE_SIGNAL_THRESHOLD:.0%} majority threshold this stage requires before asserting "
        f"a header verdict{excluded_clause}"
    )
    evidence = HeaderEvidence(tuple(positive_columns), tuple(negative_columns), informative_count, fs.column_count, note)
    return HeaderDetection(HEADER_SOURCE_MEASURED, HEADER_VERDICT_UNDETERMINED, None, fraction, evidence)


# ---------------------------------------------------------------------------
# Duplicate labels, and the four-state header-label field
#
# Computed from whichever row is THIS SHEET'S CANDIDATE -- row 1 for every
# measured sheet (the only row measured detection ever examines, whether
# or not it concludes that row is a header), or the declared row for a
# sheet with a declared override (the only candidate that exists once a
# maintainer has named one). NEVER gated on the header verdict itself.
#
# This was a real design choice, not an oversight, and it stays
# unconditional even though the reason it was first added no longer holds
# the way it did: under the original (whole-row-veto) version of this
# rule, BOTH of this workbook's attested duplicate-label cases (design
# section 4.2's own examples, Current and Collate) sat in a sheet
# measured not-identified-confident, and gating duplicate detection on
# the header verdict would have made both attested duplicates
# unreportable. Under the corrected per-column rule (2026-09-09), both
# sheets now measure identified, and both duplicates sit inside an
# identified header -- exactly what design section 4.2's prose always
# claimed. Reporting duplicates unconditionally is still the right
# default: nothing here should have to change again if some THIRD sheet's
# candidate row is later measured not-identified-confident or
# undetermined while still containing a literal duplicate value.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DuplicateLabelEntry:
    label_value: Any
    columns: Tuple[str, ...]


def _duplicate_row1_values(row_values: Tuple[Any, ...]) -> Tuple[DuplicateLabelEntry, ...]:
    by_value: Dict[Any, List[str]] = {}
    for col0, value in enumerate(row_values):
        if not is_nonempty(value):
            continue
        try:
            by_value.setdefault(value, []).append(col_to_letters(col0))
        except TypeError:
            continue  # an unhashable evaluated value (not attested in any capture) -- not comparable, skipped
    duplicates = [
        DuplicateLabelEntry(label_value=v, columns=tuple(cols))
        for v, cols in by_value.items() if len(cols) > 1
    ]
    return tuple(sorted(duplicates, key=lambda d: letters_to_col(d.columns[0])))


@dataclass(frozen=True)
class HeaderLabel:
    state: str
    value: Optional[Any] = None

    def __post_init__(self):
        if self.state not in _LABEL_STATES:
            raise ValueError(f"unknown header-label state: {self.state!r}")
        if self.state != LABEL_STATE_LABELED and self.value is not None:
            raise ValueError("only the 'labeled' state may carry a value")


def _header_label_for_column(
    header: HeaderDetection, vs_row: Optional[Tuple[Any, ...]], col0: int, column_letters: str
) -> HeaderLabel:
    # Checked first, regardless of the row's own verdict: a column whose
    # own row-1 cell is a spill origin is never a label, whether the REST
    # of the row was identified as a header, is undetermined, or is itself
    # entirely spill (see this module's own docstring on why the spill
    # signal disqualifies the column, not the row). `negative_signal_columns`
    # is always empty for a declared header, so this never fires there.
    if column_letters in header.evidence.negative_signal_columns:
        return HeaderLabel(LABEL_STATE_SPILL_ORIGIN_NOT_LABEL)
    if header.verdict == HEADER_VERDICT_IDENTIFIED or header.source == HEADER_SOURCE_DECLARED:
        value = vs_row[col0]
        if is_nonempty(value):
            return HeaderLabel(LABEL_STATE_LABELED, value)
        return HeaderLabel(LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER)
    if header.verdict == HEADER_VERDICT_UNDETERMINED:
        return HeaderLabel(LABEL_STATE_UNKNOWN_HEADER_NOT_IDENTIFIED)
    return HeaderLabel(LABEL_STATE_NONE_NO_HEADER_IN_SHEET)


# ---------------------------------------------------------------------------
# Per-sheet schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnSchemaEntry:
    sheet: str
    column: str
    header_label: HeaderLabel
    formula_count: int
    value_count: int
    distinct_pattern_count: int
    classification: str
    spill_runs: Tuple[SpillRun, ...]


@dataclass(frozen=True)
class SheetSchemaEntry:
    sheet: str
    declared_row_count: int
    declared_column_count: int
    highest_row_with_formula: Optional[int]
    highest_column_with_formula: Optional[str]
    highest_row_with_value: Optional[int]
    highest_column_with_value: Optional[str]
    frozen_rows: int
    frozen_columns: int
    named_ranges: Tuple[Any, ...]
    data_validations: Tuple[Any, ...]
    conditional_format_rules: Tuple[Any, ...]
    protected_ranges: Tuple[Any, ...]
    header_detection: HeaderDetection
    # Computed from the candidate row (declared row, or else row 1)
    # regardless of header_detection.verdict -- see `_duplicate_row1_values`'s
    # own comment for why this is unconditional.
    duplicate_labels: Tuple[DuplicateLabelEntry, ...]
    columns: Tuple[ColumnSchemaEntry, ...]

    def __post_init__(self):
        object.__setattr__(
            self, "columns", tuple(sorted(self.columns, key=lambda c: letters_to_col(c.column)))
        )


@dataclass(frozen=True)
class SchemaArtifact(ArtifactBase):
    sheets: Tuple[SheetSchemaEntry, ...]

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "sheets", tuple(sorted(self.sheets, key=lambda s: s.sheet)))


def _used_extent(fs, vs) -> Tuple[Optional[int], Optional[str], Optional[int], Optional[str]]:
    """The highest row/column holding any non-empty formula, and the
    highest row/column holding any non-empty value, over the WHOLE sheet
    -- design section 4.2's "allocated versus used". None in a slot means
    that population (formulas, or values) is empty everywhere on this
    sheet, not row/column zero."""
    max_formula_row0 = max_formula_col0 = None
    max_value_row0 = max_value_col0 = None
    for row0 in range(fs.row_count):
        frow = fs.formulas[row0]
        vrow = vs.values[row0]
        for col0 in range(fs.column_count):
            if is_nonempty(frow[col0]):
                if max_formula_row0 is None or row0 > max_formula_row0:
                    max_formula_row0 = row0
                if max_formula_col0 is None or col0 > max_formula_col0:
                    max_formula_col0 = col0
            if is_nonempty(vrow[col0]):
                if max_value_row0 is None or row0 > max_value_row0:
                    max_value_row0 = row0
                if max_value_col0 is None or col0 > max_value_col0:
                    max_value_col0 = col0
    return (
        None if max_formula_row0 is None else max_formula_row0 + 1,
        None if max_formula_col0 is None else col_to_letters(max_formula_col0),
        None if max_value_row0 is None else max_value_row0 + 1,
        None if max_value_col0 is None else col_to_letters(max_value_col0),
    )


def _build_sheet_schema(
    capture: Capture, sheet_name: str,
    stage3_columns: Dict[Tuple[str, int], ColumnProfileEntry],
    declarations: Declarations,
) -> SheetSchemaEntry:
    fs = capture.formula_sheet(sheet_name)
    vs = capture.value_sheet(sheet_name)

    highest_row_f, highest_col_f, highest_row_v, highest_col_v = _used_extent(fs, vs)

    declared_row1 = declarations.header_row_override(sheet_name)
    if declared_row1 is not None:
        evidence = HeaderEvidence((), (), 0, fs.column_count, f"declared header row {declared_row1}; no detection evidence computed for this sheet")
        header = HeaderDetection(HEADER_SOURCE_DECLARED, HEADER_VERDICT_IDENTIFIED, declared_row1, None, evidence)
        header_row0 = declared_row1 - 1
    else:
        header = detect_header(capture, sheet_name)
        header_row0 = header.header_row1 - 1 if header.header_row1 is not None else None

    header_row_values = vs.values[header_row0] if header_row0 is not None and 0 <= header_row0 < fs.row_count else None
    # Duplicate values are computed from this sheet's CANDIDATE row --
    # the declared row if one was declared, else row 1, the only row
    # measured detection ever examines -- unconditionally, regardless of
    # header_detection.verdict. See this module's own comment above
    # `_duplicate_row1_values` for why.
    candidate_row0 = header_row0 if header.source == HEADER_SOURCE_DECLARED else 0
    candidate_row_values = (
        vs.values[candidate_row0] if fs.row_count > 0 and 0 <= candidate_row0 < fs.row_count else None
    )
    duplicate_labels = _duplicate_row1_values(candidate_row_values) if candidate_row_values is not None else ()

    columns = []
    for col0 in range(fs.column_count):
        column_letters = col_to_letters(col0)
        profile = stage3_columns.get((sheet_name, col0))
        label = _header_label_for_column(header, header_row_values, col0, column_letters)
        columns.append(
            ColumnSchemaEntry(
                sheet=sheet_name,
                column=column_letters,
                header_label=label,
                formula_count=profile.total_formula_count if profile else 0,
                value_count=profile.total_value_count if profile else 0,
                distinct_pattern_count=profile.distinct_pattern_count if profile else 0,
                classification=profile.classification if profile else CLASSIFICATION_NO_FORMULA,
                spill_runs=profile.spill_runs if profile else (),
            )
        )

    return SheetSchemaEntry(
        sheet=sheet_name,
        declared_row_count=fs.row_count,
        declared_column_count=fs.column_count,
        highest_row_with_formula=highest_row_f,
        highest_column_with_formula=highest_col_f,
        highest_row_with_value=highest_row_v,
        highest_column_with_value=highest_col_v,
        frozen_rows=fs.frozen_rows,
        frozen_columns=fs.frozen_columns,
        named_ranges=fs.named_ranges,
        data_validations=fs.data_validations,
        conditional_format_rules=fs.conditional_format_rules,
        protected_ranges=fs.protected_ranges,
        header_detection=header,
        duplicate_labels=duplicate_labels,
        columns=tuple(columns),
    )


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage4Result:
    capture: Capture
    schema: SchemaArtifact
    sheet_verdict_counts: Dict[Tuple[str, str], int]  # (source, verdict) -> count
    column_label_state_counts: Dict[str, int]


def run_stage4(formulas_path: str, values_path: str, declarations_path: Optional[str] = None) -> Stage4Result:
    capture = load_capture(formulas_path, values_path)
    declarations = load_declarations(declarations_path)
    stage3_result = run_stage3(formulas_path, values_path)
    stage3_columns = {
        (c.sheet, letters_to_col(c.column)): c for c in stage3_result.column_profiles.columns
    }

    sheets = tuple(
        _build_sheet_schema(capture, name, stage3_columns, declarations)
        for name in capture.sheet_order
    )

    residue: List[ResidueEntry] = []
    for sheet_entry in sheets:
        hd = sheet_entry.header_detection
        if hd.source == HEADER_SOURCE_MEASURED and hd.verdict == HEADER_VERDICT_UNDETERMINED:
            last_col = (
                col_to_letters(sheet_entry.declared_column_count - 1)
                if sheet_entry.declared_column_count > 0 else "A"
            )
            residue.append(
                ResidueEntry(
                    what=f"header detection for {sheet_entry.sheet} is undetermined: {hd.evidence.note}",
                    locations=(f"{sheet_entry.sheet}!A1:{last_col}1",),
                    defeating_construct="no header verdict reached the majority threshold in row 1",
                    consequence=(
                        "every column's header-label field on this sheet is reported UNKNOWN, not as having "
                        "no label -- whether row 1 is a header is not resolved here. The deciding inputs are "
                        "row 1's own evaluated values and each column's evaluated value types beneath it; "
                        "inspect them directly in the raw capture, or declare this sheet's header row "
                        "explicitly in the declarations file if it is known"
                    ),
                )
            )

    sheet_verdict_counts = Counter(
        (s.header_detection.source, s.header_detection.verdict) for s in sheets
    )
    column_label_state_counts = Counter(
        c.header_label.state for s in sheets for c in s.columns
    )

    total_sheets = sum(sheet_verdict_counts.values())
    if total_sheets != len(sheets):
        raise AssertionError("sheet header-verdict accounting failed to partition every sheet exactly once")
    total_columns = sum(column_label_state_counts.values())
    expected_total_columns = sum(s.declared_column_count for s in sheets)
    if total_columns != expected_total_columns:
        raise AssertionError(
            f"column header-label accounting failed to partition every declared column exactly once: "
            f"{total_columns} != {expected_total_columns}"
        )

    staleness_note = (
        "This artifact describes the workbook as it stood at the captureDate stamped on it, not the live "
        "workbook at the moment this artifact is read. A later capture of the same workbook legitimately "
        "producing a different header-detection verdict is not evidence that this tool has broken. Read "
        "the captureDate before treating any finding, or its absence, as current."
    )
    reliability_condition = (
        "Every header label and every duplicate-label finding in this file rests on this stage's own "
        "header-detection judgment for row 1 of each sheet -- or, where declared, on the maintainer's own "
        "assertion via the declarations file, which this tool never verifies against the capture. Measured "
        "detection rests on exactly two measurements, applied per column: whether row 1's evaluated value "
        "in a column differs in type from the dominant type of that column's own evaluated values beneath "
        "it (the positive signal), and whether row 1's cell in a column is a spill origin whose measured "
        "extent reaches beyond row 1 in the same column (the negative signal). A spilling column is "
        "excluded from the row's own verdict entirely -- it is neither positive nor negative evidence for "
        "the REST of the row, because whether IT is a label is already settled (it is not: its own "
        "header-label field reports 'spill-origin-not-label', regardless of the row's overall verdict). "
        "The row's verdict is then a majority vote among the columns that remain: more than "
        f"{HEADER_POSITIVE_SIGNAL_THRESHOLD:.0%} of the informative, non-excluded columns must show the "
        "positive signal before this stage asserts IDENTIFIED -- a plain majority, chosen because a row-level "
        "verdict is a collective judgment, not a threshold fitted to make any particular sheet come out a "
        "particular way. Confidence below that threshold is still reported (the measurement is never "
        "hidden); only the VERDICT changes to UNDETERMINED, because a verdict is a decision this tool "
        "commits to and a measurement is not. If every column in a row is a spill origin, nothing remains "
        "to vote with, and the row is confidently data (not-identified-confident is now a unanimous "
        "finding, not a one-column veto). What would defeat this: a header row whose labels happen to "
        "share the exact evaluated type of the data beneath them, and are not formulas of any kind, leaves "
        "neither signal to find and is reported UNDETERMINED here, never asserted as headerless; a "
        "spilling formula whose result is exactly one row tall would not register as a spill by this "
        "measurement and could be misread as a genuine label; a sheet whose real header is a minority of "
        "its informative columns (below the majority threshold) is reported UNDETERMINED rather than "
        "identified -- the threshold's honest cost, remediable only by a declared override, never by "
        "lowering the threshold to fit one sheet; and no row other than row 1 is ever considered a header "
        "candidate, so a header placed anywhere else in a sheet is invisible to measured detection and can "
        "only be recovered via a declared override. " + staleness_note
    )

    schema = SchemaArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=reliability_condition,
        residue=tuple(residue),
        sheets=sheets,
    )

    return Stage4Result(
        capture=capture,
        schema=schema,
        sheet_verdict_counts=dict(sheet_verdict_counts),
        column_label_state_counts=dict(column_label_state_counts),
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        print("usage: python -m sheet_derivation.stage4 <capture_directory> [declarations.json]", file=sys.stderr)
        return 2

    capture_dir = argv[0]
    declarations_path = argv[1] if len(argv) == 2 else None
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage4(formulas_path, values_path, declarations_path)

    print(f"captureDate: {result.capture.capture_date}")
    print(f"sheets: {len(result.schema.sheets)}")
    print(f"sheet verdicts (source, verdict) -> count: {result.sheet_verdict_counts}")
    print(f"column label states -> count: {result.column_label_state_counts}")
    print(f"schema residue entries: {len(result.schema.residue)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
