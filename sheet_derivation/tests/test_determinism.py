import itertools
import unittest

from ..determinism import DeterminismError, assert_explicitly_sorted, verify_same_process_determinism


class TestAssertExplicitlySorted(unittest.TestCase):
    def test_passes_on_sorted_input(self):
        assert_explicitly_sorted([1, 2, 3], key=lambda x: x, label="ints")
        assert_explicitly_sorted(["a", "bb", "ccc"], key=len, label="by length")

    def test_raises_on_unsorted_input(self):
        with self.assertRaises(DeterminismError):
            assert_explicitly_sorted([3, 1, 2], key=lambda x: x, label="ints")


class TestVerifySameProcessDeterminism(unittest.TestCase):
    def test_passes_for_a_deterministic_pipeline(self):
        def pipeline():
            return tuple(sorted(["b", "a", "c"]))

        result = verify_same_process_determinism(pipeline, run_label="deterministic")
        self.assertEqual(result, ("a", "b", "c"))

    def test_raises_for_a_pipeline_that_varies_between_calls(self):
        counter = itertools.count()

        def pipeline():
            return next(counter)  # different result every call

        with self.assertRaises(DeterminismError):
            verify_same_process_determinism(pipeline, run_label="nondeterministic")

    def test_harness_actually_detects_a_forced_difference(self):
        state = {"n": 0}

        def pipeline():
            state["n"] += 1
            return state["n"]

        with self.assertRaises(DeterminismError) as ctx:
            verify_same_process_determinism(pipeline, run_label="forced")
        self.assertIn("First run", str(ctx.exception))
        self.assertIn("Second run", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
