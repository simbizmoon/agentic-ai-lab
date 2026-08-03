"""Small Korean end-to-end RAG answer evaluation dataset."""

from __future__ import annotations

from app.schemas.rag_answer_evaluation_dataset import (
    RagAnswerEvaluationCase,
    RagAnswerEvaluationDataset,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


def build_korean_rag_answer_evaluation_dataset(
) -> RagAnswerEvaluationDataset:
    """Return a small Korean grounded-answer dataset."""

    return RagAnswerEvaluationDataset(
        dataset_id="korean-rag-answer-smoke-v1",
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
                },
            ),
        ],
        cases=[
            RagAnswerEvaluationCase(
                case_id="seat-alert-answer",
                question=(
                    "사용자가 오랫동안 의자에 앉아 있으면 "
                    "장치는 어떻게 행동 변화를 유도합니까?"
                ),
                expected_document_ids=[
                    "seat-management"
                ],
                top_k=1,
            ),
            RagAnswerEvaluationCase(
                case_id="kimchi-stew-answer",
                question=(
                    "김치찌개는 어떤 순서로 조리합니까?"
                ),
                expected_document_ids=[
                    "cooking"
                ],
                top_k=1,
            ),
            RagAnswerEvaluationCase(
                case_id="python-answer",
                question=(
                    "반복적인 데이터 작업을 자동화할 때 "
                    "어떤 언어를 사용할 수 있습니까?"
                ),
                expected_document_ids=[
                    "software"
                ],
                top_k=1,
            ),
            RagAnswerEvaluationCase(
                case_id="exercise-answer",
                question=(
                    "걷기와 근력 운동은 건강에 어떤 도움을 "
                    "줄 수 있습니까?"
                ),
                expected_document_ids=[
                    "exercise"
                ],
                top_k=1,
            ),
        ],
    )
