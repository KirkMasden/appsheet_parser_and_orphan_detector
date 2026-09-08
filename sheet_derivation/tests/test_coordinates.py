import tempfile
import unittest

from ..coordinates import CoordinateModel, cell_address, col_to_letters, letters_to_col, parse_cell_address
from ..loader import load_capture
from .fixtures import build_good_pair, write_pair


class TestColumnLetterConversion(unittest.TestCase):
    def test_single_letter_columns(self):
        self.assertEqual(col_to_letters(0), "A")
        self.assertEqual(col_to_letters(25), "Z")

    def test_two_letter_columns(self):
        self.assertEqual(col_to_letters(26), "AA")
        self.assertEqual(col_to_letters(48), "AW")  # the real capture's widest column
        self.assertEqual(col_to_letters(51), "AZ")
        self.assertEqual(col_to_letters(52), "BA")

    def test_three_letter_columns(self):
        # Not attested in the real capture, but the design requires the
        # conversion to handle it -- generality, not a special case.
        self.assertEqual(col_to_letters(701), "ZZ")
        self.assertEqual(col_to_letters(702), "AAA")

    def test_round_trip_across_a_wide_range(self):
        for col0 in list(range(0, 60)) + [701, 702, 703, 1000]:
            letters = col_to_letters(col0)
            self.assertEqual(letters_to_col(letters), col0, msg=f"round trip failed for column {col0}")

    def test_letters_to_col_is_case_insensitive(self):
        self.assertEqual(letters_to_col("aw"), letters_to_col("AW"))

    def test_invalid_column_letters_raise(self):
        with self.assertRaises(ValueError):
            letters_to_col("A1")
        with self.assertRaises(ValueError):
            letters_to_col("")


class TestCellAddress(unittest.TestCase):
    def test_address_and_parse_round_trip(self):
        for row0, col0 in [(0, 0), (0, 48), (9999, 48), (156, 25)]:
            address = cell_address(row0, col0)
            self.assertEqual(parse_cell_address(address), (row0, col0))

    def test_known_addresses(self):
        self.assertEqual(cell_address(0, 0), "A1")
        self.assertEqual(cell_address(0, 48), "AW1")
        self.assertEqual(cell_address(9993, 6), "G9994")  # matches a real probe finding's shape

    def test_invalid_address_raises(self):
        with self.assertRaises(ValueError):
            parse_cell_address("1A")
        with self.assertRaises(ValueError):
            parse_cell_address("A0")


class TestCoordinateModel(unittest.TestCase):
    def test_resolves_formula_and_value_by_coords_and_address(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            capture = load_capture(fpath, vpath)
        model = CoordinateModel(capture)

        self.assertEqual(model.formula_at("Alpha", 0, 0), "=A2")
        self.assertEqual(model.formula_at_address("Alpha", "A1"), "=A2")
        self.assertEqual(model.value_at("Alpha", 1, 1), 2)
        self.assertEqual(model.value_at_address("Alpha", "B2"), 2)

    def test_out_of_bounds_raises_with_sheet_and_shape_named(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            capture = load_capture(fpath, vpath)
        model = CoordinateModel(capture)

        with self.assertRaises(IndexError) as ctx:
            model.formula_at("Alpha", 50, 50)
        message = str(ctx.exception)
        self.assertIn("Alpha", message)
        self.assertIn("2 rows", message)


if __name__ == "__main__":
    unittest.main()
