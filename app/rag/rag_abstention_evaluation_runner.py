"""Run RAG insufficient-evidence evaluation cases."""

from __future__ import annotations

from app.rag.abstention_evaluator import (
    find_abstention_markers,
)
from app.rag.question_answering_service import (
    RagQuestionAnsweringError,
    RagQuestionAnsweringService,
)
from app.schemas.rag_abstention_evaluation import (
    RagAbstentionCaseEvaluation,
    RagAbstentionEvaluationCase,
    RagAbstentionEvaluationSummary,
)
from app.schemas.rag_abstention_evaluation_dataset import (
    RagAbstentionEvaluationDataset,
)
from app.schemas.rag_abstention_evaluation_run import (
    RagAbstentionEvaluationRunResult,
)


class RagAbstentionEvaluationRunnerError(RuntimeError):
    """Raised when an abstention evaluation cannot start."""


class RagAbstentionEvaluationRunner:
    """Evaluate whether RAG abstains without relevant evidence."""

    def __init__(
        self,
        *,
        service: RagQuestionAnsweringService,
    ) -> None:
        self._service = service

    @property
    def service(self) -> RagQuestionAnsweringService:
        """Return the configured question-answering service."""

        return self._service

    def run(
        self,
        *,
        dataset: RagAbstentionEvaluationDataset,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> RagAbstentionEvaluationRunResult:
        """Index documents and evaluate all abstention cases."""

        if chunk_size <= 0:
            raise RagAbstentionEvaluationRunnerError(
                "chunk_size must be greater than zero"
            )

        if chunk_overlap < 0:
            raise RagAbstentionEvaluationRunnerError(
                "chunk_overlap must not be negative"
            )

        if chunk_overlap >= chunk_size:
            raise RagAbstentionEvaluationRunnerError(
                "chunk_overlap must be smaller than chunk_size"
            )

        retriever = (
            self.service.retrieval_pipeline.retriever
        )
        retriever.clear()

        indexed_chunk_count = 0

        for document in dataset.documents:
            index_result = retriever.index_document(
                document_id=document.document_id,
                text=document.text,
                metadata=document.metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            indexed_chunk_count += index_result.chunk_count

        case_results = [
            self._evaluate_case(case)
            for case in dataset.cases
        ]

        return RagAbstentionEvaluationRunResult(
            dataset_id=dataset.dataset_id,
            indexed_document_count=len(dataset.documents),
            indexed_chunk_count=indexed_chunk_count,
            embedding_model=(
                retriever.embedding_provider.model_name
            ),
            embedding_dimensions=(
                retriever.embedding_provider.dimensions
            ),
            answer_model=self.service.model,
            summary=self._summarize(case_results),
        )

    def _evaluate_case(
        self,
        case: RagAbstentionEvaluationCase,
    ) -> RagAbstentionCaseEvaluation:
        """Evaluate one expected-abstention question."""

        try:
            result = self.service.answer_question(
                question=case.question,
                top_k=case.top_k,
                minimum_score=case.minimum_score,
            )
        except RagQuestionAnsweringError as exc:
            return RagAbstentionCaseEvaluation(
                case_id=case.case_id,
                question=case.question,
                retrieved_document_ids=[],
                cited_ids=[],
                answer_text=None,
                matched_markers=[],
                no_evidence=False,
                no_citations=True,
                abstention_detected=False,
                answer_generated=False,
                error_code=exc.code,
                error_message=exc.safe_message,
                passed=False,
            )

        retrieved_document_ids = list(
            dict.fromkeys(
                citation.document_id
                for citation in result.retrieval.context.citations
            )
        )
        cited_ids = result.answer.cited_ids
        answer_text = result.answer.answer

        matched_markers = find_abstention_markers(
            answer_text=answer_text,
            markers=case.expected_markers,
        )

        no_evidence = not retrieved_document_ids
        no_citations = not cited_ids
        abstention_detected = bool(matched_markers)

        return RagAbstentionCaseEvaluation(
            case_id=case.case_id,
            question=case.question,
            retrieved_document_ids=retrieved_document_ids,
            cited_ids=cited_ids,
            answer_text=answer_text,
            matched_markers=matched_markers,
            no_evidence=no_evidence,
            no_citations=no_citations,
            abstention_detected=abstention_detected,
            answer_generated=True,
            error_code=None,
            error_message=None,
            passed=(
                no_evidence
                and no_citations
                and abstention_detected
            ),
        )

    @staticmethod
    def _summarize(
        cases: list[RagAbstentionCaseEvaluation],
    ) -> RagAbstentionEvaluationSummary:
        """Calculate aggregate abstention metrics."""

        case_count = len(cases)

        if case_count == 0:
            return RagAbstentionEvaluationSummary(
                cases=[],
                case_count=0,
                passed_count=0,
                answer_generated_count=0,
                no_evidence_count=0,
                no_citation_count=0,
                abstention_detected_count=0,
                pass_rate=0.0,
                abstention_rate=0.0,
            )

        passed_count = sum(
            case.passed for case in cases
        )
        answer_generated_count = sum(
            case.answer_generated for case in cases
        )
        no_evidence_count = sum(
            case.no_evidence for case in cases
        )
        no_citation_count = sum(
            case.no_citations for case in cases
        )
        abstention_detected_count = sum(
            case.abstention_detected for case in cases
        )

        return RagAbstentionEvaluationSummary(
            cases=cases,
            case_count=case_count,
            passed_count=passed_count,
            answer_generated_count=answer_generated_count,
            no_evidence_count=no_evidence_count,
            no_citation_count=no_citation_count,
            abstention_detected_count=(
                abstention_detected_count
            ),
            pass_rate=passed_count / case_count,
            abstention_rate=(
                abstention_detected_count / case_count
            ),
        )
