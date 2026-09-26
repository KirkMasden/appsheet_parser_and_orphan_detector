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
    build_stage5_appside_rows,
    build_stage5_pair,
    write_appside_columns_csv,
    write_export_html,
    write_pair,
)

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


if __name__ == "__main__":
    unittest.main()
