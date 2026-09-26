"""The pairing check over the pasted .txt files (views1.txt, views2.txt,
actions.txt), and the app-side views parser's view count in its log."""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

from .. import pairing, snapshot
from .fixtures import build_stage5_pair, write_export_html, write_pair

# A views paste with system views shown: two section notes and a slice
# group heading that are not views, and three real views -- one with a
# position, one dashboard (a "Type:" line and no "Data:"), one system view.
VIEWS_WITH_SYSTEM = """Primary Views
These views are accessed via the bottom bar of the app. Views that are used often should be in this section.
Home
firstData: HomeType: deck
Menu Views
These views are accessed via the menu at the top left of the app. Views that are used only occasionally should be in this section.
Search all
Type: dashboard
Ref Views
Things (slice)
Things_Detail
Data: ThingsType: detail
"""
# The same paste with system views hidden.
VIEWS_WITHOUT_SYSTEM = """Primary Views
These views are accessed via the bottom bar of the app. Views that are used often should be in this section.
Home
firstData: HomeType: deck
Menu Views
These views are accessed via the menu at the top left of the app. Views that are used only occasionally should be in this section.
Search all
Type: dashboard
"""
# Narrow layout (name, then its line) and wide layout (one line); a table
# heading; system-generated actions, which the check leaves out.
ACTIONS = """Actions are operations that can modify data in your app
Things
Add
System generated
Edit
System generated
Go to home
Effect: App: go to another view within this app
Mark done Effect: Data: set the values of some columns in this row
"""
EXPORT_VIEWS = ["Home", "Search all", "Things_Detail"]
EXPORT_ACTIONS = ["Add", "Edit", "Go to home", "Mark done"]


def _write(folder, name, text):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        fh.write(text)


def _folder(tmp, views1=VIEWS_WITH_SYSTEM, views2=VIEWS_WITHOUT_SYSTEM, actions=ACTIONS,
            export_views=EXPORT_VIEWS, export_actions=EXPORT_ACTIONS):
    formulas_doc, values_doc = build_stage5_pair()
    write_pair(tmp, formulas_doc, values_doc)
    write_export_html(tmp, [("Ledger", "Ledger", "google")], views=export_views, actions=export_actions)
    _write(tmp, "views1.txt", views1)
    _write(tmp, "views2.txt", views2)
    _write(tmp, "actions.txt", actions)
    return tmp


class TestTxtReaders(unittest.TestCase):
    def test_view_names_skip_notes_and_slice_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "v.txt", VIEWS_WITH_SYSTEM)
            names = pairing.read_view_names_txt(os.path.join(tmp, "v.txt"))
        self.assertEqual(names, ("Home", "Search all", "Things_Detail"))

    def test_action_names_are_user_created_only_in_both_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "a.txt", ACTIONS)
            names = pairing.read_user_action_names_txt(os.path.join(tmp, "a.txt"))
        self.assertEqual(names, ("Go to home", "Mark done"))


class TestTxtPairing(unittest.TestCase):
    def _results(self, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            return {r.kind: r for r in pairing.check_txt_pairing(_folder(tmp, **kwargs))}

    def test_matching_files(self):
        r = self._results()
        self.assertEqual(r["views"].verdict, pairing.VERDICT_MATCH)
        self.assertEqual(r["actions"].verdict, pairing.VERDICT_MATCH)
        self.assertEqual(pairing.format_txt_pairing(r["views"])[0],
                         "Pairing check: all 3 view name(s) in views1.txt and views2.txt appear in the export.")

    def test_whitespace_collapsed_by_the_paste_still_matches(self):
        r = self._results(export_views=["Home", "Search  all", "Things_Detail"])
        self.assertEqual(r["views"].verdict, pairing.VERDICT_MATCH)

    def test_some_unmatched_warns_with_examples(self):
        r = self._results(export_actions=["Go to home"])
        self.assertEqual(r["actions"].verdict, pairing.VERDICT_PARTIAL)
        self.assertEqual(r["actions"].unmatched, ("Mark done",))
        line = pairing.format_txt_pairing(r["actions"])[0]
        self.assertTrue(line.startswith("WARNING"))
        self.assertIn("'Mark done'", line)

    def test_none_matched_stops(self):
        r = self._results(export_views=["Other"], export_actions=["Unrelated"])
        self.assertTrue(r["views"].stops)
        self.assertTrue(r["actions"].stops)
        lines = pairing.format_txt_pairing(r["views"])
        self.assertTrue(lines[0].startswith("STOPPED"))
        self.assertIn(pairing.OVERRIDE_OPTION, "\n".join(lines))

    def test_almost_none_matched_stops(self):
        names = [f"View {i}" for i in range(10)]
        r = pairing.compare_names("views", ("views1.txt",), tuple(names), ("View 0",))
        self.assertEqual(r.verdict, pairing.VERDICT_NONE)  # 1 of 10 < 20%

    def test_one_in_five_is_a_warning_not_a_stop(self):
        names = [f"View {i}" for i in range(10)]
        r = pairing.compare_names("views", ("views1.txt",), tuple(names), ("View 0", "View 1"))
        self.assertEqual(r.verdict, pairing.VERDICT_PARTIAL)  # 2 of 10 = 20%

    def test_override_warns(self):
        r = self._results(export_views=["Other"])
        line = pairing.format_txt_pairing(r["views"], allow_mismatch=True)[0]
        self.assertTrue(line.startswith("WARNING"))
        self.assertIn(pairing.OVERRIDE_OPTION, line)


class TestInputFolderCheckCoversTxt(unittest.TestCase):
    def _main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = snapshot.main(argv)
        return code, out.getvalue()

    def test_matching_folder_prints_three_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._main([_folder(tmp)])
        self.assertEqual(code, 0)
        self.assertEqual(out.count("Pairing check: all"), 3)

    def test_foreign_txt_files_stop_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._main([_folder(tmp, export_views=["Other"], export_actions=["Unrelated"])])
        self.assertEqual(code, snapshot.EXIT_PAIRING_STOPPED)
        self.assertIn("STOPPED", out)

    def test_override_lets_foreign_txt_files_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._main([_folder(tmp, export_views=["Other"]), "--allow-mismatch"])
        self.assertEqual(code, 0)
        self.assertNotIn("STOPPED", out)


@unittest.skipUnless(importlib.util.find_spec("bs4"), "beautifulsoup4 not installed; the app-side parser needs it")
class TestViewCountInLog(unittest.TestCase):
    def _load(self, views1, views2):
        import views_parser
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "views1.txt", views1)
            _write(tmp, "views2.txt", views2)
            _write(tmp, "Application Documentation.html", "<html><body></body></html>")
            parser = views_parser.ViewsParser(html_path=os.path.join(tmp, "Application Documentation.html"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                parser.load_views_text_mapping()
        return parser, out.getvalue()

    def test_log_counts_only_real_views(self):
        _, log = self._load(VIEWS_WITH_SYSTEM, VIEWS_WITHOUT_SYSTEM)
        self.assertIn("Found views1.txt (3 views) and views2.txt (2 views)", log)
        self.assertIn("Found 1 system views and 2 user views", log)

    def test_swapped_files_are_still_detected(self):
        _, log = self._load(VIEWS_WITHOUT_SYSTEM, VIEWS_WITH_SYSTEM)
        self.assertIn("Identified views2.txt as containing system views", log)

    def test_mappings_are_unchanged_by_the_count_fix(self):
        parser, _ = self._load(VIEWS_WITH_SYSTEM, VIEWS_WITHOUT_SYSTEM)
        self.assertIn("Things_Detail", parser.system_views)
        self.assertEqual(parser.view_type_map.get("Search all"), "dashboard")


if __name__ == "__main__":
    unittest.main()
