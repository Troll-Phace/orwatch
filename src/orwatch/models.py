"""Frozen data model for orwatch.

This module defines the two immutable record types that every other module
operates on: :class:`EndpointRecord` (one endpoint's metadata) and
:class:`Snapshot` (a point-in-time capture of a model's endpoints).

Per the module graph (ARCHITECTURE §3.1), models.py imports nothing from the
project and nothing third-party — only stdlib — so it can be reasoned about
in isolation and imported from anywhere without pulling in HTTP or I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class EndpointRecord:
    """Metadata for a single OpenRouter endpoint of a watched model.

    :attr:`tag` is the stable identity (e.g. ``"moonshotai/mxfp4"``), not
    ``provider_name`` — a single provider can serve several endpoints for one
    model that differ in quantization, price and capability, and keying on
    ``provider_name`` would merge them. Prices are :class:`Decimal`, not
    ``float``, because they arrive as decimal strings and get compared for
    equality; binary floating point would turn "unchanged" into
    "changed by 1e-19".
    """

    tag: str
    provider_name: str
    context_length: int | None
    max_completion_tokens: int | None
    quantization: str | None
    price_prompt: Decimal
    price_completion: Decimal
    supported_parameters: frozenset[str]

    @property
    def tool_capable(self) -> bool:
        """Whether this endpoint can actually drive tool calling.

        True if and only if BOTH ``"tools"`` and ``"tool_choice"`` are present
        in :attr:`supported_parameters`. Advertising ``tools`` without
        ``tool_choice`` is false capability: the endpoint will accept the
        request but cannot be forced to call a specific tool.
        """
        return {"tools", "tool_choice"} <= self.supported_parameters


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A point-in-time capture of a model's endpoint metadata.

    :attr:`endpoints` is always sorted ascending by :attr:`EndpointRecord.tag`
    so that diffs between two snapshots are deterministic regardless of the
    order the API returned endpoints in.
    """

    model_slug: str
    fetched_at: datetime  # UTC, tz-aware
    endpoints: tuple[EndpointRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None:
            raise ValueError(f"fetched_at must be tz-aware (got naive: {self.fetched_at!r})")
        object.__setattr__(self, "endpoints", tuple(sorted(self.endpoints, key=lambda e: e.tag)))

    @classmethod
    def from_api(
        cls,
        slug: str,
        payload: object,
        *,
        fetched_at: datetime | None = None,
    ) -> Snapshot:
        """Build a :class:`Snapshot` from a raw OpenRouter API response.

        The API returns ``data.endpoints[]``; each endpoint is normalised into
        an :class:`EndpointRecord`. Parsing is tolerant of absence (a missing
        ``data`` or ``endpoints`` is a legitimate empty-but-valid response,
        ARCHITECTURE §4.1) but strict on wrong types — every malformed field
        raises :class:`ValueError` naming the offending field.

        Unknown endpoint fields are dropped deliberately; the record has a
        fixed shape.

        Raises:
            ValueError: if ``payload`` is not a dict, ``data`` or
                ``endpoints`` are present but not a dict/list, an endpoint is
                not a dict, a required field is missing or mistyped, a price
                is missing, not a string, or unparseable, or two endpoints
                share the same tag (ARCHITECTURE §4.1 makes tag the identity,
                so duplicates would make match-by-tag ambiguous).

        Args:
            slug: model slug to attach to the snapshot.
            payload: raw parsed JSON body from ``fetch_endpoints``.
            fetched_at: capture time; defaults to ``datetime.now(UTC)``.
        """
        stamp = fetched_at if fetched_at is not None else datetime.now(UTC)
        if not isinstance(payload, dict):
            raise ValueError(f"payload must be a dict (got {type(payload).__name__})")

        data = payload.get("data")
        if data is None:
            return cls(model_slug=slug, fetched_at=stamp)
        if not isinstance(data, dict):
            raise ValueError(f"payload['data'] must be a dict (got {type(data).__name__})")

        endpoints = data.get("endpoints")
        if endpoints is None:
            return cls(model_slug=slug, fetched_at=stamp)
        if not isinstance(endpoints, list):
            raise ValueError(
                f"payload['data']['endpoints'] must be a list (got {type(endpoints).__name__})"
            )

        records = [cls._parse_endpoint(ep) for ep in endpoints]

        seen: set[str] = set()
        for ep in records:
            if ep.tag in seen:
                raise ValueError(f"duplicate endpoint tag {ep.tag!r} in endpoints response")
            seen.add(ep.tag)

        return cls(model_slug=slug, fetched_at=stamp, endpoints=tuple(records))

    @classmethod
    def _parse_endpoint(cls, raw: object) -> EndpointRecord:
        """Normalise a single raw endpoint dict into an :class:`EndpointRecord`."""
        if not isinstance(raw, dict):
            raise ValueError(f"each endpoint must be a dict (got {type(raw).__name__})")

        tag = raw.get("tag")
        if not isinstance(tag, str):
            raise ValueError(f"endpoint['tag'] must be a str (got {type(tag).__name__!r})")

        provider_name = raw.get("provider_name")
        if not isinstance(provider_name, str):
            raise ValueError(
                f"endpoint['provider_name'] must be a str (got {type(provider_name).__name__!r})"
            )

        context_length = cls._optional_int(raw, "context_length")
        max_completion_tokens = cls._optional_int(raw, "max_completion_tokens")
        quantization = cls._optional_str(raw, "quantization")

        price_prompt, price_completion = cls._parse_pricing(raw.get("pricing"))
        supported_parameters = cls._parse_supported_parameters(raw.get("supported_parameters"))

        return EndpointRecord(
            tag=tag,
            provider_name=provider_name,
            context_length=context_length,
            max_completion_tokens=max_completion_tokens,
            quantization=quantization,
            price_prompt=price_prompt,
            price_completion=price_completion,
            supported_parameters=supported_parameters,
        )

    @staticmethod
    def _optional_int(raw: dict, field_name: str) -> int | None:
        value = raw.get(field_name)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                f"endpoint[{field_name!r}] must be an int or None (got {type(value).__name__!r})"
            )
        return value

    @staticmethod
    def _optional_str(raw: dict, field_name: str) -> str | None:
        value = raw.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"endpoint[{field_name!r}] must be a str or None (got {type(value).__name__!r})"
            )
        return value

    @staticmethod
    def _parse_pricing(pricing: object) -> tuple[Decimal, Decimal]:
        if not isinstance(pricing, dict):
            raise ValueError(f"endpoint['pricing'] must be a dict (got {type(pricing).__name__!r})")

        prompt = pricing.get("prompt")
        completion = pricing.get("completion")
        return (
            Snapshot._parse_price(prompt, "prompt"),
            Snapshot._parse_price(completion, "completion"),
        )

    @staticmethod
    def _parse_price(value: object, name: str) -> Decimal:
        """Parse a single price string into a :class:`Decimal`.

        Prices arrive as decimal strings (e.g. ``"1.20"``) and are compared
        for equality during diffing, so binary float is deliberately avoided.
        ``Decimal`` can also represent ``NaN``/``Infinity`` without raising
        ``InvalidOperation``; because ``NaN != NaN`` those would make two
        identical payloads compare unequal (a determinism violation), so
        non-finite results are rejected.

        Raises:
            ValueError: if ``value`` is not a string, is not a parseable
                decimal, or parses to a non-finite :class:`Decimal`.
        """
        if not isinstance(value, str):
            raise ValueError(
                f"endpoint['pricing'][{name!r}] must be a str (got {type(value).__name__!r})"
            )
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(
                f"endpoint['pricing'][{name!r}] is not a valid decimal string: {value!r}"
            ) from exc
        if not parsed.is_finite():
            raise ValueError(f"endpoint['pricing'][{name!r}] is not a finite decimal: {value!r}")
        return parsed

    @staticmethod
    def _parse_supported_parameters(raw: object) -> frozenset[str]:
        if raw is None:
            return frozenset()
        if not isinstance(raw, list):
            raise ValueError(
                f"endpoint['supported_parameters'] must be a list (got {type(raw).__name__!r})"
            )
        for item in raw:
            if not isinstance(item, str):
                raise ValueError(
                    f"endpoint['supported_parameters'] element must be a str "
                    f"(got {type(item).__name__!r})"
                )
        return frozenset(raw)
