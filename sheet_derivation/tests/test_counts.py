import tempfile
import unittest

from ..counts import compute_all_counts, compute_workbook_totals, is_nonempty
from ..loader import load_capture
from .fixtures import build_good_pair, write_pair


class TestIsNonempty(unittest.TestCase):
    def test_none_and_empty_string_are_empty(self):
        self.assertFalse(is_nonempty(None))
        self.assertFalse(is_nonempty(""))

    def test_zero_and_false_are_nonempty(self):
        # A cell holding 0 or FALSE is a real result, not an empty cell.
        self.assertTrue(is_nonempty(0))
        self.assertTrue(is_nonempty(False))

    def test_ordinary_values_are_nonempty(self):
        self.assertTrue(is_nonempty("hello"))
        self.assertTrue(is_nonempty(3.14))


class TestComputeAllCounts(unittest.TestCase):
    def setUp(self):
        formulas_doc, values_doc = build_good_pair()
        self.tmp = tempfile.TemporaryDirectory()
        fpath, vpath = write_pair(self.tmp.name, formulas_doc, values_doc)
        self.capture = load_capture(fpath, vpath)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hand_computed_per_sheet_counts(self):
        all_counts = compute_all_counts(self.capture)
        self.assertEqual([c.sheet_name for c in all_counts], ["Alpha", "Beta"])

        alpha, beta = all_counts
        self.assertEqual(alpha.total_cells, 4)
        self.assertEqual(alpha.non_empty_formulas, 1)  # only A1: "=A2"
        self.assertEqual(alpha.non_empty_values, 2)    # A1=1, B2=2
        self.assertEqual(alpha.frozen_rows, 1)
        self.assertEqual(alpha.frozen_columns, 0)

        self.assertEqual(beta.total_cells, 3)
        self.assertEqual(beta.non_empty_formulas, 0)
        self.assertEqual(beta.non_empty_values, 1)     # A1="x"
        self.assertEqual(beta.frozen_columns, 1)

    def test_workbook_totals(self):
        all_counts = compute_all_counts(self.capture)
        totals = compute_workbook_totals(self.capture, all_counts)
        self.assertEqual(totals.sheet_count, 2)
        self.assertEqual(totals.total_cells, 7)
        self.assertEqual(totals.total_non_empty_formulas, 1)
        self.assertEqual(totals.total_non_empty_values, 3)
        self.assertEqual(totals.capture_date, self.capture.capture_date)

    def test_fill_rate_percent(self):
        all_counts = compute_all_counts(self.capture)
        alpha = all_counts[0]
        self.assertAlmostEqual(alpha.fill_rate_percent, 25.0)  # 1 of 4 cells


if __name__ == "__main__":
    unittest.main()
