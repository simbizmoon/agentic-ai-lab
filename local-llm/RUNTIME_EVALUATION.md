# AIRA Local LLM Track — Runtime Evaluation

- 기준일: 2026-08-09
- 상위 저장소: `/home/moon/Project/agentic-ai-lab`
- 권장 저장 위치: `local-llm/RUNTIME_EVALUATION.md`
- 단계: Phase 3 — Local Runtime Installation & First Inference
- 상태: COMPLETE

## 1. 목적

이 문서는 AIRA Local LLM Track의 최초 runtime인 Ollama를 실제 Ubuntu PC에 설치·검증하고,
첫 Local LLM인 `qwen3.5:4b`의 GPU 실행, 메모리 사용량, API 동작, Thinking 제어 및 기본 성능을 기록한다.

이 문서의 수치는 추정값이 아니라 2026-08-09 실제 실행 결과를 기준으로 한다.

## 2. Runtime Baseline

- Ollama 설치 경로: `/usr/local/bin/ollama`
- Ollama 버전: `0.32.6`
- systemd service: enabled / active (running)
- local API: `http://127.0.0.1:11434`
- Backend: CUDA
- GPU: NVIDIA GeForce RTX 3060 Ti
- Compute Capability: 8.6

## 3. First Local Model

- Model: `qwen3.5:4b`
- Ollama model size: 약 3.4 GB
- model ID: `2a654d98e6fb`
- `ollama ps`: 약 3.1 GB
- Processor: `100% GPU`
- Context: `4096`
- CPU offload: 없음

## 4. GPU Memory Measurement

실행 전:
- total VRAM: 8192 MiB
- used VRAM: 1025 MiB
- free VRAM: 6846 MiB

실행 후:
- total VRAM: 8192 MiB
- used VRAM: 4911 MiB
- free VRAM: 2961 MiB

증가량:
`4911 - 1025 = 3886 MiB`

즉 최초 4K context baseline에서 모델 적재에 따른 VRAM 증가는 약 3.8 GiB 수준이었다.

## 5. System RAM Measurement

모델 실행 후:
- total RAM: 31 GiB
- used RAM: 약 7.0 GiB
- available RAM: 약 24 GiB
- swap used: 0 B

현재 Qwen3.5-4B GPU inference에서는 System RAM이 병목으로 관찰되지 않았다.

## 6. Korean Inference

최초 한국어 prompt에 대해 정상 응답하였다.

최소 통과 항목:
- UTF-8 / 한국어 입출력
- Ollama CLI inference
- Local model execution
- CUDA inference

품질 수준은 Phase 4 benchmark에서 별도로 평가한다.

## 7. Thinking Behavior

### 기본 Thinking ON 실험

Thinking-capable model의 기본 API 호출에서 긴 reasoning trace가 생성되었다.

측정:
- `eval_count`: 4068
- `eval_duration`: 46.57992 s
- generation throughput: 약 87.3 tokens/s
- `done_reason`: `length`
- final `response`: 빈 문자열

즉 단순 요약성 prompt에서도 Thinking이 길게 지속되면서 output budget을 소모하고
최종 답변까지 도달하지 못하는 사례가 실제 발생하였다.

### Thinking OFF 실험

CLI:
`ollama run qwen3.5:4b --think=false ...`

결과:
`{"status":"ok","message":"local model ready"}`

API에서도 `"think": false` 설정 후 최종 응답이 정상 반환되었다.

## 8. Thinking Policy

Thinking을 항상 비활성화하는 것이 프로젝트 목표는 아니다.

AIRA에서는 작업 유형에 따라 선택적으로 사용한다.

### Think OFF — 기본 Worker Mode

다음과 같이 문제 구조가 단순하거나 출력 형식이 엄격한 작업에서는 기본적으로 Thinking을 끈다.

- classification
- routing
- schema extraction
- structured JSON
- simple summarization
- simple relevance judgment
- deterministic tool selection
- format conversion
- lightweight critic/evaluator

목적:
- latency 감소
- token 사용량 감소
- output budget 보호
- Multi-Agent 전체 호출량 통제

### Think ON — Reasoning Mode

다음과 같은 작업에서는 Thinking을 켜는 실험을 수행한다.

- complex planning
- multi-hop reasoning
- difficult evidence comparison
- contradiction analysis
- hard critique
- synthesis requiring trade-off analysis
- ambiguous decision tasks

중요:
Thinking ON이 항상 더 좋은 결과를 보장한다고 가정하지 않는다.

Phase 4에서 동일 task를 Think OFF / Think ON으로 실행하여
정답률, 품질, latency, token count 및 failure rate를 직접 비교한다.

## 9. Think OFF Performance Baseline

실측:
- total_duration: 11.435096902 s
- load_duration: 10.055406807 s
- prompt_eval_count: 30
- prompt_eval_duration: 0.098902 s
- eval_count: 111
- eval_duration: 1.27833 s
- done_reason: stop

Generation throughput:
`111 / 1.27833 ≈ 86.8 tokens/s`

Prompt evaluation throughput:
`30 / 0.098902 ≈ 303.3 tokens/s`

전체 11.4초 중 약 10.1초가 model load였으므로 이 결과는 cold/warm 상태가 섞인 최초 baseline으로 취급한다.

## 10. Structured Output Baseline

Prompt-only JSON instruction에서도 올바른 단일 JSON object가 반환되었다.

AIRA integration에서는 prompt-only JSON에 의존하지 않고
가능하면 Ollama의 `format: "json"` 또는 JSON Schema 기반 structured output 기능을 우선 실험한다.

## 11. Initial Runtime Configuration

Phase 4 시작 baseline:
- Runtime: Ollama 0.32.6
- Model: qwen3.5:4b
- Context: 4096
- Parallelism: 1
- GPU execution: 100%
- Worker default: `think=false`
- Reasoning experiment: `think=true`
- API: localhost only

## 12. Phase 3 Acceptance Criteria

- [x] Ollama 설치/업데이트
- [x] systemd service 정상
- [x] local API 정상
- [x] NVIDIA CUDA 인식
- [x] RTX 3060 Ti 인식
- [x] Qwen3.5-4B pull
- [x] Local inference
- [x] 한국어 inference
- [x] 100% GPU execution
- [x] CPU offload 없음
- [x] VRAM 측정
- [x] RAM 측정
- [x] Thinking OFF 확인
- [x] structured JSON baseline
- [x] API usage metrics 확보
- [x] generation throughput 측정

**Phase 3: COMPLETE**

## 13. Known Limitations

Phase 5에서 추가 확인 완료:

- cold/warm latency 분리 측정
- repeated reasoning run 측정
- Think OFF vs Think ON verified reasoning 비교
- Thinking generation budget 1024 / 2048 / 3072 비교

상세 결과는 `BENCHMARK_RESULTS.md`에 기록한다.

아직 확인되지 않은 항목:

- 8K/16K/32K context에서 VRAM 변화
- concurrent agent execution
- long-context quality
- formal JSON Schema reliability
- actual tool calling reliability
- AIRA-native complex reasoning에서 Think ON의 품질 이득
- Main Agent 후보 9B/8B 비교

## 14. Next Phase

Runtime 설치 및 first inference 단계는 완료되었다.

현재 공식 다음 단계:
**Phase 5 — Local Model Benchmark**

첫 benchmark model:
`qwen3.5:4b`

이미 완료된 runtime/reasoning checkpoint는 `BENCHMARK_RESULTS.md`에서 관리한다.

남은 핵심 실험:
1. Korean instruction following
2. Structured output / JSON Schema
3. Tool selection / native tool calling
4. Research planning
5. Source relevance / evidence judgment
6. Factual discipline
7. AIRA-native workload
8. Main Agent 후보 비교
