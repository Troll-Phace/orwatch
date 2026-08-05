---
description: Review open milestones at a roadmap breakpoint and recommend which issues to sweep now versus defer
agent: issue-triage
subtask: true
---

# Milestone Review — $ARGUMENTS

Milestone progress:
!`gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.number)  \(.title)  open:\(.open_issues) closed:\(.closed_issues)"' 2>/dev/null`

Current phase:
!`cat .opencode/state/progress.md 2>/dev/null | head -20`

## Do this

> **The blocks above are shell-injected and may be silently empty.** In a real
> run on the OpenCode GUI build every injected block returned its failure branch
> ("No progress file yet.", "No git history.", empty tree) while the same
> commands run from this agent's own `bash` tool returned the real state one
> turn later. Treat an empty or fallback block as **no information**, never as
> evidence that the thing does not exist. Re-derive anything you are about to
> act on with `read` / `bash` before you rely on it.

1. For the target tier — or the most urgent one if `$ARGUMENTS` is empty — list its open issues by severity.
2. Recommend a **fix-now batch**: ordered by severity first, then dependency. Group issues touching disjoint files so they can be delegated in parallel.
3. Assign a suggested agent per issue, respecting the tier economics: escalate to `specialist` only for issues that genuinely need it.
4. **Identify the breakpoint.** Is now the right moment to sweep this tier, or should it wait until after the current phase? State the tradeoff explicitly — what gets harder if it waits, what gets disrupted if it does not.
5. Output the batch plan in a form the orchestrator can delegate directly.
6. If every issue in a milestone is resolved, flag it **"ready to close"**. Never close it yourself.
