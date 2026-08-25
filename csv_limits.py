"""Raise the csv module's field size limit process-wide on import.

Every entry point in this project (the master parser, individual parsers,
orphan detectors, dependency analyzers) needs the raised limit, however it
happens to be run, so each of those modules imports this one purely for its
import-time side effect rather than repeating the call itself.

The value is capped at 2**31 - 1 rather than set to sys.maxsize because
csv.field_size_limit() stores the limit in a C long. On Windows, C long is
32-bit even under 64-bit Python, so passing sys.maxsize there raises
OverflowError. Capping at the 32-bit signed max keeps the limit effectively
unbounded for real AppSheet field sizes while staying valid on every
platform.
"""

import csv
import sys

CSV_FIELD_SIZE_LIMIT = min(sys.maxsize, 2147483647)
csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
