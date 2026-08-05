---
description: Sweep untriaged and unlabeled GitHub issues, assigning type, severity, and milestone
agent: issue-triage
subtask: true
---

# Triage Issues

Needs triage:
!`gh issue list --label needs-triage --state open --limit 50 2>/dev/null`

Unlabeled:
!`gh issue list --search "no:label" --state open --limit 50 2>/dev/null`

## Do this

> **The blocks above are shell-injected and may be silently empty.** In a real
> run on the OpenCode GUI build every injected block returned its failure branch
> ("No progress file yet.", "No git history.", empty tree) while the same
> commands run from this agent's own `bash` tool returned the real state one
> turn later. Treat an empty or fallback block as **no information**, never as
> evidence that the thing does not exist. Re-derive anything you are about to
> act on with `read` / `bash` before you rely on it.

1. For each candidate, read the body — and the referenced source if the severity is not obvious from the description alone.
2. Assign one `type:`, one `severity:`, and a milestone if a tier fits:
   `gh issue edit <n> --add-label "type:X,severity:Y" --remove-label needs-triage [--milestone "<tier>"]`
3. Report a table: `# | title | type | severity | milestone`.
4. Flag genuinely ambiguous items for the user rather than guessing. A wrongly-severitied issue stops getting looked at, which is worse than an untriaged one.
