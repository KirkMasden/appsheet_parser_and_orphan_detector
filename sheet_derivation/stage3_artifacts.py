"""Writes Stage 3's two JSON Lines artifacts and one flat CSV projection
(design section 4's "Output format, decided 2026-09-09") from a
Stage3Result. Kept separate from stage3.py itself, which only computes the
result -- this module's only job is turning that result into files.

Each JSONL file mixes three kinds of self-contained line, distinguished by
a `kind` field, so that a reader (or a script) can tell them apart without
positional assumptions:

  - one `kind: "meta"` line, first, carrying the artifact's stamp
    (captureDate, tool commit) and its reliability condition -- design
    section 6's "what the whole file's reliability rests on", stated once;
  - the content lines (`kind: "pattern"` for the inventory, `kind:
    "column"` for the column-profile file), each carrying everything
    design section 4.1 (or this build's own column-profile extension)
    requires and nothing that depends on another line to be understood;
  - the `kind: "residue"` lines, one per ResidueEntry, each naming its own
    locations -- so a residue line's meaning never depends on which
    content line happens to sit near it in the file.

This shape was chosen, rather than a bare array of content items with the
stamp/condition/residue held only in a companion file, because the design
decision itself requires "no item depends on a separate file to be
understood" (section 4) while ALSO requiring every artifact to carry a
stamp, a reliability condition, and residue (section 6) -- a `kind` field
resolves the two requirements inside one file rather than trading one for
the other.
"""

import os
from typing import Any, Dict, Iterable, Tuple

from .jsonl_io import write_csv, write_jsonl
from .stage3 import ColumnProfileArtifact, FormulaInventoryArtifact, Stage3Result


def _residue_lines(residue) -> Iterable[Dict[str, Any]]:
    for r in residue:
        yield {
            "kind": "residue",
            "what": r.what,
            "locations": list(r.locations),
            "defeatingConstruct": r.defeating_construct,
            "consequence": r.consequence,
        }


def _inventory_lines(inventory: FormulaInventoryArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "formula_inventory",
        "captureDate": inventory.stamp.capture_date,
        "toolCommit": inventory.stamp.tool_commit,
        "reliabilityCondition": inventory.reliability_condition,
        "patternCount": len(inventory.patterns),
        "residueCount": len(inventory.residue),
    }
    for p in inventory.patterns:
        yield {
            "kind": "pattern",
            "pattern": p.pattern_text,
            "instanceCount": p.instance_count,
            "rawInstance": p.raw_instance,
            "locations": [
                {"sheet": l.sheet, "column": l.column, "rowStart1": l.row_start1, "rowEnd1": l.row_end1,
                 "instanceCount": l.instance_count}
                for l in p.locations
            ],
            "columnProfiles": [
                {
                    "sheet": cp.sheet,
                    "column": cp.column,
                    "distinctPatternCount": cp.distinct_pattern_count,
                    "classification": cp.classification,
                    "totalFormulaCount": cp.total_formula_count,
                    "totalValueCount": cp.total_value_count,
                    "thisPatternInstanceCount": cp.this_pattern_instance_count,
                    "thisPatternShare": cp.this_pattern_share,
                }
                for cp in p.column_profiles
            ],
        }
    yield from _residue_lines(inventory.residue)


def _column_profile_lines(columns: ColumnProfileArtifact) -> Iterable[Dict[str, Any]]:
    yield {
        "kind": "meta",
        "artifact": "column_profiles",
        "captureDate": columns.stamp.capture_date,
        "toolCommit": columns.stamp.tool_commit,
        "reliabilityCondition": columns.reliability_condition,
        "columnCount": len(columns.columns),
        "residueCount": len(columns.residue),
    }
    for c in columns.columns:
        yield {
            "kind": "column",
            "sheet": c.sheet,
            "column": c.column,
            "totalFormulaCount": c.total_formula_count,
            "totalValueCount": c.total_value_count,
            "distinctPatternCount": c.distinct_pattern_count,
            "classification": c.classification,
            "patterns": [
                {"pattern": ps.pattern_text, "instanceCount": ps.instance_count, "share": ps.share}
                for ps in c.patterns
            ],
            "spillRuns": [
                {
                    "rowStart1": sr.row_start1,
                    "rowEnd1": sr.row_end1,
                    "valueCount": sr.value_count,
                    "governingFormulaRow1": sr.governing_formula_row1,
                    "gapRows": sr.gap_rows,
                }
                for sr in c.spill_runs
            ],
        }
    yield from _residue_lines(columns.residue)


def _column_summary_rows(columns: ColumnProfileArtifact) -> Iterable[Dict[str, Any]]:
    """The one flat CSV projection this stage produces -- see this
    module's own docstring for why only this part of the inventory is
    flat enough: every OTHER field either varies in length per row
    (a pattern's location ranges, a column's per-pattern breakdown, a
    column's spill runs) or embeds a nested structure (column profiles
    inside a pattern entry). These seven fields are the exception --
    exactly one value each, for every column, with no row needing more or
    fewer fields than any other -- which is what "genuinely flat" means
    for this artifact specifically, decided by inspecting the built
    result rather than in advance."""
    for c in columns.columns:
        gaps = [r.gap_rows for r in c.spill_runs if r.gap_rows is not None]
        yield {
            "sheet": c.sheet,
            "column": c.column,
            "totalFormulaCount": c.total_formula_count,
            "totalValueCount": c.total_value_count,
            "distinctPatternCount": c.distinct_pattern_count,
            "classification": c.classification,
            "spillRunCount": len(c.spill_runs),
            "spillRunsWithoutGoverningFormula": sum(1 for r in c.spill_runs if r.governing_formula_row1 is None),
            "minGapRows": min(gaps) if gaps else "",
            "maxGapRows": max(gaps) if gaps else "",
        }


_COLUMN_SUMMARY_FIELDS: Tuple[str, ...] = (
    "sheet", "column", "totalFormulaCount", "totalValueCount", "distinctPatternCount",
    "classification", "spillRunCount", "spillRunsWithoutGoverningFormula", "minGapRows", "maxGapRows",
)


def write_stage3_artifacts(result: Stage3Result, output_dir: str) -> Dict[str, str]:
    """Writes formula_inventory.jsonl, column_profiles.jsonl, and
    column_summary.csv (DERIVED, regenerable -- see _column_summary_rows)
    into `output_dir`. Returns the paths written, keyed by artifact name."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {
        "formula_inventory": os.path.join(output_dir, "stage3_formula_inventory.jsonl"),
        "column_profiles": os.path.join(output_dir, "stage3_column_profiles.jsonl"),
        "column_summary_csv": os.path.join(output_dir, "stage3_column_summary.csv"),
    }
    write_jsonl(paths["formula_inventory"], _inventory_lines(result.inventory))
    write_jsonl(paths["column_profiles"], _column_profile_lines(result.column_profiles))
    write_csv(paths["column_summary_csv"], _COLUMN_SUMMARY_FIELDS, _column_summary_rows(result.column_profiles))
    return paths
