"""Stage 1: the token scanner (design doc, requirements R1-R2).

One scanner that classifies every region of formula text by type. Today
(per the probe) normalization and reference detection are independent
regex passes that can each be fooled by the other's blind spot -- the
HEX2DEC( -> HEX#DEC( mangling and the string-literal false-positive on
cross-sheet references are the same missing thing: nothing knows which
region of the text it is looking at. This module is that knowledge.

Nothing here may name a sheet (design section 3.2, Stage 1 spec R4): the
digit-inside-identifier rule and the A1-reference shape test are both
general rules about A1 notation and Google Sheets formula syntax, not
rules keyed to any function name or sheet name found in one workbook.

Span tiling (R2) holds by construction, not by luck: the scanner is a
single left-to-right pass that starts at the end of the previous token and
advances by at least one character every iteration, so at any point the
tokens built so far reproduce formula[:i] byte for byte when concatenated
in order. `assert_tiles` re-checks that invariant explicitly, since a
requirement this load-bearing (Stage 1's own R2) deserves a check that
runs over the real capture, not just trust in the construction.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class TokenKind(Enum):
    STRING_LITERAL = "STRING_LITERAL"
    QUOTED_SHEET_NAME = "QUOTED_SHEET_NAME"
    BARE_SHEET_NAME = "BARE_SHEET_NAME"
    A1_REFERENCE = "A1_REFERENCE"
    IDENTIFIER = "IDENTIFIER"
    FUNCTION_NAME = "FUNCTION_NAME"
    NUMBER = "NUMBER"
    ERROR_LITERAL = "ERROR_LITERAL"
    OPERATOR = "OPERATOR"
    PUNCTUATION = "PUNCTUATION"
    WHITESPACE = "WHITESPACE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Token:
    """A span into the ORIGINAL formula string, not a copy of its text.

    Deliberately carries no `text` field. Every consumer that needs the
    token's text slices `formula[tok.start:tok.end]` from the same string
    the token was built from -- this is what R3 means by "operates on
    spans over the original string, never by re-serializing tokens": there
    is no token-owned string that could drift from the source.
    """

    kind: TokenKind
    start: int
    end: int

    def text_in(self, formula: str) -> str:
        return formula[self.start:self.end]


# Closed vocabulary (R1). Order doesn't matter for correctness here -- none
# of these seven literals is a prefix of another once the leading '#N'
# pair (#N/A, #NAME?, #NULL!) is checked in full, but longest-first is
# kept anyway as the defensive default.
ERROR_LITERALS: Tuple[str, ...] = tuple(sorted(
    ["#REF!", "#N/A", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"],
    key=len, reverse=True,
))

_WHITESPACE_CHARS = " \t\r\n\v\f"
_MULTI_CHAR_OPERATORS = ("<=", ">=", "<>")
_SINGLE_CHAR_OPERATORS = set("+-*/^&=<>%")
_SINGLE_CHAR_PUNCTUATION = set("(),:;{}!$")

# The A1-reference "shape": 1-3 letters (Google Sheets' own column-address
# ceiling -- ZZZ, 18,278 columns -- not a fact about any one workbook),
# optionally followed by a digit run. This is a property of A1 notation,
# not of Kirk's workbook; using it is not the section-3.2 hazard.
_A1_SHAPE_RE = re.compile(r"^[A-Za-z]{1,3}([0-9]+)?$")
_BARE_COLUMN_RE = re.compile(r"^[A-Za-z]{1,3}$")
_TRAILING_DIGITS_RE = re.compile(r"[0-9]+$")


def is_a1_reference_shape(run_text: str) -> bool:
    """True if `run_text` (an identifier run, no $ signs) is a bare A1
    reference shape: 1-3 letters, then an optional digit run, and nothing
    else. This is what R4 requires generally: a digit preceded by a
    letter *within one identifier run* is not a row number *unless* the
    whole run is exactly this shape -- HEX2DEC fails it (letters-digits-
    letters), and so would any digit-suffixed sheet name with more than
    three letters in its stem; M153 and AH23 pass it.
    """
    return bool(_A1_SHAPE_RE.match(run_text))


def is_bare_a1_column(run_text: str) -> bool:
    """True if `run_text` is a column-only A1 shape (no digits) -- the
    'digits-omitted' form named in R1, e.g. the J in J:J."""
    return bool(_BARE_COLUMN_RE.match(run_text))


def _scan_string_literal(s: str, i: int, n: int) -> int:
    """s[i] == '"'. Returns the end offset of the string literal token
    (one past the closing, unescaped '"'), or n if the string runs
    unterminated to the end of the formula -- that is still exactly one
    token; a formula this tool did not write is not something it may
    invent a closing quote for."""
    j = i + 1
    while j < n:
        if s[j] == '"':
            if j + 1 < n and s[j + 1] == '"':
                j += 2
                continue
            return j + 1
        j += 1
    return n


def _scan_quote_run(s: str, i: int, n: int):
    """s[i] == "'". Scans a '...'-delimited run with '' as the escape,
    same shape as a string literal. Returns (end_offset, closed) where
    `closed` is False if the formula ran out before an unescaped closing
    quote was found -- in that case the run is not a candidate quoted
    sheet name at all (R5: ambiguity splits, it does not merge)."""
    j = i + 1
    while j < n:
        if s[j] == "'":
            if j + 1 < n and s[j + 1] == "'":
                j += 2
                continue
            return j + 1, True
        j += 1
    return n, False


def _scan_number(s: str, i: int, n: int) -> int:
    """s[i] is a digit, or '.' followed by a digit. Consumes an integer
    or decimal literal with an optional e/E exponent."""
    j = i
    while j < n and s[j].isdigit():
        j += 1
    if j < n and s[j] == "." and j + 1 < n and s[j + 1].isdigit():
        j += 1
        while j < n and s[j].isdigit():
            j += 1
    if j < n and s[j] in "eE":
        k = j + 1
        if k < n and s[k] in "+-":
            k += 1
        if k < n and s[k].isdigit():
            j = k
            while j < n and s[j].isdigit():
                j += 1
    return j


def _scan_identifier_run(s: str, i: int, n: int) -> int:
    """s[i] is a letter or underscore. Consumes the maximal run of
    letters, digits and underscore -- R1's identifier-run definition,
    verbatim: 'not preceded or followed by an identifier character.'"""
    j = i + 1
    while j < n and (s[j].isalnum() or s[j] == "_"):
        j += 1
    return j


def _classify_identifier_run(run_text: str, s: str, end: int, n: int) -> TokenKind:
    # FUNCTION_NAME tolerates whitespace (including newlines) between the
    # identifier and '(' -- Google Sheets accepts "YEAR (x)" as a call,
    # the same as "YEAR(x)". The lookahead below never moves `end`, so
    # the token this run becomes is still just the identifier itself;
    # any intervening whitespace is picked up as its own WHITESPACE
    # token on the next iteration of the main scan loop, and R2 tiling
    # is unaffected. No function name is special-cased.
    lookahead = end
    while lookahead < n and s[lookahead] in _WHITESPACE_CHARS:
        lookahead += 1
    if lookahead < n and s[lookahead] == "(":
        return TokenKind.FUNCTION_NAME
    if end < n and s[end] == "!":
        return TokenKind.BARE_SHEET_NAME
    if is_a1_reference_shape(run_text):
        return TokenKind.A1_REFERENCE
    return TokenKind.IDENTIFIER


def _tokenize_raw(s: str) -> list:
    """First pass: every character accounted for, $ signs left as their
    own PUNCTUATION tokens. The second pass (`_merge_dollar_signs`) folds
    a $ into an adjacent A1_REFERENCE where the combined shape is a real
    A1 address; this pass never itself builds a token containing '$',
    which keeps its per-position dispatch simple and auditable."""
    n = len(s)
    i = 0
    tokens = []
    while i < n:
        ch = s[i]

        if ch == '"':
            end = _scan_string_literal(s, i, n)
            tokens.append(Token(TokenKind.STRING_LITERAL, i, end))
            i = end
            continue

        if ch == "'":
            end, closed = _scan_quote_run(s, i, n)
            if closed and end < n and s[end] == "!":
                tokens.append(Token(TokenKind.QUOTED_SHEET_NAME, i, end))
                i = end
                continue
            tokens.append(Token(TokenKind.UNKNOWN, i, i + 1))
            i += 1
            continue

        if ch == "#":
            matched = None
            for lit in ERROR_LITERALS:
                if s.startswith(lit, i):
                    matched = lit
                    break
            if matched:
                tokens.append(Token(TokenKind.ERROR_LITERAL, i, i + len(matched)))
                i += len(matched)
            else:
                tokens.append(Token(TokenKind.UNKNOWN, i, i + 1))
                i += 1
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and s[i + 1].isdigit()):
            end = _scan_number(s, i, n)
            tokens.append(Token(TokenKind.NUMBER, i, end))
            i = end
            continue

        if ch.isalpha() or ch == "_":
            end = _scan_identifier_run(s, i, n)
            run_text = s[i:end]
            kind = _classify_identifier_run(run_text, s, end, n)
            tokens.append(Token(kind, i, end))
            i = end
            continue

        if ch in _WHITESPACE_CHARS:
            j = i + 1
            while j < n and s[j] in _WHITESPACE_CHARS:
                j += 1
            tokens.append(Token(TokenKind.WHITESPACE, i, j))
            i = j
            continue

        if s.startswith(("<=", ">=", "<>"), i):
            matched_op = next(op for op in _MULTI_CHAR_OPERATORS if s.startswith(op, i))
            tokens.append(Token(TokenKind.OPERATOR, i, i + len(matched_op)))
            i += len(matched_op)
            continue

        if ch in _SINGLE_CHAR_OPERATORS:
            tokens.append(Token(TokenKind.OPERATOR, i, i + 1))
            i += 1
            continue

        if ch == "$":
            tokens.append(Token(TokenKind.PUNCTUATION, i, i + 1))
            i += 1
            continue

        if ch in _SINGLE_CHAR_PUNCTUATION:
            tokens.append(Token(TokenKind.PUNCTUATION, i, i + 1))
            i += 1
            continue

        # Anything else (typographic quotes, stray symbols, unexpected
        # unicode) is one character the scanner could not classify.
        # Splitting to a single char, never merging, is R5's rule applied
        # to the scanner's own blind spots.
        tokens.append(Token(TokenKind.UNKNOWN, i, i + 1))
        i += 1

    return tokens


def _merge_dollar_signs(s: str, tokens: list) -> list:
    """Second pass: folds a PUNCTUATION '$' into a neighbouring
    A1_REFERENCE token wherever the combined text is still a valid A1
    shape with $ on one or both parts ($AB153, AB$153, $AB$153, $AB, A$).
    Only ever touches tokens already classified A1_REFERENCE by the first
    pass -- a '$' next to an IDENTIFIER, FUNCTION_NAME or anything else is
    left as its own PUNCTUATION token, per R5."""
    merged = []
    i = 0
    n = len(tokens)

    def is_dollar_punct(tok):
        return tok.kind == TokenKind.PUNCTUATION and s[tok.start:tok.end] == "$"

    while i < n:
        tok = tokens[i]

        if is_dollar_punct(tok) and i + 1 < n and tokens[i + 1].kind == TokenKind.A1_REFERENCE:
            ref = tokens[i + 1]
            end = ref.end
            consumed = 2
            ref_text = s[ref.start:ref.end]
            if (
                is_bare_a1_column(ref_text)
                and i + 3 < n
                and is_dollar_punct(tokens[i + 2])
                and tokens[i + 3].kind == TokenKind.NUMBER
            ):
                end = tokens[i + 3].end
                consumed = 4
            merged.append(Token(TokenKind.A1_REFERENCE, tok.start, end))
            i += consumed
            continue

        if (
            tok.kind == TokenKind.A1_REFERENCE
            and is_bare_a1_column(s[tok.start:tok.end])
            and i + 2 < n
            and is_dollar_punct(tokens[i + 1])
            and tokens[i + 2].kind == TokenKind.NUMBER
        ):
            merged.append(Token(TokenKind.A1_REFERENCE, tok.start, tokens[i + 2].end))
            i += 3
            continue

        merged.append(tok)
        i += 1

    return merged


def scan_formula(formula: str) -> Tuple[Token, ...]:
    """Tokenizes one formula's raw text. Returns tokens in order, tiling
    `formula` exactly (R2) -- see `assert_tiles` for the explicit check
    run over the whole capture."""
    raw = _tokenize_raw(formula)
    merged = _merge_dollar_signs(formula, raw)
    return tuple(merged)


def assert_tiles(formula: str, tokens: Tuple[Token, ...]) -> None:
    """R2's structural check: no gaps, no overlaps, and concatenating the
    token spans in order reproduces `formula` byte for byte. Raises
    AssertionError naming exactly where tiling failed, rather than a bare
    True/False -- a failure here is Stage 1's own defect, not a workbook
    hazard, and needs a precise location to fix."""
    pos = 0
    for idx, tok in enumerate(tokens):
        if tok.start != pos:
            raise AssertionError(
                f"tiling gap/overlap at token {idx} ({tok.kind}): expected start "
                f"{pos}, got {tok.start}, in formula {formula!r}"
            )
        if tok.end <= tok.start:
            raise AssertionError(
                f"token {idx} ({tok.kind}) has non-positive length "
                f"[{tok.start}:{tok.end}] in formula {formula!r}"
            )
        pos = tok.end
    if pos != len(formula):
        raise AssertionError(
            f"tiling does not reach the end of the formula: tokens cover up to "
            f"{pos}, formula length is {len(formula)}, formula {formula!r}"
        )
    rebuilt = "".join(formula[t.start:t.end] for t in tokens)
    if rebuilt != formula:
        raise AssertionError(
            f"concatenated token spans do not reproduce the formula byte for "
            f"byte:\n  rebuilt: {rebuilt!r}\n  original: {formula!r}"
        )
