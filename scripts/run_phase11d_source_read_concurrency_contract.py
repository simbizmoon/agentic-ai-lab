"""Print the Phase 11D source-read concurrency contract."""

from __future__ import annotations

import json

from app.research.live_runtime import (
    DEFAULT_SOURCE_READ_CONCURRENCY,
    MAX_SOURCE_READ_CONCURRENCY,
    MIN_SOURCE_READ_CONCURRENCY,
    SOURCE_READ_CONCURRENCY_ENV,
    resolve_source_read_concurrency,
)


def main() -> int:
    payload = {
        "phase": "11D",
        "environment_variable": SOURCE_READ_CONCURRENCY_ENV,
        "resolved_value": resolve_source_read_concurrency(),
        "default": DEFAULT_SOURCE_READ_CONCURRENCY,
        "minimum": MIN_SOURCE_READ_CONCURRENCY,
        "maximum": MAX_SOURCE_READ_CONCURRENCY,
        "production_default": 2,
        "safe_fallback": 1,
        "benchmark_aggressive_option": 4,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
