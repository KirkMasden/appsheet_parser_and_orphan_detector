# Project status

Last updated 2026-08-24. Records what is outstanding in this project between working sessions.

## Known defects

### Windows crash in master_parser_and_orphan_detector.py

- Line 13 calls `csv.field_size_limit(sys.maxsize)`, which raises `OverflowError` on Windows, where C `long` is 32-bit even in 64-bit Python. A portable fix is `min(sys.maxsize, 2147483647)`, since C `long` is at least 32 bits on every platform.
- Wider issue: that call exists only in `master_parser_and_orphan_detector.py`, but sixteen other scripts read CSVs and have their own `__main__` entry points. Run standalone, none of them raises the limit, so they remain exposed to the "field larger than field limit" error the call was added to prevent. Consider a small shared module imported by every entry point.
- Reported by a user in May 2026 and not yet fixed.

### Orphan detector produces false positives

Four reference paths the parser does not currently follow, each causing components that are genuinely in use to be flagged as orphans:

1. Views reached only via `LINKTOVIEW()` expressions inside actions.
2. Views referenced only through "Related" virtual columns — generally, any Enum, List or EnumList column with a Ref base type can name a view via the referenced table or slice.
3. Views contained in dashboards. Note that `navigation_edge_generator.py` already has a `process_dashboard_containment` method, added December 2025, so this is a feature that does not reach far enough rather than a missing one. Diagnose before changing.
4. Slices referenced only inside expressions in column-level fields such as suggested values, initial values and show-if conditions.

Reported by a user in May 2026 and not yet fixed. Reproduction details and test data are recorded privately — see "Private working notes" below.

### December 2025 User Settings work is unverified

The `USERSETTINGS()` parsing, User Settings orphan detection and broken-reference detection shipped 2025-12-24 with an explicit public caveat that more testing was needed. That testing has not happened.

## Where the code lives

- This repository is the authoritative working copy. Two older copies exist elsewhere on my machine, renamed with an "OLD DO NOT USE" prefix; they contain no work that is not already published.
- Users update by re-downloading the ZIP from GitHub, which is why folders named `appsheet_parser_and_orphan_detector-main` are common.

## Next steps after the bug fixes

Plan from the July 2026 project document, unchanged:

1. A `CLAUDE.md` at this repository root describing the CSV schemas, which analyzer answers which category of question, the instruction to call analyzer methods directly rather than driving the interactive menus, and the known blind spots. Ship an `AGENTS.md` with the same content for non-Anthropic tools.
2. Extend the visibility layer to the backing Google Sheet, via an Apps Script dump of formulas and displayed values.
3. A non-interactive query mode with JSON output, canned question recipes, and optionally `SKILL.md` packaging — only if a demonstrated need appears.

## Private working notes

Reproduction details, test data locations, correspondence and the machine-wide inventory are kept outside this repository, at:
`/Users/kirkmasden/Documents/雑学/260505 0852 AppSheet orphan script possible issues/NOTES.md`
