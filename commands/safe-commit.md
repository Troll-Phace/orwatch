---
description: Create a well-formatted commit with pre-flight checks
agent: orchestrator
---

# Safe Commit — $ARGUMENTS

Status:
!`git status --short`

Diff overview:
!`git diff --stat HEAD`

Staged secrets check:
!`git diff --cached --name-only | rg -i "\.env|secret|credential|\.pem$|id_rsa|\.key$" || echo "clean"`

Branch:
!`git branch --show-current`

## Do this

> **The blocks above are shell-injected and may be silently empty.** In a real
> run on the OpenCode GUI build every injected block returned its failure branch
> ("No progress file yet.", "No git history.", empty tree) while the same
> commands run from this agent's own `bash` tool returned the real state one
> turn later. Treat an empty or fallback block as **no information**, never as
> evidence that the thing does not exist. Re-derive anything you are about to
> act on with `read` / `bash` before you rely on it.

1. Review the status and diff above. If anything unexpected is present, stop and report it.
2. If the secrets check found anything, **stop**. Do not commit.
3. If source files changed, confirm the test suite passed in this session. If it did not, run it.
4. Confirm the `code-reviewer` gate has run for this work. If it has not, stop and run it.
5. Stage files **explicitly by path**. Never `git add .`.
6. Commit as:
   ```
   phase({N}): {concise description of what changed}

   Refs #NN
   Refs #MM
   ```
   Use `Refs`, never `Closes`/`Fixes` — issues are closed by the user after verification.
7. Report the commit hash and a one-line summary. Do not push unless explicitly asked.
