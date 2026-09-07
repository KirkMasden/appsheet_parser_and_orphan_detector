/**
 * sheet_capture.gs — AppSheet Sheets-Side Capture (Phase II, session 1)
 *
 * Captures a Google Sheets workbook RAW, for every sheet: formulas, raw
 * values, named ranges, data validation rules, conditional format rules,
 * number formats, frozen rows/columns, and protected ranges. Also records
 * the capture date and the IDs of this script project's own triggers.
 *
 * This script derives NOTHING. No deduplication, no reference extraction,
 * no schema, no dependency graph, no rationing. Every value below is a
 * direct, 1:1 transcription of what the SpreadsheetApp object model
 * exposes for a cell, range, or rule — never a summary or an inference
 * about what that value means. Where the object model hands back a
 * non-JSON-serializable handle (a Range, a Sheet, a User), it is
 * converted to its raw address (A1 notation, sheet name, email) rather
 * than resolved into anything more meaningful. That is the only kind of
 * "interpretation" in this file, and it exists solely so JSON.stringify
 * has something serializable to write — see RELEASE_CHECKLIST.md's
 * "ARCHITECTURE DECIDED 2026-09-07" block, decision 1, and Addendum 8 of
 * the project record ("the dump script itself does no deriving").
 *
 * OUTPUT: two separate JSON files per capture, written to a Drive folder
 * named "sheet_dumps" (created at Drive root if absent):
 *   <spreadsheet name>_formulas_<YYYYMMDD-HHmmss>.json  — formulas plus
 *     every other structural property this script captures (named
 *     ranges, validation, conditional formatting, number formats, frozen
 *     panes, protected ranges, capture date, trigger IDs).
 *   <spreadsheet name>_values_<YYYYMMDD-HHmmss>.json  — sheet name and
 *     raw values only, so it can be shared or withheld independently of
 *     the formula file.
 * Trigger IDs are recorded once, on the formulas file only (it is the
 * "everything else" file; the values file stays minimal by design).
 *
 * WHOLE-WORKBOOK VS. PER-SHEET, AND WHY: captureWorkbook() below loops
 * over every sheet in a single execution and is the normal entry point.
 * Apps Script enforces a per-execution time limit (about 6 minutes on
 * most accounts), and whether a whole-workbook capture of a workbook
 * this size fits under it has not been tested (open question, Addendum
 * 8). Rather than guess with sampling or a partial capture — explicitly
 * ruled out — every per-sheet capture step below is its own function
 * (buildSheetFormulaRecord_, buildSheetValuesRecord_), and
 * captureOneSheetToFiles(sheetNameOrIndex) is a second entry point that
 * runs just one sheet through the same functions and writes its own pair
 * of files. If a whole-workbook run risks or hits the time limit, call
 * captureOneSheetToFiles() once per sheet instead; every field captured
 * for a sheet in the whole-workbook run is captured identically when
 * that sheet is run alone — this is chunking the same capture across
 * more executions, not a reduced one.
 *
 * KNOWN CAPTURE GAP, DECLARED RATHER THAN PAPERED OVER: SpreadsheetApp's
 * ConditionalFormatRule exposes the rule's range(s) and its condition
 * (boolean or gradient) but has no getter for the format it applies —
 * background, font color, bold, and so on are settable only through the
 * builder, not readable back from an existing rule through this service.
 * Reading them would need the Sheets REST API, out of scope here. Every
 * captured conditional-format-rule entry below carries a fixed
 * "formatNote" field saying so, per this project's residue-declaring
 * convention (RELEASE_CHECKLIST.md, "ARCHITECTURE DECIDED 2026-09-07",
 * decision 3) — so a reader of the JSON is told what is missing rather
 * than left to assume the format was captured and is simply empty.
 */

var SHEET_DUMPS_FOLDER_NAME = 'sheet_dumps';

var CONDITIONAL_FORMAT_RULE_FORMAT_NOTE =
  'SpreadsheetApp.ConditionalFormatRule exposes the condition (range(s), ' +
  'boolean or gradient criteria) but not the applied visual format ' +
  '(background/font color/bold/etc.) — that has no getter in this ' +
  'service and would need the Sheets REST API. Not captured.';

/**
 * Main entry point: captures every sheet in the active spreadsheet and
 * writes the two output files. Run this manually from the Apps Script
 * editor, or wire it to a trigger.
 */
function captureWorkbook() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var captureDate = new Date().toISOString();
  var sheets = ss.getSheets();

  var formulaDoc = {
    captureDate: captureDate,
    spreadsheetName: ss.getName(),
    triggerIds: listOwnTriggerIds_(),
    sheets: []
  };
  var valuesDoc = {
    captureDate: captureDate,
    spreadsheetName: ss.getName(),
    sheets: []
  };

  for (var i = 0; i < sheets.length; i++) {
    var sheet = sheets[i];
    formulaDoc.sheets.push(buildSheetFormulaRecord_(ss, sheet));
    valuesDoc.sheets.push(buildSheetValuesRecord_(sheet));
  }

  var folder = getOrCreateDumpsFolder_();
  writeJsonToDrive_(folder, buildFilename_(ss.getName(), 'formulas', captureDate), formulaDoc);
  writeJsonToDrive_(folder, buildFilename_(ss.getName(), 'values', captureDate), valuesDoc);

  Logger.log('Captured %s sheet(s) from "%s".', sheets.length, ss.getName());
}

/**
 * Fallback entry point for one sheet at a time, when a whole-workbook run
 * risks the execution time limit. Same capture functions as
 * captureWorkbook(); writes its own pair of files, named with the sheet
 * name inserted so they do not collide with a whole-workbook capture's
 * files or with another sheet's fallback files.
 *
 * @param {string|number} sheetNameOrIndex Sheet name, or a zero-based
 *   index into getSheets().
 */
function captureOneSheetToFiles(sheetNameOrIndex) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = resolveSheet_(ss, sheetNameOrIndex);
  var captureDate = new Date().toISOString();

  var formulaDoc = {
    captureDate: captureDate,
    spreadsheetName: ss.getName(),
    triggerIds: listOwnTriggerIds_(),
    sheets: [buildSheetFormulaRecord_(ss, sheet)]
  };
  var valuesDoc = {
    captureDate: captureDate,
    spreadsheetName: ss.getName(),
    sheets: [buildSheetValuesRecord_(sheet)]
  };

  var folder = getOrCreateDumpsFolder_();
  writeJsonToDrive_(
    folder,
    buildFilename_(ss.getName(), 'formulas', captureDate, sheet.getName()),
    formulaDoc
  );
  writeJsonToDrive_(
    folder,
    buildFilename_(ss.getName(), 'values', captureDate, sheet.getName()),
    valuesDoc
  );

  Logger.log('Captured sheet "%s" from "%s".', sheet.getName(), ss.getName());
}

// ---------------------------------------------------------------------
// Per-sheet capture
// ---------------------------------------------------------------------

function buildSheetFormulaRecord_(ss, sheet) {
  var maxRows = sheet.getMaxRows();
  var maxCols = sheet.getMaxColumns();
  var fullRange = sheet.getRange(1, 1, maxRows, maxCols);

  return {
    sheetName: sheet.getName(),
    rowCount: maxRows,
    columnCount: maxCols,
    formulas: fullRange.getFormulas(),
    namedRanges: namedRangesForSheet_(ss, sheet),
    dataValidations: dataValidationsForSheet_(fullRange),
    conditionalFormatRules: conditionalFormatRulesForSheet_(sheet),
    numberFormats: fullRange.getNumberFormats(),
    frozenRows: sheet.getFrozenRows(),
    frozenColumns: sheet.getFrozenColumns(),
    protectedRanges: protectedRangesForSheet_(sheet)
  };
}

function buildSheetValuesRecord_(sheet) {
  var maxRows = sheet.getMaxRows();
  var maxCols = sheet.getMaxColumns();
  var fullRange = sheet.getRange(1, 1, maxRows, maxCols);

  return {
    sheetName: sheet.getName(),
    values: fullRange.getValues()
  };
}

/**
 * Named ranges are a spreadsheet-level construct, not a sheet-level one,
 * but each one's range sits on exactly one sheet — filtered here to the
 * sheet passed in, per this script's FILE 1 layout (named ranges nested
 * under each sheet's own entry). Filtering by the range's own sheet ID
 * is not a judgment call: it is an intrinsic property of the named
 * range, not something this script infers.
 */
function namedRangesForSheet_(ss, sheet) {
  var all = ss.getNamedRanges();
  var result = [];
  for (var i = 0; i < all.length; i++) {
    var nr = all[i];
    var range = nr.getRange();
    if (range.getSheet().getSheetId() === sheet.getSheetId()) {
      result.push({
        name: nr.getName(),
        sheetName: range.getSheet().getName(),
        a1Notation: range.getA1Notation()
      });
    }
  }
  return result;
}

/**
 * getDataValidations() returns a dense grid the same shape as the sheet,
 * mostly null. Reported here as a sparse list of only the cells that
 * carry a rule, which loses no occurrence — every non-null cell in the
 * dense grid appears once below — while not writing out a mostly-empty
 * grid the size of the whole sheet twice (once for formulas, once here).
 */
function dataValidationsForSheet_(range) {
  var grid = range.getDataValidations();
  var result = [];
  for (var r = 0; r < grid.length; r++) {
    for (var c = 0; c < grid[r].length; c++) {
      var rule = grid[r][c];
      if (rule) {
        result.push({
          row: r + 1,
          column: c + 1,
          criteriaType: rule.getCriteriaType().toString(),
          criteriaValues: sanitizeCriteriaValues_(rule.getCriteriaValues()),
          allowInvalid: rule.getAllowInvalid(),
          helpText: rule.getHelpText()
        });
      }
    }
  }
  return result;
}

function conditionalFormatRulesForSheet_(sheet) {
  var rules = sheet.getConditionalFormatRules();
  var result = [];
  for (var i = 0; i < rules.length; i++) {
    var rule = rules[i];
    var rangesA1 = [];
    var ranges = rule.getRanges();
    for (var j = 0; j < ranges.length; j++) {
      rangesA1.push(ranges[j].getA1Notation());
    }

    var entry = {
      ranges: rangesA1,
      formatNote: CONDITIONAL_FORMAT_RULE_FORMAT_NOTE
    };

    var boolCond = rule.getBooleanCondition();
    if (boolCond) {
      entry.conditionKind = 'boolean';
      entry.criteriaType = boolCond.getCriteriaType().toString();
      entry.criteriaValues = sanitizeCriteriaValues_(boolCond.getCriteriaValues());
    }

    var gradCond = rule.getGradientCondition();
    if (gradCond) {
      entry.conditionKind = 'gradient';
      entry.minColorType = gradCond.getMinType() ? gradCond.getMinType().toString() : null;
      entry.minColorValue = gradCond.getMinValue();
      entry.minColor = colorObjectToRaw_(gradCond.getMinColorObject());
      entry.midColorType = gradCond.getMidType() ? gradCond.getMidType().toString() : null;
      entry.midColorValue = gradCond.getMidValue();
      entry.midColor = colorObjectToRaw_(gradCond.getMidColorObject());
      entry.maxColorType = gradCond.getMaxType() ? gradCond.getMaxType().toString() : null;
      entry.maxColorValue = gradCond.getMaxValue();
      entry.maxColor = colorObjectToRaw_(gradCond.getMaxColorObject());
    }

    result.push(entry);
  }
  return result;
}

function protectedRangesForSheet_(sheet) {
  var result = [];
  var types = [SpreadsheetApp.ProtectionType.RANGE, SpreadsheetApp.ProtectionType.SHEET];

  for (var t = 0; t < types.length; t++) {
    var protections = sheet.getProtections(types[t]);
    for (var i = 0; i < protections.length; i++) {
      var p = protections[i];
      var entry = {
        protectionType: types[t].toString(),
        description: p.getDescription()
      };

      try {
        entry.rangeA1 = (types[t] === SpreadsheetApp.ProtectionType.RANGE)
          ? p.getRange().getA1Notation()
          : null;
      } catch (rangeErr) {
        entry.rangeA1 = null;
        entry.rangeCaptureError = rangeErr.message;
      }

      try {
        var editors = p.getEditors();
        var emails = [];
        for (var e = 0; e < editors.length; e++) {
          emails.push(editors[e].getEmail());
        }
        entry.editors = emails;
      } catch (editorsErr) {
        entry.editors = null;
        entry.editorsCaptureError = editorsErr.message;
      }

      result.push(entry);
    }
  }

  return result;
}

/**
 * getCriteriaValues() can include a Range object (e.g. "value in range"
 * validation rules) alongside plain values. A Range cannot be
 * JSON.stringify'd meaningfully, so it is converted to its A1 address
 * here — the same raw-address treatment applied to named ranges and
 * protected ranges above, not a resolution of what the range contains.
 */
function sanitizeCriteriaValues_(values) {
  var out = [];
  for (var i = 0; i < values.length; i++) {
    var v = values[i];
    if (v && typeof v.getA1Notation === 'function') {
      out.push({
        rangeA1: v.getA1Notation(),
        rangeSheet: (typeof v.getSheet === 'function') ? v.getSheet().getName() : null
      });
    } else {
      out.push(v);
    }
  }
  return out;
}

/**
 * A gradient condition's min/mid/max color can be an RGB color or a
 * theme color (Color.getColorType()), and mid is optional (null when
 * unset). Reported as raw as each type allows — hex for RGB, the theme
 * color's own enum name for a theme color — rather than assuming RGB
 * and letting a theme-colored rule throw.
 */
function colorObjectToRaw_(colorObject) {
  if (!colorObject) {
    return null;
  }
  var colorType = colorObject.getColorType().toString();
  if (colorType === 'RGB') {
    return { colorType: colorType, hex: colorObject.asRgbColor().asHexString() };
  }
  if (colorType === 'THEME') {
    return { colorType: colorType, themeColor: colorObject.asThemeColor().getThemeColorType().toString() };
  }
  return { colorType: colorType };
}

function resolveSheet_(ss, sheetNameOrIndex) {
  if (typeof sheetNameOrIndex === 'number') {
    var sheets = ss.getSheets();
    if (sheetNameOrIndex < 0 || sheetNameOrIndex >= sheets.length) {
      throw new Error('Sheet index out of range: ' + sheetNameOrIndex);
    }
    return sheets[sheetNameOrIndex];
  }
  var sheet = ss.getSheetByName(sheetNameOrIndex);
  if (!sheet) {
    throw new Error('No sheet named "' + sheetNameOrIndex + '"');
  }
  return sheet;
}

// ---------------------------------------------------------------------
// Spreadsheet-level capture
// ---------------------------------------------------------------------

/**
 * IDs only, per the architecture decision — this script does not inspect
 * what a trigger does or which function it calls.
 */
function listOwnTriggerIds_() {
  var triggers = ScriptApp.getProjectTriggers();
  var ids = [];
  for (var i = 0; i < triggers.length; i++) {
    ids.push(triggers[i].getUniqueId());
  }
  return ids;
}

// ---------------------------------------------------------------------
// Drive output
// ---------------------------------------------------------------------

function getOrCreateDumpsFolder_() {
  var root = DriveApp.getRootFolder();
  var existing = root.getFoldersByName(SHEET_DUMPS_FOLDER_NAME);
  if (existing.hasNext()) {
    return existing.next();
  }
  return root.createFolder(SHEET_DUMPS_FOLDER_NAME);
}

function writeJsonToDrive_(folder, filename, obj) {
  folder.createFile(filename, JSON.stringify(obj, null, 2), 'application/json');
}

/**
 * <spreadsheet name>_<kind>_<sheet name, only for the per-sheet fallback>
 * _<YYYYMMDD-HHmmss>.json
 */
function buildFilename_(spreadsheetName, kind, isoCaptureDate, optionalSheetName) {
  var stamp = formatTimestampForFilename_(isoCaptureDate);
  var parts = [spreadsheetName, kind];
  if (optionalSheetName) {
    parts.push(optionalSheetName);
  }
  parts.push(stamp);
  return parts.join('_') + '.json';
}

function formatTimestampForFilename_(isoString) {
  var d = new Date(isoString);
  var pad = function (n) {
    return (n < 10 ? '0' : '') + n;
  };
  return '' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) +
    '-' + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}
