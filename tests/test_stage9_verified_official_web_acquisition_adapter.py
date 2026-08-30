"""Offline E2E tests for verified official discovery through RAG packing."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_acquisition_aware_research_loop import (
    Stage9AcquisitionContextBuilder,
)
from app.research.stage9_development_runtime_factory import (
    create_stage9_development_runtime,
)
from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebDocument,
)
from app.research.stage9_verified_official_source_provider import (
    Stage9OfficialSourceCandidate,
    Stage9VerifiedOfficialSourceProvider,
)
from app.research.stage9_verified_official_web_acquisition_adapter import (
    Stage9VerifiedOfficialWebAcquisitionAdapter,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
)

DIRECTORY = Path("evals/manifests/stage9/stage9-single-agent-baseline-live-v1")
MANIFEST = DIRECTORY / "approved-live-baseline.json"
REVIEW = DIRECTORY / "runtime-budget-review.md"
CONTENT = (
    "The NIST GAI Profile identifies actions for governing and measuring GAI risks.\n\n"
    "Organizations should evaluate GAI outputs against known ground truth data."
)


class FixtureDiscovery:
    def __init__(self):
        self.calls = []

    def discover(self, *, query, allowed_domains, maximum_results):
        self.calls.append((query, allowed_domains, maximum_results))
        return (
            Stage9OfficialSourceCandidate(
                url="https://example.com/untrusted", title="Untrusted"
            ),
            Stage9OfficialSourceCandidate(
                url="https://www.nist.gov/gai-profile", title="NIST GAI Profile"
            ),
        )


class FixtureReader:
    def __init__(self):
        self.calls = []

    def read(self, *, url):
        self.calls.append(url)
        return Stage9OfficialWebDocument(
            url=url,
            title="NIST GAI Profile",
            content=CONTENT,
            retrieved_at="2026-08-30T12:00:00+09:00",
            response_sha256=hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(),
        )


class UnusedProvider:
    def acquire(self, *, request, channel):
        raise AssertionError(f"unexpected channel: {request.case_id}:{channel.value}")


class UnusedLoopFactory:
    def create(self, *, case_id, packing):
        raise AssertionError(f"loop must not run: {case_id}:{len(packing.items)}")


def test_verified_discovery_integrates_with_runtime_router_and_packing() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == "tech-01"
    )
    request = Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id="stage9-verified-official-tech-01",
    )
    discovery = FixtureDiscovery()
    reader = FixtureReader()
    official = Stage9VerifiedOfficialWebAcquisitionAdapter(
        provider=Stage9VerifiedOfficialSourceProvider(
            discovery=discovery,
            reader=reader,
        )
    )
    unused = UnusedProvider()
    runtime = create_stage9_development_runtime(
        experiment=experiment,
        official_web=official,
        scholarly_primary=unused,
        epo_patent=unused,
        local_repository=unused,
        packed_loop_factory=UnusedLoopFactory(),
    )

    acquisition = runtime.acquisition_router.acquire(request)
    packing = Stage9AcquisitionContextBuilder().build(acquisition)

    assert acquisition.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert acquisition.usage.provider_requests == 1
    assert acquisition.usage.external_requests == 2
    assert acquisition.usage.documents_read == 1
    assert reader.calls == ["https://www.nist.gov/gai-profile"]
    assert discovery.calls[0][1] == ("nist.gov",)
    assert discovery.calls[0][0].endswith("site:nist.gov")
    assert packing.included
    assert all(
        item.retrieval.chunk.metadata["source_url"].startswith("https://www.nist.gov/")
        for item in packing.included
    )
    assert all(
        "golden" not in value.casefold()
        for item in acquisition.evidence_set.document_set.documents
        for value in item.candidate.metadata.values()
        if value != "false"
    )
