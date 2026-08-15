"""Execution-scoped approval for external semantic Local Research sends."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.report_integrity import is_valid_sha256_digest
from app.research.local_document_access_policy import LocalDocumentAccessResult

SEMANTIC_LOCAL_RESEARCH_PURPOSE = "semantic_local_research"
INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE = "integrated_web_local_research"


class LocalExternalSendApprovalError(ValueError):
    """Raised when semantic Local Research lacks matching approval."""


class LocalExternalSendSourceIdentity(BaseModel):
    """Raw local-file identity bound into one approval."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    resolved_path: Path
    content_sha256: str
    file_size_bytes: int = Field(ge=0)

    @field_validator("resolved_path")
    @classmethod
    def _validate_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("resolved_path must be absolute")
        return value

    @field_validator("content_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        return value


class LocalExternalSendApproval(BaseModel):
    """Non-persistent approval bound to one execution's source identities."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    purpose: str = Field(min_length=1)
    approved: bool
    sources: tuple[LocalExternalSendSourceIdentity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_paths(self) -> LocalExternalSendApproval:
        paths = [source.resolved_path for source in self.sources]
        if len(paths) != len(set(paths)):
            raise ValueError("approved source paths must be unique")
        return self

    @classmethod
    def for_semantic_local_research(
        cls,
        sources: tuple[LocalDocumentAccessResult, ...],
        *,
        approved: bool = True,
    ) -> LocalExternalSendApproval:
        """Bind an approval decision to validated raw local sources."""
        return cls(
            purpose=SEMANTIC_LOCAL_RESEARCH_PURPOSE,
            approved=approved,
            sources=tuple(
                LocalExternalSendSourceIdentity(
                    resolved_path=source.resolved_path,
                    content_sha256=source.content_sha256,
                    file_size_bytes=source.file_size_bytes,
                )
                for source in sources
            ),
        )

    @classmethod
    def for_integrated_web_local_research(
        cls,
        sources: tuple[LocalDocumentAccessResult, ...],
        *,
        approved: bool = True,
    ) -> LocalExternalSendApproval:
        """Bind integrated approval to validated raw local sources."""
        return cls(
            purpose=INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
            approved=approved,
            sources=tuple(
                LocalExternalSendSourceIdentity(
                    resolved_path=source.resolved_path,
                    content_sha256=source.content_sha256,
                    file_size_bytes=source.file_size_bytes,
                )
                for source in sources
            ),
        )


class LocalExternalSendApprovalGate:
    """Require exact approval for the current validated local sources."""

    def validate(
        self,
        approval: LocalExternalSendApproval | None,
        current_sources: tuple[LocalDocumentAccessResult, ...],
        *,
        purpose: str = SEMANTIC_LOCAL_RESEARCH_PURPOSE,
    ) -> None:
        """Reject absent, false, or stale semantic send approval."""
        if approval is None or not approval.approved:
            research_mode = (
                "integrated Web and Local research"
                if purpose == INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE
                else "semantic local research"
            )
            raise LocalExternalSendApprovalError(
                "explicit external-send approval is required for "
                f"{research_mode}"
            )
        if approval.purpose != purpose:
            raise LocalExternalSendApprovalError(
                "external-send approval purpose mismatch"
            )

        approved_by_path = {source.resolved_path: source for source in approval.sources}
        current_by_path = {source.resolved_path: source for source in current_sources}
        if approved_by_path.keys() != current_by_path.keys():
            raise LocalExternalSendApprovalError(
                "approved and current source sets do not match"
            )

        for path, current in current_by_path.items():
            approved_source = approved_by_path[path]
            if approved_source.file_size_bytes != current.file_size_bytes:
                raise LocalExternalSendApprovalError(
                    f"approved local source size changed: {path}"
                )
            if approved_source.content_sha256 != current.content_sha256:
                raise LocalExternalSendApprovalError(
                    f"approved local source digest changed: {path}"
                )
