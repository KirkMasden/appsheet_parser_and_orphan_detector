import tempfile
import unittest

from ..determinism import verify_same_process_determinism
from .fixtures import (
    build_stage5_appside_rows,
    build_stage5_pair,
    write_appside_columns_csv,
    write_pair,
)
from .. import stage5


def _run(include_is_virtual=True, appside_dir=None):
    formulas_doc, values_doc = build_stage5_pair()
    with tempfile.TemporaryDirectory() as tmp:
        fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
        if appside_dir is None:
            appside_dir = tempfile.mkdtemp()
            write_appside_columns_csv(appside_dir, build_stage5_appside_rows(), include_is_virtual)
        return stage5.run_stage5(fpath, vpath, appside_dir)


def _table(result, name):
    return next(t for t in result.join.tables if t.table == name)


def _col(entry, name):
    return next(c for c in entry.column_results if c.column == name)


def _label(entry, sheet_column):
    return next(l for l in entry.label_results if l.sheet_column == sheet_column)


class TestAbsentWithoutAppSideParse(unittest.TestCase):
    def test_reported_absent_not_skipped(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            result = stage5.run_stage5(fpath, vpath, appside_parse_dir=None)
        self.assertFalse(result.join.present)
        self.assertEqual(result.join.tables, ())
        self.assertIn("absent", result.join.reliability_condition.lower())

    def test_absent_result_still_a_well_formed_artifact(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            result = stage5.run_stage5(fpath, vpath, None)
        self.assertTrue(result.join.reliability_condition)
        self.assertEqual(result.join.residue, ())


class TestTableMatching(unittest.TestCase):
    def test_table_matching_no_tab(self):
        result = _run()
        ghost = _table(result, "Ghost")
        self.assertEqual(ghost.table_state, stage5.TABLE_STATE_NO_TAB)
        self.assertIsNone(ghost.matched_tab)
        for c in ghost.column_results:
            self.assertEqual(c.state, stage5.COLUMN_STATE_TABLE_NO_TAB)

    def test_table_matching_a_tab_by_exact_name(self):
        result = _run()
        ledger = _table(result, "Ledger")
        self.assertEqual(ledger.table_state, stage5.TABLE_STATE_MATCHED)
        self.assertEqual(ledger.matched_tab, "Ledger")
        self.assertEqual(ledger.header_verdict, "identified")


class TestColumnDirection(unittest.TestCase):
    def test_exact_match(self):
        result = _run()
        ledger = _table(result, "Ledger")
        qty = _col(ledger, "Qty")
        self.assertEqual(qty.state, stage5.COLUMN_STATE_EXACT_MATCH)
        self.assertEqual(qty.matched_label_text, "Qty")

    def test_unmatched(self):
        result = _run()
        ledger = _table(result, "Ledger")
        self.assertEqual(_col(ledger, "Renamed").state, stage5.COLUMN_STATE_UNMATCHED)

    def test_virtual_column_reports_no_sheet_column_expected(self):
        result = _run()
        ledger = _table(result, "Ledger")
        vt = _col(ledger, "VirtualThing")
        self.assertEqual(vt.state, stage5.COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED)
        self.assertTrue(vt.is_virtual)

    def test_column_matching_a_repeated_label_is_unmatched_not_exact(self):
        result = _run()
        ledger = _table(result, "Ledger")
        dup = _col(ledger, "Dup")
        self.assertEqual(dup.state, stage5.COLUMN_STATE_UNMATCHED)

    def test_clean_whitespace_near_miss(self):
        result = _run()
        ledger = _table(result, "Ledger")
        ts = _col(ledger, "Trailing Space")
        self.assertEqual(ts.state, stage5.COLUMN_STATE_WHITESPACE_NEAR_MISS)
        self.assertEqual(ts.near_miss_candidates, ("Trailing Space ",))  # raw, verbatim, untouched

    def test_column_side_collision_names_both_candidates(self):
        result = _run()
        ledger = _table(result, "Ledger")
        foo = _col(ledger, "Foo   Bar")
        self.assertEqual(foo.state, stage5.COLUMN_STATE_WHITESPACE_NEAR_MISS)
        self.assertEqual(set(foo.near_miss_candidates), {"Foo  Bar", "Foo Bar"})

    def test_header_not_identified_state_for_undetermined_tab(self):
        result = _run()
        murky = _table(result, "Murky")
        for name in ("Name", "Amount", "Extra"):
            self.assertEqual(_col(murky, name).state, stage5.COLUMN_STATE_HEADER_NOT_IDENTIFIED)


class TestLabelDirection(unittest.TestCase):
    def test_exact_match(self):
        result = _run()
        ledger = _table(result, "Ledger")
        self.assertEqual(_label(ledger, "A").state, stage5.LABEL_STATE_EXACT_MATCH)
        self.assertEqual(_label(ledger, "A").matched_app_column, "Qty")

    def test_unmatched_label(self):
        result = _run()
        ledger = _table(result, "Ledger")
        self.assertEqual(_label(ledger, "C").state, stage5.LABEL_STATE_UNMATCHED)

    def test_repeated_label_reported_at_both_columns(self):
        result = _run()
        ledger = _table(result, "Ledger")
        self.assertEqual(_label(ledger, "D").state, stage5.LABEL_STATE_REPEATED)
        self.assertEqual(_label(ledger, "E").state, stage5.LABEL_STATE_REPEATED)

    def test_clean_whitespace_near_miss(self):
        result = _run()
        ledger = _table(result, "Ledger")
        f = _label(ledger, "F")
        self.assertEqual(f.state, stage5.LABEL_STATE_WHITESPACE_NEAR_MISS)
        self.assertEqual(f.near_miss_candidates, ("Trailing Space",))

    def test_label_side_collision_names_both_candidates(self):
        result = _run()
        ledger = _table(result, "Ledger")
        h = _label(ledger, "H")
        self.assertEqual(h.state, stage5.LABEL_STATE_WHITESPACE_NEAR_MISS)
        self.assertEqual(set(h.near_miss_candidates), {"Odd  Name", "Odd Name"})

    def test_no_label_results_for_a_table_with_no_matched_tab(self):
        result = _run()
        ghost = _table(result, "Ghost")
        self.assertEqual(ghost.label_results, ())

    def test_no_label_results_for_an_undetermined_tab(self):
        result = _run()
        murky = _table(result, "Murky")
        self.assertEqual(murky.label_results, ())


class TestWhitespaceNormalizationNeverSubstitutes(unittest.TestCase):
    def test_raw_strings_carried_verbatim_never_the_normalized_form(self):
        result = _run()
        ledger = _table(result, "Ledger")
        ts_label = _label(ledger, "F")
        self.assertEqual(ts_label.label_text, "Trailing Space ")  # trailing space preserved, not stripped
        self.assertEqual(ts_label.near_miss_candidates, ("Trailing Space",))  # the app column's own raw name
        # Neither side is ever rewritten to a shared normalized form -- the two
        # raw strings genuinely differ (one has a trailing space, one doesn't).
        self.assertNotEqual(ts_label.label_text, ts_label.near_miss_candidates[0])


class TestUndeterminedDiagnostic(unittest.TestCase):
    def test_diagnostic_built_only_for_undetermined_tabs(self):
        result = _run()
        tables_with_diagnostics = {d.table for d in result.join.diagnostics}
        self.assertEqual(tables_with_diagnostics, {"Murky"})

    def test_diagnostic_counts(self):
        result = _run()
        diag = next(d for d in result.join.diagnostics if d.table == "Murky")
        self.assertEqual(diag.app_column_count, 3)
        self.assertEqual(set(diag.app_columns_found), {"Name", "Amount"})
        self.assertEqual(diag.app_columns_not_found, ("Extra",))
        self.assertEqual(diag.row1_nonempty_count, 2)
        self.assertEqual(set(diag.row1_exact_matches), {"Name", "Amount"})

    def test_diagnostic_does_not_change_the_join_states_it_describes(self):
        """The central boundary this build must not cross: agreement in
        the diagnostic must never change COLUMN_STATE_HEADER_NOT_IDENTIFIED."""
        result = _run()
        murky = _table(result, "Murky")
        for name in ("Name", "Amount"):  # both FOUND by the diagnostic
            self.assertEqual(_col(murky, name).state, stage5.COLUMN_STATE_HEADER_NOT_IDENTIFIED)


class TestVirtualFieldResidue(unittest.TestCase):
    def test_missing_field_produces_residue_and_no_column_is_inferred_virtual(self):
        result = _run(include_is_virtual=False)
        self.assertFalse(result.join.virtual_field_present)
        matches = [r for r in result.join.residue if r.defeating_construct == "missing is_virtual column"]
        self.assertEqual(len(matches), 1)
        ledger = _table(result, "Ledger")
        vt = _col(ledger, "VirtualThing")
        # Without the field, virtuality is never inferred -- VirtualThing has no
        # sheet-side counterpart and is correctly, plainly UNMATCHED, not
        # magically excused into NO_SHEET_COLUMN_EXPECTED.
        self.assertEqual(vt.state, stage5.COLUMN_STATE_UNMATCHED)
        self.assertIsNone(vt.is_virtual)


class TestCollisionResidue(unittest.TestCase):
    def test_both_collisions_produce_residue(self):
        result = _run()
        collision_residue = [r for r in result.join.residue if r.defeating_construct == "whitespace-collapse collision"]
        self.assertEqual(len(collision_residue), 2)  # one column-side, one label-side


class TestAccountingInvariants(unittest.TestCase):
    def test_column_states_partition_every_app_column_exactly_once(self):
        result = _run()
        self.assertEqual(sum(result.column_state_counts.values()), 14)  # total app columns in the fixture

    def test_label_states_partition_every_header_label_exactly_once(self):
        result = _run()
        # Ledger has 9 labeled columns (A,B,C,D,E,F,H,I,J); Murky and Ghost contribute none.
        self.assertEqual(sum(result.label_state_counts.values()), 9)

    def test_determinism(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            appside_dir = tempfile.mkdtemp()
            write_appside_columns_csv(appside_dir, build_stage5_appside_rows())

            def pipeline():
                return stage5.run_stage5(fpath, vpath, appside_dir)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-5")
        self.assertEqual(len(result.join.tables), 3)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            appside_dir = tempfile.mkdtemp()
            write_appside_columns_csv(appside_dir, build_stage5_appside_rows())
            exit_code = stage5.main([tmp, appside_dir])
        self.assertEqual(exit_code, 0)

    def test_main_runs_end_to_end_absent(self):
        formulas_doc, values_doc = build_stage5_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage5.main([tmp])
        self.assertEqual(exit_code, 0)


class TestNormalizeWhitespace(unittest.TestCase):
    def test_collapses_runs_and_strips(self):
        self.assertEqual(stage5.normalize_whitespace("  a   b  "), "a b")

    def test_no_op_on_already_clean_string(self):
        self.assertEqual(stage5.normalize_whitespace("a b"), "a b")


if __name__ == "__main__":
    unittest.main()
