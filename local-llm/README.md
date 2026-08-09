# AIRA Local LLM Experimental Track

- 기준일: 2026-08-09
- 상위 프로젝트: Agentic AI Lab (AIRA)
- Repository: `/home/moon/Project/agentic-ai-lab`
- Local LLM Track 경로: `/home/moon/Project/agentic-ai-lab/local-llm`
- 대용량 AI 데이터 경로: `/mnt/ai-data`

## 1. 목적

이 디렉터리는 AIRA에 **Local Open-Source / Open-Weight LLM backend**를 추가하기 위한 연구·설계·평가·의사결정 기록을 관리한다.

현재 AIRA는 OpenAI API와 연동된 Single-Agent Live Research 경로를 보유하고 있으며, 다음 학습·제품 단계로 Multi-Agent Experiment를 진행한다. Local LLM은 Multi-Agent 자체와 동일한 개념으로 묶지 않고, **LLM Provider / Inference Backend의 별도 실험 축**으로 관리한다.

즉 다음 두 축을 독립적으로 비교한다.

```text
Agent Architecture
- Single-Agent
- Multi-Agent

LLM Backend
- OpenAI
- Local
- Hybrid
```

이를 통해 다음 실험이 가능해야 한다.

| Experiment | Agent Architecture | LLM Backend |
|---|---|---|
| A | Single-Agent | OpenAI |
| B | Single-Agent | Local |
| C | Multi-Agent | OpenAI |
| D | Multi-Agent | Local |
| E | Multi-Agent | Hybrid |

## 2. Repository 운영 원칙

Local LLM 작업을 위해 별도 Git repository를 만들지 않는다.

현재 Local LLM Track은 AIRA의 Research Pipeline, Tool abstraction, Guardrail, Budget, Trace, Evaluation, Citation, Evidence, Agent State 및 향후 Multi-Agent Orchestration과 직접 통합되어야 하므로 기존 `agentic-ai-lab` repository 안에서 관리한다.

```text
/home/moon/Project/agentic-ai-lab/
├── MASTER.md
├── README.md
├── ROADMAP.md
├── DECISIONS.md
├── AIRA_MULTI_AGENT_ROADMAP.md
├── local-llm/
│   ├── README.md
│   ├── ROADMAP.md
│   └── HARDWARE_BASELINE.md
├── app/
├── tests/
├── evals/
├── docs/
├── reports/
└── ...
```

`local-llm/`은 **소스코드 위치가 아니다.**

이곳에는 다음을 기록한다.

- Local LLM 도입 전략
- 모델 조사 및 선정 근거
- Runtime 조사 및 선정 근거
- 하드웨어 baseline
- benchmark 계획과 결과
- OpenAI vs Local vs Hybrid 비교
- Local LLM Track의 진행상황과 Stop Rule

실제 production code와 tests는 기존 AIRA 구조 안에 둔다.

## 3. 코드 통합 원칙

OpenAI용 Research Pipeline과 Local LLM용 Research Pipeline을 복제해서 별도로 만들지 않는다.

목표 구조는 다음과 같다.

```text
Research / Agent Logic
        │
        ▼
   LLM Port / Interface
        │
   ┌────┴────┐
   ▼         ▼
OpenAI     Local
Adapter    Adapter
   │         │
OpenAI     Ollama / llama.cpp / vLLM
API          │
          Local Model
```

Agent와 Research Pipeline은 가능한 한 어떤 LLM provider를 사용하는지 몰라도 동작해야 한다.

초기에는 기존 코드 구조와 abstraction을 먼저 실제로 audit하고, 최소 변경으로 Local LLM adapter를 추가한다. 기존 코드를 추측으로 대규모 refactor하지 않는다.

## 4. Multi-Agent와 Local LLM의 관계

Local LLM과 Multi-Agent는 별도의 연구 축이다.

- `AIRA_MULTI_AGENT_ROADMAP.md`: Single-Agent에서 Multi-Agent architecture로 어떻게 확장할지를 다룬다.
- `local-llm/ROADMAP.md`: OpenAI 이외에 Local LLM backend를 어떻게 추가·검증할지를 다룬다.

초기 Local Multi-Agent에서는 Agent마다 별도 모델을 반드시 load하지 않는다.

```text
Planner ──────┐
Researcher ───┤
Critic ───────┤──> One Local LLM Server
Evaluator ────┤
Synthesizer ──┘
```

먼저 하나의 Local LLM을 여러 logical Agent가 공유하고, 필요성이 실제 benchmark로 확인될 때만 heterogeneous model routing을 도입한다.

## 5. 저장장치 역할 분리

### Git / Source / Active Development

```text
/home/moon/Project/agentic-ai-lab
```

여기에는 다음을 둔다.

- source code
- tests
- configuration
- documentation
- 작은 실험 fixture
- Git으로 추적해야 하는 결과

### Large AI Data

```text
/mnt/ai-data
```

여기에는 Git으로 관리하지 않는 대용량 자료를 둔다.

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

현재 `/mnt/ai-data`는 2TB HDD이므로 대용량 모델, dataset, RAG corpus, crawl, archive 등에 사용한다. 자주 실행하는 모델과 latency-sensitive hot data는 필요에 따라 SSD에 둔다.

## 6. 기본 원칙

1. **No Guessing** — 모델 실행 가능성, VRAM, RAM, 속도, 품질을 추측으로 확정하지 않는다.
2. **Measurement First** — `nvidia-smi`, RAM, load time, tokens/sec, latency, task result를 실제 측정한다.
3. **Integration First** — 기존 AIRA capability를 최대한 재사용한다.
4. **Small Model First** — 4B~8B급부터 시작해 필요가 확인될 때 확장한다.
5. **Sequential Before Parallel** — RTX 3060 Ti 8GB에서 초기 Multi-Agent inference는 순차 실행을 기본으로 한다.
6. **Provider Separation** — OpenAI, Local, Hybrid를 명시적으로 구분한다.
7. **Architecture Separation** — Single/Multi-Agent 효과와 LLM backend 효과를 같은 변수로 섞지 않는다.
8. **Reproducible Evaluation** — 동일 prompt/task/eval set으로 provider와 architecture를 비교한다.
9. **No Premature Hardware Purchase** — 실제 benchmark에서 병목이 확인되기 전에는 업그레이드를 확정하지 않는다.

## 7. 현재 Git Baseline

2026-08-09 Local LLM Track 시작 직전 확인 상태:

```text
Branch: main
HEAD: 86fd1c6
Remote: origin/main
Working tree: clean
```

최근 commit:

```text
86fd1c6 docs: close single-agent stage and add multi-agent roadmap
4f50ebb feat: batch evidence-backed claim generation
9eefdba feat: batch semantic citation verification
7b1d956 feat: batch claim relevance evaluation
e36d87b feat: batch semantic evidence relevance evaluation
```

이 상태를 Local LLM Track 도입 전 기준점으로 사용한다.

## 8. 문서 역할

### `README.md`

Local LLM Track의 범위, repository 운영 원칙, OpenAI/Local/Multi-Agent 분리 원칙을 정의한다.

### `ROADMAP.md`

Local LLM 조사, runtime 설치, first model, benchmark, AIRA 통합, OpenAI/Local/Hybrid 비교의 단계와 완료 조건을 관리한다.

### `HARDWARE_BASELINE.md`

현재 PC의 실제 CPU, GPU, VRAM, RAM, storage, SMART 및 AI용 저장장치 구성을 기록한다.

향후 필요할 때 다음 문서를 추가한다.

```text
MODEL_EVALUATION.md
RUNTIME_EVALUATION.md
BENCHMARK_PLAN.md
BENCHMARK_RESULTS.md
```

빈 문서를 미리 만들지 않고 실제 작업이 시작되는 시점에 추가한다.

## 9. 현재 다음 작업

다음 작업은 **Local LLM Candidate Research**이다.

현재 PC에서 실제로 사용할 수 있는 최신 Open-Source / Open-Weight LLM을 공식 자료 기준으로 조사하고 최소 다음 역할의 후보를 선정한다.

```text
A. Small Worker Model
B. Main Local Agent Model
C. Larger Comparison Model
```

그 이후에 Runtime(Ollama / llama.cpp / 필요 시 vLLM)을 선정하고 실제 설치·benchmark를 시작한다.
