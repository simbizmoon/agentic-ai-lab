"""Tests for the bounded EPO OPS OAuth transport."""

from __future__ import annotations

import base64
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from app.research.epo_ops_client import (
    EPO_OPS_TOKEN_URL,
    EpoOpsAuthenticationError,
    EpoOpsClient,
    EpoOpsEndpointError,
    EpoOpsHttpError,
    EpoOpsNetworkError,
    EpoOpsProviderError,
    EpoOpsRateLimitError,
    EpoOpsResponseTooLargeError,
    EpoOpsResponseValidationError,
    EpoOpsTimeoutError,
)
from app.schemas.epo_ops_config import EpoOpsConfig

RESOURCE_URL = "https://ops.epo.org/3.2/rest-services/published-data/test"
CONSUMER_KEY = "private-consumer-key"
CONSUMER_SECRET = "private-consumer-secret"
BEARER_TOKEN = "private-bearer-token"


def config(**overrides: object) -> EpoOpsConfig:
    values: dict[str, object] = {
        "consumer_key": SecretStr(CONSUMER_KEY),
        "consumer_secret": SecretStr(CONSUMER_SECRET),
    }
    values.update(overrides)
    return EpoOpsConfig.model_validate(values)


def token_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json"},
        json={
            "access_token": BEARER_TOKEN,
            "token_type": "Bearer",
            "expires_in": "120",
        },
        request=request,
    )


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    value: EpoOpsConfig | None = None,
    clock: Callable[[], float] = lambda: 0.0,
) -> EpoOpsClient:
    return EpoOpsClient(
        config=value or config(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=clock,
    )


def test_token_request_uses_documented_contract() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return token_response(request)

    token = client_for(handler).access_token()

    assert token.access_token.get_secret_value() == BEARER_TOKEN
    request = captured[0]
    assert str(request.url) == EPO_OPS_TOKEN_URL
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert request.content == b"grant_type=client_credentials"
    encoded = request.headers["Authorization"].removeprefix("Basic ")
    assert base64.b64decode(encoded).decode() == (f"{CONSUMER_KEY}:{CONSUMER_SECRET}")


def test_token_is_cached_and_refreshed_before_expiry() -> None:
    now = [0.0]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return token_response(request)

    client = client_for(handler, clock=lambda: now[0])
    client.access_token()
    now[0] = 100.0
    client.access_token()
    assert calls == 1
    now[0] = 109.0
    client.access_token()
    assert calls == 2


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, EpoOpsAuthenticationError),
        (403, EpoOpsAuthenticationError),
        (429, EpoOpsRateLimitError),
        (500, EpoOpsProviderError),
        (503, EpoOpsProviderError),
        (400, EpoOpsHttpError),
    ],
)
def test_http_errors_are_mapped_without_provider_body(
    status: int,
    error_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=(CONSUMER_KEY + CONSUMER_SECRET + BEARER_TOKEN).encode(),
            request=request,
        )

    with pytest.raises(error_type) as captured:
        client_for(handler).access_token()

    rendered = str(captured.value) + repr(captured.value)
    assert CONSUMER_KEY not in rendered
    assert CONSUMER_SECRET not in rendered
    assert BEARER_TOKEN not in rendered


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        ("timeout", EpoOpsTimeoutError),
        ("network", EpoOpsNetworkError),
    ],
)
def test_transport_failures_are_mapped(
    failure: str,
    error_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        raise httpx.ConnectError("network", request=request)

    with pytest.raises(error_type):
        client_for(handler).access_token()


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b'{"token_type":"Bearer","expires_in":120}',
        b'{"access_token":"value","token_type":"mac","expires_in":120}',
    ],
)
def test_malformed_token_response_is_rejected(payload: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=payload,
            request=request,
        )

    with pytest.raises(EpoOpsResponseValidationError):
        client_for(handler).access_token()


def test_missing_content_type_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{}", request=request)

    with pytest.raises(EpoOpsResponseValidationError):
        client_for(handler).access_token()


@pytest.mark.parametrize("declared", [True, False])
def test_response_size_limit_rejects_declared_and_streamed_body(
    declared: bool,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        content = b"x" * 1_025
        if declared:
            headers["Content-Length"] = "2048"
            content = b"{}"
        return httpx.Response(200, headers=headers, content=content, request=request)

    with pytest.raises(EpoOpsResponseTooLargeError):
        client_for(
            handler,
            value=config(maximum_response_bytes=1_024),
        ).access_token()


def test_authenticated_get_adds_bearer_and_returns_unparsed_bytes() -> None:
    requests: list[httpx.Request] = []
    xml = b"<ops:world-patent-data/>"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == EPO_OPS_TOKEN_URL:
            return token_response(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/ops+xml"},
            content=xml,
            request=request,
        )

    result = client_for(handler).authenticated_get(
        endpoint=RESOURCE_URL,
        accept="application/ops+xml",
    )

    assert result == xml
    assert requests[1].method == "GET"
    assert requests[1].headers["Authorization"] == f"Bearer {BEARER_TOKEN}"
    assert requests[1].headers["Accept"] == "application/ops+xml"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://ops.epo.org/3.2/rest-services/test",
        "https://ops.epo.org.evil.example/3.2/rest-services/test",
        "https://evil-ops.epo.org/3.2/rest-services/test",
        "https://ops.epo.org:443/3.2/rest-services/test",
        "https://user:secret@ops.epo.org/3.2/rest-services/test",
        "https://ops.epo.org/rest-services/test",
    ],
)
def test_authenticated_get_rejects_unsafe_endpoint_before_auth(
    endpoint: str,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return token_response(request)

    with pytest.raises(EpoOpsEndpointError):
        client_for(handler).authenticated_get(
            endpoint=endpoint,
            accept="application/ops+xml",
        )
    assert calls == 0


def test_authenticated_get_uses_configured_timeout() -> None:
    seen: list[dict[str, float]] = []

    class RecordingTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.extensions["timeout"]))
            if str(request.url) == EPO_OPS_TOKEN_URL:
                return token_response(request)
            return httpx.Response(
                200,
                headers={"Content-Type": "application/ops+xml"},
                content=b"<xml/>",
                request=request,
            )

    client = EpoOpsClient(
        config=config(timeout_seconds=7.0),
        client=httpx.Client(transport=RecordingTransport()),
    )
    client.authenticated_get(endpoint=RESOURCE_URL, accept="application/ops+xml")

    assert seen
    assert all(value == 7.0 for timeout in seen for value in timeout.values())


def test_secret_material_is_absent_from_client_and_error_rendering() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == EPO_OPS_TOKEN_URL:
            return token_response(request)
        return httpx.Response(
            500,
            content=(CONSUMER_KEY + CONSUMER_SECRET + BEARER_TOKEN).encode(),
            request=request,
        )

    client = client_for(handler)
    with pytest.raises(EpoOpsProviderError) as captured:
        client.authenticated_get(endpoint=RESOURCE_URL, accept="application/ops+xml")

    rendered = repr(client) + str(captured.value) + repr(captured.value)
    assert CONSUMER_KEY not in rendered
    assert CONSUMER_SECRET not in rendered
    assert BEARER_TOKEN not in rendered


def test_authenticated_get_response_preserves_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == EPO_OPS_TOKEN_URL:
            return token_response(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/exchange+xml; charset=UTF-8"},
            content=b"<xml/>",
            request=request,
        )

    response = client_for(handler).authenticated_get_response(
        endpoint=RESOURCE_URL,
        accept="application/exchange+xml",
    )

    assert response.body == b"<xml/>"
    assert response.content_type == "application/exchange+xml; charset=UTF-8"


def test_documented_403_rejection_header_maps_to_fair_use() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-Rejection-Reason": "RegisteredQuotaPerWeek"},
            request=request,
        )

    with pytest.raises(EpoOpsRateLimitError):
        client_for(handler).access_token()


def test_plain_403_remains_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    with pytest.raises(EpoOpsAuthenticationError):
        client_for(handler).access_token()


def test_authenticated_get_response_accepts_bounded_ops_range_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == EPO_OPS_TOKEN_URL:
            return token_response(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/exchange+xml"},
            content=b"<xml/>",
            request=request,
        )

    client_for(handler).authenticated_get_response(
        endpoint=RESOURCE_URL,
        accept="application/exchange+xml",
        extra_headers={"X-OPS-Range": "1-4"},
    )

    assert requests[1].headers["X-OPS-Range"] == "1-4"


@pytest.mark.parametrize("name", ["Authorization", "authorization", "Accept", "accept"])
def test_authenticated_get_response_rejects_protected_header_override(
    name: str,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return token_response(request)

    with pytest.raises(EpoOpsEndpointError):
        client_for(handler).authenticated_get_response(
            endpoint=RESOURCE_URL,
            accept="application/exchange+xml",
            extra_headers={name: "override"},
        )

    assert calls == 0
