# AIRA INTEGRATION PLAN

## 1. 문서 목적

본 문서는 AIRA Live Research Vertical Slice를 작은 Integration Work Item으로
구현하기 위한 실행 순서, 산출물, 테스트, Acceptance Criteria 및 Codex 작업
경계를 정의한다.

최상위 기준:

1. `AIRA_PROJECT_CHARTER.md`
2. `DECISIONS.md`
3. `AIRA_PROJECT_AUDIT_REPORT.md`
4. `AIRA_CAPABILITY_MATRIX.md`
5. `AIRA_TARGET_ARCHITECTURE.md`
6. `MASTER.md`
7. `ROADMAP.md`

---

## 2. 전체 구현 전략

```text
Contract 확인
→ Adapter 구현
→ Fixture Unit Test
→ Integration Test
→ 실제 Smoke Test
→ Artifact 저장
→ Runner 통합
→ CLI E2E
```

각 Work Item은 기존 테스트 `4088 passed`와 Ruff 기준선을 보존해야 한다.

한 Work Item에서 다음을 동시에 무리하게 구현하지 않는다.

- Search Provider
- HTTP Reader
- Artifact Writer
- Runner
- CLI
- OpenAI Planning

각 경계를 개별적으로 검증한 뒤 연결한다.

---

## 3. 공통 개발 규칙

- 기존 Schema와 Port를 우선 재사용한다.
- 신규 추상화는 기존 계약으로 표현할 수 없을 때만 추가한다.
- 실제 Provider 호출은 Unit Test에서 수행하지 않는다.
- 실제 네트워크 테스트는 별도 Smoke Test로 분리한다.
- Secret은 Fixture, Trace, Snapshot 및 Git에 포함하지 않는다.
- 실패 경로 테스트를 성공 경로와 함께 작성한다.
- 변경 후 관련 테스트, 전체 pytest, Ruff, `git diff --check`를 수행한다.
- Work Item마다 문서와 Git Diff를 검토한 뒤 커밋한다.

---

# 4. Work Item 1 — Search Provider Decision Record

## 목표

첫 Live Web Search Adapter가 사용할 Provider와 연결 방식을 결정한다.

## 조사 항목

- API 또는 SDK 형태
- 인증 방식
- Search Result 필드
- Query당 최대 결과 수
- 날짜·Domain·언어 Filter 지원
- Timeout과 Rate Limit
- Usage 또는 비용 Metadata
- 테스트 가능성
- 약관과 데이터 처리
- Provider 장애 시 오류 형태

## 산출물

- `AIRA_SEARCH_PROVIDER_DECISION.md`
- `DECISIONS.md` 신규 결정
- Provider 설정 Schema 또는 기존 설정 확장안
- 필요한 의존성 목록

## 완료 기준

- 첫 Provider 하나를 확정한다.
- 대안 Provider와 선택 이유를 기록한다.
- 실제 API Key 없이도 Unit Test 가능한 구조를 확정한다.
- Provider 전용 객체가 Domain으로 누출되지 않도록 한다.

## 제외

- 복수 Provider 구현
- 자동 Fallback
- 가격 최적화 Routing

---

# 5. Work Item 2 — Live Web Search Adapter

## 목표

기존 `ResearchSourceSearchTool` Port를 구현하는 실제 Search Adapter를 만든다.

## 재사용 대상

- `ResearchSourceSearchTool`
- `ResearchSourceSearchResult`
- `ResearchSourceCandidate`
- `ResearchSearchQuery`

## 신규 예상 Component

- Provider Client Port 또는 최소 Wrapper
- Provider Response DTO
- Live Search Adapter
- Search Error Mapper
- Search Config

정확한 파일명은 기존 Package 구조 감사 후 Codex 작업지시에서 확정한다.

## 필수 동작

- Query 하나 실행
- 최대 Result 수 적용
- Provider 응답 정규화
- Rank 보존
- URL 검증
- 제목과 Snippet 보존
- Provider Metadata 보존
- Timeout 처리
- No Result 처리
- 인증·Rate Limit·Provider Error 구분

## Unit Test

- 정상 결과
- 결과 없음
- 잘못된 URL
- 중복 URL
- Timeout
- 인증 오류
- Rate Limit
- Provider 오류
- 최대 Result 제한
- Metadata 보존

## Smoke Test

실제 공개 Query 하나를 실행한다.

기록:

- 실행 날짜
- Provider
- Query
- Result 수
- Duration
- 오류 여부
- Secret 미노출 확인

## Acceptance Criteria

- 실제 인터넷 Search Result가 하나 이상 생성된다.
- 모든 Result가 `ResearchSourceCandidate`로 검증된다.
- Unit Test는 네트워크 없이 통과한다.
- Smoke Test는 별도 명령으로만 실행된다.
- 기존 In-memory Search Test가 유지된다.

---

# 6. Work Item 3 — HTTP/HTML Source Reader

## 목표

기존 `ResearchSourceReader` Port를 구현하는 안전한 HTTP/HTML Reader를 만든다.

## 재사용 대상

- `ResearchSourceReader`
- `ResearchSourceCandidate`
- `ResearchSourceDocument`
- `ResearchSourceDocumentSection`

## 필수 동작

- HTTP/HTTPS URL만 허용
- DNS/IP 안전성 검사
- Redirect 제한
- Timeout
- User-Agent
- Status Code 처리
- Content-Type 검사
- 최대 응답 크기
- Charset 처리
- HTML 본문 추출
- Section 생성
- Fetch 시각 기록
- Content Hash 계산
- Reader Metadata 보존

## 명시적 비지원

- PDF
- JavaScript 실행이 필요한 페이지
- 로그인 필요 페이지
- CAPTCHA
- Paywall 우회
- 파일 다운로드 자동 실행

## Unit Test

- 정상 HTML
- 정상 Plain Text
- Redirect
- 404
- 500
- Timeout
- Unsupported Content-Type
- Oversized Response
- 빈 본문
- 잘못된 Charset
- Loopback 차단
- 사설 IP 차단
- `file://` 차단
- Content Hash 안정성

## Integration Test

로컬 Fake HTTP Server 또는 Fixture Server를 사용한다.

외부 네트워크에 의존하지 않는다.

## Smoke Test

공개 정적 HTML 페이지 하나를 읽고 다음을 확인한다.

- Status
- Content-Type
- 본문 길이
- Section 수
- Content Hash
- Fetch Metadata

## Acceptance Criteria

- 실제 공개 HTML 본문을 하나 이상 읽는다.
- 실패 Source도 구조화된 실패 결과로 남는다.
- 민감 Header가 저장되지 않는다.
- Reader Unit/Integration Test가 네트워크 없이 재현된다.

---

# 7. Work Item 4 — Source Artifact Writer

## 목표

Search Result와 읽은 Source를 실행별 폴더에 안전하게 저장한다.

## 신규 예상 Component

- `SourceArtifactWriter`
- Artifact Naming Policy
- Atomic File Write Helper
- Source Manifest Schema 또는 기존 Schema 조합

## 저장 구조

```text
reports/<execution_id>/
├── request.json
├── execution.json
├── queries.json
├── search_results.json
├── sources/
│   ├── source-001.json
│   ├── source-001.md
│   └── ...
├── usage.json
├── trace.json
├── errors.json
├── result.json
└── report.md
```

## 필수 정책

- 실행 폴더 덮어쓰기 금지
- 임시 파일 후 Atomic Rename
- UTF-8
- JSON은 안정적인 Field 순서와 들여쓰기
- 파일명 Path Traversal 방지
- Source ID와 파일 연결
- 실패 Source JSON 저장
- 원문과 Metadata 분리 저장
- Secret 제거

## Unit Test

- 정상 저장
- 중복 실행 ID
- 잘못된 실행 ID
- Atomic Write 실패
- Source 파일명 안전화
- 실패 Source 저장
- JSON 재읽기
- Markdown 재읽기
- Secret Redaction

## Acceptance Criteria

- 저장 결과를 새 Process에서 다시 읽을 수 있다.
- Source JSON과 Markdown이 동일 Source ID를 가진다.
- 부분 기록만 남는 비원자적 실패를 방지한다.
- 기존 `ResearchResultWriter`와 책임이 중복되지 않도록 한다.

---

# 8. Work Item 5 — Concrete Live Research Runner

## 목표

기존 Application Service와 신규 Search·Reader·Writer를 하나의 Single-Agent
Runtime으로 연결한다.

## 재사용 대상

- `ApplicationResearchExecutionService`
- `ResearchExecutionRunner`
- `ResearchRequest`
- Task Decomposer
- Query Planner
- Search Port
- Reader Port
- Result Guardrail
- Result Writer
- ExecutionBudget
- Agent Trace

## 필수 실행 순서

1. Application Request 검증
2. ResearchRequest 변환
3. 실행 Artifact 폴더 준비
4. Trace 시작
5. Query 생성
6. Search 실행
7. Candidate 중복 제거와 제한
8. Reader 실행
9. Source Artifact 저장
10. 기본 결과 생성
11. Guardrail 검증
12. Usage·Trace·오류 저장
13. Application Output 반환

## 초기 Planning 정책

첫 통합에서 다음 중 하나를 선택한다.

### 경로 A

Deterministic Query Planner 사용

장점:

- Search·Reader 통합 검증에 집중
- 외부 LLM 변수 제거
- 실행 재현성 높음

### 경로 B

OpenAI Planner 연결

조건:

- Usage 추출 연결
- Timeout
- 오류 정규화
- 실제 API Smoke Test
- LLM 호출 Budget

초기 권장은 경로 A로 Vertical Slice를 먼저 통과한 뒤 경로 B를 추가하는 것이다.

## Unit Test

- Search와 Reader 모두 성공
- 일부 Reader 실패
- Search 결과 없음
- Search 실패
- Budget 초과
- Artifact Write 실패
- Guardrail 실패
- Trace 생성
- Application Output 검증

## Integration Test

Fake Search Adapter + Fake HTTP Reader + 실제 Artifact Writer 조합을 사용한다.

## Acceptance Criteria

- 하나의 Runner 호출로 실행별 폴더가 완성된다.
- 성공과 부분 실패가 구분된다.
- 최대 Source 수가 강제된다.
- Trace와 오류가 누락되지 않는다.
- 기존 Offline Runtime과 독립적으로 실행된다.

---

# 9. Work Item 6 — CLI Live Mode

## 목표

사용자가 Offline Baseline과 Live Runtime을 명확히 선택해 실행하도록 한다.

## 후보 Interface

```text
aira research --mode offline ...
aira research --mode live ...
```

또는 별도 Subcommand를 검토한다.

```text
aira research-local ...
aira research-live ...
```

최종 명칭은 기존 CLI 호환성과 도움말 구조를 확인한 뒤 결정한다.

## 필수 CLI 입력

- 연구 질문
- Output Root
- 최대 Query 수
- 최대 Search Result 수
- 최대 Source 수
- HTTP Timeout
- 네트워크 사용 승인
- 선택적 Provider 설정

## 필수 출력

- execution_id
- 최종 상태
- 저장 폴더
- Search Result 수
- Reader 성공·실패 수
- 전체 Duration
- 오류 요약

## 종료코드

최소 구분:

- 성공
- 입력 오류
- 설정 또는 인증 오류
- Search 실패
- Reader 전체 실패
- Artifact 저장 실패
- 내부 오류

## E2E Test

### Offline E2E

기존 동작 보존

### Live Fake E2E

Fake Search/Reader를 사용해 네트워크 없이 전체 CLI 실행

### Live Smoke E2E

명시적 환경변수 또는 옵션이 있을 때만 실제 네트워크 사용

## Acceptance Criteria

- 기존 Offline 명령이 깨지지 않는다.
- Live 실행은 사용자가 명시적으로 선택한다.
- Secret이 CLI 출력에 나타나지 않는다.
- 실행 폴더 경로가 출력된다.
- 실패 시 비정상 종료코드를 반환한다.

---

# 10. Work Item 7 — OpenAI Planning Integration

## 목표

기존 OpenAI Planning Capability를 Live Runtime에 연결한다.

## 선행 조건

- Work Item 2~6 완료
- Search와 Reader의 실제 E2E 성공
- Artifact 및 Trace 구조 안정화

## 필수 작업

- Application/Research Request → Planning Input Adapter
- Planner Usage 추출
- Timeout
- 오류 정규화
- Token Budget
- Planning Artifact 저장
- 실제 API Smoke Test
- Deterministic Planner Fallback 정책

## Acceptance Criteria

- 동일 요청에서 Deterministic과 OpenAI Planning 결과를 비교할 수 있다.
- Planner Usage가 `usage.json`에 포함된다.
- Planner 실패가 Search·Reader 오류와 구분된다.
- API Key가 저장되지 않는다.

---

# 11. 공통 테스트 Gate

각 Work Item 완료 시:

```bash
pytest <관련 테스트>
ruff check <관련 경로>
git diff --check
```

통합 단위 완료 시:

```bash
pytest -q
ruff check app tests scripts examples
git diff --check
```

최신 기준선:

```text
4088 passed
All checks passed
```

기준선 변경은 새 테스트 추가로 증가할 수 있다.

실패 테스트를 삭제하거나 완화하여 통과시키지 않는다.

---

# 12. 공통 문서 Gate

각 Work Item은 필요에 따라 다음을 갱신한다.

- `DECISIONS.md`
- `ROADMAP.md`
- `LEARNING_LOG.md`
- `AIRA_PROJECT_AUDIT_REPORT.md`
- `AIRA_CAPABILITY_MATRIX.md`
- `AIRA_TARGET_ARCHITECTURE.md`
- `AIRA_INTEGRATION_PLAN.md`

중요 설계 변경은 코드보다 먼저 또는 같은 커밋에서 기록한다.

---

# 13. 권장 커밋 단위

1. `docs: define AIRA target architecture and integration plan`
2. `docs: select initial web search provider`
3. `feat: add live research search adapter`
4. `feat: add safe HTTP HTML research reader`
5. `feat: persist live research source artifacts`
6. `feat: integrate live research runner`
7. `feat: add live research CLI mode`
8. `feat: connect OpenAI planning to live research`

각 커밋은 독립적으로 테스트되고 되돌릴 수 있어야 한다.

---

# 14. Historical Next Work Checkpoint — Search Provider Decision

> 이 section은 초기 integration planning 당시의 checkpoint다. Search Provider Decision은
> 이미 완료된 과거 작업이며 현재 다음 작업이 아니다.

당시 바로 수행할 작업은 다음이었다.

```text
Work Item 1 — Search Provider Decision Record
```

코드 구현 전에 다음을 수행한다.

1. 기존 의존성 및 설정 구조 감사
2. Search Provider 후보 조사
3. 공식 문서 기반 비교
4. Provider 하나 선택
5. `DECISIONS.md`에 결정 기록
6. Codex 구현 작업지시서 작성

# 15. Historical 2026-08-18 Integration Work Item

> 이 section의 Step 4A 계획은 완료된 historical checkpoint다. 최신 상태는 Section 16을
> 따른다.

당시 authoritative product position:

```text
Stage 5 — Internet Research Expansion
Patent Research Vertical Slice
Step 3G — FINAL PASS
Next: Step 4A — Patent Metadata Expansion
```

# 16. 2026-08-23 Post-Step-4G Integration Work Item

현재 authoritative product position은 `ROADMAP.md`를 따른다.

```text
Stage 5 — Internet Research Expansion
Academic Research Vertical Slice
Step 5C — Evidence Persistence / CLI Exposure — FINAL PASS
```

Step 4H Integration Work Item은 offline scripted UAT와 artifact review를 통과했다.
CLI usability, provider 이전 request rejection, 비용 경계, 두 publication cell, exact provenance,
legal/ranking field 부재 및 scope notice를 검증했다. 발견된 artifact wording debt도 수정했다.

Step 5A Integration Work Item은 scholarly identity/access schema, deterministic identifier
normalization, bounded provider contract, OpenAlex adapter, workflow integration 및 1-request
live metadata smoke를 통과했다.

Step 5B Integration Work Item은 exact abstract documents, whole-abstract evidence, omission과
partial failure preservation, bounded workflow, offline UAT 및 full regression을 통과했다.

다음 Integration Work Item:

```text
Stage 5 — Academic Research Vertical Slice
Step 5C — Academic Evidence Persistence / CLI Exposure
```

Step 5C는 exact scholarly evidence를 deterministic artifact와 bounded user command에
연결한다. semantic judgment, PDF/full-text acquisition 및 permission 판단은 제외한다.

Stage 5 완료 후:

```text
Stage 6 — Integrated RAG
```

Stage 6는 기존 charter대로 Parsing, Chunking, Hybrid Retrieval, Reranking 및 Citation
Grounding의 통합 책임을 가진다.

# 17. 2026-08-23 Step 5C Final Integration Work Item

Step 5C는 exact scholarly evidence를 private deterministic Markdown/JSON과 bounded CLI에
연결하고 offline E2E, one-request OpenAlex live smoke, full regression 및 artifact review UAT를
통과했다. Stage 5 Internet Research Expansion은 사용자 gate까지 완료했다.

Stage 6 Step 1 감사와 Step 2 cross-source ingestion은 완료됐다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 3 — Deterministic Keyword Retrieval
```

Step 3는 exact `DocumentChunk` corpus를 대상으로 external call 없는 lexical retrieval
baseline을 만든다. Persistent vector index, hybrid fusion, reranking과 context budget은 각각
독립된 후속 integration gate로 유지한다.

# 18. 2026-08-24 Stage 6 Step 1–2 Integration Work Item 완료

Step 1 감사에서 기존 chunking, embedding/cache, semantic top-k, context/citation 및 eval 부품의
재사용 범위를 확인했다. Step 2는 Web/Patent/Academic 등 서로 다른 source document가 같은
chunk boundary로 들어갈 때 exact source/document/range provenance를 보존하는 최소 통합
slice를 완성했다.

```text
ResearchSourceDocumentSet
→ CrossSourceChunkIngestionRuntime
→ DocumentChunk + typed provenance
→ existing deterministic embedding
→ existing InMemoryVectorStore
→ retrieval result with traceable source/document/offset
```

Step 2는 external provider, OpenAI, persistent index 또는 ranking judgment를 추가하지 않는다.
Full repository 5,808 tests와 focused 71 tests가 통과했다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 4 — Persistent Vector Index Lifecycle
```

# 19. 2026-08-24 Stage 6 Step 3 Integration Work Item 완료

Step 3는 cross-source exact chunks를 external call 없는 keyword retrieval에 연결하고 표준
`RetrievalResult`와 기존 RAG context/citation path까지 통합했다.

```text
CrossSourceChunkIngestionResult
→ unique Unicode query tokens
→ transparent token-coverage score
→ deterministic ranked RetrievalResult
→ existing RagContext + citations
→ exact source/document/chunk/offset trace
```

점수는 corpus statistics나 semantic judgment 없이 query coverage만 사용한다. 따라서 BM25나
hybrid retrieval을 대체하는 최종 알고리즘이 아니라 이후 개선을 비교하는 baseline이다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 4 — Persistent Vector Index Lifecycle
```

Step 4에서는 기존 persistent embedding cache와 별도로 searchable index의 저장, 복원,
idempotent update, deletion 및 corruption behavior를 typed offline contract로 고정한다.


# 20. 2026-08-24 Stage 6 Step 4 Integration Work Item 완료

Step 4는 embedding calculation cache와 별도로 searchable corpus state를 generation snapshot으로
저장하고 재시작 후 검색하는 lifecycle을 완성했다.

```text
CrossSourceChunkIngestionResult
→ deterministic EmbeddedDocumentChunk
→ PersistentVectorIndexSnapshot (generation + SHA-256)
→ private atomic FilePersistentVectorIndex
→ restart-safe PersistentVectorIndexSearchRuntime
→ RetrievalResult
→ existing RagContext + exact citations
```

Upsert와 targeted deletion은 최신 generation을 만들며 동일한 변경은 no-op이다. Missing snapshot은
정상 empty state지만 corrupt, unsafe path, incompatible model/dimensions 및 clock rollback은
명시적으로 실패한다. Full repository 5,931 tests와 focused E2E 97 tests가 통과했고 외부 요청은
0회였다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 5 — Deterministic Hybrid Retrieval Fusion
```

Step 5는 keyword와 persistent semantic result를 같은 `chunk_id` 기준으로 결합하는 설명 가능한
baseline을 만든다. Learned reranking, source authority, academic/patent quality 또는 final-answer
judgment는 포함하지 않는다.


# 21. 2026-08-24 Stage 6 Step 5 Integration Work Item 완료

Step 5는 Step 3 lexical 결과와 Step 4 restart-safe semantic 결과를 exact chunk identity로 결합해
표준 RAG context/citation path까지 연결했다.

```text
DeterministicKeywordRetriever ───────────┐
                                        ├─ DeterministicHybridRetriever (RRF)
PersistentVectorIndexSearchRuntime ─────┘
→ HybridRetrievalWorkflowResult
→ existing RetrievalResult / RagContext / RagCitation
```

RRF는 raw score를 합하지 않고 source ranks만 결합한다. 각 channel signal과 contribution을
보존하고 conflict/duplicate/rank drift를 명시적으로 거부한다. Full repository 6,001 tests와
focused cross-source E2E 90 tests가 통과했으며 외부 요청은 0회였다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 6 — Bounded Evidence Reranking
```

Step 6는 기존 semantic reranking 부품을 감사한 뒤 hybrid candidate pool 이후의 bounded
relevance ordering을 통합한다. Context budget과 final citation grounding은 각각 후속 gate다.


# 22. 2026-08-24 Stage 6 Step 6 Integration Work Item 완료

Step 6는 Step 5 hybrid candidate pool에 bounded relevance evaluation을 연결하고 exact RAG
context/citation path까지 통합했다.

```text
HybridRetrievalWorkflowResult
→ bounded evidence relevance evaluation
→ CrossSourceEvidenceRerankingResult
→ relevant evaluated RetrievalResult
→ existing RagContext + exact RagCitation
```

예산 소진 후보는 `unevaluated`로 보존하고 irrelevant와 구분한다. Direct/partial 후보만 context에
포함하지만 모든 hybrid signal과 provider execution identity는 audit result에 남는다. Full
repository 6,039 tests와 offline cross-source E2E/UAT가 통과했으며 외부 요청은 0회였다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 7 — Bounded RAG Context Budget
```

Step 7은 selected evidence의 item/token/byte ceiling과 deterministic packing을 정의한다. Final
answer generation이나 citation quality 판정은 이 단계에 포함하지 않는다.


# 23. 2026-08-24 Stage 6 Step 7 Integration Work Item 완료

Step 7은 Step 6의 relevant evaluated candidates와 기존 `RagContext` 사이에 auditable whole-chunk
packing boundary를 추가했다.

```text
CrossSourceEvidenceRerankingResult
→ relevant RetrievalResult candidates
→ DeterministicRagContextPacker
→ RagContextPackingResult
→ bounded existing RagContext + exact RagCitation
```

각 candidate는 included 또는 omitted로 완전히 분류되며 rendered item/byte/estimated-token 비용과
omission reason을 보존한다. Full repository 6,088 tests와 offline persistent-restart context-budget
E2E/UAT가 통과했으며 외부 요청은 0회였다.

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 8 — Grounded Answer Citation Validation
```

Step 8은 existing grounded prompt/answer service와 citation contracts를 감사한 뒤 bounded context에
없는 marker, missing support 및 answer/citation mismatch를 검출하는 offline-first boundary를 정한다.


# 24. 2026-08-24 Stage 6 Step 8 Integration Work Item 완료

Step 8은 Step 7의 bounded exact context 이후 답변 text를 statement/citation/evidence pair로 분해하고
각 pair의 semantic evaluation 상태를 bounded하게 분류하는 validation boundary를 완성했다.

완료된 integration:

- typed request, budget, statement, pair, usage 및 passed/failed/incomplete result
- deterministic exact-line parser와 strict citation marker validation
- context citation과 exact retrieval evidence의 pair binding
- bounded batch/single semantic evaluator orchestration
- explicit uncited, rejected, unevaluated 및 abstention behavior
- controlled cross-source offline E2E/UAT와 full repository regression

운영 경계:

- OpenAI/OpenAlex/EPO/network requests 0
- semantic quality, final-answer quality 및 source authority는 검증하지 않음
- chronology, patent/academic quality 및 legal conclusion을 생성하지 않음

다음 Integration Work Item:

```text
Stage 6 — Integrated RAG
Step 9 — Bounded Grounded Answer Workflow
```

Step 9는 bounded context, answer generation과 citation validation을 하나의 typed workflow로 연결한다.
Provider 호출·token budget, generation failure, validation failure/incomplete 및 abstention을 서로 다른
결과 상태로 보존하며 offline controlled path를 먼저 검증한다.


# 25. 2026-08-24 Stage 6 Step 9 Integration Work Item 완료 / Stage 6 COMPLETE

Step 9는 Step 7 packed context, 기존 grounded answer provider path와 Step 8 citation validation을
generation/validation budget 및 explicit terminal state 아래 결합했다.

완료된 integration:

- typed workflow request, generation usage, safe failure와 five-state result
- bounded generation and citation validation orchestration
- existing Responses API grounded-answer adapter with usage capture
- side-effect-free provider/evaluator factory composition
- exact packed evidence to answer and validation identity checks
- Patent/Academic offline cross-source E2E/UAT
- full repository regression `6172 passed`

Stage 6 Integrated RAG는 charter에 명시된 parsing부터 citation grounding까지 bounded answer workflow로
연결했으므로 COMPLETE다.

다음 Integration Work Item:

```text
Stage 7 — Agent Loop
Step 1 — Existing Capability Audit
```

Stage 7 Step 1은 기존 planning, tool selection, observation, evidence sufficiency, limited replanning,
termination 및 trace capability를 read-only로 감사한다. Single-Agent baseline을 우선하며 Multi-Agent는
동일 evaluation dataset에서 이점이 입증되기 전에는 도입하지 않는다.
