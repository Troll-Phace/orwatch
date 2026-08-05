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
3b. **Fetch current docs for the tooling this phase touches**, via Context7 if
   available (`resolve-library-id`, then `query-docs`) or the web otherwise.
   Do not plan against remembered API shapes — build backends, lint config keys
   and test-discovery rules change, and a plan written from memory produces a
   delegation that fails on its first command.
4. Produce the plan as a table:

   | # | Task | Agent | Files | Depends on | Success criterion |

5. Then, for each task, draft the full six-field delegation prompt (Files / Context / Requirements / Done when / Out of scope / Report). Do not dispatch them yet.
6. Flag anything in the phase that is underspecified — a criterion that is not
   mechanically checkable, a file path that does not exist, a dependency that is
   circular, or a requirement a subagent could reasonably misread.
7. List every decision you are making that the docs do not cover, as a labelled
   set (D1, D2, …) with the reasoning for each. These go into the **Decisions
   Made** section of `.opencode/state/progress.md` and get folded back into
   `docs/ARCHITECTURE.md` at the phase boundary. A decision that lives only in
   this transcript is a decision the next phase will make differently.
8. Note which tasks touch disjoint files and can therefore run in parallel — and
   say whether parallel dispatch is actually worth it, since it costs an extra
   verification pass.

Present the plan for approval before executing. Do not begin implementation from this command.
