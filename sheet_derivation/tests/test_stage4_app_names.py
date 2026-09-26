"""Stage 4: header rows decided from the app's column names, when the
export names a tab as a Google table's worksheet -- and the unchanged
type-mismatch rule everywhere else."""

import os
import tempfile
import unittest

from .. import stage4, stage5
from ..appside_parse import extract_table_sources
from ..stage4_artifacts import write_stage4_artifacts
from ..jsonl_io import read_jsonl
from .fixtures import (
    CAPTURE_DATE,
    _minimal_formulas_sheet,
    _minimal_values_sheet,
    write_appside_columns_csv,
    write_declarations,
    write_export_html,
    write_pair,
)

# "Words": text labels over text data -- the type-mismatch rule sees no
# signal and reports UNDETERMINED, although row 1 is plainly the header.
WORDS = [
    ["Word", "Meaning", "Note "],  # trailing space on "Note " -- a whitespace near-miss
    ["cat", "a small animal", "common"],
    ["dog", "a loyal animal", "common"],
    ["owl", "a night bird", "rare"],
]
# "Report": two title rows above the real header on row 3.
REPORT = [
    ["Monthly report", "", ""],
    ["prepared by hand", "", ""],
    ["Qty", "Price", "Total"],
    ["one", "two", "three"],
    ["four", "five", "six"],
]
# "Numbers": text row 1 over numeric data (the rule identifies row 1), but
# the app's column names sit on row 2.
NUMBERS = [
    ["x1", "x2", "x3"],
    ["Qty", "Price", "Total"],
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
    [10, 11, 12],
]
# "Loose": a tab no table reads.
LOOSE = [["a", "b"], ["c", "d"]]

WORD_COLUMNS = [
    ("_RowNumber", False, True),  # system-defined: never a sheet header
    ("Word", False, False),
    ("Meaning", False, False),
    ("Note", False, False),
    ("Computed", True, False),  # virtual: never a sheet header
]
QTY_COLUMNS = [("Qty", False, False), ("Price", False, False), ("Total", False, False)]


def _capture(tmp, sheets):
    formulas_doc = {"captureDate": CAPTURE_DATE, "spreadsheetName": "App Names Test", "triggerIds": [], "sheets": []}
    values_doc = {"captureDate": CAPTURE_DATE, "spreadsheetName": "App Names Test", "sheets": []}
    for name, values in sheets.items():
        formulas = [["" for _ in row] for row in values]
        formulas_doc["sheets"].append(_minimal_formulas_sheet(name, formulas))
        values_doc["sheets"].append(_minimal_values_sheet(name, values))
    return write_pair(tmp, formulas_doc, values_doc)


def _run(sheets, export_tables=None, columns=None, declarations=None):
    with tempfile.TemporaryDirectory() as tmp:
        fpath, vpath = _capture(tmp, sheets)
        html = write_export_html(tmp, export_tables, columns=columns) if export_tables is not None else None
        decl = write_declarations(tmp, declarations) if declarations else None
        return stage4.run_stage4(fpath, vpath, decl, app_export_html_path=html)


def _sheet(result, name):
    return next(s for s in result.schema.sheets if s.sheet == name)


class TestExportColumnNames(unittest.TestCase):
    def test_sheet_column_names_exclude_virtual_and_system_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_export_html(tmp, [("Vocab", "Words", "google")], columns={"Vocab": WORD_COLUMNS})
            sources = extract_table_sources(path)
        table = sources.by_table()["Vocab"]
        self.assertEqual(sources.sheet_column_names(table), ("Word", "Meaning", "Note"))

    def test_missing_flag_means_names_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_export_html(
                tmp, [("Vocab", "Words", "google")], columns={"Vocab": [("Word", None, False)]}
            )
            sources = extract_table_sources(path)
        self.assertIsNone(sources.sheet_column_names(sources.by_table()["Vocab"]))


class TestHeaderFromAppNames(unittest.TestCase):
    def test_text_over_text_tab_is_decided_by_app_names(self):
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], {"Vocab": WORD_COLUMNS})
        hd = _sheet(result, "Words").header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_APP_COLUMN_NAMES)
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_IDENTIFIED)
        self.assertEqual(hd.header_row1, 1)
        an = hd.app_names
        self.assertEqual(an.status, stage4.APP_NAMES_DECIDED)
        self.assertEqual(an.table, "Vocab")
        self.assertEqual((an.exact_matches, an.near_misses, an.names_total), (2, 1, 3))
        self.assertEqual(an.rule_verdict, stage4.HEADER_VERDICT_UNDETERMINED)
        self.assertFalse(an.disagrees_with_rule)
        labels = {c.column: c.header_label for c in _sheet(result, "Words").columns}
        self.assertEqual(labels["C"].state, stage4.LABEL_STATE_LABELED)
        self.assertEqual(labels["C"].value, "Note ")  # raw text kept, never repaired

    def test_without_export_the_rule_decides_unchanged(self):
        without = _run({"Words": WORDS})
        hd = _sheet(without, "Words").header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_MEASURED)
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_UNDETERMINED)
        self.assertEqual(hd.app_names.status, stage4.APP_NAMES_NO_EXPORT)  # recorded: the rule decided

    def test_tab_no_table_reads_is_decided_by_the_rule(self):
        result = _run({"Words": WORDS, "Loose": LOOSE}, [("Vocab", "Words", "google")], {"Vocab": WORD_COLUMNS})
        hd = _sheet(result, "Loose").header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_MEASURED)
        self.assertEqual(hd.app_names.status, stage4.APP_NAMES_NOT_A_WORKSHEET)

    def test_below_threshold_leaves_the_rule_in_charge(self):
        columns = {"Vocab": WORD_COLUMNS[:2] + [("Other1", False, False), ("Other2", False, False),
                                                ("Other3", False, False)]}
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], columns)
        hd = _sheet(result, "Words").header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_MEASURED)
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_UNDETERMINED)
        self.assertEqual(hd.app_names.status, stage4.APP_NAMES_BELOW_THRESHOLD)
        self.assertEqual((hd.app_names.matched, hd.app_names.names_total), (1, 4))

    def test_exactly_half_is_not_enough(self):
        columns = {"Vocab": [("Word", False, False), ("Meaning", False, False),
                             ("Other1", False, False), ("Other2", False, False)]}
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], columns)
        self.assertEqual(_sheet(result, "Words").header_detection.app_names.status, stage4.APP_NAMES_BELOW_THRESHOLD)

    def test_header_below_title_rows_is_found(self):
        result = _run({"Report": REPORT}, [("Sales", "Report", "google")], {"Sales": QTY_COLUMNS})
        sheet = _sheet(result, "Report")
        self.assertEqual(sheet.header_detection.header_row1, 3)
        self.assertEqual({c.column: c.header_label.value for c in sheet.columns},
                         {"A": "Qty", "B": "Price", "C": "Total"})

    def test_disagreement_prefers_app_names_and_is_recorded(self):
        result = _run({"Numbers": NUMBERS}, [("Sales", "Numbers", "google")], {"Sales": QTY_COLUMNS})
        hd = _sheet(result, "Numbers").header_detection
        self.assertEqual(hd.header_row1, 2)
        self.assertEqual(hd.app_names.rule_verdict, stage4.HEADER_VERDICT_IDENTIFIED)
        self.assertEqual(hd.app_names.rule_header_row1, 1)
        self.assertTrue(hd.app_names.disagrees_with_rule)
        self.assertIn(
            "app column names and the type-mismatch rule disagree",
            [r.defeating_construct for r in result.schema.residue],
        )

    def test_declared_row_takes_precedence(self):
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], {"Vocab": WORD_COLUMNS},
                      declarations={"Words": 2})
        hd = _sheet(result, "Words").header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_DECLARED)
        self.assertEqual(hd.header_row1, 2)
        self.assertEqual(hd.app_names.status, stage4.APP_NAMES_DECLARED_OVERRIDE)

    def test_names_unavailable_leaves_the_rule_in_charge(self):
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], {"Vocab": [("Word", None, None)]})
        self.assertEqual(_sheet(result, "Words").header_detection.app_names.status, stage4.APP_NAMES_UNAVAILABLE)

    def test_reliability_condition_states_the_app_name_rule(self):
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], {"Vocab": WORD_COLUMNS})
        self.assertIn(stage4.HEADER_SOURCE_APP_COLUMN_NAMES, result.schema.reliability_condition)


class TestArtifactsRecordTheDecision(unittest.TestCase):
    def test_jsonl_and_csv_record_source_and_counts(self):
        result = _run({"Words": WORDS}, [("Vocab", "Words", "google")], {"Vocab": WORD_COLUMNS})
        with tempfile.TemporaryDirectory() as out:
            paths = write_stage4_artifacts(result, out)
            lines = list(read_jsonl(paths["schema"]))
            import csv
            with open(paths["sheet_summary_csv"], newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        sheet_line = next(l for l in lines if l.get("kind") == "sheet" and l["sheet"] == "Words")
        an = sheet_line["headerDetection"]["appColumnNames"]
        self.assertEqual(an["status"], "decided")
        self.assertEqual((an["exactMatches"], an["nearMisses"], an["namesTotal"]), (2, 1, 3))
        row = next(r for r in rows if r["sheet"] == "Words")
        self.assertEqual(row["headerSource"], stage4.HEADER_SOURCE_APP_COLUMN_NAMES)
        self.assertEqual((row["appNamesMatched"], row["appNamesTotal"]), ("3", "3"))


class TestJoinOnAnAppNameHeader(unittest.TestCase):
    def test_near_miss_counts_for_the_header_but_stays_a_near_miss_in_the_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = _capture(tmp, {"Words": WORDS})
            html = write_export_html(tmp, [("Vocab", "Words", "google")], columns={"Vocab": WORD_COLUMNS})
            appside = os.path.join(tmp, "app")
            os.makedirs(appside)
            write_appside_columns_csv(appside, [
                {"table_name": "Vocab", "column_name": n, "is_virtual": "Yes" if v else "No"}
                for n, v, _ in WORD_COLUMNS
            ])
            result = stage5.run_stage5(fpath, vpath, appside, app_export_html_path=html)
        vocab = next(t for t in result.join.tables if t.table == "Vocab")
        self.assertEqual(vocab.header_source, stage4.HEADER_SOURCE_APP_COLUMN_NAMES)
        states = {c.column: c.state for c in vocab.column_results}
        self.assertEqual(states["Word"], stage5.COLUMN_STATE_EXACT_MATCH)
        self.assertEqual(states["Note"], stage5.COLUMN_STATE_WHITESPACE_NEAR_MISS)
        self.assertEqual(states["Computed"], stage5.COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED)
        self.assertEqual(result.join.diagnostics, ())  # no longer an undetermined tab
        self.assertIn("largely by construction", result.join.reliability_condition)


if __name__ == "__main__":
    unittest.main()
