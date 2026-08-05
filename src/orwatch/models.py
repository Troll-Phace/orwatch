"""Frozen data model for orwatch.

This module defines the two immutable record types that every other module
operates on: :class:`EndpointRecord` (one endpoint's metadata) and
:class:`Snapshot` (a point-in-time capture of a model's endpoints).

Per the module graph (ARCHITECTURE §3.1), models.py imports nothing from the
project and nothing third-party — only stdlib — so it can be reasoned about
in isolation and imported from anywhere without pulling in HTTP or I/O.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


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
