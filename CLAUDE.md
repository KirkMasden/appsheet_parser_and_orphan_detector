# Working with the AppSheet Parser Suite

## What this suite is for

AppSheet answers one direction well. Looking at a screen, you can nearly always work out why what you see is there: the row is rendered, the button is rendered, and the editor will tell you which action produced it. Everything is already resolved, and there is a single path to walk backward.

The other direction is the hard one. Start from an action, or a column, and ask where it appears, whether it appears at all, and what depends on it — and there is no path to walk. There is a conjunction to compute. An inline action reaches a screen only if the view includes the column it attaches to, and that column's own Show_If is true there, and the action's condition is true, and — where it acts through a group — the group parent's condition is true as well, and the view itself is reachable from somewhere. These are independent, and a false in any one of them means an invisible button. Nothing in the editor shows the conjunction; the factors have to be checked one at a time until one comes back false.

That asymmetry is not a gap in anyone's understanding of their own app. It is a property of how apps get built. You start from a goal, you make a component to serve it, and while you are making it you know exactly what you have in mind. AppSheet even provides a Documentation field to record that. But what you know at build time is intent, and the backward question asks about consequence — which changes every time a view is added, a condition edited, or a name changed, with no prompt to revisit anything written earlier. A component's connections are not a property of the component. They are a property of the app around it, and no per-component field can stay true to that.

This suite exports the app definition to CSV and answers the backward question from it, re-deriving the answer from the app as it is now. That is the direction a developer is in whenever they are maintaining, refactoring, or inheriting an app rather than building one — and it is the direction an AI assistant cannot help with by looking at a screen, which is why the export layer matters as much as the analysis built on it.

## What this suite does not see

The single most important limitation, and the one to state before any specific finding:

**The suite reports whether a navigation edge exists, not whether it can fire.**

An edge can exist in the app definition and still never reach a screen. Three known reasons, in decreasing order of tractability:

1. **Conditions the suite reads inconsistently.** Some modules evaluate CONTEXT() conditions through `check_context_conditions`; `view_orphan_detector.py` evaluates no conditions at all. That module is therefore systematically more permissive than its siblings, and under-reports orphans in consequence.

2. **Conditions the suite never reads.** Column-level Show_If is not consulted anywhere in the reachability path, though `appsheet_columns.csv` is loaded. An inline action attaches to a column; if that column does not render, the button does not render, whatever the action's own condition says. This has produced at least one confirmed false clearance (see STATUS.md).

3. **Conditions no static analysis can settle.** `count(Archive[Word])>0`, `INDEX(Cram[Enum],1)="On"`, `[SomeFlag]=TRUE` — these depend on live data, not the app definition. No amount of parsing resolves them. The honest report is that an edge's liveness is conditional and unresolved.

The practical consequence, and the direction of the error: **the suite can under-report orphans.** A view shown as reachable may not be. This runs opposite to the false positives fixed in August 2026, which over-reported. Both errors exist; they are different failures and are recorded separately in STATUS.md.

When answering a reachability question, say which of these applies rather than presenting a clean answer. "Reachable via X" without qualification is frequently wrong.

## How to use this suite well

These rules are not stylistic. Each was learned by getting a wrong answer without it.

**Execute the modules; do not reason from their output alone.** Import the analyzer class and call its methods directly — `ViewOrphanDetector.load_views()`, then `find_all_reachable_views()` and `print_reach_path()`. Do not drive the interactive menus. Questions that CSV inspection failed to answer have been settled in one step by running the module that produces the CSV.

**Count CSV rows with a real CSV parser.** Never `wc -l`, never line-splitting. Several fields in these outputs contain embedded newlines, and naive counting has produced a wrong answer in this project.

**Read the right field for grouped actions.** On `navigation_edges.csv` rows where `action_availability_type` is `via_group`, the button the user actually sees is the parent: read `parent_action` and `parent_prominence`, never `source_action` or `child_prominence`. A group's children are never independently visibility-checked.

**Re-parse before trusting a predicted diff.** Parse output directories are timestamped at parse start, not at code state. Check a parse directory's file mtimes against the code's own history before adopting it as a reference for a given commit. Predictions made against a stale parse have been wrong by nearly two orders of magnitude.

**A prominence value is not a rendering guarantee.** `Display_Prominently`, `Display_Overlay` (the editor's "Primary") and `Display_Inline` each interact with view type, with manual action lists, and — for inline actions — with the attach-to column's own visibility. See APPSHEET_BEHAVIOR.md, which records each platform rule with its source and the strength of that source.

**Check attributions before asserting them.** Three attributions were asserted without checking in one session of this project; two were wrong. Each check would have cost seconds.

**Say when the data does not answer the question.** These CSVs are incomplete in known ways, recorded in STATUS.md. An explicit "the parse does not record this" is more useful than an inference presented as a finding.

## Where to look

- `STATUS.md` — known defects, recently-fixed entries with commit hashes, and remaining work. Read this before trusting any output.
- `APPSHEET_BEHAVIOR.md` — a specification of AppSheet's own client behavior, with sources and an Unknowns section. Platform rules live here, not in STATUS.md.
- `CONSOLIDATION_PLAN.md` — the design for unifying the visibility logic, which is currently implemented in more than one place.

## CSV output reference

Row counts below are from the two reference parses used to generate this section:

- **Kankaku** = `20260902_180356_260831_1809_Kankaku_V18_baseline_parse`
- **Farmy** = `20260902_180352_AppsheetFarmyApp_for_Kirk_parse`

counted with Python's `csv` module (never `wc -l`, since several fields — `view_configuration`, `settings`, `with_these_properties`, `type_qualifier`, `expression`, and others — hold embedded newlines that a line-count would mis-split).

**Conventions used throughout, so they aren't repeated per field:** a field holding more than one value joins them with `|||` (triple pipe) — this shows up on `referenced_*`, `available_*`, `hidden_columns`, `view_columns`, `slice_columns`, `slice_actions`, `formatted_*`, `must_be_*`/`must_not_be_*`, `event_actions`, `onclick_actions`, `dashboard_view_entries`, `missing_view_names`, and `raw_references` on every file that has them. Boolean-shaped fields (`is_virtual`, `hidden`, `key`, `label`, `read-only`, `searchable`, `is_system_view`, `is_disabled`, `is_orphan`, `is_unused`, `modifies_data`, `needs_confirmation`, `bulk_applicable`, `is_system_generated`, `is_self_loop`) are the text strings `Yes`/`No`, not booleans. Every writer's declared or derived field list was checked against the actual header of both reference parses; **no disagreement was found anywhere** — every file below lists one field set because code and output agree on all 16.

One file the code can write was not present in either reference parse: `broken_usersettings_references.csv` (`column_orphan_detector.py`, `write_broken_usersettings_to_csv`) — zero broken `USERSETTINGS()` references were found in either app this run, and per the "write nothing on zero" pattern below, the file simply doesn't exist. Its field list is given from the code only, unverified against real output.

---

### `action_targets.csv`

One row per navigation target resolved out of an action's expression — one action can produce several rows (one per `IF`/`IFS` branch, or per `LINKTOROW`/`LINKTOVIEW` call inside a group). Written by `action_target_parser.py` (`NavigationExpressionParser.parse_actions_csv`).

Rows: Kankaku 290, Farmy 463.

Fields: `source_action`, `source_table`, `action_type`, `action_prominence`, `attach_to_column`, `target_view`, `target_row_expr`, `only_if_condition`, `must_be_in_views`, `must_not_be_in_views`, `must_be_viewtype`, `must_not_be_viewtype`, `must_be_table`, `must_not_be_table`, `ifs_branch_index`, `ifs_branch_text`, `view_match_pattern`, `view_match_type`, `referenced_actions`, `original_expression`, `source_action_normalized`, `target_view_normalized`, `must_be_in_views_normalized`, `must_not_be_in_views_normalized`, `must_be_table_normalized`, `must_not_be_table_normalized`.

- `action_type`: closed vocabulary observed `execute_group`, `go_to_view`, `new_record_form`.
- `ifs_branch_index` / `ifs_branch_text`: only populated when the target came out of an `IFS()`/`IF()` branch; which branch, and its condition text, for tracing a specific row back to its source expression.
- `view_match_type`: observed values `data_dependent_true`, `data_dependent_false`, or empty — flags a target whose resolution itself depends on row data (not a fixed view name).
- `must_be_table` / `must_not_be_table` (and their `_normalized` twins): **empty in every row of both parses.** Confirmed not a defect — `action_target_parser.py` does populate these (search the file for `target['must_be_table']`), the condition shape that would trigger it (a `CONTEXT("Table")`-style restriction) simply doesn't occur in either app's expressions.
- `*_normalized` fields: lowercased/trimmed twins of their un-normalized counterpart, used for case-insensitive matching downstream — read the un-normalized field for what the app author actually wrote.

### `action_targets_unparseable.csv`

Same source as `action_targets.csv` — one row per action expression the parser could not resolve into a target, with the reason and the raw text. Written by `action_target_parser.py` (`write_unparseable_csv`).

Rows: Kankaku 1, Farmy 13.

Fields: `action_name`, `source_table`, `action_type_plain_english`, `action_type_technical_name`, `referenced_columns`, `referenced_actions`, `action_prominence`, `navigate_target`, `referenced_views`, `attach_to_column`, `modifies_data`, `only_if_condition`, `display_name`, `action_icon`, `needs_confirmation`, `bulk_applicable`, `column_to_edit`, `to_this_value`, `with_these_properties`, `raw_references`, `is_system_generated`, `parse_failure_reason`, `expression_attempted`.

- `parse_failure_reason`: closed vocabulary observed `Unknown pattern` and `Forced sync — LINKTOROW to CONTEXT(VIEW), no navigation target` (the latter a deliberate exclusion label, not a real failure — see `STATUS.md`'s `1c22881` entry).
- `referenced_actions`, `referenced_views`, `to_this_value`: empty in every row of both parses — expected here, not a defect: a row only lands in this file because parsing failed before these could be derived.
- First 21 fields are the same shape as `appsheet_actions.csv` (this is a filtered/annotated copy of the source row); the two extra fields are this file's own.

### `appsheet_actions.csv`

One row per action defined in the app, as extracted from the HTML export. Written by `actions_parser.py` (`ActionsParser.save_to_csv`).

Rows: Kankaku 560, Farmy 970.

Fields: `action_name`, `source_table`, `action_type_plain_english`, `action_type_technical_name`, `referenced_columns`, `referenced_actions`, `action_prominence`, `navigate_target`, `referenced_views`, `attach_to_column`, `modifies_data`, `only_if_condition`, `display_name`, `action_icon`, `needs_confirmation`, `bulk_applicable`, `column_to_edit`, `to_this_value`, `with_these_properties`, `raw_references`, `is_system_generated`.

- `action_prominence`: closed vocabulary, exactly four values — `Display_Prominently`, `Display_Overlay`, `Display_Inline`, `Do_Not_Display`. See `APPSHEET_BEHAVIOR.md`'s "Position (prominence) values" for what each does on-screen.
- `action_type_technical_name`: closed vocabulary observed `go_to_view`, `execute_group`, `execute_on_rows`, `open_url`, `edit_form`, `new_record_form`, `set_columns`, `delete`, `unclassified`.
- `attach_to_column`: which column's row an inline action's button renders beside — misuse trap: **the action can still be blocked from view if that column's own `Show_If` is false**, and nothing in this suite's reachability path checks that (see `STATUS.md`, "Column-level `Show_If` is never consulted").
- `navigate_target`: **not** what downstream code parses — `action_target_parser.py` reads the raw, un-normalized copy of this field, while `actions_parser.py` itself normalizes a separate local copy for its own `referenced_views`. The two views of the same expression can disagree on curly-vs-straight quotes (`STATUS.md`, "`actions_parser.py` normalizes curly quotes for one consumer... and not the other").
- `display_name`: can be a literal quoted string (the actual on-screen button text), an expression, or blank/whitespace-only (an icon-only button) — read it as a formula, not assume it's the label a user sees.
- `is_system_generated`: `Yes`/`No` — whether AppSheet auto-created this action (e.g. default `Add`/`Edit`/`Delete`) versus the app author.

### `appsheet_columns.csv`

One row per column, across every table and slice, as extracted from the HTML export. Written by `column_parser.py` (`ColumnParser.save_to_csv`).

Rows: Kankaku 1064, Farmy 1456.

Fields: `table_name`, `column_number`, `column_name`, `unique_identifier`, `is_virtual`, `type`, `description`, `referenced_columns`, `app_formula`, `display_name`, `initial_value`, `type_qualifier_formulas`, `type_qualifier`, `show_if`, `required_if`, `editable_if`, `valid_if`, `reset_if`, `suggested_values`, `formula_context_table`, `key`, `label`, `hidden`, `read-only`, `searchable`, `ref_table`, `related_view_source`, `component_type`, `editable_initial_value`, `fixed_definition`, `localename`, `nfc_scannable`, `part_of_key`, `raw_references`, `reset_on_edit`, `scannable`, `sensitive_data`, `spreadsheet_formula`, `system_defined`. (First 27 fields are a fixed priority order in code; the last 12 are every other field found in the parsed data, alphabetically appended — stable in practice, but not a hand-maintained literal list the way the first 27 are.)

- **`show_if`, `required_if`, `editable_if`, `valid_if`, `reset_if`: empty in every row of both parses, by defect, not by design.** `show_if` is the one `STATUS.md` names directly ("`column_parser.py` never populates the `show_if` field it emits"); reading the code shows the **same root cause reaches all five** — `column_parser.py` (lines ~284–315) maps each of `Show_If`/`Required_If`/`Editable_If`/`Valid_If`/`Reset_If` out of the `type_qualifier` JSON blob, but only to extract cross-references, never to populate the corresponding top-level field. `STATUS.md` records only the `show_if` instance; the other four are the same bug, unrecorded there. **The real values live in the `type_qualifier` JSON column, under the matching capitalized key** (`type_qualifier_formulas` also carries a human-readable copy, but it disagreed with `type_qualifier` on 4 Kankaku rows — prefer `type_qualifier`).
- `type_qualifier`: a JSON object; parse it (`json.loads`) rather than string-matching it. Two Kankaku rows (`Settings[Update success]`, `Settings[Update success J]`) have unescaped quotes inside this JSON that break `json.loads()` — see `STATUS.md`, "Malformed `type_qualifier` JSON silently drops two Kankaku columns."
- `is_virtual`, `hidden`, `key`: `Yes`/`No`.
- `related_view_source`: populated only for Related-type ref columns; see `navigation_edge_generator.py`'s `related_column` edges below.

### `appsheet_format_rules.csv`

One row per conditional-formatting rule, as extracted from the HTML export. Written by `format_rules_parser.py`.

Rows: Kankaku 119, Farmy 250.

Fields: `rule_name`, `source_table`, `referenced_columns`, `formatted_columns`, `formatted_actions`, `formatted_items`, `formatted_columns_count`, `formatted_actions_count`, `condition`, `readable_settings`, `is_disabled`, `settings`, `comment`, `raw_references`.

- `settings`: raw JSON of the rule's visual formatting (color, style); `readable_settings` is the human-readable rendering of the same data.
- `formatted_columns_count` / `formatted_actions_count`: counts, not `|||`-joined lists — derived from `formatted_columns`/`formatted_actions`.
- `is_disabled`: `Yes`/`No`.

### `appsheet_slices.csv`

One row per slice (a filtered view of a table), as extracted from the HTML export. Written by `slice_parser.py`.

Rows: Kankaku 57, Farmy 195.

Fields: `slice_name`, `source_table`, `referenced_columns`, `row_filter_condition`, `slice_columns`, `slice_actions`, `formula_context_table`, `update_mode`, `visible`, `raw_references`.

- `update_mode`: closed vocabulary observed `ALL_CHANGES`, `READ_ONLY`, `ADDS_ONLY`, `UPDATES_ONLY`.
- `visible`: only value observed in either app is `ALWAYS` — this field can plausibly carry a conditional expression in other apps; treat the single observed value as this pair of apps' data, not as the full vocabulary.

### `appsheet_views.csv`

One row per view in the app, as extracted from the HTML export. Written by `views_parser.py`.

Rows: Kankaku 197, Farmy 319.

Fields: `view_name`, `view_type`, `category`, `is_system_view`, `data_source`, `source_table`, `position`, `ref_parent`, `display_mode`, `use_card_layout`, `show_action_bar`, `action_display_mode`, `referenced_actions`, `event_actions`, `onclick_actions`, `available_actions`, `view_columns`, `available_columns`, `hidden_columns`, `referenced_columns`, `dashboard_view_entries`, `show_if`, `icon`, `created_by`, `action_type`, `html_position`, `view_configuration`.

- `view_type`: closed vocabulary observed `detail`, `form`, `table`, `deck`, `dashboard`, `map`, `gallery`, `card`, `calendar`.
- `category`: closed vocabulary observed `primary`, `menu`, `ref` — `primary` and `menu` views are this suite's BFS root set (`view_orphan_detector.py`'s `find_all_reachable_views`); everything else must be reached through an edge.
- `position`: only meaningful (non-empty) for `category == primary` views — governs bottom-nav placement (`first`/`next`/`middle`/`later`/`last`); empty on every other category by design.
- `action_display_mode`: `Manual` vs. automatic action-list membership — misuse trap: `navigation_edge_generator.py` only reads this field inside its deck-view check; a manual action list on any other view type is not currently enforced (`STATUS.md`, "Manual action-list exclusion may not be enforced outside deck views").
- `show_if`: this is the **view's own** `Show_If`, populated correctly by `views_parser.py` — do not confuse with `appsheet_columns.csv`'s always-empty `show_if` above; they're different fields written by different parsers, and this one works.
- `onclick_actions`: added by commit `59db213` (custom-canvas onClick bindings) — a Kankaku/Farmy parse from before that commit will lack this column entirely, not merely have it blank.
- `view_configuration`: raw JSON of the view's full configuration (column order, action bar entries, layout); several of the other fields here are convenience extracts from it.

### `navigation_edges.csv`

One row per resolved navigation possibility between two views (or a self-loop) — the graph every orphan/reachability detector traverses. Built by combining `action_targets.csv` with `appsheet_actions.csv`/`appsheet_views.csv`/`appsheet_columns.csv`/`appsheet_slices.csv`. Written by `navigation_edge_generator.py`.

Rows: Kankaku 585, Farmy 1971.

Fields: `source_view`, `source_view_type`, `target_view`, `source_action`, `parent_action`, `action_type`, `action_availability_type`, `parent_prominence`, `child_prominence`, `event_type`, `is_self_loop`, `must_be_in_views`, `must_not_be_in_views`, `must_be_viewtype`, `must_not_be_viewtype`, `must_be_table`, `must_not_be_table`, `available_actions`, `original_expression`, `source_view_normalized`, `target_view_normalized`, `source_action_normalized`, `must_be_in_views_normalized`, `must_not_be_in_views_normalized`, `must_be_table_normalized`, `must_not_be_table_normalized`.

- **`action_availability_type` — closed vocabulary, six values, and the field most likely to be misread:** `direct`, `event`, `via_group`, `auto`, `dashboard`, `related_column`.
  - `direct` / `event`: an ordinary action edge. The prominence that gates whether it's actually visible is in **`parent_prominence`**.
  - **`via_group`: read `parent_action` and `parent_prominence`, not `source_action` or `child_prominence`.** `child_prominence` is the invoked child action's own prominence, but a group's children are never independently visibility-checked (`action_visibility.py`'s module docstring) — it's the **group container's** prominence, found via `parent_action` cross-referenced against `appsheet_actions.csv`, that gates whether the whole group (and every child edge under it) is visible at all. Getting this backwards misclassifies exactly which edges a prominence rule touches — `STATUS.md`, "Reading `navigation_edges.csv`'s prominence off the wrong field for `via_group` rows," documents a real case where this produced a wrong prediction.
  - `auto` / `dashboard` / `related_column`: no action is involved at all (row-tap-to-detail, a dashboard embedding a view, or a Related-type column's display view) — **`parent_prominence` and `child_prominence` are both blank** on these rows, and `source_action`/`parent_action` are blank or the synthetic marker `**auto**`. Nothing here is gated by an action's display setting.
- `must_be_table` / `must_not_be_table` (+ `_normalized`): empty in every row of both parses, same as in `action_targets.csv`, same non-defect explanation.
- `is_self_loop`: `Yes`/`No` — `target_view == source_view`.
- `event_type`: closed vocabulary observed `row selected`, `form saved`, or empty.
- `available_actions`: the full `|||`-joined action list available on `source_view` at the time this edge was generated — useful for confirming an action was actually reachable from that view, not just present in the app.

### `potential_action_orphans.csv`

Actions the suite found no visible invocation route for — one row per candidate, the full `appsheet_actions.csv` row plus this file's own fields. Written by `actions_orphan_detector.py`.

Rows: Kankaku 2, Farmy 87.

Fields: `action_name`, `source_table`, `notes`, `orphan_type`, `action_type_plain_english`, `action_type_technical_name`, `referenced_columns`, `referenced_actions`, `action_prominence`, `navigate_target`, `referenced_views`, `attach_to_column`, `modifies_data`, `only_if_condition`, `display_name`, `action_icon`, `needs_confirmation`, `bulk_applicable`, `column_to_edit`, `to_this_value`, `with_these_properties`, `raw_references`, `is_system_generated`, `is_orphan`, `reference_count`.

- `is_orphan`: always `Yes` in this file, on every row of both parses — the field only appears on rows that already qualified, so it's not something to filter on; it's a vestige of a shared code path with `appsheet_actions.csv` rows that carry the same field.
- `orphan_type`: closed vocabulary in code (`standard` vs. a group-member variant carrying an `UNREACHABLE - Remove from: ...` message in `notes`), but **only `standard` occurs, and `notes` is empty, in both current parses** — the group-member branch exists but wasn't exercised by either app's current data.
- Misuse trap flagged already at the source in `STATUS.md`: **`action_name` is not unique** — the same generic name (`Add`, `Edit`, `Delete`, …) recurs once per table in Farmy. Any diff or lookup against this file must key on `(action_name, source_table)` at minimum ("Diffing orphan-detector output by `action_name` alone is unreliable").

### `potential_format_rule_orphans.csv`

Format rules whose formatted columns/actions the suite could not find as existing and visible. Written by `format_rule_orphan_detector.py`.

Rows: Kankaku **absent** (zero found — see "write nothing on zero" below), Farmy 32.

Fields: the 14 `appsheet_format_rules.csv` fields plus `is_orphan`, `formatted_items_count`.

- `comment`: empty on every Farmy row here — a free-text field format-rule authors can optionally set; empty because none of the orphaned rules happen to have one, not a code defect.

### `potential_phantom_view_references.csv`

Places in the app that name a view which does not exist anywhere in `appsheet_views.csv` — actions' navigation targets, actions' `only_if_condition` text, and column `Show_If`/qualifier text, each checked by a different code path. Written by `phantom_view_reference_detector.py`.

Rows: Kankaku 2, Farmy 56.

Fields: `name`, `type`, `table`, `field`, `missing_view_names`, `expression`.

- `type`: closed vocabulary observed `Action`, `Column`, `Format Rule`.
- **Known accuracy gap, misuse trap:** the code path that checks `CONTEXT()`-based conditions (`is_phantom_reference`) matches view names **case-sensitively**, while the action-target-based path lowercases both sides first. The two Kankaku rows currently in this file are a confirmed false positive from that inconsistency — `Card status`/`Card status J` test `Context("View")="Card Stats"`, which matches the app's real view `Card stats` case-insensitively at runtime (`STATUS.md`, "`phantom_view_reference_detector.py` matches view names case-sensitively"). Not checked for Farmy.

### `potential_slice_orphans.csv`

Slices the suite found no reference to from any view, action, column, or format rule. Written by `slice_orphan_detector.py`.

Rows: Kankaku 1, Farmy 66.

Fields: the 10 `appsheet_slices.csv` fields plus `is_orphan`, `reference_count`.

- `is_orphan`: always `Yes` here, same vestige as `potential_action_orphans.csv`.

### `potential_usersettings_orphans.csv`

User Settings columns (referenced via `USERSETTINGS()`) the suite found no reference to. Written by `column_orphan_detector.py` (`write_user_settings_orphans_to_csv`). Part of the December 2025 work `STATUS.md` records as shipped with an explicit, still-unverified "needs more testing" caveat.

Rows: Kankaku 2, Farmy 2.

Fields: `table_name`, `column_number`, `column_name`, `unique_identifier`, `is_virtual`, `type`, `description`, `referenced_columns`, `app_formula`, `display_name`, `initial_value`, `orphan_reason`.

- `app_formula`, `description`, `display_name`, `initial_value`, `referenced_columns`: empty on every row of both parses — plausibly because the two flagged columns per app are plain settings values with none of these set, not confirmed as a code defect (sample size is 2 rows per app either way).
- A sibling file, `broken_usersettings_references.csv` (same detector, `write_broken_usersettings_to_csv`), exists in code but was not produced by either reference parse — see the note at the top of this section.

### `potential_view_orphans.csv`

User-created views not reachable, by BFS over `navigation_edges.csv`, from any root (`category` `primary` or `menu`) view. Written by `view_orphan_detector.py`.

Rows: Kankaku **absent** (zero found), Farmy 54.

Fields: the 27 `appsheet_views.csv` fields plus `is_orphan`, `orphan_reason`.

- `orphan_reason`: closed vocabulary observed `Detail view not reachable from any root view`, `Ref view not reachable from any root view`.
- `dashboard_view_entries`, `position`: empty on every Farmy row here — structurally expected: a `primary`-category view (the only category `position` is meaningful for) is by definition a BFS root and can't appear as unreachable; a dashboard view containing others is reachable by definition if any of its contents are referenced elsewhere. Not a defect.
- **This file's reachability is permissive, not exhaustive** — `view_orphan_detector.py` performs no `CONTEXT()` evaluation anywhere in the module (confirmed by grep, zero hits) and never reads column-level `Show_If` (loads `appsheet_columns.csv` into `self.columns_by_table` and never reads it again). A view absent from this file is not proven reachable; it means no *structural* obstruction was found (`STATUS.md`, "`view_orphan_detector.py` never evaluates `CONTEXT()`" and "Column-level `Show_If` is never consulted").
- **This file simply does not exist when the count is zero** (Kankaku, here) — not a header-only file. Diffing parse directories by file presence alone will misread "cleared to zero" as "never ran" (`STATUS.md`, "`view_orphan_detector.py` also writes no `potential_view_orphans.csv` on a zero result" — the same pattern holds for `potential_format_rule_orphans.csv` above and, per that entry, likely all five orphan detectors).

### `potential_virtual_column_orphans.csv`

Virtual (computed) columns the suite found no reference to from any other column, view, action, format rule, or slice — with a per-category reference count. Written by `column_orphan_detector.py`.

Rows: Kankaku 2, Farmy 27.

Fields: the 39 `appsheet_columns.csv` fields plus `total_references`, `columns_refs`, `views_refs`, `actions_refs`, `format_rules_refs`, `slices_refs`.

- Inherits `appsheet_columns.csv`'s `show_if`/`required_if`/`editable_if`/`valid_if`/`reset_if` always-empty defect (same root cause, described above) — also empty here in every row.
- Also empty in every row here: `description`, `initial_value`, `nfc_scannable`, `ref_table`, `spreadsheet_formula`, `suggested_values` — plausibly legitimate for virtual columns specifically (a computed column has no `initial_value`, no physical-sheet `ref_table`/`spreadsheet_formula`/`nfc_scannable` binding), not independently confirmed as intentional in code.
- `*_refs` fields are counts, not `|||`-joined lists, despite the plural-sounding name.

### `unused_system_views.csv`

System-generated views (the `Detail`/`Form`/etc. AppSheet auto-creates per table) not reachable by the same BFS as `potential_view_orphans.csv`. Written by `view_orphan_detector.py`.

Rows: Kankaku 64, Farmy 99.

Fields: the 27 `appsheet_views.csv` fields plus `is_unused`, `unused_reason`.

- `unused_reason`: closed vocabulary observed `System detail view not reachable from any root view`, `System ref view not reachable from any root view`.
- `show_if` empty on every row here is a data coincidence for this particular subset (these system views simply don't have a `Show_If` condition set), **not** the `appsheet_columns.csv` defect above — `views_parser.py` does populate `show_if` correctly in general (confirmed elsewhere in `appsheet_views.csv`, e.g. Kankaku's `D to W` view carries `=count(D to W[Key])>0`).
- Same permissive-reachability caveat as `potential_view_orphans.csv` above, and same "file absent on zero" behavior applies to this detector's write of this file too.

---

## Module reference

"Worth calling directly" below means: importable, instantiable, and answerable without going through `master_parser_and_orphan_detector.py`'s interactive menu or a module's own `input()`-driven browser — the same pattern already used in this project to answer real questions (`ViewOrphanDetector.find_all_reachable_views()` / `print_reach_path()`, called directly against a parse directory, has settled reachability questions CSV inspection alone could not). Where a module's public surface is a menu instead, that's said plainly, not implied.

### Parsers

Run, in this order, by `master_parser_and_orphan_detector.py`'s `run_all_parsers`: slices → columns → format rules → actions → views → action targets → navigation edges. Each later stage depends on files the earlier ones wrote.

#### `base_parser.py` — `BaseParser`

Answers no question on its own — abstract base class (`ABC`) for the five HTML-scraping parsers below. Not directly usable: instantiating it raises (`parse()` and `get_standard_fields()` are abstract).

- Shared methods worth knowing when reading a subclass: `normalize_string(s)`, `extract_references_from_text(text, context_table=None)`, `extract_references_from_json(json_str, context_table=None)`, `build_absolute_references(references)`, `resolve_table_reference(table_or_slice_name)`.
- Requires: nothing to import; requires a concrete subclass to instantiate.
- Reads/writes: nothing itself.

#### `slice_parser.py` — `SliceParser(BaseParser)`

Answers: *"What slices exist, and what do they filter/expose?"*

- Worth calling directly: `SliceParser(html_path).parse()`, then `.save_to_csv(output_path=None, filename='appsheet_slices.csv')`.
- Also useful standalone: `print_hierarchical_summary()` (console report, no return value worth capturing programmatically).
- Requires: an AppSheet HTML documentation export (`Application Documentation.html`); no other CSV needs to exist first — it's the pipeline's first stage.
- Reads: the HTML export. Writes: `appsheet_slices.csv`.

#### `column_parser.py` — `ColumnParser(BaseParser)`

Answers: *"What columns exist on every table, with their types and formulas?"*

- Worth calling directly: `ColumnParser(html_path).parse()`, then `.save_to_csv(output_path='appsheet_columns.csv')`.
- Requires: the HTML export; `load_slice_mapping(csv_path='appsheet_slices.csv')` expects `appsheet_slices.csv` to already exist (run `slice_parser.py` first).
- Reads: the HTML export, `appsheet_slices.csv`. Writes: `appsheet_columns.csv`.
- Carries the `show_if`/`required_if`/`editable_if`/`valid_if`/`reset_if` never-populated defect described in the CSV reference above.

#### `format_rules_parser.py` — `FormatRulesParser(BaseParser)`

Answers: *"What conditional formatting rules exist, and what do they format?"*

- Worth calling directly: `FormatRulesParser(html_path).parse()`, then `.save_to_csv(output_path=None, filename='appsheet_format_rules.csv')`.
- Requires: the HTML export; `load_slice_mapping` expects `appsheet_slices.csv` to exist first.
- Reads: the HTML export, `appsheet_slices.csv`. Writes: `appsheet_format_rules.csv`.

#### `actions_parser.py` — `ActionsParser(BaseParser)`

Answers: *"What actions exist, and what are their type/prominence/target/conditions?"*

- Worth calling directly: `ActionsParser(html_path).parse()`, then `.save_to_csv(output_path=None, filename='appsheet_actions.csv')`.
- Requires: the HTML export; `load_slice_mapping` expects `appsheet_slices.csv` first.
- Reads: the HTML export, `appsheet_slices.csv`. Writes: `appsheet_actions.csv`.
- Carries the curly-quote/normalization split between `navigate_target` and its own `referenced_views` described in the CSV reference above.

#### `views_parser.py` — `ViewsParser(BaseParser)`

Answers: *"What views exist, with their type/position/columns/actions?"*

- Worth calling directly: `ViewsParser(html_path).parse(html_path=None)`, then `.save_to_csv(output_path=None, filename='appsheet_views.csv')`.
- Also useful standalone: `print_summary()` (console report).
- Requires: the HTML export; `load_slice_mapping`, `load_actions_mapping`, `load_columns_data`, `load_actions_data` expect `appsheet_slices.csv`, `appsheet_actions.csv`, and `appsheet_columns.csv` to already exist — run slices, columns, and actions first.
- Reads: the HTML export, `appsheet_slices.csv`, `appsheet_actions.csv`, `appsheet_columns.csv`. Writes: `appsheet_views.csv`.

#### `action_target_parser.py` — `NavigationExpressionParser`

Answers: *"What does each action's navigation expression actually resolve to, view by view and branch by branch?"*

- Worth calling directly: construct with no arguments, then `load_views_csv(views_file)`, then `parse_actions_csv(input_file, output_file)` — the latter writes both `action_targets.csv` and (via `write_unparseable_csv`) `action_targets_unparseable.csv` in one call. `get_action_counts()`, `get_target_counts()`, `get_context_counts()`, `get_unparseable_counts()` are cheap post-hoc summaries.
- Requires: `appsheet_views.csv` (for `load_views_csv`) and `appsheet_actions.csv` (as `parse_actions_csv`'s `input_file`) to already exist.
- Reads: `appsheet_views.csv`, `appsheet_actions.csv`. Writes: `action_targets.csv`, `action_targets_unparseable.csv`.
- Performs no `CONTEXT()` evaluation of its own beyond structural parsing; see `navigation_edges.csv`'s reachability caveat above for how that limitation propagates.

#### `navigation_edge_generator.py` — `NavigationEdgeGenerator`

Answers: *"Given everything parsed so far, what view-to-view navigation edges actually exist, and under what conditions?"* — the graph every downstream orphan/reachability question is asked against.

- Worth calling directly: `NavigationEdgeGenerator(output_dir).load_action_targets()`, `.load_actions()`, `.load_views()`, `.load_columns()`, `.load_slices()` (each returns `False` and degrades gracefully, not raises, if its file is missing), then whatever top-level generation method wraps `process_group_action`/`process_dashboard_containment`/etc. (`main()` shows the intended call order — read it before scripting this one, since it's the module with the most load-order dependencies of the whole suite).
- Requires: `action_targets.csv`, `appsheet_actions.csv`, `appsheet_views.csv`, `appsheet_columns.csv`, `appsheet_slices.csv` — i.e., everything above must already exist.
- Reads: all five files just named. Writes: `navigation_edges.csv`.
- Hard constraint, load-bearing for the whole suite's orphan counts: its group-child edge loop deliberately performs **no** visibility check (`action_visibility.py`'s module docstring) — that's what lets group-membership invocation routes produce edges at all. Do not "fix" this without reading `CONSOLIDATION_PLAN.md` sections 1 and 6 first.

### Analyzers

Interactive, `input()`-driven browsers for a human exploring dependencies — not, in the main, meant to be scripted. `dependency_analyzer_hub.py` is the menu that routes to the other three; none of the three write any CSV.

#### `view_dependency_analyzer.py` — `ViewDependencyAnalyzer`

Answers: *"How do users reach this specific view, and where can they go from it?"* — for a human, interactively, by default.

- Primary interface is `run(return_to_hub=False)`, an interactive search-and-browse loop — **not** intended for direct scripted use.
- **Exception, worth calling directly:** `ViewDependencyAnalyzer(base_path).load_views_data()`, then `find_paths_to_view(target_view_name, max_paths=5)` returns up to `max_paths` concrete paths (as lists of formatted step strings) from every primary/menu root to the named view — no `input()` involved. Complementary to `view_orphan_detector.py`'s `find_all_reachable_views()`/`print_reach_path()`: that one gives yes/no reachability plus one path per view (first-found by BFS); this one is built to enumerate several paths to one specific, already-known view.
- Requires: a directory containing `appsheet_views.csv`, `navigation_edges.csv`, `unused_system_views.csv` (`load_views_data`, `load_unused_system_views`).
- Reads: `appsheet_views.csv`, `navigation_edges.csv`, `unused_system_views.csv`. Writes: nothing.

#### `column_dependency_analyzer.py` — `ColumnDependencyAnalyzer`

Answers: *"What does this column reference, and what references it — across views, slices, format rules, and actions?"* — for a human, interactively.

- Primary interface is `run(return_to_hub=False)`; almost every other public method (`show_*_menu`, `display_*`, `get_user_selection`) is a piece of that same interactive loop. Not intended for direct scripted use — unlike `view_dependency_analyzer.py`, there's no documented non-interactive entry point here; `analyze_column_dependencies(selected_column)` exists and returns data, but expects a row dict already selected by the interactive search, not a bare name.
- Requires: a directory containing `appsheet_columns.csv`, `appsheet_slices.csv`, `appsheet_actions.csv`, `appsheet_views.csv`, `appsheet_format_rules.csv` (its five `load_*_data` methods).
- Reads: all five files just named. Writes: nothing.

#### `action_dependency_analyzer.py` — `ActionDependencyAnalyzer`

Answers: *"What does this action call, what calls it, and what's the full chain of grouped actions around it?"* — for a human, interactively.

- Primary interface is `run(return_to_hub=False)`. Every other public method is part of that interactive surface (`search_by_name`, `browse_by_table`, `browse_by_type`, `show_*_menu`, `build_action_hierarchy`, …).
- **Feeds nothing programmatic** — confirmed in `STATUS.md`: its own visibility check (`is_action_visible_in_view`) has no `Display_Overlay` case for table views and falls through to `False`, a real defect, but "nothing programmatic consumes this function's answer — it feeds only the interactive dependency browser." This is the module `STATUS.md` names as the example of "exists only to serve an interactive browser and feeds nothing programmatic."
- Requires: a directory containing `appsheet_actions.csv`, `appsheet_columns.csv`, `appsheet_views.csv`, `appsheet_slices.csv`, `appsheet_format_rules.csv`.
- Reads: all five files just named. Writes: nothing.

#### `dependency_analyzer_hub.py` — `DependencyAnalyzerHub`

Answers nothing itself — a menu that routes to the three analyzers above (`run_column_analyzer`, `run_action_analyzer`, `run_view_analyzer`, each just constructing and calling the corresponding analyzer's own `run(return_to_hub=True)`). Purely interactive; `run()` is the only entry point worth knowing, and it's a `while True` menu loop.

- Requires: whatever the analyzer the user picks requires (the union of the three above).
- Reads/writes: nothing itself.

### Orphan detectors

Each exposes a plain, non-interactive `run_analysis()` that mirrors what its own CLI `main()` does, plus finer-grained methods for a targeted question — no `input()` anywhere in this group. All are intended for direct method-calling.

#### `view_orphan_detector.py` — `ViewOrphanDetector`

Answers: *"Which views (user or system) are unreachable from app entry points, and by what path is a given view actually reached?"*

- Constructor: `ViewOrphanDetector(parse_directory)`.
- Worth calling directly: `run_analysis()` (returns `(orphan_candidates, unused_system_views)`, writes both output files, matches CLI behavior exactly); or, for a targeted question, `validate_files()` → `load_views()` → `load_columns_data()` (optional) → `find_all_reachable_views()` (returns the reachable-view set and populates `self.reach_paths`) → `print_reach_path(view_name)` (prints one concrete path). This exact sequence — skipping `run_analysis()`'s file-writing — is what already answered reachability questions in this project that reading the CSVs by hand could not.
- Requires: `appsheet_views.csv`, `appsheet_actions.csv` (validated as required but never actually read — see below), `navigation_edges.csv`; `appsheet_columns.csv` is optional (loaded, then never read again — see the CSV reference above and `STATUS.md`).
- Reads: `appsheet_views.csv`, `navigation_edges.csv`, `appsheet_columns.csv` (loaded, unused). Writes: `potential_view_orphans.csv`, `unused_system_views.csv` (each only if non-empty).
- Carries this suite's most consequential known gap: no `CONTEXT()` evaluation anywhere, and no column-`Show_If` check — both described in the CSV reference above, both in `STATUS.md`.

#### `actions_orphan_detector.py` — `ActionOrphanDetector`

Answers: *"Which actions have no visible invocation route from any view?"*

- Constructor: `ActionOrphanDetector(parse_directory)`.
- Worth calling directly: `run_analysis()` (returns `orphan_candidates`, writes the file); or `validate_files()` → `load_actions()` → `load_view_data()` → `find_orphan_candidates()` for the list without the write.
- Requires: `appsheet_actions.csv`, `appsheet_views.csv`; `appsheet_columns.csv` for `column_exists` checks.
- Reads: `appsheet_actions.csv`, `appsheet_views.csv`, `appsheet_columns.csv`, `unused_system_views.csv` (`load_unused_system_views`). Writes: `potential_action_orphans.csv` (only if non-empty).
- Its own visibility check now routes through `action_visibility.py`'s shared `is_visible_in_views_aod` (per that module's docstring: "in production use"), with the `Do_Not_Display`-comparison bug fixed there.

#### `column_orphan_detector.py` — `VirtualColumnOrphanDetector`

Answers: *"Which virtual columns (and which User Settings columns) have no reference anywhere in the app?"* — two related but separate questions, both answered by this one class.

- Constructor: `VirtualColumnOrphanDetector(parse_directory)`.
- Worth calling directly: `run_analysis()` (runs all three checks below and writes whichever files have content; returns only the virtual-column list); or individually — `find_potential_orphans()` (virtual columns), `find_user_settings_orphans()` (`USERSETTINGS()` columns), `find_broken_usersettings_refs()` (malformed `USERSETTINGS()` references) — each callable on its own after `validate_files()`.
- Requires: `appsheet_columns.csv`; the reference search also reads `appsheet_views.csv`, `appsheet_actions.csv`, `appsheet_format_rules.csv`, `appsheet_slices.csv`.
- Reads: `appsheet_columns.csv`, `appsheet_views.csv`, `appsheet_actions.csv`, `appsheet_format_rules.csv`, `appsheet_slices.csv`, `unused_system_views.csv`. Writes: `potential_virtual_column_orphans.csv`, `potential_usersettings_orphans.csv`, `broken_usersettings_references.csv` (each only if non-empty — the third wrote nothing in either reference parse).
- The User Settings functionality (all three of `find_user_settings_orphans`, `find_broken_usersettings_refs`, and the underlying `USERSETTINGS()` parsing) is the work `STATUS.md` records as unverified since 2025-12-24.

#### `slice_orphan_detector.py` — `SliceOrphanDetector`

Answers: *"Which slices are never referenced by any view, action, column, or format rule?"*

- Constructor: `SliceOrphanDetector(parse_directory)`.
- Worth calling directly: `run_analysis()` (returns `orphan_candidates`, writes the file); or `validate_files()` → `load_slices()` → `find_orphan_candidates()` (which itself calls `check_view_references`, `check_action_references`, `check_column_references`, `check_format_rule_references`) for the list alone.
- Requires: `appsheet_slices.csv`; the reference checks also read `appsheet_views.csv`, `appsheet_actions.csv`, `appsheet_columns.csv`, `appsheet_format_rules.csv`.
- Reads: all five files just named. Writes: `potential_slice_orphans.csv` (only if non-empty).

#### `format_rule_orphan_detector.py` — `FormatRuleOrphanDetector`

Answers: *"Which format rules format a column/action that no longer exists or isn't visible?"*

- Constructor: `FormatRuleOrphanDetector(parse_directory)` — **note the attribute name is `self.parse_directory`**, not `self.parse_dir` as in its four siblings above; a script written against one won't work unmodified against the other.
- Worth calling directly, with a caveat: `run_analysis()` runs the full pipeline and writes the file — **but its `run_analysis()` has no `return` statement and always yields `None`**, unlike every other orphan detector's `run_analysis()`. Call `find_orphan_candidates()` directly (after `validate_files()` and the `load_*` calls `run_analysis()`'s source shows in order) if the list itself is needed.
- Requires: `appsheet_format_rules.csv`; visibility/existence checks also read `appsheet_slices.csv`, `appsheet_columns.csv`, `appsheet_actions.csv`, `appsheet_views.csv`, `potential_view_orphans.csv`, `unused_system_views.csv`.
- Reads: all files just named. Writes: `potential_format_rule_orphans.csv` (only if non-empty).

#### `phantom_view_reference_detector.py` — module-level functions, no class

Answers: *"Does anything in the app — an action target, an action's condition, or a column's `Show_If`/qualifier text — name a view that doesn't exist?"*

- Worth calling directly, and the simplest module in the suite to do so: `find_phantoms(parse_dir)` returns the full phantom list in one call (no object to construct); `write_results(parse_dir, phantoms)` persists it. `main()` is exactly these two calls plus print statements.
- Requires: `appsheet_views.csv` (to build the known-view set); `action_targets.csv` preferred for the action-target check, with `appsheet_actions.csv` as fallback; also reads `appsheet_columns.csv`, `appsheet_format_rules.csv` for their condition/qualifier text.
- Reads: `appsheet_views.csv`, `action_targets.csv` or `appsheet_actions.csv`, `appsheet_columns.csv`, `appsheet_format_rules.csv`. Writes: `potential_phantom_view_references.csv` (only if non-empty).
- Carries the case-sensitivity inconsistency between its two internal check paths described in the CSV reference above.

### Anything else

#### `action_visibility.py` — shared library, no class, not directly invoked

Answers nothing on its own — a behavior-preserving extraction of three previously-duplicated "is this action visible in this view" implementations (`navigation_edge_generator.py`'s NEG, `actions_orphan_detector.py`'s AOD, `action_dependency_analyzer.py`'s ADA), each now a plain function here and called by its original owner. Public functions: `is_visible_in_detail_view_neg`, `is_visible_in_deck_view_neg`, `is_visible_in_table_view_neg`, `is_visible_in_view_neg`, `is_visible_in_view_ada`, `is_visible_in_views_aod` — each takes the action/view dict(s) its name suggests, no shared state.

- Not meant to be called on its own outside the module that owns each strategy — read together with the caller, since each function is a faithful translation of that caller's original method, bugs (now-fixed) and all.
- Hard constraint stated in its own module docstring: none of this is called from `navigation_edge_generator.py`'s group-child edge loop, deliberately — see `navigation_edge_generator.py`'s entry above.
- Reads/writes no CSVs itself — pure functions over dicts its caller already loaded.

#### `csv_limits.py` — import-time side effect only

Answers nothing — raises `csv.field_size_limit()` to `min(sys.maxsize, 2**31-1)` process-wide the moment it's imported, so every module that reads or writes a CSV with a very long field (`view_configuration`, `with_these_properties`, `type_qualifier`, chart-URL formulas) doesn't hit Python's default field-size ceiling. Every parser, analyzer, and detector in this suite imports it purely for that side effect (`import csv_limits  # noqa`). No class, no function meant to be called.

#### `master_parser_and_orphan_detector.py` — top-level CLI orchestrator, no class

Answers: *"Run the whole pipeline against one HTML export, in the right order, and write everything."* Not a library module — a `main()` built on `argparse`, meant to be invoked as `python master_parser_and_orphan_detector.py <html_file> [-o output_dir] [stage flags]`. Its own functions (`run_slice_parser`, `run_column_parser`, …, `run_all_parsers`) are thin wrappers around the parser/generator classes documented above, in the dependency order those entries describe.

- Not worth calling its functions directly instead of the classes they wrap — they exist to sequence CLI flags, not to offer a cleaner API than the classes themselves.
- **Known limitation for scripted use:** raises `EOFError` on its trailing interactive "Would you like to explore dependencies now? (y/n)" prompt when run without stdin — by that point all CSV output is already written, so it's not a parse failure, but a caller driving this from a script without supplying stdin will see the process end in an unhandled exception rather than a clean exit (`STATUS.md`, "Two smaller anomalies from the Kankaku run").
- Requires: an AppSheet HTML documentation export. Reads/writes: everything documented in the CSV reference above, across one full run.
