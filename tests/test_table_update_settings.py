"""Tests for ColumnParser's table-level update setting capture
(extract_table_update_settings / save_tables_to_csv -> appsheet_tables.csv).

Run from the repository root:
    python -m unittest discover -s tests -t .
"""

import contextlib
import csv
import io
import os
import tempfile
import unittest

from column_parser import ColumnParser


def _table_block(name, update_mode_row, data_source="/appsheet/data/x/Kankaku.gsheet"):
    """One table block shaped like the export's: an h5 header followed by the
    settings table. `update_mode_row` is the raw cell text, or None for no row."""
    update_row = ""
    if update_mode_row is not None:
        update_row = (
            '<tr><td><label class="" for="UpdateMode" data-toggle="tooltip" '
            'title="Are adds, deletes and updates allowed?">Are updates allowed?</label></td>'
            f"<td>{update_mode_row}</td></tr>"
        )
    return (
        f'<h5 id="table_{name}">Table name {name}</h5>'
        '<table class="react-bridge-group"><tbody>'
        '<tr><td><label for="LocaleName">Data locale</label></td><td>en-US</td></tr>'
        f"{update_row}"
        f'<tr><td><label for="DataSourceName">Data Source</label></td><td>{data_source}</td></tr>'
        "</tbody></table>"
    )


def _html(*blocks):
    return "<html><body>" + "".join(blocks) + "</body></html>"


def _parse_settings(html):
    """Run the extraction in a scratch directory (ColumnParser looks for
    appsheet_slices.csv in the current directory) and return (settings, printed)."""
    buf = io.StringIO()
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            with contextlib.redirect_stdout(buf):
                parser = ColumnParser(html_string=html)
                settings = parser.extract_table_update_settings()
        finally:
            os.chdir(original)
    return settings, buf.getvalue(), parser


class TestTableUpdateSettings(unittest.TestCase):
    def test_all_four_known_values_are_read(self):
        html = _html(
            _table_block("Alpha", "ALL_CHANGES"),
            _table_block("Beta", "UPDATES_ONLY"),
            _table_block("Gamma", "ADDS_ONLY"),
            _table_block("Delta", "READ_ONLY"),
        )
        settings, printed, _ = _parse_settings(html)
        self.assertEqual(
            settings,
            [
                {"table_name": "Alpha", "update_mode": "ALL_CHANGES"},
                {"table_name": "Beta", "update_mode": "UPDATES_ONLY"},
                {"table_name": "Gamma", "update_mode": "ADDS_ONLY"},
                {"table_name": "Delta", "update_mode": "READ_ONLY"},
            ],
        )
        self.assertNotIn("update_mode", printed)

    def test_four_help_page_values_are_recognized_without_warning(self):
        values = ["ADDS_AND_UPDATES", "ADDS_AND_DELETES", "UPDATES_AND_DELETES", "DELETES_ONLY"]
        html = _html(*[_table_block(f"T{i}", v) for i, v in enumerate(values)])
        settings, printed, _ = _parse_settings(html)
        self.assertEqual(
            settings,
            [{"table_name": f"T{i}", "update_mode": v} for i, v in enumerate(values)],
        )
        self.assertNotIn("update_mode", printed)

    def test_native_source_table_is_included(self):
        html = _html(
            _table_block("Alpha", "ALL_CHANGES"),
            _table_block("Bot Output", "READ_ONLY", data_source="native"),
        )
        settings, _, _ = _parse_settings(html)
        self.assertEqual([s["table_name"] for s in settings], ["Alpha", "Bot Output"])
        self.assertEqual(settings[1]["update_mode"], "READ_ONLY")

    def test_missing_row_gives_empty_value_and_warning(self):
        html = _html(_table_block("Alpha", "ALL_CHANGES"), _table_block("NoRow", None))
        settings, printed, _ = _parse_settings(html)
        self.assertEqual(settings[1], {"table_name": "NoRow", "update_mode": ""})
        self.assertIn("Table 'NoRow'", printed)
        self.assertIn("no 'Are updates allowed?' row", printed)
        self.assertEqual(printed.count("Table '"), 1)

    def test_unknown_value_is_written_as_exported_with_warning(self):
        html = _html(_table_block("Alpha", "=IF(USERROLE()=&quot;Admin&quot;, &quot;ALL_CHANGES&quot;, &quot;READ_ONLY&quot;)"))
        settings, printed, _ = _parse_settings(html)
        self.assertEqual(settings[0]["update_mode"], '=IF(USERROLE()="Admin", "ALL_CHANGES", "READ_ONLY")')
        self.assertIn("Table 'Alpha'", printed)
        self.assertIn("unrecognized update_mode", printed)

    def test_lowercase_value_is_not_normalized(self):
        settings, printed, _ = _parse_settings(_html(_table_block("Alpha", "read_only")))
        self.assertEqual(settings[0]["update_mode"], "read_only")
        self.assertIn("unrecognized update_mode", printed)

    def test_csv_has_one_row_per_table_in_export_order(self):
        html = _html(_table_block("Beta", "UPDATES_ONLY"), _table_block("Alpha", None))
        _, _, parser = _parse_settings(html)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "appsheet_tables.csv")
            with contextlib.redirect_stdout(io.StringIO()):
                parser.save_tables_to_csv(path)
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fields = reader.fieldnames
        self.assertEqual(fields, ["table_name", "update_mode"])
        self.assertEqual(
            rows,
            [
                {"table_name": "Beta", "update_mode": "UPDATES_ONLY"},
                {"table_name": "Alpha", "update_mode": ""},
            ],
        )


if __name__ == "__main__":
    unittest.main()
