# AIRA MULTI-AGENT ROADMAP

## 1. 문서 목적

본 문서는 AIRA(Agentic Intelligence Research Assistant)의 다음 학습·개발 단계인
Multi-Agent System을 체계적으로 학습하고, 실제 AIRA에 적용할 가치가 있는지
검증하기 위한 실행 Roadmap이다.

본 문서의 핵심 질문은 다음과 같다.

```text
Multi-Agent는 무엇인가?
언제 필요한가?
언제 사용하면 안 되는가?
어떤 구조가 있는가?
Single-Agent보다 실제로 더 나은가?
더 낫다면 어떤 비용을 지불하는가?
AIRA에는 어디까지 적용하는 것이 적절한가?
```

Multi-Agent 구현 자체를 성공 기준으로 삼지 않는다.

최종 채택 여부는 반드시 현재 Single-Agent Baseline과의 비교 결과로 결정한다.

---

# 2. 현재 출발점

2026-08-09 현재 AIRA는 Single-Agent Live Research Runtime의 핵심 경로를
구현하고 성능 최적화까지 완료하였다.

현재 Single-Agent Live Research는 다음 주요 기능을 포함한다.

```text
Research Request
→ Query Planning
→ Live Web Search
→ HTTP/HTML Reading
→ Source Quality Evaluation
→ RRF Hybrid Retrieval
→ Semantic Evidence Relevance
→ Evidence-aware Selection
→ Generative Claim
→ Semantic Citation Verification
→ Claim Relevance
→ Semantic Answer Coverage
→ Bounded Coverage Replanning
→ Report / Result Persistence
→ Budget / Observability
```

대표 heavy-path 성능 기준:

```text
tracked LLM calls ≈ 10
recorded tokens ≈ 27K
quality baseline = 0.8845
```

이 Single-Agent Runtime을 Multi-Agent 평가의 Baseline으로 고정한다.

추가 Single-Agent micro-optimization은 현재 보류한다.

---

# 3. Multi-Agent의 정의

## 3.1 Agent

Agent는 단순한 함수가 아니다.

본 프로젝트에서 Agent는 최소한 다음 특성을 가진 실행 주체로 정의한다.

```text
Goal 또는 Role
State
Instructions
Available Tools
Decision
Action
Observation
Termination Condition
```

Agent는 무엇을 할지 판단하고, Tool 또는 다른 Agent를 호출할 수 있다.

## 3.2 Multi-Agent System

Multi-Agent System은 둘 이상의 Agent가 명확하게 분리된 역할 또는 책임을 가지고
하나의 상위 목표를 공동으로 해결하는 구조이다.

단순히 LLM 호출이 여러 번 일어난다고 Multi-Agent라고 하지 않는다.

예:

```text
Research Agent
 ├─ web_search()
 ├─ read_page()
 └─ save_report()
```

이것은 Tool이 여러 개인 Single-Agent이다.

반면:

```text
Coordinator Agent
 ├─ Technical Research Agent
 ├─ Market Research Agent
 └─ Verification Agent
```

은 각 실행 주체가 독립적인 역할과 판단 경계를 가지므로 Multi-Agent 구조다.

---

# 4. 왜 Multi-Agent를 사용하는가

Multi-Agent는 다음 문제를 해결할 때 가치가 있을 수 있다.

## 4.1 전문 역할 분리

하나의 Agent가 모든 영역을 동일한 품질로 처리하기 어려운 경우:

```text
Technical Specialist
Patent Specialist
Market Specialist
Verification Specialist
```

처럼 역할을 분리할 수 있다.

## 4.2 Context 분리

한 Agent의 Context가 지나치게 커지거나 서로 다른 작업 정보가 섞이는 경우,
각 Agent가 자신의 목적에 필요한 Context만 유지할 수 있다.

## 4.3 병렬 처리

서로 독립적인 연구 과제는 동시에 실행할 수 있다.

```text
             Coordinator
          /       |       \
     Technical  Patent   Market
          \       |       /
             Synthesis
```

병렬화가 가능하면 latency를 줄일 수 있다.

단, 총 API 비용이 반드시 감소하는 것은 아니다.

## 4.4 실패 격리

한 Specialist의 실패가 전체 상태를 오염시키지 않도록 경계를 만들 수 있다.

## 4.5 독립 검증

작성 Agent와 검증 Agent를 분리하면 자기검증보다 오류 탐지 가능성을 높일 수 있다.

예:

```text
Research Agent
      ↓
Claim
      ↓
Independent Verification Agent
```

## 4.6 서로 다른 Tool·Permission

Agent별로 사용할 수 있는 Tool을 제한할 수 있다.

예:

```text
Web Research Agent
→ web_search / reader만 사용

Patent Agent
→ patent_search / patent_reader만 사용

Writer Agent
→ 외부 Tool 사용 불가
```

이는 안전성과 책임 경계를 명확하게 할 수 있다.

---

# 5. Multi-Agent를 사용하면 안 되는 경우

Multi-Agent가 항상 더 좋은 것은 아니다.

다음 조건에서는 Single-Agent를 우선한다.

## 5.1 하나의 Agent로 충분히 해결 가능한 문제

예:

```text
하나의 공식 문서를 검색하고 핵심 내용을 설명
```

이런 작업을 Planner, Searcher, Reader, Writer Agent로 나누면
오히려 복잡성과 비용만 증가한다.

## 5.2 역할 사이 경계가 불명확한 경우

예:

```text
Research Agent A
Research Agent B
Research Agent C
```

역할이 실질적으로 같다면 Agent 수를 늘릴 이유가 없다.

## 5.3 Context 전달 비용이 큰 경우

Agent 사이에 긴 문서를 계속 전달하면:

```text
Token 증가
Latency 증가
정보 손실
요약 오류
```

가 발생할 수 있다.

## 5.4 단순한 Workflow 문제

고정 순서로 처리 가능한 작업이라면 Agent보다 Workflow가 적절할 수 있다.

```text
Parse
→ Retrieve
→ Summarize
→ Save
```

의 순서가 항상 동일하다면 굳이 각 단계를 Agent로 만들 필요가 없다.

## 5.5 검증되지 않은 품질 이점

Multi-Agent가 Single-Agent보다 품질이 좋다는 측정 결과가 없다면
기본 Runtime으로 채택하지 않는다.

---

# 6. 반드시 구분해야 할 구조

이번 Stage에서는 다음 구조를 명확히 구분한다.

---

## 6.1 Single Agent + Multiple Tools

```text
User
 ↓
Single Agent
 ├─ Search Tool
 ├─ Reader Tool
 ├─ Analysis Tool
 └─ Writer Tool
```

특징:

- 중앙 판단 주체 하나
- State 관리 단순
- 비용 관리 쉬움
- 초기 AIRA의 기본 구조

적합:

- 일반적인 단일 연구 과제
- 제한된 Tool 수
- Context가 감당 가능한 경우

---

## 6.2 Agent as Tool

한 Agent가 다른 Agent를 Tool처럼 호출한다.

```text
Coordinator Agent
      |
      +-- call Patent Specialist
      |
      +-- call Technical Specialist
```

상위 Agent가 제어권을 유지한다.

적합:

- 전문 기능을 필요할 때만 호출
- Specialist가 재사용 가능한 독립 Capability인 경우
- 중앙 Coordinator가 최종 판단해야 하는 경우

핵심 질문:

```text
이 역할은 독립 Agent여야 하는가?
아니면 단순 Tool이면 충분한가?
```

---

## 6.3 Handoff

현재 Agent가 다른 Agent에게 대화 또는 작업의 주도권을 넘긴다.

```text
General Agent
     ↓ handoff
Patent Agent
```

특징:

- 다음 Agent가 주도권을 가짐
- 사용자 interaction routing에 적합
- Agent-as-Tool과 제어권 구조가 다름

적합 후보:

- 상담 유형 전환
- 도메인 전문 Agent로 책임 이전
- 사용자와 Specialist가 직접 계속 대화해야 하는 경우

AIRA Research Pipeline의 초기 Multi-Agent 실험에서는
Agent-as-Tool보다 우선순위가 낮다.

---

## 6.4 Manager / Worker

```text
Manager
  ├─ Worker A
  ├─ Worker B
  └─ Worker C
```

Manager가:

- Task를 분해
- Worker를 선택
- 결과를 수집
- 최종 통합

한다.

적합:

- 하위 Task가 여러 개
- 각 Task가 분명히 분리 가능
- Worker 결과를 통합할 필요가 있음

위험:

- Manager LLM 호출 증가
- Task 분해 오류
- 중복 조사
- Worker Context 중복

---

## 6.5 Sequential Specialists

```text
Research Agent
      ↓
Evidence Agent
      ↓
Claim Agent
      ↓
Verification Agent
```

각 Agent가 앞 Agent 결과를 받아 순차 처리한다.

장점:

- 책임 분리
- 디버깅 쉬움

단점:

- 호출 수 증가
- latency 증가
- Agent 간 정보 손실

AIRA에서는 기존 Pipeline Component가 이미 같은 책임을 수행하고 있으므로
단순히 각 Component를 Agent로 바꾸는 것은 우선하지 않는다.

---

## 6.6 Parallel Specialists

```text
                    Coordinator
                /       |       \
           Technical  Patent   Market
                \       |       /
                   Synthesis
```

적합:

- 하위 연구 주제가 독립적
- 서로 다른 Source/Tool을 사용
- 병렬 수행이 가능

장점:

- Context 분리
- 전문화
- wall-clock 단축 가능

단점:

- 총 Token 증가 가능
- 중복 조사 가능
- 통합 단계 필요

---

## 6.7 Critic / Verifier

```text
Research Agent
      ↓
Draft Result
      ↓
Critic / Verifier
      ↓
Accept / Revise
```

가장 실용적인 Multi-Agent 패턴 중 하나다.

적합:

- 높은 신뢰성이 필요한 결과
- 서로 다른 관점의 독립 검증이 가치 있는 경우
- Citation, contradiction, completeness 확인

단, 현재 AIRA에는 이미 Semantic Citation, Claim Relevance,
Answer Coverage Evaluator가 존재한다.

따라서 별도 Verifier Agent를 도입하기 전에
기존 Evaluator보다 추가 가치가 있는지를 입증해야 한다.

---

# 7. Multi-Agent의 비용 구조

Multi-Agent의 가장 큰 위험 중 하나는 API Call fan-out이다.

현재 Single-Agent heavy path:

```text
약 10 tracked LLM calls
```

예를 들어 다음 구조를 만들면:

```text
Manager              1
Technical Worker     5
Patent Worker        5
Market Worker        5
Synthesis            1
Verifier             3
```

총 호출은 쉽게 20회 이상으로 증가할 수 있다.

따라서 Multi-Agent 평가에서는 반드시 다음을 측정한다.

```text
LLM calls
Input tokens
Output tokens
Recorded tokens
Search calls
Provider credits
Elapsed time
Quality score
Coverage
Citation accuracy
Failure count
```

### 핵심 지표

단순 Quality가 아니라 다음을 본다.

```text
Quality Gain / Additional Cost
```

개념적으로:

```text
Multi-Agent 가치
= 품질 또는 기능 개선
  ÷
  추가 비용 + 추가 latency + 추가 complexity
```

정확한 단일 공식 점수로 강제하지 않고 비교 판단의 원칙으로 사용한다.

---

# 8. 현재 AIRA의 Multi-Agent 자산 감사

새 Multi-Agent 코드를 만들기 전에 기존 저장소를 감사한다.

기존 Phase 10에서 다음 개념을 이미 학습·구현한 이력이 있다.

- Agent Role
- Capability
- Task Assignment
- Message
- Shared Workspace
- Delegation
- Specialist Agent
- Sequential Pipeline
- Parallel Pipeline
- Conflict Detection
- Revision
- Single vs Multi 비교

따라서 첫 구현 작업은 신규 작성이 아니라 다음을 확인하는 것이다.

```text
기존 Multi-Agent 코드가 어디에 있는가?
현재 테스트는 무엇인가?
현재 Runtime에 연결되어 있는가?
Fake인가 실제 LLM인가?
Agent 간 Message 구조는 무엇인가?
Shared State는 무엇인가?
비용 계측이 가능한가?
현재 Single-Agent Domain과 호환되는가?
```

각 Capability를 다음 상태로 분류한다.

```text
Implemented
Tested
Runtime-connected
Live-verified
Reusable
Needs Adapter
Needs Modification
Defer
```

---

# 9. Stage MA-0 — 개념 및 의사결정 기준 학습

## 목표

코드를 작성하기 전에 Multi-Agent Architecture 선택 기준을 이해한다.

## 학습 항목

- [ ] Agent와 Tool 차이
- [ ] Workflow와 Agent 차이
- [ ] Single Agent + Tools
- [ ] Agent-as-Tool
- [ ] Handoff
- [ ] Manager/Worker
- [ ] Sequential Specialists
- [ ] Parallel Specialists
- [ ] Critic/Verifier
- [ ] Shared State
- [ ] Message Passing
- [ ] Delegation
- [ ] Termination
- [ ] Failure propagation

## 직접 실습

주어진 10개 업무 시나리오에 대해 다음 중 하나를 선택한다.

```text
Simple function
Tool
Workflow
Single Agent
Multi-Agent
```

선택 이유를 설명한다.

## Gate

사용자가 다음 질문에 설명할 수 있어야 한다.

```text
왜 Agent를 하나 더 만드는가?
Tool로는 왜 부족한가?
Single Agent로는 왜 부족한가?
추가 비용은 무엇인가?
```

---

# 10. Stage MA-1 — 기존 Multi-Agent Capability Audit

## 목표

기존 Phase 10 자산을 정확히 확인하고 재사용 범위를 결정한다.

## Audit 대상

- Agent Role Schema
- Agent Capability
- Agent Registry
- Specialist Agent
- Coordinator
- Assignment
- Message
- Shared Workspace
- Sequential orchestration
- Parallel orchestration
- Conflict detection
- Revision
- Trace
- Usage
- Budget
- Tests
- Runtime composition

## 산출물

```text
AIRA_MULTI_AGENT_AUDIT.md
```

최소 표:

```text
Component
Location
Implemented
Tested
Runtime-connected
Live LLM
Reusable
Decision
```

## Gate

다음이 확정되어야 한다.

- 무엇을 그대로 재사용할 것인가
- 무엇에 Adapter가 필요한가
- 무엇을 수정할 것인가
- 무엇을 사용하지 않을 것인가

---

# 11. Stage MA-2 — Single vs Multi 실험 설계

## 목표

Multi-Agent 구현 전에 비교 실험을 정의한다.

Multi-Agent가 유리할 가능성이 높은 연구 질문을 선택한다.

### 실험 질문의 조건

하위 문제가 분명히 분리되어야 한다.

첫 후보:

```text
"Agentic AI framework를 도입할 때
기술적 관점과 제품/사업적 관점의 장단점 및
도입 위험을 조사하라."
```

하위 역할:

```text
Technical Specialist
Product/Business Specialist
```

필요하면 Verification 역할을 별도 실험한다.

## Baseline

현재 `aira research-live` Single-Agent를 그대로 사용한다.

## 측정값

### 품질

- Evidence Coverage
- Answer Coverage
- Claim Relevance
- Citation Support
- Source Diversity
- Contradiction Detection
- Report completeness

### 비용

- LLM calls
- Recorded tokens
- Search calls
- Search credits
- Elapsed time

### 시스템

- Context size
- Duplicate research
- Failure isolation
- Trace readability
- Debug difficulty

## Gate

Multi-Agent가 개선해야 할 목표를 구현 전에 명시한다.

예:

```text
목표:
Answer Coverage를 유의미하게 개선

허용 비용:
Single-Agent 대비 호출 수가 과도하게 증가하지 않음
```

정확한 threshold는 첫 실험 데이터 후 결정한다.

---

# 12. Stage MA-3 — 최소 Agent-as-Tool Vertical Slice

## 목표

AIRA에 가장 작은 실제 Multi-Agent 경로를 구현한다.

첫 구조는 Agent-as-Tool을 우선 검토한다.

이유:

- 기존 Single-Agent를 유지 가능
- 필요할 때만 Specialist 호출
- 중앙 Coordinator가 통제
- Handoff보다 Research Pipeline에 적합
- 기존 Tool 개념과 비교 학습 가능

예상 구조:

```text
Research Coordinator
       |
       +-- Technical Research Specialist
       |
       +-- Product/Business Specialist
       |
       +-- 기존 Research Tools
       |
       ↓
Final Synthesis
```

## 중요 원칙

Specialist는 단순 Prompt 이름 변경이 아니다.

각 Specialist는 최소 하나 이상의 차이를 가져야 한다.

예:

```text
Different objective
Different allowed tools
Different source priorities
Different completion criteria
Different context
```

실질적인 차이가 없다면 별도 Agent로 만들지 않는다.

## 구현 범위

- [ ] Coordinator contract
- [ ] Specialist contract
- [ ] Agent invocation result
- [ ] temporary agent-call identity
- [ ] failure isolation
- [ ] bounded calls
- [ ] usage aggregation
- [ ] trace
- [ ] deterministic fake tests
- [ ] one live E2E

## 제외

- 동적 Agent 생성
- Agent가 Agent를 무제한 생성
- recursive delegation
- 대규모 shared memory
- 장기 autonomous organization
- agent marketplace

---

# 13. Stage MA-4 — Parallel Specialist Experiment

## 목표

독립 하위 연구를 실제 병렬로 수행했을 때 latency 이점과 비용 증가를 평가한다.

구조:

```text
               Coordinator
              /           \
 Technical Specialist   Business Specialist
              \           /
                Synthesis
```

## 비교

### Sequential

```text
Technical
→ Business
→ Synthesis
```

### Parallel

```text
Technical ─┐
           ├→ Synthesis
Business ──┘
```

## 평가

- wall-clock latency
- total calls
- total tokens
- duplicate sources
- result quality
- failure behavior

## Gate

Parallelism은:

```text
총 비용이 같거나 증가하더라도
wall-clock 단축이 실제 사용 가치가 있을 때
```

채택할 수 있다.

병렬화 자체를 목표로 하지 않는다.

---

# 14. Stage MA-5 — Manager/Worker 평가

## 목표

하위 Task가 여러 개인 복합 연구에서 Manager가 유용한지 확인한다.

예:

```text
Research Manager
├─ Technical Worker
├─ Official Source Worker
├─ Academic Worker
└─ Patent Worker
```

## 먼저 확인할 질문

```text
현재 Query Planner + Tool Pipeline으로 충분하지 않은가?
```

충분하다면 Manager Agent를 추가하지 않는다.

Manager를 사용해야 할 가능성이 높은 조건:

- 연구 Task 종류가 동적으로 달라짐
- Specialist 선택 자체가 reasoning 문제
- Worker별 Tool/Source가 크게 다름
- 일부 Worker 실패 후 재할당이 필요함

## 위험

- 계획 Agent와 실행 Agent의 중복
- 이미 존재하는 Query Planner와 책임 충돌
- 과도한 Coordinator Context
- worker 중복 조사
- 호출 폭증

---

# 15. Stage MA-6 — Handoff 실험

## 목표

Handoff가 AIRA Research Runtime에서 실제 필요한지 검토한다.

AIRA에서 Handoff 후보:

```text
General Research Assistant
        ↓
Patent Specialist
```

또는:

```text
General Assistant
        ↓
Local Document Specialist
```

그러나 CLI 중심 Batch Research에서는 Handoff보다
Agent-as-Tool 또는 Manager/Worker가 더 자연스러울 수 있다.

따라서 Handoff는 필수 구현 항목이 아니라 학습·비교 항목으로 둔다.

## 채택 조건

- 사용자 대화 ownership 전환이 실제로 필요
- Specialist가 이후 상호작용을 직접 관리하는 것이 유리
- Agent-as-Tool보다 명확한 UX 장점 존재

---

# 16. Stage MA-7 — Critic / Independent Verification 실험

## 목표

별도 검증 Agent가 기존 Semantic Evaluator보다 실질적인 추가 가치를 주는지 확인한다.

현재 AIRA에는 이미:

- Semantic Citation Verification
- Claim Relevance
- Answer Coverage

가 있다.

따라서 Critic Agent는 이 기능을 그대로 중복하면 안 된다.

유효한 역할 후보:

```text
Cross-source contradiction detection
Missing counterargument detection
Unsupported synthesis detection
Report-level completeness review
```

## 비교

```text
Existing Evaluators only
vs
Existing Evaluators + Critic Agent
```

## Gate

다음 중 하나가 개선될 때만 유지한다.

- 실제 오류 탐지
- Contradiction detection
- Missing aspect detection
- Report completeness

단순히 더 긴 critique를 생성하는 것은 성공이 아니다.

---

# 17. Stage MA-8 — Shared State와 Message 설계

## 목표

Agent 사이에 무엇을 공유하고 무엇을 공유하지 않을지 정의한다.

전체 Transcript를 매번 전달하지 않는다.

공유 후보:

```text
Research Request
Task Assignment
Selected Sources
Evidence IDs
Claims
Coverage State
Agent Result Summary
Usage
Errors
```

Agent별 Local State:

```text
private working context
temporary reasoning artifacts
specialist-specific candidate set
local tool trace
```

## 핵심 원칙

```text
공유해야 할 사실
≠
모든 Agent의 전체 Context
```

Context duplication을 줄여 비용과 오염을 방지한다.

---

# 18. Stage MA-9 — Multi-Agent Budget

## 목표

Single-Agent Budget 위에 Multi-Agent 전용 상한을 둔다.

필수 제한 후보:

```text
maximum agents invoked
maximum delegation depth
maximum LLM calls
maximum search calls
maximum total tokens
maximum elapsed time
maximum retries per agent
```

초기 정책:

```text
delegation depth = 1
recursive delegation = disabled
```

즉:

```text
Coordinator
→ Specialist
```

까지만 허용하고:

```text
Coordinator
→ Specialist
→ Sub-specialist
→ ...
```

같은 recursive structure는 초기 범위에서 금지한다.

---

# 19. Stage MA-10 — Failure Handling

## 목표

한 Agent의 실패가 전체 실행에서 어떻게 처리되는지 명시한다.

실패 유형:

- Provider failure
- Structured output failure
- Tool failure
- Search budget exhaustion
- Specialist timeout
- No evidence
- Invalid result
- Partial result

정책 후보:

```text
Optional Specialist failure
→ 다른 결과로 계속

Required Specialist failure
→ final result에 limitation 기록

Coordinator failure
→ explicit run failure
```

Agent 실패를 무조건 다른 Agent 호출로 보완하지 않는다.

그렇게 하면 장애가 API fan-out으로 확대될 수 있다.

---

# 20. Stage MA-11 — Single vs Multi E2E Evaluation

## 목표

동일 Research Task를 Single-Agent와 Multi-Agent로 실행한다.

비교 표:

```text
Metric                     Single       Multi

Quality
Answer Coverage
Citation Support
Claim Relevance
Contradiction Detection
Source Diversity

LLM Calls
Recorded Tokens
Search Calls
Search Credits
Elapsed Time

Failure Count
Duplicate Research
Trace Complexity
```

최소 1회 실행으로 일반화하지 않는다.

동일 유형의 여러 질문을 포함한 작은 Evaluation Set을 사용한다.

초기 후보:

1. 기술 + 사업 분석
2. 기술 + 특허 분석
3. 공식자료 + 일반 Web 비교
4. 서로 상충하는 Source 분석
5. 하나의 단순 질문

5번은 의도적으로 포함한다.

목적:

```text
Multi-Agent가 필요 없는 문제에서
오히려 손해가 나는지도 확인
```

---

# 21. Multi-Agent Adoption Gate

Multi-Agent를 기본 AIRA Runtime에 채택하려면 다음 중 하나 이상의
명확한 개선을 입증해야 한다.

## 품질

- Evidence Coverage 개선
- Answer Coverage 개선
- Citation Accuracy 개선
- Contradiction Detection 개선
- 복합 분석 품질 개선

## 시스템

- Context 안정성 개선
- Failure isolation 개선
- Specialist 재사용성 개선
- wall-clock latency 개선

## 비용 대비 가치

추가 비용이 발생하더라도 개선 가치가 더 큰 경우.

다음 상황은 채택 근거가 아니다.

```text
Agent가 더 많음
Architecture가 더 복잡함
Report가 더 김
LLM 호출이 더 많음
```

---

# 22. Multi-Agent Rejection Gate

다음 상황이면 Multi-Agent를 기본 경로로 채택하지 않는다.

- 품질 개선이 측정되지 않음
- Single-Agent와 결과 차이가 미미함
- API Call/Token이 과도하게 증가
- Latency가 크게 증가
- Agent간 정보 손실
- 중복 검색 증가
- 실패 지점이 더 불명확해짐
- 유지보수 복잡성이 크게 증가

이 경우:

```text
Single-Agent
= 기본 Runtime 유지

Multi-Agent
= 선택적 Specialist Mode 또는 실험 기능
```

으로 유지할 수 있다.

---

# 23. Stop Rule

Multi-Agent도 끝없이 미세조정하지 않는다.

다음 조건에 도달하면 Stage를 종료한다.

1. 주요 Multi-Agent 패턴의 차이를 설명할 수 있다.
2. 최소 하나의 실제 Multi-Agent Vertical Slice가 동작한다.
3. Single vs Multi 비용/품질 비교가 존재한다.
4. Adoption 또는 Rejection 결정을 내릴 근거가 있다.
5. 주요 실패와 한계를 기록했다.
6. 전체 Regression을 깨뜨리지 않는다.

추가 Agent 역할과 topology는 실제 필요가 생길 때만 확장한다.

---

# 24. 구현 우선순위

권장 순서:

```text
MA-0  개념과 사용 조건
  ↓
MA-1  기존 Multi-Agent Capability Audit
  ↓
MA-2  Single vs Multi 실험 설계
  ↓
MA-3  Agent-as-Tool 최소 Vertical Slice
  ↓
MA-4  Parallel Specialist 비교
  ↓
MA-5  Manager/Worker 필요성 평가
  ↓
MA-6  Handoff 필요성 평가
  ↓
MA-7  Critic/Verifier 추가 가치 평가
  ↓
MA-8  Shared State / Message
  ↓
MA-9  Multi-Agent Budget
  ↓
MA-10 Failure Handling
  ↓
MA-11 E2E Single vs Multi Evaluation
  ↓
Adopt / Selective Use / Reject
```

모든 Stage를 구현해야 하는 것은 아니다.

앞 단계 평가에서 가치가 없다고 판단되면 후속 구현을 생략한다.

---

# 25. 첫 번째 실제 학습 단위

다음 세션의 첫 주제:

```text
MA-0.1
Agent vs Tool vs Workflow vs Multi-Agent
```

학습 순서:

```text
이론 설명
→ 작은 예제
→ 사례 분류 실습
→ 사용자가 직접 판단
→ 이해도 평가
```

그 다음:

```text
MA-0.2
Multi-Agent 대표 패턴 비교
```

학습 대상:

```text
Agent-as-Tool
Handoff
Manager/Worker
Sequential Specialists
Parallel Specialists
Critic/Verifier
```

---

# 26. 첫 번째 Codex 작업

이론과 설계 이해가 끝난 뒤 첫 Codex 작업은
**구현이 아니라 Existing Capability Audit**으로 한다.

예상 작업지시 목표:

```text
Phase 10 Multi-Agent 관련 코드와 테스트를 감사하라.

새 코드를 작성하지 말라.

다음을 확인하라.

- Agent Role
- Capability
- Assignment
- Message
- Shared Workspace
- Coordinator
- Specialist
- Sequential orchestration
- Parallel orchestration
- Conflict detection
- Usage / Budget
- Runtime connection
- Live LLM connection

각 항목을
Implemented / Tested / Runtime-connected / Live-verified
상태로 분류하라.

현재 Single-Agent Live Research에 재사용 가능한 부분과
재사용하면 안 되는 부분을 근거와 함께 보고하라.
```

---

# 27. 문서 산출물

Multi-Agent Stage에서 생성할 문서 후보:

```text
AIRA_MULTI_AGENT_ROADMAP.md
AIRA_MULTI_AGENT_AUDIT.md
AIRA_MULTI_AGENT_ARCHITECTURE.md
AIRA_SINGLE_VS_MULTI_EVAL.md
```

필요 없는 문서는 만들지 않는다.

문서의 수보다 실제 설계 판단과 비교 결과를 우선한다.

---

# 28. 최종 목표

Multi-Agent Stage의 최종 결과는
"여러 Agent가 동작한다"가 아니다.

최종적으로 다음 질문에 답할 수 있어야 한다.

```text
AIRA에서 Multi-Agent는 언제 사용하는가?

어떤 Pattern을 사용하는가?

왜 그 Pattern인가?

Single-Agent보다 무엇이 좋아지는가?

얼마나 더 비싸지는가?

언제 Single-Agent로 돌아가야 하는가?
```

최종 결정은 다음 셋 중 하나가 될 수 있다.

```text
A. Multi-Agent를 기본 경로에 부분 채택

B. 특정 복잡한 Research에서만 선택적 사용

C. 이점이 충분하지 않아 현재는 보류
```

세 결과 모두 올바른 프로젝트 결과가 될 수 있다.

중요한 것은 Agent 수가 아니라
**측정된 가치와 비용 대비 효과**이다.
