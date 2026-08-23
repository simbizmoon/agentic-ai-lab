"""Tests for the bounded scholarly evidence command request."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest
from app.schemas.scholarly_work import ScholarlyWorkType


def request(**overrides: object) -> ScholarlyEvidenceRequest:
    values: dict[str, object] = {"query": "retrieval augmented generation"}
    values.update(overrides)
    return ScholarlyEvidenceRequest.model_validate(values)


def test_request_uses_small_one_page_defaults() -> None:
    value = request()
    assert value.query == "retrieval augmented generation"
    assert value.maximum_results == 5
    assert value.maximum_provider_requests == 1
    assert value.planned_maximum_provider_requests == 1
    assert value.start_date is None
    assert value.end_date is None
    assert value.work_types == ()
    assert value.require_abstract is False


def test_request_normalizes_surrounding_query_whitespace() -> None:
    assert request(query="  exact query  ").query == "exact query"


@pytest.mark.parametrize("query", ("", " ", "\n\t"))
def test_request_rejects_blank_query(query: str) -> None:
    with pytest.raises(ValidationError, match="query must not be blank"):
        request(query=query)


@pytest.mark.parametrize("maximum_results", (0, 26))
def test_request_rejects_result_count_outside_cli_boundary(
    maximum_results: int,
) -> None:
    with pytest.raises(ValidationError):
        request(maximum_results=maximum_results)


@pytest.mark.parametrize("maximum_provider_requests", (0, 2, 10))
def test_request_allows_exactly_one_provider_request(
    maximum_provider_requests: int,
) -> None:
    with pytest.raises(ValidationError):
        request(maximum_provider_requests=maximum_provider_requests)


def test_request_accepts_dates_and_unique_work_types() -> None:
    value = request(
        start_date=date(2020, 1, 1),
        end_date=date(2026, 8, 23),
        work_types=(
            ScholarlyWorkType.JOURNAL_ARTICLE,
            ScholarlyWorkType.CONFERENCE_PAPER,
        ),
        require_abstract=True,
    )
    assert value.start_date == date(2020, 1, 1)
    assert value.end_date == date(2026, 8, 23)
    assert value.require_abstract is True


def test_request_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="start_date must not be after end_date"):
        request(start_date=date(2026, 1, 2), end_date=date(2026, 1, 1))


def test_request_rejects_duplicate_work_types() -> None:
    with pytest.raises(ValidationError, match="work_types must not contain duplicates"):
        request(
            work_types=(
                ScholarlyWorkType.JOURNAL_ARTICLE,
                ScholarlyWorkType.JOURNAL_ARTICLE,
            )
        )


def test_provider_request_preserves_every_user_boundary() -> None:
    value = request(
        query=" exact evidence ",
        maximum_results=7,
        start_date=date(2020, 1, 1),
        end_date=date(2026, 8, 23),
        work_types=(ScholarlyWorkType.PREPRINT,),
        require_abstract=True,
    )
    provider_request = value.to_provider_request(request_id=" request-001 ")
    assert provider_request.request_id == "request-001"
    assert provider_request.query == "exact evidence"
    assert provider_request.maximum_results == 7
    assert provider_request.maximum_provider_requests == 1
    assert provider_request.start_date == date(2020, 1, 1)
    assert provider_request.end_date == date(2026, 8, 23)
    assert provider_request.work_types == (ScholarlyWorkType.PREPRINT,)
    assert provider_request.require_abstract is True
    assert provider_request.metadata == {}


@pytest.mark.parametrize("request_id", ("", " ", "\n"))
def test_provider_request_rejects_blank_generated_id(request_id: str) -> None:
    with pytest.raises(ValueError, match="request_id must not be blank"):
        request().to_provider_request(request_id=request_id)


def test_provider_request_rejects_non_string_generated_id() -> None:
    with pytest.raises(TypeError, match="request_id must be a string"):
        request().to_provider_request(request_id=1)  # type: ignore[arg-type]


def test_request_is_strict_frozen_and_forbids_extra_fields() -> None:
    value = request()
    with pytest.raises(ValidationError):
        request(maximum_results="5")
    with pytest.raises(ValidationError):
        ScholarlyEvidenceRequest.model_validate(
            {**value.model_dump(), "paper_quality": "high"}
        )
    with pytest.raises(ValidationError):
        value.maximum_results = 10
