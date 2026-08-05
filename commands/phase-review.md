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

> **The blocks above are shell-injected and may be silently empty.** In a real
> run on the OpenCode GUI build every injected block returned its failure branch
> ("No progress file yet.", "No git history.", empty tree) while the same
> commands run from this agent's own `bash` tool returned the real state one
> turn later. Treat an empty or fallback block as **no information**, never as
> evidence that the thing does not exist. Re-derive anything you are about to
> act on with `read` / `bash` before you rely on it.

1. Read every file listed above in full — not only the diff hunks. A correct hunk inside a wrong function is still a finding.
2. Run the full test suite yourself. Report the actual output.
3. Verify each success criterion in `docs/INSTRUCTIONS.md` for this phase **by executing something**, not by reading and agreeing.
4. Apply the eight-point review checklist from your agent definition.
5. Report in your standard format, ending with a `VERDICT` and a `TO LOG` list.

A `PASS` verdict with no findings requires you to state explicitly what you verified versus what you took on trust.
