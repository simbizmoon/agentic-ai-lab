# Phase 11 Reliability Baseline

## 1. Baseline 목적

이 문서는 Phase 11 완료 시점의 평가, Guardrail 및 Reliability 기능을 기준선으로 고정한다.

Phase 12 이후 Application, Persistence, Background Job 또는 Deployment 기능을 추가할 때 현재 기준선과 비교하여 기능 및 품질 회귀 여부를 판단한다.

---

## 2. Baseline 식별 정보

| 항목 | 값 |
|---|---|
| 프로젝트 | AIRA — Agentic Intelligence Research Assistant |
| Phase | Phase 11 |
| 주제 | Evals, Guardrails, Reliability |
| 기준일 | 2026-08-04 |
| Python | 3.12 |
| Validation | Pydantic strict and frozen schemas |
| Test Runner | `python -m pytest -q` |
| Linter | `ruff check .` |
| Baseline 상태 | PASS |

Git Commit Hash는 Phase 11 문서 Commit 후 아래 명령으로 확인한다.

```bash
git rev-parse HEAD
