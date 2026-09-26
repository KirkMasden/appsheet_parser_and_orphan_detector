"""Writes Stage 5's JSON Lines join artifact and its flat CSV projections
from a Stage5Result -- same `kind`-tagged-line convention stages 3 and 4
set. Two CSV projections, both genuinely one-to-one:

  - `stage5_column_summary.csv`: one row per app-side column (every field
    on a ColumnMatchResult is scalar -- table, column, virtuality, state,
    and the single matched name where there is exactly one; a collision's
    2+ candidates are joined into one display string, marked as such, and
    the JSONL remains the authoritative source for the list itself).
  - `stage5_label_summary.csv`: one row per stage-4-identified header
    label, same shape mirrored for the label direction.

Diagnostics stay JSONL-only: a diagnostic entry's own found/not-found
name lists are one-to-many.
"""

import os
from typing import Any, Dict, Iterable, Tuple

from .jsonl_io import write_csv, write_jsonl
from .stage5 import JoinArtifact, Stage5Result


def _residue_lines(residue) -> Iterable[Dict[str, Any]]:
    for r in residue:
        yield {
            "kind": "residue",
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }


def _column_result_out(c) -> Dict[str, Any]:
    return {
        "column": c.column,
        "isVirtual": c.is_virtual,
        "state": c.state,
        "matchedSheetColumn": c.matched_sheet_column,
        "matchedLabelText": c.matched_label_text,
        "nearMissCandidates": list(c.near_miss_candidates),
    }


def _label_result_out(l) -> Dict[str, Any]:
    return {
        "sheetColumn": l.sheet_column,
        "labelText": l.label_text,
        "state": l.state,
        "matchedAppColumn": l.matched_app_column,
        "nearMissCandidates": list(l.near_miss_candidates),
    }


def _diagnostic_out(d) -> Dict[str, Any]:
    return {
        "kind": "diagnostic",
        "table": d.table,
        "tab": d.tab,
        "headerVerdict": d.header_verdict,
        "candidateRow1": d.candidate_row1,
        "appColumnCount": d.app_column_count,
        "appColumnsFound": list(d.app_columns_found),
        "appColumnsNotFound": list(d.app_columns_not_found),
        "row1NonemptyCount": d.row1_nonempty_count,
        "row1ExactMatches": list(d.row1_exact_matches),
        "row1NearMisses": [{"row1Value": a, "appColumn": b} for a, b in d.row1_near_misses],
        "row1Unmatched": list(d.row1_unmatched),
    }


def _provenance_out(p) -> Dict[str, Any]:
    if p is None:
        return None
    return {
        "appsideParseDir": p.appside_parse_dir,
        "appIdentity": {
            "ogTitle": p.app_identity.og_title,
            "version": p.app_identity.version,
            "defaultAppFolder": p.app_identity.default_app_folder,
            "htmlMtimeIso": p.app_identity.html_mtime_iso,
        },
        "inputFileHashes": dict(p.input_file_hashes),
        "captureDate": p.capture_date,
        "exportToCaptureGapDays": p.export_to_capture_gap_days,
    }


def _join_lines(join: JoinArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "appsheet_sheet_join",
        "present": join.present,
        "captureDate": join.stamp.capture_date,
        "toolCommit": join.stamp.tool_commit,
        "reliabilityCondition": join.reliability_condition,
        "provenance": _provenance_out(join.provenance),
        "virtualFieldPresent": join.virtual_field_present,
        "tabPairing": join.tab_pairing,
        "tabPairingNote": join.tab_pairing_note,
        "tableCount": len(join.tables),
        "diagnosticCount": len(join.diagnostics),
        "residueCount": len(join.residue),
    }
    for t in join.tables:
        yield {
            "kind": "table",
            "table": t.table,
            "tableState": t.table_state,
            "matchedTab": t.matched_tab,
            "tabSource": t.tab_source,
            "sourceWorksheet": t.source_worksheet,
            "headerVerdict": t.header_verdict,
            "headerSource": t.header_source,
            "columns": [_column_result_out(c) for c in t.column_results],
            "labels": [_label_result_out(l) for l in t.label_results],
        }
    for d in join.diagnostics:
        yield _diagnostic_out(d)
    yield from _residue_lines(join.residue)


def _column_summary_rows(join: JoinArtifact) -> Iterable[Dict[str, Any]]:
    for t in join.tables:
        for c in t.column_results:
            yield {
                "table": t.table,
                "column": c.column,
                "isVirtual": "" if c.is_virtual is None else ("Yes" if c.is_virtual else "No"),
                "state": c.state,
                "matchedName": c.matched_label_text or (
                    " | ".join(c.near_miss_candidates) if c.near_miss_candidates else ""
                ),
                "candidateCount": len(c.near_miss_candidates),
            }


_COLUMN_SUMMARY_FIELDS: Tuple[str, ...] = ("table", "column", "isVirtual", "state", "matchedName", "candidateCount")


def _label_summary_rows(join: JoinArtifact) -> Iterable[Dict[str, Any]]:
    for t in join.tables:
        for l in t.label_results:
            yield {
                "table": t.table,
                "tab": t.matched_tab or "",
                "sheetColumn": l.sheet_column,
                "labelText": l.label_text,
                "state": l.state,
                "matchedName": l.matched_app_column or (
                    " | ".join(l.near_miss_candidates) if l.near_miss_candidates else ""
                ),
                "candidateCount": len(l.near_miss_candidates),
            }


_LABEL_SUMMARY_FIELDS: Tuple[str, ...] = ("table", "tab", "sheetColumn", "labelText", "state", "matchedName", "candidateCount")


def write_stage5_artifacts(result: Stage5Result, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "join": os.path.join(output_dir, "stage5_join.jsonl"),
        "column_summary_csv": os.path.join(output_dir, "stage5_column_summary.csv"),
        "label_summary_csv": os.path.join(output_dir, "stage5_label_summary.csv"),
    }
    write_jsonl(paths["join"], _join_lines(result.join))
    write_csv(paths["column_summary_csv"], _COLUMN_SUMMARY_FIELDS, _column_summary_rows(result.join))
    write_csv(paths["label_summary_csv"], _LABEL_SUMMARY_FIELDS, _label_summary_rows(result.join))
    return paths
