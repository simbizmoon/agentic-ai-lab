"""Small Korean retrieval evaluation dataset."""

from __future__ import annotations

from app.schemas.rag_evaluation import (
    RetrievalEvaluationCase,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDataset,
    RetrievalEvaluationDocument,
)


def build_korean_retrieval_evaluation_dataset(
) -> RetrievalEvaluationDataset:
    """Return a small Korean semantic-retrieval dataset."""

    return RetrievalEvaluationDataset(
        dataset_id="korean-rag-smoke-v1",
        documents=[
            RetrievalEvaluationDocument(
                document_id="seat-management",
                text=(
                    "착석 관리 장치는 사용자가 일정 시간 이상 "
                    "의자에 앉아 있으면 진동, 표시등 또는 알림을 "
                    "출력하여 자세 변경이나 이석을 유도한다."
                ),
                metadata={
                    "source": "seat-management.txt",
                    "category": "behavior-management",
                },
            ),
            RetrievalEvaluationDocument(
                document_id="cooking",
                text=(
                    "김치찌개를 만들 때에는 김치와 돼지고기를 "
                    "볶은 뒤 물을 넣고 충분한 시간 동안 끓인다."
                ),
                metadata={
                    "source": "cooking.txt",
                    "category": "food",
                },
            ),
            RetrievalEvaluationDocument(
                document_id="software",
                text=(
                    "파이썬은 반복 작업을 자동화하고 데이터를 "
                    "처리하는 프로그램을 개발하는 데 사용할 수 "
                    "있다."
                ),
                metadata={
                    "source": "software.txt",
                    "category": "technology",
                },
            ),
            RetrievalEvaluationDocument(
                document_id="exercise",
                text=(
                    "규칙적인 걷기와 근력 운동은 신체 활동량을 "
                    "높이고 건강 유지에 도움을 줄 수 있다."
                ),
                metadata={
                    "source": "exercise.txt",
                    "category": "health",
                },
            ),
        ],
        cases=[
            RetrievalEvaluationCase(
                case_id="seat-alert",
                query=(
                    "오랫동안 의자에 앉아 있을 때 "
                    "어떻게 알려 주나요?"
                ),
                expected_document_ids=[
                    "seat-management"
                ],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="seat-behavior-change",
                query=(
                    "사용자의 자세 변경이나 일어서기를 "
                    "유도하는 장치는 무엇입니까?"
                ),
                expected_document_ids=[
                    "seat-management"
                ],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="kimchi-stew",
                query=(
                    "김치와 돼지고기로 찌개를 만드는 "
                    "방법은 무엇인가요?"
                ),
                expected_document_ids=[
                    "cooking"
                ],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="python-automation",
                query=(
                    "반복적인 데이터 작업을 자동화할 때 "
                    "어떤 언어를 사용할 수 있나요?"
                ),
                expected_document_ids=[
                    "software"
                ],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="health-exercise",
                query=(
                    "건강을 위해 걷기와 근력 운동을 "
                    "하는 이유는 무엇인가요?"
                ),
                expected_document_ids=[
                    "exercise"
                ],
                top_k=2,
            ),
        ],
    )
