import tempfile
import unittest

from ..appside_parse import (
    AppSideParseError,
    discover_appside_columns_csv,
    extract_app_identity,
    hash_file,
    load_appside_columns,
)
from .fixtures import build_stage5_appside_rows, write_appside_columns_csv


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
