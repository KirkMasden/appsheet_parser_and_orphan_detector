import tempfile
import unittest

from ..determinism import verify_same_process_determinism
from .fixtures import build_stage1_pair, write_pair
from .. import stage1
from ..tokenizer import TokenKind


class TestStage1EndToEnd(unittest.TestCase):
    def _run(self):
        formulas_doc, values_doc = build_stage1_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)
            return stage1.run_stage1(fpath, vpath)

    def test_accounting_gate_c1(self):
        """Sum of pattern instance counts equals the non-empty formula
        count, per sheet and workbook-wide -- for both gate modes."""
        result = self._run()
        self.assertEqual(
            sum(info.instance_count for info in result.gate_b_patterns.values()),
            result.total_nonempty_formulas,
        )
        self.assertEqual(
            sum(info.instance_count for info in result.gate_a_patterns.values()),
            result.total_nonempty_formulas,
        )
        for c in result.per_sheet_counts:
            self.assertEqual(
                sum(result.per_sheet_gate_b_pattern_counts[c.sheet_name].values()),
                c.non_empty_formulas,
            )

    def test_total_nonempty_formula_count(self):
        result = self._run()
        # Ledger: 3 rows x 3 cols with one blank cell (row3 col2), Other: 1.
        self.assertEqual(result.total_nonempty_formulas, 8 + 1)

    def test_string_literal_reference_shape_is_not_normalized_by_real_tool(self):
        result = self._run()
        # '="Other!B1"' must survive untouched as its own Gate B pattern.
        self.assertIn('="Other!B1"', result.gate_b_patterns)

    def test_same_text_is_a_gate_a_gate_b_split(self):
        result = self._run()
        # Under Gate A (probe-equivalent), the string-literal case gets
        # its row digit rewritten just like a real reference would.
        self.assertIn('="Other!B#"', result.gate_a_patterns)
        # Under Gate B (real tool), it does not.
        self.assertNotIn('="Other!B#"', result.gate_b_patterns)

    def test_digit_in_function_name_pattern_present(self):
        result = self._run()
        self.assertIn("=CUSTOM2FUNC(A#)", result.gate_b_patterns)
        self.assertIn("=CUSTOM2FUNC(A#)", result.gate_a_patterns)

    def test_function_vocabulary_finds_custom2func_not_a_mangled_fragment(self):
        result = self._run()
        vocab = stage1.function_vocabulary(result, use_gate_a=True)
        self.assertIn("CUSTOM2FUNC", vocab)
        self.assertEqual(vocab["CUSTOM2FUNC"], 1)
        self.assertNotIn("FUNC", vocab)  # the would-be mangled fragment

    def test_sheet_qualified_reference_positions_excludes_string_literal(self):
        real_ref = stage1.sheet_qualified_reference_positions("=Other!B1")
        self.assertEqual(len(real_ref), 1)
        self.assertEqual(real_ref[0].kind, TokenKind.BARE_SHEET_NAME)

        string_case = stage1.sheet_qualified_reference_positions('="Other!B1"')
        self.assertEqual(len(string_case), 0)

    def test_quoted_sheet_name_with_escape_is_a_reference(self):
        result = self._run()
        matches = [
            info for pat, info in result.gate_b_patterns.items()
            if "Odd '' Name" in pat
        ]
        self.assertEqual(len(matches), 1)
        refs = stage1.sheet_qualified_reference_positions(matches[0].first_raw)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].kind, TokenKind.QUOTED_SHEET_NAME)

    def test_no_unknown_tokens_in_this_fixture(self):
        result = self._run()
        self.assertEqual(result.token_kind_totals.get(TokenKind.UNKNOWN.value, 0), 0)

    def test_determinism(self):
        formulas_doc, values_doc = build_stage1_pair()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath = write_pair(tmp, formulas_doc, values_doc)

            def pipeline():
                return stage1.run_stage1(fpath, vpath)

            result = verify_same_process_determinism(pipeline, run_label="synthetic stage-1")
        self.assertEqual(result.total_nonempty_formulas, 9)

    def test_main_runs_end_to_end_via_cli_entry_point(self):
        formulas_doc, values_doc = build_stage1_pair()
        with tempfile.TemporaryDirectory() as tmp:
            write_pair(tmp, formulas_doc, values_doc)
            exit_code = stage1.main([tmp])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
