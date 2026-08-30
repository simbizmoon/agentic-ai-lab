"""Offline tests for the Stage 9 development runtime composition root."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
)
from app.research.stage9_development_runtime_factory import (
    Stage9DevelopmentRuntime,
    create_stage9_development_runtime,
)
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_source_document import ResearchSourceDocumentSet
from app.schemas.stage9_development_acquisition import (
    CHANNELS_BY_DOMAIN,
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
)
from app.schemas.stage9_development_baseline_run import STAGE9_DEVELOPMENT_CASE_IDS

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


class ControlledEmptyProvider:
    def __init__(self, expected_channel: Stage9AcquisitionChannel) -> None:
        self.expected_channel = expected_channel
        self.calls = []

    def acquire(self, *, request, channel):
        assert channel is self.expected_channel
        self.calls.append(request)
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.NO_EVIDENCE,
            evidence_set=ResearchEvidenceSet(
                request_id=request.request_id,
                document_set=ResearchSourceDocumentSet(
                    request_id=request.request_id,
                    documents=[],
                ),
                evidence=[],
            ),
            provider_requests=0,
            external_requests=0,
        )


class ControlledPackedLoopFactory:
    def create(self, *, case_id, packing):
        raise AssertionError(
            f"paid loop construction was not expected: {case_id}, {packing}"
        )


def _components():
    return {
        channel: ControlledEmptyProvider(channel)
        for channel in Stage9AcquisitionChannel
    }


def _runtime(components):
    return create_stage9_development_runtime(
        experiment=load_approved_baseline(MANIFEST, REVIEW),
        official_web=components[Stage9AcquisitionChannel.OFFICIAL_WEB],
        scholarly_primary=components[Stage9AcquisitionChannel.SCHOLARLY_PRIMARY],
        epo_patent=components[Stage9AcquisitionChannel.EPO_PATENT],
        local_repository=components[Stage9AcquisitionChannel.LOCAL_REPOSITORY],
        packed_loop_factory=ControlledPackedLoopFactory(),
    )


def test_composes_all_locked_channels_without_external_execution() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    components = _components()
    runtime = _runtime(components)

    assert isinstance(runtime, Stage9DevelopmentRuntime)
    for case_id in STAGE9_DEVELOPMENT_CASE_IDS:
        case = next(
            item
            for item in experiment.plan.manifest.cases
            if item.definition.case_id == case_id
        )
        request = Stage9DevelopmentAcquisitionRequestBuilder().build(
            case=case,
            request_id=f"runtime-factory-{case_id}",
        )
        result = runtime.acquisition_router.acquire(request)
        assert result.status is Stage9AcquisitionStatus.NO_EVIDENCE
        assert result.usage.provider_requests == 0
        assert result.usage.external_requests == 0

    for case in experiment.plan.manifest.cases:
        case_id = case.definition.case_id
        if case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            continue
        for channel in CHANNELS_BY_DOMAIN[case.domain]:
            assert any(
                request.case_id == case_id for request in components[channel].calls
            )


def test_rejects_component_without_acquire() -> None:
    components = _components()
    components[Stage9AcquisitionChannel.OFFICIAL_WEB] = object()
    with pytest.raises(TypeError, match="official_web"):
        _runtime(components)
