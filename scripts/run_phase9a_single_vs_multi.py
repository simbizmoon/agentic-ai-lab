"""Run one actual Phase 9A Single-vs-Multi local runtime pair."""

from __future__ import annotations

import json
import time

from app.evals.multi_agent_workflow_evaluator import MultiAgentWorkflowEvaluator
from app.research.claim_analyst_agent import ClaimAnalystAgent
from app.research.evidence_analyst_agent import EvidenceAnalystAgent
from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.local_quality_review_executor import (
    InMemoryResearchReportRegistry,
    LocalResearchQualityReviewExecutor,
)
from app.research.local_runtime import (
    LocalDocumentSourceQualityEvaluator,
    WholeDocumentEvidenceExtractor,
)
from app.research.multi_agent_pipeline_executors import (
    MultiAgentResearchRuntimeContext,
    PipelineResearchClaimExecutor,
    PipelineResearchEvidenceExecutor,
    PipelineResearchSearchExecutor,
    PipelineResearchSourceReaderExecutor,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchOrchestrator,
)
from app.research.multi_agent_synthesis_runtime import (
    RegisteredWorkspaceSynthesisExecutor,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_compatibility import (
    PipelineQueryPlannerAdapter,
    PipelineTaskDecomposerAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.quality_reviewer_agent import QualityReviewerAgent
from app.research.research_execution_benchmark import (
    ResearchExecutionBenchmarkNormalizer,
    research_workspace_artifacts_equivalent,
)
from app.research.research_request_validator import ResearchRequestValidator
from app.research.review_revision_loop import ReviewRevisionLoop
from app.research.search_specialist_agent import SearchSpecialistAgent
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)
from app.research.source_reader_specialist_agent import (
    SourceReaderSpecialistAgent,
)
from app.research.synthesis_specialist_agent import SynthesisSpecialistAgent
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import InMemoryResearchSourceRecord
from app.schemas.research_agent import ResearchAgentIdentity, ResearchAgentRole
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_request import ResearchRequest, ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_document import ResearchSourceContentType
from app.schemas.research_task import ResearchTask, ResearchTaskGraph
from app.schemas.research_workspace import ResearchWorkspace
from app.services.ollama_client import OllamaClient

REQUEST_ID = "phase9a-research-001"
WORKSPACE_ID = "phase9a-workspace-001"


def main() -> int:
    request = ResearchRequest(
        request_id=REQUEST_ID,
        question=(
            "How does a bounded multi-agent research workflow "
            "hand off artifacts?"
        ),
        objective=(
            "Demonstrate traceable specialist handoffs and "
            "local advisory review."
        ),
        include_topics=["bounded multi-agent artifact handoff"],
        preferred_source_types=[ResearchSourceType.ACADEMIC],
        maximum_sources=1,
    )

    source_record = InMemoryResearchSourceRecord(
        source_id="phase9a-source-001",
        title="Bounded Multi-Agent Artifact Handoff",
        url="https://example.com/phase9a-artifact-handoff",
        source_type=ResearchSourceType.ACADEMIC,
        snippet=(
            "Specialist agents exchange traceable artifacts through "
            "a shared workspace and explicit references."
        ),
        keywords=[
            "bounded",
            "multi-agent",
            "artifact",
            "handoff",
            "workspace",
            "reference",
        ],
    )
    document_record = InMemoryResearchDocumentRecord(
        source_id=source_record.source_id,
        url=source_record.url,
        content_type=ResearchSourceContentType.TEXT,
        content=(
            "A bounded multi-agent research workflow can pass traceable "
            "artifacts from search to reading, evidence extraction, claim "
            "construction, synthesis, and advisory quality review by using "
            "a shared workspace and explicit artifact references."
        ),
        language="en",
    )

    single_pipeline = _single_pipeline(
        source_record=source_record,
        document_record=document_record,
    )
    single_started = time.perf_counter()
    single_result = single_pipeline.run(
        request,
        workspace_id=WORKSPACE_ID,
    )
    single_elapsed = max(
        0.0,
        time.perf_counter() - single_started,
    )

    multi_runtime = _multi_runtime(
        request=request,
        source_record=source_record,
        document_record=document_record,
    )
    multi_started = time.perf_counter()
    multi_result = multi_runtime["orchestrator"].run(
        search_assignment=_assignment(
            "phase9a-assignment-search",
            "phase9a-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
        ),
        source_reader_template=_assignment(
            "phase9a-assignment-reader",
            "phase9a-agent-reader",
            ResearchAgentRole.SOURCE_READER,
        ),
        evidence_template=_assignment(
            "phase9a-assignment-evidence",
            "phase9a-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
        ),
        claim_template=_assignment(
            "phase9a-assignment-claim",
            "phase9a-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
        ),
        synthesis_template=_assignment(
            "phase9a-assignment-synthesis",
            "phase9a-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
        ),
        review_template=_assignment(
            "phase9a-assignment-review",
            "phase9a-agent-quality",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
    )
    multi_elapsed = max(
        0.0,
        time.perf_counter() - multi_started,
    )

    context = multi_runtime["context"]
    workflow_evaluation = MultiAgentWorkflowEvaluator().evaluate(
        multi_result
    )
    comparable_artifacts = research_workspace_artifacts_equivalent(
        single_result.workspace,
        context.workspace,
    )

    comparison = ResearchExecutionBenchmarkNormalizer().compare(
        single_result=single_result,
        single_wall_elapsed_seconds=single_elapsed,
        multi_result=multi_result,
        multi_wall_elapsed_seconds=multi_elapsed,
        workflow_evaluation=workflow_evaluation,
        comparable_upstream_artifacts=comparable_artifacts,
        evaluator_conditions_equal=False,
    )

    payload = comparison.model_dump(mode="json")
    payload["single_workspace_stage"] = (
        single_result.workspace.stage.name
    )
    payload["multi_workspace_stage"] = context.workspace.stage.name
    payload["single_quality_passed"] = single_result.quality.passed
    payload["multi_report_reference_resolved"] = multi_runtime[
        "registry"
    ].resolve("phase9a-report-output").report_id

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _single_pipeline(
    *,
    source_record: InMemoryResearchSourceRecord,
    document_record: InMemoryResearchDocumentRecord,
) -> SingleResearchAgentPipeline:
    searcher = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(records=[source_record]),
        maximum_candidates=1,
    )
    reader = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(records=[document_record])
    )

    return SingleResearchAgentPipeline(
        request_validator=ResearchRequestValidator(),
        task_decomposer=PipelineTaskDecomposerAdapter(),
        query_planner=PipelineQueryPlannerAdapter(),
        source_searcher=searcher,
        source_reader=reader,
        evidence_extractor=PipelineEvidenceExtractorAdapter(
            WholeDocumentEvidenceExtractor()
        ),
        claim_builder=DeterministicPipelineClaimBuilder(),
        source_quality_evaluator=LocalDocumentSourceQualityEvaluator(),
        collect_run_metrics=True,
    )


def _multi_runtime(
    *,
    request: ResearchRequest,
    source_record: InMemoryResearchSourceRecord,
    document_record: InMemoryResearchDocumentRecord,
) -> dict[str, object]:
    task = ResearchTask(
        task_id="phase9a-task-001",
        request_id=request.request_id,
        title="Inspect bounded multi-agent artifact handoff",
        question=request.question,
        objective=request.objective,
        completion_criteria=[
            "Produce one traceable evidence-backed claim.",
        ],
        expected_output="One traceable claim.",
    )
    task_graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[task],
    )
    query_set = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=task_graph,
        queries=[
            ResearchSearchQuery(
                query_id="phase9a-query-001",
                request_id=request.request_id,
                task_id=task.task_id,
                query_text="bounded multi-agent artifact handoff",
                preferred_source_types=[
                    ResearchSourceType.ACADEMIC,
                ],
                maximum_results=1,
            )
        ],
    )
    context = MultiAgentResearchRuntimeContext(
        workspace=ResearchWorkspace(
            workspace_id=WORKSPACE_ID,
            request=request,
            task_graph=task_graph,
            query_set=query_set,
        )
    )

    searcher = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(records=[source_record]),
        maximum_candidates=1,
    )
    reader = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(records=[document_record])
    )
    extractor = PipelineEvidenceExtractorAdapter(
        WholeDocumentEvidenceExtractor()
    )
    builder = DeterministicPipelineClaimBuilder()

    search_agent = SearchSpecialistAgent(
        profile=_profile(
            "phase9a-agent-search",
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentCapability.SEARCH_SOURCES,
        ),
        executor=PipelineResearchSearchExecutor(
            context=context,
            searcher=searcher,
        ),
        output_reference_id_factory=lambda: "phase9a-source-set",
    )
    reader_agent = SourceReaderSpecialistAgent(
        profile=_profile(
            "phase9a-agent-reader",
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentCapability.READ_SOURCES,
        ),
        executor=PipelineResearchSourceReaderExecutor(
            context=context,
            reader=reader,
        ),
        output_reference_id_factory=lambda: "phase9a-document-set",
    )
    evidence_agent = EvidenceAnalystAgent(
        profile=_profile(
            "phase9a-agent-evidence",
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ),
        executor=PipelineResearchEvidenceExecutor(
            context=context,
            extractor=extractor,
        ),
        output_reference_id_factory=lambda: "phase9a-evidence-set",
    )
    claim_agent = ClaimAnalystAgent(
        profile=_profile(
            "phase9a-agent-claim",
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=PipelineResearchClaimExecutor(
            context=context,
            builder=builder,
        ),
        output_reference_id_factory=lambda: "phase9a-claim-set",
    )

    registry = InMemoryResearchReportRegistry()
    synthesis_executor = RegisteredWorkspaceSynthesisExecutor(
        context=context,
        report_registry=registry,
        report_reference_id_factory=lambda: "phase9a-report-output",
        report_id_factory=lambda: "phase9a-report-001",
    )
    synthesis_agent = SynthesisSpecialistAgent(
        profile=_profile(
            "phase9a-agent-synthesis",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ),
        executor=synthesis_executor,
        output_reference_id_factory=(
            synthesis_executor.take_output_reference_id
        ),
    )
    quality_agent = QualityReviewerAgent(
        profile=_quality_profile(),
        executor=LocalResearchQualityReviewExecutor(
            client=OllamaClient(timeout_seconds=120.0),
            model="qwen3.5:4b",
            report_registry=registry,
        ),
        output_reference_id_factory=lambda: "phase9a-quality-output",
    )
    loop = ReviewRevisionLoop(
        synthesis_agent=synthesis_agent,
        quality_reviewer=quality_agent,
        maximum_revision_rounds=0,
    )

    return {
        "context": context,
        "registry": registry,
        "orchestrator": MultiAgentResearchOrchestrator(
            search_agent=search_agent,
            source_reader_agent=reader_agent,
            evidence_analyst_agent=evidence_agent,
            claim_analyst_agent=claim_agent,
            review_revision_loop=loop,
        ),
    }


def _identity(
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def _profile(
    agent_id: str,
    role: ResearchAgentRole,
    capability: ResearchAgentCapability,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-{agent_id}",
        agent=_identity(agent_id, role),
        capabilities=[capability],
    )


def _quality_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-phase9a-quality",
        agent=_identity(
            "phase9a-agent-quality",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
        capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
            ResearchAgentCapability.REQUEST_REVISION,
            ResearchAgentCapability.APPROVE_RESULT,
        ],
    )


def _manager_profile(
    role: ResearchAgentRole,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-phase9a-manager-{role.value}",
        agent=_identity(
            "phase9a-agent-manager",
            ResearchAgentRole.MANAGER,
        ),
        capabilities=[ResearchAgentCapability.MANAGE_RESEARCH],
        can_delegate=True,
        delegatable_roles=[role],
    )


def _required_capability(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    return {
        ResearchAgentRole.SEARCH_SPECIALIST: (
            ResearchAgentCapability.SEARCH_SOURCES
        ),
        ResearchAgentRole.SOURCE_READER: (
            ResearchAgentCapability.READ_SOURCES
        ),
        ResearchAgentRole.EVIDENCE_ANALYST: (
            ResearchAgentCapability.EXTRACT_EVIDENCE
        ),
        ResearchAgentRole.CLAIM_ANALYST: (
            ResearchAgentCapability.BUILD_CLAIMS
        ),
        ResearchAgentRole.SYNTHESIS_SPECIALIST: (
            ResearchAgentCapability.SYNTHESIZE_REPORT
        ),
        ResearchAgentRole.QUALITY_REVIEWER: (
            ResearchAgentCapability.EVALUATE_REPORT
        ),
    }[role]


def _assignment(
    assignment_id: str,
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentTaskAssignment:
    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id=REQUEST_ID,
        workspace_id=WORKSPACE_ID,
        assigner_profile=_manager_profile(role),
        assignee=_identity(agent_id, role),
        required_role=role,
        required_capabilities=[_required_capability(role)],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=["Preserve traceable artifact handoffs."],
        expected_output_type=f"{role.value}_output",
        acceptance_criteria=[
            "Return one structured primary output.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
