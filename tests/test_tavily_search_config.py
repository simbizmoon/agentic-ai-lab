"""Tests for Tavily search configuration."""

import pytest
from pydantic import SecretStr, ValidationError

from app.schemas.tavily_search_config import (
    TavilySearchConfig,
    load_tavily_search_config,
)


def test_config_accepts_valid_values() -> None:
    config = TavilySearchConfig(api_key=SecretStr("secret-key"))

    assert config.search_url == "https://api.tavily.com/search"
    assert config.maximum_results == 10
    assert config.include_domains == ()


def test_loader_reads_environment_values() -> None:
    config = load_tavily_search_config(
        {
            "TAVILY_API_KEY": "secret-key",
            "TAVILY_PROJECT_ID": "project-001",
            "TAVILY_TIMEOUT_SECONDS": "20",
            "TAVILY_MAX_RESULTS": "7",
        }
    )

    assert config.project_id == "project-001"
    assert config.timeout_seconds == 20
    assert config.maximum_results == 7


def test_loader_rejects_missing_api_key() -> None:
    with pytest.raises(
        ValidationError,
        match="TAVILY_API_KEY must not be blank",
    ):
        load_tavily_search_config({})


def test_loader_rejects_invalid_numbers() -> None:
    with pytest.raises(ValueError, match="must be numeric"):
        load_tavily_search_config(
            {
                "TAVILY_API_KEY": "secret-key",
                "TAVILY_TIMEOUT_SECONDS": "invalid",
            }
        )

    with pytest.raises(ValueError, match="must be an integer"):
        load_tavily_search_config(
            {
                "TAVILY_API_KEY": "secret-key",
                "TAVILY_MAX_RESULTS": "invalid",
            }
        )


def test_config_does_not_expose_secret_in_repr() -> None:
    config = TavilySearchConfig(api_key=SecretStr("do-not-expose"))

    assert "do-not-expose" not in repr(config)
    assert "do-not-expose" not in str(config)


def test_config_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            timeout_seconds=0,
        )

    with pytest.raises(ValidationError):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            maximum_results=21,
        )

    with pytest.raises(
        ValidationError,
        match="base_url must use https",
    ):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            base_url="ftp://api.example.com",
        )


def test_config_normalizes_include_domains_without_reordering() -> None:
    config = TavilySearchConfig(
        api_key=SecretStr("secret-key"),
        include_domains=(" Patentscope.WIPO.Int ", "EXAMPLE.GOV"),
    )

    assert config.include_domains == (
        "patentscope.wipo.int",
        "example.gov",
    )


@pytest.mark.parametrize(
    "domain",
    [
        "",
        "https://patentscope.wipo.int",
        "patentscope.wipo.int/path",
        "user@patentscope.wipo.int",
        "patentscope.wipo.int:443",
        "localhost",
        "127.0.0.1",
        "bad_domain.example",
    ],
)
def test_config_rejects_invalid_include_domains(domain: str) -> None:
    with pytest.raises(ValidationError):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            include_domains=(domain,),
        )


def test_config_rejects_normalized_duplicate_domains() -> None:
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            include_domains=(
                "patentscope.wipo.int",
                "PATENTSCOPE.WIPO.INT",
            ),
        )


def test_config_requires_immutable_strict_domain_tuple() -> None:
    with pytest.raises(ValidationError):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            include_domains=["patentscope.wipo.int"],  # type: ignore[arg-type]
        )


def test_config_bounds_include_domain_count() -> None:
    with pytest.raises(ValidationError):
        TavilySearchConfig(
            api_key=SecretStr("secret-key"),
            include_domains=tuple(f"host-{index}.example" for index in range(21)),
        )
