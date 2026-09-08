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
        self.assertEqual(normalize("=$A$1"), "=$A$#")
        self.assertEqual(normalize("=A$1"), "=A$#")
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
