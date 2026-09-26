import tempfile
import unittest

from ..appside_parse import (
    AppSideParseError,
    discover_appside_columns_csv,
    extract_app_identity,
    extract_table_sources,
    hash_file,
    load_appside_columns,
)
from .fixtures import build_stage5_appside_rows, write_appside_columns_csv, write_export_html


class TestLoadAppsideColumns(unittest.TestCase):
    def test_loads_table_names_and_virtual_flag(self):
        rows = build_stage5_appside_rows()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_appside_columns_csv(tmp, rows)
            data = load_appside_columns(path)
        self.assertTrue(data.virtual_field_present)
        self.assertEqual(set(data.table_names), {"Ledger", "Murky", "Ghost"})
        virtual_names = {c.column_name for c in data.columns if c.is_virtual}
        self.assertEqual(virtual_names, {"VirtualThing", "GhostCol2"})

    def test_missing_is_virtual_field_is_reported_not_inferred(self):
        rows = build_stage5_appside_rows()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_appside_columns_csv(tmp, rows, include_is_virtual=False)
            data = load_appside_columns(path)
        self.assertFalse(data.virtual_field_present)
        self.assertTrue(all(c.is_virtual is None for c in data.columns))

    def test_columns_for_table(self):
        rows = build_stage5_appside_rows()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_appside_columns_csv(tmp, rows)
            data = load_appside_columns(path)
        ledger_cols = {c.column_name for c in data.columns_for_table("Ledger")}
        self.assertIn("Qty", ledger_cols)
        self.assertNotIn("Name", ledger_cols)  # that's a Murky column


class TestDiscoverAppsideColumnsCsv(unittest.TestCase):
    def test_raises_clearly_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AppSideParseError):
                discover_appside_columns_csv(tmp)


class TestAppIdentity(unittest.TestCase):
    def test_none_path_yields_all_absent(self):
        identity = extract_app_identity(None)
        self.assertIsNone(identity.og_title)
        self.assertIsNone(identity.version)
        self.assertIsNone(identity.html_mtime_iso)

    def test_extracts_from_a_minimal_export_style_html(self):
        html = (
            '<meta property="og:title" content="AppSheet : mobile apps from spreadsheets : '
            'TestApp-123 Documentation"/>\n'
            '<tr><td><label for="Version" data-toggle="tooltip" title="x">Version</label>'
            "</td><td>2.000005</td></tr>\n"
            '<tr><td><label for="DefnFolderName" data-toggle="tooltip" title="x">Default app '
            "folder</label></td><td>/appsheet/data/TestApp-123</td></tr>\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            import os
            path = os.path.join(tmp, "export.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            identity = extract_app_identity(path)
        self.assertIn("TestApp-123", identity.og_title)
        self.assertEqual(identity.version, "2.000005")
        self.assertEqual(identity.default_app_folder, "/appsheet/data/TestApp-123")
        self.assertIsNotNone(identity.html_mtime_iso)


class TestTableSources(unittest.TestCase):
    def test_none_path_yields_none(self):
        self.assertIsNone(extract_table_sources(None))

    def test_reads_each_table_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_export_html(tmp, [
                ("Orders", "Order sheet", "google"),
                ("Prefs", None, "native"),
                ("Things &amp; stuff", "Things", "google"),
            ])
            sources = extract_table_sources(path)
        self.assertTrue(sources.qualifier_field_present)
        by_table = sources.by_table()
        self.assertEqual(by_table["Orders"].worksheet, "Order sheet")
        self.assertEqual(by_table["Orders"].data_source, "google")
        self.assertEqual(by_table["Orders"].source_path, "/appsheet/data/TestApp-1/Orders.gsheet")
        self.assertIsNone(by_table["Prefs"].worksheet)  # native: no qualifier row
        self.assertIn("Things & stuff", by_table)  # entities unescaped

    def test_google_worksheets_are_distinct_and_google_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_export_html(tmp, [
                ("A", "Shared", "google"),
                ("B", "Shared", "google"),
                ("C", "Elsewhere", "native"),
                ("D", "Own", "google"),
            ])
            sources = extract_table_sources(path)
        self.assertEqual(sources.google_worksheets(), ("Shared", "Own"))

    def test_export_without_the_field_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_export_html(tmp, [("Orders", "Order sheet", "google")], include_qualifier=False)
            sources = extract_table_sources(path)
        self.assertFalse(sources.qualifier_field_present)
        self.assertEqual(len(sources.tables), 1)


class TestHashFile(unittest.TestCase):
    def test_hash_is_deterministic_and_content_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            path = os.path.join(tmp, "a.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello")
            h1 = hash_file(path)
            h2 = hash_file(path)
            self.assertEqual(h1, h2)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("hello!")
            h3 = hash_file(path)
            self.assertNotEqual(h1, h3)


if __name__ == "__main__":
    unittest.main()
