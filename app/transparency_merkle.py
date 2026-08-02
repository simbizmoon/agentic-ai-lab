"""Merkle tree and proof helpers for the local transparency log."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.exceptions import (
    TransparencyConsistencyProofMismatchError,
    TransparencyMerkleProofExportError,
    TransparencyMerkleProofReadError,
    TransparencyMerkleProofValidationError,
)
from app.report_integrity import is_valid_sha256_digest

TRANSPARENCY_MERKLE_VERSION = 1
TRANSPARENCY_MERKLE_LEAF_DOMAIN = b"agentic-ai-lab:transparency-merkle-leaf:sha256:v1"
TRANSPARENCY_MERKLE_NODE_DOMAIN = b"agentic-ai-lab:transparency-merkle-node:sha256:v1"
TRANSPARENCY_MERKLE_EMPTY_DOMAIN = b"agentic-ai-lab:transparency-merkle-empty:sha256:v1"
MAX_TRANSPARENCY_PROOF_HASHES = 256
MAX_TRANSPARENCY_PROOF_BYTES = 256 * 1024
PROOF_FILE_MODE = 0o600

INCLUSION_PROOF_TYPE = "audit_report_transparency_inclusion_proof"
CONSISTENCY_PROOF_TYPE = "audit_report_transparency_consistency_proof"
_VALIDATION_MESSAGE = "The transparency Merkle proof is invalid."
_READ_MESSAGE = "Failed to read the transparency Merkle proof."
_EXPORT_MESSAGE = "Failed to export the transparency Merkle proof."
_MISMATCH_MESSAGE = "The transparency consistency proof does not match."


class TransparencyMerkleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyInclusionProofPayload(TransparencyMerkleModel):
    proof_version: Literal[TRANSPARENCY_MERKLE_VERSION]
    proof_type: Literal[INCLUSION_PROOF_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    tree_size: int = Field(ge=1)
    leaf_index: int = Field(ge=0)
    sequence: int = Field(ge=1)
    entry_hash: str
    root_hash: str
    audit_path: tuple[str, ...]
    issued_at: datetime

    @field_validator("entry_hash", "root_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("audit_path")
    @classmethod
    def _validate_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > MAX_TRANSPARENCY_PROOF_HASHES:
            raise ValueError("proof too large")
        if any(not is_valid_sha256_digest(item) for item in value):
            raise ValueError("invalid proof hash")
        return value

    @field_validator("issued_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_bounds(self) -> TransparencyInclusionProofPayload:
        if self.leaf_index >= self.tree_size:
            raise ValueError("leaf index out of bounds")
        if self.sequence != self.leaf_index + 1:
            raise ValueError("sequence mismatch")
        return self


class TransparencyConsistencyProofPayload(TransparencyMerkleModel):
    proof_version: Literal[TRANSPARENCY_MERKLE_VERSION]
    proof_type: Literal[CONSISTENCY_PROOF_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    old_tree_size: int = Field(ge=1)
    new_tree_size: int = Field(ge=1)
    old_root_hash: str
    new_root_hash: str
    consistency_path: tuple[str, ...]
    issued_at: datetime

    @field_validator("old_root_hash", "new_root_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if not is_valid_sha256_digest(value):
            raise ValueError("invalid hash")
        return value

    @field_validator("consistency_path")
    @classmethod
    def _validate_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > MAX_TRANSPARENCY_PROOF_HASHES:
            raise ValueError("proof too large")
        if any(not is_valid_sha256_digest(item) for item in value):
            raise ValueError("invalid proof hash")
        return value

    @field_validator("issued_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        return _normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_sizes(self) -> TransparencyConsistencyProofPayload:
        if self.old_tree_size > self.new_tree_size:
            raise ValueError("old tree is larger")
        return self


def calculate_transparency_leaf_hash(entry_hash: str) -> str:
    if not is_valid_sha256_digest(entry_hash):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    digest = hashlib.sha256()
    digest.update(TRANSPARENCY_MERKLE_LEAF_DOMAIN)
    digest.update(b"\0")
    digest.update(bytes.fromhex(entry_hash))
    return digest.hexdigest()


def calculate_transparency_merkle_root(entry_hashes: Sequence[str]) -> str:
    leaf_hashes = tuple(calculate_transparency_leaf_hash(entry_hash) for entry_hash in entry_hashes)
    if not leaf_hashes:
        digest = hashlib.sha256()
        digest.update(TRANSPARENCY_MERKLE_EMPTY_DOMAIN)
        digest.update(b"\0")
        return digest.hexdigest()
    return _merkle_root_from_leaf_hashes(leaf_hashes)


def generate_inclusion_audit_path(*, entry_hashes: Sequence[str], leaf_index: int) -> tuple[str, ...]:
    if not isinstance(leaf_index, int) or isinstance(leaf_index, bool):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    leaf_hashes = tuple(calculate_transparency_leaf_hash(entry_hash) for entry_hash in entry_hashes)
    if leaf_index < 0 or leaf_index >= len(leaf_hashes):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    return _inclusion_path_from_leaf_hashes(leaf_hashes, leaf_index)


def calculate_root_from_inclusion_proof(
    *,
    entry_hash: str,
    leaf_index: int,
    tree_size: int,
    audit_path: Sequence[str],
) -> str:
    if tree_size < 1 or leaf_index < 0 or leaf_index >= tree_size:
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    if len(audit_path) > MAX_TRANSPARENCY_PROOF_HASHES:
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    path = tuple(_validate_hex_hash(item) for item in audit_path)
    root, consumed = _root_from_inclusion_path(
        leaf_hash=calculate_transparency_leaf_hash(entry_hash),
        leaf_index=leaf_index,
        tree_size=tree_size,
        path=path,
        offset=0,
    )
    if consumed != len(path):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    return root


def generate_consistency_path(
    *,
    entry_hashes: Sequence[str],
    old_tree_size: int,
    new_tree_size: int,
) -> tuple[str, ...]:
    if old_tree_size < 1 or new_tree_size < old_tree_size or new_tree_size > len(entry_hashes):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    if old_tree_size == new_tree_size:
        return ()
    leaf_hashes = tuple(calculate_transparency_leaf_hash(entry_hash) for entry_hash in entry_hashes[:new_tree_size])
    return _consistency_subproof(old_tree_size, leaf_hashes, True)


def verify_consistency_path(
    *,
    old_tree_size: int,
    new_tree_size: int,
    old_root_hash: str,
    new_root_hash: str,
    consistency_path: Sequence[str],
) -> bool:
    if old_tree_size < 1 or new_tree_size < old_tree_size:
        return False
    if not is_valid_sha256_digest(old_root_hash) or not is_valid_sha256_digest(new_root_hash):
        return False
    path = tuple(consistency_path)
    if len(path) > MAX_TRANSPARENCY_PROOF_HASHES or any(not is_valid_sha256_digest(item) for item in path):
        return False
    if old_tree_size == new_tree_size:
        return old_root_hash == new_root_hash and not path
    fn = old_tree_size - 1
    sn = new_tree_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    if fn == 0:
        old_hash = old_root_hash
        new_hash = old_root_hash
        index = 0
    else:
        if not path:
            return False
        old_hash = path[0]
        new_hash = path[0]
        index = 1
    while index < len(path):
        proof_hash = path[index]
        if fn & 1 or fn == sn:
            old_hash = _node_hash(proof_hash, old_hash)
            new_hash = _node_hash(proof_hash, new_hash)
            while fn and not (fn & 1):
                fn >>= 1
                sn >>= 1
        else:
            new_hash = _node_hash(new_hash, proof_hash)
        fn >>= 1
        sn >>= 1
        index += 1
    return old_hash == old_root_hash and new_hash == new_root_hash

def canonicalize_inclusion_proof(proof: TransparencyInclusionProofPayload) -> bytes:
    return _canonicalize_model(proof)


def canonicalize_consistency_proof(proof: TransparencyConsistencyProofPayload) -> bytes:
    return _canonicalize_model(proof)


def transparency_inclusion_proof_digest(proof: TransparencyInclusionProofPayload) -> str:
    return hashlib.sha256(canonicalize_inclusion_proof(proof)).hexdigest()


def transparency_consistency_proof_digest(proof: TransparencyConsistencyProofPayload) -> str:
    return hashlib.sha256(canonicalize_consistency_proof(proof)).hexdigest()


def load_transparency_inclusion_proof(*, path: Path) -> TransparencyInclusionProofPayload:
    return TransparencyInclusionProofPayload.model_validate_json(json.dumps(_load_proof_json(path=path)))


def load_transparency_consistency_proof(*, path: Path) -> TransparencyConsistencyProofPayload:
    return TransparencyConsistencyProofPayload.model_validate_json(json.dumps(_load_proof_json(path=path)))


def export_transparency_inclusion_proof(*, path: Path, proof: TransparencyInclusionProofPayload) -> None:
    _export_proof(path=path, text=json.dumps(proof.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False))


def export_transparency_consistency_proof(*, path: Path, proof: TransparencyConsistencyProofPayload) -> None:
    _export_proof(path=path, text=json.dumps(proof.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=False))


def _merkle_root_from_leaf_hashes(leaf_hashes: Sequence[str]) -> str:
    if len(leaf_hashes) == 1:
        return leaf_hashes[0]
    split = _largest_power_of_two_less_than(len(leaf_hashes))
    return _node_hash(
        _merkle_root_from_leaf_hashes(leaf_hashes[:split]),
        _merkle_root_from_leaf_hashes(leaf_hashes[split:]),
    )


def _node_hash(left_hash: str, right_hash: str) -> str:
    digest = hashlib.sha256()
    digest.update(TRANSPARENCY_MERKLE_NODE_DOMAIN)
    digest.update(b"\0")
    digest.update(bytes.fromhex(left_hash))
    digest.update(bytes.fromhex(right_hash))
    return digest.hexdigest()


def _inclusion_path_from_leaf_hashes(leaf_hashes: Sequence[str], leaf_index: int) -> tuple[str, ...]:
    if len(leaf_hashes) == 1:
        return ()
    split = _largest_power_of_two_less_than(len(leaf_hashes))
    if leaf_index < split:
        return (*_inclusion_path_from_leaf_hashes(leaf_hashes[:split], leaf_index), _merkle_root_from_leaf_hashes(leaf_hashes[split:]))
    return (*_inclusion_path_from_leaf_hashes(leaf_hashes[split:], leaf_index - split), _merkle_root_from_leaf_hashes(leaf_hashes[:split]))


def _root_from_inclusion_path(
    *,
    leaf_hash: str,
    leaf_index: int,
    tree_size: int,
    path: Sequence[str],
    offset: int,
) -> tuple[str, int]:
    if tree_size == 1:
        return leaf_hash, offset
    split = _largest_power_of_two_less_than(tree_size)
    if leaf_index < split:
        left_hash, consumed = _root_from_inclusion_path(
            leaf_hash=leaf_hash,
            leaf_index=leaf_index,
            tree_size=split,
            path=path,
            offset=offset,
        )
        if consumed >= len(path):
            raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
        return _node_hash(left_hash, path[consumed]), consumed + 1
    right_hash, consumed = _root_from_inclusion_path(
        leaf_hash=leaf_hash,
        leaf_index=leaf_index - split,
        tree_size=tree_size - split,
        path=path,
        offset=offset,
    )
    if consumed >= len(path):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    return _node_hash(path[consumed], right_hash), consumed + 1


def _consistency_subproof(size: int, leaf_hashes: Sequence[str], complete_subtree: bool) -> tuple[str, ...]:
    if size == len(leaf_hashes):
        return () if complete_subtree else (_merkle_root_from_leaf_hashes(leaf_hashes),)
    split = _largest_power_of_two_less_than(len(leaf_hashes))
    if size <= split:
        return (*_consistency_subproof(size, leaf_hashes[:split], complete_subtree), _merkle_root_from_leaf_hashes(leaf_hashes[split:]))
    return (*_consistency_subproof(size - split, leaf_hashes[split:], False), _merkle_root_from_leaf_hashes(leaf_hashes[:split]))


def _verify_consistency_recursive(
    *,
    old_size: int,
    new_size: int,
    path: Sequence[str],
    offset: int,
    old_root: str,
) -> tuple[str, str, int]:
    if old_size == new_size:
        return old_root, old_root, offset
    split = _largest_power_of_two_less_than(new_size)
    if old_size <= split:
        old_calc, left_new, consumed = _verify_consistency_recursive(
            old_size=old_size,
            new_size=split,
            path=path,
            offset=offset,
            old_root=old_root,
        )
        if consumed >= len(path):
            raise TransparencyConsistencyProofMismatchError(_MISMATCH_MESSAGE)
        return old_calc, _node_hash(left_new, path[consumed]), consumed + 1
    right_old, right_new, consumed = _verify_consistency_recursive(
        old_size=old_size - split,
        new_size=new_size - split,
        path=path,
        offset=offset,
        old_root="",
    )
    if consumed >= len(path):
        raise TransparencyConsistencyProofMismatchError(_MISMATCH_MESSAGE)
    left = path[consumed]
    return _node_hash(left, right_old), _node_hash(left, right_new), consumed + 1


def _largest_power_of_two_less_than(value: int) -> int:
    return 1 << ((value - 1).bit_length() - 1)


def _validate_hex_hash(value: str) -> str:
    if not is_valid_sha256_digest(value):
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    return value


def _canonicalize_model(model: BaseModel) -> bytes:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_proof_json(*, path: Path) -> object:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSPARENCY_PROOF_BYTES:
            raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
        text = path.read_text(encoding="utf-8")
        return _loads_no_duplicate_keys(text)
    except OSError as error:
        raise TransparencyMerkleProofReadError(_READ_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE) from error


def _export_proof(*, path: Path, text: str) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
    temp_path: Path | None = None
    replaced = False
    dir_fd: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as tmp:
            temp_path = Path(tmp.name)
            tmp.write(text.rstrip("\n") + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            os.chmod(temp_path, PROOF_FILE_MODE)
        os.replace(temp_path, path)
        replaced = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as error:
        raise TransparencyMerkleProofExportError(_EXPORT_MESSAGE) from error
    finally:
        if dir_fd is not None:
            try:
                os.close(dir_fd)
            except OSError:
                pass
        if temp_path is not None and not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyMerkleProofValidationError(_VALIDATION_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)
