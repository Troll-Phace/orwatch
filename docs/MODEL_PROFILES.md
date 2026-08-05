# MODEL_PROFILES.md

> Loaded into every session via `instructions` in `opencode.jsonc`.
> Keep it short — everything here costs context on every single turn.
> The long-form reasoning behind these values is in `docs/SPEC.md §4`.
>
> **Verified against the live OpenRouter API on 2026-08-05.**
> Re-verify with `bash .opencode/scripts/preflight.sh` or `/model-check`.

## Tier Map

| Tier | Model | Agents |
|---|---|---|
| **DEEP** | `openrouter/moonshotai/kimi-k3` | `architect`, `specialist` |
| **ANCHOR** | `openrouter/qwen/qwen3.8-max` | `orchestrator`, `code-reviewer` |
| **WORKHORSE** | `openrouter/deepseek/deepseek-v4-flash-0731` | `backend-dev`, `test-engineer`, `issue-triage`, `researcher` |
| **TRIVIAL** | `openrouter/deepseek/deepseek-v4-flash-0731` | `small_model` (titles, summaries, compaction) |

Swap a tier: `bash .opencode/scripts/retier.sh WORKHORSE <new/slug>`, then update the provider allowlist in `opencode.jsonc` (and `model` / `small_model` if you re-tiered ANCHOR or WORKHORSE) and re-run preflight.

### Why only two endpoints are pinned for DEEP

Nine of Kimi K3's twelve endpoints are tool-capable, but provider slugs in `order` **match by prefix**, so a bare tag pulls in its `/fast` sibling too:

- `fireworks` → also `fireworks/fast`, which has **no tools at all**
- `morph` → also `morph/fast` at $6.00/$22.50 vs $2.90/$14.00
- `wafer` → also `wafer/fast` at $4.50/$22.50 vs $3.00/$15.00

`moonshotai/mxfp4` and `together` have no such sibling, both carry structured outputs, and both are $3.00/$15.00. That is why the allowlist looks smaller than the probe output suggests it could be.

## Cost

| Tier | In / Out per Mtok | Cache read | Relative output cost |
|---|---|---|---|
| DEEP | $3.00 / $15.00 | $0.30 | **83×** |
| ANCHOR | $2.00 / $6.00 | $0.25 (write $2.50) | 33× |
| WORKHORSE | $0.09 / $0.18 | $0.018 | 1× |

The DEEP tier also emits roughly **twice the median output token volume**, so its effective cost per completed task is worse than the headline ratio. Route to it deliberately.

## Behavioural Constraints That Change How You Work

| | DEEP (Kimi K3) | ANCHOR (Qwen3.8 Max) | WORKHORSE (V4 Flash 0731) |
|---|---|---|---|
| Native tool calling | yes | yes | yes |
| Reasoning | **always on**, not disableable | **mandatory** | default on |
| Effort levels that are real | `low` `high` `max` (no `medium`) | `minimal`→`xhigh` (all real) | only 2 real: `low`/`medium`→high, `xhigh`→max |
| `temperature` / `top_p` | **fixed and ignored** (1.0 / 0.95) | configurable | **ignored while thinking** |
| Force a specific tool | yes | **no** — not while thinking | yes |
| Usable context | 1,048,576 | **983,616** with thinking on | 1,048,576 |
| Max output | unset on `top_provider`; 65,535–1,048,576 by endpoint | 131,072 | **65,536** on `deepinfra/fp4` |
| Endpoints with tools **and** `tool_choice` | 9 of 12 (`chutes/mxfp4` + `fireworks/fast` lack `tools`; `modal/mxfp4` lacks `tool_choice`) | **1** — no failover | 19 of 19 |

## Rules That Follow

1. **Never set `temperature` to control determinism.** It is inert on DEEP (fixed) and on WORKHORSE (ignored while thinking). Constrain with explicit requirements and schemas instead.
2. **Never enable `compaction.prune`.** Kimi K3 runs in preserved-thinking-history mode and degrades — in solve rate, not just API validity — when reasoning history is dropped.
3. **Never use the `:floor` suffix or `provider.sort: "price"`** on an agentic model. Both silently opt out of OpenRouter's Auto Exacto, which is the default routing by measured tool-call error rate.
4. **`deepseek/deepseek-v4-flash` without `-0731` is the wrong model** — it is the older April build, worse *and* more expensive ($0.14/$0.28 vs $0.09/$0.18).
5. **Split long output.** WORKHORSE caps at 65,536 output tokens on its default provider. Do not ask an agent for an enormous file in one turn — stage the work instead. (A `longform` variant exists that routes to 384K–1M-output endpoints, but variants are selected by *you* via the `variant_cycle` keybind or an agent's `variant:` frontmatter field. An agent cannot switch its own variant mid-task.)
6. **Give the DEEP tier hard boundaries.** Its vendor documents it as *excessively proactive on ambiguous tasks, liable to make decisions on the user's behalf*. Every delegation to it carries an explicit `Out of scope:` line.
7. **`qwen/qwen3.8-max` has exactly one provider.** An Alibaba outage is a total outage for the ANCHOR tier. If orchestration starts failing with upstream errors, re-tier ANCHOR to `moonshotai/kimi-k3` temporarily.

## Measured Tool-Call Behaviour

From the Phase 1 run on 2026-08-05 (86 tool calls, ANCHOR tier):

**Qwen 3.8 Max emits a trailing empty tool call.** 21 of 86 (24%) resolved to a
tool named `unknown`. Every one had input `{}` and every one followed a
*successful* call in the same assistant message — a malformed trailing entry in
the `tool_calls` array, not a wrong tool choice. Correlates most with
`todowrite` (4/4) and `read`.

**Impact: none.** The harness recovered 21/21. It costs a wasted dispatch and
some context. This is not a reason to re-tier — the shape of the failure is
inert. Hallucinated tool *names* would be a different matter.

**Cost baseline.** A complete phase — plan, four delegations, review gate, one
logged issue, decisions folded back, commit — cost **$2.06**: 766k input, 17k
output, 20k reasoning, 1.21M cache reads. If a phase costs several times that,
something is looping; check the `steps` caps first.

## Known Harness Incompatibility

OpenCode sends non-standard top-level `mcp` and `system` fields. Strict upstream validators reject these with `Extra inputs are not permitted, field: mcp`, surfaced as a generic **"Upstream request failed."**

- **Affected:** `kimi-k3`, `kimi-k2.6`, `kimi-k2.7-code`, `qwen3.7-max` and relatives — i.e. your DEEP and possibly ANCHOR tiers.
- **Not affected:** DeepSeek models — i.e. your WORKHORSE tier.

**Diagnostic:** if the DEEP tier fails on every request while the WORKHORSE tier works fine, this is the cause, not your config. Tracked as OpenCode issue #37771. Pin a known-good OpenCode version rather than debugging your own setup.

A second class of the same problem: Kimi and DeepSeek both require the prior assistant turn's `reasoning_content` to be replayed in multi-turn tool loops. Symptoms are `HTTP 400: The reasoning_content in the thinking mode must be passed back to the API` or `thinking is enabled but reasoning_content is missing in assistant tool call message at index [N]`. This was an OpenCode bug (#24130), fixed in #24146 — if you see it, you are on a regressed build.

## Escalation Policy

| Situation | Action |
|---|---|
| Routine implementation | WORKHORSE. This is 80% of volume |
| Large but mechanical | WORKHORSE. Size is not a reason to escalate |
| A WORKHORSE agent failed twice with specific feedback | Escalate to `specialist` (DEEP) |
| Concurrency, lifetimes, memory layout, non-obvious algorithms | `specialist` (DEEP) directly |
| Bug not localised after one investigation pass | `specialist` (DEEP) |
| Architecture decision, tradeoff analysis | `architect` (DEEP), Tab to it |
| Code review | `code-reviewer` (ANCHOR) — **always a different family than the implementer** |

## Calibration

`.opencode/state/tool-errors.jsonl` accumulates every failed tool call with the tool name and arguments. After a week of real use it is a better guide to tier assignment than any published benchmark, because it measures *your* tool schemas on *your* tasks.

Worth knowing about the published numbers: no lab publishes SWE-bench Verified, τ-bench or BFCL for any of these three models, and the vendor tables that do exist mix harnesses across rows. The Artificial Analysis indices are the most comparable figures available — and note their shape: DEEP leads on **coding** (76.2 vs 69.1) but barely on **agentic** (50.1 vs 45.7). Long-horizon tool use is where the three converge, which is exactly the regime this framework operates in.
