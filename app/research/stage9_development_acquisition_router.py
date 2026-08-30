"""Budgeted channel routing for leakage-safe Stage 9 evidence acquisition."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research_evidence import ResearchEvidenceSet
from app.schemas.research_source_document import ResearchSourceDocumentSet
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequest,
    Stage9DevelopmentAcquisitionResult,
    Stage9DevelopmentAcquisitionUsage,
)


class Stage9ChannelAcquisitionResult(BaseModel):
    """One channel result with independently bounded observable usage."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_id: str
    channel: Stage9AcquisitionChannel
    status: Stage9AcquisitionStatus
    evidence_set: ResearchEvidenceSet
    provider_requests: int = Field(ge=0, le=1)
    external_requests: int = Field(ge=0, le=3)
    failure_code: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Stage9ChannelAcquisitionResult:
        if self.evidence_set.request_id != self.request_id:
            raise ValueError("channel evidence must match request ID")
        if self.external_requests < self.provider_requests:
            raise ValueError("external requests must cover provider requests")
        has_evidence = bool(self.evidence_set.evidence)
        if (
            self.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
            and not has_evidence
        ):
            raise ValueError("evidence_available channel requires evidence")
        if self.status is Stage9AcquisitionStatus.NO_EVIDENCE and has_evidence:
            raise ValueError("no_evidence channel cannot contain evidence")
        if self.status is Stage9AcquisitionStatus.FAILED:
            if self.failure_code is None or not self.failure_code.strip():
                raise ValueError("failed channel requires a failure code")
        elif self.failure_code is not None:
            raise ValueError("only failed channel may contain a failure code")
        return self


class Stage9AcquisitionChannelProvider(Protocol):
    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult: ...


class Stage9DevelopmentAcquisitionRouterError(RuntimeError):
    """Routing could not preserve request, provenance, or budget boundaries."""


class Stage9DevelopmentAcquisitionRouter:
    """Run only declared channels and merge exact evidence without ranking."""

    def __init__(
        self,
        *,
        providers: dict[Stage9AcquisitionChannel, Stage9AcquisitionChannelProvider],
    ) -> None:
        self._providers = dict(providers)

    def acquire(
        self, request: Stage9DevelopmentAcquisitionRequest
    ) -> Stage9DevelopmentAcquisitionResult:
        if not isinstance(request, Stage9DevelopmentAcquisitionRequest):
            raise TypeError("request must be a Stage9DevelopmentAcquisitionRequest")

        channel_results: list[Stage9ChannelAcquisitionResult] = []
        for channel in request.channels:
            provider = self._providers.get(channel)
            if provider is None:
                raise Stage9DevelopmentAcquisitionRouterError(
                    f"no provider is configured for channel: {channel.value}"
                )
            result = provider.acquire(request=request, channel=channel)
            if not isinstance(result, Stage9ChannelAcquisitionResult):
                raise Stage9DevelopmentAcquisitionRouterError(
                    "channel provider returned an invalid result"
                )
            if result.request_id != request.request_id or result.channel is not channel:
                raise Stage9DevelopmentAcquisitionRouterError(
                    "channel result identity does not match the routed request"
                )
            channel_results.append(result)
            if result.status is Stage9AcquisitionStatus.FAILED:
                break

        evidence_set = self._merge_evidence(request, channel_results)
        usage = Stage9DevelopmentAcquisitionUsage(
            provider_requests=sum(item.provider_requests for item in channel_results),
            external_requests=sum(item.external_requests for item in channel_results),
            documents_read=len(evidence_set.document_set.successful_documents()),
            evidence_items=len(evidence_set.evidence),
        )
        status, failure_code = self._terminal_status(channel_results, evidence_set)
        try:
            return Stage9DevelopmentAcquisitionResult(
                request=request,
                status=status,
                evidence_set=evidence_set,
                usage=usage,
                failure_code=failure_code,
            )
        except ValueError as error:
            raise Stage9DevelopmentAcquisitionRouterError(
                "merged channel result violates the acquisition budget"
            ) from error

    @staticmethod
    def _merge_evidence(
        request: Stage9DevelopmentAcquisitionRequest,
        results: list[Stage9ChannelAcquisitionResult],
    ) -> ResearchEvidenceSet:
        documents = [
            document
            for result in results
            for document in result.evidence_set.document_set.documents
        ]
        evidence = [item for result in results for item in result.evidence_set.evidence]
        try:
            document_set = ResearchSourceDocumentSet(
                request_id=request.request_id,
                documents=documents,
            )
            return ResearchEvidenceSet(
                request_id=request.request_id,
                document_set=document_set,
                evidence=evidence,
            )
        except ValueError as error:
            raise Stage9DevelopmentAcquisitionRouterError(
                "channel evidence identities or provenance collide"
            ) from error

    @staticmethod
    def _terminal_status(
        results: list[Stage9ChannelAcquisitionResult],
        evidence_set: ResearchEvidenceSet,
    ) -> tuple[Stage9AcquisitionStatus, str | None]:
        failed = next(
            (
                result
                for result in results
                if result.status is Stage9AcquisitionStatus.FAILED
            ),
            None,
        )
        if failed is not None:
            return Stage9AcquisitionStatus.FAILED, failed.failure_code
        if any(
            result.status is Stage9AcquisitionStatus.INCOMPLETE for result in results
        ):
            return Stage9AcquisitionStatus.INCOMPLETE, None
        if evidence_set.evidence:
            return Stage9AcquisitionStatus.EVIDENCE_AVAILABLE, None
        return Stage9AcquisitionStatus.NO_EVIDENCE, None
