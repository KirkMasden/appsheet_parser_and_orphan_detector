#!/usr/bin/env python3
"""
AppSheet Unsatisfiable Show_If / Action-Condition Pair Detector

RELEASE_CHECKLIST.md section B, "Unsatisfiable column-Show_If /
attached-action-condition pairs" -- the narrow mechanical half of the
Show_If gap STATUS.md's "Column-level Show_If is never consulted" entry
left open. General Show_If evaluation is an ACCEPTED LIMITATION (decided
2026-09-05) and this module does not attempt it. What it detects instead:
a column's Show_If and the condition of a Display_Inline action attached
to that column that test the SAME variable in OPPOSITE senses, so the
pair is unsatisfiable BY CONSTRUCTION -- the action can never display,
regardless of any live data. Known instance: Kankaku's `Schedule position
label` column against `Group to DW card statistics` / `Group to WD card
statistics`.

WHAT THIS IS NOT: this is not a reachability check. An unsatisfiable pair
here says "this action can never be seen even if every other gate --
navigation, prominence, view type -- lets it through." A view or action
absent from potential_view_orphans.csv / potential_action_orphans.csv can
still be listed here; the two questions are independent.

CANDIDACY, exactly:
  - The action's action_prominence is Display_Inline. attach_to_column
    only gates DISPLAY for this one prominence (action_visibility.py);
    a Do_Not_Display/Prominently/Overlay action's attach_to_column value
    is display-irrelevant vestigial data, confirmed during the section B
    form/map fix's own reconnaissance, and is silently excluded here.
  - attach_to_column names a REAL column on the action's own source_table.
    23 Farmy Display_Inline actions attach to a column that does not
    exist on their table (STATUS.md, "23 Farmy inline actions attach to
    columns that do not exist") -- silently excluded, already recorded,
    not this module's finding to repeat.
  - That column carries a Show_If. appsheet_columns.csv's top-level
    show_if FIELD is empty on every row in all three apps (recorded
    defect, column_parser.py never populates it) -- the real value is
    read from the column's type_qualifier JSON blob, key "Show_If",
    exactly as CLAUDE.md's CSV reference and STATUS.md's census already
    established. Two Kankaku columns have malformed type_qualifier JSON
    (STATUS.md, "Malformed type_qualifier JSON silently drops two Kankaku
    columns") -- json.loads() raises on both; skipped silently, same as
    every other consumer of this field.
  - The action's own only_if_condition is non-empty. An action with no
    condition of its own cannot contradict anything -- it is gated by the
    column alone.

SCOPE, narrow by design -- a row is emitted ONLY on a LITERAL
contradiction over the same variable (X="On" vs X<>"On", or X=a vs X=b
with a != b). Everything else emits NOTHING, silently and by design, not
as a fallback:
  - Arithmetic, COUNT/SUM/SELECT/lookup functions, IN(), CONTAINS(), or
    any construct this module does not explicitly recognize as a blank
    test or an equality/inequality comparison -- left OPAQUE, never
    compared against anything.
  - A condition of `true`/`TRUE` with no variable -- cannot contradict
    anything by construction, never even reaches the comparison step.
  - A pair whose shared variable sits under an OR on either side. OR is
    never decomposed (see point 3 below) -- an OR(...) call is one
    opaque term, and an opaque term is only ever compared for exact
    equality with another opaque term (never fires a contradiction, since
    a whole OR block practically never matches another side's atomic
    comparison verbatim). Several real Farmy pairs (`Open Url
    (Seeds_URL)`, `Seed Info - REVEAL`, `View Ref (Post processing from
    within)`) share a variable with the column's Show_If ONLY inside an
    OR branch and are correctly silent because of this.
  - Two expressions requiring genuine subset/superset reasoning to relate
    (one compound, one compound, no single atomic term in common) --
    never attempted; this module only ever compares ATOMIC terms
    (single blank-tests or single comparisons), one from each side.

THREE SPEC DECISIONS, pinned down here because the checklist's own
examples do not reach them and a second implementer could otherwise
diverge on a future app without changing today's answer on these three:

  1. NEGATION-FORM EQUIVALENCE -- DECIDED: YES. ISBLANK(X), ISNOTBLANK(X),
     and NOT(ISBLANK(X)) are recognized as one two-valued predicate family
     on X (blank / not-blank), not three unrelated forms. NOT(ISNOTBLANK(X))
     is recognized too, for the same reason. The checklist's own examples
     only cover `=`/`<>`; this extends the same "opposite senses on one
     variable" concept to AppSheet's other common way of writing the same
     kind of test. No candidate in any of the three apps needs this
     recognized to reach today's answer (2/0/0) -- it is here so a future
     app's genuine ISBLANK-family contradiction is not silently missed by
     a narrower reading of "literal."

  2. [_THISROW].[X] vs bare [X] -- DECIDED: NORMALIZED to the same
     variable. `[_THISROW].[X]` explicitly names the current row's own
     column value, which is exactly what bare `[X]` already means inside
     a Show_If or only_if_condition (both are evaluated in the context of
     one row). Stripped as a prefix before variable comparison. The third
     app's one candidate (`View Ref (ID TMO)`) touches this exact
     question, harmlessly -- both sides agree in sense either way, so it
     does not change today's answer, but a future app's genuine
     contradiction expressed with one side THISROW-qualified and the
     other bare would otherwise be missed.

  3. AND-decomposition is PERMITTED; OR-decomposition is REFUSED, and
     both directions are stated because the checklist's own wording only
     sharpens the OR half. An expression is recursively unwrapped through
     `AND(...)`/`and(...)` -- including AND nested inside AND -- down to
     its individual comma-separated conjuncts, each tried as its own
     atomic term. This is what lets the known Kankaku pair fire at all:
     the Show_If is `AND(ViewType<>"form", INDEX(Cram[Enum],1)<>"On")`
     and only the SECOND conjunct, taken alone, contradicts the action's
     bare `INDEX(Cram[Enum],1)="On"`. `OR(...)`/`or(...)` is NEVER
     unwrapped, at any depth -- an OR call (or anything else this module
     does not recognize: IF, COUNT, a bare column reference used as a
     truthy check, etc.) is left as ONE opaque term, exactly as it was
     found. This is what keeps the OR-guarded Farmy pairs above silent:
     decomposing into an OR's branches would let one branch's atomic term
     fire against the other side even though the OR's OTHER branch could
     independently satisfy the column, which is exactly the "AND/OR
     combination whose satisfiability depends on other terms" the
     checklist rules out.

  Implementation detail, not a fourth checklist point but disclosed for
  the same reason: variable-text matching is CASE-SENSITIVE and collapses
  only whitespace outside quoted string literals (so `INDEX(Cram[Enum],
  1)` and `INDEX(Cram[Enum],1)` match, but `INDEX(...)` and `index(...)`
  would not). None of the 205 real candidates across the three apps need
  case-insensitive matching to reach today's answer; adding it
  speculatively was rejected rather than silently assumed.

OUT OF SCOPE, considered and deliberately not caught: ACTION-VERSUS-ACTION
complementary conditions. Farmy's `Star this item` and `Star this item -
REMOVE` (both attached to the same column) carry textually opposite
conditions on EACH OTHER (`NOT(CONTAINS([Form Add More], "..."))` vs
`CONTAINS([Form Add More], "...")`), but neither contradicts the shared
column's own Show_If. This is a real pattern -- two sibling actions whose
own conditions are mutually exclusive by design, not a bug -- that this
check will never catch, because this check is column-versus-action only.
Recorded here so it is not mistaken for a gap the next time it is
noticed.

VERIFIED (reconnaissance, then confirmed identically by this
implementation against fresh parses): Kankaku 126 candidates / 2 literal
contradictions (the known pair); Farmy 78 candidates / 0 -- the first
time Farmy's candidates have been hand-checked, not merely counted; third
app 1 candidate / 0.

Usage:
    python unsatisfiable_condition_detector.py "/path/to/parse/directory/"
"""

import csv
import csv_limits  # noqa / intentional: sets csv field size limit on import — do not remove
import sys
import os
import re
import json
from pathlib import Path
from collections import defaultdict


# --- Small self-contained expression utilities -----------------------------
# Mirror the paren/quote-tracking style already used in action_target_parser.py
# (_find_matching_close_paren, _split_top_level_commas) rather than importing
# across modules for two small helpers with no shared state.

def _find_matching_close_paren(text: str, open_pos: int):
    depth = 0
    quote_char = None
    for i in range(open_pos, len(text)):
        char = text[i]
        if quote_char:
            if char == quote_char and (i == 0 or text[i - 1] != '\\'):
                quote_char = None
        elif char in ('"', "'"):
            quote_char = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_top_level_commas(text: str):
    parts = []
    current = []
    depth = 0
    quote_char = None
    for i, char in enumerate(text):
        if quote_char:
            current.append(char)
            if char == quote_char and (i == 0 or text[i - 1] != '\\'):
                quote_char = None
        elif char in ('"', "'"):
            current.append(char)
            quote_char = char
        elif char in '([':
            depth += 1
            current.append(char)
        elif char in ')]':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    parts.append(''.join(current))
    return parts


def _normalize_var_text(raw: str) -> str:
    """Whitespace-collapse (outside quotes only) plus [_THISROW].-stripping --
    spec decision 2. Case-sensitive otherwise (see module docstring)."""
    out = []
    in_quote = None
    for ch in raw:
        if in_quote:
            out.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            out.append(ch)
        elif ch.isspace():
            continue
        else:
            out.append(ch)
    text = ''.join(out)
    text = re.sub(r'^\[_THISROW\]\.', '', text, flags=re.IGNORECASE)
    return text


_BLANK_RE = re.compile(r'^IS(NOT)?BLANK\s*\((?P<inner>.*)\)\s*$', re.IGNORECASE | re.DOTALL)
_RHS_RE = re.compile(r'^(?:"(?:[^"\\]|\\.)*"|TRUE|FALSE|[A-Za-z0-9_.]+)$', re.IGNORECASE)


def _strip_outer_not(term: str):
    """Peel at most one NOT(...) wrapper spanning the WHOLE term.
    Returns (inner, negated)."""
    m = re.match(r'^NOT\(', term, re.IGNORECASE)
    if not m:
        return term, False
    close_pos = _find_matching_close_paren(term, m.end() - 1)
    if close_pos is None or close_pos != len(term) - 1:
        return term, False
    return term[m.end():close_pos], True


def classify_atomic_term(term: str):
    """Classify one already-isolated atomic term (never itself decomposed
    further). Returns a dict {'kind': 'blank'|'cmp', 'var': normalized,
    'raw_var': as-written, 'sense'|'op'/'value': ...} or None if the term
    is opaque (arithmetic, lookup, OR/IF, bare truthy column, or anything
    else not explicitly recognized) -- an opaque term never participates
    in a contradiction."""
    term = term.strip()
    if term.startswith('='):
        term = term[1:].strip()
    if not term:
        return None

    inner, negated = _strip_outer_not(term)
    inner = inner.strip()

    m = _BLANK_RE.match(inner)
    if m:
        var_raw = m.group('inner').strip()
        var = _normalize_var_text(var_raw)
        is_notblank_form = bool(m.group(1))
        sense_notblank = is_notblank_form
        if negated:
            sense_notblank = not sense_notblank
        return {
            'kind': 'blank',
            'var': var,
            'raw_var': var_raw,
            'sense': 'NOTBLANK' if sense_notblank else 'BLANK',
        }

    # Depth-0 scan for a top-level =, <>, or != -- never inside nested
    # parens/brackets/quotes, so a whole OR(...)/COUNT(...)/etc. call
    # never yields a false comparison from something nested inside it.
    depth = 0
    quote_char = None
    op_pos = None
    op_text = None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote_char:
            if ch == quote_char and (i == 0 or inner[i - 1] != '\\'):
                quote_char = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote_char = ch
            i += 1
            continue
        if ch in '([':
            depth += 1
            i += 1
            continue
        if ch in ')]':
            depth -= 1
            i += 1
            continue
        if depth == 0:
            if inner[i:i + 2] == '<>':
                op_pos, op_text = i, '<>'
                break
            if inner[i:i + 2] == '!=':
                op_pos, op_text = i, '!='
                break
            if ch == '=':
                op_pos, op_text = i, '='
                break
        i += 1

    if op_pos is None:
        return None  # opaque: no top-level comparison found

    lhs = inner[:op_pos].strip()
    rhs = inner[op_pos + len(op_text):].strip()
    if not lhs or not _RHS_RE.match(rhs):
        return None  # opaque: RHS isn't a literal this check understands

    # Canonicalize to exactly '=' or '<>' (!= is just <> spelled differently),
    # then apply an enclosing NOT(...), if any, by flipping the sense.
    op = '<>' if op_text in ('<>', '!=') else '='
    if negated:
        op = '=' if op == '<>' else '<>'

    value = rhs
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    else:
        value = value.upper() if value.upper() in ('TRUE', 'FALSE') else value

    return {
        'kind': 'cmp',
        'var': _normalize_var_text(lhs),
        'raw_var': lhs,
        'op': op,
        'value': value,
    }


def _decompose_and(expr: str):
    """Recursively unwrap AND(...)/and(...) -- spec decision 3, the
    permitted half. Returns a list of atomic-term strings (each still to
    be classified by classify_atomic_term); anything that is not itself
    an AND(...) call is returned as one opaque piece, UNCHANGED -- in
    particular OR(...) is never opened."""
    expr = expr.strip()
    if expr.startswith('='):
        expr = expr[1:].strip()
    m = re.match(r'^AND\(', expr, re.IGNORECASE)
    if not m:
        return [expr]
    close_pos = _find_matching_close_paren(expr, m.end() - 1)
    if close_pos is None or close_pos != len(expr) - 1:
        return [expr]
    inner = expr[m.end():close_pos]
    pieces = []
    for part in _split_top_level_commas(inner):
        pieces.extend(_decompose_and(part))
    return pieces


def extract_terms(expr: str):
    """Full pipeline for one expression: AND-decompose, then classify each
    resulting atomic term. Opaque terms are dropped -- they can never
    contradict anything, by design."""
    terms = []
    for piece in _decompose_and(expr):
        classified = classify_atomic_term(piece)
        if classified is not None:
            terms.append(classified)
    return terms


def find_contradiction(show_if_terms, condition_terms):
    """Return a (variable, detail) tuple for the FIRST literal
    contradiction found between the two term lists, or None. A
    contradiction requires the SAME normalized variable and OPPOSITE
    truth requirements -- same variable, same sense is consistent
    (redundant), not contradictory, and is not reported."""
    for a in show_if_terms:
        for b in condition_terms:
            if a['var'] != b['var'] or a['kind'] != b['kind']:
                continue
            if a['kind'] == 'blank':
                if a['sense'] != b['sense']:
                    detail = (f"Show_If requires {a['raw_var']} to be "
                              f"{'not blank' if a['sense'] == 'NOTBLANK' else 'blank'}; "
                              f"action condition requires it to be "
                              f"{'not blank' if b['sense'] == 'NOTBLANK' else 'blank'}")
                    return a['raw_var'], detail
            elif a['kind'] == 'cmp':
                same_value = a['value'] == b['value']
                opposite_op = a['op'] != b['op']
                if same_value and opposite_op:
                    detail = (f"Show_If requires {a['raw_var']} {a['op']} \"{a['value']}\"; "
                              f"action condition requires {b['raw_var']} {b['op']} \"{b['value']}\"")
                    return a['raw_var'], detail
                if (not same_value) and a['op'] == '=' and b['op'] == '=':
                    detail = (f"Show_If requires {a['raw_var']} = \"{a['value']}\"; "
                              f"action condition requires {b['raw_var']} = \"{b['value']}\" "
                              f"(different values, same variable, both required to be =)")
                    return a['raw_var'], detail
    return None


class UnsatisfiableConditionDetector:
    def __init__(self, parse_directory):
        self.parse_dir = Path(parse_directory)
        self.columns = []
        self.actions = []
        self.show_if_by_column = {}  # (table_name, column_name) -> raw Show_If text
        self.malformed_json_count = 0

        self.csv_files = {
            'columns': 'appsheet_columns.csv',
            'actions': 'appsheet_actions.csv',
        }

    def validate_files(self):
        missing_files = []
        for file_type, filename in self.csv_files.items():
            if not (self.parse_dir / filename).exists():
                missing_files.append(filename)
        if missing_files:
            print(f"  ❌ ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"     Expected location: {self.parse_dir}")
            return False
        return True

    def load_columns(self):
        columns_file = self.parse_dir / self.csv_files['columns']
        with open(columns_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.columns.append(row)
                tq = row.get('type_qualifier', '')
                if not tq:
                    continue
                try:
                    obj = json.loads(tq)
                except (json.JSONDecodeError, TypeError):
                    self.malformed_json_count += 1
                    continue
                show_if = obj.get('Show_If')
                if show_if:
                    self.show_if_by_column[(row['table_name'], row['column_name'])] = show_if
        print(f"  ✓ Found {len(self.columns)} columns, {len(self.show_if_by_column)} carrying a Show_If")
        if self.malformed_json_count:
            print(f"  ℹ️  {self.malformed_json_count} column(s) skipped: malformed type_qualifier JSON")

    def load_actions(self):
        actions_file = self.parse_dir / self.csv_files['actions']
        with open(actions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.actions.append(row)
        print(f"  ✓ Found {len(self.actions)} actions")

    def find_candidates(self):
        """Display_Inline actions attached to a real column that carries a
        Show_If, where the action itself also carries a condition. Returns
        the candidate list (for reporting counts) alongside each one's
        extracted Show_If/condition terms."""
        column_names_by_table = defaultdict(set)
        for c in self.columns:
            column_names_by_table[c['table_name']].add(c['column_name'])

        candidates = []
        for a in self.actions:
            if a.get('action_prominence') != 'Display_Inline':
                continue
            attach = (a.get('attach_to_column') or '').strip()
            if not attach:
                continue
            table = a.get('source_table', '')
            if attach not in column_names_by_table.get(table, set()):
                continue
            show_if = self.show_if_by_column.get((table, attach))
            if not show_if:
                continue
            condition = (a.get('only_if_condition') or '').strip()
            if not condition:
                continue
            candidates.append({
                'action_name': a.get('action_name', ''),
                'source_table': table,
                'column_name': attach,
                'show_if': show_if,
                'condition': condition,
            })
        return candidates

    def find_unsatisfiable_pairs(self):
        candidates = self.find_candidates()
        self.candidate_count = len(candidates)
        results = []
        for cand in candidates:
            show_if_terms = extract_terms(cand['show_if'])
            condition_terms = extract_terms(cand['condition'])
            contradiction = find_contradiction(show_if_terms, condition_terms)
            if contradiction is None:
                continue
            variable, detail = contradiction
            results.append({
                'action_name': cand['action_name'],
                'source_table': cand['source_table'],
                'column_name': cand['column_name'],
                'table_name': cand['source_table'],
                'show_if': cand['show_if'],
                'only_if_condition': cand['condition'],
                'contradicting_variable': variable,
                'contradiction_detail': detail,
            })
        return results

    def write_results_to_csv(self, rows):
        """Write nothing at all on a zero result -- the convention every
        sibling detector follows (view/slice/format_rule/action/column
        orphan detectors all guard with `if candidates:` before ever
        opening the file; format_rule_orphan_detector.py is not a special
        case, confirmed by reading all five call sites directly)."""
        output_file = self.parse_dir / 'potential_unsatisfiable_conditions.csv'
        if not rows:
            return None

        fieldnames = ['action_name', 'source_table', 'column_name', 'table_name',
                      'show_if', 'only_if_condition', 'contradicting_variable',
                      'contradiction_detail']
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"    ✓ Results written to: potential_unsatisfiable_conditions.csv")
        return output_file

    def generate_summary_report(self, rows, output_file):
        print(f"\n  📊 Unsatisfiable Condition Detection Summary:")
        print(f"    Candidate column/action pairs checked: {getattr(self, 'candidate_count', 0)}")
        if rows:
            print(f"    ⚠️  Unsatisfiable pairs found: {len(rows)}")
            for row in rows:
                print(f"      • {row['action_name']} (table {row['source_table']}) "
                      f"vs column {row['column_name']}: {row['contradicting_variable']}")
            if output_file:
                print(f"\n  ✅ Results saved to: potential_unsatisfiable_conditions.csv")
        else:
            print(f"    ✅ No unsatisfiable pairs detected")

    def run_analysis(self):
        print("🔍 Starting Unsatisfiable Condition Detection...")
        print(f"  📂 Directory: {self.parse_dir}")

        print("\n  ✔ Validating required files...")
        if not self.validate_files():
            return None

        print("\n  📊 Extracting columns and actions...")
        self.load_columns()
        self.load_actions()

        print("\n  🔍 Searching for unsatisfiable column/action pairs...")
        rows = self.find_unsatisfiable_pairs()

        output_file = None
        if rows:
            print("\n  💾 Writing results...")
            output_file = self.write_results_to_csv(rows)

        self.generate_summary_report(rows, output_file)
        return rows


def main():
    if len(sys.argv) != 2:
        print("Usage: python unsatisfiable_condition_detector.py '/path/to/parse/directory/'")
        sys.exit(1)

    parse_directory = sys.argv[1]
    if not os.path.exists(parse_directory):
        print(f"ERROR: Directory does not exist: {parse_directory}")
        sys.exit(1)

    detector = UnsatisfiableConditionDetector(parse_directory)
    rows = detector.run_analysis()

    if rows is not None:
        print(f"\nUnsatisfiable condition detection completed successfully!")
        if rows:
            print(f"Found {len(rows)} unsatisfiable pair(s).")
        else:
            print("No unsatisfiable pairs detected.")


if __name__ == "__main__":
    main()
