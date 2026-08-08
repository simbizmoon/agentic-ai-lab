"""Tests for embedding semantic evidence shortlisting."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.rag.embedding_provider import EmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceCandidate,
)
from app.schemas.document_embedding import TextEmbedding


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Return deterministic vectors based on marker words."""

    def __init__(self) -> None:
        self.seen_texts: list[str] = []

    @property
    def model_name(self) -> str:
        return "controlled-test-model"

    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        self.seen_texts = list(texts)
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=self._vector(text),
            )
            for text in texts
        ]

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()

        if "invoke" in normalized or "execution" in normalized:
            return [1.0, 0.0, 0.0]
        if "tool" in normalized or "callable" in normalized:
            return [0.9, 0.1, 0.0]
        if "agent loop" in normalized:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


def candidate(
    *,
    start: int,
    text: str,
    lexical_score: float,
) -> ParagraphEvidenceCandidate:
    return ParagraphEvidenceCandidate(
        start=start,
        end=start + len(text),
        text=text,
        lexical_score=lexical_score,
    )


def test_shortlist_uses_question_and_objective_in_query() -> None:
    provider = ControlledEmbeddingProvider()
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=provider,
    )

    shortlister.shortlist(
        question="How are tools exposed?",
        objective="Explain invocation during execution.",
        candidates=[
            candidate(
                start=0,
                text="A callable tool can be selected.",
                lexical_score=0.1,
            )
        ],
    )

    assert provider.seen_texts[0] == (
        "Question: How are tools exposed?\n"
        "Objective: Explain invocation during execution."
    )


def test_semantic_rank_can_promote_low_lexical_candidate() -> None:
    provider = ControlledEmbeddingProvider()
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=provider,
        maximum_candidates=2,
    )
    high_lexical_wrong = candidate(
        start=0,
        text="The agent loop is managed by the SDK.",
        lexical_score=0.95,
    )
    low_lexical_right = candidate(
        start=100,
        text="A callable can be invoked during execution.",
        lexical_score=0.05,
    )

    result = shortlister.shortlist(
        question="How does the agent invoke tools?",
        objective="Explain tool invocation during execution.",
        candidates=[
            high_lexical_wrong,
            low_lexical_right,
        ],
    )

    assert [item.candidate for item in result] == [
        low_lexical_right,
        high_lexical_wrong,
    ]
    assert result[0].semantic_score > result[1].semantic_score


def test_hybrid_rank_can_rescue_strong_lexical_candidate() -> None:
    class RankedEmbeddingProvider(EmbeddingProvider):
        @property
        def model_name(self) -> str:
            return "ranked-test-model"

        @property
        def dimensions(self) -> int:
            return 2

        def embed_texts(
            self,
            texts: Sequence[str],
        ) -> list[TextEmbedding]:
            vectors: list[list[float]] = []
            for text in texts:
                normalized = text.casefold()
                if text.startswith("Question:") or "semantic-a" in normalized:
                    vector = [1.0, 0.0]
                elif "semantic-b" in normalized:
                    vector = [0.98, 0.20]
                elif "semantic-c" in normalized:
                    vector = [0.94, 0.34]
                else:
                    vector = [0.0, 1.0]
                vectors.append(vector)

            return [
                TextEmbedding(
                    model_name=self.model_name,
                    dimensions=self.dimensions,
                    vector=vector,
                )
                for vector in vectors
            ]

    lexical_rescue = candidate(
        start=300,
        text="Lexical rescue passage with concrete function schema details.",
        lexical_score=0.99,
    )
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=RankedEmbeddingProvider(),
        maximum_candidates=2,
    )

    result = shortlister.shortlist(
        question="How are tools invoked?",
        objective="Explain execution.",
        candidates=[
            candidate(
                start=0,
                text="semantic-a general overview",
                lexical_score=0.10,
            ),
            candidate(
                start=100,
                text="semantic-b general overview",
                lexical_score=0.20,
            ),
            candidate(
                start=200,
                text="semantic-c general overview",
                lexical_score=0.30,
            ),
            lexical_rescue,
        ],
    )

    assert lexical_rescue in [item.candidate for item in result]


def test_shortlist_exposes_default_rrf_constant() -> None:
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=ControlledEmbeddingProvider(),
    )

    assert shortlister.rrf_k == 60


def test_shortlist_preserves_candidate_provenance() -> None:
    provider = ControlledEmbeddingProvider()
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=provider,
    )
    original = candidate(
        start=321,
        text="A callable can be invoked during execution.",
        lexical_score=0.08,
    )

    result = shortlister.shortlist(
        question="How are tools used?",
        objective="Explain invocation during execution.",
        candidates=[original],
    )

    assert len(result) == 1
    assert result[0].candidate is original
    assert result[0].candidate.start == 321
    assert result[0].candidate.end == original.end
    assert result[0].candidate.lexical_score == 0.08
    assert result[0].rank == 1


def test_shortlist_applies_maximum_candidates_without_threshold() -> None:
    provider = ControlledEmbeddingProvider()
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=provider,
        maximum_candidates=2,
    )

    result = shortlister.shortlist(
        question="How are tools invoked?",
        objective="Explain execution.",
        candidates=[
            candidate(
                start=0,
                text="A callable can be invoked during execution.",
                lexical_score=0.01,
            ),
            candidate(
                start=100,
                text="A tool is available to the agent.",
                lexical_score=0.02,
            ),
            candidate(
                start=200,
                text="Unrelated background material.",
                lexical_score=0.99,
            ),
        ],
    )

    assert len(result) == 2
    assert [item.rank for item in result] == [1, 2]


def test_shortlist_returns_empty_for_no_candidates() -> None:
    provider = ControlledEmbeddingProvider()
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=provider,
    )

    assert (
        shortlister.shortlist(
            question="Question",
            objective="Objective",
            candidates=[],
        )
        == []
    )
    assert provider.seen_texts == []


@pytest.mark.parametrize(
    ("question", "objective", "message"),
    [
        (" ", "Objective", "question must not be blank"),
        ("Question", " ", "objective must not be blank"),
    ],
)
def test_shortlist_rejects_blank_request_text(
    question: str,
    objective: str,
    message: str,
) -> None:
    shortlister = EmbeddingSemanticEvidenceShortlister(
        embedding_provider=ControlledEmbeddingProvider(),
    )

    with pytest.raises(ValueError, match=message):
        shortlister.shortlist(
            question=question,
            objective=objective,
            candidates=[
                candidate(
                    start=0,
                    text="candidate",
                    lexical_score=0.1,
                )
            ],
        )


def test_shortlister_rejects_invalid_rrf_k() -> None:
    with pytest.raises(
        ValueError,
        match="rrf_k must be greater than zero",
    ):
        EmbeddingSemanticEvidenceShortlister(
            embedding_provider=ControlledEmbeddingProvider(),
            rrf_k=0,
        )


def test_shortlister_rejects_invalid_maximum_candidates() -> None:
    with pytest.raises(
        ValueError,
        match="maximum_candidates must be greater than zero",
    ):
        EmbeddingSemanticEvidenceShortlister(
            embedding_provider=ControlledEmbeddingProvider(),
            maximum_candidates=0,
        )
