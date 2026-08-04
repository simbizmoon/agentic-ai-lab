# Phase 10 Baseline Report

## 1. 개요

이 문서는 AIRA Phase 10 Multi-Agent Research System의 최초 Baseline을 기록한다.

Baseline의 목적은 현재 구현 상태를 고정하고, Phase 11 이후 품질 및 신뢰성 개선 결과를 비교할 기준을 제공하는 것이다.

---

## 2. Baseline 범위

현재 Baseline은 외부 LLM, Search API 또는 Persistent Queue를 사용하지 않는 결정론적 Test 환경을 기준으로 한다.

검증 범위는 다음과 같다.

- Agent Identity와 Role
- Capability 및 위임 권한
- Assignment와 Message
- Registry
- In-Memory Message Bus
- Manager Dispatch
- Specialist Agent 실행
- Structured Result와 Failure
- Review 및 Revision Loop
- Multi-Agent Orchestration
- Single-Agent와 Multi-Agent 비교

---

## 3. Architecture Baseline

### 3.1 Agent 역할

| Agent | 주요 책임 |
|---|---|
| Research Manager | Agent 선택과 Assignment Dispatch |
| Search Specialist | Source Candidate 검색 |
| Source Reader | Source Document 읽기 및 정규화 |
| Evidence Analyst | Evidence 추출 |
| Source Critic | Source 품질 평가 |
| Citation Verifier | Claim–Citation 연결 검증 |
| Claim Analyst | Evidence 기반 Claim 생성 |
| Synthesis Specialist | Research Report 합성 |
| Quality Reviewer | Report 품질 평가 및 승인 판정 |

### 3.2 기본 Workflow

```text
Search
    → Source Reading
    → Evidence Extraction
    → Claim Construction
    → Report Synthesis
    → Quality Review
    → Optional Revision
