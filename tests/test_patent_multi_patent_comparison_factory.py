"""Tests for lazy shared-client patent comparison workflow composition."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.research.patent_multi_patent_comparison_factory import (
    build_openai_epo_patent_multi_patent_comparison_workflow,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.epo_ops_config import EpoOpsConfig
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import PatentClaim
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


@dataclass
class FakeClaimsRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        self.calls.append(record.publication_number)
        return EpoOpsClaimsRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            source_endpoint="https://ops.epo.org/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(
                        EpoOpsClaimText(
                            position=1,
                            text="1. A system comprising a sensor.",
                        ),
                    ),
                ),
            ),
        )


@dataclass
class FakeAbstractRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        self.calls.append(record.publication_number)
        return EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text=f"A sensor from {record.publication_number}.",
            abstract_language="en",
            source_endpoint="https://ops.epo.org/abstract",
        )


@dataclass(frozen=True)
class DecompositionResult:
    decomposition: PatentClaimDecomposition


class FakeDecomposer:
    def decompose(self, claim: PatentClaim) -> DecompositionResult:
        return DecompositionResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=(PatentClaimElement(element_number=1, text=claim.text),),
            )
        )


@dataclass(frozen=True)
class EvaluationResult:
    judgment: EvidenceRelevanceJudgment


class FakeEvaluator:
    def evaluate(self, *, element_text: str, evidence_excerpt: str) -> EvaluationResult:
        return EvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                relevance_score=0.5,
                rationale="Factory fixture judgment.",
                issues=[],
            )
        )


def request() -> PatentMultiPatentComparisonRequest:
    return PatentMultiPatentComparisonRequest(
        target_publication_number="EP1000000B1",
        comparison_publication_numbers=("EP2000000A1", "EP3000000A1"),
        maximum_bytes=4096,
    )


def settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-5",
        openai_timeout_seconds=30.0,
        openai_max_retries=0,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )


def test_factory_uses_no_provider_factories_when_all_components_injected() -> None:
    def unexpected(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("provider factory must not be called")

    workflow = build_openai_epo_patent_multi_patent_comparison_workflow(
        request(),
        openai_client_factory=unexpected,  # type: ignore[arg-type]
        epo_config_loader=unexpected,  # type: ignore[arg-type]
        claims_retriever=FakeClaimsRetriever(calls=[]),
        abstract_retriever=FakeAbstractRetriever(calls=[]),
        claim_decomposer=FakeDecomposer(),
        mapping_evaluator=FakeEvaluator(),
    )

    assert workflow is not None


def test_factory_binds_byte_limit_and_creates_one_shared_epo_client() -> None:
    seen: dict[str, object] = {"client_calls": 0}

    def config_loader(maximum_bytes: int) -> EpoOpsConfig:
        seen["maximum_bytes"] = maximum_bytes
        return EpoOpsConfig(
            consumer_key=SecretStr("key"),
            consumer_secret=SecretStr("secret"),
            maximum_response_bytes=maximum_bytes,
        )

    def client_factory(_config: EpoOpsConfig) -> object:
        seen["client_calls"] = int(seen["client_calls"]) + 1
        return object()

    workflow = build_openai_epo_patent_multi_patent_comparison_workflow(
        request(),
        epo_config_loader=config_loader,
        epo_client_factory=client_factory,  # type: ignore[arg-type]
        claim_decomposer=FakeDecomposer(),
        mapping_evaluator=FakeEvaluator(),
    )

    assert workflow is not None
    assert seen == {"client_calls": 1, "maximum_bytes": 4096}


def test_factory_creates_one_shared_openai_client() -> None:
    seen = {"client_calls": 0}
    fake_client = object()

    def client_factory(_settings: Settings) -> object:
        seen["client_calls"] += 1
        return fake_client

    workflow = build_openai_epo_patent_multi_patent_comparison_workflow(
        request(),
        settings=settings(),
        openai_client_factory=client_factory,  # type: ignore[arg-type]
        claims_retriever=FakeClaimsRetriever(calls=[]),
        abstract_retriever=FakeAbstractRetriever(calls=[]),
    )

    assert workflow is not None
    assert seen["client_calls"] == 1


def test_factory_rejects_mismatched_epo_byte_configuration() -> None:
    with pytest.raises(RuntimeError, match="not bound.*maximum_bytes"):
        build_openai_epo_patent_multi_patent_comparison_workflow(
            request(),
            epo_config_loader=lambda _maximum_bytes: EpoOpsConfig(
                consumer_key=SecretStr("key"),
                consumer_secret=SecretStr("secret"),
                maximum_response_bytes=8192,
            ),
            claim_decomposer=FakeDecomposer(),
            mapping_evaluator=FakeEvaluator(),
        )


def test_factory_rejects_wrong_request_type() -> None:
    with pytest.raises(TypeError, match="request must be"):
        build_openai_epo_patent_multi_patent_comparison_workflow(object())  # type: ignore[arg-type]
