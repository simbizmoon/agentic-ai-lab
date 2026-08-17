"""Tests for the bounded patent research request contract."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.patent_research_request import PatentResearchRequest


def request(**overrides: object) -> PatentResearchRequest:
    values: dict[str, object] = {
        "question": "Which patent publications are technically relevant?",
        "objective": "Identify potentially relevant technical disclosures.",
    }
    values.update(overrides)
    return PatentResearchRequest.model_validate(values)


def test_request_uses_bounded_defaults() -> None:
    value = request()

    assert value.maximum_search_results == 8
    assert value.maximum_sources == 4
    assert value.maximum_bytes == HttpHtmlReaderConfig().maximum_bytes
    assert value.prior_art_cutoff_date is None


def test_request_accepts_real_optional_cutoff_date() -> None:
    cutoff = date(2024, 1, 31)

    assert request(prior_art_cutoff_date=cutoff).prior_art_cutoff_date == cutoff


def test_request_is_strict_and_frozen() -> None:
    value = request()

    with pytest.raises(ValidationError):
        request(prior_art_cutoff_date="2024-01-31")
    with pytest.raises(ValidationError):
        request(maximum_sources="4")
    with pytest.raises(ValidationError):
        value.maximum_sources = 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("maximum_search_results", 0),
        ("maximum_search_results", 9),
        ("maximum_sources", 0),
        ("maximum_sources", 5),
    ],
)
def test_request_rejects_out_of_bounds_counts(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        request(**{field: value})


def test_request_rejects_more_sources_than_results() -> None:
    with pytest.raises(
        ValidationError,
        match="maximum_sources must not exceed maximum_search_results",
    ):
        request(maximum_search_results=2, maximum_sources=3)


@pytest.mark.parametrize("maximum_bytes", [1_023, 10_000_001])
def test_request_reuses_web_reader_byte_bounds(maximum_bytes: int) -> None:
    with pytest.raises(ValidationError):
        request(maximum_bytes=maximum_bytes)


@pytest.mark.parametrize("field", ["question", "objective"])
def test_request_rejects_blank_required_text(field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must not be blank"):
        request(**{field: "  "})
