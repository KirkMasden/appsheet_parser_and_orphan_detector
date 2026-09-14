#!/usr/bin/env python3
"""Stage 1 cross-sheet-reference gate ledger.

Not part of the sheet_derivation repo -- like 260908_stage1_gate_check.py
next to it, this script hardcodes this workbook's sheet names and the
capture probe's own transcribed numbers (section 7's edge list, section 3's
per-sheet table), which the repo's own rule (sheet_derivation/stage1.py's
module docstring) forbids inside the package itself. It imports only the
committed, workbook-agnostic machinery from sheet_derivation/ and changes
nothing there.

Purpose: settle whether the probe's section 7 claim -- 202 distinct
patterns contain a cross-sheet reference, against a 33-pair sheet-to-sheet
edge list, one dangling name ("All vertical", section 15a) -- agrees with
what Stage 1's real tokenizer measures under Gate B, its actual
normalization (250, as of commit 3ece526's fix to stop normalizing a
$-anchored row digit; Gate A's own probe-equivalent figure remains 204,
unaffected, since that fix is deliberately Gate-B-only -- see item 3
below, which reports both), and if not, show exactly which patterns/pairs
account for the difference, using result.a_to_b_split (already computed
by run_stage1) as the source of truth for the Gate A/Gate B relationship.
Nothing below is
hand-asserted without a derivation printed alongside it; where this script
transcribes a probe number for comparison, that number is never used to
produce this script's own counts -- it is only compared against them.

Every raw formula and pattern text printed below is verbatim, in full --
no slicing. This workbook holds at least one formula 2,844 characters long
(confirmed separately: Options row 3, column E), and the report must carry
it whole if it appears in any listing.

Invoked as: python -m sheet_derivation.gates.stage1_reference_ledger [options]

Writes the report to stage1_reference_ledger_report.md under an output
directory that is always an argument (default via
sheet_derivation/workspace.py, relative to the workspace root -- never a
path baked into this file), and prints a summary to stdout. Read-only
against the repository and the capture: no file under either is written
or modified by this script.
"""
import argparse
import os
import re
from collections import Counter, defaultdict

from ..coordinates import cell_address
from ..counts import is_nonempty
from ..loader import discover_capture_files, load_capture
from ..normalize import normalize_pattern
from ..residue import build_stamp
from ..tokenizer import TokenKind, scan_formula
from ..workspace import resolve_workspace_root
from .. import stage1

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage1_reference_ledger",
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
    help="Directory to write stage1_reference_ledger_report.md into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "stage1_reference_ledger_report.md")

out = []


def w(line=""):
    out.append(line)


# ---------------------------------------------------------------------------
# The probe's own section 7 edge list and section 15a finding, transcribed
# ONLY for comparison in item 5/(c) below -- never fed into this script's
# own derivation of anything.
# ---------------------------------------------------------------------------
PROBE_EDGES = [
    ("Main data", "Settings", 2), ("Settings", "Collate", 2), ("Settings", "Overall", 1),
    ("Options", "Settings", 2), ("Options", "Collate", 1), ("Options", "Stats", 1),
    ("Options", "Options", 1), ("Seminar", "Settings", 1), ("Seminar", "Collate", 1),
    ("Long Term", "Collate", 3), ("Long Term", "Progress", 2), ("Long Term", "Vertical", 2),
    ("Current", "Main data", 12), ("Current", "Settings", 6), ("Current", "Collate", 2),
    ("Vertical", "Collate", 9), ("Vertical", "Long Term", 2), ("Vertical", "Current", 2),
    ("Vertical", "All vertical", 1),
    ("Collate", "Settings", 36), ("Collate", "Main data", 30), ("Collate", "Long Term", 25),
    ("Collate", "Vertical", 18), ("Collate", "Progress", 9), ("Collate", "Seminar", 9),
    ("Collate", "Overall", 8), ("Collate", "Current", 6), ("Collate", "Archive", 3),
    ("Collate", "Collate", 2), ("Collate", "Options", 2),
    ("Overall", "Collate", 19), ("Overall", "Vertical", 8), ("Overall", "Settings", 1),
]
PROBE_TOTAL_REF_PATTERNS = 202
PROBE_DANGLING_NAMES = ["All vertical"]

# ---------------------------------------------------------------------------
# Run Stage 1 against the real capture.
# ---------------------------------------------------------------------------
formulas_path, values_path = discover_capture_files(DUMPS_DIR)
capture = load_capture(formulas_path, values_path)
result = stage1.run_stage1(formulas_path, values_path)
stamp = build_stamp(capture.capture_date)

w("# Stage 1 cross-sheet-reference gate ledger")
w()
w("Everything below is derived by running the committed `sheet_derivation` package "
  "against the real capture; nothing is asserted without the code that produced it "
  "named alongside. Where a probe number is shown, it is quoted from "
  "`capture_probe_report.md` for comparison only.")
w()

# ---------------------------------------------------------------------------
# Item 1
# ---------------------------------------------------------------------------
w("## 1. Provenance")
w()
w(f"captureDate: `{result.capture.capture_date}`")
w(f"tool commit (repository HEAD at run time): `{stamp.tool_commit}`")
w()

# ---------------------------------------------------------------------------
# Item 2
# ---------------------------------------------------------------------------
w("## 2. Distinct pattern counts, Gate A vs Gate B")
w()
w(f"**Workbook-wide:** Gate A (probe-equivalent normalization) = "
  f"{result.total_distinct_patterns_gate_a}; Gate B (tool's real normalization) = "
  f"{result.total_distinct_patterns_gate_b}. Total non-empty formulas = "
  f"{result.total_nonempty_formulas}.")
w()
w("**Per sheet:**")
w()
w("| sheet | non-empty formulas | distinct patterns (Gate A) | distinct patterns (Gate B) |")
w("|---|---:|---:|---:|")
for c in result.per_sheet_counts:
    w(f"| {c.sheet_name} | {c.non_empty_formulas} | {c.distinct_patterns_gate_a} | {c.distinct_patterns_gate_b} |")
w()

# ---------------------------------------------------------------------------
# Item 3
# ---------------------------------------------------------------------------
w("## 3. Reference-bearing pattern counts, Gate A vs Gate B")
w()
w("A pattern is 'reference-bearing' when re-tokenizing its own pattern text (not a raw "
  "instance) with `scan_formula` yields at least one `BARE_SHEET_NAME` or "
  "`QUOTED_SHEET_NAME` token -- a genuine reference-position sheet name, never a match "
  "inside a `STRING_LITERAL` span, since that span is one opaque token by construction "
  "and is never reclassified into anything else. Checking the pattern text itself, rather "
  "than one raw instance, is deliberate: normalize.py never rewrites the identifier "
  "immediately before `!`, only the digits of an `A1_REFERENCE` span, so this property is "
  "invariant across every raw instance a pattern represents -- there is nothing here "
  "sample-dependent about which instance happened to be recorded first.")
w()

gate_a_ref_patterns = {p for p in result.gate_a_patterns if stage1.sheet_qualified_reference_positions(p)}
gate_b_ref_patterns = {p for p in result.gate_b_patterns if stage1.sheet_qualified_reference_positions(p)}

w(f"**Gate A reference-bearing distinct patterns: {len(gate_a_ref_patterns)}.**")
w(f"**Gate B reference-bearing distinct patterns: {len(gate_b_ref_patterns)}** "
  f"(probe section 7's own figure, for the same question under its own un-fixed regex, "
  f"un-boundary-checked and string-literal-blind: {PROBE_TOTAL_REF_PATTERNS}).")
w()

# ---------------------------------------------------------------------------
# Item 4 -- the two-sided ledger, from a_to_b_split
# ---------------------------------------------------------------------------
w("## 4. The two-sided ledger (Gate A <-> Gate B, via `run_stage1`'s own `a_to_b_split`)")
w()
w("### 4a. Every Gate A pattern that splits into more than one Gate B pattern")
w()
splits = {a: bs for a, bs in result.a_to_b_split.items() if len(bs) > 1}
total_extra = sum(len(bs) - 1 for bs in splits.values())
w(f"{len(splits)} Gate A patterns split into more than one Gate B pattern, "
  f"{total_extra} extra Gate B patterns beyond the Gate A count they came from. "
  f"{result.total_distinct_patterns_gate_b} - {result.total_distinct_patterns_gate_a} = "
  f"{result.total_distinct_patterns_gate_b - result.total_distinct_patterns_gate_a}; "
  f"residual after accounting for these splits: "
  f"{(result.total_distinct_patterns_gate_b - result.total_distinct_patterns_gate_a) - total_extra} "
  f"(must be 0 -- a split is the ONLY way Gate B can exceed Gate A, since Gate B only ever "
  f"refines a Gate A grouping, never merges two of its members).")
w()
for a_pat, b_pats in sorted(splits.items()):
    info_a = result.gate_a_patterns[a_pat]
    w(f"- **Gate A pattern** (`{info_a.first_address}`): `{a_pat}`")
    w(f"  - raw instance verbatim (`{info_a.first_address}`): `{info_a.first_raw}`")
    for bp in sorted(b_pats):
        info_b = result.gate_b_patterns[bp]
        w(f"  - -> **Gate B pattern** (`{info_b.first_address}`): `{bp}`")
        w(f"    - raw instance verbatim (`{info_b.first_address}`): `{info_b.first_raw}`")
w()

w("### 4b. Every pattern counted as reference-bearing under one gate and not the other")
w()
w("Checked over every `a_to_b_split` entry (not only the ones that split into more than "
  "one Gate B pattern), comparing the Gate A parent's own reference-bearing status "
  "against each of its Gate B children's.")
w()
disagreements = []
for a_pat, b_pats in result.a_to_b_split.items():
    a_ref = bool(stage1.sheet_qualified_reference_positions(a_pat))
    for bp in b_pats:
        b_ref = bool(stage1.sheet_qualified_reference_positions(bp))
        if a_ref != b_ref:
            disagreements.append((a_pat, bp, a_ref, b_ref))
w(f"**Disagreements found: {len(disagreements)}.**")
w()
if disagreements:
    for a_pat, bp, a_ref, b_ref in sorted(disagreements):
        info_a = result.gate_a_patterns[a_pat]
        info_b = result.gate_b_patterns[bp]
        w(f"- Gate A pattern (`{info_a.first_address}`, reference-bearing={a_ref}): `{a_pat}`")
        w(f"  - raw: `{info_a.first_raw}`")
        w(f"  - Gate B pattern (`{info_b.first_address}`, reference-bearing={b_ref}): `{bp}`")
        w(f"  - raw: `{info_b.first_raw}`")
else:
    w("None found. `normalize_pattern` and `normalize_probe_equivalent` both rewrite only "
      "an `A1_REFERENCE` token's trailing digit run; neither ever touches the identifier "
      "run immediately before `!` that a `BARE_SHEET_NAME`/`QUOTED_SHEET_NAME` token is "
      "built from, and neither ever reclassifies a `STRING_LITERAL` span into anything "
      "else. A pattern's reference-bearing status is therefore fixed by its raw structure "
      "before either gate's row-digit rewrite is applied, so no split changes it -- Gate A "
      "and Gate B differ only in HOW MANY distinct patterns the same reference-bearing "
      "formulas fall into (item 3 above), never in WHICH formulas are reference-bearing.")
w()

# ---------------------------------------------------------------------------
# Item 5 -- derived sheet-to-sheet edge list
# ---------------------------------------------------------------------------
w("## 5. Derived sheet-to-sheet edge list")
w()
w("Same per-sheet, per-distinct-Gate-B-pattern methodology the probe's own section 7 "
  "script uses (count a referenced tab once per distinct pattern within a sheet, not "
  "once per raw instance), but reference tokens are the real tokenizer's "
  "`BARE_SHEET_NAME`/`QUOTED_SHEET_NAME`, in reference position only, over the RAW "
  "formula text -- never a text match inside a `STRING_LITERAL` span, and never the "
  "probe's own boundary-blind regex.")
w()

QUOTE_UNESCAPE_RE = re.compile(r"''")


def referenced_name_from_token(raw: str, tok) -> str:
    text = tok.text_in(raw)
    if tok.kind == TokenKind.QUOTED_SHEET_NAME:
        inner = text[1:-1]
        return QUOTE_UNESCAPE_RE.sub("'", inner)
    return text


edge_counts = defaultdict(Counter)
known_sheets = set(capture.sheet_order)
seen_patterns_by_sheet = {name: set() for name in capture.sheet_order}

for sheet_name in capture.sheet_order:
    fs = capture.formula_sheet(sheet_name)
    for r, row in enumerate(fs.formulas):
        for c, raw in enumerate(row):
            if not is_nonempty(raw):
                continue
            tokens = scan_formula(raw)
            pat = normalize_pattern(raw, tokens)
            if pat in seen_patterns_by_sheet[sheet_name]:
                continue
            seen_patterns_by_sheet[sheet_name].add(pat)
            refs = set()
            for tok in tokens:
                if tok.kind in (TokenKind.BARE_SHEET_NAME, TokenKind.QUOTED_SHEET_NAME):
                    refs.add(referenced_name_from_token(raw, tok))
            for ref in refs:
                edge_counts[sheet_name][ref] += 1

derived_edges = []
for src in capture.sheet_order:
    for tab, cnt in edge_counts[src].most_common():
        derived_edges.append((src, tab, cnt))

dangling = sorted({tab for _, tab, _ in derived_edges if tab not in known_sheets})

w(f"**Distinct (source, referenced) pairs: {len(derived_edges)}.**")
w()
w("| source sheet | referenced tab | distinct pattern count | tab exists in capture? |")
w("|---|---|---:|---|")
for src, tab, cnt in derived_edges:
    exists = "yes" if tab in known_sheets else "NO -- UNMATCHED"
    w(f"| {src} | {tab} | {cnt} | {exists} |")
w()
w(f"**Referenced names with no matching sheet in this capture: {len(dangling)}.**")
for name in dangling:
    w(f"- `{name}`")
w()

# ---------------------------------------------------------------------------
# Item 6 -- sheet-name-shaped tokens inside STRING_LITERAL position
# ---------------------------------------------------------------------------
w("## 6. Sheet-name-shaped text found inside STRING_LITERAL position")
w()
w("Listed separately from section 5 and excluded from its edge list -- none of these is "
  "a `BARE_SHEET_NAME`/`QUOTED_SHEET_NAME` token; each sits inside a `STRING_LITERAL` "
  "span, which is one opaque token by construction and is never reclassified. Checked "
  "over every distinct Gate B pattern's own first raw instance -- sufficient and "
  "exhaustive, since two raw instances sharing a Gate B pattern text share that pattern's "
  "`STRING_LITERAL` spans verbatim (Stage 1's row-digit rewrite never touches a "
  "`STRING_LITERAL` span at all, by construction), so no distinct string-literal-interior "
  "occurrence could exist on an instance whose pattern text was already checked.")
w()

SHEET_SHAPE_RE = re.compile(r"(?:'([^']*)'|([A-Za-z_][A-Za-z0-9_ ]*))!")

d6_hits = []
seen_gate_b_patterns_checked = set()
for pat, info in result.gate_b_patterns.items():
    if pat in seen_gate_b_patterns_checked:
        continue
    seen_gate_b_patterns_checked.add(pat)
    raw = info.first_raw
    tokens = scan_formula(raw)
    for tok in tokens:
        if tok.kind == TokenKind.STRING_LITERAL:
            span_text = tok.text_in(raw)
            for m in SHEET_SHAPE_RE.finditer(span_text):
                name = m.group(1) if m.group(1) is not None else m.group(2)
                d6_hits.append((info.first_sheet, cell_address(info.first_row0, info.first_col0), raw, name, span_text))

w(f"**Sheet-name-shaped tokens inside string literals: {len(d6_hits)} found.**")
w()
for sheet, addr, raw, name, span in sorted(d6_hits, key=lambda x: (x[0], x[1])):
    w(f"- `{sheet}!{addr}` -- referenced name (as written): `{name}` -- string-literal text: `{span}`")
    w(f"  - raw formula verbatim: `{raw}`")
w()

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Wrote {OUTPUT_PATH} ({len(out)} lines)")
print()
print(f"Gate A total: {result.total_distinct_patterns_gate_a}  Gate B total: {result.total_distinct_patterns_gate_b}")
print(f"Item 3 -- Gate A ref-bearing: {len(gate_a_ref_patterns)}  Gate B ref-bearing: {len(gate_b_ref_patterns)} "
      f"(probe: {PROBE_TOTAL_REF_PATTERNS})")
print(f"Item 4a -- splits: {len(splits)}  extra patterns: {total_extra}")
print(f"Item 4b -- ref-bearing disagreements between gates: {len(disagreements)}")
print(f"Item 5 -- derived edges: {len(derived_edges)} (probe transcribed: {len(PROBE_EDGES)})  dangling: {dangling}")
print(f"Item 6 -- string-literal sheet-shaped hits: {len(d6_hits)}")
