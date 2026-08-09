# AIRA Local LLM Hardware Baseline

- 기준일: 2026-08-09
- Host: `moon-B360-AORUS-GAMING-3`
- OS: Ubuntu
- 목적: AIRA Local LLM / Multi-Agent 실험을 시작하기 전 실제 하드웨어 및 저장장치 baseline을 기록한다.
- 원칙: 실제 명령 출력과 SMART 결과만 기록하며, 확인되지 않은 사양을 추측하지 않는다.

---

# 1. CPU

실제 확인 명령:

```bash
lscpu | grep -E 'Model name|Socket|Core|Thread'
```

확인 결과:

```text
Intel(R) Core(TM) i5-9600KF CPU @ 3.70GHz
```

## Local AI 관점 평가

- GPU 중심 inference의 orchestration CPU로 사용 가능
- Python, FastAPI, tool execution, parsing, state 관리에 사용 가능
- 대형 모델 CPU-only inference의 주력으로는 적합하지 않음
- GPU VRAM 부족으로 CPU/RAM offload가 증가할 경우 CPU가 추가 병목이 될 수 있음
- 현재 업그레이드 우선순위는 GPU/VRAM보다 낮음

---

# 2. GPU

실제 확인 명령:

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

확인 결과:

```text
NVIDIA GeForce RTX 3060 Ti
VRAM: 8192 MiB
Driver: 560.35.05
```

PCI 확인:

```text
01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti]
01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller
```

## Local AI 관점 평가

현재 시스템에서 가장 큰 Local LLM 제약은 **8GB VRAM**이다.

초기 실험 방향:

```text
≤ 4B      매우 적합한 후보군
7B~8B     주력 후보군
14B       quantization + CPU/RAM offload 비교 실험
20B+      현재 GPU 주력 운용에는 부적합할 가능성이 높음
30B+      실험적/비현실적 가능성 높음
70B       현재 장비의 주력 Local GPU inference 대상이 아님
```

위 범위는 최종 성능 판정이 아니다. 모델 구조, quantization, context 및 runtime에 따라 실제 측정한다.

---

# 3. System RAM

실제 확인 결과:

```text
Total: 31 GiB
Used at measurement: 약 5.0 GiB
Available at measurement: 약 26 GiB
Swap: 2.0 GiB
```

## Local AI 관점 평가

- 4B~8B GPU inference + AIRA runtime에 충분한 시작점
- 14B급 일부 CPU/RAM offload 실험 가능
- 여러 대형 모델을 RAM에 동시에 유지하는 용도에는 제한적
- 향후 필요 시 64GB 업그레이드를 검토할 수 있으나, 현재 우선순위는 GPU/VRAM보다 낮음

---

# 4. Storage Inventory

실제 `lsblk` 및 `df` 결과에 기반한 저장장치 구성.

## 4.1 Ubuntu System SSD

```text
Device: /dev/sda
Model: Samsung SSD 860 EVO 500GB
Usable size: 약 465.8 GiB
Root partition: /dev/sda5
Filesystem: ext4
Mount: /
```

측정 당시:

```text
Filesystem size: 약 457G
Used: 약 238G
Available: 약 197G
Usage: 55%
```

### 역할

- Ubuntu
- `/home/moon/Project/agentic-ai-lab`
- Python virtual environment
- Docker 및 개발 도구
- latency-sensitive active model 또는 hot data 필요 시 사용

### 정책

대형 model archive와 dataset까지 root SSD에 누적하지 않는다.

---

## 4.2 Windows Dual-Boot NVMe

```text
Device: /dev/nvme0n1
Model: Samsung SSD 970 EVO 500GB
Usable size: 약 465.8 GiB
```

파티션은 NTFS이며 Windows dual boot 용도로 사용한다.

### 정책

Local AI storage로 사용하지 않는다.

---

## 4.3 AI Data HDD

기존 Ethereum node 용도로 사용했던 2TB HDD를 Local AI data 전용으로 전환하였다.

```text
Device: /dev/sdb
Partition: /dev/sdb1
Model Family: Seagate Samsung SpinPoint M9TU (USB)
Device Model: ST2000LM005 HN-M201AAD
Serial: H4223H462A4E3I
Capacity: 2,000,398,934,016 bytes [2.00 TB]
Rotation: 5400 rpm
Form Factor: 2.5 inches
SATA: 3.0, 6.0 Gb/s
```

### 전환 전 상태

```text
Filesystem: ext4
Label: ethereum-data
Mount: /mnt/ethereum-data
Used: 약 1.4TB
```

확인된 주요 데이터:

```text
/mnt/ethereum-data/geth   약 1.3TB
/mnt/ethereum-data/prysm  약 55GB
```

`geth/keystore`에는 파일이 없었고, Prysm에서는 `network-keys`가 확인되었다. Ethereum 운영은 이미 포기한 상태였으며 해당 node sync data를 제거하고 디스크를 AI용으로 재구성하였다.

### SMART 결과

실제 명령:

```bash
sudo smartctl -a -d sat /dev/sdb
```

핵심 결과:

```text
SMART overall-health self-assessment test result: PASSED
Reallocated_Sector_Ct: 0
Current_Pending_Sector: 0
Offline_Uncorrectable: 0
UDMA_CRC_Error_Count: 0
Power_On_Hours: 452
Temperature: 33 C
SMART Error Log: No Errors Logged
```

따라서 AI 대용량 저장용 HDD로 재사용 가능한 baseline으로 판단하였다.

### 전환 후 현재 상태

```text
Partition: /dev/sdb1
Filesystem: ext4
Label: ai-data
UUID: 364aac4d-3aba-45c5-b96c-40bb451ee9bd
Mount: /mnt/ai-data
```

`/etc/fstab`:

```text
UUID=364aac4d-3aba-45c5-b96c-40bb451ee9bd /mnt/ai-data ext4 defaults,nofail,relatime 0 2
```

마운트 및 사용자 write test 성공.

초기 가용공간:

```text
Filesystem size: 약 1.8T
Available: 약 1.7T
Usage: 약 1%
```

현재 디렉터리:

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

### 역할

- model archive
- GGUF / 여러 quantization
- inactive Ollama/Hugging Face models
- datasets
- RAG corpus
- crawl archive
- experiment outputs
- generated artifacts

### 제약

5400rpm HDD이므로 다음 용도에는 우선 사용하지 않는다.

- latency-sensitive active model load가 빈번한 경우
- active vector DB hot path
- high-I/O database

---

## 4.4 Other Existing Drives

### `/dev/sdc`

```text
Model: ST1000LM025 HN-M101ABB
Size: 약 931.5G
Filesystem: NTFS
Label: 외장(백업_2019_03)
Mount: /media/moon/외장(백업_2019_03)1
```

기존 백업용으로 유지한다.

### `/dev/sdd`

```text
Model: WDC WD20NMVW-11AV3S2
Size: 약 1.8T
Filesystem: NTFS
Label: 외장(학교)
Mount: /mnt/sdc1
```

기존 데이터 용도로 유지한다.

---

# 5. Storage Operating Policy

## Hot Storage

주로 Ubuntu SSD를 사용한다.

```text
active source
Python environment
Docker
current local model when load speed matters
active embedding/vector data when needed
```

## Warm / Cold Storage

`/mnt/ai-data`를 사용한다.

```text
model archives
multiple quantizations
datasets
RAG source corpus
web crawls
experiment artifacts
old outputs
```

Repository 소스코드는 `/mnt/ai-data`에 두지 않는다.

---

# 6. Current Hardware Bottleneck Priority

초기 예상 우선순위:

```text
1. GPU VRAM (8GB)
2. System RAM (32GB)
3. CPU/platform
4. Storage
```

단, 이 순위는 구매 결정이 아니라 현재 구조상의 예상이다. 실제 Local LLM benchmark 후 재평가한다.

---

# 7. Hardware Upgrade Policy

하드웨어를 먼저 구매하지 않는다.

다음이 실제 측정으로 확인될 때 업그레이드를 검토한다.

```text
VRAM OOM 빈도
필요 context 증가
CPU offload latency
14B/20B/30B 모델의 실제 품질 이점
parallel agent requirement
AIRA production workload
OpenAI 대비 Local 품질 격차
```

GPU 업그레이드를 검토할 경우 8GB → 12GB처럼 작은 증가보다, 실제 workload가 요구한다면 16GB/24GB 이상처럼 의미 있는 VRAM 단계 상승을 우선 평가한다.

---

# 8. Baseline Verification Commands

향후 환경 변화를 확인할 때 사용한다.

```bash
echo "=== CPU ==="
lscpu | grep -E 'Model name|Socket|Core|Thread'

echo
echo "=== GPU ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

echo
echo "=== RAM ==="
free -h

echo
echo "=== STORAGE ==="
lsblk -o NAME,MODEL,SERIAL,SIZE,FSTYPE,LABEL,MOUNTPOINTS

echo
echo "=== FILESYSTEM USAGE ==="
df -h

echo
echo "=== AI DATA ==="
findmnt /mnt/ai-data
df -h /mnt/ai-data
```

---

# 9. Baseline Status

2026-08-09 기준:

```text
[x] CPU 확인
[x] GPU 및 VRAM 확인
[x] RAM 확인
[x] Storage inventory 확인
[x] Windows NVMe 용도 확인
[x] Ethereum HDD 데이터 확인
[x] HDD SMART 확인
[x] Ethereum data 삭제
[x] AI용 ext4 filesystem 생성
[x] /mnt/ai-data 구성
[x] fstab 자동 mount 등록
[x] write test 성공
```

이 문서는 Local LLM benchmark 시작 전 Hardware Baseline으로 고정한다.
