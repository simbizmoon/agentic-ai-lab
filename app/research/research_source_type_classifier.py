"""Deterministic URL-based research source type classification."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.schemas.research_request import ResearchSourceType


class ResearchSourceTypeClassifier:
    """Classify source URLs using explicit trusted-host policy."""

    def __init__(
        self,
        *,
        official_documentation_hosts: frozenset[str] = frozenset(),
    ) -> None:
        normalized_hosts = frozenset(
            host.strip().casefold()
            for host in official_documentation_hosts
            if host.strip()
        )

        if len(normalized_hosts) != len(
            official_documentation_hosts
        ):
            raise ValueError(
                "official_documentation_hosts must contain "
                "nonblank unique hosts"
            )

        self._official_documentation_hosts = normalized_hosts

    @property
    def official_documentation_hosts(self) -> frozenset[str]:
        """Return exact trusted official-documentation hosts."""

        return self._official_documentation_hosts

    def classify(self, url: str) -> ResearchSourceType:
        """Return the deterministic source type for one URL."""

        host = (urlsplit(url.strip()).hostname or "").casefold()

        if host in self._official_documentation_hosts:
            return ResearchSourceType.OFFICIAL_DOCUMENTATION

        if host.startswith(
            ("docs.", "developer.", "developers.")
        ):
            return ResearchSourceType.OFFICIAL_DOCUMENTATION

        if (
            host.endswith((".gov", ".go.kr"))
            or ".gov." in host
        ):
            return ResearchSourceType.GOVERNMENT

        if (
            host.endswith((".edu", ".ac.kr"))
            or ".edu." in host
        ):
            return ResearchSourceType.ACADEMIC

        return ResearchSourceType.OTHER
