"""Tests for Phase 10B hybrid bounded-worker composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.research.hybrid_role_policy import (
    HybridResearchRole,
    HybridResearchRolePolicy,
    ResearchExecutionProvider,
)
from app.research.hybrid_runtime import (
    build_hybrid_bounded_research_workers,
    legacy_compatible_role_policy,
)
from app.research.local_worker_runtime import LocalWorkerSettings


def settings(provider: str) -> LocalWorkerSettings:
    return LocalWorkerSettings(
        provider=provider,
        model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=120.0,
    )


def test_legacy_openai_switch_maps_all_bounded_roles_to_openai() -> None:
    policy = legacy_compatible_role_policy(
        local_worker_settings=settings("openai")
    )

    for role in (
        HybridResearchRole.SEMANTIC_CITATION,
        HybridResearchRole.CLAIM_RELEVANCE,
        HybridResearchRole.ANSWER_COVERAGE,
    ):
        assert (
            policy.provider_for(role)
            is ResearchExecutionProvider.OPENAI
        )

    assert (
        policy.provider_for(HybridResearchRole.CLAIM_GENERATION)
        is ResearchExecutionProvider.OPENAI
    )
    assert (
        policy.provider_for(HybridResearchRole.EVIDENCE_RELEVANCE)
        is ResearchExecutionProvider.OPENAI
    )


def test_legacy_local_switch_maps_only_bounded_roles_to_local() -> None:
    policy = legacy_compatible_role_policy(
        local_worker_settings=settings("local")
    )

    assert policy.roles_for(ResearchExecutionProvider.LOCAL) == (
        HybridResearchRole.SEMANTIC_CITATION,
        HybridResearchRole.CLAIM_RELEVANCE,
        HybridResearchRole.ANSWER_COVERAGE,
    )

    assert (
        policy.provider_for(HybridResearchRole.CLAIM_GENERATION)
        is ResearchExecutionProvider.OPENAI
    )
    assert (
        policy.provider_for(HybridResearchRole.EVIDENCE_RELEVANCE)
        is ResearchExecutionProvider.OPENAI
    )


def test_phase10_default_requires_local_worker_switch() -> None:
    with pytest.raises(
        ValueError,
        match="requires local bounded workers",
    ):
        build_hybrid_bounded_research_workers(
            role_policy=HybridResearchRolePolicy.phase10_default(),
            local_worker_settings=settings("openai"),
            openai_client=SimpleNamespace(),  # type: ignore[arg-type]
            openai_model="gpt-5",
        )
