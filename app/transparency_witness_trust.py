"""Trust store policy for local transparency witnesses."""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.exceptions import TransparencyWitnessTrustStoreError

TRANSPARENCY_WITNESS_TRUST_STORE_VERSION = 1
TRANSPARENCY_WITNESS_TRUST_STORE_TYPE = "audit_report_transparency_witness_trust_store"
MAX_TRANSPARENCY_WITNESS_TRUST_STORE_BYTES = 256 * 1024
RAW_WITNESS_PUBLIC_KEY_BYTES = 32

_MESSAGE = "The transparency witness trust store is invalid."
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class TransparencyWitnessStatus(str, Enum):
    ACTIVE = "active"
    VERIFY_ONLY = "verify_only"
    REVOKED = "revoked"


class RevokedWitnessPolicy(str, Enum):
    REJECT = "reject"
    ALLOW_PRE_REVOCATION = "allow_pre_revocation"


class _WitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TransparencyWitnessTrustEntry(_WitnessModel):
    witness_id: str = Field(min_length=1, max_length=128)
    public_key_b64: str
    status: TransparencyWitnessStatus
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None

    @field_validator("witness_id")
    @classmethod
    def _validate_witness_id(cls, value: str) -> str:
        if not is_valid_witness_id(value):
            raise ValueError("invalid witness id")
        return value

    @field_validator("public_key_b64")
    @classmethod
    def _validate_public_key(cls, value: str) -> str:
        decode_witness_public_key_b64(value)
        return value

    @field_validator("valid_from", "valid_until", "revoked_at")
    @classmethod
    def _validate_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_aware_datetime(value)

    @model_validator(mode="after")
    def _validate_status_time(self) -> TransparencyWitnessTrustEntry:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("invalid validity window")
        if self.revoked_at is not None and self.revoked_at < self.valid_from:
            raise ValueError("invalid revocation time")
        if self.status is TransparencyWitnessStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked witnesses require revoked_at")
        if self.status is not TransparencyWitnessStatus.REVOKED and self.revoked_at is not None:
            raise ValueError("non-revoked witnesses cannot have revoked_at")
        return self

    def public_key_bytes(self) -> bytes:
        return decode_witness_public_key_b64(self.public_key_b64)


class TransparencyWitnessTrustStorePayload(_WitnessModel):
    trust_store_version: Literal[TRANSPARENCY_WITNESS_TRUST_STORE_VERSION]
    trust_store_type: Literal[TRANSPARENCY_WITNESS_TRUST_STORE_TYPE]
    log_id: str = Field(min_length=1, max_length=128)
    minimum_quorum: int = Field(ge=1)
    witnesses: tuple[TransparencyWitnessTrustEntry, ...]

    @field_validator("minimum_quorum")
    @classmethod
    def _validate_quorum(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("invalid quorum")
        return value

    @model_validator(mode="after")
    def _validate_store(self) -> TransparencyWitnessTrustStorePayload:
        ids: set[str] = set()
        keys: set[bytes] = set()
        active_count = 0
        for witness in self.witnesses:
            if witness.witness_id in ids:
                raise ValueError("duplicate witness id")
            ids.add(witness.witness_id)
            public_key = witness.public_key_bytes()
            if public_key in keys:
                raise ValueError("duplicate witness public key")
            keys.add(public_key)
            if witness.status is TransparencyWitnessStatus.ACTIVE:
                active_count += 1
        if active_count < self.minimum_quorum:
            raise ValueError("not enough active witnesses")
        return self

    def get_witness(self, witness_id: str) -> TransparencyWitnessTrustEntry:
        if not is_valid_witness_id(witness_id):
            raise TransparencyWitnessTrustStoreError(_MESSAGE)
        for witness in self.witnesses:
            if witness.witness_id == witness_id:
                return witness
        raise TransparencyWitnessTrustStoreError(_MESSAGE)


def is_valid_witness_id(value: object) -> bool:
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None


def decode_witness_public_key_b64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as error:
        raise TransparencyWitnessTrustStoreError(_MESSAGE) from error
    if len(decoded) != RAW_WITNESS_PUBLIC_KEY_BYTES:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    try:
        Ed25519PublicKey.from_public_bytes(decoded)
    except ValueError as error:
        raise TransparencyWitnessTrustStoreError(_MESSAGE) from error
    return decoded


def normalize_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)


def load_transparency_witness_trust_store(*, path: Path) -> TransparencyWitnessTrustStorePayload:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    if path.is_symlink() or path.is_dir():
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSPARENCY_WITNESS_TRUST_STORE_BYTES:
            raise TransparencyWitnessTrustStoreError(_MESSAGE)
        payload = _loads_no_duplicate_keys(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TransparencyWitnessTrustStoreError(_MESSAGE)
        return TransparencyWitnessTrustStorePayload.model_validate_json(json.dumps(payload))
    except OSError as error:
        raise TransparencyWitnessTrustStoreError(_MESSAGE) from error
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise TransparencyWitnessTrustStoreError(_MESSAGE) from error


def ensure_witness_trusted_for_verification(
    *,
    witness: TransparencyWitnessTrustEntry,
    observed_at: datetime,
    verification_time: datetime,
    revoked_witness_policy: RevokedWitnessPolicy,
    maximum_clock_skew: timedelta,
) -> None:
    observed = normalize_aware_datetime(observed_at)
    verified = normalize_aware_datetime(verification_time)
    if maximum_clock_skew < timedelta(0):
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    if observed > verified + maximum_clock_skew:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    if observed < witness.valid_from:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    if witness.valid_until is not None and observed >= witness.valid_until:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    if witness.status in {TransparencyWitnessStatus.ACTIVE, TransparencyWitnessStatus.VERIFY_ONLY}:
        return
    if revoked_witness_policy is RevokedWitnessPolicy.REJECT:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)
    if witness.revoked_at is None or observed >= witness.revoked_at:
        raise TransparencyWitnessTrustStoreError(_MESSAGE)


def _loads_no_duplicate_keys(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransparencyWitnessTrustStoreError(_MESSAGE)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)
