"""Cross-process determinism: the check the in-process one cannot do.

determinism.py's `verify_same_process_determinism` runs a pipeline twice in
one interpreter, which catches unstable iteration order within a run. It
cannot catch instability that only appears BETWEEN processes, because
CPython randomizes string/bytes hashing per interpreter launch
(PYTHONHASHSEED) unless pinned. A `set` built from the same strings can
iterate in one order in this process and a different order in the next,
while looking perfectly stable to any single-process check.

This module runs the real check two ways:

1. `test_harness_detects_a_real_cross_process_difference` -- always runs,
   needs no private data. It launches a small fixture script (which
   deliberately emits an unsorted-set collection) under two different
   PYTHONHASHSEED values and confirms the byte-comparison mechanism
   actually reports a difference. This is the harness testing itself,
   the same way test_determinism.py's own
   `test_harness_actually_detects_a_forced_difference` does for the
   in-process check.

2. `test_real_capture_is_byte_identical_across_process_and_hash_seed` --
   runs Stage 0 against the real Kankaku capture, twice, in fresh
   subprocesses, with PYTHONHASHSEED=0 and PYTHONHASHSEED=1 (explicitly
   different, never a single pinned seed -- pinning one seed would hide
   exactly the defect this check exists to find). Skips with a clear
   message if the capture is not present, so the public repo's test suite
   runs for anyone who has not captured or been given a workbook.
"""

import filecmp
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ..errors import CaptureIntegrityError
from ..loader import discover_capture_files

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBPROCESS_TIMEOUT_SECONDS = 300


def find_real_capture_dir():
    """Where the real capture lives, if it is present on this machine.

    Checked in order: the SHEET_DERIVATION_CAPTURE_DIR environment
    variable (so anyone with their own capture, anywhere, can point the
    suite at it); then the conventional sibling location this project
    actually uses, `<repo's parent>/sheet_dumps`. Returns None -- never
    raises -- if neither yields a directory holding a valid formulas/values
    pair, since "not present" is the expected case for a public clone.
    """
    candidates = []
    env_dir = os.environ.get("SHEET_DERIVATION_CAPTURE_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates.append(str(_REPO_ROOT.parent / "sheet_dumps"))

    for candidate in candidates:
        if not os.path.isdir(candidate):
            continue
        try:
            discover_capture_files(candidate)
        except CaptureIntegrityError:
            continue
        return candidate
    return None


def find_first_difference(obj1, obj2, path="root"):
    """Walks two JSON-loaded structures in parallel and names the first
    point where they diverge, so a cross-process failure names exactly
    what was unsorted rather than just reporting "files differ"."""
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        keys1, keys2 = list(obj1.keys()), list(obj2.keys())
        if keys1 != keys2:
            return f"{path}: dict key order or membership differs: {keys1} vs {keys2}"
        for key in keys1:
            diff = find_first_difference(obj1[key], obj2[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(obj1, list) and isinstance(obj2, list):
        if len(obj1) != len(obj2):
            return f"{path}: list length differs: {len(obj1)} vs {len(obj2)}"
        for i, (a, b) in enumerate(zip(obj1, obj2)):
            diff = find_first_difference(a, b, f"{path}[{i}]")
            if diff:
                return diff
        return None
    if obj1 != obj2:
        return f"{path}: value differs: {obj1!r} vs {obj2!r}"
    return None


def run_with_hash_seed(module: str, args, seed: str):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    return subprocess.run(
        [sys.executable, "-m", module] + list(args),
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class CrossProcessDeterminismTestCase(unittest.TestCase):
    def assert_files_byte_identical(self, path1: str, path2: str, context: str):
        if filecmp.cmp(path1, path2, shallow=False):
            return
        with open(path1, encoding="utf-8") as f1, open(path2, encoding="utf-8") as f2:
            obj1 = json.load(f1)
            obj2 = json.load(f2)
        first_diff = find_first_difference(obj1, obj2)
        self.fail(
            f"{context}: two subprocess runs with different PYTHONHASHSEED values "
            f"produced different output -- this is a real cross-process determinism "
            f"defect, not something to sort away without understanding it.\n"
            f"First difference: {first_diff}"
        )


class TestHarnessDetectsARealDifference(CrossProcessDeterminismTestCase):
    """Proves the mechanism works, independent of whether the real tool
    currently has anything for it to catch. Needs no private data."""

    def test_harness_detects_a_real_cross_process_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "seed0.json")
            out1 = os.path.join(tmp, "seed1.json")

            result0 = run_with_hash_seed(
                "sheet_derivation.tests._hash_sensitive_fixture", [out0], seed="0"
            )
            self.assertEqual(result0.returncode, 0, msg=result0.stderr)
            result1 = run_with_hash_seed(
                "sheet_derivation.tests._hash_sensitive_fixture", [out1], seed="1"
            )
            self.assertEqual(result1.returncode, 0, msg=result1.stderr)

            with self.assertRaises(AssertionError):
                self.assert_files_byte_identical(out0, out1, context="harness self-test")


class TestRealCaptureCrossProcessDeterminism(CrossProcessDeterminismTestCase):
    def test_real_capture_is_byte_identical_across_process_and_hash_seed(self):
        capture_dir = find_real_capture_dir()
        if capture_dir is None:
            self.skipTest(
                "real capture not present -- set SHEET_DERIVATION_CAPTURE_DIR or place "
                "it at the sibling sheet_dumps/ directory to run this check; skipping "
                "so the public test suite still runs without private data"
            )

        with tempfile.TemporaryDirectory() as tmp:
            out0 = os.path.join(tmp, "stage0_seed0.json")
            out1 = os.path.join(tmp, "stage0_seed1.json")

            result0 = run_with_hash_seed(
                "sheet_derivation.serialize_stage0", [capture_dir, out0], seed="0"
            )
            self.assertEqual(result0.returncode, 0, msg=f"seed=0 subprocess failed: {result0.stderr}")
            result1 = run_with_hash_seed(
                "sheet_derivation.serialize_stage0", [capture_dir, out1], seed="1"
            )
            self.assertEqual(result1.returncode, 0, msg=f"seed=1 subprocess failed: {result1.stderr}")

            self.assert_files_byte_identical(out0, out1, context="real capture, Stage 0")


if __name__ == "__main__":
    unittest.main()
