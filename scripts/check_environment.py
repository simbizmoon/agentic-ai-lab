"""Check the local Python environment for Phase 2 practice."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warning(message: str) -> None:
    print(f"[WARNING] {message}")


def error(message: str) -> None:
    print(f"[ERROR] {message}")


def is_virtual_environment() -> bool:
    return sys.prefix != sys.base_prefix


def main() -> int:
    errors = 0

    # Intentionally verify the active interpreter for the environment check.
    if sys.version_info >= (3, 12):  # noqa: UP036
        ok(f"Python version is {sys.version_info.major}.{sys.version_info.minor}")
    else:
        error("Python version must be 3.12 or newer")
        errors += 1

    if is_virtual_environment():
        ok("Python is running inside a virtual environment")
    else:
        error("Python is not running inside a virtual environment")
        errors += 1

    for file_name in ("pyproject.toml", ".env.example", ".gitignore"):
        file_path = PROJECT_ROOT / file_name
        if file_path.is_file():
            ok(f"{file_name} exists")
        else:
            error(f"{file_name} is missing")
            errors += 1

    try:
        from app.config import load_settings

        settings = load_settings()
    except ModuleNotFoundError as exc:
        error(f"Settings validation failed: missing dependency {exc.name}")
        errors += 1
    except RuntimeError as exc:
        error(f"Settings validation failed: {exc}")
        errors += 1
    else:
        ok("Settings loaded successfully")
        ok("OPENAI_API_KEY is configured")
        ok(f"OPENAI_MODEL={settings.openai_model}")
        ok(f"OPENAI_TIMEOUT_SECONDS={settings.openai_timeout_seconds}")
        ok(f"OPENAI_MAX_RETRIES={settings.openai_max_retries}")
        ok(f"APP_ENV={settings.app_env}")
        ok(f"LOG_LEVEL={settings.log_level}")
        ok(f"MAX_AGENT_STEPS={settings.max_agent_steps}")

    if errors:
        error(f"Environment check failed with {errors} error(s)")
        return 1

    ok("Environment check completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
