"""Stage 1: the token scanner, the normalization built on it, and the
generic (workbook-agnostic) machinery a gate report is built from.

Nothing in this module may name a sheet, a function, or any other fact
about one workbook -- it operates on whatever Capture it is given, real or
synthetic, the same way stage0.py does. The comparison against the
probe's specific numbers for Kirk's own workbook (sheet names, expected
counts, named cells) is deliberately NOT here: that comparison lives in a
throwaway script outside the repository, the same place the probe script
itself lives, because making that comparison would mean writing this
workbook's sheet names into committed code.

Stage 1 builds no artifact (design section 4): no formula inventory, no
schema file, no dependency graph, no join, no dangling-reference report.
It ends at a token stream, a normalization built on it, and the counts a
gate report reads from -- see run_stage1's docstring for exactly what
that includes.
"""

import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Tuple

from .coordinates import cell_address
from .counts import is_nonempty
from .loader import Capture, discover_capture_files, load_capture
from .normalize import normalize_pattern, renormalize_is_stable
from .tokenizer import Token, TokenKind, assert_tiles, scan_formula
from .verify import normalize_probe_equivalent


@dataclass(frozen=True)
class PatternInfo:
    """One distinct pattern's summary: how it is found first (capture
    order: sheet order, then row-major), and how often it recurs.

    Per R6, `first_raw` is never truncated -- it is the literal formula
    text of the first instance, stored whole. Stage 1 does not build the
    formula-inventory artifact (out of scope), so this is not "the"
    canonical raw instance an artifact would carry forward; it is only
    what the gate report needs to name an example.
    """

    pattern_text: str
    instance_count: int
    first_sheet: str
    first_row0: int
    first_col0: int
    first_raw: str

    @property
    def first_address(self) -> str:
        return f"{self.first_sheet}!{cell_address(self.first_row0, self.first_col0)}"


@dataclass(frozen=True)
class SheetSheetCounts:
    sheet_name: str
    non_empty_formulas: int
    distinct_patterns_gate_a: int
    distinct_patterns_gate_b: int


@dataclass
class _Accumulator:
    """Mutable working state for one pass over the capture. Finalized
    into Stage1Result's frozen, sorted collections by run_stage1."""

    gate_a_patterns: Dict[str, PatternInfo] = field(default_factory=dict)
    gate_a_counts: Counter = field(default_factory=Counter)
    gate_b_patterns: Dict[str, PatternInfo] = field(default_factory=dict)
    gate_b_counts: Counter = field(default_factory=Counter)
    per_sheet_gate_a: Dict[str, Counter] = field(default_factory=dict)
    per_sheet_gate_b: Dict[str, Counter] = field(default_factory=dict)
    per_sheet_nonempty: Counter = field(default_factory=Counter)
    # gate_a pattern text -> set of gate_b pattern texts observed among
    # the formulas that share that gate_a pattern (Gate B2's reconciliation).
    a_to_b_split: Dict[str, set] = field(default_factory=dict)
    token_kind_totals: Counter = field(default_factory=Counter)
    unknown_token_examples: list = field(default_factory=list)
    total_nonempty_formulas: int = 0


_UNKNOWN_EXAMPLE_CAP = 50


def _record_pattern(store: Dict[str, PatternInfo], counts: Counter,
                     pattern_text: str, sheet_name: str, row0: int, col0: int, raw: str) -> None:
    counts[pattern_text] += 1
    if pattern_text not in store:
        store[pattern_text] = PatternInfo(
            pattern_text=pattern_text,
            instance_count=1,
            first_sheet=sheet_name,
            first_row0=row0,
            first_col0=col0,
            first_raw=raw,
        )


def _finalize_counts(store: Dict[str, PatternInfo], counts: Counter) -> Dict[str, PatternInfo]:
    return {
        pat: PatternInfo(
            pattern_text=info.pattern_text,
            instance_count=counts[pat],
            first_sheet=info.first_sheet,
            first_row0=info.first_row0,
            first_col0=info.first_col0,
            first_raw=info.first_raw,
        )
        for pat, info in store.items()
    }


def process_sheet(capture: Capture, sheet_name: str, acc: _Accumulator) -> None:
    """Tokenizes and normalizes every non-empty formula in one sheet,
    both ways (Gate A's probe-equivalent mode and Gate B's real tool
    mode), asserting R2 (span tiling) and Gate C3 (renormalization
    stability) on every single one -- not a sample."""
    formula_sheet = capture.formula_sheet(sheet_name)
    acc.per_sheet_gate_a.setdefault(sheet_name, Counter())
    acc.per_sheet_gate_b.setdefault(sheet_name, Counter())

    for row0, row in enumerate(formula_sheet.formulas):
        for col0, raw in enumerate(row):
            if not is_nonempty(raw):
                continue
            acc.total_nonempty_formulas += 1
            acc.per_sheet_nonempty[sheet_name] += 1

            tokens = scan_formula(raw)
            assert_tiles(raw, tokens)  # R2 / Gate C2, every formula

            for tok in tokens:
                acc.token_kind_totals[tok.kind.value] += 1
                if tok.kind == TokenKind.UNKNOWN and len(acc.unknown_token_examples) < _UNKNOWN_EXAMPLE_CAP:
                    acc.unknown_token_examples.append(
                        (sheet_name, cell_address(row0, col0), raw[tok.start:tok.end], tok.start)
                    )

            pattern_b = normalize_pattern(raw, tokens)
            if not renormalize_is_stable(raw, tokens):  # Gate C3, every formula
                raise AssertionError(
                    f"renormalization is not stable for {sheet_name}!{cell_address(row0, col0)}: "
                    f"raw={raw!r} pattern={pattern_b!r}"
                )
            pattern_a = normalize_probe_equivalent(raw)

            _record_pattern(acc.gate_b_patterns, acc.gate_b_counts, pattern_b, sheet_name, row0, col0, raw)
            _record_pattern(acc.gate_a_patterns, acc.gate_a_counts, pattern_a, sheet_name, row0, col0, raw)
            acc.per_sheet_gate_a[sheet_name][pattern_a] += 1
            acc.per_sheet_gate_b[sheet_name][pattern_b] += 1
            acc.a_to_b_split.setdefault(pattern_a, set()).add(pattern_b)


@dataclass(frozen=True)
class Stage1Result:
    capture: Capture
    gate_a_patterns: Dict[str, PatternInfo]
    gate_b_patterns: Dict[str, PatternInfo]
    per_sheet_counts: Tuple[SheetSheetCounts, ...]
    per_sheet_gate_a_pattern_counts: Dict[str, Counter]
    per_sheet_gate_b_pattern_counts: Dict[str, Counter]
    a_to_b_split: Dict[str, FrozenSet[str]]
    token_kind_totals: Dict[str, int]
    unknown_token_examples: Tuple[tuple, ...]
    total_nonempty_formulas: int

    @property
    def total_distinct_patterns_gate_a(self) -> int:
        return len(self.gate_a_patterns)

    @property
    def total_distinct_patterns_gate_b(self) -> int:
        return len(self.gate_b_patterns)


def run_stage1(formulas_path: str, values_path: str) -> Stage1Result:
    capture = load_capture(formulas_path, values_path)
    acc = _Accumulator()
    for sheet_name in capture.sheet_order:
        process_sheet(capture, sheet_name, acc)

    gate_a_final = _finalize_counts(acc.gate_a_patterns, acc.gate_a_counts)
    gate_b_final = _finalize_counts(acc.gate_b_patterns, acc.gate_b_counts)

    per_sheet_counts = tuple(
        SheetSheetCounts(
            sheet_name=name,
            non_empty_formulas=acc.per_sheet_nonempty.get(name, 0),
            distinct_patterns_gate_a=len(acc.per_sheet_gate_a.get(name, {})),
            distinct_patterns_gate_b=len(acc.per_sheet_gate_b.get(name, {})),
        )
        for name in capture.sheet_order
    )

    a_to_b_split = {pat_a: frozenset(pat_bs) for pat_a, pat_bs in acc.a_to_b_split.items()}

    return Stage1Result(
        capture=capture,
        gate_a_patterns=gate_a_final,
        gate_b_patterns=gate_b_final,
        per_sheet_counts=per_sheet_counts,
        per_sheet_gate_a_pattern_counts=acc.per_sheet_gate_a,
        per_sheet_gate_b_pattern_counts=acc.per_sheet_gate_b,
        a_to_b_split=a_to_b_split,
        token_kind_totals=dict(acc.token_kind_totals),
        unknown_token_examples=tuple(acc.unknown_token_examples),
        total_nonempty_formulas=acc.total_nonempty_formulas,
    )


def function_vocabulary(result: Stage1Result, *, use_gate_a: bool = True) -> Dict[str, int]:
    """Function name -> occurrence-weighted count across DISTINCT patterns,
    same methodology as the probe's section 5 table (its own header:
    "count (distinct patterns containing it, occurrence-weighted)") --
    each pattern's raw text is examined once regardless of its INSTANCE
    count (a pattern used in 9,999 cells is still one scan), but EVERY
    occurrence of a function name WITHIN that one pattern's text counts
    separately (a pattern with three nested IFs adds 3 to IF's total, not
    1). This module's version is token-based: only FUNCTION_NAME tokens
    count, so an identifier-followed-by-'(' inside a STRING_LITERAL span
    is correctly excluded (it is never a FUNCTION_NAME token -- the whole
    string literal is one opaque token to begin with).

    Defaults to the Gate A pattern set since that is what Stage 1's gate
    report reproduces probe section 5 against; pass use_gate_a=False to
    compute the same thing over Gate B's real pattern set instead.
    """
    patterns = result.gate_a_patterns if use_gate_a else result.gate_b_patterns
    counter: Counter = Counter()
    for info in patterns.values():
        tokens = scan_formula(info.first_raw)
        for tok in tokens:
            if tok.kind == TokenKind.FUNCTION_NAME:
                counter[info.first_raw[tok.start:tok.end].upper()] += 1
    return dict(counter)


def sheet_qualified_reference_positions(raw: str) -> Tuple[Token, ...]:
    """The BARE_SHEET_NAME / QUOTED_SHEET_NAME tokens found in `raw` --
    genuine reference-position sheet names, per the real tokenizer's
    classification (never a string-literal interior, by construction)."""
    return tuple(
        tok for tok in scan_formula(raw)
        if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME)
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m sheet_derivation.stage1 <capture_directory>", file=sys.stderr)
        return 2

    capture_dir = argv[0]
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage1(formulas_path, values_path)

    print(f"captureDate: {result.capture.capture_date}")
    print(f"non-empty formulas: {result.total_nonempty_formulas:,}")
    print(f"distinct patterns (Gate A, probe-equivalent mode): {result.total_distinct_patterns_gate_a:,}")
    print(f"distinct patterns (Gate B, real tool mode): {result.total_distinct_patterns_gate_b:,}")
    print()
    print("| sheetName | non-empty formulas | distinct patterns (A) | distinct patterns (B) |")
    print("|---|---:|---:|---:|")
    for c in result.per_sheet_counts:
        print(f"| {c.sheet_name} | {c.non_empty_formulas:,} | {c.distinct_patterns_gate_a:,} | {c.distinct_patterns_gate_b:,} |")
    print()
    print("Token kind census (over every non-empty formula):")
    for kind, count in sorted(result.token_kind_totals.items()):
        print(f"  {kind}: {count:,}")
    unknown_count = result.token_kind_totals.get(TokenKind.UNKNOWN.value, 0)
    print(f"UNKNOWN tokens: {unknown_count:,}" + (" (zero)" if unknown_count == 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
