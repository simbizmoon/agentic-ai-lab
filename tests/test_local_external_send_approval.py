from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research.local_document_access_policy import LocalDocumentAccessResult
from app.research.local_external_send_approval import (
    INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
    SEMANTIC_LOCAL_RESEARCH_PURPOSE,
    LocalExternalSendApproval,
    LocalExternalSendApprovalError,
    LocalExternalSendApprovalGate,
    LocalExternalSendSourceIdentity,
)


def _source(path: Path, content: bytes) -> LocalDocumentAccessResult:
    return LocalDocumentAccessResult(
        resolved_path=path.resolve(),
        file_size_bytes=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
    )


def test_gate_accepts_exact_approval(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    approval = LocalExternalSendApproval.for_semantic_local_research((source,))

    LocalExternalSendApprovalGate().validate(approval, (source,))


def test_models_are_strict_and_frozen(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    approval = LocalExternalSendApproval.for_semantic_local_research((source,))

    with pytest.raises(ValidationError):
        approval.approved = False
    with pytest.raises(ValidationError):
        LocalExternalSendApproval(
            purpose=SEMANTIC_LOCAL_RESEARCH_PURPOSE,
            approved=1,  # type: ignore[arg-type]
            sources=approval.sources,
        )


def test_gate_rejects_false_approval(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    approval = LocalExternalSendApproval.for_semantic_local_research(
        (source,), approved=False
    )

    with pytest.raises(LocalExternalSendApprovalError, match="explicit external-send"):
        LocalExternalSendApprovalGate().validate(approval, (source,))


def test_gate_rejects_wrong_purpose(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    identity = LocalExternalSendApproval.for_semantic_local_research((source,)).sources
    approval = LocalExternalSendApproval(
        purpose="different_purpose",
        approved=True,
        sources=identity,
    )

    with pytest.raises(LocalExternalSendApprovalError, match="purpose mismatch"):
        LocalExternalSendApprovalGate().validate(approval, (source,))


@pytest.mark.parametrize("extra_approved", [False, True])
def test_gate_rejects_missing_or_extra_source(
    tmp_path: Path,
    extra_approved: bool,
) -> None:
    first = _source(tmp_path / "first.txt", b"first")
    second = _source(tmp_path / "second.txt", b"second")
    approved = (first, second) if extra_approved else (first,)
    current = (first,) if extra_approved else (first, second)
    approval = LocalExternalSendApproval.for_semantic_local_research(approved)

    with pytest.raises(LocalExternalSendApprovalError, match="source sets"):
        LocalExternalSendApprovalGate().validate(approval, current)


def test_gate_rejects_digest_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    approved_source = _source(path, b"original")
    current_source = _source(path, b"changed!")
    approval = LocalExternalSendApproval.for_semantic_local_research((approved_source,))

    with pytest.raises(LocalExternalSendApprovalError, match="digest changed"):
        LocalExternalSendApprovalGate().validate(approval, (current_source,))


def test_gate_rejects_size_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    approved_source = _source(path, b"original")
    current_source = _source(path, b"larger content")
    approval = LocalExternalSendApproval.for_semantic_local_research((approved_source,))

    with pytest.raises(LocalExternalSendApprovalError, match="size changed"):
        LocalExternalSendApprovalGate().validate(approval, (current_source,))


def test_gate_treats_source_order_as_irrelevant(tmp_path: Path) -> None:
    first = _source(tmp_path / "first.txt", b"first")
    second = _source(tmp_path / "second.txt", b"second")
    approval = LocalExternalSendApproval.for_semantic_local_research((first, second))

    LocalExternalSendApprovalGate().validate(approval, (second, first))


def test_source_identity_rejects_malformed_digest(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="lowercase SHA-256"):
        LocalExternalSendSourceIdentity(
            resolved_path=(tmp_path / "source.txt").resolve(),
            content_sha256="invalid",
            file_size_bytes=1,
        )


def test_integrated_approval_accepts_only_integrated_purpose(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    integrated = LocalExternalSendApproval.for_integrated_web_local_research((source,))

    LocalExternalSendApprovalGate().validate(
        integrated,
        (source,),
        purpose=INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
    )
    with pytest.raises(LocalExternalSendApprovalError, match="purpose mismatch"):
        LocalExternalSendApprovalGate().validate(integrated, (source,))


def test_semantic_approval_cannot_authorize_integrated_research(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path / "source.txt", b"content")
    semantic = LocalExternalSendApproval.for_semantic_local_research((source,))

    with pytest.raises(LocalExternalSendApprovalError, match="purpose mismatch"):
        LocalExternalSendApprovalGate().validate(
            semantic,
            (source,),
            purpose=INTEGRATED_WEB_LOCAL_RESEARCH_PURPOSE,
        )
