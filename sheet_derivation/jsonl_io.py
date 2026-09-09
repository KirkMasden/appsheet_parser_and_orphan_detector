"""Generic JSON Lines and flat-CSV writers (design section 4, "Output
format, decided 2026-09-09"): the artifacts are JSON Lines, one
self-contained item per line; flat CSV projections are generated beside
them for the genuinely flat parts, marked derived and regenerable.

Nothing here names a sheet, a column, or any other fact about one
workbook -- these are mechanical writers over whatever dict/row sequence a
caller hands them. Stage 3 is the first caller (design section 4.1 is the
first artifact built), but nothing here is specific to it.

No truncation anywhere: `json.dump`/`csv.writer` are never given a size
limit, and this module imposes none of its own.
"""

import csv
import json
from typing import Any, Dict, Iterable, Sequence


def write_jsonl(path: str, items: Iterable[Dict[str, Any]]) -> int:
    """Writes one JSON object per line, in the order `items` yields them --
    determinism is the caller's responsibility (every collection this tool
    emits must already be sorted by an explicit key before it reaches
    here; see determinism.py). Returns the number of lines written.

    Uses `ensure_ascii=False` so the file holds real UTF-8 text rather than
    `\\uXXXX` escapes -- this workbook's formulas and labels are not
    restricted to ASCII, and neither is this writer.
    """
    count = 0
    with open(path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=False))
            fh.write("\n")
            count += 1
    return count


def read_jsonl(path: str):
    """Yields one parsed JSON object per non-blank line, in file order.
    The mirror of write_jsonl -- used by tests and by anything that reads
    an artifact back rather than only writing one."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_csv(path: str, fieldnames: Sequence[str], rows: Iterable[Dict[str, Any]]) -> int:
    """Writes a flat CSV projection: one row per item, in the order `rows`
    yields them. Every value is written as `csv` itself renders it (str()
    of whatever the row dict holds) -- no truncation, no re-encoding of
    numbers or booleans beyond what the `csv` module already does for any
    Python value. Returns the number of data rows written (header excluded).
    """
    count = 0
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count
