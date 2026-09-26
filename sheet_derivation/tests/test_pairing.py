import tempfile
import unittest

from .. import pairing
from .fixtures import build_stage5_pair, write_export_html, write_pair


def _folder(tmp, export_tables, include_qualifier=True):
    """An input folder: the stage 5 fixture capture (tabs "Ledger" and
    "Murky") plus an export naming `export_tables`."""
    formulas_doc, values_doc = build_stage5_pair()
    write_pair(tmp, formulas_doc, values_doc)
    if export_tables is not None:
        write_export_html(tmp, export_tables, include_qualifier=include_qualifier)
    return tmp


class TestCompare(unittest.TestCase):
    def test_match(self):
        r = pairing.compare(("A", "B"), ("A", "B", "C"))
        self.assertEqual(r.verdict, pairing.VERDICT_MATCH)
        self.assertFalse(r.stops)

    def test_partial_names_what_is_missing(self):
        r = pairing.compare(("A", "B", "X"), ("A", "B"))
        self.assertEqual(r.verdict, pairing.VERDICT_PARTIAL)
        self.assertEqual(r.missing, ("X",))
        self.assertFalse(r.stops)

    def test_none_stops(self):
        r = pairing.compare(("X", "Y"), ("A", "B"))
        self.assertEqual(r.verdict, pairing.VERDICT_NONE)
        self.assertTrue(r.stops)

    def test_capture_listing_no_sheets_stops_and_says_why(self):
        r = pairing.compare(("X",), ())
        self.assertTrue(r.stops)
        self.assertIn("lists no sheets", r.reason)
        self.assertIn("lists no sheets", pairing.format_pairing(r)[0])

    def test_nothing_expected_is_undecidable(self):
        r = pairing.compare((), ("A",))
        self.assertEqual(r.verdict, pairing.VERDICT_UNDECIDABLE)
        self.assertFalse(r.stops)


class TestCheckPairingOnAFolder(unittest.TestCase):
    def test_matching_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = pairing.check_pairing(_folder(tmp, [("Ledger", "Ledger", "google"), ("Prefs", None, "native")]))
        self.assertEqual(r.verdict, pairing.VERDICT_MATCH)
        self.assertEqual(r.expected_worksheets, ("Ledger",))  # the native table is not expected

    def test_unrelated_capture_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = pairing.check_pairing(_folder(tmp, [("Orders", "Order sheet", "google")]))
        self.assertEqual(r.verdict, pairing.VERDICT_NONE)

    def test_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = pairing.check_pairing(
                _folder(tmp, [("Ledger", "Ledger", "google"), ("Orders", "Order sheet", "google")])
            )
        self.assertEqual(r.verdict, pairing.VERDICT_PARTIAL)
        self.assertEqual(r.missing, ("Order sheet",))

    def test_no_export_is_undecidable(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = pairing.check_pairing(_folder(tmp, None))
        self.assertEqual(r.verdict, pairing.VERDICT_UNDECIDABLE)
        self.assertIn(pairing.EXPORT_HTML_NAME, r.reason)

    def test_export_without_the_field_is_undecidable(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = pairing.check_pairing(_folder(tmp, [("Orders", "Order sheet", "google")], include_qualifier=False))
        self.assertEqual(r.verdict, pairing.VERDICT_UNDECIDABLE)


class TestFormatPairing(unittest.TestCase):
    def test_match_is_one_line(self):
        lines = pairing.format_pairing(pairing.compare(("A",), ("A",)))
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Pairing check:"))

    def test_partial_warns_and_names(self):
        lines = pairing.format_pairing(pairing.compare(("A", "X"), ("A",)))
        self.assertTrue(lines[0].startswith("WARNING"))
        self.assertIn("'X'", lines[0])

    def test_none_stops_and_names_the_override(self):
        lines = pairing.format_pairing(pairing.compare(("X",), ("A",)))
        self.assertTrue(lines[0].startswith("STOPPED"))
        self.assertIn(pairing.OVERRIDE_OPTION, "\n".join(lines))

    def test_none_with_override_warns(self):
        lines = pairing.format_pairing(pairing.compare(("X",), ("A",)), allow_mismatch=True)
        self.assertTrue(lines[0].startswith("WARNING"))
        self.assertIn(pairing.OVERRIDE_OPTION, lines[0])

    def test_no_user_facing_line_uses_the_banned_word(self):
        results = [
            pairing.compare(("A",), ("A",)), pairing.compare(("A", "X"), ("A",)),
            pairing.compare(("X",), ("A",)), pairing.compare((), ("A",)),
        ]
        for r in results:
            for allow in (False, True):
                for line in pairing.format_pairing(r, allow_mismatch=allow):
                    self.assertNotIn("snapshot", line.lower())


if __name__ == "__main__":
    unittest.main()
