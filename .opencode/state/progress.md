# orwatch — progress

## Current Phase

Phase 4: Diff Engine (see docs/INSTRUCTIONS.md)

## Completed Phases

### Phase 1: Skeleton and Data Model — done (commit 2a7d148)

### Phase 2: Client and Normalisation — done (commit 463e5b6, 2026-08-05)

- [x] 2.1 fetch_endpoints — the sole httpx import (src/orwatch/client.py)
- [x] 2.2 Snapshot.from_api normalisation per §4.1 (src/orwatch/models.py)
- [x] 2.3 Real fixtures captured: moonshotai__kimi-k3 (12 endpoints),
      qwen__qwen3.8-max (1 endpoint), empty-endpoints (0 endpoints)
- [x] 2.4 Client + normalisation tests, fully offline (tests/test_client.py)
- Review gate: round 1 FAIL (CRITICAL: httpx.DecodingError escaped
  fetch_endpoints; WARNINGs: NaN prices, tautological test, coverage gaps)
  → fixed → round 2 PASS. 47 tests green, ruff clean.
- Issues filed from residuals: #2 (FetchError message prefix wording),
  #3 (duplicate-tag check only in from_api — resolved in Phase 3, D1),
  #4 (ruff extend-exclude claim, adjudicated false — close decision is
  the user's; still open as of Phase 3 close).

### Phase 3: Snapshot Store — done (commit f37698b, 2026-08-05)

- [x] 3.0 Network guard installed in tests/conftest.py + allow_network
      marker registered + tests/test_network_guard.py (the guard was
      drafted in Phase 2 but never landed — see D13; the Phase 2 D6 claim
      that it was live was false and is corrected here)
- [x] 3.1+3.2 save_snapshot / load_latest / schema_version / retention
      (src/orwatch/store.py) + duplicate-tag backstop in
      Snapshot.__post_init__ (src/orwatch/models.py, resolves issue #3)
- [x] 3.3 Store tests: 22 tests, every INSTRUCTIONS criterion covered
      (tests/test_store.py)
- Review gate: round 1 FAIL (CRITICAL: strptime ValueError escaped
  load_latest/_prune on calendar-invalid filenames — one stray file
  bricked all saves for a model; WARNINGs: schema_version accepted JSON
  true/1.0, RecursionError escaped deep-nested corrupt JSON, untested
  on-disk validation branches) → fixed → round 2 PASS. 71 tests green,
  ruff clean. Round-2 SUGGESTION nits (ResourceWarning in guard test,
  docstring refs) also fixed.
- Decisions folded into docs/ARCHITECTURE.md §3.3/§4.2/§5 at the phase
  boundary.
- Issues filed from residuals: #5 (_prune unlink-failure branch untested),
  #6 (network guard residual surface: UDP sendto / subprocess egress /
  connect_ex untested).

## Decisions Made (Phase 3)

Folded into docs/ARCHITECTURE.md §3.3/§4.2/§5 at the phase boundary
(D13 is harness/test-infra and lives only here).

- D1  — Issue #3 resolved: duplicate-tag backstop in Snapshot.__post_init__
      (ValueError, covers every construction path incl. store loads);
      from_api keeps its pre-construction check (better message, asserted
      by Phase 2 tests); store wraps construction ValueErrors into
      StoreError with the path.
- D2  — Filename = fetched_at UTC truncated to whole seconds,
      %Y-%m-%dT%H-%M-%SZ.json. Full precision persists only in the JSON
      body; load reconstructs fetched_at from the body, never the filename
      (a filename-derived fetched_at would silently lose microseconds and
      break the dataclass round-trip criterion).
- D3  — Same-second collision → -1, -2, ... suffix before .json, never
      overwrite. Ordering key everywhere is (parsed timestamp, counter);
      never lexicographic filename order ('-' < '.' would invert it).
- D4  — load_latest: missing dir or no parseable filenames → None;
      unparseable names (incl. calendar-invalid dates like month 13 —
      added after review round 1) ignored for selection and never pruned;
      only the selected file is parsed.
- D5  — schema_version accepts exactly integer 1; missing/wrong type
      (incl. JSON true and 1.0, which == 1 in Python — added after review
      round 1)/any other value → StoreError naming version and path.
- D6  — Serialisation: json.dumps(indent=2, sort_keys=True) + trailing
      newline; prices as str(Decimal); supported_parameters sorted. §5's
      example key order is illustrative; sort_keys is normative.
- D7  — fetched_at persists as UTC ISO-8601 with Z; naive parse result →
      StoreError.
- D8  — Direct non-atomic write for MVP; the corrupt-file path is handled
      and tested regardless.
- D9  — StoreError wrapping: OSError, JSONDecodeError, RecursionError
      (added after review round 1), UnicodeDecodeError, KeyError,
      TypeError, ValueError → StoreError with path, chained from exc.
- D10 — No __init__.py re-exports (package precedent from Phases 1-2);
      import from orwatch.store.
- D11 — Slug sanitisation exactly "/" → "__".
- D12 — save_snapshot(snap, root, *, retention=30): keyword-only
      retention, forward-compatible with Phase 5's [store] retention
      config without breaking the §3.3 call shape. Non-positive retention
      clamps to 0 (prunes all parseable files).
- D13 — The offline-suite network guard (autouse socket patch +
      allow_network marker) is test infrastructure owned by test-engineer;
      it was drafted in Phase 2 but the append never landed, so task 3.0
      installed it before any Phase 3 tests were written. Accepted
      residual surface logged as issue #6.

## Notes carried forward

- **Phase 4:** the interesting bugs live here — INSTRUCTIONS expects
  possible specialist use. diff.py must import nothing but models.py and
  stdlib (grep-asserted criterion: no httpx/pathlib/os imports).
  Determinism criteria are property-shaped: compare(a,a) empty, shuffle
  invariance, no timestamps inside SnapshotDiff.
- **Phase 5:** cli.py must catch ValueError from Snapshot.from_api (not an
  OrwatchError) for the exit-3 contract; follow_redirects stays False — a
  3xx surfaces as FetchError deliberately (loud failure beats silent
  redirect-following). Config threads [store] retention into
  save_snapshot's keyword-only param (D12).
- **Parallel dispatch:** disjointness is over the import/run graph, not the
  file list. A task running `uv run pytest` is never disjoint from a task
  editing `src/` — Phase 2 hit a transient NameError exactly this way.
  Phase 3 ran fully sequential (4 dispatches + review rounds) and never
  hit a race; the phase was small enough that parallelism would have cost
  more verification than it saved.
- **Working-tree strays (user action):** agents/, commands/, plugins/,
  scripts/, state/, phase2.json, APPLY.md edits, modified .opencode/*
  files, and tests/conftest_network_guard.py.append (superseded by the
  installed guard) are harness drift, deliberately excluded from the
  Phase 3 commit. Review and clean up separately.
- **Issue #4** (adjudicated false) is still open — issue-triage never
  closes issues; the close is the user's.

## Harness

v3 as of 2026-08-05. Telemetry writes to `.opencode/state/sessions.jsonl` and
`tool-errors.jsonl`; nothing but the orchestrator writes to this file.
