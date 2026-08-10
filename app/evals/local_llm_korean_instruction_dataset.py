"""Deterministic Korean instruction-following benchmark cases."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KoreanInstructionCase:
    """One objectively scorable Korean instruction-following case."""

    case_id: str
    name: str
    prompt: str
    evaluator: str


@dataclass(frozen=True)
class KoreanInstructionCaseScore:
    """Deterministic score for one instruction case."""

    passed: bool
    checks_passed: int
    checks_total: int
    failures: tuple[str, ...]


def korean_instruction_cases() -> tuple[KoreanInstructionCase, ...]:
    """Return the fixed Phase 5B-1 Korean instruction dataset."""
    return (
        KoreanInstructionCase(
            case_id="exact-001",
            name="Exact Korean output",
            prompt=(
                "다른 설명을 덧붙이지 말고 정확히 다음 한 줄만 출력하라.\n"
                "작업 완료"
            ),
            evaluator="exact_작업_완료",
        ),
        KoreanInstructionCase(
            case_id="extract-001",
            name="Field extraction",
            prompt=(
                "다음 기록에서 이름과 점수만 추출하라.\n"
                "기록: 이름=민수, 부서=연구, 점수=87, 상태=완료\n"
                "출력은 정확히 `민수|87` 한 줄이어야 한다."
            ),
            evaluator="exact_민수_87",
        ),
        KoreanInstructionCase(
            case_id="order-001",
            name="Ordering constraint",
            prompt=(
                "다음 세 단어를 가나다순으로 정렬하라: 포도, 사과, 바나나.\n"
                "쉼표 뒤에는 공백 하나만 사용하고 다른 문장은 쓰지 마라."
            ),
            evaluator="exact_바나나_사과_포도",
        ),
        KoreanInstructionCase(
            case_id="lines-001",
            name="Exact line count",
            prompt=(
                "아래 정보를 정확히 두 줄로 출력하라.\n"
                "첫째 줄: 상태: 정상\n"
                "둘째 줄: 재시도: 0\n"
                "머리말, 번호, 코드블록을 추가하지 마라."
            ),
            evaluator="two_lines_status",
        ),
        KoreanInstructionCase(
            case_id="transform-001",
            name="Korean transformation",
            prompt=(
                "문장 `서버가 요청을 정상적으로 처리했습니다.`를 "
                "명사형 상태 표현으로 바꿔라.\n"
                "정확히 `요청 처리 정상`만 출력하라."
            ),
            evaluator="exact_요청_처리_정상",
        ),
        KoreanInstructionCase(
            case_id="selection-001",
            name="Constraint selection",
            prompt=(
                "후보 A, B, C 중 조건을 모두 만족하는 것만 고르라.\n"
                "A: 지연 120ms, 오류 0\n"
                "B: 지연 80ms, 오류 1\n"
                "C: 지연 90ms, 오류 0\n"
                "조건: 지연 100ms 이하이고 오류가 0이어야 한다.\n"
                "정답 글자 하나만 출력하라."
            ),
            evaluator="exact_C",
        ),
        KoreanInstructionCase(
            case_id="format-001",
            name="Strict key-value format",
            prompt=(
                "다음 값을 지정된 형식으로만 출력하라.\n"
                "도시: 서울\n"
                "온도: 24\n"
                "형식: `도시=값;온도=값`\n"
                "공백과 단위와 설명을 추가하지 마라."
            ),
            evaluator="exact_city_temp",
        ),
        KoreanInstructionCase(
            case_id="negative-001",
            name="Forbidden content",
            prompt=(
                "다음 요청에 답할 때 영어 단어를 사용하지 말고 "
                "정확히 한 문장으로 답하라.\n"
                "질문: 시스템 상태가 안정적이라는 뜻을 짧게 표현하라.\n"
                "정확히 `시스템 상태는 안정적입니다.`라고 답하라."
            ),
            evaluator="korean_only_exact",
        ),
    )


def evaluate_korean_instruction_response(
    case: KoreanInstructionCase,
    response: str,
) -> KoreanInstructionCaseScore:
    """Evaluate one response with deterministic checks."""
    cleaned = response.strip()
    checks: list[tuple[bool, str]] = []

    exact_by_evaluator = {
        "exact_작업_완료": "작업 완료",
        "exact_민수_87": "민수|87",
        "exact_바나나_사과_포도": "바나나, 사과, 포도",
        "exact_요청_처리_정상": "요청 처리 정상",
        "exact_C": "C",
        "exact_city_temp": "도시=서울;온도=24",
        "korean_only_exact": "시스템 상태는 안정적입니다.",
    }

    if case.evaluator in exact_by_evaluator:
        expected = exact_by_evaluator[case.evaluator]
        checks.append((cleaned == expected, f"exact output must be {expected!r}"))

        if case.evaluator == "korean_only_exact":
            checks.append(
                (
                    re.search(r"[A-Za-z]", cleaned) is None,
                    "response must not contain ASCII English letters",
                )
            )

    elif case.evaluator == "two_lines_status":
        lines = response.strip().splitlines()
        checks.extend(
            [
                (len(lines) == 2, "response must contain exactly two lines"),
                (
                    len(lines) >= 1 and lines[0] == "상태: 정상",
                    "first line must be '상태: 정상'",
                ),
                (
                    len(lines) >= 2 and lines[1] == "재시도: 0",
                    "second line must be '재시도: 0'",
                ),
                ("```" not in response, "response must not contain code fences"),
            ]
        )
    else:
        raise ValueError(f"unknown evaluator: {case.evaluator}")

    failures = tuple(
        message
        for passed, message in checks
        if not passed
    )
    return KoreanInstructionCaseScore(
        passed=not failures,
        checks_passed=sum(passed for passed, _ in checks),
        checks_total=len(checks),
        failures=failures,
    )
