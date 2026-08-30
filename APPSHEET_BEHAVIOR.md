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

## Manual action lists

Source: known behaviour, stated by Kirk from experience building AppSheet apps,
2026-08-30. **When a view's actions are set manually, any action not included in that
list is ignored.** This is not deck-specific — it holds for any view type that offers
a manual action-list setting.

The "Go to ObservationActivity" / "MyPlants Food forest Deck" case recorded under
"Observed behavior" above does **not** establish this rule on its own, and should not
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
