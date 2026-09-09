"""Cross-process determinism for Stage 5 (Gate C4), same shape and same
reasoning as the Stage 0-4 versions before it -- see
test_cross_process_determinism.py's own docstring for why an in-process
check cannot catch a PYTHONHASHSEED-only defect.

Two checks. The first needs no private data: it runs the join in ABSENT
mode (no app-side parse), which is a real code path every public clone
can exercise. The second is the real thing -- a genuine app-side parse
directory, found the same opt-in way the real capture is (an environment
variable, since a parse directory is exactly as private as the capture
it was built from) -- and skips cleanly when one is not configured.
"""

import os
import tempfile
import unittest

from .test_cross_process_determinism import (
    CrossProcessDeterminismTestCase,
    find_real_capture_dir,
    run_with_hash_seed,
)


def _find_real_appside_parse_dir():
    """Opt-in only, via SHEET_DERIVATION_APPSIDE_PARSE_DIR -- this module
    never guesses a parse directory's location from the capture's own
    directory or from any naming convention, for the same reason
    stage5.py itself never does: there is no recorded link between the
    two, confirmed during the stage 5 precheck."""
    env_dir = os.environ.get("SHEET_DERIVATION_APPSIDE_PARSE_DIR")
    if env_dir and os.path.isdir(env_dir) and os.path.isfile(os.path.join(env_dir, "appsheet_columns.csv")):
        return env_dir
    return None


class TestStage5AbsentModeCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_absent_mode_is_byte_identical_across_process_and_hash_seed(self):
        capture_dir = find_real_capture_dir()
        if capture_dir is None:
            self.skipTest(
                "real capture not present -- set SHEET_DERIVATION_CAPTURE_DIR or place "
                "it at the sibling sheet_dumps/ directory to run this check; skipping "
                "so the public test suite still runs without private data"
            )

        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "stage5_absent_seed0.json")
            out1 = os.path.join(tmp, "stage5_absent_seed1.json")

            result0 = run_with_hash_seed("sheet_derivation.serialize_stage5", [capture_dir, out0], seed="0")
            self.assertEqual(result0.returncode, 0, msg=f"seed=0 subprocess failed: {result0.stderr}")
            result1 = run_with_hash_seed("sheet_derivation.serialize_stage5", [capture_dir, out1], seed="1")
            self.assertEqual(result1.returncode, 0, msg=f"seed=1 subprocess failed: {result1.stderr}")

            self.assert_files_byte_identical(out0, out1, context="real capture, Stage 5 (absent mode)")


class TestStage5RealJoinCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_real_join_is_byte_identical_across_process_and_hash_seed(self):
        capture_dir = find_real_capture_dir()
        appside_dir = _find_real_appside_parse_dir()
        if capture_dir is None or appside_dir is None:
            self.skipTest(
                "real capture and/or a real app-side parse directory not configured -- set "
                "SHEET_DERIVATION_CAPTURE_DIR and SHEET_DERIVATION_APPSIDE_PARSE_DIR to run "
                "this check; skipping so the public test suite still runs without private data"
            )

        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "stage5_join_seed0.json")
            out1 = os.path.join(tmp, "stage5_join_seed1.json")

            result0 = run_with_hash_seed(
                "sheet_derivation.serialize_stage5", [capture_dir, out0, appside_dir], seed="0"
            )
            self.assertEqual(result0.returncode, 0, msg=f"seed=0 subprocess failed: {result0.stderr}")
            result1 = run_with_hash_seed(
                "sheet_derivation.serialize_stage5", [capture_dir, out1, appside_dir], seed="1"
            )
            self.assertEqual(result1.returncode, 0, msg=f"seed=1 subprocess failed: {result1.stderr}")

            self.assert_files_byte_identical(out0, out1, context="real capture, Stage 5 (real join)")


if __name__ == "__main__":
    unittest.main()
