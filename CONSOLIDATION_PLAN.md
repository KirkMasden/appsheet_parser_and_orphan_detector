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
  (9 increment sites total) — a side effect on the instance, not a pure function.

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

View types are grouped as: the three types at least one file branches on explicitly
(`detail`, `table`, `deck`), `gallery` (branched on by two of three, folded into deck's
branch), and "**other**" — every view type none of the three names explicitly
(`map`, `card`, `calendar`, `dashboard`, `form`; **120 of the app's 319 views**: 92
form + 17 card + 7 map + 3 dashboard + 1 calendar, verified by count against
`appsheet_views.csv`). Prominence columns use the five values actually present
in the export (`appsheet_actions.csv`, confirmed by count below); "Primary" is
included even though it occurs **zero times** in this app's real data — its code
paths are entirely untested by this app.

Legend: **T** = returns/contributes `True`; **F** = returns/contributes `False`;
"list-gated" = outcome depends on `available_actions`/`referenced_actions`/
`action_display_mode`, not on prominence at all; UNRESOLVED = `APPSHEET_BEHAVIOR.md`
records no rule for this cell, so no rule is asserted here either.

| View type | Prominence | `navigation_edge_generator.py` | `actions_orphan_detector.py` | `action_dependency_analyzer.py` | `APPSHEET_BEHAVIOR.md` |
|---|---|---|---|---|---|
| Detail | Primary | **T** (unconditional) | **F** (not in allow-list) | **F** (not in allow-list) | UNRESOLVED — no view type named |
| Detail | Prominent | **T** | **T** | **T** | **T** — the one documented case |
| Detail | Inline | T/F on column match | T/F on column match **+ column exists in `appsheet_columns.csv`** | T/F on **exact** column match | UNRESOLVED (doc names only Table's caveat) |
| Detail | Overlay | **T** | **T** | **T** | UNRESOLVED — "Overlay" is not one of the four documented Position values at all |
| Detail | Hide | **F** (not in allow-list; the onclick exception below never reaches this branch — see note) | **F** | **F** | **F** — matches |
| Table | Primary | **T** ("Primary actions appear as row-level actions") | **F** (no branch) | **F** (no branch) | UNRESOLVED |
| Table | Prominent | **F** (explicit comment: not supported) | **F** (no branch) | **F** (no branch) | UNRESOLVED, though all three happen to agree |
| Table | Inline | T/F on column match | T/F on column match + exists-check | T/F on exact column match | **T, with a caveat** — Inline *replaces* the column rather than sitting beside it; none of the three files' logic distinguishes this from ordinary display |
| Table | Overlay | **F** (explicit comment: not supported) | **T only if `action_type_plain_english == 'Navigate'`** | **F** (no branch) | UNRESOLVED — three-way split, the most divergent cell in the table |
| Table | Hide | **F** (explicit check) | **F** (no branch; case-bug below does not reach here) | **F** (no branch) | **F** — matches |
| Deck | Primary | list-gated (prominence not read at all) | list-gated/Automatic (prominence not read, since Primary ≠ `'Do not display'`) | list-gated/Automatic, same as AOD | UNRESOLVED |
| Deck | Prominent | list-gated — **would say T if the action happened to be on the list**, since prominence isn't checked | list-gated/Automatic — same gap | list-gated/Automatic — same gap | **F, observed directly** (2026-08-30) — the original finding. None of the three files would produce F from prominence alone. |
| Deck | Inline | list-gated | list-gated/Automatic | list-gated/Automatic | UNRESOLVED |
| Deck | Overlay | list-gated | list-gated/Automatic | list-gated/Automatic | UNRESOLVED |
| Deck | Hide | onclick-bound **and** on the list → T, else **F** (correctly excludes) | **bug: `prominence != 'Do not display'` is always true (see §3) — never excludes Hide** | same bug as AOD | **F** — universal. AOD/ADA's actual behavior contradicts this documented rule. |
| Gallery | Primary | **T, unconditional** (gallery has no explicit branch in this file — falls to `else: return True`) | list-gated (grouped with deck) | list-gated (grouped with deck) | UNRESOLVED |
| Gallery | Prominent | **T, unconditional** | list-gated (same deck-mechanism gap as above) | list-gated | UNRESOLVED (named in doc's own Unknowns list) |
| Gallery | Inline | **T, unconditional** | list-gated | list-gated | UNRESOLVED |
| Gallery | Overlay | **T, unconditional** | list-gated | list-gated | UNRESOLVED |
| Gallery | Hide | onclick-bound → T, else F (via the shared pre-gate, then falls to the unconditional-True branch) | same case-bug as Deck/Hide | same case-bug | **F** — same contradiction as Deck/Hide |
| Other (map/card/calendar/dashboard/form) | any of the 5 | **T, unconditional**, for every one of the 5 prominence values (Hide still needs onclick-binding first) | **F**, for every one of the 5 (no branch matches, loop just continues) | **F**, for every one of the 5 (falls to final `return False`) | UNRESOLVED for map/card/calendar/dashboard/gallery (doc's own "Unknowns" list); **`form` is not even named in that list** — an omission in `APPSHEET_BEHAVIOR.md` itself, worth fixing there separately from this plan |

Two disagreements are not cells in this table because they cut across every cell in a
row or block, and deserve their own statement:

- **Deck vs. Gallery inside `navigation_edge_generator.py` itself.** The same file
  treats these two view types by completely different mechanisms — Deck is
  list-gated, Gallery is unconditionally permissive — despite AppSheet almost
  certainly treating them as siblings at the UI level (both are collection views with
  an action bar). `actions_orphan_detector.py` and `action_dependency_analyzer.py`
  both explicitly group them (`elif view_type in ['deck', 'gallery']:`). This looks
  like an omission in `navigation_edge_generator.py` — Gallery was never added when
  Deck's list-gating was written — rather than a considered choice; I could not find
  a comment explaining it, so I record it as unexplained rather than intentional.
- **Automatic-mode completeness is itself unresolved**, independent of prominence.
  `views_parser.py` (lines 770–792) populates a view's `referenced_actions` from
  `ActionColumns` + `ActionBarEntries` + non-auto `Events` only. In `Automatic` mode,
  `ActionBarEntries` is absent or empty, so `referenced_actions` may legitimately be
  incomplete relative to what AppSheet's automatic ordering would actually display —
  meaning `navigation_edge_generator.py`'s Deck check (which requires
  `referenced_actions` membership unconditionally, Automatic or not) could
  **under-count** on an Automatic deck. `actions_orphan_detector.py` and
  `action_dependency_analyzer.py` instead return `True` unconditionally for any
  non-excluded prominence in Automatic mode, without checking `referenced_actions` at
  all — which could **over-count**, since an Automatic deck's actual auto-ordering
  behavior (which actions it includes, and in what order) is not established anywhere
  in `APPSHEET_BEHAVIOR.md` or the code. I flag this as unresolved rather than
  guessing which of the two is closer to correct.

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
`navigation_edge_generator.py`** (section 2's first cross-cutting finding): make
Gallery list-gated like Deck, since two of three files already treat them as siblings
and no rationale for the current asymmetry was found. **Predicted diff:** `deck`-view
edges are unaffected; `gallery`-view edges (2 views in this app) may drop if either
gallery view is not in Manual mode with the relevant actions listed, or if it's
Automatic and the newly-required `referenced_actions` check removes previously-True
answers. Because there are only 2 gallery views in this app, the predicted diff should
be small and fully enumerable by hand before accepting it — if it touches more than a
handful of `navigation_edges.csv` rows, stop and re-examine rather than assume it's
correct because the CSV differs.

**Step 5 — Apply the Prominent-on-Deck exclusion everywhere**, since it is now the
best-evidenced single rule in this whole plan (direct observation, cited in
`APPSHEET_BEHAVIOR.md`). **Predicted diff:** could remove edges from
`navigation_edges.csv` for any `Display_Prominently` action currently reaching a deck
or gallery through list membership; per section 3's table, this app has 160
`Display_Prominently` actions total, and the number actually on a deck/gallery's
manual list is unknown without checking — recorded as a number to establish during
this step, not before it. This could move `potential_view_orphans.csv` upward if any
view was only reachable through such an edge — the opposite direction from every fix
in the last two sessions, and worth calling out to whoever reviews the diff so an
increase isn't mistaken for a regression.

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
- **This app has zero `Primary`-prominence actions**, so every claim in section 2
  about `Primary`'s behavior is a claim about *code that has never executed against
  real data in this project*. Any consolidation touching Primary's handling should be
  treated as unverified by this app regardless of how confidently the three files
  currently agree or disagree about it.
- **`APPSHEET_BEHAVIOR.md` itself has a gap this plan surfaced but was not asked to
  fix**: `form` is absent from its "Unknowns" list even though no code file names it
  either, and it is 92 of the app's 319 views — the single largest view type by count
  after `detail`. Worth a follow-up to that file, separately from this plan.

## Note added 2026-08-31

A screenshot of Leon's app editor established that the editor's Position names and
the export's `action_prominence` strings are two different vocabularies — see the new
mapping table in `APPSHEET_BEHAVIOR.md`. Editor "Primary" is stored as
`Display_Overlay`, not as the string `'Primary'`. This corrects three things above:

- Section 2's `Primary` row describes a string that never occurs in the data (0 of
  970 actions). Every verdict recorded there for `Primary` is really a claim about
  dead code, not about how the editor's actual Primary actions are handled — those are
  the rows currently labeled `Overlay`/`Display_Overlay`.
- The Table+Overlay "three-way split," flagged in section 2 as the single most
  divergent cell in the whole table, is really a contradiction about Primary
  specifically: `navigation_edge_generator.py`'s dead `'Primary'` branch says table
  views support it, while the same file's live `Display_Overlay` branch says they
  don't (see the new `STATUS.md` entry for the exact lines).
- Section 6's claim that "this app has zero `Primary`-prominence actions" is wrong.
  The app has 93, under the export name `Display_Overlay`. Section 6's underlying
  point — that a claim about a prominence value is only as trustworthy as the string
  actually being tested — still stands, and is now the stronger reason to distrust the
  three files' `'Primary'` branches specifically, rather than a reason to distrust
  their `Display_Overlay` handling, which is exercised 93 times over.

The five-step sequence in section 5 is unaffected: it never depended on distinguishing
`Primary` from `Display_Overlay`, since none of its steps singled out `Primary`'s
handling for a fix.
