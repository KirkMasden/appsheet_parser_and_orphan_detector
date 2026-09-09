"""Reads the optional app-side parse for Stage 5 (the AppSheet-to-sheet
join, design section 4.4) -- and only the one file it is allowed to read.

READS `appsheet_columns.csv` ONLY. Every other CSV the app-side parser
suite writes either carries no table/column identity this join needs, or
-- in the case of `appsheet_views.csv` -- carries six fields (`data_source`,
`source_table`, `category`, `position`, `view_type`, `ref_parent`) sourced
from `views1.txt`/`views2.txt`, browser paste captures subject to the
documented whitespace-collapse defect (`STATUS.md`, 2026-09-06). This
module never opens that file. `column_parser.py` itself never reads those
text files either (confirmed by inspection, not assumed) -- `table_name`
and `column_name` are HTML-derived, which is what makes them safe inputs
here.

Nothing here may name a table, a column, or any other fact about one
app -- this module operates on whatever `appsheet_columns.csv` a caller
points it at, the same way `loader.py` operates on whatever `sheets`
array a capture contains.
"""

import csv
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


class AppSideParseError(Exception):
    """Raised when the app-side parse directory does not contain the one
    file this module reads, or that file is missing a required column."""


@dataclass(frozen=True)
class AppColumn:
    table_name: str
    column_name: str
    is_virtual: Optional[bool]  # None when the field is absent or empty for this row


@dataclass(frozen=True)
class AppSideColumns:
    columns: Tuple[AppColumn, ...]
    table_names: Tuple[str, ...]  # distinct, sorted
    virtual_field_present: bool
    source_path: str

    def columns_for_table(self, table_name: str) -> Tuple[AppColumn, ...]:
        return tuple(c for c in self.columns if c.table_name == table_name)


def discover_appside_columns_csv(parse_dir: str) -> str:
    path = os.path.join(parse_dir, "appsheet_columns.csv")
    if not os.path.isfile(path):
        raise AppSideParseError(
            f"{parse_dir!r} does not contain 'appsheet_columns.csv' -- this is the only "
            f"file Stage 5 reads from an app-side parse; refusing to guess at another name"
        )
    return path


def load_appside_columns(csv_path: str) -> AppSideColumns:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        virtual_field_present = "is_virtual" in fieldnames
        if "table_name" not in fieldnames or "column_name" not in fieldnames:
            raise AppSideParseError(
                f"{csv_path!r} is missing 'table_name' or 'column_name' -- not a recognizable "
                f"appsheet_columns.csv"
            )
        columns = []
        for row in reader:
            table_name = row.get("table_name") or ""
            column_name = row.get("column_name") or ""
            if not table_name or not column_name:
                continue
            is_virtual: Optional[bool] = None
            if virtual_field_present:
                raw = (row.get("is_virtual") or "").strip()
                if raw:
                    is_virtual = raw == "Yes"
            columns.append(AppColumn(table_name=table_name, column_name=column_name, is_virtual=is_virtual))

    table_names = tuple(sorted({c.table_name for c in columns}))
    return AppSideColumns(
        columns=tuple(columns),
        table_names=table_names,
        virtual_field_present=virtual_field_present,
        source_path=csv_path,
    )


# ---------------------------------------------------------------------------
# App identity and stamp support. Every field here is optional and reported
# absent rather than guessed -- no parse directory records a commit hash or
# an app version anywhere (verified during the stage 5 precheck), so the
# only way to recover an app's name/version is to read its own HTML export
# directly, and the caller must say where that file is; this module never
# tries to locate it by guessing a directory-name transformation.
# ---------------------------------------------------------------------------

_OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"')
_VERSION_ROW_RE = re.compile(
    r'for="Version"[^<]*</label></td><td>([^<]*)</td>', re.IGNORECASE
)
_APP_FOLDER_RE = re.compile(
    r'for="DefnFolderName"[^<]*</label></td><td>([^<]*)</td>', re.IGNORECASE
)


@dataclass(frozen=True)
class AppIdentity:
    html_path: Optional[str]
    og_title: Optional[str]
    version: Optional[str]
    default_app_folder: Optional[str]
    html_mtime_iso: Optional[str]  # the export HTML's own file mtime, used as a PROXY
    # for export date, since no AppSheet HTML export this project has seen carries an
    # internal export-date field of its own -- stated as a proxy, never as a fact the
    # file itself asserts.


_ABSENT_IDENTITY = AppIdentity(
    html_path=None, og_title=None, version=None, default_app_folder=None, html_mtime_iso=None
)


def extract_app_identity(html_path: Optional[str]) -> AppIdentity:
    """Generic extraction over AppSheet's own fixed documentation-export
    template (`og:title` meta tag, the `Version` and `DefnFolderName` table
    rows) -- these are markup patterns AppSheet's export generator uses for
    every app, not a fact about one workbook. Returns an all-absent
    AppIdentity if `html_path` is None; this module never searches for the
    file itself."""
    if html_path is None:
        return _ABSENT_IDENTITY
    with open(html_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    og_title_match = _OG_TITLE_RE.search(content)
    version_match = _VERSION_ROW_RE.search(content)
    folder_match = _APP_FOLDER_RE.search(content)
    mtime = os.path.getmtime(html_path)
    mtime_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return AppIdentity(
        html_path=html_path,
        og_title=og_title_match.group(1) if og_title_match else None,
        version=version_match.group(1) if version_match else None,
        default_app_folder=folder_match.group(1) if folder_match else None,
        html_mtime_iso=mtime_iso,
    )


def hash_file(path: str) -> str:
    """SHA-256 hex digest of a file's exact bytes, read in chunks so a
    46 MB capture file is never held whole just to be hashed."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
