import tempfile
import unittest

from ..determinism import verify_same_process_determinism
from .fixtures import build_stage3_pair, write_pair
from .. import stage3


class TestStage3ColumnClassification(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage3.run_stage3(fpath, vpath)

    def _column(self, result, column):
        for c in result.column_profiles.columns:
            if c.sheet == "Grid" and c.column == column:
                return c
        return None

    def test_multi_pattern_column(self):
        c = self._column(self._run(), "A")
        self.assertEqual(c.distinct_pattern_count, 2)
        self.assertEqual(c.classification, stage3.CLASSIFICATION_MULTI_PATTERN)
        self.assertEqual(c.total_formula_count, 3)

    def test_single_pattern_contiguous_column(self):
        c = self._column(self._run(), "B")
        self.assertEqual(c.distinct_pattern_count, 1)
        self.assertEqual(c.classification, stage3.CLASSIFICATION_SINGLE_CONTIGUOUS)
        self.assertEqual(c.total_formula_count, 3)

    def test_single_pattern_ragged_column(self):
        c = self._column(self._run(), "C")
        self.assertEqual(c.distinct_pattern_count, 1)
        self.assertEqual(c.classification, stage3.CLASSIFICATION_SINGLE_RAGGED)
        self.assertEqual(c.total_formula_count, 3)

    def test_no_formula_column_classification(self):
        c = self._column(self._run(), "G")
        self.assertEqual(c.total_formula_count, 0)
        self.assertEqual(c.distinct_pattern_count, 0)
        self.assertEqual(c.classification, stage3.CLASSIFICATION_NO_FORMULA)
        self.assertEqual(c.total_value_count, 3)


class TestStage3SpillAssessment(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage3.run_stage3(fpath, vpath)

    def _column(self, result, column):
        for c in result.column_profiles.columns:
            if c.sheet == "Grid" and c.column == column:
                return c
        return None

    def test_spill_run_immediately_adjacent_has_zero_gap(self):
        c = self._column(self._run(), "D")
        self.assertEqual(len(c.spill_runs), 1)
        run = c.spill_runs[0]
        self.assertEqual((run.row_start1, run.row_end1), (2, 3))
        self.assertEqual(run.governing_formula_row1, 1)
        self.assertEqual(run.gap_rows, 0)

    def test_spill_run_with_one_blank_row_has_gap_one(self):
        c = self._column(self._run(), "E")
        self.assertEqual(len(c.spill_runs), 1)
        run = c.spill_runs[0]
        self.assertEqual((run.row_start1, run.row_end1), (3, 3))
        self.assertEqual(run.governing_formula_row1, 1)
        self.assertEqual(run.gap_rows, 1)

    def test_no_threshold_is_ever_applied_to_a_measured_gap(self):
        """Design section 3.2's own instruction: no gap size is judged
        'too large to be related' by this tool. Both a gap of 0 and a gap
        of 1 are reported as plain measurements, with no field anywhere
        marking either one as acceptable or suspicious."""
        result = self._run()
        d_run = self._column(result, "D").spill_runs[0]
        e_run = self._column(result, "E").spill_runs[0]
        self.assertNotEqual(d_run.gap_rows, e_run.gap_rows)
        # Neither SpillRun nor its containing ColumnProfileEntry carries any
        # flag, threshold, or verdict field beyond the measured numbers.
        for run in (d_run, e_run):
            self.assertEqual(
                set(run.__dataclass_fields__),
                {"sheet", "column", "row_start1", "row_end1", "governing_formula_row1", "gap_rows"},
            )

    def test_run_with_no_formula_above_it_becomes_residue_even_though_column_has_a_formula(self):
        result = self._run()
        c = self._column(result, "F")
        self.assertEqual(c.total_formula_count, 1)
        self.assertEqual(len(c.spill_runs), 1)
        run = c.spill_runs[0]
        self.assertIsNone(run.governing_formula_row1)
        self.assertIsNone(run.gap_rows)
        matches = [
            r for r in result.column_profiles.residue
            if r.defeating_construct == "no formula above this run in this column"
            and r.locations == ("Grid!F1",)
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("elsewhere", matches[0].what)

    def test_column_with_no_formula_anywhere_is_reported_plainly(self):
        """Design section 3.2's own worked example (Vertical column R: 10,000
        values, no formula at all) -- at fixture scale, this must NOT be
        reported as 'no dependency' but as an explicit residue entry naming
        the value count and the absence of any formula in the column."""
        result = self._run()
        c = self._column(result, "G")
        self.assertEqual(len(c.spill_runs), 1)
        run = c.spill_runs[0]
        self.assertIsNone(run.governing_formula_row1)
        matches = [
            r for r in result.column_profiles.residue
            if r.defeating_construct == "no formula anywhere in this column"
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("3", matches[0].what)  # 3 values
        self.assertIn("no formula anywhere in this column", matches[0].what)

    def test_every_value_only_run_is_either_governed_or_residue_never_neither(self):
        result = self._run()
        governed = sum(
            1 for c in result.column_profiles.columns for r in c.spill_runs
            if r.governing_formula_row1 is not None
        )
        residue = sum(
            1 for c in result.column_profiles.columns for r in c.spill_runs
            if r.governing_formula_row1 is None
        )
        self.assertEqual(governed + residue, result.spill_run_total)
        self.assertEqual(residue, result.spill_run_residue_count)
        # D and E are governed; F and G are residue.
        self.assertEqual(governed, 2)
        self.assertEqual(residue, 2)


class TestStage3NoTruncation(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage3.run_stage3(fpath, vpath)

    def test_a_very_long_raw_instance_is_carried_whole(self):
        result = self._run()
        long_patterns = [p for p in result.inventory.patterns if len(p.raw_instance) > 1000]
        self.assertEqual(len(long_patterns), 1)
        raw = long_patterns[0].raw_instance
        self.assertEqual(len(raw), 3003)  # ="  + 3000 A's + "
        self.assertTrue(raw.startswith('="AAAA'))
        self.assertTrue(raw.endswith('AAA"'))


class TestStage3UnknownTokenResidue(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage3.run_stage3(fpath, vpath)

    def test_unknown_token_pattern_still_matches_but_gets_inventory_residue(self):
        result = self._run()
        pat = next(p for p in result.inventory.patterns if p.pattern_text == "=A#?")
        self.assertEqual(pat.instance_count, 1)  # still matched to a pattern
        matches = [r for r in result.inventory.residue if r.defeating_construct == "UNKNOWN token"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].locations, ("Grid!I1",))


class TestStage3PatternLocationsAndColumnProfiles(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage3.run_stage3(fpath, vpath)

    def test_pattern_location_ranges_never_span_a_row_the_pattern_does_not_occupy(self):
        result = self._run()
        pat = next(p for p in result.inventory.patterns if p.pattern_text == "=200")
        # C column: rows 1, 2, 4 -- must be TWO ranges (1-2 and 4-4), never one 1-4 range.
        c_locations = [l for l in pat.locations if l.column == "C"]
        self.assertEqual(len(c_locations), 2)
        self.assertEqual({(l.row_start1, l.row_end1) for l in c_locations}, {(1, 2), (4, 4)})

    def test_embedded_column_profile_summary_matches_this_pattern_share(self):
        result = self._run()
        pat = next(p for p in result.inventory.patterns if p.pattern_text == "=1")
        cp = next(cp for cp in pat.column_profiles if cp.column == "A")
        self.assertEqual(cp.this_pattern_instance_count, 2)
        self.assertEqual(cp.total_formula_count, 3)
        self.assertAlmostEqual(cp.this_pattern_share, 2 / 3)
        self.assertEqual(cp.classification, stage3.CLASSIFICATION_MULTI_PATTERN)
        self.assertEqual(cp.distinct_pattern_count, 2)


class TestStage3Accounting(unittest.TestCase):
    def test_formula_accounting_is_total_by_construction(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            result = stage3.run_stage3(fpath, vpath)
        for a in result.accounting:
            self.assertTrue(a.balances)
            self.assertEqual(a.residue_formulas, 0)
        wb = result.workbook_accounting
        self.assertEqual(wb.non_empty_formulas, 14)
        self.assertEqual(wb.matched_formulas, 14)
        self.assertTrue(wb.balances)

    def test_determinism(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)

            def pipeline():
                return stage3.run_stage3(fpath, vpath)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-3")
        self.assertEqual(result.workbook_accounting.non_empty_formulas, 14)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_stage3_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage3.main([tmp])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
