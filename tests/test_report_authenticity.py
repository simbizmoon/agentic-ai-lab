from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app import report_authenticity
from app.authentication_trust import (
    AuthenticationKeyStatus,
    AuthenticationTrustStore,
    RevokedKeyPolicy,
    TrustedAuthenticationKey,
)
from app.exceptions import (
    AuditReportValidationError,
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    AuthenticationFromFutureError,
    InvalidAuthenticationFormatError,
    RejectedAuthenticationKeyError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
    UnknownAuthenticationKeyError,
)
from app.report_authenticity import (
    HMAC_ALGORITHM,
    HMAC_CHUNK_SIZE,
    HMAC_DOMAIN_SEPARATOR,
    HMAC_PROTOCOL_VERSION,
    MAX_AUTHENTICATION_CLOCK_SKEW,
    ReportAuthentication,
    ReportAuthenticityResult,
    authentication_path_for,
    build_report_authentication,
    calculate_report_hmac,
    export_authentication_file,
    format_report_authentication,
    is_valid_hmac_digest,
    is_valid_key_id,
    parse_report_authentication,
    verify_report_authenticity,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
SECRET = b"s" * 32
OTHER_SECRET = b"t" * 32
AUTHENTICATED_AT = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
VERIFICATION_TIME = datetime(2026, 8, 2, 0, 1, tzinfo=UTC)
REVOKED_AT = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
SECRET_TEXT = "SUPER-SECRET-HMAC-KEY"
PRIVATE_EXPORT_ERROR = "PRIVATE-EXPORT-ERROR"


def valid_json_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def key(
    key_id: str = "key-1",
    secret: bytes = SECRET,
    *,
    status: AuthenticationKeyStatus = AuthenticationKeyStatus.ACTIVE,
    valid_from: datetime = datetime(2026, 8, 1, 0, 0, tzinfo=UTC),
    valid_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> TrustedAuthenticationKey:
    return TrustedAuthenticationKey(
        key_id=key_id,
        secret=secret,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        revoked_at=revoked_at,
    )


def trust_store(*keys: TrustedAuthenticationKey) -> AuthenticationTrustStore:
    return AuthenticationTrustStore(keys=keys or (key(),))


def write_report(path: Path, text: str | None = None) -> Path:
    path.write_text(text if text is not None else valid_json_text(), encoding="utf-8")
    return path


def write_report_and_authentication(
    path: Path,
    *,
    signing_key: TrustedAuthenticationKey | None = None,
    authenticated_at: datetime = AUTHENTICATED_AT,
) -> tuple[Path, Path, ReportAuthentication]:
    write_report(path)
    authentication = build_report_authentication(
        report_path=path,
        key=signing_key or key(),
        authenticated_at=authenticated_at,
    )
    auth_path = authentication_path_for(path)
    export_authentication_file(authentication_path=auth_path, authentication=authentication)
    return path, auth_path, authentication


@pytest.mark.parametrize("value", ["key1", "key.1", "key_1", "key-1"])
def test_key_id_accepts_valid_values(value: str) -> None:
    assert is_valid_key_id(value) is True


@pytest.mark.parametrize("value", ["", "key 1", "key/1", r"key\1", "키", "a" * 65, 123])
def test_key_id_rejects_invalid_values(value: object) -> None:
    assert is_valid_key_id(value) is False


def test_hmac_digest_accepts_lowercase_sha256() -> None:
    assert is_valid_hmac_digest("a" * 64) is True


@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "a" * 65, "g" * 64])
def test_hmac_digest_rejects_invalid_values(value: str) -> None:
    assert is_valid_hmac_digest(value) is False


def test_authentication_path_for_appends_hmac(tmp_path: Path) -> None:
    assert authentication_path_for(tmp_path / "report.json").name == "report.json.hmac"


def test_authentication_path_for_uses_same_parent(tmp_path: Path) -> None:
    assert authentication_path_for(tmp_path / "report.json").parent == tmp_path


def test_authentication_path_for_rejects_non_path() -> None:
    with pytest.raises(TypeError):
        authentication_path_for("report.json")  # type: ignore[arg-type]


def test_hmac_protocol_v2_constants() -> None:
    assert HMAC_ALGORITHM == "hmac-sha256-v2"
    assert HMAC_PROTOCOL_VERSION == 2
    assert HMAC_DOMAIN_SEPARATOR.endswith(b"v2")
    assert MAX_AUTHENTICATION_CLOCK_SKEW == timedelta(minutes=5)


def test_hmac_same_key_file_time_and_name_is_stable(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    assert calculate_report_hmac(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    ) == calculate_report_hmac(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    )


@pytest.mark.parametrize("mutate", ["file", "filename", "key", "time", "key_id"])
def test_hmac_changes_when_bound_inputs_change(tmp_path: Path, mutate: str) -> None:
    report_path = write_report(tmp_path / "report.json")
    baseline = calculate_report_hmac(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    )

    if mutate == "file":
        report_path.write_text(
            valid_json_text().replace("gpt-5", "gpt-6"),
            encoding="utf-8",
        )
        changed = calculate_report_hmac(
            report_path=report_path,
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
        )
    elif mutate == "filename":
        other = write_report(tmp_path / "other.json")
        changed = calculate_report_hmac(
            report_path=other,
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
        )
    elif mutate == "key":
        changed = calculate_report_hmac(
            report_path=report_path,
            key=key(secret=OTHER_SECRET),
            authenticated_at=AUTHENTICATED_AT,
        )
    elif mutate == "time":
        changed = calculate_report_hmac(
            report_path=report_path,
            key=key(),
            authenticated_at=AUTHENTICATED_AT + timedelta(seconds=1),
        )
    else:
        changed = calculate_report_hmac(
            report_path=report_path,
            key=key("other-key"),
            authenticated_at=AUTHENTICATED_AT,
        )

    assert changed != baseline


def test_hmac_uses_domain_separator_key_id_timestamp_filename_and_bytes(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    expected = hmac.new(SECRET, digestmod="sha256")
    expected.update(HMAC_DOMAIN_SEPARATOR)
    expected.update(b"\0")
    expected.update(b"key-1")
    expected.update(b"\0")
    expected.update(AUTHENTICATED_AT.isoformat().encode("ascii"))
    expected.update(b"\0")
    expected.update(report_path.name.encode("utf-8"))
    expected.update(b"\0")
    expected.update(report_path.read_bytes())

    assert calculate_report_hmac(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    ) == expected.hexdigest()


def test_hmac_handles_multiple_chunks(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_bytes(b"a" * (HMAC_CHUNK_SIZE + 17))

    assert is_valid_hmac_digest(
        calculate_report_hmac(
            report_path=report_path,
            key=key(),
            authenticated_at=AUTHENTICATED_AT,
        )
    )


def test_hmac_rejects_symlink(tmp_path: Path) -> None:
    target = write_report(tmp_path / "target.json")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink is unavailable: {error}")

    with pytest.raises(ReportAuthenticationReadError):
        calculate_report_hmac(report_path=link, key=key(), authenticated_at=AUTHENTICATED_AT)


def test_hmac_converts_read_os_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    def broken_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise OSError(SECRET_TEXT)

    monkeypatch.setattr(Path, "open", broken_open)

    with pytest.raises(ReportAuthenticationReadError):
        calculate_report_hmac(report_path=report_path, key=key(), authenticated_at=AUTHENTICATED_AT)


def test_build_report_authentication_includes_authenticated_at(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    authentication = build_report_authentication(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    )

    assert authentication.authenticated_at == AUTHENTICATED_AT
    assert authentication.algorithm == HMAC_ALGORITHM
    assert authentication.protocol_version == HMAC_PROTOCOL_VERSION
    assert authentication.key_id == "key-1"
    assert authentication.filename == "report.json"
    assert is_valid_hmac_digest(authentication.digest)


def test_format_report_authentication_uses_v2_five_fields() -> None:
    text = format_report_authentication(
        ReportAuthentication(
            algorithm=HMAC_ALGORITHM,
            protocol_version=HMAC_PROTOCOL_VERSION,
            key_id="key-1",
            authenticated_at=AUTHENTICATED_AT,
            digest="a" * 64,
            filename="report.json",
        )
    )

    assert text.endswith("\n")
    assert text.count("  ") == 4
    assert text.split("  ")[0] == "hmac-sha256-v2"
    assert AUTHENTICATED_AT.isoformat() in text


def test_parse_report_authentication_accepts_v2_sidecar() -> None:
    parsed = parse_report_authentication(
        f"{HMAC_ALGORITHM}  key-1  {AUTHENTICATED_AT.isoformat()}  {'a' * 64}  report.json\n"
    )

    assert parsed.algorithm == HMAC_ALGORITHM
    assert parsed.protocol_version == HMAC_PROTOCOL_VERSION
    assert parsed.key_id == "key-1"
    assert parsed.authenticated_at == AUTHENTICATED_AT
    assert parsed.digest == "a" * 64
    assert parsed.filename == "report.json"


def test_parse_report_authentication_normalizes_timestamp_to_utc() -> None:
    parsed = parse_report_authentication(
        f"{HMAC_ALGORITHM}  key-1  2026-08-02T09:00:00+09:00  {'a' * 64}  report.json\n"
    )

    assert parsed.authenticated_at == AUTHENTICATED_AT


@pytest.mark.parametrize(
    "text",
    [
        "hmac-sha256  key-1  " + "a" * 64 + "  report.json\n",
        f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM} key-1 {AUTHENTICATED_AT.isoformat()} {'a' * 64} report.json\n",
        f"{HMAC_ALGORITHM}  key-1  {AUTHENTICATED_AT.isoformat()}  {'A' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  key/1  {AUTHENTICATED_AT.isoformat()}  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  key-1  not-a-date  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  key-1  2026-08-02T00:00:00  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  key-1  {AUTHENTICATED_AT.isoformat()}  {'a' * 64}  ../report.json\n",
    ],
)
def test_parse_report_authentication_rejects_invalid_sidecars(text: str) -> None:
    with pytest.raises(InvalidAuthenticationFormatError):
        parse_report_authentication(text)


def test_parse_report_authentication_error_omits_sidecar_text() -> None:
    secret_sidecar = f"{HMAC_ALGORITHM}  key-1  not-a-date  {'a' * 64}  {SECRET_TEXT}.json\n"

    with pytest.raises(InvalidAuthenticationFormatError) as exc_info:
        parse_report_authentication(secret_sidecar)

    assert SECRET_TEXT not in str(exc_info.value)


def test_format_report_authentication_rejects_bad_filename() -> None:
    with pytest.raises(InvalidAuthenticationFormatError):
        format_report_authentication(
            ReportAuthentication(
                algorithm=HMAC_ALGORITHM,
                protocol_version=HMAC_PROTOCOL_VERSION,
                key_id="key-1",
                authenticated_at=AUTHENTICATED_AT,
                digest="a" * 64,
                filename="../report.json",
            )
        )


def test_export_authentication_file_writes_atomically(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"
    authentication = ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id="key-1",
        authenticated_at=AUTHENTICATED_AT,
        digest="a" * 64,
        filename="report.json",
    )

    export_authentication_file(authentication_path=auth_path, authentication=authentication)

    assert auth_path.read_text(encoding="utf-8") == format_report_authentication(authentication)
    assert not list(tmp_path.glob("*.tmp"))


def test_export_authentication_file_replaces_existing_file(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"
    auth_path.write_text("old\n", encoding="utf-8")
    authentication = ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id="key-1",
        authenticated_at=AUTHENTICATED_AT,
        digest="a" * 64,
        filename="report.json",
    )

    export_authentication_file(authentication_path=auth_path, authentication=authentication)

    assert auth_path.read_text(encoding="utf-8") != "old\n"


def test_export_authentication_file_converts_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authentication = ReportAuthentication(
        algorithm=HMAC_ALGORITHM,
        protocol_version=HMAC_PROTOCOL_VERSION,
        key_id="key-1",
        authenticated_at=AUTHENTICATED_AT,
        digest="a" * 64,
        filename="report.json",
    )

    def broken_replace(source: object, target: object) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(os, "replace", broken_replace)

    with pytest.raises(AuthenticationExportError) as exc_info:
        export_authentication_file(
            authentication_path=tmp_path / "report.json.hmac",
            authentication=authentication,
        )

    assert PRIVATE_EXPORT_ERROR not in str(exc_info.value)


def test_verify_report_authenticity_success_with_active_key(tmp_path: Path) -> None:
    report_path, _, authentication = write_report_and_authentication(tmp_path / "report.json")

    result = verify_report_authenticity(
        report_path=report_path,
        trust_store=trust_store(key()),
        verification_time=VERIFICATION_TIME,
    )

    assert isinstance(result, ReportAuthenticityResult)
    assert result.algorithm == HMAC_ALGORITHM
    assert result.key_id == "key-1"
    assert result.authenticated_at == AUTHENTICATED_AT
    assert result.digest == authentication.digest
    assert result.filename == "report.json"


def test_verify_report_authenticity_allows_verify_only_key(tmp_path: Path) -> None:
    verify_key = key(status=AuthenticationKeyStatus.VERIFY_ONLY)
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=verify_key,
    )

    result = verify_report_authenticity(
        report_path=report_path,
        trust_store=trust_store(verify_key),
        verification_time=VERIFICATION_TIME,
    )

    assert result.key_id == verify_key.key_id


def test_verify_report_authenticity_rejects_revoked_key_by_default(tmp_path: Path) -> None:
    revoked_key = key(
        status=AuthenticationKeyStatus.REVOKED,
        revoked_at=REVOKED_AT,
    )
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=revoked_key,
    )

    with pytest.raises(RejectedAuthenticationKeyError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(revoked_key),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_allows_revoked_key_before_revocation_when_policy_allows(
    tmp_path: Path,
) -> None:
    revoked_key = key(
        status=AuthenticationKeyStatus.REVOKED,
        revoked_at=REVOKED_AT,
    )
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=revoked_key,
    )

    result = verify_report_authenticity(
        report_path=report_path,
        trust_store=trust_store(revoked_key),
        verification_time=VERIFICATION_TIME,
        revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
    )

    assert result.key_id == revoked_key.key_id


def test_verify_report_authenticity_rejects_revoked_key_at_revocation_boundary(tmp_path: Path) -> None:
    revoked_key = key(
        status=AuthenticationKeyStatus.REVOKED,
        revoked_at=REVOKED_AT,
    )
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=revoked_key,
        authenticated_at=REVOKED_AT,
    )

    with pytest.raises(RejectedAuthenticationKeyError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(revoked_key),
            verification_time=REVOKED_AT + timedelta(minutes=1),
            revoked_key_policy=RevokedKeyPolicy.ALLOW_PRE_REVOCATION,
        )


def test_verify_report_authenticity_blocks_future_authentication(tmp_path: Path) -> None:
    future_time = VERIFICATION_TIME + MAX_AUTHENTICATION_CLOCK_SKEW + timedelta(seconds=1)
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        authenticated_at=future_time,
    )

    with pytest.raises(AuthenticationFromFutureError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key()),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_rejects_unknown_sidecar_key_id(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=key("old-key"),
    )

    with pytest.raises(UnknownAuthenticationKeyError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key("new-key")),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_does_not_try_other_keys(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=key("actual-key"),
    )
    auth_path.write_text(
        format_report_authentication(
            ReportAuthentication(
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                key_id="missing-key",
                authenticated_at=authentication.authenticated_at,
                digest=authentication.digest,
                filename=authentication.filename,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(UnknownAuthenticationKeyError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key("actual-key")),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_detects_file_tampering(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    report_path.write_text(valid_json_text().replace("gpt-5", "gpt-6"), encoding="utf-8")

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key()),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_detects_timestamp_tampering(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(tmp_path / "report.json")
    auth_path.write_text(
        format_report_authentication(
            ReportAuthentication(
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                key_id=authentication.key_id,
                authenticated_at=AUTHENTICATED_AT + timedelta(seconds=1),
                digest=authentication.digest,
                filename=authentication.filename,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key()),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_rejects_filename_mismatch(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(tmp_path / "report.json")
    auth_path.write_text(
        format_report_authentication(
            ReportAuthentication(
                algorithm=authentication.algorithm,
                protocol_version=authentication.protocol_version,
                key_id=authentication.key_id,
                authenticated_at=authentication.authenticated_at,
                digest=authentication.digest,
                filename="other.json",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(AuthenticationFilenameMismatchError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key()),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_revalidates_json_contract(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    report_path.write_text('{"schema_version":1}\n', encoding="utf-8")
    authentication = build_report_authentication(
        report_path=report_path,
        key=key(),
        authenticated_at=AUTHENTICATED_AT,
    )
    export_authentication_file(
        authentication_path=authentication_path_for(report_path),
        authentication=authentication,
    )

    with pytest.raises(AuditReportValidationError):
        verify_report_authenticity(
            report_path=report_path,
            trust_store=trust_store(key()),
            verification_time=VERIFICATION_TIME,
        )


def test_verify_report_authenticity_uses_compare_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    calls: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def wrapped(left: str, right: str) -> bool:
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(report_authenticity.hmac, "compare_digest", wrapped)

    verify_report_authenticity(
        report_path=report_path,
        trust_store=trust_store(key()),
        verification_time=VERIFICATION_TIME,
    )

    assert len(calls) == 1


def test_secret_is_not_exposed_in_repr_or_sidecar(tmp_path: Path) -> None:
    secret = SECRET_TEXT.encode().ljust(32, b"!")
    signing_key = key(secret=secret)
    report_path, auth_path, _ = write_report_and_authentication(
        tmp_path / "report.json",
        signing_key=signing_key,
    )

    assert SECRET_TEXT not in repr(signing_key)
    assert SECRET_TEXT not in auth_path.read_text(encoding="utf-8")
    assert SECRET_TEXT not in report_path.read_text(encoding="utf-8")
