"""Deterministic keyword relevance scoring for memories."""

from __future__ import annotations

from dataclasses import dataclass

from app.memory.memory_tokenizer import (
    normalize_search_text,
    tokenize_memory_text,
)
from app.schemas.memory_record import MemoryRecord
from app.schemas.memory_search_result import (
    MemoryScoreBreakdown,
)


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    """Internal result of scoring one memory."""

    score: float
    matched_terms: list[str]
    breakdown: MemoryScoreBreakdown


class MemoryRelevanceScorer:
    """Calculate deterministic keyword relevance scores."""

    CONTENT_WEIGHT = 0.55
    TAG_WEIGHT = 0.20
    PHRASE_WEIGHT = 0.10
    IMPORTANCE_WEIGHT = 0.10
    CONFIDENCE_WEIGHT = 0.05

    def score(
        self,
        *,
        query: str,
        memory: MemoryRecord,
    ) -> ScoredMemory:
        """Calculate relevance between one query and memory."""

        normalized_query = normalize_search_text(query)
        normalized_content = normalize_search_text(
            memory.content
        )

        query_tokens = set(
            tokenize_memory_text(query)
        )
        content_tokens = set(
            tokenize_memory_text(memory.content)
        )
        tag_tokens = {
            token
            for tag in memory.tags
            for token in tokenize_memory_text(tag)
        }

        if not query_tokens:
            content_overlap = 0.0
            tag_overlap = 0.0
            matched_terms: list[str] = []
        else:
            content_matches = (
                query_tokens & content_tokens
            )
            tag_matches = query_tokens & tag_tokens
            all_matches = content_matches | tag_matches

            content_overlap = (
                len(content_matches)
                / len(query_tokens)
            )
            tag_overlap = (
                len(tag_matches)
                / len(query_tokens)
            )
            matched_terms = sorted(all_matches)

        phrase_match = float(
            normalized_query in normalized_content
        )

        breakdown = MemoryScoreBreakdown(
            content_overlap=content_overlap,
            tag_overlap=tag_overlap,
            phrase_match=phrase_match,
            importance=memory.importance,
            confidence=memory.confidence,
        )

        score = (
            content_overlap * self.CONTENT_WEIGHT
            + tag_overlap * self.TAG_WEIGHT
            + phrase_match * self.PHRASE_WEIGHT
            + memory.importance
            * self.IMPORTANCE_WEIGHT
            + memory.confidence
            * self.CONFIDENCE_WEIGHT
        )

        return ScoredMemory(
            score=min(round(score, 6), 1.0),
            matched_terms=matched_terms,
            breakdown=breakdown,
        )
