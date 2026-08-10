# AIRA Local LLM Track — Model Evaluation

- 기준일: 2026-08-09
- 상위 저장소: `/home/moon/Project/agentic-ai-lab`
- 문서 위치: `local-llm/MODEL_EVALUATION.md`
- 단계: Phase 2 — Local LLM Model Research
- 상태: 후보군 조사 완료, Qwen3.5-4B Small Worker 잠정 수용, Main Agent benchmark 대기

---

## 1. 목적

이 문서는 AIRA에 Local LLM backend를 추가하기 전에, 현재 보유 하드웨어에서 실제 실험 가치가 있는 Open-source / Open-weight 모델 후보를 공식 자료를 기준으로 선별하고 그 근거를 기록한다.

이 단계에서는 아직 특정 모델을 AIRA의 최종 기본 모델로 확정하지 않는다.

최종 모델 선택은 다음 요소를 실제 PC에서 측정한 뒤 결정한다.

- GPU VRAM 사용량
- System RAM 사용량
- 모델 load 시간
- tokens/sec
- end-to-end latency
- 한국어 품질
- instruction following
- structured JSON
- tool calling
- research planning
- citation/evidence 판단
- failure rate
- AIRA 실제 workload 품질

---

## 2. 연구 원칙

### 2.1 No Guessing

모델 이름, parameter 수 또는 일반 benchmark 평판만으로 실행 가능성과 품질을 단정하지 않는다.

가능하면 다음을 우선한다.

1. 모델 제작자의 공식 Model Card
2. 공식 runtime/model registry 자료
3. 실제 local benchmark
4. AIRA workload 기반 evaluation

### 2.2 모델 크기와 실제 VRAM 요구량을 동일시하지 않는다

GGUF/Q4 모델 파일 크기는 GPU VRAM 요구량의 하한에 가까운 참고값일 뿐이다.

실제 실행에는 추가로 다음 메모리가 필요하다.

- KV cache
- runtime buffers
- context
- tool/vision 관련 runtime memory
- concurrent sequences

따라서 `6.6GB model file < 8GB VRAM`이라는 이유만으로 8GB GPU에서 긴 context까지 안정적으로 동작한다고 단정하지 않는다.

### 2.3 Multi-Agent와 Local LLM은 서로 다른 실험축이다

AIRA의 실험축은 다음과 같이 분리한다.

| Agent Architecture | LLM Backend |
|---|---|
| Single-Agent | OpenAI |
| Single-Agent | Local |
| Multi-Agent | OpenAI |
| Multi-Agent | Local |
| Multi-Agent | Hybrid |

Local LLM 도입 효과와 Multi-Agent architecture 효과를 혼동하지 않는다.

---

## 3. Hardware Constraint

현재 실제 PC 기준:

- Host: `moon-B360-AORUS-GAMING-3`
- CPU: Intel Core i5-9600KF @ 3.70 GHz
- GPU: NVIDIA GeForce RTX 3060 Ti
- VRAM: 8192 MiB
- RAM: 31 GiB usable
- Ubuntu system SSD: Samsung SSD 860 EVO 500GB
- Windows NVMe: Samsung SSD 970 EVO 500GB
- AI data HDD: ST2000LM005 HN-M201AAD 2TB
- AI data mount: `/mnt/ai-data`

현재 가장 큰 Local LLM 제약은 GPU VRAM 8GB이다.

---

## 4. 1차 Candidate Matrix

| 모델 | 공식/배포 기준 정보 | Agent/Tool 특성 | 현재 8GB GPU 판단 | Phase 2 역할 |
|---|---|---|---|---|
| Qwen3.5-4B Q4_K_M | Ollama model 약 3.4GB | tools / thinking, Qwen 계열 agent 지원 | 매우 유력 | Small Worker |
| Qwen3.5-9B Q4_K_M | Ollama model 약 6.6GB | tool calling / thinking | 유력하나 VRAM 여유 작음 | Main 후보 A |
| Ministral 3 8B Instruct Q4_K_M | Ollama model 약 6.0GB | native function calling / JSON / agentic | 유력하나 VRAM 여유 작음 | Main 후보 B |
| DeepSeek-R1-Distill-Qwen-7B | 7B reasoning distill | reasoning 중심 | 비교 실험 가능 | Reasoning comparator |
| gpt-oss-20b | 공식 약 16GB memory에서 실행 가능 | reasoning / tool use | 8GB GPU-only 주력 부적합 | Larger Comparison |
| Qwen3.6-27B | 27B dense, tool-call 지원 | 고성능 general/agent 후보 | 현재 GPU 주력 부적합 | 향후 HW 비교 |
| Qwen3.6-35B-A3B | MoE, tool-call 지원 | agent/reasoning 후보 | 현재 GPU 주력 부적합 | 향후 HW 비교 |

---

## 5. Small Worker Model

### 선정: Qwen3.5-4B Q4_K_M

Phase 2의 Small Worker 1순위로 선정한다.

공식 Qwen3.5 모델 자료는 tool use를 지원하며, Ollama의 현재 `qwen3.5:4b` Q4_K_M 모델은 약 3.4GB이다.

### 선정 이유

현재 RTX 3060 Ti 8GB에서 다음 조건을 동시에 만족하는 첫 실험 대상으로 적합하다.

- 4B급
- Q4_K_M available
- 모델 weight가 8GB VRAM보다 충분히 작음
- tool/agent 실험 가능
- Qwen 계열의 multilingual 특성
- AIRA worker 역할과 잘 맞음

### 예상 역할

- Query Planner
- Tool Router
- Classifier
- Source Evaluator
- Critic
- Simple Summarizer
- lightweight structured-output worker

### 실제 Phase 3/5 측정 반영

Qwen3.5-4B는 현재 RTX 3060 Ti 8GB에서 다음이 확인되었다.

- Ollama `0.32.6`
- Context 4096
- 100% GPU inference
- model load 후 VRAM 증가량 약 3886 MiB
- generation throughput 약 86~88 tokens/s
- verified reasoning Think OFF: 10/10 정답
- Think ON @3072: 5/5 정답
- 현재 verified reasoning set에서는 Think ON의 정확도 이득이 관찰되지 않음
- Think ON @3072는 Think OFF 대비 평균 latency 약 6.2배, 생성 token 약 9.6배

### 현재 잠정 역할 결정

**Status: PROVISIONAL SMALL WORKER ACCEPTED**

기본 inference policy:

```text
think=false
```

현재 적합성이 높은 역할:

- Classifier
- Router
- schema / structured-output worker
- simple summarizer
- simple relevance evaluator
- deterministic tool selector
- lightweight critic/evaluator

복잡한 reasoning에서는 Qwen3.5-4B의 `think=true`를 자동 기본값으로 사용하지 않는다.
AIRA-native 복합 task에서 Think ON의 실제 품질 이득과 stronger model escalation을 비교한 뒤 결정한다.

### 아직 미검증

- formal JSON Schema reliability
- native tool calling
- research planning
- source/evidence/claim judgment
- factual discipline
- AIRA 실제 production-like workload
- long context
- concurrent execution

상세 benchmark 수치는 `BENCHMARK_RESULTS.md`를 기준으로 한다.

---

## 6. Main Local Agent Candidates

최종 Main Agent는 문서 조사만으로 확정하지 않는다.

두 후보를 동일한 AIRA workload에서 직접 경쟁시킨다.

### Candidate A — Qwen3.5-9B Q4_K_M

현재 Ollama Q4_K_M 모델 크기:

- 약 6.6GB
- context metadata: 256K
- text/image input
- tools/thinking 지원

#### 장점

- Qwen3.5 family
- tool calling
- reasoning/thinking
- multilingual
- Small Worker와 동일 family이므로 behavior 비교가 용이

#### 위험

8GB VRAM에서 모델 weight 자체가 약 6.6GB이므로 KV cache와 runtime용 여유가 작다.

따라서 공식 context maximum을 현재 GPU에서 그대로 사용할 수 있다고 간주하지 않는다.

실제 실험은 낮은 context부터 시작한다.

---

### Candidate B — Ministral 3 8B Instruct Q4_K_M

현재 Ollama Q4_K_M 모델 크기:

- 약 6.0GB
- context metadata: 256K
- text/image input

Mistral 공식 Model Card는 다음을 명시한다.

- multilingual
- Korean 포함
- native function calling
- JSON output
- agentic capabilities

#### 장점

AIRA에서 중요한 structured output과 tool calling에 직접적인 공식 지원 근거가 있다.

한국어도 공식 지원 언어에 명시돼 있어 실제 한국어 연구 작업 비교 가치가 높다.

#### 위험

6GB weight + 8GB VRAM 환경이므로 역시 긴 context 및 concurrency는 실제 측정이 필요하다.

---

## 7. Main Agent 결정 방법

Qwen3.5-9B와 Ministral 3 8B를 다음 동일 benchmark로 평가한다.

### 품질

- 한국어 instruction following
- research decomposition
- query generation
- source relevance 판단
- evidence/claim 판단
- structured JSON
- tool-call schema accuracy
- critique
- synthesis

### 성능

- model load time
- prompt evaluation speed
- generation tokens/sec
- total latency
- peak VRAM
- peak RAM
- CPU offload 여부
- OOM 여부

### 안정성

- malformed JSON rate
- invalid tool-call rate
- timeout
- repeated output
- context overflow
- runtime crash

최종 Main Agent는 이 측정 결과로 결정한다.

---

## 8. Larger Comparison Model

### 선정: gpt-oss-20b

gpt-oss-20b는 현재 RTX 3060 Ti 8GB의 기본 GPU-only 모델로 선정하지 않는다.

OpenAI 공식 자료는 gpt-oss-20b가 약 16GB memory에서 실행 가능한 local/open-weight 모델이라고 설명한다.

### 용도

- CPU/GPU hybrid/offload 비교
- 현재 8GB GPU의 한계 확인
- 더 큰 reasoning model이 AIRA 결과 품질을 얼마나 개선하는지 비교
- 향후 16GB/24GB+ GPU upgrade의 근거 확보

### 원칙

실행 가능하다는 사실과 실용적인 latency를 동일시하지 않는다.

실제 사용 가능성은 benchmark로 판단한다.

---

## 9. Reasoning Comparator

### DeepSeek-R1-Distill-Qwen-7B

DeepSeek-R1-Distill-Qwen-7B는 기본 Main Agent 후보라기보다 reasoning specialist 비교 모델로 유지한다.

용도:

- reasoning-heavy prompt
- multi-step reasoning
- coding/math comparison
- general agent model과 reasoning-specialized model의 차이 측정

AIRA의 tool orchestration 기본 모델로 채택할지는 별도 실험 결과가 필요하다.

---

## 10. 현재 제외/보류 모델

### Qwen3.6-27B

최신 고성능 후보이지만 27B dense 모델은 현재 RTX 3060 Ti 8GB의 첫 Local Agent 대상으로 적합하지 않다.

향후 GPU/RAM upgrade 또는 aggressive offload 실험에서 재검토한다.

### Qwen3.6-35B-A3B

MoE로 active parameter 수가 작더라도 전체 model weight와 runtime memory 요구는 active parameter 수만으로 판단할 수 없다.

현재 8GB GPU의 주력 모델에서는 제외한다.

### 70B급 이상

현재 hardware baseline에서는 주력 local inference 대상으로 보지 않는다.

---

## 11. Phase 2 Decision

### Small Worker

**Qwen3.5-4B Q4_K_M**

상태: 선정

### Main Local Agent

**Candidate A: Qwen3.5-9B Q4_K_M**

**Candidate B: Ministral 3 8B Instruct Q4_K_M**

상태: 실제 benchmark 후 최종 선정

### Larger Comparison

**gpt-oss-20b**

상태: 선정하되 현재 GPU-only 기본 모델 아님

### Reasoning Comparator

**DeepSeek-R1-Distill-Qwen-7B**

상태: 선택적 비교 대상

---

## 12. Phase 2 완료 조건

현재 완료:

- [x] 최신 후보군 조사
- [x] 공식 Model Card 중심 조사
- [x] agent/tool capability 조사
- [x] current Ollama Q4 배포 크기 확인
- [x] 현재 8GB GPU 1차 적합성 분류
- [x] Small Worker 선정
- [x] Main Agent shortlist 선정
- [x] Larger Comparison 선정
- [x] Reasoning Comparator 지정

후속 단계에서 계속 수행:

- [x] Qwen3.5-4B 실제 local runtime benchmark 시작
- [x] Qwen3.5-4B deterministic reasoning / Thinking baseline
- [ ] Qwen3.5-4B AIRA-native capability benchmark 완료
- [ ] 최종 Main Agent 선정

위 미완료 항목은 다음 runtime/benchmark 단계에서 수행한다.

---

## 13. 다음 단계 — Phase 3

### Phase 3 — Local Runtime Installation

초기 runtime:

**Ollama**

첫 실행 모델:

**Qwen3.5-4B Q4_K_M**

실제 측정 후 필요 시:

- llama.cpp
- vLLM

을 비교한다.

### Phase 3 Acceptance Criteria

- [ ] Ollama 정상 설치
- [ ] system service 정상
- [ ] NVIDIA GPU 사용 확인
- [ ] `qwen3.5:4b` 정상 pull
- [ ] local inference 성공
- [ ] 한국어 응답 확인
- [ ] GPU inference 확인
- [ ] VRAM 측정
- [ ] RAM 측정
- [ ] model load / response latency 측정
- [ ] 기본 context에서 OOM 없음

---

## 14. Source References

기준일 2026-08-09에 확인한 주요 자료:

### Qwen

- Qwen3.5-4B official model card  
  https://huggingface.co/Qwen/Qwen3.5-4B

- Qwen3.5-9B official model card  
  https://huggingface.co/Qwen/Qwen3.5-9B

- Qwen3.6-27B official model card  
  https://huggingface.co/Qwen/Qwen3.6-27B

- Qwen3.6-35B-A3B official model card  
  https://huggingface.co/Qwen/Qwen3.6-35B-A3B

### Mistral

- Ministral 3 8B Instruct official model card  
  https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512

- Ministral 3 collection  
  https://huggingface.co/collections/mistralai/ministral-3

### OpenAI

- Introducing gpt-oss  
  https://openai.com/index/introducing-gpt-oss/

### Ollama distribution metadata

- Qwen3.5 tags  
  https://ollama.com/library/qwen3.5/tags

- Ministral 3 tags  
  https://ollama.com/library/ministral-3/tags

---

## 15. Stop Rule

Phase 2에서 더 많은 모델을 무한히 조사하지 않는다.

현재 8GB GPU에서 실험 가치가 충분한 후보군이 확보되었으므로, 이 시점에서 문헌 조사 중심의 후보 탐색을 종료하고 실제 runtime 측정으로 이동한다.

### Reopen Condition

다음 중 하나가 발생하면 Model Research를 다시 연다.

- 현재 shortlist 모두 실사용 품질 미달
- tool calling이 AIRA 요구조건을 충족하지 못함
- 새로운 모델이 현저한 성능/메모리 우위를 보임
- GPU/RAM hardware upgrade
- vision/coding 등 새로운 필수 capability가 추가됨

=== RUNTIME EVALUATION ===
