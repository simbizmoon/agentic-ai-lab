"""Run end-to-end Korean RAG answer evaluation with OpenAI."""

from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

from app.rag.document_retriever import DocumentRetriever
from app.rag.in_memory_vector_store import InMemoryVectorStore
from app.rag.korean_rag_answer_evaluation_dataset import (
    build_korean_rag_answer_evaluation_dataset,
)
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)
from app.rag.question_answering_service import (
    RagQuestionAnsweringService,
)
from app.rag.rag_answer_evaluation_runner import (
    RagAnswerEvaluationRunner,
    RagAnswerEvaluationRunnerError,
)
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.schemas.rag_answer_evaluation_result import (
    RagAnswerCaseEvaluation,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Korean end-to-end RAG answers using "
            "OpenAI embeddings and the Responses API."
        )
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model.",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=256,
        help="Embedding vector dimensions.",
    )
    parser.add_argument(
        "--answer-model",
        default=os.getenv(
            "OPENAI_ANSWER_MODEL",
            "gpt-5-mini",
        ),
        help="OpenAI model used to generate grounded answers.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Maximum document chunk size in characters.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Character overlap between long chunks.",
    )
    parser.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=1.0,
        help="Required overall case pass rate.",
    )
    parser.add_argument(
        "--minimum-retrieval-pass-rate",
        type=float,
        default=1.0,
        help="Required retrieval pass rate.",
    )
    parser.add_argument(
        "--minimum-answer-generation-rate",
        type=float,
        default=1.0,
        help="Required successful answer-generation rate.",
    )
    parser.add_argument(
        "--minimum-citation-pass-rate",
        type=float,
        default=1.0,
        help="Required exact citation pass rate.",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Ensure the OpenAI API key is configured."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured"
        )


def validate_rate(
    *,
    name: str,
    value: float,
) -> None:
    """Validate one rate threshold."""

    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{name} must be between zero and one"
        )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""

    if not args.embedding_model.strip():
        raise ValueError(
            "embedding_model must not be blank"
        )

    if not args.answer_model.strip():
        raise ValueError(
            "answer_model must not be blank"
        )

    if args.embedding_dimensions <= 0:
        raise ValueError(
            "embedding_dimensions must be greater than zero"
        )

    if args.chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero"
        )

    if args.chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap must not be negative"
        )

    if args.chunk_overlap >= args.chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    validate_rate(
        name="minimum_pass_rate",
        value=args.minimum_pass_rate,
    )
    validate_rate(
        name="minimum_retrieval_pass_rate",
        value=args.minimum_retrieval_pass_rate,
    )
    validate_rate(
        name="minimum_answer_generation_rate",
        value=args.minimum_answer_generation_rate,
    )
    validate_rate(
        name="minimum_citation_pass_rate",
        value=args.minimum_citation_pass_rate,
    )


def join_values(values: list[str]) -> str:
    """Return printable text for a string list."""

    return ", ".join(values) if values else "(none)"


def print_case_report(
    case: RagAnswerCaseEvaluation,
) -> None:
    """Print one end-to-end evaluation case."""

    print(f"Case: {case.case_id}")
    print(f"  question: {case.question}")
    print(
        "  expected documents: "
        f"{join_values(case.expected_document_ids)}"
    )
    print(
        "  retrieved documents: "
        f"{join_values(case.retrieved_document_ids)}"
    )
    print(
        "  matched documents: "
        f"{join_values(case.matched_document_ids)}"
    )
    print(
        "  expected citations: "
        f"{join_values(case.expected_citation_ids)}"
    )
    print(
        "  cited IDs: "
        f"{join_values(case.cited_ids)}"
    )
    print(
        "  retrieval passed: "
        f"{'yes' if case.retrieval_passed else 'no'}"
    )
    print(
        "  answer generated: "
        f"{'yes' if case.answer_generated else 'no'}"
    )
    print(
        "  citation precision: "
        f"{case.citation_evaluation.precision:.6f}"
    )
    print(
        "  citation recall: "
        f"{case.citation_evaluation.recall:.6f}"
    )
    print(
        "  citation passed: "
        f"{'yes' if case.citation_evaluation.passed else 'no'}"
    )
    print(
        "  case passed: "
        f"{'yes' if case.passed else 'no'}"
    )

    if case.answer_text is not None:
        print(f"  answer: {case.answer_text}")

    if case.error_code is not None:
        print(f"  error code: {case.error_code}")

    if case.error_message is not None:
        print(f"  error message: {case.error_message}")

    print()


def main() -> int:
    """Run the OpenAI end-to-end RAG evaluation."""

    args = parse_args()

    try:
        validate_environment()
        validate_args(args)

        client = OpenAI()

        embedding_provider = OpenAIEmbeddingProvider(
            client=client,
            model_name=args.embedding_model,
            dimensions=args.embedding_dimensions,
        )
        retriever = DocumentRetriever(
            embedding_provider=embedding_provider,
            vector_store=InMemoryVectorStore(),
        )
        retrieval_pipeline = RetrievalPipeline(
            retriever=retriever,
        )
        service = RagQuestionAnsweringService(
            client=client,
            model=args.answer_model,
            retrieval_pipeline=retrieval_pipeline,
        )
        runner = RagAnswerEvaluationRunner(
            service=service,
        )
        dataset = (
            build_korean_rag_answer_evaluation_dataset()
        )

        print(
            "Running Korean end-to-end RAG evaluation..."
        )
        print(f"Dataset: {dataset.dataset_id}")
        print(
            "Embedding model: "
            f"{args.embedding_model}"
        )
        print(
            "Embedding dimensions: "
            f"{args.embedding_dimensions}"
        )
        print(
            "Answer model: "
            f"{args.answer_model}"
        )
        print()

        result = runner.run(
            dataset=dataset,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        print("Indexing summary:")
        print(
            "  indexed documents: "
            f"{result.indexed_document_count}"
        )
        print(
            "  indexed chunks: "
            f"{result.indexed_chunk_count}"
        )
        print()

        print("Case results:")
        print()

        for case in result.summary.cases:
            print_case_report(case)

        summary = result.summary

        print("Aggregate metrics:")
        print(f"  cases: {summary.case_count}")
        print(f"  passed: {summary.passed_count}")
        print(
            "  retrieval passed: "
            f"{summary.retrieval_passed_count}"
        )
        print(
            "  answers generated: "
            f"{summary.answer_generated_count}"
        )
        print(
            "  citations passed: "
            f"{summary.citation_passed_count}"
        )
        print(
            "  overall pass rate: "
            f"{summary.pass_rate:.6f}"
        )
        print(
            "  retrieval pass rate: "
            f"{summary.retrieval_pass_rate:.6f}"
        )
        print(
            "  answer generation rate: "
            f"{summary.answer_generation_rate:.6f}"
        )
        print(
            "  citation pass rate: "
            f"{summary.citation_pass_rate:.6f}"
        )
        print(
            "  mean citation precision: "
            f"{summary.mean_citation_precision:.6f}"
        )
        print(
            "  mean citation recall: "
            f"{summary.mean_citation_recall:.6f}"
        )
        print()

        print("Required thresholds:")
        print(
            "  overall pass rate: "
            f"{args.minimum_pass_rate:.6f}"
        )
        print(
            "  retrieval pass rate: "
            f"{args.minimum_retrieval_pass_rate:.6f}"
        )
        print(
            "  answer generation rate: "
            f"{args.minimum_answer_generation_rate:.6f}"
        )
        print(
            "  citation pass rate: "
            f"{args.minimum_citation_pass_rate:.6f}"
        )

        thresholds_passed = all(
            (
                summary.pass_rate
                >= args.minimum_pass_rate,
                summary.retrieval_pass_rate
                >= args.minimum_retrieval_pass_rate,
                summary.answer_generation_rate
                >= args.minimum_answer_generation_rate,
                summary.citation_pass_rate
                >= args.minimum_citation_pass_rate,
            )
        )

        print()

        if not thresholds_passed:
            print(
                "End-to-end RAG evaluation failed "
                "required thresholds.",
                file=sys.stderr,
            )
            return 2

        print(
            "OpenAI end-to-end RAG evaluation passed."
        )
        return 0

    except (
        RagAnswerEvaluationRunnerError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"End-to-end RAG evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
