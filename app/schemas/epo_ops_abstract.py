"""Internal contracts for EPO OPS abstract retrieval and verified mapping."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.patent_source_metadata import PatentSourceMetadata


class EpoOpsAbstractRecord(BaseModel):
    """One source-specific OPS abstract record bound to a DOCDB publication."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    publication_number: str
    publication_docdb: str
    abstract_text: str
    abstract_language: str | None = None
    source_endpoint: str

    @model_validator(mode="after")
    def validate_record(self) -> EpoOpsAbstractRecord:
        if not self.publication_number.strip():
            raise ValueError("publication_number must not be blank")
        if not self.publication_docdb.strip():
            raise ValueError("publication_docdb must not be blank")
        if not self.abstract_text.strip():
            raise ValueError("abstract_text must not be blank")
        if self.abstract_language is not None and not self.abstract_language.strip():
            raise ValueError("abstract_language must not be blank")
        if not self.source_endpoint.strip():
            raise ValueError("source_endpoint must not be blank")
        return self


class EpoOpsVerifiedPatentRecord(BaseModel):
    """Verified OPS metadata plus technical abstract text for later evidence use."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    metadata: PatentSourceMetadata
    abstract_text: str
    abstract_language: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> EpoOpsVerifiedPatentRecord:
        if not self.abstract_text.strip():
            raise ValueError("abstract_text must not be blank")
        if self.abstract_language is not None and not self.abstract_language.strip():
            raise ValueError("abstract_language must not be blank")
        return self
