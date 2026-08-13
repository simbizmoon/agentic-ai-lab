"""Tests for bounded local research-worker runtime composition."""

import pytest

from app.research.local_worker_runtime import (
    LocalWorkerSettings,
    build_local_research_workers,
    load_local_worker_settings,
)


def test_load_local_worker_settings_defaults_to_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "AIRA_RESEARCH_WORKER_PROVIDER",
        "AIRA_LOCAL_WORKER_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_local_worker_settings()

    assert settings.provider == "openai"
    assert settings.enabled is False
    assert settings.model == "qwen3.5:4b"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_timeout_seconds == 120.0


def test_load_local_worker_settings_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRA_RESEARCH_WORKER_PROVIDER", "LOCAL")
    monkeypatch.setenv("AIRA_LOCAL_WORKER_MODEL", " qwen3.5:4b ")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "90")

    settings = load_local_worker_settings()

    assert settings.provider == "local"
    assert settings.enabled is True
    assert settings.model == "qwen3.5:4b"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_timeout_seconds == 90.0


def test_load_local_worker_settings_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIRA_RESEARCH_WORKER_PROVIDER", "other")

    with pytest.raises(RuntimeError, match="must be one of"):
        load_local_worker_settings()


def test_build_local_workers_requires_local_provider() -> None:
    settings = LocalWorkerSettings(
        provider="openai",
        model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=120.0,
    )

    with pytest.raises(ValueError, match="provider='local'"):
        build_local_research_workers(settings=settings)


def test_build_local_workers_returns_production_services() -> None:
    settings = LocalWorkerSettings(
        provider="local",
        model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=120.0,
    )

    workers = build_local_research_workers(settings=settings)

    assert workers.semantic_citation_verifier is not None
    assert workers.claim_relevance_evaluator is not None
    assert workers.answer_coverage_evaluator is not None

def test_local_worker_bundle_preserves_claim_relevance_budget() -> None:
    from app.budget import ExecutionBudget

    settings = LocalWorkerSettings(
        provider="local",
        model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=120.0,
    )
    budget = ExecutionBudget(
        max_attempts=8,
        max_recorded_tokens=8_000,
        max_elapsed_seconds=60.0,
    )

    workers = build_local_research_workers(
        settings=settings,
        claim_relevance_budget=budget,
    )

    assert workers.claim_relevance_evaluator.budget == budget
