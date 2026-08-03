"""Run end-to-end RAG answer evaluation datasets."""

from __future__ import annotations

from app.rag.citation_evaluator import evaluate_citations
from app.rag.question_answering_service import (
    RagQuestionAnsweringError,
    RagQuestionAnsweringService,
)
from app.schemas.rag_answer_evaluation_dataset import (
    RagAnswerEvaluationDataset,
)
from app.schemas.rag_answer_evaluation_result import (
    RagAnswerCaseEvaluation,
    RagAnswerEvaluationSummary,
)
from app.schemas.rag_answer_evaluation_run import (
    RagAnswerEvaluationRunResult,
)


class RagAnswerEvaluationRunnerError(RuntimeError):
    """Raised when an end-to-end evaluation run cannot start."""


class RagAnswerEvaluationRunner:
    """Index documents and evaluate multiple grounded answers."""

    def __init__(
        self,
        *,
        service: RagQuestionAnsweringService,
    ) -> None:
        self._service = service

    @property
    def service(self) -> RagQuestionAnsweringService:
        """Return the configured RAG QA service."""

        return self._service

    def run(
        self,
        *,
        dataset: RagAnswerEvaluationDataset,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> RagAnswerEvaluationRunResult:
        """Run all end-to-end answer evaluation cases."""

        if chunk_size <= 0:
            raise RagAnswerEvaluationRunnerError(
                "chunk_size must be greater than zero"
            )

        if chunk_overlap < 0:
            raise RagAnswerEvaluationRunnerError(
                "chunk_overlap must not be negative"
            )

        if chunk_overlap >= chunk_size:
            raise RagAnswerEvaluationRunnerError(
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

        case_evaluations = [
            self._evaluate_case(case)
            for case in dataset.cases
        ]

        summary = self._summarize(case_evaluations)

        return RagAnswerEvaluationRunResult(
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
            summary=summary,
        )

    def _evaluate_case(
        self,
        case: object,
    ) -> RagAnswerCaseEvaluation:
        """Evaluate one end-to-end RAG case."""

        try:
            result = self.service.answer_question(
                question=case.question,
                top_k=case.top_k,
                minimum_score=case.minimum_score,
            )
        except RagQuestionAnsweringError as exc:
            return RagAnswerCaseEvaluation(
                case_id=case.case_id,
                question=case.question,
                expected_document_ids=(
                    case.expected_document_ids
                ),
                retrieved_document_ids=[],
                matched_document_ids=[],
                expected_citation_ids=[],
                cited_ids=[],
                retrieval_passed=False,
                answer_generated=False,
                citation_evaluation=evaluate_citations(
                    expected_citation_ids=[],
                    cited_ids=[],
                ),
                answer_text=None,
                error_code=exc.code,
                error_message=exc.safe_message,
                passed=False,
            )

        retrieved_document_ids = [
            item.chunk.document_id
            for item in result.retrieval.results
        ]
        expected_document_set = set(
            case.expected_document_ids
        )
        matched_document_ids = list(
            dict.fromkeys(
                document_id
                for document_id in retrieved_document_ids
                if document_id in expected_document_set
            )
        )

        expected_citation_ids = [
            citation.citation_id
            for citation in result.retrieval.context.citations
            if citation.document_id in expected_document_set
        ]

        citation_evaluation = evaluate_citations(
            expected_citation_ids=expected_citation_ids,
            cited_ids=result.answer.cited_ids,
        )
        retrieval_passed = bool(matched_document_ids)

        return RagAnswerCaseEvaluation(
            case_id=case.case_id,
            question=case.question,
            expected_document_ids=case.expected_document_ids,
            retrieved_document_ids=retrieved_document_ids,
            matched_document_ids=matched_document_ids,
            expected_citation_ids=expected_citation_ids,
            cited_ids=result.answer.cited_ids,
            retrieval_passed=retrieval_passed,
            answer_generated=True,
            citation_evaluation=citation_evaluation,
            answer_text=result.answer.answer,
            error_code=None,
            error_message=None,
            passed=(
                retrieval_passed
                and citation_evaluation.passed
            ),
        )

    @staticmethod
    def _summarize(
        cases: list[RagAnswerCaseEvaluation],
    ) -> RagAnswerEvaluationSummary:
        """Calculate aggregate end-to-end metrics."""

        case_count = len(cases)

        if case_count == 0:
            return RagAnswerEvaluationSummary(
                cases=[],
                case_count=0,
                passed_count=0,
                retrieval_passed_count=0,
                answer_generated_count=0,
                citation_passed_count=0,
                pass_rate=0.0,
                retrieval_pass_rate=0.0,
                answer_generation_rate=0.0,
                citation_pass_rate=0.0,
                mean_citation_precision=0.0,
                mean_citation_recall=0.0,
            )

        passed_count = sum(
            case.passed for case in cases
        )
        retrieval_passed_count = sum(
            case.retrieval_passed for case in cases
        )
        answer_generated_count = sum(
            case.answer_generated for case in cases
        )
        citation_passed_count = sum(
            case.citation_evaluation.passed
            for case in cases
        )

        return RagAnswerEvaluationSummary(
            cases=cases,
            case_count=case_count,
            passed_count=passed_count,
            retrieval_passed_count=(
                retrieval_passed_count
            ),
            answer_generated_count=(
                answer_generated_count
            ),
            citation_passed_count=(
                citation_passed_count
            ),
            pass_rate=passed_count / case_count,
            retrieval_pass_rate=(
                retrieval_passed_count / case_count
            ),
            answer_generation_rate=(
                answer_generated_count / case_count
            ),
            citation_pass_rate=(
                citation_passed_count / case_count
            ),
            mean_citation_precision=(
                sum(
                    case.citation_evaluation.precision
                    for case in cases
                )
                / case_count
            ),
            mean_citation_recall=(
                sum(
                    case.citation_evaluation.recall
                    for case in cases
                )
                / case_count
            ),
        )
