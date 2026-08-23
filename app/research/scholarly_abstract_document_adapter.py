"""Adapt provider-supplied scholarly abstracts into research documents."""

from __future__ import annotations

import json
from hashlib import sha256

from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)
from app.schemas.scholarly_document_adaptation import (
    ScholarlyDocumentAdaptation,
)
from app.schemas.scholarly_search_workflow import ScholarlySearchWorkflowArtifact
from app.schemas.scholarly_work import (
    ScholarlyIdentifierType,
    ScholarlyWork,
)


class ScholarlyAbstractDocumentAdapter:
    """Create exact generic documents without semantic selection."""

    @property
    def name(self) -> str:
        return "scholarly-abstract-document-adapter"

    def adapt(
        self,
        artifact: ScholarlySearchWorkflowArtifact,
        *,
        task_id: str,
    ) -> ScholarlyDocumentAdaptation:
        cleaned_task_id = task_id.strip()
        if not cleaned_task_id:
            raise ValueError("task_id must not be blank")
        documents: list[ResearchSourceDocument] = []
        omitted: list[str] = []
        for position, work in enumerate(artifact.result.works, start=1):
            if work.abstract is None:
                omitted.append(work.work_id)
                continue
            documents.append(
                self._document(
                    artifact=artifact,
                    work=work,
                    task_id=cleaned_task_id,
                    position=position,
                )
            )
        return ScholarlyDocumentAdaptation(
            artifact=artifact,
            document_set=ResearchSourceDocumentSet(
                request_id=artifact.result.request.request_id,
                documents=documents,
            ),
            omitted_work_ids=tuple(omitted),
        )

    def _document(
        self,
        *,
        artifact: ScholarlySearchWorkflowArtifact,
        work: ScholarlyWork,
        task_id: str,
        position: int,
    ) -> ResearchSourceDocument:
        abstract = work.abstract
        if abstract is None:  # protected by adapt()
            raise ValueError("scholarly work must contain an abstract")
        digest = sha256(
            f"{work.provenance.provider}|{work.provenance.provider_record_id}|{work.work_id}".encode()
        ).hexdigest()[:16]
        source_id = f"scholarly-source-{digest}"
        document_id = f"scholarly-document-{digest}"
        section_id = f"{document_id}-abstract"
        identifiers = {
            item.identifier_type.value: item.normalized_value
            for item in work.identifiers
        }
        doi = identifiers.get(ScholarlyIdentifierType.DOI.value, "ABSENT")
        metadata = {
            "scholarly_work_id": work.work_id,
            "scholarly_provider": work.provenance.provider,
            "scholarly_provider_record_id": work.provenance.provider_record_id,
            "scholarly_response_url": work.provenance.request_url,
            "scholarly_response_sha256": work.provenance.response_sha256,
            "scholarly_identifiers_json": json.dumps(
                identifiers, sort_keys=True, separators=(",", ":")
            ),
            "scholarly_doi": doi,
            "scholarly_version_type": work.version_type.value,
            "scholarly_access_state": work.access.state.value,
            "scholarly_license": work.access.license or "ABSENT",
            "scholarly_integrity_status": work.integrity_status.value,
            "scholarly_abstract_provider": abstract.provider,
            "scholarly_abstract_source_url": abstract.source_url,
        }
        author = ", ".join(item.display_name for item in work.authors) or None
        publisher = work.publisher or work.venue
        request = artifact.result.request
        candidate = ResearchSourceCandidate(
            source_id=source_id,
            request_id=request.request_id,
            task_id=task_id,
            query_id=f"scholarly-query-{request.request_id}",
            title=work.title,
            url=work.access.landing_page_url,
            source_type=ResearchSourceType.ACADEMIC,
            snippet=abstract.text,
            author=author,
            publisher=publisher,
            published_at=work.publication_date,
            rank=position,
            metadata={
                "search_query_text": request.query,
                **metadata,
            },
        )
        content = abstract.text
        return ResearchSourceDocument(
            document_id=document_id,
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=content,
            language=abstract.language,
            sections=[
                ResearchSourceDocumentSection(
                    section_id=section_id,
                    heading="Abstract",
                    content=content,
                    order=1,
                    start_character=0,
                    end_character=len(content),
                    metadata={"scholarly_work_id": work.work_id},
                )
            ],
            word_count=len(content.split()),
            character_count=len(content),
            reader=self.name,
            metadata=metadata,
        )
