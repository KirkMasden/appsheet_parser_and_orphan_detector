"""Tiny synthetic captures for tests. No real capture data anywhere here --
the public repo's test suite must run for anyone, without Kirk's private
workbook. Deliberately uses sheet names unlike Kirk's own capture, since
sheet names may appear in tests but must never appear in tool logic; using
different names here helps confirm that.
"""

import json
import os
import tempfile
from typing import Tuple

CAPTURE_DATE = "2099-01-01T00:00:00.000Z"


def _minimal_formulas_sheet(name: str, formulas, number_formats=None, frozen_rows=0, frozen_columns=0):
    rows = len(formulas)
    cols = len(formulas[0]) if formulas else 0
    if number_formats is None:
        number_formats = [[None for _ in range(cols)] for _ in range(rows)]
    return {
        "sheetName": name,
        "rowCount": rows,
        "columnCount": cols,
        "formulas": formulas,
        "numberFormats": number_formats,
        "namedRanges": [],
        "dataValidations": [],
        "conditionalFormatRules": [],
        "protectedRanges": [],
        "frozenRows": frozen_rows,
        "frozenColumns": frozen_columns,
    }


def _minimal_values_sheet(name: str, values):
    return {"sheetName": name, "values": values}


def build_good_pair() -> Tuple[dict, dict]:
    """Two internally-consistent, mutually-agreeing capture dicts.

    Sheet "Alpha": 2x2, one formula, two values.
    Sheet "Beta": 1x3, zero formulas, one value.
    """
    alpha_formulas = [["=A2", ""], ["", ""]]
    alpha_values = [[1, ""], ["", 2]]
    beta_formulas = [["", "", ""]]
    beta_values = [["x", "", ""]]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Test Workbook",
        "triggerIds": [],
        "sheets": [
            _minimal_formulas_sheet("Alpha", alpha_formulas, frozen_rows=1),
            _minimal_formulas_sheet("Beta", beta_formulas, frozen_columns=1),
        ],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Test Workbook",
        "sheets": [
            _minimal_values_sheet("Alpha", alpha_values),
            _minimal_values_sheet("Beta", beta_values),
        ],
    }
    return formulas_doc, values_doc


def write_pair(tmpdir: str, formulas_doc: dict, values_doc: dict) -> Tuple[str, str]:
    formulas_path = os.path.join(tmpdir, "Test_formulas_00000000-000000.json")
    values_path = os.path.join(tmpdir, "Test_values_00000000-000000.json")
    with open(formulas_path, "w", encoding="utf-8") as fh:
        json.dump(formulas_doc, fh)
    with open(values_path, "w", encoding="utf-8") as fh:
        json.dump(values_doc, fh)
    return formulas_path, values_path
