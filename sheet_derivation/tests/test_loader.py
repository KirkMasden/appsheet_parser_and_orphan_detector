import tempfile
import unittest

from ..errors import CaptureIntegrityError
from ..loader import discover_capture_files, load_capture
from .fixtures import build_good_pair, write_pair


class TestGoodCaptureLoads(unittest.TestCase):
    def test_loads_and_preserves_sheet_order(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            capture = load_capture(fpath, vpath)
        self.assertEqual(capture.sheet_order, ("Alpha", "Beta"))
        self.assertEqual(capture.capture_date, "2099-01-01T00:00:00.000Z")
        self.assertEqual(capture.formula_sheet("Alpha").row_count, 2)
        self.assertEqual(capture.formula_sheet("Alpha").column_count, 2)
        self.assertEqual(capture.value_sheet("Beta").values, (("x", "", ""),))

    def test_discover_capture_files_finds_the_pair(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            found_f, found_v = discover_capture_files(tmp)
        self.assertEqual(found_f, fpath)
        self.assertEqual(found_v, vpath)

    def test_discover_capture_files_refuses_on_zero_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaptureIntegrityError):
                discover_capture_files(tmp)

    def test_discover_capture_files_refuses_on_ambiguous_matches(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            # A second, differently-named formulas file makes the directory ambiguous.
            import json
            import os

            with open(os.path.join(tmp, "Other_formulas_11111111-111111.json"), "w") as fh:
                json.dump(formulas_doc, fh)
            with self.assertRaises(CaptureIntegrityError):
                discover_capture_files(tmp)


class TestGateOneCaptureDate(unittest.TestCase):
    def test_refuses_on_capture_date_mismatch(self):
        formulas_doc, values_doc = build_good_pair()
        values_doc["captureDate"] = "1970-01-01T00:00:00.000Z"
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError) as ctx:
                load_capture(fpath, vpath)
        self.assertIn("captureDate", str(ctx.exception))


class TestGateTwoSheetLists(unittest.TestCase):
    def test_refuses_on_different_names(self):
        formulas_doc, values_doc = build_good_pair()
        values_doc["sheets"][1]["sheetName"] = "NotBeta"
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError) as ctx:
                load_capture(fpath, vpath)
        self.assertIn("sheet lists differ", str(ctx.exception))

    def test_refuses_on_different_order(self):
        formulas_doc, values_doc = build_good_pair()
        values_doc["sheets"] = list(reversed(values_doc["sheets"]))
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError) as ctx:
                load_capture(fpath, vpath)
        self.assertIn("different order", str(ctx.exception))


class TestGateThreeDeclaredDimensions(unittest.TestCase):
    def test_refuses_on_wrong_declared_row_count(self):
        formulas_doc, values_doc = build_good_pair()
        formulas_doc["sheets"][0]["rowCount"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError) as ctx:
                load_capture(fpath, vpath)
        self.assertIn("Alpha", str(ctx.exception))
        self.assertIn("rowCount", str(ctx.exception))

    def test_refuses_on_wrong_declared_column_count(self):
        formulas_doc, values_doc = build_good_pair()
        formulas_doc["sheets"][0]["columnCount"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError) as ctx:
                load_capture(fpath, vpath)
        self.assertIn("columnCount", str(ctx.exception))

    def test_refuses_on_ragged_formula_rows(self):
        formulas_doc, values_doc = build_good_pair()
        # Make Alpha's second formula row shorter than the first -- a ragged
        # array that no single declared columnCount can honestly describe.
        formulas_doc["sheets"][0]["formulas"][1] = [""]
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError):
                load_capture(fpath, vpath)

    def test_refuses_on_values_dimension_mismatch(self):
        formulas_doc, values_doc = build_good_pair()
        values_doc["sheets"][0]["values"] = [[1, 2, 3]]  # wrong shape for Alpha (2x2)
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            with self.assertRaises(CaptureIntegrityError):
                load_capture(fpath, vpath)


if __name__ == "__main__":
    unittest.main()
