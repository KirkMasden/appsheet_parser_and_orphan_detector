"""Shared scaffolding for the stage 6 (formula checkup) tests: builds a
synthetic workbook, app-side files and export from a small description, and
runs the checkup over them. No real data anywhere; the table, tab and
column names are invented.

A single-column scenario (`scenario`) has table "T" reading tab "T", with
column A "Key" (the table's key) and column B "F", the column examined.
Each row of the scenario is a short code for what column B holds in it:

  same   =A{r}+1   converts to RC[-1]+1, the stored text STORED below
  diff   =A{r}+2   a different formula
  diff2  =A{r}*2   another, different one
  none   a plain value, no formula
  blank  nothing
  bad    ={1,2}    an array literal, which the converter will not compare
  const  0.23 as a plain value

A trailing "!" (for example "same!") leaves the key cell empty in that row.
"""

import os
import tempfile
from typing import Dict, List, Optional, Tuple

from .. import stage6
from .fixtures import (
    build_capture_from_tabs,
    write_export_html,
    write_formula_columns_csv,
    write_pair,
    write_tables_csv,
)

STORED = "RC[-1]+1"


def cell_for(code: str, row: int):
    if code == "same":
        return (f"=A{row}+1", row + 1)
    if code == "diff":
        return (f"=A{row}+2", row + 2)
    if code == "diff2":
        return (f"=A{row}*2", row * 2)
    if code == "none":
        return 7
    if code == "blank":
        return None
    if code == "bad":
        return ("={1,2}", "")
    if code == "const":
        return 0.23
    raise ValueError(code)


def scenario_rows(codes: List[str]) -> List[list]:
    rows = [["Key", "F"]]
    for i, spec in enumerate(codes):
        row = i + 2
        no_key = spec.endswith("!")
        code = spec.rstrip("!")
        rows.append([None if no_key else f"k{row}", cell_for(code, row)])
    return rows


def column_rows(table: str, names: List[str], key: Optional[str] = "Key", virtual=(), formulas: Dict[str, str] = None):
    formulas = formulas or {}
    return [
        {
            "table_name": table, "column_name": n,
            "is_virtual": "Yes" if n in virtual else "No",
            "key": "Yes" if n == key else "No",
            "spreadsheet_formula": formulas.get(n, ""),
        }
        for n in names
    ]


def make_inputs(
    tmp: str,
    tabs: Dict[str, list],
    column_rows_: List[dict],
    tables: Optional[List[Tuple[str, str]]] = None,
    worksheets: Optional[Dict[str, Optional[str]]] = None,
    export_columns: bool = True,
    columns_fields=None,
    app_folder: Optional[str] = None,
):
    """Writes capture, app-side files and export under `tmp`; returns
    (formulas_path, values_path, appside_dir, export_html_path). `tables` is
    the content of appsheet_tables.csv, or None for no such file.
    `worksheets` maps a table to the tab it reads (default: the same name;
    None means a native table with no worksheet)."""
    capture_dir = os.path.join(tmp, "capture")
    app_dir = os.path.join(tmp, "app")
    os.makedirs(capture_dir)
    os.makedirs(app_dir)
    formulas_doc, values_doc = build_capture_from_tabs(tabs)
    fpath, vpath = write_pair(capture_dir, formulas_doc, values_doc)
    write_formula_columns_csv(app_dir, column_rows_, columns_fields)
    if tables is not None:
        write_tables_csv(app_dir, tables)

    table_names = []
    for r in column_rows_:
        if r["table_name"] not in table_names:
            table_names.append(r["table_name"])
    worksheets = worksheets or {}
    export_tables = []
    for t in table_names:
        ws = worksheets[t] if t in worksheets else t
        export_tables.append((t, ws, "google" if ws is not None else "native"))
    columns = None
    if export_columns:
        columns = {
            t: [(r["column_name"], r["is_virtual"] == "Yes", False) for r in column_rows_ if r["table_name"] == t]
            for t in table_names
        }
    html = write_export_html(capture_dir, export_tables, columns=columns, app_folder=app_folder)
    return fpath, vpath, app_dir, html


def run_checkup(
    tabs, column_rows_, tables=None, worksheets=None, export_columns=True, columns_fields=None,
    app_folder=None, **kwargs
):
    with tempfile.TemporaryDirectory() as tmp:
        fpath, vpath, app_dir, html = make_inputs(
            tmp, tabs, column_rows_, tables, worksheets, export_columns, columns_fields, app_folder
        )
        return stage6.run_stage6(fpath, vpath, appside_parse_dir=app_dir, app_export_html_path=html, **kwargs)


def scenario(codes: List[str], stored: str = STORED, mode: Optional[str] = "ALL_CHANGES", key_flag: bool = True,
             **kwargs):
    """Runs the single-column scenario; `mode` None means no appsheet_tables.csv."""
    cols = column_rows("T", ["Key", "F"], key="Key" if key_flag else None, formulas={"F": stored})
    tables = None if mode is None else [("T", mode)]
    return run_checkup({"T": scenario_rows(codes)}, cols, tables, **kwargs)


def finding(result, table: str, column: str):
    for f in result.checkup.findings:
        if f.table == table and f.column == column:
            return f
    raise AssertionError(f"no finding for {table}.{column}")
