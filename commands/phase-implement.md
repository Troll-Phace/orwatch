---
description: Execute the approved phase plan by delegating to subagents in dependency order
agent: orchestrator
---

# Implement Phase $ARGUMENTS

## Do this

1. Confirm an approved plan from `/phase-plan` exists in this session. If not, stop and run `/phase-plan` first.
2. For each task in dependency order:
   - Dispatch the six-field delegation prompt to the assigned subagent via the Task tool.
   - Read the subagent's report against the acceptance criteria **you** set, not against its own summary.
   - Verify independently: run the tests yourself; check `git diff --stat` for files outside the declared scope.
   - If it falls short, re-delegate with specific feedback naming what failed and why. Do not fix it yourself.
   - After two failed attempts with clear feedback, escalate to `specialist`.
3. Tasks touching disjoint files may be dispatched together.
4. When all tasks are done and the suite passes, run the **mandatory review gate**: delegate to `code-reviewer`.
5. Route every unfixed review finding to `issue-triage` via `/log-issue`.
6. Only then update `.opencode/state/progress.md`.

Collect each subagent's `DEFERRED` section as you go. Nothing in a `DEFERRED` list may be dropped — it is logged or it is fixed.
