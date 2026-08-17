"""Bounded OAuth transport foundation for EPO Open Patent Services."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.research.patent_source_policy import EPO_OPS_HOSTNAME
from app.schemas.epo_ops_config import EpoOpsAccessToken, EpoOpsConfig

EPO_OPS_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"


@dataclass(frozen=True, slots=True)
class EpoOpsHttpResponse:
    """Bounded response metadata needed by source-specific parsers."""

    body: bytes
    content_type: str


class EpoOpsError(RuntimeError):
    """Base class for safe EPO OPS transport failures."""


class EpoOpsEndpointError(EpoOpsError):
    """The requested endpoint is outside the exact OPS HTTPS boundary."""


class EpoOpsAuthenticationError(EpoOpsError):
    """OPS rejected the application credentials or bearer token."""


class EpoOpsRateLimitError(EpoOpsError):
    """OPS rejected a request under rate or fair-use controls."""


class EpoOpsProviderError(EpoOpsError):
    """OPS returned a server-side failure."""


class EpoOpsTimeoutError(EpoOpsError):
    """An OPS request exceeded the configured timeout."""


class EpoOpsNetworkError(EpoOpsError):
    """An OPS request could not reach the provider."""


class EpoOpsResponseTooLargeError(EpoOpsError):
    """An OPS response exceeded the configured byte boundary."""


class EpoOpsResponseValidationError(EpoOpsError):
    """OPS returned a malformed token or unexpected content contract."""


class EpoOpsHttpError(EpoOpsError):
    """OPS returned an unexpected non-success HTTP status."""


class EpoOpsClient:
    """Obtain OAuth tokens and return bounded, unparsed OPS response bytes."""

    def __init__(
        self,
        *,
        config: EpoOpsConfig,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._config = config
        self._client = client
        self._clock = clock
        self._cached_token: EpoOpsAccessToken | None = None
        self._token_refresh_at = 0.0

    def access_token(self) -> EpoOpsAccessToken:
        """Return a valid in-memory token, refreshing conservatively if needed."""

        now = self._clock()
        if self._cached_token is not None and now < self._token_refresh_at:
            return self._cached_token.model_copy(deep=True)

        token = self._request_access_token()
        safety_margin = min(30.0, token.expires_in * 0.1)
        self._cached_token = token
        self._token_refresh_at = now + token.expires_in - safety_margin
        return token.model_copy(deep=True)

    def authenticated_get(self, *, endpoint: str, accept: str) -> bytes:
        """GET one exact OPS endpoint and return bounded bytes without XML parsing."""

        return self.authenticated_get_response(
            endpoint=endpoint,
            accept=accept,
        ).body

    def authenticated_get_response(
        self,
        *,
        endpoint: str,
        accept: str,
        extra_headers: dict[str, str] | None = None,
    ) -> EpoOpsHttpResponse:
        """GET one OPS endpoint and preserve its bounded content contract."""

        self._validate_endpoint(endpoint)
        if not isinstance(accept, str) or not accept.strip():
            raise EpoOpsEndpointError("EPO OPS Accept value must not be blank")

        safe_extra_headers: dict[str, str] = {}
        if extra_headers:
            for name, value in extra_headers.items():
                if not isinstance(name, str) or not isinstance(value, str):
                    raise EpoOpsEndpointError(
                        "EPO OPS extra headers must contain nonblank strings"
                    )
                normalized_name = name.strip().casefold()
                if normalized_name in {"authorization", "accept"}:
                    raise EpoOpsEndpointError(
                        "EPO OPS protected headers must not be overridden"
                    )
                if not name.strip() or not value.strip():
                    raise EpoOpsEndpointError(
                        "EPO OPS extra headers must contain nonblank strings"
                    )
                safe_extra_headers[name.strip()] = value.strip()

        headers = {
            "Authorization": (
                f"Bearer {self.access_token().access_token.get_secret_value()}"
            ),
            "Accept": accept.strip(),
            **safe_extra_headers,
        }

        return self._request_response(
            method="GET",
            url=endpoint,
            headers=headers,
        )

    def _request_access_token(self) -> EpoOpsAccessToken:
        response = self._request_response(
            method="POST",
            url=EPO_OPS_TOKEN_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            auth=httpx.BasicAuth(
                self._config.consumer_key.get_secret_value(),
                self._config.consumer_secret.get_secret_value(),
            ),
        )
        try:
            return EpoOpsAccessToken.model_validate_json(response.body)
        except (ValidationError, ValueError):
            raise EpoOpsResponseValidationError(
                "EPO OPS returned an invalid access-token response."
            ) from None

    def _request_response(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
    ) -> EpoOpsHttpResponse:
        try:
            with (
                self._client_context() as client,
                client.stream(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    auth=auth,
                    timeout=self._config.timeout_seconds,
                    follow_redirects=False,
                ) as response,
            ):
                self._raise_for_status(response)
                self._validate_content_contract(response)
                self._validate_declared_size(response)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self._config.maximum_response_bytes:
                        raise EpoOpsResponseTooLargeError(
                            "EPO OPS response exceeded the configured byte limit."
                        )
                return EpoOpsHttpResponse(
                    body=bytes(body),
                    content_type=response.headers["Content-Type"],
                )
        except httpx.TimeoutException:
            raise EpoOpsTimeoutError("EPO OPS request timed out.") from None
        except httpx.RequestError:
            raise EpoOpsNetworkError("EPO OPS request failed on the network.") from None

    def _client_context(self) -> AbstractContextManager[httpx.Client]:
        if self._client is not None:
            return nullcontext(self._client)
        return httpx.Client()

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if not isinstance(endpoint, str):
            raise TypeError("endpoint must be a string")
        parsed = urlsplit(endpoint)
        if (
            endpoint != endpoint.strip()
            or parsed.scheme.casefold() != "https"
            or (parsed.hostname or "").casefold() != EPO_OPS_HOSTNAME
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or not parsed.path.startswith("/3.2/")
        ):
            raise EpoOpsEndpointError(
                "EPO OPS endpoint is outside the accepted boundary"
            )

    def _validate_declared_size(self, response: httpx.Response) -> None:
        value = response.headers.get("Content-Length")
        if value is None:
            return
        try:
            declared = int(value)
        except ValueError:
            return
        if declared > self._config.maximum_response_bytes:
            raise EpoOpsResponseTooLargeError(
                "EPO OPS response exceeded the configured byte limit."
            )

    @staticmethod
    def _validate_content_contract(response: httpx.Response) -> None:
        if not response.headers.get("Content-Type", "").strip():
            raise EpoOpsResponseValidationError(
                "EPO OPS response did not declare a content type."
            )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status == 403 and response.headers.get("X-Rejection-Reason", "").strip():
            raise EpoOpsRateLimitError("EPO OPS rate or fair-use limit was reached.")
        if status in {401, 403}:
            raise EpoOpsAuthenticationError("EPO OPS authentication was rejected.")
        if status == 429:
            raise EpoOpsRateLimitError("EPO OPS rate or fair-use limit was reached.")
        if status >= 500:
            raise EpoOpsProviderError("EPO OPS returned a provider failure.")
        raise EpoOpsHttpError(f"EPO OPS returned HTTP status {status}.")
