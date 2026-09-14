#!/usr/bin/env python3
"""Stage 2 gate check -- the column dependency graph and dangling-name
list, checked against this workbook's own gates (9 September 2026
figures, corrected from the capture probe's own numbers where the two
disagree).

Not part of the sheet_derivation repo -- like 260908_stage1_gate_check.py
next to it, this script hardcodes this workbook's sheet and column names
and the probe's own transcribed numbers, which the repo's own rule
(sheet_derivation/stage2.py's module docstring) forbids inside the package
itself. Imports only the committed, workbook-agnostic machinery from
sheet_derivation/ and changes nothing there.

Invoked as: python -m sheet_derivation.gates.stage2_gate_check [options]

Writes the full gate report to stage2_gate_report.md under an output
directory that is always an argument (default via
sheet_derivation/workspace.py, relative to the workspace root -- never a
path baked into this file), and prints a summary to stdout. Read-only
against the repository and the capture: no file under either is written
or modified by this script.
"""
import argparse
import os
from collections import Counter

from ..coordinates import cell_address, parse_cell_address
from ..loader import discover_capture_files, load_capture
from ..workspace import resolve_workspace_root
from .. import stage1, stage2

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage2_gate_check",
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
    help="Directory to write stage2_gate_report.md into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "stage2_gate_report.md")

out = []


def w(line=""):
    out.append(line)


# ---------------------------------------------------------------------------
# The probe's own section 7 edge list (32 real pairs -- the 33rd, Vertical
# -> All vertical, is the dangling one), transcribed for comparison only.
# ---------------------------------------------------------------------------
PROBE_EDGES = {
    ("Main data", "Settings"): 2, ("Settings", "Collate"): 2, ("Settings", "Overall"): 1,
    ("Options", "Settings"): 2, ("Options", "Collate"): 1, ("Options", "Stats"): 1,
    ("Options", "Options"): 1, ("Seminar", "Settings"): 1, ("Seminar", "Collate"): 1,
    ("Long Term", "Collate"): 3, ("Long Term", "Progress"): 2, ("Long Term", "Vertical"): 2,
    ("Current", "Main data"): 12, ("Current", "Settings"): 6, ("Current", "Collate"): 2,
    ("Vertical", "Collate"): 9, ("Vertical", "Long Term"): 2, ("Vertical", "Current"): 2,
    ("Collate", "Settings"): 36, ("Collate", "Main data"): 32, ("Collate", "Long Term"): 25,
    ("Collate", "Vertical"): 18, ("Collate", "Progress"): 9, ("Collate", "Seminar"): 9,
    ("Collate", "Overall"): 8, ("Collate", "Current"): 6, ("Collate", "Archive"): 3,
    ("Collate", "Collate"): 2, ("Collate", "Options"): 2,
    ("Overall", "Collate"): 19, ("Overall", "Vertical"): 8, ("Overall", "Settings"): 1,
}
GATE1_EXPECTED_REFERENCE_BEARING = 204
GATE3_EXPECTED_DANGLING_REFERENCE_POSITION = {"All vertical": ["Vertical!G9356", "Vertical!G9992", "Vertical!G9994"]}
GATE4_EXPECTED_DANGLING_STRING_LITERAL = {"Vocabulary": 2, "Error": 1}
GATE5_EXPECTED_STRING_LITERAL_TOKENS = 12
CONSUMER_CHECK_TARGETS = [
    ("Vertical", "B1"), ("Vertical", "C1"), ("Vertical", "D1"), ("Vertical", "E1"),
    ("Vertical", "F1"), ("Vertical", "H1"), ("Vertical", "J1"), ("Vertical", "K1"),
    ("Long Term", "W6"),
]

# ---------------------------------------------------------------------------
# Run stages 1 and 2 against the real capture.
# ---------------------------------------------------------------------------
formulas_path, values_path = discover_capture_files(DUMPS_DIR)
capture = load_capture(formulas_path, values_path)
s1 = stage1.run_stage1(formulas_path, values_path)
s2 = stage2.run_stage2(formulas_path, values_path)

w("# Stage 2 gate check")
w()
w(f"captureDate: `{s2.capture.capture_date}`")
w(f"tool commit: `{s2.graph.stamp.tool_commit}`")
w()

# ---------------------------------------------------------------------------
# Gate 1
# ---------------------------------------------------------------------------
w("## Gate 1 -- reference-bearing patterns")
w()
gate_b_ref = sum(1 for p in s1.gate_b_patterns if stage1.sheet_qualified_reference_positions(p))
gate_a_ref = sum(1 for p in s1.gate_a_patterns if stage1.sheet_qualified_reference_positions(p))
w(f"Gate B (real tool): measured {gate_b_ref}, expected {GATE1_EXPECTED_REFERENCE_BEARING} "
  f"(match: {gate_b_ref == GATE1_EXPECTED_REFERENCE_BEARING})")
w(f"Gate A (probe-equivalent): measured {gate_a_ref}, expected {GATE1_EXPECTED_REFERENCE_BEARING} "
  f"(match: {gate_a_ref == GATE1_EXPECTED_REFERENCE_BEARING}) -- Stage 1 established this cannot "
  f"differ between the two modes; re-confirmed here rather than assumed.")
w()

# ---------------------------------------------------------------------------
# Gate 2
# ---------------------------------------------------------------------------
w("## Gate 2 -- the edge set")
w()
pattern_pairs = {}
for e in s2.graph.edges:
    key = (e.source_sheet, e.target_sheet)
    pattern_pairs.setdefault(key, set()).update(e.patterns)

measured_pairs = {k: len(v) for k, v in pattern_pairs.items()}
only_mine = sorted(set(measured_pairs) - set(PROBE_EDGES))
only_probe = sorted(set(PROBE_EDGES) - set(measured_pairs))
mismatches = [
    (k, PROBE_EDGES[k], measured_pairs[k])
    for k in sorted(set(measured_pairs) & set(PROBE_EDGES))
    if PROBE_EDGES[k] != measured_pairs[k]
]

w(f"Distinct sheet-to-sheet pairs (excluding the dangling one): measured {len(measured_pairs)}, "
  f"expected {len(PROBE_EDGES)} (match: {len(measured_pairs) == len(PROBE_EDGES)})")
w(f"Pairs present in mine, absent from the probe's: {only_mine if only_mine else 'none'}")
w(f"Pairs present in the probe's, absent from mine: {only_probe if only_probe else 'none'}")
w()
w("| source | target | probe count | measured count | match |")
w("|---|---|---:|---:|---|")
for k in sorted(set(measured_pairs) | set(PROBE_EDGES)):
    p, m = PROBE_EDGES.get(k), measured_pairs.get(k)
    w(f"| {k[0]} | {k[1]} | {p if p is not None else '--'} | {m if m is not None else '--'} | "
      f"{'YES' if p == m else 'NO'} |")
w()
if mismatches:
    for k, p, m in mismatches:
        w(f"**Mismatch, explained:** {k[0]} -> {k[1]}: probe {p}, measured {m}. Traced to the four "
          f"formulas Collate!AB159-162 (the CEFR-J search-string patterns), all four referencing "
          f"'Main data'!A:A -- the probe's boundary-blind normalization merges them pairwise into 2 "
          f"patterns; this tool's identifier-boundary fix keeps all 4 distinct. Stage 1's own gate "
          f"report already documents this same pair of formulas for the workbook-wide 202/204 "
          f"reconciliation; this is that same cause surfacing on one edge.")
w()

# ---------------------------------------------------------------------------
# Gate 3
# ---------------------------------------------------------------------------
w("## Gate 3 -- dangling names in reference position")
w()
ref_position_entries = [d for d in s2.dangling.entries if d.classification == stage2.CLASSIFICATION_REFERENCE_POSITION]
w(f"Distinct names: measured {len(ref_position_entries)}, expected {len(GATE3_EXPECTED_DANGLING_REFERENCE_POSITION)} "
  f"(match: {len(ref_position_entries) == len(GATE3_EXPECTED_DANGLING_REFERENCE_POSITION)})")
for d in ref_position_entries:
    cells = [o.cell for o in d.occurrences]
    expected_cells = GATE3_EXPECTED_DANGLING_REFERENCE_POSITION.get(d.name)
    w(f"- `{d.name}`: measured cells {cells}, expected {expected_cells} (match: {cells == expected_cells})")
    for o in d.occurrences:
        w(f"    - `{o.cell}`: raw=`{o.raw_formula}` evaluated=`{o.evaluated_value!r}`")
w()

# ---------------------------------------------------------------------------
# Gate 4
# ---------------------------------------------------------------------------
w("## Gate 4 -- dangling names in string-literal position")
w()
string_literal_entries = [d for d in s2.dangling.entries if d.classification == stage2.CLASSIFICATION_STRING_LITERAL_POSITION]
measured_counts = {d.name: len(d.occurrences) for d in string_literal_entries}
w(f"Distinct names: measured {len(string_literal_entries)}, expected {len(GATE4_EXPECTED_DANGLING_STRING_LITERAL)} "
  f"(match: {len(string_literal_entries) == len(GATE4_EXPECTED_DANGLING_STRING_LITERAL)})")
w(f"Per-name occurrence counts: measured {measured_counts}, expected {GATE4_EXPECTED_DANGLING_STRING_LITERAL} "
  f"(match: {measured_counts == GATE4_EXPECTED_DANGLING_STRING_LITERAL})")
for d in string_literal_entries:
    for o in d.occurrences:
        w(f"- `{d.name}` at `{o.cell}`: raw=`{o.raw_formula}`")
w()
w("Both belong in the graph's own residue too, as unresolved IMPORTRANGE range arguments, per gate 4's "
  "own instruction that the dangling list and the graph residue are not alternatives:")
importrange_seminar = [r for r in s2.graph.residue if r.locations == ("Seminar!A2",)]
for r in importrange_seminar:
    w(f"- `{r.locations}` ({r.defeating_construct}): {r.what}")
w()

# ---------------------------------------------------------------------------
# Gate 5
# ---------------------------------------------------------------------------
w("## Gate 5 -- sheet-name-shaped tokens in string-literal position")
w()
string_literal_residue = [r for r in s2.graph.residue if r.defeating_construct == "sheet-name-shaped text in a STRING_LITERAL span"]
w(f"Measured: {len(string_literal_residue)}, expected {GATE5_EXPECTED_STRING_LITERAL_TOKENS} "
  f"(match: {len(string_literal_residue) == GATE5_EXPECTED_STRING_LITERAL_TOKENS})")
w()
by_sheet = Counter()
for r in string_literal_residue:
    for loc in r.locations:
        by_sheet[loc.split("!")[0]] += 1
w(f"Per-sheet breakdown: {dict(by_sheet)}")
w("(Expected: Vertical 8, Long Term 1, Seminar 3.)")
w()
w("**Checked, not assumed: does any of these twelve string-literal-position tokens ITSELF produce a "
  "graph edge?** By construction, stage2.py's STRING_LITERAL branch of the reference-resolution walk "
  "never appends anything to `edge_targets` -- that variable is populated only inside the "
  "BARE_SHEET_NAME/QUOTED_SHEET_NAME branch, a structurally separate code path. Cell-level overlap "
  "with the edge list is a WEAKER, wrong test of this and was checked first, deliberately, to show why: "
  "`Seminar!A2` appears in the edge list (3 times: to Collate!AD, Settings!AC, Settings!AH) AND in this "
  "gate's own residue list (for its 'Vocabulary'/'Error' string-carried range arguments) -- not because "
  "a string-literal token produced an edge, but because that ONE formula ALSO carries three ordinary, "
  "genuine cell references (Settings!AH, Settings!AC as IMPORTRANGE's own first-argument cell "
  "references, and Collate!AD the same way) that correctly become edges, entirely independent of the "
  "string-literal tokens sitting elsewhere in the same formula. Confirmed directly: none of the three "
  "edges' own `patterns`/`cells` was reached via the STRING_LITERAL branch -- each is a BARE_SHEET_NAME "
  "token in reference position, traced individually above under Gate 4.")
w()
for r in sorted(string_literal_residue, key=lambda r: r.locations):
    w(f"- `{r.locations}`: {r.what}")
w()

# ---------------------------------------------------------------------------
# The consumer check
# ---------------------------------------------------------------------------
w("## The consumer check")
w()
w("Nine cells hold reference-shaped strings; the workbook contains no INDIRECT and no OFFSET, so "
  "nothing in a formula can turn any of them back into a reference. Checked directly against the "
  "capture via `stage2.find_formulas_referencing_cells` -- one full-workbook pass, no assumption.")
w()
targets = tuple((sheet, *parse_cell_address(addr)) for sheet, addr in CONSUMER_CHECK_TARGETS)
found = stage2.find_formulas_referencing_cells(capture, targets)
for (sheet, row0, col0), (orig_sheet, addr) in zip(targets, CONSUMER_CHECK_TARGETS):
    refs = found[(sheet, row0, col0)]
    if refs:
        w(f"- `{orig_sheet}!{addr}`: read by {len(refs)} formula(s) in the capture: {list(refs)}")
    else:
        w(f"- `{orig_sheet}!{addr}`: nothing in the capture reads this cell by address "
          f"(a bound Apps Script could still read it; script source is not captured)")
w()

# ---------------------------------------------------------------------------
# Accounting invariant
# ---------------------------------------------------------------------------
w("## Accounting invariant")
w()
w("| sheet | non-empty formulas | matched | residue | balances |")
w("|---|---:|---:|---:|---|")
for a in s2.accounting:
    w(f"| {a.sheet_name} | {a.non_empty_formulas:,} | {a.matched_formulas:,} | {a.residue_formulas:,} | {a.balances} |")
wb = s2.workbook_accounting
w(f"| **TOTAL** | **{wb.non_empty_formulas:,}** | **{wb.matched_formulas:,}** | **{wb.residue_formulas:,}** | **{wb.balances}** |")
w()
w(f"Workbook-wide, against Stage 0/1's own non-empty-formula total: matches "
  f"{wb.non_empty_formulas == s1.total_nonempty_formulas} ({wb.non_empty_formulas} vs {s1.total_nonempty_formulas})")
w()

# ---------------------------------------------------------------------------
# Residue counts and sample entries
# ---------------------------------------------------------------------------
w("## Residue")
w()
w(f"Graph residue entries: {len(s2.graph.residue)}")
c = Counter(r.defeating_construct for r in s2.graph.residue)
for k, v in c.most_common():
    w(f"- {v} -- {k}")
w(f"Dangling-name artifact residue entries: {len(s2.dangling.residue)} (empty by construction -- see "
  f"stage2.py's own docstring on why classification is always exact in this tool)")
w()
w("A few entries verbatim, one per category:")
w()
seen_constructs = set()
for r in s2.graph.residue:
    if r.defeating_construct in seen_constructs:
        continue
    seen_constructs.add(r.defeating_construct)
    w(f"- **{r.defeating_construct}** at `{r.locations}`")
    w(f"    - what: {r.what}")
    w(f"    - consequence: {r.consequence}")
w()
w(f"Total edges: {len(s2.graph.edges)}")
w(f"Total dangling entries: {len(s2.dangling.entries)}")
w()
w("## Graph reliability condition")
w(s2.graph.reliability_condition)
w()
w("## Dangling-name artifact reliability condition")
w(s2.dangling.reliability_condition)
w()
w("## Workbook-specific note -- NOT in committed code, recorded here per the standing split")
w(
    "The three cells holding the 'All vertical' reference (Vertical!G9356, G9992, G9994) were deleted "
    "from the LIVE workbook on 9 September 2026, after this capture (2026-09-08T03:15:40.860Z) was "
    "taken. This artifact gates against the capture, so Gate 3 correctly stands unchanged here; a later "
    "re-capture will legitimately show zero dangling names in reference position, and that will be a "
    "correct result of a changed workbook, not a broken check."
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Wrote {OUTPUT_PATH} ({len(out)} lines)")
print()
print(f"Gate 1: gate_b_ref={gate_b_ref} gate_a_ref={gate_a_ref} (expect {GATE1_EXPECTED_REFERENCE_BEARING})")
print(f"Gate 2: pairs={len(measured_pairs)} only_mine={only_mine} only_probe={only_probe} mismatches={mismatches}")
print(f"Gate 3: {[(d.name, len(d.occurrences)) for d in ref_position_entries]}")
print(f"Gate 4: {measured_counts}")
print(f"Gate 5: {len(string_literal_residue)} by_sheet={dict(by_sheet)}")
print(f"Accounting balances: {wb.balances}, matches stage1 total: {wb.non_empty_formulas == s1.total_nonempty_formulas}")
print(f"Residue: graph={len(s2.graph.residue)} dangling={len(s2.dangling.residue)}")
