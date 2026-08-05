"""Tests for client.py and Snapshot.from_api normalisation (Phase 2).

Every HTTP call goes through the single seam in client.py via
``httpx.MockTransport``; no test touches the network directly. Fixture-based
normalisation tests run against real captured responses under
``tests/fixtures/`` — the shape of the data is what we are normalising, so it
is the ground truth, never the mock.
"""

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from conftest import FIXED_FETCHED_AT

from orwatch.client import fetch_endpoints
from orwatch.errors import FetchError
from orwatch.models import Snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


KIMI = load_fixture("moonshotai__kimi-k3.json")
QWEN = load_fixture("qwen__qwen3.8-max.json")
EMPTY = load_fixture("empty-endpoints.json")

# Minimal structurally-valid endpoint for the synthetic normalisation tests.
MINIMAL_ENDPOINT = {
    "tag": "provider/endpoint",
    "provider_name": "Provider",
    "context_length": 1048576,
    "max_completion_tokens": None,
    "quantization": None,
    "pricing": {"prompt": "0.000001", "completion": "0.000003"},
    "supported_parameters": ["tools", "tool_choice"],
}


def build_payload(endpoints: object) -> dict:
    return {"data": {"endpoints": endpoints}}


# --- fetch_endpoints: happy path ---------------------------------------------


def test_fetch_endpoints_returns_parsed_json_unchanged():
    body = {"data": {"endpoints": [1, 2, 3]}, "meta": {"foo": "bar"}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    result = fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))
    assert result == body


def test_fetch_endpoints_hits_endpoints_url_for_slug():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={})

    fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))
    assert captured["url"] == "https://openrouter.ai/api/v1/models/moonshotai/kimi-k3/endpoints"


# --- fetch_endpoints: error paths --------------------------------------------


def test_fetch_endpoints_non_200_raises_fetch_error_with_slug_and_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    # The D8 guarantee: the message names the slug AND the status code.
    with pytest.raises(FetchError, match=r"moonshotai/kimi-k3.*503"):
        fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))


def test_fetch_endpoints_connect_error_surfaces_as_fetch_error_and_chains():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=httpx.Request("GET", request.url))

    with pytest.raises(FetchError, match="moonshotai/kimi-k3") as excinfo:
        fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))
    # The wrapped httpx error must ride along as __cause__, not be swallowed.
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


def test_fetch_endpoints_read_timeout_surfaces_as_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=httpx.Request("GET", request.url))

    with pytest.raises(FetchError, match="moonshotai/kimi-k3"):
        fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))


def test_fetch_endpoints_non_json_body_raises_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    with pytest.raises(FetchError, match="moonshotai/kimi-k3"):
        fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))


def test_fetch_endpoints_corrupt_encoding_raises_fetch_error():
    """A body that fails to decode under its declared Content-Encoding must
    surface as FetchError. httpx raises DecodingError — an HTTPError subclass —
    when reading the body; the seam must wrap it, not leak it.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"not gzip")

    with pytest.raises(FetchError, match="moonshotai/kimi-k3"):
        fetch_endpoints("moonshotai/kimi-k3", transport=httpx.MockTransport(handler))


# --- normalisation against the real fixtures ---------------------------------


def test_kimi_parses_to_twelve_endpoints_sorted_by_tag():
    snap = Snapshot.from_api("moonshotai/kimi-k3", KIMI, fetched_at=FIXED_FETCHED_AT)
    tags = [e.tag for e in snap.endpoints]
    assert len(tags) == 12
    assert tags == sorted(tags)


def test_kimi_digitalocean_price_is_exact_decimal():
    snap = Snapshot.from_api("moonshotai/kimi-k3", KIMI, fetched_at=FIXED_FETCHED_AT)
    rec = next(e for e in snap.endpoints if e.tag == "digitalocean")
    assert rec.price_prompt == Decimal("0.000003")
    assert rec.price_completion == Decimal("0.000015")


def test_kimi_supported_parameters_is_frozenset():
    snap = Snapshot.from_api("moonshotai/kimi-k3", KIMI, fetched_at=FIXED_FETCHED_AT)
    for rec in snap.endpoints:
        assert type(rec.supported_parameters) is frozenset


def test_kimi_null_max_completion_tokens_parses_to_none():
    snap = Snapshot.from_api("moonshotai/kimi-k3", KIMI, fetched_at=FIXED_FETCHED_AT)
    nulls = sum(1 for e in snap.endpoints if e.max_completion_tokens is None)
    assert nulls == 5  # five of the twelve captured endpoints are null


def test_unknown_endpoint_fields_are_dropped(make_endpoint):
    """An unknown key in the raw endpoint must not leak into the record.

    Uses ``latency_last_30m`` as a realistic unknown key (OpenRouter used to
    serve latency data on endpoint objects). The assertion is record equality:
    parsing a payload carrying the unknown key must yield exactly the record
    built from the known fields alone. Any future change that absorbs unknown
    fields into EndpointRecord breaks the fixpoint and fails this test.
    """
    ep = dict(MINIMAL_ENDPOINT)
    ep["latency_last_30m"] = {"p50": 100}

    snap = Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)
    expected = make_endpoint(
        tag="provider/endpoint",
        provider_name="Provider",
        context_length=1048576,
        max_completion_tokens=None,
        quantization=None,
        price_prompt=Decimal("0.000001"),
        price_completion=Decimal("0.000003"),
        supported_parameters=frozenset({"tools", "tool_choice"}),
    )
    assert snap.endpoints == (expected,)


def test_qwen_parses_to_single_alibaba_endpoint():
    snap = Snapshot.from_api("qwen/qwen3.8-max", QWEN, fetched_at=FIXED_FETCHED_AT)
    assert len(snap.endpoints) == 1
    assert snap.endpoints[0].tag == "alibaba"


def test_empty_endpoints_parses_to_zero_endpoint_snapshot():
    snap = Snapshot.from_api("moonshotai/kimi-k3", EMPTY, fetched_at=FIXED_FETCHED_AT)
    assert snap.endpoints == ()
    assert snap.model_slug == "moonshotai/kimi-k3"


# --- normalisation: synthetic shape errors -----------------------------------


def test_missing_data_parses_to_empty_snapshot():
    snap = Snapshot.from_api("moonshotai/kimi-k3", {}, fetched_at=FIXED_FETCHED_AT)
    assert snap.endpoints == ()
    assert snap.model_slug == "moonshotai/kimi-k3"


def test_data_not_dict_raises_value_error():
    with pytest.raises(ValueError, match="data"):
        Snapshot.from_api("m/slug", {"data": []}, fetched_at=FIXED_FETCHED_AT)


def test_endpoints_not_list_raises_value_error():
    with pytest.raises(ValueError, match="endpoints"):
        Snapshot.from_api("m/slug", {"data": {"endpoints": {}}}, fetched_at=FIXED_FETCHED_AT)


def test_endpoint_missing_tag_raises_value_error():
    ep = dict(MINIMAL_ENDPOINT)
    del ep["tag"]
    with pytest.raises(ValueError, match="tag"):
        Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)


def test_endpoint_missing_pricing_raises_value_error():
    ep = dict(MINIMAL_ENDPOINT)
    del ep["pricing"]
    with pytest.raises(ValueError, match="pricing"):
        Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)


def test_pricing_prompt_not_str_raises_value_error():
    ep = dict(MINIMAL_ENDPOINT)
    ep["pricing"] = {"prompt": 5, "completion": "0.000003"}
    with pytest.raises(ValueError, match="prompt"):
        Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)


def test_pricing_prompt_not_valid_decimal_raises_value_error():
    ep = dict(MINIMAL_ENDPOINT)
    ep["pricing"] = {"prompt": "not-a-number", "completion": "0.000003"}
    with pytest.raises(ValueError, match="prompt"):
        Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)


def test_missing_supported_parameters_means_not_tool_capable():
    ep = dict(MINIMAL_ENDPOINT)
    del ep["supported_parameters"]
    snap = Snapshot.from_api("m/slug", build_payload([ep]), fetched_at=FIXED_FETCHED_AT)
    rec = snap.endpoints[0]
    assert rec.supported_parameters == frozenset()
    assert rec.tool_capable is False


# --- from_api: error matrix (synthetic payloads, one failure mode each) -------


def _endpoint(**overrides: object) -> dict:
    ep = dict(MINIMAL_ENDPOINT)
    ep.update(overrides)
    return ep


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        # payload not a dict -> ValueError
        (["data", "endpoints"], "payload"),
        # an endpoint element that is not a dict -> ValueError
        (build_payload([42]), "endpoint"),
        # provider_name missing -> ValueError
        (
            build_payload([_endpoint(provider_name=None)]),
            "provider_name",
        ),
        # bool is not a valid context_length (deliberate isinstance guard) -> ValueError
        (build_payload([_endpoint(context_length=True)]), "context_length"),
        # supported_parameters not a list -> ValueError
        (build_payload([_endpoint(supported_parameters="tools")]), "supported_parameters"),
        # supported_parameters with a non-str element -> ValueError
        (
            build_payload([_endpoint(supported_parameters=["tools", 42])]),
            "supported_parameters",
        ),
        # pricing missing completion -> ValueError
        (
            build_payload([_endpoint(pricing={"prompt": "0.000001"})]),
            "completion",
        ),
        # prompt priced as NaN -> ValueError naming the field, noting finiteness
        (
            build_payload([_endpoint(pricing={"prompt": "NaN", "completion": "0.000003"})]),
            "finite",
        ),
        # prompt priced as Infinity -> ValueError naming the field, noting finiteness
        (
            build_payload([_endpoint(pricing={"prompt": "Infinity", "completion": "0.000003"})]),
            "finite",
        ),
    ],
)
def test_from_api_rejects_malformed_payload(payload, match):
    with pytest.raises(ValueError, match=match):
        Snapshot.from_api("m/slug", payload, fetched_at=FIXED_FETCHED_AT)


def test_data_present_but_null_is_tolerated_zero_endpoint_snapshot():
    """{"data": None} and an absent data key are the same empty-but-valid
    response (D3 tolerance) — this must not raise."""
    snap = Snapshot.from_api("m/slug", {"data": None}, fetched_at=FIXED_FETCHED_AT)
    assert snap.endpoints == ()
    assert snap.model_slug == "m/slug"


def test_duplicate_tags_raise_value_error():
    ep = _endpoint()
    with pytest.raises(ValueError, match="duplicate"):
        Snapshot.from_api("m/slug", build_payload([ep, ep]), fetched_at=FIXED_FETCHED_AT)


# --- fetched_at injection ----------------------------------------------------


def test_fetched_at_injected_verbatim():
    snap = Snapshot.from_api(
        "m/slug", build_payload([MINIMAL_ENDPOINT]), fetched_at=FIXED_FETCHED_AT
    )
    assert snap.fetched_at == FIXED_FETCHED_AT


def test_fetched_at_defaults_to_tz_aware():
    snap = Snapshot.from_api("m/slug", build_payload([MINIMAL_ENDPOINT]))
    assert snap.fetched_at.tzinfo is not None
