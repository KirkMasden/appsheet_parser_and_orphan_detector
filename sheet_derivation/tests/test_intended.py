"""The intended-items record: app name, the command and its refusals, the
file's format and atomic write, and the fingerprint."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from .. import intended
from ..stage6_artifacts import column_line, write_stage6_artifacts
from .stage6_support import STORED, finding, scenario

APP = "/appsheet/data/TestApp-123"


def _main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = intended.main(argv)
    return code, out.getvalue(), err.getvalue()


def _sheet_dir(tmp, codes, stored=STORED, mode="ALL_CHANGES", app_folder=APP, name="sheet"):
    result = scenario(codes, stored, mode, app_folder=app_folder)
    path = os.path.join(tmp, name)
    write_stage6_artifacts(result, path)
    return path


def _fp(codes, stored=STORED, mode="ALL_CHANGES"):
    return intended.checkup_fingerprint(column_line(finding(scenario(codes, stored, mode), "T", "F")))


class TestDeriveAppName(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(intended.derive_app_name("/appsheet/data/KankakuV19-230844"), "KankakuV19")
        self.assertEqual(intended.derive_app_name("/appsheet/data/260411KankakuV18-230844"), "260411KankakuV18")

    def test_only_the_final_hyphen_and_digits_go(self):
        self.assertEqual(intended.derive_app_name("/appsheet/data/My-App-Two-77"), "My-App-Two")
        self.assertEqual(intended.derive_app_name("/appsheet/data/App 3-5"), "App 3")
        self.assertEqual(intended.derive_app_name("/appsheet/data/KankakuV19-230844/"), "KankakuV19")

    def test_missing_or_odd_names_give_none(self):
        for value in (None, "", "   ", "/appsheet/data/", "/appsheet/data/NoDigitsHere", "/appsheet/data/App-",
                      "/appsheet/data/-123", "/appsheet/data/App-12x", 5):
            with self.subTest(value=value):
                self.assertIsNone(intended.derive_app_name(value))

    def test_a_name_that_could_not_be_a_file_name_gives_none(self):
        self.assertIsNone(intended.derive_app_name("/appsheet/data/.hidden-1"))
        self.assertFalse(intended.is_safe_app_name("a/b"))
        self.assertFalse(intended.is_safe_app_name(""))

    def test_default_folder_is_intended_in_the_workspace(self):
        folder = intended.default_intended_dir()
        self.assertEqual(os.path.basename(folder), "intended")
        self.assertTrue(os.path.isdir(os.path.dirname(folder)))
        self.assertTrue(os.path.isdir(os.path.join(os.path.dirname(folder), "appsheet_parser_and_orphan_detector-main")))


class TestAddCommand(unittest.TestCase):
    def test_add_writes_the_entry_and_prints_what_it_did(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "same", "same", "diff"])
            idir = os.path.join(tmp, "intended")
            self.assertFalse(os.path.exists(idir))
            code, out, err = _main(["add", sheet, "T", "F", "--note", "odd row is on purpose", "--intended-dir", idir])
            self.assertEqual(code, 0, msg=err)
            self.assertIn("added checkup:T|F", out)
            self.assertIn("S2B", out)
            with open(os.path.join(idir, "TestApp.json"), encoding="utf-8") as fh:
                data = json.load(fh)
        self.assertEqual(data["app"], "TestApp")
        (e,) = data["entries"]
        self.assertEqual((e["kind"], e["table"], e["column"], e["situation"], e["rows"]), ("checkup", "T", "F", "S2B", "5"))
        self.assertEqual(e["note"], "odd row is on purpose")
        self.assertRegex(e["declared"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual(len(e["fingerprint"]), 64)

    def test_minor_findings_can_be_declared_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "diff"], mode="READ_ONLY")
            code, out, err = _main(["add", sheet, "T", "F", "--intended-dir", os.path.join(tmp, "i")])
        self.assertEqual(code, 0, msg=err)

    def test_refuses_not_a_problem_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "same"])
            idir = os.path.join(tmp, "intended")
            code, out, err = _main(["add", sheet, "T", "F", "--intended-dir", idir])
            self.assertEqual(code, 1)
            self.assertIn("not a problem", err)
            self.assertIn("nothing was changed", err)
            self.assertFalse(os.path.exists(idir))

    def test_refuses_run_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["bad", "bad", "none"])
            code, out, err = _main(["add", sheet, "T", "F", "--intended-dir", os.path.join(tmp, "i")])
        self.assertEqual(code, 1)
        self.assertIn("run problem", err)

    def test_refuses_a_column_not_in_the_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "diff"])
            code, out, err = _main(["add", sheet, "T", "Nope", "--intended-dir", os.path.join(tmp, "i")])
        self.assertEqual(code, 1)
        self.assertIn("is not in the checkup", err)

    def test_refuses_when_there_is_no_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _main(["add", tmp, "T", "F", "--intended-dir", os.path.join(tmp, "i")])
        self.assertEqual(code, 1)
        self.assertIn("run the checkup first", err)

    def test_refuses_when_the_app_name_cannot_be_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "diff"], app_folder=None)
            idir = os.path.join(tmp, "i")
            code, out, err = _main(["add", sheet, "T", "F", "--intended-dir", idir])
            self.assertEqual(code, 1)
            self.assertIn("could not be derived", err)
            self.assertFalse(os.path.exists(idir))

    def test_adding_again_replaces_the_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = _sheet_dir(tmp, ["same", "same", "same", "diff"])
            idir = os.path.join(tmp, "i")
            _main(["add", sheet, "T", "F", "--note", "first", "--intended-dir", idir])
            code, out, err = _main(["add", sheet, "T", "F", "--note", "second", "--intended-dir", idir])
            with open(os.path.join(idir, "TestApp.json"), encoding="utf-8") as fh:
                entries = json.load(fh)["entries"]
        self.assertIn("replaced the entry for", out)
        self.assertEqual([e["note"] for e in entries], ["second"])


class TestOtherCommands(unittest.TestCase):
    def test_add_orphan_list_and_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            code, out, err = _main(["add-orphan", "TestApp", "view", "Old Detail", "--note", "kept for a bot", "--intended-dir", idir])
            self.assertEqual(code, 0, msg=err)
            self.assertIn("added orphan:view|Old Detail", out)
            sheet = _sheet_dir(tmp, ["same", "same", "same", "diff"])
            _main(["add", sheet, "T", "F", "--intended-dir", idir])
            code, out, err = _main(["list", "--app", "TestApp", "--intended-dir", idir])
            self.assertEqual(code, 0)
            self.assertIn("2 entries", out)
            self.assertIn("checkup:T|F", out)
            self.assertIn("orphan:view|Old Detail", out)
            self.assertIn("note: kept for a bot", out)
            code, out, err = _main(["list", "--sheet-dir", sheet, "--intended-dir", idir])
            self.assertIn("2 entries", out)
            code, out, err = _main(["remove", "--app", "TestApp", "orphan:view|Old Detail", "--intended-dir", idir])
            self.assertEqual(code, 0, msg=err)
            self.assertIn("1 entry left", out)
            code, out, err = _main(["remove", "--app", "TestApp", "orphan:view|Old Detail", "--intended-dir", idir])
            self.assertEqual(code, 1)
            self.assertIn("no entry", err)

    def test_list_with_no_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _main(["list", "--app", "Nobody", "--intended-dir", os.path.join(tmp, "i")])
            self.assertEqual(code, 0)
            self.assertIn("no record for app 'Nobody'", out)
            self.assertFalse(os.path.exists(os.path.join(tmp, "i")))

    def test_orphan_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            for argv in (["add-orphan", "a/b", "view", "x"], ["add-orphan", "App", "", "x"], ["add-orphan", "App", "view", "  "]):
                with self.subTest(argv=argv):
                    code, out, err = _main(argv + ["--intended-dir", idir])
                    self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(idir))

    def test_an_unreadable_record_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            os.makedirs(idir)
            path = os.path.join(idir, "App.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            code, out, err = _main(["add-orphan", "App", "view", "x", "--intended-dir", idir])
            self.assertEqual(code, 1)
            self.assertIn("refusing to change the record", err)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "{not json")


class TestFileFormat(unittest.TestCase):
    def test_file_is_indented_sorted_and_ends_with_a_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            _main(["add-orphan", "App", "view", "Zed", "--intended-dir", idir])
            _main(["add-orphan", "App", "action", "Alpha", "--note", "n", "--intended-dir", idir])
            with open(os.path.join(idir, "App.json"), encoding="utf-8") as fh:
                text = fh.read()
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "entries": [\n', text)
        data = json.loads(text)
        self.assertEqual(list(data), sorted(data))  # keys sorted
        for e in data["entries"]:
            self.assertEqual(list(e), sorted(e))
        self.assertEqual([e["name"] for e in data["entries"]], ["Alpha", "Zed"])  # entries sorted

    def test_write_is_atomic_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "i")
            _main(["add-orphan", "App", "view", "One", "--intended-dir", idir])
            path = os.path.join(idir, "App.json")
            with open(path, "rb") as fh:
                before = fh.read()
            with mock.patch("sheet_derivation.intended.json.dump", side_effect=RuntimeError("disk full")):
                with self.assertRaises(RuntimeError):
                    intended.cmd_add_orphan("App", "view", "Two", None, idir)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), before)  # the old file is intact
            self.assertEqual(os.listdir(idir), ["App.json"])  # and no temporary file is left

    def test_folder_is_created_only_by_the_first_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            idir = os.path.join(tmp, "deep", "intended")
            _main(["list", "--app", "App", "--intended-dir", idir])
            self.assertFalse(os.path.exists(idir))
            _main(["add-orphan", "App", "view", "One", "--intended-dir", idir])
            self.assertTrue(os.path.isfile(os.path.join(idir, "App.json")))


class TestFingerprint(unittest.TestCase):
    def test_a_case_b_entry_survives_an_added_normal_row(self):
        base = _fp(["same", "same", "same", "diff"])
        self.assertEqual(_fp(["same", "same", "same", "diff", "same"]), base)
        self.assertEqual(_fp(["same", "same", "same", "diff", "same", "same"]), base)

    def test_a_case_b_entry_lapses_when_a_second_odd_row_appears(self):
        self.assertNotEqual(_fp(["same", "same", "same", "diff", "diff"]), _fp(["same", "same", "same", "diff"]))
        self.assertNotEqual(_fp(["same", "same", "same", "diff", "none"]), _fp(["same", "same", "same", "diff"]))

    def test_it_lapses_when_the_stored_formula_changes(self):
        self.assertNotEqual(_fp(["same", "same", "same", "diff"], stored="RC[-1]+3"), _fp(["same", "same", "same", "diff"]))

    def test_it_lapses_when_the_odd_row_changes_its_formula(self):
        self.assertNotEqual(_fp(["same", "same", "same", "diff2"]), _fp(["same", "same", "same", "diff"]))

    def test_an_s1_entry_survives_an_added_row_without_a_formula(self):
        base = _fp(["same", "same"], stored="")
        self.assertEqual(_fp(["same", "same", "none"], stored=""), base)
        self.assertEqual(_fp(["same", "same", "blank"], stored=""), base)
        self.assertNotEqual(_fp(["same", "same", "same"], stored=""), base)  # a new formula row is a change

    def test_rows_without_a_formula_count_for_s2_only(self):
        self.assertNotEqual(_fp(["same", "same", "same", "none"]), _fp(["same", "same", "same", "none", "none"]))
        # S3: stored formula, none in the sheet: more plain rows do not change the finding
        self.assertEqual(_fp(["none", "none"]), _fp(["none", "none", "none"]))

    def test_it_lapses_when_the_tier_changes_with_the_table_setting(self):
        self.assertNotEqual(_fp(["none", "none"], mode="ALL_CHANGES"), _fp(["none", "none"], mode="READ_ONLY"))

    def test_it_ignores_the_declaration_fields_themselves(self):
        line = column_line(finding(scenario(["same", "same", "same", "diff"]), "T", "F"))
        a = intended.checkup_fingerprint(line)
        line["intended"] = {"dateDeclared": "2026-01-01", "note": "x"}
        line["rank"] = 9
        line["notes"] = ["something"]
        self.assertEqual(intended.checkup_fingerprint(line), a)

    def test_orphan_fingerprint_is_kind_and_name(self):
        self.assertEqual(intended.orphan_fingerprint("view", "A"), intended.orphan_fingerprint("view", "A"))
        self.assertNotEqual(intended.orphan_fingerprint("view", "A"), intended.orphan_fingerprint("action", "A"))
        self.assertNotEqual(intended.orphan_fingerprint("view", "A"), intended.orphan_fingerprint("view", "B"))


if __name__ == "__main__":
    unittest.main()
