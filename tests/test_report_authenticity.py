from __future__ import annotations

import base64
import hmac
import os
from pathlib import Path
from typing import Any

import pytest

from app import report_authenticity
from app.authentication_keyring import (
    HMAC_KEY_ENV_NAME,
    HMAC_KEY_ID_ENV_NAME,
    AuthenticationKey,
    AuthenticationKeyring,
)
from app.exceptions import (
    AuditReportValidationError,
    AuthenticationExportError,
    AuthenticationFilenameMismatchError,
    InvalidAuthenticationFormatError,
    InvalidAuthenticationKeyError,
    InvalidAuthenticationKeyIdError,
    MissingAuthenticationKeyringError,
    ReportAuthenticationReadError,
    ReportAuthenticityMismatchError,
    UnknownAuthenticationKeyError,
)
from app.report_authenticity import (
    HMAC_ALGORITHM,
    HMAC_CHUNK_SIZE,
    HMAC_DOMAIN_SEPARATOR,
    HMAC_PROTOCOL_VERSION,
    ReportAuthentication,
    ReportAuthenticityResult,
    authentication_path_for,
    build_report_authentication,
    calculate_report_hmac,
    export_authentication_file,
    format_report_authentication,
    is_valid_hmac_digest,
    is_valid_key_id,
    load_authentication_key,
    parse_report_authentication,
    validate_authentication_keyring,
    verify_report_authenticity,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
SECRET = b"s" * 32
OTHER_SECRET = b"t" * 32
SECRET_TEXT = "SUPER-SECRET-HMAC-KEY"
PRIVATE_EXPORT_ERROR = "PRIVATE-EXPORT-ERROR"


def valid_json_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def key(key_id: str = "key-1", secret: bytes = SECRET) -> AuthenticationKey:
    return AuthenticationKey(key_id=key_id, secret=secret)


def auth_keyring(
    key_id: str = "key-1",
    secret: bytes = SECRET,
    *,
    active_key_id: str | None = None,
    extra_keys: tuple[AuthenticationKey, ...] = (),
) -> AuthenticationKeyring:
    return AuthenticationKeyring(
        active_key_id=active_key_id or key_id,
        keys=(AuthenticationKey(key_id=key_id, secret=secret), *extra_keys),
    )


def write_report(path: Path, text: str | None = None) -> Path:
    path.write_text(text if text is not None else valid_json_text(), encoding="utf-8")
    return path


def write_report_and_authentication(path: Path) -> tuple[Path, Path, ReportAuthentication]:
    write_report(path)
    authentication = build_report_authentication(report_path=path, key=key())
    auth_path = authentication_path_for(path)
    export_authentication_file(authentication_path=auth_path, authentication=authentication)
    return path, auth_path, authentication


def encoded_secret(secret: bytes = SECRET) -> str:
    return base64.b64encode(secret).decode("ascii")


@pytest.mark.parametrize("value", ["key1", "key.1", "key_1", "key-1"])
def test_key_id_accepts_valid_values(value: str) -> None:
    assert is_valid_key_id(value) is True


@pytest.mark.parametrize("value", ["", "key 1", "key/1", "key\\1", "키", "a" * 65, 123])
def test_key_id_rejects_invalid_values(value: object) -> None:
    assert is_valid_key_id(value) is False


def test_hmac_digest_accepts_lowercase_sha256() -> None:
    assert is_valid_hmac_digest("a" * 64) is True


@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "a" * 65, "g" * 64])
def test_hmac_digest_rejects_invalid_values(value: str) -> None:
    assert is_valid_hmac_digest(value) is False


def test_load_authentication_key_accepts_base64_key() -> None:
    loaded = load_authentication_key(
        environ={HMAC_KEY_ENV_NAME: encoded_secret(), HMAC_KEY_ID_ENV_NAME: "key-1"}
    )

    assert loaded.secret == SECRET


def test_load_authentication_key_uses_key_id() -> None:
    loaded = load_authentication_key(
        environ={HMAC_KEY_ENV_NAME: encoded_secret(), HMAC_KEY_ID_ENV_NAME: "key-1"}
    )

    assert loaded.key_id == "key-1"


@pytest.mark.parametrize(
    "environ",
    [
        {HMAC_KEY_ID_ENV_NAME: "key-1"},
        {HMAC_KEY_ENV_NAME: encoded_secret()},
        {HMAC_KEY_ENV_NAME: "", HMAC_KEY_ID_ENV_NAME: "key-1"},
    ],
)
def test_load_authentication_key_rejects_missing_or_empty_values(
    environ: dict[str, str],
) -> None:
    with pytest.raises(MissingAuthenticationKeyringError):
        load_authentication_key(environ=environ)


def test_load_authentication_key_rejects_invalid_base64() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_key(
            environ={HMAC_KEY_ENV_NAME: "not-base64!", HMAC_KEY_ID_ENV_NAME: "key-1"}
        )


def test_load_authentication_key_rejects_non_ascii_base64() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_key(
            environ={HMAC_KEY_ENV_NAME: "한글", HMAC_KEY_ID_ENV_NAME: "key-1"}
        )


def test_load_authentication_key_rejects_short_secret() -> None:
    with pytest.raises(InvalidAuthenticationKeyError):
        load_authentication_key(
            environ={HMAC_KEY_ENV_NAME: encoded_secret(b"s" * 31), HMAC_KEY_ID_ENV_NAME: "key-1"}
        )


def test_load_authentication_key_accepts_32_byte_secret() -> None:
    loaded = load_authentication_key(
        environ={HMAC_KEY_ENV_NAME: encoded_secret(b"s" * 32), HMAC_KEY_ID_ENV_NAME: "key-1"}
    )

    assert len(loaded.secret) == 32


def test_load_authentication_key_rejects_invalid_key_id() -> None:
    with pytest.raises(InvalidAuthenticationKeyIdError):
        load_authentication_key(
            environ={HMAC_KEY_ENV_NAME: encoded_secret(), HMAC_KEY_ID_ENV_NAME: "bad key"}
        )


def test_authentication_key_repr_hides_secret() -> None:
    assert SECRET_TEXT not in repr(AuthenticationKey("key-1", (SECRET_TEXT + "x" * 32).encode()))


def test_load_authentication_key_does_not_mutate_environ() -> None:
    environ = {HMAC_KEY_ENV_NAME: encoded_secret(), HMAC_KEY_ID_ENV_NAME: "key-1"}
    before = dict(environ)

    load_authentication_key(environ=environ)

    assert environ == before


def test_load_authentication_key_error_omits_secret_value() -> None:
    with pytest.raises(InvalidAuthenticationKeyError) as exc_info:
        load_authentication_key(
            environ={HMAC_KEY_ENV_NAME: SECRET_TEXT, HMAC_KEY_ID_ENV_NAME: "key-1"}
        )

    assert SECRET_TEXT not in str(exc_info.value)


def test_authentication_path_for_appends_hmac(tmp_path: Path) -> None:
    assert authentication_path_for(tmp_path / "report.json").name == "report.json.hmac"


def test_authentication_path_for_uses_same_parent(tmp_path: Path) -> None:
    assert authentication_path_for(tmp_path / "report.json").parent == tmp_path


def test_authentication_path_for_rejects_non_path() -> None:
    with pytest.raises(TypeError):
        authentication_path_for("report.json")  # type: ignore[arg-type]


def test_hmac_same_key_file_and_name_is_stable(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    assert calculate_report_hmac(report_path=report_path, key=key()) == calculate_report_hmac(
        report_path=report_path,
        key=key(),
    )


def test_hmac_changes_when_file_bytes_change(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    before = calculate_report_hmac(report_path=report_path, key=key())
    report_path.write_text(valid_json_text().replace("gpt-5", "gpt-6"), encoding="utf-8")

    assert calculate_report_hmac(report_path=report_path, key=key()) != before


def test_hmac_changes_when_filename_changes(tmp_path: Path) -> None:
    first = write_report(tmp_path / "first.json")
    second = write_report(tmp_path / "second.json")

    assert calculate_report_hmac(report_path=first, key=key()) != calculate_report_hmac(
        report_path=second,
        key=key(),
    )


def test_hmac_changes_when_key_changes(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    assert calculate_report_hmac(report_path=report_path, key=key()) != calculate_report_hmac(
        report_path=report_path,
        key=key(secret=OTHER_SECRET),
    )


def test_hmac_uses_domain_separator(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    expected = hmac.new(SECRET, digestmod="sha256")
    expected.update(HMAC_DOMAIN_SEPARATOR)
    expected.update(b"\0")
    expected.update(report_path.name.encode("utf-8"))
    expected.update(b"\0")
    expected.update(report_path.read_bytes())

    assert calculate_report_hmac(report_path=report_path, key=key()) == expected.hexdigest()


def test_hmac_handles_multiple_chunks(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_bytes(b"a" * (HMAC_CHUNK_SIZE + 17))

    assert is_valid_hmac_digest(calculate_report_hmac(report_path=report_path, key=key()))


def test_hmac_digest_is_lowercase_64_hex(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    digest = calculate_report_hmac(report_path=report_path, key=key())

    assert is_valid_hmac_digest(digest)
    assert digest == digest.lower()


def test_hmac_rejects_symlink(tmp_path: Path) -> None:
    target = write_report(tmp_path / "target.json")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink is unavailable: {error}")

    with pytest.raises(ReportAuthenticationReadError):
        calculate_report_hmac(report_path=link, key=key())


def test_hmac_converts_read_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path = write_report(tmp_path / "report.json")

    def broken_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise OSError(SECRET_TEXT)

    monkeypatch.setattr(Path, "open", broken_open)

    with pytest.raises(ReportAuthenticationReadError):
        calculate_report_hmac(report_path=report_path, key=key())


def test_format_report_authentication_outputs_expected_fields() -> None:
    authentication = ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json")

    assert format_report_authentication(authentication) == f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json\n"


def test_format_report_authentication_field_order() -> None:
    fields = format_report_authentication(
        ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json")
    ).strip().split("  ")

    assert fields == [HMAC_ALGORITHM, "key-1", "a" * 64, "report.json"]


def test_format_report_authentication_has_newline() -> None:
    authentication = ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json")

    assert format_report_authentication(authentication).endswith("\n")


def test_parse_report_authentication_accepts_normal_text() -> None:
    parsed = parse_report_authentication(f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json\n")

    assert parsed.key_id == "key-1"


def test_parse_report_authentication_accepts_without_newline() -> None:
    parsed = parse_report_authentication(f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json")

    assert parsed.filename == "report.json"


@pytest.mark.parametrize(
    "text",
    [
        f"sha256  key-1  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  bad key  {'a' * 64}  report.json\n",
        f"{HMAC_ALGORITHM}  key-1  {'A' * 64}  report.json\n",
        f"{HMAC_ALGORITHM} key-1 {'a' * 64} report.json\n",
        f"{HMAC_ALGORITHM}   key-1   {'a' * 64}   report.json\n",
        f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json\nextra\n",
        f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  nested/report.json\n",
    ],
)
def test_parse_report_authentication_rejects_invalid_text(text: str) -> None:
    with pytest.raises(InvalidAuthenticationFormatError):
        parse_report_authentication(text)


def test_format_parse_round_trip() -> None:
    authentication = ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "b" * 64, "report.json")

    assert parse_report_authentication(format_report_authentication(authentication)) == authentication


def test_secret_is_not_in_authentication_sidecar(tmp_path: Path) -> None:
    report_path, auth_path, _ = write_report_and_authentication(tmp_path / "report.json")

    assert SECRET.decode() not in auth_path.read_text(encoding="utf-8")
    assert report_path.exists()


def test_export_authentication_file_creates_parent(tmp_path: Path) -> None:
    auth_path = tmp_path / "nested" / "report.json.hmac"

    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert auth_path.parent.is_dir()


def test_export_authentication_file_creates_hmac(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"

    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert auth_path.is_file()


def test_export_authentication_file_calls_fsync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[int] = []
    original_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(report_authenticity.os, "fsync", recording_fsync)

    export_authentication_file(
        authentication_path=tmp_path / "report.json.hmac",
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert len(calls) == 1


def test_export_authentication_file_calls_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        calls.append((source, destination))
        original_replace(source, destination)

    monkeypatch.setattr(report_authenticity.os, "replace", recording_replace)
    auth_path = tmp_path / "report.json.hmac"

    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert len(calls) == 1
    assert calls[0][1] == auth_path


def test_export_authentication_file_replaces_existing(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"
    auth_path.write_text("existing", encoding="utf-8")

    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert auth_path.read_text(encoding="utf-8") != "existing"


def test_export_authentication_file_leaves_no_temp(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"

    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
    )

    assert list(tmp_path.glob(f".{auth_path.name}.*.tmp")) == []


def test_authentication_replace_failure_preserves_existing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "report.json.hmac"
    auth_path.write_text("existing", encoding="utf-8")

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_authenticity.os, "replace", broken_replace)

    with pytest.raises(AuthenticationExportError):
        export_authentication_file(
            authentication_path=auth_path,
            authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
        )

    assert auth_path.read_text(encoding="utf-8") == "existing"


def test_authentication_replace_failure_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_authenticity.os, "replace", broken_replace)
    auth_path = tmp_path / "report.json.hmac"

    with pytest.raises(AuthenticationExportError):
        export_authentication_file(
            authentication_path=auth_path,
            authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
        )

    assert list(tmp_path.glob(f".{auth_path.name}.*.tmp")) == []


def test_authentication_export_converts_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_fsync(fd: int) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_authenticity.os, "fsync", broken_fsync)

    with pytest.raises(AuthenticationExportError):
        export_authentication_file(
            authentication_path=tmp_path / "report.json.hmac",
            authentication=ReportAuthentication(HMAC_ALGORITHM, HMAC_PROTOCOL_VERSION, "key-1", "a" * 64, "report.json"),
        )


def test_validate_keyring_accepts_authentication_keyring() -> None:
    validate_authentication_keyring(auth_keyring())


def test_validate_keyring_rejects_mapping() -> None:
    with pytest.raises(TypeError):
        validate_authentication_keyring({"key-1": SECRET})  # type: ignore[arg-type]


def test_validate_keyring_does_not_mutate_keyring() -> None:
    ring = auth_keyring()
    before = ring.keys

    validate_authentication_keyring(ring)

    assert ring.keys == before


def test_verify_report_authenticity_succeeds(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")

    result = verify_report_authenticity(report_path=report_path, keyring=auth_keyring())

    assert result.filename == "report.json"


def test_verify_report_authenticity_returns_result(tmp_path: Path) -> None:
    report_path, _, authentication = write_report_and_authentication(tmp_path / "report.json")

    result = verify_report_authenticity(report_path=report_path, keyring=auth_keyring())

    assert result == ReportAuthenticityResult(HMAC_ALGORITHM, "key-1", authentication.digest, "report.json")


def test_verify_detects_changed_file_byte(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    report_path.write_text(valid_json_text().replace("gpt-5", "gpt-6"), encoding="utf-8")

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_removed_newline(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    report_path.write_text(report_path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_different_secret(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring(secret=OTHER_SECRET))


def test_verify_detects_unknown_key_id(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")

    with pytest.raises(UnknownAuthenticationKeyError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring("other", SECRET))


def test_verify_detects_filename_mismatch(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(tmp_path / "report.json")
    auth_path.write_text(
        format_report_authentication(
            ReportAuthentication(authentication.algorithm, authentication.protocol_version, authentication.key_id, authentication.digest, "other.json")
        ),
        encoding="utf-8",
    )

    with pytest.raises(AuthenticationFilenameMismatchError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_sidecar_digest_change(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(tmp_path / "report.json")
    auth_path.write_text(
        format_report_authentication(
            ReportAuthentication(authentication.algorithm, authentication.protocol_version, authentication.key_id, "0" * 64, authentication.filename)
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReportAuthenticityMismatchError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_malformed_sidecar(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    authentication_path_for(report_path).write_text(SECRET_TEXT, encoding="utf-8")

    with pytest.raises(InvalidAuthenticationFormatError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_missing_sidecar(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    with pytest.raises(ReportAuthenticationReadError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_verify_detects_missing_report(tmp_path: Path) -> None:
    auth_path = tmp_path / "report.json.hmac"
    auth_path.write_text(f"{HMAC_ALGORITHM}  key-1  {'a' * 64}  report.json\n", encoding="utf-8")

    with pytest.raises(ReportAuthenticationReadError):
        verify_report_authenticity(report_path=tmp_path / "report.json", keyring=auth_keyring())


def test_verify_uses_compare_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    calls: list[tuple[str, str]] = []
    original_compare = report_authenticity.hmac.compare_digest

    def recording_compare(expected: str, actual: str) -> bool:
        calls.append((expected, actual))
        return original_compare(expected, actual)

    monkeypatch.setattr(report_authenticity.hmac, "compare_digest", recording_compare)

    verify_report_authenticity(report_path=report_path, keyring=auth_keyring())

    assert len(calls) == 1


def test_verify_valid_hmac_then_invalid_json_contract(tmp_path: Path) -> None:
    bad_json = valid_json_text().replace('"schema_version": 1', '"schema_version": 999')
    report_path = write_report(tmp_path / "report.json", text=bad_json)
    authentication = build_report_authentication(report_path=report_path, key=key())
    export_authentication_file(authentication_path=authentication_path_for(report_path), authentication=authentication)

    with pytest.raises(AuditReportValidationError):
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())


def test_authentication_errors_omit_secret_json_and_sidecar(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    authentication_path_for(report_path).write_text(SECRET_TEXT, encoding="utf-8")

    with pytest.raises(InvalidAuthenticationFormatError) as exc_info:
        verify_report_authenticity(report_path=report_path, keyring=auth_keyring())

    assert SECRET_TEXT not in str(exc_info.value)
    assert "schema_version" not in str(exc_info.value)


def test_verify_with_multi_keyring_uses_sidecar_key_id(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    ring = auth_keyring(
        "other",
        OTHER_SECRET,
        active_key_id="other",
        extra_keys=(AuthenticationKey("key-1", SECRET),),
    )

    result = verify_report_authenticity(report_path=report_path, keyring=ring)

    assert result.key_id == "key-1"


def test_verify_old_key_succeeds_when_active_key_is_new(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_authentication(tmp_path / "report.json")
    ring = AuthenticationKeyring(
        active_key_id="new-key",
        keys=(AuthenticationKey("old-key", OTHER_SECRET), AuthenticationKey("key-1", SECRET), AuthenticationKey("new-key", b"n" * 32)),
    )

    assert verify_report_authenticity(report_path=report_path, keyring=ring).key_id == "key-1"


def test_verify_does_not_try_other_registered_keys(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    matching_auth = build_report_authentication(
        report_path=report_path,
        key=AuthenticationKey("other-key", SECRET),
    )
    auth_path = authentication_path_for(report_path)
    export_authentication_file(
        authentication_path=auth_path,
        authentication=ReportAuthentication(
            matching_auth.algorithm,
            matching_auth.protocol_version,
            "missing-key",
            matching_auth.digest,
            matching_auth.filename,
        ),
    )
    ring = auth_keyring("other-key", SECRET)

    with pytest.raises(UnknownAuthenticationKeyError):
        verify_report_authenticity(report_path=report_path, keyring=ring)


def test_verify_protocol_version_one_and_sidecar_four_fields(tmp_path: Path) -> None:
    report_path, auth_path, authentication = write_report_and_authentication(tmp_path / "report.json")

    fields = auth_path.read_text(encoding="utf-8").strip().split("  ")

    assert authentication.protocol_version == HMAC_PROTOCOL_VERSION
    assert len(fields) == 4
    assert verify_report_authenticity(report_path=report_path, keyring=auth_keyring()).key_id == "key-1"
