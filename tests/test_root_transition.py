from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.exceptions import (
    ActiveManifestTrustStateBlocksRootTransitionError,
    RootTransitionMetadataMismatchError,
    RootTransitionValidationError,
)
from app.root_signature_trust import (
    RootSigningPrivateKey,
    TrustedRootSigningPublicKey,
    fingerprint_public_key,
)
from app.root_transition import (
    build_root_transition_manifest,
    export_root_transition_manifest,
    export_root_transition_signature,
    next_root_signature_path_for,
    previous_root_signature_path_for,
    sign_root_transition,
    verify_root_transition,
)
from app.root_trust_state import (
    apply_root_transition,
    initialize_root_trust_state,
    load_root_trust_state,
    trusted_root_public_key_from_state,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _private(key_id: str) -> RootSigningPrivateKey:
    private = Ed25519PrivateKey.generate()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return RootSigningPrivateKey(
        key_id=key_id,
        private_key_bytes=private_bytes,
        public_key_bytes=public_bytes,
        public_key_fingerprint=fingerprint_public_key(public_bytes),
    )


def _public(private: RootSigningPrivateKey) -> TrustedRootSigningPublicKey:
    return TrustedRootSigningPublicKey(
        key_id=private.key_id,
        public_key_bytes=private.public_key_bytes,
        public_key_fingerprint=private.public_key_fingerprint,
    )


def _write_transition(tmp_path: Path):
    old = _private("root-old")
    new = _private("root-new")
    path = tmp_path / "root-transition.json"
    transition = build_root_transition_manifest(
        issued_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(days=1),
        previous_root_public_key=_public(old),
        previous_root_epoch=1,
        next_root_public_key=_public(new),
        next_root_epoch=2,
    )
    old_sig, new_sig = sign_root_transition(
        transition=transition,
        previous_root_private_key=old,
        next_root_private_key=new,
        signed_at=NOW,
        filename=path.name,
    )
    export_root_transition_manifest(path=path, transition=transition)
    export_root_transition_signature(path=previous_root_signature_path_for(path), signature=old_sig)
    export_root_transition_signature(path=next_root_signature_path_for(path), signature=new_sig)
    return old, new, path


def test_cross_signed_transition_verifies(tmp_path: Path) -> None:
    old, _new, path = _write_transition(tmp_path)

    result = verify_root_transition(
        transition_path=path,
        current_root=_public(old),
        current_root_epoch=1,
        verification_time=NOW,
    )

    assert result.previous_root_epoch == 1
    assert result.next_root_epoch == 2
    assert result.is_active_for_application is True


def test_transition_requires_exact_epoch_increment() -> None:
    old = _private("root-old")
    new = _private("root-new")

    with pytest.raises(RootTransitionValidationError):
        build_root_transition_manifest(
            issued_at=NOW,
            valid_from=NOW,
            valid_until=NOW + timedelta(days=1),
            previous_root_public_key=_public(old),
            previous_root_epoch=1,
            next_root_public_key=_public(new),
            next_root_epoch=3,
        )


def test_current_root_must_match_previous_root(tmp_path: Path) -> None:
    _old, _new, path = _write_transition(tmp_path)
    other = _private("root-other")

    with pytest.raises(RootTransitionMetadataMismatchError):
        verify_root_transition(
            transition_path=path,
            current_root=_public(other),
            current_root_epoch=1,
            verification_time=NOW,
        )


def test_root_private_key_repr_hides_secret() -> None:
    key = _private("root-old")
    assert base64.b64encode(key.private_key_bytes).decode("ascii") not in repr(key)


def test_apply_root_transition_requires_retired_manifest_state(tmp_path: Path) -> None:
    old, _new, path = _write_transition(tmp_path)
    state_path = tmp_path / "root-state.json"
    active_manifest_state = tmp_path / "manifest-state.json"
    active_manifest_state.write_text("{}", encoding="utf-8")
    initialize_root_trust_state(
        path=state_path,
        root_public_key=_public(old),
        root_epoch=1,
        initialized_at=NOW,
    )

    with pytest.raises(ActiveManifestTrustStateBlocksRootTransitionError):
        apply_root_transition(
            transition_path=path,
            state_path=state_path,
            application_time=NOW,
            active_manifest_state_path=active_manifest_state,
        )


def test_apply_root_transition_updates_state_after_retire(tmp_path: Path) -> None:
    old, new, path = _write_transition(tmp_path)
    state_path = tmp_path / "root-state.json"
    initialize_root_trust_state(
        path=state_path,
        root_public_key=_public(old),
        root_epoch=1,
        initialized_at=NOW,
    )

    result = apply_root_transition(
        transition_path=path,
        state_path=state_path,
        application_time=NOW,
        active_manifest_state_path=tmp_path / "missing-manifest-state.json",
    )
    state = load_root_trust_state(path=state_path)

    assert result.state_updated is True
    assert state is not None
    assert state.current_root_epoch == 2
    assert trusted_root_public_key_from_state(state).key_id == new.key_id
