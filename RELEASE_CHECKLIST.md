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

**Closed 2026-08-31 — by documentation research, not app testing.** The five items
immediately below were resolved from Google's official documentation (four items)
and one reasoned inference from Kirk (the map item), not by running the app tests
this section originally called for. See `APPSHEET_BEHAVIOR.md`'s "Established
behavior" section for each item's specific source and the strength of that source.
The items are left below, unmodified and checked off rather than deleted, so the
record of what was originally asked survives. This closure is what unblocked
section D, and it still stands — the item opened below is a separate, later
addition and does not reopen it.

- [x] **Does Prominent (`Display_Prominently`) display on a form view?**
      92 of Leon's 319 views are forms — the single largest block of the
      undecided bucket.
      *Done when:* the answer is recorded under "Established behavior" in
      `APPSHEET_BEHAVIOR.md`, with the date and how it was tested.

- [x] **Does Prominent display on a card view?** (17 views)
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`.

- [x] **Does Prominent display on a map view?** (7 views)
      Consequential: the suite currently emits edges to Map views for
      "Go to ObservationActivity", and if the answer is no, those edges are false.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`, and the "map cell is
      currently consequential" note in that file is resolved either way.

- [x] **Is Gallery treated like Deck?**
      `navigation_edge_generator.py` treats gallery as unconditionally permissive
      while two other files group it with deck. No rationale exists in the code.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`.

- [x] **Does Prominent display on a deck view, tested without the manual-list confound?**
      The 2026-08-30 observation cited for this rule does not isolate it: the deck used
      was in Manual mode with the action absent from its action list, so the manual-list
      rule explains the non-display by itself. Test on an Automatic-mode deck, or on a
      Manual deck whose list includes the action.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md` under "Established behavior".
      **Update, 2026-09-02:** the isolating test this item called for — a Manual deck
      whose action list includes the action — was actually run, and gave the OPPOSITE
      answer to what the 2026-08-31 documentation closure below assumed. Three
      `Display_Prominently` actions on Kankaku's `W to D` deck are genuinely on that
      deck's own `ActionBarEntries`, and two were confirmed rendering as row buttons
      in the app editor's preview — see `APPSHEET_BEHAVIOR.md`'s "Established
      behavior" entry for Prominent-on-Deck. The documentation-only closure was not
      wrong to unblock section D (Automatic mode and Google's Position page remain
      untested and unchanged), but its assumption about this specific rule did not
      survive contact with an app test. No longer "blocks section D step 5" — step 5
      was implemented on the old assumption, disproved by this same 2026-09-02 test,
      and reverted without being committed (`CONSOLIDATION_PLAN.md` section 5).

Optional, only if convenient: confirm the manual-action-list exclusion on a
non-deck view type, which would close the open question already recorded under
"Manual action lists" in `APPSHEET_BEHAVIOR.md`.

**Opened 2026-09-01 — a new item, added after the closure above and not part of
it.** The 2026-08-31 closure that unblocked section D still stands; this item does
not reopen it (see the item's own note on why it does not block section D either).

- [x] **Does a case-mismatched `LINKTOROW` view name resolve at runtime?**
      **ANSWERED 2026-09-05 — YES, by direct observation in the running app.**
      `Go to card stats` fired on a qualifying card and rendered the `Card stats`
      view correctly (heading "Card statistics for 数珠", Card made date, Status:
      Scheduled), despite its expression naming `"Card Stats"` with a capital S and
      no view of that name existing. **AppSheet's `LINKTOROW` view-name argument is
      case-insensitive at runtime.** `CONSOLIDATION_PLAN.md` section 4's
      case-insensitive-by-default decision therefore no longer carries a known cost
      — the one accepted cost was exactly this shape, and it is not a cost. Neither
      Kankaku's `Card stats` nor Farmy's `Water Tanks` is affected by the failure
      case this item described.
      **Incidental finding, recorded because it affects debugging:** the AppSheet
      editor's preview echoes the view name *as written in the expression*, not the
      view's actual stored name — the preview footer read
      `View: Card Stats | Table: Card stats`. A case error propagates into the debug
      display rather than being corrected there, so it cannot be spotted by reading
      that line.
      Recorded in `APPSHEET_BEHAVIOR.md`'s case-sensitivity section, 2026-09-05.
      The original item text follows, left unmodified as the record of what was asked.
      Kankaku's "Go to card stats" (source table `Kankaku`, per
      `action_targets.csv`) navigates via `=LINKTOROW([_THISROW], “Card Stats”)`
      — the curly quotes are AppSheet's own editor's, not a transcription choice
      here, and are exactly why this call was unparseable until `1c22881`. The
      app's actual view is `Card stats` (lowercase s). Tap "Go to card stats" in
      the running Kankaku app and see whether it navigates to `Card stats`.
      If it navigates: the open question is settled empirically for the first
      time, and `CONSOLIDATION_PLAN.md` section 4's case-insensitive-by-default
      decision stops carrying a known cost — that decision's one accepted cost
      is exactly this shape.
      If it does nothing: this suite has been clearing views that are genuinely
      unreachable, and both Kankaku's `Card stats` and Farmy's `Water Tanks`
      (STATUS.md's `f4d931a` entry) are affected.
      *Does NOT block section D*, despite this section's own header: section D's
      steps 1 and 3 predict a zero diff and touch no name-matching logic, and
      section 4's case-insensitive-by-default decision is already made, its one
      cost already accepted — this test only refines what is known about that
      already-accepted cost, it does not gate whether the decision can be made.
      *Done when:* recorded in `APPSHEET_BEHAVIOR.md`'s "Case sensitivity"
      section, against the existing "Untested... whether a view name inside
      `LINKTOVIEW`/`LINKTOROW`/`LINKTOFORM` resolves case-insensitively" bullet,
      with the date and how it was tested.

**Opened 2026-09-05 — the last two undetermined cells, closed by testing rather than by choosing a default.**

- [ ] **Does Prominent (`Display_Prominently`) display on a dashboard view? On a calendar view?**
      These are the only two view types `APPSHEET_BEHAVIOR.md`'s Unknowns section still lists as unestablished, and between them they cover 4 of Farmy's 319 views. Decided 2026-09-05: with a count that small, two app tests of a few minutes each are cheaper than any argument about which default to accept, and after them no default is needed. Test bed: Kankaku has a dashboard view; the frozen copy of Farmy has the calendar view (the same frozen copy already used for the 2026-08-31 `Go to web` test, so putting a test action on it is established practice). For each: put a `Display_Prominently` action on the view, look, record.
      *Done when:* both answers are recorded under "Established behavior" in `APPSHEET_BEHAVIOR.md` with the date and how each was tested, the Unknowns section no longer lists either type, and `CONSOLIDATION_PLAN.md` section 2's two `undetermined` rows carry the observed value. If either answer is F, the view type joins the section B form/map fall-through item; if T, nothing in the code changes.

---

## B. Code fixes — specified, no decisions needed

Each is a Claude Code task with a predicted diff, verified by full re-parse and
comparison against the current reference output.

- [ ] **Re-cut both reference parses at current HEAD — before any other section B item is started.**
      Both saved references predate `a15021b` (`STATUS.md`, "Both saved reference parses are stale"), so every diff against them attributes pre-existing drift to the change under test. Decided 2026-09-05: this is the first execution item, done on its own in a session that gives it full attention, not as a closing task after a fix.
      *Done when:* fresh parses of both apps exist from the code at the current HEAD; for each parse directory the earliest file mtime inside it is later than the mtime of every `.py` file in the repository (a directory's own timestamp does not establish this — see the caution paragraph in section D); the two new directory paths replace the "Current references, as of `a15021b`" paths in section D's caution paragraph; and `STATUS.md`'s "Both saved reference parses are stale" entry records the new paths and moves to "Recently fixed".

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
      **Scope corrected 2026-09-05, and no longer dependent on anything:** section A and `CONSOLIDATION_PLAN.md` section 2 ("The former 'other' bucket, decomposed") have since settled this. The fall-through is wrong for TWO view types, not one: `form` (92 Farmy views, F, documented) and `map` (7 views, F, established 2026-09-05). Fix both. NEG (`is_visible_in_view_neg`) is the only implementation wrong here — AOD and ADA already return F by fall-through. `card`, `dashboard` and `calendar` are NOT part of this fix; they are handled by the section D bucket item below. Note `is_action_visible_in_view` no longer exists (deleted in `3b06a08`); the code to change is `is_visible_in_view_neg` in `action_visibility.py`.
      *Predicted direction:* edges REMOVED from `navigation_edges.csv` (source views of type form or map), never added; orphan counts flat or rising, never falling. Form's `Form Saved` event route is untouched because `process_event_actions` never calls the visibility function (`CONSOLIDATION_PLAN.md` section 2's note). Every removed edge must trace to a form- or map-type source view; every newly flagged orphan must trace to a removed edge. Stop and re-examine if any edge is added or any orphan count falls.
      *Sequenced:* after the reference re-cut (top of this section), and may run before or after the `view_orphan_detector.py` CONTEXT() fix below; both are restrictive in direction, so run them as separate commits with a separate re-parse each, never together.

- [x] **`action_dependency_analyzer.py`'s table-view rule** (if the current run
      confirms it is wrong).
      Its table branch has no `Display_Overlay` case and falls through to
      `False` — the same wrong answer as the edge generator's explicit
      rejection, reached by omission. Deliberately left out of the current commit
      so the two output-affecting edits could be verified alone.
      *Done when:* fixed, or recorded in `STATUS.md` as deliberately left alone
      with the reason.
      *Confirmed:* fixed in `bbe981b`, verified by direct pair-by-pair
      measurement against both reference parses (ADA feeds no CSV, so a CSV diff
      cannot verify it). Farmy: 7,440 pairs flipped, all False→True. Kankaku: 120
      pairs flipped, all False→True. Zero pairs flipped the other direction, and
      every flipped pair had `view_type == 'table'` and `action_prominence ==
      'Display_Overlay'`. `STATUS.md` defect entry moved to "Recently fixed" with
      this commit hash.

- [ ] **Audit the six never-examined modules named in `STATUS.md`.**
      `view_orphan_detector.py`, `view_dependency_analyzer.py`,
      `slice_orphan_detector.py`, `format_rules_parser.py`,
      `format_rule_orphan_detector.py`, `column_dependency_analyzer.py`. The
      seventh, `action_dependency_analyzer.py`, is already known to carry a live
      bug found the moment anyone looked — that is the reason to look at the
      others. Read-only: report what each module assumes, not a fix.
      **Search the 2025 development archive first.** Kirk holds
      dated, descriptively-named `.docx` session records from the suite's
      original July–August 2025 build, at `/Users/kirkmasden/Documents/Research
      projects/201228 My project/250608 2132 Orphan columns/` — **163**, not
      the "roughly 211" this item originally estimated; corrected 2026-09-04
      after an actual count (`find . -name "*.docx" | wc -l`, run from that
      folder). The 211 figure appears to have counted every item in that
      folder generally — including parse directories and HTML exports, not
      `.docx` files specifically — so nothing found since is missing; the
      original estimate was simply counting the wrong thing. That work
      predates this project's use of Claude Code and its current documentation
      practice, so its reasoning was never carried into code comments or into
      any current document — this archive is the only likely record of WHY a
      2025 design choice was made, and these six modules date from exactly that
      period. It is referenced by no other current project document. A
      2026-08-31 search of it already produced two specific hypotheses, both
      about modules on this list, recorded here as hypotheses from an
      undocumented archive rather than as findings:
      - `view_orphan_detector.py` may not parse `CONTEXT("View")` conditions at
        all, unlike sibling files that do. Named as a "should do this" next
        step in two separate 2025 documents and never shown as done.
        **CONFIRMED, 2026-09-02** — `view_orphan_detector.py` audited (report,
        kept outside this repository as a private working note:
        `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`;
        findings recorded in `STATUS.md`). This standing hypothesis was right:
        the module parses no `CONTEXT()` condition of any kind — confirmed by
        grep, zero hits for `context` anywhere in the file. One of six audited,
        five remain.
      - `view_dependency_analyzer.py`'s exact/table-aware matching fix, applied
        in 2025 to format rules, slices and actions, was explicitly planned for
        views and explicitly not completed.
        **MISATTRIBUTED, corrected 2026-09-04** — `view_dependency_analyzer.py`
        audited (report, kept outside this repository as a private working
        note:
        `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260903_view_dependency_analyzer_code_audit.md`,
        with supporting archive detail in the companion
        `260903_view_dependency_analyzer_design_notes.md`; findings recorded
        in `STATUS.md`). This hypothesis does not describe
        `view_dependency_analyzer.py` — it performs no name-to-candidate
        matching of any kind (confirmed by grep: zero hits for "exact" in the
        file, and the only "table" references are display-only, never used
        to disambiguate a match). The 2025 work it describes belongs to a
        different module and a different method: `column_dependency_analyzer.py`'s
        `analyze_view_dependencies()`, which asks which views reference a
        given *column* — the reverse question from what
        `view_dependency_analyzer.py` answers ("what paths reach this
        view"). That work was called "planned but not completed" in one 2025
        document and "Fixed" in a second document written roughly two hours
        later the same day; checked against the current code, it is fixed,
        and has been since 2025. The module-name / method-name resemblance
        (`view_dependency_analyzer.py` vs. `analyze_view_dependencies`) is
        the likely source of the original conflation. Three of six audited, three remain.
      - `column_dependency_analyzer.py`'s column-to-column matching
        (`categorize_references`) was never brought into the 2025 exact/table-aware
        fix — neither 2025 document mentions it, `analyze_column_dependencies`, or
        column-to-column matching at all.
        **CONFIRMED AS A SEPARATE FACT, 2026-09-04** — the module's four
        component-level methods (views, slices, format rules, actions) do have
        exact, table-aware matching, confirmed by direct read; the column-to-column
        path is a two-stage exception, and only its first stage (the gate) is exact
        — that gate also lacks the table-scoping the other four methods use.
        `categorize_references` itself is unanchored substring matching throughout:
        the pre-2025 idiom the 2025 fix set out to remove, but never reached — not a
        regression from a later fix. **Do not file this under the MISATTRIBUTED
        entry above** — that entry closes the section B hypothesis; this is a
        separate, newly surfaced fact its closure would otherwise bury. Also worth
        flagging as inaccurate: the 15:59 documentation's column-to-column field
        list, which claims `show_if`, `valid_if`, `required_if`, and `editable_if`
        references are tracked — those fields are empty in every row of every parse
        (`STATUS.md`), so the claim has been untrue for as long as the current
        parser has emitted them. (code audit, `260904_column_dependency_analyzer_code_audit.md`)
      *Done when:* the audit has been run and its findings are recorded in
      `STATUS.md`, whether or not anything needs fixing.

- [x] **`action_target_parser.py` inverts any `NOT(CONTEXT(...))` condition.**
      No handling exists anywhere for a `NOT(...)` wrapper around a `CONTEXT()`
      comparison — confirmed by grep, zero matches for `NOT(`/`not(` in the
      context-condition extraction. The regex matches the inner comparison
      regardless of the wrapper, so `NOT(CONTEXT("ViewType") = "Detail")` is
      recorded as `must_be_viewtype='Detail'`, the exact opposite of what it
      says. `check_context_conditions` then correctly enforces the wrong
      requirement — the error is RESTRICTIVE, suppressing edges and making
      reachable views look orphaned, which is invisible in any diff because it
      is stable across runs. Farmy has 7 confirmed-inverted rows (`ViewType`
      shape) and 10 more (`View`-name shape) whose inversion is not yet
      established; Kankaku has not been checked at all. Found while accounting
      for why `CONSOLIDATION_PLAN.md` step 6's Farmy edge count came in below
      its predicted floor — `Add - Beds_Form` was the one case in that
      accounting with no other explanation. See `STATUS.md`'s matching entry.
      Done `a15021b`. Scope, corrected after a scan-methodology bug (space-only
      whitespace stripping missed newline-separated `NOT(\nCONTEXT` instances):
      actual count was 21 Farmy rows / 19 distinct `(action, table)` pairs, not
      17/17. All 10 `View`-shaped rows confirmed to invert the same way as the
      `ViewType`-shaped ones; Kankaku confirmed too (7 rows / 2 actions). See
      `STATUS.md`'s `a15021b` entry for the fix and full verification.
      **The done-when below is corrected, not silently replaced — say why:**
      "edges added, never removed" cannot hold for an inversion-class fix,
      because inverting a wrong condition both unblocks edges the wrong
      condition had suppressed AND revokes edges the wrong condition had
      wrongly permitted, whenever the inverted (wrong) requirement happened to
      be satisfied by some source view. Both happened here: Farmy
      `navigation_edges.csv` 1868 → 1971 (111 added, 8 removed), Kankaku 597 →
      585 (6 added, 18 removed). The stop condition as originally written
      would have blocked a correct fix from ever being committed.
      *Done when, as originally written (superseded by the corrected version
      below):* the fix handles a `NOT(...)` wrapper around a `CONTEXT()`
      comparison correctly (inverting `must_be_viewtype`/`must_not_be_viewtype`
      or `must_be_in_views`/`must_not_be_in_views` as appropriate); whether the
      10 `CONTEXT("View")`-shaped `NOT(...)` rows invert the same way is
      established rather than assumed, not left as an open question; and
      Kankaku is checked too, not just Farmy. *Predicted direction:* edges
      ADDED, never removed — the fix only corrects an over-restrictive
      condition into the correct, less-restrictive one. Orphan counts flat or
      falling, never rising. Stop and re-examine if any edge is removed or any
      orphan count rises.
      *Corrected done-when, met:* the fix handles a `NOT(...)` wrapper around a
      `CONTEXT()` comparison correctly, established for all 10 `View`-shaped
      rows and for Kankaku; **every removed edge traces to a source view that
      the corrected condition excludes**, verified individually for all 8
      Farmy and 18 Kankaku removals (`STATUS.md`'s `a15021b` entry); orphan
      counts flat or falling, never rising — byte-identical
      `potential_action_orphans.csv` and `potential_view_orphans.csv` in both
      apps, Farmy `unused_system_views.csv` fell by 1 (`ActivityGermination_Form`
      cleared).
      **General note for the next inversion-class fix:** a done-when of "edges
      added, never removed" is the wrong shape for correcting an inverted
      boolean condition — such a fix is expected to touch both directions. The
      right done-when checks that every removal is *explained* by the
      correction (traces to a source the fixed condition genuinely excludes),
      not that no removal occurs at all.

- [x] **How `view_orphan_detector.py` determines reachability for category-`ref`
      views.**
      Evidence, from the 2026-09-02 `STATUS.md` entry: `Card stats` was flagged
      a view orphan in the `20260831_182306` Kankaku parse and not in either
      2026-09-02 parse of the same frozen export, while its single incoming
      edge (`Kankaku_Inline`, `row selected`) was unchanged and `Kankaku_Inline`
      itself had zero incoming edges in both. So the clearance came from
      something other than the navigation edge graph. Category-`ref` views are
      embedded via `ref_parent` rather than navigated to, so reachability for
      them must run through a separate path.
      Matters enough for phase one rather than the roadmap: it governs every
      category-`ref` view in both apps, not only the one that surfaced it, and
      a reachability path nobody has read is a path whose correctness is
      unknown in both directions — it could be suppressing real orphans or
      clearing false ones.
      Done, code audit (private working note, kept outside this repository):
      `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`.
      **Both halves of the done-when below are met, and the first line's own
      premise turned out to be wrong:** there is no separate `ref_parent` or
      embedding-based reachability path — `category == 'ref'` is read in
      exactly two places in the module, both purely cosmetic (choosing the
      `orphan_reason`/`unused_reason` string after the ordinary BFS result has
      already decided reachability). Every view, `ref`-category or not, is
      reachable only through the same navigation-edge graph. And the specific
      change is named: `1c22881`. `Card stats` reaches root `D to W` via
      `D to W_Detail → Definition → Card Stats` — a path that has nothing to
      do with `Kankaku_Inline` — and the one edge in that chain that differs
      between the two parses, `Definition → Card Stats` via `Go to card
      stats`, is one of the three actions `1c22881`'s own `STATUS.md` entry
      already names as recovered by that commit's curly-quote fix. Established
      by running the module's own `find_all_reachable_views()` and
      `print_reach_path()` against both reference parses, not by reading CSVs.
      See `STATUS.md`'s corrected `Card stats` entry for the full account,
      including the earlier wrong conclusion kept on record rather than
      erased.
      *Done when:* the path by which a category-`ref` view is judged reachable
      is identified in the code and described in `STATUS.md`; and the specific
      change between `ebc41d6` and `a15021b` that altered `Card stats`'s
      result is named, or it is stated that no such change was found and the
      difference remains unexplained.

- [ ] **Decide: fix `view_orphan_detector.py`'s missing `CONTEXT()` handling, or
      document it as an accepted limitation.**
      Confirmed by the 2026-09-02 code audit (private working note, kept
      outside this repository:
      `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`;
      `STATUS.md`'s matching entry): the module's BFS traversal performs no
      `CONTEXT()` evaluation at all, so an edge whose context condition can
      never actually be satisfied still counts as a real path — systematically
      more permissive than sibling modules that do check, under-reporting
      orphans in both apps by an unmeasured amount.
      **Not resolved here — this is Kirk's decision, not made by this entry.**
      Two live options, recorded so the choice isn't lost: (a) port
      `CONTEXT()` validation into this module, matching its stricter siblings;
      (b) leave it as-is and document the gap as an accepted limitation rather
      than a defect to fix.
      *Done when:* Kirk has chosen a direction, and either the fix is
      implemented and verified by full re-parse of both apps, or the decision
      to leave it and why is recorded in `STATUS.md`.

      *Suggested for a stronger model (Fable-class):* this is a judgment call, not
      an evidence question — no re-parse settles it. It fails quietly if decided
      wrongly (accepting the limitation means it stops being examined), and it now
      touches three audited modules rather than one, so the decision generalises
      further than its wording suggests.

      **DECIDED 2026-09-05 (Kirk, in a Fable planning session): option (a), FIX.** Reasoning: `CONTEXT()` conditions are central to how AppSheet apps actually work, so a reachability traversal that ignores them is not an acceptable limitation for a tool whose stated purpose is to expose the app faithfully to AI. The decision covers both modules that share the gap — `view_orphan_detector.py` and `view_dependency_analyzer.py` (`STATUS.md`, "a second instance, not a new gap") — and the fix should be one shared mechanism, not two copies, consistent with the consolidation's lesson about the same rule written three times.
      *Scope:* port `CONTEXT("View")` / `CONTEXT("ViewType")` evaluation into the BFS so that an edge is traversable from a given source view only if its context condition can be satisfied there, matching the semantics `navigation_edge_generator.py` already applies through `check_context_conditions`. In the same work, settle `STATUS.md`'s open question about the `NOT(IN(CONTEXT("View"), LIST(...)))` shape — establish by field-by-field check, not by diff, whether `a15021b`'s inversion handles it; it is the same mechanism and the same evidence method.
      *Predicted direction:* RESTRICTIVE — clearances removed, `potential_view_orphans.csv` and `unused_system_views.csv` flat or rising, never falling; downstream orphan files may rise through the documented coupling. Every newly flagged view must be individually explained by naming the edge whose context condition the traversal now rejects, per the "General note for the next inversion-class fix" in the `NOT(CONTEXT(...))` item above — explained removals, not zero removals, is the test. Stop and re-examine if any view is newly CLEARED.
      *Done when:* both modules evaluate context conditions through one shared function; verified by full re-parse of both apps against the RE-CUT references (top of this section); every newly flagged view accounted for individually; the `NOT(IN(...))` shape settled and recorded; and `STATUS.md`'s two matching Known-defects entries move to "Recently fixed" with the commit hash.
      *Sequenced:* after the reference re-cut. Not before.

- [ ] **Unsatisfiable column-`Show_If` / attached-action-condition pairs — the narrow mechanical half of the `Show_If` gap.**
      Decided 2026-09-05 (Kirk, Fable planning session), resolving the fork `STATUS.md` left open under "Column-level `Show_If` is never consulted": the two halves are different sizes and get different treatment. (1) General evaluation of column `Show_If` in the reachability path is an ACCEPTED LIMITATION — the 2026-09-03 census found that all but 2 of 148 Kankaku pairs are either data-dependent or test unrelated variables, which no static analysis settles; it stays documented in `STATUS.md` and CLAUDE.md as it is now. (2) The narrow half IS scoped work: detect a column `Show_If` and the condition of an action attached to that column that test the SAME variable in OPPOSITE senses (the `Schedule position label` / `Group to DW card statistics` instance), so the pair is unsatisfiable by construction.
      *Output:* a NEW file (suggested name `potential_unsatisfiable_conditions.csv`, one row per column/action pair, carrying both expressions verbatim and the variable they contradict on). NOT a change to any existing orphan file — this is a different kind of finding ("this can never display") from reachability, and keeping it in its own file means every existing output stays byte-identical, which is the verification.
      *Ambiguity assessment, required before this goes on the list per the "Deliberately not on this list" section's own caution:* the check fires only on a literal contradiction between two expressions over the same variable (`X="On"` versus `X<>"On"`, or `X=a` versus `X=b` with a≠b); anything requiring evaluation — arithmetic, data lookup, `AND`/`OR` combinations whose satisfiability depends on other terms — is out of scope and must not produce a row. If, when specified, the literal-contradiction detector cannot be kept that narrow, this item moves to post-publication without loss.
      *Done when:* the new CSV is produced for both apps; Kankaku's output contains exactly the two known rows (`Group to DW card statistics`, `Group to WD card statistics` against `Schedule position label`) and Farmy's rows are each hand-checked; every existing output file byte-identical in both apps (logical-key comparison where `available_actions` noise applies); CLAUDE.md's CSV reference gains an entry for the new file; recorded in `STATUS.md`.
      *Sequenced:* last in section B. Phase one only because it is narrow; it is the first item to drop to post-publication if the publication date needs protecting.

---

## C. A second reference parse — Kirk's own current app

Every verification in this project compares a re-parse against one saved reference
output: Leon's app. That is a single-app test bed, and this week showed exactly what
it misses — every defect found came from rules Kirk's app never exercised. Kirk's
app also contains prominence values and view types Leon's does not, so a second
reference covers different ground rather than merely more of the same.

- [x] **Regression guard: save a reference parse, diffed alongside Leon's on
      every subsequent change.** The consolidation's steps 1 and 3 (section D
      below) claim a zero diff across every output file, and that claim is far
      stronger verified against two apps than one.
      *Done:* `20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881`,
      a copy of `20260901_085853_260831_1809_Kankaku_V18_baseline_parse`
      (original left in place), at
      `/Users/kirkmasden/Documents/Research projects/201228 My project/250608 2132 Orphan columns/250907 1229 AppSheetAnalysis/20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881`.
      Parsed by the code at `1c22881` from the 2026-08-31 export. This is a
      regression guard — the fixed point every subsequent change is diffed
      against, alongside Farmy — and **not** a current-app snapshot: it is not
      the discovery-half output below, and it does not reflect any export more
      recent than 2026-08-31.
      **Both references are stale as of 2026-09-05** — they predate `a15021b`'s
      `NOT(CONTEXT(...))` fix, so a raw diff against either attributes
      pre-existing drift to whatever change is under test. The item stays
      checked: the references were captured, and captured correctly. What was
      not anticipated is that a reference parse decays as the parser changes.
      Until they are re-cut, any verification diff must run a control parse at
      pre-fix HEAD and compare control against post-change. See `STATUS.md`'s
      Known-defects entry for the measurement.
- [ ] **Source of new findings: run a fresh export of Kirk's current app, look
      at what gets flagged, and check the surprising results in the running
      app.** That is how this week's discoveries happened. Also covers
      *because the app has changed:* the suite was shaped around this app once;
      some rules encoded then may no longer match what Kirk builds now. Needs a
      fresh export — the regression-guard item above reuses the existing
      2026-08-31 export and does not satisfy this.

---

## D. Consolidation — `CONSOLIDATION_PLAN.md`

Do not start before section A. Steps 4 and 5 are only judgment calls because the
answers are unknown; once A is done they become mechanical.

- [x] **Step 1: extract `action_visibility.py`, switch `action_dependency_analyzer.py`
      (ADA) only.** Done `84a651d`. `action_visibility.py` holds a
      behavior-preserving translation of all three implementations (NEG, AOD,
      ADA) as separate call-compatible functions, every disagreement — including
      the `Do_Not_Display` case bug below — preserved as-is; only ADA's caller
      was switched over. **Verified by a 419,750-pair differential comparison of
      ADA's own answer, old implementation vs. new** (Farmy 970 actions × 319
      views = 309,430 pairs; Kankaku 560 actions × 197 views = 110,320 pairs; 0
      disagreements in either). This, not the CSV diff below, is what verifies
      the step: nothing programmatic consumes ADA's answer (`CONSOLIDATION_PLAN.md`
      section 1), so a full re-parse would show zero diff even if the
      extraction were wrong. A full re-parse of both apps against their saved
      references was also run and came back byte-identical on every output
      file, as predicted — recorded because the plan calls for it, not as
      evidence of correctness. **Only ADA's path through `action_visibility.py`
      is exercised as of this commit** — see `STATUS.md`'s matching entry for
      what that means for steps 2 and 3.
      *Done when:* met — `action_visibility.py` exists, `action_dependency_analyzer.py`
      calls it, and the differential comparison of ADA's own answer, old vs.
      new, shows zero disagreements.

- [x] **Step 2: fix the case bug, switch `actions_orphan_detector.py` (AOD).**
      Done `6115f30`. Fixed the `'Do_Not_Display'.replace('_',' ')` mismatch in
      the AOD strategy only — `is_visible_in_view_ada` still carries the
      identical bug, deliberately left; see `STATUS.md`'s Known-defects entry
      and step 2b below. **Verified by a 1,530-action differential comparison of
      AOD's own answer, old implementation vs. new** (Farmy 970 actions,
      Kankaku 560 actions): 64 True→False verdict flips, 0 False→True — no
      stop condition hit. **CSV diff, accounted for row by row:**
      `potential_action_orphans.csv` gained 2 rows in Farmy (`Add Go to
      NurseryDetails_Form`, `NurseryDetails_Detail - UniqueRows`, both table
      `NurseryDetails`), 0 removed; Kankaku gained nothing (0 → 0 change,
      its one True→False flip was already excluded by another gate). Every
      other output file byte-identical in both apps. See `STATUS.md`'s
      matching entry for the full trace of all 64 flips, not just the 2 that
      surfaced in a CSV.
      *Done when:* met — see above.

- [x] **Step 2b (not in the original plan; added 2026-09-01): fix the same case
      bug in `is_visible_in_view_ada`.** Deliberately deferred by step 2 rather
      than fixed alongside AOD — ADA has been live on the shared module since
      step 1 (`84a651d`), so fixing its copy changes what the interactive
      dependency browser reports, and no CSV diff can verify that change.
      Done `742b759`. Same fix as step 2 (`6115f30`) applied to
      `is_visible_in_view_ada`: the `.replace('_', ' ')` transform on
      `action_prominence` removed, and all five comparison literals inside
      the function changed from spaced to underscored form (`'Display
      Prominently'` → `'Display_Prominently'`, `'Display Overlay'` →
      `'Display_Overlay'`, `'Display Inline'` → `'Display_Inline'` (two
      occurrences), `'Do not display'` → `'Do_Not_Display'`).
      **Pre-fix scan:** every `(action, view)` pair combining a
      `Do_Not_Display` action with a deck or gallery view where the action
      is in the view's `available_actions` — 232 pairs in Farmy, 131 in
      Kankaku (363 total) — returned `True` (wrong; the bug's spaced-vs-
      underscored mismatch meant the `Do_Not_Display` exclusion on
      deck/gallery action bars never fired). All 363 span only deck views
      (no gallery views hit the pre-gate in either app) with
      `show_action_bar=True`; Farmy touches 73 actions across 21 tables and
      17 views, Kankaku 117 actions across 7 tables and 4 views.
      **Post-fix verification:** all 363 pairs now return `False`. A full
      cross-product of every `(action, view)` pair in both apps (Farmy
      309,430 pairs, Kankaku 110,320) confirms zero pairs in the
      `Do_Not_Display` × deck/gallery category return `True` anywhere —
      Farmy 10,350 affected-category pairs / 299,080 unaffected, Kankaku
      1,422 affected-category pairs / 108,898 unaffected, all unaffected
      pairs untouched by the fix (only the `Do_Not_Display`/deck-gallery
      category's logic changed).
      **Verification method note:** verified by direct function calls
      against parsed CSVs rather than via the interactive dependency
      browser — equivalent evidence, since `is_visible_in_view_ada` is a
      plain function and the browser is its only consumer. The done-when
      condition originally called for a before/after comparison of the
      browser's actual reported text; this comparison was made against the
      function's return value directly, which is exactly what the browser
      displays.
      *Done when:* met — see above.

- [x] **Step 3: switch `navigation_edge_generator.py` (NEG).**
      Done `8d6cb94`. Both call sites (`process_regular_action` and `process_view`'s
      group-action branch) now delegate to the shared `is_visible_in_view_neg`,
      passing `self.stats` through so `edges_blocked_by_visibility` keeps
      incrementing. The four old methods (`is_action_visible_in_view` and its
      three per-view-type helpers) are retained as dead code so the
      differential script could call old and new in the same process; removal
      is tracked as step 3b below. **Increment-count figure corrected:** step
      3's grep (block A0) found eight `+= 1` sites, not nine — corrected here,
      in `STATUS.md`'s `84a651d` caution paragraph, and in
      `CONSOLIDATION_PLAN.md` section 1.
      **Verified by a 204,827-pair differential comparison of NEG's own
      answer, old implementation vs. new** (Farmy 463 navigation targets × 319 views =
      147,697 pairs; Kankaku 290 navigation targets × 197 views = 57,130 pairs), run via
      `step3_neg_diff.py` (throwaway, not committed): **0 disagreements in
      either app.**
      **CSV byte-identity:** `navigation_edges.csv` byte-identical (`cmp`
      pass) for both apps, pre-switch vs. post-switch, run against fresh
      copies of the saved references. Data-row counts (Python's `csv` module,
      not `wc -l`): Farmy 1850 → 1850, Kankaku 592 → 592, both unchanged.
      **Counter match:** `edges_blocked_by_visibility` — Farmy 4020 (pre) →
      4020 (post); Kankaku 1363 (pre) → 1363 (post). Both identical,
      confirming the `stats=self.stats` wiring is correct and the counter did
      not silently stop.
      Downstream orphan files (`potential_view_orphans.csv`,
      `unused_system_views.csv`, `potential_action_orphans.csv`,
      `potential_format_rule_orphans.csv`,
      `potential_virtual_column_orphans.csv`) were not directly verified in
      this step. This step relies on the pipeline coupling documented in the
      `48eead1` "Recently fixed" entry in `STATUS.md`, under which those files
      are deterministic given `navigation_edges.csv`. If any downstream file
      had moved while `navigation_edges.csv` was byte-identical, that would be
      a finding about the coupling, not about step 3.
      *Done when:* met — see above.

- [x] **Step 3b: remove the dead methods from `navigation_edge_generator.py`.**
      Done `3b06a08`. Deleted `is_action_visible_in_view` and its three
      per-view-type helpers (`is_action_visible_in_detail_view`,
      `is_action_visible_in_deck_view`, `is_action_visible_in_table_view`),
      retained through step 3 only so the differential script could call old
      and new in one process. They served no further purpose.
      **Pre-deletion caller check:** block A's grep found zero hits outside
      the four methods themselves (the internal calls from
      `is_action_visible_in_view` to its three helpers were the only matches
      besides the dead-code comment) — confirming step 3 had already
      eliminated both external call sites.
      **Import smoke-test:** pass — `from navigation_edge_generator import
      NavigationEdgeGenerator` succeeds with no `NameError` or
      missing-attribute error after deletion.
      **CSV byte-identity:** `navigation_edges.csv` byte-identical (`cmp`
      pass) for both apps, pre-deletion vs. post-deletion, run against fresh
      copies of the saved references. Data-row counts (Python's `csv`
      module, not `wc -l`): Farmy 1850 → 1850, Kankaku 592 → 592, both
      unchanged.
      **Counter match:** `edges_blocked_by_visibility` — Farmy 4020 (pre) →
      4020 (post); Kankaku 1363 (pre) → 1363 (post). Both identical.
      Downstream orphan files (`potential_view_orphans.csv`,
      `unused_system_views.csv`, `potential_action_orphans.csv`,
      `potential_format_rule_orphans.csv`,
      `potential_virtual_column_orphans.csv`) were not directly verified in
      this step. This step relies on the pipeline coupling documented in the
      `48eead1` "Recently fixed" entry in `STATUS.md`, under which those
      files are deterministic given `navigation_edges.csv`. If any
      downstream file had moved while `navigation_edges.csv` was
      byte-identical, that would be a finding about the coupling, not about
      step 3b.
      *Done when:* met — see above.

- [ ] **Step 4: Gallery/Deck parity.** No longer blocked — section A closed
      2026-08-31 (by documentation research, not app testing; see section A's
      closure note above).

- [x] **Step 5: ~~Prominent-on-Deck exclusion, applied everywhere.~~ STRUCK 2026-09-02 — disproved and reverted, never committed; see the record below.**
      Note the direction: this can *increase* orphan counts, unlike every fix so
      far. An increase here is expected, not a regression.

      **DISPROVED, 2026-09-02 — struck, not deleted, so the record of what this
      step predicted survives.** This step was implemented, verified by full
      re-parse against both apps, and reverted the same day without being
      committed. `Display_Prominently` is NOT excluded from deck views — three
      such actions on Kankaku's `W to D` deck are genuinely on that deck's own
      `ActionBarEntries`, and two were confirmed rendering as row buttons in the
      app editor's preview. The "an increase here is expected, not a
      regression" note above must not be read on its own now: the increase this
      step actually produced (4 new `potential_view_orphans.csv` rows in
      Kankaku) was real, but the rule that predicted it is wrong — so the note
      explains why an increase would not have looked alarming, not standing
      guidance that this step should still run. See `APPSHEET_BEHAVIOR.md`'s
      "Established behavior" entry for Prominent-on-Deck and
      `CONSOLIDATION_PLAN.md` section 5's step 5 entry for the full record.

- [x] **Step 6: Deck/`Display_Overlay` parity, added to the plan 2026-09-01.**
      Done `96d8897`. Admitted Primary/`Display_Overlay` on deck views as a
      view-level floating button, ungated by `referenced_actions`,
      `show_action_bar`, or `action_display_mode`, via a shared
      `_overlay_admitted_on_deck` helper used by all three strategies — the
      deck-side counterpart of `e0530c8`'s table fix. Not blocked — Overlay-on-
      Deck was already settled by direct observation (`APPSHEET_BEHAVIOR.md`'s
      Established behavior section, Deck+Overlay entry), unlike Step 5's
      Prominent-on-Deck, which rested on documentation alone and has since been
      disproved and reverted (see above).
      **Verified by full re-parse of both apps:** 0 edges removed either app;
      Farmy +18 edges across 10 actions (11 `direct`, 7 `via_group` — the same
      `e0530c8` group-cascade pattern, a `Display_Overlay` group container
      becoming visible and its `Do_Not_Display` children producing edges
      through the group bypass); Kankaku +5, all from `Flag2 Settings`, one per
      deck, all targeting `Help_Detail E`. Zero orphan-count change in either
      app — every orphan output byte-identical.
      **Differential checks:** NEG 0 True→False / 871 False→True in Farmy and
      0/16 in Kankaku, with `edges_blocked_by_visibility` falling by exactly
      871 and 16; ADA 0/1713 and 0/60; AOD (existential) 0/0 in both apps —
      why no orphan cleared: every action that gained deck visibility already
      had another reachable path. Full detail in `STATUS.md`'s matching
      "Recently fixed" entry and `CONSOLIDATION_PLAN.md` section 5's step 6
      entry, including why the pre-implementation floor overstated Kankaku's
      real result by two orders of magnitude.
      *Done when:* met — see above.

- [ ] **The 120-view "other" bucket.** No longer blocked — section A closed
      2026-08-31 (by documentation research, not app testing; see section A's
      closure note above). This is the largest single gap in the suite and the
      one most likely to generate exactly the false positives Leon reported.
      *Asymmetry worth weighing when choosing the default:* a too-permissive rule
      emits edges that do not exist, so real orphans go unreported and nobody ever
      complains — the error is silent. A too-restrictive rule reports orphans that
      are not orphans, which is what Leon reported and how this whole round of
      fixes began. Only restrictive errors generate the feedback that corrects
      them. A permissive default buys quiet at the price of never learning it was
      wrong.

      *Suggested for a stronger model (Fable-class):* the asymmetry above is the
      whole difficulty — one error is silent, the other is loud, and choosing a
      default means choosing which failure to accept. Worth testing first whether
      the data-layer framing dissolves the question: if the honest output is
      "reached only by a Prominent action on a card view, undetermined," there may
      be no default to pick.

      **RESOLVED AS A DECISION, 2026-09-05 (Kirk, Fable planning session) — the bucket no longer exists as a single question, and no permissive-versus-restrictive default is chosen.** `CONSOLIDATION_PLAN.md` section 2 had already decomposed the 120 views by type; the pieces now go three ways:
      - **`form` (92) and `map` (7): settled F.** These are the section B "Map fall-through" item, which now covers both types — a specified code fix, not a decision.
      - **`dashboard` (3) and `calendar` (1): to be TESTED, not defaulted** — the new section A item above. Four views do not justify choosing which error to accept when one test each removes the choice.
      - **`card` (17): the one genuinely open piece, and it is not a default question either.** `APPSHEET_BEHAVIOR.md` (2026-09-05) established that card display is per-slot assignment in the Layout widget, which no prominence-keyed boolean can express. What decides its handling is one fact not yet checked: whether the export carries the Layout widget's per-slot action assignment. Recorded here as a READ-ONLY question for the execution session, with both branches written down so the answer needs no further decision: if the assignment IS in the export, parsing it is a bounded parser task of the same shape as the 2026-08-30 onClick/Layout-JSON fix; if it is NOT, card gets an entry in `APPSHEET_BEHAVIOR.md`'s scope-decisions section as an export gap and keeps its current verdicts. Either branch is POST-PUBLICATION unless the execution session finds it trivial — 17 card views do not hold up phase one.
      *On the Fable note above:* the data-layer framing (project record, Addendum 6) does bear on this, but not by dissolving it — `VisibilityResult(visible, reason)` is not built (`action_visibility.py` returns bare booleans), so the tool cannot yet report "undetermined" for anything, and building that plumbing touches output schemas the zero-diff method depends on. It stays post-publication, beside the faithfulness work Addendum 6 already assigns there. What actually dissolved the question was the evidence: five of the six cells were settled between 2026-08-31 and 2026-09-05, and the remaining two are one test each.
      *Done when:* the section B form/map item and the section A dashboard/calendar item are each done per their own conditions, and the card question above has been asked and its branch recorded in `STATUS.md`.

**Caution for whoever runs these:** the plan's predictions were originally computed
against `20260830_linktoform_verify/20260830_212632_AppsheetFarmyApp_for_Kirk_parse`,
which predates `e0530c8` and the 82 `navigation_edges.csv` rows it added, and the most
recent Leon-app parse on disk at the time this caution was written was
`20260831_primary_overlay_verify/20260831_081316_AppsheetFarmyApp_for_Kirk_parse`. Both
were stale as of 2026-09-02, and so, in turn, were the references that replaced them
(`20260902_131151_AppsheetFarmyApp_for_Kirk_parse`,
`20260901_085853_260831_1809_Kankaku_V18_regression_reference_1c22881`) once step 6's
`96d8897` and the `NOT(CONTEXT(...))` fix's `a15021b` landed. **Current references, as
of `a15021b`:** `20260902_180352_AppsheetFarmyApp_for_Kirk_parse` (Farmy) and
`20260902_180356_260831_1809_Kankaku_V18_baseline_parse` (Kankaku). Both were produced
by the code now committed as `a15021b` and are adopted at that hash without
regeneration — confirmed by comparing `action_target_parser.py`'s mtime (its last
edit) against both directories' earliest file mtimes, both later. **A directory's own
timestamp does not establish this by itself:** it names the run's START time, which
necessarily precedes the first file the run writes — check file mtimes inside the
directory against the code's own mtime, not the directory name, before adopting any
parse directory as a reference for a specific commit. Both parse directories sit
outside the repository, since `*_parse/` is gitignored. Re-parse against the current
code before trusting any predicted diff — this advice was reconfirmed three times now:
during step 6 (the pre-implementation floor for Kankaku, ~343 edges almost all from
`Session flag`, overstated the real result of 5 by nearly two orders of magnitude,
because it was not evaluated against `check_context_conditions` on a fresh parse —
`CONSOLIDATION_PLAN.md` section 5's step 6 entry has the full accounting), and again
during the `NOT(CONTEXT(...))` fix, whose own predicted done-when ("edges added, never
removed") had to be corrected against what a fresh re-parse actually showed (see this
section's own entry above).

Count CSV rows with a real CSV parser rather than `wc -l` or line-splitting: several
fields in these outputs contain embedded newlines, and naive counting gives wrong
answers. This was confirmed on 2026-08-31, when a `wc -l` count of
`navigation_edges.csv` disagreed with the true row count.

---

## E. Before contacting Leon

- [x] **Push.** Done 2026-09-03: 72 commits, `2f0cb81..28164fd`. Pushed without squashing — the recorded plan had been to squash `adfdaac`'s correction into `18e7462` so a public reader never saw the wrong LINKTOFORM count, and that was dropped deliberately: rewriting the base of a 72-commit branch would have invalidated every commit hash cited across `STATUS.md`, `CONSOLIDATION_PLAN.md` and this file, and `adfdaac` sits two commits after the error and names it in its own subject line. Keeping the correction visible in history also matches how these documents already treat superseded reasoning.

- [ ] **Report the broken view references in Leon's app — twelve names, not
      five.**
      The original five, already sent to Leon: `Seeds Form` (the real view is
      `Seeds_Form`), `ActivityForm - Transplant`, `ActivityForm - Germination`,
      `ActivityForm Observation`, and `NurseryForm2b`. Named by actions,
      absent from the app. Confirmed 2026-08-31 that a navigation action
      pointing at a nonexistent view does nothing at all when tapped — no
      error, no fallback — so these are invisible to users and findable only
      by static analysis. Worth saying so: it is the clearest demonstration of
      what the tool is for.
      Note sent with the first five: the first four are `LINKTOFORM`
      references in form actions, but `NurseryForm2b` is a `LINKTOROW`
      reference in a Sync action (`Sync | Order (Complete)`, table `Nursery`)
      — don't describe all five as form-view problems.
      **Seven more, found 2026-09-04, not yet sent:** `ActivityWater Form`,
      `Amendments ALL_Detail`, `MyPlantsReadOnly_Detail`, `New Selling Order
      Form Finish`, `Order Form Nursery Plants List`, `Orders Table`,
      `Seeds READONLY_Detail`. All twelve names — the original five and these
      seven — already appear in Farmy's `potential_phantom_view_references.csv`,
      every one of them via its `missing_view_names` field; no further suite
      work is needed to surface them, only the reporting step. Their shapes
      differ from each other and from the original five, worth keeping
      straight in any report to Leon: two (`ActivityWater Form`, `Order Form
      Nursery Plants List`) are plain `LINKTOVIEW` calls; one (`New Selling
      Order Form Finish`) is a `LINKTOROW` call, the same shape as
      `NurseryForm2b`; one (`Orders Table`) sits inside one branch of a
      30-plus-branch `SWITCH`; three (`Amendments ALL_Detail`,
      `MyPlantsReadOnly_Detail`, `Seeds READONLY_Detail`) aren't named
      directly at all — they're view names synthesized from a
      `#page=detail&table=...` deep-link URL, a structurally different kind
      of reference from every other name on this list. Full detail in the
      private working note:
      `/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260903_view_dependency_analyzer_code_audit.md`
      (2026-09-04 follow-up section — originally misdated 2026-09-05 in the
      audit document, corrected there).
      **Whether to report all twelve to Leon together, or the deep-link-derived
      three separately given their different shape, is Kirk's call — not made
      here.**
      **Before this report goes out, see `STATUS.md`'s "Two Farmy phantom names
      may be misattributed to source views whose own `action_targets.csv`
      resolution points elsewhere"** — two of these twelve,
      `MyPlantsReadOnly_Detail` and `Seeds READONLY_Detail`, may be an
      artifact of this suite's own edge generation rather than a genuine
      defect in Leon's app. Not settled; settle it before reporting these
      two specifically.

- [x] **A `CLAUDE.md` at the repository root**, per the July plan: CSV schemas,
      which analyzer answers which category of question, the instruction to call
      analyzer methods directly rather than driving the interactive menus, and
      the known blind spots. Ship an `AGENTS.md` with the same content for
      non-Anthropic tools. Required before publication, not optional: a
      published tool that other people's AI will use needs this to use the
      suite without reverse-engineering it.
      **Done `1b28db1`, 2026-09-03.**
      **On model choice:** this is the one remaining phase-one task that is
      synthesis rather than verification — it requires holding the whole suite
      in view at once (twenty-one modules, the CSV schemas they emit, which
      analyzer answers which class of question, and the documented blind
      spots) and has no verification loop to catch a shallow result. Kirk has
      credits for Claude Fable and this is the phase-one task where that
      capability fits. Practical note: hand the model `RELEASE_CHECKLIST.md`,
      `STATUS.md`, `CONSOLIDATION_PLAN.md`, `APPSHEET_BEHAVIOR.md`, and the two
      2026-09-02 audit reports — private working notes, kept outside this
      repository —
      (`~/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_path_analysis_notes.md`,
      `~/Documents/雑学/260505 0852 AppSheet orphan script possible issues/260902_view_orphan_detector_code_audit.md`) at session start
      rather than letting it discover them by reading the repo — discovery is
      where cost accumulates, and those documents already contain what it
      would reconstruct.

- [ ] **A README quick-start — and, decided 2026-09-05, NO separate user guide.**
      Decision (Kirk, Fable planning session): a prose guide for other AppSheet creators is not worth attempting. Under the design ruling that Claude Code (or another platform's equivalent) is the primary interface, a creator's interface IS a conversation with CC over a parse directory, and CLAUDE.md already holds what that conversation needs — purpose, limitations, usage rules, CSV and module reference. A human-voiced guide would duplicate it in a second voice and drift from it. What a stranger actually lacks is UPSTREAM of CLAUDE.md, and that is a page, not a guide.
      *Content of the quick-start, in this order:* (1) how to produce the inputs — the HTML documentation export, the `actions.txt` / `views1.txt` / `views2.txt` select-all-and-paste captures, and the optional hand-written `bot_actions.txt` — stating plainly WHICH editor (legacy) the capture steps assume, since that is the step that will date first; (2) how to run `master_parser_and_orphan_detector.py` and what the output directory contains, with the `EOFError`-on-no-stdin limitation noted; (3) how to open Claude Code on the output directory, and that CLAUDE.md / AGENTS.md will orient it; (4) the three example prompts from the project record's Addendum 6, verbatim, as the kind of question to ask; (5) one paragraph on what the suite does not see, pointing at CLAUDE.md's section rather than restating it.
      *Consequence for the survey specimens (actions, tables, format rules):* their reader is CC, via `APPSHEET_BEHAVIOR.md` and CLAUDE.md, not a human guide. They are worth running only where a specimen improves the faithfulness or completeness of what the parse exposes — which is where post-publication effort is directed anyway (Addendum 6) — and not as raw material for documentation that will not be written. Scope reduced, not cancelled.
      *Done when:* README.md exists at the repository root (extend the existing README if there is one, do not create a second), and the test is met: a reader holding README.md and CLAUDE.md, and no other knowledge of this project, could produce a parse and start a useful CC session. Kirk judges the test.

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
- **A check for expressions AppSheet accepts but that cannot do what the author
  intended** — malformed `CONTEXT()` arguments, dead-by-construction
  prominence/condition combinations, and the other instances
  `APPSHEET_BEHAVIOR.md`'s "AppSheet validates shape, not meaning" section
  records. An idea from this week's work, explicitly NOT phase one — recorded
  here as a candidate for after publication. Scoping constraint that makes it
  tractable: the target is not general expression validation, which would mean
  reimplementing AppSheet's own evaluator, but a specific list of
  closed-vocabulary and named-entity lookups against data the suite already
  parses. Caution: each candidate check needs its ambiguity assessed before it
  goes on that list — a check that fires on something genuinely ambiguous
  produces exactly the false positives this round of work exists to remove.
  The `#page=map` deep links, above in this same section, are the existing
  example of a case deliberately left unresolved for that reason.
  **Re-examined 2026-09-05 and kept here, deliberately:** decided (Kirk, Fable planning session) that the `CONTEXT()`-argument check DOES belong in the tool and stays POST-PUBLICATION. It is the cheapest item on the post-publication list with a demonstrated payoff (it found `Context("View Type")` in Kirk's own app, by hand), and its output belongs in a NEW file, never in an existing orphan CSV — it answers "is this expression meaningful," a different kind of question from reachability, so keeping it separate leaves every existing verdict and every existing output file untouched. Note the distinction this session had to draw: this argument check is NOT the same thing as evaluating `CONTEXT()` CONDITIONS for reachability, which is the section B `view_orphan_detector.py` fix and is phase one. Interim, zero-code version, done in the same session as this note: the closed keyword vocabulary is now recorded in `APPSHEET_BEHAVIOR.md`'s "AppSheet validates shape, not meaning" section with its source, so CC can sweep the parsed expressions for out-of-vocabulary arguments today without any parser change. The unsatisfiable-pair check (the fourth instance in that same `APPSHEET_BEHAVIOR.md` section) has been pulled OUT of this bullet into section B as scoped phase-one work, for the reasons given there.
- **The general division of labour between models.** Which model suits which kind
  of work — Claude Code for specified mechanical tasks, Sonnet for routine
  guidance and review, Opus for analysis and judgment in conversation, a
  stronger model for hard irreversible decisions — is Kirk's working practice,
  recorded outside this repository. It is kept off this list because it is
  situational and ages faster than the project: model names and capabilities
  turn over, and a reader on another platform would find the specifics useless.
  What does appear here are per-item notes, on the two items where the choice
  carries information a reader could not otherwise infer. The test those two
  notes apply: hard to reverse in practice, not settleable by running something,
  and the reasoning genuinely difficult — all three, not one or two.

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

**Design notes recorded 2026-09-05 (Kirk, Fable planning session) — not a design, not scheduled, recorded so they are not re-derived:**

- **The use case is the asked-for trace, not exhaustive checking.** Kirk's own statement of the goal: CC is able to check the calculations he ASKS it to check, even when the variables and calculations follow a circuitous path between AppSheet and Google Sheets. Exhaustive verification of every calculation is not the goal. Consequence: the dump needs COMPLETE formulas (a trace cannot know in advance which cells and tabs a circuitous path crosses) but only RATIONED values (full values for the cells on the chain under question, not for everything) — which is the Addendum 4 shape, now with its reason stated.
- **External spreadsheets are first-class sources with a declared state.** Every `IMPORTRANGE` call names its source (spreadsheet ID or URL, and range), so the dump can always record WHAT is imported even when it cannot dump it. Each external source is in one of three states — dumped in full, sampled (enough for tracing structure: formulas and header row; not enough for verifying values), or declared as a boundary — and a small manifest names each source, its state and its dump date. A chain then ends visibly at a file boundary rather than at what looks like a constant. Kirk has one important such source in his own app and may dump it or a sample; the design should support any of the three states for any user.
- **Six uses, one graph.** The project record's Addendum 7 (to be written) records the six scenarios the same data layer serves — tracing, editorial consistency, targeted calculation checking across the seam, forward feature planning ("I want to add this; is it possible in this app, and how?"), performance diagnosis (suite names the structural suspects — virtual columns running `SELECT`/`FILTER`/`LOOKUP` over large tables, `REF_ROWS` chains, wide tables, heavy sheet-side formulas — and the app's own performance profile is the measurement of record; chat-augmented, since this is trade-offs under measurement), and data-model restructuring with impact analysis (what depends on the tables you would merge or split, on both sides of the seam). The last three are FORWARD questions; CLAUDE.md currently describes only the backward one and will need a short section for them. Documentation these uses require, each a page not a module: a sourced, graded list of expensive patterns and of structural trade-offs in `APPSHEET_BEHAVIOR.md`; and a note in CLAUDE.md that the performance profile output is a candidate dumpable input alongside `bot_actions.txt`.

**On model choice:** the early architectural decisions here are the other place
extra model capability is worth spending, and arguably the stronger case — phase
one's remaining work is checkable against code and re-parses, whereas a wrong
architectural decision in phase two costs weeks before anything reveals it.
