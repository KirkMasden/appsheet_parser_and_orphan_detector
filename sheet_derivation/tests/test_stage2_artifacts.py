import csv
import tempfile
import unittest

from .. import stage2
from ..jsonl_io import read_jsonl
from ..stage2_artifacts import write_stage2_artifacts
from .fixtures import build_stage2_pair, write_pair


class TestStage2ArtifactFiles(unittest.TestCase):
    def _write(self):
        formulas_doc, values_doc = build_stage2_pair()
        with tempfile.TemporaryDirectory() as capture_tmp:
            fpath, vpath = write_pair(capture_tmp, formulas_doc, values_doc)
            result = stage2.run_stage2(fpath, vpath)
        out_tmp = tempfile.mkdtemp()
        paths = write_stage2_artifacts(result, out_tmp)
        return result, paths

    def test_dependency_graph_jsonl_has_one_meta_line_then_one_line_per_edge_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["dependency_graph"]))
        self.assertEqual(lines[0]["kind"], "meta")
        edge_lines = [l for l in lines if l["kind"] == "edge"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(edge_lines), len(result.graph.edges))
        self.assertEqual(len(residue_lines), len(result.graph.residue))
        self.assertEqual(len(lines), 1 + len(edge_lines) + len(residue_lines))

    def test_dangling_names_jsonl_has_one_meta_line_then_one_line_per_entry_then_residue(self):
        result, paths = self._write()
        lines = list(read_jsonl(paths["dangling_names"]))
        self.assertEqual(lines[0]["kind"], "meta")
        entry_lines = [l for l in lines if l["kind"] == "entry"]
        residue_lines = [l for l in lines if l["kind"] == "residue"]
        self.assertEqual(len(entry_lines), len(result.dangling.entries))
        self.assertEqual(len(residue_lines), len(result.dangling.residue))
        self.assertEqual(len(lines), 1 + len(entry_lines) + len(residue_lines))

    def test_every_edge_line_is_self_contained_with_patterns_and_cells(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["dependency_graph"]))
        edge_line = next(
            l for l in lines
            if l["kind"] == "edge" and l["sourceSheet"] == "Ledger" and l["sourceColumn"] == "A"
            and l["targetSheet"] == "Other" and l["targetColumn"] == "B"
        )
        self.assertIn("patterns", edge_line)
        self.assertIn("cells", edge_line)
        self.assertGreater(len(edge_line["patterns"]), 0)
        self.assertEqual(edge_line["cells"], ["Ledger!A1", "Ledger!A2"])

    def test_every_entry_line_carries_its_own_occurrences_with_cell_and_raw_formula(self):
        _, paths = self._write()
        lines = list(read_jsonl(paths["dangling_names"]))
        entry_line = next(l for l in lines if l["kind"] == "entry" and l["name"] == "Ghost Sheet")
        self.assertIn("classification", entry_line)
        self.assertGreater(len(entry_line["occurrences"]), 0)
        occ = entry_line["occurrences"][0]
        self.assertIn("cell", occ)
        self.assertIn("rawFormula", occ)
        self.assertIn("evaluatedValue", occ)

    def test_edge_summary_csv_is_flat_one_row_per_edge(self):
        result, paths = self._write()
        with open(paths["edge_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(result.graph.edges))
        row = next(
            r for r in rows
            if r["sourceSheet"] == "Ledger" and r["sourceColumn"] == "A"
            and r["targetSheet"] == "Other" and r["targetColumn"] == "B"
        )
        self.assertEqual(row["cellCount"], "2")

    def test_dangling_occurrence_summary_csv_is_flat_one_row_per_occurrence(self):
        result, paths = self._write()
        with open(paths["dangling_occurrence_summary_csv"], encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        expected_row_count = sum(len(e.occurrences) for e in result.dangling.entries)
        self.assertEqual(len(rows), expected_row_count)
        ghost_rows = [r for r in rows if r["name"] == "Ghost Sheet"]
        self.assertGreater(len(ghost_rows), 0)
        for r in ghost_rows:
            self.assertEqual(r["classification"], next(
                e.classification for e in result.dangling.entries
                if e.name == "Ghost Sheet" and any(o.cell == r["cell"] for o in e.occurrences)
            ))

    def test_csv_projections_have_no_nested_or_variable_length_fields(self):
        _, paths = self._write()
        for key in ("edge_summary_csv", "dangling_occurrence_summary_csv"):
            with open(paths[key], encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                rows = list(reader)
            for row in rows:
                self.assertEqual(len(row), len(header))


if __name__ == "__main__":
    unittest.main()
