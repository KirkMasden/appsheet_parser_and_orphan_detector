"""The stage 6 summary file (build stage 5): every field, the empty, absent
and all-not-a-problem cases, grouping and ordering, the record's entries,
no formula texts, and determinism."""

import json
import os
import tempfile
import unittest

from .. import intended, stage6
from ..stage6_artifacts import write_stage6_artifacts
from ..stage6_summary import SUMMARY_NAME, build_summary
from .stage6_support import STORED, column_rows, make_inputs, run_checkup, scenario, scenario_rows

APP = "/appsheet/data/TestApp-123"
CASE_B = ["same", "same", "same", "diff"]
PLACEHOLDER = '"COMPUTED_VALUE"'


def _two_tables():
    """Table A (UPDATES_ONLY, S1 on column P: raised, possible), table B
    (ALL_CHANGES, S2B on column Q: raised, likely; and S3 on column R)."""
    cols = (
        column_rows("A", ["Key", "P"], formulas={"P": ""})
        + column_rows("B", ["Key", "Q", "R"], formulas={"Q": STORED, "R": STORED})
    )
    tabs = {
        "A": [["Key", "P"], ["k2", ("=A2+1", 1)], ["k3", ("=A3+1", 1)]],
        "B": [["Key", "Q", "R"],
              ["k2", ("=A2+1", 1), 5], ["k3", ("=A3+1", 1), 5], ["k4", ("=A4+1", 1), 5], ["k5", ("=A5+2", 1), 5]],
    }
    return tabs, cols, [("A", "UPDATES_ONLY"), ("B", "ALL_CHANGES")]


class TestFields(unittest.TestCase):
    def test_header_fields(self):
        result = scenario(CASE_B, app_folder=APP)
        s = build_summary(result)
        self.assertEqual(s["kind"], "formula-checkup-summary")
        self.assertIn("DERIVED", s["derivedFrom"])
        self.assertIn("stage6_formula_checkup.jsonl", s["derivedFrom"])
        self.assertTrue(s["present"])
        self.assertIsNone(s["absentReason"])
        self.assertEqual(s["appName"], "TestApp")
        self.assertEqual(s["captureDate"], result.checkup.stamp.capture_date)
        self.assertEqual(s["toolCommit"], result.checkup.stamp.tool_commit)
        self.assertTrue(s["appsheetTablesCsv"]["found"])
        self.assertEqual(s["intendedRecord"]["state"], "no file")

    def test_missing_tables_file_and_unnamed_app_are_stated(self):
        s = build_summary(scenario(CASE_B, mode=None))
        self.assertFalse(s["appsheetTablesCsv"]["found"])
        self.assertIn("appsheet_tables.csv is absent", s["appsheetTablesCsv"]["note"])
        self.assertIsNone(s["appName"])
        self.assertEqual(s["intendedRecord"]["state"], "app name not derivable")

    def test_counts_and_raised_items(self):
        s = build_summary(scenario(CASE_B, app_folder=APP))
        c = s["counts"]
        self.assertEqual(
            (c["examined"], c["raised"], c["raisedLikely"], c["raisedPossible"], c["minor"], c["notAProblem"],
             c["runProblem"], c["notExamined"], c["intended"], c["lapsedDeclarations"], c["notAppliedEntries"],
             c["orphanEntries"]),
            (1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        )
        (item,) = s["raised"]
        self.assertEqual(
            (item["rank"], item["table"], item["column"], item["tab"], item["sheetColumn"], item["situation"],
             item["grade"], item["rows"], item["declarationLapsed"]),
            (1, "T", "F", "T", "B", "S2B", "likely", "5", None),
        )
        self.assertIn("matches 3 of the 4 counted rows", item["finding"])
        self.assertIn("only when every cell agrees", item["advice"])

    def test_rows_that_matter(self):
        s2a = build_summary(scenario(["same", "diff", "diff", "none"]))["raised"][0]
        self.assertEqual(s2a["rows"], "3-5")  # the differing rows and the row without a formula, together
        s1 = build_summary(scenario(["same", "none", "diff", "blank"], stored=""))["raised"][0]
        self.assertEqual(s1["rows"], "2, 4")  # the formula rows
        s3 = build_summary(scenario(["none", "none"]))["raised"][0]
        self.assertEqual(s3["situation"], "S3")
        self.assertEqual(s3["rows"], "")
        s4 = build_summary(scenario(["same", "none"], PLACEHOLDER))["raised"][0]
        self.assertEqual((s4["situation"], s4["grade"], s4["rows"]), ("S4", "possible", ""))

    def test_run_problems_and_not_examined(self):
        cols = column_rows("T", ["Key", "F", "Ghost"], formulas={"F": STORED, "Ghost": "RC[-1]"})
        rows = [["Key", "F"], ["k2", ("={1,2}", "")], ["k3", ("={1,2}", "")]]
        s = build_summary(run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")]))
        (rp,) = s["runProblems"]
        self.assertEqual((rp["table"], rp["column"]), ("T", "F"))
        self.assertTrue(rp["reason"])
        (ne,) = s["notExamined"]
        self.assertEqual((ne["table"], ne["column"]), ("T", "Ghost"))
        self.assertIn("no header label", ne["reason"])
        self.assertEqual((s["counts"]["runProblem"], s["counts"]["notExamined"]), (1, 1))
        self.assertEqual(s["raised"], [])  # a run problem is not a finding

    def test_no_formula_text_anywhere(self):
        rows = [["Key", "F"], ["k2", ("=A2+7+LEN(\"secretword\")", 1)], ["k3", ("=A3+1", 1)]]
        cols = column_rows("T", ["Key", "F"], formulas={"F": "RC[-1]*99+LEN(\"othersecret\")"})
        text = json.dumps(build_summary(run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")], app_folder=APP)))
        for forbidden in ("secretword", "othersecret", "RC[-1]", "=A2", "=A3", "LEN("):
            self.assertNotIn(forbidden, text)


class TestEmptyAbsentAndQuiet(unittest.TestCase):
    def test_an_empty_checkup(self):
        s = build_summary(scenario(["none", "none", "blank"], stored=""))
        self.assertTrue(s["present"])
        self.assertEqual(s["counts"]["examined"], 0)
        for key in ("raised", "raisedGroups", "minor", "runProblems", "notExamined", "intended", "lapsed",
                    "notApplied", "orphanEntries"):
            self.assertEqual(s[key], [], msg=key)

    def test_an_absent_app_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, _, _ = make_inputs(
                tmp, {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED})
            )
            s = build_summary(stage6.run_stage6(fpath, vpath, appside_parse_dir=None))
        self.assertFalse(s["present"])
        self.assertTrue(s["absentReason"])
        self.assertEqual(s["counts"]["examined"], 0)
        self.assertEqual(s["raised"], [])

    def test_only_not_a_problem_findings(self):
        s = build_summary(scenario(["same", "same", "same"]))
        self.assertEqual(s["counts"]["examined"], 1)
        self.assertEqual(s["counts"]["notAProblem"], 1)
        self.assertEqual((s["raised"], s["raisedGroups"], s["minor"], s["runProblems"]), ([], [], [], []))
        self.assertNotIn("not a problem", json.dumps(s["raised"]))  # nothing about it is listed


class TestGroupingAndOrder(unittest.TestCase):
    def test_raised_items_follow_stage_6s_rank_and_groups_follow_the_best_rank(self):
        tabs, cols, tables = _two_tables()
        result = run_checkup(tabs, cols, tables)
        s = build_summary(result)
        # Stage 6's order is by the judgment table's priority, not by table name: S3 with adds (3) and
        # S2B with adds (4) come before S1 with edits only (5), though table A sorts before table B.
        self.assertEqual(
            [(i["rank"], i["table"], i["column"]) for i in s["raised"]], [(1, "B", "R"), (2, "B", "Q"), (3, "A", "P")]
        )
        self.assertEqual([(g["table"], g["situation"]) for g in s["raisedGroups"]], [("B", "S3"), ("B", "S2B"), ("A", "S1")])
        self.assertEqual([g["bestRank"] for g in s["raisedGroups"]], [1, 2, 3])
        self.assertEqual(
            [(i["rank"], i["table"], i["column"]) for i in s["raised"]],
            [(f.rank, f.table, f.column) for f in sorted(
                (f for f in result.checkup.findings if f.rank is not None), key=lambda f: f.rank)],
        )

    def test_a_group_holds_the_columns_with_one_table_situation_and_grade(self):
        names = ["Key", "A1", "B2", "C3", "D4"]
        cols = column_rows("T", names)
        rows = [names] + [[f"k{r}", (f"=A{r}+1", 1), (f"=B{r}+1", 1), (f"=A{r}*3", 1), (f"=D{r}+1", 1)] for r in (2, 3)]
        s = build_summary(run_checkup({"T": rows}, cols, [("T", "UPDATES_ONLY")]))
        (g,) = s["raisedGroups"]
        self.assertEqual((g["table"], g["situation"], g["grade"], g["count"]), ("T", "S1", "possible", 4))
        self.assertEqual(g["columns"], ["A1", "B2", "C3", "D4"])  # in rank order, which is sheet order on a tie
        self.assertEqual([i["rank"] for i in s["raised"]], [1, 2, 3, 4])

    def test_same_table_and_situation_but_a_different_grade_are_separate_groups(self):
        # A table that allows adds: S1 is likely; S4 is possible.
        names = ["Key", "A1", "B2"]
        cols = column_rows("T", names, formulas={"B2": PLACEHOLDER})
        rows = [names, ["k2", ("=A2+1", 1), ("=A2+1", 1)], ["k3", ("=A3+1", 1), 5]]
        s = build_summary(run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")]))
        self.assertEqual([(g["situation"], g["grade"]) for g in s["raisedGroups"]], [("S1", "likely"), ("S4", "possible")])

    def test_minor_groups_by_table_and_situation_with_their_statement(self):
        names = ["Key", "A1", "B2", "C3"]
        cols = column_rows("T", names, formulas={"A1": STORED, "B2": STORED, "C3": STORED})
        rows = [names,
                ["k2", ("=A2+2", 1), ("=B2+2", 1), 5],
                ["k3", ("=A3+2", 1), ("=B3+2", 1), 5]]
        s = build_summary(run_checkup({"T": rows}, cols, [("T", "READ_ONLY")]))
        self.assertEqual(s["raised"], [])
        self.assertEqual([(g["situation"], g["count"], g["columns"]) for g in s["minor"]],
                         [("S2A", 2, ["A1", "B2"]), ("S3", 1, ["C3"])])
        g = s["minor"][0]
        self.assertEqual((g["table"], g["updateMode"], g["tableAllows"], g["settingAssumed"]), ("T", "READ_ONLY", "neither", False))
        self.assertEqual(g["declarationLapsed"], [])
        self.assertIn("differ from the sheet", g["statement"])
        self.assertIn("neither adds nor edits", g["statement"])
        self.assertIn("no trouble now", g["statement"])

    def test_minor_with_edits_only_and_an_assumed_setting(self):
        s = build_summary(scenario(["same", "diff"], mode="UPDATES_ONLY"))
        self.assertEqual(s["minor"][0]["tableAllows"], "edits-only")
        self.assertIn("2026-11-14", s["minor"][0]["statement"])


class TestRecordEntries(unittest.TestCase):
    def _declare(self, tmp, codes, **kw):
        idir = os.path.join(tmp, "intended")
        sheet = os.path.join(tmp, "sheet0")
        write_stage6_artifacts(scenario(codes, app_folder=APP, **kw), sheet)
        intended.cmd_add(sheet, "T", "F", "on purpose", idir)
        return idir

    def test_a_matched_declaration_is_listed_and_not_among_the_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = self._declare(tmp, CASE_B)
            intended.cmd_add_orphan("TestApp", "view", "Old view", "kept", idir)
            s = build_summary(scenario(CASE_B, app_folder=APP, intended_dir=idir))
        self.assertEqual(s["raised"], [])
        self.assertEqual(s["raisedGroups"], [])
        (i,) = s["intended"]
        self.assertEqual((i["table"], i["column"], i["situation"], i["tier"], i["grade"], i["note"]),
                         ("T", "F", "S2B", "raised", "likely", "on purpose"))
        self.assertRegex(i["dateDeclared"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual((s["counts"]["intended"], s["counts"]["raised"], s["counts"]["orphanEntries"]), (1, 0, 1))
        self.assertEqual(s["intendedRecord"]["state"], "read")
        (o,) = s["orphanEntries"]
        self.assertEqual((o["orphanKind"], o["name"], o["note"]), ("view", "Old view", "kept"))
        self.assertRegex(o["dateDeclared"], r"^\d{4}-\d\d-\d\d$")

    def test_a_lapsed_declaration_is_flagged_on_the_raised_item_and_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = self._declare(tmp, CASE_B)
            s = build_summary(scenario(CASE_B + ["diff"], app_folder=APP, intended_dir=idir))
        (item,) = s["raised"]
        self.assertEqual(item["declarationLapsed"]["note"], "on purpose")
        self.assertRegex(item["declarationLapsed"]["dateDeclared"], r"^\d{4}-")
        self.assertEqual(s["intended"], [])
        (lapsed,) = s["lapsed"]
        self.assertEqual((lapsed["table"], lapsed["column"]), ("T", "F"))
        self.assertEqual(s["counts"]["lapsedDeclarations"], 1)
        self.assertEqual(s["counts"]["raised"], 1)

    def test_a_lapsed_declaration_on_a_minor_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = self._declare(tmp, ["same", "diff"], mode="READ_ONLY")
            s = build_summary(scenario(["same", "diff", "diff"], mode="READ_ONLY", app_folder=APP, intended_dir=idir))
        self.assertEqual(s["minor"][0]["declarationLapsed"], ["F"])

    def test_an_entry_that_cannot_be_applied_is_listed_with_its_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            intended.write_record(
                intended.record_path("TestApp", idir), "TestApp",
                [{"kind": "checkup", "table": "T", "column": "Gone", "situation": "S1", "rows": "", "declared": "2026-11-01",
                  "note": None, "fingerprint": "x" * 64}],
            )
            s = build_summary(scenario(CASE_B, app_folder=APP, intended_dir=idir))
        (n,) = s["notApplied"]
        self.assertEqual((n["table"], n["column"], n["dateDeclared"]), ("T", "Gone", "2026-11-01"))
        self.assertIn("not among the examined columns", n["reason"])
        self.assertEqual(s["counts"]["notAppliedEntries"], 1)


class TestFileAndDeterminism(unittest.TestCase):
    def test_the_file_is_written_beside_the_others_and_equals_the_built_summary(self):
        result = scenario(CASE_B, app_folder=APP)
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_stage6_artifacts(result, tmp)
            self.assertEqual(os.path.basename(paths["summary"]), SUMMARY_NAME)
            self.assertEqual(os.path.dirname(paths["summary"]), os.path.dirname(paths["checkup"]))
            with open(paths["summary"], encoding="utf-8") as fh:
                text = fh.read()
        self.assertEqual(json.loads(text), build_summary(result))
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "present": true,\n', text)  # indented, readable

    def test_it_is_small(self):
        tabs, cols, tables = _two_tables()
        text = json.dumps(build_summary(run_checkup(tabs, cols, tables)))
        self.assertLess(len(text), 8000)

    def test_writing_twice_gives_identical_bytes_and_an_absent_run_writes_one_too(self):
        result = scenario(CASE_B, app_folder=APP)
        with tempfile.TemporaryDirectory() as tmp:
            a = write_stage6_artifacts(result, os.path.join(tmp, "a"))
            b = write_stage6_artifacts(result, os.path.join(tmp, "b"))
            with open(a["summary"], "rb") as fa, open(b["summary"], "rb") as fb:
                self.assertEqual(fa.read(), fb.read())
            fpath, vpath, _, _ = make_inputs(
                tmp, {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED})
            )
            absent = write_stage6_artifacts(stage6.run_stage6(fpath, vpath), os.path.join(tmp, "c"))
            with open(absent["summary"], encoding="utf-8") as fh:
                self.assertFalse(json.load(fh)["present"])

    def test_same_process_determinism(self):
        from ..determinism import verify_same_process_determinism
        tabs, cols, tables = _two_tables()
        verify_same_process_determinism(lambda: build_summary(run_checkup(tabs, cols, tables)), run_label="summary")


if __name__ == "__main__":
    unittest.main()
