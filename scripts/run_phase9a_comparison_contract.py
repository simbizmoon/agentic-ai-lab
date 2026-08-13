"""Print the Phase 9A runtime-comparison contract."""

from __future__ import annotations

import json

from app.research.research_execution_benchmark import (
    ResearchArchitectureComparison,
    ResearchArchitectureRunMetrics,
)


def main() -> int:
    payload = {
        "phase": "9A",
        "purpose": (
            "Normalize real single- and multi-agent runtime results "
            "without making a final architecture decision."
        ),
        "run_metric_fields": list(
            ResearchArchitectureRunMetrics.model_fields
        ),
        "comparison_fields": list(
            ResearchArchitectureComparison.model_fields
        ),
        "decision_policy": {
            "requires_comparable_upstream_artifacts": True,
            "requires_equal_evaluator_conditions": True,
        },
        "current_known_limitation": (
            "Single local runtime uses deterministic quality evaluation "
            "while Phase-8C Multi uses qwen3.5:4b advisory review."
        ),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
