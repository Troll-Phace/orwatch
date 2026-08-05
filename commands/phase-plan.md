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

> **The blocks above are shell-injected and may be silently empty.** In a real
> run on the OpenCode GUI build every injected block returned its failure branch
> ("No progress file yet.", "No git history.", empty tree) while the same
> commands run from this agent's own `bash` tool returned the real state one
> turn later. Treat an empty or fallback block as **no information**, never as
> evidence that the thing does not exist. Re-derive anything you are about to
> act on with `read` / `bash` before you rely on it.

0. **Establish state yourself, first, every time.** Do not skip this even when
   the blocks above look populated:
   - `read .opencode/state/progress.md`
   - `git log --oneline -10`
   - `git status --short`
   If `progress.md` is missing or contains something that is not phase state,
   reconstruct the current phase from `git log` and `docs/INSTRUCTIONS.md`, say
   so explicitly in your plan, and rebuild the file at the phase boundary.
1. Identify the current phase from what **you** just read. If `$ARGUMENTS` names a phase, plan that one instead.
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
8. Decide parallelism over the **import/run graph, not the file list.** Two
   tasks are safe to dispatch together only if neither can *observe* the other's
   half-finished work. Disjoint `Files:` lists are necessary, not sufficient:

   - A task that runs the test suite, the linter, or the build depends on every
     file those commands load — so it is **never** disjoint from a task editing
     `src/`. Observed in a real run: a fixture-capture task running `pytest` in
     parallel with an edit to `models.py` hit `NameError: name 'Snapshot' is
     not defined`, because it imported the module mid-edit.
   - A task writing tests against an interface another task is still building is
     not parallel work either. It may pass on timing luck; that is not a plan.
   - Two tasks writing disjoint leaf files that nothing yet imports **are** safe.

   Then say whether parallel dispatch is actually worth it, since it costs an
   extra verification pass. If you dispatch in parallel anyway, state in each
   prompt what the other agent is touching concurrently and instruct both to
   report — not fix — anything they observe in the other's scope.

Present the plan for approval before executing. Do not begin implementation from this command.
