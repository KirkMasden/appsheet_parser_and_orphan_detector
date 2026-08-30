# Release checklist

Everything standing between now and telling Leon the scripts are ready to test.
Written 2026-08-31. This list is meant to be finite: when every item is done, the
work stops and testing begins.

Not a status file (see `STATUS.md` for defects), not a specification (see
`APPSHEET_BEHAVIOR.md` for what AppSheet does), not a design (see
`CONSOLIDATION_PLAN.md` for how the visibility logic gets unified). This is the
ordered worklist.

Each item states what "done" means. An item is not done until its finish
condition is met and recorded in the file named.

---

## A. App tests — Kirk's, a few minutes each

These block section C. Each is answerable by putting an action on a view in a
running app and looking. Nothing else can answer them: the rules are facts about
AppSheet's client, not derivable from the exports.

- [ ] **Does Prominent (`Display_Prominently`) display on a form view?**
      92 of Leon's 319 views are forms — the single largest block of the
      undecided bucket.
      *Done when:* the answer is recorded under "Observed behavior" in
      `APPSHEET_BEHAVIOR.md`, with the date and how it was tested.

- [ ] **Does Prominent display on a card view?** (17 views)
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`.

- [ ] **Does Prominent display on a map view?** (7 views)
      Consequential: the suite currently emits edges to Map views for
      "Go to ObservationActivity", and if the answer is no, those edges are false.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`, and the "map cell is
      currently consequential" note in that file is resolved either way.

- [ ] **Is Gallery treated like Deck?**
      `navigation_edge_generator.py` treats gallery as unconditionally permissive
      while two other files group it with deck. No rationale exists in the code.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`.

Optional, only if convenient: confirm the manual-action-list exclusion on a
non-deck view type, which would close the open question already recorded under
"Manual action lists" in `APPSHEET_BEHAVIOR.md`.

---

## B. Code fixes — specified, no decisions needed

Each is a Claude Code task with a predicted diff, verified by full re-parse and
comparison against the current reference output.

- [ ] **`parse_linktorow` greedy regex.**
      `LINKTOROW\s*\((.*)\)` with DOTALL matches from the first opening paren to
      the last closing paren in a block, so a block containing several
      `LINKTOROW` calls yields a garbage view name. Currently produces one bogus
      row in `action_targets.csv` and one false entry in
      `potential_phantom_view_references.csv`, via the action
      "Take Image Form Save Where to next". A false phantom is worse than a
      missing one — it sends a user hunting for a button that isn't broken.
      *Done when:* both bogus entries are gone, no other output changes, and the
      `STATUS.md` defect entry moves to "Recently fixed" with its commit hash.

- [ ] **Map fall-through in `is_action_visible_in_view`.**
      Every view type without an explicit branch returns `True` unconditionally.
      Depends on item A's map result — and possibly on the form and card results
      too, since they share the same code path.
      *Done when:* the fallback reflects what section A established, and
      `STATUS.md` records the decision and its basis.

- [ ] **`action_dependency_analyzer.py`'s table-view rule** (if the current run
      confirms it is wrong).
      Its table branch has no `Display_Overlay` case and falls through to
      `False` — the same wrong answer as the edge generator's explicit
      rejection, reached by omission. Deliberately left out of the current commit
      so the two output-affecting edits could be verified alone.
      *Done when:* fixed, or recorded in `STATUS.md` as deliberately left alone
      with the reason.

---

## C. Consolidation — `CONSOLIDATION_PLAN.md`

Do not start before section A. Steps 4 and 5 are only judgment calls because the
answers are unknown; once A is done they become mechanical.

- [ ] **Steps 1–3: extract, fix the case bug, switch all callers.**
      Mechanical. Steps 1 and 3 predict a zero diff, and that zero is the test —
      any change means the extraction was not behavior-preserving and the step
      should be treated as failed, not patched forward. Step 2 fixes the
      `'Do_Not_Display'.replace('_',' ')` mismatch, which currently disables the
      Hide exclusion on deck and gallery in two of three files.
      *Done when:* all three callers use the shared module, each step verified,
      each committed separately.

- [ ] **Step 4: Gallery/Deck parity.** Blocked on item A.

- [ ] **Step 5: Prominent-on-Deck exclusion, applied everywhere.**
      Note the direction: this can *increase* orphan counts, unlike every fix so
      far. An increase here is expected, not a regression.

- [ ] **The 120-view "other" bucket.** Blocked on item A. This is the largest
      single gap in the suite and the one most likely to generate exactly the
      false positives Leon reported.

**Caution for whoever runs these:** the plan's predictions were computed against
a reference output that is now several commits old. Re-parse against the latest
before trusting any predicted diff.

---

## D. Before contacting Leon

- [ ] **Push.** The commits have been local since 2026-08-30.

- [ ] **Report the four broken form views in Leon's app.**
      `Seeds Form` (the real view is `Seeds_Form`), `ActivityForm - Transplant`,
      `ActivityForm - Germination`, `ActivityForm Observation`. Named by
      actions, absent from the app. Confirmed 2026-08-31 that a navigation
      action pointing at a nonexistent view does nothing at all when tapped —
      no error, no fallback — so these are invisible to users and findable only
      by static analysis. Worth saying so: it is the clearest demonstration of
      what the tool is for.

- [ ] **A `CLAUDE.md` at the repository root**, per the July plan: CSV schemas,
      which analyzer answers which question, the instruction to call analyzer
      methods directly rather than driving the interactive menus, and the known
      blind spots. Ship an `AGENTS.md` with the same content for non-Anthropic
      tools. Optional for a first test round, but it is what lets a tester's own
      AI use the suite without reverse-engineering it.

---

## Deliberately not on this list

Recorded so they are not mistaken for oversights.

- The 13 `#page=map` deep links, still unparsed and still misfiled as "Unknown
  pattern". Resolving them needs an app observation *and* has an ambiguity
  problem behind it: several map views can share one table.
- The 32 `Do_Not_Display` actions with no identified invocation route. Some may
  be genuinely dead buttons in Leon's app, which would be worth telling him,
  but that is analysis rather than a fix.
- Primary's client-dependent display limits, and the unverified report about
  dashboard-embedded views. Both excluded by decision on 2026-08-30 and recorded
  in `APPSHEET_BEHAVIOR.md`.
- Extending the visibility layer to the backing Google Sheet. A separate project.

---

## The pattern worth remembering

Every defect found on 2026-08-30 and 31 has the same shape: a rule enforced only
where someone wrote a branch for it, because Kirk's app never exercised the rest.
`LINKTOFILTEREDVIEW` missing from a hard-coded list; `LINKTOFORM` excluded by an
action-type gate; map views with no visibility branch; manual action lists
checked only for decks; the same display rule written three times, differently;
and `Display_Overlay` rules written without anyone recording that it means
Primary.

Leon's app is the first evidence of what that costs. A third app would surface
more. `APPSHEET_BEHAVIOR.md` and its Unknowns section exist so that the next
surprise can be traced to a documented gap rather than reverse-engineered from
inconsistent code — which may make it more useful to testers than to Kirk.
