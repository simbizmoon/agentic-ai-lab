"""Korean insufficient-evidence RAG evaluation dataset."""

from __future__ import annotations

from app.schemas.rag_abstention_evaluation import (
    RagAbstentionEvaluationCase,
)
from app.schemas.rag_abstention_evaluation_dataset import (
    RagAbstentionEvaluationDataset,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)

KOREAN_ABSTENTION_MARKERS = [
    "근거가 부족",
    "근거만으로는",
    "증거만으로는",
    "답변할 수 없",
    "답할 수 없",
    "확인할 수 없",
    "정보가 부족",
    "충분한 정보가 없",
    "정보가 포함되어 있지 않",
    "관련 증거가 검색되지 않",
    "제공된 정보",
    "제공된 증거",
]


def build_korean_rag_abstention_evaluation_dataset(
) -> RagAbstentionEvaluationDataset:
    """Return Korean out-of-scope RAG questions."""

    return RagAbstentionEvaluationDataset(
        dataset_id="korean-rag-abstention-smoke-v1",
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
                    "볶은 뒤 물을 넣고 충분히 끓인다."
                ),
                metadata={
                    "source": "cooking.txt",
                },
            ),
            RetrievalEvaluationDocument(
                document_id="software",
                text=(
                    "파이썬은 반복 작업을 자동화하고 데이터를 "
                    "처리하는 프로그램 개발에 사용할 수 있다."
                ),
                metadata={
                    "source": "software.txt",
                },
            ),
        ],
        cases=[
            RagAbstentionEvaluationCase(
                case_id="capital-of-france",
                question="프랑스의 수도는 어디입니까?",
                top_k=2,
                minimum_score=0.8,
                expected_markers=KOREAN_ABSTENTION_MARKERS,
            ),
            RagAbstentionEvaluationCase(
                case_id="moon-distance",
                question=(
                    "지구에서 달까지의 평균 거리는 "
                    "몇 킬로미터입니까?"
                ),
                top_k=2,
                minimum_score=0.8,
                expected_markers=KOREAN_ABSTENTION_MARKERS,
            ),
            RagAbstentionEvaluationCase(
                case_id="company-ceo",
                question=(
                    "현재 특정 회사의 최고경영자는 "
                    "누구입니까?"
                ),
                top_k=2,
                minimum_score=0.8,
                expected_markers=KOREAN_ABSTENTION_MARKERS,
            ),
        ],
    )
