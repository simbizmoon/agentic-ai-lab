"""Offline integration tests for the federated Web and Local runtime."""

from __future__ import annotations

import pytest

from app.research.integrated_runtime import build_integrated_research_pipeline
from app.research.integrated_source_diversity_document_selector import (
    IntegratedSourceDiversityDocumentSelector,
)
from app.research.local_runtime import WholeDocumentEvidenceExtractor
from app.research.pipeline_analysis_adapters import PipelineEvidenceExtractorAdapter
from app.research.research_source_reader import ResearchSourceReader
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_request import ResearchRequest, ResearchSourceType
from app.schemas.research_search_query import ResearchSearchQuerySet
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.research_source_quality import ResearchSourceQualityEvaluation


class OriginSearcher:
    def __init__(self, *, origin: str, source_id: str, url: str) -> None:
        self.origin = origin
        self.source_id = source_id
        self.url = url

    def search(self, query_set: ResearchSearchQuerySet) -> ResearchSourceCandidateSet:
        query = query_set.ordered_queries()[0]
        candidate = ResearchSourceCandidate(
            source_id=self.source_id,
            request_id=query.request_id,
            task_id=query.task_id,
            query_id=query.query_id,
            title=f"{self.origin.title()} evidence",
            url=self.url,
            source_type=ResearchSourceType.OTHER,
            snippet=f"AIRA combines {self.origin} evidence.",
            rank=1,
            metadata={"research_origin": self.origin},
        )
        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=[candidate],
        )


class OriginReader(ResearchSourceReader):
    def __init__(self, *, name: str, content: str) -> None:
        self._name = name
        self.content = content
        self.calls: list[ResearchSourceCandidate] = []

    @property
    def name(self) -> str:
        return self._name

    def read(self, candidate: ResearchSourceCandidate) -> ResearchSourceDocument:
        self.calls.append(candidate)
        return ResearchSourceDocument(
            document_id=f"document-{candidate.source_id}",
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=self.content,
            language="en",
            word_count=len(self.content.split()),
            character_count=len(self.content),
            reader=self.name,
        )


def test_integrated_runtime_processes_web_and_local_in_one_execution() -> None:
    web_reader = OriginReader(
        name="web-reader",
        content=(
            "Web evidence explains that AIRA can gather current public "
            "research sources."
        ),
    )
    local_reader = OriginReader(
        name="local-reader",
        content=(
            "Local evidence explains that AIRA can ground research in "
            "user-provided documents."
        ),
    )
    pipeline = build_integrated_research_pipeline(
        web_searcher=OriginSearcher(
            origin="web",
            source_id="web-source",
            url="https://example.com/aira-web",
        ),
        local_searcher=OriginSearcher(
            origin="local",
            source_id="local-source",
            url="https://local.aira.invalid/source/local-source",
        ),
        web_reader=web_reader,
        local_reader=local_reader,
    )
    request = ResearchRequest(
        request_id="integrated-runtime-001",
        question="How does AIRA combine web and local evidence?",
        objective="Explain the unified evidence path with grounded citations.",
        include_topics=["web and local evidence"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    candidates = result.workspace.candidate_set
    documents = result.workspace.document_set
    evidence_set = result.workspace.evidence_set
    claim_set = result.workspace.claim_set
    assert candidates is not None
    assert documents is not None
    assert evidence_set is not None
    assert claim_set is not None
    assert [item.metadata["research_origin"] for item in candidates.candidates] == [
        "web",
        "local",
    ]
    assert [item.source_id for item in web_reader.calls] == ["web-source"]
    assert [item.source_id for item in local_reader.calls] == ["local-source"]
    assert {
        item.candidate.metadata["research_origin"] for item in documents.documents
    } == {
        "web",
        "local",
    }
    assert {item.source_id for item in evidence_set.evidence} == {
        "web-source",
        "local-source",
    }
    citations = [citation for claim in claim_set.claims for citation in claim.citations]
    assert {item.source_id for item in citations} == {
        "web-source",
        "local-source",
    }
    evidence_by_id = {item.evidence_id: item for item in evidence_set.evidence}
    for citation in citations:
        evidence = evidence_by_id[citation.evidence_id]
        assert citation.source_id == evidence.source_id
        assert citation.document_id == evidence.document_id
        assert citation.excerpt == evidence.excerpt
        assert citation.start_character == evidence.start_character
        assert citation.end_character == evidence.end_character


class MultiOriginSearcher:
    def __init__(
        self,
        *,
        origin: str,
        sources: list[tuple[str, float]],
    ) -> None:
        self.origin = origin
        self.sources = sources

    def search(self, query_set: ResearchSearchQuerySet) -> ResearchSourceCandidateSet:
        query = query_set.ordered_queries()[0]
        candidates = [
            ResearchSourceCandidate(
                source_id=source_id,
                request_id=query.request_id,
                task_id=query.task_id,
                query_id=query.query_id,
                title=f"AIRA integrated evidence {source_id}",
                url=f"https://example.com/{source_id}",
                source_type=ResearchSourceType.OTHER,
                snippet="AIRA integrated Web and Local evidence.",
                rank=rank,
                metadata={
                    "research_origin": self.origin,
                    "quality": str(quality),
                },
            )
            for rank, (source_id, quality) in enumerate(self.sources, start=1)
        ]
        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=candidates,
        )


class MultiOriginReader(ResearchSourceReader):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def read(self, candidate: ResearchSourceCandidate) -> ResearchSourceDocument:
        content = (
            "AIRA combines current Web research with explicitly supplied "
            f"Local evidence from {candidate.source_id}."
        )
        return ResearchSourceDocument(
            document_id=f"document-{candidate.source_id}",
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=content,
            language="en",
            word_count=len(content.split()),
            character_count=len(content),
            reader=self.name,
        )


class MetadataQualityEvaluator:
    def evaluate(self, document: ResearchSourceDocument):
        score = float(document.candidate.metadata["quality"])
        return ResearchSourceQualityEvaluation(
            document=document,
            evaluator="metadata-quality",
            authority_score=score,
            primary_source_score=score,
            recency_score=score,
            completeness_score=score,
            traceability_score=score,
            overall_score=score,
            quality_level=ResearchSourceQualityEvaluation.level_for_score(score),
        )


class SelectiveRecordingEvidenceExtractor:
    def __init__(self, excluded_origins: set[str] | None = None) -> None:
        self.excluded_origins = excluded_origins or set()
        self.calls: list[tuple[str, str]] = []
        self.delegate = PipelineEvidenceExtractorAdapter(
            WholeDocumentEvidenceExtractor()
        )

    def extract(self, document_set: ResearchSourceDocumentSet):
        document = document_set.documents[0]
        origin = document.candidate.metadata["research_origin"]
        self.calls.append((document.candidate.source_id, origin))
        if origin in self.excluded_origins:
            return ResearchEvidenceSet(
                request_id=document_set.request_id,
                document_set=document_set,
                evidence=[],
            )
        return self.delegate.extract(document_set)


def smoke_shape_pipeline(
    extractor: SelectiveRecordingEvidenceExtractor,
):
    evaluator = MetadataQualityEvaluator()
    return build_integrated_research_pipeline(
        web_searcher=MultiOriginSearcher(
            origin="web",
            sources=[
                ("web-1", 0.98),
                ("web-2", 0.96),
                ("web-3", 0.94),
            ],
        ),
        local_searcher=MultiOriginSearcher(
            origin="local",
            sources=[("local-1", 0.50)],
        ),
        web_reader=MultiOriginReader("web-reader"),
        local_reader=MultiOriginReader("local-reader"),
        evidence_extractor=extractor,
        web_quality_evaluator=evaluator,
        local_quality_evaluator=evaluator,
        maximum_documents=4,
    )


def smoke_shape_request() -> ResearchRequest:
    return ResearchRequest(
        request_id="integrated-diversity-001",
        question="How does AIRA combine Web and Local evidence?",
        objective="Explain integrated research with grounded Local evidence.",
        maximum_sources=4,
    )


def test_higher_quality_web_does_not_prevent_local_evidence_opportunity() -> None:
    extractor = SelectiveRecordingEvidenceExtractor()

    result = smoke_shape_pipeline(extractor).run(smoke_shape_request())

    assert extractor.calls[:2] == [("web-1", "web"), ("local-1", "local")]
    evidence = result.workspace.evidence_set
    assert evidence is not None
    assert {item.source_id for item in evidence.evidence} == {
        "web-1",
        "web-2",
        "web-3",
        "local-1",
    }
    documents = result.workspace.document_set
    assert documents is not None
    origin_by_source = {
        item.candidate.source_id: item.candidate.metadata["research_origin"]
        for item in documents.documents
    }
    assert {origin_by_source[item.source_id] for item in evidence.evidence} == {
        "web",
        "local",
    }
    citations = [
        citation
        for claim in result.workspace.claim_set.claims
        for citation in claim.citations
    ]
    assert {item.source_id for item in citations} == set(origin_by_source)


@pytest.mark.parametrize(
    ("excluded_origin", "expected_origin"),
    [("local", "web"), ("web", "local")],
)
def test_no_evidence_origin_does_not_consume_quota_and_backfills(
    excluded_origin: str,
    expected_origin: str,
) -> None:
    extractor = SelectiveRecordingEvidenceExtractor({excluded_origin})

    result = smoke_shape_pipeline(extractor).run(smoke_shape_request())

    assert {origin for _, origin in extractor.calls} == {"web", "local"}
    documents = result.workspace.document_set
    assert documents is not None
    assert {
        item.candidate.metadata["research_origin"] for item in documents.documents
    } == {expected_origin}
    assert len(documents.documents) <= 4
    assert int(result.workspace.metadata["no_evidence_document_count"]) >= 1


def test_integrated_runtime_uses_source_diversity_selector_only_when_bounded() -> None:
    pipeline = build_integrated_research_pipeline(
        web_searcher=OriginSearcher(
            origin="web",
            source_id="web-source",
            url="https://example.com/web",
        ),
        local_searcher=OriginSearcher(
            origin="local",
            source_id="local-source",
            url="https://example.com/local",
        ),
        web_reader=OriginReader(name="web-reader", content="Web evidence."),
        local_reader=OriginReader(name="local-reader", content="Local evidence."),
        maximum_documents=2,
    )

    assert isinstance(
        pipeline.document_selector,
        IntegratedSourceDiversityDocumentSelector,
    )
