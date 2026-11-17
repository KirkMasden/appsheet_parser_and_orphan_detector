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

2a. **Labels the suite cannot resolve.** The same live-state problem reaches *names*, not just visibility. A column's or action's `display_name` is frequently a formula rather than a literal string — in Kankaku, all 87 columns carrying an override use a formula, 63 of them branching on the app's language setting — so the parse holds the label faithfully and still cannot say what text a user will see. Two different columns can carry byte-identical display-name formulas and be indistinguishable by label. View display names are worse: they are absent from the export entirely (see STATUS.md), so a view's internal name may or may not be what appears on screen, and nothing in the export says which views were renamed. **Never assert to a user that a named element exists or is unique.** Say "look for a line labelled X" rather than "the X line," and where the parse cannot establish what the label will be, say so — the definite article silently asserts something the data does not support, and the user cannot detect the error.

3. **Conditions no static analysis can settle.** `count(Archive[Word])>0`, `INDEX(Cram[Enum],1)="On"`, `[SomeFlag]=TRUE` — these depend on live data, not the app definition. No amount of parsing resolves them. The honest report is that an edge's liveness is conditional and unresolved. Note that this reaches labels as well as conditions: a `display_name` may itself be a formula over live state, so what a component is *called* on screen can be as unresolvable statically as whether it is *visible* — see item 2a above.

The practical consequence, and the direction of the error: **the suite can under-report orphans.** A view shown as reachable may not be. This runs opposite to the false positives fixed in August 2026, which over-reported. Both errors exist; they are different failures and are recorded separately in STATUS.md.

When answering a reachability question, say which of these applies rather than presenting a clean answer. "Reachable via X" without qualification is frequently wrong.

**A CSV identity is not an in-app location.** Limitation 3 above has a resolution path the suite cannot execute: the user opens the running app, performs the action, and reports what happened. Directing that test is a different task from locating a component, and the parse does not currently support it. An instruction of the form "the action X on table Y" identifies a row in `appsheet_actions.csv`; it does not tell anyone which screen to open or where on that screen to tap. Resolving an action to a tappable location requires composing several things the suite holds separately — the action's attach-to column, the views that render that column, and a navigation path to one of those views — and no module does this today. Until it does, say plainly that the parse does not record where a component appears on screen, and ask the user what they observe rather than assuming they can find it.

## What the scripts need to run

The scripts are written in Python 3 and need one third-party library, `beautifulsoup4`. Nothing else is required.

Check for both before running anything, and install whatever is missing — asking the user's permission first if you do not already have it. The published setup instructions tell users that their agent will do this, so they are not expecting to have prepared anything in advance.

If the user has already created a virtual environment (README.md describes one, for running the scripts by hand from a terminal), use it rather than installing alongside it.

Before parsing, run `python -m sheet_derivation.snapshot <folder>` on the user's input folder. It reports which of the expected input files are present and which are missing, and warns if two files look like the same capture. When the export and a capture are both there, it also runs the pairing check described below. It changes nothing, and tells the user what is missing or mismatched before a parse fails on it.

**The pairing check.** An export from one app can end up beside a capture of an unrelated workbook, and the file names will not show it; on 2026-09-25 exactly that nearly happened. Both the input-folder check and `python -m sheet_derivation.run` therefore compare the worksheet names the export gives for its Google Sheets tables ("Worksheet Name/Qualifier") with the capture's sheet names, before anything else runs. If all are present, they say so in one line. If some are missing, they warn, name them, and continue. If none are present, both stop with exit status 3 and write nothing. The input-folder check also compares the view names in `views1.txt` and `views2.txt`, and the names of the user-created actions in `actions.txt`, with the export's; it warns when some are unmatched and stops when fewer than one in five match. `run.py` does not make that comparison, since the sheet side reads none of those files. The check cannot tell two versions of the same app apart, because their workbooks share sheet names and their pasted lists share view and action names, so a pass does not prove the pair is right; it only rules out an unrelated app or workbook.

`--allow-mismatch` turns that stop into a warning. **Do not add it on your own initiative.** When the check stops, tell the user which export and which capture are in the folder and what the check found, and ask whether they belong together. Add `--allow-mismatch` only if the user confirms they do, for example because the workbook's sheets were renamed after the export was made. Never add it just to get a run to complete: a mismatched pair produces reports that look valid, and neither you nor the user can tell from the output that they are wrong.

`bot_actions.txt` is optional and written by hand: one action name per line, listing the actions the user's bots call. The suite has no other way to know an action is called by a bot, so without this file those actions are reported as orphan candidates. If the user's app uses bots and the file is absent, say so rather than treating the orphan list as complete.

## The workspace layout

Each set of files to be parsed goes in its own folder under apps/, with all the prepared files sitting directly in it and no subfolders. What the scripts produce is sorted into subfolders: output/<name>/ takes the same name as the input folder and separates the results into app/, sheet/, gates/ and investigations/. A parse first deletes from its output folder the files it is about to write (the list is MODE_OUTPUT_FILES in `master_parser_and_orphan_detector.py`; a single-parser or orphan-only mode deletes only its own files) and prints a line for each, so a file that is missing after a run means that run found nothing, not that a file from an earlier run was left behind. Nothing else in the folder is touched, `investigations/` and `gates/` included.

The difference is deliberate: keep it simple where a human assembles, sorted where a human or an agent reads. Assembling the input folder is the step a user can get wrong, and a handful of files with fixed names in one folder is the easiest shape to get right by hand. Reading the output is a different job, done by a human or an agent who benefits from the sorting instead. Do not "fix" this into one shape or the other; the difference is the point, not an inconsistency.

## How to use this suite well

These rules are not stylistic. Each was learned by getting a wrong answer without it.

**Execute the modules; do not reason from their output alone.** Import the analyzer class and call its methods directly — `ViewOrphanDetector.load_views()`, then `find_all_reachable_views()` and `print_reach_path()`. Do not drive the interactive menus. Questions that CSV inspection failed to answer have been settled in one step by running the module that produces the CSV.

**Count CSV rows with a real CSV parser.** Never `wc -l`, never line-splitting. Several fields in these outputs contain embedded newlines, and naive counting has produced a wrong answer in this project.

**Read the right field for grouped actions.** On `navigation_edges.csv` rows where `action_availability_type` is `via_group`, the button the user actually sees is the parent: read `parent_action` and `parent_prominence`, never `source_action` or `child_prominence`. A group's children are never independently visibility-checked.

**Re-parse before trusting a predicted diff.** Parse output directories are timestamped at parse start, not at code state. Check a parse directory's file mtimes against the code's own history before adopting it as a reference for a given commit. Predictions made against a stale parse have been wrong by nearly two orders of magnitude.

**A prominence value is not a rendering guarantee.** `Display_Prominently`, `Display_Overlay` (the editor's "Primary") and `Display_Inline` each interact with view type, with manual action lists, and — for inline actions — with the attach-to column's own visibility. See APPSHEET_BEHAVIOR.md, which records each platform rule with its source and the strength of that source.

**Check attributions before asserting them.** Three attributions were asserted without checking in one session of this project; two were wrong. Each check would have cost seconds.

**Say when the data does not answer the question.** These CSVs are incomplete in known ways, recorded in STATUS.md. An explicit "the parse does not record this" is more useful than an inference presented as a finding.

**When a spreadsheet formula behind an app column changes, remind the user to regenerate the table.** AppSheet keeps its own copy of the formula of each column filled by a spreadsheet formula (the export's `spreadsheet_formula` field; the editor shows it with the note "Generated from your spreadsheet. Gets applied during sync.") and writes that stored copy into every new row the app adds. The copy is refreshed from the sheet only when the table's structure is regenerated in the AppSheet editor. It can also be edited by hand in the editor without causing the editing interface to issue an error, so it may differ from the sheet for that reason too. So whenever you propose or make a change to a formula in a column that belongs to an app table, tell the user to regenerate that table afterwards. Otherwise new rows keep receiving the old formula, and nothing in the app shows it. Formulas on sheets that no app table reads need no regeneration. See APPSHEET_BEHAVIOR.md for the source of this rule.

The code uses the word "snapshot" — the module `sheet_derivation.snapshot`, the `<snapshot>` path token — but Kirk does not want it in anything he or his users read. Use plain descriptions instead: "the folder of files to be parsed", "the captured data", "the app's files". Use the word only when naming the module or command itself.

## The sketch after a parse

After you parse a new set of the app's files, give the user a brief sketch of what the run found. In a later session that works on an existing parse, give the sketch only when asked.

Judge what matters most and lead with it. As a rough guide, not a fixed order:

1. Problems with the run itself, in one line and only when there are any. Examples are columns skipped because their settings could not be read, an export and a capture that do not belong to the same app, and navigation targets the parser could not resolve. These tell the user how far to trust the rest.
2. Findings that affect what the app does for its users, such as an action that navigates to a view that does not exist, or an action whose conditions mean it can never display.
3. Everything else, largest group first, such as orphan views, actions, and columns.

The formula checkup. When the run includes the sheet side, read stage6_formula_checkup_summary.json in the run's sheet folder rather than the full output. Raise each item in "raised" as a heads-up, saying in plain words how sure it is ("likely" or "possible"). Where a group in "raisedGroups" has more than three columns, describe the pattern (for example, that seven columns in Settings hold sheet formulas the app does not store) rather than naming each column. For each group in "minor", give one line beginning "I noticed that...", and suggest that the user confirm it is intended. Mention "runProblems", and any columns listed in "notExamined", in the line about problems with the run. Do not mention findings the summary leaves out.

Intended items. If "intended" is not empty, say in one line how many findings were declared intended earlier and are not listed, and list them when the user asks. If "lapsed" is not empty, say that those findings were declared intended before but have changed since. Before reporting orphan findings, check them against "orphanEntries", and treat an orphan whose kind and name match an entry as intended in the same way.

Recording a declaration. When the user says a finding is intended, record it with python -m sheet_derivation.intended (add for a formula checkup finding, add-orphan for an orphan, giving the orphan's kind exactly as the detector's output names it), using the user's reason as the note if they gave one. Do this only when the user says so, never on your own judgment, and never edit the record file by hand. To withdraw a declaration, use remove.

Give exact counts. Name the items when there are only a few, and describe the pattern when there are many. When more than three categories have findings, give each no more than a sentence or two. Present findings as mild heads-ups, not as errors, since many will turn out to be intended. Where STATUS.md records a known false positive that bears on a count, say so in a short clause.

End with this question: "Would you like to look at any of them in more detail, or go on to some other matter?"

## Where to look

- `STATUS.md` — known defects, recently-fixed entries with commit hashes, and remaining work. Read this before trusting any output.
- `APPSHEET_BEHAVIOR.md` — a specification of AppSheet's own client behavior, with sources and an Unknowns section. Platform rules live here, not in STATUS.md.
- `maintainer/CONSOLIDATION_PLAN.md` — the design for unifying the visibility logic, which is currently implemented in more than one place.
- `AGENT_REPORT_FORMAT.md` — agent-facing, not human-facing: what to verify before reporting a finding back to the maintainer, and the shape that report should take. Read it before writing one, not after.

## CSV output reference

Row counts below are from the three reference parses used to generate this section (re-cut 2026-09-07, current HEAD — the previous 2026-09-02 pair went stale after five same-day code commits moved edge counts substantially in every app; verified rather than assumed, per `STATUS.md`'s matching correction). Most rows below still report Kankaku/Farmy only, matching this section's original scope; the third app is named where a row now covers it (`potential_unsatisfiable_conditions.csv`):

- **Kankaku** = `20260907_111603_260831_1809_Kankaku_V18_baseline_parse`
- **Farmy** = `20260907_103008_AppsheetFarmyApp_for_Kirk_parse`
- **Third app** = `20260907_103502_251130_1947_Test_parse`

counted with Python's `csv` module (never `wc -l`, since several fields — `view_configuration`, `settings`, `with_these_properties`, `type_qualifier`, `expression`, and others — hold embedded newlines that a line-count would mis-split).

**Conventions used throughout, so they aren't repeated per field:** a field holding more than one value joins them with `|||` (triple pipe) — this shows up on `referenced_*`, `available_*`, `hidden_columns`, `view_columns`, `slice_columns`, `slice_actions`, `formatted_*`, `must_be_*`/`must_not_be_*`, `event_actions`, `onclick_actions`, `dashboard_view_entries`, `missing_view_names`, and `raw_references` on every file that has them. Boolean-shaped fields (`is_virtual`, `hidden`, `key`, `label`, `read-only`, `searchable`, `is_system_view`, `is_disabled`, `is_orphan`, `is_unused`, `modifies_data`, `needs_confirmation`, `bulk_applicable`, `is_system_generated`, `is_self_loop`) are the text strings `Yes`/`No`, not booleans. Every writer's declared or derived field list was checked against the actual header of both reference parses; **no disagreement was found anywhere** — every file below that existed when the check was made lists one field set because code and output agree; `appsheet_tables.csv`, added since, was checked only against the V18 baseline and the V19 export of 2026-09-26 (see its entry).

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

### `appsheet_tables.csv`

One row per table in the export, in export order, **including the native-source tables** (for Kankaku, the six bot process/output tables) that `appsheet_columns.csv` leaves out. Written by `column_parser.py` (`ColumnParser.save_tables_to_csv`), beside the other app-side CSVs.

Rows: Kankaku 16 (checked on the V18 baseline and the V19 export of 2026-09-26; not yet run on Farmy).

Fields: `table_name`, `update_mode`.

- `update_mode`: the table's "Are updates allowed?" setting (HTML `for="UpdateMode"`), recorded **exactly as exported**, never translated or interpreted. The field takes one of the eight values AppSheet documents (help page "Control add, update, and delete operations"): `ALL_CHANGES`, `ADDS_ONLY`, `ADDS_AND_UPDATES`, `ADDS_AND_DELETES`, `UPDATES_ONLY`, `UPDATES_AND_DELETES`, `DELETES_ONLY`, `READ_ONLY`. Four have been observed in Kankaku's exports: `ALL_CHANGES`, `UPDATES_ONLY`, `ADDS_ONLY`, `READ_ONLY`. The other four (`ADDS_AND_UPDATES`, `ADDS_AND_DELETES`, `UPDATES_AND_DELETES`, `DELETES_ONLY`) are taken from the help page and have not been seen in an export. These are AppSheet's own pre-collapsed values, the same kind `appsheet_slices.csv` carries for slices. Kankaku V19: `ALL_CHANGES` Kankaku, Archive; `UPDATES_ONLY` Seminar, Settings, Options, Stats, `_Per User Settings`; `ADDS_ONLY` Progress; `READ_ONLY` Overall, Welcome and the six bot tables.
- Empty when the table's block has no such row; the parse then prints a warning naming the table. A value outside the eight known ones is still written as exported, with a warning — the export could in principle show an expression here, and none of the apps seen so far does. Treat an empty or unrecognized value as "not known", never as read-only.
- Misuse trap: the setting says what the table allows in general; whether the app actually adds or edits rows still depends on its views and actions (and `appsheet_actions.csv` labels every add-row action `set_columns`; see `STATUS.md`).

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

Rows: Kankaku 407, Farmy 902 (2026-09-02: 585 / 1971 — stale; several fixes since, from the table-less action-to-target join through the section B `CONTEXT()` work to the form/map fall-through fix, each removed or added edges in at least one app).

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

Rows: Kankaku 2, Farmy 88 (was 87 as of 2026-09-02 — `a7c283a`'s form/map fix added `Go to Take LOCATION Image Form`, table `Location`, an untraced ripple from `Location_Detail`'s second-order reachability loss; `STATUS.md` has the trace).

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

### `potential_unsatisfiable_conditions.csv`

Answers a different question from every other file above: not "is this reachable," but **"can this pair ever display, regardless of reachability."** A column's `Show_If` and the condition of a `Display_Inline` action attached to that column, tested for a literal contradiction over the same variable — same variable, opposite senses, e.g. `X="On"` on one side and `X<>"On"` on the other. When found, the action can never be visible no matter what the navigation graph says about the view it sits on: it fails before reachability is even relevant. Written by `unsatisfiable_condition_detector.py`. Only if non-empty — absent on a zero result, same convention as every sibling orphan detector (confirmed by reading all five: `view_orphan_detector.py`, `slice_orphan_detector.py`, `format_rule_orphan_detector.py`, `actions_orphan_detector.py`, `column_orphan_detector.py` all guard with `if candidates:` before ever opening their output file — none of them, `format_rule_orphan_detector.py` included, writes a header-only file on zero).

Rows: Kankaku 2, Farmy absent (zero), third app absent (zero).

Fields: `action_name`, `source_table`, `column_name`, `table_name`, `show_if`, `only_if_condition`, `contradicting_variable`, `contradiction_detail`.

- Deliberately narrow, per `maintainer/RELEASE_CHECKLIST.md` section B's own ambiguity assessment: fires ONLY on a literal contradiction (same variable, opposite `=`/`<>` sense, or an `ISBLANK`/`ISNOTBLANK` family opposite-sense pair). Arithmetic, `COUNT`/`SUM`/`SELECT`/lookup functions, and any pair whose shared variable sits inside an `OR` on either side are left silently uncaught — this is a mechanical check for construction-level impossibility, not general `Show_If` evaluation, which stays an accepted limitation (`STATUS.md`).
- **This is not a reachability finding and does not interact with any other file here.** A row in this file says the pair can never display even if every navigation/prominence/view-type gate passes; a view or action named in it can still be absent from `potential_view_orphans.csv`/`potential_action_orphans.csv`, and vice versa. The two questions are independent.
- Candidacy requires the action's `attach_to_column` to name a REAL column on its own table — the 23 Farmy `Display_Inline` actions that attach to a column that does not exist (`STATUS.md`) are silently excluded, not a false negative of this detector.
- The module's own docstring records three spec decisions a future reader should check before extending this: whether `ISBLANK`/`ISNOTBLANK`/`NOT(ISBLANK(...))` count as one family (yes), whether `[_THISROW].[X]` and bare `[X]` are the same variable (yes, normalized), and that `AND(...)` is decomposed into its conjuncts while `OR(...)` never is.
- Out of scope by design, not a gap: action-versus-action complementary conditions (two sibling actions on the same column whose own conditions are opposite each other) are a real pattern this file will never catch, since it only ever compares a column's `Show_If` against one attached action's own condition.

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
- **This file simply does not exist when the count is zero** (Kankaku, here) — not a header-only file. Diffing parse directories by file presence alone will misread "cleared to zero" as "never ran" (`STATUS.md`, "`view_orphan_detector.py` also writes no `potential_view_orphans.csv` on a zero result" — the same pattern holds for `potential_format_rule_orphans.csv` above and, per that entry, likely all five orphan detectors). Since a parse first deletes the files it is about to write, a missing file after a run means that run found nothing.

### `potential_virtual_column_orphans.csv`

Virtual (computed) columns the suite found no reference to from any other column, view, action, format rule, or slice — with a per-category reference count. Written by `column_orphan_detector.py`.

Rows: Kankaku 2, Farmy 27.

Fields: the 39 `appsheet_columns.csv` fields plus `total_references`, `columns_refs`, `views_refs`, `actions_refs`, `format_rules_refs`, `slices_refs`.

- Inherits `appsheet_columns.csv`'s `show_if`/`required_if`/`editable_if`/`valid_if`/`reset_if` always-empty defect (same root cause, described above) — also empty here in every row.
- Also empty in every row here: `description`, `initial_value`, `nfc_scannable`, `ref_table`, `spreadsheet_formula`, `suggested_values` — plausibly legitimate for virtual columns specifically (a computed column has no `initial_value`, no physical-sheet `ref_table`/`spreadsheet_formula`/`nfc_scannable` binding), not independently confirmed as intentional in code.
- `*_refs` fields are counts, not `|||`-joined lists, despite the plural-sounding name.

### `unused_system_views.csv`

System-generated views (the `Detail`/`Form`/etc. AppSheet auto-creates per table) not reachable by the same BFS as `potential_view_orphans.csv`. Written by `view_orphan_detector.py`.

Rows: Kankaku 64, Farmy 101 (was 99 as of 2026-09-02 — `a7c283a`'s form/map fix newly flagged `ActivityGermination_Form` and `Location_Detail`; `STATUS.md` has the full trace, including why `Location_Detail` is a second-order loss).

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
- Reads: the HTML export, `appsheet_slices.csv`. Writes: `appsheet_columns.csv` and `appsheet_tables.csv` (one row per table, every table in the export; `save_tables_to_csv(output_path='appsheet_tables.csv')`, filled by `extract_table_update_settings()` during `parse()`).
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
- Hard constraint, load-bearing for the whole suite's orphan counts: its group-child edge loop deliberately performs **no** visibility check (`action_visibility.py`'s module docstring) — that's what lets group-membership invocation routes produce edges at all. Do not "fix" this without reading `maintainer/CONSOLIDATION_PLAN.md` sections 1 and 6 first.

### Analyzers

Interactive, `input()`-driven browsers for a human exploring dependencies — not, in the main, meant to be scripted. `dependency_analyzer_hub.py` is the menu that routes to the other three; none of the three write any CSV.

#### `view_dependency_analyzer.py` — `ViewDependencyAnalyzer`

Answers: *"How do users reach this specific view, and where can they go from it?"* — for a human, interactively, by default.

- Primary interface is `run(return_to_hub=False)`, an interactive search-and-browse loop — **not** intended for direct scripted use.
- **Exception, worth calling directly, but only with the full sequence:** `ViewDependencyAnalyzer(base_path).load_views_data()`, then `load_unused_system_views()`, then `build_navigation_graph()`, then `find_paths_to_view(target_view_name, max_paths=5)` returns up to `max_paths` concrete paths (as lists of formatted step strings) from every primary/menu root to the named view — no `input()` involved. **`build_navigation_graph()` is not optional**: `load_views_data()` alone never populates the navigation graph, so calling `find_paths_to_view()` right after it returns zero paths for every target, silently, indistinguishable from a genuine orphan — confirmed by running exactly that two-call sequence against both reference apps. Skipping `load_unused_system_views()` doesn't zero the result the same way, but it does change it: with that file unread, `build_navigation_graph()` includes edges sourced from views the file would otherwise have excluded (64 such views in Kankaku), so a call missing that step can find different paths — or find paths a full-sequence call wouldn't — than the correct sequence would. Complementary to `view_orphan_detector.py`'s `find_all_reachable_views()`/`print_reach_path()`: that one gives yes/no reachability plus one path per view (first-found by an uncapped BFS); this one is built to enumerate several paths to one specific, already-known view, from multiple roots, under a depth limit (below).
- **Case-sensitive matching, no error on mismatch:** both `find_paths_to_view()` and `find_destinations_from_view()` compare the name argument against canonical view names with exact string equality — graph nodes are case-normalized when the graph is built, but the caller's argument is not. A one-letter case difference from the canonical spelling in `appsheet_views.csv` returns zero paths / zero destinations, with no error and no indication the name was almost right — demonstrated directly against both reference apps: swapping the case of one letter in an otherwise-valid, currently-reachable view name dropped both methods to zero, in both apps.
- **`find_paths_to_view()` returns at most one path per root, and applies a 6-edge depth limit to each root's own search.** "Up to `max_paths` paths" means up to `max_paths` different *roots*, one path each — never several distinct routes from the same root, even when several exist. Each root's own search gives up if the target isn't found within 6 edges of that root; `find_paths_to_view()` then simply tries the next root. Measured across three apps (2026-09 audits): this limit currently hides no view in any of them, but Farmy runs at exactly the 6-edge ceiling for several targets, with no headroom left — an empty result from this method does not distinguish "genuinely unreachable" from "reachable, but beyond what any tried root's capped search could find," and the two cases print identically. **This figure is dated 2026-09-04 and is STALE as of 2026-09-07** — it predates the table-less-join, `IN()`, `LEFT()`, and form/map fall-through fixes, all of which changed edge counts substantially in at least one app; see `STATUS.md`'s matching entry for an approximate 2026-09-07 re-check (not a byte-exact replacement figure).
- Requires: a directory containing `appsheet_views.csv`, `navigation_edges.csv`, `unused_system_views.csv` (`load_views_data`, `load_unused_system_views`).
- Reads: `appsheet_views.csv`, `navigation_edges.csv`, `unused_system_views.csv`. Writes: nothing.

#### `column_dependency_analyzer.py` — `ColumnDependencyAnalyzer`

Answers: *"What does this column reference, and what references it — across views, slices, format rules, and actions?"* — for a human, interactively.

- Primary interface is `run(return_to_hub=False)`; almost every other public method (`show_*_menu`, `display_*`, `get_user_selection`) is a piece of that same interactive loop. Not intended for direct scripted use — unlike `view_dependency_analyzer.py`, there's no documented non-interactive entry point here. **`analyze_column_dependencies(selected_column)` exists but does not return data** — it has zero `return` statements, returns `None`, and blocks on `input()` via `show_main_analysis_menu()` before it can return anything at all. Results are reachable only as the side effect `self.current_analysis`. It also expects a row dict already selected by the interactive search, not a bare name (code audit, 2026-09-04).
- Requires: a directory containing `appsheet_columns.csv` — the only file actually required; `load_columns_data()` returns `False` on its absence and `run()` aborts. `appsheet_slices.csv`, `appsheet_actions.csv`, `appsheet_views.csv`, `appsheet_format_rules.csv` are optional: each goes through `_load_data`, which prints a note and continues if the file is missing. A sixth file, `unused_system_views.csv`, is also read (outside any `load_*_data` method) and materially changes results by excluding any view it lists from `analyze_view_dependencies` — its absence produces no note at all, unlike the four optional CSVs above (code audit, 2026-09-04; see `STATUS.md`).
- Reads: `appsheet_columns.csv`, `appsheet_slices.csv`, `appsheet_actions.csv`, `appsheet_views.csv`, `appsheet_format_rules.csv`, `unused_system_views.csv`. Writes: nothing.
- **Performs no `CONTEXT()` evaluation of any kind** (confirmed by grep, zero hits) — the third audited module with this gap, alongside `view_orphan_detector.py` and `view_dependency_analyzer.py` (see the CSV reference notes above). This is now a suite property, not a per-module footnote.

#### `action_dependency_analyzer.py` — `ActionDependencyAnalyzer`

Answers: *"What does this action call, what calls it, and what's the full chain of grouped actions around it?"* — for a human, interactively.

- Primary interface is `run(return_to_hub=False)`. Every other public method is part of that interactive surface (`search_by_name`, `browse_by_table`, `browse_by_type`, `show_*_menu`, `build_action_hierarchy`, …).
- **Feeds nothing programmatic** — confirmed in `STATUS.md`: "nothing programmatic consumes this function's answer — it feeds only the interactive dependency browser." This is the module `STATUS.md` names as the example of "exists only to serve an interactive browser and feeds nothing programmatic." Its own visibility check (`is_action_visible_in_view`) once had no `Display_Overlay` case for table views and fell through to `False` — **fixed in `bbe981b`**, not in this method itself but in the shared `action_visibility.py`'s `is_visible_in_view_ada`, which this method now delegates to (consolidation step 1 moved the body there). Verified pair-by-pair rather than by CSV diff, since this module writes no CSV: 7,440 pairs flipped False→True in Farmy and 120 in Kankaku, none the other way.
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

#### `unsatisfiable_condition_detector.py` — `UnsatisfiableConditionDetector`

Answers: *"Does a `Display_Inline` action's own condition contradict the `Show_If` of the column it attaches to, so the action can never display regardless of live data — a different, independent question from reachability?"*

- Constructor: `UnsatisfiableConditionDetector(parse_directory)`.
- Worth calling directly: `run_analysis()` (prints progress, writes the file only if non-empty, returns the row list); or `validate_files()` → `load_columns()` → `load_actions()` → `find_unsatisfiable_pairs()` (which itself calls `find_candidates()`, then `extract_terms()`/`find_contradiction()` per candidate) for the list without the printing/writing.
- Requires: `appsheet_columns.csv`, `appsheet_actions.csv`.
- Reads: `appsheet_columns.csv`, `appsheet_actions.csv`. Writes: `potential_unsatisfiable_conditions.csv` (only if non-empty, same "write nothing on zero" convention as its siblings above).
- Narrow by design, per its own module docstring: fires only on a LITERAL contradiction over one shared variable (`=`/`<>`, or the ISBLANK/ISNOTBLANK family) after recursively decomposing top-level `AND(...)`; `OR(...)` and anything else it does not explicitly recognize (arithmetic, lookups, a bare truthy column) is left opaque and can never fire. Action-versus-action complementary conditions — two sibling actions whose own conditions oppose each other — are out of scope by the same column-versus-action-only design, not an oversight.

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

## Reading the sheet-derivation artifacts

This repository holds two tools. The first, documented above, parses an AppSheet application exported as HTML. The second reads a captured Google Sheets workbook and derives artifacts describing it. They meet in one place: a join between the app's columns and the sheet's headers. Everything else about them is separate, and either can be used without the other.

The artifacts are an index, not an analysis. They tell you what is in the workbook and — equally important — what the tool could not interpret.

### The reading rule

Every artifact carries a residue. Read it before you trust the artifact.

The residue is the list of things the tool could not resolve: an argument it could not follow, a reference it could not classify, a column whose values have no governing formula. An artifact without its residue looks complete when it is not.

This matters most when the answer is an absence. If a dependency graph shows no edge from a cell, that may mean the cell has no dependency, or it may mean the tool could not follow one. The graph alone cannot tell you which. The residue can.

A residue entry names what was not resolved, names the input a reader would have to evaluate, and gives that input's value at the time of capture. It routes you to the raw capture; it does not tell you to stop.

### One instance is not the pattern

The formula inventory deduplicates formulas into patterns and carries exactly one raw instance per pattern, kept to show the pattern's shape. Two formulas belong to the same pattern whenever the normalization collapses their difference away — and whatever varies between them beyond that (a value, a constant, a specific reference) can differ from the one instance the artifact shows you. Reading that instance tells you the shape every member of the pattern shares. It does not tell you what any particular member says.

This has already produced a wrong answer once. A twelve-row duration table on one sheet had all twelve rows sharing a single pattern, so the inventory carried one of them — and the row it carried was not the row that mattered. One reading of the artifact stopped at that one instance and generalized from it. A second fetched all twelve instances individually and found what the first had missed. The difference between those two runs was the difference between a wrong answer and a right one.

State this as a practice, not a caution: before generalizing from a pattern, fetch its individual instances. The inventory tells you what shape the formulas have, not what numbers are in them.

A related defect existed and is fixed: row digits inside a `$`-anchored absolute reference used to be rewritten the same as a relative row's, so two formulas anchored to genuinely different fixed rows collapsed into one pattern, and one of the two constants was silently absent from the artifact with nothing indicating anything was missing (fixed as of commit `3ece526`). That fix removes one cause of instances diverging within a pattern. It does not remove the others, and this rule stays necessary regardless of it.

### A search that finds nothing has not established that nothing is there

When looking for where a rule or threshold is applied in a workbook, a literal-text search over the formula inventory is not sufficient. A threshold can be computed in a cell whose own text contains no literal form of the number at all — built by arithmetic over other columns, sitting in a small lookup table, and reaching the formulas that depend on it only through a lookup, never through a literal appearing anywhere near them.

This has already produced a wrong answer once. A cell computed a threshold of 300 seconds by summing separate seconds, minutes, hours and days columns, with a 5 sitting in the minutes column; its own text contained neither "300" nor "5 minutes". Its row carried a label, and on the order of twenty thousand formulas on another sheet looked values up against the small table that row belonged to, never referencing the number directly. A literal search for the number found nothing, and an investigation that relied on that search wrongly concluded no second threshold existed.

State the practical consequence: when asking where a rule is applied, enumerate the routes by which a constant can reach a formula, and include lookup tables consumed by reference among them, not as a special case to remember separately. A search that finds nothing has narrowed the question. It has not answered it.

### Answering "where is this used?"

When asked where a column, action, view or slice is used, search in this order and report what each step covered.

1. Search the raw export for the bracketed name, for example [Min]. Every use inside an expression is written this way, so this search catches all expression-based uses.
2. Search the raw export for the bare name too, and account for every occurrence. Some settings name a column without brackets. Use a case-sensitive, whole-word search, so that a search for Min does not count the MIN() function or longer names that contain "Min".
3. On the sheet side, trace dependents at cell level. Find the cells that read the column, then the cells that read those, and continue until no further formula reads the chain.
4. Say what lies outside the export and the capture: other workbooks that read this one, bots, and bound scripts. Neither file can rule these out.

End with a coverage statement: each search you ran, what it rules out, and every occurrence accounted for, with the arithmetic shown. For example: "14 bare-name occurrences: 9 inside bracketed uses already counted, 3 in column lists, 2 in display names; 9 + 3 + 2 = 14." A list of uses without this statement cannot be told apart from an incomplete search.

This method answered the question of what the Min column on Kankaku's Main data is for (2026-09-27).

### The tool does not evaluate

It indexes. It reads formula text and captured values and reports what it finds. It does not compute, follow chains, or decide what a formula means.

So when a residue entry says something was not resolved, that is a statement about the tool, not about the data. The capture is closed under evaluation for anything whose inputs are inside it: formula text plus the captured values of every referenced cell is usually enough to determine what happened. Deducing that is the reader's work, and it is legitimate work. What is not legitimate is asserting a conclusion the capture does not support.

Four things genuinely cannot be answered from a capture: content in another workbook reached by an import; a value produced by a volatile function, whose recalculation moment is not recorded; a column holding values and no formula anywhere; and anything written by a bound script, whose source is not captured.

### Every artifact describes a moment

Each artifact carries a capture date and the tool's own commit hash. It describes the workbook as it stood at that moment, not as it stands now. The live workbook may have changed — a sheet, a formula, or the very reference an artifact reports on may no longer exist.

A later capture producing different findings is not evidence that the tool has broken. Read the capture date before treating any finding, or its absence, as current.

### Declared is not measured

Some fields the tool measures. Some a maintainer declares, through the declarations file, where they know something the capture cannot show. Every such field is marked declared rather than measured.

The tool never verifies a declaration against the capture. A declared value is an assertion by a person; treat it as such.

### Read the reliability condition

Every artifact states, once for the whole file, what its findings rest on and what would defeat them. These are not boilerplate. They name the specific construct that would produce a confident wrong answer.

Do not summarize an artifact's findings without reading its condition first.

### Running the tool

A user's only manual step is the capture. They paste the Apps Script into their workbook, authorize it, and run it; the dump it writes is their data and stays outside this repository. Everything after that is yours to run.

Run the app side first. With the documented layout, `python -m sheet_derivation.run <input folder> output/<name>/sheet` then finds the app-side results in `output/<name>/app` and the export in the input folder by itself, and prints a line for each. If it finds no app-side results, it warns that the join will be ABSENT; do not pass that over, because an ABSENT join writes CSVs holding headers only. Either parse the app first or pass `--appside-parse-dir`.

The stages run in order and each reads what the one before it produced. Never recompute something an earlier stage already states — stage 4 reads stage 3's column profiles rather than measuring them again, and a stage that recomputes an upstream fact can disagree with it, which is the failure the ordering exists to prevent.

Each stage has a gate: a set of measured numbers it must reproduce. A gate that fails is a finding to report, not a number to adjust. If you find yourself changing an expected value so a gate will pass, stop and report instead.

The gate-check scripts under sheet_derivation/gates/ only write reports. A failing comparison does not stop anything and nothing downstream reads their exit codes; the report is for you to read and investigate. This is separate from the three refusal gates in loader.py, which do halt a run by raising CaptureIntegrityError when the two capture files disagree, and from the pairing check above, which halts a run when the export and the capture share no worksheet name.

Their --output-dir default is <workspace>/output/gates — not any input folder's own output/<name>/gates/. It exists so an ad hoc gate-check run has somewhere sensible to land without an argument, but it is one shared location: a later run there overwrites an earlier one's reports. For a run whose reports are meant to be kept as part of a specific folder's record, pass --output-dir explicitly, pointed at that folder's own output/<name>/gates/.

Artifacts are JSON Lines, one self-contained item per line, with flat CSV projections beside them only where the data is genuinely flat; the projections are marked derived and regenerable, and the JSONL is authoritative. Gate and verification reports are markdown and are written for people. Nothing this tool writes is ever truncated.

### Answering questions from the artifacts

An investigation is produced fresh each time and is not written back into any artifact. It can be wrong, and it is judged on its trace rather than on its answer: which cells were examined, which were enumerated and found irrelevant, and which parts of the conclusion rest on captured values rather than on formula text.

A conclusion reached by inference from a partial view is a failure even when it happens to be correct, and it is indistinguishable from a real success if only the conclusion is inspected. Show the trace.

An exhaustive check is only meaningful per question. "Find every problem" obliges you to invent the catalogue as you go, and a clean report is then indistinguishable from an incomplete search. A question that defines its own boundary does not have that problem.

### The value query

An address in, a value out, over the captured values file. It returns the cell's formula, its value at capture, whether it is a spill origin, and the spill extent where it is one.

It resolves addresses only. It does not evaluate formulas, follow chains, or interpret.

### The A1 to R1C1 converter

`sheet_derivation/r1c1.py` converts a sheet formula from A1 to R1C1 relative to the cell that holds it and compares the result with a stored formula (the `spreadsheet_formula` field of `appsheet_columns.csv`, which AppSheet writes in R1C1 without the leading "="). Pure functions, no file access, called by stage 6 (below): `convert_a1_to_r1c1(formula, row, col)` returns the text, or "could not compare" with a reason; `compare_formulas(sheet_formula, row, col, stored_formula)` returns "same", "differs", "could not compare" or "placeholder, not compared" (the stored text `"COMPUTED_VALUE"`, with its quotes), always with both raw texts. Function-name case and whitespace outside string literals are ignored; string literals, including INDIRECT names, are never altered. Anything it does not recognize (named ranges, array literals, unplaceable characters) is "could not compare", never guessed. Only some reference spellings occur in AppSheet's own stored text (`ATTESTED_FORMS` names the stored formula that attests each); the others follow the standard convention and are returned in `by_convention`, and a difference that involves one is marked as possibly one of spelling.

### The formula checkup (stage 6)

`sheet_derivation/stage6.py` (computation), `stage6_artifacts.py` (writer) and `serialize_stage6.py` (canonical form for the determinism tests) are the checkup's per-column comparison and judgment; `appside_formulas.py` reads each column's stored formula, key flag and virtual flag from `appsheet_columns.csv` and each table's update setting from `appsheet_tables.csv` (stage 5's own reader is unchanged). `run.py` now runs stage 6 after stage 5, so the default is stages 0 to 6, and writes `stage6_formula_checkup.jsonl` (authoritative) and `stage6_formula_checkup.csv` (derived, regenerable) beside the other sheet artifacts. For every app column that a spreadsheet formula fills, or whose sheet column holds formulas below the header row, it compares those formulas with the stored one (through `r1c1.py`), names the situation, and grades it by what the table's update setting allows. Which rows count is decided by the table's key where the key is a paired sheet column, and otherwise by any value or formula in the table's paired columns. A column with a stored formula that cannot be paired with a sheet column is listed as not examined, with the reason. It only reads. It needs the app-side results; when they are absent it writes a meta line saying so and no findings. Beside the full output it writes `stage6_formula_checkup_summary.json`, a short summary derived from the same run (counts, the raised findings in rank order and grouped, the minor ones grouped, run problems, columns not examined, intended, lapsed and not-applied entries, and the stored orphan entries, with no formula texts); it is what the sketch reads, so the sketch does not need the full JSONL.

### The intended-items record

When the checkup raises a finding and the user says it is intended, the AI records that, so that later sketches do not raise it again. The record is one readable JSON file per app, `<app name>.json`, in a folder named `intended` in the workspace (the repository's parent folder, beside `apps/` and `output/`), outside every timestamped folder. The app name is the name the export gives the app: the last part of its DefnFolderName with the final hyphen and digits dropped (`/appsheet/data/KankakuV19-230844` gives `KankakuV19`; stage 6 states it on its meta line as `appName`). If the name cannot be derived, no record is read or written, and the output says so. Renaming or copying an app therefore starts a new, empty record.

The file holds two kinds of entry. Formula-checkup entries (table and column, with a fingerprint of the finding) are applied by stage 6 in code. Orphan entries (orphan kind and name) are only stored and listed; the AI applies them when it gives the sketch (the instruction for that is still to come). Only the command `python -m sheet_derivation.intended` writes the file (`add`, `add-orphan`, `list`, `remove`; each takes `--intended-dir` to override the folder), and the AI runs it only when the user says something is intended or asks to withdraw a declaration. Never edit the file by hand.

Stage 6 reads the record (`run.py --intended-dir` overrides the folder) and never writes it. A column whose fingerprint still matches keeps its situation and tier and gains an `intended` field with the date declared and the note; the meta line's `raised`, `raisedLikely`, `raisedPossible` and `minor` counts leave it out and `intendedCount` counts it. A column whose fingerprint differs has a lapsed declaration: the finding counts as new, and the column line and the meta line (`intendedLapsed`) say a declaration existed. An entry for a column that is not examined is listed on the meta line as not applied (`intendedNotApplied`), with the reason. The fingerprint is the situation, the tier and grade, the stored formula, and the non-matching part of the sheet side (the groups of differing formulas with their rows and, for S2A and S2B, the rows without a formula), so adding rows that get the normal formula does not lapse an entry. The CSV projection has an `intended` column.

### What exists

Five artifacts are built: the formula inventory, the schema file, the column dependency graph, the dangling sheet-name list, and the AppSheet join. The graph and the dangling list come from a single resolution pass, because a dangling name is one species of unresolved reference and two code paths reaching that judgment separately can disagree.

The join pairs each table with the tab its export "Worksheet Name/Qualifier" names, not the tab that shares the table's name; a native AppSheet table with no worksheet has no tab. Without an export carrying that field, it falls back to pairing by table name and says so in the artifact (`tabPairing` on the meta line, `tabSource` on each table line). It then reports agreement between the app's column names and the sheet's header labels, in both directions, and resolves nothing. The join itself never writes back into the schema.

**Header rows: one exception to "nothing on the sheet side is derived from the app side".** Stage 4 decides whether a tab has a header row. Its own rule looks for a text header above non-text values, so it cannot see a header of text labels over text data, and on Kankaku it left most tabs undetermined although their row 1 plainly held every header. Since 2026-09-26, when the export is given (`run.py` finds it in the input folder), stage 4 first compares rows 1 to 10 of any tab the export names as a Google table's worksheet with that table's column names, leaving out virtual and system-defined columns. A row holding more than half of them is the header, recorded with source `app-column-names` and its match count. Every other tab, and any tab where no row reaches that share, is decided by the old rule, unchanged, and each tab's `appColumnNames` record says which decided and why. A declared header row wins over both. The cost is the one the original rule was written to avoid: on a tab whose header was chosen from the app's column names, the join's agreement is largely by construction. So when a finding rests on header labels, read the tab's header source first. On an `app-column-names` tab, a high match count says the export and the sheet agree, not that the header was independently found. The join's per-column results still show which names match and which do not.

Where a sheet's header row could still not be identified, the join reports a marked diagnostic showing how many app column names appear verbatim in the candidate row. It is a diagnostic and not a verdict. Treat an undetermined verdict as uncertainty in the heuristic, not as evidence that a sheet has no headers. Now that tabs the app reads are decided from the app's column names, it mostly remains on tabs no table reads, and on tabs whose body is too empty to give any signal.

### The fixture record

This tool has been run on one workbook: the one its author built. It has never been run on a workbook whose author it is not.

That matters more than ordinary test coverage. The tool is designed not to encode the shape of any single workbook, and that rule cannot be enforced by reading the code, because every violation of it looks like a reasonable default at the point where it is written. It can only be tested by running the tool over workbooks the author did not build. That has not been done.

Treat any behaviour that seems to assume formula density, a particular sheet layout, or a particular header convention as a candidate defect and report it.
