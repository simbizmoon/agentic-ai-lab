# AIRA CURRENT SYSTEM GUIDE

## 1. 문서 목적

본 문서는 2026-08-14 현재 `/home/moon/Project/agentic-ai-lab` 저장소에 구현·검증된
AIRA(Agentic Intelligence Research Assistant)의 실제 기능, 기본 사용 방법,
현재 한계 및 후속 개선 방향을 사용자 관점에서 정리한다.

본 문서는 다음 질문에 답하는 것을 목표로 한다.

1. 현재 AIRA는 실제로 무엇을 할 수 있는가?
2. 어떤 명령으로 실행하는가?
3. 실행 결과는 어디에 저장되는가?
4. 결과를 어떻게 해석해야 하는가?
5. 현재 무엇을 할 수 없는가?
6. 어떤 기능을 앞으로 개선하거나 확장할 것인가?

본 문서는 제품 목표를 정의하는 `AIRA_PROJECT_CHARTER.md`를 대체하지 않는다.
설계 결정은 `DECISIONS.md`, 진행상태는 `ROADMAP.md`, 학습 결과는
`LEARNING_LOG.md`를 기준으로 한다.

---

# 2. 현재 AIRA의 위치

현재 AIRA에는 세 가지 주요 연구 경로가 존재한다.

```text
1. Local Deterministic Research
2. Local Semantic Research
3. Live Web Research
```

## 2.1 Local Deterministic Research

`aira research`의 기본값이며 `aira research --mode deterministic`과 같다.
외부 Provider 없이 `WholeDocumentEvidenceExtractor`와
`DeterministicPipelineClaimBuilder`를 사용하는 역사적 offline regression 계약을
보존한다. 기존 `report.md`와 `result.json` 생성 동작도 유지한다.
Local source는 명시적 allowed root 안의 regular file이어야 하며 leaf symlink와
32 MiB 초과 raw file은 거부된다. raw byte size와 SHA-256 provenance를 기록한다.

## 2.2 Local Semantic Research

`aira research --mode semantic`은 UTF-8 TXT/Markdown, text-based PDF 및 text-bearing HWPX 문서를 실제 local
in-memory search와 reader로 처리하고 paragraph 단위 semantic evidence와 generated
claim을 만든다. query text, local path, filename, character range, PDF physical page 및 HWPX body-section provenance를
보존한다.
Semantic 실행은 `--approve-external-send`를 요구한다. 승인은 실행 단위이며 모든
source의 canonical path, raw SHA-256 및 size에 묶인다. 문서 parsing 뒤 provider
구성 직전에 같은 access policy로 다시 fingerprint하여 변경된 파일을 거부한다.
이는 practical revalidation이며 descriptor-level TOCTOU 해결은 아니다.
승인 상태 자체는 evidence/citation metadata에 저장하지 않으며 영구 approval 저장소도 없다.

```text
TXT / Markdown / Text PDF / Text-bearing HWPX
→ LocalDocumentAdapter (PDF: pypdf; HWPX: safe ZIP + defusedxml)
→ In-memory Local Search / Reader
→ ParagraphEvidenceExtractor
→ Embedding + Lexical RRF Shortlist
→ Semantic Evidence Relevance
→ Generated Claim
→ Semantic Citation / Claim Relevance / Answer Coverage
→ ResearchResult / report.md / result.json
```

Embedding, evidence relevance, claim generation은 OpenAI를 사용한다. Citation, claim
relevance, answer coverage만 기존 bounded-worker 정책에 따라 OpenAI 또는 Local을
사용한다. `provider=local`은 full-local mode가 아니며 semantic 실패를 deterministic으로
조용히 fallback하지 않는다.

## 2.3 Live Web Research

`aira research-live`는 Tavily Search, HTTP/HTML reading, semantic evidence, claim,
citation, coverage 및 bounded replanning을 포함하는 Web 중심 경로이다.

과거 Offline Baseline과 Live Single-Agent Vertical Slice 설명은 역사적 비교 기준으로
유효하며, Local Semantic Research가 세 번째 명시적 제품 경로로 추가되었다.

# 3. 현재 구현된 핵심 기능

## 3.1 Research Request

사용자는 최소한 다음 연구 의도를 입력할 수 있다.

- Research Question
- Research Objective
- Maximum Sources
- Output Directory

대표 실행에서 다음 입력을 사용하였다.

```text
Question:
How does the OpenAI Agents SDK support tool calling?

Objective:
Explain the concrete mechanism by which functions or tools are made
available to an agent and used during execution.
```

---

## 3.2 Live Web Search

첫 Live Search Provider는 Tavily를 사용한다.

현재 확인된 특징:

- 실제 인터넷 검색
- Provider Call 수 추적
- Provider Credit 추적
- Provider Latency 추적
- 초기 검색과 Supplemental Search가 동일 Budget 공유
- Search 호출 상한
- 중복 URL 제거
- Source Candidate 정규화

기본 Search Budget의 현재 engineering 정책:

```text
maximum_provider_calls = 2
maximum_credits = 2.0
maximum total search rounds = 2
```

따라서 Evidence가 부족하더라도 무제한 검색하지 않는다.

---

## 3.3 HTTP/HTML Source Reading

검색 결과의 URL에서 실제 웹 문서를 읽는다.

현재 Live Web Research에서는:

```text
Search Result
→ HTTP/HTML Reader
→ Research Source Document
```

흐름을 사용한다.

Search Provider가 원문 전체를 대신 제공하는 구조가 아니라,
검색과 원문 수집을 분리한다.

---

# 4. Source 품질 평가

AIRA는 검색결과를 그대로 Evidence로 사용하지 않는다.

현재 Live Source에는 다음과 같은 품질 신호를 적용한다.

- Authority
- Primary-source 성격
- Recency
- Completeness
- Traceability
- Provider score
- Query relevance
- Content usefulness
- Redundancy

또한 URL을 기준으로 Source Type을 정규화한다.

대표 유형:

```text
OFFICIAL_DOCUMENTATION
GOVERNMENT
ACADEMIC
OTHER
```

예:

```text
openai.github.io
→ official_documentation

developers.openai.com
→ official_documentation
```

정확한 Trusted Host 정책을 사용하며 모든 `*.github.io`를 공식 문서로
간주하지 않는다.

---

# 5. Evidence 추출과 Retrieval

## 5.1 Paragraph Candidate

Live Web 문서를 문서 전체 하나의 Evidence로 사용하지 않는다.

웹 문서에서 paragraph-sized candidate를 생성한다.

현재 원칙:

- Source당 최종 Evidence 수 제한
- Evidence excerpt 길이 제한
- 원문 character offset 보존
- Navigation, 코드 실행 예시, 링크 목록 등의 noise filtering

## 5.2 Hybrid Retrieval

현재 Retrieval은 단순 Keyword 또는 Embedding 하나에 의존하지 않는다.

```text
Paragraph Candidates
       ↓
Embedding Rank ──┐
                 ├─ RRF Hybrid Shortlist
Lexical Rank ────┘
       ↓
LLM Semantic Evidence Relevance
       ↓
Precision-first Final Evidence Selection
```

RRF는 Reciprocal Rank Fusion을 의미한다.

Embedding과 Lexical Ranking의 순위를 합쳐 각 방식이 놓칠 수 있는
Answer-bearing Passage를 Shortlist에 포함시키는 역할을 한다.

## 5.3 Semantic Evidence Relevance

Shortlist된 Passage는 다음 관계를 평가한다.

```text
Question + Objective
        ↕
Evidence Excerpt
```

판정 범주:

```text
directly_relevant
partially_relevant
irrelevant
```

이 평가는 Source가 사실인지 판단하는 기능이 아니라,
해당 Evidence가 사용자의 질문에 실제로 답하는지를 판단하는 기능이다.

## 5.4 Precision-first Selection

Relevant Evidence가 존재하면 평가되지 않은 후보로 숫자를 채우지 않는다.

현재 정책:

```text
DIRECT 또는 PARTIAL 존재
→ 해당 Relevant Evidence만 최종 승격

Relevant 없음 + Budget exhaustion
→ best UNEVALUATED 1개 fallback

모두 평가 완료 + 모두 IRRELEVANT
→ NO_EVIDENCE
```

`UNEVALUATED`와 `IRRELEVANT`를 서로 다른 상태로 처리한다.

---

# 6. Evidence-aware Source Backfill

문서를 읽었다고 해서 반드시 좋은 Evidence가 나오는 것은 아니다.

따라서 현재 AIRA에서 `maximum_sources`는 단순히 읽은 문서 개수가 아니라
**최종적으로 Evidence를 제공하는 Source의 최대 개수**로 해석한다.

흐름:

```text
Ranked Document
→ Evidence Extraction
→ Evidence 있음
   → Source quota에 포함
→ NO_EVIDENCE
   → 다음 문서로 Backfill
```

현재 최소 Evidence Source Gate:

```text
minimum_evidence_sources = min(2, maximum_sources)
```

`maximum_sources >= 2`인데 실제 Evidence Source가 하나뿐이면
`LOW_SOURCE_DIVERSITY`를 품질 문제로 기록할 수 있다.

---

# 7. 제한된 Replanning

Evidence가 부족하면 AIRA가 한 번 더 검색할 수 있다.

현재 구조는 범용 무한 Agent Loop가 아니라 Research 목적에 맞춘
**bounded replanning**이다.

```text
Initial Search
→ Evidence Selection
→ Evidence Sufficiency / Answer Coverage 확인
→ 부족
→ Supplemental Query
→ Supplemental Search 1회
→ 신규 문서 읽기
→ 기존 자료와 합쳐 재평가
→ 종료
```

현재 핵심 제한:

```text
Supplemental Query 최대 1개
Supplemental Search 최대 1회
총 Search Round 최대 2회
```

무한 재검색을 허용하지 않는다.

---

# 8. Generative Claim Construction

초기 Baseline은 다음과 같았다.

```text
Claim.text = Evidence.excerpt
```

현재 Live Runtime은 실제 LLM을 사용해 Evidence를 Claim으로 재표현한다.

핵심 원칙:

```text
1 Evidence
→ 1 Generated Claim
```

LLM이 담당:

- Claim wording
- Claim rationale

코드가 담당:

- Claim ID
- Citation ID
- Evidence ID
- Source ID
- Document ID
- Character range
- Provenance

핵심 설계 원칙:

```text
Meaning by LLM
Provenance by code
```

---

# 9. Semantic Citation Verification

AIRA는 Claim에 Citation ID가 존재하는지만 확인하지 않는다.

다음 의미 관계도 평가한다.

```text
Claim
 ↕
Evidence
```

Support Level:

```text
fully_supported
partially_supported
unsupported
contradicted
```

결정 매핑:

```text
fully_supported
→ VERIFIED

partially_supported
→ NEEDS_REVISION

unsupported
→ REJECTED

contradicted
→ REJECTED
```

연속형 entailment score는 보조 진단 신호로 사용한다.

현재 Semantic Citation Verification은:

```text
Implemented
Tested
Live Runtime Connected
Golden Evaluated
Blind Holdout Evaluated
```

상태지만, 아직 전체 Research를 자동 차단하는 Blocking Quality Gate로
사용하지 않는다.

---

# 10. Claim Relevance Evaluation

Grounded Claim이라고 해서 반드시 사용자 질문에 답하는 것은 아니다.

따라서 AIRA는 다음 두 평가를 분리한다.

```text
Groundedness
Claim ↔ Evidence

Answer Relevance
Question + Objective ↔ Claim
```

Claim Relevance 범주:

```text
directly_relevant
partially_relevant
irrelevant
```

현재 이 기능은 Evaluated Capability이지만,
자동 Claim 삭제 또는 Blocking Gate로 사용하지 않는다.

---

# 11. Semantic Answer Coverage

개별 Claim이 관련 있어도 Claim Set 전체가 사용자의 질문을 충분히
답하지 못할 수 있다.

Answer Coverage는 다음을 평가한다.

- Covered aspects
- Missing aspects
- Overall coverage level
- Coverage score
- Rationale

Coverage Level:

```text
FULLY_COVERED
PARTIALLY_COVERED
INSUFFICIENT
```

Coverage가 부족하면 한 번의 bounded replanning을 유발할 수 있다.

Structured Output의 의미가 모순되는 경우:

```text
첫 응답 Validation 실패
→ corrective retry 최대 1회
→ 다시 실패
→ StructuredResponseValidationError
```

Schema 규칙을 느슨하게 해서 모순된 응답을 억지로 통과시키지 않는다.

---

# 12. Coverage Replanning 안전장치

Coverage Round는 신규 Evidence를 찾았다고 무조건 기존 Source를 교체하지 않는다.

현재 다음 절차가 존재한다.

- Novel document evaluation
- Novel evidence evaluation
- Strict maximum source cap
- Source substitution
- Coverage-level improvement acceptance gate

Substitution 결과가 Coverage Level을 실제로 개선하지 않으면 rollback한다.

대표 상태:

```text
accepted_level_improvement

rejected_no_level_improvement

not_attempted
```

---

# 13. Budget과 Bounded Execution

현재 AIRA는 주요 LLM 처리 단계에 Execution Budget 개념을 사용한다.

주요 제한 후보:

- maximum attempts
- maximum recorded tokens
- maximum elapsed seconds

Budget 초과는 항상 전체 Research 실패를 뜻하지 않는다.

예:

```text
성공한 Claim 생성
→ usage 기록
→ Token ceiling 초과
→ 성공한 Claim은 보존
→ 이후 Claim 생성 중단
→ 나머지 Pipeline 계속
```

이 방식을 graceful degradation으로 사용한다.

---

# 14. Observability

Live Research는 실행별 Metrics를 기록할 수 있다.

현재 측정하는 대표 항목:

- Total elapsed
- Search elapsed
- Source reading elapsed
- Evidence semantic evaluation
- Claim generation
- Citation verification
- Claim relevance
- Answer coverage
- Coverage Round별 metrics
- Search Provider call
- Search credit
- Search latency
- Recorded tokens

Observability는 Live Runtime에서는 활성화하지만,
결정론적 Baseline의 JSON 비교를 깨뜨리지 않도록 기본 Pipeline에서는
opt-in으로 관리한다.

---

# 15. Batch Optimization

Step 6.6에서는 주요 Semantic LLM fan-out을 Batch 처리했다.

Batching의 의미는 여러 Evidence를 하나의 Claim으로 합치는 것이 아니다.

```text
독립적인 여러 작업
→ 하나의 API transport 요청
→ item_id로 응답 매핑
→ 기존 의미 계약 유지
```

현재 Batch 적용 영역:

- Semantic Evidence Relevance
- Claim Generation
- Semantic Citation Verification
- Claim Relevance

논리적 작업량과 물리적 API 호출량을 분리한다.

```text
last_usage
= logical item usage

last_api_usage
= physical API usage
```

---

# 16. 현재 성능 Baseline

Step 6.6.4 대표 heavy-path baseline:

```text
tracked LLM calls ≈ 24
recorded tokens ≈ 40.9K
total elapsed median ≈ 293s
quality = 0.8845
```

최종 Step 6.6 C1 Live Run:

```text
tracked LLM calls = 10
recorded tokens = 27,248
total elapsed = 163.709s
quality = 0.8845
passed = true
```

구조적으로 확인된 physical tracked LLM call 감소:

```text
24 → 10
약 58.3% 감소
```

Token과 latency는 실행마다 변동하므로 동일 비율의 인과적 개선으로
일반화하지 않는다.

---

# 17. 기본 사용 준비

프로젝트 경로:

```bash
cd /home/moon/Project/agentic-ai-lab
```

사용 중인 Python 가상환경을 활성화한다.

프로젝트에서 사용 중인 helper가 설정된 환경에서는:

```bash
aira-env
```

를 사용한다.

Live Research에는 현재 외부 Provider credential이 필요하다.

최소한 실제 실행 환경에서 다음 Provider 설정이 준비되어 있어야 한다.

```text
OpenAI API credential
Tavily API credential
```

Secret 값은 Git에 저장하지 않는다.

---

# 18. Live Research 기본 실행

현재 실제로 반복 검증한 대표 명령:

```bash
OPENAI_TIMEOUT_SECONDS=120 aira research-live   --question "How does the OpenAI Agents SDK support tool calling?"   --objective "Explain the concrete mechanism by which functions or tools are made available to an agent and used during execution."   --maximum-sources 1   --output-dir reports/example_live_run
```

이 명령은 다음 흐름을 실행한다.

```text
Research Request
→ Query Planning
→ Tavily Search
→ HTTP/HTML Reading
→ Source Quality
→ Evidence Retrieval
→ Semantic Evidence Relevance
→ Claim Generation
→ Semantic Citation Verification
→ Claim Relevance
→ Answer Coverage
→ 필요한 경우 bounded Coverage Replanning
→ Report / Result 저장
```

주의:

CLI의 전체 옵션 목록은 코드의 CLI help를 기준으로 확인해야 한다.
본 문서는 실제 검증한 대표 옵션만 제품 사용 예제로 기록한다.

정확한 현재 옵션은 다음 명령으로 확인한다.

```bash
aira research-live --help
```

---

# 19. Local Research 실행

기존 Offline Deterministic Baseline은 `aira research` 기본 경로로 유지된다.

```bash
aira research --mode deterministic \
  --allowed-root "$PWD" \
  --question "How does grounded research use local evidence?" \
  --objective "Explain the local evidence with traceable citations." \
  --source notes.md
```

Semantic Local Research는 명시적으로 선택한다.

```bash
aira research --mode semantic \
  --approve-external-send \
  --allowed-root "$PWD" \
  --question "How does AIRA divide work between OpenAI and the local model?" \
  --objective "Explain hybrid role routing using grounded local evidence." \
  --source hybrid-routing.md
```

정확한 현재 입력 옵션은 다음으로 확인한다.

```bash
aira research --help
```

Offline 경로는 Live Web Research의 대체 제품이 아니라,
Regression 및 비교 기준으로 사용하는 것이 기본 원칙이다.

---

# 20. 실행 결과

Live Research 완료 시 CLI는 대표적으로 다음 경로를 출력한다.

```text
AIRA live report: <run-directory>/report.md
AIRA live result: <run-directory>/result.json
AIRA live quality: <score>
```

실제 예:

```text
reports/step6_6_5c1_claim_generation_batch_live/
└── aira-live-<run-id>/
    ├── report.md
    └── result.json
```

실행별 artifact가 별도의 run directory에 저장된다.

---

# 21. report.md 읽는 방법

`report.md`는 사람이 읽기 위한 Markdown Research Report이다.

현재 Report에서는 다음 내용을 중심으로 확인한다.

- Research Request
- Sources
- Evidence
- Claims
- Citations
- Quality
- 한계 및 불확실성

Report의 높은 Quality Score만으로 Semantic Answer가 완벽하다고
판단하지 않는다.

Semantic Evidence Relevance, Claim Relevance 및 Answer Coverage를
함께 봐야 한다.

---

# 22. result.json 읽는 방법

`result.json`은 프로그램이 후속 처리할 수 있는 구조화된 결과이다.

현재 주요 Top-level 영역:

```text
workspace
citation_verifications
claim_relevance_evaluations
answer_coverage_evaluation
quality
run_metrics
report
```

`workspace` 안에는 대표적으로:

```text
request
task_graph
query_set
candidate_set
document_set
evidence_set
claim_set
source_quality_evaluations
metadata
```

가 저장된다.

---

# 23. 반드시 확인할 품질 값

## 23.1 Deterministic Quality

```text
quality.overall_score
quality.passed
```

`passed=true`는 기존 deterministic quality rule을 통과했다는 의미다.

그러나 Semantic Answer Coverage와 동일한 개념은 아니다.

## 23.2 Citation

```text
citation_verifications
```

Claim이 연결 Evidence에 의해 실제 지지되는지 확인한다.

## 23.3 Claim Relevance

```text
claim_relevance_evaluations
```

Claim이 Question/Objective에 답하는지 확인한다.

## 23.4 Answer Coverage

```text
answer_coverage_evaluation.coverage_level
answer_coverage_evaluation.coverage_score
answer_coverage_evaluation.covered_aspects
answer_coverage_evaluation.missing_aspects
```

최종 답변의 내용적 충분성을 확인할 때 중요하다.

## 23.5 Metrics

```text
run_metrics
```

성능, 호출량, token 및 latency를 분석할 때 사용한다.

---

# 24. 현재 확인된 중요한 한계

## 24.1 Coverage Replanning Query 정밀도

현재 Coverage evaluator는 missing aspects를 잘 찾아도,
보완 Search가 항상 그 aspect를 직접 해결하는 Evidence를 찾는 것은 아니다.

실제 실패 예:

Question이 function-tool 등록과 runtime tool-call lifecycle을 요구했지만
최종 Evidence가:

```text
Agents + tools + built-in loop
Agents as tools / handoffs
MCP tools alongside function tools
```

에 치우쳤다.

결과:

```text
initial coverage = partially_covered
final coverage = partially_covered
```

따라서 현재 AIRA는 Coverage 부족을 감지하고 한 번 더 조사할 수 있지만,
항상 FULLY_COVERED를 보장하지 않는다.

## 24.2 Semantic Evaluator는 완전한 진실 판정기가 아니다

Citation, Evidence Relevance, Claim Relevance, Answer Coverage는 LLM 기반
Semantic Evaluation을 사용한다.

이들은 Eval Dataset으로 평가되었지만 오류 가능성이 남아 있다.

예:

```text
"The service is available during business hours."
```

같은 scoped positive statement를 지나치게 exclusive하게 해석할 수 있는
Known Failure가 Citation Judge 평가에서 확인되었다.

## 24.3 Blocking Quality Gate가 아닌 평가 기능

현재 다음 Semantic 기능은 주로 진단·평가용이다.

- Semantic Citation Verification
- Claim Relevance
- Semantic Evidence Relevance

일부 결과는 아직 자동 실행 차단이나 자동 Claim 삭제에 직접 사용하지 않는다.

## 24.4 Local Document Expansion은 진행 중

TXT/Markdown, text-based PDF 및 text-bearing HWPX Semantic Local Vertical Slice는 구현되었고 실제 CLI smoke로
`report.md`와 `result.json` 생성, relevant paragraph 선택, character/query/file
provenance, generated claim 및 semantic citation/relevance/coverage 연결을 확인했다.

그러나 다음 범위는 아직 미완성이다.

- scanned PDF/OCR (text extraction이 없는 PDF는 명확히 실패)
- HWP binary/DOCX
- line number와 table-specialized parsing
- persistent vector index/cache
- Web + Local unified Integrated RAG
- 선행특허 전문 Research

따라서 TXT/Markdown, text-based PDF 및 text-bearing HWPX vertical slice 완료를 전체 Local Document Expansion
완료로 해석하지 않는다.

## 24.5 실제 Dollar Cost 계측

현재 Recorded Token과 Provider usage는 관측 가능하지만,
모든 stage의 input/output/cached token을 실제 모델 가격과 결합한
완전한 `actual_cost_usd` 기준은 후속 개선 후보이다.

## 24.6 Embedding Usage 범위

현재 `tracked_llm_calls`는 모든 AI 관련 외부 호출 전체와 동일한 숫자가 아니다.

Embedding Provider 등의 호출이 별도의 usage 계측 범위일 수 있으므로
`tracked_llm_calls`의 의미를 정확히 유지해야 한다.

---

# 25. 현재 의도적으로 하지 않는 것

현재 Single-Agent Baseline에서 다음을 무리하게 추가하지 않는다.

- 무제한 Replanning
- 무제한 Tool Loop
- 모든 Semantic Judge를 Blocking Gate로 전환
- 모든 파일 형식 즉시 통합
- Redis/Distributed Worker
- Kubernetes
- 복잡한 Web UI
- Multi-Agent를 기본 경로로 강제
- 특정 benchmark를 위한 지속적 prompt micro-tuning

---

# 26. 현재 개선 Backlog

다음은 Known Improvement이지만 현재 즉시 수행하지 않는다.

## 26.1 Single-Agent 품질

- Coverage missing-aspect 기반 Query 정밀화
- Coverage-targeted Evidence Selection
- 더 다양한 Research Question Eval
- 반복 Live variability 평가
- Semantic Judge larger holdout
- Blocking Gate 승격 기준

## 26.2 비용

- input/output/cached token 분리
- 실제 model pricing 연결
- estimated/actual cost per run
- provider/model routing
- prompt caching 검토
- 저가 모델 또는 Local LLM 적용

## 26.3 자료 범위

- Local TXT/Markdown Runtime 통합 고도화
- PDF
- HWP/HWPX
- Academic Search
- Patent Search
- 공개 PDF
- 공식자료 전문 검색

## 26.4 Productization

- CLI UX
- Config profile
- SQLite 필요성 평가
- FastAPI 필요성 평가
- Background job 필요성 평가
- MCP 또는 ChatGPT App 연동
- Docker 및 재현 가능한 실행환경

---

# 27. 현재 Stop Rule

2026-08-09 현재 Single-Agent Live Research에 대한 추가 micro-optimization은
보류한다.

이유:

- 실제 Live Runtime 동작
- 주요 Semantic 평가 경로 통합
- Coverage failure 감지 가능
- bounded replanning 존재
- Budget 존재
- Observability 존재
- 성능 fan-out 대폭 감소
- Regression 안정성 확보
- 추가 미세조정의 개발비용 증가

현재 Baseline을 그대로 유지하여 다음 Architecture 비교 기준으로 사용한다.

---

# 28. 다음 주요 단계

다음 학습·개발 초점은 Multi-Agent System이다.

핵심 질문:

```text
Multi-Agent란 무엇인가?

언제 Single Agent보다 유리한가?

언제 사용하면 안 되는가?

Agent-as-Tool과 Handoff의 차이는 무엇인가?

Manager/Worker는 언제 필요한가?

Parallel Specialist는 언제 비용 대비 가치가 있는가?

Single-Agent 대비 실제 품질·비용·latency가 개선되는가?
```

Multi-Agent는 현재 Single-Agent를 대체하는 것으로 전제하지 않는다.

현재 Single-Agent Baseline과 동일 또는 유사한 평가 과제에서
실질적인 개선이 확인될 때만 채택 여부를 결정한다.

---

# 29. 사용자 권장 운영 방식

현재 AIRA를 사용할 때 다음 순서를 권장한다.

```text
1. 질문과 Objective를 가능한 구체적으로 작성
2. maximum_sources를 의도에 맞게 제한
3. research-live 실행
4. report.md 확인
5. result.json의 quality.passed 확인
6. Citation Verification 확인
7. Claim Relevance 확인
8. Answer Coverage와 missing_aspects 확인
9. PARTIAL/INSUFFICIENT이면 결과를 완전한 답으로 간주하지 않음
10. 중요한 실제 의사결정에는 원 Source를 다시 확인
```

AIRA는 조사 보조 시스템이며,
중요한 법률·특허·의료·재무 또는 기타 전문적 결론의 최종 전문가 판단을
대체하는 것으로 사용하지 않는다.

---

# 30. 현재 기준 요약

2026-08-14 현재 AIRA의 핵심 상태:

```text
Local Deterministic Research
→ 기본 offline 계약 유지

Local Semantic Research
→ TXT/Markdown, text-based PDF 및 text-bearing HWPX 구현·실제 smoke 검증

Live Web Research
→ 구현 및 실제 검증

Source Quality
→ 구현

Evidence-aware Backfill
→ 구현

RRF Hybrid Retrieval
→ 구현 및 Live 검증

Semantic Evidence Relevance
→ Evaluated Capability

Generative Claims
→ 구현 및 Live 검증

Semantic Citation Verification
→ Evaluated Capability

Claim Relevance
→ Evaluated Capability

Semantic Answer Coverage
→ 구현 및 Live 검증

Bounded Coverage Replanning
→ 구현

Search/LLM Budget
→ 구현

Observability
→ 구현

Batch Performance Optimization
→ 구현 및 Live 검증

Single-Agent micro-optimization
→ Deferred

Current product focus
→ Stage 4 Local Document Expansion
```

# 31. 2026-08-13 현재 시스템 갱신 — Local / Multi-Agent / Hybrid / Parallel Runtime

> 이 섹션은 2026-08-13 현재 사용자 운영 기준이다. 앞선 2026-08-09 기준 요약의
> "Next focus → Multi-Agent"는 역사적 checkpoint이며, 현재는 Phase 11까지 완료했다.

## 31.1 현재 공식 상태

```text
Local bounded worker integration       COMPLETE
OpenAI vs Local evaluation             COMPLETE
Local Multi-Agent minimum              COMPLETE
Single vs Multi-Agent evaluation       COMPLETE
Hybrid role routing                    COMPLETE
Parallelism / Runtime Scaling          COMPLETE
Hardware Upgrade Decision              CURRENT
```

## 31.2 현재 권장 Architecture

```text
Single-Agent default
+ workload-dependent Multi-Agent escalation
+ deterministic control/planning
+ OpenAI/stronger-model high-judgment escalation
+ Qwen3.5-4B bounded local workers
+ bounded-parallel HTTP source reading
```

Qwen3.5-4B 권장 역할:

- semantic citation first-pass verification
- claim relevance classification
- answer coverage review/critique

주의:

- Local `fully_covered`만으로 completeness를 확정하지 않는다.
- Qwen3.5-4B를 autonomous planner나 authoritative final factual verifier로 사용하지 않는다.

## 31.3 Source Reading Concurrency

현재 live runtime 기본값은 2이다.

```bash
unset AIRA_SOURCE_READ_CONCURRENCY
# resolved default = 2
```

명시적 fallback:

```bash
export AIRA_SOURCE_READ_CONCURRENCY=1
```

공격적 benchmark 옵션:

```bash
export AIRA_SOURCE_READ_CONCURRENCY=4
```

허용 범위는 1..8이며 잘못된 값은 runtime composition에서 거부한다.

실측 결과:

```text
Real HTTP fixed-source benchmark
c=1 mean 2.277s
c=2 mean 0.921s
c=4 mean 0.851s
```

1/2/4 모두 동일한 source별 READ/FAILED semantics를 유지했다. 따라서 현재 production
기본은 추가 압력을 크게 늘리지 않으면서 대부분의 이득을 얻은 2로 한다.

## 31.4 Local Worker 실행 예

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
unset AIRA_SOURCE_READ_CONCURRENCY
```

기본 Ollama 설정:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_TIMEOUT_SECONDS=120.0
```

## 31.5 Multi-Agent 사용 원칙

Multi-Agent는 기본값이 아니다. 다음과 같은 workload에서만 escalation 후보로 본다.

- specialist 분리가 실제 품질을 높일 가능성이 큼
- context isolation이 필요함
- failure isolation 편익이 있음
- reviewer/critic 추가 비용이 정당화됨

단순히 agent 수를 늘리기 위해 사용하지 않는다.

## 31.6 현재 검증 기준선

Phase 11 final checkpoint:

```text
Live smoke quality = 0.9345
selected documents = 2 / 2 read
ollama-local provenance observed
pytest = 4635 passed in 16.70s
Ruff = All checks passed
git diff --check = clean
commit = 5c30358
```

## 31.7 현재 다음 단계

```text
Phase 12 — Hardware Upgrade Decision
```

현재 장비에서 더 큰 Local model 또는 더 많은 parallel agent를 실행하는 것이
실제 AIRA 품질·비용·latency에 의미 있는 편익을 주는지 측정한 뒤 hardware 결정을
내린다. Phase 12 전에는 특정 업그레이드를 확정하지 않는다.


# 32. 2026-08-14 Local Document Semantic Research 갱신

> 이 섹션은 Local Document Research에 관한 최신 사용자 기준이다. 앞선 Local
> 미완성 설명은 역사적 checkpoint로 보존하되 이 섹션을 현재 상태로 우선한다.

현재 실행 경로:

```text
aira research
→ Local Deterministic Research (default, offline)

aira research --mode deterministic
→ 위 기본 경로와 동일

aira research --mode semantic
→ Local Semantic Research (explicit opt-in)

aira research-live
→ Live Web Research
```

실제 deterministic 및 semantic CLI smoke 모두 `report.md`와 `result.json`을
생성했다. Semantic smoke는 whole document가 아니라 relevant paragraph만 선택했다.

관측된 Semantic smoke 결과:

```text
evidence character range = 76..265
evidence relevance = directly_relevant / 0.95
local_path, filename, search_query_text = preserved
generated claims = 1
citations = 1
citation verification = verified / fully_supported
entailment / traceability / accuracy = 1.0 / 1.0 / 1.0
claim relevance = partially_relevant / 0.74
answer coverage = partially_covered / 0.60
report quality = 0.94 / excellent / passed
```

Partial relevance와 coverage는 runtime failure가 아니다. Fixture가 role routing은
설명하지만 grounded local evidence가 routing에 미치는 영향까지 완전히 설명하지
않는다는 한계를 올바르게 기록한 결과이다.

Text-based PDF smoke에서는 3-page fixture의 page 2 paragraph만 선택했다. Evidence는
`start_character=114`, `end_character=303`, `metadata["page_number"]="2"`를 보존했고,
citation은 동일한 excerpt와 character range를 가리켰다. Deterministic PDF smoke는
whole-document evidence이므로 여러 page를 span하며 page number를 추측하지 않았다.

HWPX real-Hancom adapter/deterministic smoke는 `Contents/section0.xml`, range `0..96`과
`hwpx_section_index="1"`을 보존했다. Semantic three-section smoke는 section 2의 relevant
paragraph만 `114..303`으로 선택했고 citation verification은 fully supported였다.

현재 지원 형식은 UTF-8 `.txt`, `.md`, `.markdown`, text-based `.pdf`, text-bearing `.hwpx`이다. PDF는 `pypdf`로 page별 text를 추출하며, 한 page section 안에 완전히 포함된 evidence는 `metadata["page_number"]`를 보존한다. HWPX는 safe ZIP direct-read와 `defusedxml`, manifest/spine 및 `sec` body classification을 사용한다. Scanned PDF/OCR, HWP binary, DOCX, table-specialized parsing, persistent vector index 및 Web+Local
unified Integrated RAG는 아직 완료되지 않았다.

현재 검증 기준:

```text
full regression = 4722 passed
Ruff = All checks passed
git diff --check = passed
```
