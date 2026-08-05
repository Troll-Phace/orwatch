# orwatch harness v2 — apply before Phase 2

Unzip **over** your repo root. Every file here is safe to overwrite: none of
them were touched during Phase 1.

```bash
cd ~/projects/orwatch
unzip -o ~/Downloads/orwatch-harness-v2.zip
rm APPLY.md
```

## Deliberately NOT included

These moved during Phase 1 and would be clobbered:

| File | Why |
|---|---|
| `docs/ARCHITECTURE.md` | D1–D7 were folded into it |
| `.opencode/state/progress.md` | advanced to Phase 2 |
| `docs/INSTRUCTIONS.md` | see step 3 below |
| `.gitignore` | already merged — see step 1 |
| `pyproject.toml` | agent-created — see step 2 |

## Three manual steps

### 1. Un-ignore progress.md  ← do this first

`.gitignore` currently has `.opencode/state/`, which makes your phase state
local-only. A fresh clone starts blind.

```diff
- .opencode/state/
+ .opencode/state/tool-errors.jsonl
```

Then `git add -f .opencode/state/progress.md` since it was already ignored.

### 2. Extend the ruff exclusion

Phase 1 added `extend-exclude = ["docs"]`. `.opencode/` is still in scope —
the reviewer counted 17 framework `.md` files being processed. Any code block
in an agent definition will eventually break `ruff format --check`.

```diff
  [tool.ruff]
- extend-exclude = ["docs"]
+ extend-exclude = ["docs", ".opencode", "AGENTS.md"]
```

### 3. Record the milestone tiers in INSTRUCTIONS.md

Your milestones exist on GitHub but are written down nowhere, so anything
reading INSTRUCTIONS.md will invent its own names. Append this, matching
whatever `gh api repos/Troll-Phace/orwatch/milestones --jq '.[].title'` shows:

```markdown
## Milestone Tiers

| Tier | Theme | Swept |
|---|---|---|
| `Tier A — MVP correctness` | Correctness in client, store, diff engine | Before Phase 5 ships |
| `Tier B — Post-MVP features` | --json, concurrency, thresholds, --since | Opportunistically after MVP |
| `Tier C — Perf & robustness hardening` | Error paths, malformed input, Windows edge cases | After Phase 5 |
```

## What changed

| Change | Files |
|---|---|
| Orchestrator can write `progress.md` (scoped edit) — it was told to maintain a file it couldn't touch | `agents/orchestrator.md`, `AGENTS.md` |
| Orientation commands allowed: `uv --version`, `git show*`, `git remote*`, `gh auth status` | `agents/orchestrator.md` |
| `docs/SPEC.md` now ships — fixes the dangling reference that became issue #1 | new |
| `guard.ts` tokenizes paths instead of substring-matching the whole command | `plugins/guard.ts` |
| `telemetry.ts` records the responsible agent and model | `plugins/telemetry.ts` |
| `/phase-plan` fetches current tooling docs, emits a labelled decision list, judges parallelism | `commands/phase-plan.md` |
| `issue-triage` gains `gh repo view*`, plus the `gh api repos/$REPO` and no-`gh milestone` notes | `agents/issue-triage.md` |
| Lint-exclusion standard | `agents/backend-dev.md` |
| Measured tool-call behaviour + cost baseline | `docs/MODEL_PROFILES.md` |
| Parsed-command matching, bootstrap delegation, publish boundaries | `AGENTS.md` |

Close issue #1 once step 1 of this file is done — `docs/SPEC.md` now exists.

Then: `opencode` → `/model-check` → `/phase-plan`.
