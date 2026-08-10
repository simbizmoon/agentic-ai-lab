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

## 20. Remaining Phase 5 Benchmarks

- [x] Korean instruction following
- [x] tool selection
- [x] native tool calling
- [x] research planning
- [x] source relevance judgment
- [ ] evidence / claim judgment
- [x] factual discipline
- [ ] AIRA-native complex reasoning
- [ ] Qwen3.5-4B Small Worker 최종 역할 결정
- [ ] Qwen3.5-9B benchmark
- [ ] Ministral 3 8B benchmark

---

## 21. Next Step

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

## 22. Stop Rule

Qwen3.5-4B에 대해 required Worker capability, failure mode, default Think policy, AIRA-native task 품질이 확인되고 더 많은 세부 benchmark가 역할 결정에 실질적인 정보를 추가하지 않으면 Small Worker benchmark를 종료한다.

### Reopen Condition

- AIRA integration 중 새로운 failure mode 발견
- context 확대 필요
- concurrency 필요
- 새로운 tool/schema requirement
- stronger model과의 비교에서 정책 재검토 필요
