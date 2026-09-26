"""Checks that an app's HTML export and a sheet capture belong together.

Compares the worksheet names the export gives for its Google tables
("Worksheet Name/Qualifier", read by `appside_parse.extract_table_sources`)
with the sheet names the capture records. Reads the export from the input
folder itself, beside the capture's two JSON files, so the check needs no
app-side parse.

Four verdicts:

  - MATCH: every worksheet name is among the capture's sheet names.
  - PARTIAL: some are missing. Reported by name; the run continues.
  - NONE: not one is present. The export and the capture almost certainly
    come from different workbooks, and a mismatched pair still produces
    reports that look valid, so callers STOP unless the user passes an
    explicit override -- the same stance `loader.py` takes when the two
    capture files disagree.
  - UNDECIDABLE: there is nothing to compare (no export in the folder, an
    export naming no Google worksheet, no readable capture file). Reported;
    the run continues.

The same comparison covers the three pasted .txt files (2026-09-26): the
view names in views1.txt and views2.txt against the export's views, and
the names of the user-created actions in actions.txt against the export's
actions (`check_txt_pairing`). A few unmatched names WARN; when fewer than
TXT_STOP_FRACTION of them are in the export, the check STOPS, with the
same override.

What this check cannot do: tell sibling versions of one app apart. Two
copies of an app read identically named worksheets, so their captures
pass this check against either export. Matching the Drive folder in each
table's "Source Path" would be needed for that, and is recorded in
STATUS.md as an idea only.

Nothing here names a table, a worksheet or any fact about one app.
"""

import fnmatch
import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .appside_parse import extract_control_names, extract_table_sources
from .loader import FORMULAS_GLOB_PATTERN, VALUES_GLOB_PATTERN

EXPORT_HTML_NAME = "Application Documentation.html"
OVERRIDE_OPTION = "--allow-mismatch"

VERDICT_MATCH = "match"
VERDICT_PARTIAL = "partial"
VERDICT_NONE = "none"
VERDICT_UNDECIDABLE = "undecidable"

VIEWS_TXT_FILES = ("views1.txt", "views2.txt")
ACTIONS_TXT_FILE = "actions.txt"

# The .txt check STOPS when fewer than this fraction of a file's names are
# in the export ("none or almost none"). Files pasted from the same app's
# editor match all or nearly all their names -- only a view or action
# renamed between the export and the paste is missing -- while files from
# an unrelated app match only by coincidence: shared generic view names
# such as a dashboard's, since the generic system-generated actions (Add,
# Edit, Delete...) are left out of the comparison for exactly this reason.
# One in five leaves a wide margin on both sides; anything between it and
# a full match WARNS.
TXT_STOP_FRACTION = 0.2

_POSITION_WORDS = ("first", "next", "middle", "later", "last")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _collapse(s: str) -> str:
    return _WHITESPACE_RUN_RE.sub(" ", s).strip()


@dataclass(frozen=True)
class PairingResult:
    verdict: str
    export_path: Optional[str]
    capture_path: Optional[str]
    expected_worksheets: Tuple[str, ...]  # the export's Google worksheet names, export order
    present: Tuple[str, ...]
    missing: Tuple[str, ...]
    reason: Optional[str] = None  # set for UNDECIDABLE, and for NONE when the capture lists no sheets

    @property
    def stops(self) -> bool:
        return self.verdict == VERDICT_NONE


def find_export_html(folder: str) -> Optional[str]:
    path = os.path.join(folder, EXPORT_HTML_NAME)
    return path if os.path.isfile(path) else None


def find_capture_file_for_sheet_names(folder: str) -> Optional[str]:
    """The capture file to read sheet names from: the values file if
    exactly one matches (it is the smaller of the two), else the formulas
    file if exactly one matches, else None. The loader separately refuses
    a pair whose two sheet lists differ, so either file is authoritative
    for this purpose."""
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return None
    for pattern in (VALUES_GLOB_PATTERN, FORMULAS_GLOB_PATTERN):
        matches = fnmatch.filter(entries, pattern)
        if len(matches) == 1:
            return os.path.join(folder, matches[0])
    return None


def read_capture_sheet_names(capture_path: str) -> Tuple[str, ...]:
    with open(capture_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return tuple(s.get("sheetName") for s in doc.get("sheets", []) if s.get("sheetName") is not None)


def compare(
    expected_worksheets: Tuple[str, ...],
    capture_sheet_names: Tuple[str, ...],
    export_path: Optional[str] = None,
    capture_path: Optional[str] = None,
) -> PairingResult:
    if not expected_worksheets:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason="the export names no Google Sheets worksheet for any table",
        )
    sheet_set = set(capture_sheet_names)
    present = tuple(w for w in expected_worksheets if w in sheet_set)
    missing = tuple(w for w in expected_worksheets if w not in sheet_set)
    if not missing:
        verdict = VERDICT_MATCH
    elif present:
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_NONE
    reason = None
    if verdict == VERDICT_NONE and not capture_sheet_names:
        reason = (
            "the capture file lists no sheets at all in the format sheet_capture.gs writes -- it may "
            "not be a sheet_capture.gs capture"
        )
    return PairingResult(
        verdict=verdict, export_path=export_path, capture_path=capture_path,
        expected_worksheets=expected_worksheets, present=present, missing=missing, reason=reason,
    )


def check_pairing(
    folder: str,
    export_path: Optional[str] = None,
    capture_path: Optional[str] = None,
) -> PairingResult:
    """Runs the check for an input folder. `export_path` and
    `capture_path` default to the export and a capture file found in
    `folder` itself."""
    export_path = export_path or find_export_html(folder)
    if export_path is None:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=None, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason=f"no {EXPORT_HTML_NAME!r} in {folder!r}, so there is no export to compare with",
        )
    capture_path = capture_path or find_capture_file_for_sheet_names(folder)
    if capture_path is None:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=None,
            expected_worksheets=(), present=(), missing=(),
            reason=f"no single capture file in {folder!r} to read sheet names from",
        )
    sources = extract_table_sources(export_path)
    if not sources.qualifier_field_present:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason="the export carries no 'Worksheet Name/Qualifier' row for any table",
        )
    try:
        sheet_names = read_capture_sheet_names(capture_path)
    except (OSError, ValueError) as exc:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason=f"could not read sheet names from {capture_path!r}: {exc}",
        )
    return compare(sources.google_worksheets(), sheet_names, export_path, capture_path)


# ---------------------------------------------------------------------------
# The pasted .txt files
# ---------------------------------------------------------------------------

def read_view_names_txt(path: str) -> Tuple[str, ...]:
    """View names in a views1.txt/views2.txt paste of the editor's view
    list. A line is a view name only when the line after it is that view's
    own detail line: one holding "Data:" (possibly after a position word),
    one starting "Type:" (a dashboard), or a bare position word. Section
    notes ("These views are accessed via...") and slice group headings
    ("X (slice)") are followed by another name, not a detail line, so they
    are never counted."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [l.strip() for l in fh.read().split("\n")]
    names = []
    for i in range(len(lines) - 1):
        line, nxt = lines[i], lines[i + 1]
        if not line or "Data:" in line or line.startswith("Type:"):
            continue
        if "Data:" in nxt or nxt.startswith("Type:") or nxt in _POSITION_WORDS:
            names.append(line)
    return tuple(dict.fromkeys(names))


def read_user_action_names_txt(path: str) -> Tuple[str, ...]:
    """Names of the actions an actions.txt paste marks as user-created
    ("Effect: ..."), in either the narrow layout (name, then its "Effect:"
    line) or the wide one (both on one line). System-generated actions are
    left out: their names (Add, Edit, Delete...) recur in every app."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [l.strip() for l in fh.read().split("\n")]
    names = []
    for i, line in enumerate(lines):
        if not line:
            continue
        if "Effect:" in line and not line.startswith("Effect:"):
            names.append(line.split("Effect:")[0].strip())
        elif i + 1 < len(lines) and lines[i + 1].startswith("Effect:") and "Effect:" not in line:
            names.append(line)
    return tuple(dict.fromkeys(n for n in names if n))


@dataclass(frozen=True)
class TxtPairingResult:
    kind: str  # "views" or "actions"
    verdict: str
    files: Tuple[str, ...]
    names: Tuple[str, ...]  # distinct names read from the file(s)
    unmatched: Tuple[str, ...]
    reason: Optional[str] = None

    @property
    def stops(self) -> bool:
        return self.verdict == VERDICT_NONE


def compare_names(kind: str, files: Tuple[str, ...], names: Tuple[str, ...], export_names: Tuple[str, ...]) -> TxtPairingResult:
    """Names are compared after collapsing whitespace, because a browser
    paste collapses runs of spaces the export keeps."""
    if not names:
        return TxtPairingResult(kind, VERDICT_UNDECIDABLE, files, (), (), f"no {kind} names found in {list(files)}")
    export_set = {_collapse(n) for n in export_names}
    unmatched = tuple(n for n in names if _collapse(n) not in export_set)
    matched_fraction = (len(names) - len(unmatched)) / len(names)
    if not unmatched:
        verdict = VERDICT_MATCH
    elif matched_fraction < TXT_STOP_FRACTION:
        verdict = VERDICT_NONE
    else:
        verdict = VERDICT_PARTIAL
    return TxtPairingResult(kind, verdict, files, names, unmatched)


def check_txt_pairing(folder: str, export_path: Optional[str] = None) -> List[TxtPairingResult]:
    """One result for the view files and one for actions.txt, each only
    when its file(s) are present. Empty when there is no export."""
    export_path = export_path or find_export_html(folder)
    if export_path is None:
        return []
    exported = extract_control_names(export_path)
    results = []
    view_files = tuple(f for f in VIEWS_TXT_FILES if os.path.isfile(os.path.join(folder, f)))
    if view_files:
        names: List[str] = []
        for f in view_files:
            names.extend(read_view_names_txt(os.path.join(folder, f)))
        results.append(compare_names("views", view_files, tuple(dict.fromkeys(names)), exported.views))
    if os.path.isfile(os.path.join(folder, ACTIONS_TXT_FILE)):
        names = read_user_action_names_txt(os.path.join(folder, ACTIONS_TXT_FILE))
        results.append(compare_names("actions", (ACTIONS_TXT_FILE,), names, exported.actions))
    return results


def format_txt_pairing(result: TxtPairingResult, allow_mismatch: bool = False, examples: int = 5) -> List[str]:
    files = " and ".join(result.files)
    n = len(result.names)
    if result.verdict == VERDICT_MATCH:
        noun = "view name(s)" if result.kind == "views" else "user-created action name(s)"
        return [f"Pairing check: all {n} {noun} in {files} appear in the export."]
    if result.verdict == VERDICT_UNDECIDABLE:
        return [f"WARNING: pairing check could not decide for {files}: {result.reason}. Continuing."]
    sample = list(result.unmatched[:examples])
    more = f" and {len(result.unmatched) - len(sample)} more" if len(result.unmatched) > len(sample) else ""
    head = (
        f"{len(result.unmatched)} of {n} {result.kind} name(s) in {files} are not in the export "
        f"(for example {sample}{more})"
    )
    if result.verdict == VERDICT_PARTIAL:
        return [f"WARNING: pairing check: {head}. Continuing."]
    head += (
        f" -- fewer than {TXT_STOP_FRACTION:.0%} match, so {files} almost certainly come"
        f"{'s' if len(result.files) == 1 else ''} from a different app than the export."
    )
    if allow_mismatch:
        return [f"WARNING: pairing check: {head} Continuing because {OVERRIDE_OPTION} was given."]
    return [
        f"STOPPED: pairing check: {head}",
        f"Put the matching files together in one folder. If you are certain they belong together, "
        f"run again with {OVERRIDE_OPTION}.",
    ]


def format_pairing(result: PairingResult, allow_mismatch: bool = False) -> List[str]:
    """The lines a caller prints. One line on a match; a WARNING naming
    what is missing, or why the check could not decide; a STOP message
    (or, with the override, a WARNING) when nothing matches."""
    n = len(result.expected_worksheets)
    if result.verdict == VERDICT_MATCH:
        return [
            f"Pairing check: all {n} worksheet name(s) the export gives for its Google tables "
            f"appear in the capture."
        ]
    if result.verdict == VERDICT_UNDECIDABLE:
        return [f"WARNING: pairing check could not decide: {result.reason}. Continuing."]
    if result.verdict == VERDICT_PARTIAL:
        return [
            f"WARNING: pairing check: {len(result.missing)} of {n} worksheet name(s) the export "
            f"gives for its Google tables are not in the capture: {list(result.missing)}. "
            f"Tables reading them will have no tab in the join. Continuing."
        ]
    capture = os.path.basename(result.capture_path) if result.capture_path else "the capture"
    head = (
        f"none of the {n} worksheet name(s) the export gives for its Google tables "
        f"({list(result.expected_worksheets)}) appear in {capture}. The export and the capture "
        f"almost certainly come from different workbooks."
    )
    if result.reason:
        head += f" Also: {result.reason}."
    if allow_mismatch:
        return [f"WARNING: pairing check: {head} Continuing because {OVERRIDE_OPTION} was given."]
    return [
        f"STOPPED: pairing check: {head}",
        f"Put the matching export and capture together in one folder. If you are certain they "
        f"belong together, run again with {OVERRIDE_OPTION}.",
    ]
