"""Tests for semantic-aware research evidence extraction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.budget import ExecutionBudget
from app.rag.embedding_provider import EmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
)
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)
from app.services.text_generation import TokenUsage


class ControlledEmbeddingProvider(EmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "controlled"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=2,
                vector=self._vector(text),
            )
            for text in texts
        ]

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        if "execution" in normalized or "callable" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]


@dataclass
class ControlledEvaluator:
    judgments: dict[str, EvidenceRelevanceLevel]

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        level = self.judgments[evidence_excerpt]
        score = {
            EvidenceRelevanceLevel.DIRECTLY_RELEVANT: 0.9,
            EvidenceRelevanceLevel.PARTIALLY_RELEVANT: 0.5,
            EvidenceRelevanceLevel.IRRELEVANT: 0.1,
        }[level]
        return EvidenceRelevanceEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=level,
                relevance_score=score,
                rationale=f"Controlled {level.value} rationale.",
                issues=[],
            ),
            response_id=f"resp-{level.value}",
            request_id=f"req-{level.value}",
            usage=TokenUsage(
                input_tokens=9,
                cached_input_tokens=0,
                output_tokens=1,
                reasoning_tokens=0,
                total_tokens=10,
            ),
            elapsed_seconds=0.1,
        )


def document(content: str) -> ResearchSourceDocument:
    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        url="https://example.com/doc",
        title="Example",
        source_type=ResearchSourceType.ACADEMIC,
        snippet="Example source",
        rank=1,
        metadata={
            "search_query_text": (
                "OpenAI Agents SDK tool calling mechanism"
            )
        },
    )
    return ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        sections=[],
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
        metadata={},
    )


def build_extractor(
    evaluator: ControlledEvaluator,
    *,
    maximum_evidence: int = 3,
    max_attempts: int = 8,
) -> SemanticResearchEvidenceExtractor:
    return SemanticResearchEvidenceExtractor(
        question="How does an agent invoke tools?",
        objective="Explain callable invocation during execution.",
        paragraph_extractor=ParagraphEvidenceExtractor(
            maximum_evidence=1,
            minimum_characters=40,
            minimum_score=0.22,
        ),
        shortlister=EmbeddingSemanticEvidenceShortlister(
            embedding_provider=ControlledEmbeddingProvider(),
            maximum_candidates=8,
        ),
        reranker=SemanticEvidenceReranker(
            evaluator=evaluator,
            budget=ExecutionBudget(
                max_attempts=max_attempts,
                max_recorded_tokens=8_000,
                max_elapsed_seconds=60.0,
            ),
        ),
        maximum_evidence=maximum_evidence,
    )


def test_semantic_extractor_promotes_low_lexical_answer_bearing_passage() -> None:
    lexical = (
        "OpenAI Agents SDK tool calling mechanism overview uses the "
        "exact search terminology but only discusses product positioning."
    )
    semantic = (
        "A callable capability can be selected during execution and "
        "invoked by the runtime even though this paragraph uses different "
        "words from the originating search query."
    )
    content = f"{lexical}\n\n{semantic}"

    extractor = build_extractor(
        ControlledEvaluator(
            {
                lexical: EvidenceRelevanceLevel.IRRELEVANT,
                semantic: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            }
        ),
        maximum_evidence=1,
    )

    result = extractor.extract(document(content))

    assert result.status is ResearchEvidenceExtractionStatus.SUCCEEDED
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.excerpt == semantic
    assert evidence.relevance_score == 0.9
    assert evidence.metadata["semantic_relevance_level"] == (
        "directly_relevant"
    )
    assert float(evidence.metadata["lexical_score"]) < 0.22


def test_semantic_extractor_preserves_character_provenance() -> None:
    first = (
        "Background material that is not the requested mechanism but "
        "is long enough to become a paragraph candidate."
    )
    second = (
        "A callable can be invoked during execution and returns a result "
        "to the runtime as part of the tool-use mechanism."
    )
    content = f"{first}\n\n{second}"
    expected_start = content.index(second)

    extractor = build_extractor(
        ControlledEvaluator(
            {
                first: EvidenceRelevanceLevel.IRRELEVANT,
                second: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            }
        ),
        maximum_evidence=1,
    )

    evidence = extractor.extract(document(content)).evidence[0]

    assert evidence.document_id == "document-001"
    assert evidence.source_id == "source-001"
    assert evidence.start_character == expected_start
    assert evidence.end_character == expected_start + len(second)
    assert content[
        evidence.start_character:evidence.end_character
    ] == evidence.excerpt


def test_budget_exhaustion_uses_one_unevaluated_fallback() -> None:
    first = (
        "Background paragraph with ordinary wording that will receive "
        "the one available semantic evaluation attempt."
    )
    second = (
        "A callable capability is invoked during execution using the "
        "runtime tool mechanism and should remain available if unevaluated."
    )
    content = f"{first}\n\n{second}"

    extractor = build_extractor(
        ControlledEvaluator(
            {
                second: EvidenceRelevanceLevel.IRRELEVANT,
            }
        ),
        maximum_evidence=2,
        max_attempts=1,
    )

    result = extractor.extract(document(content))

    assert len(result.evidence) == 1
    assert result.metadata["semantic_budget_exhausted"] == "true"
    assert (
        result.evidence[0].metadata["semantic_relevance_level"]
        == "unevaluated"
    )


def test_relevant_evidence_prevents_unevaluated_backfill() -> None:
    first = (
        "Background paragraph with ordinary wording that should remain "
        "unevaluated after the one semantic evaluation attempt."
    )
    second = (
        "A callable capability is invoked during execution using the "
        "runtime tool mechanism and directly answers the question."
    )
    content = f"{first}\n\n{second}"

    extractor = build_extractor(
        ControlledEvaluator(
            {
                second: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            }
        ),
        maximum_evidence=2,
        max_attempts=1,
    )

    result = extractor.extract(document(content))

    assert len(result.evidence) == 1
    assert result.metadata["semantic_budget_exhausted"] == "true"
    assert (
        result.evidence[0].metadata["semantic_relevance_level"]
        == "directly_relevant"
    )
    assert all(
        item.metadata["semantic_relevance_level"] != "unevaluated"
        for item in result.evidence
    )


def test_all_evaluated_irrelevant_returns_no_evidence() -> None:
    passage = (
        "This paragraph discusses unrelated pricing details and does not "
        "help answer the requested runtime mechanism."
    )
    extractor = build_extractor(
        ControlledEvaluator(
            {
                passage: EvidenceRelevanceLevel.IRRELEVANT,
            }
        ),
        maximum_evidence=1,
        max_attempts=8,
    )

    result = extractor.extract(document(passage))

    assert result.status is ResearchEvidenceExtractionStatus.NO_EVIDENCE
    assert result.evidence == []
    assert result.metadata["semantic_budget_exhausted"] == "false"


def test_empty_candidate_document_returns_no_evidence() -> None:
    extractor = build_extractor(ControlledEvaluator({}))

    result = extractor.extract(
        document("short")
    )

    assert result.status is ResearchEvidenceExtractionStatus.NO_EVIDENCE
    assert result.evidence == []
    assert result.metadata["candidate_chunk_count"] == "0"


def test_extractor_records_semantic_trace_metadata() -> None:
    passage = (
        "A callable capability is invoked during execution by the runtime "
        "and this passage directly explains the requested mechanism."
    )
    extractor = build_extractor(
        ControlledEvaluator(
            {
                passage: EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            }
        ),
        maximum_evidence=1,
    )

    evidence = extractor.extract(document(passage)).evidence[0]

    assert evidence.metadata["extractor"] == (
        "semantic-paragraph-live-document"
    )
    assert evidence.metadata["selection_rank"] == "1"
    assert evidence.metadata["embedding_rank"] == "1"
    assert evidence.metadata["semantic_evaluated"] == "true"
    assert evidence.metadata["semantic_response_id"].startswith("resp-")
    assert evidence.metadata["semantic_request_id"].startswith("req-")
