import tempfile
import unittest

from ..declarations import load_declarations
from .fixtures import write_declarations


class TestLoadDeclarations(unittest.TestCase):
    def test_none_path_yields_no_overrides(self):
        decl = load_declarations(None)
        self.assertEqual(decl.header_row_overrides, {})
        self.assertIsNone(decl.header_row_override("Anything"))

    def test_loads_overrides_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_declarations(tmp, {"SomeSheet": 3})
            decl = load_declarations(path)
        self.assertEqual(decl.header_row_override("SomeSheet"), 3)
        self.assertIsNone(decl.header_row_override("OtherSheet"))

    def test_empty_overrides_file_behaves_like_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_declarations(tmp, {})
            decl = load_declarations(path)
        self.assertEqual(decl.header_row_overrides, {})


if __name__ == "__main__":
    unittest.main()
