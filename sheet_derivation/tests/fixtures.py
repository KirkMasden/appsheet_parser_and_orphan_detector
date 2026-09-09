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


def build_stage1_pair() -> Tuple[dict, dict]:
    """A small synthetic capture exercising Stage 1's token classes and
    normalization decisions: string literals, quoted and bare sheet
    names, digit-in-identifier, error literals, $-anchored references,
    and a reference-shaped string that must NOT be treated as a
    reference. Sheet/function names are invented, unlike Kirk's own
    capture, per this file's own convention.

    Sheet "Ledger": one column (A) of formulas designed to produce a mix
    of distinct patterns, including one duplicated pattern (rows 1-2) and
    one pattern containing a digit-named function.
    Sheet "Other": referenced by Ledger, one formula of its own.
    """
    ledger_formulas = [
        ["=A1", "=Other!B1", "=CUSTOM2FUNC(A1)"],
        ["=A2", '="Other!B1"', "=#REF!"],
        ["=SUM($A$1:$A$2)", "='Odd '' Name'!C1", ""],
    ]
    other_formulas = [
        ["=1", "", ""],
    ]
    ledger_values = [[1, 2, 3], [4, 5, ""], [6, "", ""]]
    other_values = [[1, "", ""]]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage1 Test Workbook",
        "triggerIds": [],
        "sheets": [
            _minimal_formulas_sheet("Ledger", ledger_formulas),
            _minimal_formulas_sheet("Other", other_formulas),
        ],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage1 Test Workbook",
        "sheets": [
            _minimal_values_sheet("Ledger", ledger_values),
            _minimal_values_sheet("Other", other_values),
        ],
    }
    return formulas_doc, values_doc


def build_stage2_pair() -> Tuple[dict, dict]:
    """A small synthetic capture exercising Stage 2's reference-resolution
    decisions. Sheet/function names are invented, unlike Kirk's own
    capture, per this file's own convention.

    Sheet "Ledger": the main source sheet.
    Sheet "Archive": a SECOND source sheet whose column C carries the exact
      same Gate B pattern as Ledger column A/B -- this is the regression
      fixture for the bug where a pattern's source location was once read
      from only its first-found instance (`=Other!B#` occurs in
      Ledger!A1/A2, Ledger!B1, AND Archive!C1; each must produce its own
      edge, not just the first one found).
    Sheet "Other": the real cross-sheet target. Column C carries a value
      (no formula) used by the one-hop IMPORTRANGE-argument test.
    "Ghost Sheet" is referenced (quoted, for the space) but never captured
      -- the dangling name, exercised in both reference position and
      string-literal position.
    """
    ledger_formulas = [
        [
            "=Other!B1",
            "=Other!B1",
            "='Ghost Sheet'!D1",
            '="Other!B1"',
            "=\"'Ghost Sheet'!D1\"",
            "=ARRAYFORMULA(Other!B1:B2)",
        ],
        [
            "=Other!B2",
            "",
            "='Ghost Sheet'!D2",
            "",
            "",
            "=SUM(Other!B1:C2)",
        ],
        [
            '=INDIRECT("Other!B"&ROW())',
            '=IMPORTRANGE(Other!C1,"Vocab!A1:B2")',
            '=IMPORTRANGE("https://example.com/x","Vocab!A1:B2")',
            "",
            "",
            "",
        ],
    ]
    archive_formulas = [
        ["", "", "=Other!B1"],
    ]
    other_formulas = [
        ["=1", "=2", ""],
    ]

    ledger_values = [[1, 1, "", "Other!B1", "'Ghost Sheet'!D1", [1, 2]],
                      [2, "", "", "", "", ""],
                      ["", "", "", "", "", ""]]
    archive_values = [["", "", 1]]
    other_values = [[1, 2, "https://example.com/target"]]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage2 Test Workbook",
        "triggerIds": [],
        "sheets": [
            _minimal_formulas_sheet("Ledger", ledger_formulas),
            _minimal_formulas_sheet("Archive", archive_formulas),
            _minimal_formulas_sheet("Other", other_formulas),
        ],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage2 Test Workbook",
        "sheets": [
            _minimal_values_sheet("Ledger", ledger_values),
            _minimal_values_sheet("Archive", archive_values),
            _minimal_values_sheet("Other", other_values),
        ],
    }
    return formulas_doc, values_doc


def build_stage3_pair() -> Tuple[dict, dict]:
    """A small synthetic capture exercising Stage 3's column-profile
    classification and spill-assessment decisions. Sheet/column layout is
    invented, unlike Kirk's own capture, per this file's own convention.

    Sheet "Grid": one sheet, 4 rows x 9 columns (A-I), laid out so each
    column exercises exactly one Stage 3 decision:

      A: two distinct patterns ("=1" at rows 1,3; "=2+3" at row 2) -> multi-pattern.
      B: one pattern ("=100") filling rows 1-3 with no gap -> single-pattern-contiguous.
      C: one pattern ("=200") at rows 1, 2, 4 (row 3 empty) -> single-pattern-ragged.
      D: formula at row 1, value-only rows 2-3 immediately following -> spill run, gap 0.
      E: formula at row 1, row 2 empty, value-only row 3 -> spill run, gap 1.
      F: value-only row 1, row 2 empty, formula at row 3 -> no formula ABOVE the
         run, even though the column holds one elsewhere -> spill residue.
      G: value-only rows 1-3, no formula anywhere in the column -> spill residue,
         the Vertical-column-R shape (design section 3.2's own worked example),
         at fixture scale.
      H: one formula whose entire body is a ~3000-character string literal --
         the no-truncation regression fixture (design's own attested 2,844-
         character real formula).
      I: one formula containing a stray '?' (an UNKNOWN-classified span, per
         tokenizer.py) -- the inventory's own UNKNOWN-token residue path.
    """
    long_string_literal = '="' + ("A" * 3000) + '"'
    grid_formulas = [
        ["=1", "=100", "=200", "=300", "=400", "", "", long_string_literal, "=A1?"],
        ["=2+3", "=100", "=200", "", "", "", "", "", ""],
        ["=1", "=100", "", "", "", "=500", "", "", ""],
        ["", "", "=200", "", "", "", "", "", ""],
    ]
    grid_values = [
        [1, 100, 200, 300, 400, 7, 1, "placeholder", 0],
        [5, 100, 200, 5, "", "", 2, "", ""],
        [1, 100, "", 6, 9, 500, 3, "", ""],
        ["", "", 200, "", "", "", "", "", ""],
    ]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage3 Test Workbook",
        "triggerIds": [],
        "sheets": [_minimal_formulas_sheet("Grid", grid_formulas)],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage3 Test Workbook",
        "sheets": [_minimal_values_sheet("Grid", grid_values)],
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
