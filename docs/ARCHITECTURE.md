# ARCHITECTURE.md — orwatch

Technical reference. Subagents cite this by section number from delegation prompts, so section numbering is stable — append rather than renumber.

---

## 1. Project Philosophy

**What it is.** A CLI that snapshots OpenRouter endpoint metadata for a set of watched models, diffs each run against the previous one, and reports what changed.

**Why it exists.** Tool-calling capability on OpenRouter is a property of the *endpoint*, not the model. A single model ID fans out across many providers whose capabilities differ, and that set changes without announcement. With OpenRouter's default `require_parameters: false`, a request carrying `tools` that routes to a tool-less endpoint does not error — the provider drops the parameter and returns prose. The visible symptom is an agent that thinks and then stops, intermittently, with nothing in any log. This tool makes that drift visible before it bites.

**Design principles, in priority order:**

1. **Deterministic output.** Same two snapshots in, byte-identical diff out. Not "usually" — always. A watcher whose output jitters is a watcher you stop reading.
2. **Offline-testable.** All network I/O is behind one seam. Everything downstream is a pure function over already-loaded data. No test touches the live API.
3. **Absence is data.** An endpoint disappearing, or losing `tools` from its `supported_parameters`, is the highest-value signal this tool produces. Missing keys are meaningful values, never silently defaulted away.
4. **Boring dependencies.** stdlib plus `httpx`. This runs in CI and on a cron; every dependency is a thing that can break unattended.

**Non-goals.** Not a cost tracker (OpenRouter's dashboard does that). Not a benchmark runner. Not a proxy. It reads one public endpoint and reports deltas.

---

## 2. Feature Set

| Feature | MVP? | Notes |
|---|---|---|
| Fetch endpoint metadata for a model | ✅ | `GET /api/v1/models/{author}/{slug}/endpoints`, no auth |
| Normalise into typed records | ✅ | Fixed field set, unknown fields dropped deliberately |
| Persist timestamped snapshots | ✅ | JSON on disk, per-model directory |
| Diff two snapshots | ✅ | added / removed / changed, field-level |
| Classify capability regressions | ✅ | Lost `tools`, lost `tool_choice`, lost `structured_outputs` |
| Human-readable report | ✅ | Coloured terminal output |
| Exit-code contract | ✅ | For CI and cron use — §4.4 |
| Watch list from a config file | ✅ | `orwatch.toml`, so the model set isn't a CLI argument every time |
| Snapshot retention | ✅ | Keep newest N per model |
| JSON output mode | ⬜ | `--json` for piping. Post-MVP |
| Price-change thresholds | ⬜ | "only report moves >5%". Post-MVP |
| Webhook / notification sink | ⬜ | Post-MVP |

---

## 3. Technical Architecture

### 3.1 Module graph

```
            cli.py            ← argparse, exit codes, orchestration
              │
      ┌───────┼────────┬──────────────┐
      ▼       ▼        ▼              ▼
  config.py client.py store.py    render.py
      │       │        │              │
      └───────┴────────┴──────┬───────┘
                              ▼
                          models.py       ← frozen dataclasses, no imports
                              ▲
                              │
                           diff.py        ← pure functions, no I/O
```

**The seam that matters:** `client.py` is the *only* module that imports `httpx`. `diff.py` and `render.py` import nothing but `models.py` and stdlib. That is what makes the interesting logic testable without a network.

### 3.2 Data flow

```
orwatch check
  → config.load()                     read orwatch.toml → list[str] of model slugs
  → for each slug:
      client.fetch_endpoints(slug)    HTTP GET → raw JSON
      models.Snapshot.from_api(...)   normalise → Snapshot
      store.load_latest(slug)         previous Snapshot | None
      diff.compare(prev, curr)        → SnapshotDiff   (pure)
      store.save_snapshot(curr)       persist + prune to retention limit
  → render.report(diffs)              terminal output
  → cli exit code per §4.4
```

First run has no previous snapshot. `load_latest` returns `None`, `compare` treats it as "everything is new but report nothing as changed", and the run exits `0`. This is a first-class path, not an error.

### 3.3 Contracts

```python
# client.py
def fetch_endpoints(
    slug: str,
    *,
    timeout: float = 20.0,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """Raises FetchError on network failure, non-200, or unparseable JSON.
    transport is the test-injection seam (None = default transport); tests
    pass httpx.MockTransport and never construct a client themselves."""

# models.py
@dataclass(frozen=True, slots=True)
class EndpointRecord:
    tag: str                      # e.g. "moonshotai/mxfp4" — the stable identity
    provider_name: str
    context_length: int | None
    max_completion_tokens: int | None
    quantization: str | None
    price_prompt: Decimal         # per token, as returned
    price_completion: Decimal
    supported_parameters: frozenset[str]

    @property
    def tool_capable(self) -> bool:
        return {"tools", "tool_choice"} <= self.supported_parameters

@dataclass(frozen=True, slots=True)
class Snapshot:
    model_slug: str
    fetched_at: datetime          # UTC, tz-aware
    endpoints: tuple[EndpointRecord, ...]   # sorted by tag

    @classmethod
    def from_api(cls, slug: str, payload: object, *,
                 fetched_at: datetime | None = None) -> Snapshot:
        """fetched_at defaults to datetime.now(UTC); injectable for
        deterministic tests."""

# store.py
def save_snapshot(snap: Snapshot, root: Path, *, retention: int = 30) -> Path
    # retention is keyword-only so Phase 5's [store] retention config can
    # thread through without a signature break.
def load_latest(slug: str, root: Path) -> Snapshot | None  # None on first run
# both raise StoreError

# diff.py — pure, no I/O
def compare(prev: Snapshot | None, curr: Snapshot) -> SnapshotDiff
```

`Decimal` for prices, not `float`. Prices arrive as decimal strings and get compared for equality; binary floating point turns "unchanged" into "changed by 1e-19".

---

## 4. Domain Deep-Dives

### 4.1 Endpoint normalisation

The API returns `data.endpoints[]`, each with `name`, `tag`, `provider_name`, `context_length`, `max_completion_tokens`, `quantization`, `pricing{prompt,completion,...}` and `supported_parameters[]`.

**Identity is `tag`, not `provider_name`.** A single provider can serve several endpoints for one model that differ in quantization, price and capability — `wafer` and `wafer/fast` are distinct, cost $3.00 and $4.50, and only one is in our routing allowlist. Keying on `provider_name` would merge them and hide exactly the change we care about.

**Normalise `supported_parameters` to a `frozenset`.** The API's array order is not stable and carries no meaning. Comparing lists produces phantom diffs.

**Unknown fields are dropped on purpose.** The record has a fixed shape. If OpenRouter adds a field we care about, that is a code change with a test, not a silently-absorbed schema drift.

**Edge cases:**

- `max_completion_tokens` is frequently `null`. That is "unspecified", not zero. Keep it `None` and render it as `—`.
- `context_length` has been observed to differ *between endpoints of the same model* by an order of magnitude. Not an error.
- `pricing` values are strings like `"0.000003"`. Parse with `Decimal(str)`, never `float()`.
- A model slug that does not exist returns HTTP 200 with an empty `endpoints` array — **not** a 404. Empty-but-valid is a legitimate response and it is what every `:free` variant returns. Distinguish it from a fetch failure.
- The whole `data` object can be missing on an error response. Do not assume it is present.
- A 200 response whose `data` or `endpoints` key is missing or null is empty-but-valid and normalises to a zero-endpoint snapshot; present but wrong-typed structure raises `ValueError` naming the field. (models.py is stdlib-only per §3.1, so malformed payloads raise `ValueError`, not `FetchError` — callers mapping to exit codes must catch it.)
- Price strings must parse as finite `Decimal`s; "NaN"/"Infinity" are rejected.
- Duplicate `tag` values within one response are rejected — tag is the identity and duplicates would make match-by-tag ambiguous.
- The live response carries more fields than listed above (latency and uptime metrics, `model_id`, extra pricing keys like `input_cache_read`, etc.). They are dropped deliberately, like any unknown field.

### 4.2 Snapshot store

On-disk layout:

```
snapshots/
  moonshotai__kimi-k3/
    2026-08-05T00-32-17Z.json
    2026-08-04T09-14-02Z.json
  qwen__qwen3.8-max/
    ...
```

Slug sanitisation: `/` → `__`. Timestamps are UTC ISO-8601 with `:` → `-`, because `:` is illegal in Windows filenames and this runs on Windows.

**Retention:** keep the newest 30 per model, prune on every save. Sort by parsed timestamp from the filename, not by filesystem mtime — mtime lies after a copy, a restore, or a git checkout.

**Filename and ordering details:**

- **(a) Whole-second timestamps.** The filename derives from `fetched_at` truncated to whole seconds (`%Y-%m-%dT%H-%M-%SZ`). The full-precision timestamp persists only in the JSON body, and `load_latest` reconstructs it from the body — never from the filename, which is second-precision.
- **(b) Same-second collisions.** `save_snapshot` appends `-1`, `-2`, ... before `.json` until it finds a free name, never overwriting. The ordering key used everywhere (selection and pruning) is `(timestamp parsed from filename, collision counter)` — never lexicographic filename order, because `'-' < '.'` would put a suffixed name before its bare sibling and invert the sequence.
- **(c) Unrecognised names.** Files whose names do not match the recognised pattern — including regex-valid but calendar-invalid dates such as month 13 — are ignored for selection and never deleted by pruning.
- **(d) Load failures.** Every failure while loading is wrapped into `StoreError` carrying the offending path, chained from the original via `raise ... from exc`. The wrapped exception types are `OSError`, `JSONDecodeError`, `RecursionError`, `UnicodeDecodeError`, `KeyError`, `TypeError`, and `ValueError`.

**Edge cases:**

- Directory does not exist on first run → create it, do not raise.
- A corrupt or truncated JSON file → raise `StoreError` naming the path. Do not skip it silently; a snapshot that won't load is a real problem and hiding it means the next diff is against the wrong baseline.
- Two snapshots in the same second → the filename collides. The resolution is a `-1`, `-2`, ... disambiguator suffix on the second write; the first file is never clobbered.
- Clock skew producing a "latest" older than an existing file → sort handles it, but do not assume the newest write is the newest timestamp.

### 4.3 Diff semantics

```python
@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    before: object
    after: object

@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    model_slug: str
    added: tuple[EndpointRecord, ...]        # sorted by tag
    removed: tuple[EndpointRecord, ...]      # sorted by tag
    changed: tuple[tuple[str, tuple[FieldChange, ...]], ...]   # (tag, changes)
    is_first_run: bool

    @property
    def has_changes(self) -> bool: ...
    @property
    def regressions(self) -> tuple[str, ...]: ...   # tags that lost capability
```

**Matching** is by `tag`. Present in both → compare fields. Only in `curr` → added. Only in `prev` → removed.

**A capability regression** is any of:

1. An endpoint that was tool-capable is now absent entirely.
2. An endpoint that had `tools` no longer has it.
3. An endpoint that had `tool_choice` no longer has it — this is the subtle one. It still advertises `tools`, so a naive check passes, but it can no longer be forced to call a specific tool.
4. An endpoint that had `structured_outputs` no longer has it.

Regressions are ranked above ordinary changes in output because they are the ones that silently break an agent.

**Determinism requirements, all testable:**

- Every collection is sorted by `tag` before it lands in the diff.
- `supported_parameters` differences are rendered as sorted added/removed sets.
- No timestamp appears anywhere inside `SnapshotDiff`. The *report* has a timestamp; the diff structure does not, so `compare(a, b)` is a pure function of `a` and `b`.
- `compare(a, a)` is empty for every `a`. This is a property test.

### 4.4 Exit-code contract

This is a public interface. Changing it is a breaking change.

| Code | Meaning |
|---|---|
| `0` | Ran successfully, no changes detected (or first run) |
| `1` | Ran successfully, changes detected |
| `2` | Capability regression detected **and** `--fail-on-regression` was passed |
| `3` | Operational error — network failure, corrupt snapshot, bad config |

`2` only ever appears with the flag. Without it, a regression is reported in the output and still exits `1`, so ordinary interactive use is not surprising.

---

## 5. Schema

Snapshot file:

```json
{
  "schema_version": 1,
  "model_slug": "moonshotai/kimi-k3",
  "fetched_at": "2026-08-05T00:32:17Z",
  "endpoints": [
    {
      "tag": "moonshotai/mxfp4",
      "provider_name": "Moonshot AI",
      "context_length": 1048576,
      "max_completion_tokens": null,
      "quantization": "mxfp4",
      "price_prompt": "0.000003",
      "price_completion": "0.000015",
      "supported_parameters": ["reasoning", "response_format", "structured_outputs", "tool_choice", "tools"]
    }
  ]
}
```

`schema_version` is present from day one. When the record shape changes, `load_latest` on an older version raises `StoreError` with a clear message rather than mis-parsing. Prices persist as strings to survive the `Decimal` round-trip exactly. `supported_parameters` persists sorted so files are diffable in git.

**Schema-version validation.** The loader accepts exactly the integer `1`. Missing keys, wrong types (including JSON `true` and `1.0`, which compare equal to `1` in Python), and any other value raise `StoreError` naming the version and the path.

**Serialisation.** Files are written with `json.dumps(obj, indent=2, sort_keys=True)` plus a trailing newline, so byte-identical inputs yield byte-identical files. The key order in the example above is illustrative only — `sort_keys=True` is normative, and it is what makes the files byte-deterministic.

Config file, `orwatch.toml`:

```toml
[watch]
models = [
  "moonshotai/kimi-k3",
  "qwen/qwen3.8-max",
  "deepseek/deepseek-v4-flash-0731",
]

[store]
root = "snapshots"
retention = 30
```

---

## 6. Performance Budgets

Quantified so they are checkable, not aspirational.

| Operation | Budget | Measured how |
|---|---|---|
| Full check, 3 models | < 3s wall clock | `time uv run orwatch check` |
| Single fetch | < 1.5s, 20s timeout | Unit test with a delayed mock transport |
| `diff.compare` on 20-endpoint snapshots | < 10ms | `pytest-benchmark`, or assert on `perf_counter` |
| Snapshot file size | < 20 KB per model | `os.stat` in a test |

Fetches for different models are independent and may run concurrently. Do not add concurrency until Phase 5 and the sequential version is correct — a race in a diff tool produces wrong answers that look plausible.

---

## 7. Explicitly Out of Scope

- Authenticating to OpenRouter. The endpoints API is public; adding auth adds a secret to manage for no benefit.
- Tracking anything other than endpoint metadata — no usage, no spend, no latency.
- A daemon or long-running process. This is a one-shot command; scheduling belongs to cron, Task Scheduler or CI.
- A GUI or TUI. Terminal output only.
- Modifying `opencode.json` based on findings. Tempting, and wrong — the tool reports, the human decides.
