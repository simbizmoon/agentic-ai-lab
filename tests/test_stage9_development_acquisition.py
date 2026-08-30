"""Offline tests for leakage-safe Stage 9 development acquisition contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.schemas.stage9_development_acquisition import (
    CHANNELS_BY_DOMAIN,
    Stage9AcquisitionChannel,
    Stage9DevelopmentAcquisitionRequest,
    Stage9DevelopmentAcquisitionRequestBuilder,
)
from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)
DEVELOPMENT_IDS = ("tech-01", "academic-01", "patent-01", "cross-01")
HOLDOUT_IDS = (
    "tech-02",
    "academic-02",
    "patent-02",
    "patent-03",
    "cross-02",
    "cross-03",
)


def _experiment():
    return load_approved_baseline(MANIFEST, REVIEW)


def _case(case_id: str):
    return next(
        case
        for case in _experiment().plan.manifest.cases
        if case.definition.case_id == case_id
    )


def test_builder_exposes_questions_and_boundaries_but_not_golden_answers() -> None:
    builder = Stage9DevelopmentAcquisitionRequestBuilder()

    for case_id in DEVELOPMENT_IDS:
        case = _case(case_id)
        request = builder.build(case=case, request_id=f"acquisition-{case_id}")
        serialized = json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
        expected = case.definition.expected_outcome

        assert request.question == case.definition.evaluation_input.research_question
        assert request.channels == CHANNELS_BY_DOMAIN[case.domain]
        assert "expected_outcome" not in serialized
        assert "expected_sources" not in serialized
        assert "expected_evidence" not in serialized
        for evidence in expected.expected_evidence:
            assert evidence.expected_text not in serialized
            assert evidence.location_hint not in serialized
        for source in expected.expected_sources:
            assert source.canonical_url not in serialized


def test_domain_routes_are_minimal_and_explicit() -> None:
    assert CHANNELS_BY_DOMAIN == {
        Stage9EvaluationDomain.GENERAL_TECHNICAL: (
            Stage9AcquisitionChannel.OFFICIAL_WEB,
        ),
        Stage9EvaluationDomain.ACADEMIC: (Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,),
        Stage9EvaluationDomain.PATENT: (Stage9AcquisitionChannel.EPO_PATENT,),
        Stage9EvaluationDomain.CROSS_SOURCE: (
            Stage9AcquisitionChannel.SCHOLARLY_PRIMARY,
            Stage9AcquisitionChannel.LOCAL_REPOSITORY,
        ),
    }


@pytest.mark.parametrize("case_id", HOLDOUT_IDS)
def test_builder_rejects_every_blind_holdout_case(case_id: str) -> None:
    with pytest.raises(ValueError, match="holdout"):
        Stage9DevelopmentAcquisitionRequestBuilder().build(
            case=_case(case_id),
            request_id=f"forbidden-{case_id}",
        )


def test_extra_golden_fields_are_forbidden() -> None:
    request = Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=_case("tech-01"),
        request_id="acquisition-tech-01",
    )
    values = request.model_dump(mode="python")
    values["expected_evidence"] = "forbidden golden answer"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        Stage9DevelopmentAcquisitionRequest.model_validate(values)


def test_wrong_domain_channel_pair_is_rejected() -> None:
    request = Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=_case("academic-01"),
        request_id="acquisition-academic-01",
    )
    values = request.model_dump(mode="python")
    values["channels"] = (Stage9AcquisitionChannel.EPO_PATENT,)

    with pytest.raises(ValidationError, match="channels"):
        Stage9DevelopmentAcquisitionRequest.model_validate(values)
