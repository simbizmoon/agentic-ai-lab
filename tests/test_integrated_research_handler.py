"""Tests for the approved integrated Web and Local CLI handler."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.rag.caching_embedding_provider import CachingEmbeddingProvider
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.rag.openai_embedding_provider import OpenAIEmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.integrated_research_handler import IntegratedResearchHandler
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_document_adapter import LocalDocumentAdapter
from app.research.local_document_parser import LocalDocumentParser
from app.research.local_external_send_approval import LocalExternalSendApproval
from app.research.local_worker_runtime import LocalWorkerSettings
from app.research.pipeline_analysis_adapters import (
    PipelineEvidenceExtractorAdapter,
)
from app.research.research_result_writer import ResearchResultPaths
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.schemas.tavily_search_config import TavilySearchConfig


@pytest.fixture(autouse=True)
def isolate_runtime_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


def policy_for(*paths: Path) -> LocalDocumentAccessPolicy:
    return LocalDocumentAccessPolicy(
        allowed_roots=tuple(dict.fromkeys(path.parent.resolve() for path in paths)),
        maximum_file_bytes=32 * 1024 * 1024,
    )


def access_results(
    policy: LocalDocumentAccessPolicy, *paths: Path
) -> tuple[LocalDocumentAccessResult, ...]:
    gate = LocalDocumentAccessGate(policy)
    return tuple(gate.validate(path) for path in paths)


def integrated_approval(
    sources: tuple[LocalDocumentAccessResult, ...],
    *,
    approved: bool = True,
) -> LocalExternalSendApproval:
    return LocalExternalSendApproval.for_integrated_web_local_research(
        sources, approved=approved
    )


class RecordingAdapter(LocalDocumentAdapter):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def load_validated(self, access_results):
        self.calls.append("adapter")
        return super().load_validated(access_results)


class OrderRecordingParser(LocalDocumentParser):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def parse(self, source: LocalDocumentAccessResult):
        self._calls.append("parser")
        return super().parse(source)


@pytest.mark.parametrize(
    "approval_kind",
    ["missing", "false", "semantic", "partial", "extra"],
)
def test_approval_failure_blocks_adapter_and_all_provider_factories(
    tmp_path: Path,
    approval_kind: str,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    extra = tmp_path / "extra.txt"
    for path, text in (
        (first, "First evidence."),
        (second, "Second evidence."),
        (extra, "Extra evidence."),
    ):
        path.write_text(text, encoding="utf-8")
    policy = policy_for(first)
    sources = access_results(policy, first, second)
    extra_source = access_results(policy, extra)[0]
    approvals = {
        "missing": None,
        "false": integrated_approval(sources, approved=False),
        "semantic": LocalExternalSendApproval.for_semantic_local_research(sources),
        "partial": integrated_approval((sources[0],)),
        "extra": integrated_approval((*sources, extra_source)),
    }
    calls: list[str] = []
    handler = IntegratedResearchHandler(
        document_adapter=RecordingAdapter(calls),
        config_loader=lambda: calls.append("tavily"),  # type: ignore[arg-type]
        settings_loader=lambda: calls.append("settings"),  # type: ignore[arg-type]
        openai_client_factory=lambda settings: calls.append("openai"),  # type: ignore[arg-type]
        local_worker_settings_loader=lambda: calls.append("workers"),  # type: ignore[arg-type]
        embedding_cache_directory_resolver=lambda: (
            calls.append("cache") or tmp_path / "cache"
        ),
        parsed_cache_directory_resolver=lambda: (
            calls.append("parsed-cache") or tmp_path / "parsed-cache"
        ),
    )

    with pytest.raises(ValueError):
        handler(
            "How does integrated research use sources?",
            "Explain approved integrated source analysis.",
            sources,
            3,
            2048,
            tmp_path / "reports",
            policy,
            approvals[approval_kind],
        )

    assert calls == []


@pytest.mark.parametrize(
    ("changed", "message"),
    [(b"changed!", "digest changed"), (b"changed size", "size changed")],
)
def test_changed_source_blocks_provider_factories_after_adapter(
    tmp_path: Path,
    changed: bytes,
    message: str,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"original")
    policy = policy_for(source)
    sources = access_results(policy, source)
    approval = integrated_approval(sources)
    source.write_bytes(changed)
    calls: list[str] = []
    handler = IntegratedResearchHandler(
        document_adapter=RecordingAdapter(calls),
        config_loader=lambda: calls.append("tavily"),  # type: ignore[arg-type]
        settings_loader=lambda: calls.append("settings"),  # type: ignore[arg-type]
        openai_client_factory=lambda settings: calls.append("openai"),  # type: ignore[arg-type]
        embedding_cache_directory_resolver=lambda: (
            calls.append("cache") or tmp_path / "cache"
        ),
    )

    with pytest.raises(ValueError, match=message):
        handler(
            "How are changed sources rejected?",
            "Explain integrated approval revalidation.",
            sources,
            2,
            2048,
            tmp_path / "reports",
            policy,
            approval,
        )

    assert calls == []


def test_invalid_local_document_blocks_cache_and_provider_composition(
    tmp_path: Path,
) -> None:
    source = tmp_path / "malformed.pdf"
    source.write_bytes(b"not a PDF")
    policy = policy_for(source)
    sources = access_results(policy, source)
    calls: list[str] = []
    handler = IntegratedResearchHandler(
        document_adapter=RecordingAdapter(calls),
        config_loader=lambda: calls.append("tavily"),  # type: ignore[arg-type]
        settings_loader=lambda: calls.append("settings"),  # type: ignore[arg-type]
        openai_client_factory=lambda settings: calls.append("openai"),  # type: ignore[arg-type]
        embedding_cache_directory_resolver=lambda: (
            calls.append("cache") or tmp_path / "cache"
        ),
    )

    with pytest.raises(ValueError, match="could not be opened or parsed"):
        handler(
            "How is an invalid source rejected?",
            "Verify validation ordering.",
            sources,
            2,
            2048,
            tmp_path / "reports",
            policy,
            integrated_approval(sources),
        )

    assert calls == ["adapter"]


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

    def write(self, result, *, output_dir: Path, execution_id: str):
        self.calls.append((result, output_dir, execution_id))
        return self.paths


def test_success_builds_providers_only_after_adapter_and_fresh_revalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Integrated local evidence.", encoding="utf-8")
    policy = policy_for(source)
    sources = access_results(policy, source)
    approval = integrated_approval(sources)
    calls: list[str] = []
    pipeline_result = object()
    pipeline = FakePipeline(pipeline_result)
    guardrail = FakeGuardrail()
    writer = FakeWriter(
        ResearchResultPaths(
            execution_dir=tmp_path,
            report_path=tmp_path / "report.md",
            result_path=tmp_path / "result.json",
        )
    )
    original_validate = LocalDocumentAccessGate.validate

    def recording_validate(self, path):
        calls.append("revalidate")
        return original_validate(self, path)

    monkeypatch.setattr(LocalDocumentAccessGate, "validate", recording_validate)
    monkeypatch.setattr(
        "app.research.integrated_research_handler.build_hybrid_bounded_research_workers",
        lambda **kwargs: SimpleNamespace(
            semantic_citation_verifier=object(),
            claim_relevance_evaluator=object(),
            answer_coverage_evaluator=object(),
        ),
    )
    captured: dict[str, object] = {}

    def fake_build_integrated_research_pipeline(**kwargs):
        captured.update(kwargs)
        return pipeline

    monkeypatch.setattr(
        "app.research.integrated_research_handler.build_integrated_research_pipeline",
        fake_build_integrated_research_pipeline,
    )
    settings = Settings(
        openai_api_key="secret",
        openai_model="test-model",
        openai_timeout_seconds=30.0,
        openai_max_retries=0,
        app_env="test",
        log_level="INFO",
        max_agent_steps=10,
    )
    handler = IntegratedResearchHandler(
        id_factory=lambda: "integrated-001",
        local_document_parser_factory=lambda: OrderRecordingParser(calls),
        parsed_cache_directory_resolver=lambda: (
            calls.append("parsed-cache") or tmp_path / "parsed-cache"
        ),
        config_loader=lambda: (
            calls.append("tavily") or TavilySearchConfig(api_key=SecretStr("secret"))
        ),
        settings_loader=lambda: calls.append("settings") or settings,
        openai_client_factory=lambda value: calls.append("openai") or object(),  # type: ignore[arg-type]
        local_worker_settings_loader=lambda: (
            calls.append("workers")
            or LocalWorkerSettings(
                provider="openai",
                model="qwen3.5:4b",
                ollama_base_url="http://127.0.0.1:11434",
                ollama_timeout_seconds=120.0,
            )
        ),
        embedding_cache_directory_resolver=lambda: (
            calls.append("cache") or tmp_path / "embedding-cache"
        ),
        guardrail=guardrail,
        writer=writer,
        stdout=io.StringIO(),
    )

    status = handler(
        "How does integrated research use sources?",
        "Explain approved integrated source analysis.",
        sources,
        3,
        2048,
        tmp_path / "reports",
        policy,
        approval,
    )

    assert status == 0
    assert calls == [
        "revalidate",
        "parsed-cache",
        "parser",
        "revalidate",
        "cache",
        "tavily",
        "settings",
        "openai",
        "workers",
    ]
    evidence_adapter = captured["evidence_extractor"]
    assert isinstance(evidence_adapter, PipelineEvidenceExtractorAdapter)
    semantic_extractor = evidence_adapter.extractor
    assert isinstance(semantic_extractor, SemanticResearchEvidenceExtractor)
    assert isinstance(
        semantic_extractor._shortlister,
        EmbeddingSemanticEvidenceShortlister,
    )
    caching_provider = semantic_extractor._shortlister.embedding_provider
    assert isinstance(caching_provider, CachingEmbeddingProvider)
    assert isinstance(caching_provider._provider, OpenAIEmbeddingProvider)
    assert isinstance(caching_provider._cache, FileEmbeddingCache)
    assert caching_provider._cache.directory == (tmp_path / "embedding-cache").resolve()
    assert caching_provider.model_name == "text-embedding-3-small"
    assert caching_provider.dimensions == 1536
    assert captured["maximum_documents"] == 3
    assert "semantic_citation_verifier" in captured
    assert pipeline.calls[0][1] == "integrated-001-workspace"
    assert guardrail.calls == [(pipeline_result, "integrated-001")]
    assert writer.calls == [(pipeline_result, tmp_path / "reports", "integrated-001")]
