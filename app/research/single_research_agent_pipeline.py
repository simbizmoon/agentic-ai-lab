"""Orchestration pipeline for one research agent."""

from __future__ import annotations

import time
from typing import Protocol

from app.research.research_citation_verifier_executor import (
    ResearchCitationVerification,
)
from app.research.research_pipeline_error import ResearchPipelineError
from app.research.research_quality_evaluator import ResearchQualityEvaluator
from app.research.research_synthesizer import DeterministicResearchSynthesizer
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageLevel,
)
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_claim_relevance_evaluation import (
    ResearchClaimRelevanceEvaluation,
)
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
from app.schemas.research_run_metrics import ResearchRunMetrics, ResearchStageMetrics
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


class SemanticCitationVerifierProtocol(Protocol):
    """Verify semantic support for research citations."""

    def verify(
        self,
        *,
        claim_set: ResearchClaimSet,
        evidence_set: ResearchEvidenceSet,
    ) -> list[ResearchCitationVerification]: ...


class ClaimRelevanceEvaluationServiceProtocol(Protocol):
    # Evaluate research claims against the request.

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> list[ResearchClaimRelevanceEvaluation]: ...


class AnswerCoverageEvaluationServiceProtocol(Protocol):
    """Evaluate final claim-set coverage against the request."""

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> ResearchAnswerCoverageEvaluation: ...


class CoverageGapResearchQueryPlannerProtocol(Protocol):
    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
        existing_query_set: ResearchSearchQuerySet,
        coverage_evaluation: ResearchAnswerCoverageEvaluation,
    ) -> ResearchSearchQuerySet: ...


class SupplementalResearchQueryPlannerProtocol(Protocol):
    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
        initial_query_set: ResearchSearchQuerySet,
    ) -> ResearchSearchQuerySet: ...


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
        supplemental_query_planner: (
            SupplementalResearchQueryPlannerProtocol | None
        ) = None,
        synthesizer: DeterministicResearchSynthesizer | None = None,
        quality_evaluator: ResearchQualityEvaluator | None = None,
        semantic_citation_verifier: (
            SemanticCitationVerifierProtocol | None
        ) = None,
        claim_relevance_evaluator: (
            ClaimRelevanceEvaluationServiceProtocol | None
        ) = None,
        answer_coverage_evaluator: (
            AnswerCoverageEvaluationServiceProtocol | None
        ) = None,
        coverage_gap_query_planner: (
            CoverageGapResearchQueryPlannerProtocol | None
        ) = None,
        collect_run_metrics: bool = False,
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
        self._supplemental_query_planner = (
            supplemental_query_planner
        )
        self._synthesizer = synthesizer or DeterministicResearchSynthesizer()
        self._quality_evaluator = quality_evaluator or ResearchQualityEvaluator()
        self._semantic_citation_verifier = (
            semantic_citation_verifier
        )
        self._claim_relevance_evaluator = (
            claim_relevance_evaluator
        )
        self._answer_coverage_evaluator = (
            answer_coverage_evaluator
        )
        self._coverage_gap_query_planner = (
            coverage_gap_query_planner
        )
        self._collect_run_metrics = collect_run_metrics

    @property
    def semantic_citation_verifier(
        self,
    ) -> SemanticCitationVerifierProtocol | None:
        """Return the optional semantic citation verifier."""

        return self._semantic_citation_verifier

    @property
    def claim_relevance_evaluator(
        self,
    ) -> ClaimRelevanceEvaluationServiceProtocol | None:
        return self._claim_relevance_evaluator

    @property
    def answer_coverage_evaluator(
        self,
    ) -> AnswerCoverageEvaluationServiceProtocol | None:
        """Return the optional answer coverage evaluator."""

        return self._answer_coverage_evaluator

    @property
    def coverage_gap_query_planner(
        self,
    ) -> CoverageGapResearchQueryPlannerProtocol | None:
        return self._coverage_gap_query_planner

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

    @property
    def supplemental_query_planner(
        self,
    ) -> SupplementalResearchQueryPlannerProtocol | None:
        return self._supplemental_query_planner

    def run(
        self,
        request: ResearchRequest,
        *,
        workspace_id: str | None = None,
    ) -> SingleResearchPipelineResult:
        run_started_at = time.perf_counter()
        resolved_workspace_id = workspace_id or f"{request.request_id}-workspace"
        if not resolved_workspace_id.strip():
            raise ResearchPipelineError("workspace_id must not be blank")

        evidence_cache: dict[
            tuple[str, str, str],
            list[ResearchEvidence],
        ] = {}

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

        read_started_at = time.perf_counter()
        read_document_set = self._source_reader.read(candidate_set)
        round_1_source_read_elapsed_seconds = max(0.0, time.perf_counter() - read_started_at)
        if not read_document_set.successful_documents():
            raise ResearchPipelineError(
                "source reading produced no readable documents"
            )

        self._reset_component_usage(
            self._evidence_extractor
        )
        evidence_started_at = time.perf_counter()
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
            evidence_cache=evidence_cache,
        )

        round_1_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - evidence_started_at)
        replanning_metadata: dict[str, str] = {}
        supplemental_search_blocked_by_budget = False

        if self._supplemental_query_planner is not None:
            search_round_count = 1
            replanning_triggered = False
            supplemental_query_count = 0
            supplemental_candidate_count = 0
            deduplicated_candidate_count = 0

            if self._should_run_supplemental_search(
                document_set=document_set,
                maximum_sources=request.maximum_sources,
            ):
                replanning_triggered = True
                search_round_count = 2

                supplemental_query_set = (
                    self._supplemental_query_planner.plan(
                        request=request,
                        task_graph=task_graph,
                        initial_query_set=query_set,
                    )
                )
                supplemental_query_count = len(
                    supplemental_query_set.queries
                )

                search_usage_before = (
                    self._search_usage_snapshot()
                )

                raw_supplemental_candidates = (
                    self._source_searcher.search(
                        supplemental_query_set
                    )
                )

                search_usage_after = (
                    self._search_usage_snapshot()
                )
                supplemental_search_blocked_by_budget = (
                    self._supplemental_search_was_blocked(
                        before=search_usage_before,
                        after=search_usage_after,
                    )
                )

                (
                    supplemental_candidate_set,
                    deduplicated_candidate_count,
                ) = self._novel_candidates(
                    existing=candidate_set,
                    supplemental=raw_supplemental_candidates,
                )

                supplemental_candidate_count = len(
                    supplemental_candidate_set.candidates
                )

                query_set = self._merge_query_sets(
                    initial=query_set,
                    supplemental=supplemental_query_set,
                )

                candidate_set = self._merge_candidate_sets(
                    initial=candidate_set,
                    supplemental=supplemental_candidate_set,
                    query_set=query_set,
                )

                if supplemental_candidate_set.candidates:
                    supplemental_document_set = (
                        self._source_reader.read(
                            supplemental_candidate_set
                        )
                    )

                    read_document_set = (
                        self._merge_document_sets(
                            initial=read_document_set,
                            supplemental=(
                                supplemental_document_set
                            ),
                        )
                    )

                    supplemental_evidence_started_at = (
                        time.perf_counter()
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
                        maximum_sources=(
                            request.maximum_sources
                        ),
                        evidence_cache=evidence_cache,
                    )

                    round_1_evidence_extraction_elapsed_seconds += (
                        max(
                            0.0,
                            time.perf_counter()
                            - supplemental_evidence_started_at,
                        )
                    )

            replanning_metadata = {
                "search_round_count": str(
                    search_round_count
                ),
                "replanning_triggered": str(
                    replanning_triggered
                ).casefold(),
                "supplemental_query_count": str(
                    supplemental_query_count
                ),
                "supplemental_candidate_count": str(
                    supplemental_candidate_count
                ),
                "deduplicated_candidate_count": str(
                    deduplicated_candidate_count
                ),
                "supplemental_search_blocked_by_budget": (
                    str(
                        supplemental_search_blocked_by_budget
                    ).casefold()
                ),
            }

        round_1_evidence_semantic = self._component_usage_metrics(
            self._evidence_extractor
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
        round_1_claim_generation = self._component_usage_metrics(self._claim_builder)
        if not claim_set.claims:
            raise ResearchPipelineError("claim building produced no claims")

        citation_verifications: list[
            ResearchCitationVerification
        ] = []

        if self._semantic_citation_verifier is not None:
            citation_verifications = (
                self._semantic_citation_verifier.verify(
                    claim_set=claim_set,
                    evidence_set=evidence_set,
                )
            )

        round_1_citation_verification = self._component_usage_metrics(self._semantic_citation_verifier)

        claim_relevance_evaluations: list[
            ResearchClaimRelevanceEvaluation
        ] = []

        if self._claim_relevance_evaluator is not None:
            claim_relevance_evaluations = (
                self._claim_relevance_evaluator.evaluate(
                    request=request,
                    claim_set=claim_set,
                )
            )

        round_1_claim_relevance = self._component_usage_metrics(self._claim_relevance_evaluator)

        answer_coverage_evaluation: (
            ResearchAnswerCoverageEvaluation | None
        ) = None

        if self._answer_coverage_evaluator is not None:
            answer_coverage_evaluation = (
                self._answer_coverage_evaluator.evaluate(
                    request=request,
                    claim_set=claim_set,
                )
            )

        round_1_answer_coverage = self._component_usage_metrics(self._answer_coverage_evaluator)
        coverage_source_read_elapsed_seconds = 0.0
        coverage_evidence_extraction_elapsed_seconds = 0.0
        coverage_evidence_semantic = ResearchStageMetrics()
        coverage_claim_generation = ResearchStageMetrics()
        coverage_citation_verification = ResearchStageMetrics()
        coverage_claim_relevance = ResearchStageMetrics()
        coverage_answer_coverage = ResearchStageMetrics()

        coverage_replanning_metadata: dict[str, str] = {}

        if answer_coverage_evaluation is not None:
            coverage_replanning_metadata = {
                "coverage_replanning_triggered": "false",
                "coverage_replanning_attempt_count": "0",
                "coverage_replanning_query_count": "0",
                "coverage_replanning_candidate_count": "0",
                "coverage_replanning_novel_candidate_count": "0",
                "coverage_replanning_new_document_count": "0",
                "coverage_replanning_novel_evidence_count": "0",
                "coverage_replanning_adopted_novel_source_count": "0",
                "coverage_replanning_adopted_novel_evidence_count": "0",
                "coverage_replanning_substituted_source_count": "0",
                "coverage_replanning_substitution_decision": "not_attempted",
                "coverage_replanning_new_evidence_count": "0",
                "coverage_replanning_claims_rebuilt": "false",
                "coverage_replanning_blocked_by_budget": "false",
                "coverage_initial_level": (
                    answer_coverage_evaluation.coverage_level.value
                ),
                "coverage_final_level": (
                    answer_coverage_evaluation.coverage_level.value
                ),
            }

        should_replan_coverage = (
            answer_coverage_evaluation is not None
            and self._coverage_gap_query_planner is not None
            and answer_coverage_evaluation.coverage_level
            in {
                AnswerCoverageLevel.PARTIALLY_COVERED,
                AnswerCoverageLevel.INSUFFICIENT,
            }
            and bool(answer_coverage_evaluation.missing_aspects)
        )

        if should_replan_coverage:
            coverage_replanning_metadata["coverage_replanning_triggered"] = "true"
            coverage_replanning_metadata["coverage_replanning_attempt_count"] = "1"

            coverage_query_set = self._coverage_gap_query_planner.plan(
                request=request,
                task_graph=task_graph,
                existing_query_set=query_set,
                coverage_evaluation=answer_coverage_evaluation,
            )
            coverage_replanning_metadata["coverage_replanning_query_count"] = str(
                len(coverage_query_set.queries)
            )

            search_usage_before = self._search_usage_snapshot()
            raw_coverage_candidates = self._source_searcher.search(coverage_query_set)
            search_usage_after = self._search_usage_snapshot()
            coverage_blocked = self._supplemental_search_was_blocked(
                before=search_usage_before,
                after=search_usage_after,
            )
            coverage_replanning_metadata["coverage_replanning_blocked_by_budget"] = (
                str(coverage_blocked).casefold()
            )
            coverage_replanning_metadata["coverage_replanning_candidate_count"] = str(
                len(raw_coverage_candidates.candidates)
            )

            novel_coverage_candidates, _ = self._novel_candidates(
                existing=candidate_set,
                supplemental=raw_coverage_candidates,
            )
            coverage_replanning_metadata[
                "coverage_replanning_novel_candidate_count"
            ] = str(len(novel_coverage_candidates.candidates))

            query_set = self._merge_query_sets(
                initial=query_set,
                supplemental=coverage_query_set,
            )
            candidate_set = self._merge_candidate_sets(
                initial=candidate_set,
                supplemental=novel_coverage_candidates,
                query_set=query_set,
            )

            if novel_coverage_candidates.candidates:
                coverage_read_started_at = time.perf_counter()
                coverage_document_set = self._source_reader.read(
                    novel_coverage_candidates
                )
                coverage_source_read_elapsed_seconds = max(0.0, time.perf_counter() - coverage_read_started_at)
                new_documents = coverage_document_set.successful_documents()
                coverage_replanning_metadata[
                    "coverage_replanning_new_document_count"
                ] = str(len(new_documents))

                if new_documents:
                    previous_evidence_ids = {
                        item.evidence_id.strip().casefold()
                        for item in evidence_set.evidence
                    }
                    merged_read_document_set = self._merge_document_sets(
                        initial=read_document_set,
                        supplemental=coverage_document_set,
                    )
                    self._reset_component_usage(
                        self._evidence_extractor
                    )
                    coverage_evidence_started_at = time.perf_counter()
                    (
                        novel_coverage_document_set,
                        novel_coverage_evidence_set,
                        novel_coverage_quality_evaluations,
                        _,
                        _,
                    ) = self._select_documents_with_evidence(
                        coverage_document_set,
                        query_set=query_set,
                        maximum_sources=request.maximum_sources,
                        evidence_cache=evidence_cache,
                    )
                    coverage_replanning_metadata[
                        "coverage_replanning_novel_evidence_count"
                    ] = str(
                        len(novel_coverage_evidence_set.evidence)
                    )
                    (
                        candidate_document_set,
                        candidate_evidence_set,
                        candidate_quality_evaluations,
                        candidate_attempted_count,
                        candidate_no_evidence_count,
                    ) = self._select_documents_with_evidence(
                        merged_read_document_set,
                        query_set=query_set,
                        maximum_sources=request.maximum_sources,
                        evidence_cache=evidence_cache,
                    )
                    coverage_evidence_extraction_elapsed_seconds = max(0.0, time.perf_counter() - coverage_evidence_started_at)
                    coverage_evidence_semantic = self._component_usage_metrics(
                        self._evidence_extractor
                    )
                    new_evidence_ids = {
                        item.evidence_id.strip().casefold()
                        for item in candidate_evidence_set.evidence
                    } - previous_evidence_ids

                    if (
                        not new_evidence_ids
                        and novel_coverage_evidence_set.evidence
                        and novel_coverage_document_set.documents
                        and document_set.documents
                    ):
                        adopted_novel_document = (
                            novel_coverage_document_set.documents[0]
                        )
                        adopted_source_id = (
                            adopted_novel_document.candidate.source_id
                            .strip()
                            .casefold()
                        )
                        adopted_novel_evidence = [
                            item
                            for item in novel_coverage_evidence_set.evidence
                            if item.source_id.strip().casefold()
                            == adopted_source_id
                        ]
                        if adopted_novel_evidence:
                            retained_documents = list(
                                document_set.documents
                            )
                            substituted_existing_document_ids: set[str] = set()
                            if (
                                len(retained_documents)
                                >= request.maximum_sources
                            ):
                                removed_document = retained_documents.pop()
                                substituted_existing_document_ids.add(
                                    removed_document.document_id
                                    .strip()
                                    .casefold()
                                )
                                coverage_replanning_metadata[
                                    "coverage_replanning_substituted_source_count"
                                ] = "1"
                            retained_documents.append(
                                adopted_novel_document
                            )
                            candidate_document_set = ResearchSourceDocumentSet(
                                request_id=document_set.request_id,
                                documents=retained_documents,
                            )
                            candidate_evidence_set = ResearchEvidenceSet(
                                request_id=evidence_set.request_id,
                                document_set=candidate_document_set,
                                evidence=[
                                    item
                                    for item in evidence_set.evidence
                                    if (
                                        item.document_id.strip().casefold()
                                        not in substituted_existing_document_ids
                                    )
                                ]
                                + adopted_novel_evidence,
                            )
                            retained_document_ids = {
                                item.document_id.strip().casefold()
                                for item in retained_documents
                            }
                            adopted_quality = [
                                evaluation
                                for evaluation in novel_coverage_quality_evaluations
                                if (
                                    evaluation.document.document_id
                                    .strip()
                                    .casefold()
                                    in retained_document_ids
                                )
                            ]
                            candidate_quality_evaluations = [
                                evaluation
                                for evaluation in source_quality_evaluations
                                if (
                                    evaluation.document.document_id
                                    .strip()
                                    .casefold()
                                    in retained_document_ids
                                )
                            ] + adopted_quality
                            new_evidence_ids = {
                                item.evidence_id.strip().casefold()
                                for item in adopted_novel_evidence
                            }
                            coverage_replanning_metadata[
                                "coverage_replanning_adopted_novel_source_count"
                            ] = "1"
                            coverage_replanning_metadata[
                                "coverage_replanning_adopted_novel_evidence_count"
                            ] = str(len(adopted_novel_evidence))
                    coverage_replanning_metadata[
                        "coverage_replanning_new_evidence_count"
                    ] = str(len(new_evidence_ids))

                    if new_evidence_ids:
                        previous_document_set = document_set
                        previous_evidence_set = evidence_set
                        previous_source_quality_evaluations = list(
                            source_quality_evaluations
                        )
                        previous_claim_set = claim_set
                        previous_citation_verifications = list(
                            citation_verifications
                        )
                        previous_claim_relevance_evaluations = list(
                            claim_relevance_evaluations
                        )
                        previous_answer_coverage_evaluation = (
                            answer_coverage_evaluation
                        )
                        previous_evidence_attempted_document_count = (
                            evidence_attempted_document_count
                        )
                        previous_no_evidence_document_count = (
                            no_evidence_document_count
                        )

                        read_document_set = merged_read_document_set
                        document_set = candidate_document_set
                        evidence_set = candidate_evidence_set
                        source_quality_evaluations = candidate_quality_evaluations
                        evidence_attempted_document_count = candidate_attempted_count
                        no_evidence_document_count = candidate_no_evidence_count

                        candidate_evidence_by_id = {
                            item.evidence_id.strip().casefold(): item
                            for item in evidence_set.evidence
                        }
                        previous_evidence_reusable = all(
                            candidate_evidence_by_id.get(
                                item.evidence_id.strip().casefold()
                            ) == item
                            for item in previous_evidence_set.evidence
                        )
                        incremental_build = getattr(
                            self._claim_builder,
                            "build_incremental",
                            None,
                        )
                        use_incremental = (
                            previous_evidence_reusable
                            and incremental_build is not None
                        )
                        coverage_replanning_metadata[
                            "coverage_replanning_incremental_reuse"
                        ] = str(use_incremental).casefold()

                        if use_incremental:
                            new_evidence = [
                                item
                                for item in evidence_set.ordered_evidence()
                                if item.evidence_id.strip().casefold() in new_evidence_ids
                            ]
                            incremental_evidence_set = ResearchEvidenceSet(
                                request_id=evidence_set.request_id,
                                document_set=document_set,
                                evidence=new_evidence,
                            )
                            incremental_claim_set = incremental_build(
                                incremental_evidence_set,
                                start_position=len(previous_claim_set.claims) + 1,
                            )
                            coverage_claim_generation = self._component_usage_metrics(
                                self._claim_builder
                            )
                            claim_set = ResearchClaimSet(
                                request_id=evidence_set.request_id,
                                evidence_set=evidence_set,
                                claims=[
                                    *previous_claim_set.claims,
                                    *incremental_claim_set.claims,
                                ],
                            )
                            coverage_replanning_metadata[
                                "coverage_replanning_incremental_claim_count"
                            ] = str(len(incremental_claim_set.claims))

                            citation_verifications = list(
                                previous_citation_verifications
                            )
                            if (
                                self._semantic_citation_verifier is not None
                                and incremental_claim_set.claims
                            ):
                                citation_verifications.extend(
                                    self._semantic_citation_verifier.verify(
                                        claim_set=incremental_claim_set,
                                        evidence_set=evidence_set,
                                    )
                                )
                            coverage_citation_verification = self._component_usage_metrics(
                                self._semantic_citation_verifier
                            )

                            claim_relevance_evaluations = list(
                                previous_claim_relevance_evaluations
                            )
                            if (
                                self._claim_relevance_evaluator is not None
                                and incremental_claim_set.claims
                            ):
                                claim_relevance_evaluations.extend(
                                    self._claim_relevance_evaluator.evaluate(
                                        request=request,
                                        claim_set=incremental_claim_set,
                                    )
                                )
                            coverage_claim_relevance = self._component_usage_metrics(
                                self._claim_relevance_evaluator
                            )
                        else:
                            claim_set = self._claim_builder.build(evidence_set)
                            coverage_claim_generation = self._component_usage_metrics(
                                self._claim_builder
                            )
                            citation_verifications = []
                            if self._semantic_citation_verifier is not None:
                                citation_verifications = self._semantic_citation_verifier.verify(
                                    claim_set=claim_set,
                                    evidence_set=evidence_set,
                                )
                            coverage_citation_verification = self._component_usage_metrics(
                                self._semantic_citation_verifier
                            )
                            claim_relevance_evaluations = []
                            if self._claim_relevance_evaluator is not None:
                                claim_relevance_evaluations = self._claim_relevance_evaluator.evaluate(
                                    request=request,
                                    claim_set=claim_set,
                                )
                            coverage_claim_relevance = self._component_usage_metrics(
                                self._claim_relevance_evaluator
                            )

                        if not claim_set.claims:
                            raise ResearchPipelineError(
                                "coverage replanning produced no claims"
                            )
                        coverage_replanning_metadata[
                            "coverage_replanning_claims_rebuilt"
                        ] = "true"

                        if self._answer_coverage_evaluator is not None:
                            candidate_answer_coverage_evaluation = (
                                self._answer_coverage_evaluator.evaluate(
                                    request=request,
                                    claim_set=claim_set,
                                )
                            )
                            coverage_answer_coverage = self._component_usage_metrics(
                                self._answer_coverage_evaluator
                            )

                            previous_level = (
                                previous_answer_coverage_evaluation.coverage_level
                                if previous_answer_coverage_evaluation is not None
                                else None
                            )
                            candidate_level = (
                                candidate_answer_coverage_evaluation.coverage_level
                            )
                            level_rank = {
                                AnswerCoverageLevel.INSUFFICIENT: 0,
                                AnswerCoverageLevel.PARTIALLY_COVERED: 1,
                                AnswerCoverageLevel.FULLY_COVERED: 2,
                            }
                            substitution_improved = (
                                previous_level is None
                                or level_rank[candidate_level]
                                > level_rank[previous_level]
                            )

                            if substitution_improved:
                                answer_coverage_evaluation = (
                                    candidate_answer_coverage_evaluation
                                )
                                coverage_replanning_metadata[
                                    "coverage_replanning_substitution_decision"
                                ] = "accepted_level_improvement"
                            else:
                                document_set = previous_document_set
                                evidence_set = previous_evidence_set
                                source_quality_evaluations = (
                                    previous_source_quality_evaluations
                                )
                                claim_set = previous_claim_set
                                citation_verifications = (
                                    previous_citation_verifications
                                )
                                claim_relevance_evaluations = (
                                    previous_claim_relevance_evaluations
                                )
                                answer_coverage_evaluation = (
                                    previous_answer_coverage_evaluation
                                )
                                evidence_attempted_document_count = (
                                    previous_evidence_attempted_document_count
                                )
                                no_evidence_document_count = (
                                    previous_no_evidence_document_count
                                )
                                coverage_replanning_metadata[
                                    "coverage_replanning_substitution_decision"
                                ] = "rejected_no_level_improvement"

                            coverage_replanning_metadata[
                                "coverage_final_level"
                            ] = answer_coverage_evaluation.coverage_level.value

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
                **replanning_metadata,
                **coverage_replanning_metadata,
                **self._search_budget_metadata(),
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
        run_metrics = None
        if self._collect_run_metrics:
            run_metrics = ResearchRunMetrics(
                total_elapsed_seconds=max(
                    0.0,
                    time.perf_counter() - run_started_at,
                ),
                **self._search_run_metric_values(),
                round_1_source_read_elapsed_seconds=(
                    round_1_source_read_elapsed_seconds
                ),
                round_1_evidence_extraction_elapsed_seconds=(
                    round_1_evidence_extraction_elapsed_seconds
                ),
                round_1_evidence_semantic=round_1_evidence_semantic,
                round_1_claim_generation=round_1_claim_generation,
                round_1_citation_verification=(
                    round_1_citation_verification
                ),
                round_1_claim_relevance=round_1_claim_relevance,
                round_1_answer_coverage=round_1_answer_coverage,
                coverage_source_read_elapsed_seconds=(
                    coverage_source_read_elapsed_seconds
                ),
                coverage_evidence_extraction_elapsed_seconds=(
                    coverage_evidence_extraction_elapsed_seconds
                ),
                coverage_evidence_semantic=coverage_evidence_semantic,
                coverage_claim_generation=coverage_claim_generation,
                coverage_citation_verification=(
                    coverage_citation_verification
                ),
                coverage_claim_relevance=coverage_claim_relevance,
                coverage_answer_coverage=coverage_answer_coverage,
            )

        return SingleResearchPipelineResult(
            workspace=workspace,
            report=report,
            quality=quality,
            citation_verifications=(
                citation_verifications
            ),
            claim_relevance_evaluations=(
                claim_relevance_evaluations
            ),
            answer_coverage_evaluation=(
                answer_coverage_evaluation
            ),
            run_metrics=run_metrics,
        )

    @staticmethod
    def _reset_component_usage(component: object | None) -> None:
        if component is None:
            return
        reset_usage = getattr(component, "reset_usage", None)
        if reset_usage is not None:
            reset_usage()

    @staticmethod
    def _component_usage_metrics(component: object | None) -> ResearchStageMetrics:
        if component is None:
            return ResearchStageMetrics()
        usage = getattr(component, "last_usage", None)
        if usage is None:
            return ResearchStageMetrics()
        return ResearchStageMetrics(
            call_count=int(getattr(usage, "attempts", 0)),
            recorded_tokens=int(getattr(usage, "recorded_tokens", 0)),
            elapsed_seconds=float(getattr(usage, "elapsed_seconds", 0.0)),
        )

    def _search_run_metric_values(self) -> dict[str, object]:
        usage = getattr(self._source_searcher, "search_usage", None)
        if usage is None:
            return {}
        return {
            "search_provider_calls": usage.provider_call_count,
            "search_credits_used": usage.credit_used,
            "search_elapsed_seconds": usage.latency_used_ms / 1000.0,
        }

    def _search_usage_snapshot(
        self,
    ) -> tuple[int, int] | None:
        """Return call and blocked counts when available."""

        usage = getattr(
            self._source_searcher,
            "search_usage",
            None,
        )

        if usage is None:
            return None

        return (
            usage.provider_call_count,
            usage.blocked_query_count,
        )

    @staticmethod
    def _supplemental_search_was_blocked(
        *,
        before: tuple[int, int] | None,
        after: tuple[int, int] | None,
    ) -> bool:
        """Return whether budget blocked the supplemental call."""

        if before is None or after is None:
            return False

        before_calls, before_blocked = before
        after_calls, after_blocked = after

        return (
            after_calls == before_calls
            and after_blocked > before_blocked
        )

    def _search_budget_metadata(self) -> dict[str, str]:
        """Return bounded search usage metadata when available."""

        budget = getattr(
            self._source_searcher,
            "search_budget",
            None,
        )
        usage = getattr(
            self._source_searcher,
            "search_usage",
            None,
        )

        if budget is None or usage is None:
            return {}

        exhausted = (
            usage.provider_call_count
            >= budget.maximum_provider_calls
            or usage.credit_used
            >= budget.maximum_credits
            or usage.latency_used_ms
            >= budget.maximum_latency_ms
            or usage.blocked_query_count > 0
        )

        return {
            "search_provider_call_limit": str(
                budget.maximum_provider_calls
            ),
            "search_provider_call_count": str(
                usage.provider_call_count
            ),
            "search_credit_limit": str(
                budget.maximum_credits
            ),
            "search_credit_used": str(
                usage.credit_used
            ),
            "search_credit_unreported_call_count": str(
                usage.unreported_credit_call_count
            ),
            "search_latency_limit_ms": str(
                budget.maximum_latency_ms
            ),
            "search_latency_used_ms": str(
                usage.latency_used_ms
            ),
            "search_budget_exhausted": str(
                exhausted
            ).casefold(),
            "search_blocked_query_count": str(
                usage.blocked_query_count
            ),
        }

    def _should_run_supplemental_search(
        self,
        *,
        document_set: ResearchSourceDocumentSet,
        maximum_sources: int,
    ) -> bool:
        if self._supplemental_query_planner is None:
            return False

        if self._document_selector is None:
            return False

        if maximum_sources <= 1:
            return False

        required_sources = min(2, maximum_sources)

        return (
            len(document_set.successful_documents())
            < required_sources
        )

    @staticmethod
    def _merge_query_sets(
        *,
        initial: ResearchSearchQuerySet,
        supplemental: ResearchSearchQuerySet,
    ) -> ResearchSearchQuerySet:
        return ResearchSearchQuerySet(
            request_id=initial.request_id,
            task_graph=initial.task_graph,
            queries=[
                *initial.queries,
                *supplemental.queries,
            ],
        )

    @staticmethod
    def _novel_candidates(
        *,
        existing: ResearchSourceCandidateSet,
        supplemental: ResearchSourceCandidateSet,
    ) -> tuple[ResearchSourceCandidateSet, int]:
        seen_source_ids = {
            candidate.source_id.strip().casefold()
            for candidate in existing.candidates
        }
        seen_urls = {
            candidate.normalized_url()
            for candidate in existing.candidates
        }

        novel_candidates = []
        duplicate_count = 0

        for candidate in supplemental.ordered_candidates():
            source_key = (
                candidate.source_id.strip().casefold()
            )
            url_key = candidate.normalized_url()

            if (
                source_key in seen_source_ids
                or url_key in seen_urls
            ):
                duplicate_count += 1
                continue

            seen_source_ids.add(source_key)
            seen_urls.add(url_key)
            novel_candidates.append(candidate)

        return (
            ResearchSourceCandidateSet(
                request_id=supplemental.request_id,
                query_set=supplemental.query_set,
                candidates=novel_candidates,
            ),
            duplicate_count,
        )

    @staticmethod
    def _merge_candidate_sets(
        *,
        initial: ResearchSourceCandidateSet,
        supplemental: ResearchSourceCandidateSet,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        return ResearchSourceCandidateSet(
            request_id=initial.request_id,
            query_set=query_set,
            candidates=[
                *initial.candidates,
                *supplemental.candidates,
            ],
        )

    @staticmethod
    def _merge_document_sets(
        *,
        initial: ResearchSourceDocumentSet,
        supplemental: ResearchSourceDocumentSet,
    ) -> ResearchSourceDocumentSet:
        seen_document_ids = {
            document.document_id.strip().casefold()
            for document in initial.documents
        }
        seen_source_ids = {
            document.candidate.source_id.strip().casefold()
            for document in initial.documents
        }
        seen_urls = {
            document.candidate.normalized_url()
            for document in initial.documents
        }

        documents = list(initial.documents)

        for document in supplemental.documents:
            document_key = (
                document.document_id.strip().casefold()
            )
            source_key = (
                document.candidate.source_id
                .strip()
                .casefold()
            )
            url_key = (
                document.candidate.normalized_url()
            )

            if (
                document_key in seen_document_ids
                or source_key in seen_source_ids
                or url_key in seen_urls
            ):
                continue

            seen_document_ids.add(document_key)
            seen_source_ids.add(source_key)
            seen_urls.add(url_key)
            documents.append(document)

        return ResearchSourceDocumentSet(
            request_id=initial.request_id,
            documents=documents,
        )

    def _select_documents_with_evidence(
        self,
        document_set: ResearchSourceDocumentSet,
        *,
        query_set: ResearchSearchQuerySet,
        maximum_sources: int,
        evidence_cache: dict[
            tuple[str, str, str],
            list[ResearchEvidence],
        ] | None = None,
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

            cache_key = (
                document.document_id.strip().casefold(),
                normalized_url,
                document.content,
            )
            cache_hit = (
                evidence_cache is not None
                and cache_key in evidence_cache
            )

            if cache_hit:
                document_evidence = list(
                    evidence_cache[cache_key]
                )
            else:
                single_document_set = ResearchSourceDocumentSet(
                    request_id=document_set.request_id,
                    documents=[document],
                )
                extracted = self._evidence_extractor.extract(
                    single_document_set
                )
                document_evidence = extracted.ordered_evidence()
                if evidence_cache is not None:
                    evidence_cache[cache_key] = list(document_evidence)

            if not document_evidence:
                no_evidence_count += 1
                continue

            selected_documents.append(document)
            selected_evidence.extend(document_evidence)
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

        retained_issues = [
            issue
            for issue in quality.issues
            if issue.code
            is not ResearchQualityIssueCode.LOW_SOURCE_DIVERSITY
        ]

        if actual_sources >= required_sources:
            return quality.model_copy(
                update={
                    "issues": retained_issues,
                    "metadata": {
                        **quality.metadata,
                        "minimum_evidence_sources": str(
                            required_sources
                        ),
                        "actual_evidence_sources": str(
                            actual_sources
                        ),
                        "maximum_sources": str(
                            maximum_sources
                        ),
                    },
                }
            )
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
