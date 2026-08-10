# AIRA Local LLM Track — Benchmark Plan

- 기준일: 2026-08-09
- 상위 저장소: `/home/moon/Project/agentic-ai-lab`
- 권장 저장 위치: `local-llm/BENCHMARK_PLAN.md`
- 단계: Phase 4 — First Local Model Benchmark
- 최초 대상: `qwen3.5:4b`
- 상태: IN PROGRESS

## 1. 목적

Phase 4의 목적은 Local LLM이 단순히 실행되는지를 확인하는 것이 아니다.

AIRA에서 실제 Agent / Worker로 사용할 수 있는지 다음 측면에서 재현 가능하게 평가한다.

- 품질
- instruction following
- Korean capability
- structured output
- tool use
- reasoning
- factual discipline
- latency
- throughput
- VRAM/RAM
- reliability

동일 benchmark는 이후 Main Agent 후보에도 재사용한다.

## 2. Benchmark Principles

### 2.1 Same Prompt, Same Conditions

모델 간 비교 시 가능한 한 동일한:
- prompt
- context
- temperature/runtime options
- output schema
- tool definitions
- iteration count

를 사용한다.

### 2.2 Repeated Runs

한 번의 성공/실패로 모델을 판정하지 않는다.

초기 smoke test 후 핵심 benchmark는 최소 3회 반복을 기본으로 한다.

### 2.3 Separate Quality from Speed

빠른 모델이 좋은 모델이라고 판단하지 않는다.

다음 축을 별도로 기록한다.
- task quality
- task success
- latency
- throughput
- resource usage
- stability

### 2.4 Think OFF vs Think ON

Thinking-capable model은 reasoning 품질과 비용의 trade-off를 직접 측정한다.

동일 reasoning task를 최소 두 조건으로 비교한다.
- Mode A: `think=false`
- Mode B: `think=true`

Think OFF를 기본 Worker mode로 사용하되,
복잡한 reasoning task에서 Think ON이 실질적으로 품질을 개선하는지 검증한다.

## 3. Benchmark Baseline

Hardware:
- CPU: Intel Core i5-9600KF
- GPU: NVIDIA GeForce RTX 3060 Ti
- VRAM: 8192 MiB
- RAM: 31 GiB usable

Runtime:
- Ollama: 0.32.6
- Backend: CUDA
- API: `http://127.0.0.1:11434`
- Parallel: 1
- Initial Context: 4096

Model:
`qwen3.5:4b`

## 4. Benchmark Categories

### B1 — Korean Instruction Following

한국어 명령과 제약 준수 여부를 평가한다.

측정:
- instruction compliance
- language consistency
- unnecessary text
- formatting errors

### B2 — Structured Output

단계:
1. prompt-only JSON
2. `format: "json"`
3. JSON Schema

측정:
- parse success
- schema success
- extra text
- missing fields
- wrong types
- repeated-run consistency

### B3 — Tool Selection

예시 tool set:
- web_search
- read_url
- calculator
- filesystem_read
- no_tool

측정:
- correct tool
- correct arguments
- unnecessary tool call
- missed tool call

## 5. Native Tool Calling

Ollama의 native tool calling API를 사용하여 실제 function calling을 테스트한다.

측정:
- tool call generation
- function name accuracy
- argument schema accuracy
- tool result interpretation
- second-turn answer quality

## 6. Research Planning

입력:
하나의 research question

출력:
- sub-questions
- search queries
- evidence needs
- expected source types
- stop condition

측정:
- coverage
- redundancy
- query quality
- task decomposition
- feasibility

## 7. Source Relevance Judgment

source title/snippet 또는 short document를 제공하고
주어진 claim에 대한 관련성을 판단하게 한다.

측정:
- relevant / irrelevant accuracy
- over-inclusion
- false rejection
- explanation quality

가능하면 기존 AIRA evaluator fixture를 재사용한다.

## 8. Evidence / Claim Judgment

evidence와 claim pair를 제공하고 다음을 판정한다.

- supports
- contradicts
- insufficient

측정:
- label accuracy
- unsupported inference
- semantic overreach
- uncertainty handling

## 9. Summarization

측정:
- important fact coverage
- hallucination
- omitted qualification
- compression quality
- Korean readability

## 10. Critique

측정:
- factual error detection
- unsupported claim detection
- contradiction detection
- missing evidence detection
- false-positive criticism

## 11. Factual Discipline

테스트 유형:
- insufficient evidence
- deliberately missing fact
- conflicting evidence
- fake citation temptation
- ambiguous question

좋은 행동:
- uncertainty 표현
- 추가 자료 필요성 명시
- 근거 없는 확정 회피

## 12. Thinking A/B Benchmark

### Mode A — Think OFF

`"think": false`

주 대상:
- routing
- extraction
- classification
- structured output
- simple evaluation
- straightforward summarization

### Mode B — Think ON

`"think": true`

주 대상:
- multi-step planning
- difficult evidence comparison
- contradiction resolution
- complex critique
- multi-constraint synthesis

### 비교 항목

- answer quality
- correctness
- task success
- output tokens
- thinking tokens
- total latency
- final-answer latency
- malformed output
- timeout / length termination

### 결정 원칙

Think ON을 항상 더 좋다고 가정하지 않는다.
Think OFF를 항상 충분하다고도 가정하지 않는다.

AIRA는 benchmark 결과에 따라 task policy를 만든다.

예:
`simple worker -> think=false`
`hard reasoning -> think=true`

향후 필요하면 complexity router를 추가하여 task별로 자동 선택한다.

## 13. Performance Benchmark

각 실행에서 저장:
- total_duration
- load_duration
- prompt_eval_count
- prompt_eval_duration
- eval_count
- eval_duration

계산:
- Prompt throughput = `prompt_eval_count / prompt_eval_duration_seconds`
- Generation throughput = `eval_count / eval_duration_seconds`

추가 시스템 측정:
- nvidia-smi VRAM
- GPU utilization
- RAM
- swap
- processor split (`ollama ps`)

## 14. Cold vs Warm Benchmark

### Cold

모델이 unload된 뒤 첫 request.

### Warm

모델이 memory에 남아 있는 동안 연속 request.

Phase 3의 최초 Think OFF call은 load_duration 약 10.1초가 포함되었으므로
generation 성능과 전체 latency를 분리해야 한다.

## 15. Context Benchmark

초기 baseline은 4096이다.

이후 필요 시:
- 8192
- 16384
- 32768

순으로 증가시킨다.

각 단계에서 확인:
- 100% GPU 유지 여부
- VRAM
- OOM
- tokens/sec
- long-context accuracy

## 16. Scoring

초기 scoring은 100점 단일 총점보다 다차원 score를 유지한다.

권장 항목:
- Instruction Following
- Korean
- Structured Output
- Tool Use
- Research Planning
- Evidence Judgment
- Factual Discipline
- Reasoning
- Stability
- Performance

최종 모델 선택 시 weighted score가 필요하면 그때 가중치를 명시적으로 결정한다.

## 17. Experiment Artifact Policy

대용량/raw experiment data의 canonical 저장 위치:
`/mnt/ai-data/experiments/`

현재 초기 benchmark harness가 생성하는 transient JSON:
`evals/results/local_llm/`

위 디렉터리는 Git ignore 대상이며 raw JSON은 source commit에 포함하지 않는다.
반복/대규모 실험으로 확장할 때 raw artifact의 canonical 위치를 `/mnt/ai-data/experiments/`로 통일한다.

최종 요약/결정 문서:
`/home/moon/Project/agentic-ai-lab/local-llm/BENCHMARK_RESULTS.md`

benchmark scripts와 evaluator code는 repository의 기존 `scripts/`, `app/evals/`, `evals/` 구조를 재사용한다.

## 18. Phase 4 Initial Sequence

1. `qwen3.5:4b` warm/cold performance baseline
2. Korean instruction following
3. structured JSON / JSON Schema
4. tool selection + native tool calling
5. research planning
6. source relevance / evidence judgment
7. factual discipline
8. Think OFF vs Think ON reasoning A/B
9. 결과 정리 및 Phase 4 decision

## 19. Phase 5 Acceptance Criteria

- [x] benchmark harness 또는 재현 가능한 command/script 확보
- [x] raw result 저장
- [ ] Korean instruction benchmark
- [ ] structured output benchmark
- [ ] tool selection benchmark
- [ ] native tool calling benchmark
- [ ] research planning benchmark
- [ ] evidence judgment benchmark
- [ ] factual discipline benchmark
- [x] Think OFF/ON comparison
- [x] cold/warm performance measurement
- [x] VRAM/RAM baseline measurement
- [x] failure cases 기록
- [x] Qwen3.5-4B Small Worker 잠정 역할 결정
- [ ] AIRA-native capability benchmark 후 Qwen3.5-4B 최종 역할 결정

## 20. Stop Rule

Qwen3.5-4B가 Small Worker로서 필요한 수준을 충족하는지가 AIRA-native capability benchmark까지 확인되면
세부 benchmark를 무한히 확장하지 않는다.

현재 deterministic reasoning 결과만으로는 Phase 5 전체를 종료하지 않는다.

다음으로 Main Agent 후보:
- Qwen3.5-9B
- Ministral 3 8B

에 동일 핵심 benchmark를 적용한다.

## 21. Expected Decision

Phase 4 종료 시 다음 중 하나를 명확히 결정한다.

- Qwen3.5-4B를 Small Worker로 채택
- 특정 task에만 제한적으로 채택
- 품질 미달로 제외

추가로 Thinking policy를 task category별로 확정한다.
