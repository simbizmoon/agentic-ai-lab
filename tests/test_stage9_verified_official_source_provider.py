"""Offline tests for verified two-step official-source acquisition."""

from __future__ import annotations

import hashlib

import pytest

from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebDocument,
)
from app.research.stage9_verified_official_source_provider import (
    Stage9OfficialSourceCandidate,
    Stage9VerifiedOfficialSourceProvider,
    Stage9VerifiedOfficialSourceProviderError,
)

CONTENT = "# NIST GAI Profile\n\nExact controlled official content."


def _document(url: str) -> Stage9OfficialWebDocument:
    return Stage9OfficialWebDocument(
        url=url,
        title="NIST official document",
        content=CONTENT,
        retrieved_at="2026-08-30T12:00:00+09:00",
        response_sha256=hashlib.sha256(CONTENT.encode("utf-8")).hexdigest(),
    )


class FixtureDiscovery:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def discover(self, *, query, allowed_domains, maximum_results):
        self.calls.append((query, allowed_domains, maximum_results))
        return self.candidates


class FixtureReader:
    def __init__(self, redirects=None):
        self.redirects = redirects or {}
        self.calls = []

    def read(self, *, url):
        self.calls.append(url)
        return _document(self.redirects.get(url, url))


def test_reads_only_candidates_validated_before_network_read() -> None:
    official = "https://www.nist.gov/publications/gai-profile"
    discovery = FixtureDiscovery(
        (
            Stage9OfficialSourceCandidate(
                url="https://example.com/untrusted", title="Untrusted"
            ),
            Stage9OfficialSourceCandidate(url=official, title="NIST GAI Profile"),
        )
    )
    reader = FixtureReader()

    batch = Stage9VerifiedOfficialSourceProvider(
        discovery=discovery, reader=reader
    ).acquire(
        query="NIST GAI risk actions",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert reader.calls == [official]
    assert len(batch.documents) == 1
    assert batch.rejected_candidates == 1
    assert batch.discovery_provider_requests == 1
    assert batch.exact_read_external_requests == 1
    assert batch.total_external_requests == 2


def test_duplicate_candidate_is_not_read_twice() -> None:
    official = "https://nvlpubs.nist.gov/example.pdf"
    candidate = Stage9OfficialSourceCandidate(url=official, title="NIST publication")
    reader = FixtureReader()

    batch = Stage9VerifiedOfficialSourceProvider(
        discovery=FixtureDiscovery((candidate, candidate)), reader=reader
    ).acquire(
        query="NIST publication",
        allowed_domains=("nist.gov",),
        maximum_results=2,
    )

    assert reader.calls == [official]
    assert batch.rejected_candidates == 1


def test_rejects_reader_redirect_outside_official_domain() -> None:
    official = "https://www.nist.gov/example"
    provider = Stage9VerifiedOfficialSourceProvider(
        discovery=FixtureDiscovery(
            (Stage9OfficialSourceCandidate(url=official, title="NIST"),)
        ),
        reader=FixtureReader({official: "https://example.com/redirect"}),
    )

    with pytest.raises(Stage9VerifiedOfficialSourceProviderError, match="boundary"):
        provider.acquire(
            query="NIST",
            allowed_domains=("nist.gov",),
            maximum_results=1,
        )


def test_rejects_discovery_result_over_hard_boundary_without_reads() -> None:
    candidates = tuple(
        Stage9OfficialSourceCandidate(
            url=f"https://www.nist.gov/example-{index}", title=f"NIST {index}"
        )
        for index in range(3)
    )
    reader = FixtureReader()

    with pytest.raises(Stage9VerifiedOfficialSourceProviderError, match="boundary"):
        Stage9VerifiedOfficialSourceProvider(
            discovery=FixtureDiscovery(candidates), reader=reader
        ).acquire(
            query="NIST",
            allowed_domains=("nist.gov",),
            maximum_results=2,
        )

    assert reader.calls == []
