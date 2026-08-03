"""Run a small Korean semantic-search demonstration."""

from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

from app.rag.document_retriever import DocumentRetriever
from app.rag.in_memory_vector_store import InMemoryVectorStore
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)

DEFAULT_QUERY = "오랫동안 의자에 앉아 있으면 어떻게 알려 주나요?"


DOCUMENTS = [
    {
        "document_id": "seat-management",
        "text": (
            "착석 관리 장치는 사용자가 일정 시간 이상 의자에 "
            "앉아 있으면 진동, 표시등 또는 알림을 출력하여 "
            "사용자의 자세 변경이나 이석을 유도한다."
        ),
        "metadata": {
            "source": "seat-management.txt",
            "category": "behavior-management",
        },
    },
    {
        "document_id": "cooking",
        "text": (
            "김치찌개를 만들 때에는 김치와 돼지고기를 볶은 뒤 "
            "물을 넣고 충분한 시간 동안 끓인다."
        ),
        "metadata": {
            "source": "cooking.txt",
            "category": "food",
        },
    },
    {
        "document_id": "software",
        "text": (
            "파이썬은 반복 작업을 자동화하고 데이터를 처리하는 "
            "프로그램을 개발하는 데 사용할 수 있다."
        ),
        "metadata": {
            "source": "software.txt",
            "category": "technology",
        },
    },
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Index three Korean documents with OpenAI embeddings "
            "and run semantic search."
        )
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Korean semantic-search query.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of search results to return.",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=256,
        help="Embedding vector dimensions.",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Ensure the OpenAI API key is available."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured"
        )


def main() -> int:
    """Run the Korean semantic-search demonstration."""

    args = parse_args()

    try:
        validate_environment()

        if not args.query.strip():
            raise ValueError("query must not be blank")

        if args.top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

        if args.dimensions <= 0:
            raise ValueError(
                "dimensions must be greater than zero"
            )

        client = OpenAI()
        provider = OpenAIEmbeddingProvider(
            client=client,
            model_name="text-embedding-3-small",
            dimensions=args.dimensions,
        )
        retriever = DocumentRetriever(
            embedding_provider=provider,
            vector_store=InMemoryVectorStore(),
        )

        print("Indexing Korean documents...")

        for document in DOCUMENTS:
            result = retriever.index_document(
                document_id=document["document_id"],
                text=document["text"],
                metadata=document["metadata"],
                chunk_size=500,
                chunk_overlap=50,
            )

            print(
                f"- {result.document_id}: "
                f"{result.chunk_count} chunk(s)"
            )

        print()
        print(f"Query: {args.query}")
        print()

        results = retriever.retrieve(
            query=args.query,
            top_k=args.top_k,
        )

        if not results:
            print("No search results.")
            return 0

        print("Search results:")

        for result in results:
            source = result.chunk.metadata.get(
                "source",
                "unknown",
            )

            print(
                f"{result.rank}. "
                f"document_id={result.chunk.document_id}"
            )
            print(f"   score={result.score:.6f}")
            print(f"   source={source}")
            print(f"   text={result.chunk.text}")
            print()

        expected_document_id = "seat-management"
        actual_document_id = (
            results[0].chunk.document_id
        )

        if actual_document_id != expected_document_id:
            print(
                "WARNING: The expected seat-management document "
                "was not ranked first.",
                file=sys.stderr,
            )
            return 2

        print(
            "Semantic-search smoke test passed: "
            "seat-management ranked first."
        )
        return 0

    except (RuntimeError, ValueError) as exc:
        print(
            f"Semantic-search demo failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
