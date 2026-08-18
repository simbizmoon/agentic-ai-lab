# AIRA Local LLM / OpenAI LLM / Agent 사용 매뉴얼

- 기준일: 2026-08-18
- 프로젝트: Agentic AI Lab / AIRA
- 프로젝트 경로: `/home/moon/Project/agentic-ai-lab`
- 실험 데이터 경로: `/mnt/ai-data`
- 운영체제: Ubuntu 24.04 LTS
- Local runtime: Ollama 0.32.6
- 현재 권장 Local bounded worker: `qwen3.5:4b`
- 현재 기본 Architecture: **Single-Agent default + workload-dependent Multi-Agent escalation + OpenAI/Local Hybrid**

---

## 1. 이 문서의 목적

이 문서는 현재 AIRA에서 다음 작업을 실제로 수행하기 위한 운영 매뉴얼이다.

1. 현재 설치된 Local LLM 확인
2. Ollama로 Local LLM 직접 실행
3. AIRA에서 Local LLM 사용
4. AIRA에서 OpenAI LLM 사용
5. Local/OpenAI Hybrid 구조 이해
6. Single-Agent / Multi-Agent 사용 원칙 이해
7. OpenAI Agents SDK로 별도 Agent 실행
8. Local Document Research 실행과 모드 선택
9. 상태 확인, 종료, 문제 해결
10. Patent Technical Research CLI 실행

중요한 원칙:

> **설치된 모델과 AIRA에서 채택된 모델은 다르다.**

현재 여러 Local LLM이 설치되어 있지만 AIRA production-aligned bounded worker로 채택된 모델은 `qwen3.5:4b`이다.

---

# 2. 현재 설치된 Local LLM

Phase 12까지 실제 확인된 설치 모델은 다음과 같다.

| 모델 | 확인된 상태 | 대략적 모델 파일 크기 | AIRA 현재 역할 |
|---|---|---:|---|
| `qwen3.5:4b` | 설치됨 | 약 3.4 GB | **현재 채택된 bounded local worker** |
| `qwen3.5:9b` | 설치됨 | 약 6.6 GB | 평가용, 4B 대체 미채택 |
| `ministral-3:8b` | 설치됨 | 약 6.0 GB | 평가용, 4B 대체 미채택 |
| `llama3.1:8b` | 설치됨 | 약 4.9 GB | hardware capacity probe |
| `llama3.3:latest` | 설치됨 | 약 42 GB | 기존 설치 모델, 현재 AIRA production worker로 평가/채택되지 않음 |

현재 실제 AIRA 권장 Local 모델:

```text
qwen3.5:4b
```

Phase 12 실측에서:

```text
qwen3.5:4b
→ 100% GPU
→ 현재 RTX 3060 Ti 8GB에서 안정적
→ 세 bounded worker 역할의 전체 quality / latency / safety trade-off 우수

qwen3.5:9b
→ 13% CPU / 87% GPU
→ 4B 대비 전체 품질 우위 없음
→ 약 1.8x 느림

ministral-3:8b
→ 22% CPU / 78% GPU
→ 4B 대비 전체 품질 우위 없음
→ 약 1.66x 느림
```

따라서 모델 크기가 더 크다는 이유만으로 9B/8B 모델을 기본값으로 사용하지 않는다.

---

# 3. Ollama 기본 사용법

## 3.1 Ollama 상태 확인

```bash
ollama --version
```

설치된 모델 확인:

```bash
ollama list
```

현재 메모리에 올라가 실행 중인 모델 확인:

```bash
ollama ps
```

예:

```text
NAME          SIZE      PROCESSOR    CONTEXT
qwen3.5:4b    3.1 GB    100% GPU     4096
```

---

## 3.2 모델 상세정보 확인

```bash
ollama show qwen3.5:4b
```

현재 확인된 주요 정보:

```text
architecture        qwen35
parameters          4.7B
context length      262144
quantization        Q4_K_M
capabilities        completion / vision / tools / thinking
```

주의:

- 모델 metadata context와 실제 AIRA runtime context는 다를 수 있다.
- 현재 실측 runtime에서는 context `4096`으로 올라가는 것이 확인되었다.

---

# 4. Local LLM 직접 사용

## 4.1 Qwen3.5-4B 대화 시작

터미널에서:

```bash
ollama run qwen3.5:4b
```

그러면 interactive prompt가 시작된다.

종료:

```text
/bye
```

또는 `Ctrl+D`.

---

## 4.2 한 번만 질문하고 종료

```bash
ollama run qwen3.5:4b \
  "Explain what an AI agent is in five sentences."
```

---

## 4.3 Thinking 사용 주의

Qwen3.5는 기본 CLI 실행에서 Thinking을 길게 생성할 수 있다.

AIRA의 bounded worker에서는 현재 다음 원칙을 사용한다.

```text
normal bounded worker
→ think=false
```

직접 CLI에서 deterministic short task를 시험할 때도 가능하면 thinking을 끄는 편이 현재 AIRA 정책과 맞다.

예:

```bash
ollama run qwen3.5:4b --think=false \
  "Reply with exactly: LOCAL_OK"
```

현재 AIRA에서 `think=false`를 사용하는 주요 이유:

- unnecessary long reasoning 방지
- latency 예측 가능성 향상
- structured output 안정성
- generation budget 통제

---

# 5. Local 모델 메모리에서 내리기

```bash
ollama stop qwen3.5:4b
```

모두 내려갔는지 확인:

```bash
ollama ps
```

GPU 상태:

```bash
nvidia-smi
```

---

# 6. 다른 설치 모델 직접 실행

## Qwen3.5-9B

```bash
ollama run qwen3.5:9b
```

현재 PC에서는 실측상:

```text
13% CPU / 87% GPU
```

로 partial CPU offload가 발생한다.

AIRA 기본 worker로 사용하지 않는 것을 권장한다.

---

## Ministral 3 8B

```bash
ollama run ministral-3:8b
```

현재 PC에서는 실측상:

```text
22% CPU / 78% GPU
```

로 partial CPU offload가 발생한다.

AIRA 4B 대체 worker로는 현재 미채택이다.

---

## Llama 3.1 8B

```bash
ollama run llama3.1:8b
```

Phase 12에서 다음이 확인되었다.

```text
100% GPU
```

하지만 이는 hardware capacity probe이며 현재 AIRA bounded worker 품질 평가를 거쳐 채택된 모델은 아니다.

---

## Llama 3.3

```bash
ollama run llama3.3:latest
```

현재 설치 파일이 매우 크므로 현재 RTX 3060 Ti 8GB에서의 실행 전략을 AIRA production 정책으로 간주하지 않는다.

단순히 설치돼 있다는 이유로 기본 worker로 지정하지 않는다.

---

# 7. AIRA 환경 준비

프로젝트 이동:

```bash
cd /home/moon/Project/agentic-ai-lab
```

Python virtual environment 활성화:

```bash
source .venv/bin/activate
```

현재 branch/status 확인:

```bash
git status --short
git log -3 --oneline
```

AIRA CLI 확인:

```bash
aira --help
```

---

# 8. AIRA에서 Local LLM 사용

## 8.1 권장 Local worker 설정

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
```

Ollama 기본 연결값:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_TIMEOUT_SECONDS=120
```

실제 기본값이므로 특별한 이유가 없으면 명시하지 않아도 된다.

---

## 8.2 Source Reading concurrency

현재 live runtime 기본값:

```text
2
```

기본값 사용:

```bash
unset AIRA_SOURCE_READ_CONCURRENCY
```

강제 serial:

```bash
export AIRA_SOURCE_READ_CONCURRENCY=1
```

병렬 source read를 4로 시험:

```bash
export AIRA_SOURCE_READ_CONCURRENCY=4
```

허용 범위:

```text
1..8
```

현재 권장 production default:

```text
2
```

주의:

- Source Reading만 bounded parallel이다.
- Source Search는 shared usage/budget 상태 때문에 serial이다.
- Local Qwen worker 자체 concurrency는 현재 1을 유지한다.

---

## 8.3 Local Document Research 모드

`research`는 로컬 문서를 조사하는 capability이고, `--mode`는 그 문서를
어떻게 분석할지 선택한다. 현재 지원 형식은 UTF-8 `.txt`, `.md`, `.markdown`, text-based `.pdf`, text-bearing `.hwpx`이다.

### 기본 deterministic/offline 모드

`--mode`를 생략하면 기존 offline deterministic 계약을 그대로 사용한다.
OpenAI, Tavily, Ollama 설정이 필요하지 않다.

```bash
aira research \
  --allowed-root "$PWD" \
  --question "How does grounded research use local evidence?" \
  --objective "Explain the local evidence using traceable citations." \
  --source notes.md \
  --output-dir reports/local-deterministic
```

다음 명령은 완전히 같은 모드이다.

```bash
aira research --mode deterministic \
  --allowed-root "$PWD" \
  --question "How does grounded research use local evidence?" \
  --objective "Explain the local evidence using traceable citations." \
  --source notes.md
```

Text-based PDF도 같은 offline 경로를 사용할 수 있다.

```bash
aira research --mode deterministic \
  --allowed-root "$PWD" \
  --question "What evidence does this PDF provide?" \
  --objective "Create a grounded offline report from the local PDF." \
  --source evidence.pdf
```

Text-bearing HWPX도 같은 명령 계약을 사용한다.

```bash
aira research --mode deterministic \
  --allowed-root "$PWD" \
  --question "What evidence does this HWPX document contain?" \
  --objective "Create a grounded offline report from local HWPX evidence." \
  --source evidence.hwpx
```

이 경로는 `WholeDocumentEvidenceExtractor`와
`DeterministicPipelineClaimBuilder`를 사용하며 기존 `report.md`와
`result.json` 출력을 보존한다.

### 명시적 semantic Local 모드

Semantic Local Research는 opt-in이다.

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

aira research --mode semantic \
  --approve-external-send \
  --allowed-root "$PWD" \
  --question "How does AIRA divide work between OpenAI and the local model?" \
  --objective "Explain hybrid role routing using grounded local evidence." \
  --source hybrid-routing.hwpx \
  --output-dir reports/local-semantic
```

Semantic 모드는 local search/reader와 query, local path, filename provenance를
보존한다. PDF evidence는 physical page number를, HWPX evidence는 `hwpx_section_index`와 `hwpx_package_path`를 exact character range와 함께 보존하면서 paragraph candidate, lexical + embedding RRF shortlist, semantic
evidence relevance, generated claim 및 semantic citation/relevance/coverage를
실행한다.

모든 Local Research source는 명시적 `--allowed-root` 안에 있어야 하며 raw file
크기는 source당 최대 32 MiB이다. leaf symlink는 거부하고 raw byte SHA-256과 file
size를 provenance로 보존한다. Deterministic mode는 approval 없이 offline으로
실행된다. Semantic mode의 `--approve-external-send`는 현재 실행의 canonical path,
raw SHA-256 및 size에만 유효하며, provider 구성 직전에 같은 policy로 다시 검증한다.
파일이 바뀌면 새 승인이 필요하다. 이 검사는 descriptor-level TOCTOU를 완전히
해결하지 않으며 민감정보 분류·redaction·영구 approval 저장도 아직 제공하지 않는다.

Provider routing:

```text
OpenAI
- embedding
- evidence relevance
- claim generation

AIRA_RESEARCH_WORKER_PROVIDER 정책에 따라 OpenAI 또는 Local
- semantic citation
- claim relevance
- answer coverage
```

`AIRA_RESEARCH_WORKER_PROVIDER=local`은 full-local research를 뜻하지 않는다.
Semantic 모드는 여전히 유효한 OpenAI 설정이 필요하다. 실패 시 deterministic으로
조용히 fallback하지 않고 오류를 보고한다. Text-based PDF와 text-bearing HWPX는 지원하지만 scanned/image-only PDF와 OCR, HWP binary, DOCX는 아직 지원하지 않는다. HWPX table/image/layout 전용 해석도 제공하지 않는다.

### Live Web Research

인터넷 자료 조사는 별도 `research-live` capability를 사용한다. Tavily와 OpenAI
설정이 필요하며 Local 문서 모드와 혼동하지 않는다.

### Integrated Web + Local Research

현재 Web 정보와 승인된 non-sensitive Local 문서를 한 report에서 함께 조사할 때 사용한다.

```bash
aira research-integrated \
  --question "How does AIRA combine Web and Local evidence?" \
  --objective "Explain the topic using current Web sources and an approved local note." \
  --source "$PWD/non-sensitive-notes.md" \
  --allowed-root "$PWD" \
  --approve-external-send \
  --maximum-sources 4 \
  --maximum-bytes 1000000 \
  --output-dir reports/integrated
```

`--source`와 `--allowed-root`는 repeatable이며 approval flag는 필수다. 이 command에는
`--mode`가 없다. Local content는 canonical path, raw SHA-256 및 size에 묶인 distinct
Integrated approval과 fresh revalidation을 통과한 뒤 external semantic component가
처리한다. Semantic Local approval과 Integrated approval은 서로 호환되지 않는다.

Web와 Local은 각각 evidence extraction 기회를 받지만 citation은 강제되지 않는다.
Relevant Local evidence는 final claim/citation에 포함될 수 있고 irrelevant Local evidence는
`NO_EVIDENCE`로 제외된 뒤 backfill된다. Tavily usage는 Web provider search만 나타낸다.

이 경로는 Web와 Local source를 기존 research pipeline에 federation한 vertical slice이다.
Persistent vector index, parsing/embedding cache를 포함하는 full persistent RAG는 후속 범위다.

# 9. AIRA Local Single-Agent 실제 실행 예

Web-only 인터넷 Research는 `research-live`, Local-only 문서는 `research`, Web + Local
통합 Research는 `research-integrated` 경로를 사용한다.

예:

```bash
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate

export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
unset AIRA_SOURCE_READ_CONCURRENCY

aira research-live \
  --question "What are the main components of the OpenAI Agents SDK?" \
  --objective "Give a concise evidence-grounded overview using authoritative web sources." \
  --maximum-sources 2 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/manual-local-run
```

실행 결과에는 일반적으로 다음 artifact가 생성된다.

```text
report.md
result.json
```

실제 저장 경로는 실행 시 출력되는:

```text
AIRA live report:
AIRA live result:
```

를 확인한다.

---

# 10. Local worker가 실제 사용됐는지 확인

실행 중:

```bash
ollama ps
```

예:

```text
qwen3.5:4b
100% GPU
```

GPU:

```bash
nvidia-smi
```

AIRA artifact에서 Local provider provenance가 기록됐는지도 확인할 수 있다.

예:

```bash
grep -Rni "ollama-local" /mnt/ai-data/experiments/manual-local-run
```

---

# 11. AIRA에서 Qwen3.5-4B가 맡는 역할

현재 Qwen3.5-4B는 **범용 Main Agent가 아니다.**

채택된 주요 bounded worker 역할:

```text
Semantic Citation Verification
→ bounded first-pass verifier

Claim Relevance
→ bounded classifier

Answer Coverage
→ reviewer / critic
```

사용하지 않는 역할:

```text
Autonomous research planner
Unconstrained long planning
Policy-sensitive orchestration
Final authoritative factual verifier
```

특히:

> Local `fully_covered` 결과 하나만으로 답변의 완전성을 최종 확정하지 않는다.

---

# 12. 현재 AIRA Single-Agent 원칙

현재 공식 기본 구조:

```text
Single-Agent
→ DEFAULT
```

이 말은 Local LLM 하나가 모든 것을 한다는 뜻이 아니다.

AIRA Single-Agent pipeline 내부에서도 역할별로:

```text
Deterministic control
OpenAI / stronger model
Local bounded worker
```

가 조합될 수 있다.

즉 **Agent 개수와 LLM provider 개수는 같은 개념이 아니다.**

---

# 13. 현재 AIRA Hybrid Architecture

현재 기본 설계 원칙:

```text
Deterministic
+ OpenAI / stronger-model high-judgment path
+ Local qwen3.5:4b bounded semantic workers
```

대표적인 역할 분리:

## Deterministic

```text
task decomposition
query planning
source quality
document selection
control paths
synthesis where deterministic logic is sufficient
```

## OpenAI / stronger model

```text
high-judgment evidence relevance
claim generation
필요 시 high-judgment escalation
```

## Local Qwen3.5-4B

```text
semantic citation
claim relevance
answer coverage review
```

중요:

> AIRA는 모든 작업을 하나의 universal LLM provider에 강제로 연결하지 않는다.

---

# 14. AIRA에서 OpenAI LLM 사용 준비

OpenAI API key를 shell 환경변수로 설정한다.

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

확인:

```bash
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY is set"
```

키 전체를 화면에 출력하지 않는 것이 좋다.

주의:

```text
.env 또는 shell 환경변수로 관리
Git에 API key commit 금지
공개 로그에 API key 출력 금지
```

OpenAI 공식 SDK와 Agents SDK는 `OPENAI_API_KEY` 환경변수를 기본적으로 사용할 수 있다.

---

# 15. AIRA에서 OpenAI bounded worker 사용

현재 bounded worker provider를 OpenAI로 돌리려면:

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=openai
```

또는 현재 runtime 기본값이 OpenAI이므로 별도 override가 없다면:

```bash
unset AIRA_RESEARCH_WORKER_PROVIDER
```

후 live research를 실행한다.

```bash
aira research-live \
  --question "What are the main components of the OpenAI Agents SDK?" \
  --objective "Give a concise evidence-grounded overview using authoritative web sources." \
  --maximum-sources 2 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/manual-openai-run
```

주의:

- 프로젝트의 정확한 OpenAI model 선택은 현재 AIRA composition/configuration을 따른다.
- 이 매뉴얼에서는 확인되지 않은 별도 OpenAI model 환경변수 이름을 임의로 만들지 않는다.
- OpenAI API 호출은 ChatGPT Plus 구독과 별도의 API 사용량/과금 체계이다.

---

# 16. Local과 OpenAI를 빠르게 전환하는 방법

## Local Qwen3.5-4B

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
```

## OpenAI

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=openai
```

상태 확인:

```bash
echo "$AIRA_RESEARCH_WORKER_PROVIDER"
echo "$AIRA_LOCAL_WORKER_MODEL"
```

---

# 17. 권장 운영 Profile

## Profile A — 현재 권장 Hybrid/Production 방향

목적:

```text
품질이 높은 판단은 OpenAI/stronger path
반복 가능한 bounded semantic work는 Local 4B
```

장점:

- Local 비용 절감
- 4B low-latency worker 활용
- 어려운 판단을 작은 모델에 과도하게 맡기지 않음

현재 AIRA의 최종 권장 방향이다.

---

## Profile B — Local bounded-worker 중심 테스트

```bash
export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
```

용도:

- Local integration smoke
- bounded evaluator 개발
- 비용 없는 반복 테스트
- Ollama/GPU runtime 확인

---

## Profile C — OpenAI worker 기준선

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export AIRA_RESEARCH_WORKER_PROVIDER=openai
```

용도:

- OpenAI vs Local 비교
- high-judgment 기준선
- Local model regression 판단

---

# 18. Multi-Agent 사용 원칙

현재 공식 결정:

```text
Single-Agent
→ DEFAULT

Multi-Agent
→ WORKLOAD-DEPENDENT ESCALATION
```

즉 agent 수를 늘리는 것이 목표가 아니다.

Multi-Agent를 고려하는 경우:

- specialist 역할 분리가 품질을 실제로 높일 가능성이 있음
- context isolation이 필요함
- failure isolation 편익이 있음
- reviewer/critic 추가 비용이 정당화됨
- 복잡한 작업을 서로 다른 역할로 분리해야 함

사용하지 말아야 하는 이유:

```text
"Multi-Agent가 더 최신이니까"
"Agent 수가 많으면 더 똑똑할 것 같아서"
```

만으로는 충분하지 않다.

---

# 19. 현재 AIRA Multi-Agent 구조 개념

현재 구축된 orchestrator에는 다음과 같은 역할 개념이 존재한다.

```text
MANAGER
SEARCH_SPECIALIST
SOURCE_READER
EVIDENCE_ANALYST
SOURCE_CRITIC
CLAIM_ANALYST
CITATION_VERIFIER
SYNTHESIS_SPECIALIST
QUALITY_REVIEWER
```

대표 dependency 흐름:

```text
Search
→ Reader
→ Evidence
→ Claim
→ Synthesis / Review
```

현재 dependency stage는 기본적으로 순차 실행한다.

Qwen3.5-4B quality reviewer는:

```text
bounded advisory reviewer
```

이지 최종 authoritative judge가 아니다.

---

# 20. OpenAI Agents SDK로 별도 Agent 만들기

AIRA 자체 CLI와 별개로 OpenAI 공식 Agents SDK를 직접 사용할 수도 있다.

공식 설치:

```bash
pip install openai-agents
```

API key:

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

OpenAI 공식 Agents SDK에서 Agent는 기본적으로:

```text
LLM
+ instructions
+ tools
+ optional handoffs
+ guardrails
+ structured outputs
```

로 구성된다.

---

# 21. 가장 간단한 OpenAI Agent 예제

파일:

```text
example_openai_agent.py
```

내용:

```python
from agents import Agent, Runner

agent = Agent(
    name="Research Assistant",
    instructions=(
        "Answer clearly and distinguish verified facts from inference."
    ),
)

result = Runner.run_sync(
    agent,
    "Explain the difference between an LLM and an AI agent.",
)

print(result.final_output)
```

실행:

```bash
python example_openai_agent.py
```

OpenAI 공식 Agents SDK는 OpenAI 모델에서 기본적으로 Responses API 기반 모델 경로를 사용한다.

---

# 22. Tool을 가진 OpenAI Agent

예:

```python
from agents import Agent, Runner, function_tool


@function_tool
def get_project_name() -> str:
    return "Agentic AI Lab / AIRA"


agent = Agent(
    name="Project Assistant",
    instructions=(
        "Help with the AIRA project. "
        "Use tools when factual project information is needed."
    ),
    tools=[get_project_name],
)

result = Runner.run_sync(
    agent,
    "What project am I working on?",
)

print(result.final_output)
```

핵심 개념:

```text
LLM alone
→ text generation

Agent
→ instructions + LLM + tool loop + state/orchestration
```

---

# 23. OpenAI Multi-Agent의 기본 개념

OpenAI Agents SDK는 여러 Agent 사이에:

```text
handoffs
agents-as-tools
```

패턴을 지원한다.

간단한 예:

```python
from agents import Agent, Runner

research_agent = Agent(
    name="Researcher",
    instructions="Research the question carefully.",
)

review_agent = Agent(
    name="Reviewer",
    instructions="Review research outputs for gaps.",
)

manager = Agent(
    name="Manager",
    instructions="Delegate when appropriate.",
    tools=[
        research_agent.as_tool(
            tool_name="research",
            tool_description="Research a topic",
        ),
        review_agent.as_tool(
            tool_name="review",
            tool_description="Review an answer",
        ),
    ],
)

result = Runner.run_sync(
    manager,
    "Explain agentic AI and review the answer.",
)

print(result.final_output)
```

주의:

AIRA production architecture를 이 예제처럼 그대로 교체하라는 뜻이 아니다.

이 코드는 OpenAI Agents SDK의 기본 개념 학습 예시다.

---

# 24. OpenAI Agent 실행 방식

공식 Agents SDK `Runner`에는 대표적으로 다음 방식이 있다.

```text
Runner.run()
→ async

Runner.run_sync()
→ sync

Runner.run_streamed()
→ streaming
```

간단한 실험은 `run_sync()`가 가장 편하다.

서비스/비동기 앱에서는 `run()`을 사용할 수 있다.

---

# 25. Responses API와 Agents SDK 차이

현재 OpenAI 공식 기준의 개념적 구분:

## Responses API 직접 사용

적합한 경우:

- 모델 호출 loop를 직접 관리
- tool dispatch를 직접 제어
- 짧고 단순한 model call
- low-level orchestration을 직접 구현

## Agents SDK 사용

적합한 경우:

- Agent loop를 SDK가 관리
- tools
- handoffs
- guardrails
- sessions
- tracing
- multi-agent orchestration

AIRA처럼 자체 orchestration/runtime을 가진 시스템에서는 모든 것을 Agents SDK로 대체할 필요가 없다.

---

# 26. AIRA와 OpenAI Agents SDK의 관계

AIRA는 자체 research architecture를 이미 갖고 있다.

따라서 다음 두 가지를 구분한다.

```text
AIRA runtime
→ 현재 프로젝트의 production / experiment architecture

OpenAI Agents SDK
→ 별도 Agent prototype 또는 OpenAI-native orchestration 도구
```

현재 AIRA에서 중요한 원칙:

```text
기존 AIRA deterministic control을 불필요하게 버리지 않는다.
```

OpenAI Agents SDK는 필요할 때 다음 용도로 활용 가능하다.

- 새로운 Agent pattern 학습
- tool-calling prototype
- handoff 실험
- manager/sub-agent 실험
- tracing 학습
- AIRA와 외부 Agent framework 비교

---

# 27. Local LLM을 OpenAI Agents SDK에 바로 넣을 수 있는가?

개념적으로 non-OpenAI provider 연결은 가능하지만, 현재 AIRA production Local integration은 이미 자체 `OllamaClient`와 role-specific evaluator를 사용한다.

따라서 현재 프로젝트에서는:

```text
Ollama Local LLM
→ AIRA의 기존 Local worker path 사용

OpenAI LLM
→ AIRA OpenAI/high-judgment path 또는 OpenAI Agents SDK 실험
```

을 우선한다.

Ollama를 Agents SDK에 억지로 연결하는 작업은 현재 production requirement가 아니다.

---

# 28. AIRA Local benchmark 직접 실행

현재 4B worker가 정상인지 다시 확인하려면 기존 benchmark를 사용할 수 있다.

## Semantic Citation

```bash
python scripts/run_local_llm_semantic_citation_benchmark.py \
  --model qwen3.5:4b \
  --num-predict 256
```

## Claim Relevance

현재 production-aligned budget:

```bash
python scripts/run_local_llm_claim_relevance_benchmark.py \
  --model qwen3.5:4b \
  --num-predict 512
```

## Answer Coverage

```bash
python scripts/run_local_llm_answer_coverage_benchmark.py \
  --model qwen3.5:4b \
  --num-predict 384
```

이 benchmark들은:

```text
think=false
temperature=0.0
seed=42
```

기반의 bounded evaluation이다.

---

# 29. 현재 Qwen3.5-4B 품질 기준선

Phase 12 재검증:

```text
Semantic Citation
DEV     17/20 = 0.850
HOLDOUT 17/20 = 0.850

Claim Relevance
DEV     16/18 = 0.889
HOLDOUT 18/18 = 1.000

Answer Coverage
DEV     18/18 = 1.000
HOLDOUT 19/20 = 0.950
```

이 값은 현재 machine/runtime에서의 회귀 기준선으로 사용할 수 있다.

---

# 30. GPU/메모리 상태 점검

실시간:

```bash
watch -n 1 nvidia-smi
```

또는 한 번:

```bash
nvidia-smi
```

Qwen3.5-4B 현재 실측:

```text
100% GPU
VRAM peak approximately 4755 MiB
minimum free VRAM approximately 3117 MiB
GPU max temperature 74 C
```

시스템 RAM:

```bash
free -h
```

Phase 12C:

```text
minimum available RAM approximately 23975 MiB
```

현재 4B worker workload에서는 hardware pressure가 크지 않다.

---

# 31. 빠른 상태 점검 명령

```bash
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate

echo "=== GIT ==="
git status --short

echo "=== OLLAMA ==="
ollama --version
ollama list
ollama ps

echo "=== GPU ==="
nvidia-smi

echo "=== RAM ==="
free -h

echo "=== AIRA PROVIDER ==="
echo "${AIRA_RESEARCH_WORKER_PROVIDER:-<default=openai>}"
echo "${AIRA_LOCAL_WORKER_MODEL:-<default=qwen3.5:4b>}"
```

---

# 32. Local 실행 Quick Start

가장 짧은 절차:

```bash
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate

export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b
unset AIRA_SOURCE_READ_CONCURRENCY

aira research-live \
  --question "Your question here" \
  --objective "Produce an evidence-grounded answer." \
  --maximum-sources 2 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/manual-run
```

---

# 33. OpenAI 실행 Quick Start

```bash
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate

export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export AIRA_RESEARCH_WORKER_PROVIDER=openai
unset AIRA_SOURCE_READ_CONCURRENCY

aira research-live \
  --question "Your question here" \
  --objective "Produce an evidence-grounded answer." \
  --maximum-sources 2 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/manual-openai-run
```

---

# 34. 어떤 방식을 선택해야 하는가?

## 일반 AIRA Research

권장:

```text
Single-Agent default
+ Hybrid architecture
```

## Local 기능 개발/반복 테스트

권장:

```text
qwen3.5:4b
```

## 높은 판단 품질이 중요한 작업

권장:

```text
OpenAI / stronger-model escalation
```

## 역할 분리가 명확한 복잡한 workload

조건부:

```text
Multi-Agent escalation
```

## 9B/8B 큰 Local 모델

현재:

```text
기본 production worker로 사용하지 않음
```

---

# 35. 자주 발생할 수 있는 문제

## 문제 1 — Ollama가 실행되지 않음

확인:

```bash
systemctl status ollama
```

필요 시:

```bash
sudo systemctl restart ollama
```

다시:

```bash
ollama ps
```

---

## 문제 2 — Local 모델이 CPU로 많이 offload됨

```bash
ollama ps
```

확인.

예:

```text
13%/87% CPU/GPU
22%/78% CPU/GPU
```

이는 현재 8GB VRAM에 모델이 완전히 들어가지 않는다는 뜻일 수 있다.

현재 권장 해결:

```text
qwen3.5:4b 사용
```

GPU 구매를 즉시 결정하지 않는다.

---

## 문제 3 — Qwen이 너무 오래 생각함

직접 CLI 실행에서는 thinking이 켜질 수 있다.

AIRA bounded worker는 `think=false`를 사용한다.

직접 테스트도:

```bash
ollama run qwen3.5:4b --think=false "Your prompt"
```

를 우선한다.

---

## 문제 4 — OpenAI 인증 오류

확인:

```bash
test -n "$OPENAI_API_KEY" && echo "key exists"
```

키를 직접 출력하지 않는다.

현재 shell에 없다면:

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

---

## 문제 5 — Local인지 OpenAI인지 헷갈림

```bash
echo "$AIRA_RESEARCH_WORKER_PROVIDER"
```

Local:

```text
local
```

OpenAI:

```text
openai
```

Local 실행 여부:

```bash
ollama ps
```

---

# 36. 현재 Hardware 결론

현재 시스템:

```text
Intel Core i5-9600KF
~31 GiB RAM
RTX 3060 Ti 8 GiB
```

Phase 12 결론:

```text
KEEP CURRENT HARDWARE
DEFER GPU UPGRADE
NO CURRENT EVIDENCE FOR CPU/RAM/PLATFORM UPGRADE
KEEP QWEN3.5-4B
KEEP HYBRID ARCHITECTURE
```

다음 경우에만 hardware를 다시 평가한다.

- 4B보다 명확하게 좋은 Local model이 VRAM 때문에 제한됨
- 실제 concurrent Local worker가 필요해짐
- production context/KV cache pressure가 재현됨
- OpenAI 사용비용 때문에 Local 확대가 경제적으로 중요해짐
- profiler가 실제 hardware bottleneck을 확인함

---

# 37. 권장 일상 운영 Workflow

## Local 개발

```text
1. repo 이동
2. .venv 활성화
3. Ollama 상태 확인
4. provider=local
5. qwen3.5:4b
6. research-live 실행
7. result/report 확인
8. 필요 시 benchmark
```

## OpenAI 검증

```text
1. OPENAI_API_KEY 설정
2. provider=openai
3. 같은 fixture 실행
4. Local 결과와 비교
```

## Architecture 결정

```text
작은 반복 semantic worker
→ Local 4B

high-judgment
→ OpenAI/stronger model

simple deterministic task
→ code/deterministic logic

complex workload with real role-separation benefit
→ Multi-Agent escalation
```

---

# 38. 핵심 명령 Cheat Sheet

```bash
# Project
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate

# Installed local models
ollama list

# Running model
ollama ps

# Model information
ollama show qwen3.5:4b

# Direct local chat
ollama run qwen3.5:4b

# Direct bounded-style local prompt
ollama run qwen3.5:4b --think=false "Reply briefly."

# Stop model
ollama stop qwen3.5:4b

# Local AIRA
export AIRA_RESEARCH_WORKER_PROVIDER=local
export AIRA_LOCAL_WORKER_MODEL=qwen3.5:4b

# OpenAI AIRA
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
export AIRA_RESEARCH_WORKER_PROVIDER=openai

# Production source-read default
unset AIRA_SOURCE_READ_CONCURRENCY

# Integrated Web + Local research (non-sensitive approved file)
aira research-integrated \
  --question "Your question" \
  --objective "Evidence-grounded Web and Local answer" \
  --source "$PWD/non-sensitive-notes.md" \
  --allowed-root "$PWD" \
  --approve-external-send \
  --maximum-sources 4 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/integrated-run

# Live research
aira research-live \
  --question "Your question" \
  --objective "Evidence-grounded answer" \
  --maximum-sources 2 \
  --maximum-bytes 1000000 \
  --output-dir /mnt/ai-data/experiments/manual-run

# Hardware monitoring
nvidia-smi
free -h
```

---

# 39. 최종 권장사항

현재 AIRA에서 Local LLM을 사용할 때 가장 중요한 결론은 다음과 같다.

```text
Do not choose a model because it is larger.

Choose the smallest model that has passed the role-specific evaluation.
```

현재 그 모델은:

```text
qwen3.5:4b
```

이다.

현재 권장 전체 구조:

```text
AIRA
│
├─ Single-Agent default
│
├─ Deterministic control/planning
│
├─ OpenAI / stronger model
│    └─ high-judgment escalation
│
├─ Local qwen3.5:4b
│    ├─ semantic citation
│    ├─ claim relevance
│    └─ answer coverage reviewer
│
└─ Multi-Agent
     └─ workload-dependent escalation
```

이 구조가 현재 Phase 12까지의 실제 benchmark와 hardware 실측 결과에 가장 잘 맞는다.

---

# 40. 근거 및 참고

## AIRA 프로젝트 실측/문서

이 매뉴얼은 다음 프로젝트 사실을 기준으로 작성했다.

- Phase 5 Local LLM role-specific benchmark
- Phase 6 Local worker integration
- Phase 7 OpenAI vs Local bounded-worker comparison
- Phase 8 Local Multi-Agent minimum
- Phase 9 Single vs Multi-Agent evaluation
- Phase 10 Hybrid role routing
- Phase 11 bounded parallel source reading
- Phase 12 hardware/model capacity and quality evaluation
- `ROADMAP.md`
- `DECISIONS.md`
- `RUNTIME_ARCHITECTURE.md`
- `AIRA_CURRENT_SYSTEM_GUIDE.md`
- `AIRA_CAPABILITY_MATRIX.md`
- `local-llm/BENCHMARK_RESULTS.md`
- `local-llm/ROADMAP.md`
- `local-llm/HARDWARE_UPGRADE_DECISION.md`

## OpenAI 공식 문서 확인 사항 — 2026-08-13

OpenAI 공식 문서에서 다음을 확인하여 일반 OpenAI/Agent 사용법에 반영했다.

- OpenAI API SDK는 `OPENAI_API_KEY` 환경변수를 사용할 수 있음
- OpenAI Agents SDK 설치: `pip install openai-agents`
- Agent는 instructions/tools/handoffs/guardrails 등의 구성을 가질 수 있음
- `Runner.run()`, `Runner.run_sync()`, `Runner.run_streamed()` 지원
- OpenAI Agents SDK의 OpenAI 모델 기본 권장 경로는 Responses API
- Agents SDK는 tools, handoffs, guardrails, sessions, tracing을 포함하는 Agent orchestration에 적합
- Responses API 직접 사용과 Agents SDK를 한 프로젝트에서 목적에 따라 함께 사용할 수 있음

---

# 41. 2026-08-18 Patent Technical Research CLI

2026-08-18 현재 Stage 5 Patent Research Vertical Slice의 first usable CLI slice는
Step 3G User Acceptance Test까지 `FINAL PASS`다.

## 41.1 도움말

```bash
cd /home/moon/Project/agentic-ai-lab
source .venv/bin/activate
aira research-patent --help
```

## 41.2 기본 실행 형태

```bash
aira research-patent   --question "How do patent publications describe seat occupancy detection using pressure sensors?"   --objective "Identify technically relevant patent publications and evidence."
```

필요하면 다음 bounded option을 사용한다.

```text
--prior-art-cutoff-date YYYY-MM-DD
--maximum-search-results N
--maximum-sources N
--maximum-bytes N
```

`prior_art_cutoff_date`는 retrieval bound이며 법률상 prior-art 판정을 의미하지 않는다.

## 41.3 출력 의미

Finding이 존재할 때:

```text
result_status=findings_available
synthesis_accepted=true|false
```

Finding이 없을 때:

```text
result_status=no_relevant_findings
synthesis_accepted=not_applicable
verification_status=not_applicable
```

출력은 다음 의미 층을 구분한다.

```text
VERIFIED source identity
≠ TECHNICALLY RELEVANT evidence
≠ FULLY SUPPORTED synthesis
≠ LEGAL CONCLUSION
```

현재 CLI는 novelty, invalidity, obviousness, infringement, FTO, patentability 또는
current legal status를 definitive legal conclusion으로 판정하지 않는다.

## 41.4 Credential

EPO credential 값은 출력하거나 Git에 commit하지 않는다.
Production loader는 project `.env`를 읽을 수 있으나 문서에는 실제 key/secret 값을 기록하지 않는다.

## 41.5 현재 다음 제품 작업

```text
Stage 5 — Internet Research Expansion
Patent Research Vertical Slice
Step 4A — Patent Metadata Expansion
```

**문서 끝**
