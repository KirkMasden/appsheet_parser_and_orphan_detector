"""Determinism enforcement.

Every collection this tool ever emits must be sorted by an explicit key --
not left to dict, set, or glob iteration order, which can vary by Python
hash seed or filesystem between runs. This is not a style preference: the
app-side suite shipped a defect where view names came out of a set and
output order varied run to run, until it was sorted in August 2026
(RELEASE_CHECKLIST.md / STATUS.md). A tool whose entire value proposition
is that a re-run can be diffed against the last one cannot have that
property anywhere.

`assert_explicitly_sorted` is the one check every emitted collection should
pass before it is written or returned. `verify_same_process_determinism`
is the stage-0 self-test: run a whole pipeline function twice in one
process and assert the two results are identical.
"""

from typing import Any, Callable, Sequence, Tuple


class DeterminismError(AssertionError):
    """Raised when a collection is not sorted by its declared key, or when
    running a pipeline twice in one process produced two different results."""


def assert_explicitly_sorted(items: Sequence[Any], key: Callable[[Any], Any], label: str) -> None:
    """Confirms `items` is already sorted by `key`; raises if not.

    Call this at the point a collection is about to be emitted (written to
    a file, returned from a public function), so a future change that
    accidentally reintroduces set/dict iteration order is caught at the
    point it happens, not by a reader noticing the output changed.
    """
    keyed = [key(item) for item in items]
    if keyed != sorted(keyed):
        raise DeterminismError(
            f"{label} is not sorted by its declared key -- found order {keyed}, "
            f"expected {sorted(keyed)}. Every collection this tool emits must be "
            f"sorted by an explicit key; this one is not."
        )


def verify_same_process_determinism(pipeline_fn: Callable[[], Any], run_label: str) -> Any:
    """Runs `pipeline_fn` twice in this process and asserts identical results.

    Returns the (identical) result on success. Raises DeterminismError, with
    both results shown, if the two runs differ -- which is the failure mode
    a set/dict-order dependency would produce even within a single process
    on a single machine, before ever considering cross-run or cross-machine
    variation.
    """
    first = pipeline_fn()
    second = pipeline_fn()
    if first != second:
        raise DeterminismError(
            f"{run_label}: running the same pipeline twice in one process produced "
            f"two different results.\nFirst run:  {first!r}\nSecond run: {second!r}\n"
            "This means some collection in the pipeline is not sorted by an "
            "explicit key."
        )
    return first
