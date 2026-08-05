---
description: Verify a completed phase against its success criteria before advancing
agent: code-reviewer
subtask: true
---

# Review Phase $ARGUMENTS

Changes in this phase:
!`git diff --stat HEAD 2>/dev/null || echo "no diff vs HEAD"`

Files touched since the last tag or 20 commits back:
!`git diff --name-only $(git describe --tags --abbrev=0 2>/dev/null || git rev-parse HEAD~20 2>/dev/null || git rev-list --max-parents=0 HEAD) 2>/dev/null | head -50`

## Do this

1. Read every file listed above in full — not only the diff hunks. A correct hunk inside a wrong function is still a finding.
2. Run `uv run pytest` yourself. Report the actual output. Also run `uv run ruff check .`.
3. Verify each success criterion in `docs/INSTRUCTIONS.md` for this phase **by executing something**, not by reading and agreeing.
4. Apply the eight-point review checklist from your agent definition.
5. Report in your standard format, ending with a `VERDICT` and a `TO LOG` list.

A `PASS` verdict with no findings requires you to state explicitly what you verified versus what you took on trust.
