# Agent report format

This file is written for an AI agent, not for a person. It applies once you have used this tool against someone else's workbook and found something worth reporting back to the maintainer. A human template would tell you what a finished report should contain; this tells you what to go and check before you write one, because a wrong report costs the maintainer more than a slow one.

## Before you write

- **Check a pattern's individual instances before generalizing from the one the inventory carries.** See "One instance is not the pattern" in CLAUDE.md/AGENTS.md for the full reasoning; the short version is that the inventory's one worked example shows a pattern's shape, not what any particular instance says, and a claim resting on it alone can be wrong wherever the instances diverge.
- **Name the cell for every claim.** A finding without a cell address is not actionable — the maintainer cannot check it, and neither can you if asked to verify it again later.
- **Distinguish what the artifact says from what the sheet actually says.** Read the artifact's claim, then check the raw capture (the formula text, the captured value) for that same cell. Where the two differ, that difference is the finding, not a footnote to it.
- **State explicitly what could not be settled, and say which kind of "could not."** Some questions are merely unanswered — you ran out of places to look, or the answer depends on live data the capture does not carry. Others are structurally undecidable from the capture itself: no amount of further checking would settle them, because the capture is genuinely compatible with more than one answer. Attested instance: a formula counted an entire column and then subtracted a count over its first rows, so a disputed header row was added back in and taken out again under either reading of whether that row counts — the total comes out identical either way, and no recount of the same numbers can tell you which interpretation was intended. Reporting a question like this as confirmed claims more than the evidence can carry. Report it as undecidable, and say why.

## What to write

- The question you were asked to answer.
- Which artifacts, and which stages, you actually read to answer it.
- The claim, with the cell address it rests on.
- Where artifact and sheet disagree: what the artifact said, what the sheet says, side by side.
- Gate figures and residue counts, copied verbatim from the report that produced them — never paraphrased, rounded, or retyped from memory.
- An explicit unresolved section: everything the previous section asked you to check for, named rather than left out by silence.
- Which class the finding is, in one line: did the tool fail to SEE something (a construct it didn't parse, a reference it didn't follow), or did it see it correctly and JUDGE it wrong (a rule applied where it shouldn't have been, a threshold read incorrectly)? Say which, plainly. A seeing problem is usually local and diagnosis-bound — one cell, one construct, fixable without disturbing what the tool already gets right elsewhere. A judgment problem can move counts across the whole graph and needs much heavier verification before anything downstream of it can be trusted again.

## The boundary

Report by cell address and formula text. Do not attach the capture. A user's formulas/values JSON is their own private data — it stays on their machine, not in a report to the maintainer.
