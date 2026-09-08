"""Loads a raw sheet_capture.gs capture (formulas file + values file).

Loads both files whole -- no streaming, no chunking (design section 2: the
capture is not a size that needs a reading-context workaround, and stage 0's
own done-when is to reproduce exact counts, which a partial read cannot
verify). Runs the three refusal gates before returning anything, so nothing
downstream can be built on a capture whose two halves disagree.

Nothing here may name a sheet. The gates and the loader operate on whatever
`sheets` arrays the two files actually contain.
"""

import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .errors import CaptureIntegrityError


@dataclass(frozen=True)
class SheetFormulaData:
    """One sheet's entry from the formulas file, exactly as captured."""

    sheet_name: str
    row_count: int
    column_count: int
    formulas: Tuple[Tuple[str, ...], ...]
    number_formats: Tuple[Tuple[Any, ...], ...]
    named_ranges: Tuple[Any, ...]
    data_validations: Tuple[Any, ...]
    conditional_format_rules: Tuple[Any, ...]
    protected_ranges: Tuple[Any, ...]
    frozen_rows: int
    frozen_columns: int


@dataclass(frozen=True)
class SheetValueData:
    """One sheet's entry from the values file, exactly as captured."""

    sheet_name: str
    values: Tuple[Tuple[Any, ...], ...]


@dataclass(frozen=True)
class Capture:
    """Both capture files, gate-checked and merged into one model.

    `sheet_order` is the sheets array order from the formulas file -- the
    single explicit key every later stage-0 collection sorts by, since gate
    2 has already proven the values file agrees on both names and order.
    """

    capture_date: str
    spreadsheet_name: str
    trigger_ids: Tuple[Any, ...]
    sheet_order: Tuple[str, ...]
    formula_sheets: Dict[str, SheetFormulaData]
    value_sheets: Dict[str, SheetValueData]

    def formula_sheet(self, sheet_name: str) -> SheetFormulaData:
        return self.formula_sheets[sheet_name]

    def value_sheet(self, sheet_name: str) -> SheetValueData:
        return self.value_sheets[sheet_name]


def discover_capture_files(capture_dir: str) -> Tuple[str, str]:
    """Finds the formulas and values files in a directory by pattern.

    Never hardcodes a workbook's name -- matches the naming convention
    `sheet_capture.gs` itself writes (`*_formulas_*.json`, `*_values_*.json`),
    the same patterns the repo's own .gitignore uses to keep these out.
    Refuses (rather than guesses) if a pattern matches zero or more than one
    file, since an ambiguous directory is exactly the case a silent pick
    would hide.
    """
    formula_matches = sorted(glob.glob(os.path.join(capture_dir, "*formulas*.json")))
    value_matches = sorted(glob.glob(os.path.join(capture_dir, "*values*.json")))

    if len(formula_matches) != 1:
        raise CaptureIntegrityError(
            f"Expected exactly one '*formulas*.json' file in {capture_dir!r}, "
            f"found {len(formula_matches)}: {formula_matches}"
        )
    if len(value_matches) != 1:
        raise CaptureIntegrityError(
            f"Expected exactly one '*values*.json' file in {capture_dir!r}, "
            f"found {len(value_matches)}: {value_matches}"
        )
    return formula_matches[0], value_matches[0]


def _load_json_whole(path: str) -> dict:
    """Reads one capture file completely into memory. No streaming."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _freeze_2d(rows: List[List[Any]]) -> Tuple[Tuple[Any, ...], ...]:
    return tuple(tuple(row) for row in rows)


def _freeze_list(values: Optional[List[Any]]) -> Tuple[Any, ...]:
    return tuple(values) if values is not None else tuple()


def _gate_capture_dates(formulas_raw: dict, values_raw: dict, formulas_path: str, values_path: str) -> str:
    f_date = formulas_raw.get("captureDate")
    v_date = values_raw.get("captureDate")
    if f_date != v_date:
        raise CaptureIntegrityError(
            "Refusing to run: the two capture files disagree on captureDate -- "
            f"{os.path.basename(formulas_path)!r} says {f_date!r}, "
            f"{os.path.basename(values_path)!r} says {v_date!r}. "
            "These are not a matched pair from the same capture run."
        )
    if f_date is None:
        raise CaptureIntegrityError(
            "Refusing to run: neither capture file carries a captureDate value."
        )
    return f_date


def _gate_sheet_lists(formulas_raw: dict, values_raw: dict, formulas_path: str, values_path: str) -> Tuple[str, ...]:
    f_names = tuple(s.get("sheetName") for s in formulas_raw.get("sheets", []))
    v_names = tuple(s.get("sheetName") for s in values_raw.get("sheets", []))
    if f_names != v_names:
        f_set, v_set = set(f_names), set(v_names)
        if f_set != v_set:
            detail = (
                f"only in {os.path.basename(formulas_path)}: {sorted(f_set - v_set)}; "
                f"only in {os.path.basename(values_path)}: {sorted(v_set - f_set)}"
            )
        else:
            detail = (
                f"same {len(f_set)} names, different order -- "
                f"{os.path.basename(formulas_path)}: {list(f_names)}; "
                f"{os.path.basename(values_path)}: {list(v_names)}"
            )
        raise CaptureIntegrityError(
            f"Refusing to run: the two capture files' sheet lists differ ({detail}). "
            "The values file cannot be indexed by the formulas file's coordinates "
            "unless both agree on sheet names and order."
        )
    if not f_names:
        raise CaptureIntegrityError("Refusing to run: the formulas file lists no sheets at all.")
    return f_names


def _gate_declared_dimensions(sheet_name: str, declared_rows: int, declared_cols: int,
                               formulas_2d: Tuple[Tuple[Any, ...], ...],
                               numberformats_2d: Tuple[Tuple[Any, ...], ...],
                               values_2d: Tuple[Tuple[Any, ...], ...]) -> None:
    actual_formula_rows = len(formulas_2d)
    actual_formula_row_lens = {len(r) for r in formulas_2d}
    actual_nf_rows = len(numberformats_2d)
    actual_nf_row_lens = {len(r) for r in numberformats_2d}
    actual_value_rows = len(values_2d)
    actual_value_row_lens = {len(r) for r in values_2d}

    problems = []
    if actual_formula_rows != declared_rows:
        problems.append(
            f"formulas row count {actual_formula_rows} != declared rowCount {declared_rows}"
        )
    if actual_formula_row_lens not in ({declared_cols}, set()):
        problems.append(
            f"formulas row lengths {sorted(actual_formula_row_lens)} != declared columnCount {declared_cols}"
        )
    if actual_nf_rows != declared_rows:
        problems.append(
            f"numberFormats row count {actual_nf_rows} != declared rowCount {declared_rows}"
        )
    if actual_nf_row_lens not in ({declared_cols}, set()):
        problems.append(
            f"numberFormats row lengths {sorted(actual_nf_row_lens)} != declared columnCount {declared_cols}"
        )
    if actual_value_rows != declared_rows:
        problems.append(
            f"values row count {actual_value_rows} != declared rowCount {declared_rows}"
        )
    if actual_value_row_lens not in ({declared_cols}, set()):
        problems.append(
            f"values row lengths {sorted(actual_value_row_lens)} != declared columnCount {declared_cols}"
        )

    if problems:
        raise CaptureIntegrityError(
            f"Refusing to run: sheet {sheet_name!r} declares rowCount={declared_rows}, "
            f"columnCount={declared_cols}, which disagrees with the actual array "
            f"dimensions -- {'; '.join(problems)}."
        )


def load_capture(formulas_path: str, values_path: str) -> Capture:
    """Loads both files whole and runs all three refusal gates.

    Raises CaptureIntegrityError, naming exactly what disagreed, if any gate
    fails. Returns a Capture only when all three hold.
    """
    formulas_raw = _load_json_whole(formulas_path)
    values_raw = _load_json_whole(values_path)

    capture_date = _gate_capture_dates(formulas_raw, values_raw, formulas_path, values_path)
    sheet_order = _gate_sheet_lists(formulas_raw, values_raw, formulas_path, values_path)

    value_sheets_by_name: Dict[str, dict] = {
        s.get("sheetName"): s for s in values_raw.get("sheets", [])
    }

    formula_sheets: Dict[str, SheetFormulaData] = {}
    value_sheets: Dict[str, SheetValueData] = {}

    for sheet_raw in formulas_raw.get("sheets", []):
        name = sheet_raw.get("sheetName")
        declared_rows = sheet_raw.get("rowCount")
        declared_cols = sheet_raw.get("columnCount")
        formulas_2d = _freeze_2d(sheet_raw.get("formulas", []))
        numberformats_2d = _freeze_2d(sheet_raw.get("numberFormats", []))
        values_2d = _freeze_2d(value_sheets_by_name[name].get("values", []))

        _gate_declared_dimensions(
            name, declared_rows, declared_cols, formulas_2d, numberformats_2d, values_2d
        )

        formula_sheets[name] = SheetFormulaData(
            sheet_name=name,
            row_count=declared_rows,
            column_count=declared_cols,
            formulas=formulas_2d,
            number_formats=numberformats_2d,
            named_ranges=_freeze_list(sheet_raw.get("namedRanges")),
            data_validations=_freeze_list(sheet_raw.get("dataValidations")),
            conditional_format_rules=_freeze_list(sheet_raw.get("conditionalFormatRules")),
            protected_ranges=_freeze_list(sheet_raw.get("protectedRanges")),
            frozen_rows=sheet_raw.get("frozenRows"),
            frozen_columns=sheet_raw.get("frozenColumns"),
        )
        value_sheets[name] = SheetValueData(sheet_name=name, values=values_2d)

    return Capture(
        capture_date=capture_date,
        spreadsheet_name=formulas_raw.get("spreadsheetName"),
        trigger_ids=_freeze_list(formulas_raw.get("triggerIds")),
        sheet_order=sheet_order,
        formula_sheets=formula_sheets,
        value_sheets=value_sheets,
    )
