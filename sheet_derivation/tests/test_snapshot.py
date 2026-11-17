"""The input-folder check (python -m sheet_derivation.snapshot): file
listing plus the export/capture pairing check."""

import contextlib
import io
import os
import tempfile
import unittest

from .. import snapshot
from .fixtures import build_stage5_pair, write_export_html, write_pair


def _folder(tmp, export_tables):
    formulas_doc, values_doc = build_stage5_pair()
    write_pair(tmp, formulas_doc, values_doc)
    if export_tables is not None:
        write_export_html(tmp, export_tables)
    return tmp


def _main(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = snapshot.main(argv)
    return code, out.getvalue()


class TestInputFolderPairing(unittest.TestCase):
    def test_matching_folder_confirms_in_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([_folder(tmp, [("Ledger", "Ledger", "google")])])
        self.assertEqual(code, 0)
        self.assertIn("Pairing check: all 1", out)

    def test_unrelated_capture_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([_folder(tmp, [("Orders", "Order sheet", "google")])])
        self.assertEqual(code, snapshot.EXIT_PAIRING_STOPPED)
        self.assertIn("STOPPED", out)

    def test_override_warns_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([_folder(tmp, [("Orders", "Order sheet", "google")]), "--allow-mismatch"])
        self.assertEqual(code, 0)
        self.assertIn("WARNING: pairing check", out)

    def test_no_export_skips_the_pairing_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([_folder(tmp, None)])
        self.assertEqual(code, 0)
        self.assertNotIn("Pairing check", out)
        self.assertNotIn("pairing check", out)

    def test_report_avoids_the_banned_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, out = _main([_folder(tmp, [("Ledger", "Ledger", "google")])])
        self.assertNotIn("snapshot", out.lower().replace("sheet_derivation.snapshot", ""))


class TestOptionalBotActionsFile(unittest.TestCase):
    def _app_folder(self, tmp, with_bot_file):
        _folder(tmp, [("Ledger", "Ledger", "google")])
        for name in ("actions.txt", "views1.txt", "views2.txt"):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        if with_bot_file:
            with open(os.path.join(tmp, "bot_actions.txt"), "w", encoding="utf-8") as fh:
                fh.write("\nSome action\n")
        return tmp

    def test_found_is_reported_and_not_counted_or_called_unrecognized(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([self._app_folder(tmp, True)])
        self.assertEqual(code, 0)
        self.assertIn("optional: bot_actions.txt: found", out)
        self.assertIn("app-side files: 4/4 found", out)
        self.assertIn("present but not recognized: none", out)
        self.assertNotIn("not found (optional)", out)

    def test_absent_is_reported_as_optional_and_does_not_make_the_folder_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = _main([self._app_folder(tmp, False)])
        self.assertEqual(code, 0)
        self.assertIn("optional: bot_actions.txt: not found (optional)", out)
        self.assertIn("app-side files: 4/4 found", out)
        self.assertIn("Complete: both the app-side export and the sheet capture are present.", out)

    def test_inspection_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = snapshot.inspect_snapshot(self._app_folder(tmp, True))
        self.assertEqual(found.optional_found, ("bot_actions.txt",))
        self.assertEqual(found.optional_missing, ())
        self.assertTrue(found.app_side_complete)
        self.assertEqual(found.unrecognized, ())
        self.assertNotIn("bot_actions.txt", snapshot.APP_SIDE_FILES)


if __name__ == "__main__":
    unittest.main()
