"""Tests for exact patent comparison input acquisition."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.research.patent_multi_patent_comparison_acquisition import (
    PatentMultiPatentComparisonAcquisition,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


@dataclass
class FakeClaimsRetriever:
    calls: list[EpoOpsBibliographicRecord]
    publication_number: str = "EP1000000B1"
    publication_docdb: str = "EP.1000000.B1"

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        self.calls.append(record)
        return EpoOpsClaimsRecord(
            publication_number=self.publication_number,
            publication_docdb=self.publication_docdb,
            source_endpoint="https://ops.epo.org/target/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="DE",
                    claims=(
                        EpoOpsClaimText(position=1, text="1. Deutscher Anspruch."),
                    ),
                ),
                EpoOpsClaimSet(
                    language="EN",
                    claims=(
                        EpoOpsClaimText(position=1, text="1. English claim one."),
                        EpoOpsClaimText(position=2, text="2. English claim two."),
                    ),
                ),
            ),
        )


@dataclass
class FakeAbstractRetriever:
    calls: list[EpoOpsBibliographicRecord]
    drift_publication: str | None = None

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        self.calls.append(record)
        publication = self.drift_publication or record.publication_number
        docdb = (
            "EP.9999999.A1"
            if self.drift_publication is not None
            else record.publication_docdb
        )
        return EpoOpsAbstractRecord(
            publication_number=publication,
            publication_docdb=docdb,
            abstract_text=f"Exact abstract for {record.publication_number}.",
            abstract_language="en",
            source_endpoint=f"https://ops.epo.org/{record.publication_docdb}/abstract",
        )


def request(**overrides: object) -> PatentMultiPatentComparisonRequest:
    values: dict[str, object] = {
        "target_publication_number": "EP1000000B1",
        "comparison_publication_numbers": ("EP2000000A1", "EP3000000A1"),
        "claim_language": "EN",
        "claim_number": 2,
        "maximum_claim_elements": 1,
        "maximum_mapping_calls": 2,
        "maximum_bytes": 4096,
    }
    values.update(overrides)
    return PatentMultiPatentComparisonRequest.model_validate(values)


def test_acquisition_retrieves_exact_target_and_ordered_abstracts() -> None:
    claims = FakeClaimsRetriever(calls=[])
    abstracts = FakeAbstractRetriever(calls=[])

    result = PatentMultiPatentComparisonAcquisition(
        claims_retriever=claims,
        abstract_retriever=abstracts,
    ).acquire(request(), request_id="comparison-request-001")

    assert tuple(item.publication_number for item in claims.calls) == ("EP1000000B1",)
    assert tuple(item.publication_docdb for item in claims.calls) == ("EP.1000000.B1",)
    assert tuple(item.publication_number for item in abstracts.calls) == (
        "EP2000000A1",
        "EP3000000A1",
    )
    assert tuple(item.publication_docdb for item in abstracts.calls) == (
        "EP.2000000.A1",
        "EP.3000000.A1",
    )
    assert result.selected_target_claim.claim_number == 2
    assert result.selected_target_claim.provider_position == 2
    assert result.selected_target_claim.text == "English claim two."


def test_acquisition_preserves_full_multilingual_target_document() -> None:
    result = PatentMultiPatentComparisonAcquisition(
        claims_retriever=FakeClaimsRetriever(calls=[]),
        abstract_retriever=FakeAbstractRetriever(calls=[]),
    ).acquire(request(), request_id="comparison-request-001")

    assert tuple(
        item.language for item in result.target_claims_document.claim_sets
    ) == (
        "DE",
        "EN",
    )
    assert tuple(
        claim.claim_number
        for claim in result.target_claims_document.claim_sets[1].claims
    ) == (1, 2)


def test_acquisition_builds_one_exact_whole_abstract_evidence_per_publication() -> None:
    result = PatentMultiPatentComparisonAcquisition(
        claims_retriever=FakeClaimsRetriever(calls=[]),
        abstract_retriever=FakeAbstractRetriever(calls=[]),
    ).acquire(
        request(),
        request_id="comparison-request-001",
        task_id="comparison-task",
    )

    documents = result.evidence_result.document_set.documents
    evidence = result.evidence_result.evidence_set.ordered_evidence()
    assert len(documents) == len(evidence) == 2
    assert tuple(
        document.candidate.metadata["patent_publication_number"]
        for document in documents
    ) == ("EP2000000A1", "EP3000000A1")
    for document, item in zip(documents, evidence, strict=True):
        assert item.request_id == "comparison-request-001"
        assert item.task_id == "comparison-task"
        assert item.source_id == document.candidate.source_id
        assert item.document_id == document.document_id
        assert item.excerpt == document.content
        assert item.start_character == 0
        assert item.end_character == len(document.content)


def test_acquisition_preserves_request_byte_bound_and_explicit_axis() -> None:
    result = PatentMultiPatentComparisonAcquisition(
        claims_retriever=FakeClaimsRetriever(calls=[]),
        abstract_retriever=FakeAbstractRetriever(calls=[]),
    ).acquire(request(), request_id="comparison-request-001")

    collection = result.comparison_execution.collection
    assert collection.request.maximum_bytes == 4096
    assert collection.request.maximum_search_results == 2
    assert collection.request.maximum_sources == 2
    assert tuple(
        item.metadata.publication_number for item in collection.verified_records
    ) == ("EP2000000A1", "EP3000000A1")


def test_acquisition_rejects_target_claim_identity_drift_before_abstracts() -> None:
    claims = FakeClaimsRetriever(
        calls=[],
        publication_number="EP9999999B1",
        publication_docdb="EP.9999999.B1",
    )
    abstracts = FakeAbstractRetriever(calls=[])

    with pytest.raises(RuntimeError, match="target claims identity"):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=claims,
            abstract_retriever=abstracts,
        ).acquire(request(), request_id="comparison-request-001")

    assert abstracts.calls == []


def test_acquisition_rejects_abstract_identity_drift() -> None:
    with pytest.raises(RuntimeError, match="comparison abstract identity"):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=FakeClaimsRetriever(calls=[]),
            abstract_retriever=FakeAbstractRetriever(
                calls=[],
                drift_publication="EP9999999A1",
            ),
        ).acquire(request(), request_id="comparison-request-001")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"claim_language": "FR"}, "requested language"),
        ({"claim_number": 3}, "requested claim"),
    ],
)
def test_acquisition_rejects_missing_requested_claim_selection(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=FakeClaimsRetriever(calls=[]),
            abstract_retriever=FakeAbstractRetriever(calls=[]),
        ).acquire(request(**overrides), request_id="comparison-request-001")


@pytest.mark.parametrize("value", ("US1234567A1", "EP-NOT-DOCDB"))
def test_acquisition_rejects_non_epo_exact_identity(value: str) -> None:
    with pytest.raises(ValueError, match="requires an EP publication"):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=FakeClaimsRetriever(calls=[]),
            abstract_retriever=FakeAbstractRetriever(calls=[]),
        ).acquire(
            request(target_publication_number=value),
            request_id="comparison-request-001",
        )


@pytest.mark.parametrize(("field", "value"), (("request_id", " "), ("task_id", "")))
def test_acquisition_rejects_blank_runtime_identity(field: str, value: str) -> None:
    kwargs = {"request_id": "comparison-request-001", "task_id": "comparison-task"}
    kwargs[field] = value
    with pytest.raises(ValueError, match=field):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=FakeClaimsRetriever(calls=[]),
            abstract_retriever=FakeAbstractRetriever(calls=[]),
        ).acquire(request(), **kwargs)


def test_acquisition_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="request must be"):
        PatentMultiPatentComparisonAcquisition(
            claims_retriever=FakeClaimsRetriever(calls=[]),
            abstract_retriever=FakeAbstractRetriever(calls=[]),
        ).acquire(object(), request_id="comparison-request-001")  # type: ignore[arg-type]
