import tempfile
import unittest

from ..determinism import verify_same_process_determinism
from ..report import format_per_sheet_table
from .fixtures import build_good_pair, write_pair
from .. import stage0


class TestStage0EndToEnd(unittest.TestCase):
    def test_run_stage0_on_synthetic_capture(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            result = stage0.run_stage0(fpath, vpath)

        self.assertEqual(result.totals.sheet_count, 2)
        self.assertEqual(result.totals.total_cells, 7)
        self.assertEqual(result.totals.total_non_empty_formulas, 1)
        self.assertEqual(result.totals.total_non_empty_values, 3)

        table = format_per_sheet_table(result.all_counts, result.totals)
        self.assertIn("Alpha", table)
        self.assertIn("Beta", table)
        self.assertIn("**TOTAL**", table)

    def test_stage0_pipeline_is_deterministic_on_synthetic_capture(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)

            def pipeline():
                return stage0.run_stage0(fpath, vpath)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-0")
        self.assertEqual(result.totals.sheet_count, 2)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_good_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage0.main([tmp])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
