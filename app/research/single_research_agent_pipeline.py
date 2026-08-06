"""Orchestration pipeline for one research agent."""

from __future__ import annotations

from typing import Protocol

from app.research.research_pipeline_error import (
    ResearchPipelineError,
)
from app.research.research_quality_evaluator import (
    ResearchQualityEvaluator,
)
from app.research.research_synthesizer import (
    DeterministicResearchSynthesizer,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_pipeline import (
    SingleResearchPipelineResult,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)
from app.schemas.research_task import ResearchTaskGraph
from app.schemas.research_workspace import ResearchWorkspace


class ResearchRequestValidatorProtocol(Protocol):
    """Contract for validating a research request."""

    def validate(self, request: ResearchRequest) -> object:
        """Validate one request."""


class ResearchTaskDecomposerProtocol(Protocol):
    """Contract for decomposing a research request."""

    def decompose(
        self,
        request: ResearchRequest,
    ) -> ResearchTaskGraph:
        """Create a research task graph."""


class ResearchQueryPlannerProtocol(Protocol):
    """Contract for planning search queries."""

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
    ) -> ResearchSearchQuerySet:
        """Create a search query set."""


class ResearchSourceSearcherProtocol(Protocol):
    """Contract for discovering source candidates."""

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        """Search for candidate sources."""


class ResearchSourceReaderProtocol(Protocol):
    """Contract for reading candidate sources."""

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        """Read candidate source documents."""


class ResearchEvidenceExtractorProtocol(Protocol):
    """Contract for extracting evidence."""

    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet:
        """Extract evidence from source documents."""


class ResearchClaimBuilderProtocol(Protocol):
    """Contract for building research claims."""

    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet:
        """Build claims from evidence."""


class ResearchSourceQualityEvaluatorProtocol(Protocol):
    """Contract for evaluating source quality."""

    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation:
        """Evaluate one source document."""


class ResearchDocumentSelectionProtocol(Protocol):
    """Contract for selecting readable source documents."""

    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: ResearchSourceQualityEvaluatorProtocol,
    ) -> object:
        """Return selected documents and matching evaluations."""


class SingleResearchAgentPipeline:
    """Run the complete single research-agent workflow."""

    def __init__(
        self,
        *,
        request_validator: ResearchRequestValidatorProtocol,
        task_decomposer: ResearchTaskDecomposerProtocol,
        query_planner: ResearchQueryPlannerProtocol,
        source_searcher: ResearchSourceSearcherProtocol,
        source_reader: ResearchSourceReaderProtocol,
        evidence_extractor: ResearchEvidenceExtractorProtocol,
        claim_builder: ResearchClaimBuilderProtocol,
        source_quality_evaluator: (
            ResearchSourceQualityEvaluatorProtocol
        ),
        document_selector: (
            ResearchDocumentSelectionProtocol | None
        ) = None,
        synthesizer: (
            DeterministicResearchSynthesizer | None
        ) = None,
        quality_evaluator: (
            ResearchQualityEvaluator | None
        ) = None,
    ) -> None:
        self._request_validator = request_validator
        self._task_decomposer = task_decomposer
        self._query_planner = query_planner
        self._source_searcher = source_searcher
        self._source_reader = source_reader
        self._evidence_extractor = evidence_extractor
        self._claim_builder = claim_builder
        self._source_quality_evaluator = (
            source_quality_evaluator
        )
        self._document_selector = document_selector
        self._synthesizer = (
            synthesizer
            or DeterministicResearchSynthesizer()
        )
        self._quality_evaluator = (
            quality_evaluator
            or ResearchQualityEvaluator()
        )

    @property
    def source_searcher(
        self,
    ) -> ResearchSourceSearcherProtocol:
        """Return the configured source searcher."""

        return self._source_searcher

    @property
    def source_reader(
        self,
    ) -> ResearchSourceReaderProtocol:
        """Return the configured source reader."""

        return self._source_reader

    @property
    def evidence_extractor(
        self,
    ) -> ResearchEvidenceExtractorProtocol:
        """Return the configured evidence extractor."""

        return self._evidence_extractor

    @property
    def source_quality_evaluator(
        self,
    ) -> ResearchSourceQualityEvaluatorProtocol:
        """Return the configured source-quality evaluator."""

        return self._source_quality_evaluator

    @property
    def document_selector(
        self,
    ) -> ResearchDocumentSelectionProtocol | None:
        """Return the configured document selector."""

        return self._document_selector

    def run(
        self,
        request: ResearchRequest,
        *,
        workspace_id: str | None = None,
    ) -> SingleResearchPipelineResult:
        """Run the complete research pipeline."""

        resolved_workspace_id = (
            workspace_id
            or f"{request.request_id}-workspace"
        )

        if not resolved_workspace_id.strip():
            raise ResearchPipelineError(
                "workspace_id must not be blank"
            )

        self._request_validator.validate(request)

        task_graph = self._task_decomposer.decompose(
            request
        )

        if not task_graph.tasks:
            raise ResearchPipelineError(
                "task decomposition produced no tasks"
            )

        query_set = self._query_planner.plan(
            request=request,
            task_graph=task_graph,
        )

        if not query_set.queries:
            raise ResearchPipelineError(
                "query planning produced no queries"
            )

        candidate_set = self._source_searcher.search(
            query_set
        )

        if not candidate_set.candidates:
            raise ResearchPipelineError(
                "source search produced no candidates"
            )

        read_document_set = self._source_reader.read(
            candidate_set
        )

        if not read_document_set.successful_documents():
            raise ResearchPipelineError(
                "source reading produced no readable documents"
            )

        (
            document_set,
            source_quality_evaluations,
        ) = self._select_documents(read_document_set)

        if not document_set.successful_documents():
            raise ResearchPipelineError(
                "source selection produced no readable documents"
            )

        evidence_set = self._evidence_extractor.extract(
            document_set
        )

        if not evidence_set.evidence:
            raise ResearchPipelineError(
                "evidence extraction produced no evidence"
            )

        claim_set = self._claim_builder.build(
            evidence_set
        )

        if not claim_set.claims:
            raise ResearchPipelineError(
                "claim building produced no claims"
            )

        workspace = ResearchWorkspace(
            workspace_id=resolved_workspace_id,
            request=request,
            task_graph=task_graph,
            query_set=query_set,
            candidate_set=candidate_set,
            document_set=document_set,
            evidence_set=evidence_set,
            claim_set=claim_set,
            source_quality_evaluations=(
                source_quality_evaluations
            ),
            metadata={
                "pipeline": "single-research-agent",
                "read_candidate_count": str(
                    len(read_document_set.documents)
                ),
                "selected_document_count": str(
                    len(document_set.documents)
                ),
            },
        )

        report = self._synthesizer.synthesize(workspace)

        quality = self._quality_evaluator.evaluate(
            workspace=workspace,
            report=report,
        )

        return SingleResearchPipelineResult(
            workspace=workspace,
            report=report,
            quality=quality,
        )

    def _select_documents(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> tuple[
        ResearchSourceDocumentSet,
        list[ResearchSourceQualityEvaluation],
    ]:
        if self._document_selector is None:
            successful = document_set.successful_documents()
            return (
                document_set,
                [
                    self._source_quality_evaluator.evaluate(
                        document
                    )
                    for document in successful
                ],
            )

        selection = self._document_selector.select(
            document_set=document_set,
            evaluator=self._source_quality_evaluator,
        )

        return (
            selection.document_set,
            selection.evaluations,
        )
