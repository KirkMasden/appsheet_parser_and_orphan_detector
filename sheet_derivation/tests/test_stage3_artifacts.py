import csv
import os
import tempfile
import unittest

from .. import stage3
from ..jsonl_io import read_jsonl
from ..stage3_artifacts import write_stage3_artifacts
from .fixtures import build_stage3_pair, write_pair


class TestStage3ArtifactFiles(unittest.TestCase):
    def _write(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as capture_tmp:
            fpath, vpath = write_pair(capture_tmp, formulas_doc, values_doc)
            result = stage3.run_stage3(fpath, vpath)
        out_tmp = tempfile.mkdtemp()
        paths = write_stage3_artifacts(result, out_tmp)
        return result, paths

    def test_inventory_jsonl_has_one_meta_line_then_one_line_per_pattern_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["formula_inventory"]))
        self.assertEqual(lines[0]["kind"], "meta")
        pattern_lines = [l for l in lines if l["kind"] == "pattern"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(pattern_lines), len(result.inventory.patterns))
        self.assertEqual(len(residue_lines), len(result.inventory.residue))
        self.assertEqual(len(lines), 1 + len(pattern_lines) + len(residue_lines))

    def test_column_profiles_jsonl_has_one_meta_line_then_one_line_per_column_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["column_profiles"]))
        self.assertEqual(lines[0]["kind"], "meta")
        column_lines = [l for l in lines if l["kind"] == "column"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(column_lines), len(result.column_profiles.columns))
        self.assertEqual(len(residue_lines), len(result.column_profiles.residue))

    def test_every_pattern_line_is_self_contained_with_locations_and_column_profiles(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["formula_inventory"]))
        pattern_line = next(l for l in lines if l["kind"] == "pattern" and l["pattern"] == "=1")
        self.assertIn("locations", pattern_line)
        self.assertIn("columnProfiles", pattern_line)
        self.assertGreater(len(pattern_line["locations"]), 0)
        self.assertGreater(len(pattern_line["columnProfiles"]), 0)

    def test_long_raw_instance_is_not_truncated_in_the_jsonl_file(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["formula_inventory"]))
        long_line = next(l for l in lines if l["kind"] == "pattern" and len(l.get("rawInstance", "")) > 1000)
        self.assertEqual(len(long_line["rawInstance"]), 3003)

    def test_csv_projection_is_flat_one_row_per_column(self):
        result, paths = self._write()
        with open(paths["column_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(result.column_profiles.columns))
        g_row = next(r for r in rows if r["sheet"] == "Grid" and r["column"] == "G")
        self.assertEqual(g_row["classification"], stage3.CLASSIFICATION_NO_FORMULA)
        self.assertEqual(g_row["spillRunsWithoutGoverningFormula"], "1")

    def test_csv_projection_has_no_nested_or_variable_length_fields(self):
        _, paths = self._write()
        with open(paths["column_summary_csv"], encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            rows = list(reader)
        for row in rows:
            self.assertEqual(len(row), len(header))


if __name__ == "__main__":
    unittest.main()
