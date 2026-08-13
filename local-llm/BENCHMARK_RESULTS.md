# AIRA Local LLM Track — Benchmark Results

- 기준일: 2026-08-10
- 상위 저장소: `/home/moon/Project/agentic-ai-lab`
- 문서 위치: `local-llm/BENCHMARK_RESULTS.md`
- 공식 단계: Phase 5 — Local Model Benchmark
- 최초 대상: `qwen3.5:4b`
- Runtime: Ollama `0.32.6`
- 상태: **IN PROGRESS**

---

## 1. 목적

이 문서는 Local LLM benchmark의 실제 측정 결과, 실패 사례, 무효화된 실험, 해석 및 현재 의사결정을 기록한다.

`BENCHMARK_PLAN.md`가 무엇을 어떻게 측정할지를 정의한다면, 이 문서는 실제로 무엇이 측정되었고 그 결과 어떤 결정을 내렸는지를 기록하는 canonical summary이다.

원칙:

- 추정값이 아니라 실제 실행 결과만 기록한다.
- 잘못 설계된 실험은 삭제하지 않고 `INVALIDATED`로 남긴다.
- raw JSON을 Git에 commit하지 않는다.
- source repository에는 재현 가능한 harness/tests와 최종 요약/결정만 남긴다.
- 모델 역할 결정은 아직 측정하지 않은 capability까지 일반화하지 않는다.

---

## 2. Baseline

```text
CPU: Intel Core i5-9600KF
GPU: NVIDIA GeForce RTX 3060 Ti
VRAM: 8192 MiB
RAM: 31 GiB usable
Ollama: 0.32.6
Backend: CUDA
Processor: 100% GPU
Context: 4096
Parallelism: 1
Model: qwen3.5:4b
```

Phase 3 baseline에서 model load 후 VRAM 증가는 약 3886 MiB였으며, System RAM 사용량은 약 7 GiB, swap 사용량은 0 B였다.

---

## 3. Benchmark Foundation

관련 commits:

```text
2d80931 feat: add local LLM benchmark foundation
257e481 feat: add cold warm local LLM benchmark
8fc9715 feat: add verified local LLM reasoning benchmark
```

Phase 4A-3C 적용 후 repository 전체 regression:

```text
4546 passed
Ruff: All checks passed
```

---

## 4. Cold vs Warm Benchmark

| State | Total | Load | Generation throughput |
|---|---:|---:|---:|
| Cold | 10.430 s | 9.711 s | 85.76 tok/s |
| Warm | 1.084 s | 0.386 s | 88.49 tok/s |

- cold 전체 latency의 대부분은 model load였다.
- warm 상태에서는 약 1초대의 짧은 응답이 가능했다.
- generation throughput은 약 86~88 tok/s로 큰 차이가 없었다.
- `cold`는 Ollama model unload 뒤 first request이며 OS page cache까지 제거한 disk-cold를 의미하지 않는다.

---

## 5. Initial Thinking A/B — INVALIDATED

상태: **INVALIDATED FOR QUALITY COMPARISON**

무효화 이유:

1. expected answer가 잘못 정의되었다.
2. prompt에 expected answer 문자열이 포함되어 answer leakage가 발생했다.
3. 논리 문제가 유일한 해를 갖지 않았다.

따라서 해당 `quality_pass`는 reasoning 품질 근거로 사용하지 않는다.

다만 Think ON이 긴 reasoning trace를 생성하고 final response 없이 `done_reason=length`로 종료되는 runtime failure mode는 보존한다.

---

## 6. Verified Reasoning Dataset

| Case | Verified answer |
|---|---|
| `ordering-001` | `A` |
| `code-001` | `643` |
| `seating-001` | `지수` |
| `equations-001` | `8` |
| `route-001` | `6` |

```text
temperature=0.0
seed=42
keep_alive=5m
```

expected answer는 prompt와 분리하고 code-level verifier로 유일해를 확인했다.

---

## 7. Verified Reasoning — num_predict 1024

### Think OFF

```text
runs: 10
success: 10/10
quality pass: 10/10
mean latency: 2.478 s
median latency: 2.774 s
mean eval tokens: 144.4
generation throughput: 86.31 tok/s
```

### Think ON

```text
runs: 10
success: 2/10
quality pass: 2/10
mean latency: 11.672 s
median latency: 12.165 s
mean eval tokens: 948.8
mean thinking chars: 2482.8
generation throughput: 87.25 tok/s
```

Think ON의 8/10은 `num_predict=1024`를 소진하며 `done_reason=length`로 종료했다.

---

## 8. Thinking Budget Sweep — 2048

```text
Think OFF
success: 5/5
quality: 5/5
mean latency: 2.843 s
mean eval tokens: 144.4

Think ON
success: 4/5
quality: 4/5
mean latency: 16.259 s
mean eval tokens: 1292.8
```

`route-001`은 Think ON에서 2048 tokens를 모두 사용하고 length 종료했다.

---

## 9. Thinking Budget Sweep — 3072

```text
Think OFF
success: 5/5
quality: 5/5
mean latency: 2.788 s
mean eval tokens: 144.4
generation throughput: 87.37 tok/s

Think ON
success: 5/5
quality: 5/5
mean latency: 17.309 s
mean eval tokens: 1381.0
mean thinking chars: 3437.6
generation throughput: 85.71 tok/s
```

가장 긴 Think ON case:

```text
route-001
eval tokens: 2489
total latency: 29.907 s
quality: pass
```

---

## 10. Current Interpretation

동일 5/5 accuracy에서:

```text
Think ON latency / Think OFF latency ≈ 6.2x
Think ON eval tokens / Think OFF eval tokens ≈ 9.6x
```

현재 verified deterministic reasoning set에서는 Think ON의 accuracy gain이 관찰되지 않았다.

그러나 이 결과만으로 Think ON이 모든 AIRA task에서 불필요하다고 결론 내리지 않는다. AIRA-native complex reasoning, evidence comparison, contradiction, critique, synthesis에서 별도 검증한다.

---

## 11. Current Qwen3.5-4B Decision

**Status: PROVISIONAL SMALL WORKER CANDIDATE**

Default:

```text
think=false
```

현재 정책:

```text
Simple / bounded Worker Task
→ Qwen3.5-4B, think=false

Complex Reasoning Task
→ think=true 자동 기본값으로 사용하지 않음
→ AIRA-native benchmark에서 quality gain 측정
→ stronger model escalation과 비교
```

Think ON은 충분한 generation budget이 필요하며 현재 5-case set에서는 `num_predict=3072`에서 5/5 completion이 확인되었다. 이를 production 기본 budget으로 확정하지 않는다.

---

## 12. Raw Artifact / Git Policy

현재:

```text
git ls-files 'evals/results/local_llm/*.json'
→ 출력 없음

git status --ignored --short evals/results/local_llm/
→ !! evals/results/local_llm/
```

따라서 raw JSON은 Git tracked artifact가 아니다.

장기 정책:

```text
large/raw canonical experiments → /mnt/ai-data/experiments/
source/tests/harness            → Git repository
summary/decisions               → local-llm/BENCHMARK_RESULTS.md
```

---

## 13. Completed Checkpoints

- [x] benchmark foundation
- [x] cold/warm measurement
- [x] runtime metrics normalization
- [x] reproducible generation controls
- [x] verified deterministic reasoning dataset
- [x] Think OFF/ON A/B
- [x] failure capture
- [x] Thinking budget sweep 1024 / 2048 / 3072
- [x] Qwen3.5-4B Small Worker 잠정 inference policy

---

## 14. Phase 5B-1 — Korean Instruction Following

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
num_predict: 256
repetitions: 3
cases: 8
runs: 24
```

Repository validation before live run:

```text
pytest: 4551 passed
ruff: All checks passed
```

Official Think OFF result:

```text
runtime success: 24/24
instruction pass: 15/24 = 62.5%
deterministic checks: 27/36 = 75.0%
mean total latency: 675.25 ms
mean eval tokens: 6.875
```

Per-case result:

```text
PASS
exact-001        3/3
extract-001      3/3
lines-001        3/3
transform-001    3/3
negative-001     3/3

FAIL
order-001        0/3
selection-001    0/3
format-001       0/3
```

Observed deterministic failures:

```text
order-001
expected: 바나나, 사과, 포도
actual:   바나나, 포도, 사과

selection-001
expected: C
actual:   A

format-001
expected: 도시=서울;온도=24
actual:   서울=24;온도=24
```

All three failures repeated identically across all three runs at temperature 0 and seed 42.
The failure pattern is therefore treated as a reproducible capability limitation under the current Think OFF configuration rather than a runtime failure.

### Think ON diagnostic

The three failed cases were rerun once with:

```text
think: true
num_predict: 3072
temperature: 0.0
seed: 42
```

Result:

```text
selection-001
PASS
response: C
eval tokens: 780
total latency: 9.315 s

format-001
PASS
response: 도시=서울;온도=24
eval tokens: 227
total latency: 3.079 s

order-001
FAIL
done_reason: length
final response: empty
eval tokens: 3072
thinking chars: 9958
total latency: 39.439 s
```

Interpretation:

- Think ON recovered the multi-constraint selection case.
- Think ON also recovered the strict key/value binding case, but at substantially higher generation cost.
- Korean lexical ordering still failed to complete within a 3072-token reasoning budget.
- Deterministic tasks such as lexical sorting should prefer deterministic code/tool execution rather than longer LLM reasoning.
- Structured formatting failures should be tested next with native structured output / JSON Schema rather than using Think ON as the default workaround.

### Phase 5B-1 decision

Status:

**COMPLETE — CAPABILITY NOT FULLY ACCEPTED**

Qwen3.5-4B remains a Small Worker candidate, but the prior provisional acceptance is narrowed.

Current policy:

```text
simple exact output / extraction / transformation
→ Think OFF remains viable

multi-constraint judgment
→ do not assume Think OFF reliability
→ test Think ON or stronger-model escalation

strict structured data
→ prefer constrained structured output
→ do not use Think ON as the primary formatting mechanism

deterministic lexical ordering
→ prefer deterministic code/tool execution
```

The official B1 score remains the Think OFF 24-run result.
The Think ON runs are diagnostic and do not replace or rescore the B1 benchmark.

---

## 15. Phase 5B-2 — Structured Output / JSON Schema

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
num_predict: 256
repetitions: 3
cases: 3
modes: prompt_only / json / json_schema
runs: 27
```

Official result:

| Mode | Runtime | JSON parse | Schema | Exact value |
|---|---:|---:|---:|---:|
| prompt_only | 9/9 | 6/9 | 6/9 | 6/9 (66.7%) |
| json | 9/9 | 9/9 | 9/9 | 9/9 (100%) |
| json_schema | 9/9 | 9/9 | 9/9 | 9/9 (100%) |

Mean generation metrics:

```text
prompt_only
mean total: 1127.93 ms
mean eval tokens: 25.0

json
mean total: 737.08 ms
mean eval tokens: 23.33

json_schema
mean total: 734.91 ms
mean eval tokens: 23.33
```

Latency comparison is not treated as a controlled speed conclusion because the first prompt-only request included the cold model load while later modes were warm.

### Prompt-only failure pattern

`seat-schedule-001` failed 3/3 in prompt-only mode.

The semantic values were correct, but the model wrapped the JSON-like body with extra formatting text/backticks, so parsing the complete response with `json.loads` failed.

Therefore the failure was not a value-extraction failure; it was a strict serialization/compliance failure.

### Constrained output result

Both `format="json"` and `format=<JSON Schema>` produced:

```text
runtime success: 9/9
JSON parse: 9/9
strict Pydantic schema: 9/9
exact expected values: 9/9
```

under the current 3-case dataset.

### Phase 5B-2 decision

Status:

**COMPLETE — CONSTRAINED STRUCTURED OUTPUT ACCEPTED FOR CURRENT TEST SCOPE**

Current policy:

```text
strict structured worker task
→ do not rely on prompt-only JSON
→ prefer JSON Schema when a schema is known
→ format="json" remains a fallback when only valid JSON is required
```

JSON Schema is preferred for AIRA typed outputs because the application already has Pydantic schemas and strict validation, even though `json` and `json_schema` achieved the same 9/9 exact result on this small dataset.

This result narrows the B1 formatting concern:

```text
plain-text strict formatting
→ unreliable in B1

native constrained structured output
→ 100% exact in B2 current scope
```

The result does not yet establish reliability for large/deep schemas, optional/union fields, long outputs, tool schemas, or production AIRA workloads.

---

## 16. Phase 5B-3 — Tool Selection / Native Tool Calling

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
repetitions: 3
cases: 4
selection runs: 12
native runs: 12
```

Repository validation before live run:

```text
pytest: 4565 passed
ruff: All checks passed
```

The benchmark reused the actual AIRA registered document tools:

```text
get_document_statistics
extract_document_keywords
```

Cases:

```text
statistics-001
→ expected tool: get_document_statistics

keywords-001
→ expected tool: extract_document_keywords

direct-001
→ expected: no tool

multiple-ops-001
→ expected: no tool
   because the current AIRA workflow allows at most one Tool
   and requires the user to split requests that need different Tools
```

### 5B-3a — Constrained Tool Selection

Official result:

```text
9/12 = 75.0%
```

Per-case:

```text
PASS
statistics-001    3/3
keywords-001      3/3
multiple-ops-001  3/3

FAIL
direct-001        0/3
```

After tightening `tool_name` to the actual registry names plus JSON null,
`direct-001` still selected `get_document_statistics` in all three runs.

Therefore this is treated as a reproducible tool-selection limitation,
not a loose-schema artifact.

Decision:

**COMPLETE — TOOL SELECTION NOT FULLY ACCEPTED**

Current interpretation:

```text
explicit registered-tool routing
→ reliable on the current statistics / keywords cases

no-tool decision in constrained selector
→ unreliable on the current direct-explanation case

AIRA one-tool multi-operation policy
→ correctly represented by null in 3/3 constrained-selection runs
```

### 5B-3b — Ollama Native Tool Calling

Official aggregate score:

```text
9/12 = 75.0%
```

The aggregate is split because the three failures are policy failures,
not failures to identify the required functions.

Core native behavior:

```text
single-tool selection:
  statistics 3/3
  keywords   3/3

exact arguments:
  statistics 3/3
  keywords   3/3

existing AIRA dispatcher validation/execution:
  statistics 3/3
  keywords   3/3

native no-tool decision:
  direct 3/3

core native behavior:
  9/9
```

AIRA-specific one-tool policy:

```text
multiple-ops-001
expected: no tool
actual: two tool calls
result: 0/3 policy compliance
```

The model selected both semantically appropriate tools rather than abstaining.
This demonstrates native multi-tool capability but violates the current
AIRA workflow rule that a request requiring different tools must be split.

Decision:

**COMPLETE — NATIVE CORE TOOL CALLING ACCEPTED FOR CURRENT SINGLE-TOOL SCOPE; AIRA MULTI-OP POLICY NOT ACCEPTED**

Current policy:

```text
single known tool + typed arguments
→ native Ollama tool calling is viable

direct request requiring no tool
→ native Ollama path is viable on current case

free/constrained selector
→ do not assume reliable no-tool judgment

multi-operation request under AIRA one-tool policy
→ enforce orchestration policy outside the model or validate/reject multiple calls
```

This benchmark does not yet establish reliability for larger registries,
tool-result second-turn synthesis, argument correction loops, state-changing tools,
approval-required tools, or production research tools.

---

## 17. Phase 5B-4 — Research Planning

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
cases: 3
repetitions: 3
official num_predict: 1536
diagnostic num_predict: 3072
```

Repository validation before live run:

```text
pytest: 4572 passed
ruff: All checks passed
```

The benchmark reused actual AIRA planning objects and validators:

```text
ResearchTask
ResearchTaskGraph
ResearchSearchQuery
ResearchSearchQuerySet
```

The model therefore had to produce planning objects that passed the same
identity, dependency, graph, task-reference, query-uniqueness, and source-policy
constraints used by the application.

### Official 1536-token baseline

Task decomposition:

```text
run pass: 0/9
semantic checks: 15/54 = 27.8%
mean total latency: 11.56 s
mean eval tokens: 835.33
```

Query planning:

```text
run pass: 0/9
semantic checks: 0/54
mean total latency: 19.28 s
mean eval tokens: 1536.0
```

All nine query runs hit the configured generation limit, so the 1536-token
query score alone was not treated as sufficient evidence of planning inability.

### 3072-token diagnostic

Task decomposition:

```text
run pass: 0/9
semantic checks: 15/54 = 27.8%
```

Stable non-budget failures:

```text
memory-001
→ done=stop
→ 470 eval tokens
→ duplicate task IDs
→ ResearchTaskGraph rejected: task IDs must be unique

rag-agent-001
→ done=stop
→ 500 eval tokens
→ task graph structurally valid
→ synthesis_not_searchable
→ synthesis_dependencies
→ 4/6 semantic checks
```

Budget-related task failure:

```text
seat-001
→ 3/3 done=length
→ 3072 eval tokens
→ JSON incomplete
```

Query planning diagnostic:

```text
run pass: 0/9
semantic checks: 3/54 = 5.6%
```

`memory-001` and `seat-001` still stopped by length in all three runs at
3072 tokens.

`rag-agent-001` completed at 1585 tokens but the generated query set was rejected.

Primary confirmed validation failure:

```text
all query request IDs must match the query set request_id
```

The model incorrectly used task IDs such as:

```text
local-plan-rag-agent-001-task-001
local-plan-rag-agent-001-task-002
```

as `request_id` values instead of:

```text
local-plan-rag-agent-001
```

The completed `rag-agent-001` plan also showed additional planning drift:
all generated queries were typed as `focused`, `preferred_source_types`
were empty, and more queries were generated than required by the bounded plan.

### Phase 5B-4 decision

Status:

**COMPLETE — RESEARCH PLANNING CAPABILITY NOT ACCEPTED FOR QWEN3.5-4B**

Observed failure classes:

```text
task identity integrity
→ duplicate task IDs

orchestration semantics
→ synthesis search/dependency policy not preserved

bounded planning
→ task/query expansion can exhaust 1536 and 3072 token budgets

query identity integrity
→ request_id confused with task_id

query planning policy
→ required query types/source preferences not reliably preserved
```

Current role policy:

```text
Qwen3.5-4B
→ do not use as autonomous AIRA research planner

deterministic AIRA planner
→ remains authoritative for task decomposition and query construction

local 4B model
→ may still be used for bounded downstream worker tasks after a valid plan exists
```

Increasing generation budget further is not required for the current role
decision because multiple completed non-length runs already exhibit structural
and orchestration failures.

---

## 18. Phase 5B-5 — Claim Relevance / Evidence Judgment

### 5B-5a — Claim Relevance

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
num_predict: 256
response schema: ClaimRelevanceJudgment
DEV dataset: claim-relevance-golden-v2 / 2.0.0
HOLDOUT dataset: claim-relevance-holdout-v2 / 2.0.0
```

Repository validation before live run:

```text
pytest: 4578 passed
ruff: All checks passed
```

The benchmark reused:

```text
ClaimRelevanceJudgment
ClaimRelevanceEvaluationRunner
build_claim_relevance_golden_dataset_v2()
build_claim_relevance_holdout_dataset_v2()
```

The local evaluator also reused the exact AIRA
`CLAIM_RELEVANCE_INSTRUCTIONS`.

#### DEV result

```text
16/18 = 88.9%
false directly relevant: 0
false irrelevant: 1
```

Per class:

```text
directly_relevant: 6/6
partially_relevant: 5/6
irrelevant: 5/6
```

Observed failures:

```text
v2-partial-004-cost-observability
expected: partially_relevant
actual: irrelevant

v2-irrelevant-004-versioning
expected: irrelevant
actual: partially_relevant
```

Interpretation:

```text
cost observability
→ model under-valued a materially useful measurement signal

prompt versioning
→ model over-promoted unrelated operational context
```

The DEV failures therefore occurred at relevance-boundary classification,
not at structured-output parsing.

#### Blind HOLDOUT result

```text
18/18 = 100.0%
false directly relevant: 0
false irrelevant: 0
```

Per class:

```text
directly_relevant: 6/6
partially_relevant: 6/6
irrelevant: 6/6
```

The HOLDOUT dataset was not used to tune the local evaluator configuration
between DEV and HOLDOUT execution.

### Phase 5B-5a decision

Status:

**COMPLETE — CLAIM RELEVANCE ACCEPTED FOR CURRENT TEST SCOPE**

Current interpretation:

```text
structured semantic relevance classification
→ strong

direct / partial / irrelevant distinction
→ strong on blind holdout

false-direct risk
→ 0 on DEV and HOLDOUT

false-irrelevant risk
→ 1 on DEV, 0 on HOLDOUT

boundary judgment
→ not perfect; retain deterministic/schema validation and escalation policy
```

Current role policy:

```text
Qwen3.5-4B
→ suitable candidate for bounded claim-relevance worker

use cases:
- claim relevance filtering
- claim prioritization
- semantic triage before expensive stronger-model evaluation

not established by this benchmark:
- factual truth
- evidence support
- source authority
- citation correctness
```

The claim-relevance prompt explicitly separates semantic relevance from
truth and evidence support, so these results must not be generalized into
factual-discipline capability.

### 5B-5b — Evidence Relevance

The repository contains:

```text
EvidenceRelevanceJudgment
OpenAIEvidenceRelevanceEvaluator
```

but this checkpoint did not identify a dedicated evidence-relevance
golden/holdout dataset equivalent to the claim-relevance v2 datasets.

Therefore no official evidence-relevance accuracy is recorded here.

Status:

**NOT SCORED — NO VERIFIED GOLDEN/HOLDOUT DATASET IN CURRENT AUDIT**

Evidence relevance should be evaluated later only with an explicitly
identified or intentionally created benchmark dataset whose status is
clearly distinguished from the existing claim-relevance holdout.

---

## 19. Phase 5B-6 — Factual Discipline / Semantic Citation Entailment

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
num_predict: 256
response schema: SemanticCitationJudgment

DEV:
semantic-citation-golden-v2 / 2.0.0 / 20 cases

HOLDOUT:
semantic-citation-holdout-v1 / 1.0.0 / 20 cases
```

Repository validation before live execution:

```text
pytest: 4583 passed
ruff: All checks passed
```

The benchmark reused the actual AIRA semantic citation components:

```text
SemanticCitationJudgment
SemanticCitationEvaluationRunner
SEMANTIC_CITATION_INSTRUCTIONS
build_semantic_citation_golden_dataset_v2()
build_semantic_citation_holdout_dataset()
```

Support classes:

```text
fully_supported
partially_supported
unsupported
contradicted
```

The evaluator policy explicitly separates missing support from contradiction:

```text
unsupported
→ evidence does not establish the core claim but does not explicitly conflict

contradicted
→ evidence contains an assertion mutually incompatible with the claim
```

### DEV result

```text
17/20 = 85.0%
false fully supported: 0
false rejected: 3
```

Per class:

```text
fully_supported:      3/4 = 75%
partially_supported:  3/5 = 60%
unsupported:          5/5 = 100%
contradicted:         6/6 = 100%
```

Failures:

```text
fully-004-numeric-narrowing
expected: fully_supported
actual: contradicted

partial-001-conjunction
expected: partially_supported
actual: unsupported

partial-005-secondary-assertion
expected: partially_supported
actual: unsupported
```

### Blind HOLDOUT result

```text
17/20 = 85.0%
false fully supported: 1
false rejected: 2
```

Per class:

```text
fully_supported:      5/5 = 100%
partially_supported:  2/5 = 40%
unsupported:          5/5 = 100%
contradicted:         5/5 = 100%
```

Failures:

```text
holdout-partial-001-time-scope
expected: partially_supported
actual: contradicted

holdout-partial-002-exception-omitted
expected: partially_supported
actual: fully_supported

holdout-partial-003-conjunction
expected: partially_supported
actual: unsupported
```

### Combined interpretation

Across DEV and HOLDOUT:

```text
unsupported:          10/10 = 100%
contradicted:         11/11 = 100%
unsupported+contradicted: 21/21 = 100%

partially_supported:   5/10 = 50%
fully_supported:       8/9  = 88.9%
```

The dominant weakness is therefore not rejection of clearly unsupported or
contradicted claims. It is the boundary between partial support and the other
classes.

Observed partial-support failure modes include:

```text
qualifier / scope handling
exception omission
conjunctive claims
secondary unsupported assertions
numeric narrowing semantics
```

One HOLDOUT case was incorrectly promoted from `partially_supported` to
`fully_supported`, so the model must not be treated as an authoritative final
citation verifier.

### Phase 5B-6 decision

Status:

**COMPLETE — CONDITIONAL ACCEPTANCE FOR FIRST-PASS FACTUAL TRIAGE**

Role policy:

```text
Qwen3.5-4B
→ accepted for first-pass semantic citation triage
→ not accepted as final authoritative factual verifier
```

Appropriate use:

```text
strong candidate:
- detect clearly unsupported claims
- detect explicitly contradicted claims
- first-pass citation triage

requires escalation / additional validation:
- partially supported claims
- qualifier / exception boundaries
- conjunctions
- scope broadening
- final acceptance of important factual claims
```

Recommended control:

```text
Qwen3.5-4B first pass
→ unsupported / contradicted: flag or reject
→ partial / ambiguous: escalate
→ fully_supported: retain schema/rule checks and escalate high-impact claims
```

This benchmark evaluates claim-to-evidence semantic support only.
It does not establish source authority, source freshness, document authenticity,
or full report-level factual correctness.

---

## 20. Phase 5B-7 — AIRA-native Complex Reasoning / Answer Coverage

Configuration:

```text
model: qwen3.5:4b
think: false
temperature: 0.0
seed: 42
num_predict: 384
response schema: AnswerCoverageJudgment

DEV:
answer-coverage-golden-v2 / 2.0.0 / 18 cases

HOLDOUT:
answer-coverage-blind-holdout-v1 / 1.0.0 / 20 cases
```

Repository validation before live execution:

```text
pytest: 4590 passed
ruff: All checks passed
```

The benchmark reused the actual AIRA answer-coverage components:

```text
AnswerCoverageJudgment
AnswerCoverageEvaluationRunner
ANSWER_COVERAGE_INSTRUCTIONS
build_answer_coverage_golden_dataset()
build_answer_coverage_blind_holdout_dataset()
```

Coverage classes:

```text
fully_covered
partially_covered
insufficient
```

### DEV result

```text
18/18 = 100.0%
false fully covered: 0
false insufficient: 0
```

Per class:

```text
fully_covered:      6/6 = 100%
partially_covered:  6/6 = 100%
insufficient:       6/6 = 100%
```

### Blind HOLDOUT result

```text
19/20 = 95.0%
false fully covered: 0
false insufficient: 0
```

Per class:

```text
fully_covered:      6/7 = 85.7%
partially_covered:  7/7 = 100%
insufficient:       6/6 = 100%
```

The only HOLDOUT failure was:

```text
schema-validation-full-short
expected: fully_covered
actual: partially_covered
```

This is a conservative under-approval rather than an unsafe over-approval.

### Phase 5B-7 decision

Status:

**COMPLETE — AIRA-NATIVE BOUNDED REVIEWER CAPABILITY ACCEPTED**

Interpretation:

```text
multi-aspect answer coverage reasoning
→ strong

partial-vs-full distinction
→ strong

insufficient-answer detection
→ strong

false-full risk in this benchmark
→ 0 on DEV and HOLDOUT

blind generalization
→ strong: 19/20
```

The model correctly handled repeated-same-aspect answers, missing enforcement/action
steps, one-sided comparisons, narrow objectives, and unrelated-but-topical material.

This benchmark is particularly relevant to a reviewer/critic role because the model
must infer the explicit answer requirements from the question and objective, then
judge the claim set as a whole rather than classify individual claims independently.

---

## 21. Qwen3.5-4B Small Worker Final Decision

Status:

**FINAL — ACCEPTED AS BOUNDED SMALL WORKER**

Accepted roles:

```text
- constrained structured-output worker
- known single-tool caller
- bounded claim-relevance classifier
- first-pass semantic citation triage
- answer-coverage reviewer / critic
- deterministic short reasoning worker
```

Not accepted roles:

```text
- autonomous research planner
- unconstrained long-form planning
- final authoritative factual verifier
- policy-sensitive orchestration without deterministic controls
```

Required operating controls:

```text
1. Prefer think=false for normal worker tasks.
2. Use JSON Schema / typed structured output for known schemas.
3. Keep planning and orchestration deterministic or assigned to a stronger model.
4. Escalate ambiguous partial-support factual judgments.
5. Retain deterministic validation around tool policy and workflow limits.
6. Do not generalize benchmark acceptance beyond the tested role.
```

Final role boundary:

```text
Qwen3.5-4B is not the AIRA Main Agent.

Qwen3.5-4B is accepted as a bounded Small Worker for structured,
review, classification, triage, and selected deterministic reasoning tasks.
```

Phase 5 local-model benchmarking for the Qwen3.5-4B Small Worker is complete.

---

## 22. Remaining Phase 5 Benchmarks

- [x] Korean instruction following
- [x] tool selection
- [x] native tool calling
- [x] research planning
- [x] source relevance judgment
- [ ] evidence / claim judgment
- [x] factual discipline
- [ ] AIRA-native complex reasoning
- [x] Qwen3.5-4B Small Worker 최종 역할 결정
- [ ] Qwen3.5-9B benchmark
- [ ] Ministral 3 8B benchmark

---

## 23. Next Step

```text
Korean Instruction
→ Structured Output / JSON Schema
→ Tool Selection / Native Tool Calling
→ Research Planning
→ Source Relevance / Evidence Judgment
→ Factual Discipline
```

Small Worker 적합성이 여기까지 확인되면 Qwen3.5-4B 세부 benchmark를 종료하고 동일 핵심 benchmark를 Main Agent 후보에 적용한다.

---

## 24. Stop Rule

Qwen3.5-4B에 대해 required Worker capability, failure mode, default Think policy, AIRA-native task 품질이 확인되고 더 많은 세부 benchmark가 역할 결정에 실질적인 정보를 추가하지 않으면 Small Worker benchmark를 종료한다.

### Reopen Condition

- AIRA integration 중 새로운 failure mode 발견
- context 확대 필요
- concurrency 필요
- 새로운 tool/schema requirement
- stronger model과의 비교에서 정책 재검토 필요

## Phase 6 — Local LLM Adapter Integration

Status:

**COMPLETE — BOUNDED LOCAL WORKER RUNTIME INTEGRATION ACCEPTED**

Implementation scope:

```text
AIRA research-live
│
├─ deterministic planning
├─ Tavily search
├─ HTTP source reading
│
├─ OpenAI
│   ├─ evidence embeddings
│   ├─ evidence relevance
│   └─ claim generation
│
└─ Ollama / qwen3.5:4b
    ├─ claim relevance
    ├─ semantic citation verification
    └─ answer coverage review
```

The integration deliberately does not move autonomous planning, claim generation,
embedding, or final authoritative factual verification to qwen3.5:4b.

Production provider selection:

```text
AIRA_RESEARCH_WORKER_PROVIDER=openai
→ existing OpenAI worker behavior

AIRA_RESEARCH_WORKER_PROVIDER=local
AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
→ bounded research workers use Ollama
```

Default provider remains `openai`, preserving the previous production behavior
unless local workers are explicitly enabled.

Local evaluator production contracts were upgraded to preserve:

```text
response metadata
token usage
citation decision mapping
answer coverage attempt metadata
```

Semantic citation decision mapping remains code-owned:

```text
fully_supported     → verified
partially_supported → needs_revision
unsupported         → rejected
contradicted        → rejected
```

Production Claim Relevance uses `num_predict=512`.
The benchmark evaluator default remains unchanged; the larger limit applies only
to the production local-worker composition after the first live smoke reached
the 256-token generation limit.

Validation:

```text
targeted integration tests: 59 passed
full regression:             4598 passed
ruff:                        All checks passed
git diff --check:            clean
```

End-to-end live smoke:

```text
command: aira research-live
worker provider: local
local model: qwen3.5:4b
maximum sources: 1
quality score: 0.8845
```

Artifact provenance:

```text
ollama-local occurrences: 7
relevance_level:          3
support_level:            3
coverage_level:           3
decision:                 3
```

Ollama runtime observation during the smoke:

```text
qwen3.5:4b
processor: 100% GPU
context:   4096
```

Acceptance conclusion:

The actual production research pipeline successfully executed the three
Phase-5-accepted bounded workers through Ollama/qwen3.5:4b while preserving
the rest of the live research stack.

Phase 6 is therefore complete for the defined adapter-integration scope.

Next official phase:

**Phase 7 — OpenAI vs Local Single-Agent**

## Phase 7 — OpenAI vs Local Single-Agent

Status:

**COMPLETE — LOCAL BOUNDED WORKER BACKEND ACCEPTED WITH ROLE-SPECIFIC LIMITS**

### Scope

Phase 7 compared the same AIRA Single-Agent research architecture with two
bounded-worker backends:

```text
OpenAI:
- claim relevance
- semantic citation verification
- answer coverage

Local:
- qwen3.5:4b claim relevance
- qwen3.5:4b semantic citation verification
- qwen3.5:4b answer coverage
```

The following remained outside the local-worker substitution:

```text
- deterministic planning
- Tavily search
- HTTP source reading
- OpenAI embeddings
- OpenAI evidence relevance
- OpenAI claim generation
```

### Phase 7A — Live Pipeline Smoke

The first live pair completed successfully:

```text
OpenAI quality: 0.8325
Local quality:  0.8845

OpenAI total elapsed: 281.51 s
Local total elapsed:  171.12 s

OpenAI worker elapsed: 164.29 s
Local worker elapsed:   45.06 s
```

Both runs had:

```text
sources:   1
evidence:  3
claims:    3
citations: 3
```

However, the generated claim text differed materially between the two live
runs. Therefore this result was retained as an end-to-end execution smoke and
was not used as a pure backend-quality comparison.

An earlier OpenAI live attempt failed with an API timeout under the normal
30-second request timeout. The Phase 7 benchmark runner therefore used a
benchmark-only 120-second OpenAI timeout without changing the production
default.

### Claim-Relevance Budget Parity

Before the controlled comparison, the local runtime was updated so that both
OpenAI and local claim-relevance services receive the same execution budget:

```text
max_attempts:          8
max_recorded_tokens:   8,000
max_elapsed_seconds:   60
```

This removed a provider-policy difference from the benchmark.

### Phase 7C — Frozen-Input Backend Comparison

The controlled comparison reused persisted live `ResearchRequest`,
`ResearchClaimSet`, and embedded `ResearchEvidenceSet` objects.

No upstream retrieval or generation stages ran.

Design:

```text
fixtures:              2
repeats per fixture:   3
paired comparisons:    6
successful pairs:      6
failed pairs:          0
```

Aggregate result:

```text
mean citation exact agreement:              1.0000
mean claim relevance exact agreement:       0.8333
answer coverage level agreement:            0.5000
mean coverage score delta (Local-OpenAI):   +0.2750

mean wall delta (Local-OpenAI):
  citation:          -9.37 s
  claim relevance:  -16.10 s
  answer coverage:  -22.64 s
  total:            -48.12 s
```

Mean total worker wall time from the six pairs:

```text
OpenAI: approximately 67.2 s
Local:  approximately 19.1 s

Local wall-time reduction:
approximately 48.1 s
approximately 71.6%
approximately 3.5x faster
```

### Semantic Citation Result

All six pairs produced exact OpenAI/local agreement for every tested citation:

```text
citation exact agreement = 100%
```

All tested citations were judged:

```text
verified / fully_supported
```

Decision:

**ACCEPTED for the bounded first-pass semantic-citation role.**

This Phase 7 result does not replace the broader Phase 5 citation benchmark,
which included unsupported, contradicted, and partial-support cases.

### Claim Relevance Result

Aggregate exact agreement:

```text
83.3%
```

Fixture 1 repeatedly disagreed on one boundary claim:

```text
OpenAI → directly_relevant
Local  → partially_relevant
```

The disagreement was stable across all three repeats rather than random
run-to-run drift.

Fixture 2 reached 100% exact agreement across all three repeats.

Decision:

**ACCEPTED AS A BOUNDED CLASSIFIER.**

Ambiguous and high-impact relevance cases remain escalation candidates.

### Answer Coverage Result

Coverage-level agreement was only:

```text
50%
```

Fixture 1:

```text
OpenAI: partially_covered 0.45 / 0.45 / 0.50
Local:  partially_covered 0.65 / 0.65 / 0.65
```

Fixture 2:

```text
OpenAI: partially_covered 0.65 / 0.65 / 0.60
Local:  fully_covered     1.00 / 1.00 / 1.00
```

The local backend therefore showed an optimistic answer-coverage bias in the
tested fixtures.

Decision:

**ACCEPTED AS A REVIEWER / CRITIC, NOT AS AN AUTHORITATIVE FINAL COVERAGE
JUDGE.**

A Local `fully_covered` result must not by itself be treated as authoritative
proof of completeness.

### Phase 7 Final Decision

Qwen3.5-4B remains:

**FINAL — ACCEPTED AS BOUNDED SMALL WORKER**

with the following Phase-7-refined boundaries:

```text
Semantic citation:
  accepted bounded first-pass verifier

Claim relevance:
  accepted bounded classifier
  escalate ambiguous/high-impact cases

Answer coverage:
  accepted reviewer / critic
  do not use as authoritative final judge
  optimistic bias observed
```

The local worker backend also demonstrated materially lower and more stable
latency in this controlled benchmark.

Phase 7 is complete.

Next official phase:

**Phase 8 — Local Multi-Agent Minimum Experiment**

## Phase 8 — Local Multi-Agent Minimum

Phase 8 reused the existing deterministic multi-agent orchestration framework and
introduced Qwen3.5-4B only as a bounded advisory quality reviewer.

Verified characteristics:

```text
Search → Reader → Evidence → Claim
→ Synthesis / Review loop
```

The dependency chain remained sequential. A live local multi-agent smoke completed
technically; a `revision_limit_reached` terminal state with `max_revisions=0` was an
expected workflow outcome rather than a runtime failure.

Decision:

**LOCAL MULTI-AGENT MINIMUM — COMPLETE.**

The experiment did not justify making Multi-Agent the default architecture.

---

## Phase 9 — Single vs Multi-Agent Evaluation

The frozen benchmark separated three paths:

1. Single deterministic
2. Multi deterministic with approved reviewer
3. Multi + Qwen3.5-4B advisory reviewer

Across 3 fixtures × 3 repeats = 9 triplets:

```text
artifact equivalence                  100%
deterministic/local workflow integrity 100%
runtime success                       100%

single mean                           ~0.684 ms
multi deterministic mean              ~1.255 ms
pure orchestration extra              ~0.571 ms
multi + local reviewer mean           ~3.00025 s
Qwen reviewer incremental overhead    ~2.999 s
semantic repair local success         100%
```

These were tiny in-memory fixtures. Absolute latency must not be generalized to live
research workloads.

Decision:

```text
Single-Agent default
+ workload-dependent Multi-Agent escalation
+ Qwen3.5-4B bounded advisory reviewer
```

Phase 9 is complete.

---

## Phase 10 — Heterogeneous / Hybrid Architecture

Two bounded-worker backend policies were compared on frozen inputs.

OpenAI-heavy:

- evidence relevance OpenAI
- claim generation OpenAI
- semantic citation OpenAI
- claim relevance OpenAI
- answer coverage OpenAI

Hybrid:

- evidence relevance OpenAI
- claim generation OpenAI
- semantic citation Local
- claim relevance Local
- answer coverage Local

2 fixtures × 3 repeats = 6 pairs:

```text
successful pairs                    6 / 6
citation exact agreement            100%
claim relevance exact agreement     83.3%
answer coverage level agreement     50%
coverage score delta Hybrid-OpenAI  +0.313333
OpenAI worker mean                  52.20274 s
Hybrid local worker mean            18.68276 s
worker wall delta                  -33.51998 s
observed wall reduction             64.211%
observed speedup                    2.794x
```

Limitations:

- frozen bounded substitution, not full live E2E comparison
- inherited OpenAI → Local execution order can warm the Local runtime
- embeddings were excluded from the worker comparison
- no distinct safe Local-heavy baseline was established

Decision:

**HYBRID ROLE-ROUTED ARCHITECTURE ACCEPTED WITH BOUNDED LOCAL WORKERS AND
OPENAI HIGH-JUDGMENT ESCALATION.**

Phase 10 is complete.

---

## Phase 11 — Parallelism / Runtime Scaling

### Phase 11A — Safety Audit

The whole pipeline was not parallelized blindly.

Safe/current boundaries:

```text
Source Search             serial
Source Reading            bounded parallel candidate
Local Qwen workers        concurrency 1
Pipeline dependency chain sequential
Multi-Agent stage chain   sequential by dependency
Review/revision loop      sequential
```

Search concurrency was deferred because provider calls share usage/budget accounting.

### Phase 11B — Synthetic Source Reading

8 candidates, 50ms deterministic delayed reader, 5 repeats:

| concurrency | mean seconds | speedup vs 1 |
|---:|---:|---:|
| 1 | 0.401318 | 1.000x |
| 2 | 0.201090 | 1.996x |
| 4 | 0.100909 | 3.977x |

Candidate output order was preserved.

### Phase 11C — Real HTTP Source Reading

8 fixed web URLs, 3 repeats per concurrency:

| concurrency | mean seconds | median seconds | speedup vs 1 |
|---:|---:|---:|---:|
| 1 | 2.277 | 1.707 | 1.000x |
| 2 | 0.921 | 0.921 | 2.472x |
| 4 | 0.851 | 0.864 | 2.676x |

Every concurrency produced the same per-source semantics:

```text
6 sources → read
2 sources → failed / DocumentHttpError
```

Successful documents also had the same character counts across 1/2/4. The experiment
therefore found no correctness loss from bounded source-read parallelism on this fixture.

### Phase 11D — Production Wiring

Production contract:

```text
AIRA_SOURCE_READ_CONCURRENCY
live default = 2
allowed = 1..8
safe fallback = 1
aggressive benchmark option = 4
adapter default = 1
```

Why default 2 rather than 4:

- 1 → 2 captured the large performance improvement
- 2 → 4 added only a relatively small additional gain in the real HTTP benchmark
- lower default concurrency reduces unnecessary remote/network pressure
- explicit fallback to 1 remains available without code changes

Live smoke with default 2:

```text
quality = 0.9345
selected documents = 2 / 2 read
ollama-local provenance occurrences = 13
```

Final validation:

```text
4635 passed in 16.70s
Ruff = All checks passed
git diff --check = clean
```

Commit:

```text
5c30358 feat: add bounded parallel source reading
```

Decision:

**PHASE 11 COMPLETE — BOUNDED PARALLEL SOURCE READING ACCEPTED; BROADER
PIPELINE PARALLELISM REMAINS DEFERRED.**

Historical checkpoint after Phase 11:

**Phase 12 — Hardware Upgrade Decision.**

---

## Phase 12 — Hardware Upgrade Decision Evidence

### Phase 12A — Current Hardware / Runtime Baseline

Measured environment:

```text
CPU     Intel Core i5-9600KF
RAM     ~31 GiB
GPU     NVIDIA GeForce RTX 3060 Ti 8 GiB
Ollama  0.32.6
```

`qwen3.5:4b` metadata and runtime:

```text
parameters      4.7B
quantization    Q4_K_M
context length  262144 model metadata
runtime context 4096
processor       100% GPU
```

The initial live AIRA baseline completed successfully with quality `0.8845` and wall time
`1:55.23`. That wall time included the broader live research workflow and was not treated
as a pure-model throughput measurement.

### Phase 12B — Larger-model feasibility and role comparison

Hardware capacity probes:

| model | Ollama runtime placement | observed total GPU usage | interpretation |
|---|---|---:|---|
| qwen3.5:4b | 100% GPU | ~4.7 GiB | current bounded-worker baseline |
| llama3.1:8b | 100% GPU | ~6.1 GiB | capacity probe only |
| qwen3.5:9b | 13% CPU / 87% GPU | ~7.1 GiB | 8 GiB VRAM boundary / partial offload |
| ministral-3:8b | 22% CPU / 78% GPU | ~6.9 GiB | partial CPU offload |

The production-aligned comparison reused the existing Phase-5 datasets and evaluator
contracts with `think=false`, `temperature=0.0`, `seed=42`.

Budgets:

```text
semantic citation  num_predict=256
claim relevance    num_predict=512
answer coverage    num_predict=384
```

Quality comparison:

| role | Qwen3.5-4B DEV | Qwen3.5-4B HOLDOUT | Qwen3.5-9B DEV | Qwen3.5-9B HOLDOUT | Ministral 3 8B DEV | Ministral 3 8B HOLDOUT |
|---|---:|---:|---:|---:|---:|---:|
| Semantic Citation | 0.850 | 0.850 | 0.850 | 0.900 | 0.850 | 0.800 |
| Claim Relevance | 0.889 | 1.000 | 0.722 | 0.944 | 0.889 | 0.944 |
| Answer Coverage | 1.000 | 0.950 | 0.833 | 0.950 | 0.833 | 0.900 |

Safety-sensitive errors:

```text
Claim Relevance false_direct, DEV/HOLDOUT
Qwen3.5-4B      0 / 0
Qwen3.5-9B      3 / 1
Ministral 3 8B  2 / 1

Answer Coverage false_full, DEV/HOLDOUT
Qwen3.5-4B      0 / 0
Qwen3.5-9B      1 / 0
Ministral 3 8B  0 / 0
```

Wall time across the three benchmarks:

| model | semantic | claim | coverage | total | relative to 4B |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-4B | 95.27 s | 100.63 s | 106.31 s | 302.21 s | 1.00x |
| Qwen3.5-9B | 162.62 s | 169.80 s | 212.97 s | 545.39 s | 1.80x |
| Ministral 3 8B | 127.10 s | 168.86 s | 205.94 s | 501.90 s | 1.66x |

Interpretation:

- Qwen3.5-9B improved semantic-citation holdout by one case but did not establish an
  overall quality advantage across the accepted bounded roles.
- Qwen3.5-9B produced more optimistic claim-relevance and coverage errors on these
  fixtures.
- Ministral 3 8B did not establish an overall quality advantage over Qwen3.5-4B.
- Larger-model CPU offload therefore did not correspond to a demonstrated AIRA quality
  gain that would justify a VRAM upgrade.

Raw Phase 12B comparison artifacts:

```text
/mnt/ai-data/experiments/phase12b3/4b/
/mnt/ai-data/experiments/phase12b3/9b/
/mnt/ai-data/experiments/phase12b3/ministral8b/
```

### Phase 12C — Current-worker resource headroom

Qwen3.5-4B was run through the three production-aligned bounded-role benchmarks while
GPU and system resources were sampled once per second.

```text
samples                    2042
gpu utilization max        91.0%
gpu utilization mean       12.575%  (includes idle gaps between calls)
VRAM used max              4755 MiB
VRAM free min              3117 MiB
power max                  199.49 W
temperature max            74 C
RAM available min          23975 MiB
RAM available max          26160 MiB
```

The repeated quality results matched the Phase 12B 4B baseline. Repository status remained
clean because Phase 12 experiments wrote artifacts outside the repository.

Raw Phase 12C artifacts:

```text
/mnt/ai-data/experiments/phase12c1/
```

### Phase 12 Final Decision

**KEEP CURRENT HARDWARE; DEFER HARDWARE UPGRADE.**

The RTX 3060 Ti 8 GiB is a real capacity boundary for some 9B-class Q4 models, but the
larger candidates tested here did not provide the role-specific quality improvement needed
to justify buying more VRAM. Qwen3.5-4B remains the accepted bounded local worker, and the
OpenAI + Local hybrid architecture remains the preferred architecture.

Phase 12 is complete.
