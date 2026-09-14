#!/usr/bin/env python3
"""Stage 5 gate check -- the AppSheet-to-sheet join, checked against this
workbook's own capture and the app-side parse identified as current in
the stage 5 precheck (`sheet_derivation_output/260909_stage5_precheck_report.md`).

Not part of the sheet_derivation repo -- like the stage 1-4 gate-check
scripts next to it, this script names this workbook's own sheets, tables
and cells, which the repo's own rule (sheet_derivation/stage5.py's module
docstring) forbids inside the package itself. Imports only the committed,
workbook-agnostic machinery from sheet_derivation/ and changes nothing
there.

Invoked as:

    python -m sheet_derivation.gates.stage5_gate_check \
        --appside-parse-dir DIR --cited-parse-dir DIR --app-export-html FILE \
        [--capture-dir DIR] [--output-dir DIR]

The three workbook/session-specific paths this check compares against
(the app-side parse directory identified as current, the earlier parse
directory AGENTS.md/CLAUDE.md cites, and the app's HTML export) are
REQUIRED arguments, not defaults -- there is no workbook-agnostic value
for any of them, and the repo's own standing rule (sheet_derivation/
stage5.py's module docstring) forbids naming a specific workbook/app
inside committed source. Capture and output directories remain optional,
defaulting via sheet_derivation/workspace.py relative to the workspace
root.

Writes the JSONL/CSV artifacts and the gate report into an output
directory that is always an argument, and prints a summary to stdout.
Read-only against the repository, the capture, and the app-side parse: no
file under any of them is written or modified by this script (verified
below, not assumed, for the stage 4 output files this run finds already
present in its own output directory).
"""
import argparse
import hashlib
import os
from collections import Counter

from ..loader import discover_capture_files
from ..stage5_artifacts import write_stage5_artifacts
from ..workspace import resolve_workspace_root
from .. import stage5

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage5_gate_check",
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument(
    "--capture-dir",
    default=None,
    help="Directory holding the capture's two JSON files. Default: <workspace>/sheet_dumps.",
)
parser.add_argument(
    "--output-dir",
    default=None,
    help="Directory to write the stage 5 artifacts and gate report into. Default: <workspace>/output/gates.",
)
parser.add_argument(
    "--appside-parse-dir",
    required=True,
    help="The app-side parse directory identified as current for this join (holds appsheet_columns.csv etc.). Required -- no workbook-agnostic default exists.",
)
parser.add_argument(
    "--cited-parse-dir",
    required=True,
    help="The earlier parse directory this report's own commentary compares against (used only for its basename in that comparison sentence). Required -- no workbook-agnostic default exists.",
)
parser.add_argument(
    "--app-export-html",
    required=True,
    help="Path to the app's HTML documentation export, for provenance (og:title, version, export mtime). Required -- no workbook-agnostic default exists.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
REPORT_PATH = os.path.join(OUTPUT_DIR, "stage5_gate_report.md")

# Identified as current in the stage 5 precheck: a later same-day parse than
# the one AGENTS.md/CLAUDE.md cites, byte-identical to it on every file this
# stage reads, plus one additional detector's output the cited one lacks.
APPSIDE_PARSE_DIR = args.appside_parse_dir
CLAUDE_MD_CITED_PARSE_DIR = args.cited_parse_dir
APP_EXPORT_HTML = args.app_export_html

# GATE, transcribed from the prompt this stage was built from -- not
# tuned to match, and reported as a mismatch (named by cell) if it
# disagrees, per this project's own standing rule.
GATE_TABLE_COUNT = 10
GATE_MATCHED_TABLE_COUNT = 8
GATE_UNMATCHED_TABLES = {"Kankaku", "_Per User Settings"}
GATE_DIAGNOSTIC = {
    "Settings": {"row1_nonempty": 35, "row1_exact": 35, "row1_near": 0},
    "Options": {"row1_nonempty": 23, "row1_exact": 23, "row1_near": 0},
    "Archive": {"row1_nonempty": 32, "row1_exact": 31, "row1_near": 1},
}
GATE_ARCHIVE_NEAR_MISS_CELL = ("Archive", "V1", "DW last view Change Time ")  # column 22 = V

out = []


def w(line=""):
    out.append(line)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Verify stage 4's own outputs are untouched, before and after.
# ---------------------------------------------------------------------------
stage4_output_files = [
    os.path.join(OUTPUT_DIR, "stage4_schema.jsonl"),
    os.path.join(OUTPUT_DIR, "stage4_sheet_summary.csv"),
    os.path.join(OUTPUT_DIR, "stage4_column_summary.csv"),
]
hashes_before = {p: file_hash(p) for p in stage4_output_files if os.path.exists(p)}

# ---------------------------------------------------------------------------
# Run.
# ---------------------------------------------------------------------------
formulas_path, values_path = discover_capture_files(DUMPS_DIR)
result = stage5.run_stage5(
    formulas_path, values_path,
    appside_parse_dir=APPSIDE_PARSE_DIR,
    app_export_html_path=APP_EXPORT_HTML,
)

hashes_after = {p: file_hash(p) for p in stage4_output_files if os.path.exists(p)}
stage4_untouched = hashes_before == hashes_after

w("# Stage 5 gate check")
w()
w(f"App-side parse used: `{os.path.basename(APPSIDE_PARSE_DIR)}` -- identified as current in the stage 5 "
  f"precheck (byte-identical to `{os.path.basename(CLAUDE_MD_CITED_PARSE_DIR)}`, the one `AGENTS.md`/"
  f"`CLAUDE.md` cites, on every file this stage reads; this one additionally carries "
  f"`potential_unsatisfiable_conditions.csv`, which this stage does not read either way).")
w()
w(f"**Stage 4's own output files, verified byte-identical before and after this run: {stage4_untouched}**")
for p in stage4_output_files:
    w(f"- `{os.path.basename(p)}`: before={hashes_before.get(p, 'ABSENT')[:12]}... "
      f"after={hashes_after.get(p, 'ABSENT')[:12]}...")
w()

join = result.join
w(f"captureDate: `{join.provenance.capture_date}`")
w(f"tool commit: `{join.stamp.tool_commit}`")
w()

# ---------------------------------------------------------------------------
# Provenance / stamps.
# ---------------------------------------------------------------------------
w("## Provenance stamp")
w()
w(f"App-side parse directory: `{join.provenance.appside_parse_dir}`")
ident = join.provenance.app_identity
w(f"App identity, recovered from the export HTML: og:title=`{ident.og_title}`, version=`{ident.version}`, "
  f"default app folder=`{ident.default_app_folder}`")
w(f"Export HTML mtime (proxy for export date, since the export carries no internal date field): "
  f"`{ident.html_mtime_iso}`")
w(f"captureDate: `{join.provenance.capture_date}`")
gap = join.provenance.export_to_capture_gap_days
w(f"**Gap between export and capture: {gap:.2f} days** ({'capture is later' if gap and gap > 0 else 'export is later'}) "
  f"-- reported as a finding, gates nothing.")
w()
w("Content hashes of every file this stage reads:")
for name, h in join.provenance.input_file_hashes.items():
    w(f"- `{name}`: `{h}`")
w()

# ---------------------------------------------------------------------------
# Table matching.
# ---------------------------------------------------------------------------
w("## Table matching")
w()
matched = [t for t in join.tables if t.table_state == stage5.TABLE_STATE_MATCHED]
unmatched = [t for t in join.tables if t.table_state == stage5.TABLE_STATE_NO_TAB]
w(f"Tables: measured {len(join.tables)}, expected {GATE_TABLE_COUNT} (match: {len(join.tables) == GATE_TABLE_COUNT})")
w(f"Matched a tab by exact name: measured {len(matched)}, expected {GATE_MATCHED_TABLE_COUNT} "
  f"(match: {len(matched) == GATE_MATCHED_TABLE_COUNT})")
measured_unmatched = {t.table for t in unmatched}
w(f"Matched no tab: measured {sorted(measured_unmatched)}, expected {sorted(GATE_UNMATCHED_TABLES)} "
  f"(match: {measured_unmatched == GATE_UNMATCHED_TABLES})")
w()
w("| table | state | tab | header verdict |")
w("|---|---|---|---|")
for t in join.tables:
    w(f"| {t.table} | {t.table_state} | {t.matched_tab or '--'} | {t.header_verdict or '--'} |")
w()

# ---------------------------------------------------------------------------
# The undetermined diagnostic, against the gate.
# ---------------------------------------------------------------------------
w("## The undetermined diagnostic, against the gate")
w()
diag_by_table = {d.table: d for d in join.diagnostics}
for table, expected in GATE_DIAGNOSTIC.items():
    d = diag_by_table.get(table)
    if d is None:
        w(f"- **{table}**: NO DIAGNOSTIC PRODUCED (expected one) -- MISMATCH")
        continue
    measured = {
        "row1_nonempty": d.row1_nonempty_count,
        "row1_exact": len(d.row1_exact_matches),
        "row1_near": len(d.row1_near_misses),
    }
    match = measured == expected
    w(f"- **{table}**: measured {measured}, expected {expected} (match: {match})")
w()

archive_diag = diag_by_table.get("Archive")
archive_table_name, archive_cell, archive_expected_text = GATE_ARCHIVE_NEAR_MISS_CELL
near = archive_diag.row1_near_misses if archive_diag else ()
archive_confirmed = any(row1_text == archive_expected_text for row1_text, _app_col in near)
w(f"**The Archive near-miss, confirmed against the capture and the app-side parse:**")
if archive_confirmed:
    matching_pair = next((p for p in near if p[0] == archive_expected_text), None)
    w(f"- CONFIRMED: `{archive_table_name}!{archive_cell}` holds `{matching_pair[0]!r}` (trailing space), "
      f"the app-side column is `{matching_pair[1]!r}` (no trailing space). Reported as a whitespace "
      f"near-miss, not as an unmatched header -- exactly the gate's expected shape.")
else:
    w(f"- NOT CONFIRMED as expected -- see the raw diagnostic output above; this is a mismatch to report, "
      f"not to adjust away.")
w()

# ---------------------------------------------------------------------------
# Column / label state counts.
# ---------------------------------------------------------------------------
w("## Column and label state counts, workbook-wide")
w()
w(f"Column states: {result.column_state_counts}")
w(f"Label states: {result.label_state_counts}")
total_columns = sum(result.column_state_counts.values())
total_labels = sum(result.label_state_counts.values())
w(f"Accounting: {total_columns:,} app columns partitioned exactly once; {total_labels:,} header labels "
  f"partitioned exactly once (both asserted at build time in `run_stage5`, not merely reported here).")
w()

# ---------------------------------------------------------------------------
# Virtual field.
# ---------------------------------------------------------------------------
w("## Virtual-column field")
w()
w(f"`is_virtual` field present in the app-side columns file: **{join.virtual_field_present}**")
virtual_state_count = result.column_state_counts.get(stage5.COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED, 0)
w(f"App columns reported '{stage5.COLUMN_STATE_NO_SHEET_COLUMN_EXPECTED}': {virtual_state_count:,}")
w()

# ---------------------------------------------------------------------------
# Residue, verbatim (sample).
# ---------------------------------------------------------------------------
w("## Residue")
w()
w(f"Residue entries: {len(join.residue)}")
by_construct = Counter(r.defeating_construct for r in join.residue)
for k, v in by_construct.most_common():
    w(f"- {v} -- {k}")
w()
w("One entry per category, verbatim:")
seen = set()
for r in join.residue:
    if r.defeating_construct in seen:
        continue
    seen.add(r.defeating_construct)
    w(f"- **{r.defeating_construct}** at `{r.locations}`")
    w(f"    - what: {r.what}")
    w(f"    - consequence: {r.consequence}")
w()

# ---------------------------------------------------------------------------
# Reliability condition, verbatim.
# ---------------------------------------------------------------------------
w("## Reliability condition, verbatim")
w()
w(join.reliability_condition)
w()

# ---------------------------------------------------------------------------
# Write artifacts.
# ---------------------------------------------------------------------------
paths = write_stage5_artifacts(result, OUTPUT_DIR)
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
print(f"Stage 4 outputs untouched: {stage4_untouched}")
print(f"Tables: {len(join.tables)} (expect {GATE_TABLE_COUNT}); matched: {len(matched)} (expect {GATE_MATCHED_TABLE_COUNT})")
print(f"Unmatched tables: {sorted(measured_unmatched)} (expect {sorted(GATE_UNMATCHED_TABLES)})")
for table, expected in GATE_DIAGNOSTIC.items():
    d = diag_by_table.get(table)
    measured = {"row1_nonempty": d.row1_nonempty_count, "row1_exact": len(d.row1_exact_matches), "row1_near": len(d.row1_near_misses)} if d else None
    print(f"{table}: measured {measured} expected {expected}")
print(f"Archive near-miss confirmed: {archive_confirmed}")
print(f"Column state counts: {result.column_state_counts}")
print(f"Label state counts: {result.label_state_counts}")
print(f"Export-to-capture gap: {gap:.2f} days")
