"""Tests for the bounded patent comparison workflow request."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


def request(**overrides: object) -> PatentMultiPatentComparisonRequest:
    values: dict[str, object] = {
        "target_publication_number": "EP1000000B1",
        "comparison_publication_numbers": (
            "EP1000000B1",
            "EP1000000A1",
        ),
    }
    values.update(overrides)
    return PatentMultiPatentComparisonRequest.model_validate(values)


def test_request_uses_small_bounded_defaults() -> None:
    value = request()

    assert value.target_publication_number == "EP1000000B1"
    assert value.comparison_publication_numbers == (
        "EP1000000B1",
        "EP1000000A1",
    )
    assert value.claim_language == "EN"
    assert value.claim_number == 1
    assert value.maximum_claim_elements == 1
    assert value.maximum_mapping_calls == 2
    assert value.planned_maximum_mapping_calls == 2
    assert value.maximum_bytes == HttpHtmlReaderConfig().maximum_bytes


def test_request_normalizes_publication_numbers_and_language() -> None:
    value = request(
        target_publication_number=" ep 1000000 b1 ",
        comparison_publication_numbers=("ep1000000b1", " ep1000000a1 "),
        claim_language=" en ",
    )

    assert value.target_publication_number == "EP1000000B1"
    assert value.comparison_publication_numbers == (
        "EP1000000B1",
        "EP1000000A1",
    )
    assert value.claim_language == "EN"


def test_request_allows_target_to_be_one_comparison_publication() -> None:
    value = request()

    assert value.target_publication_number in value.comparison_publication_numbers


def test_request_accepts_four_publications_with_explicit_budget() -> None:
    value = request(
        comparison_publication_numbers=(
            "EP1000000A1",
            "EP2000000A1",
            "EP3000000A1",
            "EP4000000A1",
        ),
        maximum_claim_elements=3,
        maximum_mapping_calls=12,
    )

    assert value.planned_maximum_mapping_calls == 12


def test_request_rejects_budget_below_worst_case_pairs() -> None:
    with pytest.raises(
        ValidationError,
        match="planned element/evidence pairs exceed maximum_mapping_calls",
    ):
        request(maximum_claim_elements=2, maximum_mapping_calls=3)


@pytest.mark.parametrize(
    "publications",
    [
        ("EP1000000A1",),
        (
            "EP1000000A1",
            "EP2000000A1",
            "EP3000000A1",
            "EP4000000A1",
            "EP5000000A1",
        ),
    ],
)
def test_request_requires_two_to_four_comparison_publications(
    publications: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        request(comparison_publication_numbers=publications)


def test_request_rejects_duplicate_comparison_publications_after_normalization() -> (
    None
):
    with pytest.raises(
        ValidationError,
        match="comparison publication numbers must be unique",
    ):
        request(
            comparison_publication_numbers=(
                "EP1000000A1",
                " ep 1000000 a1 ",
            )
        )


@pytest.mark.parametrize(
    "publication_number",
    ("", "   ", "EP 1000000 ? A1", "EP_1000000_A1"),
)
def test_request_rejects_invalid_publication_identity(
    publication_number: str,
) -> None:
    with pytest.raises(ValidationError):
        request(target_publication_number=publication_number)


@pytest.mark.parametrize("language", ("", "E", "ENG", "한글", "E1"))
def test_request_rejects_invalid_claim_language(language: str) -> None:
    with pytest.raises(
        ValidationError,
        match="claim_language must be a two-letter ASCII language code",
    ):
        request(claim_language=language)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_number", 0),
        ("maximum_claim_elements", 0),
        ("maximum_claim_elements", 9),
        ("maximum_mapping_calls", 0),
        ("maximum_mapping_calls", 33),
    ],
)
def test_request_rejects_out_of_bounds_counts(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        request(**{field: value})


@pytest.mark.parametrize("maximum_bytes", (1_023, 10_000_001))
def test_request_reuses_shared_response_byte_bounds(maximum_bytes: int) -> None:
    with pytest.raises(ValidationError):
        request(maximum_bytes=maximum_bytes)


def test_request_is_strict_frozen_and_forbids_extra_fields() -> None:
    value = request()

    with pytest.raises(ValidationError):
        request(claim_number="1")
    with pytest.raises(ValidationError):
        PatentMultiPatentComparisonRequest.model_validate(
            {
                **value.model_dump(),
                "winner": "EP1000000A1",
            }
        )
    with pytest.raises(ValidationError):
        value.claim_number = 2
