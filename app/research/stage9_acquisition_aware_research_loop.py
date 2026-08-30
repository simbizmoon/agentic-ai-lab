"""Integrate Stage 9 acquisition, RAG packing, and the bounded research loop."""

from __future__ import annotations

from typing import Protocol

from app.research.deterministic_rag_context_packer import (
    ConservativeUtf8TokenEstimator,
    DeterministicRagContextPacker,
)
from app.research.stage9_development_acquisition_router import (
    Stage9DevelopmentAcquisitionRouter,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentRoundUsage,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
)
from app.schemas.retrieval_result import RetrievalResult
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
    Stage9DevelopmentAcquisitionResult,
)
from app.schemas.stage9_development_baseline_run import STAGE9_DEVELOPMENT_CASE_IDS
from app.schemas.stage9_evaluation_manifest import Stage9DatasetPartition

_MAXIMUM_PACKED_ITEMS = 8
_MAXIMUM_CONTEXT_BYTES = 6_000
_MAXIMUM_ESTIMATED_TOKENS = 6_000


class Stage9PackedResearchLoopFactory(Protocol):
    """Create a case loop whose grounded tool uses the supplied exact packing."""

    def create(
        self,
        *,
        case_id: str,
        packing: RagContextPackingResult,
    ) -> Stage9ResearchLoopProtocol: ...


class Stage9ResearchLoopProtocol(Protocol):
    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult: ...


class Stage9AcquisitionAwareResearchLoopError(RuntimeError):
    """Acquisition could not be joined to the loop without losing auditability."""

    def __init__(self, message: str, *, failure_code: str | None = None) -> None:
        super().__init__(message)
        self.failure_code = failure_code


class Stage9AcquisitionContextBuilder:
    """Convert exact acquired evidence into whole, bounded RAG chunks."""

    def __init__(self) -> None:
        estimator = ConservativeUtf8TokenEstimator()
        self._packer = DeterministicRagContextPacker(token_estimator=estimator)
        self._estimator_id = estimator.estimator_id

    def build(
        self, acquisition: Stage9DevelopmentAcquisitionResult
    ) -> RagContextPackingResult:
        if not isinstance(acquisition, Stage9DevelopmentAcquisitionResult):
            raise TypeError("acquisition must be a Stage 9 acquisition result")
        document_by_id = {
            item.document_id: item
            for item in acquisition.evidence_set.document_set.documents
        }
        candidates = []
        for rank, evidence in enumerate(acquisition.evidence_set.evidence, start=1):
            document = document_by_id[evidence.document_id]
            candidates.append(
                RetrievalResult(
                    chunk=DocumentChunk(
                        document_id=evidence.document_id,
                        chunk_id=evidence.evidence_id,
                        ordinal=rank - 1,
                        text=evidence.excerpt,
                        start_char=evidence.start_character,
                        end_char=evidence.end_character,
                        metadata={
                            "source_id": evidence.source_id,
                            "task_id": evidence.task_id,
                            "source_url": document.candidate.url,
                            "stage9_acquisition_channel": (
                                document.candidate.metadata.get(
                                    "acquisition_channel", "preserved_by_adapter"
                                )
                            ),
                        },
                    ),
                    score=evidence.relevance_score,
                    rank=rank,
                )
            )
        return self._packer.pack(
            request=RagContextPackingRequest(
                candidates=candidates,
                budget=RagContextPackingBudget(
                    maximum_items=_MAXIMUM_PACKED_ITEMS,
                    maximum_utf8_bytes=_MAXIMUM_CONTEXT_BYTES,
                    maximum_estimated_tokens=_MAXIMUM_ESTIMATED_TOKENS,
                    token_estimator_id=self._estimator_id,
                ),
            )
        )


class Stage9AcquisitionAwareResearchLoop:
    """Acquire before planning and retain both evidence and usage in the result."""

    def __init__(
        self,
        *,
        experiment: Stage9LockedBaselineExperiment,
        acquisition_router: Stage9DevelopmentAcquisitionRouter,
        loop_factory: Stage9PackedResearchLoopFactory,
        context_builder: Stage9AcquisitionContextBuilder | None = None,
    ) -> None:
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")
        if not isinstance(acquisition_router, Stage9DevelopmentAcquisitionRouter):
            raise TypeError("acquisition_router must be a Stage 9 router")
        self._experiment = experiment
        self._router = acquisition_router
        self._loop_factory = loop_factory
        self._context_builder = context_builder or Stage9AcquisitionContextBuilder()

    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult:
        if not isinstance(request, BoundedResearchAgentLoopRequest):
            raise TypeError("request must be a bounded research loop request")
        case = self._case_for_goal(request.goal)
        case_id = case.definition.case_id
        acquisition_request = Stage9DevelopmentAcquisitionRequestBuilder().build(
            case=case,
            request_id=f"stage9-development-acquisition-{case_id}",
        )
        acquisition = self._router.acquire(acquisition_request)
        if acquisition.status is Stage9AcquisitionStatus.FAILED:
            raise Stage9AcquisitionAwareResearchLoopError(
                "development acquisition failed safely",
                failure_code=acquisition.failure_code,
            )
        packing = self._context_builder.build(acquisition)
        delegated_request = self._reserve_acquisition_usage(request, acquisition)
        delegate = self._loop_factory.create(case_id=case_id, packing=packing)
        delegated = delegate.run(request=delegated_request)
        if not isinstance(delegated, BoundedResearchAgentLoopResult):
            raise Stage9AcquisitionAwareResearchLoopError(
                "packed research loop returned an invalid result"
            )
        if not self._packing_was_observed(delegated, packing):
            raise Stage9AcquisitionAwareResearchLoopError(
                "research loop did not preserve the acquired packing"
            )
        return self._merge_usage(
            original_request=request,
            delegated=delegated,
            acquisition=acquisition,
        )

    def _case_for_goal(self, goal: str):
        matches = [
            case
            for case in self._experiment.plan.manifest.cases
            if case.partition is Stage9DatasetPartition.DEVELOPMENT
            and case.definition.case_id in STAGE9_DEVELOPMENT_CASE_IDS
            and case.definition.evaluation_input.research_question == goal
        ]
        if len(matches) != 1:
            raise Stage9AcquisitionAwareResearchLoopError(
                "loop goal did not identify exactly one development case"
            )
        return matches[0]

    @staticmethod
    def _reserve_acquisition_usage(
        request: BoundedResearchAgentLoopRequest,
        acquisition: Stage9DevelopmentAcquisitionResult,
    ) -> BoundedResearchAgentLoopRequest:
        budget = request.budget
        provider_remaining = (
            budget.maximum_provider_calls - acquisition.usage.provider_requests
        )
        external_remaining = (
            budget.maximum_external_requests - acquisition.usage.external_requests
        )
        if provider_remaining < 0 or external_remaining < 0:
            raise Stage9AcquisitionAwareResearchLoopError(
                "acquisition exhausted the case request budget"
            )
        return request.model_copy(
            update={
                "budget": budget.model_copy(
                    update={
                        "maximum_provider_calls": provider_remaining,
                        "maximum_external_requests": external_remaining,
                    }
                )
            }
        )

    @staticmethod
    def _packing_was_observed(
        result: BoundedResearchAgentLoopResult,
        packing: RagContextPackingResult,
    ) -> bool:
        return any(
            observation.workflow_result is not None
            and observation.workflow_result.request.packing == packing
            for round_item in result.rounds
            for observation in round_item.observations
        )

    @staticmethod
    def _merge_usage(
        *,
        original_request: BoundedResearchAgentLoopRequest,
        delegated: BoundedResearchAgentLoopResult,
        acquisition: Stage9DevelopmentAcquisitionResult,
    ) -> BoundedResearchAgentLoopResult:
        first = delegated.rounds[0]
        merged_first_usage = ResearchAgentRoundUsage(
            tool_calls=first.usage.tool_calls,
            provider_calls=(
                first.usage.provider_calls + acquisition.usage.provider_requests
            ),
            recorded_tokens=first.usage.recorded_tokens,
            elapsed_seconds=first.usage.elapsed_seconds,
            external_requests=(
                first.usage.external_requests + acquisition.usage.external_requests
            ),
        )
        rounds = [
            ResearchAgentLoopRound(
                round_number=first.round_number,
                plan_id=first.plan_id,
                observations=first.observations,
                decision=first.decision,
                rationale=first.rationale,
                usage=merged_first_usage,
            ),
            *delegated.rounds[1:],
        ]
        usage = ResearchAgentLoopUsage(
            rounds=len(rounds),
            tool_calls=sum(item.usage.tool_calls for item in rounds),
            provider_calls=sum(item.usage.provider_calls for item in rounds),
            recorded_tokens=sum(item.usage.recorded_tokens for item in rounds),
            elapsed_seconds=sum(item.usage.elapsed_seconds for item in rounds),
            external_requests=sum(item.usage.external_requests for item in rounds),
        )
        try:
            return BoundedResearchAgentLoopResult(
                request=original_request,
                rounds=rounds,
                final_decision=delegated.final_decision,
                termination_reason=delegated.termination_reason,
                usage=usage,
                trace_id=delegated.trace_id,
            )
        except ValueError as error:
            raise Stage9AcquisitionAwareResearchLoopError(
                "combined acquisition and loop usage violated the case budget"
            ) from error
