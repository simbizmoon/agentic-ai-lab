"""Bridge verified URL discovery and exact reads into Stage 9 acquisition."""

from __future__ import annotations

from app.research.stage9_development_acquisition_router import (
    Stage9ChannelAcquisitionResult,
)
from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebAcquisitionAdapter,
    Stage9OfficialWebDocument,
)
from app.research.stage9_verified_official_source_provider import (
    Stage9VerifiedOfficialSourceProvider,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9DevelopmentAcquisitionRequest,
)


class _LockedDocumentBatchProvider:
    def __init__(self, documents: tuple[Stage9OfficialWebDocument, ...]) -> None:
        self._documents = documents

    def acquire(
        self,
        *,
        query: str,
        allowed_domains: tuple[str, ...],
        maximum_results: int,
    ) -> tuple[Stage9OfficialWebDocument, ...]:
        del query, allowed_domains
        if len(self._documents) > maximum_results:
            raise RuntimeError("verified document batch exceeded the adapter boundary")
        return self._documents


class Stage9VerifiedOfficialWebAcquisitionAdapter:
    """Acquire verified official documents with split request accounting."""

    def __init__(self, *, provider: Stage9VerifiedOfficialSourceProvider) -> None:
        if not isinstance(provider, Stage9VerifiedOfficialSourceProvider):
            raise TypeError("provider must be a verified official-source provider")
        self._provider = provider

    def acquire(
        self,
        *,
        request: Stage9DevelopmentAcquisitionRequest,
        channel: Stage9AcquisitionChannel,
    ) -> Stage9ChannelAcquisitionResult:
        allowed_domains = Stage9OfficialWebAcquisitionAdapter._domains_from_question(
            request.question
        )
        maximum_results = min(request.budget.maximum_documents, 2)
        batch = self._provider.acquire(
            query=Stage9OfficialWebAcquisitionAdapter._provider_query(request.question),
            allowed_domains=allowed_domains,
            maximum_results=maximum_results,
        )
        if batch.discovery_provider_requests > 1:
            raise RuntimeError("verified discovery exceeded the provider boundary")
        if batch.total_external_requests > 3:
            raise RuntimeError("verified acquisition exceeded the external boundary")
        converted = Stage9OfficialWebAcquisitionAdapter(
            provider=_LockedDocumentBatchProvider(batch.documents)
        ).acquire(request=request, channel=channel)
        return converted.model_copy(
            update={
                "provider_requests": batch.discovery_provider_requests,
                "external_requests": batch.total_external_requests,
            }
        )
