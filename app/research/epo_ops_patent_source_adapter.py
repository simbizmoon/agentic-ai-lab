"""Map matching EPO OPS records into verified patent-source product data."""

from __future__ import annotations

from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.schemas.epo_ops_abstract import (
    EpoOpsAbstractRecord,
    EpoOpsVerifiedPatentRecord,
)
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
    PatentSourceFamily,
    PatentSourceMetadata,
)


class EpoOpsPatentSourceMappingError(RuntimeError):
    """Bibliographic and abstract records could not form one verified source."""


def build_verified_epo_patent_record(
    *,
    bibliographic: EpoOpsBibliographicRecord,
    abstract: EpoOpsAbstractRecord,
) -> EpoOpsVerifiedPatentRecord:
    """Create VERIFIED metadata only after exact source-specific identity matching."""

    biblio_identity = normalize_patent_publication_number(
        bibliographic.publication_number
    )
    abstract_identity = normalize_patent_publication_number(abstract.publication_number)
    if biblio_identity != abstract_identity:
        raise EpoOpsPatentSourceMappingError(
            "EPO OPS bibliographic and abstract publication identities differ."
        )
    if bibliographic.publication_docdb != abstract.publication_docdb:
        raise EpoOpsPatentSourceMappingError(
            "EPO OPS bibliographic and abstract DOCDB identities differ."
        )

    metadata = PatentSourceMetadata(
        source_family=PatentSourceFamily.EPO_OPS,
        publication_number=bibliographic.publication_number,
        title=bibliographic.title,
        source_url=abstract.source_endpoint,
        metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
        publication_date=bibliographic.publication_date,
    )
    return EpoOpsVerifiedPatentRecord(
        metadata=metadata,
        abstract_text=abstract.abstract_text,
        abstract_language=abstract.abstract_language,
    )
