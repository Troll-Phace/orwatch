"""HTTP client for the OpenRouter endpoints API.

This is the single network seam in orwatch. Per the module graph
(ARCHITECTURE §3.1), it is the ONLY module that imports httpx; everything
downstream operates on already-loaded data. That is what keeps the rest of
the codebase testable offline.

All failures surface as :class:`orwatch.errors.FetchError` and name the model
slug being fetched.
"""

import httpx

from orwatch.errors import FetchError

BASE_URL = "https://openrouter.ai/api/v1"


def fetch_endpoints(
    slug: str,
    *,
    timeout: float = 20.0,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """Fetch the raw endpoint metadata for a model slug.

    GET ``{BASE_URL}/models/{slug}/endpoints`` and return the parsed JSON body
    unchanged — no normalisation happens here. ``transport`` is the
    test-injection seam: ``None`` selects the default httpx transport. The
    client is constructed and torn down inside this function; it is never
    exposed to callers.

    Raises:
        FetchError: on any httpx error (timeout, connection failure, DNS,
            decoding/encoding errors), on any non-200 HTTP status, or on
            unparseable JSON. Every message names the slug; non-200 messages
            also carry the status code.

    Args:
        slug: model slug, e.g. ``moonshotai/kimi-k3``.
        timeout: per-request timeout in seconds.
        transport: optional httpx transport for injecting a mock in tests.
    """
    url = f"{BASE_URL}/models/{slug}/endpoints"
    try:
        with httpx.Client(transport=transport, timeout=timeout) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise FetchError(f"transport error fetching endpoints for {slug!r}: {exc}") from exc

    if response.status_code != 200:
        raise FetchError(f"fetching endpoints for {slug!r} returned status {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise FetchError(f"unparseable JSON in endpoints response for {slug!r}") from exc
