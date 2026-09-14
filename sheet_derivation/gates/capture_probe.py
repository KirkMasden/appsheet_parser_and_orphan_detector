#!/usr/bin/env python3
"""Throwaway structural/pattern probe of a captureWorkbook() JSON pair. Read-only.

Invoked as: python -m sheet_derivation.gates.capture_probe [options]

Capture directory and output directory are both arguments; neither is
hard-coded. An explicit --capture-dir/--output-dir always wins; absent
that, both default relative to the workspace root (this repository's own
parent directory), via sheet_derivation/workspace.py -- never from an
absolute path baked into this file and never from the current working
directory.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

from ..workspace import resolve_workspace_root

parser = argparse.ArgumentParser(
    prog="python -m sheet_derivation.gates.capture_probe",
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
    help="Directory to write capture_probe_report.md into. Default: <workspace>/output/gates.",
)
args = parser.parse_args()

_workspace_root = resolve_workspace_root()
DUMPS_DIR = args.capture_dir or os.path.join(_workspace_root, "sheet_dumps")
OUTPUT_DIR = args.output_dir or os.path.join(_workspace_root, "output", "gates")
REPORT_PATH = os.path.join(OUTPUT_DIR, "capture_probe_report.md")

out = []
def w(line=""):
    out.append(line)

# ---------------------------------------------------------------------------
# Load + identify files by inspection, not filename
# ---------------------------------------------------------------------------
json_files = [f for f in os.listdir(DUMPS_DIR) if f.lower().endswith(".json")]
if len(json_files) != 2:
    print(f"FATAL: expected exactly 2 json files, found {len(json_files)}: {json_files}", file=sys.stderr)
    sys.exit(1)

loaded = {}
for fname in json_files:
    path = os.path.join(DUMPS_DIR, fname)
    with open(path, "r", encoding="utf-8") as fh:
        loaded[fname] = json.load(fh)

def sheet_kind(data):
    s = data.get("sheets", [{}])[0] if data.get("sheets") else {}
    keys = set(s.keys())
    if "formulas" in keys:
        return "formulas"
    if "values" in keys:
        return "values"
    return "unknown"

fname_formulas = fname_values = None
for fname, data in loaded.items():
    kind = sheet_kind(data)
    if kind == "formulas":
        fname_formulas = fname
    elif kind == "values":
        fname_values = fname

if not fname_formulas or not fname_values:
    print("FATAL: could not identify formulas/values files by inspection", file=sys.stderr)
    sys.exit(1)

fdata = loaded[fname_formulas]
vdata = loaded[fname_values]
fpath = os.path.join(DUMPS_DIR, fname_formulas)
vpath = os.path.join(DUMPS_DIR, fname_values)
fsize = os.path.getsize(fpath)
vsize = os.path.getsize(vpath)

fsheets = fdata.get("sheets", [])
vsheets = vdata.get("sheets", [])
fnames_order = [s.get("sheetName") for s in fsheets]
vnames_order = [s.get("sheetName") for s in vsheets]
fsheet_by_name = {s.get("sheetName"): s for s in fsheets}
vsheet_by_name = {s.get("sheetName"): s for s in vsheets}
all_sheet_names = fnames_order  # canonical order from formulas file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def col_letter(col0):
    idx = col0 + 1
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def cell_addr(row0, col0):
    return f"{col_letter(col0)}{row0 + 1}"

def trunc(s, n=200):
    s = str(s)
    return s if len(s) <= n else s[:n] + "...[TRUNCATED]"

CELL_REF_RE = re.compile(r'(\$?[A-Z]{1,3})(\$?)(\d+)')
def normalize(formula):
    return CELL_REF_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}#", formula)

FUNC_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.]*)\s*\(')
MANGLED_FUNC_RE = re.compile(r'[A-Z]+#[A-Z]*\(')

QUOTED_SHEET_REF_RE = re.compile(r"'([^']*)'!")
BARE_SHEET_REF_RE = re.compile(r'(?<![\'"\w])([A-Za-z_][A-Za-z0-9_]*)!')

TYPOGRAPHIC_QUOTES = ['“', '”', '‘', '’']

STANDARD_FUNCS = set("""
ABS ACCRINT ACCRINTM ACOS ACOSH ACOT ACOTH ADDRESS AMORLINC AND ARABIC
ARRAY_CONSTRAIN ARRAYFORMULA ASC ASIN ASINH ATAN ATAN2 ATANH AVEDEV AVERAGE
AVERAGEA AVERAGEIF AVERAGEIFS BAHTTEXT BASE BESSELI BESSELJ BESSELK BESSELY
BETADIST BETAINV BIN2DEC BIN2HEX BIN2OCT BINOMDIST BINOM.DIST BINOM.INV BITAND
BITLSHIFT BITOR BITRSHIFT BITXOR BYCOL BYROW CEILING CEILING.MATH CEILING.PRECISE
CELL CHAR CHIDIST CHIINV CHISQ.DIST CHISQ.DIST.RT CHISQ.INV CHISQ.INV.RT CHISQ.TEST
CHITEST CHOOSE CLEAN CODE COLUMN COLUMNS COMBIN COMBINA COMPLEX CONCAT
CONCATENATE CONFIDENCE CONFIDENCE.NORM CONFIDENCE.T CONVERT CORREL COS COSH
COT COTH COUNT COUNTA COUNTBLANK COUNTIF COUNTIFS COUNTUNIQUE COUPDAYBS
COUPDAYS COUPDAYSNC COUPNCD COUPNUM COUPPCD COVAR COVARIANCE.P COVARIANCE.S
CRITBINOM CUMIPMT CUMPRINC DATE DATEDIF DATEVALUE DAVERAGE DAY DAYS DAYS360
DB DBCS DCOUNT DCOUNTA DDB DECIMAL DEGREES DELTA DETECTLANGUAGE DEVSQ DGET
DMAX DMIN DOLLAR DOLLARDE DOLLARFR DPRODUCT DSTDEV DSTDEVP DSUM DURATION
DVAR DVARP EDATE EFFECT ENCODEURL EOMONTH ERF ERF.PRECISE ERFC ERFC.PRECISE
ERROR.TYPE EUROCONVERT EVEN EXACT EXP EXPAND EXPON.DIST EXPONDIST FACT
FACTDOUBLE FALSE F.DIST F.DIST.RT FILTER FIND FINDB F.INV F.INV.RT FISHER
FISHERINV FIXED FLATTEN FLOOR FLOOR.MATH FLOOR.PRECISE FORECAST FORECAST.LINEAR
FORECAST.ETS FORMULATEXT FREQUENCY F.TEST FTEST FV FVSCHEDULE GAMMA GAMMA.DIST
GAMMADIST GAMMA.INV GAMMAINV GAMMALN GAMMALN.PRECISE GAUSS GCD
GETPIVOTDATA GOOGLEFINANCE GOOGLETRANSLATE GROWTH HARMEAN HEX2BIN HEX2DEC HEX2OCT
HLOOKUP HOUR HSTACK HYPERGEOM.DIST HYPERGEOMDIST HYPERLINK IF IFERROR IFNA IFS
IMABS IMAGE IMAGINARY IMARGUMENT IMCONJUGATE IMCOS IMCOSH IMCOT IMCSC IMCSCH
IMDIV IMEXP IMLN IMLOG10 IMLOG2 IMPORTDATA IMPORTFEED IMPORTHTML IMPORTRANGE
IMPORTXML IMPOWER IMPRODUCT IMREAL IMSEC IMSECH IMSIN IMSINH IMSQRT IMSUB IMSUM
IMTAN INDEX INDIRECT INFO INT INTERCEPT INTRATE IPMT IRR ISBLANK ISDATE ISEMAIL
ISERR ISERROR ISEVEN ISFORMULA ISLOGICAL ISNA ISNONTEXT ISNUMBER ISODD
ISOWEEKNUM ISREF ISTEXT ISURL JOIN KURT LAMBDA LARGE LCM LEFT LEFTB LEN LENB
LET LINEST LN LOG LOG10 LOGEST LOGINV LOGNORM.DIST LOGNORM.INV LOGNORMDIST
LOOKUP LOWER MAKEARRAY MAP MATCH MAX MAXA MAXIFS MDETERM MDURATION MEDIAN MID
MIDB MIN MINA MINIFS MINUTE MINVERSE MIRR MMULT MOD MODE MODE.MULT MODE.SNGL
MONTH MROUND MULTINOMIAL MUNIT N NA NEGBINOM.DIST NEGBINOMDIST NETWORKDAYS
NETWORKDAYS.INTL NOMINAL NORM.DIST NORM.INV NORM.S.DIST NORM.S.INV NORMDIST
NORMINV NORMSDIST NORMSINV NOT NOW NPER NPV NUMBERVALUE OCT2BIN OCT2DEC OCT2HEX
ODD ODDFPRICE ODDFYIELD ODDLPRICE ODDLYIELD OFFSET OR OVERWORK PDURATION PEARSON
PERCENTILE PERCENTILE.EXC PERCENTILE.INC PERCENTOF PERCENTRANK PERCENTRANK.EXC
PERCENTRANK.INC PERMUT PERMUTATIONA PHI PHONETIC PI PMT POISSON POISSON.DIST
POWER PPMT PRICE PRICEDISC PRICEMAT PROB PRODUCT PROPER PV QUARTILE
QUARTILE.EXC QUARTILE.INC QUERY QUOTIENT RADIANS RAND RANDARRAY RANDBETWEEN
RANK RANK.AVG RANK.EQ RATE RECEIVED REDUCE REGEXEXTRACT REGEXMATCH REGEXREPLACE
REPLACE REPLACEB REPT RIGHT RIGHTB ROMAN ROUND ROUNDDOWN ROUNDUP ROW ROWS RRI
RSQ RTD SCAN SEARCH SEARCHB SEC SECH SECOND SEQUENCE SERIESSUM SHEETNAME SIGN
SIN SINH SKEW SKEW.P SLN SLOPE SMALL SORT SORTN SPARKLINE SPLIT SQRT SQRTPI
STANDARDIZE STDEV STDEVA STDEV.P STDEV.S STDEVP STDEVPA STOCKHISTORY SUBSTITUTE
SUBTOTAL SUM SUMIF SUMIFS SUMPRODUCT SUMSQ SUMX2MY2 SUMX2PY2 SUMXMY2 SWITCH
SYD T TAN TANH TBILLEQ TBILLPRICE TBILLYIELD T.DIST T.DIST.2T T.DIST.RT TDIST
TEXT TEXTAFTER TEXTBEFORE TEXTJOIN TEXTSPLIT TIME TIMEVALUE T.INV T.INV.2T
TINV TO_DATE TO_DOLLARS TO_PERCENT TO_PURE_NUMBER TO_TEXT TODAY TRANSPOSE
TREND TRIM TRIMMEAN TRIMRANGE TRUE TRUNC T.TEST TTEST TYPE UNICHAR UNICODE
UNIQUE UPPER VALUE VAR VARA VAR.P VAR.S VARP VARPA VDB VLOOKUP VSTACK WEEKDAY
WEEKNUM WEIBULL WEIBULL.DIST WORKDAY WORKDAY.INTL WRAPROWS WRAPCOLS XIRR XLOOKUP
XMATCH XNPV XOR YEAR YEARFRAC YIELD YIELDDISC YIELDMAT ZTEST Z.TEST
""".split())

# ---------------------------------------------------------------------------
# SECTION 1: schema confirmation
# ---------------------------------------------------------------------------
w("# Capture Probe Report")
w("")
w(f"- formulas file: `{fname_formulas}` ({fsize:,} bytes)")
w(f"- values file: `{fname_values}` ({vsize:,} bytes)")
w("")
w("## 1. Schema Confirmation")
w("")
w(f"**Top-level keys, formulas file:** `{sorted(fdata.keys())}`")
w("")
w(f"**Top-level keys, values file:** `{sorted(vdata.keys())}`")
w("")

f_keysets = [frozenset(s.keys()) for s in fsheets]
f_keyset_counts = Counter(f_keysets)
f_common_keyset = f_keyset_counts.most_common(1)[0][0] if f_keyset_counts else frozenset()
w(f"**Per-sheet key set (formulas file), most common:** `{sorted(f_common_keyset)}`")
f_outliers = [(s.get("sheetName"), sorted(frozenset(s.keys()))) for s in fsheets if frozenset(s.keys()) != f_common_keyset]
if f_outliers:
    w("**Sheets with a DIFFERENT key set (formulas file):**")
    for name, ks in f_outliers:
        w(f"- `{name}`: `{ks}`")
else:
    w("All sheets in formulas file share the same key set. No outliers.")
w("")

v_keysets = [frozenset(s.keys()) for s in vsheets]
v_keyset_counts = Counter(v_keysets)
v_common_keyset = v_keyset_counts.most_common(1)[0][0] if v_keyset_counts else frozenset()
w(f"**Per-sheet key set (values file), most common:** `{sorted(v_common_keyset)}`")
v_outliers = [(s.get("sheetName"), sorted(frozenset(s.keys()))) for s in vsheets if frozenset(s.keys()) != v_common_keyset]
if v_outliers:
    w("**Sheets with a DIFFERENT key set (values file):**")
    for name, ks in v_outliers:
        w(f"- `{name}`: `{ks}`")
else:
    w("All sheets in values file share the same key set. No outliers.")
w("")

fcd = fdata.get("captureDate")
vcd = vdata.get("captureDate")
w(f"**captureDate (formulas):** `{fcd}`")
w(f"**captureDate (values):** `{vcd}`")
w(f"**captureDate match:** {'YES' if fcd == vcd else 'NO -- MISMATCH'}")
w("")

same_order = fnames_order == vnames_order
same_set = set(fnames_order) == set(vnames_order)
w(f"**Same 17 sheet names, same order:** {'YES' if same_order else 'NO'}")
if not same_order:
    w(f"  - formulas order: `{fnames_order}`")
    w(f"  - values order: `{vnames_order}`")
    w(f"  - same set regardless of order: {'YES' if same_set else 'NO -- NAME SET DIFFERS'}")
    if not same_set:
        w(f"  - only in formulas: `{set(fnames_order) - set(vnames_order)}`")
        w(f"  - only in values: `{set(vnames_order) - set(fnames_order)}`")
w("")
w(f"**Sheet count:** formulas={len(fsheets)}, values={len(vsheets)}")
w("")

dim_mismatches = []
shape_mismatches = []
for name in all_sheet_names:
    fs = fsheet_by_name.get(name)
    vs = vsheet_by_name.get(name)
    if fs is None:
        dim_mismatches.append(f"{name}: absent from formulas file")
        continue
    decl_rows = fs.get("rowCount")
    decl_cols = fs.get("columnCount")
    formulas_2d = fs.get("formulas", [])
    numfmt_2d = fs.get("numberFormats", [])
    actual_f_rows = len(formulas_2d)
    actual_f_row_lens = set(len(r) for r in formulas_2d)
    actual_nf_rows = len(numfmt_2d)
    actual_nf_row_lens = set(len(r) for r in numfmt_2d)

    if actual_f_rows != decl_rows:
        dim_mismatches.append(f"{name}: formulas row count {actual_f_rows} != declared rowCount {decl_rows}")
    if actual_f_row_lens != {decl_cols}:
        dim_mismatches.append(f"{name}: formulas row lengths {actual_f_row_lens} != declared columnCount {decl_cols}")
    if actual_nf_rows != decl_rows:
        dim_mismatches.append(f"{name}: numberFormats row count {actual_nf_rows} != declared rowCount {decl_rows}")
    if actual_nf_row_lens != {decl_cols}:
        dim_mismatches.append(f"{name}: numberFormats row lengths {actual_nf_row_lens} != declared columnCount {decl_cols}")

    if actual_f_rows != actual_nf_rows or actual_f_row_lens != actual_nf_row_lens:
        shape_mismatches.append(f"{name}: formulas shape ({actual_f_rows} rows, lens {actual_f_row_lens}) != numberFormats shape ({actual_nf_rows} rows, lens {actual_nf_row_lens})")

    if vs is not None:
        values_2d = vs.get("values", [])
        actual_v_rows = len(values_2d)
        actual_v_row_lens = set(len(r) for r in values_2d)
        if actual_v_rows != decl_rows:
            dim_mismatches.append(f"{name}: values row count {actual_v_rows} != formulas-declared rowCount {decl_rows}")
        if actual_v_row_lens != {decl_cols}:
            dim_mismatches.append(f"{name}: values row lengths {actual_v_row_lens} != formulas-declared columnCount {decl_cols}")

w("**rowCount/columnCount vs actual array dimensions:**")
if dim_mismatches:
    w(f"FINDING -- {len(dim_mismatches)} dimension mismatch(es):")
    for m in dim_mismatches:
        w(f"- {m}")
else:
    w("No mismatches. Declared rowCount/columnCount match actual array dimensions for formulas, numberFormats, and values, in every sheet.")
w("")
w("**formulas vs numberFormats shape identity per sheet:**")
if shape_mismatches:
    w(f"FINDING -- {len(shape_mismatches)} shape mismatch(es):")
    for m in shape_mismatches:
        w(f"- {m}")
else:
    w("formulas and numberFormats have identical shape in every sheet.")
w("")

# ---------------------------------------------------------------------------
# Pre-compute per-sheet non-empty formula locations + normalized patterns
# (used by sections 2, 3, 4, 5, 6, 7, 10)
# ---------------------------------------------------------------------------
per_sheet_formula_cells = {}   # name -> list of (row0, col0, raw_formula)
per_sheet_nonascii_functail = defaultdict(list)

for name in all_sheet_names:
    fs = fsheet_by_name[name]
    cells = []
    for r, row in enumerate(fs.get("formulas", [])):
        for c, val in enumerate(row):
            if val is not None and val != "":
                cells.append((r, c, val))
    per_sheet_formula_cells[name] = cells

# global pattern tracking
pattern_count_global = Counter()
pattern_first_loc = {}   # pattern -> (sheet, row0, col0)
per_sheet_pattern_count = {name: Counter() for name in all_sheet_names}
per_sheet_nonempty_count = {}

for name in all_sheet_names:
    cells = per_sheet_formula_cells[name]
    per_sheet_nonempty_count[name] = len(cells)
    for r, c, raw in cells:
        pat = normalize(raw)
        pattern_count_global[pat] += 1
        per_sheet_pattern_count[name][pat] += 1
        if pat not in pattern_first_loc:
            pattern_first_loc[pat] = (name, r, c)

# ---------------------------------------------------------------------------
# SECTION 2: per-sheet size table
# ---------------------------------------------------------------------------
w("## 2. Per-Sheet Size Table")
w("")
w("| sheetName | rowCount | columnCount | total cells | non-empty formulas | fill rate % | non-empty values | frozenRows | frozenColumns |")
w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

tot_cells = tot_formulas = tot_values = 0
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    rc = fs.get("rowCount")
    cc = fs.get("columnCount")
    cells = rc * cc
    nf = per_sheet_nonempty_count[name]
    fill = (nf / cells * 100) if cells else 0.0
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    nv = sum(1 for row in values_2d for val in row if val is not None and val != "")
    fr = fs.get("frozenRows")
    fc = fs.get("frozenColumns")
    w(f"| {name} | {rc} | {cc} | {cells:,} | {nf:,} | {fill:.2f} | {nv:,} | {fr} | {fc} |")
    tot_cells += cells
    tot_formulas += nf
    tot_values += nv

overall_fill = (tot_formulas / tot_cells * 100) if tot_cells else 0.0
w(f"| **TOTAL** | | | **{tot_cells:,}** | **{tot_formulas:,}** | **{overall_fill:.2f}** | **{tot_values:,}** | | |")
w("")

# ---------------------------------------------------------------------------
# SECTION 3: formula pattern counts
# ---------------------------------------------------------------------------
w("## 3. Formula Pattern Counts")
w("")
w("Normalization: every A1-style cell reference `(\\$?[A-Z]{1,3})(\\$?)(\\d+)` has its row number replaced with `#`. Simple regex, not a real parser.")
w("")
w("| sheetName | non-empty formulas | distinct patterns | compression ratio (formulas/patterns) |")
w("|---|---:|---:|---:|")
for name in all_sheet_names:
    nf = per_sheet_nonempty_count[name]
    dp = len(per_sheet_pattern_count[name])
    ratio = (nf / dp) if dp else 0.0
    w(f"| {name} | {nf:,} | {dp:,} | {ratio:.2f} |")
w("")

total_distinct_patterns = len(pattern_count_global)
w(f"**Total distinct patterns, workbook-wide:** {total_distinct_patterns:,}")
w(f"**Total non-empty formulas, workbook-wide:** {tot_formulas:,}")
overall_ratio = (tot_formulas / total_distinct_patterns) if total_distinct_patterns else 0.0
w(f"**Workbook-wide compression ratio:** {overall_ratio:.2f}")
w("")

top15 = pattern_count_global.most_common(15)
w("**15 most frequent patterns:**")
w("")
w("| rank | count | pattern (truncated 200 chars) |")
w("|---:|---:|---|")
for i, (pat, cnt) in enumerate(top15, 1):
    w(f"| {i} | {cnt:,} | `{trunc(pat)}` |")
w("")

singletons = [pat for pat, cnt in pattern_count_global.items() if cnt == 1]
w(f"**Patterns occurring exactly once:** {len(singletons):,}")
w("")
w("**Up to 30 singleton patterns (sheet, cell, pattern truncated 200 chars):**")
w("")
w("| sheet | cell | pattern |")
w("|---|---|---|")
for pat in singletons[:30]:
    sheet, r, c = pattern_first_loc[pat]
    w(f"| {sheet} | {cell_addr(r, c)} | `{trunc(pat)}` |")
w("")

mangled_examples = [pat for pat in pattern_count_global if MANGLED_FUNC_RE.search(pat)]
w(f"**Normalization collision caveat:** function names containing a digit (e.g. LOG10, ATAN2, or a digit in the middle like HEX2DEC) collide with the "
  f"cell-reference regex and get partially mangled (e.g. `HEX2DEC(` -> `HEX#DEC(`), which can split one function name into a mangled prefix plus a "
  f"spurious second identifier that Section 5's function-vocabulary regex WILL pick up as if it were a separate function -- see the `DEC` entry in "
  f"Section 5, which is actually mangled `HEX2DEC`, not a real function named DEC. "
  f"Found {len(mangled_examples):,} distinct pattern(s) containing this collision shape.")
if mangled_examples:
    w("Examples (truncated 200 chars):")
    for pat in mangled_examples[:10]:
        w(f"- `{trunc(pat)}`")
w("")

# ---------------------------------------------------------------------------
# SECTION 4: column uniformity
# ---------------------------------------------------------------------------
w("## 4. Column Uniformity")
w("")

col_summary_counts = Counter()  # 'single-contiguous' | 'single-ragged' | 'multi'
multi_pattern_columns = []

for name in all_sheet_names:
    cells = per_sheet_formula_cells[name]
    by_col = defaultdict(list)  # col0 -> list of (row0, pattern)
    for r, c, raw in cells:
        by_col[c].append((r, normalize(raw)))
    for c, entries in by_col.items():
        rows = sorted(e[0] for e in entries)
        patterns_in_col = set(e[1] for e in entries)
        n_patterns = len(patterns_in_col)
        contiguous = (max(rows) - min(rows) + 1) == len(rows)
        if n_patterns == 1:
            key = "single-contiguous" if contiguous else "single-ragged"
            col_summary_counts[key] += 1
        else:
            col_summary_counts["multi"] += 1
            multi_pattern_columns.append((name, col_letter(c), n_patterns))

w("**Summary:**")
w(f"- single-pattern-contiguous columns: {col_summary_counts['single-contiguous']:,}")
w(f"- single-pattern-ragged columns: {col_summary_counts['single-ragged']:,}")
w(f"- multi-pattern columns: {col_summary_counts['multi']:,}")
w("")
w("**All multi-pattern columns (sheet, column letter, distinct pattern count):**")
w("")
w("| sheet | column | distinct patterns |")
w("|---|---|---:|")
for name, col, n in sorted(multi_pattern_columns, key=lambda x: (-x[2], x[0], x[1])):
    w(f"| {name} | {col} | {n} |")
w("")

# ---------------------------------------------------------------------------
# SECTION 5: function vocabulary
# ---------------------------------------------------------------------------
w("## 5. Function Vocabulary")
w("")
w("Counted across DISTINCT normalized patterns (each pattern counted once regardless of instance count); "
  "all regex matches of an identifier immediately followed by `(` within each distinct pattern's text, upper-cased.")
w("")

func_counter = Counter()
func_pattern_examples = defaultdict(list)  # FUNC -> list of example patterns (up to a handful)
for pat in pattern_count_global:
    for m in FUNC_RE.finditer(pat):
        fn = m.group(1).upper()
        func_counter[fn] += 1
        if len(func_pattern_examples[fn]) < 5:
            func_pattern_examples[fn].append(pat)

w("**Full frequency table (descending):**")
w("")
w("| function | count (distinct patterns containing it, occurrence-weighted) |")
w("|---|---:|")
for fn, cnt in func_counter.most_common():
    w(f"| {fn} | {cnt:,} |")
w("")

callouts = ["IMPORTRANGE", "QUERY", "INDIRECT", "OFFSET", "ARRAYFORMULA", "LAMBDA"]
w("**Named callouts:**")
w("")
for fn in callouts:
    cnt = func_counter.get(fn, 0)
    w(f"### {fn} -- count: {cnt}")
    if cnt:
        for ex in func_pattern_examples[fn]:
            w(f"- `{trunc(ex)}`")
    w("")

unrecognized = sorted(fn for fn in func_counter if fn not in STANDARD_FUNCS)
w(f"**Functions not recognized as standard Google Sheets functions:** {len(unrecognized)}")
w("")
if unrecognized:
    for fn in unrecognized:
        w(f"### {fn} (UNRECOGNIZED) -- count: {func_counter[fn]}")
        for ex in func_pattern_examples[fn]:
            w(f"- `{trunc(ex)}`")
        w("")
else:
    w("None -- every function name found matches the hardcoded standard-function list used by this probe (which is best-effort, not authoritative).")
w("")

# ---------------------------------------------------------------------------
# SECTION 6: IMPORTRANGE inventory
# ---------------------------------------------------------------------------
w("## 6. IMPORTRANGE Inventory")
w("")

def find_calls(text, func_name):
    """Find all top-level calls to func_name( ... ) in raw formula text, returning
    (start_idx, arg_list_str, end_idx) for each, respecting quotes and nested parens."""
    calls = []
    pattern = re.compile(re.escape(func_name) + r'\s*\(', re.IGNORECASE)
    for m in pattern.finditer(text):
        start = m.end()  # index right after '('
        depth = 1
        i = start
        in_quotes = False
        while i < len(text) and depth > 0:
            ch = text[i]
            if in_quotes:
                if ch == '"':
                    if i + 1 < len(text) and text[i + 1] == '"':
                        i += 2
                        continue
                    in_quotes = False
            else:
                if ch == '"':
                    in_quotes = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        calls.append((m.start(), text[start:i], i + 1))
    return calls

def split_top_level(arg_str):
    parts = []
    depth = 0
    in_quotes = False
    cur = []
    i = 0
    while i < len(arg_str):
        ch = arg_str[i]
        if in_quotes:
            cur.append(ch)
            if ch == '"':
                if i + 1 < len(arg_str) and arg_str[i + 1] == '"':
                    cur.append(arg_str[i + 1])
                    i += 2
                    continue
                in_quotes = False
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            cur.append(ch)
        elif ch == '(':
            depth += 1
            cur.append(ch)
        elif ch == ')':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append(''.join(cur))
    return [p.strip() for p in parts]

def is_literal(arg):
    a = arg.strip()
    if len(a) < 2 or a[0] != '"' or a[-1] != '"':
        return False
    inner = a[1:-1]
    # unescape doubled quotes and ensure no stray unescaped quote remains
    return '"' not in inner.replace('""', '')

def unquote(arg):
    a = arg.strip()
    if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
        return a[1:-1].replace('""', '"')
    return a

importrange_calls = defaultdict(lambda: {"count": 0, "locations": [], "arg1_raw": None, "arg2_raw": None})
for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        for start, argstr, end in find_calls(raw, "IMPORTRANGE"):
            parts = split_top_level(argstr)
            arg1 = parts[0] if len(parts) > 0 else ""
            arg2 = parts[1] if len(parts) > 1 else ""
            key = (arg1.strip(), arg2.strip())
            rec = importrange_calls[key]
            rec["count"] += 1
            rec["arg1_raw"] = arg1
            rec["arg2_raw"] = arg2
            if len(rec["locations"]) < 10:
                rec["locations"].append((name, cell_addr(r, c)))

w(f"**Distinct IMPORTRANGE calls found:** {len(importrange_calls)}")
w(f"**Total IMPORTRANGE instances (including duplicates/multiple per cell):** {sum(v['count'] for v in importrange_calls.values())}")
w("")
if not importrange_calls:
    w("No IMPORTRANGE calls found anywhere in the formulas file.")
else:
    for i, (key, rec) in enumerate(sorted(importrange_calls.items(), key=lambda kv: -kv[1]["count"]), 1):
        arg1, arg2 = key
        arg1_kind = "literal" if is_literal(arg1) else "expression (not a literal string)"
        arg2_kind = "literal" if is_literal(arg2) else "expression (not a literal string)"
        w(f"### Call {i} -- instances: {rec['count']}")
        w(f"- arg1 ({arg1_kind}): `{trunc(arg1, 300)}`")
        if arg1_kind == "literal":
            w(f"  - unquoted value: `{trunc(unquote(arg1), 300)}`")
        w(f"- arg2 ({arg2_kind}): `{trunc(arg2, 300)}`")
        if arg2_kind == "literal":
            w(f"  - unquoted value: `{trunc(unquote(arg2), 300)}`")
        locs = ", ".join(f"{s}!{addr}" for s, addr in rec["locations"])
        more = " (+more, truncated at 10 locations shown)" if rec["count"] > len(rec["locations"]) else ""
        w(f"- locations: {locs}{more}")
        w("")

# ---------------------------------------------------------------------------
# SECTION 7: cross-sheet references
# ---------------------------------------------------------------------------
w("## 7. Cross-Sheet References")
w("")
w("Detected via a simple regex over raw (non-normalized) formula text for `TabName!` and `'Tab Name'!` forms. "
  "This can false-positive on text literals inside formulas that happen to contain a `word!` shape -- treat matches inside string literals with suspicion.")
w("")

edge_counts = defaultdict(Counter)  # source_sheet -> Counter(referenced_tab -> distinct pattern count)
patterns_with_xref = set()
referenced_tabs_seen = set()

# work per-sheet over distinct patterns (not instances) to satisfy "count of distinct patterns"
for name in all_sheet_names:
    seen_patterns_for_sheet = set()
    for r, c, raw in per_sheet_formula_cells[name]:
        pat = normalize(raw)
        if pat in seen_patterns_for_sheet:
            continue
        seen_patterns_for_sheet.add(pat)
        refs = set()
        for m in QUOTED_SHEET_REF_RE.finditer(raw):
            refs.add(m.group(1))
        for m in BARE_SHEET_REF_RE.finditer(raw):
            refs.add(m.group(1))
        if refs:
            patterns_with_xref.add(pat)
            for ref in refs:
                referenced_tabs_seen.add(ref)
                edge_counts[name][ref] += 1

w(f"**Distinct patterns containing a reference to another tab:** {len(patterns_with_xref):,}")
w("")
w("**Edge list (source sheet -> referenced tab : distinct-pattern count):**")
w("")
w("| source sheet | referenced tab | distinct pattern count | tab exists in capture? |")
w("|---|---|---:|---|")
for src in all_sheet_names:
    for tab, cnt in edge_counts[src].most_common():
        exists = "yes" if tab in set(all_sheet_names) else "NO -- UNMATCHED"
        w(f"| {src} | {tab} | {cnt} | {exists} |")
w("")

unmatched_tabs = sorted(t for t in referenced_tabs_seen if t not in set(all_sheet_names))
w(f"**Referenced tab names with NO matching sheet in this capture:** {len(unmatched_tabs)}")
if unmatched_tabs:
    for t in unmatched_tabs:
        w(f"- `{t}`")
w("")

# ---------------------------------------------------------------------------
# SECTION 8: non-formula metadata
# ---------------------------------------------------------------------------
w("## 8. Non-Formula Metadata")
w("")
w("| sheetName | namedRanges | dataValidations | conditionalFormatRules | protectedRanges |")
w("|---|---:|---:|---:|---:|")
nonempty_dump = defaultdict(list)  # field -> list of (sheet, entries[:3])
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    lens = {}
    for field in ["namedRanges", "dataValidations", "conditionalFormatRules", "protectedRanges"]:
        val = fs.get(field, [])
        lens[field] = len(val) if isinstance(val, list) else -1
        if isinstance(val, list) and len(val) > 0:
            nonempty_dump[field].append((name, val[:3]))
    w(f"| {name} | {lens['namedRanges']} | {lens['dataValidations']} | {lens['conditionalFormatRules']} | {lens['protectedRanges']} |")
w("")

for field in ["namedRanges", "dataValidations", "conditionalFormatRules", "protectedRanges"]:
    w(f"### First 3 entries of non-empty `{field}` (verbatim, by sheet)")
    w("")
    if not nonempty_dump[field]:
        w(f"No sheet has a non-empty `{field}`.")
    else:
        for name, entries in nonempty_dump[field]:
            w(f"**{name}:**")
            w("```json")
            w(json.dumps(entries, indent=2, ensure_ascii=False))
            w("```")
    w("")

numfmt_counter_global = Counter()
w("**Distinct number-format strings per sheet:**")
w("")
w("| sheetName | distinct number formats |")
w("|---|---:|")
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    nf2d = fs.get("numberFormats", [])
    distinct = set()
    for row in nf2d:
        for val in row:
            distinct.add(val)
            numfmt_counter_global[val] += 1
    w(f"| {name} | {len(distinct)} |")
w("")

w("**10 most common number-format strings, workbook-wide (by cell count):**")
w("")
w("| format string | cell count |")
w("|---|---:|")
for fmt, cnt in numfmt_counter_global.most_common(10):
    w(f"| `{trunc(fmt, 100)}` | {cnt:,} |")
w("")

# ---------------------------------------------------------------------------
# SECTION 9: header rows
# ---------------------------------------------------------------------------
w("## 9. Header Rows")
w("")
for name in all_sheet_names:
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    row1 = values_2d[0] if values_2d else []
    fs = fsheet_by_name[name]
    formulas_2d = fs.get("formulas", [])
    frow1 = formulas_2d[0] if formulas_2d else []
    w(f"### {name}")
    display = [trunc(v, 40) if v not in (None, "") else "" for v in row1]
    w("Row 1 (values, truncated 40 chars/cell): `" + " | ".join(display) + "`")
    nonempty_row1 = [v for v in row1 if v not in (None, "")]
    str_count = sum(1 for v in nonempty_row1 if isinstance(v, str))
    has_formula_row1 = any(v not in (None, "") for v in frow1)
    looks_like_header = (len(nonempty_row1) > 0 and str_count / max(len(nonempty_row1), 1) >= 0.5 and not has_formula_row1)
    dup_check = [v for v in nonempty_row1 if nonempty_row1.count(v) > 1]
    notes = []
    if not looks_like_header:
        notes.append("row 1 does NOT look like a header row (few non-empty strings, or formulas present in row 1) -- header may be row 2+")
    if has_formula_row1:
        notes.append("row 1 contains formulas")
    if dup_check:
        notes.append(f"duplicate non-empty values in row 1: {sorted(set(dup_check))[:10]}")
    if not notes:
        notes.append("row 1 looks like a plausible header row")
    for n in notes:
        w(f"- {n}")
    w("")

# ---------------------------------------------------------------------------
# SECTION 10: text hazards
# ---------------------------------------------------------------------------
w("## 10. Text Hazards")
w("")

typographic_hits = []
long_formulas = []
nonascii_func_hits = []
IDENT_UNICODE_RE = re.compile(r'([^\W\d](?:[^\W]|[.])*)\s*\(', re.UNICODE)

for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        if any(q in raw for q in TYPOGRAPHIC_QUOTES):
            typographic_hits.append((name, cell_addr(r, c), raw))
        if len(raw) > 500:
            long_formulas.append((name, cell_addr(r, c), len(raw)))
        for m in IDENT_UNICODE_RE.finditer(raw):
            token = m.group(1)
            if any(ord(ch) > 127 for ch in token):
                nonascii_func_hits.append((name, cell_addr(r, c), token))

w(f"**Formulas containing typographic quotation marks (U+201C/U+201D/U+2018/U+2019):** {len(typographic_hits)}")
w("")
if typographic_hits:
    w("| sheet | cell | formula (truncated 200) |")
    w("|---|---|---|")
    for name, addr, raw in typographic_hits[:10]:
        w(f"| {name} | {addr} | `{trunc(raw)}` |")
w("")

w(f"**Formulas longer than 500 characters:** {len(long_formulas)}")
w("")
if long_formulas:
    w("Top 5 longest:")
    w("")
    w("| sheet | cell | length |")
    w("|---|---|---:|")
    for name, addr, ln in sorted(long_formulas, key=lambda x: -x[2])[:5]:
        w(f"| {name} | {addr} | {ln:,} |")
w("")

w(f"**Non-ASCII characters appearing in function-name position:** {len(nonascii_func_hits)}")
if nonascii_func_hits:
    w("")
    w("| sheet | cell | token |")
    w("|---|---|---|")
    for name, addr, token in nonascii_func_hits[:20]:
        w(f"| {name} | {addr} | `{token}` |")
w("")

# ---------------------------------------------------------------------------
# SECTION 11: value layer spot check
# ---------------------------------------------------------------------------
w("## 11. Value Layer Spot Check")
w("")

sheet_cell_counts = [(name, fsheet_by_name[name].get("rowCount", 0) * fsheet_by_name[name].get("columnCount", 0)) for name in all_sheet_names]
top3 = [n for n, _ in sorted(sheet_cell_counts, key=lambda x: -x[1])[:3]]
w(f"**3 largest sheets by cell count:** {top3}")
w("")

for name in top3:
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    type_counter = Counter()
    type_examples = defaultdict(list)
    for row in values_2d:
        for val in row:
            tname = type(val).__name__
            type_counter[tname] += 1
            if len(type_examples[tname]) < 5:
                type_examples[tname].append(val)
    w(f"### {name}")
    w("")
    w("| Python type | count | up to 5 examples |")
    w("|---|---:|---|")
    for tname, cnt in type_counter.most_common():
        examples = ", ".join(trunc(repr(e), 60) for e in type_examples[tname])
        w(f"| {tname} | {cnt:,} | {examples} |")
    w("")

# ---------------------------------------------------------------------------
# SECTION 12: allocated versus used
# ---------------------------------------------------------------------------
w("## 12. Allocated Versus Used")
w("")
w("For each sheet: highest row/column (1-indexed; column shown as a letter) holding any non-empty VALUE, "
  "and any non-empty FORMULA, alongside declared rowCount/columnCount.")
w("")
w("| sheetName | rowCount | columnCount | last value row | last value col | last formula row | last formula col |")
w("|---|---:|---:|---:|---|---:|---|")

for name in all_sheet_names:
    fs = fsheet_by_name[name]
    vs = vsheet_by_name.get(name, {})
    rc = fs.get("rowCount")
    cc = fs.get("columnCount")
    values_2d = vs.get("values", [])
    last_v_row = last_v_col = None
    for r, row in enumerate(values_2d):
        for c, val in enumerate(row):
            if val is not None and val != "":
                if last_v_row is None or r > last_v_row:
                    last_v_row = r
                if last_v_col is None or c > last_v_col:
                    last_v_col = c
    cells = per_sheet_formula_cells[name]
    last_f_row = max((r for r, c, raw in cells), default=None)
    last_f_col = max((c for r, c, raw in cells), default=None)
    lv_row_disp = (last_v_row + 1) if last_v_row is not None else "(none)"
    lv_col_disp = col_letter(last_v_col) if last_v_col is not None else "(none)"
    lf_row_disp = (last_f_row + 1) if last_f_row is not None else "(none)"
    lf_col_disp = col_letter(last_f_col) if last_f_col is not None else "(none)"
    w(f"| {name} | {rc} | {cc} | {lv_row_disp} | {lv_col_disp} | {lf_row_disp} | {lf_col_disp} |")
w("")

w("### Vertical: top 5 formula patterns, highest row reached")
w("")
vert_top5 = per_sheet_pattern_count["Vertical"].most_common(5)
vert_pattern_locs = defaultdict(list)  # pattern -> list of (row0, col0)
for r, c, raw in per_sheet_formula_cells["Vertical"]:
    vert_pattern_locs[normalize(raw)].append((r, c))

w("| rank | instance count | highest row reached | column(s) at that row | pattern (truncated 200) |")
w("|---:|---:|---:|---|---|")
for i, (pat, cnt) in enumerate(vert_top5, 1):
    locs = vert_pattern_locs[pat]
    max_r = max(r for r, c in locs)
    cols_at_max = sorted(set(col_letter(c) for r, c in locs if r == max_r))
    w(f"| {i} | {cnt:,} | {max_r + 1} | {', '.join(cols_at_max)} | `{trunc(pat)}` |")
w("")

# ---------------------------------------------------------------------------
# SECTION 13: unexplained values
# ---------------------------------------------------------------------------
w("## 13. Unexplained Values")
w("")
w("A cell is 'unexplained' here if it holds a non-empty VALUE while its FORMULA cell is empty, within a column that is "
  "at least 50% formula-driven (non-empty formula count / rowCount >= 0.5). Reported per sheet+column with up to 20 "
  "example cell addresses. No causal claim is made -- these are just counted.")
w("")

def _unexplained_in_column(name, c, rc):
    fs = fsheet_by_name[name]
    vs = vsheet_by_name.get(name, {})
    formulas_2d = fs.get("formulas", [])
    values_2d = vs.get("values", [])
    count = 0
    examples = []
    for r in range(rc):
        fval = formulas_2d[r][c] if r < len(formulas_2d) else None
        vval = values_2d[r][c] if r < len(values_2d) and c < len(values_2d[r]) else None
        f_empty = (fval is None or fval == "")
        v_nonempty = (vval is not None and vval != "")
        if f_empty and v_nonempty:
            count += 1
            if len(examples) < 20:
                examples.append(cell_addr(r, c))
    return count, examples

unexplained_rows = []
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    rc = fs.get("rowCount")
    if not rc:
        continue
    col_formula_counts = Counter(c for r, c, raw in per_sheet_formula_cells[name])
    qualifying_cols = sorted(c for c, cnt in col_formula_counts.items() if (cnt / rc) >= 0.5)
    for c in qualifying_cols:
        count, examples = _unexplained_in_column(name, c, rc)
        if count > 0:
            unexplained_rows.append((name, col_letter(c), count, examples))

w("**Columns >=50% formula-driven, with unexplained value cells (formula empty, value non-empty):**")
w("")
if unexplained_rows:
    w("| sheet | column | count | example cells (up to 20) |")
    w("|---|---|---:|---|")
    for name, col, count, examples in unexplained_rows:
        w(f"| {name} | {col} | {count:,} | {', '.join(examples)} |")
else:
    w("None found -- every >=50%-formula-driven column has zero value-without-formula cells.")
w("")

w("### Volatile Formulas Report and Downstream Dependency Report (regardless of formula fill rate)")
w("")
for name in ["Volatile Formulas Report", "Downstream Dependency Report"]:
    fs = fsheet_by_name[name]
    cc = fs.get("columnCount")
    rc = fs.get("rowCount")
    w(f"**{name}:**")
    w("")
    w("| column | count | example cells (up to 20) |")
    w("|---|---:|---|")
    any_found = False
    for c in range(cc):
        count, examples = _unexplained_in_column(name, c, rc)
        if count > 0:
            any_found = True
            w(f"| {col_letter(c)} | {count:,} | {', '.join(examples)} |")
    if not any_found:
        w("| (none) | 0 | |")
    w("")

# ---------------------------------------------------------------------------
# SECTION 14: the two report sheets, full dump
# ---------------------------------------------------------------------------
w("## 14. The Two Report Sheets (Full Dump)")
w("")
w("Volatile Formulas Report and Downstream Dependency Report are outputs of a bound Apps Script utility, not spreadsheet "
  "data. Every non-empty value cell is dumped below with its address, to show structure and check for a date/run stamp.")
w("")
for name in ["Volatile Formulas Report", "Downstream Dependency Report"]:
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    nonempty = []
    for r, row in enumerate(values_2d):
        for c, val in enumerate(row):
            if val is not None and val != "":
                nonempty.append((r, c, val))
    w(f"### {name} -- {len(nonempty)} non-empty cell(s)")
    w("")
    w("```")
    for r, c, val in nonempty:
        w(f"{cell_addr(r, c)}: {val!r}")
    w("```")
    w("")

# ---------------------------------------------------------------------------
# SECTION 15: two specific hazards
# ---------------------------------------------------------------------------
w("## 15. Two Specific Hazards")
w("")
w("### 15a. The \"All vertical\" reference")
w("")

ALLV = "All vertical"
allv_hits = []
for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        start = 0
        while True:
            idx = raw.find(ALLV, start)
            if idx == -1:
                break
            allv_hits.append((name, r, c, raw, idx))
            start = idx + 1

w(f"**Occurrences of the literal string \"{ALLV}\" in any formula:** {len(allv_hits)}")
w("")
if not allv_hits:
    w("None found via direct substring search. Section 7's flag of `All vertical` as an unmatched referenced tab came from "
      "the bare-reference regex (`NAME!`), so it is worth re-checking that match manually if this seems inconsistent -- "
      "not re-derived here since this section searches for the literal substring only.")
else:
    for name, r, c, raw, idx in allv_hits:
        before = raw[idx - 1] if idx > 0 else ""
        after = raw[idx + len(ALLV): idx + len(ALLV) + 2]
        quote_count_before = raw[:idx].count('"')
        inside_dquote_heuristic = (quote_count_before % 2 == 1)
        looks_like_ref = (before == "'" and after.startswith("'!"))
        w(f"**{name}!{cell_addr(r, c)}**")
        w("```")
        w(raw)
        w("```")
        if looks_like_ref:
            classification = "REFERENCE POSITION -- appears as `'All vertical'!`, i.e. a quoted sheet-name reference."
        elif inside_dquote_heuristic:
            classification = ("Heuristically INSIDE A DOUBLE-QUOTED STRING LITERAL (an odd number of `\"` characters precede it "
                               "in the formula). This quote-parity heuristic does NOT correctly handle Google Sheets' "
                               "`\"\"`-escaped-quote convention, so treat this as a best guess, not a proven classification.")
        else:
            classification = "AMBIGUOUS -- neither a clean quoted-sheet-reference pattern nor a confident quote-parity string-literal match. Not resolved."
        w(f"- context: character immediately before = `{before!r}`, two characters immediately after = `{after!r}`")
        w(f"- classification: {classification}")
        w("")

w("### 15b. Digit-in-name normalization collision -- blast radius")
w("")

digit_funcs = set()
for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        for m in FUNC_RE.finditer(raw):
            fn = m.group(1).upper()
            if any(ch.isdigit() for ch in fn):
                digit_funcs.add(fn)

w(f"**Distinct function names (raw, unnormalized formula text) containing a digit, found anywhere in the workbook:** {len(digit_funcs)}")
for fn in sorted(digit_funcs):
    w(f"- `{fn}`")
w("")

digit_sheet_names = [name for name in all_sheet_names if any(ch.isdigit() for ch in name)]
w(f"**Sheet names containing a digit:** {digit_sheet_names if digit_sheet_names else '(none)'}")
w("")

for dsn in digit_sheet_names:
    w(f"#### References to `{dsn}`")
    w("")
    bare_re = re.compile(r'(?<![\'"\w])' + re.escape(dsn) + r'!')
    quoted_re = re.compile(r"'" + re.escape(dsn) + r"'!")
    matched_patterns = {}  # normalized pattern -> example raw text
    for name in all_sheet_names:
        for r, c, raw in per_sheet_formula_cells[name]:
            if bare_re.search(raw) or quoted_re.search(raw):
                pat = normalize(raw)
                if pat not in matched_patterns:
                    matched_patterns[pat] = raw
    w(f"Distinct patterns containing a reference qualified by `{dsn}`: {len(matched_patterns)}")
    w("")
    if not matched_patterns:
        w(f"No formula anywhere in the workbook references `{dsn}!` or `'{dsn}'!` -- nothing to show for this sheet name.")
    else:
        for pat, raw in matched_patterns.items():
            w("**raw:**")
            w("```")
            w(raw)
            w("```")
            w("**normalized (current crude normalizer's output):**")
            w("```")
            w(pat)
            w("```")
            w("")
w("")

# ---------------------------------------------------------------------------
# SECTION 16: the Overall sheet in full
# ---------------------------------------------------------------------------
w("## 16. The Overall Sheet In Full")
w("")
_ov_name = "Overall"
_ov_fs = fsheet_by_name[_ov_name]
_ov_vs = vsheet_by_name.get(_ov_name, {})
_ov_rc = _ov_fs.get("rowCount")
_ov_cc = _ov_fs.get("columnCount")
_ov_formulas = _ov_fs.get("formulas", [])
_ov_values = _ov_vs.get("values", [])
w(f"{_ov_name}: {_ov_rc} rows x {_ov_cc} columns = {_ov_rc * _ov_cc} cells. Every cell, row by row, untruncated:")
w("")
w("```")
for r in range(_ov_rc):
    for c in range(_ov_cc):
        fval = _ov_formulas[r][c] if r < len(_ov_formulas) else None
        vval = _ov_values[r][c] if r < len(_ov_values) and c < len(_ov_values[r]) else None
        addr = cell_addr(r, c)
        fdisp = fval if fval not in (None, "") else "(none)"
        vdisp = repr(vval) if vval not in (None, "") else "(none)"
        w(f"{addr}: formula={fdisp} | value={vdisp}")
w("```")
w("")

# ---------------------------------------------------------------------------
# SECTION 17: the 'All vertical' reference -- deep dive
# ---------------------------------------------------------------------------
w("## 17. The 'All vertical' Reference")
w("")

def letter_to_col0(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - ord('A') + 1)
    return n - 1

def compress_ranges(rows_1indexed_sorted):
    if not rows_1indexed_sorted:
        return ""
    ranges = []
    start = prev = rows_1indexed_sorted[0]
    for x in rows_1indexed_sorted[1:]:
        if x == prev + 1:
            prev = x
            continue
        ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = x
    ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(ranges)

def get_formula(name, row0, col0):
    fs = fsheet_by_name[name]
    formulas_2d = fs.get("formulas", [])
    if row0 < len(formulas_2d) and col0 < len(formulas_2d[row0]):
        return formulas_2d[row0][col0]
    return None

def get_value(name, row0, col0):
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    if row0 < len(values_2d) and col0 < len(values_2d[row0]):
        return values_2d[row0][col0]
    return None

def classify_value(val):
    if val is None or val == "":
        return "empty"
    if isinstance(val, str) and val.startswith("#"):
        return "ERROR STRING"
    return "real result"

VERT = "Vertical"
COL_G = letter_to_col0("G")
COL_C = letter_to_col0("C")
COL_F = letter_to_col0("F")

# --- (a) evaluated state ---
w("### 17a. Evaluated State (from the values file)")
w("")
w("| cell | value | classification |")
w("|---|---|---|")
target_rows = [9356, 9992, 9994]
for rn in target_rows:
    row0 = rn - 1
    for col_letter_str, col0 in [("G", COL_G), ("C", COL_C), ("F", COL_F)]:
        val = get_value(VERT, row0, col0)
        w(f"| Vertical!{col_letter_str}{rn} | `{val!r}` | {classify_value(val)} |")
w("")

# --- (b) whole column G ---
w("### 17b. Column G of Vertical, In Full")
w("")
col_g_cells = sorted((r, c, raw) for r, c, raw in per_sheet_formula_cells[VERT] if c == COL_G)
if not col_g_cells:
    w("No formulas found in column G of Vertical.")
else:
    first_row = col_g_cells[0][0] + 1
    last_row = col_g_cells[-1][0] + 1
    w(f"**First formula row:** {first_row}  **Last formula row:** {last_row}  **Total formula cells in column G:** {len(col_g_cells):,}")
    w("")
    pattern_rows = defaultdict(list)
    pattern_example_raw = {}
    for r, c, raw in col_g_cells:
        pat = normalize(raw)
        pattern_rows[pat].append(r + 1)
        if pat not in pattern_example_raw:
            pattern_example_raw[pat] = raw
    w(f"**Distinct patterns in column G:** {len(pattern_rows)}")
    w("")
    for pat, rows in sorted(pattern_rows.items(), key=lambda kv: -len(kv[1])):
        rows_sorted = sorted(rows)
        w(f"**Pattern (instances: {len(rows_sorted):,}):** `{trunc(pat)}`")
        w(f"- row ranges: {compress_ranges(rows_sorted)}")
        w("- raw example:")
        w("```")
        w(pattern_example_raw[pat])
        w("```")
        w("")

# --- (c) immediate neighbours ---
w("### 17c. Immediate Neighbours")
w("")
w("Raw formula and evaluated value for columns C, F, G, rows 9354-9358 and 9990-9996.")
w("")
for block in [range(9354, 9359), range(9990, 9997)]:
    w("| row | C formula | C value | F formula | F value | G formula | G value |")
    w("|---:|---|---|---|---|---|---|")
    for rn in block:
        row0 = rn - 1
        cf = get_formula(VERT, row0, COL_C)
        cv = get_value(VERT, row0, COL_C)
        ff = get_formula(VERT, row0, COL_F)
        fv = get_value(VERT, row0, COL_F)
        gf = get_formula(VERT, row0, COL_G)
        gv = get_value(VERT, row0, COL_G)
        cf_d = cf if cf not in (None, "") else "(none)"
        ff_d = ff if ff not in (None, "") else "(none)"
        gf_d = gf if gf not in (None, "") else "(none)"
        w(f"| {rn} | `{trunc(cf_d, 120)}` | `{cv!r}` | `{trunc(ff_d, 120)}` | `{fv!r}` | `{trunc(gf_d, 120)}` | `{gv!r}` |")
    w("")

# --- (d) search for the literal range text ---
w("### 17d. Search for the Literal Range `AO3:AP14` (any $ combination)")
w("")
RANGE_RE = re.compile(r'\$?AO\$?3:\$?AP\$?14\b')
range_hits = []
for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        if RANGE_RE.search(raw):
            range_hits.append((name, cell_addr(r, c), raw))

w(f"**Hits for the range text `AO3:AP14` (any absolute/relative `$` combination), anywhere in the workbook:** {len(range_hits)}")
w("")
if not range_hits:
    w("None found -- no formula anywhere in the capture contains this exact range text in any $ combination, other than the "
      "three already-known `'All vertical'!AO$3:AP$14` cells (which are included above if matched by this same search).")
else:
    for name, addr, raw in range_hits:
        w(f"**{name}!{addr}**")
        w("```")
        w(raw)
        w("```")
        w("")

# --- (e) where the lookup table actually lives ---
w("### 17e. Where a 12-row, 2-column Table at AO3:AP14 Could Live")
w("")
AO0 = letter_to_col0("AO")
AP0 = letter_to_col0("AP")
wide_enough = [name for name in all_sheet_names if fsheet_by_name[name].get("columnCount", 0) >= (AP0 + 1)]
w(f"**Sheets with at least {AP0 + 1} columns (i.e. wide enough to have a column AP):** {wide_enough if wide_enough else '(none)'}")
w("")
for name in wide_enough:
    w(f"**{name} -- AO3:AP14:**")
    w("```")
    for rn in range(3, 15):
        row0 = rn - 1
        ao_f = get_formula(name, row0, AO0)
        ao_v = get_value(name, row0, AO0)
        ap_f = get_formula(name, row0, AP0)
        ap_v = get_value(name, row0, AP0)
        ao_f_d = ao_f if ao_f not in (None, "") else "(none)"
        ap_f_d = ap_f if ap_f not in (None, "") else "(none)"
        w(f"AO{rn}: formula={ao_f_d} | value={ao_v!r}    AP{rn}: formula={ap_f_d} | value={ap_v!r}")
    w("```")
    w("")

# --- (f) any other dangling sheet names ---
w("### 17f. Every Dangling Sheet-Name Reference in the Workbook")
w("")
w("Every quoted (`'Name'!`) and unquoted (`Name!`) sheet-qualified reference found in any formula, filtered to names that do "
  "NOT match one of the 17 captured sheet names. Classification of reference-vs-string-literal position uses the same "
  "quote-parity heuristic as Section 15a and is not authoritative where flagged ambiguous.")
w("")

known_sheets = set(all_sheet_names)
dangling = defaultdict(lambda: {"count": 0, "examples": []})
for name in all_sheet_names:
    for r, c, raw in per_sheet_formula_cells[name]:
        found_this_cell = {}
        for m in QUOTED_SHEET_REF_RE.finditer(raw):
            rn = m.group(1)
            if rn not in known_sheets and rn not in found_this_cell:
                found_this_cell[rn] = ("quoted", m.start())
        for m in BARE_SHEET_REF_RE.finditer(raw):
            rn = m.group(1)
            if rn not in known_sheets and rn not in found_this_cell:
                found_this_cell[rn] = ("bare", m.start())
        for rn, (kind, s_idx) in found_this_cell.items():
            rec = dangling[rn]
            rec["count"] += 1
            if len(rec["examples"]) < 5:
                quote_count_before = raw[:s_idx].count('"')
                inside_dquote = (quote_count_before % 2 == 1)
                if kind == "quoted":
                    classification = "REFERENCE POSITION (quoted `'Name'!` form)"
                elif inside_dquote:
                    classification = ("AMBIGUOUS -- heuristic (odd `\"` count before match) suggests this sits INSIDE A "
                                       "DOUBLE-QUOTED STRING LITERAL, but the heuristic does not handle Sheets' `\"\"`-escaped-quote "
                                       "convention, so this is not decided")
                else:
                    classification = "REFERENCE POSITION (bare `Name!` form; even quote-count before match suggests outside any string literal)"
                rec["examples"].append((name, cell_addr(r, c), classification))

w(f"**Distinct dangling (unmatched) sheet names referenced:** {len(dangling)}")
w("")
if not dangling:
    w("None -- every sheet-qualified reference found anywhere in the workbook resolves to one of the 17 captured sheets.")
else:
    for rn, rec in sorted(dangling.items(), key=lambda kv: -kv[1]["count"]):
        w(f"#### `{rn}` -- {rec['count']} formula(s) reference it")
        w("")
        for sheet, addr, classification in rec["examples"]:
            w(f"- {sheet}!{addr} -- {classification}")
        w("")

# ---------------------------------------------------------------------------
# SECTION 18: spill columns and value-without-formula cells (no threshold)
# ---------------------------------------------------------------------------
w("## 18. Spill Columns and Value-Without-Formula Cells")
w("")
w("The earlier value-without-formula check (Section 13) only looked at columns >=50% formula-driven, which structurally "
  "excludes any column populated by a single spilling array formula (SORT/TRANSPOSE/ARRAYFORMULA and similar) whose result "
  "fills the column below it with values that carry no formula of their own. This section removes that threshold and looks "
  "at spill columns directly.")
w("")

def build_col_formula_map(name):
    m = defaultdict(list)  # col0 -> list of (row1, raw)
    for r, c, raw in per_sheet_formula_cells[name]:
        m[c].append((r + 1, raw))
    for c in m:
        m[c].sort()
    return m

def build_col_value_rows(name):
    vs = vsheet_by_name.get(name, {})
    values_2d = vs.get("values", [])
    m = defaultdict(list)  # col0 -> list of row1 (sorted by construction)
    for r, row in enumerate(values_2d):
        for c, val in enumerate(row):
            if val is not None and val != "":
                m[c].append(r + 1)
    return m

# --- (a) spill candidates ---
w("### 18a. Spill Candidates")
w("")
w("Every column, any sheet, with formula count <=5 AND non-empty value count >=20. Sorted by value count descending.")
w("")

spill_candidates = []  # (sheet, col0, formula_rows_raw, value_count, last_value_row)
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    cc = fs.get("columnCount", 0)
    col_formulas = build_col_formula_map(name)
    col_values = build_col_value_rows(name)
    for c in range(cc):
        frows = col_formulas.get(c, [])
        vrows = col_values.get(c, [])
        if len(frows) <= 5 and len(vrows) >= 20:
            last_value_row = max(vrows) if vrows else None
            spill_candidates.append((name, c, frows, len(vrows), last_value_row, vrows))

spill_candidates.sort(key=lambda x: -x[3])

w(f"**Spill candidates found:** {len(spill_candidates)}")
w("")
for name, c, frows, vcount, last_value_row, vrows in spill_candidates:
    w(f"#### {name}!{col_letter(c)} -- formula count: {len(frows)}, value count: {vcount:,}, highest value row: {last_value_row}")
    w("")
    if not frows:
        w("No formula cell at all in this column (values present with zero governing formula anywhere in the column).")
    else:
        for row1, raw in frows:
            w(f"- row {row1}:")
            w("```")
            w(raw)
            w("```")
    w("")

# --- (b) spill extent ---
w("### 18b. Spill Extent")
w("")
w("For each candidate: the row ranges (compressed) of non-empty values strictly below the highest formula row in that "
  "column, and whether that run is gap-free.")
w("")
for name, c, frows, vcount, last_value_row, vrows in spill_candidates:
    anchor_row = max(r for r, raw in frows) if frows else 0
    rows_below = sorted(r for r in vrows if r > anchor_row)
    w(f"**{name}!{col_letter(c)}** (formula anchor row: {anchor_row if frows else '(none)'})")
    if not rows_below:
        w("- no non-empty values below the formula row")
    else:
        compressed = compress_ranges(rows_below)
        n_segments = len(compressed.split(", "))
        gap_free = (n_segments == 1)
        w(f"- first row below formula with a value: {rows_below[0]}")
        w(f"- last row with a value: {rows_below[-1]}")
        w(f"- gap-free run: {'YES' if gap_free else 'NO -- ' + str(n_segments) + ' separate segments'}")
        w(f"- row ranges: {compressed}")
    w("")

# --- (c) Vertical column by column ---
w("### 18c. Vertical, Column By Column (A through T)")
w("")
vert_fs = fsheet_by_name["Vertical"]
vert_cc = vert_fs.get("columnCount", 0)
vert_col_formulas = build_col_formula_map("Vertical")
vert_col_values = build_col_value_rows("Vertical")
w("| column | formula count | value count | highest value row | highest formula row | distinct formula patterns |")
w("|---|---:|---:|---:|---:|---:|")
for c in range(vert_cc):
    frows = vert_col_formulas.get(c, [])
    vrows = vert_col_values.get(c, [])
    fcount = len(frows)
    vcount = len(vrows)
    highest_v = max(vrows) if vrows else "(none)"
    highest_f = max(r for r, raw in frows) if frows else "(none)"
    distinct_patterns = len(set(normalize(raw) for r, raw in frows))
    w(f"| {col_letter(c)} | {fcount:,} | {vcount:,} | {highest_v} | {highest_f} | {distinct_patterns} |")
w("")

# --- (d) collision risk ---
w("### 18d. Collision Risk")
w("")
w("For each spill candidate, any OTHER formula cell in that same column below the primary (lowest-row) formula -- these "
  "would block or interrupt the spill if it grew far enough to reach them.")
w("")
any_collision = False
for name, c, frows, vcount, last_value_row, vrows in spill_candidates:
    if len(frows) <= 1:
        continue
    primary_row = min(r for r, raw in frows)
    others = [(r, raw) for r, raw in frows if r > primary_row]
    if not others:
        continue
    any_collision = True
    w(f"**{name}!{col_letter(c)}** -- primary formula at row {primary_row}, current spill reaches row {last_value_row}")
    for r, raw in others:
        gap = r - last_value_row if last_value_row is not None else None
        gap_note = (f"{gap:,} rows of headroom before the spill would reach it" if gap is not None and gap > 0
                    else "ALREADY WITHIN OR AT the current value extent -- overlap, not headroom" if gap is not None
                    else "no current values to compare against")
        w(f"- {name}!{col_letter(c)}{r}: gap = {gap} ({gap_note})")
        w("```")
        w(raw)
        w("```")
    w("")
if not any_collision:
    w("None of the spill candidates identified in 18a have more than one formula cell in their column -- no collision risk "
      "found among them.")
    w("")

# --- (e) value-without-formula, no threshold ---
w("### 18e. Value-Without-Formula, No Threshold")
w("")
w("Every column, every sheet, no fill-rate threshold: cells holding a non-empty value with an empty formula, classified "
  "into row 1 / spill-candidate column / everything else.")
w("")

spill_candidate_cols = set((name, c) for name, c, frows, vcount, last_value_row, vrows in spill_candidates)

w("| sheet | total unexplained | row 1 | spill-candidate column | everything else |")
w("|---|---:|---:|---:|---:|")

other_group_by_sheet_col = defaultdict(list)  # (sheet, col0) -> list of cell addresses (up to 20)
other_count_by_sheet_col = Counter()  # (sheet, col0) -> true total count
sheet_totals = {}
for name in all_sheet_names:
    fs = fsheet_by_name[name]
    vs = vsheet_by_name.get(name, {})
    rc = fs.get("rowCount", 0)
    cc = fs.get("columnCount", 0)
    formulas_2d = fs.get("formulas", [])
    values_2d = vs.get("values", [])
    row1_count = 0
    spill_count = 0
    other_count = 0
    for r in range(rc):
        frow = formulas_2d[r] if r < len(formulas_2d) else []
        vrow = values_2d[r] if r < len(values_2d) else []
        for c in range(cc):
            fval = frow[c] if c < len(frow) else None
            vval = vrow[c] if c < len(vrow) else None
            f_empty = (fval is None or fval == "")
            v_nonempty = (vval is not None and vval != "")
            if f_empty and v_nonempty:
                if r == 0:
                    row1_count += 1
                elif (name, c) in spill_candidate_cols:
                    spill_count += 1
                else:
                    other_count += 1
                    other_count_by_sheet_col[(name, c)] += 1
                    if len(other_group_by_sheet_col[(name, c)]) < 20:
                        other_group_by_sheet_col[(name, c)].append(cell_addr(r, c))
    total = row1_count + spill_count + other_count
    sheet_totals[name] = (total, row1_count, spill_count, other_count)
    w(f"| {name} | {total:,} | {row1_count:,} | {spill_count:,} | {other_count:,} |")
w("")

w("**'Everything else' group -- per sheet and column, up to 20 example cells (cells with no formula-based explanation at all):**")
w("")
if not other_group_by_sheet_col:
    w("None -- every value-without-formula cell in the workbook falls in row 1 or in a spill-candidate column.")
else:
    w("| sheet | column | count | example cells (up to 20) |")
    w("|---|---|---:|---|")
    for (name, c), addrs in sorted(other_group_by_sheet_col.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        true_count = other_count_by_sheet_col[(name, c)]
        w(f"| {name} | {col_letter(c)} | {true_count:,} | {', '.join(addrs)} |")
w("")

# ---------------------------------------------------------------------------
# write report
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(REPORT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print(f"Report written to: {REPORT_PATH}")
print(f"Total sections written. Line count: {len(out)}")
