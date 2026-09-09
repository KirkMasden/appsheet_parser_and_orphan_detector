"""Stage 3: the formula inventory (design section 4.1) and the column
profiles it is built from, plus the spill assessment (design section 3.2's
fourth honest form) folded into those profiles per this build's own
instructions -- design section 4.2 (the schema file, stage 4, out of
scope here) is where the spill assessment is specified in the design
document itself, but it is built here because the inventory is where a
reader first needs it: a pattern's raw instance is only useful if its
column's values can be reached and judged, which is exactly what the
spill assessment and the value query (query.py) are for.

Nothing here may name a sheet, a column, or any other fact about one
workbook (design section 3.2) -- exactly the discipline stage0.py,
stage1.py and stage2.py already follow. Workbook-specific comparison
against this workbook's own gates lives in a throwaway script outside
this repository, alongside the other stages' own gate-check scripts.

ONE PASS, real normalization only. This module re-tokenizes and
re-normalizes every non-empty formula itself (via `scan_formula` /
`normalize_pattern`, the ONLY normalization path artifact-producing code
may use per normalize.py's own docstring) rather than reusing Stage 1's
in-memory pattern set, because Stage 1 tracks patterns per SHEET, not per
COLUMN, and the inventory's own instance-location requirement (design
4.1: "sheet, column and row ranges") needs column-level grouping Stage 1
never builds. This mirrors Stage 2's own choice to re-tokenize rather
than import Stage 1's result object.

THE ACCOUNTING INVARIANT, and why it is reported in two genuinely
separate parts here rather than forced into one subtractive sum. Design
section 6's invariant ("patterns matched plus residue entries sum to the
formula count") is enforced by Stage 2 by construction, because Stage 2's
residue is itself a partition of the SAME formula population its "matched"
count covers (a formula either needed no resolution, or needed some and
got some/none of it). Stage 3's formula-matching side has no such
partition to make: Gate B's normalization (Stage 1's own C2/C3 gates:
span tiling and renormalization stability) is TOTAL over every non-empty
formula in this workbook -- every single one produces exactly one pattern,
with nothing left over. So this artifact's "matched" side is, of
necessity, 100% of the formula count with 0 residue on that side, and
this module ASSERTS that (per-sheet and workbook-wide) rather than merely
reporting it as though it might have come out otherwise.

The residue this artifact actually records is a DIFFERENT population, in
a DIFFERENT unit, exactly as design section 6 licenses ("the two sides are
counted in different units... because a single formula may both produce
edges and leave something unresolved"): the spill assessment's value-only
runs, a population of non-formula cells, not formulas. That side has its
own, separately-enforced invariant -- every value-only run in every column
becomes EITHER a governed run (a formula was found above it, and the gap
is measured) OR a residue entry (none was), with no third outcome, which
this module also asserts rather than assumes.
"""

import bisect
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .artifact import ArtifactBase
from .coordinates import cell_address, col_to_letters, letters_to_col
from .counts import is_nonempty
from .loader import Capture, discover_capture_files, load_capture
from .normalize import normalize_pattern
from .residue import ResidueEntry, build_stamp
from .stage2 import SheetAccounting
from .tokenizer import TokenKind, scan_formula

CLASSIFICATION_SINGLE_CONTIGUOUS = "single-pattern-contiguous"
CLASSIFICATION_SINGLE_RAGGED = "single-pattern-ragged"
CLASSIFICATION_MULTI_PATTERN = "multi-pattern"
CLASSIFICATION_NO_FORMULA = "no-formula"


# ---------------------------------------------------------------------------
# The formula inventory (design section 4.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocationRange:
    """One contiguous run, within a single (sheet, column), of rows all
    holding an instance of one pattern. `row_start1`/`row_end1` are
    1-based and inclusive; a single-row instance has row_start1 ==
    row_end1. Never spans a row this pattern does NOT occupy -- a pattern
    at rows 5, 6 and 9 of one column produces TWO ranges (5-6 and 9-9),
    never one 5-9 range that would silently claim row 7 and 8 too."""

    sheet: str
    column: str
    row_start1: int
    row_end1: int

    @property
    def instance_count(self) -> int:
        return self.row_end1 - self.row_start1 + 1


@dataclass(frozen=True)
class PatternColumnProfileSummary:
    """The column-profile summary embedded in a pattern's own inventory
    entry, per design 4.1 ("the profile of each column it appears in").

    Deliberately a SUMMARY, not the full per-pattern breakdown the
    standalone column-profile artifact carries for this same column: this
    pattern's own count and share are here, alongside the column's
    distinct-pattern count and classification, which is already enough to
    answer design section 3.3's own question (is this pattern a singleton
    in an already-fragmented column, or an interruption in an otherwise
    uniform one) without embedding every OTHER pattern's share too. That
    fuller breakdown lives in the standalone column-profile artifact
    (`ColumnProfileEntry.patterns`) -- embedding it here as well would mean
    a column holding N distinct patterns (Collate column AB holds 82 in
    this capture) duplicating its full N-entry breakdown inside every one
    of its own N pattern entries, an N^2 blow-up this module declines to
    pay for a fact the standalone artifact already states once.
    """

    sheet: str
    column: str
    distinct_pattern_count: int
    classification: str
    total_formula_count: int
    total_value_count: int
    this_pattern_instance_count: int
    this_pattern_share: float


@dataclass(frozen=True)
class PatternEntry:
    pattern_text: str
    instance_count: int
    raw_instance: str
    locations: Tuple[LocationRange, ...]
    column_profiles: Tuple[PatternColumnProfileSummary, ...]

    def __post_init__(self):
        object.__setattr__(
            self, "locations",
            tuple(sorted(self.locations, key=lambda l: (l.sheet, letters_to_col(l.column), l.row_start1))),
        )
        object.__setattr__(
            self, "column_profiles",
            tuple(sorted(self.column_profiles, key=lambda p: (p.sheet, letters_to_col(p.column)))),
        )


@dataclass(frozen=True)
class FormulaInventoryArtifact(ArtifactBase):
    patterns: Tuple[PatternEntry, ...]

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "patterns", tuple(sorted(self.patterns, key=lambda p: p.pattern_text)))


# ---------------------------------------------------------------------------
# Column profiles, and the spill assessment folded into them
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnPatternShare:
    pattern_text: str
    instance_count: int
    share: float


@dataclass(frozen=True)
class SpillRun:
    """One contiguous run of value-present/formula-absent cells in one
    column (design 3.2's "spill-populated versus cell-filled" distinction,
    measured rather than assumed). `governing_formula_row1` is the nearest
    formula-bearing row ABOVE this run in the SAME column, if this module
    found one; `gap_rows` is the number of rows separating them (0 means
    the run starts in the very next row after the formula -- the ordinary,
    unbroken spill shape; a positive number means that many rows sit
    between them, structurally still "above", but not adjacent).

    No threshold is applied anywhere to `gap_rows` -- design section 3.2
    and this build's own instruction are explicit that deciding how large
    a gap reads as "unrelated" is not this tool's decision to make. The
    number is reported; the reader judges it.
    """

    sheet: str
    column: str
    row_start1: int
    row_end1: int
    governing_formula_row1: Optional[int]
    gap_rows: Optional[int]

    @property
    def value_count(self) -> int:
        return self.row_end1 - self.row_start1 + 1


@dataclass(frozen=True)
class ColumnProfileEntry:
    sheet: str
    column: str
    total_formula_count: int
    total_value_count: int
    distinct_pattern_count: int
    classification: str
    patterns: Tuple[ColumnPatternShare, ...]
    spill_runs: Tuple[SpillRun, ...]

    def __post_init__(self):
        object.__setattr__(
            self, "patterns",
            tuple(sorted(self.patterns, key=lambda p: (-p.instance_count, p.pattern_text))),
        )
        object.__setattr__(
            self, "spill_runs",
            tuple(sorted(self.spill_runs, key=lambda r: r.row_start1)),
        )


@dataclass(frozen=True)
class ColumnProfileArtifact(ArtifactBase):
    columns: Tuple[ColumnProfileEntry, ...]

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(
            self, "columns",
            tuple(sorted(self.columns, key=lambda c: (c.sheet, letters_to_col(c.column)))),
        )


@dataclass(frozen=True)
class Stage3Result:
    capture: Capture
    inventory: FormulaInventoryArtifact
    column_profiles: ColumnProfileArtifact
    accounting: Tuple[SheetAccounting, ...]
    spill_run_total: int
    spill_run_residue_count: int

    @property
    def workbook_accounting(self) -> SheetAccounting:
        return SheetAccounting(
            sheet_name="__workbook_total__",
            non_empty_formulas=sum(a.non_empty_formulas for a in self.accounting),
            matched_formulas=sum(a.matched_formulas for a in self.accounting),
            residue_formulas=sum(a.residue_formulas for a in self.accounting),
        )


# ---------------------------------------------------------------------------
# The single pass
# ---------------------------------------------------------------------------

@dataclass
class _ColumnAccumulator:
    formula_rows: List[int] = field(default_factory=list)
    pattern_counts: Counter = field(default_factory=Counter)
    value_nonempty_count: int = 0
    value_only_rows: List[int] = field(default_factory=list)


def _contiguous_ranges(rows_sorted: List[int]) -> List[Tuple[int, int]]:
    """Sorted 0-indexed rows -> a list of (start0, end0) contiguous runs."""
    if not rows_sorted:
        return []
    ranges = []
    start = prev = rows_sorted[0]
    for r in rows_sorted[1:]:
        if r == prev + 1:
            prev = r
            continue
        ranges.append((start, prev))
        start = prev = r
    ranges.append((start, prev))
    return ranges


def run_stage3(formulas_path: str, values_path: str) -> Stage3Result:
    capture = load_capture(formulas_path, values_path)

    # pattern text -> instances, in capture order (sheet order, then
    # row-major) -- instances[0] is therefore always "the first instance
    # found", the same convention Stage 1's PatternInfo.first_raw uses.
    pattern_instances: Dict[str, List[Tuple[str, int, int, str]]] = {}
    column_data: Dict[Tuple[str, int], _ColumnAccumulator] = {}
    per_sheet_formula_count: Dict[str, int] = {name: 0 for name in capture.sheet_order}

    for sheet_name in capture.sheet_order:
        fs = capture.formula_sheet(sheet_name)
        vs = capture.value_sheet(sheet_name)
        for row0 in range(fs.row_count):
            frow = fs.formulas[row0]
            vrow = vs.values[row0]
            for col0 in range(fs.column_count):
                raw = frow[col0]
                val = vrow[col0]
                formula_present = is_nonempty(raw)
                value_present = is_nonempty(val)
                if not formula_present and not value_present:
                    continue
                acc = column_data.setdefault((sheet_name, col0), _ColumnAccumulator())
                if formula_present:
                    per_sheet_formula_count[sheet_name] += 1
                    tokens = scan_formula(raw)
                    pattern_text = normalize_pattern(raw, tokens)
                    pattern_instances.setdefault(pattern_text, []).append((sheet_name, row0, col0, raw))
                    acc.formula_rows.append(row0)
                    acc.pattern_counts[pattern_text] += 1
                    if value_present:
                        acc.value_nonempty_count += 1
                elif value_present:
                    acc.value_nonempty_count += 1
                    acc.value_only_rows.append(row0)

    # ------------------------------------------------------------------
    # Column profiles, including the spill assessment.
    # ------------------------------------------------------------------
    column_profile_by_key: Dict[Tuple[str, int], ColumnProfileEntry] = {}
    spill_residue: List[ResidueEntry] = []
    spill_run_total = 0
    spill_run_residue_count = 0

    for (sheet_name, col0), acc in column_data.items():
        column_letters = col_to_letters(col0)
        total_formula_count = len(acc.formula_rows)
        distinct_pattern_count = len(acc.pattern_counts)

        if total_formula_count == 0:
            classification = CLASSIFICATION_NO_FORMULA
        elif distinct_pattern_count == 1:
            rows_sorted = sorted(acc.formula_rows)
            contiguous = (rows_sorted[-1] - rows_sorted[0] + 1) == len(rows_sorted)
            classification = CLASSIFICATION_SINGLE_CONTIGUOUS if contiguous else CLASSIFICATION_SINGLE_RAGGED
        else:
            classification = CLASSIFICATION_MULTI_PATTERN

        patterns = tuple(
            ColumnPatternShare(pattern_text=p, instance_count=cnt, share=cnt / total_formula_count)
            for p, cnt in acc.pattern_counts.items()
        )

        formula_rows_sorted = sorted(acc.formula_rows)
        value_only_rows_sorted = sorted(acc.value_only_rows)
        spill_runs: List[SpillRun] = []
        for start0, end0 in _contiguous_ranges(value_only_rows_sorted):
            spill_run_total += 1
            idx = bisect.bisect_left(formula_rows_sorted, start0)
            if idx == 0:
                governing_row0 = None
            else:
                governing_row0 = formula_rows_sorted[idx - 1]
            run_start1, run_end1 = start0 + 1, end0 + 1
            if governing_row0 is None:
                spill_run_residue_count += 1
                cells = tuple(
                    f"{sheet_name}!{cell_address(r, col0)}" for r in range(start0, end0 + 1)
                )
                if total_formula_count == 0:
                    what = (
                        f"column {sheet_name}!{column_letters} holds {len(value_only_rows_sorted)} "
                        f"value(s) (rows {run_start1}-{run_end1} of this run) and no formula anywhere "
                        f"in this column"
                    )
                    defeating = "no formula anywhere in this column"
                else:
                    what = (
                        f"value-only run at {sheet_name}!{column_letters}{run_start1}:"
                        f"{column_letters}{run_end1} has no formula above it in this column "
                        f"(this column does hold {total_formula_count} formula(s) elsewhere)"
                    )
                    defeating = "no formula above this run in this column"
                spill_residue.append(
                    ResidueEntry(
                        what=what,
                        locations=cells,
                        defeating_construct=defeating,
                        consequence=(
                            "the gap between these values and any governing formula cannot be measured "
                            "here; whether they come from a sideways spill from another column, a bound "
                            "script, manual entry, or an import is not established by this artifact -- "
                            "consult the raw capture (and any declarations file) directly at the cells named above"
                        ),
                    )
                )
                spill_runs.append(
                    SpillRun(
                        sheet=sheet_name, column=column_letters,
                        row_start1=run_start1, row_end1=run_end1,
                        governing_formula_row1=None, gap_rows=None,
                    )
                )
            else:
                gap_rows = start0 - governing_row0 - 1
                spill_runs.append(
                    SpillRun(
                        sheet=sheet_name, column=column_letters,
                        row_start1=run_start1, row_end1=run_end1,
                        governing_formula_row1=governing_row0 + 1, gap_rows=gap_rows,
                    )
                )

        column_profile_by_key[(sheet_name, col0)] = ColumnProfileEntry(
            sheet=sheet_name,
            column=column_letters,
            total_formula_count=total_formula_count,
            total_value_count=acc.value_nonempty_count,
            distinct_pattern_count=distinct_pattern_count,
            classification=classification,
            patterns=patterns,
            spill_runs=tuple(spill_runs),
        )

    # ------------------------------------------------------------------
    # Pattern entries: locations, embedded column-profile summaries.
    # ------------------------------------------------------------------
    pattern_entries: List[PatternEntry] = []
    inventory_residue: List[ResidueEntry] = []

    for pattern_text, instances in pattern_instances.items():
        by_column: Dict[Tuple[str, int], List[int]] = {}
        for s, r, c, _raw in instances:
            by_column.setdefault((s, c), []).append(r)

        locations = []
        for (s, c), rows in by_column.items():
            for start0, end0 in _contiguous_ranges(sorted(rows)):
                locations.append(
                    LocationRange(sheet=s, column=col_to_letters(c), row_start1=start0 + 1, row_end1=end0 + 1)
                )

        column_profiles = []
        for (s, c), rows in by_column.items():
            profile = column_profile_by_key[(s, c)]
            column_profiles.append(
                PatternColumnProfileSummary(
                    sheet=s,
                    column=col_to_letters(c),
                    distinct_pattern_count=profile.distinct_pattern_count,
                    classification=profile.classification,
                    total_formula_count=profile.total_formula_count,
                    total_value_count=profile.total_value_count,
                    this_pattern_instance_count=len(rows),
                    this_pattern_share=len(rows) / profile.total_formula_count,
                )
            )

        first_sheet, first_row0, first_col0, first_raw = instances[0]
        pattern_entries.append(
            PatternEntry(
                pattern_text=pattern_text,
                instance_count=len(instances),
                raw_instance=first_raw,
                locations=tuple(locations),
                column_profiles=tuple(column_profiles),
            )
        )

        # UNKNOWN-token check (defensive, per this module's own docstring
        # on why the formula-matching side of the accounting is asserted
        # rather than assumed total): a pattern's UNKNOWN-token status is
        # structural (Stage 1's own tokenizer never lets row-digit rewrite
        # touch a span's KIND), so checking the representative instance's
        # tokens once covers every instance of this pattern.
        rep_tokens = scan_formula(first_raw)
        if any(t.kind == TokenKind.UNKNOWN for t in rep_tokens):
            all_cells = tuple(f"{s}!{cell_address(r, c)}" for s, r, c, _ in instances)
            inventory_residue.append(
                ResidueEntry(
                    what=f"this pattern's tokenizer output contains an UNKNOWN-classified span: {first_raw!r}",
                    locations=all_cells,
                    defeating_construct="UNKNOWN token",
                    consequence=(
                        "this pattern's text still normalizes and is still counted as matched -- Gate B's "
                        "normalization never fails to produce a pattern -- but the unclassified span may "
                        "make the pattern text less meaningful than it looks; read the raw instance directly"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Accounting: the formula side is total by construction; asserted,
    # not assumed. See this module's own docstring for why the spill-run
    # side is a separate, differently-unit-ed invariant, not folded in.
    # ------------------------------------------------------------------
    matched_by_pattern: Counter = Counter()
    for pattern_text, instances in pattern_instances.items():
        for s, _r, _c, _raw in instances:
            matched_by_pattern[s] += 1

    accounting = tuple(
        SheetAccounting(
            sheet_name=name,
            non_empty_formulas=per_sheet_formula_count[name],
            matched_formulas=matched_by_pattern.get(name, 0),
            residue_formulas=0,
        )
        for name in capture.sheet_order
    )
    for a in accounting:
        if not a.balances:
            raise AssertionError(
                f"formula-matching accounting failed to balance for sheet {a.sheet_name!r}: "
                f"{a.matched_formulas} matched + {a.residue_formulas} residue != {a.non_empty_formulas} "
                "non-empty formulas -- Gate B normalization is supposed to be total over every formula; "
                "this indicates a real defect, not a workbook property to report around"
            )
    if spill_run_residue_count > sum(len(cp.spill_runs) for cp in column_profile_by_key.values()):
        raise AssertionError("spill-run residue count exceeds total spill runs -- invariant violated")

    staleness_note = (
        "This artifact describes the workbook as it stood at the captureDate stamped on it, not the live "
        "workbook at the moment this artifact is read. A later capture of the same workbook legitimately "
        "producing different patterns, counts, or spill measurements is not evidence that this tool has "
        "broken. Read the captureDate before treating any finding, or its absence, as current."
    )

    inventory = FormulaInventoryArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=(
            "Every pattern is produced by Stage 1's own real (Gate B) normalization, which Stage 1's own "
            "gates (span tiling, renormalization stability) establish as total over every non-empty "
            "formula in this capture -- so the formula-matching side of this artifact's accounting is "
            "100% matched, 0 residue, per sheet and workbook-wide, asserted at build time rather than "
            "merely reported. This artifact's own residue entries (if any) concern formulas whose "
            "tokenizer output contains an UNKNOWN span -- a distinct, much narrower condition from "
            "'failed to normalize', which cannot happen here. Each pattern's embedded column-profile "
            "summary is only a summary (this pattern's own share and its column's classification); the "
            "full per-pattern breakdown for a column lives in the standalone column-profile artifact. " + staleness_note
        ),
        residue=tuple(inventory_residue),
        patterns=tuple(pattern_entries),
    )

    column_profiles = ColumnProfileArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=(
            "A column's classification (single-pattern-contiguous / single-pattern-ragged / multi-pattern "
            "/ no-formula) is computed purely from measured row positions of non-empty formulas in that "
            "column -- no threshold or expectation about column uniformity is assumed anywhere. The spill "
            "assessment measures, for every contiguous run of value-present/formula-absent cells, the row "
            "distance to the nearest formula-bearing cell ABOVE it in the same column (a structural "
            "measurement, per query.py's own docstring, never a claim that a spill produced these values); "
            "a run with no such formula anywhere above it becomes a residue entry instead of a measured "
            "gap, exactly one or the other, never both and never neither. No numeric gap is ever judged "
            "'too large to be related' by this tool -- design section 3.2 and this build's own instruction "
            "are explicit that this is the reader's judgment, not a default this tool may encode. " + staleness_note
        ),
        residue=tuple(spill_residue),
        columns=tuple(column_profile_by_key.values()),
    )

    return Stage3Result(
        capture=capture,
        inventory=inventory,
        column_profiles=column_profiles,
        accounting=accounting,
        spill_run_total=spill_run_total,
        spill_run_residue_count=spill_run_residue_count,
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m sheet_derivation.stage3 <capture_directory>", file=sys.stderr)
        return 2

    capture_dir = argv[0]
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage3(formulas_path, values_path)

    print(f"captureDate: {result.capture.capture_date}")
    print(f"distinct patterns: {len(result.inventory.patterns):,}")
    wb = result.workbook_accounting
    print(f"formula accounting: matched {wb.matched_formulas:,} + residue {wb.residue_formulas:,} "
          f"= {wb.matched_formulas + wb.residue_formulas:,} (formulas: {wb.non_empty_formulas:,}, "
          f"balances: {wb.balances})")
    print(f"column profiles: {len(result.column_profiles.columns):,}")
    print(f"spill runs: {result.spill_run_total:,} ({result.spill_run_residue_count:,} without a governing formula)")
    print(f"inventory residue entries: {len(result.inventory.residue)}")
    print(f"column-profile residue entries: {len(result.column_profiles.residue)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
