"""Tests for the A1 to R1C1 converter and the comparison (r1c1.py).

Synthetic formulas for the reference forms and the edge cases; a few real
formula texts (with their cell addresses) from the Kankaku V19 capture of
2026-09-26 for the cells the checkup has to get right. Only the texts the
tests need are embedded here, not the capture.
"""

import unittest

from .. import r1c1
from ..r1c1 import (
    ATTESTED_FORMS,
    COL_ABSOLUTE,
    COL_SAME,
    OPEN_ENDED,
    RANGE,
    ROW_OFFSET,
    ROW_SAME,
    SHEET_BARE,
    SHEET_QUOTED,
    SHEET_RANGE,
    STATUS_CONVERTED,
    STATUS_COULD_NOT_COMPARE,
    VERDICT_COULD_NOT_COMPARE,
    VERDICT_DIFFERS,
    VERDICT_PLACEHOLDER,
    VERDICT_SAME,
    WHOLE_COLUMN,
    WHOLE_ROW,
    canonical_for_comparison,
    column_number,
    compare_formulas,
    convert_a1_to_r1c1,
)


def conv(formula, row, col):
    return convert_a1_to_r1c1(formula, row, col)


class ColumnNumberTests(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(column_number("A"), 1)
        self.assertEqual(column_number("z"), 26)
        self.assertEqual(column_number("AA"), 27)
        self.assertEqual(column_number("AL"), 38)
        self.assertEqual(column_number("ZZZ"), 18278)


class ReferenceFormTests(unittest.TestCase):
    """Every reference form named in the stage 2 instructions."""

    def check(self, formula, row, col, expected):
        r = conv(formula, row, col)
        self.assertEqual(r.status, STATUS_CONVERTED, r.reason)
        self.assertEqual(r.text, expected)
        self.assertIsNone(r.reason)
        return r

    def test_single_cell_same_row(self):
        self.check("=A1", 1, 3, "RC[-2]")

    def test_single_cell_other_row_and_column(self):
        self.check("=B2", 5, 5, "R[-3]C[-3]")

    def test_cell_to_the_right_and_below(self):
        self.check("=E9", 1, 2, "R[8]C[3]")

    def test_same_cell_is_rc(self):
        self.check("=C3", 3, 3, "RC")

    def test_fully_absolute(self):
        self.check("=$A$1", 3, 3, "R1C1")

    def test_mixed_absolute_row(self):
        self.check("=A$1", 3, 3, "R1C[-2]")

    def test_mixed_absolute_column(self):
        self.check("=$A1", 3, 3, "R[-2]C1")

    def test_range(self):
        self.check("=SUM(A1:B2)", 1, 3, "SUM(RC[-2]:R[1]C[-1])")

    def test_range_with_absolute_start_row(self):
        # the form attested by Archive's Count column
        self.check("=counta(A$2:A2)", 2, 32, "counta(R2C[-31]:RC[-31])")

    def test_whole_column(self):
        self.check("=SUM(A:A)", 1, 3, "SUM(C[-2]:C[-2])")

    def test_whole_column_absolute(self):
        self.check("=SUM($A:$A)", 1, 3, "SUM(C1:C1)")

    def test_whole_column_two_columns(self):
        self.check("=SUM(A:C)", 1, 4, "SUM(C[-3]:C[-1])")

    def test_whole_row(self):
        self.check("=SUM(2:2)", 5, 5, "SUM(R[-3]:R[-3])")

    def test_whole_row_absolute(self):
        self.check("=SUM($2:$2)", 5, 5, "SUM(R2:R2)")

    def test_whole_rows_span(self):
        self.check("=SUM(2:4)", 1, 1, "SUM(R[1]:R[3])")

    def test_open_ended_range(self):
        self.check("=SUM(A2:A)", 1, 3, "SUM(R[1]C[-2]:C[-2])")

    def test_open_ended_range_absolute_row(self):
        self.check("=SUM(A$2:A)", 1, 3, "SUM(R2C[-2]:C[-2])")

    def test_other_sheet_unquoted_mixed(self):
        # attested: the stored form of Settings!AH$20 in Main data AL
        self.check("=Settings!AH$20", 22, 38, "Settings!R20C[-4]")

    def test_other_sheet_unquoted_with_digit(self):
        self.check("=Sheet2!B3", 3, 2, "Sheet2!RC")

    def test_other_sheet_quoted(self):
        self.check("='Main data'!A1", 2, 2, "'Main data'!R[-1]C[-1]")

    def test_other_sheet_quoted_with_doubled_quote(self):
        self.check("='It''s data'!A1", 1, 2, "'It''s data'!RC[-1]")

    def test_other_sheet_quoted_with_unusual_characters(self):
        self.check("='Q1 (2026) - plan!'!B2", 2, 2, "'Q1 (2026) - plan!'!RC")

    def test_other_sheet_non_ascii_name(self):
        self.check("=雑学!A1", 1, 2, "雑学!RC[-1]")

    def test_other_sheet_range(self):
        self.check("=Sheet2!A1:B2", 1, 1, "Sheet2!RC:R[1]C[1]")

    def test_other_sheet_whole_column(self):
        self.check("=COUNTIF(Vertical!E:E, \">0\")", 2, 20,
                   'COUNTIF(Vertical!C[-15]:C[-15], ">0")')

    def test_range_with_function_as_second_end(self):
        # the shape of Overall column J: Collate!$I2:INDEX(Collate!$I:$I,C2+1)
        self.check("=Collate!$I2:INDEX(Collate!$I:$I,C2+1)", 2, 10,
                   "Collate!RC9:INDEX(Collate!C9:C9,RC[-7]+1)")

    def test_two_functions_joined_by_colon(self):
        self.check("=INDEX(A:A,1):INDEX(A:A,5)", 1, 3,
                   "INDEX(C[-2]:C[-2],1):INDEX(C[-2]:C[-2],5)")

    def test_lowercase_reference(self):
        self.check("=a1+$b$2", 1, 3, "RC[-2]+R2C2")

    def test_many_references_in_one_formula(self):
        self.check("=IF(A1=B1,C$1,$D2)", 1, 5, "IF(RC[-4]=RC[-3],R1C[-2],R[1]C4)")

    def test_two_letter_and_three_letter_columns(self):
        self.check("=AB1+AAA1", 1, 1, "RC[27]+RC[702]")


class StringLiteralTests(unittest.TestCase):
    def test_string_that_looks_like_a_cell_is_untouched(self):
        r = conv('="A1"', 1, 1)
        self.assertEqual(r.text, '"A1"')

    def test_string_with_comma_untouched(self):
        r = conv('=IF(A1="a,b",1,0)', 1, 3)
        self.assertEqual(r.text, 'IF(RC[-2]="a,b",1,0)')

    def test_string_with_escaped_quote_untouched(self):
        r = conv('="say ""A1"" now"&A1', 2, 2)
        self.assertEqual(r.text, '"say ""A1"" now"&R[-1]C[-1]')

    def test_string_with_reference_range_inside_untouched(self):
        r = conv('=COUNTIF(A1:A9,"B2:B3")', 1, 3)
        self.assertEqual(r.text, 'COUNTIF(RC[-2]:R[8]C[-2],"B2:B3")')

    def test_string_with_sheet_reference_inside_untouched(self):
        r = conv('="Settings!AH$20"', 1, 1)
        self.assertEqual(r.text, '"Settings!AH$20"')

    def test_string_with_non_ascii_and_semicolon_untouched(self):
        r = conv('=SPLIT(A1,"の;{")', 1, 2)
        self.assertEqual(r.status, STATUS_CONVERTED)
        self.assertEqual(r.text, 'SPLIT(RC[-1],"の;{")')

    def test_indirect_string_is_text_not_a_reference(self):
        r = conv('=INDIRECT("Collate!$AP2:$AP"&(C2+1))', 2, 10)
        self.assertEqual(r.text, 'INDIRECT("Collate!$AP2:$AP"&(RC[-7]+1))')

    def test_indirect_string_whitespace_inside_is_kept(self):
        r = conv('=INDIRECT( "My  Sheet!A1" )', 1, 1)
        self.assertEqual(r.text, 'INDIRECT( "My  Sheet!A1" )')

    def test_unterminated_string_cannot_be_compared(self):
        r = conv('="abc', 1, 1)
        self.assertEqual(r.status, STATUS_COULD_NOT_COMPARE)
        self.assertIn("unterminated", r.reason)


class FunctionNameAndLiteralTests(unittest.TestCase):
    def test_function_names_with_digits_are_not_cells(self):
        r = conv('=LOG10(A1)+ATAN2(B1,2)+DEC2BIN(C1)+HEX2DEC("FF")', 1, 5)
        self.assertEqual(
            r.text, 'LOG10(RC[-4])+ATAN2(RC[-3],2)+DEC2BIN(RC[-2])+HEX2DEC("FF")')

    def test_function_name_with_space_before_paren(self):
        r = conv("=LOG10 (A1)", 1, 2)
        self.assertEqual(r.text, "LOG10 (RC[-1])")

    def test_numbers_in_exponent_form(self):
        r = conv("=1E5+2.5e-3+.5+1E+2", 1, 1)
        self.assertEqual(r.text, "1E5+2.5e-3+.5+1E+2")

    def test_true_and_false_are_literals(self):
        r = conv("=IF(A1=TRUE,false,True)", 1, 2)
        self.assertEqual(r.status, STATUS_CONVERTED)
        self.assertEqual(r.text, "IF(RC[-1]=TRUE,false,True)")

    def test_error_literal_passes_as_a_literal(self):
        r = conv("=IFERROR(A1,#N/A)", 1, 2)
        self.assertEqual(r.text, "IFERROR(RC[-1],#N/A)")

    def test_operators_and_percent(self):
        r = conv("=A1<=B1&A1<>B1^2%", 1, 3)
        self.assertEqual(r.text, "RC[-2]<=RC[-1]&RC[-2]<>RC[-1]^2%")

    def test_leading_equals_is_stripped_once(self):
        r = conv("==A1", 1, 3)
        # the second '=' is an operator the converter does not own; the
        # text after the first '=' is converted as it stands
        self.assertEqual(r.text, "=RC[-2]")

    def test_whitespace_and_newlines_are_kept_in_converted_text(self):
        r = conv('=IF(A1="",\n  "",\n  B1)', 1, 3)
        self.assertEqual(r.text, 'IF(RC[-2]="",\n  "",\n  RC[-1])')


class CouldNotConvertTests(unittest.TestCase):
    def check(self, formula, fragment, row=1, col=1):
        r = conv(formula, row, col)
        self.assertEqual(r.status, STATUS_COULD_NOT_COMPARE, r.text)
        self.assertIsNone(r.text)
        self.assertIn(fragment, r.reason)
        self.assertEqual(r.by_convention, ())
        return r

    def test_named_range_more_than_three_letters(self):
        self.check("=SUM(TaxRate)", "bare identifier 'TaxRate'")

    def test_named_range_of_three_letters_looks_like_a_column(self):
        self.check("=SUM(tax)", "'tax'")

    def test_named_range_with_underscore(self):
        self.check("=rate_2026*A1", "bare identifier 'rate_2026'")

    def test_identifier_ending_in_digits_beyond_three_letters(self):
        # ABCD1 is not an A1 address (columns stop at ZZZ)
        self.check("=ABCD1", "bare identifier 'ABCD1'")

    def test_function_name_without_parenthesis_is_an_identifier(self):
        self.check("=ATAN2", "bare identifier 'ATAN2'")

    def test_log10_without_parenthesis_is_a_real_cell_address(self):
        # LOG is a valid column (columns run to ZZZ), so LOG10 on its own is
        # a cell; with a parenthesis it is the function (see the tests above)
        r = conv("=LOG10", 1, 1)
        self.assertEqual(r.status, STATUS_CONVERTED)
        self.assertEqual(r.text, "R[9]C[8508]")

    def test_array_literal(self):
        self.check("={1,2;3,4}", "array literal")

    def test_array_literal_with_references(self):
        self.check("={A1,B1}", "array literal")

    def test_array_literal_vertical_stack(self):
        self.check("=SUM({Archive!C2:C9; 'Main data'!C2:C9})", "array literal")

    def test_semicolon_separator(self):
        self.check("=IF(A1;1;2)", "';'")

    def test_unknown_character_curly_quote(self):
        self.check("=IF(A1=“x”,1,2)", "cannot place")

    def test_unclosed_single_quote(self):
        self.check("='Main data!A1", "cannot place")

    def test_quoted_name_without_bang_is_not_a_sheet(self):
        self.check("='abc'+1", "cannot place")

    def test_stray_hash(self):
        self.check("=#foo", "cannot place")

    def test_stray_dollar(self):
        self.check("=$+1", "stray '$'")

    def test_stray_bang(self):
        self.check("=(A1)!B1", "'!'")

    def test_sheet_followed_by_non_reference(self):
        self.check("=Sheet2!foo", "not one end of a range")

    def test_sheet_followed_by_error_literal(self):
        self.check("=Sheet2!#REF!", "expected a cell, column or row reference")

    def test_range_with_second_end_on_another_sheet(self):
        self.check("=Sheet1!A1:Sheet2!B2", "second end carries its own sheet prefix")

    def test_column_to_cell_range(self):
        self.check("=SUM(A:B2)", "range shape col:cell")

    def test_cell_to_row_range(self):
        self.check("=SUM(A1:2)", "range shape cell:row")

    def test_bare_column_without_colon(self):
        self.check("=SUM(A)", "not one end of a range")

    def test_whole_row_without_colon_is_a_number(self):
        # a lone number is a number, not a row reference
        r = conv("=SUM(2)", 1, 1)
        self.assertEqual(r.text, "SUM(2)")

    def test_row_zero(self):
        self.check("=A0", "row number 0")

    def test_whole_row_zero(self):
        self.check("=SUM(0:0)", "row number 0")

    def test_colon_not_in_a_range(self):
        self.check("=IF(A1,1:)", "':'")

    def test_not_a_formula_no_equals(self):
        self.check("A1+1", "does not start with '='")

    def test_not_a_formula_empty(self):
        self.check("", "does not start with '='")

    def test_not_a_formula_only_equals(self):
        self.check("=", "nothing after")

    def test_not_a_formula_whitespace_after_equals(self):
        self.check("=   ", "nothing after")

    def test_none_is_not_a_formula(self):
        r = convert_a1_to_r1c1(None, 1, 1)
        self.assertEqual(r.status, STATUS_COULD_NOT_COMPARE)

    def test_bad_position_raises(self):
        for row, col in ((0, 1), (1, 0), (-1, 1), (1.5, 1), (True, 1), ("1", 1)):
            with self.subTest(row=row, col=col):
                with self.assertRaises(ValueError):
                    convert_a1_to_r1c1("=A1", row, col)
        with self.assertRaises(ValueError):
            compare_formulas("=A1", 0, 1, "RC")

    def test_one_bad_part_fails_the_whole_formula(self):
        # never a partial conversion: the good reference is not returned
        r = conv("=A1+TaxRate", 1, 3)
        self.assertEqual(r.status, STATUS_COULD_NOT_COMPARE)
        self.assertIsNone(r.text)


class SpellingByConventionTests(unittest.TestCase):
    def test_attested_forms_carry_no_flag(self):
        for formula, row, col in (
            ("=A1", 1, 3),                      # RC[-2]
            ("=Settings!AH$20", 22, 38),        # Settings!R20C[-4]
            ("=counta(A$2:A2)", 2, 32),         # R2C[-31]:RC[-31]
            ("=Settings!Y$15", 2, 31),          # Settings!R15C[-6]
        ):
            with self.subTest(formula=formula):
                r = conv(formula, row, col)
                self.assertEqual(r.status, STATUS_CONVERTED)
                self.assertEqual(r.by_convention, ())
                self.assertTrue(r.forms_used)

    def test_forms_used_lists_attested_forms_too(self):
        r = conv("=Settings!AH$20", 22, 38)
        self.assertIn(SHEET_BARE, r.forms_used)

    def test_relative_row_offset_is_by_convention(self):
        self.assertEqual(conv("=B2", 5, 5).by_convention, (ROW_OFFSET,))

    def test_same_column_is_by_convention(self):
        self.assertEqual(conv("=A2", 5, 1).by_convention, (ROW_OFFSET, COL_SAME))

    def test_absolute_column_is_by_convention(self):
        self.assertEqual(conv("=$A$1", 3, 3).by_convention, (COL_ABSOLUTE,))

    def test_whole_column_is_by_convention(self):
        self.assertEqual(conv("=SUM(A:A)", 1, 3).by_convention, (WHOLE_COLUMN,))

    def test_whole_row_is_by_convention(self):
        self.assertEqual(conv("=SUM(2:2)", 2, 3).by_convention, (WHOLE_ROW,))

    def test_open_ended_is_by_convention(self):
        r = conv("=SUM(A$2:A)", 1, 3)
        self.assertEqual(r.by_convention, (OPEN_ENDED,))

    def test_quoted_sheet_is_by_convention(self):
        r = conv("='Main data'!A1", 1, 3)
        self.assertEqual(r.by_convention, (SHEET_QUOTED,))

    def test_sheet_range_is_by_convention(self):
        r = conv("=Sheet2!A1:B1", 1, 3)
        self.assertIn(SHEET_RANGE, r.by_convention)
        self.assertNotIn(RANGE, r.by_convention)  # range itself is attested

    def test_attested_forms_have_evidence_text(self):
        for form, evidence in ATTESTED_FORMS.items():
            self.assertTrue(evidence, form)
        self.assertIn(ROW_SAME, ATTESTED_FORMS)
        self.assertIn(RANGE, ATTESTED_FORMS)


class CanonicalFormTests(unittest.TestCase):
    def test_function_names_lowercased_and_whitespace_dropped(self):
        self.assertEqual(
            canonical_for_comparison('IF( RC[-1] = "A  b" ,  Max(1,2) )'),
            'if(RC[-1]="A  b",max(1,2))')

    def test_string_text_keeps_case_and_whitespace(self):
        self.assertEqual(canonical_for_comparison('"Ab  Cd"'), '"Ab  Cd"')

    def test_quoted_sheet_name_keeps_its_spaces(self):
        self.assertEqual(canonical_for_comparison("'Main data'!RC"), "'Main data'!RC")

    def test_non_function_text_keeps_case(self):
        self.assertEqual(canonical_for_comparison("Settings!R20C[-4]=TRUE"),
                         "Settings!R20C[-4]=TRUE")


class CompareTests(unittest.TestCase):
    def test_same(self):
        r = compare_formulas("=A1+1", 1, 3, "RC[-2]+1")
        self.assertEqual(r.verdict, VERDICT_SAME)
        self.assertEqual(r.converted, "RC[-2]+1")
        self.assertEqual(r.sheet_formula, "=A1+1")
        self.assertEqual(r.stored_formula, "RC[-2]+1")
        self.assertIsNone(r.reason)
        self.assertEqual(r.note, "")

    def test_same_ignoring_function_name_case(self):
        r = compare_formulas("=IFERROR(SPLIT(A1,\",\"),)", 1, 3,
                             'iferror(split(RC[-2],","),)')
        self.assertEqual(r.verdict, VERDICT_SAME)

    def test_same_ignoring_whitespace_outside_strings(self):
        r = compare_formulas('=IF( A1 = "x" ,\n 1 , 2 )', 1, 3, 'if(RC[-2]="x",1,2)')
        self.assertEqual(r.verdict, VERDICT_SAME)

    def test_whitespace_inside_a_string_is_a_difference(self):
        r = compare_formulas('=IF(A1="a b",1,2)', 1, 3, 'IF(RC[-2]="a  b",1,2)')
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_case_inside_a_string_is_a_difference(self):
        r = compare_formulas('=IF(A1="Ab",1,2)', 1, 3, 'IF(RC[-2]="ab",1,2)')
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_whitespace_inside_quoted_sheet_name_is_a_difference(self):
        r = compare_formulas("='Main data'!A1", 1, 3, "'Maindata'!RC[-2]")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_case_of_true_is_not_ignored(self):
        # only the case of function names is ignored, per the approved rule
        r = compare_formulas("=IF(A1=true,1,2)", 1, 3, "IF(RC[-2]=TRUE,1,2)")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_case_of_sheet_name_is_not_ignored(self):
        r = compare_formulas("=settings!A1", 1, 3, "Settings!RC[-2]")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_differs_returns_both_raw_texts_and_converted(self):
        r = compare_formulas("=A1+1", 1, 3, "RC[-2]+2")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)
        self.assertEqual(r.sheet_formula, "=A1+1")
        self.assertEqual(r.stored_formula, "RC[-2]+2")
        self.assertEqual(r.converted, "RC[-2]+1")
        self.assertEqual(r.compared_sheet, "RC[-2]+1")
        self.assertEqual(r.compared_stored, "RC[-2]+2")
        self.assertEqual(r.note, "")  # only attested forms: no spelling caveat

    def test_differs_with_convention_form_says_so(self):
        r = compare_formulas("=B2", 5, 5, "R[-3]C[-2]")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)
        self.assertEqual(r.by_convention, (ROW_OFFSET,))
        self.assertIn("spelling by convention, not attested", r.note)
        self.assertIn("might be one of spelling", r.note)

    def test_same_with_convention_form_says_so(self):
        r = compare_formulas("=B2", 5, 5, "R[-3]C[-3]")
        self.assertEqual(r.verdict, VERDICT_SAME)
        self.assertEqual(r.by_convention, (ROW_OFFSET,))
        self.assertIn("evidence", r.note)

    def test_could_not_compare_keeps_raw_texts_and_reason(self):
        r = compare_formulas("=SUM(TaxRate)", 1, 1, "SUM(TaxRate)")
        self.assertEqual(r.verdict, VERDICT_COULD_NOT_COMPARE)
        self.assertIn("TaxRate", r.reason)
        self.assertEqual(r.sheet_formula, "=SUM(TaxRate)")
        self.assertEqual(r.stored_formula, "SUM(TaxRate)")
        self.assertIsNone(r.converted)
        self.assertIsNone(r.compared_sheet)

    def test_could_not_compare_when_sheet_cell_is_not_a_formula(self):
        r = compare_formulas("", 1, 1, "RC[1]")
        self.assertEqual(r.verdict, VERDICT_COULD_NOT_COMPARE)

    def test_placeholder_exact_text(self):
        r = compare_formulas("=ARRAYFORMULA(A1:A9)", 1, 1, '"COMPUTED_VALUE"')
        self.assertEqual(r.verdict, VERDICT_PLACEHOLDER)
        self.assertIsNone(r.converted)
        self.assertIsNone(r.compared_sheet)
        self.assertEqual(r.sheet_formula, "=ARRAYFORMULA(A1:A9)")
        self.assertEqual(r.stored_formula, '"COMPUTED_VALUE"')

    def test_placeholder_is_recognized_before_converting(self):
        # a sheet text the converter could not handle: still the placeholder verdict
        r = compare_formulas("={1,2;3,4}", 1, 1, '"COMPUTED_VALUE"')
        self.assertEqual(r.verdict, VERDICT_PLACEHOLDER)
        r = compare_formulas("", 1, 1, '"COMPUTED_VALUE"')
        self.assertEqual(r.verdict, VERDICT_PLACEHOLDER)

    def test_placeholder_lookalikes_are_compared_as_formulas(self):
        for stored in ("COMPUTED_VALUE", ' "COMPUTED_VALUE"', '"COMPUTED_VALUE" ',
                       '"computed_value"', "'COMPUTED_VALUE'"):
            with self.subTest(stored=stored):
                r = compare_formulas("=A1", 1, 3, stored)
                self.assertNotEqual(r.verdict, VERDICT_PLACEHOLDER)

    def test_stored_constant_same_as_sheet_constant(self):
        r = compare_formulas("=0.23", 1, 1, "0.23")
        self.assertEqual(r.verdict, VERDICT_SAME)

    def test_stored_constant_differs_from_sheet_formula(self):
        r = compare_formulas("=round(A1/B1,2)", 1, 3, "0.23")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_stored_plain_call_same(self):
        r = compare_formulas("=NOW()", 1, 1, "now()")
        self.assertEqual(r.verdict, VERDICT_SAME)

    def test_stored_plain_call_differs_from_reference(self):
        r = compare_formulas("=Collate!$AH$31", 2, 27, "now()")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_stored_with_leading_equals_is_a_difference(self):
        r = compare_formulas("=A1", 1, 3, "=RC[-2]")
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_indirect_names_are_left_alone_on_both_sides(self):
        r = compare_formulas('=INDIRECT("Collate!$AP2:$AP"&C2)', 2, 10,
                             'indirect("Collate!$AP2:$AP"&RC[-7])')
        self.assertEqual(r.verdict, VERDICT_SAME)
        r = compare_formulas('=INDIRECT("Collate!$AP2:$AP"&C2)', 2, 10,
                             'indirect("Collate!$AP3:$AP"&RC[-7])')
        self.assertEqual(r.verdict, VERDICT_DIFFERS)

    def test_all_four_verdicts_are_distinct_values(self):
        self.assertEqual(
            len({VERDICT_SAME, VERDICT_DIFFERS, VERDICT_COULD_NOT_COMPARE,
                 VERDICT_PLACEHOLDER}), 4)
        self.assertEqual(VERDICT_PLACEHOLDER, "placeholder, not compared")


# ---------------------------------------------------------------------------
# Real formulas: Kankaku V19, capture of 2026-09-26 12:04 JST, with the stored
# formulas of appsheet_columns.csv (spreadsheet_formula). Cell addresses are
# (row, column number); AL = 38, AM = 39, AN = 40, J = 10, T = 20, AA = 27,
# AE = 31, Archive AF = 32.
# ---------------------------------------------------------------------------

MAX_STORED = (
    'max(iferror(split(RC[-25],","),),if(RC[-36]=0,0,RC[-36]+'
    'if(Settings!R20C[-4]=TRUE,max(split(Settings!R20C[-19],",")),'
    'max(split(Settings!R20C[-18],",")))))')
MIN_STORED = 'if(RC[-26]="",RC[-37],min(RC[-37],split(RC[-26],",")))'
FINISHED_STORED = (
    'ifs(RC[-23]<>TRUE,"",RC[-30]="","",COUNTIF(arrayformula(isnumber('
    'match(transpose(arrayformula(trim(split(RC[-30],",")))),'
    'TRANSPOSE(arrayformula(trim(split(Settings!R8C[-21],",")))),0))),'
    'true)=counta(split(RC[-30],",")),"Y",true,"")')

MAX_22 = ('=max(iferror(split(M22,","),),if(B22=0,0,B22+if(Settings!AH$20=TRUE,'
          'max(split(Settings!S$20,",")),max(split(Settings!T$20,",")))))')
MAX_23 = ('=if(A23="","",max(iferror(split(M23,","),),if(B23=0,0,B23+'
          'if(Settings!AH$20=TRUE,max(split(Settings!S$20,",")),'
          'max(split(Settings!T$20,","))))))')
MIN_22 = '=if(M22="",B22,min(B22,split(M22,",")))'
MIN_23 = '=if(A23="","",if(M23="",B23,min(B23,split(M23,","))))'
FINISHED_22 = (
    '=ifs(Q22<>TRUE,"",J22="","",COUNTIF(arrayformula(isnumber(match('
    'transpose(arrayformula(trim(split(J22,",")))),TRANSPOSE(arrayformula('
    'trim(split(Settings!S$8,",")))),0))),true)=counta(split(J22,",")),'
    '"Y",true,"")')
FINISHED_23 = (
    '=if(A23="","",ifs(Q23<>TRUE,"",J23="","",COUNTIF(arrayformula(isnumber('
    'match(transpose(arrayformula(trim(split(J23,",")))),TRANSPOSE('
    'arrayformula(trim(split(Settings!S$8,",")))),0))),true)=counta('
    'split(J23,",")),"Y",true,""))')

OVERALL_DAILY_STORED = (
    'arrayformula(concatenate(trim(unique(indirect(concatenate('
    '"Collate!$AP2:$AP",value(RC[-7]+1))))) & char(10)))')
OVERALL_J2 = ('=iferror(arrayformula(concatenate(trim(unique(Collate!$I2:INDEX('
              'Collate!$I:$I,C2+1))) & char(10))),)')
OVERALL_J3 = ('=iferror(arrayformula(concatenate(trim(unique(Collate!$AU2:INDEX('
              'Collate!$AU:$AU,C3+1))) & char(10))),)')
OVERALL_T2 = '=round((Vertical!Q$2-COUNTIF(Vertical!E:E, ">0"))/Vertical!Q$2,2)'
OVERALL_T3 = '=round((Vertical!Q$4-Collate!AL153)/Vertical!Q$4,2)'

# A stored formula and the sheet's formulas as they stand in the capture.
SEMINAR_A2 = (
    '=iferror(\nif(Settings!AH23=TRUE,importrange(Settings!AC23,'
    '"Vocabulary!A2:Q"),\nimportrange(Collate!AD110,"Vocabulary!A2:Q")),'
    'importrange("https://docs.google.com/spreadsheets/d/EXAMPLE/edit#gid=0",'
    '"Error!A2:L4"))')


class RealDataAgreeTests(unittest.TestCase):
    """Cells where the sheet and the stored formula really agree."""

    def test_kankaku_max_row_22(self):
        r = compare_formulas(MAX_22, 22, 38, MAX_STORED)
        self.assertEqual(r.verdict, VERDICT_SAME)
        self.assertEqual(r.by_convention, ())

    def test_kankaku_min_row_22(self):
        r = compare_formulas(MIN_22, 22, 39, MIN_STORED)
        self.assertEqual(r.verdict, VERDICT_SAME)
        self.assertEqual(r.by_convention, ())

    def test_kankaku_finished_cram_card_row_22(self):
        r = compare_formulas(FINISHED_22, 22, 40, FINISHED_STORED)
        self.assertEqual(r.verdict, VERDICT_SAME)
        self.assertEqual(r.by_convention, ())

    def test_same_formula_other_rows_converts_to_the_same_text(self):
        # relative references are what make rows 22 and 24 one stored formula
        for row in (2, 22, 24, 31):
            with self.subTest(row=row):
                text = MIN_22.replace("22", str(row))
                self.assertEqual(
                    compare_formulas(text, row, 39, MIN_STORED).verdict,
                    VERDICT_SAME)

    def test_archive_count_rows_2_and_3(self):
        stored = "counta(R2C[-31]:RC[-31])"
        self.assertEqual(
            compare_formulas("=counta(A$2:A2)", 2, 32, stored).verdict, VERDICT_SAME)
        self.assertEqual(
            compare_formulas("=counta(A$2:A3)", 3, 32, stored).verdict, VERDICT_SAME)

    def test_overall_end_agrees(self):
        # Overall AE2 and AE3 hold =Settings!Y$15; the stored End formula is
        # Settings!R15C[-6]. They agree, so End is not among the differing
        # Overall columns in this capture.
        for row in (2, 3):
            with self.subTest(row=row):
                r = compare_formulas("=Settings!Y$15", row, 31, "Settings!R15C[-6]")
                self.assertEqual(r.verdict, VERDICT_SAME)


class RealDataDifferTests(unittest.TestCase):
    """The known differing cells."""

    def test_main_data_row_23_al(self):
        r = compare_formulas(MAX_23, 23, 38, MAX_STORED)
        self.assertEqual(r.verdict, VERDICT_DIFFERS)
        self.assertEqual(r.sheet_formula, MAX_23)
        self.assertEqual(r.stored_formula, MAX_STORED)
        # the sheet's row 23 is the stored formula wrapped in if(A23="","",...)
        self.assertEqual(r.converted, 'if(RC[-37]="","",' + MAX_STORED + ")")
        self.assertEqual(r.by_convention, ())
        self.assertEqual(r.note, "")

    def test_main_data_row_23_am(self):
        r = compare_formulas(MIN_23, 23, 39, MIN_STORED)
        self.assertEqual(r.verdict, VERDICT_DIFFERS)
        self.assertEqual(r.converted, 'if(RC[-38]="","",' + MIN_STORED + ")")

    def test_main_data_row_23_an(self):
        r = compare_formulas(FINISHED_23, 23, 40, FINISHED_STORED)
        self.assertEqual(r.verdict, VERDICT_DIFFERS)
        self.assertEqual(r.converted, 'if(RC[-39]="","",' + FINISHED_STORED + ")")

    def test_overall_daily_record_j2_and_j3(self):
        r2 = compare_formulas(OVERALL_J2, 2, 10, OVERALL_DAILY_STORED)
        r3 = compare_formulas(OVERALL_J3, 3, 10, OVERALL_DAILY_STORED)
        self.assertEqual(r2.verdict, VERDICT_DIFFERS)
        self.assertEqual(r3.verdict, VERDICT_DIFFERS)
        self.assertEqual(
            r2.converted,
            'iferror(arrayformula(concatenate(trim(unique(Collate!RC9:INDEX('
            'Collate!C9:C9,RC[-7]+1))) & char(10))),)')
        self.assertEqual(
            r3.converted,
            'iferror(arrayformula(concatenate(trim(unique(Collate!R[-1]C47:'
            'INDEX(Collate!C47:C47,RC[-7]+1))) & char(10))),)')
        # by-convention forms are involved, and the verdict says so
        self.assertIn(WHOLE_COLUMN, r2.by_convention)
        self.assertIn(COL_ABSOLUTE, r2.by_convention)
        self.assertIn("might be one of spelling", r2.note)

    def test_overall_dw_5min_ratio_t2_t3(self):
        r2 = compare_formulas(OVERALL_T2, 2, 20, "0.23")
        r3 = compare_formulas(OVERALL_T3, 3, 20, "0.23")
        self.assertEqual(r2.verdict, VERDICT_DIFFERS)
        self.assertEqual(r3.verdict, VERDICT_DIFFERS)
        self.assertEqual(
            r2.converted,
            'round((Vertical!R2C[-3]-COUNTIF(Vertical!C[-15]:C[-15], ">0"))/'
            'Vertical!R2C[-3],2)')
        self.assertEqual(
            r3.converted,
            'round((Vertical!R4C[-3]-Collate!R[150]C[18])/Vertical!R4C[-3],2)')
        self.assertEqual(r3.stored_formula, "0.23")

    def test_overall_latest_update_aa2_aa3(self):
        r2 = compare_formulas("=Collate!$AH$31", 2, 27, "now()")
        r3 = compare_formulas("=AA2", 3, 27, "now()")
        self.assertEqual(r2.verdict, VERDICT_DIFFERS)
        self.assertEqual(r3.verdict, VERDICT_DIFFERS)
        self.assertEqual(r2.converted, "Collate!R31C34")
        self.assertEqual(r3.converted, "R[-1]C")


class RealDataPlaceholderTests(unittest.TestCase):
    def test_seminar_computed_value(self):
        r = compare_formulas(SEMINAR_A2, 2, 1, '"COMPUTED_VALUE"')
        self.assertEqual(r.verdict, VERDICT_PLACEHOLDER)
        self.assertEqual(r.sheet_formula, SEMINAR_A2)

    def test_seminar_a2_converts_on_its_own(self):
        # the importrange formula itself is convertible; only the verdict is
        # decided by the placeholder rule
        r = convert_a1_to_r1c1(SEMINAR_A2, 2, 1)
        self.assertEqual(r.status, STATUS_CONVERTED)
        self.assertIn('"Vocabulary!A2:Q"', r.text)
        self.assertIn("Settings!R[21]C[33]", r.text)


class ModuleSurfaceTests(unittest.TestCase):
    def test_no_file_access_in_module(self):
        import inspect
        src = inspect.getsource(r1c1)
        for needle in ("open(", "import os", "import json", "import csv",
                       "pathlib", "write("):
            self.assertNotIn(needle, src)


if __name__ == "__main__":
    unittest.main()
