"""The base every one of the five artifacts (stages 1-5, not built yet) must extend.

No artifact is defined here -- this is the shared shape, so that a later
stage literally cannot construct an artifact object without supplying a
stamp, a reliability condition, and a residue tuple. Leaving any one of
these out is a missing required dataclass argument, not a silent gap a
reviewer has to notice.
"""

from dataclasses import dataclass
from typing import Tuple

from .residue import ArtifactStamp, ResidueEntry


@dataclass(frozen=True)
class ArtifactBase:
    """Fields every artifact carries, per design section 6.

    `reliability_condition` is the artifact-level statement -- stated once,
    general -- of what the artifact's content rests on (the Downstream
    Dependency Report model: "a DEAD verdict is only as reliable as the file
    is free of INDIRECT reads back into this range"). `residue` is the
    enumerated, per-item list of the specific things that could defeat that
    condition. A future artifact subclass adds its own fields on top of
    these three; it does not get to omit them.
    """

    stamp: ArtifactStamp
    reliability_condition: str
    residue: Tuple[ResidueEntry, ...]

    def __post_init__(self):
        if not self.reliability_condition or not self.reliability_condition.strip():
            raise ValueError(
                "ArtifactBase.reliability_condition is required -- every artifact "
                "must state, once, what its content's trustworthiness rests on"
            )
        # residue may legitimately be empty (nothing defeated the extractor),
        # but it must be a tuple, not a list, list of lists, or lazy generator
        # -- fixed at construction so equality and sorting stay well-defined.
        object.__setattr__(self, "residue", tuple(self.residue))
