"""The formula checkup's reader of appsheet_columns.csv (stored formula, key,
virtual) and appsheet_tables.csv (update setting). Stage 5's own reader is
tested in test_appside_parse.py and is not touched."""

import os
import tempfile
import unittest

from .. import appside_formulas
from ..appside_formulas import (
    discover_appside_tables_csv,
    load_appside_formula_columns,
    load_appside_tables,
)
from ..appside_parse import AppSideParseError
from .fixtures import write_formula_columns_csv, write_tables_csv


class TestFormulaColumns(unittest.TestCase):
    def test_reads_the_four_fields_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_formula_columns_csv(tmp, [
                {"table_name": "T", "column_name": "A", "is_virtual": "No", "key": "Yes", "spreadsheet_formula": ""},
                {"table_name": "T", "column_name": "B", "is_virtual": "Yes", "key": "No",
                 "spreadsheet_formula": ' if(RC[-1]="a",1,\n2) '},
                {"table_name": "U", "column_name": "C", "is_virtual": "", "key": "", "spreadsheet_formula": '"COMPUTED_VALUE"'},
            ])
            loaded = load_appside_formula_columns(path)
        self.assertTrue(loaded.spreadsheet_formula_field_present)
        self.assertTrue(loaded.key_field_present)
        a, b, c = loaded.columns
        self.assertEqual((a.is_virtual, a.is_key, a.spreadsheet_formula), (False, True, ""))
        self.assertEqual((b.is_virtual, b.is_key), (True, False))
        self.assertEqual(b.spreadsheet_formula, ' if(RC[-1]="a",1,\n2) ')  # never trimmed
        self.assertEqual((c.is_virtual, c.is_key, c.spreadsheet_formula), (None, None, '"COMPUTED_VALUE"'))
        self.assertEqual([x.column_name for x in loaded.columns_for_table("T")], ["A", "B"])

    def test_missing_fields_are_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_formula_columns_csv(
                tmp, [{"table_name": "T", "column_name": "A"}], fieldnames=["table_name", "column_name"]
            )
            loaded = load_appside_formula_columns(path)
        self.assertFalse(loaded.spreadsheet_formula_field_present)
        self.assertFalse(loaded.key_field_present)
        self.assertFalse(loaded.virtual_field_present)
        self.assertIsNone(loaded.columns[0].is_key)

    def test_a_file_that_is_not_a_columns_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "appsheet_columns.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x,y\n1,2\n")
            with self.assertRaises(AppSideParseError):
                load_appside_formula_columns(path)


class TestTablesFile(unittest.TestCase):
    def test_reads_every_setting_as_exported(self):
        rows = [("A", "ALL_CHANGES"), ("B", ""), ("C", '=IF([x],"READ_ONLY","ALL_CHANGES")'), ("A", "READ_ONLY")]
        with tempfile.TemporaryDirectory() as tmp:
            write_tables_csv(tmp, rows)
            path = discover_appside_tables_csv(tmp)
            loaded = load_appside_tables(path)
        self.assertEqual(loaded.settings, tuple(rows))
        self.assertEqual(loaded.by_table(), {"A": "ALL_CHANGES", "B": "", "C": '=IF([x],"READ_ONLY","ALL_CHANGES")'})

    def test_absent_file_is_none_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(discover_appside_tables_csv(tmp))

    def test_a_file_without_the_fields_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, appside_formulas.TABLES_CSV_NAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("table_name\nA\n")
            with self.assertRaises(AppSideParseError):
                load_appside_tables(path)


if __name__ == "__main__":
    unittest.main()
