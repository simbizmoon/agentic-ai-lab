"""Source-universe-aware document ranking for Integrated Research."""

from __future__ import annotations

from app.research.quality_aware_document_selector import (
    QualityAwareDocumentSelector,
    ResearchDocumentSelection,
)
from app.schemas.research_search_query import ResearchSearchQuerySet
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import ResearchSourceQualityEvaluation


class _CachingQualityEvaluator:
    """Evaluate each document once across combined and per-origin rankings."""

    def __init__(self, evaluator: object) -> None:
        self._evaluator = evaluator
        self._cache: dict[str, ResearchSourceQualityEvaluation] = {}

    def evaluate(
        self, document: ResearchSourceDocument
    ) -> ResearchSourceQualityEvaluation:
        key = document.document_id.strip().casefold()
        if key not in self._cache:
            evaluate = self._evaluator.evaluate  # type: ignore[attr-defined]
            self._cache[key] = evaluate(document)
        return self._cache[key]


class IntegratedSourceDiversityDocumentSelector:
    """Give Web and Local documents a fair evidence-extraction opportunity."""

    def __init__(self, *, maximum_documents: int) -> None:
        if maximum_documents < 1:
            raise ValueError("maximum_documents must be greater than zero")
        self._maximum_documents = maximum_documents
        self._quality_selector = QualityAwareDocumentSelector(
            maximum_documents=maximum_documents
        )

    @property
    def maximum_documents(self) -> int:
        return self._maximum_documents

    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        ranked = self.rank(
            document_set=document_set,
            evaluator=evaluator,
            query_set=query_set,
        )
        return ResearchDocumentSelection(
            document_set=ResearchSourceDocumentSet(
                request_id=ranked.document_set.request_id,
                documents=ranked.document_set.documents[: self._maximum_documents],
            ),
            evaluations=ranked.evaluations[: self._maximum_documents],
        )

    def rank(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> ResearchDocumentSelection:
        readable = document_set.successful_documents()
        by_origin: dict[str, list[ResearchSourceDocument]] = {
            "web": [],
            "local": [],
        }
        for document in readable:
            origin = document.candidate.metadata.get("research_origin")
            if origin not in by_origin:
                raise ValueError(
                    "integrated document requires research_origin "
                    "metadata equal to web or local"
                )
            by_origin[origin].append(document)

        cached_evaluator = _CachingQualityEvaluator(evaluator)
        combined = self._quality_selector.rank(
            document_set=document_set,
            evaluator=cached_evaluator,
            query_set=query_set,
        )
        if (
            self._maximum_documents == 1
            or not by_origin["web"]
            or not by_origin["local"]
        ):
            return combined

        per_origin = {
            origin: self._quality_selector.rank(
                document_set=ResearchSourceDocumentSet(
                    request_id=document_set.request_id,
                    documents=documents,
                ),
                evaluator=cached_evaluator,
                query_set=query_set,
            )
            for origin, documents in by_origin.items()
        }
        ordered_documents: list[ResearchSourceDocument] = []
        ordered_evaluations: list[ResearchSourceQualityEvaluation] = []
        seen_document_ids: set[str] = set()

        def append_selection(selection: ResearchDocumentSelection) -> None:
            evaluation_by_id = {
                item.document.document_id.strip().casefold(): item
                for item in selection.evaluations
            }
            for document in selection.document_set.documents:
                key = document.document_id.strip().casefold()
                if key in seen_document_ids:
                    continue
                seen_document_ids.add(key)
                ordered_documents.append(document)
                ordered_evaluations.append(evaluation_by_id[key])

        append_selection(
            ResearchDocumentSelection(
                document_set=ResearchSourceDocumentSet(
                    request_id=document_set.request_id,
                    documents=per_origin["web"].document_set.documents[:1],
                ),
                evaluations=per_origin["web"].evaluations[:1],
            )
        )
        append_selection(
            ResearchDocumentSelection(
                document_set=ResearchSourceDocumentSet(
                    request_id=document_set.request_id,
                    documents=per_origin["local"].document_set.documents[:1],
                ),
                evaluations=per_origin["local"].evaluations[:1],
            )
        )
        append_selection(combined)

        return ResearchDocumentSelection(
            document_set=ResearchSourceDocumentSet(
                request_id=document_set.request_id,
                documents=ordered_documents,
            ),
            evaluations=ordered_evaluations,
        )
