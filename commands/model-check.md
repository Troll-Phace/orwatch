---
description: Live capability probe — verify every pinned model still advertises tool calling on its allowlisted OpenRouter providers. Run once per session and after any model or provider change.
agent: orchestrator
---

# Model Check

!`bash .opencode/scripts/preflight.sh 2>&1`

## Do this

> **If the block above is empty, you have no probe result — you do not have a
> passing one.** Shell injection in commands is unreliable (a real run had every
> injected block in `/phase-plan` return its failure branch while the same
> commands worked from the agent's own `bash` tool). Reporting "healthy" from an
> empty block is the worst possible outcome here, because the whole point of
> this command is to catch a tier that has silently lost tool calling. If the
> block is empty, run `bash .opencode/scripts/preflight.sh` yourself and report
> from that.

Read the output above and report, in under 10 lines:

1. Any model where **zero** allowlisted providers advertise `tools`. This is a hard failure — agents bound to that tier will silently receive prose instead of tool calls. Say so plainly and name the affected agents.
2. Any model where the allowlist has thinned to one provider (no failover), or where a pinned provider has disappeared entirely.
3. Any price change greater than 20% from the values recorded in `docs/MODEL_PROFILES.md`.
4. Whether `max_completion_tokens` on the top-priority provider is low enough to truncate long output.

If everything is healthy, say so in one line and stop.
