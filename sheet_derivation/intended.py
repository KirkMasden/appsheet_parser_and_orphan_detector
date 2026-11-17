"""The intended-items record (formula checkup build stage 4), and the small
command that writes it.

When the checkup raises a finding that the user says is intended, the AI
records it here, so that later sketches do not raise it again. Intended
items are kept apart from new findings, not dropped.

THE FILE. One readable JSON file per app, `<intended folder>/<app name>.json`.
The default folder is `intended` in the workspace (the repository's parent
folder), beside apps/ and output/, outside every timestamped folder. The app
name is the name the export gives the app: the last part of its
DefnFolderName ("/appsheet/data/KankakuV19-230844" gives "KankakuV19"; the
final hyphen and digits are dropped). If it cannot be derived, no record is
read or written. Renaming or copying an app therefore starts a new, empty
record.

TWO KINDS OF ENTRY. Formula-checkup entries (table and column) are applied
in code, by stage 6. Orphan entries (orphan kind and name) are only stored
and listed here; the AI applies them when it gives the sketch.

ONLY THE COMMAND WRITES IT, and the AI runs the command only when the user
says something is intended, or asks to withdraw a declaration. Nobody
edits the file by hand.

FINGERPRINT. A checkup entry carries a fingerprint of what makes the
finding what it is, so that the entry lapses when the finding changes but
not when unrelated rows are added. It is built by `checkup_fingerprint`
from a stage 6 column line (the same function serves the command and stage
6, so they cannot disagree): the situation, the tier and grade, the stored
formula as exported, and the non-matching part of the sheet side (each
group of differing formulas by its canonical converted text with its rows;
for S2A and S2B only, also the rows without a formula). Matching rows are
not part of it. An orphan's fingerprint is its kind and name.

    python -m sheet_derivation.intended add <sheet_dir> <table> <column> [--note N]
    python -m sheet_derivation.intended add-orphan <app> <orphan kind> <name> [--note N]
    python -m sheet_derivation.intended list (--app A | --sheet-dir D)
    python -m sheet_derivation.intended remove (--app A | --sheet-dir D) <entry id>

Every subcommand takes --intended-dir to override the default folder.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .workspace import resolve_workspace_root

FORMAT_VERSION = 1
KIND_CHECKUP = "checkup"
KIND_ORPHAN = "orphan"
CHECKUP_JSONL_NAME = "stage6_formula_checkup.jsonl"

_FOLDER_RE = re.compile(r"^(?P<name>.+)-[0-9]+$")
_JST = timezone(timedelta(hours=9))


class IntendedError(Exception):
    """A refusal the command reports to the user, with a clear message."""


# ---------------------------------------------------------------------------
# App name, paths, dates
# ---------------------------------------------------------------------------


def derive_app_name(default_app_folder: Optional[str]) -> Optional[str]:
    """The app's name from the export's DefnFolderName, or None. The last
    path part, minus its final hyphen and digits; None when there is no
    such part, when nothing is left of the name, or when the name could not
    safely be a file name."""
    if not default_app_folder or not isinstance(default_app_folder, str):
        return None
    last = default_app_folder.strip().replace("\\", "/").rstrip("/").split("/")[-1].strip()
    match = _FOLDER_RE.match(last)
    if not match:
        return None
    name = match.group("name").strip()
    return name if is_safe_app_name(name) else None


def is_safe_app_name(name: str) -> bool:
    return bool(name) and name == name.strip() and not name.startswith(".") and not re.search(r"[/\\\x00]", name)


def default_intended_dir() -> str:
    return os.path.join(resolve_workspace_root(announce=False), "intended")


def record_path(app_name: str, intended_dir: Optional[str] = None) -> str:
    return os.path.join(intended_dir or default_intended_dir(), f"{app_name}.json")


def today_jst() -> str:
    return datetime.now(_JST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def _hash(parts: Any) -> str:
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checkup_fingerprint(line: Dict[str, Any]) -> str:
    """The fingerprint of a stage 6 column line (a dict as stage6_artifacts
    writes it)."""
    situation = line["situation"]
    groups = sorted(
        ([g["canonicalConverted"], g["rows"]] for g in line.get("differingGroups", [])),
        key=lambda pair: (pair[1], pair[0]),
    )
    parts: Dict[str, Any] = {
        "situation": situation,
        "tier": line["tier"],
        "grade": line.get("grade"),
        "storedFormula": line["storedFormula"],
        "groups": groups,
    }
    if situation in ("S2A", "S2B"):
        parts["noFormulaRows"] = line.get("noFormulaRows", "")
    return _hash(parts)


def orphan_fingerprint(orphan_kind: str, name: str) -> str:
    return _hash({"orphanKind": orphan_kind, "name": name})


def _rows_for_entry(line: Dict[str, Any]) -> str:
    """Readable aid in the entry: the rows that make the finding."""
    situation = line["situation"]
    if situation in ("S2A", "S2B"):
        pieces = [g["rows"] for g in line.get("differingGroups", [])]
        if line.get("noFormulaRows"):
            pieces.append(line["noFormulaRows"])
        return ", ".join(pieces)
    if situation == "S1":
        return ", ".join(g["rows"] for g in line.get("differingGroups", []))
    return ""


# ---------------------------------------------------------------------------
# The record file
# ---------------------------------------------------------------------------


def entry_id(entry: Dict[str, Any]) -> str:
    if entry["kind"] == KIND_CHECKUP:
        return f"{KIND_CHECKUP}:{entry['table']}|{entry['column']}"
    return f"{KIND_ORPHAN}:{entry['orphanKind']}|{entry['name']}"


def _sort_key(entry: Dict[str, Any]) -> Tuple[str, str, str]:
    if entry["kind"] == KIND_CHECKUP:
        return (entry["kind"], entry["table"], entry["column"])
    return (entry["kind"], entry["orphanKind"], entry["name"])


class RecordUnreadable(Exception):
    pass


def read_record(path: str) -> Optional[Dict[str, Any]]:
    """The parsed record, or None when the file does not exist. Raises
    RecordUnreadable, saying why, when it exists and cannot be used."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RecordUnreadable(f"{path} could not be read as JSON ({exc})")
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise RecordUnreadable(f"{path} is not an intended-items record (no 'entries' list)")
    for e in data["entries"]:
        if not isinstance(e, dict) or e.get("kind") not in (KIND_CHECKUP, KIND_ORPHAN):
            raise RecordUnreadable(f"{path} holds an entry of an unknown kind: {e!r}")
        needed = ("table", "column") if e["kind"] == KIND_CHECKUP else ("orphanKind", "name")
        if any(not isinstance(e.get(k), str) for k in needed + ("fingerprint",)):
            raise RecordUnreadable(f"{path} holds an incomplete entry: {e!r}")
    return data


def write_record(path: str, app_name: str, entries: List[Dict[str, Any]]) -> None:
    """Atomic: a temporary file in the same folder, then a rename. The
    folder is created here, so only when something is written."""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    data = {
        "app": app_name,
        "entries": sorted(entries, key=_sort_key),
        "format": FORMAT_VERSION,
    }
    fd, tmp_path = tempfile.mkstemp(prefix=".intended-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_for_write(path: str) -> List[Dict[str, Any]]:
    try:
        data = read_record(path)
    except RecordUnreadable as exc:
        raise IntendedError(f"refusing to change the record: {exc}")
    return [] if data is None else list(data["entries"])


# ---------------------------------------------------------------------------
# Reading the checkup artifact
# ---------------------------------------------------------------------------


def read_checkup_lines(sheet_dir: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    path = os.path.join(sheet_dir, CHECKUP_JSONL_NAME)
    if not os.path.isfile(path):
        raise IntendedError(f"{path} does not exist; run the checkup first (python -m sheet_derivation.run)")
    lines = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))
    if not lines or lines[0].get("kind") != "meta":
        raise IntendedError(f"{path} does not start with a meta line")
    return lines[0], lines[1:]


def app_name_from_sheet_dir(sheet_dir: str) -> str:
    meta, _ = read_checkup_lines(sheet_dir)
    if not meta.get("present"):
        raise IntendedError(f"the checkup in {sheet_dir} is absent ({meta.get('absentReason')}); there is nothing to declare")
    name = meta.get("appName")
    if not name:
        raise IntendedError(
            "the app's name could not be derived from the export (no usable DefnFolderName), so no record is "
            "read or written; nothing was changed"
        )
    return name


# ---------------------------------------------------------------------------
# Commands (each returns the text it prints)
# ---------------------------------------------------------------------------


def cmd_add(sheet_dir: str, table: str, column: str, note: Optional[str], intended_dir: Optional[str]) -> str:
    meta, lines = read_checkup_lines(sheet_dir)
    app_name = app_name_from_sheet_dir(sheet_dir)
    line = next((l for l in lines if l.get("kind") == "column" and l["table"] == table and l["column"] == column), None)
    if line is None:
        raise IntendedError(
            f"column {table!r} | {column!r} is not in the checkup of {sheet_dir}: it was not examined (it has "
            "neither a stored formula nor sheet formulas below the header row, or it does not exist), so there is "
            "no finding to declare"
        )
    if line["tier"] not in ("raised", "minor"):
        raise IntendedError(
            f"column {table!r} | {column!r} has tier {line['tier']!r}, not 'raised' or 'minor', so it is not a "
            "finding to declare; nothing was changed"
        )
    path = record_path(app_name, intended_dir)
    entries = _load_for_write(path)
    entry = {
        "kind": KIND_CHECKUP,
        "table": table,
        "column": column,
        "situation": line["situation"],
        "rows": _rows_for_entry(line),
        "declared": today_jst(),
        "note": note,
        "fingerprint": checkup_fingerprint(line),
    }
    replaced = any(entry_id(e) == entry_id(entry) for e in entries)
    entries = [e for e in entries if entry_id(e) != entry_id(entry)] + [entry]
    write_record(path, app_name, entries)
    verb = "replaced the entry for" if replaced else "added"
    return (
        f"{verb} {entry_id(entry)} (situation {entry['situation']}, tier {line['tier']}"
        f"{', grade ' + line['grade'] if line.get('grade') else ''}) in {path}"
    )


def cmd_add_orphan(app_name: str, orphan_kind: str, name: str, note: Optional[str], intended_dir: Optional[str]) -> str:
    if not is_safe_app_name(app_name):
        raise IntendedError(f"{app_name!r} cannot be used as an app name (empty, or it would not be a safe file name)")
    orphan_kind, name = orphan_kind.strip(), name.strip()
    if not orphan_kind or not name:
        raise IntendedError("an orphan entry needs a kind and a name, both non-empty")
    path = record_path(app_name, intended_dir)
    entries = _load_for_write(path)
    entry = {
        "kind": KIND_ORPHAN,
        "orphanKind": orphan_kind,
        "name": name,
        "declared": today_jst(),
        "note": note,
        "fingerprint": orphan_fingerprint(orphan_kind, name),
    }
    replaced = any(entry_id(e) == entry_id(entry) for e in entries)
    entries = [e for e in entries if entry_id(e) != entry_id(entry)] + [entry]
    write_record(path, app_name, entries)
    return f"{'replaced the entry for' if replaced else 'added'} {entry_id(entry)} in {path}"


def format_entry(entry: Dict[str, Any]) -> str:
    bits = [f"declared {entry.get('declared')}"]
    if entry["kind"] == KIND_CHECKUP:
        bits.insert(0, f"situation {entry.get('situation')}" + (f", rows {entry['rows']}" if entry.get("rows") else ""))
    if entry.get("note"):
        bits.append(f"note: {entry['note']}")
    return f"{entry_id(entry)}  ({'; '.join(bits)})"


def cmd_list(app_name: str, intended_dir: Optional[str]) -> str:
    path = record_path(app_name, intended_dir)
    try:
        data = read_record(path)
    except RecordUnreadable as exc:
        raise IntendedError(str(exc))
    if data is None:
        return f"no record for app {app_name!r} (would be {path})"
    entries = sorted(data["entries"], key=_sort_key)
    if not entries:
        return f"record for app {app_name!r} ({path}) holds no entries"
    out = [f"record for app {app_name!r} ({path}): {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"]
    out += [f"  {format_entry(e)}" for e in entries]
    return "\n".join(out)


def cmd_remove(app_name: str, id_text: str, intended_dir: Optional[str]) -> str:
    path = record_path(app_name, intended_dir)
    entries = _load_for_write(path)
    kept = [e for e in entries if entry_id(e) != id_text]
    if len(kept) == len(entries):
        raise IntendedError(f"no entry {id_text!r} in {path}; 'list' shows the entry ids")
    write_record(path, app_name, kept)
    return f"removed {id_text} from {path} ({len(kept)} entr{'y' if len(kept) == 1 else 'ies'} left)"


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sheet_derivation.intended",
        description=(
            "The intended-items record. Run only when the user says something is intended, or asks to "
            "withdraw a declaration; never edit the file by hand."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--intended-dir", default=None, help="Folder holding the records (default: <workspace>/intended).")

    def app_selector(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--app", help="The app's name.")
        g.add_argument("--sheet-dir", help="The sheet output folder of a run; the app name is taken from its checkup.")

    p = sub.add_parser("add", help="Declare a checkup finding intended.")
    p.add_argument("sheet_dir", help="The sheet output folder of a run (output/<name>/sheet).")
    p.add_argument("table")
    p.add_argument("column")
    p.add_argument("--note", default=None)
    common(p)

    p = sub.add_parser("add-orphan", help="Declare an orphan intended.")
    p.add_argument("app")
    p.add_argument("orphan_kind", help="As the detector names it: view, action, slice, virtual column, format rule.")
    p.add_argument("name")
    p.add_argument("--note", default=None)
    common(p)

    p = sub.add_parser("list", help="Print the app's entries.")
    app_selector(p)
    common(p)

    p = sub.add_parser("remove", help="Remove one entry, identified as 'list' shows it.")
    app_selector(p)
    p.add_argument("entry_id", help="For example checkup:Overall|Daily record or orphan:view|Some view")
    common(p)
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "add":
            text = cmd_add(args.sheet_dir, args.table, args.column, args.note, args.intended_dir)
        elif args.command == "add-orphan":
            text = cmd_add_orphan(args.app, args.orphan_kind, args.name, args.note, args.intended_dir)
        else:
            app = args.app if args.app else app_name_from_sheet_dir(args.sheet_dir)
            if args.command == "list":
                text = cmd_list(app, args.intended_dir)
            else:
                text = cmd_remove(app, args.entry_id, args.intended_dir)
    except IntendedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
