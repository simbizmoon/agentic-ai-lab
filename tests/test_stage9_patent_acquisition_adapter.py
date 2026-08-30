"""Offline tests for exact, leakage-safe Stage 9 EPO claim acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_patent_acquisition_adapter import (
    Stage9PatentAcquisitionAdapter,
    Stage9PatentAcquisitionError,
)
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)
CLAIM_TEXT = "A bounded fixture apparatus comprising independently observed parts."


def _request():
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == "patent-01"
    )
    return Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id="stage9-patent-patent-01",
    )


class FixtureClaimsRetriever:
    def __init__(self, *, publication_number: str = "EP1000000B1") -> None:
        self.publication_number = publication_number
        self.records = []

    def retrieve(self, record):
        self.records.append(record)
        docdb = (
            "EP.1000000.B1"
            if self.publication_number == "EP1000000B1"
            else "EP.9999999.B1"
        )
        return EpoOpsClaimsRecord(
            publication_number=self.publication_number,
            publication_docdb=docdb,
            source_endpoint=f"https://ops.epo.org/example/{docdb}/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(EpoOpsClaimText(position=1, text=f"1. {CLAIM_TEXT}"),),
                ),
            ),
        )


def test_extracts_identity_only_from_question_and_preserves_exact_claim() -> None:
    retriever = FixtureClaimsRetriever()
    result = Stage9PatentAcquisitionAdapter(claims_retriever=retriever).acquire(
        request=_request(),
        channel=Stage9AcquisitionChannel.EPO_PATENT,
    )

    assert retriever.records[0].publication_number == "EP1000000B1"
    assert retriever.records[0].publication_docdb == "EP.1000000.B1"
    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert result.provider_requests == result.external_requests == 1
    evidence = result.evidence_set.evidence[0]
    document = result.evidence_set.document_set.documents[0]
    assert evidence.excerpt == CLAIM_TEXT == document.content
    assert (evidence.start_character, evidence.end_character) == (0, len(CLAIM_TEXT))
    assert evidence.metadata["claim_construction_performed"] == "false"
    assert document.candidate.metadata["golden_evidence_supplied"] == "false"


def test_rejects_provider_identity_mismatch() -> None:
    adapter = Stage9PatentAcquisitionAdapter(
        claims_retriever=FixtureClaimsRetriever(publication_number="EP9999999B1")
    )
    with pytest.raises(Stage9PatentAcquisitionError, match="identity"):
        adapter.acquire(
            request=_request(),
            channel=Stage9AcquisitionChannel.EPO_PATENT,
        )


def test_missing_requested_claim_is_explicit_no_evidence() -> None:
    request = _request().model_copy(
        update={
            "question": "What exact technical features are present in claim 2 of EP1000000B1?"
        }
    )
    result = Stage9PatentAcquisitionAdapter(
        claims_retriever=FixtureClaimsRetriever()
    ).acquire(request=request, channel=Stage9AcquisitionChannel.EPO_PATENT)
    assert result.status is Stage9AcquisitionStatus.NO_EVIDENCE
    assert result.evidence_set.evidence == []


def test_requires_one_explicit_publication_and_claim_number() -> None:
    request = _request().model_copy(update={"question": "Summarize this patent."})
    with pytest.raises(Stage9PatentAcquisitionError, match="exactly one"):
        Stage9PatentAcquisitionAdapter(
            claims_retriever=FixtureClaimsRetriever()
        ).acquire(request=request, channel=Stage9AcquisitionChannel.EPO_PATENT)


def test_rejects_wrong_channel() -> None:
    with pytest.raises(ValueError, match="epo_patent"):
        Stage9PatentAcquisitionAdapter(
            claims_retriever=FixtureClaimsRetriever()
        ).acquire(
            request=_request(),
            channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
        )
