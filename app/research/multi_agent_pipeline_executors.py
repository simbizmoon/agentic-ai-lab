"""Bridge existing pipeline components into multi-agent executor contracts."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.research.research_claim_executor import (
    ResearchClaimExecutionResult,
    ResearchClaimExecutor,
    ResearchConstructedCitation,
    ResearchConstructedClaim,
)
from app.research.research_evidence_executor import (
    ResearchEvidenceDocumentFailure,
    ResearchEvidenceExecutionResult,
    ResearchEvidenceExecutor,
    ResearchExtractedEvidence,
)
from app.research.research_search_executor import (
    ResearchSearchExecutionResult,
    ResearchSearchExecutor,
    ResearchSearchHit,
)
from app.research.research_source_reader_executor import (
    ResearchReadDocument,
    ResearchSourceReaderExecutionResult,
    ResearchSourceReaderExecutor,
    ResearchSourceReadFailure,
)
from app.research.single_research_agent_pipeline import (
    ResearchClaimBuilderProtocol,
    ResearchEvidenceExtractorProtocol,
    ResearchSourceReaderProtocol,
    ResearchSourceSearcherProtocol,
)
from app.schemas.research_agent_assignment import ResearchAgentTaskAssignment
from app.schemas.research_workspace import ResearchWorkspace


@dataclass(slots=True)
class MultiAgentResearchRuntimeContext:
    """Own the current immutable workspace for sequential Phase 8 execution."""

    workspace: ResearchWorkspace

    def replace_workspace(
        self,
        **changes: object,
    ) -> ResearchWorkspace:
        """Apply one stage update and revalidate workspace invariants."""

        candidate = self.workspace.model_copy(update=changes)

        # model_copy preserves already-validated nested domain objects.
        # Re-run only the workspace-level cross-object invariants.
        candidate.validate_workspace()

        self.workspace = candidate
        return self.workspace


class PipelineResearchSearchExecutor(ResearchSearchExecutor):
    """Adapt a pipeline set-level source searcher to the agent contract."""

    def __init__(
        self,
        *,
        context: MultiAgentResearchRuntimeContext,
        searcher: ResearchSourceSearcherProtocol,
    ) -> None:
        self._context = context
        self._searcher = searcher

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        """Search the current workspace query set."""

        del assignment
        query_set = self._context.workspace.query_set
        if query_set is None:
            raise RuntimeError(
                "research workspace must contain query_set before search"
            )

        started_at = time.perf_counter()
        candidate_set = self._searcher.search(query_set)
        duration_ms = _elapsed_ms(started_at)

        self._context.replace_workspace(
            candidate_set=candidate_set,
        )

        hits = [
            ResearchSearchHit(
                source_id=candidate.source_id,
                title=candidate.title,
                location=candidate.url,
                query_id=candidate.query_id,
                metadata={
                    "source_type": candidate.source_type.value,
                },
            )
            for candidate in candidate_set.ordered_candidates()
        ]

        return ResearchSearchExecutionResult(
            hits=hits,
            query_count=len(query_set.queries),
            tool_call_count=_search_tool_call_count(
                self._searcher
            ),
            duration_ms=duration_ms,
            metadata={
                "adapter": self.__class__.__name__,
            },
        )


class PipelineResearchSourceReaderExecutor(
    ResearchSourceReaderExecutor
):
    """Adapt a pipeline set-level source reader to the agent contract."""

    def __init__(
        self,
        *,
        context: MultiAgentResearchRuntimeContext,
        reader: ResearchSourceReaderProtocol,
    ) -> None:
        self._context = context
        self._reader = reader

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        """Read the current workspace candidate set."""

        del assignment
        candidate_set = self._context.workspace.candidate_set
        if candidate_set is None:
            raise RuntimeError(
                "research workspace must contain candidate_set before reading"
            )

        started_at = time.perf_counter()
        document_set = self._reader.read(candidate_set)
        duration_ms = _elapsed_ms(started_at)

        self._context.replace_workspace(
            document_set=document_set,
        )

        documents: list[ResearchReadDocument] = []
        failures: list[ResearchSourceReadFailure] = []

        for document in document_set.documents:
            candidate = document.candidate
            content = document.content

            if content is not None and content.strip():
                documents.append(
                    ResearchReadDocument(
                        document_id=document.document_id,
                        source_id=candidate.source_id,
                        title=candidate.title,
                        content=content,
                        location=candidate.url,
                        content_type=document.content_type.value,
                        word_count=document.word_count,
                        metadata={
                            "reader": document.reader,
                            "status": document.status.value,
                        },
                    )
                )
                continue

            failures.append(
                ResearchSourceReadFailure(
                    source_id=candidate.source_id,
                    code="SOURCE_NOT_READABLE",
                    message=(
                        "The pipeline source reader returned "
                        "no readable document content."
                    ),
                    retryable=False,
                    metadata={
                        "document_id": document.document_id,
                        "status": document.status.value,
                    },
                )
            )

        return ResearchSourceReaderExecutionResult(
            requested_source_count=len(
                candidate_set.candidates
            ),
            documents=documents,
            failures=failures,
            tool_call_count=len(
                candidate_set.candidates
            ),
            duration_ms=duration_ms,
            metadata={
                "adapter": self.__class__.__name__,
            },
        )


class PipelineResearchEvidenceExecutor(
    ResearchEvidenceExecutor
):
    """Adapt a pipeline set-level evidence extractor to the agent contract."""

    def __init__(
        self,
        *,
        context: MultiAgentResearchRuntimeContext,
        extractor: ResearchEvidenceExtractorProtocol,
    ) -> None:
        self._context = context
        self._extractor = extractor

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        """Extract evidence from the current readable document set."""

        del assignment
        document_set = self._context.workspace.document_set
        if document_set is None:
            raise RuntimeError(
                "research workspace must contain document_set "
                "before evidence extraction"
            )

        reset_usage = getattr(
            self._extractor,
            "reset_usage",
            None,
        )
        if callable(reset_usage):
            reset_usage()

        started_at = time.perf_counter()
        evidence_set = self._extractor.extract(
            document_set
        )
        duration_ms = _elapsed_ms(started_at)

        self._context.replace_workspace(
            evidence_set=evidence_set,
        )

        evidence = [
            ResearchExtractedEvidence(
                evidence_id=item.evidence_id,
                document_id=item.document_id,
                source_id=item.source_id,
                text=item.excerpt,
                interpretation=(
                    item.rationale
                    or "Traceable evidence extracted by the pipeline."
                ),
                relevance_score=item.relevance_score,
                confidence_score=item.confidence_score,
                location_reference=(
                    "characters:"
                    f"{item.start_character}-{item.end_character}"
                ),
                metadata={
                    "stance": item.stance.value,
                    "evidence_type": item.evidence_type.value,
                },
            )
            for item in evidence_set.ordered_evidence()
        ]

        successful_document_ids = {
            item.document_id.strip().casefold()
            for item in evidence_set.evidence
        }
        readable_documents = (
            document_set.successful_documents()
        )
        failures = [
            ResearchEvidenceDocumentFailure(
                document_id=document.document_id,
                source_id=document.candidate.source_id,
                code="NO_EVIDENCE_EXTRACTED",
                message=(
                    "The pipeline extractor returned no evidence "
                    "for the readable document."
                ),
                retryable=False,
            )
            for document in readable_documents
            if (
                document.document_id.strip().casefold()
                not in successful_document_ids
            )
        ]

        usage = getattr(
            self._extractor,
            "last_usage",
            None,
        )

        return ResearchEvidenceExecutionResult(
            requested_document_count=len(
                readable_documents
            ),
            evidence=evidence,
            failures=failures,
            tool_call_count=len(
                readable_documents
            ),
            duration_ms=duration_ms,
            output_token_count=(
                int(
                    getattr(
                        usage,
                        "recorded_tokens",
                        0,
                    )
                )
                if usage is not None
                else 0
            ),
            metadata={
                "adapter": self.__class__.__name__,
            },
        )


class PipelineResearchClaimExecutor(
    ResearchClaimExecutor
):
    """Adapt a pipeline claim builder to the agent claim contract."""

    def __init__(
        self,
        *,
        context: MultiAgentResearchRuntimeContext,
        builder: ResearchClaimBuilderProtocol,
    ) -> None:
        self._context = context
        self._builder = builder

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchClaimExecutionResult:
        """Build claims from the current workspace evidence set."""

        del assignment
        evidence_set = self._context.workspace.evidence_set
        if evidence_set is None:
            raise RuntimeError(
                "research workspace must contain evidence_set "
                "before claim construction"
            )

        started_at = time.perf_counter()
        claim_set = self._builder.build(
            evidence_set
        )
        duration_ms = _elapsed_ms(started_at)

        self._context.replace_workspace(
            claim_set=claim_set,
        )

        return ResearchClaimExecutionResult(
            requested_evidence_group_count=len(
                evidence_set.evidence
            ),
            claims=[
                _constructed_claim(claim)
                for claim in claim_set.claims
            ],
            failures=[],
            tool_call_count=0,
            duration_ms=duration_ms,
            metadata={
                "adapter": self.__class__.__name__,
            },
        )


def _constructed_claim(
    claim: object,
) -> ResearchConstructedClaim:
    citations = [
        ResearchConstructedCitation(
            citation_id=citation.citation_id,
            evidence_id=citation.evidence_id,
            source_id=citation.source_id,
            document_id=citation.document_id,
            location_reference=(
                "characters:"
                f"{citation.start_character}-{citation.end_character}"
            ),
            metadata=dict(
                citation.metadata
            ),
        )
        for citation in claim.citations
    ]

    return ResearchConstructedClaim(
        claim_id=claim.claim_id,
        text=claim.text,
        rationale=(
            claim.rationale
            or "Claim constructed from traceable research evidence."
        ),
        confidence_score=claim.confidence_score,
        evidence_ids=[
            citation.evidence_id
            for citation in claim.citations
        ],
        citations=citations,
        metadata=dict(claim.metadata),
    )


def _search_tool_call_count(
    searcher: object,
) -> int:
    usage = getattr(
        searcher,
        "search_usage",
        None,
    )
    if usage is None:
        return 0
    return int(
        getattr(
            usage,
            "provider_call_count",
            0,
        )
    )


def _elapsed_ms(
    started_at: float,
) -> int:
    return max(
        0,
        int(
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        ),
    )
