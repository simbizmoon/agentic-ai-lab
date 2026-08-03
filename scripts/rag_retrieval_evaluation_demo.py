"""Run Korean retrieval evaluation with OpenAI embeddings."""

from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

from app.rag.document_retriever import DocumentRetriever
from app.rag.in_memory_vector_store import InMemoryVectorStore
from app.rag.korean_retrieval_evaluation_dataset import (
    build_korean_retrieval_evaluation_dataset,
)
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)
from app.rag.retrieval_evaluation_runner import (
    RetrievalEvaluationRunner,
    RetrievalEvaluationRunnerError,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Korean semantic retrieval using "
            "OpenAI embeddings."
        )
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model.",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=256,
        help="Embedding vector dimensions.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Maximum Chunk size in characters.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Character overlap for long Chunks.",
    )
    parser.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=1.0,
        help="Required evaluation pass rate.",
    )
    parser.add_argument(
        "--minimum-mrr",
        type=float,
        default=0.8,
        help="Required mean reciprocal rank.",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Ensure the OpenAI API key is configured."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured"
        )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""

    if not args.embedding_model.strip():
        raise ValueError(
            "embedding model must not be blank"
        )

    if args.dimensions <= 0:
        raise ValueError(
            "dimensions must be greater than zero"
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

    if not 0.0 <= args.minimum_pass_rate <= 1.0:
        raise ValueError(
            "minimum_pass_rate must be between zero and one"
        )

    if not 0.0 <= args.minimum_mrr <= 1.0:
        raise ValueError(
            "minimum_mrr must be between zero and one"
        )


def print_case_report(case: object) -> None:
    """Print one retrieval evaluation case."""

    print(f"Case: {case.case_id}")
    print(f"  query: {case.query}")
    print(
        "  expected: "
        f"{', '.join(case.expected_document_ids)}"
    )

    retrieved = (
        ", ".join(case.retrieved_document_ids)
        if case.retrieved_document_ids
        else "(none)"
    )
    matched = (
        ", ".join(case.matched_document_ids)
        if case.matched_document_ids
        else "(none)"
    )
    rank = (
        str(case.first_relevant_rank)
        if case.first_relevant_rank is not None
        else "(none)"
    )

    print(f"  retrieved: {retrieved}")
    print(f"  matched: {matched}")
    print(f"  first relevant rank: {rank}")
    print(f"  recall@k: {case.recall_at_k:.6f}")
    print(
        "  reciprocal rank: "
        f"{case.reciprocal_rank:.6f}"
    )
    print(
        "  passed: "
        f"{'yes' if case.passed else 'no'}"
    )
    print()


def main() -> int:
    """Run the OpenAI retrieval evaluation."""

    args = parse_args()

    try:
        validate_environment()
        validate_args(args)

        client = OpenAI()
        embedding_provider = OpenAIEmbeddingProvider(
            client=client,
            model_name=args.embedding_model,
            dimensions=args.dimensions,
        )
        retriever = DocumentRetriever(
            embedding_provider=embedding_provider,
            vector_store=InMemoryVectorStore(),
        )
        runner = RetrievalEvaluationRunner(
            retriever=retriever,
        )
        dataset = (
            build_korean_retrieval_evaluation_dataset()
        )

        print(
            "Running Korean retrieval evaluation..."
        )
        print(f"Dataset: {dataset.dataset_id}")
        print(
            f"Embedding model: {args.embedding_model}"
        )
        print(
            f"Embedding dimensions: {args.dimensions}"
        )
        print()

        result = runner.run(
            dataset=dataset,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        print(
            "Indexing summary:"
        )
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

        print("Aggregate metrics:")
        print(
            "  cases: "
            f"{result.summary.case_count}"
        )
        print(
            "  passed: "
            f"{result.summary.passed_count}"
        )
        print(
            "  pass rate: "
            f"{result.summary.pass_rate:.6f}"
        )
        print(
            "  mean recall@k: "
            f"{result.summary.mean_recall_at_k:.6f}"
        )
        print(
            "  MRR: "
            f"{result.summary.mean_reciprocal_rank:.6f}"
        )

        pass_rate_ok = (
            result.summary.pass_rate
            >= args.minimum_pass_rate
        )
        mrr_ok = (
            result.summary.mean_reciprocal_rank
            >= args.minimum_mrr
        )

        print()
        print(
            "Required pass rate: "
            f"{args.minimum_pass_rate:.6f}"
        )
        print(
            "Required MRR: "
            f"{args.minimum_mrr:.6f}"
        )

        if not pass_rate_ok or not mrr_ok:
            print(
                "Retrieval evaluation failed required thresholds.",
                file=sys.stderr,
            )
            return 2

        print(
            "OpenAI retrieval evaluation passed."
        )
        return 0

    except (
        RetrievalEvaluationRunnerError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"Retrieval evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
