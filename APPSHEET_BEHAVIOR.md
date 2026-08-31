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

- **Prominent (export: `Display_Prominently`) on a Deck view: not established by
  observation.** The documentation above names only detail views for Prominent, and
  nothing here contradicts it — but the test once cited as confirming it does not
  isolate the rule. Action "Go to ObservationActivity" (table `MyPlants`, prominence
  Prominent, condition `OR(CONTEXT("ViewType")="Deck", CONTEXT("ViewType")="Map")`)
  never appeared on "MyPlants Food forest Deck". Checked against the export
  2026-08-31: that deck's `action_display_mode` is `Manual` and the action is absent
  from its `referenced_actions`, though present in its `available_actions`. The
  manual-list rule below therefore accounts for the non-display on its own, exactly as
  prominence would. Either rule alone explains what was seen, so the case establishes
  neither — this is the same reasoning already applied to it under "Manual action
  lists" below, now applied in both directions. Until an isolating test is run, treat
  Prominent-on-Deck as resting on Google's documentation alone.
- **Primary (export: `Display_Overlay`) DOES display on table views.** Source:
  observed in Kirk's own app, 2026-08-31, using a purpose-made External action set to
  Primary — "Go to web" (table `NurseryDetails`, effect External: go to a website) —
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

- **Gallery views are treated as siblings of deck and table views.** Source: two
  Google pages agree. "Actions: The Essentials" groups table, deck and gallery
  together for bulk actions; "Run actions based on view events" states that the Row
  Selected event fires when a user taps a record in a deck, gallery or table view.
  This supports the two files that group gallery with deck, and is evidence against
  `navigation_edge_generator.py`'s unconditional permissiveness for gallery.
  Documentation, not observation: no gallery view has been tested directly.

- **Map views: inference, not established.** Google's "Map view type" page describes
  information about the selected row appearing in a deck-view row at the bottom of
  the screen, and notes a built-in driving-directions action on each map view. Kirk's
  inference from this, 2026-08-31: an action will not appear on a map view unless it
  is properly designated for it, in the same way a deck view requires an action to be
  on its action bar. **This is a reasoned guess, not a test.** Kirk's own app does not
  use actions on map views, and testing it in Leon's app was judged not worth the
  effort relative to its value. The suite acts on this inference; it should be
  re-tested by anyone using the suite on an app with actions on map views. 7 of
  Leon's 319 views are maps.

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

Deck-specific documentation, source: Google's official page, "Customize deck and
table views", <https://support.google.com/appsheet/answer/10106514>. The deck view's
`Actions` setting is documented as: "Action buttons to display in the action bar. The
actions are ordered automatically by AppSheet." The page then describes overriding
that automatic order: "To manually control the action order, do any of the following:
Click **Add** to add actions that you want to display in the order you want them to
appear... If you changed the action order, click **Reset** to switch back to the
AppSheet automatic order." The page does not use the words "excluded" or "hidden";
it names deck views only. The rule at the top of this section is the general form
Kirk gave it, of which this page's `Actions` field is one documented instance.

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

## Scope decisions — deliberate exclusions

Source: Kirk's decision, 2026-08-30. Recorded so these are not re-litigated.

- **Primary (export: `Display_Overlay`) has documented client-dependent display
  limits** — a maximum of six primary actions on the new mobile framework, four on the
  legacy mobile design (per the Position documentation above). The suite will NOT
  model or flag this. Actions are assumed valid; app users can discover such cases
  themselves.
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

Prominent-on-Deck is no longer tracked as a separate unknown here. The Position
documentation above already named only Detail for Prominent, and the gallery/deck/
table sibling grouping recorded under "Established behavior" corroborates that
Google's pages delineate view-type eligibility deliberately when they name one at
all — evidence that the silence about deck is the same kind of deliberate omission,
not an oversight. See the Deck bullet under "Established behavior" for the full
reasoning; it still rests on documentation alone, not on an isolating observational
test, and that distinction is why it isn't marked resolved-by-observation there.

Each unknown remaining here — calendar and dashboard — is answerable by one test in
a running app, the same way form, card, gallery, map, and deck were each closed
without one.
