# Project status

Last updated 2026-09-05. Records what is outstanding in this project between working sessions.

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
- **These five are specific cases, not a total.** They were found by two commits (`f4d931a`, `496d5ed`) tracing particular `LINKTOFORM`/`LINKTOROW` calls, not by a survey of every phantom reference in the app. Farmy's `potential_phantom_view_references.csv` currently holds 16 rows where an action's `navigate_target` names a missing view (`type=Action`, `field=navigate_target`), and 56 rows in total once every phantom-reference category is counted (actions, `only_if_condition` text, and column-level references) — counted directly against the current parse (`20260902_131151_AppsheetFarmyApp_for_Kirk_parse`). The five above are the ones this project has specifically investigated and named; the rest are real, correctly-surfaced findings this section has not individually narrated.

### Manual action-list exclusion may not be enforced outside deck views

- `action_display_mode` is present for every view type in the export, but `navigation_edge_generator.py` reads it only inside `is_action_visible_in_deck_view` — see the open question under "Manual action lists" in `APPSHEET_BEHAVIOR.md`. Not investigated.

### Seven modules have had no logic change since they were written — a blind spot, not a clean bill of health

- `view_orphan_detector.py`, `view_dependency_analyzer.py`, `slice_orphan_detector.py`, `format_rules_parser.py`, `format_rule_orphan_detector.py`, `column_dependency_analyzer.py`, and `action_dependency_analyzer.py` have never had a logic change since being written, per `git log` on each file (only the mechanical `csv_limits.py` import touches any of them). "Untouched" is ambiguous: it means either the code is solid, or it has never been exercised against real, varied data, and git history alone cannot tell the two apart. `action_dependency_analyzer.py` has already been shown to be the second case, not the first — see the `action_visibility.py`/`is_visible_in_view_ada` Display_Overlay entry under "Recently fixed" below: never modified, and wrong the whole time it sat unmodified. **`view_orphan_detector.py` is now a third confirmed case of the second kind — see its own entry below, added 2026-09-02.** **`view_dependency_analyzer.py` has now also been audited (2026-09-03 through 2026-09-04, three sessions) — see its own entries below** (private working note, kept outside this repository: `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260903_view_dependency_analyzer_code_audit.md`). **`column_dependency_analyzer.py` has now also been audited (2026-09-04) — see its own entries below** (private working note, kept outside this repository: `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260904_column_dependency_analyzer_code_audit.md`). The other three — `slice_orphan_detector.py`, `format_rules_parser.py`, `format_rule_orphan_detector.py` — have still not been examined; nothing here should be read as implying they are sound.
- The pattern found across the wider history bears on how much confidence that absence of past fixes should give: `navigation_edge_generator.py` and `action_target_parser.py` were each untouched (beyond the mechanical `csv_limits` import) for months, then took every one of their real fixes inside a single 48-hour window, 2026-08-30 to 08-31, when the suite was first stress-tested against a second app in depth. In this project's own history, a long gap since the last fix has meant "not yet tested against different data" at least as often as it has meant "correct."

### Column-level `Show_If` is never consulted, so inline actions on a hidden column are counted as reachable

- An inline action attaches to a column (`attach_to_column`) and renders beside that column's row. If the column does not render — its own `Show_If` being false in the current state — the button never appears and its navigation edges are dead. Nothing in the reachability path consults column `Show_If`. `view_orphan_detector.py` loads `appsheet_columns.csv` into `self.columns_by_table` and never reads it again (see the module audit entry above); this is a consequence of that, not a separate omission. The platform rule belongs in `APPSHEET_BEHAVIOR.md`; what this entry records is that this code does not implement it.
- Confirmed instance, found by hand in the app editor 2026-09-03, not by the tool. Kankaku's `Schedule position label` column on the `Definition` table carries `Show_If`: `and(CONTEXT("ViewType") <> "form",INDEX(Cram[Enum],1)<>"On")`. Five actions attach to that column; two of them, `Group to DW card statistics` and `Group to WD card statistics`, carry the condition `INDEX(Cram[Enum],1)="On"`. The column exists only when Cram is off, the buttons only when Cram is on. The two cannot both hold, so neither button can ever appear. Observed in the running app: in cram the `Schedule position label` row is absent and no button attached to it appears; out of cram the row is present and shows one button, `Visualize schedule 2`, whose condition is `true`.
- **Consequence for a clearance already recorded in this file.** The 2026-09-02 "Recently fixed" entry for `Card stats` reports it reachable via `D to W → D to W_Detail → Definition → Card Stats`, the last hop supplied by `Go to card stats` inside `Group to DW card statistics`. That hop is dead in the app. `Card stats` is not reachable, and the tool cleared it as a false NEGATIVE — the first of that direction recorded here; every earlier false-positive category ran the other way. The parse is right that the edge exists and `1c22881`'s account of why it appeared is right; what is wrong is treating an edge's existence as reachability.
- Second, independent consequence: the same expression's first clause, `CONTEXT("ViewType") <> "form"`, means the column never renders on a form view, so the `Main Data_Form` edges for these actions are dead as well — for a reason separate from whether form views display actions at all (`RELEASE_CHECKLIST.md` section A's form item, and `APPSHEET_BEHAVIOR.md`'s "Established behavior").
- **Measured 2026-09-03, against the two current reference parses.** Kankaku: 148 of 315 `Display_Inline` actions attach to a column carrying a non-empty `Show_If` (146 distinct action names); those actions are named by 126 `navigation_edges.csv` rows, reaching 21 distinct target views, 8 of which have no incoming edge from outside this set (`Card Stats`, `Card stats 2`, `Dictionaries`, `Graphic`, `Graphic and card stats`, `Graphic and card stats pre-activation`, `Stats_Detail`, `Stats_Detail 2`). Farmy: 79 of 301 (76 distinct names), 527 edge rows, 31 distinct target views, 3 with no other incoming edge (`Harvests_Other_Detail`, `MyPlantsReadOnly_Detail`, `Seeds READONLY_Detail`). So 11 views across the two apps have reachability resting entirely on edges whose liveness this suite cannot assess.
- **What the census says about the fix-versus-document fork.** Reading all 148 Kankaku pairs, only 2 are genuine contradictions — an action condition and a column `Show_If` testing the same variable in opposite senses — and both are the pair named above. Every other pair either tests different variables or is data-dependent (`count(Archive[Word])>0`, `[Britannica true/false]`, `INDEX(Cram[Tag],1)=...`), which no static analysis can settle from the app definition alone. The two halves are therefore different sizes: detecting unsatisfiable combinations is a narrow mechanical check, while evaluating column conditions generally is not available. Fork deliberately left open.
- **Fork settled, 2026-09-05 (Kirk, Fable planning session), along the line the census drew:** general `Show_If` evaluation is an ACCEPTED LIMITATION and stays recorded here and in CLAUDE.md as it is; the narrow mechanical half — literal contradictions between a column `Show_If` and an attached action's condition over the same variable — is scoped phase-one work, output to a NEW file, in `RELEASE_CHECKLIST.md` section B ("Unsatisfiable column-`Show_If` / attached-action-condition pairs"). This entry stays under Known defects because the limitation it records does not go away when the narrow check ships.
- Caveat on snapshots: the `Show_If` above was read from the live app 2026-09-03, while the attach-to-column and action data come from the 2026-08-31 frozen export. They agree here, but they are not the same snapshot.
- The contradictory pair is a live instance of the class `RELEASE_CHECKLIST.md`'s "Deliberately not on this list" records as a post-publication candidate: AppSheet accepts both expressions, neither is malformed, and only their combination is unsatisfiable.

### `column_parser.py` never populates the `_if` qualifier fields it emits — `show_if`, `required_if`, `editable_if`, `valid_if`, `reset_if`

- `appsheet_columns.csv` carries a `show_if` column that is empty on every row in both apps (0 of 1064 Kankaku rows non-empty). Per `column_parser.py` lines 265–350 it is never written from the parsed Show_If. The data exists only inside the `type_qualifier` JSON blob, under key `Show_If`, so any consumer must parse JSON rather than read the field. Found 2026-09-03. A field created and left unpopulated, not a design decision.
- A secondary text field, `type_qualifier_formulas`, carries a human-readable `Show_If:` fragment, but it disagrees with `type_qualifier` on 4 Kankaku rows (355 vs 359 non-null). Which is correct is not established.
- The same root cause reaches four more fields, not just `show_if`: `required_if`, `editable_if`, `valid_if`, and `reset_if` are also empty in every row of both parses. `column_parser.py`'s `type_formula_fields` mapping (lines ~287–297) extracts all five keys — `Show_If`, `Required_If`, `Editable_If`, `Valid_If`, `Reset_If` — out of `type_qualifier` for reference-scanning only, and never writes any of the five into the top-level row. One unreported root cause behind five empty fields, not one. Found 2026-09-03, generating `CLAUDE.md`'s CSV reference section.
- Consequence in `column_dependency_analyzer.py`: four of `categorize_references`'s eight checks (`show_if`, `valid_if`, `required_if`, `editable_if`) are dead code testing permanently empty strings. The module's only live categorisation path is a separate `type_qualifier_formulas` text-marker branch that re-derives these labels by pattern-matching rendered text (code audit, 2026-09-04).

### Malformed `type_qualifier` JSON silently drops two Kankaku columns

- `Settings[Update success]` and `Settings[Update success J]` have unescaped quotes inside the `Show_If` string in their `type_qualifier` blob, so `json.loads()` fails on them. Their Show_If is visibly non-empty in the raw field but uncountable by any consumer that parses the blob. Found 2026-09-03. Two rows in one app; the frequency in other apps is unknown.

### 23 Farmy inline actions attach to columns that do not exist

- 23 of Farmy's 301 `Display_Inline` actions with a non-empty `attach_to_column` name a column that is not present as a `column_name` for that `table_name` in `appsheet_columns.csv`, mostly TS-prefixed names. This is the phantom-reference pattern applied to columns rather than views, and nothing currently surfaces it — `potential_phantom_view_references.csv` covers views only. Found 2026-09-03; excluded from that day's Show_If join rather than assumed empty. Whether these are stale names, a parser gap, or a naming convention this suite does not model is not established, and it should be before anything is reported to Leon.

### `format_rule_orphan_detector.py`'s `run_analysis()` returns nothing

- Its four sibling orphan detectors return a value from `run_analysis()`; this one has no `return` statement and always yields `None`. Found 2026-09-03 while generating the module reference for `CLAUDE.md`. Whether any caller depends on that return value is not established, and should be checked before this is treated as user-visible. Noted because it is the same shape as the `action_dependency_analyzer.py` finding above: an inconsistency sitting unexamined in a module with no logic change since it was written.

### `view_orphan_detector.py` never evaluates `CONTEXT()` — systematically more permissive than sibling modules, under-reporting orphans in both apps

- Confirmed by full code audit, 2026-09-02, the first of the six never-examined
  modules in the entry above to actually be audited (report, kept outside this
  repository as a private working note:
  `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`).
  The module's own logic has been stable across the whole window this project has
  been active — no commit has touched it since the initial commit, apart from
  the mechanical `csv_limits` import and one Windows-only field-size fix
  (`2f0cb81`).
- **The confirmed finding:** reachability is a plain, root-seeded BFS over
  `navigation_graph`, built entirely from `navigation_edges.csv`
  (`build_navigation_graph_from_edges()`), with **zero additional validation
  performed inside this module during traversal** — no visibility check, no
  column-existence check, and no `CONTEXT()` evaluation of any kind, confirmed
  by grep (`grep -n -i "context" view_orphan_detector.py` — zero hits, anywhere
  in the file). Whatever an edge in `navigation_edges.csv` represents, this
  module treats it as unconditionally traversable. This makes it
  **systematically more permissive than sibling modules that do check
  context** — an edge whose `must_be_in_views`/`must_be_viewtype`/etc.
  condition can never actually be satisfied still counts as a real path here,
  which means this module under-reports both `potential_view_orphans.csv` and
  `unused_system_views.csv` in both apps, in every parse to date, by an amount
  that has not been measured. This is the same "restrictive vs. permissive"
  asymmetry already recorded elsewhere in this file for other modules, just in
  the permissive direction, which is quieter and harder to notice than the
  restrictive kind — a permissive error emits a false "reachable," and nobody
  complains about a view that isn't flagged.
- **Not decided:** whether to add `CONTEXT()` evaluation to this module (making
  it match its stricter siblings) or to document the gap as an accepted
  limitation instead. That is Kirk's call, not made here — see
  `RELEASE_CHECKLIST.md` section B.
- Other findings from the same audit, all confirmed directly against the code:
  no `ref_parent` or embedding-based reachability path exists for
  category-`ref` views — `category == 'ref'` only selects which reason string
  to write (`'Ref view not reachable from any root view'` /
  `'System ref view not reachable from any root view'`), after the same BFS
  result gates every view regardless of category. `appsheet_actions.csv` is a
  required input (`validate_files()` fails without it) but is never actually
  read anywhere in the module. `appsheet_columns.csv` is loaded into
  `self.columns_by_table` and then never read again — no column-existence
  validation happens despite the data being present. `is_always_false_condition()`
  is a small fixed list of literal patterns (`false`, `false()`, `1=2`,
  `"a"="b"`, `true=false`, each with an optional leading `=`), not a general
  expression evaluator — a `show_if` that's always false through any other
  phrasing silently falls through as "not always false."
- **Neither 2025 design document matches the code, and the mismatch runs in
  opposite directions** (source: `260902_view_orphan_path_analysis_notes.md`,
  a separate read of the four 2025 `.docx` design records). `250809` describes
  a comprehensive, validated BFS as already implemented; `250819`, ten days
  later, describes the then-current algorithm as pure reference-collection
  with no path verification at all. The code today is root-seeded BFS with no
  per-step validation — closer in *shape* to `250809` (the function names and
  root-view definition match) but without the validation `250809` claimed was
  built, and structurally nothing like `250819`'s flat reference-collection
  description (there is no `available_actions` scanning anywhere in the file).
  Neither document is an accurate account of the code as it exists now. Also
  confirmed: none of the four 2025 documents mentions `ref_parent` at all
  (verified by grep across all four) — the code's silence on embedding-based
  reachability is not a case of undocumented divergence from a design; the
  design never addressed the question either.
- Not fixed. Read-only finding as of 2026-09-02.
- **Decision, 2026-09-05: FIX, not document.** Recorded with its reasoning and done-when in `RELEASE_CHECKLIST.md` section B ("Decide: fix `view_orphan_detector.py`'s missing `CONTEXT()` handling..."). Covers `view_dependency_analyzer.py` too (next entry). Sequenced after the reference re-cut.

### `view_dependency_analyzer.py` also evaluates no `CONTEXT()` conditions and never loads column data — a second instance, not a new gap

- Confirmed by full code audit, 2026-09-03 (private working note, kept
  outside this repository:
  `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260903_view_dependency_analyzer_code_audit.md`).
  `grep -c -i "context" view_dependency_analyzer.py` → 0, same as
  `view_orphan_detector.py`. This module doesn't even load
  `appsheet_columns.csv` — confirmed by grep, zero references anywhere in
  the file — so column-level `Show_If` plays no role here either, for the
  same reason it plays none in `view_orphan_detector.py` (see the entry
  above): the file that would carry it is never opened at all, a step
  further than `view_orphan_detector.py`'s load-then-discard.
- **This is a second instance of the gap already recorded above for
  `view_orphan_detector.py`, not a fresh discovery.** Say so rather than
  presenting it as new: the suite's most consequential known gap now applies,
  confirmed, to both of the two modules that answer "is this view reachable."
- Not fixed. Read-only finding as of 2026-09-03.
- **Decision, 2026-09-05: fixed together with `view_orphan_detector.py` through one shared mechanism** — see the previous entry and `RELEASE_CHECKLIST.md` section B.

### `load_unused_system_views()` gives no signal distinguishing a missing `unused_system_views.csv` from one recording zero unused views

- Read-side counterpart to the write-side defect already recorded above
  (`view_orphan_detector.py` writes nothing on a zero result for the same
  file). `view_dependency_analyzer.py`'s `load_unused_system_views()` is
  gated entirely on whether the file exists; when it's absent, the method
  does nothing — no exception, no message — and `self.unused_system_views`
  stays the same empty set it would be if the file existed but recorded zero
  unused views. Three distinct states — never ran, ran and found zero, file
  absent — collapse into one, on the read side of the same file the write
  side already collapses two of three for.
- **Measured consequence, not just a description of the code path:** with
  the file absent, `build_navigation_graph()` on Kankaku's data loads 585
  navigation edges (the full, unfiltered `navigation_edges.csv` row count)
  instead of 384 (with the real, populated file — 64 entries — loaded
  first) — silently, with nothing distinguishing "ran with the exclusion
  filter" from "ran without it because the file wasn't there."
- Found 2026-09-04. Not fixed. Read-only finding.

### Three code-level reachability-rule differences between `view_dependency_analyzer.py` and `view_orphan_detector.py` — no live disagreement found across three apps, but the depth cap runs at its ceiling in one

- `view_dependency_analyzer.py`'s `is_always_false()` is a strict subset of
  `view_orphan_detector.py`'s `is_always_false_condition()` (missing five
  regex patterns for `1=2`/`"a"="b"`/`true=false`-shaped conditions);
  `view_dependency_analyzer.py` never checks a *target* view's own `show_if`
  as an override the way `view_orphan_detector.py` does; and
  `view_dependency_analyzer.py`'s `bfs_find_paths()` caps search depth at a
  6-edge maximum per root, which `view_orphan_detector.py`'s unbounded BFS
  does not share.
- **Measured against three apps, not asserted:** the first two differences
  produce no live disagreement in any of Kankaku, Farmy, or a third app
  parsed 2026-09-04 (no view with a matching `show_if` shape exists in any
  of the three). The depth cap is the one that matters in practice — the
  smallest cap that would hide nothing needs **5 edges in Kankaku, 5 in the
  third app, and 7 in Farmy**, against the code's current 6-edge maximum.
  Farmy alone currently has 19 (root, target) pairs whose shortest path
  exceeds the cap — invisible today only because `find_paths_to_view()`
  retries other roots and one of them succeeds within the cap.
- **No view is currently hidden by the cap in any of the three apps
  measured — but Farmy is the outlier of the three, not the typical case**,
  and its margin is a live, currently-occurring shortfall (19 pairs), not a
  comfortable, far-off one. Any future summary of this finding should say
  "two of three apps show no margin pressure; Farmy is the current
  exception," not imply a representative split.
- Confirmed by audit — the 2026-09-04 correction, the 2026-09-04 follow-up
  (originally misdated 2026-09-05 in the audit document; corrected there
  2026-09-04), and a third-app re-run the same day (see the private
  working note above). Not fixed — Kirk's call on whether to widen the
  cap. Read-only finding.

### `view_orphan_detector.py` admits unresolvable `target_view` strings into its `reachable` set as raw text, overstating its reported reachable count

- `build_navigation_graph_from_edges()` falls back to the raw, unresolved
  `target_view` string from `navigation_edges.csv` when its own
  `view_name_by_lower` canonicalization can't match it to any real view —
  and that raw string then enters `reachable` indistinguishably from a
  genuine view name. Measured: 12 such phantom names in Farmy, 0 in
  Kankaku, 0 in a third app parsed 2026-09-04.
- **The derived orphan CSVs are not affected** — `potential_view_orphans.csv`
  and `unused_system_views.csv` are built by iterating real view rows and
  checking set membership, so a phantom entry in `reachable` simply never
  matches a real row. What's affected is `view_orphan_detector.py`'s own
  printed "reachable" *count*, which overstates real, navigable views by
  exactly the phantom count — a reader taking that console number at face
  value, rather than the derived files, would be misled.
- Whether this is the same class of dangling reference
  `phantom_view_reference_detector.py` already catches from other source
  fields, or a distinct blind spot specific to `navigation_edges.csv`'s own
  `target_view`, is not established. Found 2026-09-04. Not fixed. Read-only
  finding.

### Two Farmy phantom names may be misattributed to source views whose own `action_targets.csv` resolution points elsewhere

- For two of Farmy's phantom view names, `MyPlantsReadOnly_Detail` and
  `Seeds READONLY_Detail`, `navigation_edges.csv`'s recorded target for a
  source view does not match what `action_targets.csv` independently
  resolved for that source view's own table. Both arise from an action
  name shared across several tables — `View Ref (MyPlants_ID)` and
  `View Ref (Seeds_ID)` — where `action_targets.csv` resolves each table's
  own variant separately and correctly, most of them to real, existing
  views (`Plants without DB reference_Detail`, `Seeds_Detail`), while
  `navigation_edges.csv` records 9 of 12 and 7 of 10 source views under the
  phantom target instead. See the private working note for the full
  figures and view lists rather than relying on this summary:
  `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260903_view_dependency_analyzer_code_audit.md`
  (2026-09-04 follow-up section).
- **Cause not established.** Reported as evidence only, not diagnosed
  against `navigation_edge_generator.py`'s own logic, which was out of
  scope for the audit that found this.
- **Why this matters now:** both `MyPlantsReadOnly_Detail` and
  `Seeds READONLY_Detail` sit on `RELEASE_CHECKLIST.md` section E's list of
  broken view references pending a report to Leon. If edges are being
  attributed to source views whose own resolution points elsewhere, some of
  those names may be an artifact of this suite rather than a defect in his
  app. **Recommend settling this before the follow-up report goes to
  Leon — not settled here, and the call on how to proceed is not made
  here.**
- Found 2026-09-04. Not fixed. Read-only finding.

### The parser doesn't recognize the `#page=fastTable&table=...` deep-link pattern used by chart-data actions

- 6 unparseable navigation expressions in a third app parsed 2026-09-04, all
  shaped `="#page=fastTable&table=..."`, all tied to chart-view actions —
  zero occurrences in either Kankaku's or Farmy's
  `action_targets_unparseable.csv`. Distinct from the already-known
  `#page=map&table=...&mapcolumn=...` gap (13 rows in Farmy, 6 more in the
  same third app) — this is a different `#page=` value the deep-link
  recognizer doesn't handle at all, not a variant of the known one.
- **Observation, not investigated:** the same six actions also carry six of
  the twelve `CONTEXT()`-bearing `only_if_condition` rows in that app's
  `appsheet_actions.csv`, and that same parse reported zero edges blocked
  by conditions. The unparseable navigation targets and the unexercised
  condition checking may be connected — not diagnosed here.
- Not fixed. Read-only finding.

### Open question: does `a15021b`'s `NOT(CONTEXT(...))` fix cover a membership-test shape it wasn't tested against?

- `a15021b` fixed `NOT()` wrapping a *direct* `CONTEXT()` comparison (e.g.
  `NOT(CONTEXT("ViewType") = "Detail")`). A third app parsed 2026-09-04
  exercises a different shape six times: `NOT(IN(CONTEXT("View"),
  LIST(...)))`, a `NOT()` wrapping a membership test rather than an
  equality. Whether this inverts the same way is not established — not
  audited here, flagged as an open question.
- **Why this can't be settled by diffing:** the original defect this class
  of bug belongs to was RESTRICTIVE — it suppresses edges rather than
  fabricating them — and restrictive errors are stable across runs, so a
  before/after CSV diff would show nothing even if this shape is still
  mishandled (`a15021b`'s own entry below records the same asymmetry).
  Confirming or ruling this out needs the same kind of targeted,
  field-by-field check `a15021b`'s own verification used, not a diff.
- Found 2026-09-04. Not fixed. Read-only finding.

### `broken_usersettings_references.csv` was non-empty for the first time in this project

- One row, found in a third app parsed 2026-09-04, involving a column in
  the app's standard `_Per User Settings` table referencing another column
  that doesn't exist in it — both Kankaku's and Farmy's
  `broken_usersettings_references.csv` have zero rows (the file doesn't get
  written at all, "write nothing on zero"). This gives the December 2025
  USERSETTINGS() work below a real, non-synthetic test case for the first
  time. Low priority; not investigated further here.

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

### Reading `navigation_edges.csv`'s prominence off the wrong field for `via_group` rows misattributes what actually gates a group's visibility

- Found 2026-09-02, tracing the Kankaku discrepancy in the entry below. An edge's
  own prominence — the value that actually governs whether the *invoked* action
  displays — is in `parent_prominence` when `action_availability_type` is `direct`
  or `event`, and in `child_prominence` when it is `via_group`. But for `via_group`
  rows specifically, `child_prominence` is the *invoked child action's* own
  prominence, and `parent_prominence` is the *group container action's* own
  prominence — and it is the container's prominence, not the child's, that gates
  whether the group (and therefore every child edge under it) is visible at all,
  since a group's children are never independently visibility-checked
  (`action_visibility.py`'s module docstring; hard constraint carried from
  `CONSOLIDATION_PLAN.md` sections 1/6). A measurement that reads `child_prominence`
  off a `via_group` row and treats it as "this edge's own, independently-checked
  prominence" will misclassify which edges a prominence-based rule change actually
  touches — exactly what happened in the entry below: two `via_group` edges whose
  `child_prominence` was `Display_Prominently` were predicted removable by the step
  5 attempt and were not (their group parent's own prominence was `Do_Not_Display`,
  untouched by the rule), while three edges whose `child_prominence` was
  `Do_Not_Display` were actually removed, because their group parent's own
  prominence — findable only via the row's separate `parent_action` field,
  cross-referenced against `appsheet_actions.csv` — was `Display_Prominently`.
- **General caution, not a one-off**, in the same spirit as the `action_name`-alone
  caution above: any future comparison or prediction involving `via_group` rows in
  this CSV must resolve the *group container's own* prominence via `parent_action`,
  not assume `parent_prominence`/`child_prominence` alone tells the whole story —
  `child_prominence` describes the invoked action, not what gates its visibility.
- Not a defect in the tool's own output — every field genuinely present on the row
  is correct and derivable; this is a hazard in how a reader interprets which field
  answers "is this edge gated by prominence," recorded so it is not rediscovered
  the hard way in a future session.

### `CONSOLIDATION_PLAN.md` step 5 (Prominent-on-Deck exclusion): implemented, disproved, reverted — no commit

- Implemented 2026-09-02 in `action_visibility.py` (all three strategies, via a
  shared `_prominent_excluded_on_deck` helper), verified by full re-parse against
  both apps, then reverted the same day before being committed — HEAD never moved
  past `ebc41d6`. The uncommitted diff is preserved outside the repository, not
  applied to the working tree, at `~/Documents/雑学/260505 0852 AppSheet orphan
  script possible issues/260902_step5_disproved.patch`.
- **Why reverted:** disproved by Kirk's own 2026-09-02 observation in the app
  editor — see `APPSHEET_BEHAVIOR.md`'s "Established behavior" entry for
  Prominent-on-Deck. Three `Display_Prominently` actions on Kankaku's `W to D` deck
  are genuinely on that deck's own `view_configuration` `ActionBarEntries`
  (`Displayed Got It (WD)`, `Play (Main Data)`, `Display Answer (W to D)`), and two
  were confirmed rendering as row buttons (thumbs-up, right-arrow) in the editor
  preview. Google's Position documentation, which names only Detail for Prominent,
  does not hold on deck views under Manual-list membership.
- **What the implementation actually did, verified against both apps before the
  revert, and not what the step predicted:** removed exactly 1 edge in Farmy
  (target `ActivityForm - Germination`, itself a phantom view reference — no real
  orphan consequence) and 3 in Kankaku (targets `Word`, `WDend`, `WDend J`). All 3
  Kankaku removals were `via_group` edges whose *group parent* action — not the
  invoked child action itself — carried `Display_Prominently` and sat on `W to D`'s
  action bar (`Display Answer (W to D)` parenting the `Word` edge, `Displayed Got
  It (WD)` parenting the `WDend`/`WDend J` edges); blocking the parent cascaded to
  every child edge under this module's hard constraint that a group's children are
  never independently visibility-checked — see the entry above. This cascaded to 4
  new rows in `potential_view_orphans.csv` (`Word`, `WDend`, `WDend J`, `Card stats
  2` — the last one's own only other reachability path was already broken
  independently of this step) — a real orphan-count increase, where the working
  measurement taken before implementation had predicted zero. AOD's existential
  channel showed 0 True→False flips in either app; 0 `Display_Overlay` rows were
  touched anywhere, as required.
- Not fixed, not applied, not committed. Read-only finding as of 2026-09-02.

### `column_dependency_analyzer.py` silently drops exact-gated column-to-column references (line 299)

- An exact-gated reference that `categorize_references` cannot find a field to attribute is dropped from `referencing_columns` entirely — no note, no counter, no trace in the summary. Measured exhaustively across every ordered column pair in three apps: 2 dropped in Kankaku, 35 in Farmy, 0 in the third app. Cause established for 35 of the 37 (all Farmy): the reference lives in the raw `type_qualifier` JSON but is never rendered into `type_qualifier_formulas`, the only field `categorize_references` can see (clean specimen: `Beds[SHOW Bed location and Bed Name]`). The remaining 2 (Kankaku, sourced from `description` prose) happen to mask two genuine parser false positives (`Stats[New stats]`, `Stats[Current got it count and image no]`) — record this so a naive fix to the drop doesn't simply surface both bad parses. (code audit, 2026-09-04)

### `column_dependency_analyzer.py`'s `is_system` field never populates (line 1355)

- Reads `action.get('is_system')`; the real field is `is_system_generated`, present and non-empty in 560/560, 970/970, 370/370 rows across the three apps. `is_system` is therefore always `False`, and the summary line at 400–401 ("System-generated from this column: N actions") is unreachable — 95, 230, and 102 system-generated actions respectively go unreported. The 2025 archive documents this exact line as a deliberate addition to make `[SYSTEM]` badges work; it has never worked since being added. (code audit, 2026-09-04)

### `column_dependency_analyzer.py`'s `prominence` field never populates (line 1354)

- Reads `action.get('prominence')`; the real field is `action_prominence`, present and non-empty in all three apps. `prominence` is therefore always `None`, and renders as such wherever the display code shows it. (code audit, 2026-09-04)

### `column_dependency_analyzer.py` cannot distinguish a missing optional CSV from a genuinely empty one, after load time

- `_load_data`'s return value (`True` on success, `False` on absence) is discarded at all four call sites. `self.slices_data`, `self.actions_data`, etc. become `[]` either way, and downstream summary text ("0 slices use this column…") is identical for "file genuinely has zero" and "file was never opened." The two states ARE distinguishable at load time — the console prints different notes for each ("Loaded 0 slices" vs. "Note: No actions file found") — but that note scrolls past before the interactive session begins and is never repeated in report output, so a reader of the report alone cannot tell the difference. (code audit, 2026-09-04)

### `unused_system_views.csv` absence produces no signal at all in `column_dependency_analyzer.py`

- Unlike the four optional CSVs above, whose absence at least prints a note, a missing `unused_system_views.csv` falls through its `if unused_file.exists()` check with nothing printed at all. The summary line that would otherwise report "N unreachable system views excluded from analysis" is itself suppressed by its own guard, so every system view is analysed, silently, with no clue in the output that the exclusion never happened. This is the one input in this module whose absence produces no signal whatsoever. (code audit, 2026-09-04)

### `column_dependency_analyzer.py` — lower-priority code hygiene (not yet acted on)

- `_load_data` is defined twice, identically (lines 34–49 and 51–66, byte-identical by diff). The first is dead, shadowed at class-creation time — no behavioural effect, but a future fix applied to the dead copy would look correct on inspection and do nothing.
- `os` is imported and never used (zero `os.` references) — the same pattern already noted in `view_dependency_analyzer.py`.
- Line 1292's `action.get('source_table') or action.get('table')` fallback references a `table` column that does not exist in any actions parse; harmless (`source_table` is populated in all but one Farmy row, which falls through to `None` rather than raising) but implies a schema variant that isn't real.
- `categorize_references` omits `reset_if` while checking the other four fields of the same group (`show_if`, `valid_if`, `required_if`, `editable_if`) — an inconsistency, currently moot since all five are empty per the entry above.
(code audit, 2026-09-04)

### The suite holds a component's identity, not its location on screen — presentation-layer gap (2026-09-05)

- A component has three addresses — its CSV identity, its editor location, and its location in the running app — and only the third can be tapped. The suite computes the first two; nothing computes the third. Found via reconnaissance into Kankaku's `Go to card stats` action, which also exposed that view display names are entirely absent from the `Application Documentation.html` export (a view's Display Name field has no home there), and that 87 of 157 Kankaku columns' display-name overrides are language-branching formulas rather than literal strings — two columns share a byte-identical formula and are indistinguishable to a user by label alone. Full findings, including a proposed phrasing rule for instructions ("look for a line labelled X," never "the X line," wherever the parse cannot establish uniqueness) and a survey method for the remaining component types (slices, actions, tables, format rules): private working note, kept outside this repository: `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260905_presentation_layer_gap_working_note.md`. The note's closing list has now been applied — see the two entries directly below, the labels-are-formulas note in `CLAUDE.md` and `AGENTS.md`, and the closure of `RELEASE_CHECKLIST.md` section A. One item in that list is deliberately NOT recorded in this repository: the Cram-mode logical contradiction the note describes is a finding about Kirk's own app, not about this tool, and lives only in the working note.

### View display names exist in AppSheet's editor but are absent from the export — an export gap, not a parser defect

- A view's Display Name is a real, settable field in the AppSheet editor: confirmed 2026-09-05 by direct inspection, with the editor's own tooltip stating that a view left blank simply uses its own name. The `Application Documentation.html` export does not carry it. Kankaku's `D to W` view record holds exactly ten fields — View name, Created by, View type, ActionType, Position, View configuration, Visible?, Icon, Menu order, Show if — and that field set is uniform across the entire Views section. Searching the raw export for the known display name `M to W` returns 261 hits, every one inside a *column* display-name formula and none inside any view record.
- `views_parser.py` is not discarding it. Its label-matching branches cover exactly the ten fields the HTML offers; there is nothing else there to read. Closing this gap would require a different export mechanism from AppSheet, or supplying the values by hand.
- Two things bound the severity. Per the editor tooltip's fallback rule, a view with no override displays under its own name — so the export's silence is harmless for every view that has never been renamed, and the gap bites only on the renamed subset. But nothing in the export identifies which views those are. Kankaku's `D to W` is a live instance: it displays to users as `M to W`, an old internal name surviving under a newer label.
- Consequence for anything that directs a user to a screen: the internal view name remains usable in an instruction provided it is not asserted as what the user will see. A small side mapping of view name to display name, kept beside the parse rather than inside it, would hold what the export omits without compromising the parse as a faithful record. A display name is stable state, so this is a one-time cost per view.
- Incidental, not pursued: `view_configuration` carries `ColumnOrder` and `QuickEditColumns`, neither promoted to a top-level CSV column — unpromoted, not missing. The editor's "App link" field is derived from the view name, not a stored property, so there is nothing there to extract. Separately, a view's Descriptive comment is also absent from the export, though the field exists in the export template and IS carried for format rules and actions.
- Found 2026-09-05 (working note: `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260905_presentation_layer_gap_working_note.md`).

### Column display names are carried faithfully but are formulas over live state, not readable strings — and they can collide

- Unlike views, both columns and actions carry a `display_name` in the export and it reaches the CSV intact. Pipeline fidelity was verified on Kankaku's `Card status` column, inspected in full: of its 21 raw fields, `column_parser.py` drops only `Visible?` and `Formula version` via a blanket `excluded_fields` set, and re-emits `Virtual?` as `is_virtual`. Everything else survives verbatim — nothing that determines or gates a column's meaning is lost on that path.
- The problem is what the field contains. Of 157 Kankaku columns, 70 carry no override; of the 87 that do, **all 87 are formulas — not one is a literal string** — and 63 branch on `INDEX(System language[Enum],1)`. So the parse holds the display name faithfully and still cannot say what a user will read without knowing live state. This is the same class of limitation as the column-level `Show_If` gap, applied to *labels* rather than to visibility.
- **Labels can collide.** `Schedule position label` and `D to W accuracy in cram` carry byte-identical display-name formulas, so both render as "Card statistics" / 「カード統計」 despite being different columns with mutually exclusive `Show_If` conditions. Complete data, and still not enough to tell two things apart from a label alone.
- A display name of `=" "` — a single space — is a deliberate choice meaning "no visible label," not a missing value; the control then appears as an icon alone. Kankaku's `Go to card stats` is such a case.
- **Nothing records which of several inline actions renders.** Five actions attach to `Schedule position label`, three of them top-level and `Display_Inline` at once. `appsheet_actions.csv` has no position or sequence field, `view_configuration.ActionColumns` is null for `D to W`, and `available_actions` / `view_columns` are unordered `|||`-joined lists not proven to reflect render order. When more than one inline action on a column has a satisfiable condition simultaneously, the export does not say which renders, in what order, or whether several appear side by side. Observable only in the running app.
- Found 2026-09-05 (same working note as the entry above).

### `master_parser_and_orphan_detector.py` tests for `'UNSURE'` but the value written is `'Unsure'` — duplicate-name actions miscounted in the top-level summary

- Line 74 compares against `'UNSURE'` (upper case). `actions_parser.py`'s duplicate-name pass writes `'Unsure'` (mixed case), so the comparison never matches and a genuinely-flagged duplicate is summarised as "unknown" rather than "unsure". The per-app safety net itself is unaffected — `actions_orphan_detector.py` excludes these rows by testing for `'No'`, not by testing for this value — so the miscount is confined to the top-level summary text.
- This is the same class of defect as the `Do_Not_Display` prominence mismatch that `CONSOLIDATION_PLAN.md` sections 3 and 4 fixed in two of three strategies, and as the view-type case bug fixed in `748e329`: a literal compared against a differently-cased literal, failing silently. Third instance of the pattern found in this codebase.
- Found 2026-09-05 during a read-only investigation into duplicate action names. Not fixed; no code changed.

### `actions_parser.py`'s `used_action_keys` is declared and never used

- `self.used_action_keys = set()` at line 40 is never read from or written to anywhere in the file (checked by grep for `used_action_keys`, `.pop`, `.discard`, `.remove` — no other hits). The compound-key `||SYSTEM` / `||USER` lookup around lines 1018–1057, which this state appears to have been introduced to support, tries `||SYSTEM` before `||USER` and takes the first hit without de-duplicating.
- Interpretation, NOT confirmed: this looks like a fix whose state was introduced but never wired up. No live case exists in either reference parse to execute it against, so the failure has not been observed — only inferred from reading. If the inference is right, a same-table duplicate carrying both a `||SYSTEM` and a `||USER` entry in `actions.txt` would resolve every same-named HTML row to `'Yes'`.
- Currently masked: the later duplicate-name pass re-checks by plain name plus table and marks both rows `'Unsure'`, which neutralises the ambiguity regardless. So no wrong result is produced today — but a future change to that pass would unmask this silently. Recorded for that reason.
- Found 2026-09-05, same investigation. Not fixed; no code changed.

### Duplicate `action_name` values across tables are expected and benign — investigated 2026-09-05, no defect

- 11 duplicated names in `20260902_131151_AppsheetFarmyApp_for_Kirk_parse` (of 970 rows), 6 in `20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881` (of 560). Every one, in both apps, is a cross-table repeat of a generic system-action name — `Add`, `Delete`, `Edit`, `Open Url (...)`, `View Ref (...)` — one such action existing once per table by normal AppSheet design. Measured: zero same-table collisions, zero compound-key (`table + name`) collisions, zero involving a non-system action.
- **This tolerance is deliberate.** The July 2025 fix recorded in the 2025 archive (`250726 1714 Action Orphan Detection Fix Report.docx`, with its companion `250725...` report) moved duplicate detection from plain name to a compound `action name + table name` key specifically to avoid misclassifying distinct system actions such as `Edit` that legitimately appear in many tables. Today's behaviour is that fix working, not an oversight.
- The safety net for the case that IS a problem — a same-table duplicate — exists and works: `actions_parser.py`'s `detect_duplicate_action_names` (lines ~391–419) marks both rows `'Unsure'`, warns interactively, and `actions_orphan_detector.py` excludes them from orphan detection and counts them separately. **It has never fired on either reference app**, so it is untested against live data.
- The scenario it guards against is real and dated: `250723 0642 Action Parser Duplicate Name Issue.docx` records Kankaku's `Options` table holding two actions both named `View Ref (System)`, one system-generated and one user-created, with the 2025 note supposing it had been auto-converted from a duplicate system action by AppSheet's own error handling. That supposition is now confirmed by vendor documentation: AppSheet's error-messages page (`https://www.appsheet.com/support/errormessages`) states that when it detects a duplicated system action it marks the duplicate as non-system-generated so the author can fix or delete it. **Consequence worth carrying: `is_system_generated` cannot be relied on to identify which row of a colliding pair was originally the system one, because AppSheet mutates that flag precisely in this case.** No document in the 2025 archive cites this vendor page; the confirmation is new as of 2026-09-05.
- That specific `Options` case is no longer present in the current Kankaku parse — only `View Ref (System) E` and `View Ref (System) J` now exist, which are distinct names. The app changed, not the tooling.
- Recorded so that a future reader encountering 17 duplicate names does not repeat this investigation. No code changed.

### `slice_parser.py`'s `parse_slice_actions` is unreachable dead code

- `parse_slice_actions` (~lines 171–234) is a fallback parser for the slice-actions cell that can never execute. Its only caller is guarded by `slice_actions_cell is None` — the specialized loop found no row whose label *substring*-matches both 'slice' and 'action' — while `'slice_actions' in slice_info` is already true, the generic loop's *exact*-match transform having set it from the same rows. The exact-match condition is strictly narrower than the substring condition over the identical `table_element.find_all('tr')`, so any row satisfying the first necessarily satisfies the second, and the `elif` can never fire.
- Confirmed empirically as well as structurally: the fallback strips formatting artifacts, which would turn `**auto**` into bare `auto`. Not one of the 252 slice rows across the two apps shows that signature — every auto-assigned row carries the asterisks intact.
- Same shape as the `actions_parser.py` `used_action_keys` entry above: machinery introduced for a case that the surrounding control flow makes unreachable. No wrong result is produced today; recorded so that a future change to the specialized loop's matching does not silently activate a parser nobody has tested.
- Found 2026-09-05, same survey. Not removed; no code changed.

### `action_dependency_analyzer.py` never matches an action against an auto-assigned slice — interactive browsing only

- `analyze_slice_dependencies` (~lines 1017–1023) answers "which slices use this action?" by exact-string matching the action name against the `|||`-split `slice_actions` list. An auto-assigned slice's list contains only the literal `**auto**`, which matches no action name, so such a slice is never reported as using any action — silently, with no note that the list was a placeholder rather than a membership set. That is 167 of 195 Farmy slices and 10 of 57 Kankaku slices.
- Scope is display only. ADA feeds nothing programmatic (its existing "feeds nothing programmatic" characterization elsewhere in this file), so this affects what the interactive dependency browser tells a user and nothing that reaches a CSV. Whether it is worth fixing therefore turns on the open question already recorded here about whether the interactive browser survives the two-outputs framing — the same dependency that made section D step 2b not a straightforward pending fix.
- A second, smaller consumer with the same blind spot: `slice_parser.py`'s console summary printer (~line 529) counts `len(split('|||'))` to report "N actions" per slice during parsing, so an auto-assigned slice prints as "1 action". Cosmetic, console-only, no persisted effect.
- Found 2026-09-05, same survey. Not fixed; no code changed.

### Both saved reference parses are stale, so the section C regression guard has been measuring unrelated drift since 2026-09-02

- The two reference parses this project diffs against — `20260902_131151_AppsheetFarmyApp_for_Kirk_parse` and `20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881` — both predate parser changes that legitimately altered their output. Kankaku's reference was captured at `1c22881` on 2026-09-01; `a15021b` fixed `action_target_parser.py`'s `NOT(CONTEXT(...))` inversion the following day. Farmy's reference carries the same divergence plus drift in its own `unused_system_views.csv`.
- **Measured, not inferred.** Re-parsing at pre-fix HEAD with no code change at all produces `action_targets.csv` and `navigation_edges.csv` differing from the Kankaku reference, and `action_targets.csv`, `navigation_edges.csv` and `unused_system_views.csv` differing from the Farmy reference. The Kankaku divergence was traced to a `must_be_in_views`/`must_not_be_in_views` field swap — exactly the shape `a15021b` corrected.
- **Consequence for the method, which is the reason this is filed as a defect rather than as housekeeping.** Every verification in this project since 2026-09-02 that diffed a post-change parse against a saved reference has been attributing pre-existing drift to the change under test. The `b68f854` verification avoided this only because a control parse at pre-fix HEAD was run first and the divergence was noticed. Until the references are re-cut, any diff against them must go through a control parse at pre-fix HEAD, and the change under test is what separates control from post-change — not what separates the reference from either.
- Re-cutting both references is outstanding. It is deliberately not being done in the same session as the fix that exposed the problem: a fresh baseline is what every future diff rests on, and it should be captured and checked by a session that can give it full attention rather than as a closing task.
- `RELEASE_CHECKLIST.md` section C's regression-guard item stays checked — the reference parses were captured, and captured correctly. What this records is that a reference parse decays, which the checklist item did not anticipate.
- Found 2026-09-05 during the `b68f854` verification.
- **Sequenced 2026-09-05 as the FIRST execution item**, ahead of every remaining section B fix — `RELEASE_CHECKLIST.md` section B, top item.

### `available_actions` is a raw passthrough column in three output files, so byte-comparison on them overstates what changed

- A view's `available_actions` string is embedded verbatim as a context column in `navigation_edges.csv`, `potential_view_orphans.csv` and `unused_system_views.csv`. Any change to a view's available-action set therefore makes every pre-existing row carrying that view show as a byte-level difference in all three files, without any logical change to the row.
- **Observed instance.** The `b68f854` verification showed `potential_view_orphans.csv` and `unused_system_views.csv` both differing at the byte level while their sets of flagged view names were completely unchanged — 0 added, 0 removed, in either file. Two rows in each moved, all four in the embedded column only. The same mechanism made one pre-existing `navigation_edges.csv` edge appear as both "removed" and "added" in a multiset diff, so a raw count read 93 new rows where 92 were genuinely new.
- **Consequence for the method.** This project leans on byte-identity as its primary verification signal. On these three files that signal is not reliable on its own for any change touching `available_actions`: a diff must be read at the level of the logical key (flagged view names; edge source/target pairs) before a byte difference is treated as a finding. Recorded because the failure is silent in the safe direction — it reports change where there is none, which wastes an investigation rather than hiding a defect, but it also makes a genuine change harder to see among the noise.
- Found 2026-09-05 during the `b68f854` verification.

### Slice records: what the export carries, what the editor has, and what the parse keeps — 2026-09-05 component survey, no defect

- **The export's field set is uniform.** A slice record carries exactly 7 fields in a fixed order: Slice Name, Slice Columns, Row filter condition, Update mode, Source Table, Visible? (internal `for="Visibility"`), Slice Actions. The only variation across 252 records in the two apps is that Row filter condition is omitted entirely when the slice has no filter — 36 of 195 Farmy, 10 of 57 Kankaku, confirmed against a real example (`MyPlants ALL`). That is the field-omitted-when-empty pattern already established for other component types, not a structural inconsistency.
- **Fields the editor has that the export lacks: Descriptive comment**, absent from all 252 slice records in both apps. Same gap already recorded for views, and the same asymmetry: the export template does carry a Descriptive comment for format rules and actions.
- **Fields the export has that the parse drops: none.** `base_parser.py`'s `extract_component_data` snake-cases and stores every two-cell label verbatim; `slice_parser.py` then overwrites `slice_columns` and `slice_actions` with a better parse from the raw `<ol><li>` structure and adds three synthetic fields not in the export at all — `referenced_columns`, `raw_references`, `formula_context_table`. Every export field reaches the CSV.
- **Two fidelity caveats on what "kept" means.** Update mode is kept as AppSheet's own pre-collapsed enum — one value from `ALL_CHANGES`, `READ_ONLY`, `UPDATES_ONLY`, `ADDS_ONLY` (all four seen across the two apps) — not as the editor's four independent toggles, so the export, and therefore the parse, cannot distinguish combinations the enum does not name. And `Visible?` is an export-only field with no counterpart in the editor's enumerated slice fields; it is the constant `ALWAYS` in every one of the 252 rows, so it currently carries no information.
- **Column population in the parsed CSV** (of 195 Farmy / 57 Kankaku): `slice_name`, `source_table`, `slice_columns`, `formula_context_table`, `update_mode`, `visible` populated in every row of both; `slice_actions` 189/195 and 55/57; `referenced_columns`, `row_filter_condition`, `raw_references` 159/195 and 47/57. No column is empty in every row of either app.
- Recorded so a future reader does not repeat the survey. Of the three defects it turned up, two are the entries directly above; the third — the mixed-slice `**auto**` reachability defect — was fixed the same day and is recorded under "Recently fixed" as `b68f854`.

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
- 2026-09-01, `8d6cb94` — `CONSOLIDATION_PLAN.md` step 3: switched `navigation_edge_generator.py`'s two call sites (`process_regular_action`, and `process_view`'s `execute_group` branch) to delegate to `action_visibility.is_visible_in_view_neg`, passing `stats=self.stats` through so `edges_blocked_by_visibility` keeps incrementing exactly as the original did. The four old methods (`is_action_visible_in_view` and its three per-view-type helpers) are retained as dead code, marked with a comment, pending step 3b's removal — see `RELEASE_CHECKLIST.md` section D.
  - **Increment-count figure corrected:** the `84a651d` caution paragraph above and `RELEASE_CHECKLIST.md`/`CONSOLIDATION_PLAN.md` all previously stated nine `+= 1` sites for NEG's visibility function. Step 3's grep found eight, not nine (`self.stats['edges_blocked_by_visibility'] += 1` at lines 211, 219, 246, 252, 281, 298, 312, 317 of the pre-switch file); corrected in all three documents.
  - **Verified by a 204,827-pair differential comparison of NEG's own answer, old implementation vs. new** (Farmy 463 navigation targets × 319 views = 147,697 pairs; Kankaku 290 navigation targets × 197 views = 57,130 pairs), via a throwaway script (`step3_neg_diff.py`, not committed) that called the retained-dead `is_action_visible_in_view` and the new shared `is_visible_in_view_neg` on every `(action, view)` pair derivable from each app's parsed CSVs: **0 disagreements in either app.**
  - **CSV byte-identity:** fresh copies of the saved references were re-parsed with NEG standalone before and after the switch; `navigation_edges.csv` came back byte-identical (`cmp` pass) for both apps. Data-row counts, confirmed with Python's `csv` module: Farmy 1850 → 1850, Kankaku 592 → 592.
  - **Counter match:** `edges_blocked_by_visibility` — Farmy 4020 (pre-switch) → 4020 (post-switch); Kankaku 1363 (pre-switch) → 1363 (post-switch). Both unchanged, confirming the `stats=self.stats` wiring is correct — this is the check the `84a651d` caution paragraph warned the other two checks cannot substitute for.
  - Downstream orphan files were not directly verified. This entry relies on the pipeline coupling documented in the `48eead1` entry: those files are deterministic given `navigation_edges.csv`. If any had moved while `navigation_edges.csv` was byte-identical, that would be a finding about the coupling, not about step 3.
- 2026-09-02, `3b06a08` — `CONSOLIDATION_PLAN.md` step 3b: deleted the four dead visibility methods from `navigation_edge_generator.py` (`is_action_visible_in_view` and its three per-view-type helpers, `is_action_visible_in_detail_view`, `is_action_visible_in_deck_view`, `is_action_visible_in_table_view`), retained through step 3 only so the differential script (`step3_neg_diff.py`) could call old and new in one process. They served no further purpose once that comparison was done.
  - **Why safe:** step 3 (`8d6cb94`) had already switched both of NEG's call sites to delegate to `action_visibility.is_visible_in_view_neg`; the four old methods had no callers left outside their own internal chain (`is_action_visible_in_view` calling its three helpers).
  - **Pre-deletion caller check:** a grep for all four method names found hits only inside the four methods themselves (the dead-code comment plus the three internal delegating calls) — no external caller, confirming the block was safe to delete outright.
  - **Import smoke-test:** pass — `from navigation_edge_generator import NavigationEdgeGenerator` succeeds with no `NameError` or missing-attribute error after deletion.
  - **CSV byte-identity:** fresh copies of the saved references were re-parsed with NEG standalone before and after deletion; `navigation_edges.csv` came back byte-identical (`cmp` pass) for both apps. Data-row counts, confirmed with Python's `csv` module: Farmy 1850 → 1850, Kankaku 592 → 592.
  - **Counter match:** `edges_blocked_by_visibility` — Farmy 4020 (pre-deletion) → 4020 (post-deletion); Kankaku 1363 (pre-deletion) → 1363 (post-deletion). Both unchanged.
  - Downstream orphan files were not directly verified. This entry relies on the same pipeline coupling as the step 3 entry above (documented in `48eead1`): those files are deterministic given `navigation_edges.csv`.
- 2026-09-02, `742b759` — `CONSOLIDATION_PLAN.md` step 2b: fixed `action_dependency_analyzer.py`'s copy of the `Do_Not_Display` case bug in `is_visible_in_view_ada` (`action_visibility.py`), the same `.replace('_', ' ')` mismatch step 2 (`6115f30`) fixed in AOD, deliberately deferred then because ADA had just gone live on the shared module and fixing it mid-step would have changed the interactive dependency browser's output outside what step 2 predicted.
  - **The fix:** the `.replace('_', ' ')` transform on `action_prominence` removed; all five comparison literals inside the function changed from spaced to underscored form (`'Display Prominently'`, `'Display Overlay'`, `'Display Inline'` ×2, `'Do not display'` → their `_`-joined equivalents).
  - **Pre-fix scan:** every `(action, view)` pair combining a `Do_Not_Display` action with a deck or gallery view where the action is in the view's `available_actions` returned `True` (wrong) — 232 pairs in Farmy, 131 in Kankaku, 363 total. All 363 span deck views only (no gallery view hit the pre-gate in either app), all with `show_action_bar=True`. Farmy: 73 actions, 21 tables, 17 views. Kankaku: 117 actions, 7 tables, 4 views.
  - **Post-fix verification:** all 363 pairs now return `False`. A full cross-product of every `(action, view)` pair in both apps (Farmy 309,430 pairs, Kankaku 110,320) confirms zero pairs in the `Do_Not_Display` × deck/gallery category return `True` anywhere: Farmy 10,350 affected-category pairs / 299,080 unaffected, Kankaku 1,422 affected-category pairs / 108,898 unaffected — the fix changed only the affected category's logic, nothing else.
  - **Verification method note:** verified by direct calls to `is_visible_in_view_ada` against parsed CSVs rather than via the interactive dependency browser — equivalent evidence, since the function is plain and the browser is its only consumer, and this is exactly the value the browser displays. `RELEASE_CHECKLIST.md`'s original done-when condition called for a before/after comparison of the browser's actual reported text; this is that comparison, made directly against the function's return value.
  - Not a CSV diff and no CSV changed: ADA feeds only the interactive dependency browser (`CONSOLIDATION_PLAN.md` section 1), so nothing programmatic downstream of this function is affected.
- 2026-09-02, `96d8897` — `CONSOLIDATION_PLAN.md` step 6: admitted Primary/`Display_Overlay` on deck views as a view-level floating button, ungated by `referenced_actions`, `show_action_bar`, or `action_display_mode` — the deck-side counterpart of `e0530c8`'s table fix. Added a shared `_overlay_admitted_on_deck` helper to `action_visibility.py`, used by all three strategies: NEG's deck helper admits it ahead of the `referenced_actions`/`event_actions` membership test (this branch previously read no prominence at all); AOD's and ADA's deck/gallery branches admit it ahead of the `show_action_bar` test, for deck only — gallery untouched.
  - **Verified by full re-parse of both apps:** 0 edges removed in either app. Farmy: +18 edges across 10 actions (11 `direct`, 7 `via_group`). Kankaku: +5 edges, all from `Flag2 Settings`, one per deck (5 decks), all targeting `Help_Detail E`.
  - **Group-cascade pattern, the same one `e0530c8` found on tables:** 7 of Farmy's 18 added edges are `via_group` rows where a `Display_Overlay` group CONTAINER became visible and its `Do_Not_Display` children then produced edges through the group bypass — the children were never prominence-checked, before or after this fix.
  - **Zero orphan-count change in either app** — every orphan output file byte-identical, so nothing cleared, matching the plan's guess by analogy to `e0530c8` (which also cleared nothing on tables).
  - **Differential checks**, pre-change vs. post-change module comparison: NEG 0 True→False / 871 False→True in Farmy and 0/16 in Kankaku, with `edges_blocked_by_visibility` falling by exactly 871 and 16 respectively — confirming the counter tracks the same flips the edge count reflects. ADA 0/1713 and 0/60. AOD (existential) 0/0 in both apps — which is why no orphan cleared: every action that gained deck visibility already had another reachable path.
- 2026-09-02, `a15021b` — `action_target_parser.py` inverted any `NOT(CONTEXT(...))` condition: a `NOT()` wrapping a `CONTEXT` comparison was previously ignored, so the condition was stored with its sense reversed — `NOT(CONTEXT("ViewType")="Detail")` became `must_be_viewtype='Detail'`, the exact opposite of what it says. The error was RESTRICTIVE in one direction and PERMISSIVE in the other: it suppressed real edges from every view type the condition actually allowed, while admitting false ones from the one view type it was written to exclude. Added two shared helpers, `_not_wraps_context_match` and `_invert_operator`, applied at four call sites: `parse_context_condition` (feeding `parse_if_expression`'s single-condition branch and `parse_ifs_expression`), and both of `process_action`'s inline `only_if_condition` regex loops (`execute_group` and regular-action branches).
  - **Known limitation, not a defect:** the OR branch of `parse_if_expression` is deliberately not fixed — a `NOT()` on one OR term needs a different transform than bare-comparison inversion (that branch already collects every OR'd value into one shared must-be/must-not-be list, with no per-term negation), and the shape occurs in neither app, so it is unattested rather than tested.
  - **Measured effect:** Farmy `navigation_edges.csv` 1868 → 1971 (111 added, 8 removed); Kankaku 597 → 585 (6 added, 18 removed, of which 6 are self-loop edges recounted after a field-only change — same `(source, target)` pair, corrected condition fields — so 12 are genuine revocations of edges that only existed because of the bug). `potential_action_orphans.csv` and `potential_view_orphans.csv` byte-identical in both apps. Farmy `unused_system_views.csv` 100 → 99, `ActivityGermination_Form` cleared.
  - **Verification actually performed, stronger than a diff:** all 28 affected rows (21 Farmy, 7 Kankaku) were checked field-by-field against their source `only_if_condition` expressions, not merely against each other, confirmed correct across: lowercase `not(`/`and(`; newlines inside both `NOT(` and `CONTEXT(` itself (e.g. `NOT(\n    CONTEXT(\n      "View"\n    ) = ...)`, `ADJUST QUANTITY 0a - Group`); several `NOT()` terms in one `AND` (up to 3, `ActivityTransplant_Form 2`); mixed `View`- and `ViewType`-shaped `NOT()` conditions in one expression (`ActivityTransplant_Form`); and a row where a target-side `ViewType` condition from the navigate_target expression's own branch sits beside a `NOT`-wrapped view-name condition from `only_if_condition` and must be left untouched (`Images_Form - AmendmentPrep`, whose unrelated `must_be_viewtype='Form|||Dashboard|||Detail'` is confirmed unchanged on both of its rows).
- 2026-09-02 — Kankaku's three `20260831_182306` view orphans (`Card stats`, `Card stats 2`, `Overall_Detail J`, all "Detail view not reachable from any root view") are absent from the `20260902_142806` parse of the SAME frozen export — which precedes the `NOT()` fix above — so they were cleared by commits made between those two parses, not by `a15021b`. All three trace to `1c22881`, though not by the same mechanism: `Card stats 2` and `Overall_Detail J` are explained directly, by a new `navigation_edges.csv` edge reaching each of them (below); `Card stats` is explained indirectly, via a path through an unrelated view, established only after this entry's first version wrongly concluded the mechanism was unidentified — see its own bullet below for the corrected account and why the first attempt missed it.
  - `Card stats 2` gained 4 incoming `navigation_edges.csv` rows, all from `Go to card stats 2` (0 → 4). `Overall_Detail J` gained 10, split evenly between `Go to long-term statistics` and `Go to short-term statistics` (1 → 11, the 1 pre-existing edge from `Flag (Overall)` unchanged) — edges that existed in the app all along and were invisible only because the expressions naming them could not be parsed.
  - **`Card stats`, corrected 2026-09-02 by the `view_orphan_detector.py` code audit** (private working note, kept outside this repository: `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`): it DOES trace to `1c22881`, via `D to W (root) → D to W_Detail → Definition → Card Stats` — a path through `Definition`, not through `Kankaku_Inline`. The first two hops are identical in both parses; the third, `Definition → Card Stats` via action `Go to card stats`, has zero rows in `20260831_182306` and two in `20260902_142806` — `Go to card stats` is one of the three single-call actions `1c22881`'s own entry above already names as recovered by the curly-quote fix (`"Go to card stats" → "Card Stats"`). `view_orphan_detector.py`'s existing, unchanged case-insensitive view-name resolution (`view_name_by_lower`, built in `load_views()`) attaches the mismatched-case target `'Card Stats'` to the real view `Card stats`. Established by executing the module itself — importing `ViewOrphanDetector` and running its own `find_all_reachable_views()` and `print_reach_path()` against both reference parse directories — not by reading the CSVs by hand.
    - **Keeping the earlier conclusion on record rather than erasing it, because the reasoning behind it stands even though the conclusion was wrong:** the `Kankaku_Inline → Card stats` edge (`**auto**`, `row selected`) genuinely is byte-identical in both parses, and `Kankaku_Inline` genuinely has zero incoming edges in both — that observation was correct, and that edge truly is a dead end, in both parses, that never explains the clearance. What was wrong was concluding "mechanism not identified" from that alone: `Kankaku_Inline` is not `Card stats`'s only incoming edge, and the second path (through `Definition`) was never checked before drawing that conclusion. The lesson is the gap between "this specific edge doesn't explain it" and "no edge explains it" — the first was established, the second wasn't, and the entry stated the second anyway.
    - **Superseded 2026-09-03, one level further out.** The path traced here is correct as a statement about `navigation_edges.csv`, and wrong as a statement about the app: the `Definition → Card Stats` hop cannot fire, because the column its action attaches to is hidden in exactly the state the action requires. See "Column-level `Show_If` is never consulted" under "Known defects". Kept rather than rewritten, on the same principle as the bullet above: the reasoning was sound and the data was read correctly; what was missing was a factor nothing in the module consults.
  - The one remaining `action_targets_unparseable.csv` row is not a mystery — it is `Force sync`, already correctly identified and labeled (`"Forced sync — LINKTOROW to CONTEXT(VIEW), no navigation target"`) by `1c22881`'s second fix (confirmed by `git log -S` on that exact string: only `1c22881`'s diff to `action_target_parser.py` adds it; `d5afd61` and `7aeb2c3` merely quote it in this file). Recorded here so a reader checking today's parses against the row count doesn't go looking for an unidentified failure that isn't there.
    - **Roadmap note, not a defect and not phase one:** this expression's `CONTEXT(VIEW)` uses a bare, unquoted argument — every other `CONTEXT()` call in both apps (101 in Farmy, 230 in Kankaku, confirmed by scanning `navigate_target` and `only_if_condition` in both) uses a quoted string literal (`CONTEXT("View")`, `CONTEXT("ViewType")`, and so on). AppSheet accepts both forms. Relevant to any future `CONTEXT()` argument-validation checker: one keyed on quoted literals alone would miss or misflag this form.
  - `potential_format_rule_orphans.csv` is absent from the `20260831_182306` parse too — Kankaku's format-rule orphan count has been zero throughout this entire interval, and there is no change to explain there.
- 2026-09-04 — `LINKTOFILTEREDVIEW` (added by `48eead1`, 2026-08-30) was
  exercised by real data for the first time since that fix shipped: a third
  app parsed this date uses it 13 times, all parsing cleanly into
  `action_targets.csv`, none appearing in `action_targets_unparseable.csv`.
  A fix confirmed by new data, not a defect found.
- 2026-09-05, `bbe981b` — `action_visibility.py`'s `is_visible_in_view_ada` had no case for `Display_Overlay` in its table branch and fell through to the function's final `return False` — the same wrong answer `navigation_edge_generator.py` gave before `e0530c8` and `actions_orphan_detector.py`'s table branch already avoids (it has carried the `Display_Overlay` case since `e0530c8`), reached by omission rather than an explicit rejecting rule. Deliberately left out of `e0530c8` so that fix's two output-affecting edits could be verified alone; `is_visible_in_view_ada` is the correct current location, not `action_dependency_analyzer.py`'s own `is_action_visible_in_view` — consolidation step 1 (`84a651d`) moved this method's body into `action_visibility.py`, and `action_dependency_analyzer.py` line 663 is now only a one-line delegation (`return is_visible_in_view_ada(action, view)`). Added the identical `if prominence == 'Display_Overlay': return True` case AOD's table branch already carries, on the same basis: the 2026-08-31 live app test recorded in `APPSHEET_BEHAVIOR.md`'s "Established behavior" section.
  - **Verified by direct pair-by-pair measurement, not a CSV diff:** ADA feeds only the interactive dependency browser and writes no CSV (`CONSOLIDATION_PLAN.md` section 1), so verification called `is_visible_in_view_ada(action, view)` directly across every `(action, view)` pair in both reference parses (`20260902_131151_AppsheetFarmyApp_for_Kirk_parse`, `20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881`) before and after the change. Farmy: 7,440 pairs flipped, all False→True. Kankaku: 120 pairs flipped, all False→True. Zero pairs flipped True→False in either app, and every flipped pair had `view_type == 'table'` and `action_prominence == 'Display_Overlay'` — the fix changed exactly the intended category and nothing else.
- 2026-09-05, `b68f854` — a slice whose action list mixed `**auto**` with explicitly named actions fell through `views_parser.py`'s sole-entry guard (`len(available_actions) == 1 and available_actions[0] == '**auto**'`), so the view's `available_actions` carried the literal string `**auto**` as though it were an action name and omitted every action the source table auto-assigns. The guard now fires whenever `**auto**` appears anywhere in the list, taking the same wholesale-replacement path the pure-auto case already used. **The platform rule was established by direct editor observation, 2026-09-05, not inferred from the export:** removing a named action from a slice's list and adding `Auto assign` left that action's button rendering anyway, alongside the full table set — so `Auto assign` overrides the explicit list rather than adding to it. Merge order, deduplication and list position are all moot as a result.
  - **Correction to the entry this replaces.** The original Known-defects entry (`1b619a0`) named `actions_orphan_detector.py` as the consumer through which this defect reached output, and predicted a false action-orphan. That was wrong on this data: all 23 candidate rows fail on gates unrelated to `available_actions` — one source view is already listed in `unused_system_views.csv`, three are form/map types for which `is_visible_in_views_aod` has no branch at all, and the three AmendmentPrep candidates are `Do_Not_Display` on a deck. AOD's effect measured exactly zero. The live consumer is `navigation_edge_generator.py` via `is_visible_in_view_neg`, which the original entry did not mention. A third consumer, `format_rule_orphan_detector.py`, reads the field and was not resolved against live data. The original entry also predicted the effect would be confined to the five affected views; that was wrong in principle, since edges from those views land on others.
  - **Verified by control parse at pre-fix HEAD versus post-fix parse, both apps** — not against the saved references, which are stale (see the Known-defects entry above). Kankaku byte-identical across all 14 output files, as predicted (0 mixed slices). Farmy: exactly 5 rows changed in `appsheet_views.csv`, `available_actions` field only (`Amendments Deck` 2→38; `EDIT MyPlants with GPS Location Form`, `MyPlants with GPS Location_Detail`, `MyPlants with GPS Location_Form`, `MyPlantsFoodForestGPS` all 4→108). 92 new `navigation_edges.csv` rows — 81 regular, 11 `via_group`. Zero views added to or removed from `potential_view_orphans.csv` or `unused_system_views.csv`.
  - **Where the advance prediction held and where it did not.** The group-derived count (11) matched exactly a figure computed before the fix was applied. The regular-edge count came in at 81 against 76 predicted; the shortfall was traced to two condition fields misread in the read-only analysis — `Go to TransplantActivity` carries `must_not_be_in_views: 'MyPlants Detail'` (permissive everywhere but that view), not `must_be_in_views`, accounting for +1 on each of four MyPlants views; and `Images_Form - AmendmentPrep`'s second target row is gated by `must_not_be_viewtype: 'Form|||Dashboard|||Detail'`, which a deck does not match, so it passes rather than being blocked, accounting for +1 on `Amendments Deck`. Both fields were afterwards printed verbatim from `action_targets.csv` to confirm the reconciliation rather than leaving it as an after-the-fact story. 4×1 + 1 = 5 reconciles 76→81 exactly.
  - **What a future reader of this diff should not misread.** `available_actions` grows to include actions the slice visibly tried to exclude. That is correct. An explicit action list is a decluttering mechanism, and the old behaviour was reporting the app author's intent rather than the platform's behaviour — the wrong side to be right on for a tool whose job is to model what the platform does.
  - Nine of the new edge rows target views that do not exist — `ActivityForm - Germination` (4), `ActivityForm - Transplant` (4), `ActivityForm Observation` (1). All three names are already recorded above under "Known defects" as app-level defects in the app being analysed, not defects in this tool. No previously unknown phantom target appeared.

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

1. A `CLAUDE.md` at this repository root describing the CSV schemas, which analyzer answers which category of question, the instruction to call analyzer methods directly rather than driving the interactive menus, and the known blind spots. Ship an `AGENTS.md` with the same content for non-Anthropic tools. **Done `1b28db1`, 2026-09-03** — left in this list unmodified so the July plan reads as it was written; see `RELEASE_CHECKLIST.md` section E, which also records the 2026-09-05 decision that a README quick-start, and NOT a separate user guide, is what follows it.
2. Extend the visibility layer to the backing Google Sheet, via an Apps Script dump of formulas and displayed values.
3. A non-interactive query mode with JSON output, canned question recipes, and optionally `SKILL.md` packaging — only if a demonstrated need appears.

## Private working notes

Reproduction details, test data locations, correspondence and the machine-wide inventory are kept outside this repository, at:
`/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/NOTES.md`
