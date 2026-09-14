"""Normalization tests (design section 5, Stage 1 spec R3-R5). No real
capture data -- synthetic formulas only, per fixtures.py's convention."""

import unittest

from ..normalize import normalize_pattern, renormalize_is_stable
from ..tokenizer import scan_formula


def normalize(formula):
    return normalize_pattern(formula, scan_formula(formula))


class RowDigitRewriteTests(unittest.TestCase):
    def test_row_number_is_rewritten(self):
        self.assertEqual(normalize("=A1"), "=A#")

    def test_dollar_signs_preserved(self):
        # A '$' immediately before the row digit means the row is a fixed
        # anchor, not a relative offset -- see AnchoredRowNotNormalizedTests
        # below for why that digit is therefore NOT rewritten. Only the
        # column-anchored-alone case ($A1: column fixed, row still
        # relative) has a row digit left to rewrite.
        self.assertEqual(normalize("=$A$1"), "=$A$1")
        self.assertEqual(normalize("=A$1"), "=A$1")
        self.assertEqual(normalize("=$A1"), "=$A#")

    def test_column_only_reference_has_nothing_to_rewrite(self):
        self.assertEqual(normalize("=J:J"), "=J:J")

    def test_case_is_never_altered(self):
        self.assertEqual(normalize("=if(a1>0,1,0)"), "=if(a#>0,1,0)")
        self.assertEqual(normalize("=IF(A1>0,1,0)"), "=IF(A#>0,1,0)")

    def test_whitespace_is_never_altered(self):
        formula = "=SUM(\n  A1 ,  B2 )"
        self.assertEqual(normalize(formula), "=SUM(\n  A# ,  B# )")


class DigitInIdentifierNormalizationTests(unittest.TestCase):
    """The attested HEX2DEC-shaped bug, reproduced with an invented
    function/sheet name so no real workbook fact appears in this file."""

    def test_function_name_with_digit_is_never_mangled(self):
        formula = "=CUSTOM2FUNC(A1)"
        self.assertEqual(normalize(formula), "=CUSTOM2FUNC(A#)")

    def test_sheet_name_with_digit_is_never_mangled(self):
        formula = "=Tab7Data!A1"
        self.assertEqual(normalize(formula), "=Tab7Data!A#")


class AnchoredRowNotNormalizedTests(unittest.TestCase):
    """A '$' immediately before a row digit marks a fixed anchor, not a
    relative offset -- the digit-inside-identifier fix and the
    string-literal exclusion are both about NOT rewriting something that
    isn't a relative row number either; this is the third such case, and
    the one the defect fixed here got wrong (a $-anchored row digit was
    being rewritten to '#' exactly like a relative one, so two formulas
    pointing at two different fixed rows collapsed into one pattern with
    only one of the two constants surviving into the inventory)."""

    def test_fully_anchored_reference_is_left_completely_untouched(self):
        self.assertEqual(normalize("=Sheet1!$AB$26"), "=Sheet1!$AB$26")

    def test_row_anchored_only_reference_is_left_untouched(self):
        # Column not anchored, row anchored: the row digit is still a
        # fixed anchor and must not be rewritten.
        self.assertEqual(normalize("=AB$26"), "=AB$26")

    def test_column_anchored_only_reference_still_has_its_row_rewritten(self):
        # Column anchored, row NOT anchored ('$AB26', not '$AB$26'): the
        # row is still a relative offset and must be rewritten as usual.
        self.assertEqual(normalize("=$AB26"), "=$AB#")

    def test_two_formulas_differing_only_in_anchor_row_are_different_patterns(self):
        # The worked case this fix exists for: two formulas identical
        # except for which fixed row they anchor to must NOT collapse
        # into one pattern -- the two anchors are different constants,
        # not the same relative offset seen twice.
        formula_a = "=if(and(M1>Sheet1!$AB$26,C1<=300),1,0)"
        formula_b = "=if(and(M1>Sheet1!$AB$21,C1<=300),1,0)"
        pattern_a = normalize(formula_a)
        pattern_b = normalize(formula_b)
        self.assertNotEqual(pattern_a, pattern_b)
        self.assertEqual(pattern_a, "=if(and(M#>Sheet1!$AB$26,C#<=300),1,0)")
        self.assertEqual(pattern_b, "=if(and(M#>Sheet1!$AB$21,C#<=300),1,0)")

    def test_relative_reference_anchor_and_absolute_range_together(self):
        # A mix in one formula: a relative reference, a row-anchored
        # single cell, and a fully-anchored range -- only the relative
        # reference's row digit is rewritten.
        formula = "=SUMIFS(A2:A10,Sheet1!B$5,$C$1:$C$100)"
        self.assertEqual(normalize(formula), "=SUMIFS(A#:A#,Sheet1!B$5,$C$1:$C$100)")


class StringLiteralsNotNormalizedTests(unittest.TestCase):
    """The explicit Stage 1 decision: row numbers inside string literals
    are left untouched, since they were never a cell reference."""

    def test_reference_shaped_text_inside_a_string_is_untouched(self):
        formula = '="Data!A1"'
        self.assertEqual(normalize(formula), formula)

    def test_mixed_real_reference_and_string_literal_reference_shape(self):
        formula = '=IF(A1="Data!A1",A1,"")'
        # The real A1 in reference position is rewritten; the identical
        # text inside the string literal is not.
        self.assertEqual(normalize(formula), '=IF(A#="Data!A1",A#,"")')


class NoTruncationTests(unittest.TestCase):
    def test_long_formula_is_never_truncated(self):
        long_string_content = "x" * 3000
        formula = f'=CONCATENATE("{long_string_content}",A1)'
        result = normalize(formula)
        self.assertEqual(len(result), len(formula))
        self.assertIn(long_string_content, result)
        self.assertTrue(result.endswith("A#)"))


class RenormalizationStabilityTests(unittest.TestCase):
    """Gate C3: re-normalizing any stored raw instance reproduces its
    pattern text."""

    FORMULAS = [
        "=A1",
        "=$A$1+A$1+$A1",
        "=CUSTOM2FUNC(A1)",
        '="Data!A1"',
        "=J:J",
        "='My Sheet'!A1",
        '=IF(A1="Data!A1",A1,"")',
        "=#REF!",
    ]

    def test_stability_holds_for_a_variety_of_shapes(self):
        for formula in self.FORMULAS:
            with self.subTest(formula=formula):
                self.assertTrue(renormalize_is_stable(formula, scan_formula(formula)))


if __name__ == "__main__":
    unittest.main()
