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

**Status: PROVISIONAL SMALL WORKER ACCEPTED**

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

## 15. Remaining Phase 5 Benchmarks

- [ ] Korean instruction following
- [ ] structured JSON
- [ ] JSON Schema reliability
- [ ] tool selection
- [ ] native tool calling
- [ ] research planning
- [ ] source relevance judgment
- [ ] evidence / claim judgment
- [ ] factual discipline
- [ ] AIRA-native complex reasoning
- [ ] Qwen3.5-4B Small Worker 최종 역할 결정
- [ ] Qwen3.5-9B benchmark
- [ ] Ministral 3 8B benchmark

---

## 16. Next Step

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

## 17. Stop Rule

Qwen3.5-4B에 대해 required Worker capability, failure mode, default Think policy, AIRA-native task 품질이 확인되고 더 많은 세부 benchmark가 역할 결정에 실질적인 정보를 추가하지 않으면 Small Worker benchmark를 종료한다.

### Reopen Condition

- AIRA integration 중 새로운 failure mode 발견
- context 확대 필요
- concurrency 필요
- 새로운 tool/schema requirement
- stronger model과의 비교에서 정책 재검토 필요
