"""Tests for the probe-equivalent verification mode (verify.py). This
mode exists only to build Gate A's comparison pattern set -- it is
deliberately NOT the tool's real normalization, and these tests confirm
it reproduces the probe's own methodology (including the probe's own
blind spots) with only the one attested bug fixed."""

import unittest

from ..normalize import normalize_pattern
from ..tokenizer import scan_formula
from ..verify import normalize_probe_equivalent


class ProbeEquivalentFixesTheAttestedBugTests(unittest.TestCase):
    def test_digit_in_function_name_is_no_longer_mangled(self):
        formula = "=CUSTOM2FUNC(A1)"
        self.assertEqual(normalize_probe_equivalent(formula), "=CUSTOM2FUNC(A#)")

    def test_digit_in_sheet_name_is_no_longer_mangled(self):
        formula = "=Tab7Data!A1"
        self.assertEqual(normalize_probe_equivalent(formula), "=Tab7Data!A#")


class ProbeEquivalentStillNormalizesInsideStringsTests(unittest.TestCase):
    """This is the deliberate difference from the real tool (normalize.py):
    probe-equivalent mode reproduces the probe's blindness to string-
    literal boundaries, which is exactly what Gate B measures the fix
    for."""

    def test_reference_shaped_text_inside_a_string_IS_rewritten(self):
        formula = '="Other!B1"'
        self.assertEqual(normalize_probe_equivalent(formula), '="Other!B#"')

    def test_real_tool_leaves_the_same_text_untouched(self):
        formula = '="Other!B1"'
        real_pattern = normalize_pattern(formula, scan_formula(formula))
        probe_pattern = normalize_probe_equivalent(formula)
        self.assertEqual(real_pattern, formula)  # untouched
        self.assertNotEqual(real_pattern, probe_pattern)  # this is the split


class ProbeEquivalentIsCaseSensitiveLikeTheOriginalRegexTests(unittest.TestCase):
    """The probe's own regex, `(\\$?[A-Z]{1,3})(\\$?)(\\d+)`, matches
    uppercase column letters only. Gate A reproduces that restriction
    faithfully -- a lowercase reference is one of the differences the
    real tool (case-insensitive by design) can introduce, and Gate A3
    requires naming every such difference rather than silently adopting
    the tokenizer's more general behavior as the comparison baseline."""

    def test_lowercase_reference_is_not_rewritten_by_probe_equivalent_mode(self):
        formula = "=if(a1>0,1,0)"
        self.assertEqual(normalize_probe_equivalent(formula), formula)

    def test_real_tool_does_rewrite_the_lowercase_reference(self):
        formula = "=if(a1>0,1,0)"
        real_pattern = normalize_pattern(formula, scan_formula(formula))
        self.assertEqual(real_pattern, "=if(a#>0,1,0)")


if __name__ == "__main__":
    unittest.main()
