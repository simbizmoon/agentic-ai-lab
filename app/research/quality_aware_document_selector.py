"""Topic-relevant and diversity-aware research document selection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.schemas.research_search_query import ResearchSearchQuerySet
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)

_WORD_PATTERN = re.compile(r"[A-Za-z0-9가-힣]{3,}")
_CODE_MARKERS = (
    "authorization:",
    "api_key",
    "import ",
    "curl ",
    "requests.post",
    "client.responses",
    "functionname",
    "functionparameters",
)
_INDEX_MARKERS = (
    "## guides",
    "documentation index",
    "llms.txt",
    "table of contents",
)
_GENERIC_TERMS = {
    "official",
    "documentation",
    "overview",
    "explain",
    "using",
    "concise",
    "authoritative",
    "evidence",
}


@dataclass(frozen=True)
class ResearchDocumentSelection:
    """Selected documents and their matching quality evaluations."""

    document_set: ResearchSourceDocumentSet
    evaluations: list[ResearchSourceQualityEvaluation]


@dataclass(frozen=True)
class _ScoredDocument:
    evaluation: ResearchSourceQualityEvaluation
    document: ResearchSourceDocument
    base_score: float
    relevance_score: float
    usefulness_score: float
    provider_score: float
    tokens: frozenset[str]


class QualityAwareDocumentSelector:
    """Select authoritative, relevant, and nonredundant documents."""

    def __init__(
        self,
        *,
        maximum_documents: int,
        redundancy_weight: float = 0.25,
        maximum_quality_gap: float = 0.12,
    ) -> None:
        if maximum_documents < 1:
            raise ValueError(
                "maximum_documents must be greater than zero"
            )
        if not 0 <= redundancy_weight <= 1:
            raise ValueError(
                "redundancy_weight must be between zero and one"
            )
        if not 0 <= maximum_quality_gap <= 1:
            raise ValueError(
                "maximum_quality_gap must be between zero and one"
            )

        self._maximum_documents = maximum_documents
        self._redundancy_weight = redundancy_weight
        self._maximum_quality_gap = maximum_quality_gap

    @property
    def maximum_documents(self) -> int:
        """Return the final readable-document limit."""

        return self._maximum_documents

    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        """Evaluate readable documents and select the configured maximum."""

        ranked = self.rank(
            document_set=document_set,
            evaluator=evaluator,
            query_set=query_set,
        )
        return ResearchDocumentSelection(
            document_set=ResearchSourceDocumentSet(
                request_id=ranked.document_set.request_id,
                documents=ranked.document_set.documents[
                    : self._maximum_documents
                ],
            ),
            evaluations=ranked.evaluations[
                : self._maximum_documents
            ],
        )

    def rank(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        """Return all quality-eligible documents in selection order."""

        query_text_by_id = {
            query.query_id: query.query_text
            for query in (
                query_set.queries
                if query_set is not None
                else []
            )
        }

        scored = [
            self._score_document(
                document=document,
                evaluation=evaluator.evaluate(document),
                query_text=query_text_by_id.get(
                    document.candidate.query_id,
                    "",
                ),
            )
            for document in document_set.successful_documents()
        ]

        eligible = self._eligible_documents(scored)
        selected: list[_ScoredDocument] = []
        remaining = list(eligible)

        while remaining:
            best = min(
                remaining,
                key=lambda item: self._selection_key(
                    item=item,
                    selected=selected,
                ),
            )
            selected.append(best)
            remaining.remove(best)

        return ResearchDocumentSelection(
            document_set=ResearchSourceDocumentSet(
                request_id=document_set.request_id,
                documents=[
                    item.document
                    for item in selected
                ],
            ),
            evaluations=[
                item.evaluation.model_copy(
                    update={
                        "metadata": {
                            **item.evaluation.metadata,
                            "selection_base_score": (
                                f"{item.base_score:.6f}"
                            ),
                            "selection_relevance_score": (
                                f"{item.relevance_score:.6f}"
                            ),
                            "selection_usefulness_score": (
                                f"{item.usefulness_score:.6f}"
                            ),
                        }
                    }
                )
                for item in selected
            ],
        )

    def _eligible_documents(
        self,
        scored: list[_ScoredDocument],
    ) -> list[_ScoredDocument]:
        if not scored:
            return []

        highest_quality = max(
            item.evaluation.overall_score
            for item in scored
        )
        threshold = max(
            0.0,
            highest_quality - self._maximum_quality_gap,
        )
        eligible = [
            item
            for item in scored
            if item.evaluation.overall_score >= threshold
        ]

        if eligible:
            return eligible

        return [
            max(
                scored,
                key=lambda item: item.evaluation.overall_score,
            )
        ]

    def _score_document(
        self,
        *,
        document: ResearchSourceDocument,
        evaluation: ResearchSourceQualityEvaluation,
        query_text: str,
    ) -> _ScoredDocument:
        candidate = document.candidate
        parsed = urlsplit(candidate.url)
        path_text = parsed.path.replace("/", " ")
        path_tokens = frozenset(self._tokens(path_text))
        query_tokens = self._query_tokens(query_text)

        title_score = self._coverage(
            query_tokens,
            self._tokens(candidate.title),
        )
        snippet_score = self._coverage(
            query_tokens,
            self._tokens(candidate.snippet),
        )
        path_score = self._coverage(
            query_tokens,
            path_tokens,
        )
        body_score = self._coverage(
            query_tokens,
            self._tokens(document.content[:8_000]),
        )

        relevance = (
            0.40 * title_score
            + 0.25 * snippet_score
            + 0.20 * path_score
            + 0.15 * body_score
        )
        usefulness = self._usefulness(document.content)
        provider_score = self._provider_score(
            candidate.metadata.get("provider_score")
        )
        base_score = (
            0.40 * evaluation.overall_score
            + 0.38 * relevance
            + 0.12 * usefulness
            + 0.10 * provider_score
        )

        combined_text = " ".join(
            (
                candidate.title,
                candidate.snippet,
                path_text,
                document.content[:4_000],
            )
        )

        return _ScoredDocument(
            evaluation=evaluation,
            document=document,
            base_score=base_score,
            relevance_score=relevance,
            usefulness_score=usefulness,
            provider_score=provider_score,
            tokens=frozenset(self._tokens(combined_text)),
        )

    def _selection_key(
        self,
        *,
        item: _ScoredDocument,
        selected: list[_ScoredDocument],
    ) -> tuple[float, float, float, float, int, str]:
        redundancy = max(
            (
                self._jaccard(item.tokens, prior.tokens)
                for prior in selected
            ),
            default=0.0,
        )
        adjusted = (
            item.base_score
            - self._redundancy_weight * redundancy
        )
        candidate = item.document.candidate

        return (
            -adjusted,
            -item.relevance_score,
            -item.evaluation.overall_score,
            -item.provider_score,
            candidate.rank,
            candidate.source_id,
        )

    @staticmethod
    def _query_tokens(text: str) -> set[str]:
        return {
            token
            for token in QualityAwareDocumentSelector._tokens(text)
            if token not in _GENERIC_TERMS
        }

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            match.group(0)
            for match in _WORD_PATTERN.finditer(text.casefold())
        }

    @staticmethod
    def _coverage(
        query_tokens: set[str],
        candidate_tokens: set[str] | frozenset[str],
    ) -> float:
        if not query_tokens:
            return 0.0
        return len(query_tokens & set(candidate_tokens)) / len(query_tokens)

    @staticmethod
    def _provider_score(raw: str | None) -> float:
        if raw is None:
            return 0.0
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            return 0.0

    @staticmethod
    def _usefulness(content: str) -> float:
        normalized = content.casefold()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]
        link_like = sum(
            line.startswith(("-", "*", "[", "##"))
            or "http://" in line
            or "https://" in line
            for line in lines
        )
        link_ratio = link_like / max(1, len(lines))
        code_hits = sum(
            normalized.count(marker)
            for marker in _CODE_MARKERS
        )
        index_hits = sum(
            marker in normalized
            for marker in _INDEX_MARKERS
        )
        sentence_bonus = min(
            1.0,
            sum(
                normalized.count(mark)
                for mark in (".", "?", "!")
            )
            / 12,
        )
        penalty = min(
            0.75,
            0.45 * link_ratio
            + 0.06 * code_hits
            + 0.18 * index_hits,
        )
        return max(
            0.0,
            min(1.0, 0.55 + 0.45 * sentence_bonus - penalty),
        )

    @staticmethod
    def _jaccard(
        first: frozenset[str],
        second: frozenset[str],
    ) -> float:
        if not first or not second:
            return 0.0
        return len(first & second) / len(first | second)
