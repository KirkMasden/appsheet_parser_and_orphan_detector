"""Tiny synthetic captures for tests. No real capture data anywhere here --
the public repo's test suite must run for anyone, without Kirk's private
workbook. Deliberately uses sheet names unlike Kirk's own capture, since
sheet names may appear in tests but must never appear in tool logic; using
different names here helps confirm that.
"""

import csv
import json
import os
import tempfile
from typing import List, Tuple

CAPTURE_DATE = "2099-01-01T00:00:00.000Z"


def _minimal_formulas_sheet(
    name: str, formulas, number_formats=None, frozen_rows=0, frozen_columns=0,
    named_ranges=None, data_validations=None, conditional_format_rules=None, protected_ranges=None,
):
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
        "namedRanges": named_ranges if named_ranges is not None else [],
        "dataValidations": data_validations if data_validations is not None else [],
        "conditionalFormatRules": conditional_format_rules if conditional_format_rules is not None else [],
        "protectedRanges": protected_ranges if protected_ranges is not None else [],
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


def build_stage4_pair() -> Tuple[dict, dict]:
    """A small synthetic capture exercising Stage 4's header-detection
    rule -- corrected 2026-09-09 to disqualify a spilling COLUMN rather
    than veto the whole ROW, and to require a majority (not just a
    nonzero count) of informative columns before asserting IDENTIFIED --
    and the four-state header-label field. Sheet/column layout is
    invented, unlike Kirk's own capture, per this file's own convention.

      "Ledger" (4 rows x 5 cols): IDENTIFIED via the positive (type-
      mismatch) signal alone, no spills at all -- row 1 holds text over
      numeric columns A, B, D (3 of 3 informative, comfortably above the
      majority threshold). Also exercises: a duplicate label (A1 and B1
      both "Qty"), a blank header cell (C1) -> no-label-in-identified-
      header, a fully empty column (E, no formula or value anywhere) ->
      the stage-3-profile-absent fallback path, and named ranges / data
      validations / conditional format rules / protected ranges
      pass-through.
      "MixedHeaderSheet" (3 rows x 5 cols): THE CENTRAL CASE THE VETO GOT
      WRONG, at fixture scale -- 4 of 5 columns (A-D) are genuine typed
      text labels over numeric bodies, and 1 column (E) holds a formula at
      row 1 whose row 2 cell is a bare value with no formula (a governing
      downward spill). Under the corrected rule, E is excluded from the
      row's own verdict and reports SPILL_ORIGIN_NOT_LABEL; the row is
      IDENTIFIED on the strength of A-D alone (4 of 4 informative, 100%,
      comfortably above the majority threshold) -- exactly the shape this
      workbook's own Collate turned out to have (a handful of spilling
      columns among a majority of plain labels).
      "AllSpillSheet" (3 rows x 3 cols): every column's row 1 cell is a
      spill origin -- nothing remains to judge the row by once each column
      is excluded, so the row is confidently data (NOT-IDENTIFIED-
      CONFIDENT is now a UNANIMOUS finding, not a one-column veto), and
      every column reports SPILL_ORIGIN_NOT_LABEL.
      "SpillSheet" (4 rows x 4 cols): a smaller mixed case -- column A
      spills and is excluded; columns B and C independently show the
      positive signal (2 of 2 informative, 100%), so the row is now
      IDENTIFIED under the corrected rule (it was NOT-IDENTIFIED-CONFIDENT
      under the superseded whole-row veto -- kept as a regression fixture
      for that exact change). Also carries a duplicate label (B1 and C1
      both "Dup") to exercise duplicate detection running independently of
      the header verdict.
      "UndeterminedSheet" (2 rows x 2 cols): a signal WAS measurable but
      found nothing -- column A's row 1 value matches its body's own type
      (numeric over numeric: 0 of 1 informative column shows the
      mismatch, confidence 0.0, not None), column B is empty throughout,
      and no formula exists anywhere in row 1.
      "NoSignalSheet" (2 rows x 2 cols): NO signal was even measurable --
      every column's row 1 cell is blank, so there is nothing to compare
      against any column's body type at all (0 informative columns,
      confidence None) -- deliberately distinct from UndeterminedSheet's
      "measured, found nothing" case above.
      "DeclaredSheet" (4 rows x 2 cols): row 1 sits EXACTLY AT the
      majority threshold under measured detection (1 of 2 informative
      columns, 50% -- not a majority, so UNDETERMINED, not identified,
      under the corrected rule) -- so declaring row 2 as the true header
      row is a real override of a real (if boundary-case) measured
      result, not a no-op, when the declarations mechanism is exercised
      against this fixture.
    """
    ledger_formulas = [
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
    ]
    ledger_values = [
        ["Qty", "Qty", "", "Price", ""],
        [1, 2, 3, 4, ""],
        [5, 6, 7, 8, ""],
        [9, 10, 11, 12, ""],
    ]

    mixed_header_formulas = [
        ["", "", "", "", "=500"],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
    ]
    mixed_header_values = [
        ["ColA", "ColB", "ColC", "ColD", 500],
        [1, 3, 5, 7, 999],
        [2, 4, 6, 8, ""],
    ]

    all_spill_formulas = [
        ["=1", "=2", "=3"],
        ["", "", ""],
        ["", "", ""],
    ]
    all_spill_values = [
        [1, 2, 3],
        [9, 9, 9],
        ["", "", ""],
    ]

    spill_formulas = [
        ["=100", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
    ]
    spill_values = [
        [100, "Dup", "Dup", ""],
        [999, 1, 2, 3],
        ["", 4, 5, 6],
        ["", 7, 8, 9],
    ]

    undetermined_formulas = [
        ["", ""],
        ["", ""],
    ]
    undetermined_values = [
        [1, ""],
        [2, ""],
    ]

    no_signal_formulas = [
        ["", ""],
        ["", ""],
    ]
    no_signal_values = [
        ["", ""],
        [5, "x"],
    ]

    declared_formulas = [
        ["", ""],
        ["", ""],
        ["", ""],
        ["", ""],
    ]
    declared_values = [
        ["junk1", "junk2"],
        ["Name", "Age"],
        ["Alice", 30],
        ["Bob", 40],
    ]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage4 Test Workbook",
        "triggerIds": [],
        "sheets": [
            _minimal_formulas_sheet(
                "Ledger", ledger_formulas,
                named_ranges=[{"name": "QtyRange", "range": "A2:A4"}],
                data_validations=[{"range": "A1", "rule": "TEXT_IS_NOT_EMPTY"}],
                conditional_format_rules=[{"range": "D2:D4", "rule": "NUMBER_GREATER"}],
                protected_ranges=[{"range": "A1:E1", "description": "header"}],
            ),
            _minimal_formulas_sheet("MixedHeaderSheet", mixed_header_formulas),
            _minimal_formulas_sheet("AllSpillSheet", all_spill_formulas),
            _minimal_formulas_sheet("SpillSheet", spill_formulas),
            _minimal_formulas_sheet("UndeterminedSheet", undetermined_formulas),
            _minimal_formulas_sheet("NoSignalSheet", no_signal_formulas),
            _minimal_formulas_sheet("DeclaredSheet", declared_formulas),
        ],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage4 Test Workbook",
        "sheets": [
            _minimal_values_sheet("Ledger", ledger_values),
            _minimal_values_sheet("MixedHeaderSheet", mixed_header_values),
            _minimal_values_sheet("AllSpillSheet", all_spill_values),
            _minimal_values_sheet("SpillSheet", spill_values),
            _minimal_values_sheet("UndeterminedSheet", undetermined_values),
            _minimal_values_sheet("NoSignalSheet", no_signal_values),
            _minimal_values_sheet("DeclaredSheet", declared_values),
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


def write_declarations(tmpdir: str, header_row_overrides: dict) -> str:
    """Writes a minimal declarations file (design section 8) -- only the
    header-row-override key any stage currently reads."""
    path = os.path.join(tmpdir, "declarations.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"headerRowOverrides": header_row_overrides}, fh)
    return path


def build_stage5_pair() -> Tuple[dict, dict]:
    """A synthetic capture exercising Stage 5's join, matched against
    `build_stage5_appside_rows()` below. Sheet/column layout is invented,
    unlike Kirk's own capture, per this file's own convention.

      "Ledger" (4 rows x 10 cols): IDENTIFIED header (9 of 9 informative
      columns show the type-mismatch signal; column G is blank and
      contributes nothing). Exercises, against the app-side "Ledger"
      table:
        A "Qty", B "Price"        -> exact match, both directions
        C "OldName"               -> label with no app-side counterpart -> unmatched
        D "Dup", E "Dup"          -> the SAME text at two columns -> label-repeated-
                                     within-tab at both; the app-side "Dup" column
                                     matches the repeated text and is reported
                                     unmatched (ambiguous), not exact
        F "Trailing Space "       -> whitespace near-miss against app column
                                     "Trailing Space" (clean, one candidate each way)
        G ""                      -> no label; outside the join's concern entirely
        H "Odd   Name" (3 spaces) -> whitespace-collapses the same as app columns
                                     "Odd  Name" (2 spaces) AND "Odd Name" (1 space)
                                     -> a LABEL-side collision (two distinct app
                                     columns, one collapsed form)
        I "Foo  Bar" (2 spaces), J "Foo Bar" (1 space) -> two DISTINCT labels (not a
                                     repeated pair -- the raw text differs) that both
                                     collapse the same as app column "Foo   Bar"
                                     (3 spaces) -> a COLUMN-side collision

      "Murky" (3 rows x 2 cols): UNDETERMINED header (row 1's text matches
      its own body's type in both columns, informative but zero
      mismatch) -- exercises the undetermined-diagnostic path and the
      tab-header-not-identified column state.
    """
    ledger_formulas = [["" for _ in range(10)] for _ in range(4)]
    ledger_values = [
        ["Qty", "Price", "OldName", "Dup", "Dup", "Trailing Space ", "", "Odd   Name", "Foo  Bar", "Foo Bar"],
        [10, 11, 12, 13, 14, 15, "", 16, 17, 18],
        [20, 21, 22, 23, 24, 25, "", 26, 27, 28],
        [30, 31, 32, 33, 34, 35, "", 36, 37, 38],
    ]

    murky_formulas = [["", ""], ["", ""], ["", ""]]
    murky_values = [
        ["Name", "Amount"],
        ["Alice", "Cash"],
        ["Bob", "Cash"],
    ]

    formulas_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage5 Test Workbook",
        "triggerIds": [],
        "sheets": [
            _minimal_formulas_sheet("Ledger", ledger_formulas),
            _minimal_formulas_sheet("Murky", murky_formulas),
        ],
    }
    values_doc = {
        "captureDate": CAPTURE_DATE,
        "spreadsheetName": "Stage5 Test Workbook",
        "sheets": [
            _minimal_values_sheet("Ledger", ledger_values),
            _minimal_values_sheet("Murky", murky_values),
        ],
    }
    return formulas_doc, values_doc


def build_stage5_appside_rows() -> List[dict]:
    """Rows for a synthetic `appsheet_columns.csv`, matched against
    `build_stage5_pair()` above. See that function's own docstring for
    what each row is designed to exercise. Table "Ghost" matches no tab
    in the capture at all."""
    rows = []

    def add(table, column, is_virtual="No"):
        rows.append({"table_name": table, "column_name": column, "is_virtual": is_virtual})

    add("Ledger", "Qty")
    add("Ledger", "Price")
    add("Ledger", "Renamed")
    add("Ledger", "VirtualThing", is_virtual="Yes")
    add("Ledger", "Dup")
    add("Ledger", "Trailing Space")
    add("Ledger", "Odd  Name")   # 2 spaces
    add("Ledger", "Odd Name")    # 1 space
    add("Ledger", "Foo   Bar")   # 3 spaces

    add("Murky", "Name")
    add("Murky", "Amount")
    add("Murky", "Extra")

    add("Ghost", "GhostCol1")
    add("Ghost", "GhostCol2", is_virtual="Yes")

    return rows


def write_appside_columns_csv(tmpdir: str, rows: List[dict], include_is_virtual: bool = True) -> str:
    """Writes a minimal `appsheet_columns.csv` -- just the two or three
    fields Stage 5 actually reads (`table_name`, `column_name`, and
    `is_virtual` unless `include_is_virtual` is False, which exercises
    the missing-field residue path)."""
    fieldnames = ["table_name", "column_name"] + (["is_virtual"] if include_is_virtual else [])
    path = os.path.join(tmpdir, "appsheet_columns.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    return path
