"""Snapshot persistence for orwatch.

Handles writing :class:`~orwatch.models.Snapshot` objects to disk as JSON,
loading the most recent one back, and pruning old snapshots down to a
retention limit. See ARCHITECTURE §4.2 for the on-disk layout.

Layout (per model, slug sanitised by replacing ``/`` with ``__``)::

    snapshots/
      moonshotai__kimi-k3/
        2026-08-05T00-32-17Z.json
        2026-08-05T00-32-17Z-1.json        # same-second collision suffix
        ...

Everything here is pure stdlib (``json``, ``pathlib``, ``datetime``,
``re``, ``decimal``). This module never imports ``httpx`` — per §3.1 only
``client.py`` may.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from orwatch.errors import StoreError
from orwatch.models import EndpointRecord, Snapshot

# A recognised snapshot filename: a second-precision UTC timestamp followed by
# an optional ``-<counter>`` collision suffix, then ``.json``.
_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)(?:-(\d+))?\.json\Z", re.ASCII)

_SCHEMA_VERSION = 1


def save_snapshot(snap: Snapshot, root: Path, *, retention: int = 30) -> Path:
    """Persist ``snap`` under ``root`` and return the path written.

    The model directory (``root / slug.replace("/", "__")``) is created if it
    does not exist. The filename derives from ``snap.fetched_at`` truncated to
    whole seconds; a same-second collision (the target name already exists)
    is resolved by appending ``-1``, ``-2``, ... before ``.json`` — never
    overwriting. After writing, old snapshots are pruned so only the newest
    ``retention`` (by the ordering key described in :func:`_parse_filename`)
    remain.

    Note:
        Serialisation is ``json.dumps(obj, indent=2, sort_keys=True)`` plus a
        trailing newline, so byte-identical inputs yield byte-identical files.

    Args:
        snap: the snapshot to persist.
        root: the snapshots root directory.
        retention: the number of newest snapshots (per model) to keep; older
            matching files are deleted on every save.

    Returns:
        The ``Path`` that was written.

    Raises:
        StoreError: if the model directory cannot be created, the file
            cannot be written, or pruning cannot delete an old file. The
            offending path is always included in the message.
    """
    model_dir = _model_dir(snap.model_slug, root)
    try:
        model_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StoreError(f"cannot create snapshot directory {model_dir}: {exc}") from exc

    target = _unique_path(model_dir, _filename(snap))
    text = json.dumps(_snapshot_to_dict(snap), indent=2, sort_keys=True) + "\n"
    try:
        target.write_text(text, encoding="utf-8")
    except (OSError, UnicodeEncodeError) as exc:
        raise StoreError(f"cannot write snapshot {target}: {exc}") from exc

    _prune(model_dir, retention)
    return target


def load_latest(slug: str, root: Path) -> Snapshot | None:
    """Load the most recent snapshot for ``slug``, or ``None`` on first run.

    The model directory is ``root / slug.replace("/", "__")``. A missing
    directory, or a directory containing no parseable snapshot filenames,
    returns ``None`` (this is the first-run case, not an error — §4.2).
    Files whose names do not match the recognised pattern are ignored for
    selection and never deleted by pruning. Only the selected (newest) file
    is parsed.

    Args:
        slug: model slug to look up.
        root: the snapshots root directory.

    Returns:
        The newest :class:`~orwatch.models.Snapshot`, or ``None`` if none
        exists.

    Raises:
        StoreError: if the model directory cannot be enumerated, or the
            selected file cannot be read or parsed (corrupt/truncated JSON,
            unsupported schema version, malformed fields, duplicate tags,
            or a naive ``fetched_at``). The offending path is always included
            in the message.
    """
    model_dir = _model_dir(slug, root)
    if not model_dir.is_dir():
        return None

    best: tuple[tuple[datetime, int], Path] | None = None
    try:
        for child in model_dir.iterdir():
            if not child.is_file():
                continue
            parsed = _parse_filename(child.name)
            if parsed is None:
                continue
            if best is None or parsed > best[0]:
                best = (parsed, child)
    except OSError as exc:
        raise StoreError(f"cannot enumerate snapshot directory {model_dir}: {exc}") from exc

    if best is None:
        return None
    return _load_file(best[1])


# --- serialisation ------------------------------------------------------------


def _snapshot_to_dict(snap: Snapshot) -> dict:
    """Convert a :class:`Snapshot` to the JSON-serialisable schema (§5)."""
    return {
        "schema_version": _SCHEMA_VERSION,
        "model_slug": snap.model_slug,
        "fetched_at": snap.fetched_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "endpoints": [
            {
                "tag": ep.tag,
                "provider_name": ep.provider_name,
                "context_length": ep.context_length,
                "max_completion_tokens": ep.max_completion_tokens,
                "quantization": ep.quantization,
                "price_prompt": str(ep.price_prompt),
                "price_completion": str(ep.price_completion),
                "supported_parameters": sorted(ep.supported_parameters),
            }
            for ep in snap.endpoints
        ],
    }


def _load_file(path: Path) -> Snapshot:
    """Parse a single snapshot file into a :class:`Snapshot`."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StoreError(f"cannot read snapshot {path}: {exc}") from exc

    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StoreError(f"cannot parse snapshot {path}: {exc}") from exc

    return _dict_to_snapshot(doc, path)


def _dict_to_snapshot(doc: object, path: Path) -> Snapshot:
    """Convert a parsed JSON document into a :class:`Snapshot`.

    Validates :attr:`schema_version` (must be the integer ``1``), the
    ``fetched_at`` string (parsed with :func:`datetime.fromisoformat`; a naive
    result is an error, §§ D5/D7), and every endpoint field. Model
    construction ValueErrors (duplicate tag, naive datetime) are wrapped.
    """
    if not isinstance(doc, dict):
        raise StoreError(f"cannot load snapshot {path}: top-level JSON value is not an object")

    version = doc.get("schema_version")
    if not (
        isinstance(version, int) and not isinstance(version, bool) and version == _SCHEMA_VERSION
    ):
        raise StoreError(
            f"cannot load snapshot {path}: unsupported schema_version {version!r} "
            f"(expected {_SCHEMA_VERSION})"
        )

    try:
        model_slug = doc["model_slug"]
        fetched_at = _parse_fetched_at(doc["fetched_at"], path)
        raw_endpoints = doc["endpoints"]
    except KeyError as exc:
        raise StoreError(f"cannot load snapshot {path}: missing key {exc.args[0]!r}") from exc
    except TypeError as exc:
        raise StoreError(f"cannot load snapshot {path}: {exc}") from exc

    if not isinstance(model_slug, str):
        raise StoreError(f"cannot load snapshot {path}: model_slug must be a string")
    if not isinstance(raw_endpoints, list):
        raise StoreError(f"cannot load snapshot {path}: endpoints must be a list")

    endpoints = [_parse_endpoint(raw, path) for raw in raw_endpoints]
    try:
        return Snapshot(model_slug=model_slug, fetched_at=fetched_at, endpoints=tuple(endpoints))
    except ValueError as exc:
        raise StoreError(f"cannot load snapshot {path}: {exc}") from exc


def _parse_endpoint(raw: object, path: Path) -> EndpointRecord:
    """Convert one serialised endpoint dict back into an :class:`EndpointRecord`."""
    if not isinstance(raw, dict):
        raise StoreError(f"cannot load snapshot {path}: endpoint is not an object")

    try:
        tag = raw["tag"]
        provider_name = raw["provider_name"]
        context_length = raw["context_length"]
        max_completion_tokens = raw["max_completion_tokens"]
        quantization = raw["quantization"]
        supported_parameters = raw["supported_parameters"]
    except KeyError as exc:
        raise StoreError(
            f"cannot load snapshot {path}: endpoint missing key {exc.args[0]!r}"
        ) from exc

    if not isinstance(tag, str):
        raise StoreError(f"cannot load snapshot {path}: endpoint tag must be a string")
    if not isinstance(provider_name, str):
        raise StoreError(f"cannot load snapshot {path}: endpoint provider_name must be a string")
    if not isinstance(supported_parameters, list):
        raise StoreError(
            f"cannot load snapshot {path}: endpoint supported_parameters must be a list"
        )
    for item in supported_parameters:
        if not isinstance(item, str):
            raise StoreError(
                f"cannot load snapshot {path}: supported_parameters element must be a string"
            )

    return EndpointRecord(
        tag=tag,
        provider_name=provider_name,
        context_length=_optional_int(context_length, "context_length", path),
        max_completion_tokens=_optional_int(max_completion_tokens, "max_completion_tokens", path),
        quantization=_optional_str(quantization, "quantization", path),
        price_prompt=_parse_price(raw.get("price_prompt"), "price_prompt", path),
        price_completion=_parse_price(raw.get("price_completion"), "price_completion", path),
        supported_parameters=frozenset(supported_parameters),
    )


def _parse_fetched_at(value: object, path: Path) -> datetime:
    if not isinstance(value, str):
        raise StoreError(f"cannot load snapshot {path}: fetched_at must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StoreError(
            f"cannot load snapshot {path}: invalid fetched_at {value!r}: {exc}"
        ) from exc
    if parsed.tzinfo is None:
        raise StoreError(f"cannot load snapshot {path}: fetched_at is naive: {value!r}")
    return parsed.astimezone(UTC)


def _parse_price(value: object, name: str, path: Path) -> Decimal:
    if not isinstance(value, str):
        raise StoreError(f"cannot load snapshot {path}: endpoint[{name!r}] must be a string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise StoreError(
            f"cannot load snapshot {path}: endpoint[{name!r}] is not a decimal: {value!r}"
        ) from exc
    if not parsed.is_finite():
        raise StoreError(
            f"cannot load snapshot {path}: endpoint[{name!r}] is not a finite decimal: {value!r}"
        )
    return parsed


def _optional_int(value: object, name: str, path: Path) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StoreError(f"cannot load snapshot {path}: endpoint[{name!r}] must be an int or null")
    return value


def _optional_str(value: object, name: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StoreError(
            f"cannot load snapshot {path}: endpoint[{name!r}] must be a string or null"
        )
    return value


# --- naming and pruning -------------------------------------------------------


def _model_dir(slug: str, root: Path) -> Path:
    return root / slug.replace("/", "__")


def _filename(snap: Snapshot) -> str:
    """Return the second-precision base filename (no collision suffix)."""
    ts = snap.fetched_at.astimezone(UTC).replace(microsecond=0)
    return ts.strftime("%Y-%m-%dT%H-%M-%SZ") + ".json"


def _unique_path(model_dir: Path, filename: str) -> Path:
    """Return a free path, appending ``-1``, ``-2``, ... on same-second collision."""
    candidate = model_dir / filename
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = model_dir / f"{filename[: -len('.json')]}-{counter}.json"
    return candidate


def _parse_filename(name: str) -> tuple[datetime, int] | None:
    """Parse a filename into its ordering key ``(timestamp, counter)``.

    Returns ``None`` for names that do not match the recognised pattern. The
    ordering key is ``(parsed second-precision timestamp, collision counter)``
    — never a lexicographic sort of the filename, because ``'-' < '.'`` would
    put a suffixed name before its bare sibling (decision D3).
    """
    match = _FILENAME_RE.match(name)
    if match is None:
        return None
    ts_str, counter_str = match.group(1), match.group(2)
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=UTC)
    except ValueError:
        # Regex-valid but calendar-invalid (e.g. 2026-13-99), hence
        # unparseable — treat as ignored/never-pruned per decision D4.
        return None
    counter = int(counter_str) if counter_str is not None else 0
    return (ts, counter)


def _prune(model_dir: Path, retention: int) -> None:
    """Delete all but the newest ``retention`` parseable snapshots in the dir."""
    retention = max(0, retention)

    matches: list[tuple[tuple[datetime, int], Path]] = []
    try:
        for child in model_dir.iterdir():
            if not child.is_file():
                continue
            parsed = _parse_filename(child.name)
            if parsed is not None:
                matches.append((parsed, child))
    except OSError as exc:
        raise StoreError(f"cannot enumerate snapshot directory {model_dir}: {exc}") from exc

    matches.sort(key=lambda m: m[0], reverse=True)
    for _, stale in matches[retention:]:
        try:
            stale.unlink()
        except OSError as exc:
            raise StoreError(f"cannot prune snapshot {stale}: {exc}") from exc
