from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.research.local_document_access_policy as access_policy_module
from app.exceptions import ReportIntegrityReadError
from app.research.local_document_access_policy import (
    LocalDocumentAccessError,
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)


def _policy(root: Path, *, maximum_file_bytes: int = 1024) -> LocalDocumentAccessPolicy:
    return LocalDocumentAccessPolicy(
        allowed_roots=(root,),
        maximum_file_bytes=maximum_file_bytes,
    )


def test_gate_accepts_file_inside_allowed_root(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"research")

    result = LocalDocumentAccessGate(_policy(tmp_path)).validate(source)

    assert result.resolved_path == source.resolve()
    assert result.file_size_bytes == 8


def test_gate_accepts_nested_file(tmp_path: Path) -> None:
    nested = tmp_path / "documents" / "nested"
    nested.mkdir(parents=True)
    source = nested / "source.md"
    source.write_text("nested", encoding="utf-8")

    result = LocalDocumentAccessGate(_policy(tmp_path)).validate(source)

    assert result.resolved_path == source.resolve()


def test_gate_rejects_file_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    source = tmp_path / "outside.txt"
    source.write_text("outside", encoding="utf-8")

    with pytest.raises(LocalDocumentAccessError, match="outside the allowed roots"):
        LocalDocumentAccessGate(_policy(allowed)).validate(source)


def test_gate_rejects_prefix_lookalike_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "data"
    lookalike = tmp_path / "database"
    allowed.mkdir()
    lookalike.mkdir()
    source = lookalike / "source.txt"
    source.write_text("outside", encoding="utf-8")

    with pytest.raises(LocalDocumentAccessError, match="outside the allowed roots"):
        LocalDocumentAccessGate(_policy(allowed)).validate(source)


def test_gate_accepts_file_in_any_of_multiple_allowed_roots(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    source = second / "source.txt"
    source.write_text("second", encoding="utf-8")
    policy = LocalDocumentAccessPolicy(
        allowed_roots=(first, second),
        maximum_file_bytes=1024,
    )

    result = LocalDocumentAccessGate(policy).validate(source)

    assert result.resolved_path == source.resolve()


def test_policy_rejects_duplicate_resolved_roots(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="allowed roots must be unique"):
        LocalDocumentAccessPolicy(
            allowed_roots=(tmp_path, tmp_path / "."),
            maximum_file_bytes=1,
        )


def test_policy_rejects_empty_allowed_roots() -> None:
    with pytest.raises(ValidationError, match="nonempty tuple"):
        LocalDocumentAccessPolicy(allowed_roots=(), maximum_file_bytes=1)


@pytest.mark.parametrize("maximum_file_bytes", [0, -1, True])
def test_policy_rejects_invalid_maximum_file_size(
    tmp_path: Path,
    maximum_file_bytes: object,
) -> None:
    with pytest.raises(ValidationError):
        LocalDocumentAccessPolicy(
            allowed_roots=(tmp_path,),
            maximum_file_bytes=maximum_file_bytes,
        )


def test_policy_rejects_relative_or_nonexistent_or_file_root(tmp_path: Path) -> None:
    root_file = tmp_path / "root.txt"
    root_file.write_text("not a directory", encoding="utf-8")

    for root in (Path("relative"), tmp_path / "missing", root_file):
        with pytest.raises(ValidationError):
            LocalDocumentAccessPolicy(allowed_roots=(root,), maximum_file_bytes=1)


def test_gate_rejects_invalid_path_type(tmp_path: Path) -> None:
    with pytest.raises(LocalDocumentAccessError, match="must be a Path"):
        LocalDocumentAccessGate(_policy(tmp_path)).validate("source.txt")  # type: ignore[arg-type]


def test_gate_rejects_missing_source(tmp_path: Path) -> None:
    with pytest.raises(LocalDocumentAccessError, match="does not exist"):
        LocalDocumentAccessGate(_policy(tmp_path)).validate(tmp_path / "missing.txt")


def test_gate_rejects_directory_source(tmp_path: Path) -> None:
    with pytest.raises(LocalDocumentAccessError, match="regular file"):
        LocalDocumentAccessGate(_policy(tmp_path)).validate(tmp_path)


def test_gate_translates_source_resolution_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    policy = _policy(tmp_path)
    resolution_error = RuntimeError("symlink loop")

    def fail_resolution(_: Path, *, strict: bool = False) -> Path:
        raise resolution_error

    monkeypatch.setattr(Path, "resolve", fail_resolution)

    with pytest.raises(LocalDocumentAccessError, match="could not be resolved") as exc_info:
        LocalDocumentAccessGate(policy).validate(source)

    assert exc_info.value.__cause__ is resolution_error


def test_gate_rejects_leaf_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    link = tmp_path / "source-link.txt"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("platform cannot create symlinks")

    with pytest.raises(LocalDocumentAccessError, match="must not be a symlink"):
        LocalDocumentAccessGate(_policy(tmp_path)).validate(link)


def test_gate_rejects_ancestor_symlink_resolving_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("outside", encoding="utf-8")
    linked_directory = allowed / "linked-directory"
    try:
        linked_directory.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("platform cannot create symlinks")

    with pytest.raises(LocalDocumentAccessError, match="outside the allowed roots"):
        LocalDocumentAccessGate(_policy(allowed)).validate(linked_directory / source.name)


def test_gate_accepts_file_exactly_at_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"1234")

    result = LocalDocumentAccessGate(_policy(tmp_path, maximum_file_bytes=4)).validate(source)

    assert result.file_size_bytes == 4


def test_gate_rejects_file_over_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"12345")

    with pytest.raises(LocalDocumentAccessError, match="exceeds the maximum"):
        LocalDocumentAccessGate(_policy(tmp_path, maximum_file_bytes=4)).validate(source)


def test_gate_returns_exact_known_sha256(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"abc")

    result = LocalDocumentAccessGate(_policy(tmp_path)).validate(source)

    assert result.content_sha256 == hashlib.sha256(b"abc").hexdigest()


def test_same_bytes_have_same_digest_and_changed_bytes_do_not(tmp_path: Path) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    changed = tmp_path / "changed.bin"
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    changed.write_bytes(b"different")
    gate = LocalDocumentAccessGate(_policy(tmp_path))

    first_digest = gate.validate(first).content_sha256
    second_digest = gate.validate(second).content_sha256
    changed_digest = gate.validate(changed).content_sha256

    assert first_digest == second_digest
    assert first_digest != changed_digest


def test_gate_translates_hash_read_failure_without_disclosing_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("private document content", encoding="utf-8")
    read_error = ReportIntegrityReadError("private document content")
    read_error.__cause__ = OSError("read failed")

    def fail_hash(_: Path) -> str:
        raise read_error

    monkeypatch.setattr(access_policy_module, "calculate_sha256", fail_hash)

    with pytest.raises(LocalDocumentAccessError, match="could not be hashed") as exc_info:
        LocalDocumentAccessGate(_policy(tmp_path)).validate(source)

    assert "private document content" not in str(exc_info.value)
    assert exc_info.value.__cause__ is read_error


def test_policy_and_result_are_strict_immutable_models(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    result = LocalDocumentAccessResult(
        resolved_path=tmp_path.resolve(),
        file_size_bytes=3,
        content_sha256=hashlib.sha256(b"abc").hexdigest(),
    )

    with pytest.raises(ValidationError):
        policy.maximum_file_bytes = 2
    with pytest.raises(ValidationError):
        result.file_size_bytes = 4
    with pytest.raises(ValidationError):
        LocalDocumentAccessResult(
            resolved_path=tmp_path.resolve(),
            file_size_bytes=3,
            content_sha256="ABC",
        )
    with pytest.raises(ValidationError):
        LocalDocumentAccessPolicy(
            allowed_roots=[tmp_path],  # type: ignore[arg-type]
            maximum_file_bytes=1,
        )
