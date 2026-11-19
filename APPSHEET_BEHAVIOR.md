# AppSheet display behavior

This is a specification of AppSheet's own client behavior — facts about what AppSheet
does, not about what this suite's code does. It exists because those two things have
drifted apart: the suite's rules about when an action displays in a view were derived
from one app (Kirk's), and testing against a second app on 2026-08-30 exposed rules
that were never encoded because the first app never triggered them. Today those rules
exist only as three hand-written, mutually inconsistent copies inside
`navigation_edge_generator.py`, `actions_orphan_detector.py`, and
`action_dependency_analyzer.py` — see STATUS.md for that defect and what it costs.

These facts cannot be derived from the CSV exports; the exports carry the *inputs* to
each rule (an action's `action_prominence`, a view's `view_type`, and so on) but not
the rule itself, which is a fact about AppSheet's rendering client. Every rule below
therefore names its source inline, so a later reader can weigh it before depending on
it. Nothing here is a claim about this repository's code — see STATUS.md for that.

## Position (prominence) values

The editor's Position names and the export's `action_prominence` strings are
different vocabularies, and one pair is not guessable:

| Editor Position | Export `action_prominence` string | Count in this app |
|---|---|---|
| Primary | `Display_Overlay` | 93 |
| Prominent | `Display_Prominently` | 160 |
| Inline | `Display_Inline` | 303 |
| Hide | `Do_Not_Display` | 414 |

Source: editor Position names from Google's documentation; export strings verified
against `appsheet_actions.csv` (970 actions total, exactly these four values and no
others); the Primary/`Display_Overlay` pair confirmed from an app-editor screenshot,
2026-08-31. Corroborating evidence: of the 93 `Display_Overlay` actions, 48 are
system-generated, and the sample is dominated by AppSheet's own "Edit" (26) and "Add"
(22) buttons — the floating buttons that hover over a view, which is exactly what the
documentation below describes Primary as.

This matters because the documentation below states its rules in editor vocabulary
and the code reads export vocabulary; without this mapping a reader cannot connect a
documented rule to the code branch that implements it. The code itself should keep
using the export strings throughout — the editor names belong in documentation,
comments, and user-facing text, not as an internal translation layer that could drift
out of sync with this table.

Source for the four definitions below: Google's official page, "Actions: The
Essentials", <https://support.google.com/appsheet/answer/10107706>.

- **Primary** (export: `Display_Overlay`) — "Display independently of scrolling, such
  as floating buttons on mobile devices and at the top of a view on desktop browsers."
  No view type is named in the documentation; the placement is described as
  scroll-independent, not view-type-specific.
- **Prominent** (export: `Display_Prominently`) — "Display in detail views as a
  button at the top of the screen (most common)." Detail is the only view type the
  documentation names for this position.
- **Inline** (export: `Display_Inline`) — "Display alongside the associated column,"
  so it requires a view that renders columns. Documented caveat for table views
  specifically: "the action replaces the column content instead of displaying
  alongside it" — an inline action in a table does not appear beside its column, it
  takes the column's place.
- **Hide** (export: `Do_Not_Display`) — "Don't display in any view."

## Established behavior

Each entry names how it was established. Direct observation, documentation, reasoned
inference, and third-party report are not interchangeable, and an entry's strength is
the strength of its source. The fourth category was added 2026-09-05: a report by
someone outside this project — a community forum post, a relayed vendor answer — is
weaker than our own observation and stronger than our own guess, and several
independent ones agreeing is worth more than any one of them. Such reports are named
with their date and their author's standing where known, so a reader can weigh them
without re-finding them.

Source: observed in Leon's app, 2026-08-30, by Kirk.

- **Prominent (export: `Display_Prominently`) on a Deck view: DOES display, when the
  action is on the view's action bar.** Source: observed in Kankaku (260411 Kankaku
  V18), 2026-09-02, by Kirk, in the app editor's preview. The `W to D` deck
  (`show_action_bar` `True`, `action_display_mode` `Manual`) lists three
  `Display_Prominently` actions in its own `view_configuration`'s `ActionBarEntries` —
  `Displayed Got It (WD)` (thumbs-up icon), `Play (Main Data)` (play icon),
  `Display Answer (W to D)` (right-arrow icon). Kirk confirmed visually that the
  thumbs-up and right-arrow buttons render on the deck's rows. Method: the app
  editor's preview plus the export's own `ActionBarEntries` list — not inference from
  a button's shape alone, the way the earlier Overlay-on-Deck observation above had to
  rely on shape.

  This is consistent with, not contradicted by, the earlier withdrawn 2026-08-30 case
  it replaces: that case was one `Display_Prominently` action ABSENT from a Manual
  deck's action list, not displaying; this one is three `Display_Prominently` actions
  PRESENT on a Manual deck's action list, displaying. Together they point the same
  way — deck display turns on action-bar list membership, not on prominence.
  Prominent-on-Deck is not an exception the deck action bar makes for its own
  prominence value; it follows the same list-membership rule every other prominence
  on a deck follows.

  **Limit of this claim, stated explicitly:** this establishes that
  `Display_Prominently` is NOT excluded from deck views. It does NOT establish what
  happens to a `Display_Prominently` action that is absent from a Manual deck's
  action list (the manual-list rule below already accounts for that case,
  independent of prominence), nor anything about Automatic-mode decks — whether
  `referenced_actions` is itself complete there remains an open question
  (`maintainer/CONSOLIDATION_PLAN.md` section 5's "Deliberately deferred" note). Google's
  Position documentation, which names only Detail for Prominent, is now directly
  contradicted by observation for this one case; whether Prominent excludes itself
  under any other deck condition is untested.

  `maintainer/CONSOLIDATION_PLAN.md` section 5's step 5 applied the opposite rule — excluding
  `Display_Prominently` from deck views entirely, on the strength of the
  documentation-only reading this entry now supersedes — across all three visibility
  strategies. It has been disproved by the observation above and reverted, 2026-09-02,
  without ever being committed; see `STATUS.md` and `maintainer/CONSOLIDATION_PLAN.md` for the
  code-level record.
- **Primary (export: `Display_Overlay`) DOES display on table views.** Source:
  observed in Leon's app, in Kirk's frozen copy, 2026-08-31, using a purpose-made
  External action set to Primary — "Go to web" (table `NurseryDetails`, effect
  External: go to a website) —
  built specifically to test this. It displayed on a table view, confirmed visually in
  the app editor's preview, rendering as a floating button over the table's rows. This
  agrees with the Position documentation above, which describes Primary as
  scroll-independent and names no view type at all; table views were never excluded by
  the documentation, only by this suite's own code. This confirms the documentation
  rather than extending it: the Position page describes Primary purely by placement —
  scroll-independent, floating on mobile, top of view on desktop — and names no view
  type at all, unlike Prominent, which the same page ties explicitly to detail views.
  The absence of a named restriction was already consistent with Primary working on
  any view type, including tables; this observation resolves what the documentation
  had left implicit rather than adding a new fact to it. The test action's effect was
  External, not Navigate — worth noting because it shows Display_Overlay's
  eligibility to display on a table view does not depend on the action being a
  navigation action specifically.
- **Primary (export: `Display_Overlay`) displays on Deck views.** Source: observed in
  Leon's app, in Kirk's frozen copy, 2026-08-31, in the app editor's preview of the
  "Beds Deck" view (table `Beds Veggies`) — a floating overlay button rendered over
  the deck's rows.
  Three caveats limit what this observation establishes, and are recorded here
  explicitly: (a) the button seen is most likely AppSheet's system-generated Add
  action rather than an author-created one; (b) the action's prominence was not read
  directly off the editor at the time, only inferred from the button's floating
  placement; (c) the deck's "Show action bar" setting state was not recorded, so this
  observation does not by itself establish that an overlay button displays on a deck
  whose action bar is disabled.

  Corroborating documentation, both new to this file: "Explore the desktop design",
  <https://support.google.com/appsheet/answer/12407883>, states that primary actions
  for a view appear in the top navigation bar of the panel and, for the legacy desktop
  design, as overlay (floating) icons; the panels it describes are defined in the same
  passage as the collection views — card, deck, gallery, or table — and detail views,
  displayed in separate panels. Deck is named in that set. "About the new mobile
  framework", <https://support.google.com/appsheet/answer/15831909>, presents primary
  actions under "Floating navigation buttons" as a framework-level UI element, naming
  no view type.

  Consequence: the deck action bar and a Primary button are two different UI elements,
  and all three of this suite's implementations currently gate the second on the
  first — see STATUS.md's known-defects list for the code-level detail; this file is
  about AppSheet, not about this code.

  Because the collection-view passage names card, gallery and table alongside deck,
  Display_Overlay is documented to display on all four collection view types plus
  detail. This does **not** extend to form, map, calendar or dashboard: that passage
  covers collection and detail panels only, and forms are separately documented above
  as not displaying action buttons.
- **A navigation action whose target names a view that does not exist does nothing
  when tapped.** No error message, no fallback to a default view. This is why a
  phantom view reference is invisible to app users and can only be found by static
  analysis of the export.

- **Actions do not display as buttons on form views.** Source: Google's "Actions: The
  Essentials" page, which states that a button is shown for each action in the detail
  view and that actions can be applied in bulk in table, deck and gallery views; form
  views are named nowhere in its account of where actions display. Corroborated by
  Kirk's own experience building AppSheet apps, 2026-08-31, and by community
  workarounds that add pseudo-buttons to forms using Enum columns plus a Form Saved
  grouped action — a workaround nobody would need if actions displayed on forms.
  **A form can still invoke an action**, via the Form Saved event, which per Google's
  "Run actions based on view events" page replaces the default navigation behavior
  when the action navigates. So a navigation route out of a form view is real when it
  rests on an event binding and false when it rests on prominence. 92 of Leon's 319
  views are forms.

- **Card views display actions, but how many and in what form is a property of the
  chosen layout, not of prominence.** Mechanism identified 2026-09-05 by direct
  editor observation in Kankaku (`Card view test`, layout `large`), corroborated by
  Google's "Card view type" page.

  Actions are assigned **per slot, in the Layout widget** — the panel captioned "Click
  on an item in the card to customize it for your app." Selecting a slot opens a small
  pane offering "On Click," from which an action is chosen; Kirk's test view showed
  `Next (Definition)` assigned this way. The four layouts differ in both capacity and
  invocation:

  | Layout | Actions | How invoked |
  |---|---|---|
  | Full (`large`) | up to 4 | 2 as text, 2 as icons |
  | Compact (`list`) | up to 3 | in an Actions drop-down menu |
  | Backdrop | 1 | clicking the card |
  | Photo | 1 | clicking the card |

  **Two of the four layouts have no action buttons at all** — the card itself is the
  target. This resolved what first looked like a contradiction: Farmy's `Histories`
  card view displays no action buttons, and its layout is `photo`. Nothing was missing.

  **The four-action ceiling is a designation limit, not a display limit.** A fifth
  action cannot be assigned, because there is no slot for it — unlike Primary's
  documented maximum, where the actions exist and the client shows fewer. The two are
  currently treated as the same class of thing by the exclusion under "Scope decisions"
  below. That exclusion was made when they looked alike and has NOT been revisited
  here; flagged, not decided.

  **The two icon slots are `favourite` (heart) and `share`, and they are buggy.**
  Third-party reports: July 2022, a user found that setting both to None did not stick
  — they reappeared on save — and Steve escalated it to AppSheet that August; July 2023,
  still unfixed, with a further report that the blank-icon workaround also failed;
  April 2024, a workaround of assigning any action first and then setting None. An
  earlier 2021 thread describes the same resistance and works around it with a dummy
  "Do Not Display" action, and a regular there remarks that card view has been buggy
  since it launched. Kirk reproduced this 2026-09-05: the two text slots accepted an
  assignment and the heart did not. **No source states that the slots restrict which
  KINDS of action they accept**; the observed difference between text and icon slots
  is this bug, not a documented rule. Sources: Google Developer forums, AppSheet Q&A,
  threads 90088 and 75843.

  **Card layout is not confined to card views** — AppSheet offers "Use Card Layout
  inside a Detail View," and several of the threads above concern exactly that. So
  these slots can appear on a view whose `view_type` is `detail`. How often that option
  is used in Kankaku (140 detail views) or Farmy (94) has NOT been measured, and is an
  open question for the suite rather than for AppSheet. 17 of Leon's 319 views are
  cards; Kankaku's 2026-08-31 baseline has none — `Card view test` was created by Kirk
  on 2026-09-05 for this test and postdates that parse.

- **Gallery views are treated as siblings of deck and table views.** Source: three
  Google pages agree, one of them structural rather than behavioral and stronger for
  it. "Explore the desktop design", already cited above under the Deck+Overlay entry,
  groups card, deck, gallery and table together as the collection views that share one
  panel treatment — a claim about UI structure, not about a shared feature the way the
  other two are. "Actions: The Essentials" groups table, deck and gallery together for
  bulk actions; "Run actions based on view events" states that the Row Selected event
  fires when a user taps a record in a deck, gallery or table view. Together these
  support the two files that group gallery with deck, and are evidence against
  `navigation_edge_generator.py`'s unconditional permissiveness for gallery.
  Documentation, not observation: no gallery view has been tested directly.

- **Map views offer no route at all for an author-created action.** Established
  2026-09-05 on three independent legs, strongest first.

  **(a) Editor observation, Kirk, 2026-09-05, with a control.** In Farmy's `Food
  forest Map` view (view type map), View Options offers Map column, Secondary data
  table, Secondary data column, Map type, Location mode and Minimum Cluster Size —
  and nothing else. There is no Actions list and no Show action bar toggle. Under
  Behavior, the Event Actions label appears with no control beside it: no dropdowns,
  no rows, not even an empty selector. The same app's `Beds Deck` view, checked
  immediately afterwards as a control, shows all three of the things the map view
  lacks — Show action bar (on), an Actions list set to Manual listing six selectable
  actions, and three populated Event Actions dropdowns (Row Selected bound to
  `Beds_Details`; Row Swiped Left and Right both "Auto assign (None)"). So both routes
  by which an action could reach a view — view-level designation and event binding —
  are structurally absent for map, and demonstrably present for deck in the same app
  on the same day.

  **(b) Five third-party reports, 2020 through 2025, no dissent found.** June 2020,
  Koichi Tsuji: had asked AppSheet support about setting an overlay action on a map
  view and was told it was not possible. April 2022, WillowMobileSys: states there is
  no ability to add actions to a map view, and reports having just re-tested adding an
  Overlay action himself, without success — the only one of the five that is a direct
  test. September 2024, Steve (a long-standing community authority), answering
  separately in two threads the same day: not possible, including specifically as
  primary or prominent. November 2024, Fabian Weller, the most precise: the only
  actions displayable on a map view as primary are the Add action and the
  automatically created pin action — that is, system-generated ones only, with a
  screenshot. January 2025, Fabian again: no on-click event can be set for a map view,
  and deck view's on-click event does not function inside a map. One further reply in
  that last thread, December 2024, offered a workaround binding an action to pin
  selection; Fabian corrected it a fortnight later as not actually possible, and it
  reads as generated boilerplate. It is disregarded. Sources are the AppSheet Q&A
  category of the Google Developer forums, threads 78905, 84689, 166007 and 165909.

  **(c) The documentation's silence.** Google's "Map view type" page describes the
  selected pin's information appearing in a sidebar detail view or a compact deck-view
  row, and names a built-in driving-directions action — itself system-generated,
  consistent with (b). It never mentions author-created actions. Google's "View types"
  page describes map purely as displaying addresses, XY and LatLong columns, while
  describing card as displaying content *and actions*; the omission is not an
  oversight in a list where the distinction is drawn elsewhere.

  **This supersedes the 2026-08-31 inference previously recorded here**, which held
  that a map action needs designating in the way a deck action needs action-bar
  membership. That was the right conclusion by the wrong mechanism: there is no gate,
  because there is no control to set. The distinction matters — `maintainer/CONSOLIDATION_PLAN.md`
  section 2 concluded from the gate reading that the map cell "cannot be filled by a
  boolean at all," and that conclusion no longer holds.

  **What this does and does not establish, stated explicitly.** It establishes what a
  map view's definition can express, which is the relevant fact for a tool that reads
  the export rather than the screen: an action that cannot be designated cannot appear
  in a map view's `referenced_actions` either. It does not establish what the runtime
  would do with a definition that somehow contained such an action — a distinction
  worth keeping in view, since the 2026-09-05 `LINKTOROW` finding recorded under "Case
  sensitivity" showed the runtime being more permissive than the stored data implied.
  Nothing found in (b) is later than January 2025 and AppSheet ships changes, so this
  should be re-checked by anyone running the suite against an app that does use actions
  on map views.

  **Consequence for a restrictive rule.** Unlike form, map has no event route needing
  protection: a restrictive map rule removes nothing real, because there is no event
  binding to remove. 7 of Leon's 319 views are maps; Kankaku's 2026-08-31 baseline has
  none.

- **Prominent (`Display_Prominently`) does NOT display on a dashboard view.** Observed
  2026-09-07 by Kirk in Kankaku's `Search all` dashboard (three Large view entries,
  Interactive mode off, Use tabs in mobile view off). Two independent grounds:

  **(a) Negative-population argument, the stronger of the two.** Kankaku already
  contains many unrestricted actions on the table the dashboard reports as its own
  (see the next entry for why that reported table is not the whole story). If a
  dashboard rendered its own table's actions, at least some of these would already be
  visible on it. None are.

  **(b) A fresh confirming case.** Kirk created action `My website` (table `Kankaku`,
  effect External: go to a website, Position `Primary`) specifically to test this. It
  does not appear on the dashboard — testing Primary rather than Prominent directly,
  but on the same question of whether a dashboard renders its reported table's
  actions at all, and getting the same answer as (a).

  **What the screenshot's bottom bar is, stated so it is not mistaken for evidence
  against this:** the bar visible at the bottom of the dashboard screenshot is the
  app's own navigation bar (the bottom-nav row every screen in the app carries), not
  the dashboard view's own action bar. Its presence is not evidence of an action
  displaying at dashboard level.

  This closes the dashboard half of the `maintainer/RELEASE_CHECKLIST.md` section A item that
  opened both the dashboard and calendar questions 2026-09-05. **The calendar half
  remains open and unscheduled.**

- **A dashboard's reported `source_table`/`data_source` names one attached table, not
  the tables of the views actually embedded inside it.** Observed 2026-09-07 by Kirk,
  in the same `Search all` test above: the editor preview reports `Table: Kankaku` for
  this dashboard, while it contains three child view entries over three different
  tables. So a dashboard's reported table in both the editor and this suite's export
  is one attached value, not a summary of what is actually in play inside the
  dashboard.

  **Consequence for this suite, recorded in `STATUS.md`:** any reasoning from a
  dashboard's `source_table` is reasoning from a value that does not mean what it
  appears to. `navigation_edge_generator.py`'s `process_dashboard_containment`
  hard-codes all six condition fields to empty for a containment edge — already
  correct behavior, since a containment edge carries no action and so has nothing to
  condition, but the reason had not been written down until this observation
  supplied it.

- **An inline action renders only if the column it is attached to renders.** An inline action's button appears beside its attach-to column's row; if that column's own `Show_If` is false in the current state, the column is absent and so is the button. This holds for a group whose parent action is inline as well, and therefore for the group's children. Observed in Kirk's running Kankaku app, 2026-09-03: the `Schedule position label` column on the `Definition` table carries `Show_If` `and(CONTEXT("ViewType") <> "form",INDEX(Cram[Enum],1)<>"On")`; in cram mode the row is absent from the view and no button attached to it appears, while out of cram the row is present and shows one button, `Visualize schedule 2`, whose condition is `true`. Five actions attach to this column per the 2026-08-31 parse; they were not checked individually in the app, and the general rule above is what the observation supports. Consequence for this suite is recorded in `STATUS.md`, not here.

## Manual action lists

Source: known behaviour, stated by Kirk from experience building AppSheet apps,
2026-08-30. **When a view's actions are set manually, any action not included in that
list is ignored.** This is not deck-specific — it holds for any view type that offers
a manual action-list setting.

The "Go to ObservationActivity" / "MyPlants Food forest Deck" case recorded under
"Established behavior" above does **not** establish this rule on its own, and should not
be cited as if it did: that action was also Prominent, and Prominent does not display
on a deck view for an entirely separate, already-documented reason. Either fact alone
would have produced the same non-display, so that single case cannot isolate which
rule is doing the work. The rule above rests on Kirk's stated experience, not on that
observation.

Deck-specific documentation, source: Google's official page, "Deck and table view
types", <https://support.google.com/appsheet/answer/10106514>. The deck view's
`Actions` setting is documented as: "Action buttons to display in the action bar. The
actions are ordered automatically by AppSheet." The page then describes overriding
that automatic order: "To manually control the action order, do any of the following:
Click **Add** to add actions that you want to display in the order you want them to
appear... If you changed the action order, click **Reset** to switch back to the
AppSheet automatic order." The page does not use the words "excluded" or "hidden";
it names deck views only. The rule at the top of this section is the general form
Kirk gave it, of which this page's `Actions` field is one documented instance.

The same page scopes that `Actions` setting to a specific element: the "Show action
bar" setting is described as showing action
buttons at the bottom of each row, and the "Actions" setting immediately below it is
described as the action buttons to display in that action bar. The action bar is
therefore a per-row element, and the manual list governs its membership. A Primary
(`Display_Overlay`) action is a view-level floating button, not a member of that
row-level bar, so the manual-list exclusion cannot govern it — as the observation
recorded above under "Established behavior" shows. The same page's table-view options
contain no action bar setting at all.

### Open question this raises about the code

`action_display_mode` (manual vs. automatic) is present in the exported view data for
every view type, but `navigation_edge_generator.py` never reads that field at all —
confirmed by search. The manual-list exclusion above is enforced only inside
`is_action_visible_in_deck_view`, hard-coded to the `deck` view type. If a manual
action list can exist on other view types, the suite is currently treating an action
absent from that list as visible there anyway. Not investigated or fixed here; see the
matching entry under "Known defects" in STATUS.md.

## Grouped actions

Source: Google's official page, "Actions: The Essentials",
<https://support.google.com/appsheet/answer/10107706>.

For desktop browsers and the new mobile framework: "Only one navigation action or
external action is executed, even if you specify more than one. It also ends the
execution of the grouped action." A grouped action naming several navigation actions
does not make several destinations reachable through it — only the first navigation
or external action in the group runs, and running it ends the group.

## Case sensitivity

Several independent case-(in)sensitivity facts, established on 2026-08-31 and
expanded 2026-09-01. Do not conflate them — each is a different mechanism, and this
section's own history is why: one AppSheet expert's single sentence lumped two
functions together as "the only case-sensitive places," and testing found that claim
holds for one of them and not the other. Each mechanism named below has been tested
on its own; none is inferred from a sibling.

- **AppSheet's `=` operator is case-insensitive on text.** Source, observation: Kirk
  evaluated the expression `"Card Stats"="card stats"` directly in AppSheet's
  expression tester on 2026-08-31, and it returned `Y`. Corroborating: Google's
  `IN()` page states its match is case-insensitive and gives `([Email] = "@")` as an
  equivalent of `IN("@", LIST([Email]))`; and an AppSheet engineer, replying to a 2019
  report that `LINKTOFORM` column-name references were case-sensitive
  (<https://discuss.google.dev/t/case-sensitivity/78971>), treated that as a bug and
  shipped a fix — indicating case-insensitive comparison is the intended standard and
  exceptions are defects.
- **`CONTEXT()`'s argument is case-insensitive, in both its bare and quoted forms —
  but only within its closed vocabulary.** Source, observation: Kirk tested in
  Kankaku's expression tester, 2026-09-01. `CONTEXT(view)`, `Context(View)`,
  `Context("view")`, and `Context("View")` all worked, regardless of case or quoting.
  But the argument is otherwise unforgiving of anything outside its recognized
  keywords: `CONTEXT(vew)` — a misspelling — silently stopped matching, with no error
  raised; `Context(View Type)` — a space inserted into the keyword — also failed,
  where `Context(ViewType)` (no space) worked. Case is forgiven; spelling and shape
  are not.
- **`FIND()` IS case-sensitive.** Source, observation: Kirk tested
  `FIND("a","ABC")>0` (returned false) against `FIND("A","ABC")>0` (returned true) in
  Kankaku's expression tester, 2026-09-01.
- **What this means for sourcing claims in this section:** an AppSheet expert
  (Steve, March 2020, <https://discuss.google.dev/t/case-sensitivity/78971>) stated
  that `CONTEXT()` and `FIND()` were the only two case-sensitive places in AppSheet.
  `FIND()` still holds; `CONTEXT()` does not, at least as tested in 2026. Whether the
  2020 claim was wrong or the behavior has changed since cannot be told from here, and
  this file records that as an open question rather than picking a side. The same
  thread shows the list growing under further, uncorroborated hands: later replies
  added `LOOKUP()` (Feb 2023) and unspecified "references" (Jul 2023) — the list is
  community-maintained, not authoritative, and neither addition has been tested here.
  The governing principle, restated because this thread demonstrates it directly:
  each mechanism must be tested on its own, not inferred from a sibling — the two
  functions named in one expert's one sentence turned out to behave differently.
- **AppSheet's view namespace is case-insensitive at creation.** Source, observation:
  Kirk created a view named "help" in an app that already had a view named "Help" on
  2026-08-31; the editor immediately and silently renamed the new view to "help 2". So
  two views whose names differ only by case cannot coexist. **What this does not
  cover:** it was observed at creation time in the current editor, and says nothing
  about renames that would create a collision, nor about the action, slice or column
  namespaces, which are separate. Consequence worth stating: a case-insensitive
  view-name match cannot be ambiguous, since two spellings can never denote two
  different views.
- **Untested, and it bears on this suite's code: whether a view name inside
  `LINKTOVIEW`/`LINKTOROW`/`LINKTOFORM` resolves case-insensitively.** The only
  evidence pointing either way is the same thread's Jul 2023 reply that "references"
  are case-sensitive — a one-line reply with no detail, which may not even be about
  view names. This is not an idle gap: see STATUS.md's `f4d931a` entry, which records
  the view `Water Tanks` clearing through this suite's own case-insensitive matching
  of the app's wrong-case `LINKTOVIEW("Water tanks")` call. If AppSheet itself would
  not resolve that call at runtime, the tool cleared a view that is actually
  unreachable — the code-level detail belongs in STATUS.md, not here; this file only
  records that the platform fact needed to judge it is currently unknown.
- **Established 2026-09-05, by app test:** a `LINKTOROW` view-name argument DOES
  resolve case-insensitively at runtime. Kankaku's action `Go to card stats`
  navigates via `=LINKTOROW([_THISROW], "Card Stats")` — capital S, curly quotes —
  and no view named `Card Stats` exists in the app. Tapped on a qualifying card in
  the running app, it rendered the real view `Card stats` correctly. Tested by Kirk
  by direct observation, not inferred from documentation. Incidental: the AppSheet
  editor's preview echoes the view name as spelled in the expression rather than the
  stored view name (`View: Card Stats | Table: Card stats`), so a case error is
  invisible in that display.

## Blank operands in `=` and `<>`

UNSETTLED. Two sources agree that `=` returns TRUE when one operand is blank,
whatever the other holds, and disagree about which operand:

- **Right-hand operand blank.** Source, Google's documentation, the `ISBLANK()`
  help page (<https://support.google.com/appsheet/answer/10107337?hl=en>): "the
  is-equal-to operator (`=`) will always return `TRUE` if the second operand is a
  blank value, regardless of the first operator." The page says nothing about `<>`.
- **Left-hand operand blank.** Source, community forum: an AppSheet expert (Steve,
  23 April 2021,
  <https://discuss.google.dev/t/comparing-column-values-before-and-after/65372/2>):
  "There is a quirk with the is-equal operator (and the is-not-equal operator) where
  if the left-side operand is blank, the expression is TRUE regardless of the
  right-side value."

The documentation is the stronger source by kind, but it is a single sentence on a
page about a different function; the forum answer is a single expert statement, and
it is the only one of the two that mentions `<>`. Neither has been tested here. Both
could be partly true, but neither source says so.

Why it matters: expressions like `[Start at session no] = 0` or `[Cram only] <> TRUE`
put the column on the left, and the column is the side that may be blank. Under the
forum reading, a blank column makes both expressions TRUE; under the documentation's
reading, a blank on the left is not covered at all.

Observed context, which does not settle the question: on Kankaku V19, 2026-09-25,
rows entered directly into the sheet had blank Yes/No and date cells (`Cram only`,
`Early bird`, `Early date`) that the app would normally fill, and the action "Update
session start number with session increment" stopped selecting any card. Filling
the cells fixed it. The cells were filled together, so which blank was decisive, and
through which operator, was not isolated. Settling it needs a test in the expression
tester with a blank column on each side of `=` and of `<>`.

## AppSheet validates shape, not meaning

AppSheet rejects most malformed expressions at save time, so this suite's real
opportunity is narrower and more specific than "catching what AppSheet misses":
AppSheet validates an expression's SHAPE — is this a well-formed call, is this a
valid string literal — but not whether the NAMES inside it denote anything. A
well-formed call with a valid string literal passes, whatever the literal actually
says. From AppSheet's own point of view nothing is wrong in any of the cases below,
which is exactly why its validation cannot be expected to catch them, and exactly why
this is a job for static analysis specifically.

Four instances are established in this project so far, all failing with no error
and no visible symptom:

- **A `CONTEXT()` argument outside its closed vocabulary.** `CONTEXT(vew)`,
  `Context("View Type")` — see "Case sensitivity" above. Neither raised an error;
  neither ever matches (observed 2026-09-01).
  **The closed vocabulary, recorded 2026-09-05 so the check can be done without a parser change.** Source: Google's `CONTEXT()` reference, <https://support.google.com/appsheet/answer/10107885> [documented]. The option must be one of exactly seven keywords: `AppName`, `Device`, `Host`, `OwnerEmail`, `Table`, `View`, `ViewType`. The same page states that an invalid option returns a null value — which is the documented form of the silent non-match observed above, so the observation and the documentation agree. **Case is NOT established by this record:** the page's own sample usage writes `CONTEXT("VIEWTYPE")` in uppercase, which suggests the keyword is matched case-insensitively and sits against the 2020 forum claim (Case sensitivity section above) that `CONTEXT()` is one of the case-sensitive places; neither has been tested here. Practical rule for any sweep or check: flag an argument that fails a CASE-INSENSITIVE match against the seven keywords — `"View Type"`, `"vew"` — as invalid; treat a case-only mismatch (`"VIEWTYPE"`, `"viewtype"`) as unverified rather than invalid until tested. Note also the two AppSheet-side restrictions the same documentation family records, which are not the parser's concern but may explain a false expectation: governance-policy condition expressions accept only `AppName` and `OwnerEmail`; and `Host` returns `Server` when evaluated server-side (automations, security filters, virtual columns computed during sync), so a `Host`-keyed branch can behave differently on sync than on screen.
- **A navigation action naming a view that does not exist does nothing when
  tapped.** Already recorded above under "Established behavior"; not restated here.
- **An action whose prominence and whose own `CONTEXT("ViewType")` condition cannot
  both be satisfied is dead by construction.** [Inferred, not independently tested.]
  Example: a condition requiring `CONTEXT("ViewType")="Deck"` paired with Prominent
  prominence, which the Position documentation above names only for detail views —
  the condition can be true only on a view type where, per that documentation, the
  prominence would never display anyway. This follows logically from two facts
  already established above (Position values; `CONTEXT()`'s behavior), not from a
  new observation of its own.
- **A column's `Show_If` and the condition on an action attached to that column can
  be mutually unsatisfiable.** [Observed, 2026-09-03 — the first directly observed
  instance of the dead-by-construction class above, which until now rested on
  inference.] Kankaku's `Schedule position label` requires
  `INDEX(Cram[Enum],1)<>"On"` to render; two group actions attached to it require
  `INDEX(Cram[Enum],1)="On"` to be visible. Both expressions are well-formed and
  AppSheet accepts both. Only their conjunction is impossible, and nothing in the
  editor reports it. Note that the contradiction here is between a column and an
  action, not within one expression — a checker scanning expressions individually
  would not find it.

## Spreadsheet formulas behind app columns

ESTABLISHED IN PART. For each column filled by a spreadsheet formula, AppSheet keeps its own copy of that formula and writes the copy into every new row the app adds. The copy is refreshed from the sheet when the table's structure is regenerated in the editor. It can also be edited by hand in the editor.

What is stored. The export's `spreadsheet_formula` field holds the copy, in R1C1 notation (references written relative to the cell, for example `counta(R2C[-30]:RC[-30])`), without the leading `=`. The editor shows it under Auto Compute as "Spreadsheet formula", with the note "Generated from your spreadsheet. Gets applied during sync." Fifteen Seminar columns in the Kankaku V19 export store the literal text `COMPUTED_VALUE` instead of a formula. The placeholder does not line up with spill, column by column. Seminar's import in cell A2 covers sheet columns A to Q. Of the 15 placeholder columns, one (Category 2, sheet column R) lies outside that range; one inside the range (Image link, column F) is empty; and three columns inside the range (Tags, Hide translation, Cram) carry no placeholder. So the reading that `COMPUTED_VALUE` marks a spill-filled column is not reliable per column. A likely explanation, not confirmed, is that AppSheet sets the marker when the table is regenerated, according to what the sheet held at that time. Kirk confirmed in the V19 editor on 2026-11-14 that the stored formula shows in the column's Auto Compute section as "Spreadsheet formula", reading `COMPUTED_VALUE` for Seminar's Word column (direct observation). Edits leave such columns alone (see observation A2 below).

Sources, with their strength:

- The editor's own wording, quoted above. Platform text, but it describes the field rather than when the copy is written or refreshed.
- Google's documentation, "Configure column properties" (https://support.google.com/appsheet/answer/10106509?hl=en): a spreadsheet formula is calculated, and its result shown in the app, once the user clicks Save (or Sync if the app uses Delayed Sync). It does not say what happens to existing rows.
- Kirk's test, 2026-09-27. After he changed the Finished cram card formula (Main data column AN) in his master copy and regenerated the Kankaku table, a new card added in the app (row 554) received the new formula. Direct observation.
- Ordinary use, observed 2026-10-04. A card created in the app at 2026-10-04 05:47 JST (row 555 of the master copy) holds the corrected AN formula. Independent of the test above and consistent with it.
- Kirk's test, 2026-10-04. In the editor, he changed Archive[Count]'s stored formula from `counta(R2C[-30]:RC[-30])` to `counta(R2C[-30]:RC[-29])`. The editor accepted it without any error and kept it; he then reverted it. Direct observation.
- Indirect evidence that the copy goes stale without regeneration: in the Kankaku V19 export of 2026-09-26, the Overall table's stored formulas are `0.23` for DW 5min ratio, `now()` for Latest update, and an INDIRECT formula over Collate column AP for Daily record, while the sheet holds different formulas in all three. Consistent with the table not having been regenerated after those formulas changed; not observed as such.
- AppSheet's error-message reference (https://www.appsheet.com/support/errormessages) lists an error for a column definition that specifies both a sheet formula and an app formula. An older page; its current wording has not been checked.
- A1, Kirk's direct observation, 2026-11-14. Kankaku V19, Main data row 23, column AL (app column Max). Kirk replaced the cell's formula with one that differed from the app's stored formula only by an `if(A23="","",...)` wrapper. He then edited that row from the app three times (15:15, 15:18, and 15:23 JST), twice through a form with a Save button (changing a field's text, then adding a tag) and once through an action that marks a correct answer in cram mode. The row's "Last edit" value advanced each time. After each sync, AL23 still held the wrapped formula. So an edit to a row, whether saved from a form or made by an action, did not write the stored formula back into a column that AppSheet knows as a formula column. Limits: one column, one app (V19), one row, three edits. It does not cover adds (a new row still receives the stored formula, established above). It does not cover a column AppSheet does not recognize as a formula column, where a sheet formula may still be overwritten with its computed value on an edit; that remains an untested inference.
- A2, Kirk's direct observation, 2026-11-14, corroborating A1. Seminar (an UPDATES_ONLY table) has 15 columns that store the placeholder. Over its 200 keyed rows, the Copy column holds 29 values Kirk wrote through ordinary app use. The import in cell A2 still fills columns A to I for all 200 rows, and the placeholder columns were not disturbed by those 29 edits. Limit: Seminar allows only edits, not adds, so this says nothing about what a newly added row does to a placeholder column.
- Kirk's observation of 2026-11-10, from experience building AppSheet apps (not a test). The pending-sync counter (the orange circle showing changes waiting to be written) counts one item per row changed, however many cells in that row were changed, and changes to several rows count as several items. Consistent with whole-row writes, though it does not by itself show that unchanged cells are rewritten.
- Update settings in the export. The export records each table's update setting in a row labeled "Are updates allowed?" (HTML `for="UpdateMode"`), and `column_parser.py` records the value exactly as exported. The code recognizes eight values: ALL_CHANGES, ADDS_ONLY, ADDS_AND_UPDATES, ADDS_AND_DELETES, UPDATES_ONLY, UPDATES_AND_DELETES, DELETES_ONLY, and READ_ONLY. The first four of the eight were seen in the Kankaku exports by Claude Code's read-only check of 2026-11-10; the other four come from Google's documentation (AppSheet Help, "Control add, update, and delete operations", https://support.google.com/appsheet/answer/10106345), where I confirmed on 2026-11-19 that the page lists these eight as the values an expression may return. No table in either Kankaku export uses an expression; how the export would show one is unobserved, and that the export writes these same names for ticked combinations is assumed, not observed.

Not established:

- That new rows receive the OLD stored formula when the sheet's formula has changed but the table has not been regenerated. This follows from the rule but has not been directly observed.
- Whether an app edit to an EXISTING row rewrites that row's formula with the stored copy. If it does, a table whose rows deliberately hold different formulas (Kankaku's two-row Overall table) could have a row's formula replaced by a stale stored one. Observation A1 answers this for one case, a column AppSheet knows as a formula column: the edits did not write the stored formula back. The whole-row-write reports below make the question more open, not less, for a column AppSheet does not know as a formula column.
- Whether regeneration picks up a formula newly added to a column that previously had none, and clears the stored copy when a column's formulas are removed. Very likely, since it is the same mechanism, but not observed.
- Whether new rows receive a hand-edited stored formula, and whether a later regeneration overwrites a hand edit.

### Reported by third parties, not observed here

These are community reports and AppSheet help articles, not tests by this project. They are listed with their strength so that the formula checkup's "likely" and "possible" wording follows them. Pages were opened on 2026-11-19 through a summarizing fetch tool, so the paraphrases below rest on those summaries, not on a full reading.

- Whole-row writes (community reports, several replies). Replies say that when any column of a row changes, AppSheet writes the whole row back, not just the changed cell, and that edits made to the same row in the meantime can be overwritten. Four threads, all on the Google Developer forums:
  - "Row vs cell updates." A reply by a staff member says changes are written per row, not per cell, with the last writer winning, whatever the data source. Original question posted 2019-04-03; the date of the reply was not retrieved. https://discuss.google.dev/t/row-vs-cell-updates/56646
  - "New Bug Encountered: Add a new row to another table." A reply dated 2020-04-08 says the whole row is sent when any column changes, so columns an action did not list were reset to empty. https://discuss.google.dev/t/new-bug-encountered-add-a-new-row-to-another-table/64816
  - "Form no working to add line in Smartsheet anymore." A reply dated 2022-06-28 states the whole-row write specifically for Google Sheets. https://discuss.google.dev/t/form-no-working-to-add-line-in-smartsheet-anymore/68559
  - "Data disappearing" (AppSheet Q&A). A reply dated 2022-04-29 says the whole row is written, including the old values of the other columns, so two near-simultaneous edits can overwrite each other. https://discuss.google.dev/t/data-disappearing/84936
- Sheet formulas AppSheet does not know about are erased when the app adds a row (community reports, two threads, Google Cloud Community pages that redirect to discuss.google.dev).
  - "Is there a way to tell an Appsheet Column NOT to delete a Spreadsheet formula when a row is added?" The reply, dated 2019-09-09 (the original post's date was not retrieved), advises putting the formula in every existing row and regenerating at once, after which new rows get the formula. The fetch summary did not show the plan's further point that regeneration made the column read-only, nor the pointer to the "Mismatched spreadsheet formulas" article; neither is confirmed here. https://www.googlecloudcommunity.com/gc/AppSheet-Q-A/Is-there-a-way-to-tell-an-Appsheet-Column-NOT-to-delete-a/m-p/267160
  - "Appsheet deleting formulas when inserting new data into the sheet." Question posted 2025-05-03, reply 2025-05-05. The reply says AppSheet rewrites the whole row, so sheet formulas are overwritten even in protected cells. This reply reads somewhat like generated boilerplate and is the weakest source of the group. https://www.googlecloudcommunity.com/gc/AppSheet-Q-A/Appsheet-deleting-formulas-when-inserting-new-data-into-the/td-p/902655/jump-to/first-unread-message
- Platform documentation, not a community report, and not observed here: AppSheet Help, "Mismatched spreadsheet formulas" (https://support.google.com/appsheet/answer/10101313), checked 2026-11-19; the page shows no date beyond a 2026 copyright line. It says AppSheet converts each cell's formula to R1C1, finds the share of cells using each formula, and assigns the most common formula to the whole column when one formula covers a high percentage of cells, tolerating "the occasional distinct formula type". Cells that differ are flagged in a warning in the editor that lists the first five, the comparison is strict (a one-character difference is a mismatch), and the page advises fixing the cells and regenerating. No threshold is given. This is not the same as the earlier reading that a column's formula is recognized only if every cell matches.
- A COMPUTED_VALUE column can write the literal text into the sheet (one community report). A column filled by an array formula got `COMPUTED_VALUE` as its stored formula, and AppSheet wrote that string into the sheet when rows were added, breaking the array formula. The reply, dated 2021-06-09, says AppSheet's support for spreadsheet formulas is limited. "Rows added to google sheet column have value COMPUTED_VALUE," Google Cloud Community. https://www.googlecloudcommunity.com/gc/AppSheet-Q-A/Rows-added-to-google-sheet-column-have-value-quot-COMPUTED-VALUE/m-p/335009
- What `COMPUTED_VALUE` is (community thread with a staff reply). A staff reply of 2019-11-25 to 2019-11-26 says the placeholder appears when regeneration reads a sheet formula that has no Excel equivalent, such as QUERY: regeneration exports the sheet to Excel format, and AppSheet then stores the resulting literal text as the column's formula and writes it into new rows. This explains where the placeholder comes from, and supports the "when the table is regenerated" explanation above, but does not mention spill. "What is COMPUTED_VALUE in Spreadsheet formula and How does it Work?", Google Developer forums. https://discuss.google.dev/t/what-is-computed-value-in-spreadsheet-formula-and-how-does-it-work/71284

The suite's formula checkup words its findings "likely" and "possible" according to the grades above (see "Built: the formula checkup for app-table columns" in STATUS.md).

## Scope decisions — deliberate exclusions

Source: Kirk's decision, 2026-08-30. Recorded so these are not re-litigated.

- **Primary (export: `Display_Overlay`) has documented client-dependent display
  limits.** Source: "About the new mobile framework",
  <https://support.google.com/appsheet/answer/15831909> — not the Position
  documentation above, which names no such limits. The new mobile framework supports
  up to 6 primary actions and shows a More menu once there are 3 or more; the current
  (legacy) framework overlays action buttons on content to a maximum of 4. The suite
  will NOT model or flag this. Actions are assumed valid; app users can discover such
  cases themselves.
- **One unverified community report** holds that a Primary (export: `Display_Overlay`)
  action does not display when its view is embedded as a reference view inside a
  dashboard. Recorded as unverified, and out of scope for the same reason as the limit
  above.
- The general principle these two share, since it will come up again: **some display
  rules depend on the client or on the containing view, rather than on the view's own
  type** — and a prominence-by-view-type table, however complete, cannot express
  either kind.

## Unknowns

What Prominent (export: `Display_Prominently`) does on **calendar** views remains
genuinely unestablished — named nowhere in the documentation read for this file, and
not tested. This is the only view type left from the original six-type list once
tracked here; `form`, `card`, `gallery`, `map`, and now `dashboard` are addressed
under "Established behavior" above, each entry naming its own source. This is not
silence by omission; it is the current honest boundary of what is known.

The map cell's consequence for this suite's output — the edges it emits to Map views
for the "Go to ObservationActivity" action (see STATUS.md) — is addressed in the map
bullet under "Established behavior" above; not repeated here.

Prominent-on-Deck is not listed separately here because it is recorded in full
under "Established behavior" above. It is no longer a documentation-only claim: the
isolating test once described here as missing — a `Display_Prominently` action on a
Manual deck whose action list includes it — was run 2026-09-02, and the action
displayed. What remains untested is the other half of that same isolating test: a
`Display_Prominently` action on a deck whose `action_display_mode` is `Automatic`,
and, more broadly, whether `Automatic` mode's `referenced_actions` field is itself
complete — an open question independent of this one (`maintainer/CONSOLIDATION_PLAN.md`
section 5's "Deliberately deferred" note).

Calendar remains answerable by one test in a running app, the same way dashboard
just was; the frozen copy of Farmy holding the calendar view is unscheduled. Form,
card and gallery were closed by documentation; map rests on Kirk's stated
inference; dashboard is now settled by direct observation, 2026-09-07 (see
"Established behavior" above). Deck is no longer a single grade: both
Prominent-on-Deck and Overlay-on-Deck are now settled by direct observation (see
"Established behavior" above) — Prominent-on-Deck for the Manual-list-membership
case specifically, not yet for Automatic mode. Those are several different grades
of evidence and this file does not treat them as one.

How `=` and `<>` treat a blank operand — left or right — is unsettled, with a
documentation source and a forum source disagreeing; see "Blank operands in `=` and
`<>`" above.
