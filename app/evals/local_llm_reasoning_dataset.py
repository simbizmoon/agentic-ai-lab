"""Verified reasoning cases for local LLM Think OFF/ON comparison."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations


@dataclass(frozen=True)
class LocalLLMReasoningCase:
    """One reasoning case with a separately stored expected answer."""

    case_id: str
    name: str
    prompt: str
    expected_answer: str


def reasoning_cases() -> list[LocalLLMReasoningCase]:
    """Return the fixed Phase 4A-3C reasoning dataset."""
    return [
        LocalLLMReasoningCase(
            case_id="ordering-001",
            name="Four-task ordering",
            prompt="""네 작업 D, A, B, C를 한 번씩 수행한다.

조건:
- D는 A보다 먼저 수행한다.
- A는 B보다 먼저 수행한다.
- B는 C보다 먼저 수행한다.

두 번째로 수행되는 작업을 구하라.
간단히 설명하고 마지막 줄에는 `정답: <값>` 형식만 사용하라.""",
            expected_answer="A",
        ),
        LocalLLMReasoningCase(
            case_id="code-001",
            name="Three-digit code",
            prompt="""서로 다른 세 숫자로 이루어진 세 자리 수가 있다.

조건:
- 백의 자리 숫자는 일의 자리 숫자의 2배이다.
- 십의 자리 숫자는 일의 자리 숫자보다 1 크다.
- 세 자리 숫자의 합은 13이다.
- 각 자리는 0부터 9 사이의 정수이다.

세 자리 수를 구하라.
간단히 설명하고 마지막 줄에는 `정답: <값>` 형식만 사용하라.""",
            expected_answer="643",
        ),
        LocalLLMReasoningCase(
            case_id="seating-001",
            name="Four-person seating",
            prompt="""민수, 영호, 지수, 수진 네 사람이 1번부터 4번까지
한 줄로 한 자리씩 앉는다.

조건:
- 영호는 민수의 바로 다음 자리에 앉는다.
- 지수는 영호의 바로 다음 자리에 앉는다.
- 수진은 1번 자리에 앉지 않는다.

3번 자리에 앉는 사람을 구하라.
간단히 설명하고 마지막 줄에는 `정답: <값>` 형식만 사용하라.""",
            expected_answer="지수",
        ),
        LocalLLMReasoningCase(
            case_id="equations-001",
            name="Pairwise sums",
            prompt="""세 정수 A, B, C가 다음 조건을 만족한다.

A + B = 17
B + C = 13
A + C = 14

B의 값을 구하라.
간단히 설명하고 마지막 줄에는 `정답: <값>` 형식만 사용하라.""",
            expected_answer="8",
        ),
        LocalLLMReasoningCase(
            case_id="route-001",
            name="Shortest route",
            prompt="""출발점 S에서 도착점 G까지 이동한다.
각 연결의 비용은 다음과 같고, 양방향으로 이동할 수 있다.

S-A: 4
S-B: 2
B-A: 1
A-G: 3
B-G: 8

같은 지점을 반복 방문하지 않는 경로 중
S에서 G까지의 최소 총비용을 구하라.
간단히 설명하고 마지막 줄에는 `정답: <값>` 형식만 사용하라.""",
            expected_answer="6",
        ),
    ]


def verify_reasoning_dataset() -> dict[str, str]:
    """Independently compute each case's unique expected answer."""
    verified: dict[str, str] = {}

    # ordering-001: enumerate all task orders satisfying the constraints.
    orders = [
        order
        for order in permutations(("D", "A", "B", "C"))
        if (
            order.index("D") < order.index("A")
            and order.index("A") < order.index("B")
            and order.index("B") < order.index("C")
        )
    ]
    if len(orders) != 1:
        raise ValueError("ordering-001 must have exactly one solution")
    verified["ordering-001"] = orders[0][1]

    # code-001: enumerate all distinct decimal digits.
    codes: list[str] = []
    for hundreds in range(1, 10):
        for tens in range(10):
            for units in range(10):
                if len({hundreds, tens, units}) != 3:
                    continue
                if hundreds != 2 * units:
                    continue
                if tens != units + 1:
                    continue
                if hundreds + tens + units != 13:
                    continue
                codes.append(f"{hundreds}{tens}{units}")
    if len(codes) != 1:
        raise ValueError("code-001 must have exactly one solution")
    verified["code-001"] = codes[0]

    # seating-001: enumerate all seatings satisfying adjacency.
    seatings = [
        order
        for order in permutations(("민수", "영호", "지수", "수진"))
        if (
            order.index("영호") == order.index("민수") + 1
            and order.index("지수") == order.index("영호") + 1
            and order[0] != "수진"
        )
    ]
    if len(seatings) != 1:
        raise ValueError("seating-001 must have exactly one solution")
    verified["seating-001"] = seatings[0][2]

    # equations-001: solve over a bounded integer domain.
    triples = [
        (a, b, c)
        for a in range(-50, 51)
        for b in range(-50, 51)
        for c in range(-50, 51)
        if a + b == 17 and b + c == 13 and a + c == 14
    ]
    if len(triples) != 1:
        raise ValueError("equations-001 must have exactly one solution")
    verified["equations-001"] = str(triples[0][1])

    # route-001: enumerate the simple routes explicitly.
    route_costs = {
        "S-A-G": 4 + 3,
        "S-B-G": 2 + 8,
        "S-B-A-G": 2 + 1 + 3,
        "S-A-B-G": 4 + 1 + 8,
    }
    minimum = min(route_costs.values())
    winning_routes = [
        route
        for route, cost in route_costs.items()
        if cost == minimum
    ]
    if len(winning_routes) != 1:
        raise ValueError("route-001 must have one shortest route")
    verified["route-001"] = str(minimum)

    return verified
