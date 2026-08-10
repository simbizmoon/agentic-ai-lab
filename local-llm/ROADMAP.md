# AIRA Local LLM Experimental Track Roadmap

- 기준일: 2026-08-09
- 상위 프로젝트: Agentic AI Lab (AIRA)
- Repository: `/home/moon/Project/agentic-ai-lab`
- Track directory: `/home/moon/Project/agentic-ai-lab/local-llm`
- Large data root: `/mnt/ai-data`
- 상태: Phase 5 — Local Model Benchmark 진행 중

---

# 1. Track Goal

기존 AIRA의 OpenAI API 기반 Agent/Research capability를 유지하면서, Local Open-Source / Open-Weight LLM을 **교체 가능한 별도 LLM backend**로 추가한다.

최종적으로 다음 조합을 동일 AIRA workload와 evaluation framework에서 객관적으로 비교한다.

```text
Single-Agent + OpenAI
Single-Agent + Local
Multi-Agent  + OpenAI
Multi-Agent  + Local
Multi-Agent  + Hybrid
```

Local LLM 자체와 Multi-Agent architecture를 동일한 실험 변수로 섞지 않는다.

---

# 2. Success Definition

본 Track은 단순히 로컬 Chatbot을 실행하는 것으로 완료되지 않는다.

최종적으로 다음이 가능해야 한다.

1. 현재 PC에서 Local LLM을 안정적으로 실행한다.
2. Local LLM을 AIRA의 실제 LLM-dependent capability에 adapter 방식으로 연결한다.
3. 기존 OpenAI 경로를 깨뜨리지 않는다.
4. 동일 task/eval set으로 OpenAI와 Local을 비교한다.
5. 동일 provider 조건에서 Single-Agent와 Multi-Agent를 비교한다.
6. 필요할 경우 Local + Cloud Hybrid routing을 실험한다.
7. VRAM/RAM/latency/quality/failure를 실제 측정한다.
8. 하드웨어 업그레이드가 필요한지 측정값으로 판단한다.

---

# 3. Experimental Axes

## Axis A — Agent Architecture

```text
Single-Agent
Multi-Agent
```

## Axis B — LLM Backend

```text
OpenAI
Local
Hybrid
```

## Primary Comparison Matrix

| ID | Architecture | Backend | Purpose |
|---|---|---|---|
| A | Single-Agent | OpenAI | 현재/기준 baseline |
| B | Single-Agent | Local | 순수 backend 차이 측정 |
| C | Multi-Agent | OpenAI | Multi-Agent 효과 측정 |
| D | Multi-Agent | Local | Local 환경 Multi-Agent 효과 측정 |
| E | Multi-Agent | Hybrid | Local+Cloud routing 가치 측정 |

주요 해석:

```text
A vs B → OpenAI vs Local backend 차이
A vs C → OpenAI 조건에서 Multi-Agent 효과
B vs D → Local 조건에서 Multi-Agent 효과
C vs D → 동일 Multi-Agent 구조에서 backend 차이
D vs E → Cloud 보조의 추가 가치
```

---

# 4. Governing Principles

## 4.1 No Guessing

모델의 실행 가능성, 메모리 사용량, 성능 및 품질을 parameter 수만으로 확정하지 않는다.

가능하면 다음을 근거로 한다.

- 공식 Model Card
- 공식 GitHub / Documentation
- 실제 local execution
- `nvidia-smi`
- RAM 측정
- tokens/sec
- latency
- AIRA eval 결과

## 4.2 Integration First

OpenAI용 Pipeline을 복사하여 Local 전용 Pipeline을 만들지 않는다.

목표:

```text
AIRA Logic
   ↓
LLM Port
   ├── OpenAI Adapter
   └── Local Adapter
```

기존 Research Pipeline, Evidence, Citation, Guardrail, Budget, Trace, Evaluation 및 Multi-Agent 구성요소를 재사용한다.

## 4.3 Small Model First

현재 GPU는 RTX 3060 Ti 8GB이므로 초기 목표는 4B~8B quantized model이다.

```text
Small Model
    ↓
Single Local LLM
    ↓
AIRA Integration
    ↓
Local Single-Agent
    ↓
Local Multi-Agent
    ↓
Larger / Hybrid Experiment
```

## 4.4 Sequential Before Parallel

초기 Multi-Agent inference는 `Concurrency = 1`을 기본으로 한다.

병렬 실행은 다음이 실제 측정으로 필요하다고 확인된 뒤 검토한다.

- latency bottleneck
- 충분한 VRAM 여유
- KV cache 여유
- 병렬화에 따른 task-level 이점

---

# 5. Phase 0 — Repository and Baseline Audit

상태: **COMPLETE**

완료 내용:

- 기존 AIRA repository 확인
- root-level 주요 문서 확인
- 기존 `docs/`의 실제 역할 확인
- `AIRA_MULTI_AGENT_ROADMAP.md` 존재 확인
- Local LLM과 Multi-Agent를 별도 축으로 관리하기로 결정
- 별도 repository를 만들지 않기로 결정
- root-level `local-llm/` workstream directory 사용 결정

Git baseline:

```text
Branch: main
HEAD: 86fd1c6
origin/main: 동일
Working tree: clean
```

Stop Rule:

- Local LLM Track 시작 전 clean baseline이 확보되었으므로 종료한다.

---

# 6. Phase 1 — Hardware and Storage Baseline

상태: **COMPLETE**

확인된 실제 하드웨어:

```text
CPU: Intel Core i5-9600KF @ 3.70GHz
GPU: NVIDIA GeForce RTX 3060 Ti
VRAM: 8192 MiB
RAM: 31 GiB usable
NVIDIA Driver: 560.35.05
```

Storage 역할:

```text
Samsung 860 EVO 500GB SATA SSD
→ Ubuntu / source / active development / hot storage

Samsung 970 EVO 500GB NVMe
→ Windows dual boot, Local AI용으로 사용하지 않음

ST2000LM005 HN-M201AAD 2TB HDD
→ AI data 전용으로 재구성 완료
→ /mnt/ai-data
```

AI HDD 구성:

```text
Filesystem: ext4
Label: ai-data
UUID: 364aac4d-3aba-45c5-b96c-40bb451ee9bd
Mount: /mnt/ai-data
```

생성된 구조:

```text
/mnt/ai-data/
├── models/
├── datasets/
├── rag/
├── crawls/
├── experiments/
├── artifacts/
└── archive/
```

Stop Rule:

- Local LLM 실험을 시작하기 위한 storage와 hardware baseline 확보 완료.

---

# 7. Phase 2 — Local LLM Candidate Research

상태: **COMPLETE**

## Goal

2026-08-09 기준 유력 Open-Source / Open-Weight LLM을 공식 자료로 조사하여 현재 RTX 3060 Ti 8GB에서의 실용 후보를 선정한다.

## Candidate Families

최소 다음 계열을 검토한다.

```text
Qwen
Gemma
gpt-oss
Llama
Mistral
DeepSeek
GLM
기타 최신 Agent-oriented Open Models
```

## Required Evaluation Fields

```text
Model
Release Date
License
Architecture
Total Parameters
Active Parameters
Context Length
Reasoning
Tool Calling
Agent Capability
Coding
Multilingual
Korean
Quantization Support
GGUF Availability
Expected Memory Class
8GB GPU Suitability
CPU/RAM Offload Suitability
AIRA Role Suitability
Official Sources
```

## Deliverables

최소 다음 세 역할의 후보를 선정한다.

```text
A. Small Worker Model
B. Main Local Agent Model
C. Larger Comparison Model
```

## Acceptance Criteria

- 모든 핵심 판단은 공식/1차 자료 또는 실제 측정으로 근거를 남긴다.
- 현재 8GB VRAM에서 주력으로 사용할 후보와 실험만 가능한 후보를 구분한다.
- License를 반드시 기록한다.

## Stop Rule

- First Runtime Experiment에 사용할 1차 모델 세트가 확정되면 종료한다.

---

# 8. Phase 3 — Runtime Evaluation and Selection

상태: **COMPLETE**

## Candidates

### Ollama

초기 개발 편의성 및 API integration 후보.

### llama.cpp

GGUF, GPU layer offload, CPU/GPU hybrid inference, 8GB VRAM 환경 세밀 조정 후보.

### vLLM

동시성/throughput이 실제 요구사항이 된 이후 검토한다.

## Evaluation Fields

```text
Installation Complexity
Model Compatibility
GPU Detection
VRAM Control
CPU Offload
Context Control
Structured Output
Tool Calling Compatibility
OpenAI-compatible API
Concurrency
Observability
Operational Complexity
```

## Measured Result

- 초기 Runtime으로 Ollama `0.32.6` 사용
- NVIDIA CUDA 및 RTX 3060 Ti 인식 확인
- `qwen3.5:4b` 100% GPU inference 확인
- Context 4096 baseline 확인
- Phase 5 benchmark를 위한 runtime으로 사용 중

## Stop Rule

- 첫 Local LLM benchmark를 수행할 기본 Runtime으로 Ollama가 검증되었으므로 종료한다.
- llama.cpp / vLLM은 현재 benchmark에서 필요성이 확인될 때 재검토한다.

---

# 9. Phase 4 — First Local Model Execution

상태: **COMPLETE**

## Goal

4B~8B quantized model을 현재 GPU에서 안정적으로 실행한다.

## Required Measurements

```text
Model
Quantization
Runtime
Context
GPU Utilization
Peak VRAM
RAM Usage
CPU Usage
Load Time
Prompt Tokens
Output Tokens
Tokens/sec
Total Latency
OOM 여부
```

## Acceptance Criteria

- [x] NVIDIA GPU inference 확인
- [x] OOM 없이 반복 실행 가능
- [x] 한국어 정상 생성
- [x] prompt-only structured output baseline 통과
- [x] 실제 VRAM/RAM/속도 기록

## Measured Result

- Model: `qwen3.5:4b`
- Processor: 100% GPU
- Context: 4096
- 모델 적재 후 VRAM 증가량: 약 3886 MiB
- System RAM used: 약 7 GiB
- swap used: 0 B
- generation throughput baseline: 약 86~88 tokens/s

세부 내용은 `RUNTIME_EVALUATION.md`를 기준으로 한다.

---

# 10. Phase 5 — Local Model Benchmark

상태: **IN PROGRESS**

동일 prompt/eval set으로 여러 후보를 비교한다.

테스트 분야:

```text
General QA
Korean
Reasoning
Research Planning
Summarization
Coding
Tool Selection
Structured Output / JSON
Citation Judgment
Critique
```

평가 항목:

```text
Task Success
Answer Quality
Tool Success
Format Compliance
Latency
Tokens/sec
VRAM
RAM
Failure Rate
```

### 현재 완료된 benchmark checkpoint

```text
✓ runtime / deterministic reasoning baseline
✓ Phase 5B-1 Korean Instruction Following
✓ Phase 5B-2 Structured Output / JSON Schema
✓ Phase 5B-3 Tool Selection
✓ Phase 5B-3 Native Tool Calling
```

Current Phase 5 status remains **IN PROGRESS**.


- [x] benchmark foundation
- [x] cold vs warm runtime benchmark
- [x] verified deterministic reasoning benchmark
- [x] Think OFF vs Think ON comparison
- [x] Thinking generation budget sweep (1024 / 2048 / 3072)
- [x] Qwen3.5-4B Small Worker 잠정 inference policy

### 남은 핵심 benchmark

- [x] Korean instruction following
- [x] structured JSON / JSON Schema
- [ ] tool selection
- [ ] native tool calling
- [ ] research planning
- [ ] source relevance / evidence judgment
- [ ] factual discipline
- [ ] AIRA-native workload에서 Small Worker 최종 역할 결정

상세 실측은 `BENCHMARK_RESULTS.md`에 기록한다.

---

# 11. Phase 6 — Local LLM Adapter Integration

상태: **PENDING**

## Goal

AIRA의 기존 OpenAI 경로를 유지하면서 Local LLM provider를 adapter 방식으로 추가한다.

## Before Coding

반드시 실제 repository를 audit한다.

확인 대상:

- 현재 OpenAI adapter/client 위치
- protocol/port 존재 여부
- config와 environment variable 처리
- dependency injection/composition 위치
- tests와 fake/mock 구조
- usage/budget/trace와의 결합

## Forbidden Shortcut

```text
openai_pipeline.py 복사
→ local_pipeline.py 생성
```

같은 provider별 Pipeline 복제는 피한다.

## Acceptance Criteria

- 기존 OpenAI tests/regression 유지
- Local provider를 config로 선택 가능
- core research/agent logic에 provider-specific branching 최소화

---

# 12. Phase 7 — OpenAI vs Local Single-Agent

상태: **PENDING**

## Experiments

```text
A: Single-Agent + OpenAI
B: Single-Agent + Local
```

## Compare

```text
Task Success
Research Quality
Evidence Coverage
Citation Accuracy
Latency
LLM Calls
Tokens
VRAM
RAM
Cost
Failure Rate
```

이 단계에서 먼저 backend 차이를 분리해서 측정한다.

---

# 13. Phase 8 — Local Multi-Agent Minimum Experiment

상태: **PENDING**

최초 구조:

```text
User
 ↓
Planner
 ↓
Researcher
 ↓
Critic
 ↓
Synthesizer
```

초기 정책:

```text
One Local LLM Server
Same Model Shared
Sequential Execution
Concurrency = 1
```

목표는 최대 성능이 아니라 Multi-Agent coordination의 필요성과 비용을 측정하는 것이다.

---

# 14. Phase 9 — Single vs Multi-Agent Evaluation

상태: **PENDING**

동일 Local backend 조건에서 비교한다.

```text
B: Local Single-Agent
D: Local Multi-Agent
```

평가:

```text
Task Success
Answer Quality
Evidence Coverage
Citation Accuracy
Reasoning / Critique Value
Latency
LLM Call Count
Total Tokens
Peak VRAM
RAM
Failure Rate
Implementation Complexity
```

Stop Rule:

- Multi-Agent의 이점이 비용/복잡성에 비해 유의미하지 않으면 불필요한 Agent 추가를 중단한다.

---

# 15. Phase 10 — Heterogeneous / Hybrid Experiment

상태: **PENDING**

필요성이 확인된 경우에만 진행한다.

예:

```text
Planner       → Small Local Model
Researcher    → Main Local Model
Critic        → Local or OpenAI
Coder         → Coding-specialized Model
Synthesizer   → Main Local or OpenAI
```

Hybrid 예:

```text
Simple / Private Task → Local
Hard Reasoning        → OpenAI
Critical Verification → OpenAI
```

목표:

```text
Quality
Cost
Latency
Privacy
Reliability
```

의 최적 균형을 찾는다.

---

# 16. Phase 11 — Parallelism and Runtime Scaling

상태: **PENDING**

Sequential 구조가 검증된 뒤에만 실행한다.

측정:

```text
Parallel Requests
Peak VRAM
KV Cache Pressure
RAM
Throughput
Latency
OOM / Preemption
Quality
```

8GB VRAM에서 parallel agent execution이 실제 가치가 있는지 판단한다.

---

# 17. Phase 12 — Hardware Upgrade Decision

상태: **PENDING**

현재 예상 최대 병목은 RTX 3060 Ti의 8GB VRAM이지만 구매 결정은 실제 측정 후에 한다.

검토 기준:

```text
OOM frequency
Required context
CPU offload latency
14B/20B/30B quality gain
Parallel agent requirement
AIRA real workload
Local vs OpenAI quality gap
```

예상 검토 구간:

```text
12GB → 개선폭 제한 가능
16GB → 일부 20B급 접근
24GB → 의미 있는 단계 상승
32GB+ → 더 큰 Local Agent 환경
```

이 수치는 구매 결론이 아니라 benchmark 후 검토 프레임이다.

---

# 18. Progress Snapshot

2026-08-10 현재:

```text
[x] Existing AIRA repository 확인
[x] Git clean baseline 확인
[x] Multi-Agent와 Local LLM 실험 축 분리
[x] 별도 repository를 만들지 않기로 결정
[x] root-level local-llm workstream 결정
[x] 현재 PC CPU/GPU/VRAM/RAM 확인
[x] AI data storage 구성
[x] Local LLM 최신 후보 조사
[x] First model set 선정
[x] Ollama Runtime 선정 및 설치
[x] Qwen3.5-4B first local model 실행
[x] GPU/VRAM/RAM/tokens/sec baseline
[x] benchmark foundation
[x] cold/warm benchmark
[x] verified reasoning benchmark
[x] Think OFF/ON benchmark
[x] Thinking budget sweep

[ ] Korean instruction benchmark
[x] structured output / JSON Schema benchmark
[ ] tool selection / native tool calling benchmark
[ ] research planning benchmark
[ ] source relevance / evidence judgment benchmark
[ ] factual discipline benchmark
[ ] AIRA Local LLM adapter audit/design
[ ] Local provider integration
[ ] OpenAI vs Local Single-Agent
[ ] Local Multi-Agent
[ ] Single vs Multi evaluation
[ ] Hybrid experiment
[ ] Hardware upgrade decision
```

---

# 19. Standard Phase Record

각 주요 단계는 가능한 한 다음 형식으로 기록한다.

```text
Goal
Acceptance Criteria
Measured Result
Known Limitation
Stop Rule
Reopen Condition
```

완벽함을 단계 완료 조건으로 삼지 않는다.

---

# 20. Immediate Next Step

**Phase 5 — Local Model Benchmark**를 계속한다.

현재 Qwen3.5-4B는 Small Worker 후보로서 runtime 및 deterministic reasoning baseline을 통과했다.

다음 순서:

```text
Research Planning
→ Source Relevance / Evidence Judgment
→ Factual Discipline
→ AIRA-native complex reasoning
→ Qwen3.5-4B Small Worker 최종 결정
```

이후 동일 핵심 benchmark를 Main Agent 후보인 Qwen3.5-9B와 Ministral 3 8B에 적용한다.
