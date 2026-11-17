"""Stage 6 (the formula checkup): situations, the judgment table, row
counting, the Case A / Case B boundary, the update settings, pairing, and
the absent paths. Synthetic fixtures only; see stage6_support.py for the
scenario codes."""

import os
import tempfile
import unittest

from .. import stage6
from ..determinism import verify_same_process_determinism
from ..serialize_stage6 import build_canonical_structure
from .fixtures import write_formula_columns_csv
from .stage6_support import (
    STORED,
    column_rows,
    finding,
    make_inputs,
    run_checkup,
    scenario,
    scenario_rows,
)

ADDS, EDITS, NEITHER = "ALL_CHANGES", "UPDATES_ONLY", "READ_ONLY"

PLACEHOLDER = '"COMPUTED_VALUE"'


class TestFormatRowRanges(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(stage6.format_row_ranges([]), "")
        self.assertEqual(stage6.format_row_ranges([5]), "5")
        self.assertEqual(stage6.format_row_ranges([2, 3, 4, 6]), "2-4, 6")
        self.assertEqual(stage6.format_row_ranges((31, 2, 3, 3, 23)), "2-3, 23, 31")


class TestUpdateModes(unittest.TestCase):
    def test_each_of_the_eight_values(self):
        expected = {
            "ALL_CHANGES": (True, True, stage6.KIND_ADDS),
            "ADDS_ONLY": (True, False, stage6.KIND_ADDS),
            "ADDS_AND_UPDATES": (True, True, stage6.KIND_ADDS),
            "ADDS_AND_DELETES": (True, False, stage6.KIND_ADDS),
            "UPDATES_ONLY": (False, True, stage6.KIND_EDITS_ONLY),
            "UPDATES_AND_DELETES": (False, True, stage6.KIND_EDITS_ONLY),
            "DELETES_ONLY": (False, False, stage6.KIND_NEITHER),
            "READ_ONLY": (False, False, stage6.KIND_NEITHER),
        }
        self.assertEqual(set(expected), set(stage6.UPDATE_MODES))
        for mode, (adds, edits, kind) in expected.items():
            with self.subTest(mode=mode):
                got = stage6.interpret_update_mode("T", {"T": mode})
                self.assertEqual(got, (mode, adds, edits, stage6.SETTING_EXPORTED, False))
                self.assertEqual(stage6.setting_kind(adds, edits), kind)

    def test_each_value_end_to_end(self):
        # An S1 column is "raised, likely" with adds, "raised, possible" with edits
        # only, and "not a problem" with neither: the tier shows the setting was read.
        want = {
            "ALL_CHANGES": (stage6.TIER_RAISED, "likely"),
            "ADDS_ONLY": (stage6.TIER_RAISED, "likely"),
            "ADDS_AND_UPDATES": (stage6.TIER_RAISED, "likely"),
            "ADDS_AND_DELETES": (stage6.TIER_RAISED, "likely"),
            "UPDATES_ONLY": (stage6.TIER_RAISED, "possible"),
            "UPDATES_AND_DELETES": (stage6.TIER_RAISED, "possible"),
            "DELETES_ONLY": (stage6.TIER_NOT_A_PROBLEM, None),
            "READ_ONLY": (stage6.TIER_NOT_A_PROBLEM, None),
        }
        for mode, (tier, grade) in want.items():
            with self.subTest(mode=mode):
                f = finding(scenario(["same", "same"], stored="", mode=mode), "T", "F")
                self.assertEqual(f.situation, stage6.S1)
                self.assertEqual((f.tier, f.grade), (tier, grade))
                self.assertEqual(f.update_mode, mode)
                self.assertFalse(f.setting_assumed)

    def test_empty_setting_is_both_and_said_so(self):
        f = finding(scenario(["same", "same"], stored="", mode=""), "T", "F")
        self.assertEqual((f.adds_allowed, f.edits_allowed), (True, True))
        self.assertTrue(f.setting_assumed)
        self.assertEqual(f.setting_basis, stage6.SETTING_ASSUMED_EMPTY)
        self.assertEqual(f.update_mode, "")
        self.assertTrue(any("allowing both adds and edits" in n for n in f.notes))

    def test_an_expression_or_unrecognized_value_is_both_and_said_so(self):
        for value in ('=IF([Locked],"READ_ONLY","ALL_CHANGES")', "SOMETHING_NEW", "all_changes"):
            with self.subTest(value=value):
                f = finding(scenario(["same", "same"], stored="", mode=value), "T", "F")
                self.assertEqual((f.adds_allowed, f.edits_allowed), (True, True))
                self.assertTrue(f.setting_assumed)
                self.assertEqual(f.setting_basis, stage6.SETTING_ASSUMED_UNRECOGNIZED)
                self.assertEqual(f.update_mode, value)  # as exported, untouched

    def test_missing_tables_file_is_both_and_said_once_at_the_top(self):
        result = scenario(["same", "same"], stored="", mode=None)
        f = finding(result, "T", "F")
        self.assertEqual((f.adds_allowed, f.edits_allowed), (True, True))
        self.assertTrue(f.setting_assumed)
        self.assertEqual(f.setting_basis, stage6.SETTING_ASSUMED_NO_FILE)
        self.assertIsNone(f.update_mode)
        self.assertFalse(result.checkup.tables_csv_found)
        self.assertIn("appsheet_tables.csv is absent", result.checkup.tables_csv_note)

    def test_table_missing_from_the_tables_file(self):
        cols = column_rows("T", ["Key", "F"], formulas={"F": ""})
        result = run_checkup({"T": scenario_rows(["same", "same"])}, cols, tables=[("Other", ADDS)])
        f = finding(result, "T", "F")
        self.assertEqual(f.setting_basis, stage6.SETTING_ASSUMED_NOT_LISTED)
        self.assertTrue(result.checkup.tables_csv_found)

    def test_setting_with_surrounding_space_is_still_recognized_and_kept_as_exported(self):
        got = stage6.interpret_update_mode("T", {"T": " READ_ONLY "})
        self.assertEqual(got, (" READ_ONLY ", False, False, stage6.SETTING_EXPORTED, False))


class TestJudgmentTable(unittest.TestCase):
    """Every situation under every kind of setting, run end to end."""

    CASES = {
        stage6.S1: dict(codes=["same", "same"], stored=""),
        stage6.S2A: dict(codes=["same", "same", "diff", "diff"], stored=STORED),  # a tie
        stage6.S2B: dict(codes=["same", "same", "same", "diff"], stored=STORED),
        stage6.S3: dict(codes=["none", "none", "blank"], stored=STORED),
        stage6.S4: dict(codes=["same", "none", "blank"], stored=PLACEHOLDER),
        stage6.S5: dict(codes=[], stored=STORED),
        stage6.S6: dict(codes=["same", "same", "same"], stored=STORED),
    }

    # (adds, edits-only, neither) -> (tier, grade)
    R, M, N = stage6.TIER_RAISED, stage6.TIER_MINOR, stage6.TIER_NOT_A_PROBLEM
    EXPECTED = {
        stage6.S1: {ADDS: (R, "likely"), EDITS: (R, "possible"), NEITHER: (N, None)},
        stage6.S2A: {ADDS: (R, "likely"), EDITS: (M, None), NEITHER: (M, None)},
        stage6.S2B: {ADDS: (R, "likely"), EDITS: (M, None), NEITHER: (M, None)},
        stage6.S3: {ADDS: (R, "likely"), EDITS: (M, None), NEITHER: (M, None)},
        stage6.S4: {ADDS: (R, "possible"), EDITS: (N, None), NEITHER: (N, None)},
        stage6.S5: {ADDS: (N, None), EDITS: (N, None), NEITHER: (N, None)},
        stage6.S6: {ADDS: (N, None), EDITS: (N, None), NEITHER: (N, None)},
    }

    def test_every_situation_under_every_kind_of_setting(self):
        for situation, case in self.CASES.items():
            for mode, (tier, grade) in self.EXPECTED[situation].items():
                with self.subTest(situation=situation, mode=mode):
                    f = finding(scenario(case["codes"], case["stored"], mode), "T", "F")
                    self.assertEqual(f.situation, situation)
                    self.assertEqual((f.tier, f.grade), (tier, grade))
                    self.assertEqual(stage6.JUDGMENT_TABLE[(f.allows, situation)].tier, tier)

    def test_the_table_holds_all_twenty_one_cells(self):
        self.assertEqual(len(stage6.JUDGMENT_TABLE), 21)
        for kind in (stage6.KIND_ADDS, stage6.KIND_EDITS_ONLY, stage6.KIND_NEITHER):
            for s in (stage6.S1, stage6.S2A, stage6.S2B, stage6.S3, stage6.S4, stage6.S5, stage6.S6):
                self.assertIn((kind, s), stage6.JUDGMENT_TABLE)

    def test_only_raised_findings_have_a_grade_and_a_rank(self):
        for situation, case in self.CASES.items():
            for mode in (ADDS, EDITS, NEITHER):
                f = finding(scenario(case["codes"], case["stored"], mode), "T", "F")
                with self.subTest(situation=situation, mode=mode):
                    self.assertEqual(f.tier == stage6.TIER_RAISED, f.grade is not None)
                    self.assertEqual(f.tier == stage6.TIER_RAISED, f.rank is not None)

    def test_statements_say_what_the_spec_says(self):
        s1 = finding(scenario(["same", "same"], "", ADDS), "T", "F")
        self.assertIn("a new row can erase it", s1.advice)
        s1e = finding(scenario(["same", "same"], "", EDITS), "T", "F")
        self.assertIn("might write the computed value over the formula", s1e.advice)
        self.assertIn("untested inference", s1e.advice)
        s2b = finding(scenario(["same", "same", "same", "diff"]), "T", "F")
        self.assertIn("only when every cell agrees", s2b.advice)
        self.assertIn("a risk, not a certainty", s2b.advice)
        s2a = finding(scenario(["same", "diff", "diff"]), "T", "F")
        self.assertIn("regenerate the table", s2a.advice)
        s3 = finding(scenario(["none", "none"]), "T", "F")
        self.assertIn("not regenerated after the formulas were removed", s3.advice)
        s4 = finding(scenario(["same", "none"], PLACEHOLDER), "T", "F")
        self.assertIn("breaking a spill", s4.advice)
        self.assertIn("no claim about whether a spill fills this column", s4.advice)
        s5 = finding(scenario([], STORED), "T", "F")
        self.assertIn("may lose that formula", s5.advice)
        for mode in (EDITS, NEITHER):
            minor = finding(scenario(["none", "none"], STORED, mode), "T", "F")
            self.assertEqual(minor.tier, stage6.TIER_MINOR)
        edits_minor = finding(scenario(["none", "none"], STORED, EDITS), "T", "F")
        self.assertIn("2026-11-14", edits_minor.advice)
        edits_s4 = finding(scenario(["same", "none"], PLACEHOLDER, EDITS), "T", "F")
        self.assertIn("2026-11-14", edits_s4.advice)


class TestRowCounting(unittest.TestCase):
    def test_key_in_the_sheet_counts_rows_with_a_key_value(self):
        # Row 4 has a value in F but no key: it does not count. Row 5 is blank.
        f = finding(scenario(["same", "same", "none!", "blank"]), "T", "F")
        self.assertEqual(f.row_basis, stage6.ROW_BASIS_KEY)
        self.assertEqual(f.key_column, "Key")
        self.assertEqual(f.key_sheet_column, "A")
        self.assertEqual(f.counted_rows, (2, 3, 5))  # rows 2, 3 and the blank-F row 5 (it has a key)
        self.assertEqual(f.matching_rows, (2, 3))
        self.assertEqual(f.no_formula_rows, (5,))

    def test_a_row_counts_through_its_formula_without_a_key(self):
        f = finding(scenario(["same", "same!"]), "T", "F")
        self.assertEqual(f.counted_rows, (2, 3))
        self.assertEqual(f.situation, stage6.S6)

    def test_truly_blank_rows_never_count(self):
        f = finding(scenario(["same", "blank!", "same", "blank!"]), "T", "F")
        self.assertEqual(f.counted_rows, (2, 4))

    def test_a_row_with_a_key_and_nothing_else_counts(self):
        f = finding(scenario(["same", "blank"]), "T", "F")
        self.assertEqual(f.counted_rows, (2, 3))
        self.assertEqual(f.no_formula_rows, (3,))
        self.assertEqual(f.blank_row_count, 1)
        self.assertEqual(f.situation, stage6.S2A)  # one matching row against one row with no formula: a tie

    def test_key_not_in_the_sheet_uses_any_value_in_any_paired_column(self):
        # The table's key is _RowNumber, which has no column in the sheet.
        cols = column_rows("T", ["_RowNumber", "Key", "F"], key="_RowNumber", formulas={"F": STORED})
        rows = [["Key", "F"],
                ["k2", ("=A2+1", 3)],
                [None, 7],            # a value in F only: counts
                [None, None],         # blank: does not count
                ["k5", None]]         # a value in Key only: counts
        f = finding(run_checkup({"T": rows}, cols, [("T", ADDS)]), "T", "F")
        self.assertEqual(f.row_basis, stage6.ROW_BASIS_ANY_PAIRED)
        self.assertIsNone(f.key_sheet_column)
        self.assertEqual(f.counted_rows, (2, 3, 5))
        self.assertIn("'_RowNumber'", f.row_basis_detail)
        self.assertTrue(any("key-based row set was unavailable" in n for n in f.notes))

    def test_virtual_key_is_not_a_sheet_column(self):
        cols = column_rows("T", ["Key", "F"], key="Key", virtual=("Key",), formulas={"F": STORED})
        rows = [["F"], [("=A2+1", 3)], [None], [7]]
        # Key is virtual and has no header; F sits in column A here.
        f = finding(run_checkup({"T": rows}, cols, [("T", ADDS)]), "T", "F")
        self.assertEqual(f.row_basis, stage6.ROW_BASIS_ANY_PAIRED)
        self.assertEqual(f.counted_rows, (2, 4))

    def test_no_key_flag_at_all_falls_back(self):
        f = finding(scenario(["same", "none", "blank!"], key_flag=False), "T", "F")
        self.assertEqual(f.row_basis, stage6.ROW_BASIS_ANY_PAIRED)
        self.assertIn("no column with key = Yes", f.row_basis_detail)
        self.assertEqual(f.counted_rows, (2, 3))

    def test_two_key_columns_fall_back(self):
        cols = column_rows("T", ["Key", "F"], key="Key", formulas={"F": STORED})
        cols[1]["key"] = "Yes"
        f = finding(run_checkup({"T": scenario_rows(["same", "same"])}, cols, [("T", ADDS)]), "T", "F")
        self.assertEqual(f.row_basis, stage6.ROW_BASIS_ANY_PAIRED)
        self.assertIn("more than one column with key = Yes", f.row_basis_detail)

    def test_an_empty_table(self):
        f = finding(scenario(["blank!", "blank!"], STORED), "T", "F")
        self.assertEqual(f.counted_rows, ())
        self.assertEqual(f.situation, stage6.S5)
        f = finding(scenario([], PLACEHOLDER), "T", "F")
        self.assertEqual(f.situation, stage6.S5)  # a placeholder in an empty table is S5, not S4

    def test_a_column_with_neither_a_formula_nor_a_stored_formula_is_not_examined(self):
        result = scenario(["none", "none", "blank"], stored="")
        self.assertEqual(result.checkup.findings, ())
        self.assertEqual(result.checkup.not_examined, ())

    def test_rows_above_and_at_the_header_row_never_count(self):
        f = finding(scenario(["same", "same"]), "T", "F")
        self.assertEqual(f.header_row1, 1)
        self.assertNotIn(1, f.counted_rows)


class TestCaseABoundary(unittest.TestCase):
    def sit(self, codes, stored=STORED):
        return finding(scenario(codes, stored), "T", "F").situation

    def test_a_tie_is_case_a(self):
        self.assertEqual(self.sit(["same", "same", "diff", "diff"]), stage6.S2A)

    def test_one_more_than_the_largest_other_group_is_case_b(self):
        self.assertEqual(self.sit(["same", "same", "same", "diff", "diff"]), stage6.S2B)

    def test_rows_with_no_formula_are_one_group_and_count_as_not_matching(self):
        self.assertEqual(self.sit(["same", "same", "none", "none"]), stage6.S2A)  # tie with the no-formula group
        self.assertEqual(self.sit(["same", "same", "same", "none", "none"]), stage6.S2B)
        self.assertEqual(self.sit(["same", "none"]), stage6.S2A)  # 1 against 1

    def test_blank_and_plain_value_rows_are_one_no_formula_group(self):
        # 3 matching, then 2 plain-value rows and 1 blank row: the no-formula group is 3, a tie.
        self.assertEqual(self.sit(["same", "same", "same", "none", "none", "blank"]), stage6.S2A)

    def test_each_group_of_differing_formulas_counts_on_its_own(self):
        # Four matching against two groups of two: 4 is more than any one group, so Case B,
        # even though 4 is not more than the 4 non-matching rows taken together.
        self.assertEqual(self.sit(["same"] * 4 + ["diff", "diff", "diff2", "diff2"]), stage6.S2B)
        # Two matching against two groups of two: a tie with each group, so Case A.
        self.assertEqual(self.sit(["same", "same", "diff", "diff", "diff2", "diff2"]), stage6.S2A)

    def test_no_row_matches(self):
        f = finding(scenario(["diff", "diff2"]), "T", "F")
        self.assertEqual(f.situation, stage6.S2A)
        self.assertEqual(f.matching_rows, ())

    def test_case_b_lists_the_non_matching_rows(self):
        f = finding(scenario(["same", "same", "same", "diff", "none", "same"]), "T", "F")
        self.assertEqual(f.situation, stage6.S2B)
        self.assertEqual(f.matching_rows, (2, 3, 4, 7))
        self.assertEqual(f.no_formula_rows, (6,))
        self.assertEqual(f.differing_groups[0].rows, (5,))
        self.assertIn("(5)", f.finding)
        self.assertIn("(6)", f.finding)

    def test_everything_agrees(self):
        f = finding(scenario(["same", "same", "same!"]), "T", "F")
        self.assertEqual(f.situation, stage6.S6)
        self.assertEqual(f.differing_groups, ())
        self.assertEqual(f.no_formula_rows, ())


class TestGroupingAndFlags(unittest.TestCase):
    def test_identical_relative_formulas_group_together(self):
        f = finding(scenario(["same", "diff", "diff", "diff2", "diff"]), "T", "F")
        groups = {g.canonical: g for g in f.differing_groups}
        self.assertEqual(len(groups), 2)
        plus2 = groups["RC[-1]+2"]
        self.assertEqual(plus2.rows, (3, 4, 6))
        self.assertEqual(plus2.representative_row, 3)
        self.assertEqual(plus2.raw_formula, "=A3+2")
        self.assertEqual(plus2.converted, "RC[-1]+2")
        self.assertEqual(groups["RC[-1]*2"].rows, (5,))

    def test_by_convention_forms_are_flagged_and_noted(self):
        cols = column_rows("T", ["Key", "F"], formulas={"F": STORED})
        rows = [["Key", "F"], ["k2", ("=SUM(A:A)", 1)], ["k3", ("=SUM(A:A)", 1)]]
        f = finding(run_checkup({"T": rows}, cols, [("T", ADDS)]), "T", "F")
        self.assertIn("whole column (A:A)", f.by_convention)
        self.assertIn("might be one of spelling", f.differing_groups[0].note)
        self.assertTrue(any("might be one of spelling" in n for n in f.notes))

    def test_nothing_is_flagged_when_every_form_is_attested(self):
        f = finding(scenario(["same", "diff"]), "T", "F")
        self.assertEqual(f.by_convention, ())

    def test_s1_groups_the_formulas_without_a_stored_formula(self):
        f = finding(scenario(["same", "same", "diff", "none"], stored=""), "T", "F")
        self.assertEqual(f.situation, stage6.S1)
        self.assertEqual(f.matching_rows, ())
        self.assertEqual([g.rows for g in f.differing_groups], [(2, 3), (4,)])
        self.assertEqual(f.formula_row_count, 3)


class TestPlaceholderAndConstants(unittest.TestCase):
    def test_placeholder_is_not_compared(self):
        f = finding(scenario(["same", "diff", "none", "blank"], PLACEHOLDER), "T", "F")
        self.assertEqual(f.situation, stage6.S4)
        self.assertEqual(f.placeholder_rows, (2, 3))
        self.assertEqual(f.matching_rows, ())
        self.assertEqual(f.differing_groups, ())
        self.assertEqual((f.formula_row_count, f.value_only_row_count, f.blank_row_count), (2, 1, 1))
        self.assertIn("COMPUTED_VALUE", f.finding)

    def test_placeholder_without_its_quotes_is_an_ordinary_formula(self):
        f = finding(scenario(["same", "same"], "COMPUTED_VALUE"), "T", "F")
        self.assertEqual(f.situation, stage6.S2A)  # compared, and not the same

    def test_a_stored_constant_against_plain_values_is_case_s3(self):
        f = finding(scenario(["const", "const"], "0.23"), "T", "F")
        self.assertEqual(f.situation, stage6.S3)
        self.assertEqual(f.value_only_row_count, 2)
        self.assertIn("none of the 2 counted rows holds a formula", f.finding)

    def test_a_stored_constant_against_a_formula_that_is_the_constant_agrees(self):
        cols = column_rows("T", ["Key", "F"], formulas={"F": "0.23"})
        rows = [["Key", "F"], ["k2", ("=0.23", 0.23)], ["k3", ("=0.23", 0.23)]]
        f = finding(run_checkup({"T": rows}, cols, [("T", ADDS)]), "T", "F")
        self.assertEqual(f.situation, stage6.S6)


class TestUncomparedCells(unittest.TestCase):
    def test_an_uncompared_cell_is_left_out_and_said_so(self):
        result = scenario(["same", "same", "bad"])
        f = finding(result, "T", "F")
        self.assertEqual(f.situation, stage6.S6)
        self.assertEqual([u.row for u in f.uncompared], [4])
        self.assertEqual(f.uncompared[0].cell, "B4")
        self.assertEqual(f.uncompared[0].raw_formula, "={1,2}")
        self.assertTrue(f.uncompared[0].reason)
        self.assertEqual(f.formula_row_count, 3)
        self.assertTrue(any("could not be compared" in n for n in f.notes))
        self.assertEqual(len(result.checkup.residue), 1)
        self.assertEqual(result.checkup.residue[0].locations, ("T!B4",))

    def test_an_uncompared_cell_does_not_make_a_row_match_or_differ(self):
        f = finding(scenario(["same", "bad", "diff", "diff"]), "T", "F")
        self.assertEqual(f.matching_rows, (2,))
        self.assertEqual(f.differing_groups[0].rows, (4, 5))
        self.assertEqual(f.situation, stage6.S2A)  # 1 matching row against a group of 2

    def test_a_column_where_no_cell_could_be_compared_is_a_run_problem(self):
        for mode in (ADDS, EDITS, NEITHER):
            with self.subTest(mode=mode):
                f = finding(scenario(["bad", "bad", "none"], STORED, mode), "T", "F")
                self.assertEqual(f.situation, stage6.COULD_NOT_COMPARE)
                self.assertEqual(f.tier, stage6.TIER_RUN_PROBLEM)
                self.assertIsNone(f.grade)
                self.assertIsNone(f.rank)

    def test_s1_does_not_need_the_formulas_to_convert(self):
        f = finding(scenario(["bad", "same"], stored=""), "T", "F")
        self.assertEqual(f.situation, stage6.S1)
        self.assertEqual(len(f.uncompared), 1)


class TestPairing(unittest.TestCase):
    def test_a_whitespace_near_miss_label_is_examined_and_flagged(self):
        cols = column_rows("T", ["Key", "F", "G"], formulas={"F": STORED})
        rows = [["Key", "F ", "G"], ["k2", ("=A2+1", 3), 1], ["k3", ("=A3+1", 4), 2]]
        result = run_checkup({"T": rows}, cols, [("T", ADDS)])
        f = finding(result, "T", "F")
        self.assertEqual(f.label_state, "whitespace-near-miss")
        self.assertEqual(f.label_text, "F ")
        self.assertEqual(f.sheet_column, "B")
        self.assertEqual(f.situation, stage6.S6)

    def test_stored_formula_with_no_matching_label_is_not_examined(self):
        cols = column_rows("T", ["Key", "F", "Ghost"], formulas={"Ghost": "RC[-1]"})
        rows = [["Key", "F"], ["k2", 1]]
        result = run_checkup({"T": rows}, cols, [("T", ADDS)])
        self.assertEqual(result.checkup.findings, ())
        (n,) = result.checkup.not_examined
        self.assertEqual((n.table, n.column, n.stored_formula), ("T", "Ghost", "RC[-1]"))
        self.assertIn("no header label", n.reason)

    def test_stored_formula_on_a_virtual_column_is_not_examined(self):
        cols = column_rows("T", ["Key", "F", "V"], virtual=("V",), formulas={"V": "RC[-1]"})
        result = run_checkup({"T": [["Key", "F"], ["k2", 1]]}, cols, [("T", ADDS)])
        (n,) = result.checkup.not_examined
        self.assertEqual(n.column, "V")
        self.assertIn("virtual", n.reason)

    def test_stored_formula_in_a_table_with_no_tab_is_not_examined(self):
        cols = column_rows("T", ["Key", "F"]) + column_rows("N", ["A1"], key="A1", formulas={"A1": "RC[-1]"})
        result = run_checkup({"T": [["Key", "F"], ["k2", 1]]}, cols, [("T", ADDS)], worksheets={"N": None})
        (n,) = result.checkup.not_examined
        self.assertEqual((n.table, n.column), ("N", "A1"))
        self.assertIn("no tab", n.reason)

    def test_stored_formula_on_a_tab_whose_header_is_not_identified_is_not_examined(self):
        # Text over text, with no export schema to read the header from: stage 4 cannot decide.
        cols = column_rows("U", ["Name", "Amount"], key="Name", formulas={"Amount": "RC[-1]"})
        rows = [["Name", "Amount"], ["Alice", "Cash"], ["Bob", "Cash"]]
        result = run_checkup({"U": rows}, cols, [("U", ADDS)], export_columns=False)
        self.assertEqual(result.checkup.findings, ())
        (n,) = result.checkup.not_examined
        self.assertEqual(n.column, "Amount")
        self.assertIn("header row", n.reason)
        self.assertIn("row basis is uncertain", n.reason)

    def test_not_examined_columns_are_never_silently_dropped(self):
        cols = column_rows("T", ["Key", "F", "G", "H"], virtual=("H",), formulas={"G": "RC[-1]", "H": "RC[-1]"})
        result = run_checkup({"T": [["Key", "F"], ["k2", 1]]}, cols, [("T", ADDS)])
        self.assertEqual({n.column for n in result.checkup.not_examined}, {"G", "H"})


class TestRanking(unittest.TestCase):
    def test_raised_findings_are_ranked_and_s1_with_adds_ranks_highest(self):
        names = ["Key", "A1", "B2", "C3", "D4"]
        cols = column_rows("T", names, formulas={"B2": STORED, "C3": STORED, "D4": STORED})
        rows = [
            names,
            ["k2", ("=A2+1", 1), ("=B2+1", 1), 7, ("=D2+1", 1)],   # each formula refers to the cell to its left
            ["k3", ("=A3+1", 1), ("=B3+2", 1), 7, ("=D3+1", 1)],   # B2's formula differs in this row
        ]
        # A1 has no stored formula but holds formulas: S1. B2: 1 match, 1 differing: a tie, S2A.
        # C3: none in the sheet: S3. D4: S6.
        result = run_checkup({"T": rows}, cols, [("T", ADDS)])
        by_col = {f.column: f for f in result.checkup.findings}
        self.assertEqual(by_col["A1"].situation, stage6.S1)
        self.assertEqual(by_col["B2"].situation, stage6.S2A)
        self.assertEqual(by_col["C3"].situation, stage6.S3)
        self.assertEqual(by_col["D4"].situation, stage6.S6)
        self.assertEqual((by_col["A1"].rank, by_col["B2"].rank, by_col["C3"].rank), (1, 2, 3))
        self.assertIsNone(by_col["D4"].rank)

    def test_ranks_run_from_one_without_gaps(self):
        names = ["Key", "A1", "B2"]
        cols = column_rows("T", names)
        rows = [names, ["k2", ("=A2+1", 1), ("=A2+2", 1)], ["k3", ("=A3+1", 1), 5]]
        result = run_checkup({"T": rows}, cols, [("T", EDITS)])
        ranks = sorted(f.rank for f in result.checkup.findings if f.rank is not None)
        self.assertEqual(ranks, list(range(1, len(ranks) + 1)))
        self.assertEqual(len(ranks), 2)


class TestAbsentPaths(unittest.TestCase):
    def test_no_app_side_directory_gives_an_absent_artifact_and_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, _, _ = make_inputs(
                tmp, {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED})
            )
            result = stage6.run_stage6(fpath, vpath, appside_parse_dir=None)
        self.assertFalse(result.checkup.present)
        self.assertEqual(result.checkup.findings, ())
        self.assertIn("ABSENT", result.checkup.reliability_condition)
        self.assertIsNone(result.stage5)

    def test_a_directory_without_the_columns_file_gives_an_absent_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, _, _ = make_inputs(
                tmp, {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED})
            )
            empty = os.path.join(tmp, "empty")
            os.makedirs(empty)
            result = stage6.run_stage6(fpath, vpath, appside_parse_dir=empty)
        self.assertFalse(result.checkup.present)
        self.assertIn("stage 5's join is ABSENT", result.checkup.absent_reason)

    def test_a_columns_file_without_the_stored_formula_field_gives_an_absent_artifact(self):
        fields = ["table_name", "column_name", "is_virtual", "key"]
        result = run_checkup(
            {"T": scenario_rows(["same"])}, column_rows("T", ["Key", "F"], formulas={"F": STORED}),
            [("T", ADDS)], columns_fields=fields,
        )
        self.assertFalse(result.checkup.present)
        self.assertIn("spreadsheet_formula", result.checkup.absent_reason)

    def test_a_precomputed_stage5_result_is_used_as_it_is(self):
        from .. import stage5
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, app_dir, html = make_inputs(
                tmp, {"T": scenario_rows(["same", "same"])},
                column_rows("T", ["Key", "F"], formulas={"F": STORED}), [("T", ADDS)],
            )
            s5 = stage5.run_stage5(fpath, vpath, appside_parse_dir=app_dir, app_export_html_path=html)
            via_given = stage6.run_stage6(fpath, vpath, stage5_result=s5)
            direct = stage6.run_stage6(fpath, vpath, appside_parse_dir=app_dir, app_export_html_path=html)
        self.assertIs(via_given.stage5, s5)
        self.assertEqual(build_canonical_structure(via_given), build_canonical_structure(direct))


class TestReliabilityAndDeterminism(unittest.TestCase):
    def test_every_artifact_states_its_reliability_condition_and_capture_date(self):
        result = scenario(["same", "diff"])
        self.assertIn("same version of the app", result.checkup.reliability_condition)
        self.assertTrue(result.checkup.stamp.capture_date)
        self.assertTrue(result.checkup.stamp.tool_commit)

    def test_same_process_determinism_on_a_busy_workbook(self):
        names = ["Key", "A1", "B2", "C3"]
        cols = column_rows("T", names, formulas={"B2": STORED, "C3": PLACEHOLDER})
        rows = [names] + [
            [f"k{r}", (f"=A{r}+1", 1), (f"=A{r}+{1 + (r % 3)}", 1), (f"=A{r}*2", 1) if r % 2 else 5]
            for r in range(2, 14)
        ]

        def pipeline():
            return build_canonical_structure(run_checkup({"T": rows}, cols, [("T", ADDS)]))

        verify_same_process_determinism(pipeline, run_label="synthetic stage-6")


if __name__ == "__main__":
    unittest.main()
