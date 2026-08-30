"""Offline tests for bounded Stage 9 acquisition channel routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
    Stage9DevelopmentAcquisitionRouter,
    Stage9DevelopmentAcquisitionRouterError,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
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


def _request(case_id: str):
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == case_id
    )
    return Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id=f"stage9-acquisition-{case_id}",
    )


def _evidence_set(request_id: str, label: str) -> ResearchEvidenceSet:
    content = f"Exact independently acquired evidence for {label}."
    candidate = ResearchSourceCandidate(
        source_id=f"source-{label}",
        request_id=request_id,
        task_id=f"task-{label}",
        query_id=f"query-{label}",
        title=f"Source {label}",
        url=f"https://example.test/{label}",
        source_type=ResearchSourceType.PRIMARY_RESEARCH,
        rank=1,
        status=ResearchSourceCandidateStatus.READ,
    )
    document = ResearchSourceDocument(
        document_id=f"document-{label}",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="controlled-local-reader",
    )
    document_set = ResearchSourceDocumentSet(
        request_id=request_id,
        documents=[document],
    )
    return ResearchEvidenceSet(
        request_id=request_id,
        document_set=document_set,
        evidence=[
            ResearchEvidence(
                evidence_id=f"evidence-{label}",
                request_id=request_id,
                task_id=f"task-{label}",
                source_id=candidate.source_id,
                document_id=document.document_id,
                excerpt=content,
                start_character=0,
                end_character=len(content),
                evidence_type=ResearchEvidenceType.FACT,
                stance=ResearchEvidenceStance.NEUTRAL,
                relevance_score=1.0,
                confidence_score=1.0,
            )
        ],
    )


class ControlledProvider:
    def __init__(self, label: str, *, with_evidence: bool = True) -> None:
        self.label = label
        self.with_evidence = with_evidence
        self.calls = 0

    def acquire(self, *, request, channel) -> Stage9ChannelAcquisitionResult:
        self.calls += 1
        evidence_set = (
            _evidence_set(request.request_id, self.label)
            if self.with_evidence
            else ResearchEvidenceSet(
                request_id=request.request_id,
                document_set=ResearchSourceDocumentSet(
                    request_id=request.request_id,
                    documents=[],
                ),
                evidence=[],
            )
        )
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=(
                Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
                if self.with_evidence
                else Stage9AcquisitionStatus.NO_EVIDENCE
            ),
            evidence_set=evidence_set,
            provider_requests=1,
            external_requests=1,
        )


def test_cross_source_routes_and_merges_two_exact_channels() -> None:
    scholarly = ControlledProvider("scholarly")
    local = ControlledProvider("local")
    request = _request("cross-01")
    result = Stage9DevelopmentAcquisitionRouter(
        providers={
            Stage9AcquisitionChannel.SCHOLARLY_PRIMARY: scholarly,
            Stage9AcquisitionChannel.LOCAL_REPOSITORY: local,
        }
    ).acquire(request)

    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert [item.source_id for item in result.evidence_set.evidence] == [
        "source-scholarly",
        "source-local",
    ]
    assert result.usage.provider_requests == 2
    assert result.usage.external_requests == 2
    assert result.usage.documents_read == 2
    assert result.usage.evidence_items == 2
    assert scholarly.calls == local.calls == 1


def test_no_evidence_is_explicit_and_not_a_failure() -> None:
    provider = ControlledProvider("academic", with_evidence=False)
    result = Stage9DevelopmentAcquisitionRouter(
        providers={Stage9AcquisitionChannel.SCHOLARLY_PRIMARY: provider}
    ).acquire(_request("academic-01"))

    assert result.status is Stage9AcquisitionStatus.NO_EVIDENCE
    assert result.evidence_set.evidence == []
    assert result.failure_code is None


def test_missing_declared_provider_fails_before_partial_claim() -> None:
    with pytest.raises(Stage9DevelopmentAcquisitionRouterError, match="no provider"):
        Stage9DevelopmentAcquisitionRouter(providers={}).acquire(_request("patent-01"))


def test_cross_channel_source_collision_is_rejected() -> None:
    first = ControlledProvider("same")
    second = ControlledProvider("same")
    with pytest.raises(Stage9DevelopmentAcquisitionRouterError, match="collide"):
        Stage9DevelopmentAcquisitionRouter(
            providers={
                Stage9AcquisitionChannel.SCHOLARLY_PRIMARY: first,
                Stage9AcquisitionChannel.LOCAL_REPOSITORY: second,
            }
        ).acquire(_request("cross-01"))


def test_router_does_not_accept_undeclared_channels() -> None:
    official = ControlledProvider("official")
    router = Stage9DevelopmentAcquisitionRouter(
        providers={
            Stage9AcquisitionChannel.OFFICIAL_WEB: official,
            Stage9AcquisitionChannel.EPO_PATENT: ControlledProvider("epo"),
        }
    )

    result = router.acquire(_request("tech-01"))

    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert official.calls == 1
