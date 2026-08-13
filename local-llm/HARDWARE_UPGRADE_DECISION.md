# AIRA Hardware Upgrade Decision

Date: 2026-08-13  
Status: **FINAL — KEEP CURRENT HARDWARE; DEFER UPGRADE**

## 1. Decision

AIRA will keep the current development hardware:

```text
CPU  Intel Core i5-9600KF
RAM  ~31 GiB
GPU  NVIDIA GeForce RTX 3060 Ti 8 GiB
```

No GPU, RAM, CPU, motherboard/platform, or full-PC upgrade is justified by the current
AIRA workload evidence.

The current Local architecture remains:

```text
Qwen3.5-4B
→ bounded local worker
→ 100% GPU execution

OpenAI / stronger model
→ high-judgment escalation where required

Single-Agent
→ default

Multi-Agent
→ workload-dependent escalation
```

## 2. Question evaluated

Phase 12 did not ask whether a larger GPU could run larger models. It asked whether the
current hardware is an actual AIRA bottleneck and whether removing that bottleneck would
produce enough quality, latency, concurrency, or operating-cost benefit to justify an
upgrade.

## 3. Current-worker baseline

`qwen3.5:4b`:

```text
architecture        qwen35
parameters          4.7B
quantization        Q4_K_M
runtime processor   100% GPU
runtime context     4096
```

Phase 12C measured the current bounded-worker workload while running semantic citation,
claim relevance, and answer coverage benchmarks.

```text
GPU samples               2042
GPU utilization max       91.0%
GPU utilization mean      12.575%  (includes idle gaps)
VRAM used max             4755 MiB
VRAM free min             3117 MiB
power max                 199.49 W
temperature max           74 C
RAM available min         23975 MiB
RAM available max         26160 MiB
```

There is substantial RAM headroom and more than 3 GiB minimum observed VRAM headroom for
the accepted 4B worker under this benchmark. The model remains fully GPU-resident.

## 4. Larger-model capacity evidence

### Qwen3.5-9B

```text
parameters          9.7B
quantization        Q4_K_M
runtime placement   13% CPU / 87% GPU
observed GPU usage  ~7.1 GiB total
```

This confirms that 8 GiB VRAM is a real boundary for this 9B-class model: it runs, but it
requires partial CPU offload.

### Ministral 3 8B

```text
parameters          8.9B
quantization        Q4_K_M
runtime placement   22% CPU / 78% GPU
observed GPU usage  ~6.9 GiB total
```

It also requires partial CPU offload on the current configuration.

### Llama 3.1 8B

```text
runtime placement   100% GPU
observed GPU usage  ~6.1 GiB total
```

This was used only as a hardware capacity probe. It was not evaluated as a replacement for
the accepted AIRA bounded worker and is not part of the quality decision.

## 5. Production-role quality comparison

The comparison reused existing AIRA Phase-5 evaluator datasets and contracts. All tested
roles used deterministic worker settings including `think=false`, `temperature=0.0`, and
`seed=42`.

```text
Semantic Citation   num_predict=256
Claim Relevance     num_predict=512
Answer Coverage     num_predict=384
```

### Accuracy

| Role | Qwen3.5-4B DEV | Qwen3.5-4B HOLDOUT | Qwen3.5-9B DEV | Qwen3.5-9B HOLDOUT | Ministral 3 8B DEV | Ministral 3 8B HOLDOUT |
|---|---:|---:|---:|---:|---:|---:|
| Semantic Citation | 0.850 | 0.850 | 0.850 | 0.900 | 0.850 | 0.800 |
| Claim Relevance | 0.889 | 1.000 | 0.722 | 0.944 | 0.889 | 0.944 |
| Answer Coverage | 1.000 | 0.950 | 0.833 | 0.950 | 0.833 | 0.900 |

### Safety-sensitive errors

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

Qwen3.5-9B improved one semantic-citation holdout case, but it did not establish an overall
quality advantage across the accepted roles. Its claim-relevance behavior was more prone
to optimistic `directly_relevant` classifications, and one DEV answer-coverage case was
incorrectly promoted to `fully_covered`.

Ministral 3 8B likewise did not establish an overall quality advantage over Qwen3.5-4B.

## 6. Latency comparison

| Model | Semantic | Claim | Coverage | Total | Relative to 4B |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-4B | 95.27 s | 100.63 s | 106.31 s | 302.21 s | 1.00x |
| Qwen3.5-9B | 162.62 s | 169.80 s | 212.97 s | 545.39 s | 1.80x |
| Ministral 3 8B | 127.10 s | 168.86 s | 205.94 s | 501.90 s | 1.66x |

The larger candidates were materially slower on the current hardware and did not provide a
matching overall quality gain.

## 7. Hardware decision matrix

| Option | Decision | Evidence |
|---|---|---|
| Keep RTX 3060 Ti 8 GiB | **ACCEPT** | current 4B worker fully GPU-resident with headroom |
| Upgrade GPU for more VRAM now | **DEFER** | larger tested models did not provide sufficient role-quality gain |
| Add RAM | **NO CURRENT NEED** | minimum available RAM remained ~23.4 GiB |
| Upgrade CPU | **NO CURRENT EVIDENCE** | accepted 4B worker has no CPU offload requirement |
| Replace CPU/board/RAM platform | **NO** | no workload evidence justifies platform cost |
| Replace whole PC | **NO** | no measured AIRA benefit justifies it |
| Keep Qwen3.5-4B + Hybrid | **ACCEPT** | best measured quality / latency / resource fit |

## 8. Why a larger GPU is not justified yet

A larger-VRAM GPU would reduce or eliminate CPU offload for the 9B-class candidates tested.
That is a real technical benefit. However, the decision is not based on model residency
alone.

The tested larger models did not show the role-specific quality improvement needed to make
faster execution of those models valuable to AIRA. Buying more VRAM now would therefore
solve a capacity limit that is not currently preventing the preferred architecture from
meeting its bounded-worker goals.

## 9. Re-evaluation triggers

Reopen the hardware decision when one or more of the following is demonstrated with actual
AIRA workload evidence:

1. A Local model materially outperforms Qwen3.5-4B on accepted production roles but cannot
   run efficiently because of VRAM limits.
2. Concurrent Local workers or parallel Local agents become a validated production need.
3. Production context/KV-cache requirements create reproducible 8 GiB VRAM pressure.
4. OpenAI/Hybrid operating costs become high enough that expanding Local inference is
   economically preferable.
5. Profiling identifies CPU, GPU, RAM, storage, or interconnect as a meaningful end-to-end
   bottleneck.

A newer or larger model by itself is not a re-evaluation trigger.

## 10. Evidence locations

Phase 12B model comparison artifacts:

```text
/mnt/ai-data/experiments/phase12b3/4b/
/mnt/ai-data/experiments/phase12b3/9b/
/mnt/ai-data/experiments/phase12b3/ministral8b/
```

Phase 12C headroom artifacts:

```text
/mnt/ai-data/experiments/phase12c1/
```

## 11. Final

```text
PHASE 12 — COMPLETE

KEEP CURRENT HARDWARE
DEFER HARDWARE UPGRADE
KEEP QWEN3.5-4B AS BOUNDED LOCAL WORKER
KEEP OPENAI + LOCAL HYBRID ARCHITECTURE
```
