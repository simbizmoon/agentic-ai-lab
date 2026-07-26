"""Configuration loading for the Agentic AI Lab project."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

ALLOWED_APP_ENVS = {"development", "test", "staging", "production"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings loaded from environment variables."""

    openai_api_key: str = field(repr=False)
    openai_model: str
    openai_timeout_seconds: float
    openai_max_retries: int
    app_env: str
    log_level: str
    max_agent_steps: int


def load_settings() -> Settings:
    """Load, validate, and return application settings."""

    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "").strip()
    openai_timeout_seconds_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "30").strip()
    openai_max_retries_raw = os.getenv("OPENAI_MAX_RETRIES", "2").strip()
    app_env = os.getenv("APP_ENV", "development").strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    max_agent_steps_raw = os.getenv("MAX_AGENT_STEPS", "10").strip()

    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    if not openai_model:
        raise RuntimeError("OPENAI_MODEL is required")

    try:
        openai_timeout_seconds = float(openai_timeout_seconds_raw)
    except ValueError as exc:
        raise RuntimeError("OPENAI_TIMEOUT_SECONDS must be a number") from exc

    if not 1 <= openai_timeout_seconds <= 300:
        raise RuntimeError("OPENAI_TIMEOUT_SECONDS must be between 1 and 300")

    try:
        openai_max_retries = int(openai_max_retries_raw)
    except ValueError as exc:
        raise RuntimeError("OPENAI_MAX_RETRIES must be an integer") from exc

    if not 0 <= openai_max_retries <= 5:
        raise RuntimeError("OPENAI_MAX_RETRIES must be between 0 and 5")

    if app_env not in ALLOWED_APP_ENVS:
        raise RuntimeError(
            "APP_ENV must be one of: development, test, staging, production"
        )

    if log_level not in ALLOWED_LOG_LEVELS:
        raise RuntimeError(
            "LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        )

    try:
        max_agent_steps = int(max_agent_steps_raw)
    except ValueError as exc:
        raise RuntimeError("MAX_AGENT_STEPS must be an integer") from exc

    if not 1 <= max_agent_steps <= 100:
        raise RuntimeError("MAX_AGENT_STEPS must be between 1 and 100")

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_timeout_seconds=openai_timeout_seconds,
        openai_max_retries=openai_max_retries,
        app_env=app_env,
        log_level=log_level,
        max_agent_steps=max_agent_steps,
    )
