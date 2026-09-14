"""Resolves the WORKSPACE root -- the directory that contains this
repository -- for anything that needs a default capture or output
location without the caller supplying one explicitly. Today that is only
sheet_derivation/gates/, but the rule is written once here so nothing
else that needs it has to work it out for itself again.

Three rules, applied in this order, every time:

1. An explicit path always wins. Passing `explicit` returns it unchanged
   -- nothing here ever overrides a caller's own choice, and nothing here
   removes a caller's ability to pass its own paths.
2. Absent that, the workspace root is the PARENT of this repository's own
   directory, computed from __file__ -- specifically, THIS module's own
   __file__, not the caller's, so the answer does not depend on how deep
   in the package tree a particular caller happens to live. Never derived
   from the current working directory, which changes with how a script
   happens to be invoked and would silently pick a different answer run
   to run.
3. Printed once per call (default on), so a wrong guess surfaces
   immediately at the start of a run rather than failing confusingly
   several directories downstream. Call this once per run and reuse the
   returned value for every default derived from it -- calling it twice
   announces it twice.

No marker file is required and none is looked for; a caller who has
moved this repository somewhere else entirely still gets the right
answer by construction (rule 2), and can always override it (rule 1).
"""

from pathlib import Path
from typing import Optional

# This file lives at <repo>/sheet_derivation/workspace.py. Its own parent
# is <repo>/sheet_derivation; that directory's parent is <repo> itself;
# and <repo>'s own parent is the workspace -- three fixed steps from this
# module's own location, regardless of where any particular caller lives
# in the package tree.
_REPO_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE_ROOT = _REPO_DIR.parent


def resolve_workspace_root(explicit: Optional[str] = None, announce: bool = True) -> str:
    """Rule 1: `explicit`, if given, is returned as-is. Rule 2: otherwise,
    the workspace root computed from this module's own __file__. Rule 3:
    printed once, unless `announce=False` (for a caller that has already
    announced it this run, or that has a reason not to)."""
    root = explicit if explicit is not None else str(_WORKSPACE_ROOT)
    if announce:
        print(f"workspace root: {root}")
    return root
