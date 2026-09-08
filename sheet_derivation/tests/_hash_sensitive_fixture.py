"""Not part of the tool. A standalone script that deliberately reproduces
the exact defect class the cross-process check exists to catch -- a
collection emitted straight from set iteration, with no explicit sort key
-- so test_cross_process_determinism.py can prove its subprocess-launch
and byte-comparison mechanism actually detects a real difference, without
needing the real capture or waiting for a regression in the tool itself to
prove it.

These eight names are an empirically-checked pair: under this Python
build, PYTHONHASHSEED=0 and PYTHONHASHSEED=1 produce two different
`set` iteration orders for exactly this set. That is the whole point --
this script's output is expected, by design, to differ between the two
seeds, which is what confirms the harness would catch it if the real
tool ever regressed the same way.
"""

import json
import sys

_NAMES = {"Zeta", "Alpha", "Mid", "Beta", "Gamma", "Kappa", "Omega", "Delta"}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m sheet_derivation.tests._hash_sensitive_fixture <output_path>", file=sys.stderr)
        return 2
    with open(argv[0], "w", encoding="utf-8") as fh:
        json.dump(list(_NAMES), fh)  # deliberately unsorted -- the defect under test
    return 0


if __name__ == "__main__":
    sys.exit(main())
