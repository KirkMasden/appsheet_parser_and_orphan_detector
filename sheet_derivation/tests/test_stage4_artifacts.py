import csv
import tempfile
import unittest

from .. import stage4
from ..jsonl_io import read_jsonl
from ..stage4_artifacts import write_stage4_artifacts
from .fixtures import build_stage4_pair, write_pair


class TestStage4ArtifactFiles(unittest.TestCase):
    def _write(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as capture_tmp:
            fpath, vpath = write_pair(capture_tmp, formulas_doc, values_doc)
            result = stage4.run_stage4(fpath, vpath)
        out_tmp = tempfile.mkdtemp()
        paths = write_stage4_artifacts(result, out_tmp)
        return result, paths

    def test_schema_jsonl_has_one_meta_line_then_one_line_per_sheet_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["schema"]))
        self.assertEqual(lines[0]["kind"], "meta")
        sheet_lines = [l for l in lines if l["kind"] == "sheet"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(sheet_lines), len(result.schema.sheets))
        self.assertEqual(len(residue_lines), len(result.schema.residue))
        self.assertEqual(len(lines), 1 + len(sheet_lines) + len(residue_lines))

    def test_sheet_line_is_self_contained(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["schema"]))
        ledger = next(l for l in lines if l["kind"] == "sheet" and l["sheet"] == "Ledger")
        self.assertIn("headerDetection", ledger)
        self.assertIn("duplicateLabels", ledger)
        self.assertIn("columns", ledger)
        self.assertEqual(ledger["headerDetection"]["verdict"], "identified")
        self.assertEqual(ledger["duplicateLabels"], [{"labelValue": "Qty", "columns": ["A", "B"]}])

    def test_sheet_summary_csv_is_flat_one_row_per_sheet(self):
        result, paths = self._write()
        with open(paths["sheet_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(result.schema.sheets))
        spill_row = next(r for r in rows if r["sheet"] == "SpillSheet")
        self.assertEqual(spill_row["headerVerdict"], "not-identified-confident")
        self.assertEqual(spill_row["duplicateLabelCount"], "1")

    def test_column_summary_csv_is_flat_one_row_per_column(self):
        result, paths = self._write()
        with open(paths["column_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        expected_rows = sum(s.declared_column_count for s in result.schema.sheets)
        self.assertEqual(len(rows), expected_rows)
        ledger_a = next(r for r in rows if r["sheet"] == "Ledger" and r["column"] == "A")
        self.assertEqual(ledger_a["headerLabelState"], "labeled")
        self.assertEqual(ledger_a["headerLabelValue"], "Qty")

    def test_csv_has_no_nested_or_variable_length_fields(self):
        _, paths = self._write()
        for key in ("sheet_summary_csv", "column_summary_csv"):
            with open(paths[key], encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                for row in reader:
                    self.assertEqual(len(row), len(header))


if __name__ == "__main__":
    unittest.main()
