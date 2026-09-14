#!/usr/bin/env python3
"""Stage 3 gate check -- the formula inventory, the column profiles (with
the spill assessment folded in), and the value query, checked against this
workbook's own gates (9 September 2026 figures).

Not part of the sheet_derivation repo -- like 260908_stage1_gate_check.py
and 260909_stage2_gate_check.py next to it, this script hardcodes this
workbook's sheet and column names and its own measured numbers, which the
repo's own rule (sheet_derivation/stage3.py's module docstring) forbids
inside the package itself. Imports only the committed, workbook-agnostic
machinery from sheet_derivation/ and changes nothing there.

Invoked as: python -m sheet_derivation.gates.stage3_gate_check [options]

Writes the JSONL/CSV artifacts and the gate report into an output
directory that is always an argument (default via
sheet_derivation/workspace.py, relative to the workspace root -- never a
path baked into this file), and prints a summary to stdout. Read-only
against the repository and the capture: no file under either is written or
modified by this script.
"""
import argparse
import os
import time
from collections import Counter

from ..coordinates import parse_cell_address
from ..loader import discover_capture_files, load_capture
from ..stage3_artifacts import write_stage3_artifacts
from ..workspace import resolve_workspace_root
from .. import query, stage1, stage3

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage3_gate_check",
    description=__doc__,
)
parser.add_argument(
    "--capture-dir",
    default=None,
    help="Directory holding the capture's two JSON files. Default: <workspace>/sheet_dumps.",
)
parser.add_argument(
    "--output-dir",
    default=None,
    help="Directory to write the stage 3 artifacts and gate report into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
REPORT_PATH = os.path.join(OUTPUT_DIR, "stage3_gate_report.md")

out = []


def w(line=""):
    out.append(line)


# ---------------------------------------------------------------------------
# Expected figures, this workbook's own -- 9 September 2026.
# ---------------------------------------------------------------------------
GATE_B_EXPECTED_PATTERNS = 388
GATE_A_EXPECTED_PATTERNS = 384
PROBE_WRONG_FIGURE = 382
EXPECTED_NONEMPTY_FORMULAS = 185661
EXPECTED_LONGEST_FORMULA_LEN = 2844
EXPECTED_LONGEST_FORMULA_CELL = ("Options", "E3")
EXPECTED_CLASSIFICATION_COUNTS = {
    "single-pattern-contiguous": 82,
    "single-pattern-ragged": 9,
    "multi-pattern": 53,
}
VERTICAL_NO_FORMULA_COLUMN = ("Vertical", "R")
VERTICAL_NO_FORMULA_VALUE_COUNT = 10000

# ---------------------------------------------------------------------------
# Run.
# ---------------------------------------------------------------------------
formulas_path, values_path = discover_capture_files(DUMPS_DIR)
capture = load_capture(formulas_path, values_path)
t0 = time.time()
s1 = stage1.run_stage1(formulas_path, values_path)
s3 = stage3.run_stage3(formulas_path, values_path)
build_seconds = time.time() - t0

w("# Stage 3 gate check")
w()
w(f"captureDate: `{s3.capture.capture_date}`")
w(f"tool commit: `{s3.inventory.stamp.tool_commit}`")
w(f"build time (stage 1 + stage 3, real capture): {build_seconds:.1f}s")
w()

# ---------------------------------------------------------------------------
# Gate: distinct pattern counts.
# ---------------------------------------------------------------------------
w("## Gate -- distinct pattern counts")
w()
gate_b = len(s3.inventory.patterns)
gate_a = s1.total_distinct_patterns_gate_a
w(f"Gate B (real tool normalization, what the inventory actually carries): measured {gate_b}, "
  f"expected {GATE_B_EXPECTED_PATTERNS} (match: {gate_b == GATE_B_EXPECTED_PATTERNS})")
w(f"Gate A (probe-equivalent normalization, comparison only -- never used to build the artifact): "
  f"measured {gate_a}, expected {GATE_A_EXPECTED_PATTERNS} (match: {gate_a == GATE_A_EXPECTED_PATTERNS})")
w(f"The capture probe's own figure, {PROBE_WRONG_FIGURE}, is NOT reproduced by either gate above, "
  f"and is not expected to be -- design section 5 and Stage 1's own gate report attribute it to the "
  f"probe's boundary-blind regex, which this tool does not carry forward.")
w()
w(f"**Non-empty formulas:** measured {s3.workbook_accounting.non_empty_formulas:,}, expected "
  f"{EXPECTED_NONEMPTY_FORMULAS:,} (match: {s3.workbook_accounting.non_empty_formulas == EXPECTED_NONEMPTY_FORMULAS})")
w()
w("The 384-to-388 difference is entirely within one sheet (Vertical) and comes from two Gate-A "
  "patterns that split under the decision not to normalize row numbers inside string literals -- "
  "named in Stage 1's own gate ledger (`stage1_reference_ledger_report.md`, section 4a): "
  "`=\"Collate!AK#\"` (Vertical!B1/H1) and `=\"Collate!AB#\"` (Vertical!D1/E1/J1/K1).")
w()

# ---------------------------------------------------------------------------
# Gate: column classification (design's own 82/9/53 worked example).
# ---------------------------------------------------------------------------
w("## Gate -- column classification")
w()
measured_classification = Counter(c.classification for c in s3.column_profiles.columns)
for classification, expected_count in EXPECTED_CLASSIFICATION_COUNTS.items():
    measured_count = measured_classification.get(classification, 0)
    w(f"- `{classification}`: measured {measured_count}, expected {expected_count} "
      f"(match: {measured_count == expected_count})")
w(f"- `no-formula` (not gated by the design's own 82/9/53 figure, which only covers columns holding "
  f"at least one formula): measured {measured_classification.get('no-formula', 0)}")
w(f"- Total columns profiled (any formula or value content): {len(s3.column_profiles.columns)}")
w()

# ---------------------------------------------------------------------------
# Gate: no truncation, anywhere.
# ---------------------------------------------------------------------------
w("## Gate -- no truncation")
w()
longest = max(s3.inventory.patterns, key=lambda p: len(p.raw_instance))
longest_loc = longest.locations[0]
sheet, addr = EXPECTED_LONGEST_FORMULA_CELL
w(f"Longest raw instance carried by the inventory: {len(longest.raw_instance):,} characters, expected "
  f"{EXPECTED_LONGEST_FORMULA_LEN:,} (match: {len(longest.raw_instance) == EXPECTED_LONGEST_FORMULA_LEN})")
w(f"Its location: `{longest_loc.sheet}!{longest_loc.column}{longest_loc.row_start1}`, expected "
  f"`{sheet}!{addr}` (match: {(longest_loc.sheet, f'{longest_loc.column}{longest_loc.row_start1}') == EXPECTED_LONGEST_FORMULA_CELL})")
w(f"First 80 / last 80 characters, to show it is not a placeholder: "
  f"`{longest.raw_instance[:80]}` ... `{longest.raw_instance[-80:]}`")
w()

# ---------------------------------------------------------------------------
# Gate: the accounting invariant.
# ---------------------------------------------------------------------------
w("## Gate -- the accounting invariant")
w()
w("| sheet | non-empty formulas | matched | residue | balances |")
w("|---|---:|---:|---:|---|")
for a in s3.accounting:
    w(f"| {a.sheet_name} | {a.non_empty_formulas:,} | {a.matched_formulas:,} | {a.residue_formulas:,} | {a.balances} |")
wb = s3.workbook_accounting
w(f"| **TOTAL** | **{wb.non_empty_formulas:,}** | **{wb.matched_formulas:,}** | **{wb.residue_formulas:,}** | **{wb.balances}** |")
w()
w(f"Formula-instance side: matched {wb.matched_formulas:,} + residue {wb.residue_formulas:,} = "
  f"{wb.matched_formulas + wb.residue_formulas:,} = non-empty formulas {wb.non_empty_formulas:,} "
  f"(balances: {wb.balances}) -- this side is 100%/0% by construction (see stage3.py's own docstring: "
  f"Gate B normalization is total over every formula, asserted at build time, not merely reported here).")
w()
w(f"Spill-run side (a DIFFERENT population, in a DIFFERENT unit -- value-only cells, not formulas): "
  f"{s3.spill_run_total:,} total runs = {s3.spill_run_total - s3.spill_run_residue_count:,} governed "
  f"(a formula was found above) + {s3.spill_run_residue_count:,} residue (none was), which by "
  f"construction always sums to the total: "
  f"{(s3.spill_run_total - s3.spill_run_residue_count) + s3.spill_run_residue_count == s3.spill_run_total}.")
w()
w(f"Workbook-wide, against Stage 1's own non-empty-formula total: matches "
  f"{wb.non_empty_formulas == s1.total_nonempty_formulas} ({wb.non_empty_formulas:,} vs {s1.total_nonempty_formulas:,})")
w()

# ---------------------------------------------------------------------------
# Gate: the Vertical!R worked example from the design document itself.
# ---------------------------------------------------------------------------
w("## Gate -- the design's own worked example (Vertical column R)")
w()
r_sheet, r_col = VERTICAL_NO_FORMULA_COLUMN
r_profile = next(c for c in s3.column_profiles.columns if c.sheet == r_sheet and c.column == r_col)
w(f"`{r_sheet}!{r_col}`: measured {r_profile.total_formula_count} formulas, "
  f"{r_profile.total_value_count} values, classification `{r_profile.classification}` -- design section "
  f"3.2 states this column '{VERTICAL_NO_FORMULA_VALUE_COUNT} values and contains no formula at all'; "
  f"measured value count matches: {r_profile.total_value_count == VERTICAL_NO_FORMULA_VALUE_COUNT}.")
r_residue = [r for r in s3.column_profiles.residue if r.locations[0].startswith(f"{r_sheet}!{r_col}")]
w(f"Residue entries for this column: {len(r_residue)}")
for r in r_residue:
    w(f"- what: {r.what}")
    w(f"    consequence: {r.consequence}")
w()

# ---------------------------------------------------------------------------
# Residue summary and sample entries.
# ---------------------------------------------------------------------------
w("## Residue")
w()
w(f"Inventory residue entries (UNKNOWN-token patterns): {len(s3.inventory.residue)}")
w(f"Column-profile residue entries (spill runs with no governing formula found): {len(s3.column_profiles.residue)}")
by_construct = Counter(r.defeating_construct for r in s3.column_profiles.residue)
for k, v in by_construct.most_common():
    w(f"- {v:,} -- {k}")
w()
by_sheet = Counter(r.locations[0].split("!")[0] for r in s3.column_profiles.residue)
w("Per-sheet breakdown, top 10 (most residue concentrates in sheets with few or no formulas at all, "
  "where sparse manual/imported data fragments into many short value-only runs):")
for sheet_name, n in by_sheet.most_common(10):
    w(f"- {sheet_name}: {n:,}")
w()
w("A few entries verbatim, one per category, plus a governed (non-residue) spill run for contrast:")
w()
seen = set()
for r in s3.column_profiles.residue:
    if r.defeating_construct in seen:
        continue
    seen.add(r.defeating_construct)
    w(f"- **{r.defeating_construct}** at `{r.locations[:1]}`" + (f" (+{len(r.locations)-1} more cells)" if len(r.locations) > 1 else ""))
    w(f"    - what: {r.what}")
    w(f"    - consequence: {r.consequence}")
w()

governed_example = None
for c in s3.column_profiles.columns:
    for run in c.spill_runs:
        if run.governing_formula_row1 is not None and run.gap_rows and run.gap_rows > 0:
            governed_example = (c, run)
            break
    if governed_example:
        break
if governed_example:
    c, run = governed_example
    w(f"A non-zero measured gap, reported without judgment (design section 3.2: no threshold is this "
      f"tool's decision to make): `{c.sheet}!{c.column}{run.row_start1}:{c.column}{run.row_end1}` "
      f"({run.value_count} values), nearest formula above at row {run.governing_formula_row1}, "
      f"gap = {run.gap_rows} row(s). Whether row {run.governing_formula_row1}'s formula plausibly "
      f"governs values starting {run.gap_rows} rows later is left to the reader.")
    w()

# ---------------------------------------------------------------------------
# The value query, demonstrated.
# ---------------------------------------------------------------------------
w("## The value query (design section 9)")
w()
w("Interface: `query.query_address(capture, sheet_name, address) -> AddressQueryResult` -- "
  "`.formula`, `.value`, `.is_spill_origin`, `.spill_extent` (`.down_to_row1`, `.right_to_column`, `.note`). "
  "Resolves addresses only; never evaluates, never follows a chain.")
w()
demo_addresses = [("Vertical", "A2"), ("Options", "E3"), ("Vertical", "R1")]
for sheet_name, addr in demo_addresses:
    result = query.query_address(capture, sheet_name, addr)
    w(f"- `query_address(capture, {sheet_name!r}, {addr!r})`:")
    w(f"    - formula: `{result.formula[:120] + '...' if result.formula and len(result.formula) > 120 else result.formula}`")
    w(f"    - value: `{result.value!r}`")
    w(f"    - is_spill_origin: {result.is_spill_origin}")
    if result.spill_extent:
        w(f"    - spill_extent: down_to_row1={result.spill_extent.down_to_row1}, "
          f"right_to_column={result.spill_extent.right_to_column!r}")
w()

# ---------------------------------------------------------------------------
# Write the real artifacts.
# ---------------------------------------------------------------------------
paths = write_stage3_artifacts(s3, OUTPUT_DIR)
w("## Artifacts written")
w()
for name, path in paths.items():
    size = os.path.getsize(path)
    w(f"- `{os.path.basename(path)}` ({size:,} bytes)")
w()
w("## Reliability conditions")
w()
w("**Formula inventory:**")
w(s3.inventory.reliability_condition)
w()
w("**Column profiles:**")
w(s3.column_profiles.reliability_condition)

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(REPORT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Wrote {REPORT_PATH} ({len(out)} lines)")
for name, path in paths.items():
    print(f"Wrote {path} ({os.path.getsize(path):,} bytes)")
print()
print(f"Gate B patterns: {gate_b} (expect {GATE_B_EXPECTED_PATTERNS})")
print(f"Gate A patterns: {gate_a} (expect {GATE_A_EXPECTED_PATTERNS})")
print(f"Non-empty formulas: {wb.non_empty_formulas} (expect {EXPECTED_NONEMPTY_FORMULAS})")
print(f"Classification: {dict(measured_classification)}")
print(f"Longest raw instance: {len(longest.raw_instance)} chars at {longest_loc.sheet}!{longest_loc.column}{longest_loc.row_start1}")
print(f"Accounting balances: {wb.balances}")
print(f"Spill runs: {s3.spill_run_total} total, {s3.spill_run_residue_count} residue")
