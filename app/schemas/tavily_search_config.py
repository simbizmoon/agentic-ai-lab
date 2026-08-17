"""Configuration for Tavily web search."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from ipaddress import ip_address
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

MAXIMUM_INCLUDE_DOMAINS = 20
_DOMAIN_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class TavilySearchConfig(BaseModel):
    """Validated configuration for Tavily Search API."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    api_key: SecretStr
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    maximum_results: int = Field(default=10, ge=1, le=20)
    project_id: str | None = None
    include_domains: tuple[str, ...] = Field(
        default=(), max_length=MAXIMUM_INCLUDE_DOMAINS
    )

    @field_validator("include_domains", mode="before")
    @classmethod
    def normalize_include_domains(cls, value: object) -> object:
        """Return canonical lower-case hostnames without changing order."""

        if not isinstance(value, tuple):
            return value

        normalized: list[str] = []
        for domain in value:
            if not isinstance(domain, str):
                raise TypeError("include_domains values must be strings")
            canonical = domain.strip().casefold()
            cls._validate_domain(canonical)
            normalized.append(canonical)

        if len(set(normalized)) != len(normalized):
            raise ValueError("include_domains must not contain duplicates")
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        """Validate text fields without exposing secrets."""

        if not self.api_key.get_secret_value().strip():
            raise ValueError("TAVILY_API_KEY must not be blank")

        if not self.base_url.strip():
            raise ValueError("base_url must not be blank")

        if not self.base_url.startswith("https://"):
            raise ValueError("base_url must use https")

        if self.project_id is not None and not self.project_id.strip():
            raise ValueError("project_id must not be blank when provided")

        return self

    @staticmethod
    def _validate_domain(domain: str) -> None:
        if not domain:
            raise ValueError("include_domains must not contain blank values")
        if len(domain) > 253:
            raise ValueError("include_domains contains an invalid domain")
        if any(character in domain for character in ":/@"):
            raise ValueError("include_domains values must be hostnames")
        if domain.endswith("."):
            raise ValueError("include_domains contains an invalid domain")
        if domain == "localhost" or domain.endswith(".localhost"):
            raise ValueError("include_domains contains an unsafe hostname")
        try:
            ip_address(domain)
        except ValueError:
            pass
        else:
            raise ValueError("include_domains values must not be IP addresses")
        if any(
            _DOMAIN_LABEL_PATTERN.fullmatch(label) is None
            for label in domain.split(".")
        ):
            raise ValueError("include_domains contains an invalid domain")

    @property
    def search_url(self) -> str:
        """Return the Tavily search endpoint."""

        return f"{self.base_url.rstrip('/')}/search"


def load_tavily_search_config(
    environ: Mapping[str, str] | None = None,
) -> TavilySearchConfig:
    """Load Tavily configuration from environment values."""

    values = os.environ if environ is None else environ

    api_key = values.get("TAVILY_API_KEY", "").strip()
    project_id = values.get("TAVILY_PROJECT_ID", "").strip()
    timeout_raw = values.get("TAVILY_TIMEOUT_SECONDS", "15").strip()
    maximum_results_raw = values.get("TAVILY_MAX_RESULTS", "10").strip()

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("TAVILY_TIMEOUT_SECONDS must be numeric") from exc

    try:
        maximum_results = int(maximum_results_raw)
    except ValueError as exc:
        raise ValueError("TAVILY_MAX_RESULTS must be an integer") from exc

    return TavilySearchConfig(
        api_key=SecretStr(api_key),
        timeout_seconds=timeout_seconds,
        maximum_results=maximum_results,
        project_id=project_id or None,
    )
