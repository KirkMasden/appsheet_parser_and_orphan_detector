import tempfile
import unittest

from ..loader import load_capture
from .. import query
from .fixtures import build_stage3_pair, write_pair


class TestQueryAddress(unittest.TestCase):
    def _capture(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return load_capture(fpath, vpath)

    def test_plain_formula_cell_with_no_spill(self):
        """Grid!B1 is a formula, but B2/B3 hold THEIR OWN formulas (not
        bare values) -- this must not be reported as a spill."""
        capture = self._capture()
        result = query.query_address(capture, "Grid", "B1")
        self.assertEqual(result.formula, "=100")
        self.assertEqual(result.value, 100)
        self.assertFalse(result.is_spill_origin)
        self.assertIsNone(result.spill_extent)

    def test_formula_cell_with_downward_spill(self):
        """Grid!D1 is a formula; D2/D3 hold values with no formula of
        their own -- the query must report the down-extent without being
        asked to follow anything."""
        capture = self._capture()
        result = query.query_address(capture, "Grid", "D1")
        self.assertEqual(result.formula, "=300")
        self.assertTrue(result.is_spill_origin)
        self.assertIsNotNone(result.spill_extent)
        self.assertEqual(result.spill_extent.down_to_row1, 3)
        self.assertEqual(result.spill_extent.right_to_column, "D")  # no rightward extension

    def test_value_only_cell_is_not_itself_a_spill_origin(self):
        """Grid!D2 holds a value with no formula -- only a FORMULA cell can
        be reported as a spill origin; D2 is a spill TARGET, a different
        question the column profile's spill assessment answers, not this
        query."""
        capture = self._capture()
        result = query.query_address(capture, "Grid", "D2")
        self.assertIsNone(result.formula)
        self.assertEqual(result.value, 5)
        self.assertFalse(result.is_spill_origin)
        self.assertIsNone(result.spill_extent)

    def test_unknown_sheet_raises(self):
        capture = self._capture()
        with self.assertRaises(query.UnknownSheetError):
            query.query_address(capture, "Nonexistent Sheet", "A1")

    def test_out_of_bounds_address_raises(self):
        capture = self._capture()
        with self.assertRaises(IndexError):
            query.query_address(capture, "Grid", "A999")

    def test_spill_extent_note_states_it_is_structural_not_a_confirmation(self):
        capture = self._capture()
        result = query.query_address(capture, "Grid", "D1")
        self.assertIn("not a confirmation", result.spill_extent.note.lower())


if __name__ == "__main__":
    unittest.main()
