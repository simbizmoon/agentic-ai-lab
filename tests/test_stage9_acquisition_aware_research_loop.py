"""Offline integration tests for Stage 9 acquisition-aware research loops."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import (
    BoundedAnswerCitationVerifier,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import ResearchCitationDecision
from app.research.stage9_acquisition_aware_research_loop import (
    Stage9AcquisitionAwareResearchLoop,
    Stage9AcquisitionAwareResearchLoopError,
)
from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
    Stage9DevelopmentAcquisitionRouter,
)
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationBudget,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
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
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)
from app.schemas.stage9_development_acquisition import (
    CHANNELS_BY_DOMAIN,
    Stage9AcquisitionStatus,
)
from app.schemas.stage9_development_baseline_run import STAGE9_DEVELOPMENT_CASE_IDS
from app.services.text_generation import TokenUsage

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


class ControlledChannelProvider:
    def __init__(self) -> None:
        self.requests = []

    def acquire(self, *, request, channel):
        self.requests.append((request, channel))
        text = f"Exact controlled evidence for {request.case_id} via {channel.value}."
        task_id = f"{request.request_id}-{channel.value}"
        source_id = f"source-{request.case_id}-{channel.value}"
        document_id = f"document-{request.case_id}-{channel.value}"
        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request.request_id,
            task_id=task_id,
            query_id=f"query-{request.case_id}-{channel.value}",
            title=f"Controlled {channel.value}",
            url=f"https://example.invalid/{request.case_id}/{channel.value}",
            source_type=ResearchSourceType.OTHER,
            rank=1,
            status=ResearchSourceCandidateStatus.READ,
        )
        document = ResearchSourceDocument(
            document_id=document_id,
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=text,
            word_count=len(text.split()),
            character_count=len(text),
            reader="controlled-stage9-acquisition",
        )
        evidence_set = ResearchEvidenceSet(
            request_id=request.request_id,
            document_set=ResearchSourceDocumentSet(
                request_id=request.request_id, documents=[document]
            ),
            evidence=[
                ResearchEvidence(
                    evidence_id=f"evidence-{request.case_id}-{channel.value}",
                    request_id=request.request_id,
                    task_id=task_id,
                    source_id=source_id,
                    document_id=document_id,
                    excerpt=text,
                    start_character=0,
                    end_character=len(text),
                    evidence_type=ResearchEvidenceType.OTHER,
                    stance=ResearchEvidenceStance.NEUTRAL,
                    relevance_score=1.0,
                    confidence_score=1.0,
                )
            ],
        )
        external = 0 if channel.value == "local_repository" else 1
        return Stage9ChannelAcquisitionResult(
            request_id=request.request_id,
            channel=channel,
            status=Stage9AcquisitionStatus.EVIDENCE_AVAILABLE,
            evidence_set=evidence_set,
            provider_requests=external,
            external_requests=external,
        )


class ControlledEvaluator:
    def evaluate(self, *, claim_text, evidence_excerpt):
        del claim_text, evidence_excerpt
        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
                entailment_score=1.0,
                rationale="Controlled local support.",
                issues=[],
            ),
            decision=ResearchCitationDecision.VERIFIED,
            response_id="controlled-evaluator-response",
            request_id="controlled-evaluator-request",
            usage=TokenUsage(
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                reasoning_tokens=0,
                total_tokens=0,
            ),
            elapsed_seconds=0.0,
        )


class PackedLoopFactory:
    def __init__(self) -> None:
        self.values = []

    def create(self, *, case_id, packing):
        self.values.append((case_id, packing))
        return PackedAbstainingLoop(packing)


class PackedAbstainingLoop:
    def __init__(self, packing) -> None:
        self.packing = packing

    def run(self, *, request):
        workflow_request = GroundedAnswerWorkflowRequest(
            question=request.goal,
            packing=self.packing,
            generation_budget=GroundedAnswerGenerationBudget(
                maximum_attempts=1,
                maximum_recorded_tokens=100,
                maximum_elapsed_seconds=10.0,
            ),
            citation_validation_budget=AnswerCitationValidationBudget(
                maximum_statements=10,
                maximum_pairs=10,
                maximum_attempts=10,
                maximum_recorded_tokens=100,
                maximum_elapsed_seconds=10.0,
            ),
        )
        retrievals = [
            item.retrieval.model_copy(update={"rank": item.packed_rank})
            for item in self.packing.included
        ]
        context = build_rag_context(retrievals)
        answer = GroundedAnswerResult(
            question=request.goal,
            answer="[S1] Controlled answer.",
            citations=context.citations,
            cited_ids=[item.citation_id for item in context.citations],
            response_id="controlled-answer-response",
            model_name="controlled-local-model",
            evidence_available=True,
        )
        validation = BoundedAnswerCitationVerifier(
            evaluator=ControlledEvaluator()
        ).verify(
            request=AnswerCitationValidationRequest(
                question=request.goal,
                answer=answer.answer,
                context=context,
                evidence_retrievals=retrievals,
                citation_required=True,
                budget=workflow_request.citation_validation_budget,
                response_id=answer.response_id,
                model_name=answer.model_name,
            )
        )
        workflow = BoundedGroundedAnswerWorkflowResult(
            request=workflow_request,
            status=GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE,
            generation_usage=GroundedAnswerGenerationUsage(
                attempts=1, recorded_tokens=5, elapsed_seconds=0.01
            ),
            generation_budget_exhausted=False,
            answer=answer,
            citation_validation=validation,
            abstention_detected=False,
        )
        observation = ResearchAgentObservation(
            observation_id="controlled-packed-observation",
            tool_name="bounded_grounded_answer",
            status=ResearchAgentObservationStatus.WORKFLOW_RESULT,
            workflow_result=workflow,
        )
        round_usage = ResearchAgentRoundUsage(
            tool_calls=1,
            provider_calls=1,
            recorded_tokens=5,
            elapsed_seconds=0.01,
            external_requests=1,
        )
        round_item = ResearchAgentLoopRound(
            round_number=1,
            plan_id="controlled-packed-plan",
            observations=[observation],
            decision=ResearchAgentLoopDecision.GOAL_ACHIEVED,
            rationale="Controlled packed evidence was used.",
            usage=round_usage,
        )
        return BoundedResearchAgentLoopResult(
            request=request,
            rounds=[round_item],
            final_decision=ResearchAgentLoopDecision.GOAL_ACHIEVED,
            termination_reason=ResearchAgentTerminationReason.GOAL_ACHIEVED,
            usage=ResearchAgentLoopUsage(
                rounds=1,
                tool_calls=1,
                provider_calls=1,
                recorded_tokens=5,
                elapsed_seconds=0.01,
                external_requests=1,
            ),
            trace_id="controlled-packed-trace",
        )


def _request(goal: str):
    return BoundedResearchAgentLoopRequest(
        goal=goal,
        constraints=["Preserve exact evidence."],
        allowed_tools=["bounded_grounded_answer"],
        budget=BoundedResearchAgentLoopBudget(
            maximum_rounds=2,
            maximum_tool_calls=2,
            maximum_provider_calls=4,
            maximum_recorded_tokens=30_000,
            maximum_elapsed_seconds=720.0,
            maximum_external_requests=6,
        ),
    )


@pytest.mark.parametrize("case_id", STAGE9_DEVELOPMENT_CASE_IDS)
def test_all_development_cases_acquire_pack_and_account_usage(case_id: str) -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == case_id
    )
    provider = ControlledChannelProvider()
    router = Stage9DevelopmentAcquisitionRouter(
        providers={channel: provider for channel in CHANNELS_BY_DOMAIN[case.domain]}
    )
    factory = PackedLoopFactory()
    result = Stage9AcquisitionAwareResearchLoop(
        experiment=experiment,
        acquisition_router=router,
        loop_factory=factory,
    ).run(request=_request(case.definition.evaluation_input.research_question))

    packing = factory.values[0][1]
    assert factory.values[0][0] == case_id
    assert packing.included
    assert result.rounds[0].observations[0].workflow_result.request.packing == packing
    acquisition_calls = len(provider.requests)
    external_acquisition_calls = sum(
        channel.value != "local_repository" for _, channel in provider.requests
    )
    assert result.usage.provider_calls == 1 + external_acquisition_calls
    assert result.usage.external_requests == 1 + external_acquisition_calls
    assert acquisition_calls in {1, 2}


def test_unknown_goal_is_rejected_before_acquisition() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    provider = ControlledChannelProvider()
    router = Stage9DevelopmentAcquisitionRouter(providers={})
    with pytest.raises(Stage9AcquisitionAwareResearchLoopError, match="development"):
        Stage9AcquisitionAwareResearchLoop(
            experiment=experiment,
            acquisition_router=router,
            loop_factory=PackedLoopFactory(),
        ).run(request=_request("Unknown holdout or user question"))
    assert provider.requests == []
