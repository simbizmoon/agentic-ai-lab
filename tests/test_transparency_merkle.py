from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.exceptions import TransparencyMerkleProofValidationError
from app.transparency_merkle import (
    CONSISTENCY_PROOF_TYPE,
    INCLUSION_PROOF_TYPE,
    TRANSPARENCY_MERKLE_VERSION,
    TransparencyConsistencyProofPayload,
    TransparencyInclusionProofPayload,
    calculate_root_from_inclusion_proof,
    calculate_transparency_leaf_hash,
    calculate_transparency_merkle_root,
    export_transparency_inclusion_proof,
    generate_consistency_path,
    generate_inclusion_audit_path,
    load_transparency_inclusion_proof,
    verify_consistency_path,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def hashes(count: int) -> list[str]:
    return [f"{index + 1:064x}" for index in range(count)]


def test_leaf_hash_is_domain_separated_and_validates_input() -> None:
    entry_hash = "a" * 64

    assert calculate_transparency_leaf_hash(entry_hash) != entry_hash
    assert len(calculate_transparency_leaf_hash(entry_hash)) == 64
    with pytest.raises(TransparencyMerkleProofValidationError):
        calculate_transparency_leaf_hash("PRIVATE-BAD-HASH")


def test_merkle_root_depends_on_leaf_order() -> None:
    values = hashes(3)

    assert calculate_transparency_merkle_root(values) != calculate_transparency_merkle_root(list(reversed(values)))


def test_merkle_root_handles_non_power_of_two_without_leaf_duplication() -> None:
    values = hashes(3)
    duplicated = [*values, values[-1]]

    assert calculate_transparency_merkle_root(values) != calculate_transparency_merkle_root(duplicated)


@pytest.mark.parametrize("index", [0, 2, 4])
def test_inclusion_proof_for_first_middle_last_leaf(index: int) -> None:
    values = hashes(5)
    proof = generate_inclusion_audit_path(entry_hashes=values, leaf_index=index)

    calculated = calculate_root_from_inclusion_proof(
        entry_hash=values[index],
        leaf_index=index,
        tree_size=len(values),
        audit_path=proof,
    )

    assert calculated == calculate_transparency_merkle_root(values)
    assert len(proof) < len(values)


def test_tampered_inclusion_sibling_is_rejected() -> None:
    values = hashes(5)
    proof = list(generate_inclusion_audit_path(entry_hashes=values, leaf_index=1))
    proof[0] = "f" * 64

    assert calculate_root_from_inclusion_proof(
        entry_hash=values[1],
        leaf_index=1,
        tree_size=len(values),
        audit_path=proof,
    ) != calculate_transparency_merkle_root(values)


@pytest.mark.parametrize(("old", "new"), [(1, 2), (2, 3), (3, 5), (5, 8), (8, 9)])
def test_consistency_proof_sizes(old: int, new: int) -> None:
    values = hashes(9)
    proof = generate_consistency_path(entry_hashes=values, old_tree_size=old, new_tree_size=new)

    assert verify_consistency_path(
        old_tree_size=old,
        new_tree_size=new,
        old_root_hash=calculate_transparency_merkle_root(values[:old]),
        new_root_hash=calculate_transparency_merkle_root(values[:new]),
        consistency_path=proof,
    )
    assert len(proof) < new


def test_consistency_proof_detects_past_leaf_change() -> None:
    values = hashes(5)
    proof = generate_consistency_path(entry_hashes=values, old_tree_size=3, new_tree_size=5)
    changed = [*values]
    changed[0] = "f" * 64

    assert not verify_consistency_path(
        old_tree_size=3,
        new_tree_size=5,
        old_root_hash=calculate_transparency_merkle_root(changed[:3]),
        new_root_hash=calculate_transparency_merkle_root(values[:5]),
        consistency_path=proof,
    )


def test_inclusion_payload_contract_and_file_roundtrip(tmp_path: Path) -> None:
    payload = TransparencyInclusionProofPayload(
        proof_version=TRANSPARENCY_MERKLE_VERSION,
        proof_type=INCLUSION_PROOF_TYPE,
        log_id="log-1",
        tree_size=1,
        leaf_index=0,
        sequence=1,
        entry_hash="a" * 64,
        root_hash=calculate_transparency_merkle_root(["a" * 64]),
        audit_path=(),
        issued_at=NOW,
    )
    path = tmp_path / "proof.json"
    export_transparency_inclusion_proof(path=path, proof=payload)

    assert load_transparency_inclusion_proof(path=path) == payload
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_proof_payload_rejects_extra_fields() -> None:
    data = {
        "proof_version": TRANSPARENCY_MERKLE_VERSION,
        "proof_type": CONSISTENCY_PROOF_TYPE,
        "log_id": "log-1",
        "old_tree_size": 1,
        "new_tree_size": 1,
        "old_root_hash": "a" * 64,
        "new_root_hash": "a" * 64,
        "consistency_path": (),
        "issued_at": NOW,
        "extra": "blocked",
    }

    with pytest.raises(ValidationError):
        TransparencyConsistencyProofPayload.model_validate(data)
