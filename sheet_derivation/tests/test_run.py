"""run.py: the pairing check before any stage, and finding the app-side
results beside the output folder."""

import contextlib
import io
import os
import tempfile
import unittest

from .. import run
from ..jsonl_io import read_jsonl
from .fixtures import (
    build_capture_from_tabs,
    build_stage5_appside_rows,
    build_stage5_pair,
    write_appside_columns_csv,
    write_export_html,
    write_formula_columns_csv,
    write_pair,
    write_tables_csv,
)
from .stage6_support import STORED, column_rows, scenario_rows

_MATCHING_EXPORT = [("Ledger", "Ledger", "google"), ("Murky", "Murky", "google"), ("Ghost", None, "native")]
_UNRELATED_EXPORT = [("Orders", "Order sheet", "google")]


def _workspace(tmp, export_tables=_MATCHING_EXPORT, with_app_results=True):
    """<tmp>/apps/Test (input folder) and <tmp>/output/Test/{app,sheet}."""
    input_dir = os.path.join(tmp, "apps", "Test")
    os.makedirs(input_dir)
    formulas_doc, values_doc = build_stage5_pair()
    write_pair(input_dir, formulas_doc, values_doc)
    if export_tables is not None:
        write_export_html(input_dir, export_tables)
    app_dir = os.path.join(tmp, "output", "Test", "app")
    if with_app_results:
        os.makedirs(app_dir)
        write_appside_columns_csv(app_dir, build_stage5_appside_rows())
    sheet_dir = os.path.join(tmp, "output", "Test", "sheet")
    return input_dir, app_dir, sheet_dir


def _main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = run.main(argv)
    return code, out.getvalue(), err.getvalue()


def _meta(sheet_dir):
    return next(iter(read_jsonl(os.path.join(sheet_dir, "stage5_join.jsonl"))))


class TestFindAppsideResultsBeside(unittest.TestCase):
    def test_found_in_documented_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, app_dir, sheet_dir = _workspace(tmp)
            self.assertEqual(run.find_appside_results_beside(sheet_dir), app_dir)

    def test_not_found_when_output_folder_is_not_named_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            _workspace(tmp)
            self.assertIsNone(run.find_appside_results_beside(os.path.join(tmp, "output", "Test", "other")))

    def test_not_found_when_app_folder_lacks_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, sheet_dir = _workspace(tmp, with_app_results=False)
            os.makedirs(os.path.join(tmp, "output", "Test", "app"))
            self.assertIsNone(run.find_appside_results_beside(sheet_dir))


class TestRunFindsInputsItself(unittest.TestCase):
    def test_documented_command_produces_a_present_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, app_dir, sheet_dir = _workspace(tmp)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5"])
            meta = _meta(sheet_dir)
        self.assertEqual(code, 0, msg=err)
        self.assertIn(f"app-side results: using {app_dir}", out)
        self.assertIn("app export: using", out)
        self.assertIn("Pairing check: all 2", out)
        self.assertTrue(meta["present"])
        self.assertEqual(meta["tabPairing"], "by-export-worksheet-name")

    def test_no_app_side_results_warns_that_the_join_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp, with_app_results=False)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5"])
            meta = _meta(sheet_dir)
        self.assertEqual(code, 0)
        self.assertFalse(meta["present"])
        self.assertIn("WARNING: no app-side results found", err)
        self.assertIn("ABSENT", err)
        self.assertIn("--appside-parse-dir", err)

    def test_explicit_appside_dir_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp)
            other = os.path.join(tmp, "elsewhere")
            os.makedirs(other)
            write_appside_columns_csv(other, build_stage5_appside_rows())
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5", "--appside-parse-dir", other])
            meta = _meta(sheet_dir)
        self.assertEqual(code, 0, msg=err)
        self.assertNotIn("app-side results: using", out)
        self.assertEqual(meta["provenance"]["appsideParseDir"], other)

    def test_explicit_appside_dir_without_results_still_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp)
            empty = os.path.join(tmp, "empty")
            os.makedirs(empty)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5", "--appside-parse-dir", empty])
        self.assertEqual(code, 0)
        self.assertIn("join is ABSENT", err)


class TestRunPairingCheck(unittest.TestCase):
    def test_unrelated_capture_stops_before_any_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp, export_tables=_UNRELATED_EXPORT)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5"])
            wrote = os.path.exists(os.path.join(sheet_dir, "stage5_join.jsonl"))
        self.assertEqual(code, run.EXIT_PAIRING_STOPPED)
        self.assertIn("STOPPED", err)
        self.assertIn("--allow-mismatch", err)
        self.assertFalse(wrote)
        self.assertNotIn("stage 5: running", out)

    def test_override_lets_it_through_with_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp, export_tables=_UNRELATED_EXPORT)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5", "--allow-mismatch"])
            wrote = os.path.exists(os.path.join(sheet_dir, "stage5_join.jsonl"))
        self.assertEqual(code, 0, msg=err)
        self.assertIn("WARNING: pairing check", out)
        self.assertIn("--allow-mismatch was given", out)
        self.assertTrue(wrote)

    def test_no_export_in_folder_warns_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _workspace(tmp, export_tables=None)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5"])
            meta = _meta(sheet_dir)
        self.assertEqual(code, 0, msg=err)
        self.assertIn("WARNING: pairing check could not decide", out)
        self.assertEqual(meta["tabPairing"], "by-table-name-fallback")


def _checkup_workspace(tmp, with_app_results=True):
    """Like _workspace, but holding a workbook the formula checkup can judge:
    table T reads tab T, whose column F holds one matching and one differing
    formula against the stored formula."""
    input_dir = os.path.join(tmp, "apps", "Test")
    os.makedirs(input_dir)
    formulas_doc, values_doc = build_capture_from_tabs({"T": scenario_rows(["same", "same", "same", "diff"])})
    write_pair(input_dir, formulas_doc, values_doc)
    cols = column_rows("T", ["Key", "F"], formulas={"F": STORED})
    write_export_html(
        input_dir, [("T", "T", "google")],
        columns={"T": [(r["column_name"], False, False) for r in cols]},
    )
    app_dir = os.path.join(tmp, "output", "Test", "app")
    if with_app_results:
        os.makedirs(app_dir)
        write_formula_columns_csv(app_dir, cols)
        write_tables_csv(app_dir, [("T", "ALL_CHANGES")])
    return input_dir, app_dir, os.path.join(tmp, "output", "Test", "sheet")


class TestRunStage6(unittest.TestCase):
    def test_the_default_run_includes_stage_6_after_stage_5(self):
        self.assertEqual(run.ALL_STAGES, (0, 1, 2, 3, 4, 5, 6))
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _checkup_workspace(tmp)
            code, out, err = _main([input_dir, sheet_dir])
            lines = list(read_jsonl(os.path.join(sheet_dir, "stage6_formula_checkup.jsonl")))
            csv_exists = os.path.exists(os.path.join(sheet_dir, "stage6_formula_checkup.csv"))
        self.assertEqual(code, 0, msg=err)
        self.assertLess(out.index("stage 5: running"), out.index("stage 6: running"))
        self.assertIn("stage 6: wrote", out)
        self.assertTrue(csv_exists)
        self.assertTrue(lines[0]["present"])
        self.assertEqual(lines[0]["examined"], 1)
        self.assertEqual(lines[0]["raisedLikely"], 1)
        self.assertEqual([l["situation"] for l in lines if l["kind"] == "column"], ["S2B"])

    def test_stage_6_alone_finds_the_app_side_results_and_runs_what_it_needs(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, app_dir, sheet_dir = _checkup_workspace(tmp)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "6"])
            present = next(iter(read_jsonl(os.path.join(sheet_dir, "stage6_formula_checkup.jsonl"))))["present"]
            wrote_stage5 = os.path.exists(os.path.join(sheet_dir, "stage5_join.jsonl"))
        self.assertEqual(code, 0, msg=err)
        self.assertIn(f"app-side results: using {app_dir}", out)
        self.assertTrue(present)
        self.assertFalse(wrote_stage5)  # stage 5 was computed for stage 6, not written

    def test_without_app_side_results_stage_6_is_absent_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, _, sheet_dir = _checkup_workspace(tmp, with_app_results=False)
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5,6"])
            meta = next(iter(read_jsonl(os.path.join(sheet_dir, "stage6_formula_checkup.jsonl"))))
        self.assertEqual(code, 0)
        self.assertFalse(meta["present"])
        self.assertIn("stage 6 (the formula checkup) will be ABSENT", err)
        self.assertIn("stage 6's formula checkup is ABSENT", err)

    def test_an_older_app_side_folder_without_the_tables_file_is_said_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir, app_dir, sheet_dir = _checkup_workspace(tmp)
            os.remove(os.path.join(app_dir, "appsheet_tables.csv"))
            code, out, err = _main([input_dir, sheet_dir, "--stages", "5,6"])
            meta = next(iter(read_jsonl(os.path.join(sheet_dir, "stage6_formula_checkup.jsonl"))))
        self.assertEqual(code, 0, msg=err)
        self.assertFalse(meta["appsheetTablesCsvFound"])
        self.assertIn("appsheet_tables.csv is absent", meta["appsheetTablesCsvNote"])
        self.assertIn("appsheet_tables.csv is absent", out)

    def test_stage_numbers_up_to_6_are_accepted_and_7_is_not(self):
        self.assertEqual(run._parse_stages("6,5"), (5, 6))
        with self.assertRaises(ValueError):
            run._parse_stages("7")


if __name__ == "__main__":
    unittest.main()
