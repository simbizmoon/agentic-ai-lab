from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from app import report_integrity
from app.exceptions import (
    AuditReportValidationError,
    ChecksumExportError,
    ChecksumFilenameMismatchError,
    InvalidChecksumFormatError,
    ReportIntegrityMismatchError,
    ReportIntegrityReadError,
)
from app.report_integrity import (
    CHECKSUM_ALGORITHM,
    SHA256_CHUNK_SIZE,
    ReportChecksum,
    ReportIntegrityResult,
    build_report_checksum,
    calculate_sha256,
    calculate_sha256_bytes,
    checksum_path_for,
    export_checksum_file,
    format_report_checksum,
    is_valid_sha256_digest,
    parse_report_checksum,
    verify_report_integrity,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit_report_v1.json"
PRIVATE_PATH = "PRIVATE-PATH"
PRIVATE_TEXT = "PRIVATE-CHECKSUM-TEXT"
PRIVATE_EXPORT_ERROR = "PRIVATE-EXPORT-ERROR"


def valid_json_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def write_report(path: Path, text: str | None = None) -> Path:
    path.write_text(text if text is not None else valid_json_text(), encoding="utf-8")
    return path


def write_report_and_checksum(path: Path) -> tuple[Path, Path, ReportChecksum]:
    write_report(path)
    checksum = build_report_checksum(path)
    checksum_path = checksum_path_for(path)
    export_checksum_file(checksum_path=checksum_path, checksum=checksum)
    return path, checksum_path, checksum



def test_calculate_sha256_bytes_known_bytes() -> None:
    assert calculate_sha256_bytes(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_calculate_sha256_bytes_empty_bytes() -> None:
    assert calculate_sha256_bytes(b"") == hashlib.sha256(b"").hexdigest()


def test_calculate_sha256_bytes_returns_lowercase_64_hex() -> None:
    digest = calculate_sha256_bytes(b"abc")

    assert is_valid_sha256_digest(digest)
    assert digest == digest.lower()


@pytest.mark.parametrize("value", ["abc", bytearray(b"abc")])
def test_calculate_sha256_bytes_rejects_non_bytes(value: object) -> None:
    with pytest.raises(TypeError):
        calculate_sha256_bytes(value)  # type: ignore[arg-type]


def test_calculate_sha256_known_bytes(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")

    assert calculate_sha256(path) == hashlib.sha256(b"abc").hexdigest()


def test_calculate_sha256_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")

    assert calculate_sha256(path) == hashlib.sha256(b"").hexdigest()


def test_calculate_sha256_multiple_chunks(tmp_path: Path) -> None:
    data = b"a" * (SHA256_CHUNK_SIZE + 17)
    path = tmp_path / "large.bin"
    path.write_bytes(data)

    assert calculate_sha256(path) == hashlib.sha256(data).hexdigest()


def test_calculate_sha256_returns_lowercase_64_hex(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")

    digest = calculate_sha256(path)

    assert is_valid_sha256_digest(digest)
    assert digest == digest.lower()


def test_calculate_sha256_rejects_non_file(tmp_path: Path) -> None:
    with pytest.raises(ReportIntegrityReadError):
        calculate_sha256(tmp_path / "missing.bin")


def test_calculate_sha256_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"abc")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink is unavailable: {error}")

    with pytest.raises(ReportIntegrityReadError):
        calculate_sha256(link)


def test_calculate_sha256_converts_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")

    def broken_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise OSError(PRIVATE_PATH)

    monkeypatch.setattr(Path, "open", broken_open)

    with pytest.raises(ReportIntegrityReadError):
        calculate_sha256(path)


def test_calculate_sha256_error_omits_private_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")

    def broken_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise OSError(PRIVATE_PATH)

    monkeypatch.setattr(Path, "open", broken_open)

    with pytest.raises(ReportIntegrityReadError) as exc_info:
        calculate_sha256(path)

    assert PRIVATE_PATH not in str(exc_info.value)


def test_digest_validator_accepts_lowercase_sha256() -> None:
    assert is_valid_sha256_digest("a" * 64) is True


@pytest.mark.parametrize("value", ["A" * 64, "a" * 63, "a" * 65, "g" * 64, 123])
def test_digest_validator_rejects_invalid_values(value: object) -> None:
    assert is_valid_sha256_digest(value) is False


def test_checksum_path_for_uses_same_parent(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"

    assert checksum_path_for(report_path).parent == tmp_path


def test_checksum_path_for_appends_sha256_name(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"

    assert checksum_path_for(report_path).name == "report.json.sha256"


def test_checksum_path_for_rejects_non_path() -> None:
    with pytest.raises(TypeError):
        checksum_path_for("report.json")  # type: ignore[arg-type]


def test_format_report_checksum_outputs_expected_format() -> None:
    checksum = ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json")

    assert format_report_checksum(checksum) == f"{'a' * 64}  report.json\n"


def test_format_report_checksum_ends_with_newline() -> None:
    checksum = ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json")

    assert format_report_checksum(checksum).endswith("\n")


def test_parse_report_checksum_accepts_normal_format() -> None:
    checksum = parse_report_checksum(f"{'a' * 64}  report.json\n")

    assert checksum == ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json")


def test_parse_report_checksum_accepts_without_newline() -> None:
    checksum = parse_report_checksum(f"{'a' * 64}  report.json")

    assert checksum.filename == "report.json"


@pytest.mark.parametrize(
    "text",
    [
        f"{'a' * 64} report.json\n",
        f"{'a' * 64}   report.json\n",
        f"{'a' * 64}  report.json\nextra\n",
        f"{'a' * 64}  \n",
        f"{'a' * 64}  nested/report.json\n",
        f"{'a' * 64}  nested\\report.json\n",
        f"{'a' * 64}  ..\n",
        f"{'A' * 64}  report.json\n",
    ],
)
def test_parse_report_checksum_rejects_invalid_text(text: str) -> None:
    with pytest.raises(InvalidChecksumFormatError):
        parse_report_checksum(text)


def test_parse_report_checksum_error_omits_original_text() -> None:
    with pytest.raises(InvalidChecksumFormatError) as exc_info:
        parse_report_checksum(PRIVATE_TEXT)

    assert PRIVATE_TEXT not in str(exc_info.value)


def test_checksum_format_parse_round_trip() -> None:
    checksum = ReportChecksum(CHECKSUM_ALGORITHM, "b" * 64, "audit-report.json")

    assert parse_report_checksum(format_report_checksum(checksum)) == checksum


def test_export_checksum_file_creates_parent_directory(tmp_path: Path) -> None:
    checksum_path = tmp_path / "nested" / "report.json.sha256"

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert checksum_path.parent.is_dir()


def test_export_checksum_file_writes_utf8_text(tmp_path: Path) -> None:
    checksum_path = tmp_path / "report.json.sha256"

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert checksum_path.read_text(encoding="utf-8") == f"{'a' * 64}  report.json\n"


def test_export_checksum_file_writes_single_newline(tmp_path: Path) -> None:
    checksum_path = tmp_path / "report.json.sha256"

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert checksum_path.read_text(encoding="utf-8").endswith("\n")
    assert not checksum_path.read_text(encoding="utf-8").endswith("\n\n")


def test_export_checksum_file_calls_fsync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[int] = []
    original_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(report_integrity.os, "fsync", recording_fsync)

    export_checksum_file(
        checksum_path=tmp_path / "report.json.sha256",
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert len(calls) == 1


def test_export_checksum_file_calls_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        calls.append((source, destination))
        original_replace(source, destination)

    monkeypatch.setattr(report_integrity.os, "replace", recording_replace)
    checksum_path = tmp_path / "report.json.sha256"

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert len(calls) == 1
    assert calls[0][1] == checksum_path


def test_export_checksum_file_replaces_existing_checksum(tmp_path: Path) -> None:
    checksum_path = tmp_path / "report.json.sha256"
    checksum_path.write_text("existing", encoding="utf-8")

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert checksum_path.read_text(encoding="utf-8") != "existing"


def test_export_checksum_file_leaves_no_temp_file(tmp_path: Path) -> None:
    checksum_path = tmp_path / "report.json.sha256"

    export_checksum_file(
        checksum_path=checksum_path,
        checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
    )

    assert list(tmp_path.glob(f".{checksum_path.name}.*.tmp")) == []


def test_replace_failure_preserves_existing_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checksum_path = tmp_path / "report.json.sha256"
    checksum_path.write_text("existing", encoding="utf-8")

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_integrity.os, "replace", broken_replace)

    with pytest.raises(ChecksumExportError):
        export_checksum_file(
            checksum_path=checksum_path,
            checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
        )

    assert checksum_path.read_text(encoding="utf-8") == "existing"


def test_replace_failure_cleans_temp_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checksum_path = tmp_path / "report.json.sha256"

    def broken_replace(source: Path, destination: Path) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_integrity.os, "replace", broken_replace)

    with pytest.raises(ChecksumExportError):
        export_checksum_file(
            checksum_path=checksum_path,
            checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
        )

    assert list(tmp_path.glob(f".{checksum_path.name}.*.tmp")) == []


def test_export_checksum_file_converts_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_fsync(fd: int) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_integrity.os, "fsync", broken_fsync)

    with pytest.raises(ChecksumExportError):
        export_checksum_file(
            checksum_path=tmp_path / "report.json.sha256",
            checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
        )


def test_checksum_export_error_omits_private_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_fsync(fd: int) -> None:
        raise OSError(PRIVATE_EXPORT_ERROR)

    monkeypatch.setattr(report_integrity.os, "fsync", broken_fsync)

    with pytest.raises(ChecksumExportError) as exc_info:
        export_checksum_file(
            checksum_path=tmp_path / "report.json.sha256",
            checksum=ReportChecksum(CHECKSUM_ALGORITHM, "a" * 64, "report.json"),
        )

    assert PRIVATE_EXPORT_ERROR not in str(exc_info.value)


def test_verify_report_integrity_succeeds(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_checksum(tmp_path / "report.json")

    result = verify_report_integrity(report_path=report_path)

    assert result.filename == "report.json"


def test_verify_report_integrity_returns_result(tmp_path: Path) -> None:
    report_path, _, checksum = write_report_and_checksum(tmp_path / "report.json")

    result = verify_report_integrity(report_path=report_path)

    assert result == ReportIntegrityResult(CHECKSUM_ALGORITHM, checksum.digest, "report.json")


def test_verify_detects_changed_json_byte(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_checksum(tmp_path / "report.json")
    report_path.write_text(valid_json_text().replace("gpt-5", "gpt-6"), encoding="utf-8")

    with pytest.raises(ReportIntegrityMismatchError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_removed_final_newline(tmp_path: Path) -> None:
    report_path, _, _ = write_report_and_checksum(tmp_path / "report.json")
    report_path.write_text(report_path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    with pytest.raises(ReportIntegrityMismatchError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_changed_checksum_digest(tmp_path: Path) -> None:
    report_path, checksum_path, _ = write_report_and_checksum(tmp_path / "report.json")
    checksum_path.write_text(f"{'0' * 64}  report.json\n", encoding="utf-8")

    with pytest.raises(ReportIntegrityMismatchError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_changed_checksum_filename(tmp_path: Path) -> None:
    report_path, checksum_path, checksum = write_report_and_checksum(tmp_path / "report.json")
    checksum_path.write_text(f"{checksum.digest}  other.json\n", encoding="utf-8")

    with pytest.raises(ChecksumFilenameMismatchError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_malformed_checksum(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    checksum_path_for(report_path).write_text(PRIVATE_TEXT, encoding="utf-8")

    with pytest.raises(InvalidChecksumFormatError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_missing_checksum(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")

    with pytest.raises(ReportIntegrityReadError):
        verify_report_integrity(report_path=report_path)


def test_verify_detects_missing_report(tmp_path: Path) -> None:
    checksum_path = tmp_path / "report.json.sha256"
    checksum_path.write_text(f"{'a' * 64}  report.json\n", encoding="utf-8")

    with pytest.raises(ReportIntegrityReadError):
        verify_report_integrity(report_path=tmp_path / "report.json")


def test_verify_valid_digest_then_invalid_json_contract(tmp_path: Path) -> None:
    bad_json = valid_json_text().replace('"schema_version": 1', '"schema_version": 999')
    report_path = write_report(tmp_path / "report.json", text=bad_json)
    checksum = build_report_checksum(report_path)
    export_checksum_file(checksum_path=checksum_path_for(report_path), checksum=checksum)

    with pytest.raises(AuditReportValidationError):
        verify_report_integrity(report_path=report_path)


def test_verify_uses_hmac_compare_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report_path, _, _ = write_report_and_checksum(tmp_path / "report.json")
    calls: list[tuple[str, str]] = []
    original_compare = hmac_compare = report_integrity.hmac.compare_digest

    def recording_compare(expected: str, actual: str) -> bool:
        calls.append((expected, actual))
        return original_compare(expected, actual)

    monkeypatch.setattr(report_integrity.hmac, "compare_digest", recording_compare)

    verify_report_integrity(report_path=report_path)

    assert len(calls) == 1
    assert calls[0][0] == calls[0][1]
    assert hmac_compare is original_compare


def test_verify_error_omits_sensitive_content(tmp_path: Path) -> None:
    report_path = write_report(tmp_path / "report.json")
    checksum_path_for(report_path).write_text(PRIVATE_TEXT, encoding="utf-8")

    with pytest.raises(InvalidChecksumFormatError) as exc_info:
        verify_report_integrity(report_path=report_path)

    assert PRIVATE_TEXT not in str(exc_info.value)
