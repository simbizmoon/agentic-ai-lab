# Phase 10 — Multi-Agent Research System

## 1. 목적

Phase 10의 목적은 단일 Research Agent Workflow를 역할 기반 Multi-Agent Research System으로 확장하는 것이다.

각 Agent는 독립적인 역할, Capability, Assignment, Message, Result 및 Failure 계약을 가지며, Manager와 Orchestrator가 전체 연구 흐름을 조정한다.

Phase 10은 외부 LLM이나 Search API에 종속되지 않는 결정론적 실행 구조를 우선 구현한다.

---

## 2. 핵심 설계 원칙

### 2.1 역할 분리

각 Agent는 하나의 명확한 연구 책임을 가진다.

- Research Manager
- Search Specialist
- Source Reader
- Evidence Analyst
- Source Critic
- Citation Verifier
- Claim Analyst
- Synthesis Specialist
- Quality Reviewer

Agent 간 역할을 분리하여 검색, 읽기, 분석, 주장 생성, 합성 및 검토가 동일한 실행 주체에 집중되지 않도록 한다.

### 2.2 구조화된 계약

Agent 간 협업은 자유 형식 문자열이 아니라 Pydantic Schema를 사용한다.

주요 계약은 다음과 같다.

- Agent Identity
- Agent Role
- Agent Status
- Capability Profile
- Task Assignment
- Agent Message
- Message Delivery
- Task Result
- Structured Failure
- Shared Research Workspace

### 2.3 결정론적 실행

테스트에서 시간, ID, Executor 결과를 주입할 수 있도록 설계하였다.

이를 통해 외부 API 없이 다음 항목을 검증할 수 있다.

- Agent 선택
- Assignment 생성
- Message 전달
- Agent 실행
- Result 생성
- Failure 변환
- Review 및 Revision 반복
- Orchestration 종료 조건

### 2.4 추적 가능성

모든 주요 Artifact는 이전 단계의 Artifact를 참조한다.

대표적인 추적 흐름은 다음과 같다.

```text
Research Request
    → Search Result
    → Source Document
    → Evidence
    → Claim
    → Citation
    → Report
    → Quality Review
