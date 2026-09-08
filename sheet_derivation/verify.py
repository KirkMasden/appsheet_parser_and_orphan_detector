"""Stage 1 verification only: the probe-equivalent normalization mode
needed for Gate A's reconciliation, and nothing else.

The probe (260908_capture_probe_report.md) normalized with one global
regex over raw formula text, `(\\$?[A-Z]{1,3})(\\$?)(\\d+)`, applied
everywhere -- inside string literals as much as outside them, since a
plain regex has no notion of "inside a string literal." That is the
attested HEX2DEC( -> HEX#DEC( bug (design section 5): the regex has no
boundary check, so a digit run that continues into more letters (DEC)
still gets swallowed as if it were a row number.

Gate A asks a narrow question: with ONLY that one bug fixed -- add the
identifier-boundary check, change nothing else about the probe's
methodology, including its restriction to uppercase column letters and
its blindness to string-literal boundaries -- does the pattern count and
per-sheet table still reproduce the probe exactly? That is what
`normalize_probe_equivalent` answers. It is deliberately NOT the tool's
real normalization (normalize.py's `normalize_pattern`, which is
token-based and never touches text inside a STRING_LITERAL span at all,
by construction). Reproducing the probe's own string-literal blindness
here is the whole point: Gate B then measures how much of the 382 changes
once that blindness is removed, and Gate D names every pattern the
difference is attributable to.

No artifact-producing code may import this module. Stage 1's real
normalization path (normalize.py) does not import it, and no later stage
should either -- it exists to answer "does Stage 1 reproduce the probe,
modulo the one attested bug," a question with a shelf life bounded by
Gate A itself.
"""

import re

# Mirrors the probe's own regex (`CELL_REF_RE` in 260908_capture_probe.py)
# character for character -- uppercase-only column letters, optional $ on
# either part -- with one addition: a lookbehind/lookahead requiring that
# what is matched is not part of a longer identifier run. That lookaround
# is the "identifier-run fix" Gate A names; everything else is unchanged
# from the probe, deliberately, including its blindness to quotes.
_PROBE_EQUIVALENT_A1_RE = re.compile(
    r"(?<![A-Za-z0-9_])(\$?[A-Z]{1,3}\$?)([0-9]+)(?![A-Za-z0-9_])"
)


def normalize_probe_equivalent(formula: str) -> str:
    """Row-digit rewrite applied globally over raw text, string-literal
    spans included -- the probe's own methodology, with the
    digit-inside-identifier bug fixed and nothing else changed. Used only
    to build Gate A's comparison pattern set; never used to build any
    artifact."""
    return _PROBE_EQUIVALENT_A1_RE.sub(lambda m: m.group(1) + "#", formula)
