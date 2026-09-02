# Consolidation plan: one shared "is this action visible here" implementation

This is a plan, not a change. Nothing in the repository is modified by this document.
Every claim below is sourced to a specific file, line, or a command run against the
reference parse output at `20260830_linktoform_verify/20260830_212632_AppsheetFarmyApp_for_Kirk_parse`
(the most recent full re-parse). Where I could not establish something from the code
or the data, I say so rather than guessing.

**Out of scope, and why:** `navigation_edge_generator.py`'s `check_context_conditions`
(lines 320–378) is a fourth, single, already-unified mechanism — it resolves the
`must_be_viewtype` / `must_be_in_views` / `must_be_table` conditions derived from an
action's `only_if_condition`, which is a completely orthogonal question ("is this view
permitted by the condition") from the one this plan addresses ("is this prominence
displayable in this view type at all"). It is not duplicated anywhere and this plan
does not touch it.

## 1. Are the three call sites asking the same question?

No — two of the three ask the same pointwise question with the same shape, but the
third asks an existential question over all views. This matters for the shared-module
design in section 4.

### `navigation_edge_generator.py` — two call sites, both pointwise, both mutate shared state

- **`process_regular_action`, line 524**: `if not self.is_action_visible_in_view(target_row, view): return`.
  Input: one `target_row` dict from `action_targets.csv` (via `self.targets_by_action`,
  keyed by `source_action`) and one `view` dict from `appsheet_views.csv`. Return:
  `bool`. Caller's use: gates whether an edge is appended to `self.edges` — a `False`
  here means **no row is ever written to `navigation_edges.csv`** for this
  (action, view) pair.
- **`process_view`, line 853**: `if not self.is_action_visible_in_view(target_row, view): continue`,
  called only when `target_row.get('action_type') == 'execute_group'`. Same input/return
  shape. Caller's use: gates whether `process_group_action` is invoked at all for this
  group, on this view — i.e., whether the *group's own button* is considered visible
  before its children are expanded.
- Both call sites, and the three per-type helpers they dispatch to
  (`is_action_visible_in_detail_view`, `is_action_visible_in_deck_view`,
  `is_action_visible_in_table_view`), increment `self.stats['edges_blocked_by_visibility']`
  (8 increment sites total; corrected from 9 by step 3's grep — see block A0) —
  a side effect on the instance, not a pure function.

**A finding not named in the background, worth stating plainly: inside the same file,
a third, undocumented behavior exists.** `process_group_action` (lines 428–516), which
runs once the group's own gate above has passed, creates one edge per child action
(lines 484–515) **without ever calling `is_action_visible_in_view` on the child**. The
only gate a child action passes through is `check_context_conditions` (line 481, the
out-of-scope mechanism above). This means prominence-vs-view-type compatibility is
never checked for any action reached through a group — which is exactly the mechanism
that let the four `Do_Not_Display` actions confirmed reachable through group
membership (STATUS.md, `f4d931a` entry) produce edges at all. **This is a hard
constraint on any consolidation**: if the shared function were also applied inside
`process_group_action`'s child loop, it would newly block some of those already-verified,
correct group-membership edges — a regression, not a fix. Section 4 returns to this.

### `actions_orphan_detector.py` — existential, no view parameter, one call site

`is_action_visible_in_views` (lines 201–277). Input: one `action` dict only — **there
is no `view` parameter**; the function loops over `self.views` internally (line 214)
and returns `True` at the first view where the action would display, `False` if none
match after the full loop. Return: `bool`. Called once, in `find_orphan_candidates`
(line 459): `is_visible_in_views = self.is_action_visible_in_views(action)`, combined
at line 462 as `if not has_reachable_reference and not is_event_action and not
is_visible_in_views:` — a `True` here is one of three independent reasons an action is
*excluded* from `potential_action_orphans.csv`.

This is the "could this action ever display anywhere" question, not "does it display
in this view" — a genuinely different question from the other two, exactly the case
the task background asked me to watch for. It cannot be a thin wrapper that just calls
a shared pointwise function once; it has to iterate every view and OR the results
together, which is a legitimate second function built *on top of* the shared pointwise
one, not a reason to avoid sharing the pointwise logic. It also carries additional
plumbing the other two don't: a literal `only_if_condition == 'false'` short-circuit
(line 211–212, the *only* place any of the three functions look at the condition
field at all, and only for that one literal string — not for `CONTEXT(...)`
expressions), a `source_table` vs. view `source_table`/`data_source` match (lines
231–235, added `# NEW`, not present in the other two files), and a lazily-built
`self.columns_checked` cache via `column_exists` (lines 279–293) used only for the
`Display Inline` case, to confirm the attached column actually exists in
`appsheet_columns.csv` — a check neither of the other two files performs.

### `action_dependency_analyzer.py` — pointwise, one call site, interactive only

`is_action_visible_in_view` (lines 654–693). Input: one `action` dict and one `view`
dict — same shape as `navigation_edge_generator.py`'s function. Return: `bool`. Called
once, in `analyze_view_dependencies` (line 598), itself called only from the
interactive dependency browser. **Confirmed by grep**: `ActionDependencyAnalyzer` is
instantiated only in `dependency_analyzer_hub.py` line 58, which in turn is reached
only through the optional "Would you like to explore dependencies now? (y/n)" prompt
at the end of `master_parser_and_orphan_detector.py`, or by running the hub directly.
**No CSV output depends on this function.** Its caller appends the string
`'Displayed action'` to a per-view list shown to a human browsing one action's
dependencies (line 599) — a report label, not a filter that removes or keeps
anything. This is the lowest-risk of the three to touch, because nothing downstream
consumes its answer programmatically.

### Summary answer to question 1

Two shared functions, not one: a **pointwise** `is_visible(action, view) -> bool`
(replacing the logic in `navigation_edge_generator.py` and
`action_dependency_analyzer.py`, and forming the inner loop body of the third), and an
**existential** `is_visible_anywhere(action, views) -> bool` built on top of it
(replacing `actions_orphan_detector.py`'s function, plus its `only_if == 'false'`
short-circuit, its table-match check, and its `column_exists` check, none of which
belong in the pointwise function since the other two callers don't want them applied
silently).

## 2. Where do the three disagree, cell by cell?

Audited read-only against the working tree on 2026-08-31: `navigation_edge_generator.py`
(NEG), `actions_orphan_detector.py` (AOD), `action_dependency_analyzer.py` (ADA). Every
verdict below was derived from the code as it currently stands, not from the previous
version of this section, several of whose claims were wrong.

### Changes from the previous version of this section

Recorded so a reader who remembers the old table knows what moved and why, rather than
assuming the differences are typos.

- **Five prominence columns are now four.** `Primary` is not an export value and cannot
  occur in the data. It appears here only as a footnote about dead code.
- **The 120-view "other" bucket is decomposed.** It could not take a single verdict: on
  form views NEG is wrong and the other two right; on card views the reverse. No default
  is correct for both.
- **The fourth column carries evidence grades.** `APPSHEET_BEHAVIOR.md` now distinguishes
  observed, documented and inferred, and the old binary UNRESOLVED flattened them.
- **Table+Overlay is no longer a three-way split.** Commit `e0530c8` moved NEG and AOD to
  True. What remains is ADA alone, already recorded as a known defect.
- **Deck+Overlay is a new finding: all three files are wrong.** Established after the
  previous version was written.
- **Deck+Prominent is no longer "F, observed directly."** The observation once cited for
  it has been withdrawn in `APPSHEET_BEHAVIOR.md` as non-isolating.

### Prominence values

The export contains exactly four `action_prominence` strings — `Do_Not_Display`,
`Display_Inline`, `Display_Prominently`, `Display_Overlay` — verified by count against
Leon's app (970 actions). The editor's Position names map onto these per the table in
`APPSHEET_BEHAVIOR.md`; only the Primary/`Display_Overlay` pair is confirmed by direct
evidence, the other three being literal-looking but unverified.

The literal string `'Primary'` occurs zero times in the data. It survives in one place in
the code: `is_action_visible_in_detail_view`'s allow-list, line 239. Commit `e0530c8`
deleted the other occurrence, in `is_action_visible_in_table_view`, but not this one. It
is dead code and is deliberately not given rows in the tables below. Step 1 will preserve
it; that is correct behavior-preservation and should not be mistaken for a rule.

### Pre-gates, applied before any view-type branch

Stated once here rather than repeated into every cell.

- **NEG** — `Do_Not_Display` is rejected unless the action is in *this* view's
  `onclick_actions`; if it is, it proceeds and is judged by the view-type branch like any
  other prominence. Every view type additionally requires membership in
  `available_actions`, compared case-sensitively.
- **AOD** — `only_if_condition == 'false'` returns False outright, the only place any of
  the three reads that field. Then, per view: skip unused system views, skip views with
  `show_if == 'false'`, require `available_actions` membership (case-insensitive), and
  require the action's `source_table` to equal the view's source when both are non-empty.
- **ADA** — `show_if == 'false'` returns False. The `available_actions` gate is **in the
  caller** (line 597), not in the function — so an extraction that pulls the pre-gate into
  the shared function changes ADA's function boundary even if it changes no verdict.

### Legend

**T** / **F** = returns or contributes that value. "list-gated" = outcome turns on
`referenced_actions` membership, not prominence. "bar + mode gated" = requires
`show_action_bar` true, then Manual mode requires `referenced_actions` membership while
Automatic mode returns True unconditionally. Behavior grades: **[observed]** in a running
app, **[documented]** from Google's pages, **[inferred]** reasoned but untested,
**[none]** no rule established.

---

### Detail views

| Prominence | NEG | AOD | ADA | AppSheet behavior |
|---|---|---|---|---|
| `Do_Not_Display` | **F** — reaches the branch when onclick-bound, then fails the allow-list | **F** | **F** | **F** [documented] |
| `Display_Inline` | **T** if `attach_to_column` is empty; else T only if it is in `view_columns` | T only if attach is non-empty, in `view_columns`, **and** exists in `appsheet_columns.csv` | T only if attach is non-empty and exactly in `view_columns` | **T** [documented] — requires a view that renders columns |
| `Display_Prominently` | **T** | **T** | **T** | **T** [documented] — the only view type the docs name for this position |
| `Display_Overlay` | **T** | **T** | **T** | **T** [documented] — collection and detail panels both carry primary actions |

The Inline row is a genuine three-way disagreement, not a phrasing difference: NEG returns
**True** for an Inline action with no attached column; AOD and ADA return False.

### Table views

| Prominence | NEG | AOD | ADA | AppSheet behavior |
|---|---|---|---|---|
| `Do_Not_Display` | **F** — explicit check, overriding the onclick exception | **F** | **F** | **F** [documented] |
| `Display_Inline` | T only if attach is non-empty and in `view_columns` | T only if attach is non-empty, in `view_columns`, and the column exists | T only if attach is non-empty and exactly in `view_columns` | **T with a caveat** [documented] — the action *replaces* the column content rather than sitting beside it; none of the three model this |
| `Display_Prominently` | **F** — explicit `else`, comment says unsupported | **F** — no branch | **F** — no branch | **Not established** [documented, weak] — docs name only detail for Prominent. All three agree on F, but on documentation, not observation |
| `Display_Overlay` | **T** | **T** | **F** — no branch, falls to `return False` | **T — observed**, Leon's app, 2026-08-31, purpose-built External action |

`e0530c8` moved two of the three to T. What remains is a two-against-one split where the
odd file out is ADA, already recorded as a known defect and listed in checklist section B.
Calling Table+Overlay "the most divergent cell in the table" is no longer true; that
description now fits Deck+`Do_Not_Display`.

Note also the within-NEG asymmetry: Inline with an empty `attach_to_column` is True on
detail and False on table, in the same file, from the same input.

### Deck views

NEG does not read prominence in this branch at all. Its rule is membership in
`referenced_actions` and absence from `event_actions`. It never reads `show_action_bar`
or `action_display_mode`.

| Prominence | NEG | AOD | ADA | AppSheet behavior |
|---|---|---|---|---|
| `Do_Not_Display` | T only if onclick-bound **and** in `referenced_actions` **and** not an event action | **T** — the case bug never excludes it | **T** — same bug | **F** [documented], universal |
| `Display_Inline` | list-gated | bar + mode gated | bar + mode gated | **[none]** |
| `Display_Prominently` | list-gated — T if listed | bar + mode gated | bar + mode gated | **T** [observed] — see `APPSHEET_BEHAVIOR.md` |
| `Display_Overlay` | list-gated — **wrong** | bar + mode gated — **wrong** | bar + mode gated — **wrong** | **T** [observed], independent of the action bar |

**Deck+Overlay is the cell where all three files are wrong, and it is the newest finding
in this section.** The deck's action bar is a per-row strip of buttons, enabled by
`Show action bar` and populated by the `Actions` setting; a Primary action is a view-level
floating button. They are different UI elements, and every one of the three files gates
the second on the first. Observed 2026-08-31 in Leon's app: a floating overlay button
displaying over the rows of the `Beds Deck` view in the editor preview. Corroborated by
documentation, which places primary actions in the panel for collection views — card,
deck, gallery and table by name — and describes them under floating navigation buttons
with no view type attached.

Consequence for AOD and ADA specifically: their `show_action_bar` requirement means a
Primary action on a deck with the action bar switched off is invisible to them, blocked by
a setting that governs a different element. Leon's app contains one such deck.

**Deck+Prominent now has observational support, pointing the opposite way from the
documentation.** The previous version of this section, and of section 5's original
step 5, called Deck+Prominent the best-evidenced rule in the plan, citing a direct
2026-08-30 observation; `APPSHEET_BEHAVIOR.md` withdrew that observation the same
day the plan moved past it — the deck used was in Manual mode with the action absent
from its list, so the manual-list rule accounted for the non-display by itself and
the case isolated nothing. Section 5's step 5 was then implemented on documentation
alone (Google's Position page naming only Detail), verified by full re-parse against
both apps, and reverted, 2026-09-02, without being committed — a new, isolating
observation disproved it before it shipped. Kankaku's `W to D` deck
(`show_action_bar` `True`, `action_display_mode` `Manual`) lists three
`Display_Prominently` actions in its own `view_configuration`'s `ActionBarEntries`,
and Kirk confirmed two of them (thumbs-up, right-arrow) rendering on deck rows in the
app editor's preview. See `APPSHEET_BEHAVIOR.md`'s "Established behavior" entry for
the full evidence and the explicit limit of what it does and does not establish —
Manual-list membership only; Automatic mode remains untested.

All three files' cells for this row were already correct under these exact
conditions (bar on, Manual mode, action listed): NEG's list-gated rule returns True
because the action is on the list; AOD's and ADA's bar + mode gated rule returns True
because the bar is on, mode is Manual, and the action is in `referenced_actions`. No
code change follows from this finding — it corrects the documentation's account of
AppSheet's own behavior, not any of the three files' existing logic.

### Gallery views

| Prominence | NEG | AOD | ADA | AppSheet behavior |
|---|---|---|---|---|
| `Do_Not_Display` | T if onclick-bound, via the unconditional-True branch | **T** — case bug | **T** — case bug | **F** [documented] |
| `Display_Inline` | **T, unconditional** — no branch exists | bar + mode gated | bar + mode gated | **[none]** |
| `Display_Prominently` | **T, unconditional** | bar + mode gated | bar + mode gated | **Not established** [documented, weak] |
| `Display_Overlay` | **T**, but by the unconditional `else`, not by a rule | bar + mode gated — **wrong** | bar + mode gated — **wrong** | **T** [documented] — same collection class as deck; not observed on gallery specifically |

Step 4's premise is now stronger than the plan states: gallery being a sibling of deck and
table is supported by documentation, not only by two files agreeing. But step 4 as
originally written would introduce a defect — making gallery list-gated like deck is right
for the bar-gated prominences and wrong for `Display_Overlay`, which should not be
list-gated on either view type. NEG currently gets Gallery+Overlay right for the wrong
reason, and step 4 would break it.

### The former "other" bucket, decomposed

All three files behave identically across every prominence for every type below. **NEG
returns T unconditionally** via `else: return True`; **AOD contributes F** because no
branch matches and the loop continues; **ADA returns F** at the final statement. Only the
platform's actual behavior differs, so this is one row per view type.

| View type | Views | AppSheet behavior | Which files are wrong |
|---|---|---|---|
| `form` | 92 | **F** — documented. Actions don't display as buttons on forms | NEG |
| `card` | 17 | **Displays actions** — documented; `Display_Overlay` **T** [documented] as a collection view. Which other positions apply is unstated | AOD, ADA |
| `map` | 7 | **[inferred]** (Kirk, 2026-08-31) — needs designation, analogous to a deck action bar. Not tested | NEG, probably; but the rule is a designation gate, not a flat F, so AOD and ADA are not right either |
| `dashboard` | 3 | **[none]** | undetermined |
| `calendar` | 1 | **[none]** | undetermined |

Two notes for whoever implements this bucket.

A restrictive default for `form` is **safe with respect to event routes**. In NEG the Form
Saved path is served by `process_event_actions`, which never calls
`is_action_visible_in_view` — the visibility function's only call sites are lines 524 and
853. Making form return False removes prominence-based display without touching the event
binding that `APPSHEET_BEHAVIOR.md` identifies as the real navigation route out of a form.
The same holds for `dashboard`: containment edges come from
`process_dashboard_containment`, also independent of this function.

The `map` cell cannot be filled by a boolean at all if Kirk's inference is right. "Needs
designation" is deck's mechanism, and deck's mechanism is not a prominence rule — which
means the honest table has a cell type this legend does not provide.

---

### Disagreements that are not cells

**Case sensitivity of action-name comparisons.** AOD lowercases both sides for
`available_actions` and `referenced_actions`. NEG and ADA compare case-sensitively.
`748e329` already fixed this class of bug once, for view types in
`check_context_conditions`; the same class is still live for action names in two of three
files. Not in the previous version of this section.

**Event actions.** NEG's deck branch excludes an action that is in `referenced_actions` if
it is also in `event_actions`, on the stated grounds that events are handled elsewhere.
AOD and ADA apply no such exclusion. So an action that is both an event action and on a
deck's manual list gets three different treatments, and a naive unification would have to
pick one.

**Automatic-mode completeness, unresolved and independent of prominence.**
`views_parser.py` populates `referenced_actions` from `ActionColumns` plus
`ActionBarEntries` plus non-auto `Events`. In Automatic mode `ActionBarEntries` is absent
or empty, so `referenced_actions` may be legitimately incomplete relative to what
AppSheet's automatic ordering displays. NEG requires membership unconditionally and so may
**under-count**; AOD and ADA return True unconditionally in Automatic mode and so may
**over-count**. Which is closer to correct is not established anywhere.

**`show_action_bar` is read by two files and not the third.** Folded into "list-gated" in
the previous version, which made NEG and the other two look closer than they are.

---

### What this section does not establish

- The view-type counts (92 form, 17 card, 7 map, 3 dashboard, 1 calendar, of 319) are
  carried over from the previous version, which computed them against a superseded parse.
  There is no reason to think they moved — `e0530c8` left every parser output file
  byte-identical, and `appsheet_views.csv` is a parser output — but they are the only
  figures here not derived from the code, and should be recounted with a real CSV parser
  rather than trusted.
- That exactly four prominence values exist was verified against Leon's app when this
  section was written. The 2026-08-31 baseline parse of Kirk's own app (Kankaku) has since
  confirmed the same four and no others in a second app.
- Three of the four editor-to-export prominence mappings are unverified. They are
  literal-looking, and nothing in this section depends on them, but the fourth column is
  stated in editor vocabulary and reaches the code through that mapping.
- The blast radius of the `Do_Not_Display` case bug — how many of the 414 such actions it
  actually changes an answer for — is unmeasured. The mechanism is confirmed; the count is
  a verification step, not a finding.
- Deck+Overlay is observed with the action bar's state unrecorded, and the button seen was
  most likely a system-generated Add action rather than an author-created one. Neither
  weakens the conclusion much, but the entry says what was seen rather than what it
  implies.

### Sources for the behavior column

- Actions: The Essentials — https://support.google.com/appsheet/answer/10107706
- Deck and table view types — https://support.google.com/appsheet/answer/10106514
- Explore the desktop design — https://support.google.com/appsheet/answer/12407883
- About the new mobile framework — https://support.google.com/appsheet/answer/15831909
- Card view type — https://support.google.com/appsheet/answer/11908538
- Map view type — https://support.google.com/appsheet/answer/10106601

The third and fourth are new to this project and are what settled Deck+Overlay. The fourth
is also the correct source for the six-on-new-framework and four-on-legacy limits on
primary actions.

## 3. What data does each implementation read? Is the prominence-string mismatch real?

Confirmed against the reference output's `appsheet_actions.csv` (414 + 303 + 160 + 93
rows respectively; `Primary` occurs 0 times):

```
'Do_Not_Display'      414
'Display_Inline'      303
'Display_Prominently'  160
'Display_Overlay'      93
```

**The CSVs contain the underscored spelling.** `navigation_edge_generator.py` compares
against underscored strings directly (`'Display_Prominently'`, etc. — e.g. line 239)
and needs no normalization; it is reading the real data correctly.
`actions_orphan_detector.py` (line 205) and `action_dependency_analyzer.py` (line 656)
both do `prominence = action.get('action_prominence', '').replace('_', ' ')` before
comparing against spaced strings (`'Display Prominently'`, `'Display Overlay'`, `'Do
not display'`). For three of the four real values this round-trips correctly —
`'Display_Prominently'.replace('_',' ')` == `'Display Prominently'`, and the same for
`Display_Inline`/`Display_Overlay` — because those words are naturally capitalized the
same way on both sides.

**It does not round-trip for `Do_Not_Display`, and this is a real, currently-active
bug, not a hypothetical one.** Verified directly:

```python
>>> 'Do_Not_Display'.replace('_', ' ')
'Do Not Display'
>>> 'Do Not Display' == 'Do not display'
False
```

Both files' deck/gallery branches guard with `if prominence != 'Do not display':`
(`actions_orphan_detector.py` line 268; the same construction in
`action_dependency_analyzer.py`). Because the normalized string is `'Do Not Display'`
(title case, from the underscore replace) and the comparison target is `'Do not
display'` (sentence case), the two never match, so this condition is **always true**
for an actual `Do_Not_Display` action — the intended exclusion never fires. Combined
with the Manual/Automatic branch below it, this means: in Automatic mode, a
`Do_Not_Display` action on a deck or gallery view is reported visible unconditionally;
in Manual mode, it is reported visible if it happens to be on the manual list — in
both cases, wrongly, per `APPSHEET_BEHAVIOR.md`'s unambiguous "Hide: don't display in
any view." I did not trace how many of the app's 414 `Do_Not_Display` actions this
actually changes the answer for (that would need `actions_orphan_detector.py` and
`action_dependency_analyzer.py` re-run with instrumentation); flagging the mechanism
as confirmed, its blast radius as unmeasured, is left as a verification step in
section 5.

**Fields read, by file:**

| Field | `navigation_edge_generator.py` | `actions_orphan_detector.py` | `action_dependency_analyzer.py` |
|---|---|---|---|
| `action_prominence` | yes, raw | yes, `.replace('_',' ')`'d | yes, `.replace('_',' ')`'d |
| `attach_to_column` | yes | yes | yes |
| `view_columns` | yes | yes | yes |
| `available_actions` | yes (universal pre-gate) | yes | yes |
| `onclick_actions` | yes (Do_Not_Display exception only) | no | no |
| `referenced_actions` | yes (deck only) | yes (deck/gallery) | yes (deck/gallery) |
| `event_actions` | yes (deck only) | no | no |
| `action_display_mode` | **no — confirmed absent by grep across the file** | yes | yes |
| `show_action_bar` | no | yes, `.lower() == 'true'` | yes, `.lower() == 'true'` |
| `action_type_plain_english`/`action_type` | no | yes (table + Overlay only) | no |

`show_action_bar`'s real value is the string `'True'` (Python-style, capital T,
confirmed by count against deck views: 22 `'True'`, 1 `'False'`). Both files' `.lower()
== 'true'` comparison handles this correctly — this one normalization is not buggy.

## 4. Where should the shared implementation live, and what changes if callers switch to it?

**Proposed module: a new `action_visibility.py` at the repository root**, holding
plain functions with no `self`, no CSV I/O, and no side effects — everything it needs
passed in as arguments, everything it decides returned rather than mutated onto an
instance. Concretely:

```python
def is_visible_in_view(action_prominence, view_type, *, action_name='',
                        attach_to_column='', view_columns=(),
                        available_actions=(), onclick_actions=(),
                        referenced_actions=(), event_actions=(),
                        action_display_mode='', show_action_bar=True,
                        column_exists=None) -> VisibilityResult
```

returning a small named tuple `VisibilityResult(visible: bool, reason: str)` rather
than a bare `bool`, so a caller that wants `navigation_edge_generator.py`'s
`self.stats['edges_blocked_by_visibility']` counter (or a future breakdown by reason,
which section 3 of the read-only audit found nothing currently provides) can still
build it from the `reason` string without the shared function owning any counter
itself. `column_exists` is accepted as an optional callable so
`actions_orphan_detector.py` can keep its extra existence check (section 1) as a
caller-supplied behavior rather than a silently-added requirement for the other two
callers. A second function, `is_visible_in_any_view(action_prominence, views,
**kwargs_per_view) -> bool`, is a thin loop over the first — this is the
existential wrapper section 1 established `actions_orphan_detector.py` genuinely
needs, kept separate rather than folded in.

**What this deliberately does *not* decide yet:** which of the disagreeing cells in
section 2's table the shared function should resolve which way. That is a product
decision (does the consolidated logic follow `APPSHEET_BEHAVIOR.md` where it has an
answer, and remain permissive, restrictive, or explicitly "unknown" elsewhere?), not
an engineering one, and I have deliberately left it out of this plan per the
instruction to plan, not implement.

**Behavior-change risk per caller, if each switched to a shared function that fixed
every table-2 disagreement to match `APPSHEET_BEHAVIOR.md` where it has an answer, and
picked *some* single default for the UNRESOLVED cells:**

- **`navigation_edge_generator.py` is the most exposed.** It currently defaults
  permissively (`True`) for Gallery and the entire "other" bucket (120 views).
  Tightening any UNRESOLVED cell toward `False` would **remove** edges from
  `navigation_edges.csv`, which cascades: fewer edges can only *increase*
  `potential_view_orphans.csv`, which (per STATUS.md's documented coupling) also
  increases `unused_system_views.csv`, which in turn can increase
  `potential_action_orphans.csv`, `potential_format_rule_orphans.csv`, and
  `potential_virtual_column_orphans.csv` — the exact chain the last two sessions'
  verifications traced in the opposite direction. This is the caller where a wrong
  default choice would move the most numbers, and the one most worth verifying with a
  full re-parse before trusting.
- **`actions_orphan_detector.py` is exposed in the other direction.** It currently
  defaults restrictively (`False`) for the "other" bucket and (correctly, if
  accidentally) for Deck/Gallery + `Do_Not_Display` once the case bug is fixed as a
  side effect of any rewrite. Fixing the case bug alone, with no other change, would
  make *fewer* actions "visible," which would make *more* actions eligible for
  `potential_action_orphans.csv` — a plausible, probably-desired tightening, but one
  that needs to be checked, not assumed, since `find_orphan_candidates` also gates on
  `has_reachable_reference` and `is_event_action` (section 1), and an action already
  excluded by one of those two would show no change at all.
- **`action_dependency_analyzer.py` is the safe one to move first.** As established
  in section 1, nothing programmatic consumes its answer; the only effect of any
  change is different text in an interactive session. It is the natural first mover.

**Interface uncertainty I want to flag rather than resolve here:** whether
`attach_to_column`/`view_columns` comparison should be exact-match (as
`action_dependency_analyzer.py`'s comment insists, "EXACT MATCH, not substring") or
allow the looser handling the other two files use without comment. All three currently
do exact `in` membership tests, so there may be no live disagreement here — I could
not find a case in the reference data where this distinction changes an answer, and
did not go looking exhaustively; recorded as unconfirmed rather than asserted safe.

**Decision, Kirk, 2026-09-01: name matching in the consolidated logic is
case-INSENSITIVE unless a specific mechanism has been tested and found otherwise.**
Reasoning: case-insensitive is the permissive choice — it resolves more names,
produces more edges, and reports fewer orphans, so its errors are the silent kind
rather than the complaint-generating kind, the same asymmetry argument already made
in `RELEASE_CHECKLIST.md` section D. Its one known cost is the `Water Tanks` shape
recorded in `APPSHEET_BEHAVIOR.md`'s Case sensitivity section — a possible false
negative, a view cleared as reachable that AppSheet itself might not actually
resolve — and that cost is accepted.

Two exclusions, so this rule is not over-applied later:

- **`FIND()`** is tested and found case-sensitive (`APPSHEET_BEHAVIOR.md`'s Case
  sensitivity section), but it is a text search inside content, not name matching —
  a different category, unaffected by this decision.
- **The `Do_Not_Display` case bug fixed in step 2 below is NOT a case-insensitivity
  problem**, and this decision does not apply to it. The code transforms a
  controlled export string into a spelling (`'Do Not Display'`) that never occurs in
  the data it is compared against (`'Do not display'`); the fix is to stop
  transforming it, not to compare loosely. Applying case-insensitive comparison
  there would paper over the real bug rather than fix it.

## 5. Proposed sequence

Mirroring the two-edits-then-verify shape of `48eead1` and `f4d931a`, in ascending
order of blast radius:

**Step 1 — Extract, without changing any rule.** Write `action_visibility.py`
containing `is_visible_in_view`/`is_visible_in_any_view` as a byte-for-byte behavioral
copy of the three existing implementations combined — i.e., for now, encode *all*
three files' disagreements as-is behind a `strategy` parameter (or three thin
call-compatible functions), and switch only `action_dependency_analyzer.py` to call
the extracted version. **Predicted diff: zero.** No CSV changes at all, since this
caller's output was never written to a CSV; the only verification available is
running the interactive dependency browser against a known action (e.g.
"Go to ObservationActivity") before and after and confirming identical text. This step
proves the extraction is mechanical before any rule changes.

**Step 2 — Fix the `Do_Not_Display` case bug only, in the extracted module, and
switch `actions_orphan_detector.py` to it.** This is a pure bug fix with a documented,
unambiguous source (`APPSHEET_BEHAVIOR.md`'s "Hide: don't display in any view"), not a
judgment call about an UNRESOLVED cell. **Predicted diff:** `potential_action_orphans.csv`
may gain rows (actions that were wrongly "visible" on a deck/gallery through the buggy
check, and have no other reachable reference or event binding) or may show no change
at all if `has_reachable_reference`/`is_event_action` already excluded them from
consideration; it should not lose any rows, and no other CSV should change, since
`action_dependency_analyzer.py` writes nothing and `navigation_edge_generator.py`
hasn't been touched yet. Verify by full re-parse and diff exactly as the last two
sessions did.

**Step 3 — Switch `navigation_edge_generator.py` to the extracted module, still with
no rule changes (each of its three helpers kept as its own `strategy`).** This is the
highest-risk step by exposure (section 4), but zero-risk by design if step 3 is purely
mechanical. **Predicted diff: zero**, and that zero is itself the test — any
change here means the extraction was not actually behavior-preserving, and step 3
should be treated as failed and re-examined before continuing, not patched forward.

**Step 4 — Decide and apply the Gallery-vs-Deck fix inside
`navigation_edge_generator.py`, excluding `Display_Overlay`** (section 2's Gallery
views entry): make Gallery list-gated like Deck for the bar-gated prominences —
`Do_Not_Display`, `Display_Inline`, `Display_Prominently` — since two of three files
already treat them as siblings and no rationale for the current asymmetry was found.
**`Display_Overlay` must be excluded from this change.** It is a view-level floating
button, not a row-level action-bar entry, so list-gating it on Gallery the way Deck is
list-gated would introduce the same defect Deck+`Display_Overlay` already has
(section 2), not fix a parity gap — NEG's current unconditional-True answer for
Gallery+`Display_Overlay` is coincidentally correct and step 4 must not touch it.
**Predicted diff:** `deck`-view edges are unaffected; `gallery`-view edges (2 views in
this app) may drop, for the three bar-gated prominences only, if either gallery view
is not in Manual mode with the relevant actions listed, or if it's Automatic and the
newly-required `referenced_actions` check removes previously-True answers;
`Display_Overlay` edges on either view type must not change at all. Because there are
only 2 gallery views in this app, the predicted diff should be small and fully
enumerable by hand before accepting it — if it touches more than a handful of
`navigation_edges.csv` rows, or touches any `Display_Overlay` row, stop and re-examine
rather than assume it's correct because the CSV differs.

**Step 5 — Apply the Prominent-on-Deck exclusion everywhere**, per Google's Position
documentation, which names only Detail for `Display_Prominently`
(`APPSHEET_BEHAVIOR.md`). The direct observation once cited to justify this step has
since been withdrawn there: the deck used was in Manual mode with the action absent
from its list, so the manual-list rule accounts for the non-display on its own and
the case isolates nothing. The rule now rests on documentation alone, not on an
isolating test — it may still be right, but is no longer the best-evidenced rule in
this plan. **Predicted diff:** could remove edges from
`navigation_edges.csv` for any `Display_Prominently` action currently reaching a deck
or gallery through list membership; per section 3's table, this app has 160
`Display_Prominently` actions total, and the number actually on a deck/gallery's
manual list is unknown without checking — recorded as a number to establish during
this step, not before it. This could move `potential_view_orphans.csv` upward if any
view was only reachable through such an edge — the opposite direction from every fix
in the last two sessions, and worth calling out to whoever reviews the diff so an
increase isn't mistaken for a regression.

**DISPROVED, 2026-09-02 — struck, not deleted, so the record of what this step
predicted survives.** The paragraph above rests on the documentation-only reading
that Kirk's 2026-09-02 observation (`APPSHEET_BEHAVIOR.md`'s "Established behavior"
entry) directly contradicts: three `Display_Prominently` actions on Kankaku's
`W to D` deck are genuinely on that deck's own `ActionBarEntries`, and two of them
were confirmed rendering as row buttons in the app editor's preview.
`Display_Prominently` is not excluded from deck views.

The step was implemented, verified by full re-parse against both apps, and reverted
— never committed. What it actually did does not match what it predicted: it
removed exactly 1 edge in Farmy (target `ActivityForm - Germination`, itself a
phantom view reference — no real orphan consequence) and 3 in Kankaku (targets
`Word`, `WDend`, `WDend J`), not through any action's own `Display_Prominently`
prominence being independently checked, but through the *group parent* actions
`Display Answer (W to D)` and `Displayed Got It (WD)` — both genuinely
`Display_Prominently` and genuinely on `W to D`'s action bar — being wrongly excluded
by the (disproved) rule, which cascaded to remove all of their children's edges per
this module's hard constraint that a group's children are never independently
visibility-checked. Kankaku's 3 removed edges cascaded to 4 new rows in
`potential_view_orphans.csv` (`Word`, `WDend`, `WDend J`, and `Card stats 2`, whose
own only other reachability path was already broken independently of this step) — a
real orphan-count increase, not the zero a working measurement taken before
implementation had predicted.

The step's own predicted diff named "a deck or gallery," while this step's heading
and `APPSHEET_BEHAVIOR.md`'s scope named deck only; gallery was never applied under
this step and the question is now moot along with the rest of it.

The patch implementing this step is preserved outside the repository, not committed,
at `~/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_step5_disproved.patch`.

**Step 6 — Remove the action-bar gate entirely for `Display_Overlay` on deck views,
in all three files** (STATUS.md's "All three visibility implementations gate
`Display_Overlay` on a deck's action bar" entry; section 2's Deck views entry). This
is the deck-side counterpart of the fix `e0530c8` already applied to Table+
`Display_Overlay`: treat Primary/`Display_Overlay` as a view-level floating button,
ungated by `referenced_actions`, `show_action_bar`, or `action_display_mode`, for the
deck view type too. **Not covered by step 4 above.** Step 4 addresses only Gallery's
bar-gated prominences and explicitly excludes `Display_Overlay`, leaving Deck's
current (wrong) behavior untouched by design — its own text says
"`Display_Overlay` edges on either view type must not change at all." This step is
the route step 4 deliberately does not take. **Predicted diff, by analogy to
`e0530c8` rather than by measurement:** likely to add edges to `navigation_edges.csv`
for `Display_Overlay` actions currently blocked on deck views wherever
`referenced_actions` membership or `show_action_bar` currently fails, and — following
the same pattern `e0530c8` found on table views, where 82 new edges cleared zero
orphans because every affected target was already reachable another way — may clear
no orphan at all. This is a guess by analogy, not a number, and should be verified by
a full re-parse exactly as `e0530c8` was, not assumed.

**Deliberately deferred, not sequenced here:** the "other" bucket's permissive-vs-restrictive
default (section 2's second cross-cutting finding, 120 views, the single largest
number in this plan) and the Automatic-mode `referenced_actions` completeness
question. Both require either new observation (extending `APPSHEET_BEHAVIOR.md`'s
Unknowns list) or a judgment call this plan was not asked to make. I recommend not
scheduling either until at least one of the "Unknowns" cells has been tested in a
running app, the same way the Deck case was settled.

## 6. What makes this harder than it looks

- **The group-action bypass (section 1) is the single biggest trap.** Any refactor
  that mechanically threads the new shared function into every place prominence and
  view type are both available — including `process_group_action`'s child-edge loop,
  which currently checks neither — would silently revoke the group-membership routes
  confirmed real in the `f4d931a` session (four views cleared this way, cross-checked
  against the live app for one of them). The plan above never touches
  `process_group_action`; any future step that does needs its own explicit
  justification and predicted diff, not a drive-by inclusion.
- **`navigation_edge_generator.py`'s side effects are entangled with its call sites,
  not just its logic.** `self.stats['edges_blocked_by_visibility']` is incremented
  from nine separate points inside the current helpers; a naive extraction that
  forgets to wire the new `reason` field back into that counter would make the
  end-of-run summary print a silently wrong number without any CSV changing — a
  regression invisible to the diff-based verification this whole project has relied
  on so far.
- **`actions_orphan_detector.py`'s existential loop has caching state
  (`self.columns_checked`, lazily built on first `column_exists` call) that a pure
  function can't own** without either taking a pre-built lookup as a parameter or
  accepting that the extraction isn't fully pure. This is a small thing but will
  produce an awkward function signature if not decided up front.
- **Interactive vs. automated risk is easy to lose track of once the code is merged.**
  Once `action_dependency_analyzer.py` calls the same function as
  `navigation_edge_generator.py`, a future change made "for the edge generator's sake"
  will also change what a human sees in the interactive browser, and vice versa —
  worth a comment at the call sites, not just in this plan, once step 1 lands.
- **No test suite exists to depend on current behavior** — I searched for one and
  found none; verification throughout this project has been full-reparse-and-diff
  against the reference output, which is why the sequence above is structured the
  same way. This means every step's "predicted diff: zero" claims are only as good as
  actually running the parse, not as good as the code review that produced the
  prediction.
- **This app has zero actions carrying the literal export string `'Primary'`** — that
  string never occurs in the data; `93` of this app's actions carry the real export
  value, `Display_Overlay`, and are exercised throughout. Claims in section 2 about
  the `'Primary'` string specifically are claims about dead code; its `Display_Overlay`
  claims are not. The three files also no longer disagree three ways here:
  `e0530c8` moved NEG and AOD to `True` for Table+`Display_Overlay`, leaving only ADA
  wrong — a known defect (STATUS.md), not a live contradiction.
- **The gap this plan originally surfaced in `APPSHEET_BEHAVIOR.md`'s "Unknowns" list
  — `form` named nowhere in it — was closed in an earlier session.** That section now
  names `form`, `card`, `gallery` and `map` as addressed under "Established behavior,"
  each with its own source; only `calendar` and `dashboard` remain genuinely
  unestablished there. No further follow-up is needed on this point.

## Note added 2026-08-31 (superseded 2026-08-31)

Originally written to patch the old section 2 with the Primary/`Display_Overlay`
vocabulary correction, found via a screenshot of Leon's app editor. Section 2 has
since been replaced entirely (see its own "Changes from the previous version of this
section"), which now carries that correction directly and more currently — including
the Table+`Display_Overlay` resolution this note used to describe as still open; that
resolution (`e0530c8` moved NEG and AOD to `True`, leaving only ADA wrong) is stated
in section 2 and, for section 6's claim, directly in section 6 above. What is not said
elsewhere, and is kept here for that reason: the sequence in section 5 (five steps
when this note was written, six as of the step added 2026-09-01 for Deck+`Display_Overlay`)
never depended on distinguishing `Primary` from `Display_Overlay`, since none of its
steps singled out the literal `Primary` string's handling for a fix — that string is
dead code (section 6 above) — so it is unaffected by any of this.
