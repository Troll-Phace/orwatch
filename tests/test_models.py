"""Tests for the frozen data model (models.py).

Covers the tool_capable property across all four capability combinations, the
frozen/slots enforcement, Snapshot's tag-sorting and tz-awareness validation,
and the value/hash semantics that the diff layer will rely on.
"""

from dataclasses import FrozenInstanceError

import pytest

from orwatch.models import Snapshot

# --- tool_capable: the four capability combinations -------------------------


def test_tool_capable_true_when_tools_and_tool_choice_present(make_endpoint):
    ep = make_endpoint()
    assert ep.tool_capable is True


def test_tool_capable_false_when_tools_without_tool_choice(make_endpoint):
    """tools present but tool_choice absent is false capability.

    The endpoint still advertises tools, so it would pass a naive
    "does it have tools" check — the subtle regression this tool exists to
    surface. Must be `is False`, not merely falsy.
    """
    ep = make_endpoint(supported_parameters=frozenset({"tools", "reasoning"}))
    assert ep.tool_capable is False


def test_tool_capable_false_when_neither_present(make_endpoint):
    ep = make_endpoint(supported_parameters=frozenset({"reasoning"}))
    assert ep.tool_capable is False


def test_tool_capable_false_when_only_tool_choice_present(make_endpoint):
    ep = make_endpoint(supported_parameters=frozenset({"tool_choice", "reasoning"}))
    assert ep.tool_capable is False


# --- EndpointRecord immutability --------------------------------------------


def test_endpoint_record_is_frozen(make_endpoint):
    ep = make_endpoint()
    with pytest.raises(FrozenInstanceError):
        ep.tag = "some/other"  # type: ignore[misc]


# --- Snapshot construction ----------------------------------------------------


def test_snapshot_sorts_endpoints_by_tag(make_endpoint, make_snapshot):
    z = make_endpoint(tag="z/end")
    a = make_endpoint(tag="a/start")
    m = make_endpoint(tag="m/mid")
    snap = make_snapshot(endpoints=(z, a, m))

    assert [e.tag for e in snap.endpoints] == ["a/start", "m/mid", "z/end"]


def test_snapshot_rejects_naive_fetched_at(make_endpoint):
    """fetched_at without tzinfo must raise ValueError in __post_init__."""
    from datetime import datetime

    naive = datetime(2026, 8, 5, 0, 32, 17)  # no tzinfo → invalid
    with pytest.raises(ValueError, match="fetched_at must be tz-aware"):
        Snapshot(
            model_slug="moonshotai/kimi-k3",
            fetched_at=naive,
            endpoints=(make_endpoint(),),
        )


# --- value and hash semantics ------------------------------------------------


def test_equal_records_are_equal_and_hash_equally(make_endpoint):
    a = make_endpoint()
    b = make_endpoint()
    assert a == b
    assert hash(a) == hash(b)


def test_records_with_different_tags_are_unequal(make_endpoint):
    a = make_endpoint(tag="moonshotai/mxfp4")
    b = make_endpoint(tag="moonshotai/mxfp4/fast")
    assert a != b
    assert hash(a) != hash(b)


def test_tool_capable_ignores_extra_parameters(make_endpoint):
    ep = make_endpoint(
        supported_parameters=frozenset(
            {"tools", "tool_choice", "response_format", "structured_outputs"}
        )
    )
    assert ep.tool_capable is True


def test_snapshot_is_frozen(make_snapshot):
    snap = make_snapshot()
    with pytest.raises(FrozenInstanceError):
        snap.model_slug = "some/other"  # type: ignore[misc]


def test_snapshot_endpoints_default_to_empty_tuple(make_snapshot):
    snap = make_snapshot()
    assert snap.endpoints == ()
