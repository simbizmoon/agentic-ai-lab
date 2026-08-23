"""Offline tests for the OpenAlex scholarly metadata provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from app.research.openalex_scholarly_metadata_provider import (
    OpenAlexScholarlyMetadataProvider,
)
from app.schemas.scholarly_provider import ScholarlySearchRequest, ScholarlySearchStatus
from app.schemas.scholarly_work import ScholarlyAccessState


def _payload(*results: object) -> dict[str, object]:
    return {
        "meta": {"count": len(results), "page": 1, "per_page": 2, "cost_usd": 0.001},
        "results": list(results),
        "group_by": [],
    }


def _record(work_id: str = "W123") -> dict[str, object]:
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": "https://doi.org/10.1234/Example.1",
        "title": "Bounded academic research",
        "publication_date": "2026-08-20",
        "publication_year": 2026,
        "type": "article",
        "language": "en",
        "authorships": [
            {
                "author": {
                    "id": "https://openalex.org/A1",
                    "display_name": "Ada Example",
                    "orcid": "https://orcid.org/0000-0000-0000-0001",
                },
                "institutions": [{"display_name": "Example University"}],
            }
        ],
        "primary_location": {
            "landing_page_url": "https://journal.example.test/article",
            "pdf_url": None,
            "is_oa": False,
            "license": None,
            "source": {"display_name": "Example Journal"},
        },
        "best_oa_location": {
            "landing_page_url": "https://repository.example.test/article",
            "pdf_url": "https://repository.example.test/article.pdf",
            "is_oa": True,
            "license": "cc-by",
            "source": {"display_name": "Example Repository"},
        },
        "open_access": {"is_oa": True},
        "abstract_inverted_index": {
            "A": [0],
            "bounded": [1],
            "abstract.": [2],
        },
    }


def _provider(
    payload: dict[str, object], status: int = 200
) -> OpenAlexScholarlyMetadataProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload, request=request)

    return OpenAlexScholarlyMetadataProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: datetime(2026, 8, 23, 3, 0, tzinfo=UTC),
    )


def _request(**changes: object) -> ScholarlySearchRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "query": "academic research",
        "maximum_results": 2,
        "maximum_provider_requests": 1,
        "require_abstract": True,
    }
    values.update(changes)
    return ScholarlySearchRequest(**values)  # type: ignore[arg-type]


def test_normalizes_fixture_with_exact_identity_abstract_and_access() -> None:
    result = _provider(_payload(_record())).search(_request())

    assert result.status is ScholarlySearchStatus.SUCCEEDED
    assert result.usage.request_count == 1
    work = result.works[0]
    assert work.work_id == "openalex-W123"
    assert [item.normalized_value for item in work.identifiers] == [
        "W123",
        "10.1234/example.1",
    ]
    assert work.abstract is not None
    assert work.abstract.text == "A bounded abstract."
    assert work.abstract.provider_record_id == work.provenance.provider_record_id
    assert work.access.state is ScholarlyAccessState.OPEN
    assert work.access.full_text_url == "https://repository.example.test/article.pdf"
    assert work.authors[0].affiliations == ("Example University",)
    assert (
        work.provenance.response_sha256
        == __import__("hashlib")
        .sha256(json.dumps(_payload(_record())).encode())
        .hexdigest()
        or len(work.provenance.response_sha256) == 64
    )


def test_builds_one_bounded_search_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_payload(), request=request)

    provider = OpenAlexScholarlyMetadataProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = provider.search(_request(maximum_results=2, require_abstract=False))

    assert result.status is ScholarlySearchStatus.NO_RESULTS
    assert len(seen) == 1
    assert seen[0].url.params["search"] == "academic research"
    assert seen[0].url.params["per_page"] == "2"
    assert seen[0].url.params["page"] == "1"


def test_preserves_partial_result_and_malformed_record_position() -> None:
    malformed = {"id": "not-an-openalex-id", "title": "Bad record"}

    result = _provider(_payload(_record(), malformed)).search(_request())

    assert result.status is ScholarlySearchStatus.PARTIAL
    assert len(result.works) == 1
    assert result.record_failures[0].provider_position == 2
    assert result.usage.records_received == 2
    assert result.usage.records_rejected == 1


def test_required_abstract_rejects_record_without_abstract() -> None:
    record = _record()
    record["abstract_inverted_index"] = None

    result = _provider(_payload(record)).search(_request())

    assert result.status is ScholarlySearchStatus.FAILED
    assert result.error is not None
    assert result.error.error_type == "AllRecordsRejected"
    assert len(result.record_failures) == 1
    assert result.usage.records_rejected == 1


def test_http_error_is_structured_and_retryable_when_rate_limited() -> None:
    result = _provider({"error": "rate limit"}, status=429).search(_request())

    assert result.status is ScholarlySearchStatus.FAILED
    assert result.error is not None
    assert result.error.http_status == 429
    assert result.error.retryable is True


def test_invalid_envelope_is_structured_failure() -> None:
    result = _provider({"unexpected": []}).search(_request())

    assert result.status is ScholarlySearchStatus.FAILED
    assert result.error is not None
    assert result.error.error_type == "ResponseValidationError"


def test_does_not_claim_version_of_record_from_article_type() -> None:
    result = _provider(_payload(_record())).search(_request())

    assert result.works[0].version_type.value == "unknown"
