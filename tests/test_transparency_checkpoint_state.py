from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.exceptions import (
    TransparencyCheckpointConsistencyRequiredError,
    TransparencyCheckpointRollbackError,
    TransparencyCheckpointSplitViewError,
)
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationResult,
    TransparencyConsistencyProofVerificationResult,
)
from app.transparency_checkpoint_state import (
    TRANSPARENCY_CHECKPOINT_STATE_TYPE,
    TRANSPARENCY_CHECKPOINT_STATE_VERSION,
    TransparencyCheckpointStatePayload,
    apply_verified_checkpoint_to_state,
    checkpoint_state_lock_path_for,
    load_transparency_checkpoint_state,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def checkpoint(*, size: int, root: str, digest: str | None = None) -> TransparencyCheckpointVerificationResult:
    return TransparencyCheckpointVerificationResult(
        checkpoint_version=1,
        log_id="log-1",
        tree_size=size,
        root_hash=root,
        last_entry_hash=f"{size:064x}",
        issued_at=NOW,
        log_signing_key_id="log-key-1",
        checkpoint_sha256=digest or root,
    )


def consistency(old: TransparencyCheckpointVerificationResult, new: TransparencyCheckpointVerificationResult) -> TransparencyConsistencyProofVerificationResult:
    return TransparencyConsistencyProofVerificationResult(
        log_id="log-1",
        old_tree_size=old.tree_size,
        new_tree_size=new.tree_size,
        old_root_hash=old.root_hash,
        new_root_hash=new.root_hash,
    )


def test_state_payload_contract() -> None:
    state = TransparencyCheckpointStatePayload(
        state_version=TRANSPARENCY_CHECKPOINT_STATE_VERSION,
        state_type=TRANSPARENCY_CHECKPOINT_STATE_TYPE,
        log_id="log-1",
        highest_tree_size=1,
        highest_root_hash="a" * 64,
        highest_checkpoint_sha256="b" * 64,
        log_signing_key_id="log-key-1",
        updated_at=NOW,
    )

    assert state.updated_at == NOW
    with pytest.raises(ValidationError):
        TransparencyCheckpointStatePayload.model_validate({**state.model_dump(mode="json"), "extra": "blocked"})


def test_first_checkpoint_tofu_creates_state(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    cp = checkpoint(size=1, root="a" * 64, digest="b" * 64)

    result = apply_verified_checkpoint_to_state(
        state_path=state_path,
        checkpoint=cp,
        consistency_proof=None,
        updated_at=NOW,
    )

    assert result.stored_state is None
    assert result.state_updated is True
    assert load_transparency_checkpoint_state(path=state_path).highest_tree_size == 1
    assert oct(state_path.stat().st_mode & 0o777) == "0o600"
    assert oct(checkpoint_state_lock_path_for(state_path).stat().st_mode & 0o777) == "0o600"


def test_same_checkpoint_is_idempotent(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    cp = checkpoint(size=1, root="a" * 64, digest="b" * 64)
    apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=cp, consistency_proof=None, updated_at=NOW)

    result = apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=cp, consistency_proof=None, updated_at=NOW)

    assert result.state_updated is False


def test_rollback_is_rejected(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    old = checkpoint(size=1, root="a" * 64, digest="b" * 64)
    new = checkpoint(size=2, root="c" * 64, digest="d" * 64)
    apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=new, consistency_proof=None, updated_at=NOW)

    with pytest.raises(TransparencyCheckpointRollbackError):
        apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=old, consistency_proof=None, updated_at=NOW)


def test_same_size_different_root_is_split_view(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    first = checkpoint(size=1, root="a" * 64, digest="b" * 64)
    second = checkpoint(size=1, root="c" * 64, digest="d" * 64)
    apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=first, consistency_proof=None, updated_at=NOW)

    with pytest.raises(TransparencyCheckpointSplitViewError):
        apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=second, consistency_proof=None, updated_at=NOW)


def test_larger_checkpoint_requires_consistency_proof(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    old = checkpoint(size=1, root="a" * 64, digest="b" * 64)
    new = checkpoint(size=2, root="c" * 64, digest="d" * 64)
    apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=old, consistency_proof=None, updated_at=NOW)

    with pytest.raises(TransparencyCheckpointConsistencyRequiredError):
        apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=new, consistency_proof=None, updated_at=NOW)


def test_larger_checkpoint_updates_with_consistency_proof(tmp_path: Path) -> None:
    state_path = tmp_path / "checkpoint-state.json"
    old = checkpoint(size=1, root="a" * 64, digest="b" * 64)
    new = checkpoint(size=2, root="c" * 64, digest="d" * 64)
    apply_verified_checkpoint_to_state(state_path=state_path, checkpoint=old, consistency_proof=None, updated_at=NOW)

    result = apply_verified_checkpoint_to_state(
        state_path=state_path,
        checkpoint=new,
        consistency_proof=consistency(old, new),
        updated_at=NOW,
    )

    assert result.state_updated is True
    assert result.current_state.highest_tree_size == 2
