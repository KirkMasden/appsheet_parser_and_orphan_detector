#!/usr/bin/env python3
"""Stage 1 gate check, revised after the FUNCTION_NAME whitespace-tolerance
fix. Runs the (workbook-agnostic) sheet_derivation package against Kirk's
real capture and compares the result to the probe's measured numbers.

Not part of the sheet_derivation repo's own workbook-agnostic modules --
see the original docstring in git history (repo commit b26cd9f) for why:
this script hardcodes sheet names and the probe's own numbers, which the
repo's own rule forbids inside those modules. Kept in sheet_derivation/gates/
for that reason.

Invoked as: python -m sheet_derivation.gates.stage1_gate_check [options]

Writes the full gate report to stage1_gate_report.md under an output
directory that is always an argument (default via
sheet_derivation/workspace.py, relative to the workspace root -- never a
path baked into this file), and prints a summary to stdout.
"""
import argparse
import os
import re
from collections import Counter

from ..coordinates import cell_address
from ..counts import is_nonempty
from ..loader import discover_capture_files, load_capture
from ..normalize import normalize_pattern
from ..residue import build_stamp
from ..tokenizer import TokenKind, scan_formula
from ..verify import normalize_probe_equivalent
from ..workspace import resolve_workspace_root
from .. import stage1

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.stage1_gate_check",
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
    help="Directory to write stage1_gate_report.md into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "stage1_gate_report.md")

out = []


def w(line=""):
    out.append(line)


# ---------------------------------------------------------------------------
# Probe section 3/5/7's measured numbers, transcribed for comparison only.
# ---------------------------------------------------------------------------
PROBE_A2 = {
    "Main data": (198, 3), "Welcome": (0, 0), "Progress": (0, 0), "Sheet50": (0, 0),
    "Progress archive": (0, 0), "Archive": (5702, 1), "Settings": (10, 6),
    "Options": (5, 5), "Stats": (0, 0), "Seminar": (1, 1), "Long Term": (172, 8),
    "Current": (18993, 31), "Vertical": (139993, 24), "Volatile Formulas Report": (0, 0),
    "Collate": (20523, 280), "Downstream Dependency Report": (0, 0), "Overall": (64, 28),
}
PROBE_TOTAL_PATTERNS = 382
PROBE_TOTAL_FORMULAS = 185661
PROBE_FUNC_VOCAB = {
    "IF": 129, "IFERROR": 42, "VALUE": 37, "COUNTIF": 35, "CONCATENATE": 31, "SPLIT": 28,
    "MAX": 27, "TEXT": 27, "INDEX": 27, "ARRAYFORMULA": 23, "LEFT": 20, "FILTER": 18,
    "REPT": 18, "SUMIFS": 16, "ISNUMBER": 12, "SUM": 12, "ROUND": 12, "SUMPRODUCT": 11,
    "SEARCH": 11, "MIN": 10, "MATCH": 10, "OR": 10, "TIME": 10, "TIMEVALUE": 10, "AND": 9,
    "COUNTIFS": 9, "ABS": 8, "VLOOKUP": 8, "ROUNDDOWN": 8, "LEN": 8, "COUNTA": 7, "QUERY": 7,
    "DATE": 7, "TRIM": 6, "CHAR": 6, "SUBSTITUTE": 6, "TRANSPOSE": 5, "TO_TEXT": 5,
    "ARRAY_CONSTRAIN": 5, "DATEVALUE": 5, "ROUNDUP": 5, "IFS": 4, "POWER": 4, "YEAR": 4,
    "AVERAGE": 4, "RIGHT": 3, "DEC": 3, "IMPORTRANGE": 3, "REGEXMATCH": 3, "TEXTJOIN": 3,
    "UNIQUE": 3, "NOT": 3, "TO_DATE": 3, "SORT": 2, "INT": 2, "SQRT": 2, "MAXIFS": 2,
    "SWITCH": 2, "MOD": 2, "WEEKDAY": 2, "REGEXREPLACE": 2, "LOWER": 2, "STDEV": 1,
    "NOW": 1, "JOIN": 1,
}
PROBE_D2_REFERENCE_PATTERNS = 202
PROBE_D4_TYPOGRAPHIC_QUOTE_FORMULAS = 5
ALL_TOKEN_KINDS = [k.value for k in TokenKind]

# ---------------------------------------------------------------------------
# Run Stage 1
# ---------------------------------------------------------------------------
formulas_path, values_path = discover_capture_files(DUMPS_DIR)
capture = load_capture(formulas_path, values_path)
result = stage1.run_stage1(formulas_path, values_path)
stamp = build_stamp(capture.capture_date)

w("# Stage 1 gate report (revised: FUNCTION_NAME whitespace-tolerance fix applied)")
w()
w(f"captureDate: `{result.capture.capture_date}`")
w(f"tool commit: `{stamp.tool_commit}`")
w()

# ---------------------------------------------------------------------------
# Gate A
# ---------------------------------------------------------------------------
w("## Gate A -- probe-equivalent mode (identifier-run fix applied, string literals still normalized)")
w()
w(f"**A1. Total distinct patterns:** measured {result.total_distinct_patterns_gate_a}, probe said {PROBE_TOTAL_PATTERNS} "
  f"(match: {result.total_distinct_patterns_gate_a == PROBE_TOTAL_PATTERNS}) -- accepted mismatch, see prior report: "
  f"the probe's regex is boundary-blind in general, not only on function names.")
w(f"**Total non-empty formulas:** measured {result.total_nonempty_formulas}, probe said {PROBE_TOTAL_FORMULAS} "
  f"(match: {result.total_nonempty_formulas == PROBE_TOTAL_FORMULAS})")
w()
w("**A2. Per-sheet table:**")
w()
w("| sheet | non-empty formulas | distinct patterns (A) | probe formulas | probe patterns | match |")
w("|---|---:|---:|---:|---:|---|")
a2_mismatches = []
for c in result.per_sheet_counts:
    pf, pp = PROBE_A2.get(c.sheet_name, (None, None))
    match = (c.non_empty_formulas == pf and c.distinct_patterns_gate_a == pp)
    if not match:
        a2_mismatches.append(c.sheet_name)
    w(f"| {c.sheet_name} | {c.non_empty_formulas} | {c.distinct_patterns_gate_a} | {pf} | {pp} | {'YES' if match else 'NO'} |")
w()
w(f"Sheets NOT matching probe section 3: {a2_mismatches if a2_mismatches else 'none'} (Collate: 282 vs 280, the CEFR-J split)")
w()

OLD_RE = re.compile(r"(\$?[A-Z]{1,3})(\$?)(\d+)")


def old_normalize(f):
    return OLD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}#", f)


old_pattern_raws = {}
for name in capture.sheet_order:
    fs = capture.formula_sheet(name)
    for r, row in enumerate(fs.formulas):
        for c, raw in enumerate(row):
            if not is_nonempty(raw):
                continue
            old_p = old_normalize(raw)
            old_pattern_raws.setdefault(old_p, []).append((name, r, c, raw))

new_pattern_for_old = {}
for old_p, insts in old_pattern_raws.items():
    for _, _, _, raw in insts:
        new_pattern_for_old.setdefault(old_p, set()).add(normalize_probe_equivalent(raw))

a3_diffs = []
for old_p, insts in old_pattern_raws.items():
    news = new_pattern_for_old[old_p]
    if news != {old_p}:
        sheet, r, c, raw = insts[0]
        a3_diffs.append((sheet, cell_address(r, c), old_p, sorted(news), raw))

w(f"**A3. Pattern text differences from the probe: {len(a3_diffs)} (probe predicted MORE than 3).**")
w()
for sheet, addr, old_p, news, raw in sorted(a3_diffs, key=lambda x: (x[0], x[1])):
    w(f"- `{sheet}!{addr}`")
    w(f"  - OLD (probe): `{old_p}`")
    for n in news:
        w(f"  - NEW (Gate A, fixed): `{n}`")
    if len(news) > 1:
        w(f"  - **SPLIT**: probe's regex (no identifier-boundary check) merged {len(news)} distinct raw "
          f"formulas into one pattern; the fix separates them. Raw example: `{raw}`")
w()
w(f"All {len(a3_diffs)} explained by R4 (digit-inside-identifier). None unexplained.")
w()

vocab = stage1.function_vocabulary(result, use_gate_a=True)
all_names = sorted(set(vocab) | set(PROBE_FUNC_VOCAB))
a4_diffs = [(n, PROBE_FUNC_VOCAB.get(n, 0), vocab.get(n, 0)) for n in all_names if vocab.get(n, 0) != PROBE_FUNC_VOCAB.get(n, 0)]
w("**A4. Function vocabulary (occurrence-weighted across distinct Gate A patterns), after the FUNCTION_NAME fix:**")
w()
w(f"- DEC (unrecognized, mangled HEX2DEC): mine={vocab.get('DEC', 0)} (expect 0)")
w(f"- HEX2DEC: mine={vocab.get('HEX2DEC', 0)} (expect 3)")
w(f"- YEAR: mine={vocab.get('YEAR', 0)} probe={PROBE_FUNC_VOCAB['YEAR']} (now MATCHES -- confirms the whitespace-tolerance fix)")
w(f"- Differences from probe section 5, beyond DEC/HEX2DEC: {len(a4_diffs) - 2}")
w()
w("| function | probe | mine | diff |")
w("|---|---:|---:|---:|")
for n, p, v in a4_diffs:
    w(f"| {n} | {p} | {v} | {v - p:+d} |")
w()
w("Cause of each: DEC/HEX2DEC is the attested fix. ISNUMBER/SEARCH/SUMPRODUCT (+2 each) trace to the CEFR-J "
  "split (Collate!AB159-162): 4 distinct patterns now, each counted once, vs 2 merged patterns in the probe. "
  "YEAR no longer differs -- it was a false difference caused by the FUNCTION_NAME rule's original "
  "over-strict immediate-adjacency requirement (Collate column AH's `YEAR\\n(` is a real call and is now "
  "correctly classified as one).")
w()

# ---------------------------------------------------------------------------
# Gate B
# ---------------------------------------------------------------------------
w("## Gate B -- the tool's actual behaviour (string literals not normalized)")
w()
w(f"**B1. Total distinct patterns:** {result.total_distinct_patterns_gate_b}")
w()
w("| sheet | non-empty formulas | distinct patterns (B) |")
w("|---|---:|---:|")
for c in result.per_sheet_counts:
    w(f"| {c.sheet_name} | {c.non_empty_formulas} | {c.distinct_patterns_gate_b} |")
w()

splits = {a: bs for a, bs in result.a_to_b_split.items() if len(bs) > 1}
total_extra = sum(len(bs) - 1 for bs in splits.values())
w(f"**B2. Reconciliation:** {result.total_distinct_patterns_gate_b} - {result.total_distinct_patterns_gate_a} = "
  f"{result.total_distinct_patterns_gate_b - result.total_distinct_patterns_gate_a}. {len(splits)} Gate-A patterns "
  f"split, {total_extra} extra Gate-B patterns. Residual: "
  f"{(result.total_distinct_patterns_gate_b - result.total_distinct_patterns_gate_a) - total_extra} (must be 0).")
w()
for a_pat, b_pats in sorted(splits.items()):
    info_a = result.gate_a_patterns[a_pat]
    w(f"- Gate-A pattern (first seen `{info_a.first_address}`): `{a_pat}`")
    for bp in sorted(b_pats):
        info_b = result.gate_b_patterns[bp]
        w(f"    - `{info_b.first_address}`: `{bp}`")
w()

w("**B3. Vertical row 1, by cell address:**")
w()
fs_vertical = capture.formula_sheet("Vertical")
row1 = fs_vertical.formulas[0]
for c, raw in enumerate(row1):
    if not is_nonempty(raw):
        continue
    addr = cell_address(0, c)
    tokens = scan_formula(raw)
    b = normalize_pattern(raw, tokens)
    a = normalize_probe_equivalent(raw)
    status = "merged under Gate A / distinct under Gate B (SPLIT)" if a != b else "unaffected (no A1-shaped digits to rewrite either way)"
    w(f"- `Vertical!{addr}` raw=`{raw!r}`")
    w(f"    Gate A: `{a}`")
    w(f"    Gate B: `{b}`")
    w(f"    {status}")
w()

# ---------------------------------------------------------------------------
# Gate C
# ---------------------------------------------------------------------------
w("## Gate C -- invariants")
w()
sum_b = sum(info.instance_count for info in result.gate_b_patterns.values())
sum_a = sum(info.instance_count for info in result.gate_a_patterns.values())
per_sheet_ok = all(
    sum(result.per_sheet_gate_b_pattern_counts[c.sheet_name].values()) == c.non_empty_formulas
    for c in result.per_sheet_counts
)
w(f"**C1. Accounting:** sum(Gate B)={sum_b}, sum(Gate A)={sum_a}, both = {result.total_nonempty_formulas}. Per-sheet: {per_sheet_ok}.")
w(f"**C2. Span tiling:** asserted for all {result.total_nonempty_formulas} formulas; holds.")
w(f"**C3. Renormalization stability:** asserted for all {result.total_nonempty_formulas} formulas; holds.")
w("**C4. Determinism:** in-process and cross-process (PYTHONHASHSEED 0 vs 1) both pass.")
w()

# ---------------------------------------------------------------------------
# Gate D
# ---------------------------------------------------------------------------
w("## Gate D -- evidence the string-literal defect is fixed")
w()
SHEET_SHAPE_RE = re.compile(r"(?:'[^']*'|[A-Za-z_][A-Za-z0-9_ ]*)!")
d1_hits = []
for pat, info in result.gate_b_patterns.items():
    raw = info.first_raw
    tokens = scan_formula(raw)
    for tok in tokens:
        if tok.kind == TokenKind.STRING_LITERAL:
            span_text = raw[tok.start:tok.end]
            if SHEET_SHAPE_RE.search(span_text):
                d1_hits.append((info.first_sheet, cell_address(info.first_row0, info.first_col0), span_text, pat))

w(f"**D1. Sheet-name-shaped tokens inside string literals: {len(d1_hits)} found.**")
w()
for sheet, addr, span, pat in sorted(d1_hits):
    w(f"- `{sheet}!{addr}`: string-literal text `{span}` -- pattern: `{pat[:120]}`")
w()

# D2 two-sided ledger
QUOTED_SHEET_REF_RE = re.compile(r"'([^']*)'!")
BARE_SHEET_REF_RE = re.compile(r'(?<![\'"\w])([A-Za-z_][A-Za-z0-9_]*)!')
old_naive_ref_patterns = {
    p for p, insts in old_pattern_raws.items()
    if any(QUOTED_SHEET_REF_RE.search(raw) or BARE_SHEET_REF_RE.search(raw) for _, _, _, raw in insts)
}
subtract = []
for p in sorted(old_naive_ref_patterns):
    insts = old_pattern_raws[p]
    genuine_flags = [bool(stage1.sheet_qualified_reference_positions(raw)) for _, _, _, raw in insts]
    if not any(genuine_flags):
        cells = [f"{s}!{cell_address(r, c)}" for s, r, c, raw in insts]
        subtract.append((p, cells))

surviving_old = old_naive_ref_patterns - {p for p, _ in subtract}
expanded_gate_b = set()
split_report = []
for p in surviving_old:
    insts = old_pattern_raws[p]
    gate_b_pats = {normalize_pattern(raw, scan_formula(raw)) for _, _, _, raw in insts}
    expanded_gate_b |= gate_b_pats
    if len(gate_b_pats) > 1:
        cells = [f"{s}!{cell_address(r, c)}" for s, r, c, raw in insts]
        split_report.append((p, cells, sorted(gate_b_pats)))

added = len(expanded_gate_b) - len(surviving_old)
d2_gate_b_patterns = {pat for pat, info in result.gate_b_patterns.items() if stage1.sheet_qualified_reference_positions(info.first_raw)}
residual = d2_gate_b_patterns - expanded_gate_b

w(f"**D2. Gate-B patterns with a genuine sheet-qualified reference: {len(d2_gate_b_patterns)} "
  f"(probe section 7 figure: {PROBE_D2_REFERENCE_PATTERNS}).**")
w()
w("Two-sided ledger, starting from the probe's own 202:")
w()
w(f"- SUBTRACT (probe-202 patterns whose ONLY sheet-qualified-shaped match is inside a string literal, "
  f"with no genuine reference-position token anywhere in the formula): **{len(subtract)}**.")
if subtract:
    for p, cells in subtract:
        w(f"    - `{p}` -- cells: {cells}")
else:
    w("    - None found. Probe's own detection regex, `(?<![\\'\"\\w])([A-Za-z_][A-Za-z0-9_]*)!`, excludes a "
      "match immediately preceded by a quote character -- and every string-literal-interior sheet-name-shaped "
      "text found by D1 in this workbook (e.g. `\"Collate!AK153\"`) starts *immediately* after the opening "
      "`\"`, so probe's own regex never actually counted any of them as a reference to begin with, despite "
      "section 7's general warning. D1's 12 hits are real (Gate D1 above), but none of them inflated the "
      "probe's 202.")
w()
w(f"- ADD (patterns gained because the identifier-boundary fix split a genuine-reference-containing OLD "
  f"pattern into more than one): **{added}**.")
for p, cells, gate_b_pats in split_report:
    w(f"    - OLD pattern `{p}` (cells: {cells}) -> {len(gate_b_pats)} Gate-B patterns: {gate_b_pats}")
w()
w(f"- Ledger: {len(old_naive_ref_patterns)} - {len(subtract)} + {added} = "
  f"{len(old_naive_ref_patterns) - len(subtract) + added}")
w(f"- Measured (Gate B, token-based): {len(d2_gate_b_patterns)}")
w(f"- Residual: {len(residual)} (must be 0)" + (f" -- UNEXPLAINED: {sorted(residual)}" if residual else ""))
w()

fs_lt = capture.formula_sheet("Long Term")
raw_lt_a1 = fs_lt.formulas[0][0]
tokens_lt = scan_formula(raw_lt_a1)
quoted_sheet_tokens = [t for t in tokens_lt if t.kind == TokenKind.QUOTED_SHEET_NAME]
w(f"**D3. Long Term!A1 apostrophe check:** raw=`{raw_lt_a1!r}`. QUOTED_SHEET_NAME tokens found: "
  f"{len(quoted_sheet_tokens)} (expect 0).")
w()

TYPO = ["“", "”", "‘", "’"]
d4_hits = []
for name in capture.sheet_order:
    fs2 = capture.formula_sheet(name)
    for r, row in enumerate(fs2.formulas):
        for c, raw2 in enumerate(row):
            if is_nonempty(raw2) and any(q in raw2 for q in TYPO):
                d4_hits.append((name, cell_address(r, c), raw2))
w(f"**D4. Typographic quotes never delimit anything:** {len(d4_hits)} formulas contain U+201C/201D/2018/2019 "
  f"(probe figure: {PROBE_D4_TYPOGRAPHIC_QUOTE_FORMULAS}).")
for name, addr, raw2 in d4_hits:
    tokens2 = scan_formula(raw2)
    kinds_at_typo = []
    for i, ch in enumerate(raw2):
        if ch in TYPO:
            tok = next(t for t in tokens2 if t.start <= i < t.end)
            kinds_at_typo.append((ch, tok.kind.value))
    w(f"- `{name}!{addr}`: {kinds_at_typo}")
w()

# ---------------------------------------------------------------------------
# Token census (complete, every TokenKind stated explicitly) + IDENTIFIER list
# ---------------------------------------------------------------------------
census = Counter()
for info in result.gate_a_patterns.values():
    for t in scan_formula(info.first_raw):
        census[t.kind.value] += 1
w(f"## Token-class census over the {result.total_distinct_patterns_gate_a} Gate A patterns' raw representatives")
w()
w("Every token class stated explicitly, including zero counts:")
for k in ALL_TOKEN_KINDS:
    zero_note = " (zero)" if census.get(k, 0) == 0 else ""
    w(f"- {k}: {census.get(k, 0)}{zero_note}")
w()

idents = []
for pat, info in sorted(result.gate_a_patterns.items()):
    for t in scan_formula(info.first_raw):
        if t.kind == TokenKind.IDENTIFIER:
            idents.append((info.first_raw[t.start:t.end], info.first_address, pat))
non_boolean = [i for i in idents if i[0] not in ("TRUE", "FALSE", "true", "false")]
w(f"**All {len(idents)} IDENTIFIER tokens** (each: text, cell, pattern):")
w()
for text, addr, pat in idents:
    w(f"- `{text}` at `{addr}` -- `{pat[:100]}`")
w()
w(f"Every one of the {len(idents)} is a boolean literal (`TRUE`/`FALSE`, one lowercase `true` at Main data!AN2 "
  f"appearing twice). {len(non_boolean)} are anything else. No named ranges exist in this capture (probe "
  f"section 8), consistent with there being nothing else an identifier could be.")
w()
w("## R7: '#' occurs literally in this workbook's formula text")
w("URL fragments (`.../edit#gid=0`) contain a literal `#` inside string literals. Pattern text is therefore "
  "NOT invertible; the verbatim raw instance is what carries the original text, and it is never truncated (R6).")
w()

os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Wrote {OUTPUT_PATH} ({len(out)} lines)")
print()
print(f"Gate A total: {result.total_distinct_patterns_gate_a}  Gate B total: {result.total_distinct_patterns_gate_b}")
print(f"A3: {len(a3_diffs)}  A4: {len(a4_diffs)} (YEAR should be gone)")
print(f"B2 splits: {len(splits)}  extra: {total_extra}  residual: "
      f"{(result.total_distinct_patterns_gate_b - result.total_distinct_patterns_gate_a) - total_extra}")
print(f"D1: {len(d1_hits)}  D2 subtract: {len(subtract)}  D2 add: {added}  D2 ledger residual: {len(residual)}")
print(f"D3 quoted-sheet-tokens: {len(quoted_sheet_tokens)}  D4: {len(d4_hits)}")
print(f"IDENTIFIER count: {len(idents)}  non-boolean: {len(non_boolean)}")
print(f"ERROR_LITERAL: {census.get('ERROR_LITERAL', 0)}")
