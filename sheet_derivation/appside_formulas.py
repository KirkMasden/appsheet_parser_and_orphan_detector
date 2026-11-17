"""Reads the two app-side files the formula checkup (stage 6) needs and
stage 5 does not: the stored spreadsheet formula, key flag and virtual flag
of each column (`appsheet_columns.csv`), and each table's update setting
(`appsheet_tables.csv`).

Kept apart from appside_parse.py on purpose: stage 5 reads three fields of
`appsheet_columns.csv` and nothing else, and that boundary is not widened
here. This module is a second, separate reader of the same file for a
different stage.

Nothing here names a table, a column or any other fact about one app.
Values are returned exactly as the CSV holds them: a stored formula is
never trimmed or interpreted, and an update setting is never translated.
"""

import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .appside_parse import AppSideParseError

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

TABLES_CSV_NAME = "appsheet_tables.csv"


@dataclass(frozen=True)
class AppFormulaColumn:
    table_name: str
    column_name: str
    is_virtual: Optional[bool]  # None when the field is absent or empty for this row
    is_key: Optional[bool]  # None when the field is absent or empty for this row
    spreadsheet_formula: str  # exactly as in the CSV; "" when empty


@dataclass(frozen=True)
class AppFormulaColumns:
    columns: Tuple[AppFormulaColumn, ...]  # file order
    spreadsheet_formula_field_present: bool
    key_field_present: bool
    virtual_field_present: bool
    source_path: str

    def columns_for_table(self, table_name: str) -> Tuple[AppFormulaColumn, ...]:
        return tuple(c for c in self.columns if c.table_name == table_name)


def _yes_no(raw: Optional[str]) -> Optional[bool]:
    text = (raw or "").strip()
    if not text:
        return None
    return text == "Yes"


def load_appside_formula_columns(csv_path: str) -> AppFormulaColumns:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "table_name" not in fieldnames or "column_name" not in fieldnames:
            raise AppSideParseError(
                f"{csv_path!r} is missing 'table_name' or 'column_name' -- not a recognizable "
                f"appsheet_columns.csv"
            )
        formula_present = "spreadsheet_formula" in fieldnames
        key_present = "key" in fieldnames
        virtual_present = "is_virtual" in fieldnames
        columns = []
        for row in reader:
            table_name = row.get("table_name") or ""
            column_name = row.get("column_name") or ""
            if not table_name or not column_name:
                continue
            columns.append(
                AppFormulaColumn(
                    table_name=table_name,
                    column_name=column_name,
                    is_virtual=_yes_no(row.get("is_virtual")) if virtual_present else None,
                    is_key=_yes_no(row.get("key")) if key_present else None,
                    spreadsheet_formula=(row.get("spreadsheet_formula") or "") if formula_present else "",
                )
            )
    return AppFormulaColumns(
        columns=tuple(columns),
        spreadsheet_formula_field_present=formula_present,
        key_field_present=key_present,
        virtual_field_present=virtual_present,
        source_path=csv_path,
    )


@dataclass(frozen=True)
class AppTableSettings:
    """Each table's update setting, as exported. `settings` keeps file
    order; a table named twice keeps its first row."""

    settings: Tuple[Tuple[str, str], ...]  # (table_name, update_mode as exported)
    source_path: str

    def by_table(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for name, mode in self.settings:
            result.setdefault(name, mode)
        return result


def discover_appside_tables_csv(parse_dir: str) -> Optional[str]:
    """The path of `appsheet_tables.csv` in an app-side parse folder, or
    None when there is none (a parse made before the file existed)."""
    path = os.path.join(parse_dir, TABLES_CSV_NAME)
    return path if os.path.isfile(path) else None


def load_appside_tables(csv_path: str) -> AppTableSettings:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "table_name" not in fieldnames or "update_mode" not in fieldnames:
            raise AppSideParseError(
                f"{csv_path!r} is missing 'table_name' or 'update_mode' -- not a recognizable "
                f"appsheet_tables.csv"
            )
        settings = []
        for row in reader:
            name = row.get("table_name") or ""
            if not name:
                continue
            settings.append((name, row.get("update_mode") or ""))
    return AppTableSettings(settings=tuple(settings), source_path=csv_path)
