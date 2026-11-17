"""Cross-process determinism for Stage 6, same reasoning as the earlier
stages (see test_cross_process_determinism.py for why an in-process check
cannot catch a PYTHONHASHSEED-only defect).

Unlike the earlier stages' checks, this one needs no private data: the
checkup is run over a synthetic workbook written into a temporary folder, so
it runs for anyone. A second check uses the real capture and a real app-side
parse directory when they are configured (the same opt-in environment
variables stage 5's check uses), and skips otherwise.
"""

import os
import tempfile
import unittest

from .stage6_support import STORED, column_rows, make_inputs
from .test_cross_process_determinism import (
    CrossProcessDeterminismTestCase,
    find_real_capture_dir,
    run_with_hash_seed,
)
from .test_cross_process_determinism_stage5 import _find_real_app_export_html, _find_real_appside_parse_dir

PLACEHOLDER = '"COMPUTED_VALUE"'


def _busy_workbook():
    names = ["Key", "A1", "B2", "C3", "D4", "E5", "F6"]
    cols = column_rows(
        "T", names,
        formulas={"B2": STORED, "C3": PLACEHOLDER, "D4": STORED, "E5": "RC[-4]*2", "F6": "RC[-1]"},
    )
    rows = [names]
    for r in range(2, 16):
        rows.append([
            f"k{r}",
            (f"=A{r}+1", 1),
            (f"=B{r}+{1 + r % 4}", 1),
            7 if r % 3 else (f"=A{r}", 1),
            (f"=D{r}+1", 1) if r != 9 else ("={1,2}", ""),
            (f"=A{r}*2", 1) if r % 2 else (f"=A{r}*{r % 5}", 1),
            None,
        ])
    return {"T": rows}, cols


class TestStage6SyntheticCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_synthetic_checkup_is_byte_identical_across_process_and_hash_seed(self):
        tabs, cols = _busy_workbook()
        with tempfile.TemporaryDirectory() as tmp:
            fpath, vpath, app_dir, html = make_inputs(tmp, tabs, cols, [("T", "ALL_CHANGES")])
            capture_dir = os.path.dirname(fpath)
            out0 = os.path.join(tmp, "stage6_seed0.json")
            out1 = os.path.join(tmp, "stage6_seed1.json")
            r0 = run_with_hash_seed("sheet_derivation.serialize_stage6", [capture_dir, out0, app_dir, html], seed="0")
            self.assertEqual(r0.returncode, 0, msg=f"seed=0 subprocess failed: {r0.stderr}")
            r1 = run_with_hash_seed("sheet_derivation.serialize_stage6", [capture_dir, out1, app_dir, html], seed="1")
            self.assertEqual(r1.returncode, 0, msg=f"seed=1 subprocess failed: {r1.stderr}")
            self.assert_files_byte_identical(out0, out1, context="synthetic workbook, Stage 6")
            with open(out0, encoding="utf-8") as fh:
                self.assertIn('"situation"', fh.read())  # the run produced real findings, not an absent artifact


class TestStage6RealCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_real_checkup_is_byte_identical_across_process_and_hash_seed(self):
        capture_dir = find_real_capture_dir()
        appside_dir = _find_real_appside_parse_dir()
        if capture_dir is None or appside_dir is None:
            self.skipTest(
                "real capture and/or a real app-side parse directory not configured -- set "
                "SHEET_DERIVATION_CAPTURE_DIR and SHEET_DERIVATION_APPSIDE_PARSE_DIR to run "
                "this check; skipping so the public test suite still runs without private data"
            )
        export_html = _find_real_app_export_html()
        extra = [export_html] if export_html else []
        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "stage6_real_seed0.json")
            out1 = os.path.join(tmp, "stage6_real_seed1.json")
            r0 = run_with_hash_seed("sheet_derivation.serialize_stage6", [capture_dir, out0, appside_dir] + extra, seed="0")
            self.assertEqual(r0.returncode, 0, msg=f"seed=0 subprocess failed: {r0.stderr}")
            r1 = run_with_hash_seed("sheet_derivation.serialize_stage6", [capture_dir, out1, appside_dir] + extra, seed="1")
            self.assertEqual(r1.returncode, 0, msg=f"seed=1 subprocess failed: {r1.stderr}")
            self.assert_files_byte_identical(out0, out1, context="real capture, Stage 6")


if __name__ == "__main__":
    unittest.main()
