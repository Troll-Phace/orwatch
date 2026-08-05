# orwatch — Progress

<!-- Injected into every session via `instructions` in opencode.jsonc.
     The ORCHESTRATOR maintains this file manually. No plugin advances
     phases or checks off tasks — the telemetry plugin only appends
     session-idle lines to the log at the bottom. -->

## Current Phase

Phase: 2
Title: Client and Normalisation
Status: NOT STARTED
Started: —

## Completed Phases

- [x] Phase 1: Skeleton and Data Model (2026-08-04)

## Current Phase Tasks

- [ ] 2.1 fetch_endpoints(slug, timeout) — the sole httpx import in the codebase (src/orwatch/client.py)
- [ ] 2.2 Snapshot.from_api(slug, payload) normalisation per ARCHITECTURE §4.1 (src/orwatch/models.py)
- [ ] 2.3 Capture real fixtures: many-endpoint, single-endpoint, empty-endpoints (tests/fixtures/*.json)
- [ ] 2.4 Client and normalisation tests, all offline (tests/test_client.py)

## Blocked / Waiting

<!-- Anything that cannot proceed, and what it is waiting on. -->

## Decisions Made

<!-- Architectural decisions taken mid-phase not yet folded into
     ARCHITECTURE.md. Fold them in at the phase boundary. -->

Folded into ARCHITECTURE.md §3.3 at the Phase 1 boundary:
- Snapshot enforces tz-aware fetched_at (ValueError on naive) and tag-sorted
  endpoints at construction; endpoints defaults to an empty tuple.
- Exception hierarchy: OrwatchError base with FetchError (client.py),
  StoreError (store.py), ConfigError (config.py).

Phase 1 tooling decisions (not architecture, recorded only):
- hatchling build backend with src layout.
- docs/ excluded from ruff via extend-exclude — ruff reformats Markdown code
  blocks and the docs are a stable reference.
- .gitignore.append merged into .gitignore (both blocks).

## Session Log

- 2026-08-05 01:12: session idle (started 2026-08-05 01:06) — 0 tool calls, 0 failed (0.0%)
- 2026-08-05 01:22: session idle (started 2026-08-05 01:21) — 2 tool calls, 0 failed (0.0%)
