"""Writes Stage 2's two JSON Lines artifacts -- the column dependency
graph and the dangling sheet-name list -- from a Stage2Result. Same
`kind`-tagged-line convention stage3_artifacts.py/stage4_artifacts.py/
stage5_artifacts.py already set: one "meta" line first (stamp,
reliability condition, summary counts), then one line per content item,
then one line per residue entry -- so no line's meaning depends on
another line, or on its position in the file, to be understood.

Field names for the graph edges (sourceSheet/sourceColumn/targetSheet/
targetColumn/patterns/cells) and for the dangling-name entries and their
occurrences (name/classification/occurrences -> cell/rawFormula/
evaluatedValue) match this stage's own serialize_stage2.py, which already
established camelCase names for these exact fields, rather than inventing
new ones for the same data.

Two CSV projections, each decided by inspecting Stage2Result rather than
assumed in advance, following the two rules stage3/stage4/stage5's own
CSVs already established:

  - a plain list field with no further nested structure is reduced to a
    count in a one-row-per-entity CSV, exactly as stage4_sheet_summary.csv
    does for namedRanges/dataValidations/conditionalFormatRules/
    protectedRanges.
  - a nested one-to-many field whose children are themselves flat,
    multi-field records is projected at the CHILD's own granularity, with
    the parent's key denormalized onto each child row, exactly as
    stage4_column_summary.csv (sheet -> column) and stage5's two summary
    CSVs (table -> column, table -> label) already do.

`stage2_edge_summary.csv`: one row per graph edge -- (sourceSheet,
sourceColumn, targetSheet, targetColumn) already uniquely identifies an
edge, the same granularity as the JSONL's own "edge" lines, not a coarser
grouping of them. An edge's own `patterns`/`cells` are plain string
tuples with no further structure, so the first rule above applies:
patternCount/cellCount are carried here; the lists themselves stay
JSONL-only, exactly as stage3/stage4 already leave a column's own pattern
texts and spill-run detail JSONL-only while summarizing them as counts.

`stage2_dangling_occurrence_summary.csv`: one row per dangling
OCCURRENCE, not per dangling-name entry. A DanglingNameEntry itself has
only two scalar fields (name, classification); everything a reader would
act on -- which cell, what raw formula, what value at capture -- lives
one level down, on each DanglingOccurrence, itself a flat, three-field
record with no further nesting. Projecting at the entry level would
produce a row of little more than (name, classification, occurrenceCount)
and lose exactly the cell-level detail that is this artifact's entire
point; projecting at the occurrence level, with name and classification
denormalized onto each row, follows the second rule above and is the same
choice stage4_column_summary.csv and stage5's two summary CSVs already
made for their own child-record collections.
"""

import os
from typing import Any, Dict, Iterable, Tuple

from .jsonl_io import write_csv, write_jsonl
from .stage2 import DanglingNameArtifact, DependencyGraphArtifact, Stage2Result


def _residue_lines(residue) -> Iterable[Dict[str, Any]]:
    for r in residue:
        yield {
            "kind": "residue",
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }


def _graph_lines(graph: DependencyGraphArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "dependency_graph",
        "captureDate": graph.stamp.capture_date,
        "toolCommit": graph.stamp.tool_commit,
        "reliabilityCondition": graph.reliability_condition,
        "edgeCount": len(graph.edges),
        "residueCount": len(graph.residue),
    }
    for e in graph.edges:
        yield {
            "kind": "edge",
            "sourceSheet": e.source_sheet,
            "sourceColumn": e.source_column,
            "targetSheet": e.target_sheet,
            "targetColumn": e.target_column,
            "patterns": list(e.patterns),
            "cells": list(e.cells),
        }
    yield from _residue_lines(graph.residue)


def _dangling_lines(dangling: DanglingNameArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "dangling_names",
        "captureDate": dangling.stamp.capture_date,
        "toolCommit": dangling.stamp.tool_commit,
        "reliabilityCondition": dangling.reliability_condition,
        "entryCount": len(dangling.entries),
        "residueCount": len(dangling.residue),
    }
    for entry in dangling.entries:
        yield {
            "kind": "entry",
            "name": entry.name,
            "classification": entry.classification,
            "occurrences": [
                {"cell": o.cell, "rawFormula": o.raw_formula, "evaluatedValue": o.evaluated_value}
                for o in entry.occurrences
            ],
        }
    yield from _residue_lines(dangling.residue)


def _edge_summary_rows(graph: DependencyGraphArtifact) -> Iterable[Dict[str, Any]]:
    for e in graph.edges:
        yield {
            "sourceSheet": e.source_sheet,
            "sourceColumn": e.source_column,
            "targetSheet": e.target_sheet,
            "targetColumn": e.target_column,
            "patternCount": len(e.patterns),
            "cellCount": len(e.cells),
        }


_EDGE_SUMMARY_FIELDS: Tuple[str, ...] = (
    "sourceSheet", "sourceColumn", "targetSheet", "targetColumn", "patternCount", "cellCount",
)


def _dangling_occurrence_summary_rows(dangling: DanglingNameArtifact) -> Iterable[Dict[str, Any]]:
    for entry in dangling.entries:
        for o in entry.occurrences:
            yield {
                "name": entry.name,
                "classification": entry.classification,
                "cell": o.cell,
                "rawFormula": o.raw_formula,
                "evaluatedValue": o.evaluated_value,
            }


_DANGLING_OCCURRENCE_SUMMARY_FIELDS: Tuple[str, ...] = (
    "name", "classification", "cell", "rawFormula", "evaluatedValue",
)


def write_stage2_artifacts(result: Stage2Result, output_dir: str) -> Dict[str, str]:
    """Writes stage2_dependency_graph.jsonl, stage2_dangling_names.jsonl,
    stage2_edge_summary.csv (DERIVED, regenerable -- see
    _edge_summary_rows), and stage2_dangling_occurrence_summary.csv
    (DERIVED, regenerable -- see _dangling_occurrence_summary_rows) into
    `output_dir`. Returns the paths written, keyed by artifact name."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "dependency_graph": os.path.join(output_dir, "stage2_dependency_graph.jsonl"),
        "dangling_names": os.path.join(output_dir, "stage2_dangling_names.jsonl"),
        "edge_summary_csv": os.path.join(output_dir, "stage2_edge_summary.csv"),
        "dangling_occurrence_summary_csv": os.path.join(output_dir, "stage2_dangling_occurrence_summary.csv"),
    }
    write_jsonl(paths["dependency_graph"], _graph_lines(result.graph))
    write_jsonl(paths["dangling_names"], _dangling_lines(result.dangling))
    write_csv(paths["edge_summary_csv"], _EDGE_SUMMARY_FIELDS, _edge_summary_rows(result.graph))
    write_csv(
        paths["dangling_occurrence_summary_csv"],
        _DANGLING_OCCURRENCE_SUMMARY_FIELDS,
        _dangling_occurrence_summary_rows(result.dangling),
    )
    return paths
