# THE AGENTIC FRAMEWORK 2.1-OC

**A Cross-Model Orchestration Framework for OpenCode**
Model-Agnostic • Capability-Aware • Enforcement-First

**Version:** 2.1-OC
**Author:** Anthony Grimaldi
**Date:** August 4, 2026
**Derived from:** Agentic Framework 2.1 (Claude Code)
**Verified against:** OpenCode v1.18.13 (`anomalyco/opencode`), OpenRouter API (live, 2026-08-04), Cherry Studio docs (CherryHQ/cherry-studio-docs @ 2026-08-04)

---

# 0. What Changed and Why

Framework 2.1 was written for one model. Every agent omitted `model:` and inherited the session default, because on Claude Code the model is a constant and the interesting variables are *role*, *context*, and *permission*.

Under OpenCode + OpenRouter, **the model is the variable**. You are running three families with different tool-calling contracts, different reasoning semantics, different sampling behaviour, and — critically — different *providers behind the same model ID*, some of which do not support tool calling at all.

2.1-OC therefore adds one new layer and hardens one existing principle.

**New layer — the Model Capability Profile (§4).** A declarative record of what each model can actually do, which agent tiers it is eligible for, and what config consequences follow. Model choice becomes a single-file edit, not a scavenger hunt through nine agent definitions.

**Hardened principle — enforcement over prose.** 2.1 relied partly on CLAUDE.md saying "NEVER write implementation code yourself." That works on Claude because Claude follows negative constraints well. It does **not** transfer. The field evidence is unambiguous: prose role constraints on an orchestrator are ignored by non-Anthropic models, and the only control that binds is the *absence of the tool from the tool list*. In 2.1-OC the orchestrator cannot write code because `permission.edit` is `deny`, not because a prompt asks it not to.

Everything else — the phase loop, the mandatory review gate, the issue-tracking subsystem, `Refs #NN` with no auto-close — carries over intact.

---

# 1. Design Principles (revised)

1. **Enforcement over prose.** Any constraint that matters is expressed as a `permission` entry, a `steps` cap, or an absent tool. Prompts explain *why*; permissions decide *whether*.
2. **Deterministic over probabilistic.** Plugins and `instructions` guarantee behaviour; instructions in a system prompt hope for it.
3. **Capability-aware routing.** Each agent declares a *tier*, not a model. Tiers bind to models in one place. Re-tiering is a config change, not a refactor.
4. **Heterogeneous review.** The reviewing agent runs on a *different model family* than the implementing agent. Correlated blind spots are the failure mode a same-model review cannot catch.
5. **Pin the endpoint, not just the model.** A model ID on OpenRouter is a fan-out over providers with non-uniform capability. Tool calling is a property of the *endpoint*.
6. **Probe, don't assume.** Capability is verified by a live smoke test (`/model-check`) before a phase, not inferred from a model card.
7. **Domain isolation.** Subagents touch only their domain, enforced by path-scoped `permission.edit` and `permission.bash`.
8. **Stateful across sessions.** `instructions` re-injects phase state and model profiles into every session deterministically.

---

# 2. Directory Structure

```
project-root/
├── opencode.json                       # Provider pinning, tier map, permissions, commands  [CUSTOMIZE]
├── AGENTS.md                           # Orchestrator identity + delegation contract        [CUSTOMIZE]
├── .opencode/
│   ├── agents/
│   │   ├── orchestrator.md             # primary, default — plans and delegates, cannot edit
│   │   ├── architect.md                # primary — deep design reasoning, cannot edit
│   │   ├── backend-dev.md              # subagent — WORKHORSE tier                          [CUSTOMIZE]
│   │   ├── frontend-dev.md             # subagent — WORKHORSE tier                          [CUSTOMIZE]
│   │   ├── specialist.md               # subagent — DEEP tier, the hard 20%
│   │   ├── test-engineer.md            # subagent — tests/ only
│   │   ├── code-reviewer.md            # subagent — read-only, DIFFERENT family by design
│   │   ├── issue-triage.md             # subagent — gh only
│   │   └── researcher.md               # subagent — read-only + web
│   ├── commands/
│   │   ├── phase-plan.md   phase-implement.md   phase-review.md   phase-status.md
│   │   ├── log-issue.md    triage-issues.md     milestone-review.md
│   │   ├── safe-commit.md
│   │   └── model-check.md              # NEW — live capability probe
│   ├── plugins/
│   │   ├── guard.ts                    # protected-path denial (replaces PreToolUse hook)
│   │   ├── format.ts                   # format-on-edit (replaces PostToolUse hook)
│   │   └── telemetry.ts                # per-model tool-failure log → feeds §4 calibration
│   ├── scripts/
│   │   ├── preflight.sh                # verify every pinned model/provider still has tools
│   │   └── retier.sh                   # swap a tier's model across all agent files
│   ├── skills/                         # optional; .claude/skills/ is ALSO read natively
│   └── state/
│       ├── progress.md                 # phase tracking (injected via `instructions`)
│       └── tool-errors.jsonl           # written by telemetry.ts
└── docs/
    ├── ARCHITECTURE.md                 [CUSTOMIZE]
    ├── INSTRUCTIONS.md                 [CUSTOMIZE]
    ├── MODEL_PROFILES.md               # THE TIER MAP — single source of model truth
    └── DESIGN_SYSTEM.md                [CUSTOMIZE, UI projects only]
```

**Path notes.** OpenCode v1.18 uses the **plural** directory names `agents/`, `commands/`, `plugins/`, `skills/`. Global equivalents live under `~/.config/opencode/` on macOS and Linux, and `%USERPROFILE%\.config\opencode\` on Windows. OpenCode also reads `.claude/skills/<name>/SKILL.md` and `~/.claude/skills/` natively — **your existing Claude Code skills work unmodified** unless you set `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`.

---

# 3. Feature Mapping: 2.1 → 2.1-OC

| Framework 2.1 (Claude Code) | 2.1-OC (OpenCode) | Notes |
|---|---|---|
| `.claude/CLAUDE.md` | `AGENTS.md` | `CLAUDE.md` also works as a fallback; `AGENTS.md` wins if both exist |
| `.claude/settings.json` | `opencode.json` | Also `opencode.jsonc` (comments + trailing commas are schema-legal) |
| `.claude/rules/*.md` (path-scoped) | `instructions: [...]` in `opencode.json` | **No path-scoping.** Globs select *files*, not activation conditions. See §6 |
| `.claude/agents/*.md` | `.opencode/agents/*.md` | Near-identical frontmatter; `effort` → `steps` + `reasoning` |
| `.claude/skills/*/SKILL.md` | `.opencode/skills/` **or** `.claude/skills/` | Read natively. `permission.skill` gates them |
| Slash commands / skills | `.opencode/commands/*.md` | `$ARGUMENTS`, `$1..$N`, `` !`cmd` ``, `@file` |
| `SessionStart` hook (cat progress) | `instructions: [".opencode/state/progress.md"]` | Deterministic, no shell |
| `SessionStart` hook (gh backlog) | `/phase-status` command with `` !`gh issue list` `` | On-demand rather than automatic — see §6.2 |
| `PreToolUse` block (exit 2) | `plugins/guard.ts` → `tool.execute.before` throws | Throwing rejects the call |
| `PostToolUse` formatter | `plugins/format.ts` → `file.edited` event, or built-in `formatter` | OpenCode ships formatters for most languages already |
| `SessionEnd` timestamp | `plugins/telemetry.ts` → `session.idle` | |
| Agent `tools:` field | `permission:` object | `tools` is **deprecated**; `permission` has pattern granularity |
| Agent `effort: max` | `steps:` cap + per-model `reasoning.effort` | Different mechanics — see §4.4 |
| `isolation: worktree` | *(no equivalent)* | Use `git worktree` manually |
| Implicit model inheritance | **Explicit tier binding** | The core change |

---

# 4. The Model Capability Profile

## 4.1 Why This Layer Exists

Three facts make model choice load-bearing in a way it is not on Claude Code:

1. **Tool calling is an endpoint property, not a model property.** With OpenRouter's default `require_parameters: false`, "providers that don't support all the LLM parameters specified in your request can still receive the request, but will ignore unknown parameters." A request carrying `tools` routed to a tool-less endpoint returns prose with `finish_reason: "stop"` and no `tool_calls`. Live, right now, `moonshotai/kimi-k3` has 12 endpoints and **2 of them (`chutes/mxfp4`, `fireworks/fast`) do not support `tools` at all**, and a third (`modal/mxfp4`) supports `tools` but not `tool_choice`, so it cannot be forced to call one. That count moved during the writing of this document — an endpoint (`wafer`) appeared between morning and evening on 2026-08-04. Re-probe rather than trusting this paragraph.

2. **Reasoning semantics differ per model and interact with tool loops.** All three of your models are reasoning-by-default. Kimi K3 and DeepSeek V4 both **reject multi-turn tool sequences that drop the prior assistant turn's `reasoning_content`** — DeepSeek returns HTTP 400 *"The reasoning_content in the thinking mode must be passed back to the API."* This is the inverse of the old `deepseek-reasoner` rule, which required *stripping* it.

3. **Sampling controls silently no-op on some models.** Kimi K3 fixes `temperature=1.0, top_p=0.95` and ignores overrides. DeepSeek V4 Flash ignores `temperature`, `top_p`, `presence_penalty` and `frequency_penalty` *while thinking is on* — which is the default. Setting `temperature: 0.1` on a reviewer agent to make it deterministic does nothing on either.

A profile is the place where those facts live once, instead of being rediscovered per agent.

## 4.2 Profile Schema

Every model used by the framework gets a record with these dimensions:

| Dimension | Values | Config consequence |
|---|---|---|
| `tier` | `DEEP` \| `ANCHOR` \| `WORKHORSE` \| `TRIVIAL` | Which agents may bind it |
| `slug` | exact OpenRouter ID | `model:` in agent frontmatter |
| `native_tools` | `yes` \| `partial` \| `no` | `no` → not eligible for any agent with tools |
| `endpoint_allowlist` | provider tags with verified `tools` | `provider.order` + `allow_fallbacks: false` |
| `structured_outputs` | `yes` \| `no` | Exclude SO-less endpoints if you use `response_format` |
| `parallel_tools` | `yes` \| `no` \| `unknown` | Affects expected step count |
| `reasoning` | `off-able` \| `default-on` \| `mandatory` | Blanket-disabling reasoning hard-fails on `mandatory` |
| `effort_levels` | actual accepted strings | Illusory levels waste config |
| `sampling` | `configurable` \| `fixed` \| `ignored-when-thinking` | Whether `temperature`/`top_p` do anything |
| `max_output` | tokens, **per endpoint** | Plan/diff truncation risk |
| `useful_context` | tokens, honest number | Compaction threshold |
| `cost` | in / out / cache-read per Mtok | Tier assignment economics |
| `edit_reliability` | `diff` \| `whole-file` \| `unknown` | Whether to trust patch-style edits |
| `known_failures` | free text | Prompt-adapter and `steps` decisions |

## 4.3 Tier Definitions

| Tier | Purpose | Typical agents | Selection criterion |
|---|---|---|---|
| **DEEP** | Hard design reasoning; the 20% of implementation that actually needs it | `architect`, `specialist` | Highest reasoning/coding index. Cost tolerated because turn count is low |
| **ANCHOR** | Long-horizon coordination and review. Holds plan state across many turns | `orchestrator`, `code-reviewer` | Large *useful* context, stable instruction-following, moderate cost. **Must differ in family from WORKHORSE** |
| **WORKHORSE** | Bulk implementation, tests, search, triage | `backend-dev`, `frontend-dev`, `test-engineer`, `issue-triage`, `researcher` | Best coding-per-dollar. This tier does 80% of the token volume |
| **TRIVIAL** | Titles, summaries, compaction | `small_model` | Cheapest thing that reliably follows format |

## 4.4 `effort` Does Not Port

Framework 2.1's `effort: max` was a Claude Code thinking-depth control. OpenCode has no `effort` frontmatter field. The equivalent behaviour is split across two independent knobs:

- **`steps`** — the maximum number of agentic iterations before the agent is forced to reply in text only. This is your *runaway guard*, and it is the single most important cost control in a K3-heavy setup. The legacy `maxSteps` field is deprecated.
- **`reasoning.effort`** — a provider-level parameter passed through `provider.<id>.models.<model>.options`, or via a named **variant**. Accepted values differ per model and several advertised levels are fake (see §4.5).

Rule of thumb: `effort: max` in 2.1 → `steps: 40` + a `deep` variant with `reasoning.effort` at that model's real ceiling.

The scaffold makes one deliberate exception: the ANCHOR model's `deep` variant sits at `high`, not its `xhigh` ceiling. `xhigh` is already Qwen3.8 Max's *default*, and on an orchestrator taking dozens of turns it is the single largest silent cost in the config. `high` is the escalation; `xhigh` is available by removing the pin entirely.

## 4.5 Profiles — Your Three Models

Everything below was read from the live OpenRouter models and endpoints API on 2026-08-04 and cross-checked against vendor documentation.

### DEEP — `moonshotai/kimi-k3`

| | |
|---|---|
| Cost | **$3.00 in / $15.00 out** per Mtok · cache read $0.30 (90% off) · no cache-write charge |
| Context | 1,048,576 · `top_provider.max_completion_tokens` is **null**; per-endpoint values range 65,535 – 1,048,576 |
| Architecture | 2.8T total / 104B active MoE, multimodal (text + image), MXFP4 weights with quantisation-aware training |
| Tools | Native OpenAI-style. `json_schema` with `strict: true` supported |
| **Endpoint allowlist** (tools + tool_choice) | 9 of 12: `morph` (cheapest, $2.90), `moonshotai/mxfp4`, `together`, `fireworks`, `wafer`, `wafer/fast`, `morph/fast`; plus `baseten/fp8`* and `digitalocean`* |
| **Endpoints to AVOID** | **`chutes/mxfp4` and `fireworks/fast` have NO `tools`.** `modal/mxfp4` has `tools` but no `tool_choice`. \*`baseten/fp8` and `digitalocean` lack `structured_outputs` |
| Reasoning | **Always on**, not disableable. `reasoning_effort` accepts exactly `low` \| `high` \| `max`. Default `max`. Note: no `medium` |
| Sampling | **Fixed. `temperature=1.0`, `top_p=0.95`, non-configurable.** Setting temperature is a no-op |
| Known failures | Documented by Moonshot as *"excessively proactive on ambiguous tasks; may make decisions on the user's behalf."* Emits ~2× the median output token volume at $15/Mtok. Below-median throughput (~62 tok/s). Dropping reasoning history from the transcript **degrades quality**, not just API validity — it operates in preserved-thinking-history mode |
| Indices | intelligence 57.1 · coding 76.2 · agentic 50.1 (Artificial Analysis, via OpenRouter) |

**Framework consequences:** cap `steps` hard (25–40). Never set `temperature`. Do not enable `compaction.prune`. Give it unambiguous, fully-specified tasks — its documented failure mode is filling ambiguity with unrequested action, which is exactly what a delegation prompt with vague acceptance criteria produces.

### ANCHOR — `qwen/qwen3.8-max`

| | |
|---|---|
| Cost | **$2.00 in / $6.00 out** per Mtok · cache read $0.25 · **cache WRITE $2.50 (1.25× input)** |
| Context | 1,000,000 advertised — **but Alibaba documents usable input as 983,616 when thinking is on** |
| Max output | 131,072 |
| Tools | Native. Parallel tool calls supported |
| **Endpoint allowlist** | `alibaba` — **the only endpoint. No failover exists.** |
| Reasoning | **`mandatory: true`.** Cannot be disabled through OpenRouter. Effort ∈ `minimal` \| `low` \| `medium` \| `high` \| `xhigh`, **defaulting to `xhigh`** — the most expensive setting, silently |
| Sampling | Configurable |
| Known failures | **Cannot force a specific tool while thinking is active** — `tool_choice: {"type":"function",...}` needs a fallback path. Replayed reasoning history is billed as input tokens |
| Indices | intelligence 53.4 · coding 68.9 · agentic 49.9 |
| Weights | Announced 2026-08-03, **not yet published**. Not open-weight as of today; license undisclosed |

**Framework consequences:** explicitly set `reasoning.effort` to `medium` or `high` for routine orchestration — the `xhigh` default is a real cost leak on an agent that takes many turns. Because there is exactly one provider, configure a fallback model at the framework level. Size compaction against 983K, not 1M. Do not adopt an aggressive explicit-caching strategy: at 1.25× input for a write, caching a churning agent prefix costs more than not caching.

### WORKHORSE — `deepseek/deepseek-v4-flash-0731`

| | |
|---|---|
| Cost | **$0.09 in / $0.18 out** per Mtok · cache read $0.018 |
| Context | 1,048,576 |
| **Max output** | **Only 65,536 on the cheapest endpoint (`deepinfra/fp4`).** `parasail/fp8` and `ambient/fp4` allow 1,048,576; `deepseek/fp8` and `cloudflare/fp8` allow 384,000 |
| Tools | Native, on every endpoint |
| **Endpoint allowlist** | `deepinfra/fp4`, `fireworks`, `together`, `cloudflare/fp8`, `parasail/fp8`, `atlas-cloud/fp8`; plus `ambient/fp4` in the `longform` variant |
| Endpoints lacking `structured_outputs` | `gmicloud/fp8`, `novita/fp8`, `deepseek/fp8` |
| Reasoning | Default-on. Effort accepts `low`/`medium`/`high`/`max` but **`low` and `medium` both map internally to `high`, and `xhigh` maps to `max` — only two real levels exist** |
| Sampling | **`temperature`, `top_p`, `presence_penalty`, `frequency_penalty` are silently ignored while thinking is on** (which is the default) |
| Indices | intelligence 49.9 · **coding 69.1** · agentic 45.7 |

> ### ⚠️ The slug trap
> **`deepseek/deepseek-v4-flash` is NOT this model.** The unsuffixed slug resolves to the **April 0423 build**, which is *older*, *worse*, and *more expensive* ($0.14/$0.28). Pin `deepseek/deepseek-v4-flash-0731`, or use the floating alias `~deepseek/deepseek-v4-flash-latest`.

**The headline finding for your setup:** V4 Flash 0731's coding index (69.1) is **marginally higher than Qwen3.8 Max's (68.9) at roughly 1/22nd of the input price and 1/33rd of the output price.** You are currently using V4 Flash for "simpler chat sessions." It should be doing the majority of your implementation volume, with K3 reserved for the genuinely hard 20%. That single reallocation is the largest cost lever in this document.

## 4.6 Cross-Model Hazards

These apply regardless of which model sits in which tier.

**The `reasoning_content` passback contract.** Kimi K3 and DeepSeek V4 both require that the complete prior assistant message — including `reasoning_content` *and* `tool_calls` — be replayed into `messages[]` on the next turn of a tool loop. Dropping it produces `HTTP 400: The reasoning_content in the thinking mode must be passed back to the API` (DeepSeek) or `thinking is enabled but reasoning_content is missing in assistant tool call message at index [N]` (Kimi). This has broken n8n (#29661) and OpenCode itself (#24130, fixed in #24146 via an `interleaved` config). If you see either error, you are on a build that regressed this — pin a known-good OpenCode version rather than fighting it.

**OpenCode's extra top-level fields.** OpenCode issue #37771: OpenCode sends non-standard top-level `mcp` and `system` fields, which strict upstream validators reject with `Extra inputs are not permitted, field: mcp`. This surfaces as a generic *"Upstream request failed."* **Affects `kimi-k3`, `kimi-k2.6`, `kimi-k2.7-code`, `qwen3.7-max` and relatives. DeepSeek tolerates it.** So the same harness silently works on your workhorse and hard-fails on your DEEP tier. Check this first when K3 errors and Flash does not.

**Auto Exacto and the `:floor` trap.** OpenRouter runs *Auto Exacto* by default on every request containing `tools` — it reorders providers by measured Tool Call Error Rate and throughput. Setting `provider.sort: "price"` or appending the `:floor` suffix **silently opts out of it**. A cost-optimising config that reflexively appends `:floor` degrades tool-calling reliability. Never use `:floor` on an agentic model.

**`require_parameters: true` is a double-edged filter.** It is the only hard guard against `tools` being dropped — but it filters on *every* parameter in the request. Sending an extra param such as `top_k`, `seed` or `logprobs` alongside it can collapse the eligible endpoint set to zero and produce a no-provider-available error. Send the minimal parameter set.

**`order` alone does not restrict.** OpenRouter proceeds to unlisted providers if the listed ones are down. `order` **must** be paired with `allow_fallbacks: false`. Separately, `provider.order` **disables prompt-cache sticky routing** — pinning providers for determinism costs you cache hits. And note that base slugs prefix-match: `"fireworks"` also matches `"fireworks/fast"`, which is one of the K3 endpoints that lacks tools.

**Account-level settings override per-request config.** Allowed/ignored provider lists at `openrouter.ai/settings/privacy` are *merged* with per-request `only`/`ignore`. Your framework config is not fully authoritative. Check the dashboard once.

**No working `:free` tier.** `moonshotai/kimi-k3:free`, `qwen/qwen3.8-max:free` and `deepseek/deepseek-v4-flash:free` all resolve to pages with **zero live endpoints**.

## 4.7 Benchmarks: What Not to Trust

No lab publishes SWE-bench Verified, τ-bench/τ²-bench, or BFCL for any of these three models. They report DeepSWE, Terminal-Bench 2.1, Toolathlon, Agents' Last Exam and AutomationBench instead. Any SWE-bench Verified percentage you see quoted for K3 is inferred or vendor-run, not measured. Moonshot's own comparison table additionally **mixes harnesses across rows** (Kimi Code, Claude Code, Codex, mini-SWE-agent), so cross-model deltas in it are not controlled comparisons.

Vendor-reported, same table, ~2026-08-03: Terminal-Bench 2.1 — K3 88.3 / Qwen3.8-Max 86.6 / V4 Flash 82.7. DeepSWE 1.1 — 67.5 / 56.6 / 54.4. Toolathlon Verified — 76.5 / 72.5 / 70.3.

Note the shape of the Artificial Analysis numbers: K3's **coding** lead is large (76.2 vs 69.1) but its **agentic** lead is not (50.1 vs 45.7). Long-horizon tool use is where all three converge — which is precisely the regime an orchestration framework operates in. That is the empirical justification for the tiering in §4.3: buy K3 for hard reasoning, not for agentic stamina.

---

# 5. AGENTS.md — The Orchestrator Contract

`AGENTS.md` replaces `CLAUDE.md`. It is read from the project root (traversing upward), then `~/.config/opencode/AGENTS.md`, then `~/.claude/CLAUDE.md` as a Claude Code fallback. **The first match in each category wins** — if you have both `AGENTS.md` and `CLAUDE.md` in the project, only `AGENTS.md` is used.

Two changes from the 2.1 template matter.

**First, the delegation instructions must be explicit and worked-through.** OpenCode issue #22244 documented Gemini *never once* invoking the Task tool because OpenCode's `gemini.txt` system prompt omitted the delegation section that `anthropic.txt` and `default.txt` contained. Delegation failure on a non-Claude model is almost always a prompt-adapter gap, not a capability gap. Your `AGENTS.md` must therefore state the delegation rule, give the routing table, **and show a worked example** — not just assert the principle.

**Second, no negative-only constraints.** Replace "NEVER write implementation code" with a positive contract ("your job is to produce delegation prompts and verify their output") *plus* the permission that makes it true. The prose is there so the model understands the shape of its job; the permission is there because the prose will not hold under pressure.

---

# 6. Rules and Context Injection

## 6.1 There Is No Path-Scoping

This is the sharpest capability regression from Claude Code. Framework 2.1's `rules/code-style.md` used YAML frontmatter `paths:` so the rule injected only when Claude touched matching files. **OpenCode has no equivalent.** The `instructions` array accepts globs, but the globs select *which files to load*, not *when to load them*. Everything in `instructions` is concatenated with `AGENTS.md` and loaded every session.

Three viable strategies:

1. **Consolidate.** Fold `code-style.md`, `testing.md` and `git-conventions.md` into the agent prompts of the agents that need them. `test-engineer.md` carries the testing standards in its body; `backend-dev.md` carries the code standards. This is the recommended default — it keeps per-session context small and puts each rule where its reader is.
2. **Lazy-load by instruction.** Keep separate rule files and teach the model to read them, as the OpenCode docs themselves suggest: *"When you encounter a file reference (e.g. @rules/general.md), use your Read tool to load it on a need-to-know basis."* Works, but depends on model compliance — which is exactly what §1 says not to rely on. Acceptable for advisory rules, not for constraints.
3. **Always-load the small ones.** `instructions: [".opencode/state/progress.md", "docs/MODEL_PROFILES.md"]`. Correct for state and profiles, which every agent needs.

2.1-OC uses (1) for standards and (3) for state.

## 6.2 The SessionStart Backlog Injector

2.1 injected the open GitHub issue backlog at session start via a `SessionStart` hook. OpenCode's plugin events are `session.created`, `session.updated`, `session.idle` and so on, but there is **no documented event that injects text into the model's initial context**. `tui.prompt.append` writes to the *user's input box*, which is not the same thing.

The honest port is **on-demand rather than automatic**: `/phase-status` uses command-level shell injection (`` !`gh issue list ...` ``) to pull the backlog into the prompt when you ask for it. This is a genuine loss of determinism relative to 2.1, and it is called out here rather than papered over. Run `/phase-status` at the start of a session; it is one keystroke and it also gives you the phase state and git log.

---

# 7. Agents

## 7.1 Frontmatter Reference (OpenCode v1.18)

| Field | Type | Purpose |
|---|---|---|
| `description` | string | **Required.** Drives Task-tool auto-invocation. Be specific — this is how the orchestrator picks |
| `mode` | `primary` \| `subagent` \| `all` | Defaults to `all`. `primary` = Tab-cyclable; `subagent` = `@mention` or Task tool |
| `model` | `provider/model-id` | **2.1-OC sets this explicitly on every agent.** Subagents otherwise inherit from the invoking primary |
| `temperature` | 0.0–1.0 | *Verify it does anything on your model* — see §4.5 |
| `top_p` | 0.0–1.0 | Alternative to temperature |
| `steps` | number | Max agentic iterations before forced text-only reply. **The cost guard.** (`maxSteps` is deprecated) |
| `permission` | object | The enforcement layer. See §7.2 |
| `prompt` | `{file:./path}` | External system prompt |
| `options` | object | **Provider options, passed through verbatim.** This is how 2.1-OC sets `reasoning.effort` per agent |
| `variant` | string | Select a named variant from `provider.<id>.models.<model>.variants` |
| `hidden` | boolean | Hide from `@` autocomplete; still Task-invocable |
| `disable` | boolean | Turn the agent off |
| `color` | hex or theme name | `primary`/`secondary`/`accent`/`success`/`warning`/`error`/`info` |
| *anything else* | — | **Silently swallowed into `options`** — no error, no warning. A typo like `temprature:` or `permissions:` (plural) fails silently. Always use the explicit `options:` block |
| `tools` | object | **Deprecated.** Use `permission` |

## 7.2 Permissions — The Enforcement Layer

Every key takes `"allow"`, `"ask"` or `"deny"`. The keys `read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`, `external_directory`, `lsp` and `skill` additionally accept an object mapping glob patterns to actions. The remaining keys (`todowrite`, `webfetch`, `websearch`, `question`, `doom_loop`) take the shorthand only.

| Key | Gates |
|---|---|
| `read` | `read` |
| `edit` | `write`, `edit`, `apply_patch` |
| `bash` | `bash` |
| `task` | `task` — **which subagents this agent may invoke** |
| `external_directory` | any tool touching files outside the worktree |
| `webfetch` / `websearch` | network reads |
| `skill` | skill loading, by name pattern |
| `doom_loop` | recovery prompts when an agent appears stuck |

### `ask` is friction, not a decision point

Worth knowing before you design a permission map: agents route around `ask`.

Observed in a real run — `uv add*` was set to `ask`, and the orchestrator's delegation prompt instructed the subagent to *"declare dependencies by editing pyproject.toml directly, then run `uv lock`. Do not use `uv add`."* The outcome was identical and arguably better, so this was benign. But the mechanism is general: given two paths to the same result, an agent takes the one that does not stop to ask.

So `ask` is useful as a speed bump on things you want to *notice*, and unreliable as a gate on things you want to *approve*. If a human decision genuinely has to happen, use `deny` and let the agent escalate to you — that produces a conversation, where `ask` produces a workaround.

Note also that **bash permissions match parsed commands, not command lines.** `ls*` will not match `ls -la && ls docs`, and a pattern containing a pipe can never match anything. Compound commands are split before matching, which costs agents a turn when they discover it.

**Rules are evaluated in order and the last match wins.** Put `"*"` first and specific rules after:

```yaml
permission:
  bash:
    "*": deny
    "git status*": allow
    "git diff*": allow
    "npm test*": allow
```

**`permission.task` is the delegation firewall** and it is the single most important construct in 2.1-OC:

```json
"permission": {
  "task": {
    "*": "deny",
    "backend-dev": "allow",
    "frontend-dev": "allow",
    "code-reviewer": "allow"
  }
}
```

When a subagent is set to `deny`, **it is removed from the Task tool's description entirely**, so the model never sees it and cannot attempt it. This is capability removal, not instruction. It is exactly the mechanism that Kiro issue #5922 demonstrated is the *only* thing that binds. Note that a *user* can still `@mention` any subagent directly regardless of task permissions — the firewall constrains the model, not you.

## 7.3 Heterogeneous Review

`code-reviewer` binds to the **ANCHOR** tier while `backend-dev` and `frontend-dev` bind to **WORKHORSE**. This is deliberate and it is a capability you did not have on Claude Code.

A same-model review is structurally weak: the reviewer shares the implementer's training distribution, its tokenizer biases, its blind spots, and — with reasoning models — often its reasoning trajectory. It is disproportionately likely to find the errors the implementer was already close to catching and to miss the ones it is systematically blind to. Running the review on a different lab's model turns a correlated check into a partially independent one.

Concretely: DeepSeek V4 Flash implements, Qwen3.8 Max reviews. If the review pass starts feeling like a rubber stamp, swap the reviewer to K3 rather than raising its `reasoning.effort`.

## 7.4 The Roster

| Agent | Mode | Tier | `edit` | `bash` | `task` | Purpose |
|---|---|---|---|---|---|---|
| `orchestrator` | primary (default) | ANCHOR | `deny` | read-only patterns | allowlist | Plans, delegates, verifies. **Cannot write code** |
| `architect` | primary | DEEP | `deny` | read-only patterns | `deny` | Design reasoning, ARCHITECTURE.md authorship, tradeoff analysis |
| `backend-dev` | subagent | WORKHORSE | `allow` | `allow` | `deny` | Server/data/systems implementation |
| `frontend-dev` | subagent | WORKHORSE | `allow` | `allow` | `deny` | UI implementation |
| `specialist` | subagent | DEEP | `allow` | `allow` | `deny` | The hard 20% — concurrency, algorithms, gnarly debugging |
| `test-engineer` | subagent | WORKHORSE | scoped to tests | `allow` | `deny` | Test authorship and execution |
| `code-reviewer` | subagent | ANCHOR | `deny` | read-only | `deny` | **Mandatory gate.** Different family from implementers |
| `issue-triage` | subagent | WORKHORSE | `deny` | `gh *` only | `deny` | GitHub issue logging and triage |
| `researcher` | subagent | WORKHORSE | `deny` | read-only | `deny` | Codebase and external research |

Note that **no subagent can invoke another subagent** (`task: deny` everywhere below the orchestrator). This prevents recursive delegation storms, which are a documented failure mode and are expensive on a $15/Mtok output model. It also mirrors Cline's design, which gives subagents six read-only tools and forbids nested spawning.

---

# 8. Orchestration Loop

Unchanged in structure from 2.1, with two additions.

```
0. PREFLIGHT   — /model-check once per session, or after any model/provider change
1. UNDERSTAND  — read the current phase in docs/INSTRUCTIONS.md
2. PLAN        — break into delegatable tasks; identify dependencies
3. DELEGATE    — send prompts with FULL context (see §8.1)
4. COORDINATE  — sequence dependent tasks; pass outputs forward
5. VERIFY      — run tests. MANDATORY review gate: implementation → code-reviewer → issue-triage.
                 Unconditional; not gated on the orchestrator's confidence.
                 Any defect found but NOT fixed this phase → /log-issue before closing.
6. BREAKPOINT  — at the phase boundary run /milestone-review: sweep a tier now, or defer.
```

**Step 0 is new.** Endpoint capability changes without notice. `/model-check` hits the OpenRouter endpoints API for each pinned model and fails loudly if a pinned provider has stopped advertising `tools`.

## 8.1 The Delegation Prompt Template

On Claude Code a terse delegation prompt is usually enough. It is not enough here. Weaker-model failure analysis consistently traces bad subagent output to under-specified prompts rather than model incapacity, and K3 specifically is documented as *filling ambiguity with unrequested action*. Every delegation carries all six fields:

```
@{agent}: {one-sentence task}

Files:        {exact paths to create or modify — no globs, no "the relevant files"}
Context:      {docs/ARCHITECTURE.md §N; any file the agent must read first}
Requirements: {numbered, specific, each independently checkable}
Done when:    {measurable criteria lifted verbatim from INSTRUCTIONS.md}
Out of scope: {what NOT to touch — the single highest-value line for K3}
Report:       {what to return: files changed, test results, anything deferred}
```

The `Out of scope:` line exists because *positive* constraints bind better than negative ones on these models, and because bounding the blast radius is cheaper than reviewing an over-eager diff.

---

# 9. Context and Compaction

Compaction thresholds across agents are **formulas involving max output tokens, not flat percentages** — Roo uses `contextWindow × 0.9 − maxOutputTokens`; Claude Code uses `contextWindow − min(maxOutput, 20k) − 13k`. Hardcoding a percentage overruns on reasoning models with large reserved output budgets, which is all three of yours.

OpenCode exposes:

```json
"compaction": { "auto": true, "prune": false, "reserved": 32000 }
```

- **`prune: false` is deliberate and should stay false.** Pruning removes old tool outputs to save tokens. Kimi K3 operates in *preserved thinking history mode* and its own evaluation guidance states that dropping reasoning history produces unstable performance. On a K3 agent, pruning trades a small token saving for solve-rate variance.
- **`reserved: 32000`** is sized for reasoning models. The default (10,000) assumes a non-reasoning output budget.
- Set `OPENCODE_DISABLE_AUTOCOMPACT` only when debugging.

Two further context notes: Qwen3.8 Max's usable input drops to **983,616** when thinking is on, so do not budget against the round 1M. And DeepSeek V4 Flash on the cheapest endpoint caps output at **65,536** despite the 1M context — long plan or diff generation will truncate unless you route to `parasail/fp8` or `cloudflare/fp8`.

---

# 10. Issue Tracking and Triage

Carries over from 2.1 §9 essentially unchanged — it is `gh`-based and model-independent. Label taxonomy (one `type:` + one `severity:` per issue), breakpoint-tier milestones, `Refs #NN` with no auto-close, and user-only issue closing all stand.

Three OpenCode-specific adjustments:

1. The always-loaded `issue-tracking.md` rule becomes a section inside `AGENTS.md`, since there is no path-scoped rule loading.
2. The `issue-triage` agent keeps its tool scoping, now expressed as `permission` rather than `tools`:
   ```yaml
   permission:
     edit: deny
     task: deny
     bash:
       "*": deny
       "gh *": allow
       "git log*": allow
       "git status*": allow
   ```
3. The backlog is surfaced by `/phase-status` rather than a SessionStart hook (§6.2).

---

# 11. Plugins — The Hook Replacement

OpenCode plugins are JS/TS modules in `.opencode/plugins/` (project) or `~/.config/opencode/plugins/` (global), auto-loaded at startup. A plugin exports an async function receiving `{ project, client, $, directory, worktree }` and returning a hooks object.

| 2.1 hook | 2.1-OC plugin hook |
|---|---|
| `PreToolUse` matcher + `exit 2` | `"tool.execute.before": async (input, output) => { ... throw new Error(...) }` |
| `PostToolUse` formatter | `event: ({event}) => { if (event.type === "file.edited") ... }`, or the built-in `formatter` config |
| `SessionEnd` timestamp | `event.type === "session.idle"` |
| Environment injection | `"shell.env": async (input, output) => { output.env.X = "..." }` |

`$` is Bun's shell API. Local plugins can use npm packages if you add a `.opencode/package.json` — OpenCode runs `bun install` at startup.

2.1-OC ships three:

- **`guard.ts`** — rejects reads *and* writes to secret-shaped paths (`.env*`, `*secret*`, `*credential*`, `*.pem`, `id_rsa`, `.netrc`), and rejects *writes* to lockfiles (reads of a lockfile are fine and often necessary). It handles `apply_patch` separately — that tool carries `patchText`, not `filePath`, and on GPT-class models it is the *only* write tool OpenCode exposes. It also scans `bash`, because `cat .env` would otherwise route around the file-tool checks entirely and OpenCode's bash permission patterns match parsed commands, so a pattern containing a pipe can never match.

  For bash it tests **path-like tokens, not the raw command string** — with quoted spans stripped first. This is a correction from a real run, and the reasoning generalises. The original version matched `/secret/i` against the whole command, which blocked a legitimate `gh label create "type:security" -d "Vulnerability, secret exposure, unsafe input"`; the agent then spent four turns trying to smuggle the word past the check, escalating to `printf '%s' 'secret'` and finally reasoning explicitly about making the substring non-contiguous. It behaved that way because the denial message claimed a "protected path" was involved when none was — so it correctly inferred a false positive. **A guard whose message is inaccurate teaches agents to evade guards in general**, including the ones that are right. Any rule you add should name the exact token that matched and state that the remedy is to change the rule, not to reword the command.
- **`format.ts`** — a thin `file.edited` formatter hook. Note OpenCode already ships built-in formatters (`"formatter": true`); this exists for project-specific commands the built-ins do not cover.
- **`telemetry.ts`** — the interesting one. It records every failed tool call, with the agent and model responsible, to `.opencode/state/tool-errors.jsonl`. Over a week this gives you *your own* measured tool-call error rate per model on *your* workload, which is worth considerably more than any published benchmark for deciding tier assignments. Feed it back into §4.5.

---

# 12. Known Regressions vs Framework 2.1

Stated plainly rather than glossed.

| 2.1 capability | 2.1-OC status |
|---|---|
| Path-scoped rule injection (`paths:` frontmatter) | **Lost.** Fold rules into agent prompts (§6.1) |
| Deterministic SessionStart context injection | **Partially lost.** `instructions` covers static files; the dynamic `gh` backlog moves to on-demand `/phase-status` (§6.2) |
| `isolation: worktree` on an agent | **Lost.** Use `git worktree` manually |
| `effort:` frontmatter | **Replaced** by `steps` + per-model `reasoning.effort` (§4.4) |
| Model-agnostic agent definitions | **Deliberately abandoned.** Explicit tiering is the point of 2.1-OC |
| Reliable negative-constraint prose | **Never actually worked; now made explicit.** Enforce via `permission` |

And two things that got *better*:

- `permission.task` gives per-subagent delegation control with pattern matching, which Claude Code has no equivalent of.
- `permission.bash` glob patterns are finer-grained than Claude Code's allow/deny string list.

---

# 13. Setup Checklist

| # | Task |
|---|---|
| 1 | `opencode auth login` → OpenRouter, paste `sk-or-...` (or run `/connect`) |
| 2 | Copy `scaffold/` contents into the project root |
| 3 | `bash .opencode/scripts/preflight.sh` — confirms every pinned model still advertises `tools` on its allowlisted providers |
| 4 | Customise `docs/ARCHITECTURE.md` and `docs/INSTRUCTIONS.md` |
| 5 | Customise `AGENTS.md`: project name, delegation table, build/test commands |
| 6 | Customise `backend-dev.md` / `frontend-dev.md` for the stack; delete `frontend-dev` on CLI/API projects |
| 7 | Fold code-style and testing standards into those agent prompts (§6.1) |
| 8 | Seed `.opencode/state/progress.md` with Phase 1 |
| 9 | `gh auth login`; run the label bootstrap; create initial milestone tiers |
| 10 | Add `.opencode/state/` and `opencode.local.json` to `.gitignore` |
| 11 | Launch `opencode`, run `/model-check`, then `/phase-plan` |

---

# Appendix A. Change Log

| Date | Version | Change |
|---|---|---|
| 2026-08-04 | 2.1-OC | Port of Agentic Framework 2.1 to OpenCode. Added the Model Capability Profile layer (§4) with verified profiles for `moonshotai/kimi-k3`, `qwen/qwen3.8-max` and `deepseek/deepseek-v4-flash-0731`. Replaced prose role constraints with `permission`-based enforcement (§1, §7.2). Introduced tiering (DEEP/ANCHOR/WORKHORSE/TRIVIAL) and heterogeneous review (§7.3). Documented OpenRouter endpoint-level tool-capability pinning (§4.6). Mapped hooks→plugins (§11). Recorded regressions honestly (§12). |
| 2026-06-30 | 2.1 | Issue Tracking & Triage subsystem (Claude Code) |
| 2026-04-10 | 2.0 | Initial orchestrator-subagent specification |

*End of Specification — Agentic Framework 2.1-OC*
