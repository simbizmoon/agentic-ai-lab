"""Quorum verification for transparency witness statements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.exceptions import (
    TransparencyWitnessEquivocationError,
    TransparencyWitnessQuorumError,
    TransparencyWitnessQuorumNotSatisfiedError,
)
from app.transparency_checkpoint import TransparencyCheckpointVerificationResult
from app.transparency_witness import (
    MAX_WITNESS_CLOCK_SKEW,
    TransparencyWitnessStatementVerificationResult,
    load_transparency_witness_statement,
    verify_transparency_witness_statement,
)
from app.transparency_witness_trust import (
    RevokedWitnessPolicy,
    TransparencyWitnessTrustStorePayload,
)

_QUORUM_MESSAGE = "The transparency witness quorum was not satisfied."
_EQUIVOCATION_MESSAGE = "A transparency witness signed conflicting checkpoints."


@dataclass(frozen=True)
class TransparencyWitnessQuorumResult:
    log_id: str
    tree_size: int
    root_hash: str
    checkpoint_sha256: str
    required_quorum: int
    valid_witness_count: int
    valid_witness_ids: tuple[str, ...]
    quorum_satisfied: bool


def verify_transparency_witness_quorum(
    *,
    checkpoint: TransparencyCheckpointVerificationResult,
    statement_paths: tuple[Path, ...] | list[Path],
    trust_store: TransparencyWitnessTrustStorePayload,
    verification_time: datetime,
    required_quorum: int | None = None,
    revoked_witness_policy: RevokedWitnessPolicy = RevokedWitnessPolicy.REJECT,
    maximum_clock_skew: timedelta = MAX_WITNESS_CLOCK_SKEW,
) -> TransparencyWitnessQuorumResult:
    if not isinstance(trust_store, TransparencyWitnessTrustStorePayload):
        raise TypeError("trust_store must be a TransparencyWitnessTrustStorePayload")
    if trust_store.log_id != checkpoint.log_id:
        raise TransparencyWitnessQuorumError(_QUORUM_MESSAGE)
    minimum = trust_store.minimum_quorum if required_quorum is None else required_quorum
    if isinstance(minimum, bool) or minimum < trust_store.minimum_quorum:
        raise TransparencyWitnessQuorumError(_QUORUM_MESSAGE)
    valid_by_witness: dict[str, TransparencyWitnessStatementVerificationResult] = {}
    for path in statement_paths:
        envelope = load_transparency_witness_statement(path=path)
        statement = envelope.statement
        existing = valid_by_witness.get(statement.witness_id)
        if existing is not None:
            if (
                existing.log_id != statement.log_id
                or existing.tree_size != statement.tree_size
                or existing.root_hash != statement.root_hash
                or existing.checkpoint_sha256 != statement.checkpoint_sha256
            ):
                raise TransparencyWitnessEquivocationError(_EQUIVOCATION_MESSAGE)
            continue
        result = verify_transparency_witness_statement(
            statement_path=path,
            checkpoint=checkpoint,
            trust_store=trust_store,
            verification_time=verification_time,
            revoked_witness_policy=revoked_witness_policy,
            maximum_clock_skew=maximum_clock_skew,
        )
        if (
            result.log_id != checkpoint.log_id
            or result.tree_size != checkpoint.tree_size
            or result.root_hash != checkpoint.root_hash
            or result.checkpoint_sha256 != checkpoint.checkpoint_sha256
        ):
            raise TransparencyWitnessQuorumError(_QUORUM_MESSAGE)
        valid_by_witness[result.witness_id] = result
    valid_ids = tuple(sorted(valid_by_witness))
    if len(valid_ids) < minimum:
        raise TransparencyWitnessQuorumNotSatisfiedError(_QUORUM_MESSAGE)
    return TransparencyWitnessQuorumResult(
        log_id=checkpoint.log_id,
        tree_size=checkpoint.tree_size,
        root_hash=checkpoint.root_hash,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        required_quorum=minimum,
        valid_witness_count=len(valid_ids),
        valid_witness_ids=valid_ids,
        quorum_satisfied=True,
    )
