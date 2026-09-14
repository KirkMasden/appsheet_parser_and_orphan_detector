"""Maintainer gate-check scripts: each names this one workbook's own
sheet/table names and hand-transcribed expected figures, which the
sheet_derivation package's own rule forbids inside its workbook-agnostic
modules (see e.g. stage2.py's module docstring). Kept in their own
sub-package for that reason -- importing only the committed,
workbook-agnostic machinery from the rest of sheet_derivation/, and
changing nothing there.

Each script is runnable directly: `python -m sheet_derivation.gates.<name>
[options]`. Capture and output directories are always accepted as
arguments and default via sheet_derivation/workspace.py's
resolve_workspace_root() when not supplied; nothing here requires editing
a script's own source to point at a different capture, output location,
or repository position.

A future reader comparing one of these scripts' gate reports against an
older copy (e.g. after moving these scripts, or after any change that
doesn't touch what a report actually measures) should expect three
sources of byte-level variation that are NOT findings -- each was
produced and reproduced against the untouched, pre-move originals during
the 2026-09-14 move into this sub-package, so none of them is specific to
being here rather than at the workspace root:

1. Hash-seed ordering noise. At least one report (capture_probe's, and
   stage1_reference_ledger's) iterates a plain `set()` of sheet/tab names
   when building a table; row order for ties then depends on Python's
   per-process string-hash randomization and varies from run to run
   under the default, unseeded interpreter. Reproducible only by fixing
   PYTHONHASHSEED to the same value on both runs being compared -- under
   a matched seed, output is byte-identical.
2. The toolCommit stamp. Several reports print `git rev-parse HEAD` at
   write time (via residue.build_stamp); this legitimately differs
   between two runs taken at different commits, exactly as it does for
   the stage 3/4/5 JSONL artifacts (see stage2_artifacts.py's own
   analogous note). Exclude the tool-commit line from any comparison.
3. Wall-clock timing. stage3_gate_check.py prints a "build time" line
   (stage 1 + stage 3, real capture) that varies with machine load and
   is not deterministic by design.

None of the three affects the substance of a report -- every gate table,
figure, and residue entry compares byte-for-byte once these three lines
are accounted for.
"""
