"""Tests for heterogeneous research role routing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.research.hybrid_role_policy import (
    HybridResearchRole,
    HybridResearchRolePolicy,
    ResearchExecutionProvider,
)


def test_phase10_default_assigns_expected_providers() -> None:
    policy = HybridResearchRolePolicy.phase10_default()

    assert policy.provider_for(
        HybridResearchRole.TASK_DECOMPOSITION
    ) is ResearchExecutionProvider.DETERMINISTIC
    assert policy.provider_for(
        HybridResearchRole.EVIDENCE_RELEVANCE
    ) is ResearchExecutionProvider.OPENAI
    assert policy.provider_for(
        HybridResearchRole.CLAIM_GENERATION
    ) is ResearchExecutionProvider.OPENAI
    assert policy.provider_for(
        HybridResearchRole.SEMANTIC_CITATION
    ) is ResearchExecutionProvider.LOCAL
    assert policy.provider_for(
        HybridResearchRole.CLAIM_RELEVANCE
    ) is ResearchExecutionProvider.LOCAL
    assert policy.provider_for(
        HybridResearchRole.ANSWER_COVERAGE
    ) is ResearchExecutionProvider.LOCAL
    assert policy.provider_for(
        HybridResearchRole.SYNTHESIS
    ) is ResearchExecutionProvider.DETERMINISTIC
    assert policy.provider_for(
        HybridResearchRole.FINAL_QUALITY_REVIEW
    ) is ResearchExecutionProvider.OPENAI


def test_phase10_default_covers_every_role() -> None:
    policy = HybridResearchRolePolicy.phase10_default()

    assert set(policy.as_role_map()) == set(HybridResearchRole)


def test_roles_for_returns_local_bounded_workers() -> None:
    policy = HybridResearchRolePolicy.phase10_default()

    assert policy.roles_for(
        ResearchExecutionProvider.LOCAL
    ) == (
        HybridResearchRole.SEMANTIC_CITATION,
        HybridResearchRole.CLAIM_RELEVANCE,
        HybridResearchRole.ANSWER_COVERAGE,
    )


def test_local_final_quality_review_is_rejected() -> None:
    values = HybridResearchRolePolicy.phase10_default().model_dump()
    values["final_quality_review"] = ResearchExecutionProvider.LOCAL

    with pytest.raises(
        ValidationError,
        match="final_quality_review must not use local provider",
    ):
        HybridResearchRolePolicy.model_validate(values)
