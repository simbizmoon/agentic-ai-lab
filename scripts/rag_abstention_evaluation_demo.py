"""Run Korean RAG abstention evaluation with OpenAI."""

from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

from app.rag.document_retriever import DocumentRetriever
from app.rag.in_memory_vector_store import InMemoryVectorStore
from app.rag.korean_rag_abstention_evaluation_dataset import (
    build_korean_rag_abstention_evaluation_dataset,
)
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)
from app.rag.question_answering_service import (
    RagQuestionAnsweringService,
)
from app.rag.rag_abstention_evaluation_runner import (
    RagAbstentionEvaluationRunner,
    RagAbstentionEvaluationRunnerError,
)
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.schemas.rag_abstention_evaluation import (
    RagAbstentionCaseEvaluation,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate whether Korean RAG answers abstain "
            "when relevant evidence is unavailable."
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
        help="OpenAI model used for grounded answers.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Maximum document chunk size.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Character overlap between chunks.",
    )
    parser.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=1.0,
        help="Required complete abstention pass rate.",
    )
    parser.add_argument(
        "--minimum-abstention-rate",
        type=float,
        default=1.0,
        help="Required explicit abstention detection rate.",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Ensure that the OpenAI API key exists."""

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
        name="minimum_abstention_rate",
        value=args.minimum_abstention_rate,
    )


def join_values(values: list[str]) -> str:
    """Return printable text for a string list."""

    return ", ".join(values) if values else "(none)"


def print_case_report(
    case: RagAbstentionCaseEvaluation,
) -> None:
    """Print one abstention evaluation result."""

    print(f"Case: {case.case_id}")
    print(f"  question: {case.question}")
    print(
        "  evidence documents: "
        f"{join_values(case.retrieved_document_ids)}"
    )
    print(
        "  cited IDs: "
        f"{join_values(case.cited_ids)}"
    )
    print(
        "  matched abstention markers: "
        f"{join_values(case.matched_markers)}"
    )
    print(
        "  no evidence: "
        f"{'yes' if case.no_evidence else 'no'}"
    )
    print(
        "  no citations: "
        f"{'yes' if case.no_citations else 'no'}"
    )
    print(
        "  abstention detected: "
        f"{'yes' if case.abstention_detected else 'no'}"
    )
    print(
        "  answer generated: "
        f"{'yes' if case.answer_generated else 'no'}"
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
    """Run the actual OpenAI abstention evaluation."""

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
        pipeline = RetrievalPipeline(
            retriever=retriever,
        )
        service = RagQuestionAnsweringService(
            client=client,
            model=args.answer_model,
            retrieval_pipeline=pipeline,
        )
        runner = RagAbstentionEvaluationRunner(
            service=service,
        )
        dataset = (
            build_korean_rag_abstention_evaluation_dataset()
        )

        print(
            "Running Korean RAG abstention evaluation..."
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
            "  answers generated: "
            f"{summary.answer_generated_count}"
        )
        print(
            "  no-evidence cases: "
            f"{summary.no_evidence_count}"
        )
        print(
            "  no-citation cases: "
            f"{summary.no_citation_count}"
        )
        print(
            "  abstentions detected: "
            f"{summary.abstention_detected_count}"
        )
        print(
            "  pass rate: "
            f"{summary.pass_rate:.6f}"
        )
        print(
            "  abstention rate: "
            f"{summary.abstention_rate:.6f}"
        )
        print()

        print("Required thresholds:")
        print(
            "  minimum pass rate: "
            f"{args.minimum_pass_rate:.6f}"
        )
        print(
            "  minimum abstention rate: "
            f"{args.minimum_abstention_rate:.6f}"
        )
        print()

        thresholds_passed = all(
            (
                summary.pass_rate
                >= args.minimum_pass_rate,
                summary.abstention_rate
                >= args.minimum_abstention_rate,
            )
        )

        if not thresholds_passed:
            print(
                "RAG abstention evaluation failed "
                "required thresholds.",
                file=sys.stderr,
            )
            return 2

        print(
            "OpenAI RAG abstention evaluation passed."
        )
        return 0

    except (
        RagAbstentionEvaluationRunnerError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"RAG abstention evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
