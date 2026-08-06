"""Configuration for Tavily web search."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class TavilySearchConfig(BaseModel):
    """Validated configuration for Tavily Search API."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    api_key: SecretStr
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    maximum_results: int = Field(default=10, ge=1, le=20)
    project_id: str | None = None

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
