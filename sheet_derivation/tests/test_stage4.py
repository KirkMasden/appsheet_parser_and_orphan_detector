import tempfile
import unittest

from ..determinism import verify_same_process_determinism
from .fixtures import build_stage4_pair, write_declarations, write_pair
from .. import stage4


def _run(declarations_path=None):
    formulas_doc, values_doc = build_stage4_pair()
    with tempfile.TemporaryDirectory() as tmp:
        fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
        return stage4.run_stage4(fpath, vpath, declarations_path)


def _sheet(result, name):
    return next(s for s in result.schema.sheets if s.sheet == name)


def _column(sheet_entry, letters):
    return next(c for c in sheet_entry.columns if c.column == letters)


class TestHeaderDetectionPositiveSignal(unittest.TestCase):
    def test_identified_via_type_mismatch_alone(self):
        """Ledger has no formulas anywhere -- only the positive (type-
        mismatch) signal is available, and it alone must be enough to
        identify row 1 as the header."""
        s = _sheet(_run(), "Ledger")
        hd = s.header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_MEASURED)
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_IDENTIFIED)
        self.assertEqual(hd.header_row1, 1)
        self.assertEqual(hd.evidence.positive_signal_columns, ("A", "B", "D"))
        self.assertEqual(hd.evidence.negative_signal_columns, ())
        self.assertAlmostEqual(hd.confidence, 1.0)

    def test_row_need_not_be_uniform_to_be_identified(self):
        """Design's own rule: a row may be a header while containing cells
        that are not labels. Ledger column C (blank) and E (entirely
        empty) contribute nothing, and must not block identification."""
        s = _sheet(_run(), "Ledger")
        self.assertEqual(s.header_detection.verdict, stage4.HEADER_VERDICT_IDENTIFIED)


class TestHeaderDetectionNegativeSignal(unittest.TestCase):
    def test_a_single_governing_spill_overrides_any_positive_signal(self):
        """SpillSheet column A holds a formula at row 1 whose row 2 cell is
        a bare value with no formula -- a governing downward spill. This
        must classify the WHOLE row not-identified-confident, even though
        columns B and C independently show a type-mismatch signal."""
        s = _sheet(_run(), "SpillSheet")
        hd = s.header_detection
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT)
        self.assertIsNone(hd.header_row1)
        self.assertEqual(hd.evidence.negative_signal_columns, ("A",))
        self.assertIn("B", hd.evidence.positive_signal_columns)
        self.assertEqual(hd.confidence, 1.0)

    def test_every_column_gets_the_no_header_in_sheet_label_state(self):
        s = _sheet(_run(), "SpillSheet")
        for c in s.columns:
            self.assertEqual(c.header_label.state, stage4.LABEL_STATE_NONE_NO_HEADER_IN_SHEET)
            self.assertIsNone(c.header_label.value)


class TestHeaderDetectionUndetermined(unittest.TestCase):
    def test_no_signal_anywhere_is_undetermined_not_headerless(self):
        s = _sheet(_run(), "UndeterminedSheet")
        hd = s.header_detection
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_UNDETERMINED)
        self.assertIsNone(hd.header_row1)
        self.assertIsNone(hd.confidence)
        self.assertEqual(hd.evidence.positive_signal_columns, ())
        self.assertEqual(hd.evidence.negative_signal_columns, ())

    def test_every_column_gets_the_unknown_label_state_not_none(self):
        """UNDETERMINED must not be reported the same way as a confident
        'no header' -- the column-label state distinguishes them."""
        s = _sheet(_run(), "UndeterminedSheet")
        for c in s.columns:
            self.assertEqual(c.header_label.state, stage4.LABEL_STATE_UNKNOWN_HEADER_NOT_IDENTIFIED)

    def test_undetermined_sheet_produces_exactly_one_residue_entry(self):
        result = _run()
        matches = [
            r for r in result.schema.residue
            if r.locations and r.locations[0].startswith("UndeterminedSheet!")
        ]
        self.assertEqual(len(matches), 1)
        self.assertIn("no measurable header signal", matches[0].defeating_construct)
        self.assertIn("declarations file", matches[0].consequence)


class TestThreeStateHeaderLabel(unittest.TestCase):
    def test_labeled_state_carries_the_value(self):
        s = _sheet(_run(), "Ledger")
        a = _column(s, "A")
        self.assertEqual(a.header_label.state, stage4.LABEL_STATE_LABELED)
        self.assertEqual(a.header_label.value, "Qty")

    def test_blank_cell_in_identified_header_is_its_own_state(self):
        s = _sheet(_run(), "Ledger")
        c = _column(s, "C")
        self.assertEqual(c.header_label.state, stage4.LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER)
        self.assertIsNone(c.header_label.value)

    def test_fully_empty_column_still_gets_a_label_state_not_an_empty_string(self):
        """Column E has no formula or value anywhere -- no Stage 3 profile
        exists for it at all. It must still receive a well-formed
        HeaderLabel, using the stage-3-absent fallback."""
        s = _sheet(_run(), "Ledger")
        e = _column(s, "E")
        self.assertEqual(e.header_label.state, stage4.LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER)
        self.assertEqual(e.classification, stage4.CLASSIFICATION_NO_FORMULA)
        self.assertEqual(e.formula_count, 0)
        self.assertEqual(e.value_count, 0)

    def test_no_state_is_ever_a_bare_none_or_empty_string(self):
        result = _run()
        for s in result.schema.sheets:
            for c in s.columns:
                self.assertIn(c.header_label.state, stage4._LABEL_STATES)
                self.assertTrue(c.header_label.state)


class TestDuplicateLabelsIndependentOfVerdict(unittest.TestCase):
    def test_duplicate_found_in_an_identified_header(self):
        s = _sheet(_run(), "Ledger")
        self.assertEqual(len(s.duplicate_labels), 1)
        self.assertEqual(s.duplicate_labels[0].label_value, "Qty")
        self.assertEqual(s.duplicate_labels[0].columns, ("A", "B"))

    def test_duplicate_found_even_though_the_sheet_is_not_a_header(self):
        """The regression case this workbook's own real capture produced:
        both attested duplicate-label sheets are classified data, not a
        header, yet the duplicate itself is still real and must still be
        reported."""
        s = _sheet(_run(), "SpillSheet")
        self.assertEqual(s.header_detection.verdict, stage4.HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT)
        self.assertEqual(len(s.duplicate_labels), 1)
        self.assertEqual(s.duplicate_labels[0].label_value, "Dup")
        self.assertEqual(s.duplicate_labels[0].columns, ("B", "C"))

    def test_no_duplicates_in_sheets_without_one(self):
        result = _run()
        self.assertEqual(_sheet(result, "UndeterminedSheet").duplicate_labels, ())


class TestDeclaredOverride(unittest.TestCase):
    def test_without_declaration_measured_detection_picks_row_one(self):
        s = _sheet(_run(), "DeclaredSheet")
        self.assertEqual(s.header_detection.source, stage4.HEADER_SOURCE_MEASURED)
        self.assertEqual(s.header_detection.header_row1, 1)

    def test_declared_row_overrides_measured_detection(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            decl_path = write_declarations(tmp, {"DeclaredSheet": 2})
            result = stage4.run_stage4(fpath, vpath, decl_path)
        s = _sheet(result, "DeclaredSheet")
        hd = s.header_detection
        self.assertEqual(hd.source, stage4.HEADER_SOURCE_DECLARED)
        self.assertEqual(hd.verdict, stage4.HEADER_VERDICT_IDENTIFIED)
        self.assertEqual(hd.header_row1, 2)
        self.assertEqual(_column(s, "A").header_label.value, "Name")
        self.assertEqual(_column(s, "B").header_label.value, "Age")

    def test_declared_sheet_produces_no_undetermined_residue(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            decl_path = write_declarations(tmp, {"DeclaredSheet": 2})
            result = stage4.run_stage4(fpath, vpath, decl_path)
        matches = [r for r in result.schema.residue if r.locations[0].startswith("DeclaredSheet!")]
        self.assertEqual(matches, [])

    def test_other_sheets_are_unaffected_by_an_unrelated_declaration(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            decl_path = write_declarations(tmp, {"DeclaredSheet": 2})
            declared_result = stage4.run_stage4(fpath, vpath, decl_path)
            plain_result = stage4.run_stage4(fpath, vpath, None)
        self.assertEqual(
            _sheet(declared_result, "Ledger").header_detection,
            _sheet(plain_result, "Ledger").header_detection,
        )

    def test_no_declarations_file_behaves_exactly_like_an_empty_one(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            empty_decl_path = write_declarations(tmp, {})
            result_no_path = stage4.run_stage4(fpath, vpath, None)
            result_empty_decl = stage4.run_stage4(fpath, vpath, empty_decl_path)
        self.assertEqual(result_no_path.sheet_verdict_counts, result_empty_decl.sheet_verdict_counts)


class TestStage3PassThrough(unittest.TestCase):
    def test_classification_formula_and_value_counts_are_read_not_recomputed(self):
        s = _sheet(_run(), "SpillSheet")
        a = _column(s, "A")
        self.assertEqual(a.classification, "single-pattern-contiguous")
        self.assertEqual(a.formula_count, 1)
        self.assertEqual(a.value_count, 2)  # the formula cell's own value (100) plus the spilled value (999)
        self.assertEqual(len(a.spill_runs), 1)  # A2's value-only cell, governed by A1's formula, gap 0
        self.assertEqual(a.spill_runs[0].governing_formula_row1, 1)
        self.assertEqual(a.spill_runs[0].gap_rows, 0)


class TestNamedRangesAndValidationsPassThrough(unittest.TestCase):
    def test_sheet_level_capture_fields_are_carried_verbatim(self):
        s = _sheet(_run(), "Ledger")
        self.assertEqual(s.named_ranges, ({"name": "QtyRange", "range": "A2:A4"},))
        self.assertEqual(len(s.data_validations), 1)
        self.assertEqual(len(s.conditional_format_rules), 1)
        self.assertEqual(len(s.protected_ranges), 1)


class TestUsedExtent(unittest.TestCase):
    def test_highest_row_and_column_with_formula_and_value(self):
        s = _sheet(_run(), "SpillSheet")
        self.assertEqual(s.declared_row_count, 4)
        self.assertEqual(s.declared_column_count, 4)
        self.assertEqual(s.highest_row_with_formula, 1)  # only A1 holds a formula
        self.assertEqual(s.highest_column_with_formula, "A")
        self.assertEqual(s.highest_row_with_value, 4)  # D4 = 9
        self.assertEqual(s.highest_column_with_value, "D")


class TestAccountingInvariants(unittest.TestCase):
    def test_sheet_verdicts_partition_every_sheet_exactly_once(self):
        result = _run()
        self.assertEqual(sum(result.sheet_verdict_counts.values()), len(result.schema.sheets))
        self.assertEqual(len(result.schema.sheets), 4)

    def test_column_label_states_partition_every_declared_column_exactly_once(self):
        result = _run()
        expected = sum(s.declared_column_count for s in result.schema.sheets)
        self.assertEqual(sum(result.column_label_state_counts.values()), expected)
        self.assertEqual(expected, 5 + 4 + 2 + 2)  # Ledger + SpillSheet + UndeterminedSheet + DeclaredSheet

    def test_determinism(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)

            def pipeline():
                return stage4.run_stage4(fpath, vpath)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-4")
        self.assertEqual(len(result.schema.sheets), 4)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_stage4_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage4.main([tmp])
        self.assertEqual(exit_code, 0)


class TestValueTypeCategory(unittest.TestCase):
    def test_empty_is_not_a_type(self):
        self.assertIsNone(stage4.value_type_category(""))
        self.assertIsNone(stage4.value_type_category(None))

    def test_boolean_checked_before_numeric(self):
        self.assertEqual(stage4.value_type_category(True), "boolean")

    def test_numeric(self):
        self.assertEqual(stage4.value_type_category(3), "numeric")
        self.assertEqual(stage4.value_type_category(3.5), "numeric")

    def test_error_literal_is_its_own_category(self):
        self.assertEqual(stage4.value_type_category("#REF!"), "error")

    def test_ordinary_string_is_text(self):
        self.assertEqual(stage4.value_type_category("hello"), "text")


if __name__ == "__main__":
    unittest.main()
