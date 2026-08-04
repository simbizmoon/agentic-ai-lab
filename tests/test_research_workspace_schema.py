"""Tests for the central research workspace schema."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
    ResearchClaimSet,
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
    ResearchSourceQualityLevel,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
    ResearchWorkspaceStage,
)

CONTENT = "Agent memory stores contextual information."


def request(
    *,
    request_id: str = "research-001",
) -> ResearchRequest:
    """Return one research request."""

    return ResearchRequest(
        request_id=request_id,
        question=(
            "How do agent memory architectures differ?"
        ),
        objective=(
            "Compare memory architectures and explain "
            "their engineering trade-offs."
        ),
        include_topics=["agent memory"],
        preferred_source_types=[
            ResearchSourceType.ACADEMIC,
        ],
    )


def task_graph(
    *,
    request_id: str = "research-001",
) -> ResearchTaskGraph:
    """Return one research task graph."""

    return ResearchTaskGraph(
        request_id=request_id,
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id=request_id,
                title="Investigate agent memory",
                question=(
                    "How does agent memory work?"
                ),
                objective=(
                    "Produce verified findings about "
                    "agent memory."
                ),
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Structured findings.",
            )
        ],
    )


def query_set(
    *,
    graph: ResearchTaskGraph | None = None,
) -> ResearchSearchQuerySet:
    """Return one search query set."""

    value = graph or task_graph()

    return ResearchSearchQuerySet(
        request_id=value.request_id,
        task_graph=value,
        queries=[
            ResearchSearchQuery(
                query_id="query-001",
                request_id=value.request_id,
                task_id="task-001",
                query_text="agent memory architecture",
            )
        ],
    )


def candidate_set(
    *,
    queries: ResearchSearchQuerySet | None = None,
) -> ResearchSourceCandidateSet:
    """Return one source candidate set."""

    value = queries or query_set()

    return ResearchSourceCandidateSet(
        request_id=value.request_id,
        query_set=value,
        candidates=[
            ResearchSourceCandidate(
                source_id="source-001",
                request_id=value.request_id,
                task_id="task-001",
                query_id="query-001",
                title="Agent memory research",
                url="https://example.com/source",
                source_type=ResearchSourceType.ACADEMIC,
                author="Example Author",
                publisher="Example Publisher",
                published_at=date(2026, 1, 1),
                rank=1,
            )
        ],
    )


def document_set(
    *,
    request_id: str = "research-001",
) -> ResearchSourceDocumentSet:
    """Return one source document set."""

    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id=request_id,
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        author="Example Author",
        publisher="Example Publisher",
        published_at=date(2026, 1, 1),
        rank=1,
    )

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )

    return ResearchSourceDocumentSet(
        request_id=request_id,
        documents=[document],
    )


def evidence_set(
    *,
    documents: ResearchSourceDocumentSet | None = None,
) -> ResearchEvidenceSet:
    """Return one evidence set."""

    value = documents or document_set()

    return ResearchEvidenceSet(
        request_id=value.request_id,
        document_set=value,
        evidence=[
            ResearchEvidence(
                evidence_id="evidence-001",
                request_id=value.request_id,
                task_id="task-001",
                source_id="source-001",
                document_id="document-001",
                excerpt=CONTENT,
                start_character=0,
                end_character=len(CONTENT),
                evidence_type=ResearchEvidenceType.FACT,
                stance=ResearchEvidenceStance.SUPPORTS,
                relevance_score=0.9,
                confidence_score=0.8,
            )
        ],
    )


def claim_set(
    *,
    evidence_value: ResearchEvidenceSet | None = None,
) -> ResearchClaimSet:
    """Return one claim set."""

    value = evidence_value or evidence_set()

    citation = ResearchCitation(
        citation_id="citation-001",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=CONTENT,
        start_character=0,
        end_character=len(CONTENT),
    )

    claim = ResearchClaim(
        claim_id="claim-001",
        request_id=value.request_id,
        task_id="task-001",
        text=CONTENT,
        claim_type=ResearchClaimType.FACTUAL,
        status=ResearchClaimStatus.SUPPORTED,
        confidence_score=0.8,
        citations=[citation],
        supporting_evidence_ids=[
            "evidence-001"
        ],
    )

    return ResearchClaimSet(
        request_id=value.request_id,
        evidence_set=value,
        claims=[claim],
    )


def quality(
    *,
    documents: ResearchSourceDocumentSet,
) -> ResearchSourceQualityEvaluation:
    """Return one source quality evaluation."""

    return ResearchSourceQualityEvaluation(
        document=documents.documents[0],
        evaluator="test-evaluator",
        authority_score=0.9,
        primary_source_score=0.8,
        recency_score=1.0,
        completeness_score=0.45,
        traceability_score=1.0,
        overall_score=0.77,
        quality_level=ResearchSourceQualityLevel.HIGH,
    )


def complete_workspace() -> ResearchWorkspace:
    """Return one complete research workspace."""

    graph = task_graph()
    queries = query_set(graph=graph)
    candidates = candidate_set(queries=queries)
    documents = document_set()
    evidence_value = evidence_set(
        documents=documents
    )
    claims = claim_set(
        evidence_value=evidence_value
    )

    return ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
        task_graph=graph,
        query_set=queries,
        candidate_set=candidates,
        document_set=documents,
        evidence_set=evidence_value,
        claim_set=claims,
        source_quality_evaluations=[
            quality(documents=documents)
        ],
        metadata={
            "agent": "single-research-agent",
        },
    )


def test_workspace_accepts_request_only() -> None:
    workspace = ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
    )

    assert workspace.stage is (
        ResearchWorkspaceStage.REQUESTED
    )


def test_workspace_accepts_complete_state() -> None:
    workspace = complete_workspace()

    assert workspace.stage is (
        ResearchWorkspaceStage.CLAIMS_BUILT
    )
    assert workspace.progress().claim_count == 1


@pytest.mark.parametrize(
    ("field_name", "expected_stage"),
    [
        ("task_graph", ResearchWorkspaceStage.DECOMPOSED),
        (
            "query_set",
            ResearchWorkspaceStage.QUERIES_PLANNED,
        ),
        (
            "candidate_set",
            ResearchWorkspaceStage.SOURCES_DISCOVERED,
        ),
        (
            "document_set",
            ResearchWorkspaceStage.DOCUMENTS_READ,
        ),
        (
            "evidence_set",
            ResearchWorkspaceStage.EVIDENCE_EXTRACTED,
        ),
        (
            "claim_set",
            ResearchWorkspaceStage.CLAIMS_BUILT,
        ),
    ],
)
def test_workspace_reports_progressive_stage(
    field_name: str,
    expected_stage: ResearchWorkspaceStage,
) -> None:
    graph = task_graph()
    queries = query_set(graph=graph)
    candidates = candidate_set(queries=queries)
    documents = document_set()
    evidence_value = evidence_set(
        documents=documents
    )
    claims = claim_set(
        evidence_value=evidence_value
    )

    values: dict[str, object] = {
        "workspace_id": "workspace-001",
        "request": request(),
        "task_graph": graph,
        "query_set": queries,
        "candidate_set": candidates,
        "document_set": documents,
        "evidence_set": evidence_value,
        "claim_set": claims,
    }

    ordered_fields = [
        "task_graph",
        "query_set",
        "candidate_set",
        "document_set",
        "evidence_set",
        "claim_set",
    ]

    field_index = ordered_fields.index(field_name)

    for later_field in ordered_fields[
        field_index + 1:
    ]:
        values[later_field] = None

    workspace = ResearchWorkspace.model_validate(
        values
    )

    assert workspace.stage is expected_stage


def test_workspace_rejects_blank_workspace_id() -> None:
    with pytest.raises(
        ValidationError,
        match="workspace_id must not be blank",
    ):
        ResearchWorkspace(
            workspace_id=" ",
            request=request(),
        )


def test_workspace_rejects_query_without_graph() -> None:
    with pytest.raises(
        ValidationError,
        match="query_set requires task_graph",
    ):
        ResearchWorkspace(
            workspace_id="workspace-001",
            request=request(),
            query_set=query_set(),
        )


def test_workspace_rejects_candidate_without_query() -> None:
    with pytest.raises(
        ValidationError,
        match="candidate_set requires query_set",
    ):
        ResearchWorkspace(
            workspace_id="workspace-001",
            request=request(),
            task_graph=task_graph(),
            candidate_set=candidate_set(),
        )


def test_workspace_rejects_document_without_candidate() -> None:
    graph = task_graph()
    queries = query_set(graph=graph)

    with pytest.raises(
        ValidationError,
        match="document_set requires candidate_set",
    ):
        ResearchWorkspace(
            workspace_id="workspace-001",
            request=request(),
            task_graph=graph,
            query_set=queries,
            document_set=document_set(),
        )


def test_workspace_rejects_mismatched_request_id() -> None:
    graph = task_graph(request_id="research-002")

    with pytest.raises(
        ValidationError,
        match=(
            "all workspace request IDs must match"
        ),
    ):
        ResearchWorkspace(
            workspace_id="workspace-001",
            request=request(),
            task_graph=graph,
        )


def test_workspace_rejects_different_query_graph() -> None:
    workspace_graph = task_graph()
    different_graph = ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="task-002",
                request_id="research-001",
                title="Different task",
                question="What differs in this task?",
                objective=(
                    "Produce different verified findings."
                ),
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Different findings.",
            )
        ],
    )

    different_query_set = ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=different_graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-002",
                request_id="research-001",
                task_id="task-002",
                query_text="different research query",
            )
        ],
    )

    with pytest.raises(
        ValidationError,
        match=(
            "query_set task_graph must match "
            "workspace task_graph"
        ),
    ):
        ResearchWorkspace(
            workspace_id="workspace-001",
            request=request(),
            task_graph=workspace_graph,
            query_set=different_query_set,
        )


def test_workspace_rejects_duplicate_quality_documents() -> None:
    workspace = complete_workspace()
    evaluation = (
        workspace.source_quality_evaluations[0]
    )

    values = workspace.model_dump()
    values["source_quality_evaluations"] = [
        evaluation,
        evaluation,
    ]

    with pytest.raises(
        ValidationError,
        match=(
            "source quality evaluations must have "
            "unique document IDs"
        ),
    ):
        ResearchWorkspace.model_validate(values)


def test_workspace_progress_counts_objects() -> None:
    progress = complete_workspace().progress()

    assert progress.task_count == 1
    assert progress.searchable_task_count == 1
    assert progress.query_count == 1
    assert progress.candidate_count == 1
    assert progress.document_count == 1
    assert progress.successful_document_count == 1
    assert progress.failed_document_count == 0
    assert progress.evidence_count == 1
    assert progress.claim_count == 1
    assert progress.quality_evaluation_count == 1


def test_workspace_returns_task() -> None:
    workspace = complete_workspace()

    result = workspace.task(" TASK-001 ")

    assert result is not None
    assert result.task_id == "task-001"
    assert workspace.task("missing-task") is None


def test_workspace_returns_task_scoped_objects() -> None:
    workspace = complete_workspace()

    assert len(
        workspace.queries_for_task("task-001")
    ) == 1
    assert len(
        workspace.candidates_for_task("task-001")
    ) == 1
    assert len(
        workspace.documents_for_task("task-001")
    ) == 1
    assert len(
        workspace.evidence_for_task("task-001")
    ) == 1
    assert len(
        workspace.claims_for_task("task-001")
    ) == 1


def test_workspace_returns_empty_for_unbuilt_layers() -> None:
    workspace = ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
        task_graph=task_graph(),
    )

    assert (
        workspace.queries_for_task("task-001")
        == []
    )
    assert (
        workspace.claims_for_task("task-001")
        == []
    )


def test_workspace_returns_quality_by_document() -> None:
    workspace = complete_workspace()

    result = workspace.quality_for_document(
        " DOCUMENT-001 "
    )

    assert result is not None
    assert result.overall_score == 0.77
    assert (
        workspace.quality_for_document(
            "missing-document"
        )
        is None
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "task",
        "queries_for_task",
        "candidates_for_task",
        "documents_for_task",
        "evidence_for_task",
        "claims_for_task",
    ],
)
def test_workspace_rejects_blank_task_lookup(
    method_name: str,
) -> None:
    workspace = complete_workspace()
    method = getattr(workspace, method_name)

    with pytest.raises(
        ValueError,
        match="task_id must not be blank",
    ):
        method(" ")


def test_workspace_rejects_blank_document_lookup() -> None:
    with pytest.raises(
        ValueError,
        match="document_id must not be blank",
    ):
        complete_workspace().quality_for_document(" ")


def test_workspace_is_deterministic() -> None:
    first = complete_workspace()
    second = complete_workspace()

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
