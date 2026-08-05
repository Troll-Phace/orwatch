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

1. For the target tier — or the most urgent one if `$ARGUMENTS` is empty — list its open issues by severity.
2. Recommend a **fix-now batch**: ordered by severity first, then dependency. Group issues touching disjoint files so they can be delegated in parallel.
3. Assign a suggested agent per issue, respecting the tier economics: escalate to `specialist` only for issues that genuinely need it.
4. **Identify the breakpoint.** Is now the right moment to sweep this tier, or should it wait until after the current phase? State the tradeoff explicitly — what gets harder if it waits, what gets disrupted if it does not.
5. Output the batch plan in a form the orchestrator can delegate directly.
6. If every issue in a milestone is resolved, flag it **"ready to close"**. Never close it yourself.
