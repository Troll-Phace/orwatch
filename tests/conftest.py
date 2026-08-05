"""Shared fixtures for the orwatch test suite.

The two factory fixtures here are intentionally general: :func:`make_endpoint`
builds an :class:`EndpointRecord` and :func:`make_snapshot` builds a
:class:`Snapshot`. Later phases (store, diff, cli) reuse them, so defaults
match the realistic example record shape from ARCHITECTURE §5 and every field
is overridable by keyword.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orwatch.models import EndpointRecord, Snapshot

# Fixed, tz-aware UTC datetime per the delegation's determinism rule. Never
# datetime.now() — the diff/store layers depend on stable, injectable times.
FIXED_FETCHED_AT = datetime(2026, 8, 5, 0, 32, 17, tzinfo=UTC)

# Realistic defaults lifted from ARCHITECTURE §5, which the fixtures must stay
# consistent with. Prices are Decimal string literals, never floats.
ENDPOINT_DEFAULTS: dict = {
    "tag": "moonshotai/mxfp4",
    "provider_name": "Moonshot AI",
    "context_length": 1048576,
    "max_completion_tokens": None,
    "quantization": "mxfp4",
    "price_prompt": Decimal("0.000003"),
    "price_completion": Decimal("0.000015"),
    "supported_parameters": frozenset(
        {"reasoning", "response_format", "structured_outputs", "tool_choice", "tools"}
    ),
}


@pytest.fixture
def make_endpoint():
    def _make(**overrides: object) -> EndpointRecord:
        fields = {**ENDPOINT_DEFAULTS, **overrides}
        return EndpointRecord(**fields)

    return _make


@pytest.fixture
def make_snapshot():
    def _make(
        endpoints: tuple[EndpointRecord, ...] = (),
        *,
        model_slug: str = "moonshotai/kimi-k3",
        fetched_at: datetime = FIXED_FETCHED_AT,
    ) -> Snapshot:
        return Snapshot(
            model_slug=model_slug,
            fetched_at=fetched_at,
            endpoints=endpoints,
        )

    return _make
