# Release checklist

Everything standing between now and telling Leon the scripts are ready to test.
Written 2026-08-31. This list is meant to be finite: when every item is done, the
work stops and testing begins. That is phase one, and everything through section E
below belongs to it. A phase two exists — a related but separate project, described
at the end of this file — and it begins only after phase one ends at publication and
a break is taken. Nothing in phase two is pending release work; it should not be
sequenced into the sections above it.

Not a status file (see `STATUS.md` for defects), not a specification (see
`APPSHEET_BEHAVIOR.md` for what AppSheet does), not a design (see
`CONSOLIDATION_PLAN.md` for how the visibility logic gets unified). This is the
ordered worklist.

Each item states what "done" means. An item is not done until its finish
condition is met and recorded in the file named.

---

## A. App tests — Kirk's, a few minutes each

These block section D. Each is answerable by putting an action on a view in a
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

- [ ] **Does Prominent display on a deck view, tested without the manual-list confound?**
      The 2026-08-30 observation cited for this rule does not isolate it: the deck used
      was in Manual mode with the action absent from its action list, so the manual-list
      rule explains the non-display by itself. Test on an Automatic-mode deck, or on a
      Manual deck whose list includes the action.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md` under "Observed behavior".
      Blocks section D step 5, which is billed on this rule and can raise orphan counts.

Optional, only if convenient: confirm the manual-action-list exclusion on a
non-deck view type, which would close the open question already recorded under
"Manual action lists" in `APPSHEET_BEHAVIOR.md`.

---

## B. Code fixes — specified, no decisions needed

Each is a Claude Code task with a predicted diff, verified by full re-parse and
comparison against the current reference output.

- [x] **`parse_linktorow` greedy regex.**
      `LINKTOROW\s*\((.*)\)` with DOTALL matches from the first opening paren to
      the last closing paren in a block, so a block containing several
      `LINKTOROW` calls yields a garbage view name. Currently produces one bogus
      row in `action_targets.csv` and one false entry in
      `potential_phantom_view_references.csv`, via the action
      "Take Image Form Save Where to next". A false phantom is worse than a
      missing one — it sends a user hunting for a button that isn't broken.
      *Done when:* the bogus `action_targets.csv` row and the false
      `potential_phantom_view_references.csv` entry are both gone, every added row is
      accounted for individually, and the `STATUS.md` defect entry moves to "Recently
      fixed" with its commit hash.
      *Predicted direction, not a row count:* rows will be ADDED, not merely removed.
      That expression holds 8 `LINKTOROW` and 3 `LINKTOFORM` calls, counted against the
      export 2026-08-31, yet currently yields only 2 rows in `action_targets.csv`, one
      of them the bogus one — because `parse_linktorow` uses `re.search` rather than
      `re.finditer` and so returns at most one target per expression however the regex
      is written. Expect up to 8 LINKTOROW targets to appear. The 3 `LINKTOFORM` calls
      in the same block will still be dropped afterwards; they are lost to the separate
      first-match-only dispatch defect, which is its own later item. New phantom entries
      are possible if a recovered target names a view that does not exist. Stop and
      re-examine if the counts move in any other direction.
      *Confirmed, with one addition the prediction did not anticipate:* fixed in
      `496d5ed`. The predicted direction held — rows added, not merely removed — but
      the real root cause was broader than "multiple `LINKTOROW` calls in one block":
      it was the regex running past each call's own closing paren, which a single
      call followed by trailing string concatenation can trigger too. That second
      trigger surfaced a second affected action, `Sync | Order (Complete)`, that
      this item's brief did not name. See `STATUS.md`'s "Recently fixed" entry for
      full verification detail.

- [x] **`parse_navigation_expression`'s first-match-only dispatch.**
      The four-function tail (`LINKTOVIEW`, `LINKTOROW`, `LINKTOFILTEREDVIEW`,
      `LINKTOFORM`) was a chain of early returns, so an expression mixing more than
      one navigation function resolved to whichever function the chain checked
      first, silently dropping the rest. Named in `Level 0 - Go to`
      (`LINKTOVIEW("Nursery_Form")` alongside two `LINKTOFORM("MyPlants_Form", ...)`
      calls in one `SWITCH` case) and in the `parse_linktorow` item above (the 3
      `LINKTOFORM` calls it left dropped).
      *Done when:* fixed in `43d9167`, verified by full re-parse against
      `20260831_151553_AppsheetFarmyApp_for_Kirk_parse`, and the `STATUS.md` defect
      entry moved to "Recently fixed" with its commit hash.
      *Confirmed:* `action_targets.csv` 458 → 463 (+5, 0 removed, 0 modified), across
      exactly the two actions predicted — `Level 0 - Go to` (+3, including one more
      instance of the same defect in a different branch than the one originally
      named) and `Take Image Form Save Where to next` (+2 of its 3 `LINKTOFORM`
      calls; the third was already reachable pre-fix). The control, `Go to
      LinkToView` (~30 single-function `SWITCH` branches), is byte-for-byte
      unchanged. All 5 recovered target views exist; all five orphan-count files
      unchanged. `SWITCH` still isn't decomposed as a branching construct —
      recovered `SWITCH` targets carry no `ifs_branch_index`/`ifs_branch_text` —
      and that gap remains open.

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

- [ ] **Audit the six never-examined modules named in `STATUS.md`.**
      `view_orphan_detector.py`, `view_dependency_analyzer.py`,
      `slice_orphan_detector.py`, `format_rules_parser.py`,
      `format_rule_orphan_detector.py`, `column_dependency_analyzer.py`. The
      seventh, `action_dependency_analyzer.py`, is already known to carry a live
      bug found the moment anyone looked — that is the reason to look at the
      others. Read-only: report what each module assumes, not a fix.
      *Done when:* the audit has been run and its findings are recorded in
      `STATUS.md`, whether or not anything needs fixing.

---

## C. A second reference parse — Kirk's own current app

Every verification in this project compares a re-parse against one saved reference
output: Leon's app. That is a single-app test bed, and this week showed exactly what
it misses — every defect found came from rules Kirk's app never exercised. Kirk's
app also contains prominence values and view types Leon's does not, so a second
reference covers different ground rather than merely more of the same.

- [ ] **Produce and save a reference parse of Kirk's current app.**
      Three reasons, listed separately because they need different work:
      - *Regression guard:* a saved reference parse of the current app, diffed
        alongside Leon's on every subsequent change. The consolidation's steps 1
        and 3 (section D below) claim a zero diff across every output file, and
        that claim is far stronger verified against two apps than one.
      - *Source of new findings:* run it, look at what gets flagged, and check
        the surprising results in the running app. That is how this week's
        discoveries happened.
      - *Because the app has changed:* the suite was shaped around this app once;
        some rules encoded then may no longer match what Kirk builds now.
      *Done when:* a reference parse of the current app exists at a stable path,
      that path is recorded in this checklist, and both references are diffed on
      every subsequent change.

---

## D. Consolidation — `CONSOLIDATION_PLAN.md`

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
`20260830_linktoform_verify/20260830_212632_AppsheetFarmyApp_for_Kirk_parse`, which
predates `e0530c8` and the 82 `navigation_edges.csv` rows it added. The most recent
Leon-app parse on disk is
`20260831_primary_overlay_verify/20260831_081316_AppsheetFarmyApp_for_Kirk_parse`.
Both sit outside the repository, since `*_parse/` is gitignored. Re-parse against the
current code before trusting any predicted diff.

Count CSV rows with a real CSV parser rather than `wc -l` or line-splitting: several
fields in these outputs contain embedded newlines, and naive counting gives wrong
answers. This was confirmed on 2026-08-31, when a `wc -l` count of
`navigation_edges.csv` disagreed with the true row count.

---

## E. Before contacting Leon

- [ ] **Push.** The commits have been local since 2026-08-30.

- [ ] **Report the five broken view references in Leon's app.**
      `Seeds Form` (the real view is `Seeds_Form`), `ActivityForm - Transplant`,
      `ActivityForm - Germination`, `ActivityForm Observation`, and `NurseryForm2b`.
      Named by actions, absent from the app. Confirmed 2026-08-31 that a navigation
      action pointing at a nonexistent view does nothing at all when tapped —
      no error, no fallback — so these are invisible to users and findable only
      by static analysis. Worth saying so: it is the clearest demonstration of
      what the tool is for.
      Note for the report to Leon: the first four are `LINKTOFORM` references in
      form actions, but `NurseryForm2b` is a `LINKTOROW` reference in a Sync action
      (`Sync | Order (Complete)`, table `Nursery`) — don't describe all five as
      form-view problems.

- [ ] **A `CLAUDE.md` at the repository root**, per the July plan: CSV schemas,
      which analyzer answers which category of question, the instruction to call
      analyzer methods directly rather than driving the interactive menus, and
      the known blind spots. Ship an `AGENTS.md` with the same content for
      non-Anthropic tools. Required before publication, not optional: a
      published tool that other people's AI will use needs this to use the
      suite without reverse-engineering it.

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
- Extending the visibility layer to the backing Google Sheet. See "Phase two" at
  the end of this file — a separate project, broader than this one line suggests.

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

---

## Phase two — making the backing Google Sheet visible to AI

Not pending release work. Do not sequence this into phase one above, and do not
start it before phase one ends at publication and a break is taken.

A related but separate project: making an entire AppSheet app visible to AI,
including the backing Google Sheets and the computation done in them. The existing
CSV export layer already does this for the app definition; the sheet side, formulas
included, is the half AI still cannot see.

`STATUS.md`'s "Next steps" section describes a narrower version of this as
extending the visibility layer to the backing Google Sheet via an Apps Script dump
of formulas and displayed values. That framing is narrower than intended here: the
Apps Script dump is one possible means, not the goal itself. The goal is the whole
sheet side made visible; how that gets built is still open.

The non-interactive query mode with JSON output, also named in `STATUS.md`'s "Next
steps", is not part of this project and stays where that file puts it: only if a
demonstrated need appears.
