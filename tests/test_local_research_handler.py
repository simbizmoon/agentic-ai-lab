"""Tests for the default local research handler."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.rag.openai_embedding_provider import OpenAIEmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.generative_pipeline_claim_builder import (
    GenerativePipelineClaimBuilder,
)
from app.research.hybrid_role_policy import (
    HybridResearchRole,
    ResearchExecutionProvider,
)
from app.research.local_research_handler import (
    LOCAL_CLAIM_GENERATION_BUDGET,
    LOCAL_CLAIM_RELEVANCE_BUDGET,
    LOCAL_EVIDENCE_RELEVANCE_BUDGET,
    SemanticLocalResearchHandler,
)
from app.research.local_worker_runtime import LocalWorkerSettings
from app.research.openai_evidence_claim_generator import (
    OpenAIEvidenceClaimGenerator,
)
from app.research.openai_evidence_relevance_evaluator import (
    OpenAIEvidenceRelevanceEvaluator,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.pipeline_analysis_adapters import (
    PipelineEvidenceExtractorAdapter,
)
from app.research.research_result_writer import ResearchResultPaths
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
)
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)


class FakePipeline:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, str]] = []

    def run(self, request: object, *, workspace_id: str) -> object:
        self.calls.append((request, workspace_id))
        return self.result


class FakeGuardrail:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    def validate(self, result: object, *, execution_id: str) -> None:
        self.calls.append((result, execution_id))


class FakeWriter:
    def __init__(self, paths: ResearchResultPaths) -> None:
        self.paths = paths
        self.calls: list[tuple[object, Path, str]] = []

    def write(
        self,
        result: object,
        *,
        output_dir: Path,
        execution_id: str,
    ) -> ResearchResultPaths:
        self.calls.append((result, output_dir, execution_id))
        return self.paths


def worker_settings(provider: str) -> LocalWorkerSettings:
    return LocalWorkerSettings(
        provider=provider,
        model="qwen3.5:4b",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_timeout_seconds=120.0,
    )


def test_handler_validates_sources_before_loading_providers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unsupported.pdf"
    source.write_bytes(b"PDF")
    calls: list[str] = []

    def settings_loader() -> object:
        calls.append("settings")
        return object()

    def openai_client_factory(_settings: object) -> object:
        calls.append("openai-client")
        return object()

    def local_worker_settings_loader() -> LocalWorkerSettings:
        calls.append("local-worker-settings")
        return worker_settings("openai")

    handler = SemanticLocalResearchHandler(
        id_factory=lambda: "handler-invalid-source",
        settings_loader=settings_loader,  # type: ignore[arg-type]
        openai_client_factory=openai_client_factory,  # type: ignore[arg-type]
        local_worker_settings_loader=(
            local_worker_settings_loader
        ),
    )

    with pytest.raises(
        ValueError,
        match="could not be opened or parsed",
    ):
        handler(
            "Question",
            "Objective",
            (source,),
            tmp_path / "reports",
        )

    assert calls == []


@pytest.mark.parametrize(
    ("provider", "expected_provider"),
    [
        ("openai", ResearchExecutionProvider.OPENAI),
        ("local", ResearchExecutionProvider.LOCAL),
    ],
)
def test_handler_wires_semantic_analysis_and_bounded_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    provider: str,
    expected_provider: ResearchExecutionProvider,
) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        "Grounded research connects claims to evidence.",
        encoding="utf-8",
    )
    captured_pipeline: dict[str, object] = {}
    captured_workers: dict[str, object] = {}
    result = object()
    pipeline = FakePipeline(result)
    verifier = object()
    relevance_evaluator = object()
    coverage_evaluator = object()

    def fake_build_local_research_pipeline(
        bundle: object,
        **kwargs: object,
    ) -> FakePipeline:
        captured_pipeline["bundle"] = bundle
        captured_pipeline.update(kwargs)
        return pipeline

    def fake_build_hybrid_bounded_research_workers(
        **kwargs: object,
    ) -> object:
        captured_workers.update(kwargs)
        return SimpleNamespace(
            semantic_citation_verifier=verifier,
            claim_relevance_evaluator=relevance_evaluator,
            answer_coverage_evaluator=coverage_evaluator,
        )

    monkeypatch.setattr(
        "app.research.local_research_handler."
        "build_local_research_pipeline",
        fake_build_local_research_pipeline,
    )
    monkeypatch.setattr(
        "app.research.local_research_handler."
        "build_hybrid_bounded_research_workers",
        fake_build_hybrid_bounded_research_workers,
    )
    paths = ResearchResultPaths(
        execution_dir=tmp_path / "reports" / "handler-001",
        report_path=tmp_path / "reports" / "handler-001" / "report.md",
        result_path=tmp_path / "reports" / "handler-001" / "result.json",
    )
    writer = FakeWriter(paths)
    guardrail = FakeGuardrail()
    stdout = io.StringIO()
    fake_client = object()
    handler = SemanticLocalResearchHandler(
        id_factory=lambda: "handler-001",
        writer=writer,  # type: ignore[arg-type]
        guardrail=guardrail,  # type: ignore[arg-type]
        stdout=stdout,
        settings_loader=lambda: SimpleNamespace(
            openai_model="gpt-5",
        ),  # type: ignore[arg-type]
        openai_client_factory=lambda _settings: fake_client,  # type: ignore[arg-type]
        local_worker_settings_loader=lambda: worker_settings(
            provider
        ),
    )

    status = handler(
        "How does grounded research connect claims to evidence?",
        "Explain traceable evidence.",
        (source,),
        tmp_path / "reports",
    )

    assert status == 0
    evidence_adapter = captured_pipeline["evidence_extractor"]
    assert isinstance(
        evidence_adapter,
        PipelineEvidenceExtractorAdapter,
    )
    semantic_extractor = evidence_adapter.extractor
    assert isinstance(
        semantic_extractor,
        SemanticResearchEvidenceExtractor,
    )
    assert semantic_extractor.question == (
        "How does grounded research connect claims to evidence?"
    )
    assert semantic_extractor.objective == "Explain traceable evidence."
    assert isinstance(
        semantic_extractor._paragraph_extractor,
        ParagraphEvidenceExtractor,
    )
    assert isinstance(
        semantic_extractor._shortlister,
        EmbeddingSemanticEvidenceShortlister,
    )
    assert isinstance(
        semantic_extractor._shortlister.embedding_provider,
        OpenAIEmbeddingProvider,
    )
    assert isinstance(
        semantic_extractor._reranker,
        SemanticEvidenceReranker,
    )
    assert isinstance(
        semantic_extractor._reranker.evaluator,
        OpenAIEvidenceRelevanceEvaluator,
    )
    assert (
        semantic_extractor._reranker.budget
        == LOCAL_EVIDENCE_RELEVANCE_BUDGET
    )

    claim_builder = captured_pipeline["claim_builder"]
    assert isinstance(claim_builder, GenerativePipelineClaimBuilder)
    assert isinstance(
        claim_builder._generator,
        OpenAIEvidenceClaimGenerator,
    )
    assert claim_builder._budget == LOCAL_CLAIM_GENERATION_BUDGET
    assert captured_pipeline["semantic_citation_verifier"] is verifier
    assert (
        captured_pipeline["claim_relevance_evaluator"]
        is relevance_evaluator
    )
    assert (
        captured_pipeline["answer_coverage_evaluator"]
        is coverage_evaluator
    )

    role_policy = captured_workers["role_policy"]
    for role in (
        HybridResearchRole.SEMANTIC_CITATION,
        HybridResearchRole.CLAIM_RELEVANCE,
        HybridResearchRole.ANSWER_COVERAGE,
    ):
        assert role_policy.provider_for(role) is expected_provider
    assert (
        role_policy.provider_for(HybridResearchRole.EVIDENCE_RELEVANCE)
        is ResearchExecutionProvider.OPENAI
    )
    assert (
        role_policy.provider_for(HybridResearchRole.CLAIM_GENERATION)
        is ResearchExecutionProvider.OPENAI
    )
    assert (
        captured_workers["claim_relevance_budget"]
        == LOCAL_CLAIM_RELEVANCE_BUDGET
    )
    assert pipeline.calls[0][1] == "handler-001-workspace"
    assert guardrail.calls == [(result, "handler-001")]
    assert writer.calls == [
        (result, tmp_path / "reports", "handler-001")
    ]
    assert "AIRA report:" in stdout.getvalue()
    assert "AIRA result:" in stdout.getvalue()
