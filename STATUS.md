# Project status

Last updated 2026-08-30. Records what is outstanding in this project between working sessions.

## Known defects

### Orphan detector false positives — view switched at runtime, no navigation link

Of the four false-positive categories originally reported, three are fixed (see "Recently fixed" below). One remains open.

- The view in question is never declared in any dashboard's entries at all — this is not a shortfall in `process_dashboard_containment`, which works correctly and emits an edge for every view a dashboard declares. Instead, the view is switched in at runtime by `set_columns` actions that write a value into a column, combined with sibling views whose show-if conditions test that column. There is no navigation link of any kind, so no edge exists to be followed.
- Detecting this would mean inferring intent from an action's written value and a view's condition. This was investigated and not attempted: the pattern does not hold reliably enough to detect on its own, and a rule loose enough to catch it would exempt views with no actual evidence of being reachable.

### Orphan detector false positives — unhandled navigation functions (LINKTOFORM only)

- An earlier version of this document stated that `LINKTOFORM` appears 77 times as an unhandled navigation function. That was wrong, and the error is worth recording. `LINKTOFORM` does not appear in `navigate_target` at all. It appears in the `with_these_properties` field of 69 actions whose type is `new_record_form` — an action type that `process_action` filters out before any parsing occurs, and a field the navigation parser does not read. The original figure came from counting occurrences across the whole documentation export rather than in the field the parser uses.

- Confirmed a defect, 2026-08-30, by direct observation: tapping "Copy to PlantDBLog and edit the copy" on `PlantDatabase_Detail` navigated to `PlantDB_LOG_Changes_Form`, the view named in the action's `with_these_properties` field. `LINKTOFORM` does navigate to the named form view, so excluding all 69 `new_record_form` actions from the reachability graph drops real navigation edges. Not yet fixed. 6 actions name 4 currently-flagged views this way: `Nursery Form Completion`, `Images_Form - Seeds`, `Images_Form - ActivityTransplant`, and `Images_Form - from Nursery Form Completion`.
- Caveat on the observation: the view observed, `PlantDB_LOG_Changes_Form`, is system-generated (`created_by: System`); all four flagged targets above are author-created forms (`created_by: App owner`). The same behaviour is expected for them but was not directly observed — this is inference, one step beyond the evidence.
- Second caveat: all 6 of those actions are `Do_Not_Display`. Parsing `LINKTOFORM` is therefore necessary but may not be sufficient to clear the four views; whether they actually clear depends on the group-membership question already noted under "Remaining work on the false positives" below.
- New finding from the same file: 4 of the 69 `new_record_form` actions name form views that do not exist in `appsheet_views.csv` — `Seeds Form` (the actual view is `Seeds_Form`), `ActivityForm - Transplant`, `ActivityForm - Germination`, `ActivityForm Observation`. These look like stale names left after view renames, which would mean those buttons are broken in the app. Not yet verified by observation.
- `LINKTOPARENTVIEW` is recognized and explicitly marked unparseable, which is correct behaviour rather than a gap.
- `phantom_view_reference_detector.py` contains a richer extractor that does understand `LINKTOFILTEREDVIEW` and `LINKTOFORM`, but it sits on a fallback path that only runs when `action_targets.csv` is absent, which never happens in a normal run.
- The `LINKTOFILTEREDVIEW` gap described in this section as of the 2026-08-30 review, and the nested-expression claim made alongside it, were wrong in a different way and are recorded under "Recently fixed" below.

### December 2025 User Settings work is unverified

The `USERSETTINGS()` parsing, User Settings orphan detection and broken-reference detection shipped 2025-12-24 with an explicit public caveat that more testing was needed. That testing has not happened.

## Recently fixed

- 2026-08-25, `2f0cb81` — the Windows `OverflowError` crash. The wider concern noted in the old entry is also addressed: a shared `csv_limits` module is now imported by all sixteen modules that read CSVs, so standalone entry points are no longer exposed.
- 2026-08-30, `ad7a830` — view names in the `referenced_views` field came from a Python `set`, so their order varied between runs under Python's randomized hash seed, making parse output non-reproducible. Now sorted. Deduplication unchanged.
- 2026-08-30, `5b2c06b` — false positive category 4, slices referenced in column-level expressions. `parse_column()` extracted the Suggested Values formula but never assigned it to the `suggested_values` field, which the slice orphan detector scans, so that field was empty for every column in every app. Any slice referenced only through a Suggested Values expression was reported as an orphan.
- 2026-08-30, `59db213` — false positive category 1, views reached via actions. The specific cause was custom-canvas Layout onClick bindings: an action invoked by tapping a view element is normally set to `Do_Not_Display`, and the edge generator treated that prominence as an unconditional dead end. `views_parser` now records onClick-bound actions and the veto has a scoped exception for them. The rule is unchanged for every other case.
- 2026-08-30, `90555be` — false positive category 2, views referenced through Related virtual columns, PARTIALLY fixed. A List-type column's `ReferencedTableName` is now extracted and resolved to a view when exactly one view has that value as its data source. Where several views share it, nothing is resolved and no edge is created, because choosing among sibling Detail, Form and Inline views would be a convention rather than a fact. See "Remaining work on the false positives" below.
- 2026-08-30, `fa68783` — a latent crash in `column_orphan_detector.py`, exposed by the fix above. `write_results_to_csv()` writes from a fixed fieldnames list while each row is a full copy of a column dict, so any newly added column field raised `ValueError`. Left without `extrasaction='ignore'` deliberately, so a missing field fails loudly rather than being dropped silently.
- 2026-08-30, `748e329` — `check_context_conditions` in `navigation_edge_generator.py` compared view types case-sensitively. `CONTEXT("ViewType")` conditions carry the app author's literal casing while `appsheet_views.csv` stores `view_type` in lower case, so every such condition failed and no edge was created. Eleven rows in the test app were affected. Both sides are now normalized. The fix produced two new edges but changed no orphan count in that app, because the affected paths are also blocked by unrelated visibility gates.
- 2026-08-30, `48eead1` — `LINKTOFILTEREDVIEW` unhandled in `action_target_parser.py`, which recognized only `LINKTOVIEW` and `LINKTOROW`. 34 of the 36 actions using it fell through `parse_navigation_expression`'s dispatch chain into `action_targets_unparseable.csv` as "Unknown pattern"; the other 2 were silently discarded inside `IF` branches by a second, independent copy of the same function-name list in `parse_if_expression`'s `has_nav_true`/`has_nav_false` check. The nested-expression claim recorded above under "unhandled navigation functions" was wrong: nested `IF`s were already traversed correctly by recursion, and the branch was lost to that hard-coded substring test, not to nesting depth. Added `parse_linktofilteredview` and its dispatch branch, and replaced the hard-coded test with one shared `NAV_FUNCTIONS` tuple (`LINKTOVIEW`, `LINKTOROW`, `LINKTOFILTEREDVIEW`) and a helper used by both branches, so the two lists cannot drift apart again. Verified by a full re-parse of the test app: 34 rows left `action_targets_unparseable.csv`, 37 rows were added to `action_targets.csv` (34 from the dispatch fix, 3 recovered `IF` branches), all 34 newly-parsed target view names matched an existing view, and six previously-flagged views cleared.
  - A seventh view cleared unexpectedly: its only naming action is `Do_Not_Display` with no onClick or event binding, but that action is a member of group action "TRANSPLANT 0 - GROUP", itself available (`Display_Overlay`) on its source view — a real, previously-unidentified invocation route. Only one view now remains flagged for this reason, "Order Form Seeds List BUYING"; earlier reasoning in this project had treated two views as unexplained, having checked only onClick and event bindings. A `Do_Not_Display` action has a third possible route, membership in a group action that is itself reachable, and that check had not been made. See "Remaining work" below.
  - Pipeline coupling found during verification, previously undocumented: `unused_system_views.csv` is written from `navigation_edges.csv` reachability by `view_orphan_detector.py`, then read by both `actions_orphan_detector.py` and `format_rule_orphan_detector.py` to gate their own orphan checks. Any change to navigation edges therefore moves the action-orphan and format-rule-orphan counts too, not only the view-orphan count. This run: `unused_system_views.csv` -4 rows, `potential_action_orphans.csv` -2, `potential_format_rule_orphans.csv` -2.
  - Unresolved: the fix produced 178 new `navigation_edges.csv` rows against a rough pre-fix estimate of ~163-167. The estimate excluded group-action edges, and the finding above shows at least one such edge is active on this action set, but the ~11-row gap has not been traced to specific edges.
  - The predicate refactor (shared `NAV_FUNCTIONS`) cleared no orphan by itself — its 3 recovered `IF` branches (`Level 0 - Locations`, `Order Form Seeds List BUYING`, `Order Form Plants List`) all name views that were already reachable through other routes. It is justified by correctness, recovering branches the old hard-coded test silently dropped, and by removing the duplicated function-name list — not by any orphan it clears.
  - The `#page=map` CONCATENATE actions (13 of them, `parse_direct_navigation`) remain unhandled and are still misfiled as "Unknown pattern" in `action_targets_unparseable.csv`; untouched by this fix.

## Remaining work on the false positives

- 79 Related-column cases were left ambiguous by the 2026-08-30 fix, because several views share the same table or slice as their data source and nothing in the data says which one is the display view.
- Two columns' resolved view is not rendered by any view's `view_columns`, and were left flagged deliberately rather than guessed at.
- Open question: should the parser report an unresolvable reference — an ambiguous match, or a value that names neither a table, slice, nor view — rather than staying silent about it, so a reader can see that a reference was found but not resolved.
- The ~70 `Do_Not_Display` actions with no identified onClick or event binding should be re-examined for group-action membership before any of them is treated as unreachable — the 2026-08-30 `LINKTOFILTEREDVIEW` fix above found one such action invoked only through a group.

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
