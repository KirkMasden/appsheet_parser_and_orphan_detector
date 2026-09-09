import os
import tempfile
import unittest

from ..jsonl_io import read_jsonl, write_csv, write_jsonl


class TestJsonlRoundTrip(unittest.TestCase):
    def test_write_then_read_preserves_order_and_content(self):
        items = [{"kind": "meta", "n": 1}, {"kind": "thing", "n": 2, "text": "hello"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            count = write_jsonl(path, items)
            self.assertEqual(count, 2)
            read_back = list(read_jsonl(path))
        self.assertEqual(read_back, items)

    def test_one_json_object_per_line_no_pretty_printing_that_would_split_a_line(self):
        items = [{"a": 1}, {"b": 2}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            write_jsonl(path, items)
            with open(path, encoding="utf-8") as fh:
                lines = [l for l in fh.read().split("\n") if l]
        self.assertEqual(len(lines), 2)

    def test_long_string_is_never_truncated(self):
        long_text = "x" * 5000
        items = [{"rawInstance": long_text}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            write_jsonl(path, items)
            read_back = list(read_jsonl(path))
        self.assertEqual(len(read_back[0]["rawInstance"]), 5000)

    def test_non_ascii_is_written_as_real_utf8_not_escaped(self):
        items = [{"label": "Collate!AK153 -- 日本語"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            write_jsonl(path, items)
            with open(path, encoding="utf-8") as fh:
                raw_text = fh.read()
        self.assertIn("日本語", raw_text)
        self.assertNotIn("\\u", raw_text)


class TestCsvWriter(unittest.TestCase):
    def test_writes_header_then_one_row_per_item(self):
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.csv")
            count = write_csv(path, ["a", "b"], rows)
            self.assertEqual(count, 2)
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        self.assertEqual(lines[0], "a,b")
        self.assertEqual(lines[1:], ["1,x", "2,y"])


if __name__ == "__main__":
    unittest.main()
