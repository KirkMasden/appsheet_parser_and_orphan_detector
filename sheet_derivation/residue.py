"""The residue record and the artifact-level stamp (design sections 6, 4).

Defined now, used by nothing yet: stage 0 builds no artifact. The point of
defining these types before any artifact exists is that a later stage
cannot be written without importing and populating them -- there is no
artifact constructor that accepts a bare "could not parse" in place of a
ResidueEntry, because ResidueEntry itself refuses to be constructed with
placeholder content.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class ResidueEntry:
    """One thing an artifact's extraction could not interpret.

    Per design section 6, a residue entry is four things, all required:
    what was not interpreted, where (as cell addresses or pattern
    identifiers), which construct defeated the extractor, and what the
    artifact may consequently be wrong about. A bare "could not parse"
    satisfies none of the last three, so it is rejected here rather than
    left for a reader to notice its absence later.
    """

    what: str
    locations: Tuple[str, ...]
    defeating_construct: str
    consequence: str

    def __post_init__(self):
        if not self.what or not self.what.strip():
            raise ValueError("ResidueEntry.what must describe what was not interpreted")
        if not self.locations:
            raise ValueError(
                "ResidueEntry.locations must name at least one cell address or "
                "pattern identifier -- a residue entry with no location cannot "
                "route a reader anywhere"
            )
        if not self.defeating_construct or not self.defeating_construct.strip():
            raise ValueError(
                "ResidueEntry.defeating_construct must name the specific construct "
                "that defeated the extractor (e.g. 'INDIRECT argument', "
                "'digit inside identifier') -- 'could not parse' alone is not a construct"
            )
        if not self.consequence or not self.consequence.strip():
            raise ValueError(
                "ResidueEntry.consequence must state what the artifact may "
                "consequently be wrong about"
            )
        # Locations are frozen at construction time in sorted order: every
        # collection this tool emits is sorted by an explicit key, and a
        # residue entry's own location list is no exception.
        object.__setattr__(self, "locations", tuple(sorted(self.locations)))


def get_tool_commit(repo_dir: str = None) -> str:
    """The tool's own git commit hash, for the artifact stamp.

    Falls back to a clear, non-crashing string if the tool is not running
    from inside a git checkout (e.g. a copied source tree) -- an artifact
    stamp that can't name a commit still has to say why, not raise.
    """
    cwd = repo_dir or str(Path(__file__).resolve().parent)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        return f"unknown (git rev-parse failed: {exc})"


@dataclass(frozen=True)
class ArtifactStamp:
    """What every artifact carries (design section 6): its capture's date,
    and the commit of the tool that built it. Both required -- there is no
    default capture_date or tool_commit, because an artifact whose
    provenance is unstated will be read as current (design section 6)."""

    capture_date: str
    tool_commit: str

    def __post_init__(self):
        if not self.capture_date:
            raise ValueError("ArtifactStamp.capture_date is required")
        if not self.tool_commit:
            raise ValueError("ArtifactStamp.tool_commit is required")


def build_stamp(capture_date: str, repo_dir: str = None) -> ArtifactStamp:
    """Convenience constructor: pairs a capture's date with the tool's own commit."""
    return ArtifactStamp(capture_date=capture_date, tool_commit=get_tool_commit(repo_dir))
