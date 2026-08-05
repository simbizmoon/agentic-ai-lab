"""Tests for local research document conversion."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.schemas.research_request import ResearchSourceType


def test_adapter_loads_markdown_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "grounded-research.md"
    path.write_text(
        (
            "# Grounded Research\n\n"
            "Grounded research connects claims to "
            "traceable evidence and citations."
        ),
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert len(bundle.source_records) == 1
    assert len(bundle.document_records) == 1

    source = bundle.source_records[0]
    document = bundle.document_records[0]

    assert source.title == "Grounded Research"
    assert source.source_type is ResearchSourceType.OTHER
    assert source.url.startswith(
        "https://local.aira.invalid/source/"
    )
    assert source.metadata["local_path"] == str(
        path.resolve()
    )
    assert "grounded" in source.keywords

    assert document.source_id == source.source_id
    assert document.url == source.url
    assert "traceable evidence" in document.content
    assert document.language == "en"
    assert document.metadata["filename"] == path.name


def test_adapter_uses_filename_when_heading_is_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agent_memory_notes.md"
    path.write_text(
        "Agent memory preserves useful prior context.",
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert (
        bundle.source_records[0].title
        == "agent memory notes"
    )


def test_adapter_detects_korean_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "연구자료.txt"
    path.write_text(
        (
            "근거 기반 연구는 출처와 증거를 연결하고 "
            "주장을 검증하는 과정이다."
        ),
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load((path,))

    assert bundle.document_records[0].language == "ko"


def test_adapter_loads_multiple_documents(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.txt"

    first.write_text(
        "# First Source\n\nEvidence from the first source.",
        encoding="utf-8",
    )
    second.write_text(
        "Evidence from the second source.",
        encoding="utf-8",
    )

    bundle = LocalDocumentAdapter().load(
        (
            first,
            second,
        )
    )

    assert len(bundle.source_records) == 2
    assert len(bundle.document_records) == 2
    assert (
        bundle.source_records[0].source_id
        != bundle.source_records[1].source_id
    )


def test_adapter_source_ids_are_stable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "# Stable Source\n\nStable content.",
        encoding="utf-8",
    )

    adapter = LocalDocumentAdapter()

    first = adapter.load((path,))
    second = adapter.load((path,))

    assert (
        first.source_records[0].source_id
        == second.source_records[0].source_id
    )


def test_adapter_rejects_empty_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.md"
    path.write_text(" \n\n ", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_rejects_non_utf8_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.txt"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(
        ValueError,
        match="not valid UTF-8",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_rejects_duplicate_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "# Source\n\nTraceable evidence.",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="duplicate local document",
    ):
        LocalDocumentAdapter().load(
            (
                path,
                path,
            )
        )


def test_adapter_rejects_unsupported_suffix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.pdf"
    path.write_bytes(b"PDF")

    with pytest.raises(
        ValueError,
        match="Markdown or text",
    ):
        LocalDocumentAdapter().load((path,))


def test_adapter_requires_at_least_one_document() -> None:
    with pytest.raises(
        ValueError,
        match="at least one local document",
    ):
        LocalDocumentAdapter().load(())
