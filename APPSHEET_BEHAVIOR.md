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
  (`CONSOLIDATION_PLAN.md` section 5's "Deliberately deferred" note). Google's
  Position documentation, which names only Detail for Prominent, is now directly
  contradicted by observation for this one case; whether Prominent excludes itself
  under any other deck condition is untested.

  `CONSOLIDATION_PLAN.md` section 5's step 5 applied the opposite rule — excluding
  `Display_Prominently` from deck views entirely, on the strength of the
  documentation-only reading this entry now supersedes — across all three visibility
  strategies. It has been disproved by the observation above and reverted, 2026-09-02,
  without ever being committed; see `STATUS.md` and `CONSOLIDATION_PLAN.md` for the
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
  because there is no control to set. The distinction matters — `CONSOLIDATION_PLAN.md`
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

What Prominent (export: `Display_Prominently`) does on **calendar** and **dashboard**
views remains genuinely unestablished — named nowhere in the documentation read for
this file, and not tested. These are the only two view types left from the original
six-type list once tracked here; `form`, `card`, `gallery`, and `map` are now
addressed under "Established behavior" above, each entry naming its own source. This
is not silence by omission; it is the current honest boundary of what is known.

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
complete — an open question independent of this one (`CONSOLIDATION_PLAN.md`
section 5's "Deliberately deferred" note).

Calendar and dashboard are each answerable by one test in a running app. Form,
card and gallery were closed by documentation; map rests on Kirk's stated
inference. Deck is no longer a single grade: both Prominent-on-Deck and
Overlay-on-Deck are now settled by direct observation (see "Established behavior"
above) — Prominent-on-Deck for the Manual-list-membership case specifically, not
yet for Automatic mode. Those are several different grades of evidence and this
file does not treat them as one.
