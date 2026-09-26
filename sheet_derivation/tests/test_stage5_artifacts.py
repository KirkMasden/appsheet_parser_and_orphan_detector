import csv
import tempfile
import unittest

from .. import stage5
from ..jsonl_io import read_jsonl
from ..stage5_artifacts import write_stage5_artifacts
from .fixtures import build_stage5_appside_rows, build_stage5_pair, write_appside_columns_csv, write_pair


class TestStage5ArtifactFiles(unittest.TestCase):
    def _write(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as capture_tmp:
            fpath, vpath = write_pair(capture_tmp, formulas_doc, values_doc)
            appside_dir = tempfile.mkdtemp()
            write_appside_columns_csv(appside_dir, build_stage5_appside_rows())
            result = stage5.run_stage5(fpath, vpath, appside_dir)
        out_tmp = tempfile.mkdtemp()
        paths = write_stage5_artifacts(result, out_tmp)
        return result, paths

    def test_join_jsonl_has_meta_then_tables_then_diagnostics_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["join"]))
        self.assertEqual(lines[0]["kind"], "meta")
        table_lines = [l for l in lines if l["kind"] == "table"]
        diag_lines = [l for l in lines if l["kind"] == "diagnostic"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(table_lines), len(result.join.tables))
        self.assertEqual(len(diag_lines), len(result.join.diagnostics))
        self.assertEqual(len(residue_lines), len(result.join.residue))
        self.assertEqual(len(lines), 1 + len(table_lines) + len(diag_lines) + len(residue_lines))

    def test_meta_and_table_lines_state_the_tab_pairing(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["join"]))
        self.assertEqual(lines[0]["tabPairing"], stage5.TAB_PAIRING_TABLE_NAME)
        self.assertTrue(lines[0]["tabPairingNote"])
        ledger = next(l for l in lines if l["kind"] == "table" and l["table"] == "Ledger")
        self.assertEqual(ledger["tabSource"], stage5.TAB_SOURCE_TABLE_NAME)
        self.assertIn("sourceWorksheet", ledger)

    def test_table_line_is_self_contained(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["join"]))
        ledger = next(l for l in lines if l["kind"] == "table" and l["table"] == "Ledger")
        self.assertIn("columns", ledger)
        self.assertIn("labels", ledger)
        qty = next(c for c in ledger["columns"] if c["column"] == "Qty")
        self.assertEqual(qty["state"], "exact-match")

    def test_meta_line_carries_provenance(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["join"]))
        meta = lines[0]
        self.assertIn("provenance", meta)
        self.assertIn("inputFileHashes", meta["provenance"])
        self.assertTrue(meta["provenance"]["inputFileHashes"])

    def test_column_summary_csv_is_flat_one_row_per_app_column(self):
        result, paths = self._write()
        with open(paths["column_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        total_app_columns = sum(len(t.column_results) for t in result.join.tables)
        self.assertEqual(len(rows), total_app_columns)

    def test_label_summary_csv_is_flat_one_row_per_label(self):
        result, paths = self._write()
        with open(paths["label_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        total_labels = sum(len(t.label_results) for t in result.join.tables)
        self.assertEqual(len(rows), total_labels)

    def test_csv_has_no_nested_or_variable_length_fields(self):
        _, paths = self._write()
        for key in ("column_summary_csv", "label_summary_csv"):
            with open(paths[key], encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                for row in reader:
                    self.assertEqual(len(row), len(header))

    def test_absent_join_still_writes_a_valid_meta_only_file(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            result = stage5.run_stage5(fpath, vpath, None)
        out_tmp = tempfile.mkdtemp()
        paths = write_stage5_artifacts(result, out_tmp)
        lines = list(read_jsonl(paths["join"]))
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0]["present"])


if __name__ == "__main__":
    unittest.main()
