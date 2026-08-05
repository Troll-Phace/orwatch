---
description: Plan the current development phase and produce a delegation-ready task list
agent: orchestrator
---

# Plan Phase $ARGUMENTS

Current state:
!`cat .opencode/state/progress.md 2>/dev/null || echo "No progress file yet."`

Recent history:
!`git log --oneline -10 2>/dev/null || echo "No git history."`

Working tree:
!`git status --short 2>/dev/null`

## Do this

1. Identify the current phase from the state above. If `$ARGUMENTS` names a phase, plan that one instead.
2. Read `docs/INSTRUCTIONS.md` for that phase's tasks and success criteria.
3. Read the `docs/ARCHITECTURE.md` sections it references. For UI phases, read `docs/DESIGN_SYSTEM.md`.
4. Produce the plan as a table:

   | # | Task | Agent | Files | Depends on | Success criterion |

5. Then, for each task, draft the full six-field delegation prompt (Files / Context / Requirements / Done when / Out of scope / Report). Do not dispatch them yet.
6. Flag anything in the phase that is underspecified — a criterion that is not mechanically checkable, a file path that does not exist, a dependency that is circular.
7. Note which tasks touch disjoint files and can therefore run in parallel.

Present the plan for approval before executing. Do not begin implementation from this command.
