"""Phase 8C end-to-end local multi-agent workflow test."""

from __future__ import annotations

import json

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
    MultiAgentResearchStatus,
)
from app.research.multi_agent_synthesis_runtime import (
    RegisteredWorkspaceSynthesisExecutor,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.pipeline_source_adapters import (
    PipelineSourceReaderAdapter,
    PipelineSourceSearchAdapter,
)
from app.research.quality_reviewer_agent import QualityReviewerAgent
from app.research.review_revision_loop import ReviewRevisionLoop
from app.research.search_specialist_agent import SearchSpecialistAgent
from app.research.source_reader_specialist_agent import (
    SourceReaderSpecialistAgent,
)
from app.research.synthesis_specialist_agent import (
    SynthesisSpecialistAgent,
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
from app.schemas.research_request import (
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
from app.schemas.research_workspace import ResearchWorkspace
from app.services.ollama_client import OllamaGenerateResponse


class FakeOllamaClient:
    def generate(self, **kwargs: object) -> OllamaGenerateResponse:
        del kwargs
        return OllamaGenerateResponse(
            model="qwen3.5:4b",
            response=json.dumps(
                {
                    "decision": "approved",
                    "completeness": 0.9,
                    "evidence_coverage": 0.9,
                    "citation_quality": 0.9,
                    "source_quality": 0.8,
                    "logical_consistency": 0.9,
                    "clarity": 0.9,
                    "summary": "The report is traceable and clear.",
                    "strengths": ["Traceable evidence and citations"],
                    "revision_requests": [],
                    "rejection_reason": None,
                }
            ),
            thinking="",
            done=True,
            done_reason="stop",
            total_duration_ns=10_000_000,
            load_duration_ns=1_000_000,
            prompt_eval_count=100,
            prompt_eval_duration_ns=2_000_000,
            eval_count=50,
            eval_duration_ns=7_000_000,
        )


def test_full_multi_agent_path_reaches_local_quality_reviewer() -> None:
    runtime = _runtime()
    result = runtime["orchestrator"].run(
        search_assignment=_assignment(
            "assignment-search-001",
            "agent-search-001",
            ResearchAgentRole.SEARCH_SPECIALIST,
        ),
        source_reader_template=_assignment(
            "assignment-reader-001",
            "agent-reader-001",
            ResearchAgentRole.SOURCE_READER,
        ),
        evidence_template=_assignment(
            "assignment-evidence-001",
            "agent-evidence-001",
            ResearchAgentRole.EVIDENCE_ANALYST,
        ),
        claim_template=_assignment(
            "assignment-claim-001",
            "agent-claim-001",
            ResearchAgentRole.CLAIM_ANALYST,
        ),
        synthesis_template=_assignment(
            "assignment-synthesis-001",
            "agent-synthesis-001",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
        ),
        review_template=_assignment(
            "assignment-review-001",
            "agent-quality-001",
            ResearchAgentRole.QUALITY_REVIEWER,
        ),
    )

    assert result.status is MultiAgentResearchStatus.COMPLETED
    assert result.completed is True
    assert result.review_revision_result is not None
    assert result.review_revision_result.final_review_result is not None
    review_result = result.review_revision_result.final_review_result
    assert review_result.payload["review"]["decision"] == "approved"
    assert review_result.metadata["provider"] == "ollama-local"
    assert review_result.metadata["authoritative"] == "false"

    context = runtime["context"]
    assert context.workspace.claim_set is not None
    assert len(context.workspace.claim_set.claims) == 1

    report_registry = runtime["report_registry"]
    report = report_registry.resolve("report-output-001")
    assert report.sections[0].claim_ids == [
        context.workspace.claim_set.claims[0].claim_id
    ]


def _runtime() -> dict[str, object]:
    request = ResearchRequest(
        request_id="research-001",
        question="How are multi-agent research artifacts handed off?",
        objective=(
            "Produce a traceable research result through specialist agents."
        ),
        maximum_sources=1,
    )
    task = ResearchTask(
        task_id="task-001",
        request_id=request.request_id,
        title="Inspect artifact handoff",
        question=request.question,
        objective=request.objective,
        completion_criteria=[
            "Produce one evidence-backed traceable claim.",
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
                query_id="query-001",
                request_id=request.request_id,
                task_id=task.task_id,
                query_text="multi-agent artifact handoff",
                preferred_source_types=[
                    ResearchSourceType.ACADEMIC,
                ],
                maximum_results=1,
            )
        ],
    )
    context = MultiAgentResearchRuntimeContext(
        workspace=ResearchWorkspace(
            workspace_id="workspace-001",
            request=request,
            task_graph=task_graph,
            query_set=query_set,
        )
    )

    searcher = PipelineSourceSearchAdapter(
        InMemoryResearchSourceSearchTool(
            records=[
                InMemoryResearchSourceRecord(
                    source_id="source-001",
                    title="Artifact Handoff",
                    url="https://example.com/artifact-handoff",
                    source_type=ResearchSourceType.ACADEMIC,
                    snippet=(
                        "Specialist stages can share traceable artifacts."
                    ),
                    keywords=["artifact", "handoff", "specialist"],
                )
            ]
        ),
        maximum_candidates=1,
    )
    reader = PipelineSourceReaderAdapter(
        InMemoryResearchSourceReader(
            records=[
                InMemoryResearchDocumentRecord(
                    source_id="source-001",
                    url="https://example.com/artifact-handoff",
                    content_type=ResearchSourceContentType.TEXT,
                    content=(
                        "Specialist stages share traceable research artifacts "
                        "through a common workspace and explicit references."
                    ),
                    language="en",
                )
            ]
        )
    )
    extractor = PipelineEvidenceExtractorAdapter(
        WholeDocumentEvidenceExtractor()
    )
    builder = DeterministicPipelineClaimBuilder()

    search_agent = SearchSpecialistAgent(
        profile=_profile(
            "agent-search-001",
            ResearchAgentRole.SEARCH_SPECIALIST,
            ResearchAgentCapability.SEARCH_SOURCES,
        ),
        executor=PipelineResearchSearchExecutor(
            context=context,
            searcher=searcher,
        ),
        output_reference_id_factory=lambda: "source-set-001",
    )
    reader_agent = SourceReaderSpecialistAgent(
        profile=_profile(
            "agent-reader-001",
            ResearchAgentRole.SOURCE_READER,
            ResearchAgentCapability.READ_SOURCES,
        ),
        executor=PipelineResearchSourceReaderExecutor(
            context=context,
            reader=reader,
        ),
        output_reference_id_factory=lambda: "document-set-001",
    )
    evidence_agent = EvidenceAnalystAgent(
        profile=_profile(
            "agent-evidence-001",
            ResearchAgentRole.EVIDENCE_ANALYST,
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ),
        executor=PipelineResearchEvidenceExecutor(
            context=context,
            extractor=extractor,
        ),
        output_reference_id_factory=lambda: "evidence-set-001",
    )
    claim_agent = ClaimAnalystAgent(
        profile=_profile(
            "agent-claim-001",
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=PipelineResearchClaimExecutor(
            context=context,
            builder=builder,
        ),
        output_reference_id_factory=lambda: "claim-set-001",
    )

    report_registry = InMemoryResearchReportRegistry()
    synthesis_executor = RegisteredWorkspaceSynthesisExecutor(
        context=context,
        report_registry=report_registry,
        report_reference_id_factory=lambda: "report-output-001",
        report_id_factory=lambda: "report-001",
    )
    synthesis_agent = SynthesisSpecialistAgent(
        profile=_profile(
            "agent-synthesis-001",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ),
        executor=synthesis_executor,
        output_reference_id_factory=(
            synthesis_executor.take_output_reference_id
        ),
    )

    quality_executor = LocalResearchQualityReviewExecutor(
        client=FakeOllamaClient(),
        model="qwen3.5:4b",
        report_registry=report_registry,
        review_id_factory=lambda: "quality-review-001",
    )
    quality_agent = QualityReviewerAgent(
        profile=_quality_profile(),
        executor=quality_executor,
        output_reference_id_factory=lambda: "quality-output-001",
    )
    loop = ReviewRevisionLoop(
        synthesis_agent=synthesis_agent,
        quality_reviewer=quality_agent,
        maximum_revision_rounds=0,
        loop_id_factory=lambda: "review-loop-001",
        review_assignment_id_factory=lambda _: "review-round-001",
    )

    return {
        "context": context,
        "report_registry": report_registry,
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
        profile_id=f"profile-{role.value}",
        agent=_identity(agent_id, role),
        capabilities=[capability],
    )


def _quality_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-quality",
        agent=_identity(
            "agent-quality-001",
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
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=_manager_profile(role),
        assignee=_identity(agent_id, role),
        required_role=role,
        required_capabilities=[_required_capability(role)],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=[
            "Use the shared traceable research artifacts.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="template-input",
                reference_type="template",
                reference_id="template-001",
            )
        ],
        expected_output_type=(
            "research_report"
            if role is ResearchAgentRole.SYNTHESIS_SPECIALIST
            else (
                "research_quality_review"
                if role is ResearchAgentRole.QUALITY_REVIEWER
                else f"{role.value}_output"
            )
        ),
        acceptance_criteria=[
            "Return one structured primary output.",
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )
