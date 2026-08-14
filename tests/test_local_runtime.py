"""Tests for the local-document AIRA runtime."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from app.budget import ExecutionBudget
from app.rag.embedding_provider import EmbeddingProvider
from app.research.embedding_semantic_evidence_shortlister import (
    EmbeddingSemanticEvidenceShortlister,
)
from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    WholeDocumentEvidenceExtractor,
    build_local_research_pipeline,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceExtractor,
)
from app.research.pipeline_analysis_adapters import (
    DeterministicPipelineClaimBuilder,
    PipelineEvidenceExtractorAdapter,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
    ResearchCitationVerification,
)
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
)
from app.research.semantic_research_evidence_extractor import (
    SemanticResearchEvidenceExtractor,
)
from app.research.single_research_agent_pipeline import (
    AnswerCoverageEvaluationServiceProtocol,
    ClaimRelevanceEvaluationServiceProtocol,
    SemanticCitationVerifierProtocol,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel
from app.schemas.claim_relevance_judgment import ClaimRelevanceLevel
from app.schemas.document_embedding import TextEmbedding
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_claim_relevance_evaluation import (
    ResearchClaimRelevanceEvaluation,
)
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSet,
)
from app.services.text_generation import TokenUsage
from tests.test_local_pdf_text_extractor import write_pdf


class RecordingEvidenceExtractor:
    """Delegate evidence extraction while recording calls."""

    def __init__(self) -> None:
        self.calls = 0
        self._delegate = PipelineEvidenceExtractorAdapter(
            WholeDocumentEvidenceExtractor()
        )

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        self.calls += 1
        return self._delegate.extract(document_set)


class RecordingClaimBuilder:
    """Delegate claim building while recording calls."""

    def __init__(self) -> None:
        self.calls = 0
        self._delegate = DeterministicPipelineClaimBuilder()

    def build(self, evidence_set: ResearchEvidenceSet) -> ResearchClaimSet:
        self.calls += 1
        return self._delegate.build(evidence_set)


def test_local_runtime_runs_end_to_end(
    tmp_path: Path,
) -> None:
    source = tmp_path / "grounded-research.md"
    source.write_text(
        (
            "# Grounded Research Evidence\n\n"
            "Grounded research connects claims to "
            "traceable evidence and citations."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)
    assert pipeline.semantic_citation_verifier is None
    assert pipeline.claim_relevance_evaluator is None
    assert pipeline.answer_coverage_evaluator is None
    request = ResearchRequest(
        request_id="local-runtime-001",
        question=(
            "How does grounded research use traceable evidence?"
        ),
        objective=(
            "Explain how grounded research connects claims "
            "to evidence and citations."
        ),
        include_topics=["grounded research evidence"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    assert result.workspace.progress().candidate_count == 1
    assert result.workspace.progress().document_count == 1
    assert result.workspace.progress().evidence_count == 1
    assert result.workspace.progress().claim_count == 1
    assert result.report.claim_count == 1
    assert result.report.citation_count == 1
    assert result.quality.passed is True



def test_local_runtime_runs_pdf_deterministically(
    tmp_path: Path,
) -> None:
    source = tmp_path / "deterministic.pdf"
    first = "First PDF page evidence."
    second = "Second PDF page evidence."
    write_pdf(source, [first, second])
    bundle = LocalDocumentAdapter().load((source,))
    request = ResearchRequest(
        request_id="local-runtime-pdf-deterministic",
        question="What evidence is in the local PDF document?",
        objective="Create an offline grounded claim from the PDF evidence.",
        include_topics=["local PDF evidence"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=1,
    )

    result = build_local_research_pipeline(bundle).run(request)

    document = result.workspace.document_set.documents[0]
    evidence = result.workspace.evidence_set.evidence[0]
    assert document.content_type is ResearchSourceContentType.PDF_TEXT
    assert [section.metadata["page_number"] for section in document.sections] == [
        "1",
        "2",
    ]
    assert evidence.excerpt == document.content
    assert "page_number" not in evidence.metadata
    assert result.workspace.progress().claim_count == 1
    assert result.report.citation_count == 1


def test_local_runtime_uses_injected_analysis_components(
    tmp_path: Path,
) -> None:
    source = tmp_path / "injected-components.md"
    source.write_text(
        "Injected analysis components use this evidence.",
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    evidence_extractor = RecordingEvidenceExtractor()
    claim_builder = RecordingClaimBuilder()
    pipeline = build_local_research_pipeline(
        bundle,
        evidence_extractor=evidence_extractor,
        claim_builder=claim_builder,
    )
    request = ResearchRequest(
        request_id="local-runtime-injected-001",
        question="How are analysis components injected?",
        objective="Use injected analysis components.",
        include_topics=["injected analysis components"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    assert evidence_extractor.calls == 1
    assert claim_builder.calls == 1
    assert result.workspace.progress().evidence_count == 1
    assert result.workspace.progress().claim_count == 1


def test_local_runtime_forwards_optional_evaluators(
    tmp_path: Path,
) -> None:
    source = tmp_path / "optional-evaluators.md"
    source.write_text("Optional evaluators.", encoding="utf-8")
    bundle = LocalDocumentAdapter().load((source,))
    verifier = cast(SemanticCitationVerifierProtocol, object())
    relevance_evaluator = cast(
        ClaimRelevanceEvaluationServiceProtocol,
        object(),
    )
    coverage_evaluator = cast(
        AnswerCoverageEvaluationServiceProtocol,
        object(),
    )

    pipeline = build_local_research_pipeline(
        bundle,
        semantic_citation_verifier=verifier,
        claim_relevance_evaluator=relevance_evaluator,
        answer_coverage_evaluator=coverage_evaluator,
    )

    assert pipeline.semantic_citation_verifier is verifier
    assert pipeline.claim_relevance_evaluator is relevance_evaluator
    assert pipeline.answer_coverage_evaluator is coverage_evaluator


class HybridRoutingEmbeddingProvider(EmbeddingProvider):
    """Return deterministic vectors for the hybrid-routing paragraph."""


    @property
    def model_name(self) -> str:
        return "hybrid-routing-test"


    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=(
                    [1.0, 0.0]
                    if "aira" in text.casefold()
                    or "hybrid research" in text.casefold()
                    else [0.0, 1.0]
                ),
            )
            for text in texts
        ]


class HybridRoutingRelevanceEvaluator:
    """Select only the paragraph describing hybrid role routing."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        relevant = "bounded citation" in evidence_excerpt.casefold()
        level = (
            EvidenceRelevanceLevel.DIRECTLY_RELEVANT
            if relevant
            else EvidenceRelevanceLevel.IRRELEVANT
        )
        return EvidenceRelevanceEvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=level,
                relevance_score=0.95 if relevant else 0.05,
                rationale="Controlled offline relevance judgment.",
                issues=[],
            ),
            response_id="offline-relevance",
            request_id="offline-request",
            usage=TokenUsage(
                input_tokens=1,
                cached_input_tokens=0,
                output_tokens=1,
                reasoning_tokens=0,
                total_tokens=2,
            ),
            elapsed_seconds=0.0,
        )


class RecordingCitationVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(
        self,
        *,
        claim_set: ResearchClaimSet,
        evidence_set: ResearchEvidenceSet,
    ) -> list[ResearchCitationVerification]:
        self.calls += 1
        claim = claim_set.claims[0]
        citation = claim.citations[0]
        evidence = evidence_set.evidence[0]
        return [
            ResearchCitationVerification(
                verification_id="offline-verification",
                claim_id=claim.claim_id,
                citation_id=citation.citation_id,
                evidence_id=evidence.evidence_id,
                source_id=evidence.source_id,
                decision=ResearchCitationDecision.VERIFIED,
                entailment_score=1.0,
                traceability_score=1.0,
                citation_accuracy_score=1.0,
                rationale="Controlled evidence supports the claim.",
                issues=[],
            )
        ]


class RecordingClaimRelevanceEvaluator:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> list[ResearchClaimRelevanceEvaluation]:
        self.calls += 1
        return [
            ResearchClaimRelevanceEvaluation(
                evaluation_id="offline-claim-relevance",
                claim_id=claim_set.claims[0].claim_id,
                relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                relevance_score=1.0,
                rationale="The claim directly answers the request.",
                issues=[],
            )
        ]


class RecordingAnswerCoverageEvaluator:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> ResearchAnswerCoverageEvaluation:
        self.calls += 1
        return ResearchAnswerCoverageEvaluation(
            evaluation_id="offline-answer-coverage",
            request_id=request.request_id,
            claim_ids=[claim.claim_id for claim in claim_set.claims],
            coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            coverage_score=1.0,
            covered_aspects=["hybrid research role routing"],
            missing_aspects=[],
            rationale="The grounded claim covers the requested routing.",
        )



@pytest.mark.parametrize("source_format", ["markdown", "pdf"])
def test_local_runtime_runs_semantic_pipeline_offline(
    tmp_path: Path,
    source_format: str,
) -> None:
    docker = (
        "Docker bridge networking assigns private addresses and forwards "
        "container traffic through host networking rules."
    )
    routing = (
        "AIRA routes high-judgment evidence relevance and claim generation "
        "to OpenAI while bounded citation, claim relevance, and answer "
        "coverage roles may use the local qwen3.5:4b worker."
    )
    postgres = (
        "PostgreSQL backups use base backups and archived write-ahead logs "
        "to support point-in-time database recovery."
    )
    content = f"{docker}\n\n{routing}\n\n{postgres}"
    source = tmp_path / (
        "hybrid-routing.pdf"
        if source_format == "pdf"
        else "hybrid-routing.md"
    )
    if source_format == "pdf":
        write_pdf(source, [docker, routing, postgres])
    else:
        source.write_text(content, encoding="utf-8")
    bundle = LocalDocumentAdapter().load((source,))
    evidence_extractor = PipelineEvidenceExtractorAdapter(
        SemanticResearchEvidenceExtractor(
            question=(
                "How does AIRA divide research work between "
                "OpenAI and the local model?"
            ),
            objective=(
                "Explain the hybrid research role routing using "
                "grounded local evidence."
            ),
            paragraph_extractor=ParagraphEvidenceExtractor(
                maximum_evidence=3,
                minimum_characters=40,
            ),
            shortlister=EmbeddingSemanticEvidenceShortlister(
                embedding_provider=HybridRoutingEmbeddingProvider(),
                maximum_candidates=3,
            ),
            reranker=SemanticEvidenceReranker(
                evaluator=HybridRoutingRelevanceEvaluator(),
                budget=ExecutionBudget(
                    max_attempts=3,
                    max_recorded_tokens=100,
                    max_elapsed_seconds=10.0,
                ),
            ),
            maximum_evidence=1,
        )
    )
    citation_verifier = RecordingCitationVerifier()
    relevance_evaluator = RecordingClaimRelevanceEvaluator()
    coverage_evaluator = RecordingAnswerCoverageEvaluator()
    pipeline = build_local_research_pipeline(
        bundle,
        evidence_extractor=evidence_extractor,
        claim_builder=DeterministicPipelineClaimBuilder(),
        semantic_citation_verifier=citation_verifier,
        claim_relevance_evaluator=relevance_evaluator,
        answer_coverage_evaluator=coverage_evaluator,
    )
    request = ResearchRequest(
        request_id="local-runtime-offline-001",
        question=(
            "How does AIRA divide research work between "
            "OpenAI and the local model?"
        ),
        objective=(
            "Explain the hybrid research role routing using "
            "grounded local evidence."
        ),
        include_topics=["AIRA hybrid research role routing"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=1,
    )

    result = pipeline.run(request)

    candidate = result.workspace.candidate_set.candidates[0]
    document = result.workspace.document_set.documents[0]
    evidence = result.workspace.evidence_set.evidence[0]
    query_by_id = {
        query.query_id: query.query_text
        for query in result.workspace.query_set.queries
    }

    assert evidence.excerpt == routing
    if source_format == "pdf":
        assert document.content_type is ResearchSourceContentType.PDF_TEXT
        assert evidence.metadata["page_number"] == "2"
        assert [
            section.metadata["page_number"]
            for section in document.sections
        ] == ["1", "2", "3"]
    assert evidence.excerpt != document.content
    assert document.content[
        evidence.start_character:evidence.end_character
    ] == evidence.excerpt
    assert candidate.metadata["local_path"] == str(source.resolve())
    assert document.metadata["filename"] == source.name
    assert candidate.metadata["search_query_text"] == (
        query_by_id[candidate.query_id]
    )
    claim = result.workspace.claim_set.claims[0]
    citation = claim.citations[0]
    assert claim.text == routing
    assert citation.excerpt == evidence.excerpt
    assert citation.start_character == evidence.start_character
    assert citation.end_character == evidence.end_character
    assert citation_verifier.calls == 1
    assert relevance_evaluator.calls == 1
    assert coverage_evaluator.calls == 1
    assert len(result.citation_verifications) == 1
    assert len(result.claim_relevance_evaluations) == 1
    assert result.answer_coverage_evaluation is not None
    assert result.report.claim_count == 1
    assert result.report.citation_count == 1
    assert result.quality.passed is True


def test_local_runtime_supports_korean_search(
    tmp_path: Path,
) -> None:
    source = tmp_path / "근거기반연구.md"
    source.write_text(
        (
            "# 근거 기반 연구\n\n"
            "근거 기반 연구는 주장과 출처 및 증거를 "
            "추적 가능하게 연결한다."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)
    request = ResearchRequest(
        request_id="local-runtime-ko-001",
        question=(
            "근거 기반 연구는 주장과 증거를 어떻게 연결하는가?"
        ),
        objective=(
            "출처와 증거의 추적 가능성을 바탕으로 "
            "근거 기반 연구를 설명한다."
        ),
        include_topics=["근거 기반 연구"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    assert result.workspace.progress().candidate_count == 1
    assert result.workspace.progress().claim_count == 1
