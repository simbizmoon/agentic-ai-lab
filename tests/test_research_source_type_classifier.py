"""Tests for deterministic research source type classification."""

import pytest

from app.research.research_source_type_classifier import (
    ResearchSourceTypeClassifier,
)
from app.schemas.research_request import ResearchSourceType


def test_classifier_accepts_exact_trusted_official_host() -> None:
    classifier = ResearchSourceTypeClassifier(
        official_documentation_hosts=frozenset(
            {"openai.github.io"}
        )
    )

    assert classifier.classify(
        "https://openai.github.io/openai-agents-python/"
    ) is ResearchSourceType.OFFICIAL_DOCUMENTATION


def test_classifier_does_not_trust_other_github_io_hosts() -> None:
    classifier = ResearchSourceTypeClassifier(
        official_documentation_hosts=frozenset(
            {"openai.github.io"}
        )
    )

    assert classifier.classify(
        "https://example.github.io/project/"
    ) is ResearchSourceType.OTHER


def test_classifier_recognizes_existing_host_patterns() -> None:
    classifier = ResearchSourceTypeClassifier()

    assert classifier.classify(
        "https://developers.example.com/reference"
    ) is ResearchSourceType.OFFICIAL_DOCUMENTATION
    assert classifier.classify(
        "https://agency.gov/report"
    ) is ResearchSourceType.GOVERNMENT
    assert classifier.classify(
        "https://research.example.edu/paper"
    ) is ResearchSourceType.ACADEMIC


def test_classifier_rejects_blank_hosts() -> None:
    with pytest.raises(
        ValueError,
        match="nonblank unique hosts",
    ):
        ResearchSourceTypeClassifier(
            official_documentation_hosts=frozenset(
                {"openai.github.io", " "}
            )
        )
