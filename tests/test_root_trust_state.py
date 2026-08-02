from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    RootTrustStateAlreadyExistsError,
    RootTrustStateValidationError,
)
from app.root_signature_trust import TrustedRootSigningPublicKey, fingerprint_public_key
from app.root_trust_state import (
    ROOT_STATE_FILE_MODE,
    build_initial_root_trust_state,
    export_root_trust_state,
    initialize_root_trust_state,
    load_root_trust_state,
    root_trust_state_lock_path_for,
    trusted_root_public_key_from_state,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _public(key_id: str = "root-key") -> TrustedRootSigningPublicKey:
    private = Ed25519PrivateKey.generate()
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return TrustedRootSigningPublicKey(
        key_id=key_id,
        public_key_bytes=public_bytes,
        public_key_fingerprint=fingerprint_public_key(public_bytes),
    )


def test_initial_root_trust_state_round_trip(tmp_path: Path) -> None:
    root = _public()
    path = tmp_path / "root-state.json"
    state = build_initial_root_trust_state(
        root_public_key=root,
        root_epoch=1,
        initialized_at=NOW,
    )

    export_root_trust_state(path=path, state=state)
    loaded = load_root_trust_state(path=path)

    assert loaded == state
    assert path.stat().st_mode & 0o777 == ROOT_STATE_FILE_MODE


def test_initialize_refuses_existing_state(tmp_path: Path) -> None:
    root = _public()
    path = tmp_path / "root-state.json"
    initialize_root_trust_state(path=path, root_public_key=root, root_epoch=1, initialized_at=NOW)

    with pytest.raises(RootTrustStateAlreadyExistsError):
        initialize_root_trust_state(path=path, root_public_key=root, root_epoch=1, initialized_at=NOW)


def test_lock_path_is_same_directory(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    assert root_trust_state_lock_path_for(path) == tmp_path / "state.json.lock"


def test_load_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "state.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink unsupported")

    with pytest.raises(RootTrustStateValidationError):
        load_root_trust_state(path=link)


def test_public_key_from_state_preserves_current_root() -> None:
    root = _public()
    state = build_initial_root_trust_state(
        root_public_key=root,
        root_epoch=3,
        initialized_at=NOW,
    )

    assert trusted_root_public_key_from_state(state) == root
