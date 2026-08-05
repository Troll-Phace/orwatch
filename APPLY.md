# orwatch harness — v2 → v3

Folds the eight Phase 2 findings in. Unzip over the repo root; everything here
replaces a file you already have, except the two marked **new**.

```
.opencode/plugins/telemetry.ts        ← replace   (P2-1, breaking-ish: see step 1)
.opencode/agents/orchestrator.md      ← replace   (P2-3, P2-7)
.opencode/agents/backend-dev.md       ← replace   (P2-5)
.opencode/agents/test-engineer.md     ← replace   (P2-3)
.opencode/commands/phase-plan.md      ← replace   (P2-2, P2-4)
.opencode/commands/phase-status.md    ← replace   (P2-2)
.opencode/commands/phase-review.md    ← replace   (P2-2)
.opencode/commands/safe-commit.md     ← replace   (P2-2)
.opencode/commands/milestone-review.md ← replace  (P2-2)
.opencode/commands/triage-issues.md   ← replace   (P2-2)
tests/conftest_network_guard.py.append ← new, append by hand (P2-3, step 3)
```

Not shipped, deliberately: `opencode.jsonc`, `AGENTS.md`, `docs/*`,
`.opencode/state/progress.md`, and the five agents that did not change. Yours are
current or project-specific — see the manual steps below for the two that need a
one-line edit.

---

## Manual steps

### 1. `.gitignore` — this one is still outstanding from v2

Phase 2's commit hit this:

```
$ git add … .opencode/state/progress.md
The following paths are ignored by one of your .gitignore files:
.opencode/state
```

`progress.md` only survived because it was already tracked. Any **new** state
file will silently not commit. Replace the directory ignore with the two
telemetry files:

```diff
-.opencode/state/
+.opencode/state/tool-errors.jsonl
+.opencode/state/sessions.jsonl
```

Then confirm: `git check-ignore -v .opencode/state/progress.md` should print
nothing.

### 2. `AGENTS.md` — add two sections

Both are short and both matter for Phase 3. Paste into the sections named:

**Under "Issue Tracking Protocol", before "Bash permissions match parsed commands":**

```markdown
### Parallel dispatch is bounded by the import graph, not the file list

Two tasks may be dispatched together only if neither can observe the other's
half-finished work. Disjoint `Files:` lists are necessary but not sufficient: a
task that runs the test suite, the linter or the build depends on **every file
those commands load**, so it is never disjoint from a task editing `src/`.
Observed in Phase 2 — the fixture-capture task ran `pytest` alongside an edit to
`models.py`, imported the module mid-edit, and hit
`NameError: name 'Snapshot' is not defined`.

When you do dispatch in parallel, name the concurrent work in both prompts and
tell each agent to **report, not fix**, anything it sees in the other's scope.

### Project-wide tooling rules

- **Lint exclusions:** `[tool.ruff] extend-exclude = ["docs"]` is correct and
  sufficient. Do not widen it to `.opencode` or `AGENTS.md` — Phase 2 confirmed
  `uv run ruff format --check .` passes with both in scope, because ruff does
  not format markdown. Issue #4 exists to record that adjudication; close it.
- **Money is `Decimal`.** Parse with `Decimal(str(v))`, never `float()`, and
  reject non-finite values.
- **The test suite is offline.** Enforced by the autouse fixture in
  `tests/conftest.py`, not by convention.
```

**Replace the "State" section's last paragraph with:**

```markdown
You are its **only** writer. `telemetry.ts` logs to
`.opencode/state/sessions.jsonl` and `.opencode/state/tool-errors.jsonl`;
nothing else touches `progress.md`. If you open it and find machine-generated
lines instead of phase state, something is misconfigured — reconstruct from
`git log` and `docs/INSTRUCTIONS.md`, rebuild the file, and log an issue.

Because you rewrite this file wholesale, **read it immediately before writing
it.** Never write it from a copy you loaded earlier in the session.
```

### 3. `tests/conftest.py` — append the network guard

Append the body of `tests/conftest_network_guard.py.append` to your existing
`tests/conftest.py`, then delete the `.append` file. Register the marker in
`pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["allow_network: test may open real sockets (fixture capture only)"]
```

Verify — all 47 tests should still pass, since they all use `MockTransport`:

```bash
uv run pytest -q
```

Validated here against httpx 0.28 + pytest 9: `MockTransport` passes through
untouched, a real `httpx.get` raises `NetworkAccessDenied`, and the
`@pytest.mark.allow_network` marker opts out cleanly.

### 4. `.opencode/state/progress.md` — check its first line

If the top of the file is a line like
`- 2026-08-05 02:52: session idle (started …) — 11 tool calls, 0 failed (0.0%)`,
that is the old telemetry plugin writing into your phase state. Delete the line.
The new `telemetry.ts` writes to `sessions.jsonl` instead, so it will not come
back.

### 5. Close issue #4

Its premise was adjudicated false in-phase (`AGENTS.md` never prescribed the
wider exclude — the rule lived in `backend-dev.md`, which v3 fixes by moving it
to `AGENTS.md` and telling agents to cite the right source). Close it with a
note; #2 and #3 stay open for Phase 3.

---

## What changed and why, in one line each

| ID | Change |
|---|---|
| P2-1 | `telemetry.ts` session stamp moved from `progress.md` → `sessions.jsonl`. Two writers were racing over one file. |
| P2-2 | Every `` !`…` ``-using command now warns that an empty block means *no information*; `/phase-plan` gained a step 0 that re-derives state itself. |
| P2-3 | Orchestrator and `test-engineer` are told a test runner is not a permission boundary and that routing a denied operation through it is a defect; `"uv run python scripts/*": ask` added as the legitimate door; `conftest` socket guard added as the real enforcement. |
| P2-4 | `/phase-plan` step 8 and `AGENTS.md` scope parallelism to the import/run graph. |
| P2-5 | Lint-exclusion rule moved to `AGENTS.md` and narrowed to `["docs"]`; `backend-dev` told to distinguish its own standing instructions from citable project docs. |
| P2-6 | `.gitignore` names the two telemetry files instead of the `state/` directory. |
| P2-7 | Orchestrator: a permission denial is final — re-plan, do not retry a simplified variant. |
| P2-8 | `MODEL_PROFILES.md` updated with the two-run aggregate (45/173, 26%, position not restricted to trailing) and the $2.06–2.09 cost band. |

`docs/MODEL_PROFILES.md` is worth updating too if you want the current numbers in
session context — the relevant sections are in the framework tarball under
`scaffold/docs/MODEL_PROFILES.md`. It is not required for Phase 3 to run.

---

## Phase 3 entry check

```bash
git check-ignore -v .opencode/state/progress.md   # → no output
uv run pytest -q                                   # → 47 passed
uv run ruff check . && uv run ruff format --check . # → clean
head -3 .opencode/state/progress.md                # → phase state, not telemetry
```

Then `/phase-plan` for Phase 3: Snapshot Store. Its first open decision is
issue #3 — whether duplicate-tag rejection moves to `Snapshot.__post_init__`
(covers every construction path) or happens at load time in `store.py`.
