# INSTRUCTIONS.md — orwatch

The phased build plan. The orchestrator reads the current phase from `.opencode/state/progress.md`, then reads that phase here.

Every success criterion is checkable by **running something**. That is deliberate: the orchestrator verifies these literally, so a criterion like "works correctly" produces an agent's opinion about its own work instead of a fact.

---

## Phase 1: Skeleton and Data Model

**Objective:** A `uv`-managed package with the frozen record types and a green empty test suite.

**Prerequisites:** `uv` installed. `gh auth login` done if you want issue tracking from day one.

### Tasks

| # | Task | Agent | Files | Depends on |
|---|---|---|---|---|
| 1.1 | `pyproject.toml` (uv, py3.12+, httpx, pytest, ruff), package skeleton, `ruff` config | `backend-dev` | `pyproject.toml`, `src/orwatch/__init__.py`, `.python-version` | — |
| 1.2 | Exception hierarchy: `OrwatchError` and per-module subclasses | `backend-dev` | `src/orwatch/errors.py` | 1.1 |
| 1.3 | `EndpointRecord` and `Snapshot` frozen dataclasses per §3.3, with `tool_capable` | `backend-dev` | `src/orwatch/models.py` | 1.2 |
| 1.4 | Tests for the model layer, including `tool_capable` when `tools` is present but `tool_choice` is not | `test-engineer` | `tests/test_models.py`, `tests/conftest.py` | 1.3 |

### Success Criteria

- [ ] `uv sync` exits 0
- [ ] `uv run pytest` exits 0 with at least 6 passing tests
- [ ] `uv run ruff check . && uv run ruff format --check .` exits 0
- [ ] `uv run python -c "from orwatch.models import EndpointRecord, Snapshot"` exits 0
- [ ] A test asserts `tool_capable is False` for an endpoint with `tools` but no `tool_choice`
- [ ] `code-reviewer` returns PASS or PASS WITH FINDINGS, all CRITICAL resolved or logged

### Out of Scope

- No HTTP. No filesystem. No CLI.
- Do not add dependencies beyond httpx, pytest, ruff.

---

## Phase 2: Client and Normalisation

**Objective:** Fetch a model's endpoints and turn the response into a `Snapshot`, with the network fully mocked in tests.

### Tasks

| # | Task | Agent | Files | Depends on |
|---|---|---|---|---|
| 2.1 | `fetch_endpoints(slug, timeout)` — the sole `httpx` import in the codebase | `backend-dev` | `src/orwatch/client.py` | Phase 1 |
| 2.2 | `Snapshot.from_api(slug, payload)` normalisation per §4.1 | `backend-dev` | `src/orwatch/models.py` | 2.1 |
| 2.3 | Capture real fixtures: one many-endpoint model, one single-endpoint model, one empty-endpoints response | `test-engineer` | `tests/fixtures/*.json` | 2.1 |
| 2.4 | Client and normalisation tests, all offline | `test-engineer` | `tests/test_client.py` | 2.3 |

### Success Criteria

- [ ] `uv run pytest` exits 0
- [ ] `rg -l "import httpx" src/ | wc -l` outputs exactly `1`, and that file is `src/orwatch/client.py`
- [ ] `rg -c "httpx.get|httpx.Client|requests\." tests/` finds no unmocked client construction
- [ ] Parsing the many-endpoint fixture yields endpoints sorted by `tag`
- [ ] Prices round-trip as `Decimal` — a test asserts `price_prompt == Decimal("0.000003")`, not an approximate float compare
- [ ] The empty-endpoints fixture parses to a `Snapshot` with zero endpoints and does **not** raise
- [ ] A non-200 response raises `FetchError` with the slug in the message
- [ ] `code-reviewer` PASS, all CRITICAL resolved or logged

### Out of Scope

- No disk persistence. No diffing. No CLI.
- Do not hand-author fixtures — capture real responses and trim them.

---

## Phase 3: Snapshot Store

**Objective:** Persist and retrieve snapshots, with retention.

### Tasks

| # | Task | Agent | Files | Depends on |
|---|---|---|---|---|
| 3.1 | `save_snapshot` / `load_latest` per §4.2, `schema_version` handling | `backend-dev` | `src/orwatch/store.py` | Phase 2 |
| 3.2 | Retention pruning — keep newest 30, sort by filename timestamp not mtime | `backend-dev` | `src/orwatch/store.py` | 3.1 |
| 3.3 | Store tests including the round-trip property and the corrupt-file path | `test-engineer` | `tests/test_store.py` | 3.2 |

### Success Criteria

- [ ] `uv run pytest` exits 0
- [ ] Round-trip property holds: `load_latest(save_snapshot(s)) == s`, asserted on the dataclass, not on JSON text
- [ ] First run — no snapshot directory at all — returns `None` and does not raise
- [ ] Saving 31 snapshots leaves exactly 30 files on disk
- [ ] A truncated JSON file raises `StoreError` and the message contains the file path
- [ ] A snapshot with `schema_version: 999` raises `StoreError`, not a parse error
- [ ] Written filenames contain no `:` (Windows-safe) — asserted in a test
- [ ] `code-reviewer` PASS, all CRITICAL resolved or logged

### Out of Scope

- No diffing. No CLI. No concurrency.

---

## Phase 4: Diff Engine

**Objective:** Compare two snapshots deterministically and classify capability regressions.

This is the phase where the interesting bugs live. Expect to use `specialist`.

### Tasks

| # | Task | Agent | Files | Depends on |
|---|---|---|---|---|
| 4.1 | `FieldChange` / `SnapshotDiff` types per §4.3 | `backend-dev` | `src/orwatch/diff.py` | Phase 3 |
| 4.2 | `compare(prev, curr)` — matching by tag, field comparison, sorted everywhere | `backend-dev` | `src/orwatch/diff.py` | 4.1 |
| 4.3 | `regressions` classification, all four cases in §4.3 | `backend-dev` | `src/orwatch/diff.py` | 4.2 |
| 4.4 | Diff tests including the determinism property and every regression case | `test-engineer` | `tests/test_diff.py` | 4.3 |

### Success Criteria

- [ ] `uv run pytest` exits 0
- [ ] `rg -c "import (httpx|pathlib|os)" src/orwatch/diff.py` outputs `0` — the diff engine has no I/O
- [ ] Property: `compare(a, a).has_changes is False` for every fixture snapshot
- [ ] Determinism: `compare(a, b)` called twice produces equal results, and shuffling the input endpoint order does not change the output
- [ ] A test covers an endpoint that keeps `tools` but loses `tool_choice`, and asserts it appears in `regressions`
- [ ] A test covers an endpoint disappearing entirely and asserts it appears in both `removed` and `regressions`
- [ ] A test covers price changing with nothing else changing
- [ ] `is_first_run` is `True` when `prev is None`, and `has_changes` is `False` in that case
- [ ] `code-reviewer` PASS, all CRITICAL resolved or logged

### Out of Scope

- No rendering. No CLI. No config file.
- Do not optimise. Correctness first; §6 budgets are generous.

---

## Phase 5: CLI, Rendering and Config

**Objective:** A usable command with the documented exit codes.

### Tasks

| # | Task | Agent | Files | Depends on |
|---|---|---|---|---|
| 5.1 | `orwatch.toml` loading with defaults per §5 | `backend-dev` | `src/orwatch/config.py` | Phase 4 |
| 5.2 | Terminal rendering — regressions first, then added/removed/changed | `backend-dev` | `src/orwatch/render.py` | 5.1 |
| 5.3 | `cli.py` — argparse, `check` subcommand, `--fail-on-regression`, exit codes per §4.4 | `backend-dev` | `src/orwatch/cli.py`, `pyproject.toml` | 5.2 |
| 5.4 | End-to-end tests driving `main()` with a mocked transport, asserting exit codes | `test-engineer` | `tests/test_cli.py` | 5.3 |

### Success Criteria

- [ ] `uv run pytest` exits 0
- [ ] `uv run orwatch check --help` exits 0
- [ ] Against a mocked transport with no prior snapshot, exit code is `0`
- [ ] Second run with an identical response, exit code is `0`
- [ ] Second run with a changed response, exit code is `1`
- [ ] Run with a capability regression **and** `--fail-on-regression`, exit code is `2`
- [ ] Run with an unreachable host, exit code is `3` and stderr names the model
- [ ] A test asserts all four exit codes explicitly — this is the public contract
- [ ] `uv run ruff check . && uv run ruff format --check .` exits 0
- [ ] `code-reviewer` PASS, all CRITICAL resolved or logged

### Out of Scope

- No `--json` mode, no thresholds, no webhooks. Those are post-MVP.
- No concurrency yet.

---

## Post-MVP backlog

Not phases. Log these as GitHub issues and sweep them at a breakpoint.

- `--json` output for piping
- Concurrent fetches (only after §6 shows sequential is actually the bottleneck)
- Price-change thresholds
- A `--since <timestamp>` mode diffing against an older snapshot
- GitHub Action wrapper
