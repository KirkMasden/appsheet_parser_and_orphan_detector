import tempfile
import unittest

from ..coordinates import cell_address
from ..determinism import verify_same_process_determinism
from .fixtures import build_stage2_pair, write_pair
from .. import stage2


class TestStage2EndToEnd(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage2_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage2.run_stage2(fpath, vpath)

    def _edge(self, result, source_sheet, source_column, target_sheet, target_column):
        for e in result.graph.edges:
            if (e.source_sheet, e.source_column, e.target_sheet, e.target_column) == (
                source_sheet, source_column, target_sheet, target_column,
            ):
                return e
        return None

    def test_same_pattern_two_sheets_two_columns_produces_separate_edges(self):
        """Regression fixture for the bug where a graph edge's source
        location was read from only a pattern's first-found instance.
        `=Other!B#` occurs in Ledger!A1/A2 (column A), Ledger!B1 (column
        B), and Archive!C1 (column C) -- three distinct source columns
        across two sheets must produce three distinct edges, not one."""
        result = self._run()
        e_a = self._edge(result, "Ledger", "A", "Other", "B")
        e_b = self._edge(result, "Ledger", "B", "Other", "B")
        e_archive = self._edge(result, "Archive", "C", "Other", "B")
        self.assertIsNotNone(e_a)
        self.assertIsNotNone(e_b)
        self.assertIsNotNone(e_archive)
        self.assertEqual(e_a.cells, ("Ledger!A1", "Ledger!A2"))
        self.assertEqual(e_b.cells, ("Ledger!B1",))
        self.assertEqual(e_archive.cells, ("Archive!C1",))
        self.assertEqual(e_a.patterns, ("=Other!B#",))
        self.assertEqual(e_b.patterns, e_a.patterns)
        self.assertEqual(e_archive.patterns, e_a.patterns)

    def test_range_reference_spans_every_column_it_covers(self):
        """`=SUM(Other!B1:C2)` must produce edges to both column B and
        column C of Other, from the same source column."""
        result = self._run()
        self.assertIsNotNone(self._edge(result, "Ledger", "F", "Other", "B"))
        self.assertIsNotNone(self._edge(result, "Ledger", "F", "Other", "C"))

    def test_arrayformula_still_resolves_its_inner_reference_into_an_edge(self):
        """ARRAYFORMULA(...) flags residue but must not block the ordinary
        reference inside it from becoming a graph edge."""
        result = self._run()
        edge = self._edge(result, "Ledger", "F", "Other", "B")
        self.assertIn("Ledger!F1", edge.cells)
        residue_locations = [r.locations for r in result.graph.residue if r.defeating_construct == "ARRAYFORMULA span"]
        self.assertEqual(residue_locations, [("Ledger!F1",)])

    def test_dangling_reference_position_name_carries_every_cell(self):
        result = self._run()
        entries = [d for d in result.dangling.entries if d.name == "Ghost Sheet" and d.classification == "reference position"]
        self.assertEqual(len(entries), 1)
        cells = [o.cell for o in entries[0].occurrences]
        self.assertEqual(cells, ["Ledger!C1", "Ledger!C2"])
        self.assertEqual(entries[0].occurrences[0].raw_formula, "='Ghost Sheet'!D1")

    def test_dangling_reference_position_also_produces_graph_residue(self):
        """The standing invariant: a dangling reference-position token is
        not a graph edge, so it must also appear in the graph's own
        residue -- not only in the dangling-name artifact."""
        result = self._run()
        matches = [r for r in result.graph.residue if r.defeating_construct == "dangling sheet name (reference position)"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].locations, ("Ledger!C1", "Ledger!C2"))

    def test_string_literal_naming_a_real_sheet_is_residue_only_not_dangling(self):
        """'="Other!B1"' names a REAL sheet from inside a string literal --
        it must become a graph residue entry (first addition to the
        residue rule) but must NOT appear in the dangling-name artifact,
        since 'Other' is not dangling."""
        result = self._run()
        self.assertFalse(any(d.name == "Other" for d in result.dangling.entries))
        matches = [
            r for r in result.graph.residue
            if r.defeating_construct == "sheet-name-shaped text in a STRING_LITERAL span"
            and r.locations == ("Ledger!D1",)
        ]
        self.assertEqual(len(matches), 1)

    def test_string_literal_naming_a_dangling_sheet_is_both_dangling_and_residue(self):
        """'="'Ghost Sheet'!D1"' is Gate 4's own shape: the name is both
        dangling AND inside a string literal -- both artifacts get it."""
        result = self._run()
        dangling = [d for d in result.dangling.entries if d.name == "Ghost Sheet" and d.classification == "string literal position"]
        self.assertEqual(len(dangling), 1)
        self.assertEqual([o.cell for o in dangling[0].occurrences], ["Ledger!E1"])
        residue = [
            r for r in result.graph.residue
            if r.defeating_construct == "sheet-name-shaped text in a STRING_LITERAL span"
            and r.locations == ("Ledger!E1",)
        ]
        self.assertEqual(len(residue), 1)

    def test_indirect_argument_is_residue_and_produces_no_edge(self):
        result = self._run()
        matches = [r for r in result.graph.residue if r.defeating_construct == "INDIRECT argument"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].locations, ("Ledger!A3",))
        self.assertFalse(any("Ledger!A3" in e.cells for e in result.graph.edges))

    def test_importrange_one_hop_resolution_follows_exactly_one_hop(self):
        """IMPORTRANGE(Other!C1, ...) -- Other!C1 is a bare single-cell
        reference; the residue entry must name that cell and its value at
        capture time, and must not chase anything beyond it."""
        result = self._run()
        matches = [
            r for r in result.graph.residue
            if "IMPORTRANGE" in r.defeating_construct and r.locations == ("Ledger!B3",)
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("Other!C1", matches[0].what)
        self.assertIn("https://example.com/target", matches[0].what)

    def test_importrange_literal_argument_is_not_one_hop_resolved(self):
        result = self._run()
        matches = [
            r for r in result.graph.residue
            if "IMPORTRANGE" in r.defeating_construct and r.locations == ("Ledger!C3",)
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("not resolved here as a", matches[0].what)

    def test_accounting_balances_per_sheet_and_workbook_wide(self):
        result = self._run()
        for a in result.accounting:
            self.assertTrue(a.balances, msg=f"{a.sheet_name} does not balance: {a}")
        self.assertTrue(result.workbook_accounting.balances)
        self.assertEqual(result.workbook_accounting.non_empty_formulas, 12 + 1 + 2)

    def test_dangling_artifact_residue_is_empty_by_construction(self):
        result = self._run()
        self.assertEqual(result.dangling.residue, ())

    def test_determinism(self):
        formulas_doc, values_doc = build_stage2_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)

            def pipeline():
                return stage2.run_stage2(fpath, vpath)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-2")
        self.assertEqual(result.workbook_accounting.non_empty_formulas, 15)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_stage2_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage2.main([tmp])
        self.assertEqual(exit_code, 0)


class TestAddressHelpers(unittest.TestCase):
    def test_split_column_and_row_plain(self):
        self.assertEqual(stage2._split_column_and_row("AB153"), ("AB", 153))

    def test_split_column_and_row_dollar_signs(self):
        self.assertEqual(stage2._split_column_and_row("$AB$153"), ("AB", 153))

    def test_split_column_and_row_bare_column(self):
        self.assertEqual(stage2._split_column_and_row("J"), ("J", None))
        self.assertEqual(stage2._split_column_and_row("$J"), ("J", None))

    def test_columns_between_single(self):
        self.assertEqual(stage2._columns_between("AM", "AM"), ("AM",))

    def test_columns_between_range(self):
        self.assertEqual(stage2._columns_between("B", "D"), ("B", "C", "D"))

    def test_columns_between_reversed_order(self):
        self.assertEqual(stage2._columns_between("D", "B"), ("B", "C", "D"))


class TestStringLiteralScan(unittest.TestCase):
    def test_finds_bare_sheet_shaped_run(self):
        found = stage2.find_sheet_shaped_names_in_string_literal('"Collate!AK153"')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Collate")

    def test_finds_quoted_sheet_shaped_run(self):
        found = stage2.find_sheet_shaped_names_in_string_literal("\"'Ghost Sheet'!D1\"")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Ghost Sheet")

    def test_plain_string_with_no_reference_shape_finds_nothing(self):
        found = stage2.find_sheet_shaped_names_in_string_literal('"just some text"')
        self.assertEqual(found, ())


class TestConsumerCheckHelper(unittest.TestCase):
    def _run(self):
        from ..loader import load_capture
        formulas_doc, values_doc = build_stage2_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return load_capture(fpath, vpath)

    def test_finds_a_sheet_qualified_single_cell_reference(self):
        capture = self._run()
        # Other!B1 (row0=0, col0=1) is referenced directly by Ledger!A1,
        # Ledger!B1 and Archive!C1, and covered by the two ranges at
        # Ledger!F1 (ARRAYFORMULA(Other!B1:B2)) and Ledger!F2
        # (SUM(Other!B1:C2)) -- Ledger!A2 references Other!B2, not B1, and
        # must NOT appear.
        results = stage2.find_formulas_referencing_cells(capture, (("Other", 0, 1),))
        self.assertEqual(
            set(results[("Other", 0, 1)]),
            {"Ledger!A1", "Ledger!B1", "Archive!C1", "Ledger!F1", "Ledger!F2"},
        )

    def test_finds_nothing_for_a_cell_nothing_references(self):
        capture = self._run()
        results = stage2.find_formulas_referencing_cells(capture, (("Ledger", 0, 3),))  # Ledger!D1
        self.assertEqual(results[("Ledger", 0, 3)], ())


if __name__ == "__main__":
    unittest.main()
