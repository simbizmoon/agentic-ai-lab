"""Adapt verified patent records into generic research documents."""

from __future__ import annotations

from app.research.patent_research_plan_executor import (
    PatentResearchPlanExecutionResult,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


class PatentResearchDocumentAdapter:
    """Map one bounded verified patent execution into research documents."""

    def adapt(
        self,
        execution: PatentResearchPlanExecutionResult,
        *,
        request_id: str,
        task_id: str,
    ) -> ResearchSourceDocumentSet:
        """Return generic readable documents with patent provenance."""

        cleaned_request_id = request_id.strip()
        cleaned_task_id = task_id.strip()

        if not cleaned_request_id:
            raise ValueError("request_id must not be blank")
        if not cleaned_task_id:
            raise ValueError("task_id must not be blank")

        documents = [
            self._document(
                execution=execution,
                request_id=cleaned_request_id,
                task_id=cleaned_task_id,
                position=position,
            )
            for position, _record in enumerate(
                execution.collection.verified_records,
                start=1,
            )
        ]

        return ResearchSourceDocumentSet(
            request_id=cleaned_request_id,
            documents=documents,
        )

    @staticmethod
    def _document(
        *,
        execution: PatentResearchPlanExecutionResult,
        request_id: str,
        task_id: str,
        position: int,
    ) -> ResearchSourceDocument:
        record = execution.collection.verified_records[position - 1]
        metadata = record.metadata
        source_id = f"patent-source-{position:03d}"
        query_id = f"patent-query-{execution.query.purpose.value}"
        document_id = f"patent-document-{position:03d}"
        abstract_text = record.abstract_text

        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request_id,
            task_id=task_id,
            query_id=query_id,
            title=metadata.title,
            url=metadata.source_url,
            source_type=ResearchSourceType.OTHER,
            snippet=abstract_text,
            published_at=metadata.publication_date,
            rank=position,
            metadata={
                "search_query_text": execution.query.cql_query,
                "patent_source_family": metadata.source_family.value,
                "patent_publication_number": metadata.publication_number,
                "patent_verification_state": (
                    metadata.metadata_verification_state.value
                ),
                "patent_query_purpose": execution.query.purpose.value,
            },
        )

        document_metadata = {
            "patent_source_family": metadata.source_family.value,
            "patent_publication_number": metadata.publication_number,
            "patent_verification_state": (metadata.metadata_verification_state.value),
            "patent_query_purpose": execution.query.purpose.value,
        }
        if record.abstract_language is not None:
            document_metadata["patent_abstract_language"] = record.abstract_language

        return ResearchSourceDocument(
            document_id=document_id,
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=abstract_text,
            language=record.abstract_language,
            sections=[],
            word_count=len(abstract_text.split()),
            character_count=len(abstract_text),
            reader="verified-epo-patent-adapter",
            metadata=document_metadata,
        )
