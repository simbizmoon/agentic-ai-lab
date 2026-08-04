"""Central workspace schema for a single research-agent workflow."""

from __future__ import annotations

from enum import IntEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_claim import (
    ResearchClaim,
    ResearchClaimSet,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
)
from app.schemas.research_source_quality import (
    ResearchSourceQualityEvaluation,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


class ResearchWorkspaceStage(IntEnum):
    """Highest completed stage represented in a workspace."""

    REQUESTED = 10
    DECOMPOSED = 20
    QUERIES_PLANNED = 30
    SOURCES_DISCOVERED = 40
    DOCUMENTS_READ = 50
    EVIDENCE_EXTRACTED = 60
    CLAIMS_BUILT = 70


class ResearchWorkspaceProgress(BaseModel):
    """Deterministic progress summary for a workspace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    stage: ResearchWorkspaceStage
    task_count: int = Field(ge=0)
    searchable_task_count: int = Field(ge=0)
    query_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    successful_document_count: int = Field(ge=0)
    failed_document_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    quality_evaluation_count: int = Field(ge=0)


class ResearchWorkspace(BaseModel):
    """Central immutable state for one research workflow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    workspace_id: str
    request: ResearchRequest
    task_graph: ResearchTaskGraph | None = None
    query_set: ResearchSearchQuerySet | None = None
    candidate_set: ResearchSourceCandidateSet | None = None
    document_set: ResearchSourceDocumentSet | None = None
    evidence_set: ResearchEvidenceSet | None = None
    claim_set: ResearchClaimSet | None = None
    source_quality_evaluations: list[
        ResearchSourceQualityEvaluation
    ] = Field(default_factory=list)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_workspace(self) -> Self:
        """Validate identity and progressive workspace structure."""

        if not self.workspace_id.strip():
            raise ValueError(
                "workspace_id must not be blank"
            )

        self._validate_progressive_structure()
        self._validate_request_identity()
        self._validate_object_connections()
        self._validate_quality_evaluations()
        self._validate_metadata()

        return self

    def _validate_progressive_structure(self) -> None:
        """Require each workflow layer to have its predecessor."""

        dependencies = [
            (
                self.query_set,
                self.task_graph,
                "query_set requires task_graph",
            ),
            (
                self.candidate_set,
                self.query_set,
                "candidate_set requires query_set",
            ),
            (
                self.document_set,
                self.candidate_set,
                "document_set requires candidate_set",
            ),
            (
                self.evidence_set,
                self.document_set,
                "evidence_set requires document_set",
            ),
            (
                self.claim_set,
                self.evidence_set,
                "claim_set requires evidence_set",
            ),
        ]

        for current, required, message in dependencies:
            if current is not None and required is None:
                raise ValueError(message)

        if (
            self.source_quality_evaluations
            and self.document_set is None
        ):
            raise ValueError(
                "source quality evaluations "
                "require document_set"
            )

    def _validate_request_identity(self) -> None:
        """Require every workspace layer to use one request ID."""

        request_id = self.request.request_id

        request_ids: list[str] = []

        if self.task_graph is not None:
            request_ids.append(
                self.task_graph.request_id
            )

        if self.query_set is not None:
            request_ids.append(
                self.query_set.request_id
            )

        if self.candidate_set is not None:
            request_ids.append(
                self.candidate_set.request_id
            )

        if self.document_set is not None:
            request_ids.append(
                self.document_set.request_id
            )

        if self.evidence_set is not None:
            request_ids.append(
                self.evidence_set.request_id
            )

        if self.claim_set is not None:
            request_ids.append(
                self.claim_set.request_id
            )

        if any(
            value != request_id
            for value in request_ids
        ):
            raise ValueError(
                "all workspace request IDs must match"
            )

    def _validate_object_connections(self) -> None:
        """Require embedded sets to reference workspace objects."""

        if (
            self.query_set is not None
            and self.task_graph is not None
            and self.query_set.task_graph
            != self.task_graph
        ):
            raise ValueError(
                "query_set task_graph must match "
                "workspace task_graph"
            )

        if (
            self.candidate_set is not None
            and self.query_set is not None
            and self.candidate_set.query_set
            != self.query_set
        ):
            raise ValueError(
                "candidate_set query_set must match "
                "workspace query_set"
            )

        if (
            self.evidence_set is not None
            and self.document_set is not None
            and self.evidence_set.document_set
            != self.document_set
        ):
            raise ValueError(
                "evidence_set document_set must match "
                "workspace document_set"
            )

        if (
            self.claim_set is not None
            and self.evidence_set is not None
            and self.claim_set.evidence_set
            != self.evidence_set
        ):
            raise ValueError(
                "claim_set evidence_set must match "
                "workspace evidence_set"
            )

    def _validate_quality_evaluations(self) -> None:
        """Validate source quality evaluations against documents."""

        evaluation_document_ids = [
            evaluation.document.document_id
            .strip()
            .casefold()
            for evaluation
            in self.source_quality_evaluations
        ]

        if len(set(evaluation_document_ids)) != len(
            evaluation_document_ids
        ):
            raise ValueError(
                "source quality evaluations must have "
                "unique document IDs"
            )

        if self.document_set is None:
            return

        document_by_id = {
            document.document_id.strip().casefold():
            document
            for document in self.document_set.documents
        }

        for evaluation in self.source_quality_evaluations:
            document = document_by_id.get(
                evaluation.document.document_id
                .strip()
                .casefold()
            )

            if document is None:
                raise ValueError(
                    "source quality evaluation must "
                    "reference a workspace document"
                )

            if evaluation.document != document:
                raise ValueError(
                    "source quality evaluation document "
                    "must match the workspace document"
                )

    def _validate_metadata(self) -> None:
        """Validate workspace metadata."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def stage(self) -> ResearchWorkspaceStage:
        """Return the highest represented workflow stage."""

        if self.claim_set is not None:
            return ResearchWorkspaceStage.CLAIMS_BUILT

        if self.evidence_set is not None:
            return (
                ResearchWorkspaceStage.EVIDENCE_EXTRACTED
            )

        if self.document_set is not None:
            return ResearchWorkspaceStage.DOCUMENTS_READ

        if self.candidate_set is not None:
            return (
                ResearchWorkspaceStage.SOURCES_DISCOVERED
            )

        if self.query_set is not None:
            return (
                ResearchWorkspaceStage.QUERIES_PLANNED
            )

        if self.task_graph is not None:
            return ResearchWorkspaceStage.DECOMPOSED

        return ResearchWorkspaceStage.REQUESTED

    def progress(self) -> ResearchWorkspaceProgress:
        """Return deterministic workspace progress counts."""

        tasks = (
            self.task_graph.tasks
            if self.task_graph is not None
            else []
        )
        queries = (
            self.query_set.queries
            if self.query_set is not None
            else []
        )
        candidates = (
            self.candidate_set.candidates
            if self.candidate_set is not None
            else []
        )
        documents = (
            self.document_set.documents
            if self.document_set is not None
            else []
        )
        evidence = (
            self.evidence_set.evidence
            if self.evidence_set is not None
            else []
        )
        claims = (
            self.claim_set.claims
            if self.claim_set is not None
            else []
        )

        successful_documents = (
            self.document_set.successful_documents()
            if self.document_set is not None
            else []
        )
        failed_documents = (
            self.document_set.failed_documents()
            if self.document_set is not None
            else []
        )

        return ResearchWorkspaceProgress(
            stage=self.stage,
            task_count=len(tasks),
            searchable_task_count=sum(
                task.requires_search
                for task in tasks
            ),
            query_count=len(queries),
            candidate_count=len(candidates),
            document_count=len(documents),
            successful_document_count=len(
                successful_documents
            ),
            failed_document_count=len(
                failed_documents
            ),
            evidence_count=len(evidence),
            claim_count=len(claims),
            quality_evaluation_count=len(
                self.source_quality_evaluations
            ),
        )

    def task(
        self,
        task_id: str,
    ) -> ResearchTask | None:
        """Return one task by normalized ID."""

        if not task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        if self.task_graph is None:
            return None

        normalized = task_id.strip().casefold()

        return next(
            (
                task
                for task in self.task_graph.tasks
                if task.task_id.strip().casefold()
                == normalized
            ),
            None,
        )

    def queries_for_task(
        self,
        task_id: str,
    ) -> list[ResearchSearchQuery]:
        """Return queries belonging to one task."""

        self._validate_task_lookup(task_id)

        if self.query_set is None:
            return []

        return self.query_set.queries_for_task(
            task_id
        )

    def candidates_for_task(
        self,
        task_id: str,
    ) -> list[ResearchSourceCandidate]:
        """Return candidates belonging to one task."""

        normalized = self._validate_task_lookup(
            task_id
        )

        if self.candidate_set is None:
            return []

        return [
            candidate
            for candidate
            in self.candidate_set.ordered_candidates()
            if candidate.task_id.strip().casefold()
            == normalized
        ]

    def documents_for_task(
        self,
        task_id: str,
    ) -> list[ResearchSourceDocument]:
        """Return documents belonging to one task."""

        normalized = self._validate_task_lookup(
            task_id
        )

        if self.document_set is None:
            return []

        return [
            document
            for document in self.document_set.documents
            if (
                document.candidate.task_id
                .strip()
                .casefold()
                == normalized
            )
        ]

    def evidence_for_task(
        self,
        task_id: str,
    ) -> list[ResearchEvidence]:
        """Return evidence belonging to one task."""

        self._validate_task_lookup(task_id)

        if self.evidence_set is None:
            return []

        return self.evidence_set.evidence_for_task(
            task_id
        )

    def claims_for_task(
        self,
        task_id: str,
    ) -> list[ResearchClaim]:
        """Return claims belonging to one task."""

        self._validate_task_lookup(task_id)

        if self.claim_set is None:
            return []

        return self.claim_set.claims_for_task(
            task_id
        )

    def quality_for_document(
        self,
        document_id: str,
    ) -> ResearchSourceQualityEvaluation | None:
        """Return one source quality evaluation."""

        if not document_id.strip():
            raise ValueError(
                "document_id must not be blank"
            )

        normalized = (
            document_id.strip().casefold()
        )

        return next(
            (
                evaluation
                for evaluation
                in self.source_quality_evaluations
                if (
                    evaluation.document.document_id
                    .strip()
                    .casefold()
                    == normalized
                )
            ),
            None,
        )

    def _validate_task_lookup(
        self,
        task_id: str,
    ) -> str:
        """Validate task lookup input and return normalized ID."""

        if not task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        return task_id.strip().casefold()
