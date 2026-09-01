# Project status

Last updated 2026-08-31. Records what is outstanding in this project between working sessions.

See `APPSHEET_BEHAVIOR.md` for AppSheet's own display rules (positions, deck action
bars, grouped-action execution) with sources for each. This file stays about defects
in this code; that one is a specification of the platform's behavior. Don't duplicate
between them — a platform rule goes there, this code's handling of it stays here.

## Known defects

### Orphan detector false positives — view switched at runtime, no navigation link (category 3)

Of the four false-positive categories originally reported, three are fixed (see "Recently fixed" below). This one remains open — category 3, by elimination against 1, 2, and 4 below, which is where the label had lived unassigned until now.

- The view in question is never declared in any dashboard's entries at all — this is not a shortfall in `process_dashboard_containment`, which works correctly and emits an edge for every view a dashboard declares. Instead, the view is switched in at runtime by `set_columns` actions that write a value into a column, combined with sibling views whose show-if conditions test that column. There is no navigation link of any kind, so no edge exists to be followed.
- Detecting this would mean inferring intent from an action's written value and a view's condition. This was investigated and not attempted: the pattern does not hold reliably enough to detect on its own, and a rule loose enough to catch it would exempt views with no actual evidence of being reachable.

### Five actions in the app itself target views that do not exist

- `Seeds Form` (the actual view is `Seeds_Form`), `ActivityForm - Transplant`, `ActivityForm - Germination`, and `ActivityForm Observation` are named by `LINKTOFORM` calls in the app (actions `Add Seeds to Order`; `Go to TransplantActivity`; `Go to Germination - From MyPlants Direct Sow`; `Go to ObservationActivity` and `Go to ObservationActivity 2`), but no view by these names exists in `appsheet_views.csv`. A fifth, `NurseryForm2b`, is named by a `LINKTOROW` call in the Sync action `Sync | Order (Complete)` on table `Nursery`; no such view exists either, and the nearest existing names are `Nursery_Form`, `NurseryDetails_Form`, and `Nursery Creating_Form`. Unlike the other four, this one is not a `new_record_form`/`LINKTOFORM` case, and it did not surface until `496d5ed`'s `parse_linktorow` fix stopped the greedy-regex bug from swallowing it into a bogus row first (see "Recently fixed" above) — the fix didn't create this phantom, it stopped hiding it. All five look like stale names left after view renames — a defect in the app being analyzed, not in this tool. `f4d931a` (for the first four) and `496d5ed` (for the fifth) emit them as targets rather than silently correcting or dropping them, so they now surface correctly in `potential_phantom_view_references.csv`. Not verified by observation in the running app.

### All three visibility implementations gate `Display_Overlay` on a deck's action bar, the wrong element

- `navigation_edge_generator.py`'s `is_action_visible_in_deck_view` requires membership
  in `referenced_actions`; `actions_orphan_detector.py` and
  `action_dependency_analyzer.py` require `show_action_bar` to be true and then branch
  on `action_display_mode`. All three therefore make a Primary/`Display_Overlay`
  action's visibility depend on the deck's row-level action bar.
- Per `APPSHEET_BEHAVIOR.md`'s Deck+Overlay entry, a Primary action is a view-level
  floating button and not a member of that bar, so none of these gates should apply to
  it. See `CONSOLIDATION_PLAN.md` section 2's Deck views entry for the cell-by-cell
  detail; the platform reasoning is not restated here.
- Consequence worth stating: on a deck whose action bar is switched off, a Primary
  action is invisible to AOD and ADA, blocked by a setting governing a different
  element. Leon's app contains one such deck.
- Not fixed.

### Manual action-list exclusion may not be enforced outside deck views

- `action_display_mode` is present for every view type in the export, but `navigation_edge_generator.py` reads it only inside `is_action_visible_in_deck_view` — see the open question under "Manual action lists" in `APPSHEET_BEHAVIOR.md`. Not investigated.

### `action_dependency_analyzer.py`'s table branch has no `Display_Overlay` case

- Confirmed, not merely suspected: its table branch (lines 677–682) has no case for `Display_Overlay` at all and falls through to the function's final `return False` — the same wrong answer `navigation_edge_generator.py` gave before `e0530c8` (see "Recently fixed"), reached by omission rather than an explicit rejecting rule. Deliberately left out of `e0530c8` so the two output-affecting edits could be verified alone. Nothing programmatic consumes this function's answer — it feeds only the interactive dependency browser (`dependency_analyzer_hub.py`) — so the error currently affects only text shown there, not any CSV or orphan count.

### Seven modules have had no logic change since they were written — a blind spot, not a clean bill of health

- `view_orphan_detector.py`, `view_dependency_analyzer.py`, `slice_orphan_detector.py`, `format_rules_parser.py`, `format_rule_orphan_detector.py`, `column_dependency_analyzer.py`, and `action_dependency_analyzer.py` have never had a logic change since being written, per `git log` on each file (only the mechanical `csv_limits.py` import touches any of them). "Untouched" is ambiguous: it means either the code is solid, or it has never been exercised against real, varied data, and git history alone cannot tell the two apart. `action_dependency_analyzer.py` has already been shown to be the second case, not the first — see the entry directly above: never modified, and wrong the whole time it sat unmodified. The other six have not been examined at all; nothing here should be read as implying they are sound.
- The pattern found across the wider history bears on how much confidence that absence of past fixes should give: `navigation_edge_generator.py` and `action_target_parser.py` were each untouched (beyond the mechanical `csv_limits` import) for months, then took every one of their real fixes inside a single 48-hour window, 2026-08-30 to 08-31, when the suite was first stress-tested against a second app in depth. In this project's own history, a long gap since the last fix has meant "not yet tested against different data" at least as often as it has meant "correct."

### December 2025 User Settings work is unverified

The `USERSETTINGS()` parsing, User Settings orphan detection and broken-reference detection shipped 2025-12-24 with an explicit public caveat that more testing was needed. That testing has not happened. The caveat itself could not be verified from this repository or its git history — no commit message or file records it — so treat "explicit public caveat" as asserted, not established, until a source is found.

### One remaining defect found by the section C reference parse of Kankaku

Two entries originally stood here, both found 2026-08-31 by the section C reference
parse of Kirk's own app, Kankaku (260411 Kankaku V18) — see `RELEASE_CHECKLIST.md`
section C. Baseline parse: `20260831_182306_260831_1809_Kankaku_V18_baseline_parse`.
The second, the curly-quote parsing defect, is fixed as of `1c22881` and has moved
to "Recently fixed" below; only the phantom-reference case-sensitivity entry remains
open here.

Note the counting, since this file uses "second app" elsewhere with the opposite
sense (see "Seven modules..." above): Kankaku is the app the suite's display rules
were originally derived from; Farmy — Leon's app, in Kirk's frozen copy — is the
second app, the one whose stress-testing exposed the 2026-08-30/31 fixes below. What
is new here is not a second app but a current one. Kankaku was last parsed in
September 2025 at version 17, and every parse since has been of Farmy; this is the
first time Kankaku's current version has been parsed by the current suite, and the
first time it has been saved as a regression baseline alongside Farmy's.

#### `phantom_view_reference_detector.py` matches view names case-sensitively, producing false positives

- Symptom: `potential_phantom_view_references.csv` flags 2 rows, both columns on the
  `Kankaku` table — "Card status" and "Card status J", field
  `type_qualifier_formulas`. Both carry a `Show_If` with a branch testing
  `Context("View")="Card Stats"`. The app's actual view is named "Card stats"
  (lowercase s), confirmed in the app editor 2026-08-31; no view named "Card Stats"
  exists.
- Why this is the tool's error and not the app's: AppSheet's `=` operator is
  case-insensitive on text, so the expression matches the view correctly in the
  running app. See `APPSHEET_BEHAVIOR.md`'s "Case sensitivity" section for the
  platform rule and its sources.
- Evidence internal to the same expression, worth recording because it isolates the
  mechanism: the same `Show_If` also tests `Context("View")="Card stats 2"`, which
  matches an existing view exactly and was NOT flagged. Two branches in one
  expression, differing only in the case of one letter, got different verdicts.
- Class: the third instance of the same class in this project. `748e329` fixed
  case-sensitive view-TYPE comparison in `check_context_conditions`; the `f4d931a`
  entry below records `LINKTOVIEW("Water tanks")` resolving through already-existing
  case-insensitive matching. Case handling is inconsistent across modules.
- Severity: a false phantom is worse than a missing one, because it sends a user
  hunting for a button that is not broken — the same reasoning that already governs
  how this file treats the genuine phantom references surfaced under "Five actions in
  the app itself target views that do not exist" above, just cutting the other way
  here: those are real and correctly surfaced, these two are not real and should not
  have been.
- Whether this also affects Farmy is NOT established. Farmy's 56 phantom references
  (`potential_phantom_view_references.csv`) have not been checked for case-mismatch
  false positives. Do not describe this defect as Kankaku-specific until that check
  is done.
- Not fixed. Read-only finding.

### Two smaller anomalies from the Kankaku run — not parsing defects

- `format_rule_orphan_detector.py` does not write `potential_format_rule_orphans.csv`
  at all when zero orphans are found. A missing file and an empty file are different
  things to anyone diffing parse output directories mechanically. This is not unique
  to this detector — see "`view_orphan_detector.py` also writes no
  `potential_view_orphans.csv` on a zero result" below for the shared class and how
  far it reaches.
- `master_parser_and_orphan_detector.py` raises `EOFError` on its trailing
  interactive "Would you like to explore dependencies now? (y/n)" prompt when run
  without stdin. All output is already written by then, so it is not a parse
  failure, but it will affect anyone running the suite from a script.

### `view_orphan_detector.py` also writes no `potential_view_orphans.csv` on a zero result

- Confirmed by reading `write_results_to_csv` (lines 367–390): `if orphan_candidates:`
  gates the entire write, exactly the shape already recorded above for
  `format_rule_orphan_detector.py` — zero orphans means no file, not a header-only
  one. That entry's "unlike sibling detectors, which write a header-only file"
  framing is therefore wrong for at least this sibling.
- Broader than a pair: `actions_orphan_detector.py` (`if not orphan_candidates:
  return`, line 486) and `slice_orphan_detector.py` (same guard, line 254) show the
  identical pattern on inspection. `column_orphan_detector.py`'s equivalent
  (`if potential_orphans:`, line 452) has not been separately re-checked here but
  reads the same way. This may be all five orphan detectors sharing one behavior,
  not two of five — not confirmed exhaustively, but the "unlike sibling detectors"
  framing should not be trusted for any of them until each is actually checked.
- Surfaced 2026-09-01 verifying the curly-quote fix below: Kankaku's
  `potential_view_orphans.csv` (3 rows pre-fix) is simply absent post-fix, not
  present with a header and no rows, which is what prompted reading the source.
- Not fixed. Read-only finding.

### Kankaku's `Card stats` clearance rests on an untested platform assumption

- The curly-quote fix below recovers a `LINKTOROW` call in "Go to card stats"
  targeting `"Card Stats"`, cleared as reachable only because this suite resolved
  that name to the app's real view, `Card stats` (lowercase s), case-insensitively.
  Whether AppSheet itself resolves the mismatch that way at runtime is untested —
  the same shape of risk already recorded against `Water Tanks` in Farmy (see the
  `f4d931a` entry below).
- The app test that would settle this is `RELEASE_CHECKLIST.md` section A's
  2026-09-01 item; the answer, once run, belongs in `APPSHEET_BEHAVIOR.md`'s "Case
  sensitivity" section, not here.

### `parse_linktoform` and `parse_linktofilteredview` share the curly-quote blindness `parse_linktorow` had

- Both use a single quoted-argument regex requiring a literal straight `"`
  (`LINKTOFORM\s*\(\s*"([^"]+)"`, the identical shape for `LINKTOFILTEREDVIEW`), with
  no fallback pattern. A curly-quoted view name in either — the same shape of
  argument the `496d5ed` regression affected in `parse_linktorow` (see "Recently
  fixed" below) — would match zero times and fail silently, filing the whole
  expression as an unparseable "Unknown pattern" the same way.
- `parse_linktoview` survives this by accident, not by design: its unquoted fallback
  pattern (`LINKTOVIEW\s*\(([^")][^)]*)\)`) does not require a straight quote at all,
  so it captures `“ViewName”` whole, and the existing
  `.strip(chr(8220)).strip(chr(8221))` cleanup recovers the correct name afterward.
- Found 2026-09-01 while investigating the `parse_linktorow` curly-quote fix below;
  that fix's scope was `parse_linktorow` only. Not fixed. Read-only finding.

### `actions_parser.py` normalizes curly quotes for one consumer of `navigate_target` and not the other

- `extract_views_from_navigate_target` (line ~738) normalizes a *local copy* of the
  navigation expression — curly quotes to straight, via `base_parser.normalize_string`
  — before extracting `referenced_views` for its own use. But the raw, un-normalized
  `value` it was given is what gets stored into `action_info['navigate_target']` at
  line ~975, and that field is exactly what `action_target_parser.py` later reads to
  do its own parsing.
- One function call produces two different views of the same expression: normalized
  for `actions_parser.py`'s own `referenced_views` field, raw for the field the rest
  of the pipeline depends on.
- Found 2026-09-01 alongside the finding above. Not fixed. Read-only finding.

### `action_dependency_analyzer.py`'s copy of the `Do_Not_Display` case bug is still live

- `is_visible_in_view_ada` (in `action_visibility.py`, since `84a651d`) still does
  `action_prominence.replace('_', ' ')` before comparing against `'Do not display'`,
  the same mismatch `84a651d`'s companion commit `6115f30` fixed in the AOD
  strategy — see that entry below for the mechanism. Deliberately not fixed
  alongside it: ADA has been live on `action_visibility.py` since step 1, so
  fixing its copy changes what the interactive dependency browser
  (`dependency_analyzer_hub.py`) actually reports for any `Do_Not_Display`
  action on a deck or gallery view, a real behavior change with no CSV to
  verify it against.
- **What fixing it will take:** the same string-stops-transforming fix
  `6115f30` applied to `is_visible_in_views_aod`, applied to `is_visible_in_view_ada`.
  Verification cannot be a CSV diff or a differential pairwise-verdict
  comparison alone (a verdict changing is the *point* of this fix, unlike
  steps 1–2, so "zero disagreements" is the wrong success criterion here) —
  it needs a before/after comparison of the browser's actual reported text
  for at least one `Do_Not_Display` action known to sit on a deck or gallery
  view, confirming the "Displayed action" label now correctly disappears for
  that view and does not disappear anywhere it should not. See
  `CONSOLIDATION_PLAN.md` section 5, between steps 2 and 3, for where this
  belongs in sequence.
- Not fixed. Read-only finding as of 2026-09-01.

### Diffing orphan-detector output by `action_name` alone is unreliable — `action_name` is not unique

- Found 2026-09-01 verifying `6115f30`: Farmy's export reuses generic action
  names ("Add", "Edit", "Delete", …) across many different tables — one `Add`
  action per table, not one per app. A first pass at both the CSV diff (comparing
  `potential_action_orphans.csv` row sets by `action_name` alone) and the gate
  trace that explains verdict changes (matching flipped actions back to a
  specific row by `action_name` alone) gave a misleading result before being
  redone: the CSV-diff pass could have missed added/removed rows that share a
  name already present on both sides of the diff (it happened not to, this
  time, confirmed by redoing it keyed on `(action_name, source_table)`), and
  the gate-trace pass would have attributed one flipped row's gate values to
  every other row sharing its name, double- and mis-counting whenever a name
  is not unique.
- **General caution, not a one-off:** any future comparison of this suite's
  output — CSV diffs, differential verdict comparisons, gate traces — must key
  on `(action_name, source_table)` at minimum, or on row identity (index into
  the source CSV) where even that pair might collide, never on `action_name`
  alone. This applies to any file keyed by action name, not only
  `potential_action_orphans.csv`.
- Not a defect in the tool's own output — the tool's `write_results_to_csv`
  writes every qualifying row regardless of name collisions. It is a hazard
  in how this project's own verification scripts are written, recorded here
  so it is not rediscovered the hard way in a future session.

## Recently fixed

Entries from `48eead1` onward carry full verification detail — row counts, byte-identical claims, named views. Earlier entries are compressed summaries; for the fuller reasoning behind one of those, read that commit's own message rather than expecting it here.

- 2026-08-25, `2f0cb81` — the Windows `OverflowError` crash, a regression introduced by `cd9eaac`'s own fix (2026-04-18): `csv.field_size_limit(sys.maxsize)` overflows the 32-bit C `long` Windows uses even under 64-bit Python. The wider concern noted in the old entry is also addressed: a shared `csv_limits` module is now imported by all sixteen modules that read CSVs, so standalone entry points are no longer exposed.
- 2026-08-30, `ad7a830` — view names in the `referenced_views` field came from a Python `set`, so their order varied between runs under Python's randomized hash seed, making parse output non-reproducible. Now sorted. Deduplication unchanged.
- 2026-08-30, `5b2c06b` — false positive category 4, slices referenced in column-level expressions. `parse_column()` extracted the Suggested Values formula but never assigned it to the `suggested_values` field, which the slice orphan detector scans, so that field was empty for every column in every app. Any slice referenced only through a Suggested Values expression was reported as an orphan.
- 2026-08-30, `59db213` — false positive category 1, views reached via actions. The specific cause was custom-canvas Layout onClick bindings: an action invoked by tapping a view element is normally set to `Do_Not_Display`, and the edge generator treated that prominence as an unconditional dead end. `views_parser` now records onClick-bound actions and the veto has a scoped exception for them. The rule is unchanged for every other case. The JSON is walked structurally rather than matched by regex — key order varies and bindings nest arbitrarily deep, and a regex approach was measured to find only 18 of the 22 views a full walk finds. `attach_to_column` was evaluated as a cheaper proxy for onClick detection and rejected: actions carrying it exist with no binding and no other evidence of invocation, so using it would exempt genuine orphans.
- 2026-08-30, `90555be` — false positive category 2, views referenced through Related virtual columns, PARTIALLY fixed. A List-type column's `ReferencedTableName` is now extracted and resolved to a view when exactly one view has that value as its data source. Where several views share it, nothing is resolved and no edge is created, because choosing among sibling Detail, Form and Inline views would be a convention rather than a fact. See "Remaining work on the false positives" below.
- 2026-08-30, `fa68783` — a latent crash in `column_orphan_detector.py`, exposed by the fix above. `write_results_to_csv()` writes from a fixed fieldnames list while each row is a full copy of a column dict, so any newly added column field raised `ValueError`. Left without `extrasaction='ignore'` deliberately, so a missing field fails loudly rather than being dropped silently.
- 2026-08-30, `748e329` — `check_context_conditions` in `navigation_edge_generator.py` compared view types case-sensitively. `CONTEXT("ViewType")` conditions carry the app author's literal casing while `appsheet_views.csv` stores `view_type` in lower case, so every such condition failed and no edge was created. Eleven rows in the test app were affected. Both sides are now normalized. The fix produced two new edges but changed no orphan count in that app, because the affected paths are also blocked by unrelated visibility gates.
- 2026-08-30, `48eead1` — `LINKTOFILTEREDVIEW` unhandled in `action_target_parser.py`, which recognized only `LINKTOVIEW` and `LINKTOROW`. 34 of the 36 actions using it fell through `parse_navigation_expression`'s dispatch chain into `action_targets_unparseable.csv` as "Unknown pattern"; the other 2 were silently discarded inside `IF` branches by a second, independent copy of the same function-name list in `parse_if_expression`'s `has_nav_true`/`has_nav_false` check. A nested-expression claim made earlier the same day was wrong: nested `IF`s were already traversed correctly by recursion, and the branch was lost to that hard-coded substring test, not to nesting depth. Added `parse_linktofilteredview` and its dispatch branch, and replaced the hard-coded test with one shared `NAV_FUNCTIONS` tuple (`LINKTOVIEW`, `LINKTOROW`, `LINKTOFILTEREDVIEW`) and a helper used by both branches, so the two lists cannot drift apart again. Verified by a full re-parse of the test app: 34 rows left `action_targets_unparseable.csv`, 37 rows were added to `action_targets.csv` (34 from the dispatch fix, 3 recovered `IF` branches), all 34 newly-parsed target view names matched an existing view, and six previously-flagged views cleared.
  - A seventh view cleared unexpectedly: its only naming action is `Do_Not_Display` with no onClick or event binding, but that action is a member of group action "TRANSPLANT 0 - GROUP", itself available (`Display_Overlay`) on its source view — a real, previously-unidentified invocation route. Only one view now remains flagged for this reason, "Order Form Seeds List BUYING"; earlier reasoning in this project had treated two views as unexplained, having checked only onClick and event bindings. A `Do_Not_Display` action has a third possible route, membership in a group action that is itself reachable, and that check had not been made. See "Remaining work" below.
  - Pipeline coupling found during verification, previously undocumented: `unused_system_views.csv` is written from `navigation_edges.csv` reachability by `view_orphan_detector.py`, then read by `actions_orphan_detector.py` and `format_rule_orphan_detector.py` to gate their own orphan checks — and, found during the `f4d931a` verification below, by `column_orphan_detector.py` too, whose `search_references_in_file` skips any view on that list when counting column references. Any change to navigation edges therefore moves the action-orphan, format-rule-orphan, and virtual-column-orphan counts too, not only the view-orphan count. This run: `unused_system_views.csv` -4 rows, `potential_action_orphans.csv` -2, `potential_format_rule_orphans.csv` -2.
  - Unresolved: the fix produced 178 new `navigation_edges.csv` rows against a rough pre-fix estimate of ~163-167. The estimate excluded group-action edges, and the finding above shows at least one such edge is active on this action set, but the ~11-row gap has not been traced to specific edges.
  - The predicate refactor (shared `NAV_FUNCTIONS`) cleared no orphan by itself — its 3 recovered `IF` branches (`Level 0 - Locations`, `Order Form Seeds List BUYING`, `Order Form Plants List`) all name views that were already reachable through other routes. It is justified by correctness, recovering branches the old hard-coded test silently dropped, and by removing the duplicated function-name list — not by any orphan it clears.
  - The `#page=map` CONCATENATE actions (13 of them, `parse_direct_navigation`) remain unhandled and are still misfiled as "Unknown pattern" in `action_targets_unparseable.csv`; untouched by this fix.
- 2026-08-30, `f4d931a` — `LINKTOFORM` unhandled in `action_target_parser.py`. `new_record_form` actions (69 in the test app) were entirely excluded by `process_action`'s action-type gate, and their navigation expression is not in `navigate_target` (empty for this type) but under the `"NavigateTarget"` key inside `with_these_properties` (JSON) instead. Confirmed by direct observation in the running app the same day: tapping "Copy to PlantDBLog and edit the copy" navigated to `PlantDB_LOG_Changes_Form`, the view named in that field. Added `new_record_form` to the gate; when `navigate_target` is empty and the action is `new_record_form`, `json.loads` the field and take `NavigateTarget`, guarded so a malformed or missing key leaves `nav_expr` empty rather than raising. Added `parse_linktoform` (view name is the quoted first argument; the column/value pairs that follow are ignored) and its dispatch branch, and added `LINKTOFORM` to `NAV_FUNCTIONS`. `edit_form` (39 actions) was checked and correctly excluded: 0 of 39 carry a `NavigateTarget` key — their JSON carries in-place edit-behavior keys instead (`DesktopBehavior`, `DesktopEditBehavior`, etc.), a different shape with no deep-link expression.
  - Verified by a full re-parse: all 366 pre-existing `action_targets.csv` rows are unchanged (0 removed, 0 modified), `action_targets_unparseable.csv` is unchanged at 13 (still all `#page=map`), and 451 rows now exist in `action_targets.csv` (+85, not +69 — five `new_record_form` actions have genuinely multi-branch nested `IF`/`SWITCH` expressions with more than one real target; `Level 0 - Go to` alone contributes 12). All four candidate views cleared, plus two more unexpectedly.
  - The four candidate views (`Nursery Form Completion`, `Images_Form - Seeds`, `Images_Form - ActivityTransplant`, `Images_Form - from Nursery Form Completion`) all cleared through group-action membership — the same route `48eead1` found once, now confirmed real and load-bearing rather than a one-off: e.g. `Images_Form - ActivityTransplant` on `ActivityTransplant_Detail` via group `TRANSPLANT 0 - GROUP`; `Images_Form - Seeds` via group `2 CHOICE - Add Image and Add seed weights activity` on a form-saved event; `Nursery Form Completion` and `Images_Form - from Nursery Form Completion` each via two further groups. See "Remaining work" below for what this settles and what remains open.
  - Two more views cleared unexpectedly, both via `Level 0 - Go to` and both via the already-known onClick route (`59db213`), not group membership: that action is `Do_Not_Display` but bound via `onclick_actions` on views `Level 0 - Locations`, `Level 0 - Locations - Record a Yield`, and `Level 0 - Locations OLD`. The two cleared views are `Nursery_Form Edit Existing` and `Water Tanks` — the latter despite the app's own `LINKTOVIEW("Water tanks")` call using the wrong case; already-existing case-insensitive matching resolved it, not a new fix.
  - View-orphan count: 67 → 60 (actual, after `48eead1`; 61 was that fix's pre-run prediction, recorded here so the prediction isn't mistaken for the record) → 54 with this fix (six cleared: the four candidates plus the two unexpected).
  - Coupling numbers for this run (see the pipeline-coupling note under `48eead1` above): `unused_system_views.csv` -12, `potential_format_rule_orphans.csv` -10, `potential_virtual_column_orphans.csv` -2 (its first appearance in this coupling — see the corrected note above), `potential_action_orphans.csv` unchanged (the same 2 actions `48eead1` already cleared; this fix added no further ones).
  - Two pre-existing parser defects were exposed (not introduced) by letting `new_record_form` actions reach the parser for the first time, and are recorded above under "Known defects" rather than fixed here: `parse_linktorow`'s greedy regex, and `parse_navigation_expression`'s first-match-only dispatch.
  - The four nonexistent-view names this fix surfaced are recorded above under "Known defects" as a live defect in the app itself, not in this tool.
- 2026-08-31, `e0530c8` — the editor's Primary Position is stored in the export as `Display_Overlay`, not as the literal string `'Primary'` (see `APPSHEET_BEHAVIOR.md`'s Position mapping table). `is_action_visible_in_table_view` rejected `Display_Overlay` on table views with a comment claiming they aren't supported, while a dead `if prominence == 'Primary': return True` branch twelve lines earlier claimed the opposite — the same rule written twice with contradictory answers, the live one wrong. Kirk built a purpose-made test action ("Go to web", table `NurseryDetails`, effect External, Position Primary) and confirmed visually in the app editor's preview that it displays on a table view as a floating button over the rows, disproving the rejection. `is_action_visible_in_table_view` now returns `True` for `Display_Overlay`; the dead `'Primary'` branch is deleted rather than merged, since it was never testing anything real. `actions_orphan_detector.py`'s narrower version of the same rule — admitting `Display_Overlay` on tables only when `action_type_plain_english == 'Navigate'` — was also disproved by the same test (the test action was External, not Navigate) and the condition removed. This was a second pass at a known problem, not a new discovery: `6994be5` (2025-12-02) already tried to fix `Display_Overlay` on table views, adding that now-removed `Navigate`-only restriction to `actions_orphan_detector.py`; that fix never touched `navigation_edge_generator.py` at all, despite it carrying the identical rejecting rule, which is why the sibling file's bug survived untouched for nine more months.
  - Verified by full re-parse. Say this plainly rather than implying the fix cleared anything: every parser output file is byte-identical (confirms no parsing was touched), `navigation_edges.csv` gained 82 edges and lost none, every added edge has a table-type source view and `Display_Overlay` prominence — but `potential_view_orphans.csv` and `potential_action_orphans.csv` are both byte-identical, and every coupled orphan file (`unused_system_views.csv`, `potential_format_rule_orphans.csv`, `potential_virtual_column_orphans.csv`) is unchanged too. Zero views and zero actions cleared. The fix removes a real class of false suppression; it simply changed no verdict in this app, because every target that suppression had been blocking was already reachable another way.
  - Of the 82 new edges, 56 are direct — the `Display_Overlay` action itself now shows on the table view. The other 26 are a `Display_Overlay` group action becoming visible on a table view, whose `Do_Not_Display` children then pass through unconditionally via the documented group bypass (`CONSOLIDATION_PLAN.md` section 1). Worth having on record so the 26 aren't mistaken later for prominence checks being skipped somewhere they shouldn't be: the children were never checked for prominence once inside a group, by design of that bypass, before or after this fix.
  - `action_dependency_analyzer.py` has the identical gap; recorded separately under "Known defects" since it was deliberately not touched by this commit.
- 2026-08-31, `496d5ed` — `parse_linktorow`'s regex, `LINKTOROW\s*\((.*)\)` with `re.search` and `re.DOTALL`, matched greedily past each call's own closing paren to the *last* `)` anywhere in the expression, rather than to that call's own matching close. Several `LINKTOROW` calls in one block (e.g. inside a `SWITCH`) was one way to trigger this — the first call's opening paren swallowing every later call — but not the only way: `Sync | Order (Complete)`'s expression holds a single `LINKTOROW([Nursery_ID], "NurseryForm2b")` call followed by trailing string concatenation (`&"&at="&(NOW()+1)`), and the same regex ran straight past that call's own close paren into the trailing text. This second action was found by the fix, not predicted by it — the original brief described only the multiple-call trigger. Replaced the single greedy regex with `re.finditer` over each `LINKTOROW(` occurrence, followed by a paren-depth scan (respecting quoted strings, including the smart quotes the existing code already handled) to find that call's own closing paren; the existing top-level-comma split and self-referential forced-sync skip are unchanged, just applied per call instead of once per expression.
  - Verified by full re-parse (`20260831_145854_AppsheetFarmyApp_for_Kirk_parse` against the `20260831_144803` baseline, counted with a real CSV parser): `action_targets.csv` 451 → 458 (2 bogus rows removed — the `Sync | Order (Complete)` row and the `Take Image Form Save Where to next` row described under "Known defects" before this fix — 9 real rows added, net +7); `navigation_edges.csv` 1832 → 1839 (+7, one edge per recovered target); `potential_phantom_view_references.csv` 57 → 56 (the two false entries matching the bogus rows removed, one genuine new phantom entry added — see "Five actions ... target views that do not exist" above). All five orphan-count files (`potential_view_orphans.csv`, `potential_action_orphans.csv`, `unused_system_views.csv`, `potential_format_rule_orphans.csv`, `potential_virtual_column_orphans.csv`) unchanged.
  - All 8 recovered `LINKTOROW` targets from `Take Image Form Save Where to next` name views that exist: `MyPlants_Detail`, `Nursery_Detail`, `ActivityHarvest_Detail`, `AmendmentPrep_Detail`, `Beds_Detail`, `Containers_Detail`, `Seeds_Detail`, `NurseryDetails_Detail`.
  - The 3 `LINKTOFORM` calls in that same expression are still dropped, lost to the separate first-match-only dispatch defect (`parse_navigation_expression`'s dispatch, recorded above under "Known defects"), which this fix does not touch.
- 2026-08-31, `43d9167` — `parse_navigation_expression`'s four-function tail (`LINKTOVIEW`, `LINKTOROW`, `LINKTOFILTEREDVIEW`, `LINKTOFORM`) was a chain of early returns: an expression mixing more than one navigation function resolved to whichever function the chain checked first, silently dropping the rest. Found in `Level 0 - Go to`: one `SWITCH` case holds `LINKTOVIEW("Nursery_Form")` alongside two `LINKTOFORM("MyPlants_Form", ...)` calls; dispatch resolved to `parse_linktoview` and never looked at that block again for the `LINKTOFORM` calls. Replaced the four early returns with independent `if <FUNCTION> in expr_upper` checks that each extend one shared targets list, so every function present contributes its targets; no dedup, so two calls naming the same view are two targets. Branches above the chain (direct navigation, bare column reference, IFS, IF) are unchanged.
  - Control: `Go to LinkToView` (~30 `SWITCH` branches, all `LINKTOVIEW`, so only one function is ever present) is byte-for-byte unchanged — 32 rows, identical multiset, confirming the fix leaves single-function expressions untouched.
  - Verified by full re-parse (`20260831_151553_AppsheetFarmyApp_for_Kirk_parse` against the `20260831_145854` baseline, counted with a real CSV parser): `action_targets.csv` 458 → 463 (+5, 0 removed, 0 modified), across two actions. `Level 0 - Go to` (+3): the two `LINKTOFORM("MyPlants_Form")` calls named above, plus one more instance of the same defect in a different `SWITCH` branch of the same action — undocumented by the original finding but the same action, and the same class of bug. `Take Image Form Save Where to next` (+2): two of its three `LINKTOFORM` calls (`PlantDB_LOG_Changes_Form`, `ActivitySeedWeights_Form`); the third, `Reminders_Form`, was already reachable pre-fix since it sits alone in its own `IF` branch with no competing function. All 5 recovered target views (`MyPlants_Form`, `MyPlants Food forest Deck`, `PlantDB_LOG_Changes_Form`, `ActivitySeedWeights_Form`) exist in `appsheet_views.csv`.
  - `navigation_edges.csv` 1839 → 1850 (+11, 0 removed) — more than one edge per recovered target, because both affected actions are available from multiple source views. `potential_phantom_view_references.csv` unchanged at 56. All five orphan-count files (`potential_view_orphans.csv`, `potential_action_orphans.csv`, `unused_system_views.csv`, `potential_format_rule_orphans.csv`, `potential_virtual_column_orphans.csv`) unchanged — no view or action cleared; `STATUS.md`'s prediction that `MyPlants_Form`/`Nursery_Form` were already reachable another route held.
  - `SWITCH` is still not decomposed as a branching construct: this fix lets each recovered target inside a `SWITCH` block be *found*, but `ifs_branch_index` and `ifs_branch_text` stay empty for them, unlike targets recovered from `IF`/`IFS` branches, which record which branch a target came from. No `SWITCH` decomposition was added by this commit; that gap remains open and is not tracked elsewhere in this file yet.
- 2026-09-01, `1c22881` — `parse_linktorow`'s two quote-tracking loops (the paren-depth scan for a call's own closing paren, and the top-level-comma scan separating `row_expr` from `view_name`) treated the typographic quotes “ (U+201C) and ” (U+201D) as independent, self-closing characters via a plain membership test (`char in ['"', "'", chr(8220), chr(8221)]`), rather than pairing them. A view name wrapped “like this” opened the scanner on “, and nothing ever closed it back: the close test required `char == quote_char`, and `quote_char` was still “, which no `”` satisfies. The scanner therefore stayed in string mode through the rest of the expression, the call's own closing paren was never counted, `end` stayed `None`, and the call was silently dropped by the `continue` right after the loop. **This is a regression introduced by `496d5ed`** (2026-08-31): the greedy regex it replaced did no quote tracking at all when locating a call's closing paren, so it could not have had this particular failure, even though it had its own, worse one. Fixed by replacing the membership test with an explicit opener-to-closer map (`{'"': '"', "'": "'", chr(8220): chr(8221)}`) in both loops, so “ closes only on its own ” partner; ” is deliberately not a key, since nothing should be able to open a string on it. The single curly quotes ‘/’ are deliberately excluded from the map too, since ’ doubles as an apostrophe in ordinary text and including it would reopen the identical class of bug wherever a view name contains one.
  - Also fixes a second, unrelated defect the same investigation surfaced: the self-referential "Force sync" pattern, `LINKTOROW([_THISROW], CONTEXT(VIEW))`, was already recognized and correctly skipped by `parse_linktorow`, but skipping produced zero targets with no way for `process_action` to tell "found nothing" from "found something and deliberately excluded it," so a correct exclusion was filed as an unparseable "Unknown pattern." Added an instance flag, `forced_sync_skipped`, reset by `process_action` immediately before each top-level `parse_navigation_expression` call and set by `parse_linktorow` at its existing `continue`; `process_action` now writes `"Forced sync — LINKTOROW to CONTEXT(VIEW), no navigation target"` instead of calling `classify_parse_failure` when the flag is set. Known limitation, not solved: an expression holding both a forced-sync call and a genuinely unparseable one will take the forced-sync label.
  - Verified by full re-parse of both apps, row counts confirmed with Python's `csv` module rather than `wc -l` or line-splitting (the Force sync expression itself has embedded newlines). Farmy (control, `20260901_090005_AppsheetFarmyApp_for_Kirk_parse` against `20260831_151553`): every one of the 16 output files byte-identical (`cmp -s`, not merely equal row counts) — Farmy's expressions contain no curly quotes, so this confirms the fix did not leak outside its intended scope.
  - Kankaku (subject): both the before and after parses used the same `260831 1809 Kankaku V18 baseline` export (2026-08-31) — no new export was pulled today. The pre-fix side (`20260901_085747_..._parse`) was produced by `git stash`-ing this fix, parsing, then popping the stash and re-parsing for the post-fix side (`20260901_085853_..._parse`). **This makes `20260901_085853_...` a same-export re-parse for verifying this specific fix, not a reference parse of Kirk's current app** — a copy of it has since been saved as the standing regression reference, satisfying `RELEASE_CHECKLIST.md` section C's regression-guard half, but it does not satisfy that section's discovery half, which needs a fresh export from the live app, not a re-parse of an existing one. `action_targets_unparseable.csv`: 6 → 1 — exactly the 5 curly-quote rows go, and the sole remaining row is "Force sync," carrying the new reason string rather than one of the five. `action_targets.csv`: 0 rows removed or modified (verified by full-row multiset comparison, not just the count), 7 rows added — one per recovered `LINKTOROW` call: 3 single-call actions (`Go to card stats` → `Card Stats`; `Go to card stats 2` → `Card stats 2`; `View Ref (Show WD stats) 2` → `Stats_Detail`) plus 2 branches each from the two `IF`-wrapped actions (`Go to long-term statistics`, `Go to short-term statistics`, each → `Overall_Detail` and `Overall_Detail J`). `navigation_edges.csv`: 0 removed, +31 added — more than one edge per target, since some of the affected actions are available from multiple source views (`Overall_Detail` and `Overall_Detail J` each pick up 10).
  - Orphan counts, all moving the direction the pipeline coupling predicts (see the `48eead1` entry above) and none increasing: `potential_view_orphans.csv` — the same 3 previously-flagged views (`Card stats`, `Card stats 2`, `Overall_Detail J`) clear, and since 0 remain, the file is no longer written at all — see "`view_orphan_detector.py` also writes no `potential_view_orphans.csv` on a zero result" above, found while checking this. `unused_system_views.csv`: -2 (`Overall_Detail`, `Stats_Detail`), 0 added. `potential_action_orphans.csv`: unchanged, same 2 actions. `potential_virtual_column_orphans.csv`: 29 → 2, 0 added — checked for residue rather than assumed: all 27 cleared columns are on table `Overall` (25) or `Stats` (2), and every one of the 27 appears verbatim (as `Table[Column]`) in `Overall_Detail`'s or `Stats_Detail`'s `referenced_columns` field in the post-fix `appsheet_views.csv`, so the entire clearance is accounted for by the two views leaving `unused_system_views.csv`; zero residue. `potential_format_rule_orphans.csv`: absent (0) both before and after.
  - `potential_phantom_view_references.csv` stayed at 2 rows, unchanged — deliberately not predicted in either direction beforehand, since one recovered target (`Card Stats`) names the same view as the app's actual `Card stats`, differing only by case. Traced rather than assumed: `phantom_view_reference_detector.py`'s action-targets-based check (`find_action_phantoms_from_targets`) already lowercases both sides before comparing, so the case difference never registers there and the recovered target correctly produced no new phantom row. The 2 rows that are already flagged come from a different code path in the same file — `is_phantom_reference`'s `CONTEXT()` branch, which compares case-sensitively by design (its own comment claims "`CONTEXT()` is case-sensitive in AppSheet"). That comment is the defect, not a justification: it is the same defect the "`phantom_view_reference_detector.py` matches view names case-sensitively, producing false positives" entry already records above, for these same 2 rows — see that entry for the evidence, not restated here. This fix leaves that defect exactly as it was; the two code paths in this one file disagree with each other, and the `CONTEXT()` one is the one that is wrong.
  - The "Navigation expressions using typographic (curly) quotes..." known-defects entry that described this bug, including its "Kankaku's 3 potential view orphans and 2 phantom references... are downstream of this" caveat, is removed as fixed and superseded by the verification above. The two Task 3 findings that fix did not cover (`parse_linktoform`/`parse_linktofilteredview`'s identical blindness, and `actions_parser.py`'s inconsistent curly-quote normalization) are recorded separately above under "Known defects."
- 2026-09-01, `84a651d` — `CONSOLIDATION_PLAN.md` step 1: extracted `action_visibility.py`, a behavior-preserving translation of all three existing "is this action visible here" implementations (`navigation_edge_generator.py`/NEG, `actions_orphan_detector.py`/AOD, `action_dependency_analyzer.py`/ADA) into separate, call-compatible functions — `self`/instance state replaced by explicit parameters, every disagreement between the three (`CONSOLIDATION_PLAN.md` section 2), including the `Do_Not_Display` `.replace('_',' ')` case bug, preserved exactly as it stood. Only ADA's caller was switched over: its `is_action_visible_in_view` method now delegates to the shared `is_visible_in_view_ada`, preserving ADA's function boundary (the `available_actions` gate stays in `analyze_view_dependencies`, not pulled into the shared function, per section 2's Pre-gates note). `navigation_edge_generator.py` and `actions_orphan_detector.py` are untouched; step 2 (case-bug fix, AOD switch) and step 3 (NEG switch) remain open.
  - **Verified by a 419,750-pair differential comparison of ADA's own answer, old implementation vs. new**, via a throwaway script (not committed) that reproduced the pre-switch method body verbatim (checked against `git diff`) and compared it against `action_visibility.is_visible_in_view_ada` for every `(action, view)` pair derivable from each app's parsed CSVs: Farmy 970 actions × 319 views = 309,430 pairs, Kankaku 560 actions × 197 views = 110,320 pairs, **0 disagreements in either app**. This is the test that actually verifies the step, because nothing programmatic consumes ADA's answer (`CONSOLIDATION_PLAN.md` section 1) — it feeds only the interactive dependency browser.
  - A full re-parse of both apps against their saved references (Farmy `20260901_090005_...`, Kankaku `20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881`) was also run, row counts confirmed with Python's `csv` module: every output file byte-identical in both apps, as predicted. **State this plainly rather than letting it stand as evidence:** this check is weak for a step like this one — it would have come back zero even if the extraction had been wrong, since ADA writes no CSV. The differential comparison above is what verifies it.
  - **Only ADA's path through `action_visibility.py` is exercised by this commit.** The NEG and AOD functions in the new module (`is_visible_in_view_neg` and its three per-view-type helpers, `is_visible_in_views_aod`) are unverified transcriptions until steps 3 and 2 switch those callers over — each will need its own differential check against its own original implementation when its step runs; a zero CSV diff will not be sufficient evidence for either, for the same reason it wasn't sufficient here.
  - **Caution for whoever runs step 3:** NEG's original `is_action_visible_in_view` and its three helpers mutate `self.stats['edges_blocked_by_visibility']` at nine call sites (corrected to eight by step 3's grep — see `CONSOLIDATION_PLAN.md` block A0, and the step 3 entry below). The extracted `is_visible_in_view_neg` takes an optional `stats` dict parameter instead of mutating an instance directly, and it is a no-op if the switch's call site forgets to pass `self.stats` through. In that failure mode, every `navigation_edges.csv` row and every downstream CSV stays byte-identical, and a pairwise verdict comparison (this commit's method, repeated for NEG) still passes — neither check would catch it, since the counter is a side effect the return value doesn't carry. Step 3's verification must compare `self.stats['edges_blocked_by_visibility']`'s final value before and after as a third, separate check, not assume the other two cover it.
- 2026-09-01, `6115f30` — `CONSOLIDATION_PLAN.md` step 2: fixed the `Do_Not_Display` case bug in `action_visibility.is_visible_in_views_aod` (the AOD strategy) and switched `actions_orphan_detector.py` to call it. **Mechanism, restated from `CONSOLIDATION_PLAN.md` section 3:** the original compared `action_prominence.replace('_', ' ')` against spaced literals; three of four prominence values round-trip correctly through that transform, but `'Do_Not_Display'` becomes `'Do Not Display'` (title case), which never matches the comparison target `'Do not display'` (sentence case), so the intended Hide exclusion on deck/gallery views never fired. **This is not a case-insensitivity problem and was not fixed as one** — per section 4's second exclusion, the fix is to stop transforming the string and compare the real underscored values directly, which is what this commit does.
  - **Scope decision:** fixed in the AOD strategy only. `is_visible_in_view_ada` carries the identical bug, deliberately left — ADA has been live on `action_visibility.py` since step 1 (`84a651d`), so fixing its copy now would change what the interactive dependency browser reports, a real behavior change outside what step 2 predicts or what step 2's verification (a CSV diff) could catch, since ADA writes no CSV. Recorded as its own open item above under "Known defects."
  - **Verified by a 1,530-action differential comparison of AOD's own answer, old implementation vs. new** (Farmy 970 actions, Kankaku 560 actions; existential, one verdict per action, not per (action, view) pair, per `CONSOLIDATION_PLAN.md` section 1): **64 True→False verdict flips, 0 False→True** — no stop condition hit.
  - **Full accounting of all 64 flips**, traced against `find_orphan_candidates`' other gates rather than assumed: 44 were already excluded by `has_reachable_reference` or `is_event_action` (43 in Farmy, 1 in Kankaku — Kankaku's sole flip, `WD deck to detail group action`, is both referenced elsewhere and an event action); 18 (Farmy only) are system-generated actions (`is_system_generated == 'Yes'`) that `find_orphan_candidates` never considers at all, since it iterates `self.user_actions`, not `self.all_actions` — found while tracing, not anticipated going in; and 2 newly qualify as orphans, matching exactly the 2 rows the full re-parse actually added.
  - **State plainly what the 18 system-generated flips mean, so the 2-row CSV diff is not mistaken for the whole effect of this fix:** the bug had been reporting system-generated `Add` actions (and one `View Ref (NurseryDetails_Seed)`) as wrongly "visible" on deck and gallery views via the broken exclusion; fixing it correctly reverses that for all 18, and it changes no downstream verdict for those 18 only because they never reach orphan consideration in the first place — the same shape as `e0530c8` (2026-08-31): a real class of wrong answer removed, most of its instances clearing no orphan because something else already made the right call moot.
  - **CSV diff, accounted for row by row:** `potential_action_orphans.csv` gained 2 rows in Farmy — `Add Go to NurseryDetails_Form` and `NurseryDetails_Detail - UniqueRows`, both table `NurseryDetails` (85 → 87 rows, 0 removed, confirmed by a `(action_name, source_table)`-keyed diff, not by `action_name` alone — see the new Known-defects entry above on why bare-name diffing is unreliable in this export). Kankaku's file is unchanged, 2 → 2. Every other output file in both apps is byte-identical to its reference, row counts confirmed with Python's `csv` module.
- 2026-09-01, `66ddb54` — `CONSOLIDATION_PLAN.md` step 3: switched `navigation_edge_generator.py`'s two call sites (`process_regular_action`, and `process_view`'s `execute_group` branch) to delegate to `action_visibility.is_visible_in_view_neg`, passing `stats=self.stats` through so `edges_blocked_by_visibility` keeps incrementing exactly as the original did. The four old methods (`is_action_visible_in_view` and its three per-view-type helpers) are retained as dead code, marked with a comment, pending step 3b's removal — see `RELEASE_CHECKLIST.md` section D.
  - **Increment-count figure corrected:** the `84a651d` caution paragraph above and `RELEASE_CHECKLIST.md`/`CONSOLIDATION_PLAN.md` all previously stated nine `+= 1` sites for NEG's visibility function. Step 3's grep found eight, not nine (`self.stats['edges_blocked_by_visibility'] += 1` at lines 211, 219, 246, 252, 281, 298, 312, 317 of the pre-switch file); corrected in all three documents.
  - **Verified by a 204,827-pair differential comparison of NEG's own answer, old implementation vs. new** (Farmy 463 navigation targets × 319 views = 147,697 pairs; Kankaku 290 navigation targets × 197 views = 57,130 pairs), via a throwaway script (`step3_neg_diff.py`, not committed) that called the retained-dead `is_action_visible_in_view` and the new shared `is_visible_in_view_neg` on every `(action, view)` pair derivable from each app's parsed CSVs: **0 disagreements in either app.**
  - **CSV byte-identity:** fresh copies of the saved references were re-parsed with NEG standalone before and after the switch; `navigation_edges.csv` came back byte-identical (`cmp` pass) for both apps. Data-row counts, confirmed with Python's `csv` module: Farmy 1850 → 1850, Kankaku 592 → 592.
  - **Counter match:** `edges_blocked_by_visibility` — Farmy 4020 (pre-switch) → 4020 (post-switch); Kankaku 1363 (pre-switch) → 1363 (post-switch). Both unchanged, confirming the `stats=self.stats` wiring is correct — this is the check the `84a651d` caution paragraph warned the other two checks cannot substitute for.
  - Downstream orphan files were not directly verified. This entry relies on the pipeline coupling documented in the `48eead1` entry: those files are deterministic given `navigation_edges.csv`. If any had moved while `navigation_edges.csv` was byte-identical, that would be a finding about the coupling, not about step 3.

## Remaining work on the false positives

- 79 Related-column cases were left ambiguous by the 2026-08-30 fix, because several views share the same table or slice as their data source and nothing in the data says which one is the display view.
- Two columns' resolved view is not rendered by any view's `view_columns`, and were left flagged deliberately rather than guessed at.
- Open question: should the parser report an unresolvable reference — an ambiguous match, or a value that names neither a table, slice, nor view — rather than staying silent about it, so a reader can see that a reference was found but not resolved.
- Whether group-action membership is a real, load-bearing invocation route for `Do_Not_Display` actions is no longer open — `48eead1` found one such route and `f4d931a` found four more, clearing all four of its candidate views this way. What remains open is which specific actions still lack any identified route. Using the narrower, reproducible definition — a `Do_Not_Display` action with a non-empty `target_view` somewhere in `action_targets.csv` (i.e., it navigates at all) — 86 of the app's 414 `Do_Not_Display` actions qualify, and of those, 32 currently have no identified route (no onClick binding, no group membership, no row in `navigation_edges.csv`) and should be re-examined before being treated as unreachable, reflecting the post-`f4d931a` state (20 of the 86 are `new_record_form` actions, which only parse as of this fix). A broader count is a different thing and shouldn't be folded into the above: 115 `Do_Not_Display` actions appear in `action_targets.csv` at all, including group-container rows whose own `target_view` is left empty by design; of those, 61 have no identified route.

## Where the code lives

- This repository is the authoritative working copy. Two older copies exist elsewhere on my machine, renamed with an "OLD DO NOT USE" prefix; they contain no work that is not already published.
- Users update by re-downloading the ZIP from GitHub, which is why folders named `appsheet_parser_and_orphan_detector-main` are common.

## Next steps after the bug fixes

Plan from the July 2026 project document, unchanged:

1. A `CLAUDE.md` at this repository root describing the CSV schemas, which analyzer answers which category of question, the instruction to call analyzer methods directly rather than driving the interactive menus, and the known blind spots. Ship an `AGENTS.md` with the same content for non-Anthropic tools.
2. Extend the visibility layer to the backing Google Sheet, via an Apps Script dump of formulas and displayed values.
3. A non-interactive query mode with JSON output, canned question recipes, and optionally `SKILL.md` packaging — only if a demonstrated need appears.

## Private working notes

Reproduction details, test data locations, correspondence and the machine-wide inventory are kept outside this repository, at:
`/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/NOTES.md`
