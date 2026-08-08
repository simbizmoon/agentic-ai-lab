"""Semantic-aware evidence extraction for live research documents."""

from __future__ import annotations

from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.research_evidence_extractor import ResearchEvidenceExtractor
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
    SemanticEvidenceRerankItem,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceLevel,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStance,
    ResearchEvidenceType,
)
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionResult,
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_source_document import ResearchSourceDocument


class SemanticResearchEvidenceExtractor(ResearchEvidenceExtractor):
    """Extract evidence using paragraph, embedding, and LLM relevance stages."""

    def __init__(
        self,
        *,
        question: str,
        objective: str,
        paragraph_extractor: ParagraphEvidenceExtractor,
        shortlister: EmbeddingSemanticEvidenceShortlister,
        reranker: SemanticEvidenceReranker,
        maximum_evidence: int = 3,
    ) -> None:
        if not question.strip():
            raise ValueError("question must not be blank")
        if not objective.strip():
            raise ValueError("objective must not be blank")
        if maximum_evidence < 1:
            raise ValueError(
                "maximum_evidence must be greater than zero"
            )

        self._question = question.strip()
        self._objective = objective.strip()
        self._paragraph_extractor = paragraph_extractor
        self._shortlister = shortlister
        self._reranker = reranker
        self._maximum_evidence = maximum_evidence

    @property
    def name(self) -> str:
        return "semantic-paragraph-live-document"

    @property
    def question(self) -> str:
        return self._question

    @property
    def objective(self) -> str:
        return self._objective

    def extract(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchEvidenceExtractionResult:
        candidates = self._paragraph_extractor.candidate_chunks(
            document
        )

        shortlist = self._shortlister.shortlist(
            question=self._question,
            objective=self._objective,
            candidates=candidates,
        )

        reranked = self._reranker.rerank(
            question=self._question,
            objective=self._objective,
            shortlist=shortlist,
        )

        selected = self._select_final_items(
            reranked.items,
            budget_exhausted=reranked.budget_exhausted,
        )

        evidence = [
            self._evidence(
                document=document,
                item=item,
                position=position,
            )
            for position, item in enumerate(
                selected,
                start=1,
            )
        ]

        return ResearchEvidenceExtractionResult(
            document=document,
            status=(
                ResearchEvidenceExtractionStatus.SUCCEEDED
                if evidence
                else ResearchEvidenceExtractionStatus.NO_EVIDENCE
            ),
            extractor=self.name,
            evidence=evidence,
            duration_ms=0,
            metadata={
                "mode": "semantic-paragraph-selection",
                "candidate_chunk_count": str(len(candidates)),
                "embedding_shortlist_count": str(len(shortlist)),
                "selected_chunk_count": str(len(evidence)),
                "semantic_budget_attempts": str(
                    reranked.usage.attempts
                ),
                "semantic_budget_recorded_tokens": str(
                    reranked.usage.recorded_tokens
                ),
                "semantic_budget_elapsed_seconds": str(
                    reranked.usage.elapsed_seconds
                ),
                "semantic_budget_exhausted": str(
                    reranked.budget_exhausted
                ).casefold(),
            },
        )

    def _select_final_items(
        self,
        items: list[SemanticEvidenceRerankItem],
        *,
        budget_exhausted: bool,
    ) -> list[SemanticEvidenceRerankItem]:
        """Select precision-first evidence after semantic reranking."""

        relevant = [
            item
            for item in items
            if item.judgment is not None
            and item.judgment.relevance_level
            in {
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            }
        ]

        if relevant:
            return relevant[: self._maximum_evidence]

        if budget_exhausted:
            unevaluated = [
                item
                for item in items
                if item.judgment is None
            ]
            return unevaluated[:1]

        return []

    def _evidence(
        self,
        *,
        document: ResearchSourceDocument,
        item: SemanticEvidenceRerankItem,
        position: int,
    ) -> ResearchEvidence:
        candidate = item.shortlist_item.candidate
        source = document.candidate

        return ResearchEvidence(
            evidence_id=(
                f"{document.document_id}-evidence-{position:03d}"
            ),
            request_id=source.request_id,
            task_id=source.task_id,
            source_id=source.source_id,
            document_id=document.document_id,
            excerpt=candidate.text,
            start_character=candidate.start,
            end_character=candidate.end,
            evidence_type=ResearchEvidenceType.FACT,
            stance=ResearchEvidenceStance.SUPPORTS,
            relevance_score=self._relevance_score(item),
            confidence_score=0.8,
            rationale=self._rationale(item),
            metadata={
                "extractor": self.name,
                "selection_rank": str(position),
                "embedding_rank": str(
                    item.shortlist_item.rank
                ),
                "embedding_score": str(
                    item.shortlist_item.semantic_score
                ),
                "lexical_score": str(
                    candidate.lexical_score
                ),
                "semantic_evaluated": str(
                    item.evaluated
                ).casefold(),
                **self._judgment_metadata(item),
            },
        )

    @staticmethod
    def _relevance_score(
        item: SemanticEvidenceRerankItem,
    ) -> float:
        if item.judgment is not None:
            return item.judgment.relevance_score

        return item.shortlist_item.candidate.lexical_score

    @staticmethod
    def _rationale(
        item: SemanticEvidenceRerankItem,
    ) -> str:
        if item.judgment is None:
            return (
                "Selected from the embedding shortlist without an LLM "
                "relevance judgment because the semantic evaluation "
                "budget was exhausted."
            )

        return item.judgment.rationale

    @staticmethod
    def _judgment_metadata(
        item: SemanticEvidenceRerankItem,
    ) -> dict[str, str]:
        judgment = item.judgment

        if judgment is None:
            return {
                "semantic_relevance_level": "unevaluated",
            }

        metadata = {
            "semantic_relevance_level": (
                judgment.relevance_level.value
            ),
            "semantic_relevance_score": str(
                judgment.relevance_score
            ),
        }

        if item.response_id is not None:
            metadata["semantic_response_id"] = item.response_id
        if item.request_id is not None:
            metadata["semantic_request_id"] = item.request_id

        if (
            judgment.relevance_level
            is EvidenceRelevanceLevel.IRRELEVANT
        ):
            metadata["semantic_irrelevant"] = "true"

        return metadata
