"""Stage 2: reference resolution -- the column dependency graph (design
section 4.3) and the dangling sheet-name list (design section 4.5), both
built from ONE pass over the capture using Stage 1's own token stream
(`scan_formula`, `normalize_pattern`). This module runs no regular
expression of its own over formula text: every reference-shaped run this
module finds is found by reading `TokenKind`s Stage 1 already assigned, or
by re-applying `scan_formula` itself to an already-isolated span (a
STRING_LITERAL token's own interior) -- never by scanning raw formula text
with a new pattern. Where the token stream does not carry something a
finding needs (see `_looks_like_indirect_or_offset`'s argument text, for
instance), that gap is reported as residue, not patched with a new regex.

Nothing here may name a sheet, a column, or any other fact about one
workbook (design section 3.2) -- exactly the discipline stage0.py and
stage1.py already follow. Workbook-specific comparison against this
workbook's own gates lives in a throwaway script outside this repository,
alongside the capture-probe script and stage 1's own gate-check scripts.

THE STANDING INVARIANT THIS MODULE ENFORCES, stated once here because it
governs several design decisions below: every reference-shaped token
becomes either a graph edge or a residue entry, with no third outcome.
This reaches further than design section 4.3's own four residue
categories (INDIRECT/OFFSET arguments, IMPORTRANGE/QUERY string ranges,
ARRAYFORMULA spans, unclassifiable-position tokens) in two ways this
module treats as settled, not optional:

1. A sheet-qualified reference in REFERENCE position whose name matches no
   captured sheet cannot become a graph edge (there is no target column to
   point at) -- so it becomes a graph residue entry too, alongside its
   entry in the dangling-name artifact. The two artifacts are not
   alternatives; a dangling name that only appeared in one of them would
   have vanished from the other.
2. A sheet-name-shaped run found inside a STRING_LITERAL is, BY THIS
   MODULE'S OWN DEFINITION, never a candidate for a graph edge (the graph
   only draws edges from REFERENCE-position tokens) -- so every one always
   becomes a residue entry, even when the name it names is a real,
   captured sheet. Only omitting the graph residue entry would let a
   correctly-classified token disappear from every artifact, which is
   exactly what the standing invariant forbids.

CLASSIFICATION IS EXACT, NOT HEURISTIC, IN THIS TOOL. Design section 4.5
flags one field of the dangling-name artifact as needing an "ambiguous"
state, because the capture probe's own quote-parity heuristic cannot always
tell a reference from a string-literal occurrence. This module has no such
gap: `scan_formula`'s token stream tiles the formula exactly (Stage 1's own
R2), so a run is either inside a BARE_SHEET_NAME/QUOTED_SHEET_NAME token
(reference position) or inside a STRING_LITERAL token (string-literal
position) -- never both, never neither, by construction. The "ambiguous"
state is kept in the classification vocabulary below for design fidelity
and for any future construct that might defeat it, but this module never
assigns it, and that is a fact about this tool, not an empirical finding
that could vary by workbook.
"""

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from .artifact import ArtifactBase
from .coordinates import CoordinateModel, cell_address, col_to_letters, letters_to_col
from .counts import SheetCounts, compute_all_counts, is_nonempty
from .loader import Capture, discover_capture_files, load_capture
from .normalize import normalize_pattern
from .residue import ArtifactStamp, ResidueEntry, build_stamp
from .tokenizer import Token, TokenKind, scan_formula

# Function names whose argument this stage does not evaluate. Per design
# section 4.3; INDIRECT/OFFSET arguments are never resolved even one hop,
# since the reference they name is computed at evaluation time, not written
# in the formula. Uppercased for comparison since Google Sheets formulas are
# case-insensitive on function names.
_OPAQUE_ARGUMENT_FUNCTIONS = frozenset({"INDIRECT", "OFFSET"})
_STRING_RANGE_CARRYING_FUNCTIONS = frozenset({"IMPORTRANGE", "QUERY"})
_ARRAY_CONTEXT_FUNCTIONS = frozenset({"ARRAYFORMULA"})

CLASSIFICATION_REFERENCE_POSITION = "reference position"
CLASSIFICATION_STRING_LITERAL_POSITION = "string literal position"
CLASSIFICATION_AMBIGUOUS = "ambiguous"


# ---------------------------------------------------------------------------
# A1 address helpers. Manual character scans over an already-isolated
# token's own text -- the same style tokenizer.py itself uses for its
# scanners -- never a `re` pattern over formula text.
# ---------------------------------------------------------------------------

def _split_column_and_row(a1_reference_text: str) -> Tuple[str, Optional[int]]:
    """'$AB$153' -> ('AB', 153); 'AB' -> ('AB', None); '$J' -> ('J', None).

    `a1_reference_text` is one A1_REFERENCE token's own text, dollar signs
    and all -- never re-derived from raw formula text by pattern matching.
    """
    i, n = 0, len(a1_reference_text)
    while i < n and a1_reference_text[i] == "$":
        i += 1
    letters_start = i
    while i < n and a1_reference_text[i].isalpha():
        i += 1
    letters = a1_reference_text[letters_start:i].upper()
    while i < n and a1_reference_text[i] == "$":
        i += 1
    digits = a1_reference_text[i:]
    row1 = int(digits) if digits else None
    return letters, row1


def _columns_between(col1: str, col2: str) -> Tuple[str, ...]:
    """Every column letter from col1 to col2 inclusive, in sheet order --
    handles col1 == col2 (a single column) and either order (a range
    written high-to-low)."""
    n1, n2 = letters_to_col(col1), letters_to_col(col2)
    lo, hi = min(n1, n2), max(n1, n2)
    return tuple(col_to_letters(n) for n in range(lo, hi + 1))


@dataclass(frozen=True)
class AddressExpression:
    """One resolved cell or range reference: the columns it spans (always
    at least one), and its row span, or (None, None) for a whole-column
    reference with no row bound at all (e.g. 'AM:AM')."""

    columns: Tuple[str, ...]
    row_start: Optional[int]
    row_end: Optional[int]
    next_token_index: int

    def contains(self, row1: int, column_letters: str) -> bool:
        if column_letters not in self.columns:
            return False
        if self.row_start is None or self.row_end is None:
            return True
        return self.row_start <= row1 <= self.row_end


def _read_address_expression(tokens: Tuple[Token, ...], raw: str, i: int) -> Optional[AddressExpression]:
    """Starting at tokens[i], consumes one A1_REFERENCE, optionally followed
    by a ':' A1_REFERENCE range. Returns None if tokens[i] is not an
    A1_REFERENCE at all -- callers use that to mean "not an address here"."""
    if i >= len(tokens) or tokens[i].kind != TokenKind.A1_REFERENCE:
        return None
    col1, row1 = _split_column_and_row(tokens[i].text_in(raw))
    j = i + 1
    col2, row2 = col1, row1
    if (
        j + 1 < len(tokens)
        and tokens[j].kind == TokenKind.PUNCTUATION
        and tokens[j].text_in(raw) == ":"
        and tokens[j + 1].kind == TokenKind.A1_REFERENCE
    ):
        col2, row2 = _split_column_and_row(tokens[j + 1].text_in(raw))
        j += 2
    columns = _columns_between(col1, col2)
    row_start, row_end = row1, row2
    if row_start is not None and row_end is not None and row_start > row_end:
        row_start, row_end = row_end, row_start
    # A range with one bare (row-less) end and one row-bearing end is not a
    # shape this workbook's probe or Stage 1 ever attested; treat it as
    # whole-column (the more permissive reading) rather than guess further.
    if row1 is None or row2 is None:
        row_start = row_end = None
    return AddressExpression(columns=columns, row_start=row_start, row_end=row_end, next_token_index=j)


def _unescape_quoted_sheet_name(token_text: str) -> str:
    """A QUOTED_SHEET_NAME token's own text, e.g. "'Odd '' Name'" (quotes
    included, per tokenizer.py) -> "Odd ' Name"."""
    inner = token_text[1:-1]
    return inner.replace("''", "'")


def _unescape_string_literal(token_text: str) -> str:
    """A STRING_LITERAL token's own text, e.g. '"a ""quote"" here"' (quotes
    included, per tokenizer.py) -> 'a "quote" here'."""
    inner = token_text[1:-1]
    return inner.replace('""', '"')


def sheet_name_from_reference_token(tok: Token, raw: str) -> str:
    """The sheet name a BARE_SHEET_NAME or QUOTED_SHEET_NAME token names,
    unescaped, without the trailing '!'."""
    text = tok.text_in(raw)
    if tok.kind == TokenKind.QUOTED_SHEET_NAME:
        return _unescape_quoted_sheet_name(text)
    return text


# ---------------------------------------------------------------------------
# Recursive string-literal scan: reuses `scan_formula` itself (no new
# regex) against a STRING_LITERAL token's own unescaped interior, to find
# any sheet-name-shaped run inside it. A string's content is not formula
# syntax, but the same character-class rules (identifier run immediately
# followed by '!', or a quoted run immediately followed by '!') are a
# general property of "what looks like a sheet reference", not a rule
# invented for this workbook -- this is why re-running the same scanner is
# the read-the-token-stream move rather than a fresh scan of formula text:
# no new pattern is authored anywhere in this module.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StringLiteralNameOccurrence:
    name: str
    matched_text: str
    string_literal_text: str


def find_sheet_shaped_names_in_string_literal(string_literal_token_text: str) -> Tuple[StringLiteralNameOccurrence, ...]:
    """Every BARE_SHEET_NAME/QUOTED_SHEET_NAME-shaped run found by
    tokenizing a STRING_LITERAL token's own (unescaped) interior as if it
    were itself a formula fragment. Returns one entry per such run, in the
    order found."""
    inner = _unescape_string_literal(string_literal_token_text)
    found = []
    for tok in scan_formula(inner):
        if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
            found.append(
                StringLiteralNameOccurrence(
                    name=sheet_name_from_reference_token(tok, inner),
                    matched_text=tok.text_in(inner),
                    string_literal_text=inner,
                )
            )
    return tuple(found)


# ---------------------------------------------------------------------------
# One-hop resolution (the SECOND addition to the residue rule). Only ever
# follows a single, bare, single-cell sheet-qualified reference used as a
# function argument -- never a range, never a second hop.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OneHopResolution:
    cell: str
    value_at_capture: Any


def one_hop_resolve_bare_cell_argument(
    argument_tokens: Tuple[Token, ...], argument_raw: str, capture: Capture
) -> Optional[OneHopResolution]:
    """If `argument_tokens` is EXACTLY one sheet-qualified reference to a
    single cell (not a range, not a whole column, and nothing else in the
    argument), fetches that cell's value at capture time and returns it.
    Returns None for anything else -- a literal, a range, an expression, or
    a reference to an uncaptured sheet -- rather than guessing.

    This is the only place this module reads beyond the formula that names
    the reference: one hop, per the design's own limit, and never chased
    further even if the target cell is itself another reference.
    """
    tokens = [t for t in argument_tokens if t.kind != TokenKind.WHITESPACE]
    if len(tokens) != 3:
        return None
    sheet_tok, bang_tok, addr_tok = tokens
    if sheet_tok.kind not in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
        return None
    if not (bang_tok.kind == TokenKind.PUNCTUATION and bang_tok.text_in(argument_raw) == "!"):
        return None
    if addr_tok.kind != TokenKind.A1_REFERENCE:
        return None
    sheet_name = sheet_name_from_reference_token(sheet_tok, argument_raw)
    column, row1 = _split_column_and_row(addr_tok.text_in(argument_raw))
    if row1 is None:
        return None  # a bare column, not a single cell -- not one-hop-able
    if sheet_name not in capture.sheet_order:
        return None  # dangling target -- nothing to fetch
    coords = CoordinateModel(capture)
    address = cell_address(row1 - 1, letters_to_col(column))
    value = coords.value_at_address(sheet_name, address)
    return OneHopResolution(cell=f"{sheet_name}!{address}", value_at_capture=value)


# ---------------------------------------------------------------------------
# Paren-matched argument extraction, used only for the opaque-function and
# string-range-carrying residue categories. Walks PUNCTUATION '(' / ')'
# depth over the already-tokenized stream -- not a text scan.
# ---------------------------------------------------------------------------

def _split_call_arguments(tokens: Tuple[Token, ...], raw: str, open_paren_index: int) -> List[Tuple[Token, ...]]:
    """Given the index of the '(' token opening a call, returns each
    top-level, comma-separated argument as its own tuple of tokens (the
    parenthesis tokens themselves excluded), splitting only at comma depth
    zero relative to this call."""
    depth = 0
    args: List[List[Token]] = [[]]
    i = open_paren_index + 1
    while i < len(tokens):
        tok = tokens[i]
        text = tok.text_in(raw)
        if tok.kind == TokenKind.PUNCTUATION and text == "(":
            depth += 1
            args[-1].append(tok)
        elif tok.kind == TokenKind.PUNCTUATION and text == ")":
            if depth == 0:
                break
            depth -= 1
            args[-1].append(tok)
        elif tok.kind == TokenKind.PUNCTUATION and text == "," and depth == 0:
            args.append([])
        else:
            args[-1].append(tok)
        i += 1
    return [tuple(a) for a in args]


def _argument_raw_text(arg_tokens: Tuple[Token, ...], raw: str) -> str:
    if not arg_tokens:
        return ""
    return raw[arg_tokens[0].start:arg_tokens[-1].end]


# ---------------------------------------------------------------------------
# The dependency graph
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphEdge:
    source_sheet: str
    source_column: str
    target_sheet: str
    target_column: str
    patterns: Tuple[str, ...]
    cells: Tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "patterns", tuple(sorted(set(self.patterns))))
        object.__setattr__(self, "cells", tuple(sorted(set(self.cells))))


@dataclass(frozen=True)
class DependencyGraphArtifact(ArtifactBase):
    edges: Tuple[GraphEdge, ...]

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(
            self,
            "edges",
            tuple(sorted(self.edges, key=lambda e: (e.source_sheet, e.source_column, e.target_sheet, e.target_column))),
        )


# ---------------------------------------------------------------------------
# The dangling sheet-name list
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DanglingOccurrence:
    cell: str
    raw_formula: str
    evaluated_value: Any


@dataclass(frozen=True)
class DanglingNameEntry:
    name: str
    classification: str
    occurrences: Tuple[DanglingOccurrence, ...]

    def __post_init__(self):
        if self.classification not in (
            CLASSIFICATION_REFERENCE_POSITION,
            CLASSIFICATION_STRING_LITERAL_POSITION,
            CLASSIFICATION_AMBIGUOUS,
        ):
            raise ValueError(f"unknown classification: {self.classification!r}")
        object.__setattr__(
            self, "occurrences", tuple(sorted(self.occurrences, key=lambda o: o.cell))
        )


@dataclass(frozen=True)
class DanglingNameArtifact(ArtifactBase):
    entries: Tuple[DanglingNameEntry, ...]

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(
            self, "entries", tuple(sorted(self.entries, key=lambda e: (e.name, e.classification)))
        )


# ---------------------------------------------------------------------------
# The accounting invariant
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SheetAccounting:
    sheet_name: str
    non_empty_formulas: int
    matched_formulas: int
    residue_formulas: int

    @property
    def balances(self) -> bool:
        return self.matched_formulas + self.residue_formulas == self.non_empty_formulas


@dataclass(frozen=True)
class Stage2Result:
    capture: Capture
    graph: DependencyGraphArtifact
    dangling: DanglingNameArtifact
    accounting: Tuple[SheetAccounting, ...]

    @property
    def workbook_accounting(self) -> SheetAccounting:
        return SheetAccounting(
            sheet_name="__workbook_total__",
            non_empty_formulas=sum(a.non_empty_formulas for a in self.accounting),
            matched_formulas=sum(a.matched_formulas for a in self.accounting),
            residue_formulas=sum(a.residue_formulas for a in self.accounting),
        )


def _formula_needs_resolution(raw: str, tokens: Tuple[Token, ...]) -> bool:
    """True if this formula's own tokens contain anything reference
    resolution has work to do on: a reference-position sheet name, an
    opaque-argument or string-range-carrying or array-context function
    name, or a STRING_LITERAL holding a sheet-name-shaped run. False means
    this formula contributes to the "matched" side of the accounting
    invariant with nothing further to record -- there was nothing to
    resolve, not something resolved and discarded."""
    for tok in tokens:
        if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
            return True
        if tok.kind == TokenKind.FUNCTION_NAME:
            name = tok.text_in(raw).upper()
            if name in _OPAQUE_ARGUMENT_FUNCTIONS or name in _STRING_RANGE_CARRYING_FUNCTIONS or name in _ARRAY_CONTEXT_FUNCTIONS:
                return True
        if tok.kind == TokenKind.STRING_LITERAL:
            if find_sheet_shaped_names_in_string_literal(tok.text_in(raw)):
                return True
    return False


@dataclass
class _PatternAccumulator:
    pattern_text: str
    instances: List[Tuple[str, int, int, str]] = field(default_factory=list)  # sheet,row0,col0,raw


def run_stage2(formulas_path: str, values_path: str) -> Stage2Result:
    capture = load_capture(formulas_path, values_path)
    coords = CoordinateModel(capture)

    # A single pass: every non-empty formula is tokenized and normalized
    # exactly once. Formulas with nothing for this stage to resolve are
    # tallied and discarded immediately -- only formulas whose tokens
    # contain a reference-shaped construct are kept, grouped by their Gate
    # B pattern, since reference structure is invariant across every
    # instance of one pattern (row-digit rewriting never touches the
    # identifier before '!', and never reclassifies a STRING_LITERAL --
    # the same invariant the Stage 1 follow-up already established).
    per_sheet_matched: Dict[str, int] = {name: 0 for name in capture.sheet_order}
    per_sheet_residue: Dict[str, int] = {name: 0 for name in capture.sheet_order}
    pattern_accumulators: Dict[str, _PatternAccumulator] = {}

    for sheet_name in capture.sheet_order:
        fs = capture.formula_sheet(sheet_name)
        for row0, row in enumerate(fs.formulas):
            for col0, raw in enumerate(row):
                if not is_nonempty(raw):
                    continue
                tokens = scan_formula(raw)
                if not _formula_needs_resolution(raw, tokens):
                    per_sheet_matched[sheet_name] += 1
                    continue
                pattern_text = normalize_pattern(raw, tokens)
                acc = pattern_accumulators.setdefault(pattern_text, _PatternAccumulator(pattern_text))
                acc.instances.append((sheet_name, row0, col0, raw))

    graph_residue: List[ResidueEntry] = []
    dangling_by_key: Dict[Tuple[str, str], List[DanglingOccurrence]] = {}
    edge_accumulator: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    # pattern text -> descriptive lines for every IMPORTRANGE/QUERY call
    # found in that ONE pattern's own formula -- grouped by PATTERN, the
    # same convention every other residue category here uses (one entry,
    # `locations` naming every instance cell), so a pattern repeated down
    # a column produces one entry, not one per cell; and the design's own
    # 4th condition (several calls in one cell recorded together) falls
    # out of this for free when those calls share one formula/pattern.
    importrange_query_by_pattern: Dict[str, List[str]] = {}

    known_sheets = frozenset(capture.sheet_order)

    for pattern_text, acc in pattern_accumulators.items():
        instance_cells = tuple(f"{s}!{cell_address(r, c)}" for s, r, c, _ in acc.instances)
        instance_count = len(acc.instances)
        # Reference STRUCTURE (which sheets/columns are named, in reference
        # or string-literal position; which constructs defeat resolution)
        # is a property of the pattern text, not of any one instance --
        # verified for this exact class of rewrite by the Stage 1
        # whitespace follow-up. One representative instance's tokens are
        # read once, below, for that structure.
        #
        # The SOURCE location is NOT invariant across instances, and must
        # not be read from the representative alone: the identical pattern
        # `=Settings!Y$#` occurs in both Collate!Z30 and Overall!AE2/AE3 in
        # this capture -- same reference structure, three different source
        # cells across two different sheets. `edge_targets` below collects
        # only the resolved (target_sheet, target_columns) pairs; every
        # instance's own (sheet, column) is applied to that list after the
        # walk, in the per-instance loop that follows it.
        rep_sheet, rep_row0, rep_col0, rep_raw = acc.instances[0]
        rep_tokens = scan_formula(rep_raw)

        this_pattern_has_residue = False
        edge_targets: List[Tuple[str, Tuple[str, ...]]] = []

        i = 0
        while i < len(rep_tokens):
            tok = rep_tokens[i]

            if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
                target_sheet = sheet_name_from_reference_token(tok, rep_raw)
                # tok is immediately followed by '!' (tokenizer guarantee)
                addr = _read_address_expression(rep_tokens, rep_raw, i + 2)
                if addr is None:
                    i += 1
                    continue
                if target_sheet in known_sheets:
                    edge_targets.append((target_sheet, addr.columns))
                else:
                    this_pattern_has_residue = True
                    occ_key = (target_sheet, CLASSIFICATION_REFERENCE_POSITION)
                    occs = dangling_by_key.setdefault(occ_key, [])
                    for s, r, c, raw_i in acc.instances:
                        occs.append(
                            DanglingOccurrence(
                                cell=f"{s}!{cell_address(r, c)}",
                                raw_formula=raw_i,
                                evaluated_value=coords.value_at(s, r, c),
                            )
                        )
                    graph_residue.append(
                        ResidueEntry(
                            what=f"sheet-qualified reference to {target_sheet!r}, which matches no captured sheet",
                            locations=instance_cells,
                            defeating_construct="dangling sheet name (reference position)",
                            consequence=(
                                f"no graph edge is drawn for this reference; the {instance_count} "
                                f"instance(s) of this pattern are recorded in the dangling-name "
                                f"artifact instead, classified {CLASSIFICATION_REFERENCE_POSITION!r}"
                            ),
                        )
                    )
                i = addr.next_token_index
                continue

            if tok.kind == TokenKind.STRING_LITERAL:
                found = find_sheet_shaped_names_in_string_literal(tok.text_in(rep_raw))
                for occurrence in found:
                    this_pattern_has_residue = True
                    if occurrence.name not in known_sheets:
                        occ_key = (occurrence.name, CLASSIFICATION_STRING_LITERAL_POSITION)
                        occs = dangling_by_key.setdefault(occ_key, [])
                        for s, r, c, raw_i in acc.instances:
                            occs.append(
                                DanglingOccurrence(
                                    cell=f"{s}!{cell_address(r, c)}",
                                    raw_formula=raw_i,
                                    evaluated_value=coords.value_at(s, r, c),
                                )
                            )
                    graph_residue.append(
                        ResidueEntry(
                            what=(
                                f"text shaped like a sheet reference ({occurrence.matched_text!r}, naming "
                                f"{occurrence.name!r}) found inside a string literal"
                            ),
                            locations=instance_cells,
                            defeating_construct="sheet-name-shaped text in a STRING_LITERAL span",
                            consequence=(
                                "no graph edge is drawn -- this module only draws edges from reference-"
                                "position tokens, never from string-literal content, per this module's own "
                                "standing invariant. The name is not resolved further here: whether "
                                + (
                                    f"a formula anywhere reads it back by address is a separate, one-hop "
                                    f"question this artifact does not answer for you -- check the raw "
                                    f"capture at the cell(s) named above."
                                    if occurrence.name in known_sheets
                                    else "it is a stale name or a name meant for another workbook is not "
                                    "established here"
                                )
                            ),
                        )
                    )
                i += 1
                continue

            if tok.kind == TokenKind.FUNCTION_NAME:
                name = tok.text_in(rep_raw).upper()
                if name in _OPAQUE_ARGUMENT_FUNCTIONS:
                    this_pattern_has_residue = True
                    open_paren = i + 1
                    while open_paren < len(rep_tokens) and rep_tokens[open_paren].kind == TokenKind.WHITESPACE:
                        open_paren += 1
                    args = _split_call_arguments(rep_tokens, rep_raw, open_paren)
                    arg_text = _argument_raw_text(args[0], rep_raw) if args else ""
                    graph_residue.append(
                        ResidueEntry(
                            what=f"{name}({arg_text}) -- the argument names a reference that is computed, not written",
                            locations=instance_cells,
                            defeating_construct=f"{name} argument",
                            consequence=(
                                f"this stage does not evaluate {name}, so any reference {arg_text!r} may "
                                f"resolve to at capture time is not represented in the graph or the "
                                f"dangling-name list. Not resolved here; the deciding input is the "
                                f"argument text itself, {arg_text!r} -- read it directly at the cell(s) named above."
                            ),
                        )
                    )
                elif name in _STRING_RANGE_CARRYING_FUNCTIONS:
                    this_pattern_has_residue = True
                    open_paren = i + 1
                    while open_paren < len(rep_tokens) and rep_tokens[open_paren].kind == TokenKind.WHITESPACE:
                        open_paren += 1
                    args = _split_call_arguments(rep_tokens, rep_raw, open_paren)
                    lines = importrange_query_by_pattern.setdefault(pattern_text, [])
                    for arg_index, arg_tokens in enumerate(args):
                        arg_text = _argument_raw_text(arg_tokens, rep_raw)
                        one_hop = one_hop_resolve_bare_cell_argument(arg_tokens, rep_raw, capture)
                        if one_hop is not None:
                            lines.append(
                                f"{name} argument {arg_index + 1} ({arg_text}) not resolved here -- "
                                f"one hop only: the deciding input is {one_hop.cell}, whose value at "
                                f"capture was {one_hop.value_at_capture!r}"
                            )
                        else:
                            lines.append(
                                f"{name} argument {arg_index + 1} ({arg_text}) not resolved here as a "
                                f"range/reference; read it directly at this cell"
                            )
                elif name in _ARRAY_CONTEXT_FUNCTIONS:
                    this_pattern_has_residue = True
                    graph_residue.append(
                        ResidueEntry(
                            what=f"{name}(...) call present in this pattern",
                            locations=instance_cells,
                            defeating_construct="ARRAYFORMULA span",
                            consequence=(
                                "ordinary reference tokens inside this call are still resolved into edges "
                                "or dangling entries as usual; this entry only flags that the call's own "
                                "result may spill across a row or column range whose extent this stage "
                                "does not assess -- that assessment belongs to the schema artifact (stage 3)"
                            ),
                        )
                    )
                i += 1
                continue

            i += 1

        # Applied per instance, never per pattern: each instance's own
        # sheet is credited in the accounting invariant, and each
        # instance's own (sheet, column) is the source of an edge for
        # every target this pattern's representative resolved above.
        for s, r, c, raw_i in acc.instances:
            if this_pattern_has_residue:
                per_sheet_residue[s] += 1
            else:
                per_sheet_matched[s] += 1
            source_column = col_to_letters(c)
            instance_cell = f"{s}!{cell_address(r, c)}"
            for target_sheet, target_columns in edge_targets:
                for target_column in target_columns:
                    key = (s, source_column, target_sheet, target_column)
                    entry = edge_accumulator.setdefault(key, {"patterns": set(), "cells": set()})
                    entry["patterns"].add(pattern_text)
                    entry["cells"].add(instance_cell)

    # IMPORTRANGE/QUERY residue entries, one per pattern, grouped so a
    # single cell holding several such calls (Seminar!A2, three IMPORTRANGE
    # calls in one formula) is recorded together per the SECOND addition's
    # fourth condition.
    for pattern_text, lines in importrange_query_by_pattern.items():
        acc = pattern_accumulators[pattern_text]
        instance_cells = tuple(f"{s}!{cell_address(r, c)}" for s, r, c, _ in acc.instances)
        graph_residue.append(
            ResidueEntry(
                what=f"{len(lines)} unresolved IMPORTRANGE/QUERY argument(s) in this pattern: " + "; ".join(lines),
                locations=instance_cells,
                defeating_construct="IMPORTRANGE/QUERY string-carried range or computed-source argument",
                consequence=(
                    "the range(s) these calls import are not represented as graph edges; where a one-hop "
                    "source cell is named above, its value at capture time is the deciding input -- follow "
                    "it there, not further"
                ),
            )
        )

    edges = tuple(
        GraphEdge(
            source_sheet=src_sheet,
            source_column=src_col,
            target_sheet=tgt_sheet,
            target_column=tgt_col,
            patterns=tuple(v["patterns"]),
            cells=tuple(v["cells"]),
        )
        for (src_sheet, src_col, tgt_sheet, tgt_col), v in edge_accumulator.items()
    )

    dangling_entries = tuple(
        DanglingNameEntry(name=name, classification=classification, occurrences=tuple(occs))
        for (name, classification), occs in dangling_by_key.items()
    )

    coarse_column_note = (
        "A column-level node is too coarse inside a column holding many distinct patterns -- this "
        "workbook has one column (Collate, column AB) holding 82 distinct patterns. An edge saying "
        "that column depends on another is true of the column and not necessarily of any given cell "
        "in it; this artifact does not, and cannot, resolve that down to individual cells."
    )
    # Generalized staleness note, shared verbatim by both artifacts below --
    # written to hold for any capture of any workbook, never naming a sheet,
    # a cell, or a date. Workbook-specific instances of this condition (which
    # cells, which date) belong in a throwaway script's own report, never
    # here -- see this module's own docstring on why.
    staleness_note = (
        "This artifact describes the workbook as it stood at the captureDate stamped on it, not the "
        "live workbook at the moment this artifact is read. The live workbook may have changed since "
        "that capture was taken -- a sheet, a formula, or the very reference this artifact reports on "
        "may no longer exist, or may exist differently -- and a later capture of the same workbook "
        "legitimately producing different findings is not evidence that this tool has broken. Read the "
        "captureDate before treating any finding, or its absence, as current."
    )
    graph = DependencyGraphArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=(
            "Every edge is drawn only from a reference-position sheet-qualified token whose named "
            "sheet is present in this capture; a dangling target or a string-literal occurrence never "
            "produces an edge, only a residue entry (see this artifact's own residue list) and, where "
            "the name is dangling, an entry in the dangling-name artifact. " + coarse_column_note + " "
            + staleness_note
        ),
        residue=tuple(sorted(graph_residue, key=lambda r: r.locations)),
        edges=edges,
    )

    dangling_classification_note = (
        "Every entry's classification as reference position or string literal position rests entirely "
        "on where Stage 1's tokenizer placed the boundaries of a string literal, never on a heuristic "
        "guess from surrounding punctuation: a name is classified by which of two disjoint token "
        "searches found it, one reading the formula's own reference-position tokens, the other reading "
        "only the interior of a string-literal token the formula's own tokenizer already isolated. That "
        "determination is exact rather than approximate because Stage 1's token tiling covers every "
        "character of a formula exactly once, with no gaps and no overlaps, and the two searches are "
        "applied to spans that cannot overlap either -- there is no third position for either search to "
        "disagree about. The one construct that would defeat this: a formula containing an unterminated "
        "string literal (a stray, unclosed quote) folds everything after it, real formula code included, "
        "into one string-literal token to the end of the formula -- and a reference-shaped name inside "
        "that fold would be classified string literal position confidently and wrongly, with no residue "
        "entry anywhere in either artifact to indicate that the classification rests on a broken quote "
        "rather than a genuine string."
    )
    dangling = DanglingNameArtifact(
        stamp=build_stamp(capture.capture_date),
        reliability_condition=(
            dangling_classification_note + " A name is reported once per (name, classification) pair it "
            "actually occurs in; the same name occurring in both positions across different cells would "
            "produce two entries, not one merged or one dropped. " + staleness_note
        ),
        # This artifact's own residue is empty by construction, not merely
        # empirically: every occurrence this pass finds is classified
        # exactly (reference position or string literal position), never
        # left ambiguous -- see this module's own docstring. A future
        # construct that defeats that classification would populate this
        # tuple rather than being silently folded into one of the two
        # classifications.
        residue=(),
        entries=dangling_entries,
    )

    accounting = tuple(
        SheetAccounting(
            sheet_name=name,
            non_empty_formulas=per_sheet_matched[name] + per_sheet_residue[name],
            matched_formulas=per_sheet_matched[name],
            residue_formulas=per_sheet_residue[name],
        )
        for name in capture.sheet_order
    )

    return Stage2Result(capture=capture, graph=graph, dangling=dangling, accounting=accounting)


# ---------------------------------------------------------------------------
# The consumer check: does any formula anywhere reference a given cell by
# address, whether bare (same-sheet, unqualified) or sheet-qualified. A
# generic, reusable capability -- not workbook-specific in itself, even
# though invoking it with particular target cells is (and belongs in the
# throwaway script, not here).
# ---------------------------------------------------------------------------

def find_formulas_referencing_cells(
    capture: Capture, targets: Tuple[Tuple[str, int, int], ...]
) -> Dict[Tuple[str, int, int], Tuple[str, ...]]:
    """For each (sheet, row0, col0) in `targets`, every "Sheet!Addr" of a
    formula, anywhere in the workbook, whose token stream contains a
    reference (bare, sheet-qualified, or a range) covering that cell. One
    full pass over the capture regardless of how many targets are given.

    A bare (unqualified) A1_REFERENCE is resolved against the FORMULA'S OWN
    sheet -- Google Sheets' own rule for what an unqualified reference
    means. This does not attempt to resolve INDIRECT/OFFSET arguments (see
    run_stage2's residue for why) or any reference computed rather than
    written.
    """
    target_set = frozenset(targets)
    results: Dict[Tuple[str, int, int], List[str]] = {t: [] for t in targets}
    known_sheets = frozenset(capture.sheet_order)

    for sheet_name in capture.sheet_order:
        fs = capture.formula_sheet(sheet_name)
        for row0, row in enumerate(fs.formulas):
            for col0, raw in enumerate(row):
                if not is_nonempty(raw):
                    continue
                tokens = scan_formula(raw)
                i = 0
                while i < len(tokens):
                    tok = tokens[i]
                    if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
                        ref_sheet = sheet_name_from_reference_token(tok, raw)
                        addr = _read_address_expression(tokens, raw, i + 2)
                        if addr is not None and ref_sheet in known_sheets:
                            for t_sheet, t_row0, t_col0 in target_set:
                                if t_sheet == ref_sheet and addr.contains(t_row0 + 1, col_to_letters(t_col0)):
                                    results[(t_sheet, t_row0, t_col0)].append(f"{sheet_name}!{cell_address(row0, col0)}")
                        if addr is not None:
                            i = addr.next_token_index
                            continue
                        i += 1
                        continue
                    if tok.kind == TokenKind.A1_REFERENCE:
                        addr = _read_address_expression(tokens, raw, i)
                        if addr is not None:
                            for t_sheet, t_row0, t_col0 in target_set:
                                if t_sheet == sheet_name and addr.contains(t_row0 + 1, col_to_letters(t_col0)):
                                    results[(t_sheet, t_row0, t_col0)].append(f"{sheet_name}!{cell_address(row0, col0)}")
                            i = addr.next_token_index
                            continue
                    i += 1

    return {k: tuple(sorted(set(v))) for k, v in results.items()}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m sheet_derivation.stage2 <capture_directory>", file=sys.stderr)
        return 2

    capture_dir = argv[0]
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage2(formulas_path, values_path)

    print(f"captureDate: {result.capture.capture_date}")
    print(f"graph edges: {len(result.graph.edges)}")
    print(f"graph residue entries: {len(result.graph.residue)}")
    print(f"dangling-name entries: {len(result.dangling.entries)}")
    wb = result.workbook_accounting
    print(f"accounting: matched {wb.matched_formulas:,} + residue {wb.residue_formulas:,} "
          f"= {wb.matched_formulas + wb.residue_formulas:,} (formulas: {wb.non_empty_formulas:,}, "
          f"balances: {wb.balances})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
