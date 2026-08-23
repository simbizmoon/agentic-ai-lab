"""Production composition for bounded OpenAlex scholarly evidence."""

from __future__ import annotations

import httpx

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.openalex_scholarly_metadata_provider import (
    OpenAlexScholarlyMetadataProvider,
)
from app.research.scholarly_evidence_full_workflow import (
    ScholarlyEvidenceFullWorkflow,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest


def build_openalex_scholarly_evidence_workflow(
    request: ScholarlyEvidenceRequest,
    *,
    provider: ScholarlyMetadataProvider | None = None,
    client: httpx.Client | None = None,
    base_url: str = "https://api.openalex.org",
    timeout_seconds: float = 30.0,
    api_key: str | None = None,
) -> ScholarlyEvidenceFullWorkflow:
    """Build a request-bound workflow without making an external request."""

    if not isinstance(request, ScholarlyEvidenceRequest):
        raise TypeError("request must be a ScholarlyEvidenceRequest")
    if provider is not None and client is not None:
        raise ValueError("client must not be supplied with an injected provider")
    resolved_provider = provider or OpenAlexScholarlyMetadataProvider(
        client=client,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
    )
    return ScholarlyEvidenceFullWorkflow(
        evidence_workflow=BoundedScholarlyEvidenceWorkflow(
            provider=resolved_provider,
        )
    )
