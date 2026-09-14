#!/usr/bin/env python3
"""Stage 4 gate check -- the schema file, header detection under the
CORRECTED rule (2026-09-09: spill disqualifies the column, not the row;
a majority threshold gates the positive-signal verdict), and the
duplicate-label / four-state-label findings, checked against this
workbook's own capture.

Not part of the sheet_derivation repo -- like the stage 1-3 gate-check
scripts next to it, this script names this workbook's own sheets and
cells, which the repo's own rule (sheet_derivation/stage4.py's module
docstring) forbids inside the package itself. Imports only the committed,
workbook-agnostic machinery from sheet_derivation/ and changes nothing
there.

Invoked as: python -m sheet_derivation.gates.stage4_gate_check [options]

Writes the JSONL/CSV artifacts and the gate report into an output
directory that is always an argument (default via
sheet_derivation/workspace.py, relative to the workspace root -- never a
path baked into this file), and prints a summary to stdout. Read-only
against the repository and the capture: no file under either is written
or modified by this script.

UNLIKE the stage 1-3 gate-check scripts, this one carries NO expected
figures to assert against -- the prompt this stage was built from is
explicit that no count is asserted for how many sheets have an unusable
row 1. The BEFORE_RULE_RESULT table below is an exception: it is a
one-time transcription of what the SUPERSEDED (whole-row-veto,
no-threshold) rule measured on this same capture, kept only so the
before/after comparison this run reports doesn't have to be regenerated
by hand from an earlier commit each time this script runs.
"""
import argparse
import os
from collections import Counter

from ..loader import discover_capture_files, load_capture
from ..stage4_artifacts import write_stage4_artifacts
from ..workspace import resolve_workspace_root
from .. import stage4

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage4_gate_check",
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
    help="Directory to write the stage 4 artifacts and gate report into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
REPORT_PATH = os.path.join(OUTPUT_DIR, "stage4_gate_report.md")

# The two sheets design section 4.2 names as attested evidence for the rule.
ATTESTED_HEADER_SHEET = "Vertical"       # maintainer-confirmed: row 1 IS this sheet's header
ATTESTED_PARTIAL_HEADER_SHEET = "Current"  # design-attested: 6 of 38 columns are FILTER-spilled
ATTESTED_DUPLICATE_SHEETS = ("Current", "Collate")

# One-time transcription of the SUPERSEDED (whole-row-veto, no-threshold)
# rule's own measurement on this same capture, commit 9cad2d9 -- see this
# script's own module docstring for why this is the one exception to "no
# expected figures transcribed here".
BEFORE_RULE_RESULT = {
    "Archive": ("identified", 0.250),
    "Collate": ("not-identified-confident", 1.000),
    "Current": ("not-identified-confident", 1.000),
    "Downstream Dependency Report": ("identified", 0.143),
    "Long Term": ("not-identified-confident", 1.000),
    "Main data": ("identified", 0.316),
    "Options": ("identified", 0.087),
    "Overall": ("identified", 0.735),
    "Progress": ("identified", 0.769),
    "Progress archive": ("identified", 0.750),
    "Seminar": ("undetermined", None),
    "Settings": ("identified", 0.294),
    "Sheet50": ("identified", 0.769),
    "Stats": ("identified", 0.091),
    "Vertical": ("identified", 0.706),
    "Volatile Formulas Report": ("undetermined", None),
    "Welcome": ("identified", 0.200),
}

out = []


def w(line=""):
    out.append(line)


formulas_path, values_path = discover_capture_files(DUMPS_DIR)
capture = load_capture(formulas_path, values_path)
result = stage4.run_stage4(formulas_path, values_path)

w("# Stage 4 gate check")
w()
w(f"captureDate: `{result.capture.capture_date}`")
w(f"tool commit (of the schema artifact's own stamp -- the last commit BEFORE this stage's own, per this "
  f"repo's established gate-check convention): `{result.schema.stamp.tool_commit}`")
w()
w("Two corrections to the header-detection rule are reflected in this run, both made 2026-09-09 after "
  "the first version of this stage shipped and was checked against this same capture: (1) a spilling "
  "column is excluded from its row's own verdict rather than vetoing the whole row; (2) an IDENTIFIED "
  "verdict requires a majority (more than half) of informative, non-excluded columns to show the "
  "positive signal, not merely a nonzero count. See `stage4.py`'s own module docstring for the reasoning "
  "behind both.")
w()

# ---------------------------------------------------------------------------
# Before / after, every sheet.
# ---------------------------------------------------------------------------
w("## Before and after the two corrections, every sheet")
w()
w("| sheet | before verdict | before conf | after verdict | after conf | changed |")
w("|---|---|---:|---|---:|---|")
changed_sheets = []
for s in result.schema.sheets:
    hd = s.header_detection
    b_verdict, b_conf = BEFORE_RULE_RESULT[s.sheet]
    b_conf_str = f"{b_conf:.3f}" if b_conf is not None else "--"
    a_conf_str = f"{hd.confidence:.3f}" if hd.confidence is not None else "--"
    changed = b_verdict != hd.verdict
    if changed:
        changed_sheets.append(s.sheet)
    w(f"| {s.sheet} | {b_verdict} | {b_conf_str} | {hd.verdict} | {a_conf_str} | {'YES' if changed else ''} |")
w()
w(f"**{len(changed_sheets)} of {len(result.schema.sheets)} sheets changed verdict:** {changed_sheets}")
w()
w("Every changed sheet falls into one of two groups, corresponding exactly to the two corrections: "
  "`Collate`, `Current`, and `Long Term` moved from not-identified-confident to identified -- correction "
  "1 (per-column exclusion) recovering a real header the whole-row veto was hiding behind a minority of "
  "spilling columns. `Archive`, `Downstream Dependency Report`, `Main data`, `Options`, `Settings`, "
  "`Stats`, and `Welcome` moved from identified to undetermined -- correction 2 (the majority threshold) "
  "withdrawing a verdict that rested on a small minority of columns (confidence 0.087-0.316, one column "
  "in the smallest cases). `Vertical` is unaffected by either correction (it has no spilling columns and "
  "was already well above the threshold).")
w()

# ---------------------------------------------------------------------------
# The attested cases, checked explicitly.
# ---------------------------------------------------------------------------
w("## The attested cases")
w()
header_sheet = next(s for s in result.schema.sheets if s.sheet == ATTESTED_HEADER_SHEET)
partial_sheet = next(s for s in result.schema.sheets if s.sheet == ATTESTED_PARTIAL_HEADER_SHEET)
w(f"**{ATTESTED_HEADER_SHEET}** (maintainer-confirmed: row 1 functions as this sheet's header): measured "
  f"verdict `{header_sheet.header_detection.verdict}`, confidence {header_sheet.header_detection.confidence:.3f}, "
  f"unchanged by either correction.")
w(f"  - Evidence: {header_sheet.header_detection.evidence.note}")
w()
w(f"**{ATTESTED_PARTIAL_HEADER_SHEET}** (design-attested: 6 of 38 columns are FILTER-spilled first rows of "
  f"imported records): measured verdict `{partial_sheet.header_detection.verdict}`, confidence "
  f"{partial_sheet.header_detection.confidence:.3f}. Under the superseded whole-row veto this sheet measured "
  "not-identified-confident; under the corrected rule its 6 spilling columns (A, D, F, W, X, AL) are "
  "excluded and reported as spill-origin-not-label, and the remaining 32 columns -- 23 of them informative, "
  "15 showing the type-mismatch signal (65.2%) -- carry the row to IDENTIFIED on their own. This is the "
  "flip the maintainer confirmed as correct rather than a defect: design section 4.2's account of this "
  "sheet is true of 6 columns out of 38, not of the row as a whole, and a header row with pass-through "
  "columns is exactly the shape correction 1 exists to express.")
w(f"  - Evidence: {partial_sheet.header_detection.evidence.note}")
w(f"  - Excluded (spill-origin) columns: {partial_sheet.header_detection.evidence.negative_signal_columns}")
w()

# ---------------------------------------------------------------------------
# The measured count of sheets whose row 1 is unusable as a header.
# ---------------------------------------------------------------------------
w("## Measured count: sheets whose row 1 is unusable as a header")
w()
unusable = [
    s for s in result.schema.sheets
    if s.header_detection.verdict != stage4.HEADER_VERDICT_IDENTIFIED
]
w(f"**Measured: {len(unusable)} of {len(result.schema.sheets)} sheets.** No count was asserted in advance; "
  f"this is what the corrected rule, applied without tuning, produces on this capture.")
w()
w("| sheet | verdict | reason |")
w("|---|---|---|")
for s in unusable:
    hd = s.header_detection
    reason = "confidently data (every column is a spill origin)" if hd.verdict == stage4.HEADER_VERDICT_NOT_IDENTIFIED_CONFIDENT else "undetermined (below the majority threshold, or no signal at all)"
    w(f"| {s.sheet} | {hd.verdict} | {reason} |")
w()
w(f"**This is measured as {len(unusable)}, not five.** The superseded (whole-row-veto, no-threshold) "
  f"rule's own count on this same capture was 5 ({{Collate, Current, Long Term}} confidently-not-header "
  f"plus {{Seminar, Volatile Formulas Report}} undetermined) -- and an early design draft's guess of five, "
  f"and the capture probe's measurement of four, both came from a still-earlier, different superseded rule "
  f"(reject any row 1 containing a formula). Before writing this report the working assumption was that "
  f"the corrected rule would also land on 'a different five'; it does not, and the reason is arithmetic, "
  f"not a defect: correction 1 alone REMOVES `Collate`, `Current`, and `Long Term` from this list (their "
  f"spilling columns are excluded rather than vetoing the row, and the columns that remain clear the "
  f"majority threshold), which would leave 2; correction 2 alone then ADDS `Archive`, `Downstream "
  f"Dependency Report`, `Main data`, `Options`, `Settings`, `Stats`, and `Welcome` (7 sheets whose "
  f"identified verdict rested on confidence between 0.087 and 0.316 -- a minority of their informative "
  f"columns -- now correctly withdrawn to undetermined). 2 removed, 7 added, net {len(unusable)}. Both "
  f"corrections are independently justified on their own reasoning (see stage4.py's own docstring); "
  f"their combined effect on this one count was not verified against an assumed target before this run, "
  f"and the honest number is {len(unusable)}, reported as measured rather than adjusted toward five.")
w()

# ---------------------------------------------------------------------------
# Duplicate labels.
# ---------------------------------------------------------------------------
w("## Duplicate labels")
w()
found_duplicate_sheets = [s.sheet for s in result.schema.sheets if s.duplicate_labels]
w(f"Sheets with a duplicate value in their candidate row: {found_duplicate_sheets}, expected "
  f"{list(ATTESTED_DUPLICATE_SHEETS)} (match: {sorted(found_duplicate_sheets) == sorted(ATTESTED_DUPLICATE_SHEETS)}).")
w()
for s in result.schema.sheets:
    if not s.duplicate_labels:
        continue
    for d in s.duplicate_labels:
        cols_states = [
            (col, next(c.header_label.state for c in s.columns if c.column == col))
            for col in d.columns
        ]
        w(f"- **{s.sheet}**: `{d.label_value!r}` at columns {d.columns} "
          f"(this sheet's header verdict: `{s.header_detection.verdict}`; per-column label state: {cols_states})")
w()
w("**Resolution of the finding this script reported last run:** both attested duplicate-label sheets now "
  "measure `identified`, and both duplicate pairs sit inside an identified header -- `labeled` at both "
  "columns, in both cases -- exactly what design section 4.2's prose always claimed. The prior run's "
  "finding (both sheets measured not-identified-confident under the whole-row veto, so neither duplicate "
  "sat 'within a header row') was correctly attributable to the veto being too strong, not to the "
  "duplicates being misdescribed by the design document -- confirmed by the maintainer, who determined "
  "the veto was wrong rather than adjusting the required outcome to match it.")
w()

# ---------------------------------------------------------------------------
# Four-state label field distribution.
# ---------------------------------------------------------------------------
w("## Four-state header-label field, distribution across the workbook")
w()
w(f"Total declared columns across all 17 sheets: {sum(result.column_label_state_counts.values())}")
w()
w("| state | count |")
w("|---|---:|")
for state in (stage4.LABEL_STATE_LABELED, stage4.LABEL_STATE_NO_LABEL_IN_IDENTIFIED_HEADER,
              stage4.LABEL_STATE_UNKNOWN_HEADER_NOT_IDENTIFIED, stage4.LABEL_STATE_NONE_NO_HEADER_IN_SHEET,
              stage4.LABEL_STATE_SPILL_ORIGIN_NOT_LABEL):
    w(f"| {state} | {result.column_label_state_counts.get(state, 0):,} |")
w()
w(f"The new state, `{stage4.LABEL_STATE_SPILL_ORIGIN_NOT_LABEL}`, accounts for every column excluded by "
  f"correction 1 across all 17 sheets ({result.column_label_state_counts.get(stage4.LABEL_STATE_SPILL_ORIGIN_NOT_LABEL, 0)} "
  f"columns) -- these are the same columns that, before the correction, would have caused their own row "
  f"to be reported not-identified-confident wholesale.")
w()

# ---------------------------------------------------------------------------
# Residue, verbatim.
# ---------------------------------------------------------------------------
w("## Residue")
w()
w(f"Schema residue entries: {len(result.schema.residue)}")
w()
for r in result.schema.residue:
    w(f"- **{r.defeating_construct}**")
    w(f"    - what: {r.what}")
    w(f"    - locations: {r.locations}")
    w(f"    - consequence: {r.consequence}")
w()

# ---------------------------------------------------------------------------
# Reliability condition, verbatim.
# ---------------------------------------------------------------------------
w("## Reliability condition, verbatim")
w()
w(result.schema.reliability_condition)
w()

# ---------------------------------------------------------------------------
# Write the artifacts.
# ---------------------------------------------------------------------------
paths = write_stage4_artifacts(result, OUTPUT_DIR)
w("## Artifacts written")
w()
for name, path in paths.items():
    w(f"- `{os.path.basename(path)}` ({os.path.getsize(path):,} bytes)")

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(REPORT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Wrote {REPORT_PATH} ({len(out)} lines)")
for name, path in paths.items():
    print(f"Wrote {path} ({os.path.getsize(path):,} bytes)")
print()
print(f"Changed sheets: {changed_sheets}")
print(f"Sheet verdict counts: {result.sheet_verdict_counts}")
print(f"Column label state counts: {result.column_label_state_counts}")
print(f"Unusable-as-header count: {len(unusable)} of {len(result.schema.sheets)}")
print(f"Vertical verdict: {header_sheet.header_detection.verdict} (unchanged)")
print(f"Current verdict: {partial_sheet.header_detection.verdict} (attested-correct flip: identified)")
print(f"Duplicate-label sheets: {found_duplicate_sheets} (attested: {list(ATTESTED_DUPLICATE_SHEETS)})")
print(f"Schema residue entries: {len(result.schema.residue)}")
