"""Offline scholarly artifact-to-evidence integration runtime."""

from __future__ import annotations

from app.research.scholarly_abstract_document_adapter import (
    ScholarlyAbstractDocumentAdapter,
)
from app.research.scholarly_whole_abstract_evidence_adapter import (
    ScholarlyWholeAbstractEvidenceAdapter,
)
from app.schemas.scholarly_evidence_adaptation import ScholarlyEvidenceAdaptation
from app.schemas.scholarly_search_workflow import ScholarlySearchWorkflowArtifact


class ScholarlyArtifactEvidenceRuntime:
    """Compose exact scholarly document and evidence adapters."""

    def __init__(
        self,
        *,
        document_adapter: ScholarlyAbstractDocumentAdapter | None = None,
        evidence_adapter: ScholarlyWholeAbstractEvidenceAdapter | None = None,
    ) -> None:
        self._document_adapter = document_adapter or (
            ScholarlyAbstractDocumentAdapter()
        )
        self._evidence_adapter = evidence_adapter or (
            ScholarlyWholeAbstractEvidenceAdapter()
        )

    def build(
        self,
        artifact: ScholarlySearchWorkflowArtifact,
        *,
        task_id: str,
    ) -> ScholarlyEvidenceAdaptation:
        """Build exact whole-abstract evidence without external calls."""

        documents = self._document_adapter.adapt(
            artifact,
            task_id=task_id,
        )
        return self._evidence_adapter.adapt(documents)
