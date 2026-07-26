"""OpenAI client creation helpers."""

from __future__ import annotations

from openai import OpenAI

from app.config import Settings


def create_openai_client(settings: Settings) -> OpenAI:
    """Create an OpenAI client from validated settings."""

    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
