"""Cross-process determinism for Stage 2 (Gate C4), same shape and same
reasoning as test_cross_process_determinism.py for Stage 0 and
test_cross_process_determinism_stage1.py for Stage 1 -- see that first
module's docstring for why an in-process check cannot catch a
PYTHONHASHSEED-only defect. This module runs the real check against the
real capture only (skipping cleanly if it is not present); the harness
self-test that the mechanism itself works already lives in Stage 0's
version and is not duplicated here.
"""

import os
import tempfile
import unittest

from .test_cross_process_determinism import (
    CrossProcessDeterminismTestCase,
    find_real_capture_dir,
    run_with_hash_seed,
)


class TestStage2RealCaptureCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_real_capture_is_byte_identical_across_process_and_hash_seed(self):
        capture_dir = find_real_capture_dir()
        if capture_dir is None:
            self.skipTest(
                "real capture not present -- set SHEET_DERIVATION_CAPTURE_DIR or place "
                "it at the sibling sheet_dumps/ directory to run this check; skipping "
                "so the public test suite still runs without private data"
            )

        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "stage2_seed0.json")
            out1 = os.path.join(tmp, "stage2_seed1.json")

            result0 = run_with_hash_seed(
                "sheet_derivation.serialize_stage2", [capture_dir, out0], seed="0"
            )
            self.assertEqual(result0.returncode, 0, msg=f"seed=0 subprocess failed: {result0.stderr}")
            result1 = run_with_hash_seed(
                "sheet_derivation.serialize_stage2", [capture_dir, out1], seed="1"
            )
            self.assertEqual(result1.returncode, 0, msg=f"seed=1 subprocess failed: {result1.stderr}")

            self.assert_files_byte_identical(out0, out1, context="real capture, Stage 2")


if __name__ == "__main__":
    unittest.main()
