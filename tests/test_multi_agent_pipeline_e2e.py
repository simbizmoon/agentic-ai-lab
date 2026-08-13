"""Phase 8A end-to-end test for the real multi-agent data-plane bridge."""

from __future__ import annotations

from datetime import UTC, datetime

from app.research.claim_analyst_agent import ClaimAnalystAgent
from app.research.evidence_analyst_agent import EvidenceAnalystAgent
from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.in_memory_research_source_search_tool import (
    InMemoryResearchSourceSearchTool,
)
from app.research.local_runtime import WholeDocumentEvidenceExtractor
from app.research.multi_agent_pipeline_executors import (
    MultiAgentResearchRuntimeContext,
    PipelineResearchClaimExecutor,
    PipelineResearchEvidenceExecutor,
    PipelineResearchSearchExecutor,
    PipelineResearchSourceReaderExecutor,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchOrchestrator,
    MultiAgentResearchStage,
    MultiAgentResearchStatus,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoopResult,
    ReviewRevisionLoopStatus,
    ReviewRevisionRound,
)
from app.research.search_specialist_agent import SearchSpecialistAgent
from app.research.source_reader_specialist_agent import (
    SourceReaderSpecialistAgent,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentInput,
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_agent_result import (
    ResearchAgentExecutionMetrics,
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
)
from app.schemas.research_task import ResearchTask, ResearchTaskGraph
from app.schemas.research_workspace import (
    ResearchWorkspace,
    ResearchWorkspaceStage,
)


class StubApprovedReviewRevisionLoop:
    """Keep Phase 8A focused on the first four real specialist stages."""

    def __init__(self) -> None:
        self.calls: list[
            tuple[
                ResearchAgentTaskAssignment,
                ResearchAgentTaskAssignment,
            ]
        ] = []

    def run(
        self,
        *,
        initial_synthesis_assignment: ResearchAgentTaskAssignment,
        review_assignment_template: ResearchAgentTaskAssignment,
    ) -> ReviewRevisionLoopResult:
        self.calls.append(
            (
                initial_synthesis_assignment,
                review_assignment_template,
            )
        )

        synthesis_identity = ResearchAgentIdentity(
            agent_id="agent-synthesis-001",
            name="synthesis_specialist",
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
            description="synthesis specialist agent.",
        )
        synthesis_result = ResearchAgentTaskResult(
            result_id="result-synthesis-001",
            assignment=initial_synthesis_assignment,
            agent=synthesis_identity,
            status=ResearchAgentResultStatus.SUCCEEDED,
            summary="Stub synthesis result.",
            outputs=[
                ResearchAgentOutputReference(
                    name="research-report",
                    output_type="research_report",
                    reference_id="report-001",
                    primary=True,
                )
            ],
            metrics=ResearchAgentExecutionMetrics(),
            completed_at=datetime(
                2026,
                8,
                13,
                4,
                0,
                tzinfo=UTC,
            ),
        )
        round_result = ReviewRevisionRound(
            round_number=1,
            synthesis_assignment=initial_synthesis_assignment,
            synthesis_result=synthesis_result,
        )
        return ReviewRevisionLoopResult(
            loop_id="loop-phase8a-001",
            status=ReviewRevisionLoopStatus.APPROVED,
            rounds=[round_result],
            maximum_revision_rounds=0,
            revision_rounds_used=0,
            final_synthesis_result=synthesis_result,
            summary="Phase 8A stub review loop approved the handoff.",
        )


def test_real_specialists_advance_shared_workspace_through_claims() -> None:
    request = ResearchRequest(
        request_id="research-001",
        question="How does the multi-agent runtime share research artifacts?",
        objective="Build one traceable claim from a deterministic local source.",
        depth=ResearchDepth.QUICK,
        output_format=ResearchOutputFormat.BRIEF,
        maximum_sources=1,
        require_citations=True,
    )
    task = ResearchTask(
        task_id="task-001",
        request_id=request.request_id,
        title="Inspect the runtime source",
        question=request.question,
        objective=request.objective,
        completion_criteria=[
            "Produce one traceable evidence-backed claim.",
        ],
        expected_output="One traceable evidence-backed claim.",
    )
    task_graph = ResearchTaskGraph(
        request_id=request.request_id,
        tasks=[task],
    )
    query = ResearchSearchQuery(
        query_id="query-001",
        request_id=request.request_id,
        task_id=task.task_id,
        query_text="multi-agent runtime workspace",
        preferred_source_types=[
            ResearchSourceType.ACADEMIC,
        ],
        maximum_results=1,
    )
    query_set = ResearchSearchQuerySet(
        request_id=request.request_id,
        task_graph=task_graph,
        queries=[query],
    )
    context = MultiAgentResearchRuntimeContext(
        workspace=ResearchWorkspace(
            workspace_id="workspace-001",
            request=request,
            task_graph=task_graph,
            query_set=query_set,
        )
    )

    source_searcher = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=[
                InMemoryResearchSourceRecord(
                    source_id="source-001",
                    title="Multi-Agent Runtime Workspace",
                    url="https://example.com/multi-agent-runtime",
                    source_type=ResearchSourceType.ACADEMIC,
                    snippet=(
                        "A shared research workspace carries "
                        "traceable artifacts between specialist stages."
                    ),
                    keywords=[
                        "multi-agent",
                        "runtime",
                        "workspace",
                    ],
                    metadata={
                        "fixture": "phase8a",
                    },
                )
            ]
        ),
        maximum_candidates=1,
    )
    source_reader = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(
            records=[
                InMemoryResearchDocumentRecord(
                    source_id="source-001",
                    url="https://example.com/multi-agent-runtime",
                    content_type=ResearchSourceContentType.TEXT,
                    content=(
                        "A shared research workspace carries traceable "
                        "artifacts between specialist stages."
                    ),
                    language="en",
                    metadata={
                        "fixture": "phase8a",
                    },
                )
            ]
        )
    )
    evidence_extractor = PipelineEvidenceExtractorAdapter(
        WholeDocumentEvidenceExtractor()
    )
    claim_builder = DeterministicPipelineClaimBuilder()

    search_agent = SearchSpecialistAgent(
        profile=_specialist_profile(
            "agent-search-001",
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentCapability.SEARCH_SOURCES,
        ),
        executor=PipelineResearchSearchExecutor(
            context=context,
            searcher=source_searcher,
        ),
        result_id_factory=lambda: "result-search-001",
        output_reference_id_factory=lambda: "source-set-001",
    )
    reader_agent = SourceReaderSpecialistAgent(
        profile=_specialist_profile(
            "agent-reader-001",
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentCapability.READ_SOURCES,
        ),
        executor=PipelineResearchSourceReaderExecutor(
            context=context,
            reader=source_reader,
        ),
        result_id_factory=lambda: "result-reader-001",
        output_reference_id_factory=lambda: "document-set-001",
    )
    evidence_agent = EvidenceAnalystAgent(
        profile=_specialist_profile(
            "agent-evidence-001",
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ),
        executor=PipelineResearchEvidenceExecutor(
            context=context,
            extractor=evidence_extractor,
        ),
        result_id_factory=lambda: "result-evidence-001",
        output_reference_id_factory=lambda: "evidence-set-001",
    )
    claim_agent = ClaimAnalystAgent(
        profile=_specialist_profile(
            "agent-claim-001",
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=PipelineResearchClaimExecutor(
            context=context,
            builder=claim_builder,
        ),
        result_id_factory=lambda: "result-claim-001",
        output_reference_id_factory=lambda: "claim-set-001",
    )

    review_loop = StubApprovedReviewRevisionLoop()
    orchestrator = MultiAgentResearchOrchestrator(
        search_agent=search_agent,
        source_reader_agent=reader_agent,
        evidence_analyst_agent=evidence_agent,
        claim_analyst_agent=claim_agent,
        review_revision_loop=review_loop,
    )

    result = orchestrator.run(
        search_assignment=_assignment(
            assignment_id="assignment-search-001",
            agent_id="agent-search-001",
            role=ResearchAgentRole.SEARCH_SPECIALIST,
        ),
        source_reader_template=_assignment(
            assignment_id="assignment-reader-001",
            agent_id="agent-reader-001",
            role=ResearchAgentRole.SOURCE_READER,
        ),
        evidence_template=_assignment(
            assignment_id="assignment-evidence-001",
            agent_id="agent-evidence-001",
            role=ResearchAgentRole.EVIDENCE_ANALYST,
        ),
        claim_template=_assignment(
            assignment_id="assignment-claim-001",
            agent_id="agent-claim-001",
            role=ResearchAgentRole.CLAIM_ANALYST,
        ),
        synthesis_template=_assignment(
            assignment_id="assignment-synthesis-001",
            agent_id="agent-synthesis-001",
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
        ),
        review_template=_assignment(
            assignment_id="assignment-review-001",
            agent_id="agent-quality-001",
            role=ResearchAgentRole.QUALITY_REVIEWER,
        ),
    )

    assert result.status is MultiAgentResearchStatus.COMPLETED
    assert result.completed is True
    assert [
        stage.stage
        for stage in result.stages
    ] == [
        MultiAgentResearchStage.SEARCH,
        MultiAgentResearchStage.SOURCE_READING,
        MultiAgentResearchStage.EVIDENCE_EXTRACTION,
        MultiAgentResearchStage.CLAIM_CONSTRUCTION,
    ]
    assert all(
        stage.result.status is ResearchAgentResultStatus.SUCCEEDED
        for stage in result.stages
    )

    assert context.workspace.stage is ResearchWorkspaceStage.CLAIMS_BUILT
    assert context.workspace.candidate_set is not None
    assert context.workspace.document_set is not None
    assert context.workspace.evidence_set is not None
    assert context.workspace.claim_set is not None
    assert len(context.workspace.candidate_set.candidates) == 1
    assert len(context.workspace.document_set.successful_documents()) == 1
    assert len(context.workspace.evidence_set.evidence) == 1
    assert len(context.workspace.claim_set.claims) == 1
    assert context.workspace.claim_set.claims[0].citations

    assert len(review_loop.calls) == 1
    synthesis_assignment, _ = review_loop.calls[0]
    assert synthesis_assignment.inputs[0].reference_id == "claim-set-001"

    assert result.stages[1].assignment.inputs[0].reference_id == (
        "source-set-001"
    )
    assert result.stages[2].assignment.inputs[0].reference_id == (
        "document-set-001"
    )
    assert result.stages[3].assignment.inputs[0].reference_id == (
        "evidence-set-001"
    )


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


def _specialist_profile(
    agent_id: str,
    role: ResearchAgentRole,
    capability: ResearchAgentCapability,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-{role.value}",
        agent=_identity(
            agent_id,
            role,
        ),
        capabilities=[capability],
    )


def _capability_for_role(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    mapping = {
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
    }
    return mapping[role]


def _manager_profile(
    role: ResearchAgentRole,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-manager-{role.value}",
        agent=_identity(
            "agent-manager-001",
            ResearchAgentRole.MANAGER,
        ),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[role],
    )


def _assignment(
    *,
    assignment_id: str,
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentTaskAssignment:
    capability = _capability_for_role(role)

    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=_manager_profile(role),
        assignee=_identity(
            agent_id,
            role,
        ),
        required_role=role,
        required_capabilities=[capability],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=[
            "Use the shared research workspace.",
            "Return one structured primary output.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="template-input",
                reference_type="template",
                reference_id="template-001",
            )
        ],
        expected_output_type=f"{role.value}_output",
        acceptance_criteria=[
            "Return one primary output.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )
