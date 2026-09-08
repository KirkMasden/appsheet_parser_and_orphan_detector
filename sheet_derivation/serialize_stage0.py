"""CLI: run Stage 0 against a capture directory and write its canonical
serialization to a file. Meant to be launched as a subprocess with a
specific PYTHONHASHSEED already set in its environment -- see
tests/test_cross_process_determinism.py, which is the only caller.

Usage:
    python -m sheet_derivation.serialize_stage0 <capture_directory> <output_path>
"""

import sys

from .loader import discover_capture_files
from .serialize import build_canonical_structure, write_canonical_json
from .stage0 import run_stage0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(
            "usage: python -m sheet_derivation.serialize_stage0 <capture_directory> <output_path>",
            file=sys.stderr,
        )
        return 2

    capture_dir, output_path = argv
    formulas_path, values_path = discover_capture_files(capture_dir)
    result = run_stage0(formulas_path, values_path)
    structure = build_canonical_structure(result)
    write_canonical_json(output_path, structure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
