# orwatch — progress

## Current Phase

Phase 3: Snapshot Store (see docs/INSTRUCTIONS.md)

## Completed Phases

### Phase 1: Skeleton and Data Model — done (commit 2a7d148)

### Phase 2: Client and Normalisation — done (2026-08-05)

- [x] 2.1 fetch_endpoints — the sole httpx import (src/orwatch/client.py)
- [x] 2.2 Snapshot.from_api normalisation per §4.1 (src/orwatch/models.py)
- [x] 2.3 Real fixtures captured: moonshotai__kimi-k3 (12 endpoints),
      qwen__qwen3.8-max (1 endpoint), empty-endpoints (0 endpoints)
- [x] 2.4 Client + normalisation tests, fully offline (tests/test_client.py)
- Review gate: round 1 FAIL (CRITICAL: httpx.DecodingError escaped
  fetch_endpoints; WARNINGs: NaN prices, tautological test, coverage gaps)
  → fixed → round 2 PASS. 47 tests green, ruff clean.
- Issues filed from residuals: #2 (FetchError message prefix wording),
  #3 (duplicate-tag check only in from_api — decide __post_init__ vs
  load-time validation), #4 (ruff extend-exclude claim, adjudicated false).

## Decisions Made (Phase 2)

Folded into docs/ARCHITECTURE.md §3.3/§4.1 at the phase boundary.

- D1 — fetch_endpoints gains keyword-only `transport: httpx.BaseTransport |
  None = None` test seam; tests pass httpx.MockTransport and never construct
  a client (keeps the rg offline-contract criterion mechanically true).
- D2 — BASE_URL = "https://openrouter.ai/api/v1" module constant.
- D3 — from_api tolerant of absence (missing/null `data` or `endpoints` →
  zero-endpoint Snapshot), strict on wrong type (ValueError naming the
  field). ValueError, not FetchError, because models.py is stdlib-only (§3.1).
- D4 — Field policy: tag/provider_name/prices required; context_length/
  max_completion_tokens/quantization default None; supported_parameters
  defaults to empty frozenset; unknown fields dropped.
- D5 — from_api(slug, payload, *, fetched_at=None), default datetime.now(UTC).
- D6 — Fixtures captured from the live API via a throwaway pytest file
  (`uv run python` is permission-denied), saved verbatim with
  json.dumps(indent=2, sort_keys=True).
- D7 — Tasks 2.1+2.2 merged into one dispatch.
- D8 — FetchError messages always contain the slug; non-200 also carries the
  status code; wrapped exceptions chain via `raise ... from exc`.
- D9 — Duplicate tags within one response are rejected (ValueError); tag is
  identity per §4.1. Non-finite price strings ("NaN"/"Infinity") rejected.

## Notes carried forward

- **Phase 3:** decide duplicate-tag enforcement path — Snapshot.__post_init__
  vs load-time validation in store.py (issue #3). `uv run python` is denied
  by the permission map; any scripting must go through `uv run pytest`.
- **Phase 5:** cli.py must catch ValueError from Snapshot.from_api (not an
  OrwatchError) for the exit-3 contract; follow_redirects stays False — a
  3xx surfaces as FetchError deliberately (loud failure beats silent
  redirect-following).

## Session log

- 2026-08-05 02:52: session idle (started 2026-08-05 02:50) — 11 tool calls, 0 failed (0.0%)
