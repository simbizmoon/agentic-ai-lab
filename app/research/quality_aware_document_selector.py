"""Quality-aware selection of readable research documents."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)


@dataclass(frozen=True)
class ResearchDocumentSelection:
    """Selected documents and their matching quality evaluations."""

    document_set: ResearchSourceDocumentSet
    evaluations: list[ResearchSourceQualityEvaluation]


class QualityAwareDocumentSelector:
    """Select the strongest readable documents deterministically."""

    def __init__(self, *, maximum_documents: int) -> None:
        if maximum_documents < 1:
            raise ValueError(
                "maximum_documents must be greater than zero"
            )

        self._maximum_documents = maximum_documents

    @property
    def maximum_documents(self) -> int:
        """Return the final readable-document limit."""

        return self._maximum_documents

    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: object,
    ) -> ResearchDocumentSelection:
        """Evaluate readable documents and keep the strongest ones."""

        scored: list[
            tuple[
                ResearchSourceQualityEvaluation,
                ResearchSourceDocument,
            ]
        ] = []

        for document in document_set.successful_documents():
            evaluation = evaluator.evaluate(document)
            scored.append((evaluation, document))

        selected = sorted(
            scored,
            key=self._sort_key,
        )[: self._maximum_documents]

        return ResearchDocumentSelection(
            document_set=ResearchSourceDocumentSet(
                request_id=document_set.request_id,
                documents=[
                    document
                    for _, document in selected
                ],
            ),
            evaluations=[
                evaluation
                for evaluation, _ in selected
            ],
        )

    @staticmethod
    def _sort_key(
        item: tuple[
            ResearchSourceQualityEvaluation,
            ResearchSourceDocument,
        ],
    ) -> tuple[float, float, float, float, int, str]:
        evaluation, document = item
        candidate = document.candidate

        try:
            provider_score = float(
                candidate.metadata.get(
                    "provider_score",
                    "0",
                )
            )
        except ValueError:
            provider_score = 0.0

        return (
            -evaluation.overall_score,
            -evaluation.authority_score,
            -evaluation.primary_source_score,
            -provider_score,
            candidate.rank,
            candidate.source_id,
        )
