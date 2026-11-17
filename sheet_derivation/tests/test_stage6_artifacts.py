import csv
import os
import tempfile
import unittest

from .. import stage6
from ..jsonl_io import read_jsonl
from ..stage6_artifacts import CSV_NAME, JSONL_NAME, tier_counts, write_stage6_artifacts
from .stage6_support import STORED, column_rows, make_inputs, run_checkup, scenario_rows

PLACEHOLDER = '"COMPUTED_VALUE"'


def _busy():
    """Raised, minor and not-a-problem findings, a placeholder, an uncompared
    cell and an unpaired stored-formula column, all in one workbook."""
    names = ["Key", "A1", "B2", "C3", "D4", "Ghost"]
    cols = column_rows("T", names, formulas={"B2": STORED, "C3": PLACEHOLDER, "D4": STORED, "Ghost": "RC[-1]"})
    rows = [
        names[:5],
        ["k2", ("=A2+1", 1), ("=B2+1", 1), 7, ("={1,2}", "")],
        ["k3", ("=A3+1", 1), ("=B3+2", 1), 7, ("=D3+1", 1)],
    ]
    return run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")])


class TestArtifactFiles(unittest.TestCase):
    def _write(self, result):
        out = tempfile.mkdtemp()
        return write_stage6_artifacts(result, out)

    def test_jsonl_has_meta_then_columns_then_not_examined_then_residue(self):
        result = _busy()
        lines = list(read_jsonl(self._write(result)["checkup"]))
        kinds = [l["kind"] for l in lines]
        self.assertEqual(kinds[0], "meta")
        self.assertEqual(kinds.count("meta"), 1)
        order = {"meta": 0, "column": 1, "not-examined": 2, "residue": 3}
        self.assertEqual(kinds, sorted(kinds, key=order.get))
        self.assertEqual(kinds.count("column"), len(result.checkup.findings))
        self.assertEqual(kinds.count("not-examined"), len(result.checkup.not_examined))
        self.assertEqual(kinds.count("residue"), len(result.checkup.residue))
        self.assertGreater(kinds.count("column"), 0)
        self.assertEqual(kinds.count("not-examined"), 1)
        self.assertEqual(kinds.count("residue"), 1)

    def test_meta_states_what_the_artifact_rests_on(self):
        result = _busy()
        meta = next(iter(read_jsonl(self._write(result)["checkup"])))
        self.assertTrue(meta["present"])
        self.assertTrue(meta["appsheetTablesCsvFound"])
        self.assertTrue(meta["reliabilityCondition"])
        self.assertTrue(meta["toolCommit"])
        self.assertEqual(meta["captureDate"], result.checkup.stamp.capture_date)
        self.assertIn("DERIVED", meta["csvProjection"])
        self.assertIn("appsheet_columns.csv", meta["inputFileHashes"])
        self.assertIn("appsheet_tables.csv", meta["inputFileHashes"])
        self.assertEqual(meta["notExaminedCount"], 1)

    def test_tier_counts_add_up_to_the_examined_columns(self):
        result = _busy()
        counts = tier_counts(result.checkup)
        self.assertEqual(
            counts["raised"] + counts["minor"] + counts["notAProblem"] + counts["runProblem"], counts["examined"]
        )
        self.assertEqual(counts["raised"], counts["raisedLikely"] + counts["raisedPossible"])
        meta = next(iter(read_jsonl(self._write(result)["checkup"])))
        for key, value in counts.items():
            self.assertEqual(meta[key], value)

    def test_the_column_that_agrees_is_listed_too(self):
        result = _busy()
        lines = [l for l in read_jsonl(self._write(result)["checkup"]) if l["kind"] == "column"]
        agrees = [l for l in lines if l["situation"] == "S6"]
        self.assertEqual([l["column"] for l in agrees], ["D4"])  # one match, one uncompared cell
        self.assertEqual(agrees[0]["uncomparedRowCount"], 1)
        self.assertEqual(agrees[0]["tier"], "not a problem")

    def test_a_column_line_carries_what_the_prompt_asks_for(self):
        result = _busy()
        lines = [l for l in read_jsonl(self._write(result)["checkup"]) if l["kind"] == "column"]
        b2 = next(l for l in lines if l["column"] == "B2")
        for key in (
            "table", "column", "tab", "sheetColumn", "updateModeAsExported", "addsAllowed", "editsAllowed",
            "settingAssumed", "rowBasis", "countedRows", "countedRowCount", "matchingRows", "matchingRowCount",
            "differingGroups", "differingRowCount", "noFormulaRows", "noFormulaRowCount", "uncompared",
            "storedFormula", "situation", "tier", "grade", "rank", "finding", "advice", "byConvention",
        ):
            self.assertIn(key, b2)
        group = b2["differingGroups"][0]
        self.assertEqual(group["rawSheetFormula"], "=B3+2")
        self.assertEqual(group["convertedText"], "RC[-1]+2")
        self.assertEqual(group["rows"], "3")
        self.assertEqual(b2["updateModeAsExported"], "ALL_CHANGES")
        self.assertEqual(b2["storedFormula"], STORED)

    def test_not_examined_line_names_its_reason(self):
        result = _busy()
        (line,) = [l for l in read_jsonl(self._write(result)["checkup"]) if l["kind"] == "not-examined"]
        self.assertEqual((line["table"], line["column"], line["storedFormula"]), ("T", "Ghost", "RC[-1]"))
        self.assertTrue(line["reason"])

    def test_csv_has_one_row_per_examined_and_per_not_examined_column(self):
        result = _busy()
        paths = self._write(result)
        self.assertEqual(os.path.basename(paths["checkup"]), JSONL_NAME)
        self.assertEqual(os.path.basename(paths["checkup_csv"]), CSV_NAME)
        with open(paths["checkup_csv"], newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(result.checkup.findings) + len(result.checkup.not_examined))
        self.assertEqual(sum(1 for r in rows if r["situation"] == "not examined"), 1)
        b2 = next(r for r in rows if r["column"] == "B2")
        self.assertEqual(b2["situation"], "S2A")
        self.assertEqual(b2["storedFormula"], STORED)

    def test_nothing_is_truncated(self):
        long_formula = "=" + "+".join(f"A{r}" for r in range(2, 400))
        cols = column_rows("T", ["Key", "F"], formulas={"F": ""})
        rows = [["Key", "F"], ["k2", (long_formula, 1)]]
        result = run_checkup({"T": rows}, cols, [("T", "ALL_CHANGES")])
        lines = [l for l in read_jsonl(self._write(result)["checkup"]) if l["kind"] == "column"]
        self.assertEqual(lines[0]["differingGroups"][0]["rawSheetFormula"], long_formula)

    def test_absent_artifact_writes_a_meta_line_and_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, _, _ = make_inputs(
                tmp, {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED})
            )
            result = stage6.run_stage6(fpath, vpath, appside_parse_dir=None)
        paths = self._write(result)
        lines = list(read_jsonl(paths["checkup"]))
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0]["present"])
        self.assertTrue(lines[0]["absentReason"])
        self.assertIn("ABSENT", lines[0]["reliabilityCondition"])
        with open(paths["checkup_csv"], newline="", encoding="utf-8") as fh:
            self.assertEqual(list(csv.DictReader(fh)), [])

    def test_rewriting_gives_identical_files(self):
        result = _busy()
        a, b = self._write(result), self._write(result)
        for key in ("checkup", "checkup_csv"):
            with open(a[key], "rb") as fa, open(b[key], "rb") as fb:
                self.assertEqual(fa.read(), fb.read())


if __name__ == "__main__":
    unittest.main()
