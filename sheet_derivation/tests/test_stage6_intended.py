"""How stage 6 applies the intended-items record: a matching entry, a
lapsed one, one that cannot be applied, no file, no derivable app name, the
meta counts, the CSV column, and determinism with a record present."""

import csv
import os
import tempfile
import unittest

from .. import intended, stage6
from ..jsonl_io import read_jsonl
from ..serialize_stage6 import build_canonical_structure
from ..stage6_artifacts import tier_counts, write_stage6_artifacts
from .stage6_support import STORED, column_rows, finding, run_checkup, scenario, scenario_rows

APP = "/appsheet/data/TestApp-123"
CASE_B = ["same", "same", "same", "diff"]


def _declare(tmp, codes, note="on purpose", stored=STORED, mode="ALL_CHANGES", column="F"):
    """Runs the scenario, writes its artifact, declares `column` intended in
    <tmp>/intended; returns the intended folder."""
    idir = os.path.join(tmp, "intended")
    sheet = os.path.join(tmp, "sheet0")
    write_stage6_artifacts(scenario(codes, stored, mode, app_folder=APP), sheet)
    intended.cmd_add(sheet, "T", column, note, idir)
    return idir


class TestMatchingEntry(unittest.TestCase):
    def test_a_matching_entry_marks_the_column_intended_and_keeps_its_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(CASE_B, app_folder=APP, intended_dir=idir)
        f = finding(result, "T", "F")
        self.assertEqual((f.situation, f.tier, f.grade), (stage6.S2B, stage6.TIER_RAISED, "likely"))
        self.assertEqual(f.intended.note, "on purpose")
        self.assertRegex(f.intended.date_declared, r"^\d{4}-\d\d-\d\d$")
        self.assertIsNone(f.lapsed)
        self.assertIsNone(f.rank)  # an intended finding is not ranked among the raised ones
        self.assertEqual(result.checkup.record_state, stage6.RECORD_READ)
        self.assertEqual(result.checkup.app_name, "TestApp")

    def test_the_meta_counts_exclude_the_intended_column_and_add_intended_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            without = tier_counts(scenario(CASE_B, app_folder=APP).checkup)
            with_record = tier_counts(scenario(CASE_B, app_folder=APP, intended_dir=idir).checkup)
        self.assertEqual((without["raised"], without["raisedLikely"], without["intendedCount"]), (1, 1, 0))
        self.assertEqual((with_record["raised"], with_record["raisedLikely"], with_record["intendedCount"]), (0, 0, 1))
        self.assertEqual(with_record["examined"], without["examined"])

    def test_a_minor_intended_column_drops_the_minor_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, ["same", "diff"], mode="READ_ONLY")
            counts = tier_counts(scenario(["same", "diff"], mode="READ_ONLY", app_folder=APP, intended_dir=idir).checkup)
        self.assertEqual((counts["minor"], counts["intendedCount"]), (0, 1))

    def test_the_column_line_and_csv_say_intended(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(CASE_B, app_folder=APP, intended_dir=idir)
            out = os.path.join(tmp, "out")
            paths = write_stage6_artifacts(result, out)
            lines = list(read_jsonl(paths["checkup"]))
            with open(paths["checkup_csv"], newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        meta, col = lines[0], lines[1]
        self.assertEqual(col["intended"]["note"], "on purpose")
        self.assertIsNone(col["intendedLapsed"])
        self.assertEqual(col["tier"], "raised")
        self.assertEqual(rows[0]["intended"], "yes")
        self.assertEqual(meta["intendedCount"], 1)
        self.assertEqual(meta["raised"], 0)
        self.assertEqual(meta["intendedRecord"]["state"], "read")
        self.assertTrue(meta["intendedRecord"]["file"].endswith("TestApp.json"))
        self.assertEqual(meta["appName"], "TestApp")
        self.assertEqual(meta["intendedLapsed"], [])
        self.assertEqual(meta["intendedNotApplied"], [])

    def test_an_added_normal_row_does_not_lapse_the_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(CASE_B + ["same", "same"], app_folder=APP, intended_dir=idir)
        self.assertIsNotNone(finding(result, "T", "F").intended)

    def test_only_the_declared_column_is_marked(self):
        names = ["Key", "A1", "B2"]
        cols = column_rows("T", names, formulas={"A1": STORED, "B2": STORED})
        rows = [names, ["k2", ("=A2+2", 1), ("=A2+2", 1)], ["k3", ("=A3+2", 1), ("=A3+2", 1)]]  # both differ from STORED
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            first = run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")], app_folder=APP)
            sheet = os.path.join(tmp, "s")
            write_stage6_artifacts(first, sheet)
            intended.cmd_add(sheet, "T", "B2", None, idir)
            second = run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")], app_folder=APP, intended_dir=idir)
        self.assertIsNone(finding(second, "T", "A1").intended)
        self.assertIsNotNone(finding(second, "T", "B2").intended)
        self.assertEqual(finding(second, "T", "A1").rank, 1)
        self.assertEqual(finding(first, "T", "A1").tier, finding(second, "T", "A1").tier)


class TestLapsedEntry(unittest.TestCase):
    def test_a_changed_finding_lapses_the_entry_and_counts_as_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(CASE_B + ["diff"], app_folder=APP, intended_dir=idir)  # a second odd row
            out = os.path.join(tmp, "out")
            paths = write_stage6_artifacts(result, out)
            lines = list(read_jsonl(paths["checkup"]))
            with open(paths["checkup_csv"], newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        f = finding(result, "T", "F")
        self.assertIsNone(f.intended)
        self.assertEqual(f.lapsed.note, "on purpose")
        self.assertEqual(f.rank, 1)  # raised and ranked as new
        self.assertTrue(any("has lapsed" in n for n in f.notes))
        meta, col = lines[0], lines[1]
        self.assertEqual((meta["raised"], meta["intendedCount"]), (1, 0))
        self.assertEqual(len(meta["intendedLapsed"]), 1)
        self.assertEqual(meta["intendedLapsed"][0]["column"], "F")
        self.assertEqual(col["intendedLapsed"]["note"], "on purpose")
        self.assertIsNone(col["intended"])
        self.assertEqual(rows[0]["intended"], "lapsed declaration")

    def test_a_changed_stored_formula_lapses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(CASE_B, stored="RC[-1]+9", app_folder=APP, intended_dir=idir)
        self.assertIsNotNone(finding(result, "T", "F").lapsed)

    def test_a_finding_that_went_away_lapses_it_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            result = scenario(["same", "same", "same", "same"], app_folder=APP, intended_dir=idir)
        f = finding(result, "T", "F")
        self.assertEqual(f.situation, stage6.S6)
        self.assertIsNotNone(f.lapsed)
        self.assertEqual(tier_counts(result.checkup)["notAProblem"], 1)


class TestEntryThatCannotBeApplied(unittest.TestCase):
    def _record_with(self, tmp, table, column):
        idir = os.path.join(tmp, "i")
        intended.write_record(
            intended.record_path("TestApp", idir), "TestApp",
            [{"kind": "checkup", "table": table, "column": column, "situation": "S1", "rows": "", "declared": "2026-11-01",
              "note": None, "fingerprint": "x" * 64}],
        )
        return idir

    def test_a_column_that_is_not_examined_is_listed_with_the_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = self._record_with(tmp, "T", "Nowhere")
            result = scenario(CASE_B, app_folder=APP, intended_dir=idir)
            lines = list(read_jsonl(write_stage6_artifacts(result, os.path.join(tmp, "o"))["checkup"]))
        (item,) = lines[0]["intendedNotApplied"]
        self.assertEqual((item["table"], item["column"], item["dateDeclared"]), ("T", "Nowhere", "2026-11-01"))
        self.assertIn("not among the examined columns", item["reason"])
        self.assertEqual(lines[0]["intendedCount"], 0)
        self.assertEqual(lines[0]["raised"], 1)  # the real finding is unaffected

    def test_a_not_examined_column_says_why(self):
        cols = column_rows("T", ["Key", "F", "Ghost"], formulas={"F": STORED, "Ghost": "RC[-1]"})
        with tempfile.TemporaryDirectory() as tmp:
            idir = self._record_with(tmp, "T", "Ghost")
            rows = scenario_rows(CASE_B)
            result = run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")], app_folder=APP, intended_dir=idir)
        (item,) = result.checkup.not_applied_entries
        self.assertIn("listed as not examined", item[3])


class TestRecordStates(unittest.TestCase):
    def test_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scenario(CASE_B, app_folder=APP, intended_dir=os.path.join(tmp, "none"))
        self.assertEqual(result.checkup.record_state, stage6.RECORD_NO_FILE)
        self.assertIn("no intended-items record exists", result.checkup.record_note)
        self.assertEqual(tier_counts(result.checkup)["raised"], 1)

    def test_no_derivable_app_name_reads_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            for folder in (None, "/appsheet/data/NoDigits"):
                with self.subTest(folder=folder):
                    result = scenario(CASE_B, app_folder=folder, intended_dir=idir)
                    self.assertEqual(result.checkup.record_state, stage6.RECORD_NO_APP_NAME)
                    self.assertIsNone(result.checkup.app_name)
                    self.assertIn("could not be derived", result.checkup.record_note)
                    self.assertIsNone(finding(result, "T", "F").intended)

    def test_an_unreadable_record_is_reported_and_the_run_goes_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            os.makedirs(idir)
            with open(os.path.join(idir, "TestApp.json"), "w", encoding="utf-8") as fh:
                fh.write("[]")
            result = scenario(CASE_B, app_folder=APP, intended_dir=idir)
        self.assertEqual(result.checkup.record_state, stage6.RECORD_UNREADABLE)
        self.assertTrue(result.checkup.present)
        self.assertEqual(tier_counts(result.checkup)["raised"], 1)

    def test_orphan_entries_are_counted_and_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            intended.cmd_add_orphan("TestApp", "view", "Some view", None, idir)
            intended.cmd_add_orphan("TestApp", "slice", "Some slice", "n", idir)
            result = scenario(CASE_B, app_folder=APP, intended_dir=idir)
            meta = next(iter(read_jsonl(write_stage6_artifacts(result, os.path.join(tmp, "o"))["checkup"])))
        self.assertEqual(meta["orphanEntryCount"], 2)
        self.assertEqual(meta["intendedCount"], 1)

    def test_stage_6_never_writes_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "never")
            scenario(CASE_B, app_folder=APP, intended_dir=idir)
            self.assertFalse(os.path.exists(idir))
            idir = _declare(tmp, CASE_B)
            path = intended.record_path("TestApp", idir)
            with open(path, "rb") as fh:
                before = fh.read()
            scenario(CASE_B + ["diff"], app_folder=APP, intended_dir=idir)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)


class TestDeterminismWithARecord(unittest.TestCase):
    def test_same_inputs_and_record_give_identical_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = _declare(tmp, CASE_B)
            intended.cmd_add_orphan("TestApp", "view", "Some view", None, idir)
            a = build_canonical_structure(scenario(CASE_B, app_folder=APP, intended_dir=idir))
            b = build_canonical_structure(scenario(CASE_B, app_folder=APP, intended_dir=idir))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
