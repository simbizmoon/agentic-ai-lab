# AIRA MVP Specification

## 1. 제품 정의

AIRA는 개인이 연구 질문과 로컬 문서를 입력하면,
문서의 근거를 분석하여 Claim과 Citation이 연결된
Markdown 연구 보고서를 생성하는 개인용 연구 지원 도구다.

AIRA의 목표는 완전 자율적인 연구 조직이나 대규모 플랫폼을 만드는 것이
아니다.

사용자가 반복적으로 실제 사용할 수 있고,
결과의 근거와 한계를 확인할 수 있는 작고 신뢰할 수 있는 도구를 만든다.

## 2. 핵심 사용자

초기 사용자는 프로젝트 소유자 한 명이다.

현재 범위에서는 다음 기능을 구현하지 않는다.

- 회원가입
- 다중 사용자
- 조직과 Workspace 권한
- 협업
- 결제
- 관리자 화면

## 3. 해결할 문제

사용자는 여러 문서와 자료를 직접 읽고 비교하고 핵심 내용을 정리하는 데
많은 시간을 사용한다.

AIRA는 다음 작업을 지원한다.

1. 연구 질문 이해
2. 관련 문서 읽기
3. Evidence 추출
4. Claim 작성
5. Claim과 Citation 연결
6. 결론과 권고 작성
7. 불확실성과 한계 표시
8. 결과 저장과 재조회

## 4. 초기 입력

필수 입력:

- 연구 질문

선택 입력:

- 하나 이상의 로컬 Markdown 또는 Text 문서

초기 MVP에서는 다음 입력을 기본 지원하지 않는다.

- 이메일
- Google Drive
- 웹 브라우저 자동화
- 대규모 PDF 수집
- 실시간 외부 데이터
- 사용자별 Cloud 저장소

## 5. 초기 출력

AIRA는 실행별로 다음 파일을 생성한다.

```text
reports/<execution-id>/report.md
reports/<execution-id>/result.json

report.md 기본 구조:

결론
핵심 발견
근거
권고사항
한계와 불확실성
출처

result.json에는 다음 정보를 저장한다.

실행 ID
연구 질문
입력 문서
상태
요약
Claim
Citation
평가 결과
시작 시각
완료 시각
실패 정보

기존 Research 및 Application 모델을 우선 재사용한다.

## 6. 기본 실행 흐름
연구 질문
→ 로컬 문서 읽기
→ Research Task 결정
→ Evidence 추출
→ Claim과 Citation 연결
→ 보고서 생성
→ 기본 Eval과 Guardrail
→ Markdown과 JSON 저장

## 7. Agent 사용 원칙

기본 경로는 Single Research Agent다.

Planning은 복잡한 요청에만 사용한다.

Memory는 실제로 재사용할 사용자 정보나 프로젝트 상태가 있을 때만
사용한다.

Multi-Agent는 Single Agent보다 품질 향상이 평가로 확인될 때만 사용한다.

## 8. 초기 CLI 목표
python -m app.cli research \
  --question "연구 질문" \
  --document document1.md \
  --document document2.md

실행 완료 시 다음 정보를 표시한다.

실행 ID
성공 또는 실패 상태
보고서 경로
JSON 결과 경로
간단한 품질 평가

## 9. 실제 검증 사례

최소 세 가지 실제 사례로 검증한다.

사례 1

Agentic AI Lab 기준 문서 분석

목표:

현재 프로젝트 목표 정합성 확인
과도한 확장 식별
실용적인 다음 작업 제안
사례 2

AIRA 또는 다른 AI 서비스 아이디어 조사

목표:

여러 문서에서 핵심 기능과 위험 추출
Evidence 기반 제품 결정 지원
사례 3

특허 또는 기술 문서 비교

목표:

문서 간 공통점과 차이점 정리
근거 위치 표시
불확실한 판단 구분

## 10. 완료 기준

Phase 13은 다음 조건을 충족하면 완료한다.

CLI에서 질문과 로컬 문서를 입력할 수 있다.
Single Research Agent 기본 경로가 실행된다.
Evidence, Claim과 Citation이 연결된다.
Markdown 보고서가 생성된다.
JSON 실행 결과가 저장된다.
기본 Eval과 Guardrail 결과가 표시된다.
저장한 결과를 다시 확인할 수 있다.
실제 사례 세 개를 실행한다.
Docker에서 동일한 흐름을 실행할 수 있다.
사용자가 전체 Agent 흐름과 설계 판단을 설명할 수 있다.

## 11. 선택 기능

다음 기능은 필요성이 확인된 경우에만 구현한다.

최소 FastAPI
SQLite 저장
PDF 입력
웹 검색
제한된 Multi-Agent 비교
간단한 Human Approval

## 12. 비목표

현재 MVP의 비목표:

완벽한 상용 제품
다중 사용자 SaaS
Redis 또는 RabbitMQ
분산 Worker Cluster
Kubernetes
복잡한 인증과 RBAC
상용 수준 Web UI
완전 자율 연구 조직
대규모 운영 인프라
