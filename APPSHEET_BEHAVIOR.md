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

Each entry names how it was established. Direct observation, documentation, and
reasoned inference are not interchangeable, and an entry's strength is the strength
of its source.

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

- **Card views display actions.** Source: Google's "Card view type" page, which
  describes the card view as displaying content and actions for a single element, and
  specifies how many each layout holds — up to four on the full card (two as text,
  two as icons) and up to three on the compact card. 17 of Leon's 319 views are cards.
  The per-layout action cap is a client display limit of the same kind as Primary's
  documented maximum, and is out of scope by the decision recorded under "Scope
  decisions" below.

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

- **Map views: inference, not established.** Google's "Map view type" page describes
  information about the selected row appearing in a deck-view row at the bottom of
  the screen, and notes a built-in driving-directions action on each map view. Kirk's
  inference from this, 2026-08-31: an action will not appear on a map view unless it
  is properly designated for it, in the same way a deck view requires an action to be
  on its action bar. **This is a reasoned guess, not a test.** Kirk's own app does not
  use actions on map views — confirmed more strongly by the 2026-08-31 Kankaku
  baseline parse: its view types are detail 140, form 35, table 12, deck 9, dashboard
  1, with no map views at all — and testing it in Leon's app was judged not worth the
  effort relative to its value. The suite acts on this inference; it should be
  re-tested by anyone using the suite on an app with actions on map views. 7 of
  Leon's 319 views are maps.

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
