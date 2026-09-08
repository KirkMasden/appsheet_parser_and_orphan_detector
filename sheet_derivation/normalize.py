"""Stage 1: normalization built on the token stream (design section 5,
Stage 1 spec R3-R5).

Two formulas belong to the same pattern when they differ only in row
numbers within A1-style references. The rule is asymmetric on purpose
(design section 5): over-splitting costs a line in the inventory,
over-merging hides a one-off formula inside a crowd with no trace it was
ever there. Everything here is written to split on doubt, never merge.

This is the ONLY normalization path artifact-producing code may use. The
probe-equivalent, string-literal-normalizing comparison mode required for
Gate A lives in verify.py, not here, and nothing in this module imports
it -- see verify.py's docstring for why.
"""

import re
from typing import Tuple

from .tokenizer import Token, TokenKind

_TRAILING_DIGITS_RE = re.compile(r"[0-9]+$")


def _rewrite_trailing_digits(span_text: str) -> str:
    """An A1_REFERENCE token's text, e.g. 'M153', '$AB$153', 'J' (no
    digits -- the digits-omitted column-only form). Replaces the trailing
    digit run with '#' if one exists; a column-only reference has nothing
    to rewrite and is returned unchanged."""
    return _TRAILING_DIGITS_RE.sub("#", span_text, count=1)


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
