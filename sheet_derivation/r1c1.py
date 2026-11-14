"""Formula checkup, stage 2: the A1 to R1C1 converter and the comparison.

AppSheet stores the formula of a spreadsheet-formula column in R1C1
notation without the leading "=" (appsheet_columns.csv, field
spreadsheet_formula). The sheet capture holds each formula in A1
notation WITH the leading "=" (and "" for a cell that is not a formula).
This module converts a sheet formula from A1 to R1C1 relative to the cell
that holds it, and compares the converted text with the stored text.

Everything here is a pure function over strings: no file input or output,
and nothing is written anywhere. Wiring into a stage, keyed-row counting
and the judgment table belong to a later stage.

Reuse of the existing tokenizer (tokenizer.py)
----------------------------------------------
The tokenizer is reused, not duplicated: it already knows string
literals (with the doubled-quote escape), quoted and bare sheet names,
function names (so LOG10( or ATAN2( is never mistaken for a cell), the
digit-inside-identifier rule, numbers in exponent form, and `$` folded
into a reference. What it does not do, and what this module adds on top
of its token stream, is assemble reference tokens into whole references:
a sheet prefix, the two ends of a range, whole columns (A:A), whole rows
(2:2, which the tokenizer sees as NUMBER ':' NUMBER) and open-ended
ranges (A2:A). normalize.py is not used: it rewrites row digits to '#'
for pattern grouping, which is a different job.

Rules (approved by Kirk; see the implementation plan, "Technical Rules")
-----------------------------------------------------------------------
* Convert each sheet formula relative to its own cell; strip the leading
  "=".
* Compare ignoring the case of function names and ignoring whitespace
  OUTSIDE string literals (and outside a quoted sheet name, which is a
  name, not whitespace). Text inside string literals is never altered.
  Both raw texts are always returned.
* Names inside INDIRECT("...") strings are string literals, so they are
  left alone on both sides.
* Anything not recognized is "could not compare", with a reason, never
  guessed at and never passed through silently. That covers bare
  identifiers other than TRUE and FALSE (named ranges and the like),
  array literals and semicolons, a stray '$' or '!', and any character
  the tokenizer cannot place.
* The stored text "COMPUTED_VALUE" (with its double quotes, exactly) is a
  placeholder, not a formula, and is not converted or compared.

Attested versus by convention
-----------------------------
Only some reference spellings are known to be what AppSheet itself
writes, because they occur in stored formulas (ATTESTED_FORMS below, each
with the stored text that attests it). A conversion that uses any other
form follows the standard R1C1 convention and says so in
`by_convention`; a comparison that differs while such a form is involved
says in `note` that the difference might be one of spelling. No AppSheet
spelling is invented.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .tokenizer import Token, TokenKind, scan_formula

STATUS_CONVERTED = "converted"
STATUS_COULD_NOT_COMPARE = "could not compare"

VERDICT_SAME = "same"
VERDICT_DIFFERS = "differs"
VERDICT_COULD_NOT_COMPARE = "could not compare"
VERDICT_PLACEHOLDER = "placeholder, not compared"

# The stored text, with its double quotes, that AppSheet writes for a
# column filled by an array formula. Matched exactly, never trimmed.
PLACEHOLDER_STORED_TEXT = '"COMPUTED_VALUE"'

# ---- reference forms ------------------------------------------------------
# Each tag names one part of how a reference is spelled in R1C1. A
# converted formula carries the set of tags its references used; the tags
# that are not in ATTESTED_FORMS are reported as "by convention".

ROW_SAME = "row same as the formula's own (R)"
ROW_OFFSET = "row relative with a nonzero offset (R[n])"
ROW_ABSOLUTE = "row absolute (Rn)"
COL_SAME = "column same as the formula's own (C)"
COL_OFFSET = "column relative with a nonzero offset (C[n])"
COL_ABSOLUTE = "column absolute (Cn)"
RANGE = "range of two cells (X:Y)"
WHOLE_COLUMN = "whole column (A:A)"
WHOLE_ROW = "whole row (2:2)"
OPEN_ENDED = "open-ended range (A2:A)"
SHEET_BARE = "sheet prefix, unquoted (Name!)"
SHEET_QUOTED = "sheet prefix, quoted ('Name'!)"
SHEET_RANGE = "range with a sheet prefix"

# form -> the stored formula (table | column: text) that attests it, taken
# from appsheet_columns.csv of Kankaku V19 (output/KankakuV19_20260926_120403)
# and of the V18 baseline parse (20260907_111603_...), which agree.
ATTESTED_FORMS = {
    ROW_SAME: "Kankaku | Max: RC[-36]",
    ROW_ABSOLUTE: "Archive | Count: R2C[-31]; Kankaku | Max: Settings!R20C[-4]",
    COL_OFFSET: "Kankaku | Max: RC[-36]",
    RANGE: "Archive | Count: R2C[-31]:RC[-31]",
    SHEET_BARE: "Overall | End: Settings!R15C[-6]",
}

_ALL_FORMS = (
    ROW_SAME, ROW_OFFSET, ROW_ABSOLUTE, COL_SAME, COL_OFFSET, COL_ABSOLUTE,
    RANGE, WHOLE_COLUMN, WHOLE_ROW, OPEN_ENDED, SHEET_BARE, SHEET_QUOTED,
    SHEET_RANGE,
)


def _order(tags) -> Tuple[str, ...]:
    return tuple(t for t in _ALL_FORMS if t in tags)


def unattested(tags) -> Tuple[str, ...]:
    """The tags in `tags` that AppSheet's own stored text does not attest,
    in the fixed order of _ALL_FORMS."""
    return tuple(t for t in _order(tags) if t not in ATTESTED_FORMS)


# ---- result objects --------------------------------------------------------

@dataclass(frozen=True)
class ConversionResult:
    """Outcome of converting one A1 formula.

    status is STATUS_CONVERTED or STATUS_COULD_NOT_COMPARE. `text` is the
    R1C1 text without the leading "=" and is None when the status is
    could-not-compare, in which case `reason` says why. `by_convention`
    lists the reference forms used that AppSheet's stored text does not
    attest (empty when every form used is attested). `forms_used` lists
    all forms used, attested or not.
    """

    source: str
    row: int
    col: int
    status: str
    text: Optional[str]
    reason: Optional[str]
    by_convention: Tuple[str, ...]
    forms_used: Tuple[str, ...]


@dataclass(frozen=True)
class ComparisonResult:
    """Outcome of comparing a sheet formula with a stored formula.

    Both raw texts are always present. `converted` is the converted sheet
    text (None when the verdict is could-not-compare or placeholder).
    `compared_sheet` and `compared_stored` are the canonical texts that
    were actually compared (function names lowercased, whitespace outside
    string literals removed); None when no comparison took place.
    `note` is non-empty when a by-convention form bears on the verdict.
    """

    verdict: str
    sheet_formula: str
    stored_formula: str
    row: int
    col: int
    converted: Optional[str]
    reason: Optional[str]
    by_convention: Tuple[str, ...]
    note: str
    compared_sheet: Optional[str]
    compared_stored: Optional[str]


class _CouldNotConvert(Exception):
    pass


# ---- addresses --------------------------------------------------------------

_ENDPOINT_RE = re.compile(r"^(\$?)([A-Za-z]{1,3})(?:(\$?)([0-9]+))?$")
_DIGITS_RE = re.compile(r"^[0-9]+$")


def column_number(letters: str) -> int:
    """'A' -> 1, 'Z' -> 26, 'AA' -> 27, case-insensitive."""
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _row_part(ref_row: int, absolute: bool, own_row: int, tags: set) -> str:
    if ref_row < 1:
        raise _CouldNotConvert(f"row number {ref_row} is not a valid row")
    if absolute:
        tags.add(ROW_ABSOLUTE)
        return f"R{ref_row}"
    off = ref_row - own_row
    if off == 0:
        tags.add(ROW_SAME)
        return "R"
    tags.add(ROW_OFFSET)
    return f"R[{off}]"


def _col_part(ref_col: int, absolute: bool, own_col: int, tags: set) -> str:
    if absolute:
        tags.add(COL_ABSOLUTE)
        return f"C{ref_col}"
    off = ref_col - own_col
    if off == 0:
        tags.add(COL_SAME)
        return "C"
    tags.add(COL_OFFSET)
    return f"C[{off}]"


class _Endpoint:
    """One end of a reference: a cell (A1), a column (A) or a row (2)."""

    __slots__ = ("kind", "text", "col_abs", "col", "row_abs", "row")

    def __init__(self, kind, text, col_abs=False, col=0, row_abs=False, row=0):
        self.kind = kind  # "cell", "col" or "row"
        self.text = text
        self.col_abs = col_abs
        self.col = col
        self.row_abs = row_abs
        self.row = row

    def convert(self, own_row: int, own_col: int, tags: set) -> str:
        if self.kind == "cell":
            return (_row_part(self.row, self.row_abs, own_row, tags)
                    + _col_part(self.col, self.col_abs, own_col, tags))
        if self.kind == "col":
            return _col_part(self.col, self.col_abs, own_col, tags)
        return _row_part(self.row, self.row_abs, own_row, tags)


# ---- the walk over the token stream ----------------------------------------

class _Walker:
    def __init__(self, body: str, own_row: int, own_col: int):
        self.s = body
        self.tokens: List[Token] = list(scan_formula(body))
        self.n = len(self.tokens)
        self.own_row = own_row
        self.own_col = own_col
        self.pieces: List[str] = []
        self.tags: set = set()
        # What the last non-whitespace thing emitted was: "ref", ")" or
        # something else. Used only to decide whether a stray ':' (as in
        # Sheet!A2:INDEX(...)) is the join between two separate parts.
        self.last_sig = None

    # token helpers
    def text(self, i: int) -> str:
        t = self.tokens[i]
        return self.s[t.start:t.end]

    def kind(self, i: int):
        return self.tokens[i].kind

    def is_punct(self, i: int, ch: str) -> bool:
        return (0 <= i < self.n and self.kind(i) == TokenKind.PUNCTUATION
                and self.text(i) == ch)

    def next_sig(self, i: int) -> int:
        j = i + 1
        while j < self.n and self.kind(j) == TokenKind.WHITESPACE:
            j += 1
        return j

    # endpoints
    def endpoint_at(self, i: int):
        """Parses an endpoint starting at token i. Returns (endpoint, next
        index) or None if the tokens at i do not start one."""
        if i >= self.n:
            return None
        k = self.kind(i)
        if k == TokenKind.A1_REFERENCE:
            text = self.text(i)
            m = _ENDPOINT_RE.match(text)
            if not m:
                raise _CouldNotConvert(
                    f"reference-shaped text {text!r} is not a valid A1 address")
            col_abs = m.group(1) == "$"
            col = column_number(m.group(2))
            if m.group(4) is None:
                return _Endpoint("col", text, col_abs=col_abs, col=col), i + 1
            row = int(m.group(4))
            return _Endpoint("cell", text, col_abs=col_abs, col=col,
                             row_abs=(m.group(3) == "$"), row=row), i + 1
        if k == TokenKind.NUMBER and _DIGITS_RE.match(self.text(i)):
            return _Endpoint("row", self.text(i), row=int(self.text(i))), i + 1
        if (self.is_punct(i, "$") and i + 1 < self.n
                and self.kind(i + 1) == TokenKind.NUMBER
                and _DIGITS_RE.match(self.text(i + 1))):
            return _Endpoint("row", "$" + self.text(i + 1), row_abs=True,
                             row=int(self.text(i + 1))), i + 2
        return None

    def parse_reference(self, i: int, prefix: str, prefix_tag: Optional[str]):
        """Parses a reference (single cell or a range) starting at token
        i, with an optional already-read sheet prefix. Returns the next
        index and appends the converted text."""
        first = self.endpoint_at(i)
        if first is None:
            raise _CouldNotConvert(
                f"expected a cell, column or row reference after {prefix!r}"
                if prefix else "expected a reference")
        e1, j = first
        tags = set()
        if prefix_tag:
            tags.add(prefix_tag)

        # a range: endpoint ':' endpoint, adjacent, no whitespace
        if self.is_punct(j, ":"):
            nxt = j + 1
            if nxt < self.n and self.kind(nxt) in (TokenKind.QUOTED_SHEET_NAME,
                                                   TokenKind.BARE_SHEET_NAME):
                raise _CouldNotConvert(
                    "range whose second end carries its own sheet prefix")
            second = self.endpoint_at(nxt)
            if second is not None:
                e2, k = second
                shape = (e1.kind, e2.kind)
                if shape == ("cell", "cell"):
                    tags.add(RANGE)
                elif shape == ("col", "col"):
                    tags.add(WHOLE_COLUMN)
                elif shape == ("row", "row"):
                    tags.add(WHOLE_ROW)
                elif shape == ("cell", "col"):
                    tags.add(OPEN_ENDED)
                else:
                    raise _CouldNotConvert(
                        f"range shape {e1.kind}:{e2.kind} "
                        f"({e1.text}:{e2.text}) is not one the converter covers")
                if prefix_tag:
                    tags.add(SHEET_RANGE)
                c1 = e1.convert(self.own_row, self.own_col, tags)
                c2 = e2.convert(self.own_row, self.own_col, tags)
                self.pieces.append(prefix + c1 + ":" + c2)
                self.tags |= tags
                self.last_sig = "ref"
                return k
            # ':' followed by something that is not an endpoint (for
            # example INDEX( ): the first end stands alone and the ':'
            # is dealt with by the main loop.

        if e1.kind != "cell":
            raise _CouldNotConvert(
                f"{'column' if e1.kind == 'col' else 'row'} reference "
                f"{e1.text!r} that is not one end of a range "
                f"(a named range, or an incomplete reference)")
        self.pieces.append(prefix + e1.convert(self.own_row, self.own_col, tags))
        self.tags |= tags
        self.last_sig = "ref"
        return j

    def run(self) -> str:
        i = 0
        while i < self.n:
            k = self.kind(i)
            t = self.text(i)

            if k in (TokenKind.QUOTED_SHEET_NAME, TokenKind.BARE_SHEET_NAME):
                if not self.is_punct(i + 1, "!"):
                    raise _CouldNotConvert(f"sheet name {t} without '!'")
                tag = SHEET_QUOTED if k == TokenKind.QUOTED_SHEET_NAME else SHEET_BARE
                i = self.parse_reference(i + 2, t + "!", tag)
                continue

            if k == TokenKind.A1_REFERENCE or k == TokenKind.NUMBER:
                if k == TokenKind.NUMBER and not (
                        self.is_punct(i + 1, ":") and self.endpoint_at(i + 2)):
                    self.pieces.append(t)
                    self.last_sig = "other"
                    i += 1
                    continue
                i = self.parse_reference(i, "", None)
                continue

            if k == TokenKind.PUNCTUATION:
                if t == "$":
                    if self.endpoint_at(i) is not None:
                        i = self.parse_reference(i, "", None)
                        continue
                    raise _CouldNotConvert("stray '$' that is not part of a reference")
                if t in "(),":
                    self.pieces.append(t)
                    self.last_sig = ")" if t == ")" else "other"
                    i += 1
                    continue
                if t == ":":
                    j = self.next_sig(i)
                    ok_prev = self.last_sig in ("ref", ")")
                    ok_next = j < self.n and self.kind(j) in (
                        TokenKind.FUNCTION_NAME, TokenKind.A1_REFERENCE)
                    if ok_prev and ok_next:
                        self.pieces.append(":")
                        self.last_sig = "other"
                        i += 1
                        continue
                    raise _CouldNotConvert(
                        "':' that is not inside a recognized range")
                if t in "{};":
                    raise _CouldNotConvert(
                        f"{t!r}: array literal or locale-dependent separator "
                        "(spelling in R1C1 not attested)")
                if t == "!":
                    raise _CouldNotConvert(
                        "'!' not preceded by a sheet name the tokenizer recognizes")
                raise _CouldNotConvert(f"unrecognized punctuation {t!r}")

            if k == TokenKind.STRING_LITERAL:
                if len(t) < 2 or t.count('"') % 2 == 1:
                    raise _CouldNotConvert("unterminated string literal")
                self.pieces.append(t)
                self.last_sig = "other"
                i += 1
                continue

            if k == TokenKind.IDENTIFIER:
                if t.upper() in ("TRUE", "FALSE"):
                    self.pieces.append(t)
                    self.last_sig = "other"
                    i += 1
                    continue
                raise _CouldNotConvert(
                    f"bare identifier {t!r} (a named range, or a name the "
                    "converter does not recognize)")

            if k == TokenKind.UNKNOWN:
                raise _CouldNotConvert(
                    f"character {t!r} that the tokenizer cannot place")

            if k == TokenKind.WHITESPACE:
                self.pieces.append(t)
                i += 1
                continue

            # FUNCTION_NAME, NUMBER (handled above), ERROR_LITERAL, OPERATOR
            self.pieces.append(t)
            self.last_sig = "other"
            i += 1
        return "".join(self.pieces)


# ---- public functions ------------------------------------------------------

def _check_position(row: int, col: int) -> None:
    for name, v in (("row", row), ("col", col)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError(f"{name} must be an integer >= 1, got {v!r}")


def convert_a1_to_r1c1(formula: str, row: int, col: int) -> ConversionResult:
    """Converts one A1 formula (as the sheet capture holds it, with the
    leading "=") to R1C1 relative to the cell at (row, col), both
    1-based, that holds it. Returns a ConversionResult; never raises on
    formula content (a bad `row` or `col` raises ValueError)."""
    _check_position(row, col)

    def fail(reason: str) -> ConversionResult:
        return ConversionResult(formula, row, col, STATUS_COULD_NOT_COMPARE,
                                None, reason, (), ())

    if not isinstance(formula, str) or not formula.startswith("="):
        return fail("not a formula: the text does not start with '='")
    body = formula[1:]
    if body.strip() == "":
        return fail("not a formula: nothing after '='")
    walker = _Walker(body, row, col)
    try:
        text = walker.run()
    except _CouldNotConvert as exc:
        return fail(str(exc))
    return ConversionResult(
        formula, row, col, STATUS_CONVERTED, text, None,
        unattested(walker.tags), _order(walker.tags))


def canonical_for_comparison(text: str) -> str:
    """The text as compared: function names lowercased, whitespace outside
    string literals (and outside quoted sheet names) removed, everything
    else exactly as written."""
    out = []
    for tok in scan_formula(text):
        piece = text[tok.start:tok.end]
        if tok.kind == TokenKind.WHITESPACE:
            continue
        if tok.kind == TokenKind.FUNCTION_NAME:
            piece = piece.lower()
        out.append(piece)
    return "".join(out)


def compare_formulas(sheet_formula: str, row: int, col: int,
                     stored_formula: str) -> ComparisonResult:
    """Compares a sheet formula (A1, with the leading "=", held in the
    cell at (row, col)) with a stored formula (R1C1, no leading "=").

    Verdicts: "same", "differs", "could not compare" and "placeholder,
    not compared". The placeholder is recognized from the stored text
    alone (exactly '"COMPUTED_VALUE"') and nothing is converted for it.
    Whether a stored text is empty is not decided here: the caller
    decides which cells to compare.
    """
    _check_position(row, col)

    if stored_formula == PLACEHOLDER_STORED_TEXT:
        return ComparisonResult(
            VERDICT_PLACEHOLDER, sheet_formula, stored_formula, row, col,
            None, None, (), "", None, None)

    conv = convert_a1_to_r1c1(sheet_formula, row, col)
    if conv.status != STATUS_CONVERTED:
        return ComparisonResult(
            VERDICT_COULD_NOT_COMPARE, sheet_formula, stored_formula, row, col,
            None, conv.reason, (), "", None, None)

    a = canonical_for_comparison(conv.text)
    b = canonical_for_comparison(stored_formula)
    flags = conv.by_convention
    if a == b:
        note = ""
        if flags:
            note = ("the texts match, which is evidence that AppSheet spells "
                    "these forms this way: " + "; ".join(flags))
        return ComparisonResult(
            VERDICT_SAME, sheet_formula, stored_formula, row, col, conv.text,
            None, flags, note, a, b)
    note = ""
    if flags:
        note = ("differs, but the converted text uses spelling by convention, "
                "not attested in AppSheet's stored text (" + "; ".join(flags)
                + "), so the difference might be one of spelling rather than "
                "of formula")
    return ComparisonResult(
        VERDICT_DIFFERS, sheet_formula, stored_formula, row, col, conv.text,
        None, flags, note, a, b)
