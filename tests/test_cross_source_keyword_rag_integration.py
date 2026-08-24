"""Offline integration of cross-source chunks with keyword RAG retrieval."""

from __future__ import annotations

from app.rag.context_builder import build_rag_context
from app.research.cross_source_chunk_ingestion_runtime import (
    CrossSourceChunkIngestionRuntime,
)
from app.research.deterministic_keyword_retriever import (
    DeterministicKeywordRetriever,
)
from app.schemas.keyword_retrieval import KeywordRetrievalRequest
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


def _candidate(
    *,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="stage6-step3-request",
        task_id=f"task-{rank}",
        query_id=f"query-{rank}",
        title=f"Source {rank}",
        url=f"https://example.com/source-{rank}",
        source_type=source_type,
        rank=rank,
        status=ResearchSourceCandidateStatus.READ,
    )


def _read_document(
    *,
    document_id: str,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
    content: str,
) -> ResearchSourceDocument:
    return ResearchSourceDocument(
        document_id=document_id,
        candidate=_candidate(
            source_id=source_id,
            source_type=source_type,
            rank=rank,
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="offline-keyword-integration-fixture",
    )


def _document_set() -> ResearchSourceDocumentSet:
    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=_candidate(
            source_id="source-failed",
            source_type=ResearchSourceType.INDUSTRY,
            rank=3,
        ),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="offline-keyword-integration-fixture",
        error=ResearchSourceDocumentError(
            error_type="FixtureReadError",
            message="The fixture intentionally failed.",
            retryable=False,
        ),
    )
    return ResearchSourceDocumentSet(
        request_id="stage6-step3-request",
        documents=[
            _read_document(
                document_id="document-academic",
                source_id="source-academic",
                source_type=ResearchSourceType.ACADEMIC,
                rank=1,
                content=(
                    "Retrieval augmented generation combines retrieval with generation."
                ),
            ),
            _read_document(
                document_id="document-official",
                source_id="source-official",
                source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
                rank=2,
                content=(
                    "Official guidance requires citations to traceable source text."
                ),
            ),
            failed,
        ],
    )


def test_cross_source_chunks_flow_into_ranked_keyword_rag_context() -> None:
    document_set = _document_set()
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=document_set)
    response = DeterministicKeywordRetriever().search(
        chunks=ingestion.ordered_chunks(),
        request=KeywordRetrievalRequest(
            query="retrieval generation citations",
            top_k=2,
        ),
    )
    retrieval_results = [item.retrieval for item in response.matches]
    context = build_rag_context(retrieval_results)

    assert [item.chunk.document_id for item in retrieval_results] == [
        "document-academic",
        "document-official",
    ]
    assert [item.score for item in retrieval_results] == [0.666667, 0.333333]
    assert [item.rank for item in retrieval_results] == [1, 2]
    assert [item.explanation.matched_terms for item in response.matches] == [
        ["retrieval", "generation"],
        ["citations"],
    ]
    assert [item.document_id for item in context.citations] == [
        "document-academic",
        "document-official",
    ]
    assert "Retrieval augmented generation" in context.context_text
    assert "Official guidance requires citations" in context.context_text


def test_keyword_results_remain_traceable_to_exact_source_ranges() -> None:
    document_set = _document_set()
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=document_set)
    response = DeterministicKeywordRetriever().search(
        chunks=ingestion.ordered_chunks(),
        request=KeywordRetrievalRequest(query="traceable source"),
    )

    match = response.matches[0]
    chunk = match.retrieval.chunk
    document = next(
        item for item in document_set.documents if item.document_id == chunk.document_id
    )
    provenance = next(
        item for item in ingestion.provenance if item.chunk_id == chunk.chunk_id
    )
    context = build_rag_context([match.retrieval])
    citation = context.citations[0]

    assert chunk.metadata["source_id"] == "source-official"
    assert provenance.source_id == "source-official"
    assert provenance.source_type is ResearchSourceType.OFFICIAL_DOCUMENTATION
    assert provenance.document_id == "document-official"
    assert chunk.text == document.content[chunk.start_char : chunk.end_char]
    assert (provenance.start_character, provenance.end_character) == (
        chunk.start_char,
        chunk.end_char,
    )
    assert (citation.start_char, citation.end_char) == (
        chunk.start_char,
        chunk.end_char,
    )
    assert citation.document_id == provenance.document_id
    assert citation.chunk_id == provenance.chunk_id


def test_failed_document_never_enters_keyword_corpus_or_context() -> None:
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=_document_set())
    response = DeterministicKeywordRetriever().search(
        chunks=ingestion.ordered_chunks(),
        request=KeywordRetrievalRequest(query="fixture failed industry"),
    )
    context = build_rag_context([item.retrieval for item in response.matches])

    assert ingestion.failed_document_ids == ["document-failed"]
    assert response.corpus_chunk_count == 2
    assert response.matches == []
    assert context.context_text == ""
    assert context.citations == []


def test_complete_cross_source_keyword_run_is_deterministic() -> None:
    document_set = _document_set()

    def run_once() -> tuple[object, object]:
        ingestion = CrossSourceChunkIngestionRuntime(
            chunk_size=200,
            chunk_overlap=20,
        ).ingest(document_set=document_set)
        response = DeterministicKeywordRetriever().search(
            chunks=ingestion.ordered_chunks(),
            request=KeywordRetrievalRequest(
                query="retrieval generation citations",
                top_k=2,
            ),
        )
        context = build_rag_context([item.retrieval for item in response.matches])
        return response, context

    assert run_once() == run_once()
