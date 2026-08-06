"""Orchestration pipeline for one research agent."""

from __future__ import annotations

from typing import Protocol

from app.research.research_pipeline_error import ResearchPipelineError
from app.research.research_quality_evaluator import ResearchQualityEvaluator
from app.research.research_synthesizer import DeterministicResearchSynthesizer
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
)
from app.schemas.research_pipeline import SingleResearchPipelineResult
from app.schemas.research_quality import (
    ResearchQualityEvaluation,
    ResearchQualityIssue,
    ResearchQualityIssueCode,
    ResearchQualityIssueSeverity,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import ResearchSearchQuerySet
from app.schemas.research_source_candidate import ResearchSourceCandidateSet
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import ResearchSourceQualityEvaluation
from app.schemas.research_task import ResearchTaskGraph
from app.schemas.research_workspace import ResearchWorkspace


class ResearchRequestValidatorProtocol(Protocol):
    def validate(self, request: ResearchRequest) -> object: ...


class ResearchTaskDecomposerProtocol(Protocol):
    def decompose(self, request: ResearchRequest) -> ResearchTaskGraph: ...


class ResearchQueryPlannerProtocol(Protocol):
    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
    ) -> ResearchSearchQuerySet: ...


class ResearchSourceSearcherProtocol(Protocol):
    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet: ...


class ResearchSourceReaderProtocol(Protocol):
    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet: ...


class ResearchEvidenceExtractorProtocol(Protocol):
    def extract(
        self,
        document_set: ResearchSourceDocumentSet,
    ) -> ResearchEvidenceSet: ...


class ResearchClaimBuilderProtocol(Protocol):
    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet: ...


class ResearchSourceQualityEvaluatorProtocol(Protocol):
    def evaluate(
        self,
        document: ResearchSourceDocument,
    ) -> ResearchSourceQualityEvaluation: ...


class ResearchDocumentSelectionProtocol(Protocol):
    def select(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        evaluator: ResearchSourceQualityEvaluatorProtocol,
        query_set: ResearchSearchQuerySet | None = None,
    ) -> object: ...


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
        source_quality_evaluator: ResearchSourceQualityEvaluatorProtocol,
        document_selector: ResearchDocumentSelectionProtocol | None = None,
        synthesizer: DeterministicResearchSynthesizer | None = None,
        quality_evaluator: ResearchQualityEvaluator | None = None,
    ) -> None:
        self._request_validator = request_validator
        self._task_decomposer = task_decomposer
        self._query_planner = query_planner
        self._source_searcher = source_searcher
        self._source_reader = source_reader
        self._evidence_extractor = evidence_extractor
        self._claim_builder = claim_builder
        self._source_quality_evaluator = source_quality_evaluator
        self._document_selector = document_selector
        self._synthesizer = synthesizer or DeterministicResearchSynthesizer()
        self._quality_evaluator = quality_evaluator or ResearchQualityEvaluator()

    @property
    def source_searcher(self) -> ResearchSourceSearcherProtocol:
        return self._source_searcher

    @property
    def source_reader(self) -> ResearchSourceReaderProtocol:
        return self._source_reader

    @property
    def evidence_extractor(self) -> ResearchEvidenceExtractorProtocol:
        return self._evidence_extractor

    @property
    def source_quality_evaluator(
        self,
    ) -> ResearchSourceQualityEvaluatorProtocol:
        return self._source_quality_evaluator

    @property
    def document_selector(
        self,
    ) -> ResearchDocumentSelectionProtocol | None:
        return self._document_selector

    def run(
        self,
        request: ResearchRequest,
        *,
        workspace_id: str | None = None,
    ) -> SingleResearchPipelineResult:
        resolved_workspace_id = workspace_id or f"{request.request_id}-workspace"
        if not resolved_workspace_id.strip():
            raise ResearchPipelineError("workspace_id must not be blank")

        self._request_validator.validate(request)
        task_graph = self._task_decomposer.decompose(request)
        if not task_graph.tasks:
            raise ResearchPipelineError("task decomposition produced no tasks")

        query_set = self._query_planner.plan(
            request=request,
            task_graph=task_graph,
        )
        if not query_set.queries:
            raise ResearchPipelineError("query planning produced no queries")

        candidate_set = self._source_searcher.search(query_set)
        if not candidate_set.candidates:
            raise ResearchPipelineError("source search produced no candidates")

        read_document_set = self._source_reader.read(candidate_set)
        if not read_document_set.successful_documents():
            raise ResearchPipelineError(
                "source reading produced no readable documents"
            )

        (
            document_set,
            evidence_set,
            source_quality_evaluations,
            evidence_attempted_document_count,
            no_evidence_document_count,
        ) = self._select_documents_with_evidence(
            read_document_set,
            query_set=query_set,
            maximum_sources=request.maximum_sources,
        )
        if not document_set.successful_documents():
            raise ResearchPipelineError(
                "source selection produced no evidence-bearing documents"
            )
        if not evidence_set.evidence:
            raise ResearchPipelineError(
                "evidence extraction produced no evidence"
            )

        claim_set = self._claim_builder.build(evidence_set)
        if not claim_set.claims:
            raise ResearchPipelineError("claim building produced no claims")

        workspace = ResearchWorkspace(
            workspace_id=resolved_workspace_id,
            request=request,
            task_graph=task_graph,
            query_set=query_set,
            candidate_set=candidate_set,
            document_set=document_set,
            evidence_set=evidence_set,
            claim_set=claim_set,
            source_quality_evaluations=source_quality_evaluations,
            metadata={
                "pipeline": "single-research-agent",
                "read_candidate_count": str(len(read_document_set.documents)),
                "evidence_attempted_document_count": str(
                    evidence_attempted_document_count
                ),
                "selected_document_count": str(len(document_set.documents)),
                "evidence_source_count": str(len(document_set.documents)),
                "backfilled_document_count": str(
                    max(
                        0,
                        evidence_attempted_document_count
                        - len(document_set.documents),
                    )
                ),
                "no_evidence_document_count": str(
                    no_evidence_document_count
                ),
            },
        )
        report = self._synthesizer.synthesize(workspace)
        quality = self._quality_evaluator.evaluate(
            workspace=workspace,
            report=report,
        )
        if self._document_selector is not None:
            quality = self._apply_minimum_evidence_source_gate(
                quality=quality,
                actual_sources=report.source_count,
                maximum_sources=request.maximum_sources,
            )
        return SingleResearchPipelineResult(
            workspace=workspace,
            report=report,
            quality=quality,
        )

    def _select_documents_with_evidence(
        self,
        document_set: ResearchSourceDocumentSet,
        *,
        query_set: ResearchSearchQuerySet,
        maximum_sources: int,
    ) -> tuple[
        ResearchSourceDocumentSet,
        ResearchEvidenceSet,
        list[ResearchSourceQualityEvaluation],
        int,
        int,
    ]:
        if self._document_selector is None:
            selected, evaluations = self._select_documents(
                document_set,
                query_set=query_set,
            )
            evidence_set = self._evidence_extractor.extract(selected)
            evidence_document_ids = {
                item.document_id.strip().casefold()
                for item in evidence_set.evidence
            }
            final_documents = [
                document
                for document in selected.successful_documents()
                if document.document_id.strip().casefold()
                in evidence_document_ids
            ]
            final_document_set = ResearchSourceDocumentSet(
                request_id=selected.request_id,
                documents=final_documents,
            )
            return (
                final_document_set,
                ResearchEvidenceSet(
                    request_id=evidence_set.request_id,
                    document_set=final_document_set,
                    evidence=evidence_set.evidence,
                ),
                [
                    evaluation
                    for evaluation in evaluations
                    if (
                        evaluation.document.document_id
                        .strip()
                        .casefold()
                        in evidence_document_ids
                    )
                ],
                len(selected.successful_documents()),
                len(selected.successful_documents()) - len(final_documents),
            )

        rank = getattr(self._document_selector, "rank", None)
        if rank is None:
            selected, evaluations = self._select_documents(
                document_set,
                query_set=query_set,
            )
            ranked_documents = selected.successful_documents()
            ranked_evaluations = evaluations
        else:
            selection = rank(
                document_set=document_set,
                evaluator=self._source_quality_evaluator,
                query_set=query_set,
            )
            ranked_documents = selection.document_set.successful_documents()
            ranked_evaluations = selection.evaluations

        evaluation_by_document_id = {
            evaluation.document.document_id.strip().casefold(): evaluation
            for evaluation in ranked_evaluations
        }
        selected_documents: list[ResearchSourceDocument] = []
        selected_evidence: list[ResearchEvidence] = []
        selected_evaluations: list[ResearchSourceQualityEvaluation] = []
        attempted_count = 0
        no_evidence_count = 0
        seen_urls: set[str] = set()

        for document in ranked_documents:
            if len(selected_documents) >= maximum_sources:
                break

            normalized_url = document.candidate.normalized_url()
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            attempted_count += 1

            single_document_set = ResearchSourceDocumentSet(
                request_id=document_set.request_id,
                documents=[document],
            )
            extracted = self._evidence_extractor.extract(single_document_set)
            if not extracted.evidence:
                no_evidence_count += 1
                continue

            selected_documents.append(document)
            selected_evidence.extend(extracted.ordered_evidence())
            evaluation = evaluation_by_document_id.get(
                document.document_id.strip().casefold()
            )
            if evaluation is not None:
                selected_evaluations.append(evaluation)

        final_document_set = ResearchSourceDocumentSet(
            request_id=document_set.request_id,
            documents=selected_documents,
        )
        return (
            final_document_set,
            ResearchEvidenceSet(
                request_id=document_set.request_id,
                document_set=final_document_set,
                evidence=selected_evidence,
            ),
            selected_evaluations,
            attempted_count,
            no_evidence_count,
        )

    @staticmethod
    def _apply_minimum_evidence_source_gate(
        *,
        quality: ResearchQualityEvaluation,
        actual_sources: int,
        maximum_sources: int,
    ) -> ResearchQualityEvaluation:
        required_sources = min(2, maximum_sources)
        if actual_sources >= required_sources:
            return quality

        retained_issues = [
            issue
            for issue in quality.issues
            if issue.code
            is not ResearchQualityIssueCode.LOW_SOURCE_DIVERSITY
        ]
        retained_issues.append(
            ResearchQualityIssue(
                code=ResearchQualityIssueCode.LOW_SOURCE_DIVERSITY,
                severity=ResearchQualityIssueSeverity.ERROR,
                message=(
                    "The report contains evidence from fewer "
                    "independent sources than required."
                ),
                related_ids=[],
            )
        )
        return quality.model_copy(
            update={
                "issues": retained_issues,
                "metadata": {
                    **quality.metadata,
                    "minimum_evidence_sources": str(required_sources),
                    "actual_evidence_sources": str(actual_sources),
                    "maximum_sources": str(maximum_sources),
                },
            }
        )

    def _select_documents(
        self,
        document_set: ResearchSourceDocumentSet,
        *,
        query_set: ResearchSearchQuerySet,
    ) -> tuple[
        ResearchSourceDocumentSet,
        list[ResearchSourceQualityEvaluation],
    ]:
        if self._document_selector is None:
            successful = document_set.successful_documents()
            return (
                document_set,
                [
                    self._source_quality_evaluator.evaluate(document)
                    for document in successful
                ],
            )

        selection = self._document_selector.select(
            document_set=document_set,
            evaluator=self._source_quality_evaluator,
            query_set=query_set,
        )
        return selection.document_set, selection.evaluations
