"""Tests for the exact first-slice patent source policy."""

import pytest

from app.research.patent_source_policy import (
    EPO_OPS_HOSTNAME,
    EPO_OPS_SOURCE_FAMILY,
    WIPO_PATENTSCOPE_SOURCE_FAMILY,
    source_family_for_url,
    validate_patent_source_url,
)


def test_policy_accepts_exact_wipo_https_host() -> None:
    url = "https://patentscope.wipo.int/search/en/detail.jsf?docId=example"

    validate_patent_source_url(url)
    assert source_family_for_url(url) == WIPO_PATENTSCOPE_SOURCE_FAMILY


def test_policy_accepts_exact_epo_ops_https_host() -> None:
    url = "https://ops.epo.org/3.2/rest-services/published-data"

    validate_patent_source_url(url)
    assert source_family_for_url(url) == EPO_OPS_SOURCE_FAMILY
    assert EPO_OPS_HOSTNAME == "ops.epo.org"


@pytest.mark.parametrize(
    "url",
    [
        "http://patentscope.wipo.int/search/en/detail.jsf",
        "https://patentscope.wipo.int.evil.example/detail",
        "https://evil-patentscope.wipo.int/detail",
        "https://wipo.int/detail",
        "https://localhost/detail",
        "https://127.0.0.1/detail",
        "http://ops.epo.org/3.2/rest-services",
        "https://ops.epo.org.evil.example/3.2/rest-services",
        "https://evil-ops.epo.org/3.2/rest-services",
        "https://epo.org/3.2/rest-services",
    ],
)
def test_policy_rejects_unaccepted_scheme_or_host(url: str) -> None:
    with pytest.raises(ValueError):
        validate_patent_source_url(url)


def test_policy_rejects_credentials_and_port() -> None:
    with pytest.raises(ValueError, match="credentials"):
        validate_patent_source_url("https://user:secret@patentscope.wipo.int/detail")
    with pytest.raises(ValueError, match="port"):
        validate_patent_source_url("https://patentscope.wipo.int:443/detail")
    with pytest.raises(ValueError, match="credentials"):
        validate_patent_source_url("https://user:secret@ops.epo.org/3.2/")
    with pytest.raises(ValueError, match="port"):
        validate_patent_source_url("https://ops.epo.org:443/3.2/")


def test_policy_is_strict_and_network_free() -> None:
    with pytest.raises(TypeError):
        validate_patent_source_url(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="surrounding whitespace"):
        validate_patent_source_url(" https://patentscope.wipo.int/detail ")
