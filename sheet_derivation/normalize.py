"""Stage 1: normalization built on the token stream (design section 5,
Stage 1 spec R3-R5).

Two formulas belong to the same pattern when they differ only in RELATIVE
row numbers within A1-style references. The rule is asymmetric on purpose
(design section 5): over-splitting costs a line in the inventory,
over-merging hides a one-off formula inside a crowd with no trace it was
ever there. Everything here is written to split on doubt, never merge.

A row number preceded by '$' is not a relative offset -- it is a fixed
anchor, e.g. the 26 in 'Collate!$AB$26'. Two formulas differing only in
which anchor row they point at are not the same pattern: normalizing an
anchored row away would silently drop one of two genuinely different
constants from the inventory (only one raw instance is kept per pattern),
with nothing in the artifact indicating anything went missing. Whether a
row is anchored is read from the token's own text -- a '$' immediately
before the digit run -- never inferred from context or from a cell's
column.

This is the ONLY normalization path artifact-producing code may use. The
probe-equivalent, string-literal-normalizing comparison mode required for
Gate A lives in verify.py, not here, and nothing in this module imports
it -- see verify.py's docstring for why. verify.py's own regex reproduces
the probe's historical behavior, anchored-row blindness included; it is
not changed by this rule, since Gate A's whole purpose is comparison
against what the probe actually measured, not against what is correct.
"""

import re
from typing import Tuple

from .tokenizer import Token, TokenKind

# An optional '$' immediately before the trailing digit run, captured so
# the replacement can tell the two cases apart -- see _rewrite_trailing_digits.
_TRAILING_DIGITS_RE = re.compile(r"(\$?)([0-9]+)$")


def _rewrite_trailing_digits(span_text: str) -> str:
    """An A1_REFERENCE token's text, e.g. 'M153', '$AB$153', 'AB$153',
    'J' (no digits -- the digits-omitted column-only form). Replaces the
    trailing digit run with '#' UNLESS it is immediately preceded by '$'
    (a fixed anchor, not a relative row offset) -- '$AB$153' and 'AB153'
    are therefore rewritten differently ('$AB$153' unchanged, 'AB153' ->
    'AB#'), because only one of the two digit runs is a relative offset a
    pattern should collapse across. A column-only reference has no digit
    run to rewrite and is returned unchanged either way.

    Written as a single regex with a captured, optional leading '$'
    rather than a lookbehind on the digit run itself: a lookbehind here
    would only block a match from STARTING immediately after a '$', not
    the digit run as a whole, so a greedy `[0-9]+` would back off and
    match a shorter, un-anchored suffix of the same run instead of
    correctly leaving the whole thing alone (checked directly: naively
    written, '$AB$26' would incorrectly become '$AB$2#').
    """
    def _replace(match: "re.Match") -> str:
        return match.group(0) if match.group(1) == "$" else "#"

    return _TRAILING_DIGITS_RE.sub(_replace, span_text, count=1)


def normalize_pattern(formula: str, tokens: Tuple[Token, ...]) -> str:
    """The pattern text: `formula` with the row digits of A1_REFERENCE
    tokens replaced by '#', nothing else altered (R3).

    Every piece appended below is a literal slice of `formula` itself
    (`formula[tok.start:tok.end]`), never a token's "logical" or
    reconstructed value -- R3's ban on re-serializing tokens is about
    exactly this: a canonical token representation could silently differ
    from the source (case, escaping) in a way a raw slice cannot. Because
    R2 guarantees the token spans tile `formula` with no gaps or overlaps,
    concatenating these slices in order reproduces `formula` exactly
    wherever no rewrite was applied -- the only content that ever changes
    is the digit run inside an A1_REFERENCE span, and only there.

    Row numbers inside string literals are NOT normalized (Stage 1's
    explicit decision): a STRING_LITERAL token is never reclassified as
    A1_REFERENCE, so its span is always taken verbatim here, digits and
    all.
    """
    pieces = []
    for tok in tokens:
        span_text = formula[tok.start:tok.end]
        if tok.kind == TokenKind.A1_REFERENCE:
            span_text = _rewrite_trailing_digits(span_text)
        pieces.append(span_text)
    return "".join(pieces)


def renormalize_is_stable(formula: str, tokens: Tuple[Token, ...]) -> bool:
    """Gate C3's check: re-normalizing a stored raw instance reproduces
    its pattern text. Tokenizing the *pattern text itself* (which already
    carries '#' in place of row digits -- '#' is not a letter or digit, so
    it never re-enters an identifier run) and normalizing that a second
    time must yield the same pattern text unchanged."""
    from .tokenizer import scan_formula  # local import: keeps this a pure check

    pattern_text = normalize_pattern(formula, tokens)
    pattern_tokens = scan_formula(pattern_text)
    return normalize_pattern(pattern_text, pattern_tokens) == pattern_text
