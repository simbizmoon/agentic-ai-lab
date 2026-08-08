"""Tests for the live research CLI handler."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from app.research.live_research_handler import (
    LIVE_CLAIM_GENERATION_BUDGET,
    LiveResearchHandler,
)
from app.schemas.tavily_search_config import (
    TavilySearchConfig,
)


class FakeWriter:
    """Marker writer replaced by a fake runner boundary."""


def test_handler_rejects_blank_execution_id() -> None:
    handler = LiveResearchHandler(
        id_factory=lambda: " ",
        config_loader=lambda: TavilySearchConfig(
            api_key=SecretStr("secret")
        ),
    )

    try:
        handler(
            "How does live grounded research work?",
            "Explain live grounded research safely.",
            1,
            1024,
            Path("reports"),
        )
    except RuntimeError as error:
        assert "execution ID factory returned blank" in str(error)
    else:
        raise AssertionError("expected RuntimeError")


def test_live_claim_generation_budget_is_bounded() -> None:
    assert LIVE_CLAIM_GENERATION_BUDGET.max_attempts == 8
    assert (
        LIVE_CLAIM_GENERATION_BUDGET.max_recorded_tokens
        == 8_000
    )
    assert (
        LIVE_CLAIM_GENERATION_BUDGET.max_elapsed_seconds
        == 60.0
    )



def test_live_handler_wires_claim_relevance_service(
    monkeypatch,
    tmp_path,
) -> None:
    from types import SimpleNamespace

    from app.research.claim_relevance_evaluation_service import (
        ClaimRelevanceEvaluationService,
    )
    from app.research.live_research_handler import (
        LIVE_CLAIM_RELEVANCE_BUDGET,
    )

    captured: dict[str, object] = {}

    class FakePipeline:
        pass

    def fake_build_live_research_pipeline(**kwargs):
        captured.update(kwargs)
        return FakePipeline()

    class FakeRunner:
        def __init__(
            self,
            *,
            pipeline_factory,
            writer,
            output_dir,
            artifact_execution_id_factory,
        ) -> None:
            self._pipeline_factory = pipeline_factory
            self._artifact_execution_id_factory = (
                artifact_execution_id_factory
            )

        def execute(self, request):
            research_request = SimpleNamespace(
                request_id=request.request_id,
                question=request.query,
                objective=request.context["objective"],
                maximum_sources=request.context[
                    "maximum_sources"
                ],
            )
            self._pipeline_factory(research_request)
            execution_id = self._artifact_execution_id_factory(
                request
            )
            return SimpleNamespace(
                result={
                    "artifact_paths": {
                        "report": (
                            tmp_path
                            / execution_id
                            / "report.md"
                        ),
                        "result": (
                            tmp_path
                            / execution_id
                            / "result.json"
                        ),
                    },
                    "quality_score": 0.9,
                }
            )

    monkeypatch.setattr(
        "app.research.live_research_handler."
        "build_live_research_pipeline",
        fake_build_live_research_pipeline,
    )
    monkeypatch.setattr(
        "app.research.live_research_handler."
        "ConcreteAiraResearchRunner",
        FakeRunner,
    )

    handler = LiveResearchHandler(
        id_factory=lambda: "execution-1",
        config_loader=lambda: TavilySearchConfig(
            api_key="test-key",
            maximum_results=3,
        ),
        settings_loader=lambda: SimpleNamespace(
            openai_model="gpt-5",
        ),
        openai_client_factory=lambda _settings: object(),
    )

    assert handler(
        "How can an agent bound model usage?",
        "Describe a concrete runtime mechanism.",
        1,
        10_000,
        tmp_path,
    ) == 0

    relevance = captured["claim_relevance_evaluator"]
    assert isinstance(
        relevance,
        ClaimRelevanceEvaluationService,
    )
    assert (
        relevance.budget
        == LIVE_CLAIM_RELEVANCE_BUDGET
    )

def test_live_evidence_relevance_budget_is_bounded() -> None:
    from app.research.live_research_handler import (
        LIVE_EVIDENCE_RELEVANCE_BUDGET,
    )

    assert LIVE_EVIDENCE_RELEVANCE_BUDGET.max_attempts == 8
    assert (
        LIVE_EVIDENCE_RELEVANCE_BUDGET.max_recorded_tokens
        == 8_000
    )
    assert (
        LIVE_EVIDENCE_RELEVANCE_BUDGET.max_elapsed_seconds
        == 60.0
    )


def test_live_handler_wires_semantic_evidence_extractor(
    monkeypatch,
    tmp_path,
) -> None:
    from types import SimpleNamespace

    from app.rag.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )
    from app.research.embedding_semantic_evidence_shortlister import (
        EmbeddingSemanticEvidenceShortlister,
    )
    from app.research.openai_evidence_relevance_evaluator import (
        OpenAIEvidenceRelevanceEvaluator,
    )
    from app.research.pipeline_analysis_adapters import (
        PipelineEvidenceExtractorAdapter,
    )
    from app.research.semantic_evidence_reranker import (
        SemanticEvidenceReranker,
    )
    from app.research.semantic_research_evidence_extractor import (
        SemanticResearchEvidenceExtractor,
    )

    captured: dict[str, object] = {}

    class FakePipeline:
        pass

    def fake_build_live_research_pipeline(**kwargs):
        captured.update(kwargs)
        return FakePipeline()

    class FakeRunner:
        def __init__(
            self,
            *,
            pipeline_factory,
            writer,
            output_dir,
            artifact_execution_id_factory,
        ) -> None:
            self._pipeline_factory = pipeline_factory
            self._artifact_execution_id_factory = (
                artifact_execution_id_factory
            )

        def execute(self, request):
            research_request = SimpleNamespace(
                request_id=request.request_id,
                question=request.query,
                objective=request.context["objective"],
                maximum_sources=request.context[
                    "maximum_sources"
                ],
            )
            self._pipeline_factory(research_request)
            execution_id = self._artifact_execution_id_factory(
                request
            )
            return SimpleNamespace(
                result={
                    "artifact_paths": {
                        "report": (
                            tmp_path
                            / execution_id
                            / "report.md"
                        ),
                        "result": (
                            tmp_path
                            / execution_id
                            / "result.json"
                        ),
                    },
                    "quality_score": 0.9,
                }
            )

    monkeypatch.setattr(
        "app.research.live_research_handler."
        "build_live_research_pipeline",
        fake_build_live_research_pipeline,
    )
    monkeypatch.setattr(
        "app.research.live_research_handler."
        "ConcreteAiraResearchRunner",
        FakeRunner,
    )

    fake_client = object()
    handler = LiveResearchHandler(
        id_factory=lambda: "execution-semantic-evidence",
        config_loader=lambda: TavilySearchConfig(
            api_key="test-key",
            maximum_results=3,
        ),
        settings_loader=lambda: SimpleNamespace(
            openai_model="gpt-5",
        ),
        openai_client_factory=lambda _settings: fake_client,
    )

    assert handler(
        "How does an agent invoke tools?",
        "Explain callable invocation during execution.",
        1,
        10_000,
        tmp_path,
    ) == 0

    adapter = captured["evidence_extractor"]
    assert isinstance(
        adapter,
        PipelineEvidenceExtractorAdapter,
    )

    extractor = adapter.extractor
    assert isinstance(
        extractor,
        SemanticResearchEvidenceExtractor,
    )
    assert extractor.question == "How does an agent invoke tools?"
    assert extractor.objective == (
        "Explain callable invocation during execution."
    )

    shortlister = extractor._shortlister
    assert isinstance(
        shortlister,
        EmbeddingSemanticEvidenceShortlister,
    )
    assert isinstance(
        shortlister.embedding_provider,
        OpenAIEmbeddingProvider,
    )

    reranker = extractor._reranker
    assert isinstance(reranker, SemanticEvidenceReranker)
    assert isinstance(
        reranker.evaluator,
        OpenAIEvidenceRelevanceEvaluator,
    )

    from app.research.live_research_handler import (
        LIVE_EVIDENCE_RELEVANCE_BUDGET,
    )

    assert reranker.budget == LIVE_EVIDENCE_RELEVANCE_BUDGET
