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

Source: Google's official page, "Actions: The Essentials",
<https://support.google.com/appsheet/answer/10107706>.

- **Primary** — "Display independently of scrolling, such as floating buttons on
  mobile devices and at the top of a view on desktop browsers." No view type is named
  in the documentation; the placement is described as scroll-independent, not
  view-type-specific.
- **Prominent** — "Display in detail views as a button at the top of the screen (most
  common)." Detail is the only view type the documentation names for this position.
- **Inline** — "Display alongside the associated column," so it requires a view that
  renders columns. Documented caveat for table views specifically: "the action
  replaces the column content instead of displaying alongside it" — an inline action
  in a table does not appear beside its column, it takes the column's place.
- **Hide** — "Don't display in any view." (This suite's data calls this value
  `Do_Not_Display`.)

## Observed behavior

Source: observed in Leon's app, 2026-08-30, by Kirk.

- An action set to **Prominent does NOT display on a Deck view.** Confirmed by direct
  test: action "Go to ObservationActivity" (table `MyPlants`, prominence Prominent,
  condition `OR(CONTEXT("ViewType")="Deck", CONTEXT("ViewType")="Map")`) never
  appeared on the deck. This agrees with the documentation above naming only detail
  views for Prominent — it is confirmation of the documented rule's boundary, not a
  new rule.
- **A navigation action whose target names a view that does not exist does nothing
  when tapped.** No error message, no fallback to a default view. This is why a
  phantom view reference is invisible to app users and can only be found by static
  analysis of the export.

## Deck view action bar

Source: Google's official page, "Customize deck and table views",
<https://support.google.com/appsheet/answer/10106514>.

The deck view's `Actions` setting is documented as: "Action buttons to display in the
action bar. The actions are ordered automatically by AppSheet." The page then
describes overriding that automatic order: "To manually control the action order, do
any of the following: Click **Add** to add actions that you want to display in the
order you want them to appear... If you changed the action order, click **Reset** to
switch back to the AppSheet automatic order."

The page does not use the words "excluded" or "hidden," but the field is defined as
*the* list of actions to display — so an action not added to it, once the list has
been manually built, does not display there regardless of its Position. This reading
is confirmed by the observed case above: "Go to ObservationActivity" is absent from
"MyPlants Food forest Deck"'s manually-built action list (`action_display_mode` =
Manual there), and it does not display on that deck — independently of, and prior to,
the Prominent/Deck incompatibility also confirmed there.

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

- **Primary has documented client-dependent display limits** — a maximum of six
  primary actions on the new mobile framework, four on the legacy mobile design (per
  the Position documentation above). The suite will NOT model or flag this. Actions
  are assumed valid; app users can discover such cases themselves.
- **One unverified community report** holds that a Primary action does not display
  when its view is embedded as a reference view inside a dashboard. Recorded as
  unverified, and out of scope for the same reason as the limit above.
- The general principle these two share, since it will come up again: **some display
  rules depend on the client or on the containing view, rather than on the view's own
  type** — and a prominence-by-view-type table, however complete, cannot express
  either kind.

## Unknowns

What Prominent does on **map, card, gallery, calendar, or dashboard** views is
unestablished — named nowhere in the documentation read for this file, and not yet
tested. This is not silence by omission; it is the current honest boundary of what is
known.

The **map cell is currently consequential**, not merely unknown: the suite emits
edges to Map views for the "Go to ObservationActivity" action described above (see
STATUS.md). If Prominent does not render on maps, those edges are false, in the same
way the deck edges would have been false had "Go to ObservationActivity" been on that
deck's action list.

Each unknown here is answerable by one test in a running app, the same way the Deck
case above was settled.
