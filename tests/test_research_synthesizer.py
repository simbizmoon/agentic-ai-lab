"""Tests for deterministic research report synthesis."""

import pytest

from app.research.research_synthesis_error import (
    ResearchSynthesisError,
)
from app.research.research_synthesizer import (
    DeterministicResearchSynthesizer,
)
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
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
)

CONTENT = "Agent memory stores contextual information."


def request() -> ResearchRequest:
    """Return one research request."""

    return ResearchRequest(
        request_id="research-001",
        question=(
            "How does agent memory support AI systems?"
        ),
        objective=(
            "Explain the role of agent memory using "
            "traceable evidence."
        ),
    )


def graph() -> ResearchTaskGraph:
    """Return one research task graph."""

    return ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            ResearchTask(
                task_id="task-001",
                request_id="research-001",
                title="Agent memory findings",
                question=(
                    "How does agent memory work?"
                ),
                objective=(
                    "Produce verified agent-memory findings."
                ),
                completion_criteria=[
                    "Produce one supported finding"
                ],
                expected_output="Structured findings.",
            )
        ],
    )


def query_set(
    task_graph: ResearchTaskGraph,
) -> ResearchSearchQuerySet:
    """Return one valid search query set."""

    return ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=task_graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-001",
                request_id="research-001",
                task_id="task-001",
                query_text="agent memory architecture",
            )
        ],
    )


def candidate_set(
    queries: ResearchSearchQuerySet,
) -> ResearchSourceCandidateSet:
    """Return one valid source candidate set."""

    return ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=queries,
        candidates=[candidate()],
    )


def candidate() -> ResearchSourceCandidate:
    """Return one source candidate."""

    return ResearchSourceCandidate(
        source_id="source-001",
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url="https://example.com/source",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def documents() -> ResearchSourceDocumentSet:
    """Return one source document set."""

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate(),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        sections=[],
        word_count=len(CONTENT.split()),
        character_count=len(CONTENT),
        reader="test-reader",
    )

    return ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[document],
    )


def evidence_value(
    document_set: ResearchSourceDocumentSet,
) -> ResearchEvidenceSet:
    """Return one evidence set."""

    return ResearchEvidenceSet(
        request_id="research-001",
        document_set=document_set,
        evidence=[
            ResearchEvidence(
                evidence_id="evidence-001",
                request_id="research-001",
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


def claims(
    evidence_set: ResearchEvidenceSet,
) -> ResearchClaimSet:
    """Return one supported claim set."""

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
        request_id="research-001",
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
        request_id="research-001",
        evidence_set=evidence_set,
        claims=[claim],
    )


def workspace() -> ResearchWorkspace:
    """Return one synthesizable workspace."""

    task_graph = graph()
    queries = query_set(task_graph)
    candidates = candidate_set(queries)
    document_set = documents()
    evidence_set = evidence_value(document_set)

    return ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
        task_graph=task_graph,
        query_set=queries,
        candidate_set=candidates,
        document_set=document_set,
        evidence_set=evidence_set,
        claim_set=claims(evidence_set),
    )


def test_synthesizer_creates_report() -> None:
    result = (
        DeterministicResearchSynthesizer()
        .synthesize(workspace())
    )

    assert result.report_id == (
        "research-001-report"
    )
    assert result.claim_count == 1
    assert result.citation_count == 1
    assert result.source_count == 1


def test_synthesizer_builds_task_section() -> None:
    result = (
        DeterministicResearchSynthesizer()
        .synthesize(workspace())
    )

    assert len(result.sections) == 1
    assert result.sections[0].task_id == "task-001"
    assert result.sections[0].claim_ids == [
        "claim-001"
    ]
    assert "[1]" in result.sections[0].content


def test_synthesizer_builds_source_citation() -> None:
    result = (
        DeterministicResearchSynthesizer()
        .synthesize(workspace())
    )

    citation = result.citations[0]

    assert citation.evidence_id == "evidence-001"
    assert citation.title == "Agent memory research"
    assert citation.url == (
        "https://example.com/source"
    )
    assert citation.label == "[1]"


def test_synthesizer_builds_summary() -> None:
    result = (
        DeterministicResearchSynthesizer()
        .synthesize(workspace())
    )

    assert "1 claims" in result.executive_summary
    assert "1 citations" in result.executive_summary
    assert "1 sources" in result.executive_summary


def test_synthesizer_rejects_missing_graph() -> None:
    value = ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
    )

    with pytest.raises(
        ResearchSynthesisError,
        match="workspace must contain a task graph",
    ):
        (
            DeterministicResearchSynthesizer()
            .synthesize(value)
        )


def test_synthesizer_rejects_missing_claim_set() -> None:
    value = ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
        task_graph=graph(),
    )

    with pytest.raises(
        ResearchSynthesisError,
        match="workspace must contain a claim set",
    ):
        (
            DeterministicResearchSynthesizer()
            .synthesize(value)
        )


def test_synthesizer_rejects_empty_claim_set() -> None:
    task_graph = graph()
    queries = query_set(task_graph)
    candidates = candidate_set(queries)
    document_set = documents()
    evidence_set = evidence_value(document_set)

    value = ResearchWorkspace(
        workspace_id="workspace-001",
        request=request(),
        task_graph=task_graph,
        query_set=queries,
        candidate_set=candidates,
        document_set=document_set,
        evidence_set=evidence_set,
        claim_set=ResearchClaimSet(
            request_id="research-001",
            evidence_set=evidence_set,
            claims=[],
        ),
    )

    with pytest.raises(
        ResearchSynthesisError,
        match=(
            "workspace must contain at least one claim"
        ),
    ):
        (
            DeterministicResearchSynthesizer()
            .synthesize(value)
        )


def test_synthesizer_rejects_blank_name() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        DeterministicResearchSynthesizer(
            name=" "
        )


def test_synthesis_is_deterministic() -> None:
    value = workspace()
    synthesizer = DeterministicResearchSynthesizer()

    first = synthesizer.synthesize(value)
    second = synthesizer.synthesize(value)

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )
