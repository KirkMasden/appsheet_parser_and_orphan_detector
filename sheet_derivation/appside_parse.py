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
import html
import os
import re
import sys
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Table sources. The export gives every table its own block
# (`data-type="DataSets"`) holding, among other rows, the table's name, its
# "Source Path" (`SourcePath`), its "Worksheet Name/Qualifier"
# (`SourceQualifier`) and its "Data Source" (`DataSourceName`, e.g. `google`
# or `native`). Same fixed template as the identity rows above -- a fact
# about AppSheet's export generator, not about any one app. A native
# AppSheet table (a user-settings table, a bot's state table) has no
# qualifier row at all; its `worksheet` is reported None, not guessed.
# ---------------------------------------------------------------------------

_DATASET_BLOCK_RE = re.compile(
    r'<table[^>]*data-type="DataSets"[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL
)


def _dataset_row_re(field: str) -> "re.Pattern":
    return re.compile(
        r'for="' + field + r'"[^>]*>[^<]*</label></td><td>([^<]*)</td>', re.IGNORECASE
    )


_TABLE_NAME_ROW_RE = _dataset_row_re("Name")
_SOURCE_PATH_ROW_RE = _dataset_row_re("SourcePath")
_SOURCE_QUALIFIER_ROW_RE = _dataset_row_re("SourceQualifier")
_DATA_SOURCE_ROW_RE = _dataset_row_re("DataSourceName")
_SCHEMA_NAME_ROW_RE = _dataset_row_re("SchemaName")
_SOURCE_QUALIFIER_LABEL_RE = re.compile(r'for="SourceQualifier"', re.IGNORECASE)


@dataclass(frozen=True)
class TableSource:
    table: str
    source_path: Optional[str]
    worksheet: Optional[str]  # None when the block has no qualifier row, or an empty one
    data_source: Optional[str]
    schema_name: Optional[str] = None


@dataclass(frozen=True)
class ExportColumn:
    """One column as the export's schema section defines it. `is_virtual`
    and `is_system` are None when the export has no such row for it."""

    name: str
    is_virtual: Optional[bool]
    is_system: Optional[bool]


@dataclass(frozen=True)
class ExportTableSources:
    html_path: str
    tables: Tuple[TableSource, ...]  # in export order
    # False when no table block carries a "Worksheet Name/Qualifier" row at
    # all -- an export too old or too different to say which worksheet any
    # table reads. A caller must then fall back, and say so, rather than
    # read every table's `worksheet` of None as "native, no worksheet".
    qualifier_field_present: bool
    # Schema name -> that schema's columns, in export order. Empty when the
    # export has no schema section this module recognizes.
    columns_by_schema: Dict[str, Tuple[ExportColumn, ...]] = field(default_factory=dict)

    def by_table(self) -> Dict[str, TableSource]:
        return {t.table: t for t in self.tables}

    def sheet_column_names(self, table: TableSource) -> Optional[Tuple[str, ...]]:
        """The names of `table`'s columns that are stored in its worksheet:
        every column the export marks neither virtual nor system-defined
        (a system column such as `_RowNumber` is AppSheet's own, never a
        sheet header). None when the table's schema is not found, or any of
        its columns lacks either flag -- a caller must then not guess."""
        if table.schema_name is None or table.schema_name not in self.columns_by_schema:
            return None
        columns = self.columns_by_schema[table.schema_name]
        if any(c.is_virtual is None or c.is_system is None for c in columns):
            return None
        return tuple(c.name for c in columns if not c.is_virtual and not c.is_system)

    def google_worksheets(self) -> Tuple[str, ...]:
        """Distinct worksheet names of the tables whose data source is
        `google`, in export order."""
        seen: Dict[str, None] = {}
        for t in self.tables:
            if t.worksheet and (t.data_source or "").strip().lower() == "google":
                seen.setdefault(t.worksheet, None)
        return tuple(seen)


def _row(regex: "re.Pattern", block: str) -> Optional[str]:
    match = regex.search(block)
    if not match:
        return None
    value = html.unescape(match.group(1)).strip()
    return value or None


_SCHEMA_BLOCK_START_RE = re.compile(r'<table[^>]*data-type="DataSchemas"[^>]*>', re.IGNORECASE)
_SCHEMA_FIELD_BLOCK_RE = re.compile(
    r'<table[^>]*data-type="SchemaField"[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL
)
_COLUMN_NAME_ROW_RE = _dataset_row_re("Name")
_IS_VIRTUAL_ROW_RE = _dataset_row_re("IsVirtual")
_IS_SYSTEM_ROW_RE = _dataset_row_re("IsSys")


def _yes_no(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "yes":
        return True
    if lowered == "no":
        return False
    return None


def _extract_columns_by_schema(content: str) -> Dict[str, Tuple[ExportColumn, ...]]:
    """Each `DataSchemas` block names a schema; the `SchemaField` blocks
    after it, up to the next `DataSchemas` block, are that schema's
    columns -- the same fixed export template the table blocks use."""
    starts = [m for m in _SCHEMA_BLOCK_START_RE.finditer(content)]
    result: Dict[str, Tuple[ExportColumn, ...]] = {}
    for i, start in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(content)
        segment = content[start.start():end]
        header_end = segment.find("</table>")
        schema_name = _row(_COLUMN_NAME_ROW_RE, segment[:header_end] if header_end >= 0 else segment)
        if schema_name is None:
            continue
        columns = []
        for field_match in _SCHEMA_FIELD_BLOCK_RE.finditer(segment):
            block = field_match.group(1)
            name = _row(_COLUMN_NAME_ROW_RE, block)
            if name is None:
                continue
            columns.append(
                ExportColumn(
                    name=name,
                    is_virtual=_yes_no(_row(_IS_VIRTUAL_ROW_RE, block)),
                    is_system=_yes_no(_row(_IS_SYSTEM_ROW_RE, block)),
                )
            )
        result[schema_name] = tuple(columns)
    return result


def extract_table_sources(html_path: Optional[str]) -> Optional[ExportTableSources]:
    """Every table's name and source rows, read from the export's own
    table blocks. Returns None if `html_path` is None; this module never
    searches for the file itself. A block with no table name is skipped."""
    if html_path is None:
        return None
    with open(html_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    tables = []
    qualifier_field_present = False
    for block_match in _DATASET_BLOCK_RE.finditer(content):
        block = block_match.group(1)
        name = _row(_TABLE_NAME_ROW_RE, block)
        if name is None:
            continue
        if _SOURCE_QUALIFIER_LABEL_RE.search(block):
            qualifier_field_present = True
        tables.append(
            TableSource(
                table=name,
                source_path=_row(_SOURCE_PATH_ROW_RE, block),
                worksheet=_row(_SOURCE_QUALIFIER_ROW_RE, block),
                data_source=_row(_DATA_SOURCE_ROW_RE, block),
                schema_name=_row(_SCHEMA_NAME_ROW_RE, block),
            )
        )
    return ExportTableSources(
        html_path=html_path, tables=tuple(tables), qualifier_field_present=qualifier_field_present,
        columns_by_schema=_extract_columns_by_schema(content),
    )


def hash_file(path: str) -> str:
    """SHA-256 hex digest of a file's exact bytes, read in chunks so a
    46 MB capture file is never held whole just to be hashed."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
