"""Tokenizer tests. No real capture data -- every formula here is
invented, using sheet/function names unlike Kirk's own workbook, per
fixtures.py's convention."""

import unittest

from ..tokenizer import (
    ERROR_LITERALS,
    Token,
    TokenKind,
    assert_tiles,
    is_a1_reference_shape,
    is_bare_a1_column,
    scan_formula,
)


def kinds(tokens):
    return [t.kind for t in tokens]


def texts(formula, tokens):
    return [formula[t.start:t.end] for t in tokens]


class TilingHoldsEverywhere(unittest.TestCase):
    """R2: run the tiling assertion itself over a wide variety of shapes.
    A failure here is a scanner defect, not a workbook hazard."""

    FORMULAS = [
        '=A1',
        '=SUM(A1:B10)',
        '=IF(A1="","",A1)',
        '="hello ""world"""',
        "=Data!A1",
        "='My Sheet'!A1",
        "='It''s Data'!A1",
        '=#REF!',
        '=#N/A',
        '=#VALUE!+1',
        '=#DIV/0!',
        '=#NAME?',
        '=#NUM!',
        '=#NULL!',
        '=1+2.5-3E10*4e-2',
        '=A1<=B1',
        '=A1<>B1',
        '=A1>=B1&"x"',
        '=$A$1+A$1+$A1',
        '=CUSTOM2FUNC(A1)',
        '="text with # inside"',
        '="curly “‘’” quotes"',
        "=IF(A1=\"x's\",1,0)",
        '=SORT(TRANSPOSE(A1:B2))\n',
        '=A1\r\n+B1',
        '=J:J',
        '=$A:A',
        '=A$1:A',
        '',  # not iterated by stage1 (empty), but scanner must not crash
    ]

    def test_every_formula_tiles_exactly(self):
        for formula in self.FORMULAS:
            with self.subTest(formula=formula):
                tokens = scan_formula(formula)
                assert_tiles(formula, tokens)


class StringLiteralTests(unittest.TestCase):
    def test_simple_string_literal(self):
        formula = '="hello"'
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.STRING_LITERAL])
        self.assertEqual(texts(formula, tokens), ["=", '"hello"'])

    def test_doubled_quote_escape_stays_inside_one_token(self):
        formula = '="say ""hi"" now"'
        tokens = scan_formula(formula)
        string_tok = [t for t in tokens if t.kind == TokenKind.STRING_LITERAL][0]
        self.assertEqual(formula[string_tok.start:string_tok.end], '"say ""hi"" now"')

    def test_apostrophe_inside_double_quoted_string_does_not_open_quoted_sheet_name(self):
        # D3's synthetic equivalent: a straight apostrophe inside a "..."
        # string must not be treated as the start of a quoted sheet name.
        formula = '=CONCAT("it\'s fine", A1)'
        tokens = scan_formula(formula)
        self.assertNotIn(TokenKind.QUOTED_SHEET_NAME, kinds(tokens))
        string_tok = [t for t in tokens if t.kind == TokenKind.STRING_LITERAL][0]
        self.assertEqual(formula[string_tok.start:string_tok.end], '"it\'s fine"')

    def test_typographic_quotes_do_not_delimit_anything(self):
        # D4's synthetic equivalent.
        formula = '="“‘’”"'
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.STRING_LITERAL])
        self.assertEqual(formula[tokens[1].start:tokens[1].end], '"“‘’”"')

    def test_hash_inside_string_literal_is_swallowed_not_tokenized_separately(self):
        # R7: '#' occurs literally in real formula text (URL fragments).
        # It must stay inside the STRING_LITERAL span, never become its
        # own token or an ERROR_LITERAL.
        formula = '="https://example.com/x#frag=1"'
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.STRING_LITERAL])

    def test_unterminated_string_literal_is_still_one_token_to_end(self):
        formula = '="never closes'
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.STRING_LITERAL])
        assert_tiles(formula, tokens)


class QuotedSheetNameTests(unittest.TestCase):
    def test_quoted_sheet_name_requires_trailing_bang(self):
        formula = "='My Sheet'!A1"
        tokens = scan_formula(formula)
        self.assertEqual(
            kinds(tokens),
            [
                TokenKind.OPERATOR,
                TokenKind.QUOTED_SHEET_NAME,
                TokenKind.PUNCTUATION,
                TokenKind.A1_REFERENCE,
            ],
        )
        self.assertEqual(texts(formula, tokens)[1], "'My Sheet'")

    def test_doubled_single_quote_escape(self):
        formula = "='It''s Data'!A1"
        tokens = scan_formula(formula)
        quoted = [t for t in tokens if t.kind == TokenKind.QUOTED_SHEET_NAME][0]
        self.assertEqual(formula[quoted.start:quoted.end], "'It''s Data'")

    def test_quote_run_not_followed_by_bang_is_not_a_quoted_sheet_name(self):
        formula = "='not a ref'+1"
        tokens = scan_formula(formula)
        self.assertNotIn(TokenKind.QUOTED_SHEET_NAME, kinds(tokens))
        # Ambiguity splits: the opening quote is its own UNKNOWN token,
        # never merged into anything.
        self.assertEqual(tokens[1].kind, TokenKind.UNKNOWN)
        assert_tiles(formula, tokens)


class BareSheetNameTests(unittest.TestCase):
    def test_bare_sheet_name_before_bang(self):
        formula = "=Data!A1"
        tokens = scan_formula(formula)
        self.assertEqual(
            kinds(tokens),
            [
                TokenKind.OPERATOR,
                TokenKind.BARE_SHEET_NAME,
                TokenKind.PUNCTUATION,
                TokenKind.A1_REFERENCE,
            ],
        )
        self.assertEqual(texts(formula, tokens)[1], "Data")


class DigitInIdentifierTests(unittest.TestCase):
    """R4: a digit preceded by a letter within one identifier run is not
    a row number -- general rule, no function or sheet name hardcoded."""

    def test_function_name_with_embedded_digit_is_not_mangled(self):
        formula = "=CUSTOM2FUNC(A1)"
        tokens = scan_formula(formula)
        func_tok = [t for t in tokens if t.kind == TokenKind.FUNCTION_NAME][0]
        self.assertEqual(formula[func_tok.start:func_tok.end], "CUSTOM2FUNC")

    def test_sheet_name_with_embedded_digit_is_not_mangled(self):
        formula = "=Tab7Data!A1"
        tokens = scan_formula(formula)
        sheet_tok = [t for t in tokens if t.kind == TokenKind.BARE_SHEET_NAME][0]
        self.assertEqual(formula[sheet_tok.start:sheet_tok.end], "Tab7Data")

    def test_pure_a1_shape_row_number_is_still_a_reference(self):
        formula = "=M153"
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.A1_REFERENCE])
        self.assertEqual(texts(formula, tokens)[1], "M153")


class A1ReferenceShapeTests(unittest.TestCase):
    def test_shape_helper_accepts_letters_only_and_letters_plus_digits(self):
        self.assertTrue(is_a1_reference_shape("A"))
        self.assertTrue(is_a1_reference_shape("AB"))
        self.assertTrue(is_a1_reference_shape("ABC"))
        self.assertTrue(is_a1_reference_shape("M153"))
        self.assertFalse(is_a1_reference_shape("ABCD"))  # 4 letters exceeds A1's ceiling
        self.assertFalse(is_a1_reference_shape("HEX2DEC"))  # digit then more letters
        self.assertFalse(is_a1_reference_shape("Tab7Data"))

    def test_bare_column_helper(self):
        self.assertTrue(is_bare_a1_column("J"))
        self.assertTrue(is_bare_a1_column("AB"))
        self.assertFalse(is_bare_a1_column("AB1"))
        self.assertFalse(is_bare_a1_column(""))

    def test_column_only_range_form(self):
        formula = "=J:J"
        tokens = scan_formula(formula)
        self.assertEqual(
            kinds(tokens),
            [TokenKind.OPERATOR, TokenKind.A1_REFERENCE, TokenKind.PUNCTUATION, TokenKind.A1_REFERENCE],
        )

    def test_dollar_both_parts(self):
        formula = "=$A$1"
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.A1_REFERENCE])
        self.assertEqual(texts(formula, tokens)[1], "$A$1")

    def test_dollar_row_only(self):
        formula = "=A$1"
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.A1_REFERENCE])
        self.assertEqual(texts(formula, tokens)[1], "A$1")

    def test_dollar_column_only(self):
        formula = "=$A1"
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.A1_REFERENCE])
        self.assertEqual(texts(formula, tokens)[1], "$A1")

    def test_dollar_bare_column_no_digits(self):
        formula = "=$A:B"
        tokens = scan_formula(formula)
        self.assertEqual(
            kinds(tokens),
            [TokenKind.OPERATOR, TokenKind.A1_REFERENCE, TokenKind.PUNCTUATION, TokenKind.A1_REFERENCE],
        )
        self.assertEqual(texts(formula, tokens)[1], "$A")

    def test_dollar_sign_next_to_non_reference_identifier_is_not_merged(self):
        # $ is never valid next to a plain identifier/function name in
        # Sheets syntax; confirm the merge pass leaves it alone (splits).
        formula = "=$TRUEVALUE"
        tokens = scan_formula(formula)
        self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.PUNCTUATION, TokenKind.IDENTIFIER])
        assert_tiles(formula, tokens)


class ErrorLiteralTests(unittest.TestCase):
    def test_all_seven_error_literals_recognized(self):
        for lit in ["#REF!", "#N/A", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"]:
            with self.subTest(lit=lit):
                formula = f"={lit}"
                tokens = scan_formula(formula)
                self.assertEqual(kinds(tokens), [TokenKind.OPERATOR, TokenKind.ERROR_LITERAL])
                self.assertEqual(texts(formula, tokens)[1], lit)

    def test_bare_hash_not_matching_any_literal_is_unknown(self):
        formula = "=A1#B1"
        tokens = scan_formula(formula)
        self.assertIn(TokenKind.UNKNOWN, kinds(tokens))


class NumberTests(unittest.TestCase):
    def test_integer_decimal_exponent(self):
        formula = "=1+2.5-3E10*4e-2"
        tokens = scan_formula(formula)
        numbers = [formula[t.start:t.end] for t in tokens if t.kind == TokenKind.NUMBER]
        self.assertEqual(numbers, ["1", "2.5", "3E10", "4e-2"])

    def test_number_not_confused_with_reference(self):
        formula = "=B1*300"
        tokens = scan_formula(formula)
        self.assertEqual(
            kinds(tokens),
            [TokenKind.OPERATOR, TokenKind.A1_REFERENCE, TokenKind.OPERATOR, TokenKind.NUMBER],
        )


class WhitespaceAndFunctionTests(unittest.TestCase):
    def test_newline_is_whitespace(self):
        formula = "=SUM(\nA1)"
        tokens = scan_formula(formula)
        ws = [t for t in tokens if t.kind == TokenKind.WHITESPACE]
        self.assertEqual(len(ws), 1)
        self.assertEqual(formula[ws[0].start:ws[0].end], "\n")

    def test_function_name_requires_immediate_paren(self):
        formula = "=FUNC (A1)"  # space before paren
        tokens = scan_formula(formula)
        self.assertNotIn(TokenKind.FUNCTION_NAME, kinds(tokens))
        ident = [t for t in tokens if t.kind == TokenKind.IDENTIFIER][0]
        self.assertEqual(formula[ident.start:ident.end], "FUNC")


class UnknownTokenTests(unittest.TestCase):
    def test_unexpected_character_is_unknown_and_splits(self):
        formula = "=A1~B1"
        tokens = scan_formula(formula)
        unknown = [t for t in tokens if t.kind == TokenKind.UNKNOWN]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(formula[unknown[0].start:unknown[0].end], "~")
        assert_tiles(formula, tokens)


if __name__ == "__main__":
    unittest.main()
