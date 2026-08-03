"""Run an end-to-end Korean RAG question-answering demo."""

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
from app.rag.question_answering_service import (
    RagQuestionAnsweringError,
    RagQuestionAnsweringService,
)
from app.rag.retrieval_pipeline import RetrievalPipeline

DEFAULT_QUESTION = (
    "사용자가 오랫동안 의자에 앉아 있으면 "
    "장치는 어떤 방식으로 행동 변화를 유도합니까?"
)


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
            "Index Korean documents, retrieve evidence, and "
            "generate a grounded answer."
        )
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="Question to answer from the indexed documents.",
    )
    parser.add_argument(
        "--answer-model",
        default=os.getenv(
            "OPENAI_ANSWER_MODEL",
            "gpt-5-mini",
        ),
        help="Responses API model used for answer generation.",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="Embedding model used for document retrieval.",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=256,
        help="Embedding vector dimensions.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=2,
        help="Number of document chunks to retrieve.",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Ensure the required API key is configured."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured"
        )


def main() -> int:
    """Run the complete Korean RAG workflow."""

    args = parse_args()

    try:
        validate_environment()

        if not args.question.strip():
            raise ValueError(
                "question must not be blank"
            )

        if not args.answer_model.strip():
            raise ValueError(
                "answer model must not be blank"
            )

        if args.dimensions <= 0:
            raise ValueError(
                "dimensions must be greater than zero"
            )

        if args.top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

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
        retrieval_pipeline = RetrievalPipeline(
            retriever=retriever,
        )
        service = RagQuestionAnsweringService(
            client=client,
            model=args.answer_model,
            retrieval_pipeline=retrieval_pipeline,
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
        print(f"Question: {args.question}")
        print()

        result = service.answer_question(
            question=args.question,
            top_k=args.top_k,
        )

        print("Retrieved evidence:")

        for retrieval_result in result.retrieval.results:
            source = retrieval_result.chunk.metadata.get(
                "source",
                "unknown",
            )

            print(
                f"- rank={retrieval_result.rank} "
                f"score={retrieval_result.score:.6f} "
                f"document_id="
                f"{retrieval_result.chunk.document_id} "
                f"source={source}"
            )

        print()
        print("Grounded answer:")
        print(result.answer.answer)
        print()
        print(
            "Cited IDs: "
            f"{', '.join(result.answer.cited_ids)}"
        )
        print(
            "Response ID: "
            f"{result.answer.response_id}"
        )

        if not result.answer.cited_ids:
            print(
                "RAG demo failed: no citation was produced.",
                file=sys.stderr,
            )
            return 2

        if result.retrieval.results[0].chunk.document_id != (
            "seat-management"
        ):
            print(
                "RAG demo failed: expected evidence was not "
                "ranked first.",
                file=sys.stderr,
            )
            return 2

        print()
        print(
            "RAG question-answering smoke test passed."
        )
        return 0

    except (
        RagQuestionAnsweringError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"RAG question-answering demo failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
