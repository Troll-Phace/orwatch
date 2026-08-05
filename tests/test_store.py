"""Tests for the snapshot store (store.py, Phase 3).

Everything here is filesystem-only (``tmp_path``) and fully offline — no
network, no ``tests/fixtures/*.json``. Coverage maps 1:1 to the Phase 3
success criteria in INSTRUCTIONS.md and the edge cases in ARCHITECTURE §4.2:

  C-1 Round-trip property (save then load_latest == original, on the dataclass)
  C-2 First run (no root / no model dir) returns None without raising
  C-3 Saving 31 snapshots leaves exactly 30 files
  C-4 Truncated JSON raises StoreError with the path in the message
  C-5 schema_version 999 (and missing) raises StoreError, not a parse error
  C-6 Written filenames contain no ':' (Windows-safe); model dir uses '__'
  E-1 Same-second collision produces two files; load_latest returns the newer
  E-2 Retention sorts by filename timestamp, not mtime
  E-3 Out-of-order writes still return the newer snapshot
  E-4 On-disk duplicate tags raise StoreError (wrapped ValueError) with path
  E-5 Unparseable filenames are ignored and survive pruning

All timestamps are injected (``FIXED_FETCHED_AT``) — never ``datetime.now()``.
"""

import json
import os
import time
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import FIXED_FETCHED_AT

from orwatch.errors import StoreError
from orwatch.store import load_latest, save_snapshot

SLUG = "moonshotai/kimi-k3"


def _stamp(seconds: int, microseconds: int = 0) -> datetime:
    """Return FIXED_FETCHED_AT shifted by ``seconds`` with optional micros."""
    return FIXED_FETCHED_AT + timedelta(seconds=seconds, microseconds=microseconds)


def _fname(seconds: int) -> str:
    """Return the on-disk snapshot filename that a save of ``_stamp(seconds)`` writes."""
    return _stamp(seconds).astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ") + ".json"


# --- C-1: round-trip on the dataclass -----------------------------------------


def test_round_trip_multiep_mixed_none_full_precision(make_endpoint, make_snapshot, tmp_path):
    """save then load_latest returns a Snapshot *equal to the original*.

    Mixed None fields, Decimal prices compared exactly (not float), and a
    fetched_at with microseconds to prove full-precision round-trip from the
    JSON body rather than the second-precision filename.
    """
    snap = make_snapshot(
        endpoints=(
            make_endpoint(
                tag="moonshotai/mxfp4",
                quantization="mxfp4",
                context_length=1_048_576,
                max_completion_tokens=None,
            ),
            make_endpoint(
                tag="nvidia/nemotron",
                quantization=None,
                context_length=None,
                max_completion_tokens=16384,
                price_prompt=Decimal("0.000003"),
                price_completion=Decimal("0.000015"),
            ),
            make_endpoint(
                tag="together",
                context_length=131072,
                max_completion_tokens=None,
                supported_parameters=frozenset({"tools", "tool_choice"}),
            ),
        ),
        fetched_at=_stamp(0, microseconds=123456),
    )

    save_snapshot(snap, tmp_path)
    loaded = load_latest(SLUG, tmp_path)

    # Dataclass equality (frozen, includes Decimal and frozenset members).
    assert loaded == snap
    assert loaded.fetched_at == _stamp(0, microseconds=123456)
    # The price survived as an exact Decimal, not a float approximation.
    assert loaded.endpoints[1].price_prompt == Decimal("0.000003")


# --- C-2: first run returns None, does not raise -------------------------------


def test_first_run_root_absent_returns_none(tmp_path):
    """No snapshots root at all → load_latest returns None, never raises."""
    missing_root = tmp_path / "does" / "not" / "exist"
    assert load_latest(SLUG, missing_root) is None


def test_first_run_model_dir_absent_returns_none(tmp_path):
    """Root exists but the per-model directory does not → None."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert load_latest(SLUG, tmp_path) is None


# --- C-3: retention limit ------------------------------------------------------


def test_saving_31_snapshots_leaves_exactly_30_files(make_snapshot, tmp_path):
    """31 distinct timestamped snapshots → exactly 30 files remain on disk."""
    for i in range(31):
        snap = make_snapshot(fetched_at=_stamp(i))
        save_snapshot(snap, tmp_path)

    model_dir = tmp_path / SLUG.replace("/", "__")
    files = [f for f in model_dir.iterdir() if f.is_file()]
    assert len(files) == 30
    # The survivor set is exactly stamps 1..30 — the oldest (_stamp(0), the
    # single file saved first) is the loser. Identity, not just count.
    remaining = {f.name for f in files}
    assert remaining == {_fname(i) for i in range(1, 31)}


# --- C-4: truncated JSON -------------------------------------------------------


def test_truncated_json_raises_store_error_with_path(make_snapshot, tmp_path):
    """A corrupt/truncated newest file raises StoreError naming the path."""
    # A valid baseline so the directory exists and is non-empty.
    save_snapshot(make_snapshot(fetched_at=_stamp(0)), tmp_path)

    # The newest slot, written with truncated JSON so load_latest selects it.
    model_dir = tmp_path / SLUG.replace("/", "__")
    broken = model_dir / "2026-08-05T00-33-17Z.json"  # _stamp(60) -> the newest
    broken.write_text('{"schema_version": 1, "endpoints": [', encoding="utf-8")

    with pytest.raises(StoreError) as excinfo:
        load_latest(SLUG, tmp_path)
    assert str(broken) in str(excinfo.value)


# --- C-5: schema_version validation --------------------------------------------


def _write_snapshot_doc(root: Path, doc: dict, *, name: str = "2026-08-05T00-32-17Z.json"):
    model_dir = root / SLUG.replace("/", "__")
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / name).write_text(json.dumps(doc), encoding="utf-8")


def test_schema_version_999_raises_store_error_not_json_error(tmp_path):
    _write_snapshot_doc(
        tmp_path,
        {
            "schema_version": 999,
            "model_slug": SLUG,
            "fetched_at": "2026-08-05T00:32:17Z",
            "endpoints": [],
        },
    )
    with pytest.raises(StoreError, match="schema_version"):
        load_latest(SLUG, tmp_path)


def test_schema_version_missing_raises_store_error(tmp_path):
    _write_snapshot_doc(
        tmp_path,
        {"model_slug": SLUG, "fetched_at": "2026-08-05T00:32:17Z", "endpoints": []},
    )
    with pytest.raises(StoreError, match="schema_version"):
        load_latest(SLUG, tmp_path)


# --- C-6: Windows-safe filenames -----------------------------------------------


def test_filename_has_no_colon_and_model_dir_uses_underscores(make_snapshot, tmp_path):
    written = save_snapshot(make_snapshot(fetched_at=_stamp(0)), tmp_path)
    assert ":" not in written.name
    assert written.parent.name == SLUG.replace("/", "__")
    assert written.suffix == ".json"


# --- E-1: same-second collision ------------------------------------------------


def test_same_second_collision_returns_second_saved(make_endpoint, make_snapshot, tmp_path):
    """Two saves with identical fetched_at → two files, no clobber; load_latest
    returns the second-saved one (distinguished by endpoint set)."""
    a = make_snapshot(endpoints=(make_endpoint(tag="a/one"),), fetched_at=_stamp(0))
    b = make_snapshot(endpoints=(make_endpoint(tag="b/two"),), fetched_at=_stamp(0))

    save_snapshot(a, tmp_path)
    save_snapshot(b, tmp_path)

    model_dir = tmp_path / SLUG.replace("/", "__")
    files = sorted(f.name for f in model_dir.iterdir() if f.is_file())
    assert len(files) == 2  # both writes landed, nothing clobbered

    loaded = load_latest(SLUG, tmp_path)
    assert loaded == b
    assert loaded.endpoints[0].tag == "b/two"


# --- E-2: retention sorts by filename timestamp, not mtime ----------------------


def test_retention_prunes_by_filename_timestamp_not_mtime(make_snapshot, tmp_path):
    """Give the oldest snapshot the newest mtime; it must still be the one
    pruned when the retention limit is exceeded."""
    # 30 snapshots with increasing timestamps fill the retention window.
    for i in range(30):
        save_snapshot(make_snapshot(fetched_at=_stamp(i)), tmp_path)

    model_dir = tmp_path / SLUG.replace("/", "__")
    oldest = model_dir / "2026-08-05T00-32-17Z.json"  # _stamp(0) = FIXED_FETCHED_AT
    assert oldest.exists()

    # Make the *oldest-by-name* file have the *newest* mtime on disk.
    far_future = time.time() + 10_000
    os.utime(oldest, (far_future, far_future))

    # A 31st save triggers pruning. The single loser must be the oldest by
    # filename timestamp (the file with the newest mtime), not by mtime.
    save_snapshot(make_snapshot(fetched_at=_stamp(30)), tmp_path)

    assert not oldest.exists()
    remaining = [f for f in model_dir.iterdir() if f.is_file()]
    assert len(remaining) == 30
    # The survivor set is exactly stamps 1..30 — _stamp(0), despite the
    # newest mtime, is the loser. Identity, not just count.
    survivor_names = {f.name for f in remaining}
    assert survivor_names == {_fname(i) for i in range(1, 31)}


# --- E-3: out-of-order writes ---------------------------------------------------


def test_out_of_order_write_returns_newer_snapshot(make_endpoint, make_snapshot, tmp_path):
    """Saving an older timestamp after a newer one — load_latest still returns
    the newer snapshot (clock-skew tolerance, §4.2)."""
    newer = make_snapshot(endpoints=(make_endpoint(tag="new/one"),), fetched_at=_stamp(10))
    older = make_snapshot(endpoints=(make_endpoint(tag="old/one"),), fetched_at=_stamp(5))

    save_snapshot(newer, tmp_path)
    save_snapshot(older, tmp_path)  # written later but stamped earlier

    loaded = load_latest(SLUG, tmp_path)
    assert loaded == newer


# --- E-4: duplicate tags on disk ------------------------------------------------


def test_duplicate_tags_on_disk_raise_store_error_with_path(make_endpoint, tmp_path):
    """A stored snapshot whose endpoints share a tag must raise StoreError
    (the Snapshot.__post_init__ ValueError wrapped), with the path named."""
    doc = {
        "schema_version": 1,
        "model_slug": SLUG,
        "fetched_at": "2026-08-05T00:32:17Z",
        "endpoints": [
            {
                "tag": "dup/tag",
                "provider_name": "P",
                "context_length": None,
                "max_completion_tokens": None,
                "quantization": None,
                "price_prompt": "0.000003",
                "price_completion": "0.000015",
                "supported_parameters": [],
            },
            {
                "tag": "dup/tag",
                "provider_name": "Q",
                "context_length": None,
                "max_completion_tokens": None,
                "quantization": None,
                "price_prompt": "0.000003",
                "price_completion": "0.000015",
                "supported_parameters": [],
            },
        ],
    }
    _write_snapshot_doc(tmp_path, doc)

    with pytest.raises(StoreError) as excinfo:
        load_latest(SLUG, tmp_path)
    assert "dup/tag" in str(excinfo.value)
    assert SLUG.replace("/", "__") in str(excinfo.value)  # the path is named


# --- E-5: unparseable filenames are ignored and survive pruning -----------------


def test_load_ignores_unparseable_filenames_when_none_valid(make_snapshot, tmp_path):
    """A model dir containing only non-snapshot files is treated as first run."""
    model_dir = tmp_path / SLUG.replace("/", "__")
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "notes.txt").write_text("hi", encoding="utf-8")
    (model_dir / "corrupt.json").write_text("nope", encoding="utf-8")

    assert load_latest(SLUG, tmp_path) is None


def test_unparseable_filenames_survive_pruning(make_snapshot, tmp_path):
    """Non-snapshot files are ignored for selection and are never deleted by a
    pruning save — the retention pass only removes parseable snapshots."""
    model_dir = tmp_path / SLUG.replace("/", "__")
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "notes.txt").write_text("keep me", encoding="utf-8")

    # A valid baseline snapshot plus 30 more pushes past the retention limit.
    save_snapshot(make_snapshot(fetched_at=_stamp(0)), tmp_path)
    for i in range(1, 31):
        save_snapshot(make_snapshot(fetched_at=_stamp(i)), tmp_path)

    assert (model_dir / "notes.txt").exists()
    assert sum(1 for f in model_dir.iterdir() if f.is_file()) == 31  # 30 snaps + notes


# --- E-6: calendar-invalid filenames (round-1 CRITICAL regression) -------------


def test_calendar_invalid_filename_ignored_for_selection_and_survives_pruning(
    make_snapshot, tmp_path
):
    """A filename that matches the regex but holds a calendar-invalid date
    (e.g. month 13 / day 99) must be treated exactly like any other
    unparseable name: ignored for selection and never deleted by pruning.

    Regression for the round-1 CRITICAL: before the fix, _parse_filename
    raised a bare ValueError on calendar-invalid dates (month 13 / day 99
    parse fine against the regex but not against strptime), and that escaped
    uncaught out of load_latest and _prune.
    """
    model_dir = tmp_path / SLUG.replace("/", "__")
    model_dir.mkdir(parents=True, exist_ok=True)
    stray = model_dir / "2026-13-99T00-00-00Z.json"
    # Regex-matching shape with the right keys so a naive parse-selection
    # would otherwise have been tempted to load it.
    stray.write_text(
        '{"schema_version": 1, "model_slug": "x", '
        '"fetched_at": "2026-08-05T00:32:17Z", "endpoints": []}',
        encoding="utf-8",
    )

    # A valid snapshot co-exists; load_latest must pick it, never the stray.
    valid = make_snapshot(fetched_at=_stamp(0))
    save_snapshot(valid, tmp_path)
    assert load_latest(SLUG, tmp_path) == valid

    # A second save triggers pruning; the calendar-invalid stray survives.
    save_snapshot(make_snapshot(fetched_at=_stamp(1)), tmp_path)
    assert stray.exists()


# --- C-5b: schema_version rejects bool/float -----------------------------------


@pytest.mark.parametrize("bad_version", [True, 1.0])
def test_schema_version_bool_and_float_rejected(tmp_path, bad_version):
    """schema_version that is a JSON boolean (true) or a float (1.0) is not
    the integer 1 and must raise StoreError — bool short-circuits the int
    check and float fails the equality, neither should be accepted (D5)."""
    _write_snapshot_doc(
        tmp_path,
        {
            "schema_version": bad_version,
            "model_slug": SLUG,
            "fetched_at": "2026-08-05T00:32:17Z",
            "endpoints": [],
        },
    )
    with pytest.raises(StoreError, match="schema_version"):
        load_latest(SLUG, tmp_path)


# --- E-7: on-disk field validation branches (reviewer-confirmed branches) ------


def _valid_doc() -> dict:
    """A fully valid on-disk snapshot doc; individual tests mutate one field."""
    return {
        "schema_version": 1,
        "model_slug": SLUG,
        "fetched_at": "2026-08-05T00:32:17Z",
        "endpoints": [
            {
                "tag": "moonshotai/mxfp4",
                "provider_name": "Moonshot AI",
                "context_length": None,
                "max_completion_tokens": None,
                "quantization": None,
                "price_prompt": "0.000003",
                "price_completion": "0.000015",
                "supported_parameters": [],
            }
        ],
    }


@pytest.mark.parametrize(
    "mutate",
    [
        # naive fetched_at: no timezone offset on the string
        lambda doc: doc.update({"fetched_at": "2026-08-05T00:32:17"}),
        # non-string endpoint tag
        lambda doc: doc["endpoints"][0].update({"tag": 123}),
        # non-list supported_parameters
        lambda doc: doc["endpoints"][0].update({"supported_parameters": "tools"}),
        # non-finite price string
        lambda doc: doc["endpoints"][0].update({"price_prompt": "NaN"}),
    ],
)
def test_on_disk_field_validation_branch_raises_store_error_with_path(tmp_path, mutate):
    """Each rejected on-disk field must raise StoreError *and* name the path.
    These cover the validation branches in _dict_to_snapshot/_parse_endpoint
    that the reviewer confirmed correct but were previously untested."""
    doc = _valid_doc()
    mutate(doc)
    _write_snapshot_doc(tmp_path, doc)

    model_dir = tmp_path / SLUG.replace("/", "__")
    snapshot_file = model_dir / "2026-08-05T00-32-17Z.json"

    with pytest.raises(StoreError) as excinfo:
        load_latest(SLUG, tmp_path)
    assert str(snapshot_file) in str(excinfo.value)


# --- E-8: non-UTC tz-aware fetched_at round-trip -------------------------------


def test_round_trip_non_utc_timezone_fetched_at_instant_equality(make_snapshot, tmp_path):
    """A fetched_at expressed in a non-UTC tz (UTC+02:00) round-trips with
    *instant* equality: the reloaded value represents the same moment in
    time, normalised to UTC, whatever the original wall-clock offset (D5)."""
    tz = timezone(timedelta(hours=2))
    source = datetime(2026, 8, 5, 2, 32, 17, tzinfo=tz)  # == 00:32:17Z instant
    snap = make_snapshot(fetched_at=source)

    save_snapshot(snap, tmp_path)
    loaded = load_latest(SLUG, tmp_path)

    # Same instant: datetime equality on aware datetimes compares instants,
    # and the loader must have normalised to UTC (zero offset, no shift).
    assert loaded.fetched_at == source
    assert loaded.fetched_at == source.astimezone(UTC)
    assert loaded.fetched_at.utcoffset() == timedelta(0)
    assert loaded.fetched_at.tzinfo is UTC
