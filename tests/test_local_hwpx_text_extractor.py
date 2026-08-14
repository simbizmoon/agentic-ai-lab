"""Tests for safe local HWPX text extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from app.research.local_hwpx_text_extractor import (
    CONTENT_HPF_PATH,
    MAXIMUM_ARCHIVE_MEMBER_COUNT,
    MAXIMUM_MEMBER_UNCOMPRESSED_BYTES,
    MAXIMUM_TOTAL_UNCOMPRESSED_BYTES,
    SECTION_SEPARATOR,
    LocalHwpxTextExtractionError,
    LocalHwpxTextExtractor,
)


def test_archive_safety_limit_contract() -> None:
    assert MAXIMUM_ARCHIVE_MEMBER_COUNT == 2_048
    assert MAXIMUM_MEMBER_UNCOMPRESSED_BYTES == 16 * 1024 * 1024
    assert MAXIMUM_TOTAL_UNCOMPRESSED_BYTES == 128 * 1024 * 1024


def content_hpf(
    manifest: list[tuple[str, str]],
    spine: list[str],
) -> str:
    """Return minimal namespace-qualified package metadata."""

    items = "".join(
        f'<opf:item id="{item_id}" href="{href}"/>'
        for item_id, href in manifest
    )
    references = "".join(
        f'<opf:itemref idref="{item_id}"/>'
        for item_id in spine
    )
    return (
        '<opf:package xmlns:opf="urn:oasis:names:tc:opendocument:'
        'xmlns:container">'
        f"<opf:manifest>{items}</opf:manifest>"
        f"<opf:spine>{references}</opf:spine>"
        "</opf:package>"
    )


def section_xml(*paragraphs: str) -> str:
    """Return minimal HWPX-like section XML."""

    body = "".join(
        f"<hp:p><hp:run><hp:t>{paragraph}</hp:t></hp:run></hp:p>"
        for paragraph in paragraphs
    )
    return (
        '<hs:sec xmlns:hs="urn:hancom:section" '
        'xmlns:hp="urn:hancom:paragraph">'
        f"{body}</hs:sec>"
    )


def header_xml(text: str = "") -> str:
    """Return a non-body HWPX-like header XML document."""

    return (
        '<hh:head xmlns:hh="urn:hancom:header" '
        'xmlns:hp="urn:hancom:paragraph">'
        f"<hp:p><hp:t>{text}</hp:t></hp:p>"
        "</hh:head>"
    )


def write_hwpx(
    path: Path,
    *,
    sections: dict[str, tuple[str, ...]],
    spine: list[str] | None = None,
    manifest: list[tuple[str, str]] | None = None,
    content_hpf_text: str | None = None,
    extra_members: dict[str, str] | None = None,
) -> None:
    """Write a deterministic minimal HWPX-like ZIP package."""

    manifest_items = manifest or [
        (f"section-{index}", package_path)
        for index, package_path in enumerate(sections)
    ]
    spine_items = spine or [item_id for item_id, _ in manifest_items]

    with ZipFile(path, "w") as archive:
        archive.writestr(
            CONTENT_HPF_PATH,
            content_hpf_text
            if content_hpf_text is not None
            else content_hpf(manifest_items, spine_items),
        )
        for package_path, paragraphs in sections.items():
            archive.writestr(
                package_path,
                section_xml(*paragraphs),
            )
        for package_path, value in (extra_members or {}).items():
            archive.writestr(package_path, value)


def test_resolves_hancom_package_root_section_href(tmp_path: Path) -> None:
    path = tmp_path / "one-section.hwpx"
    text = "AIRA preserves grounded local evidence."
    write_hwpx(
        path,
        sections={"Contents/section0.xml": (text,)},
    )

    result = LocalHwpxTextExtractor().extract(path)

    assert result.content == text
    assert result.total_section_count == 1
    section = result.sections[0]
    assert section.section_index == 1
    assert section.package_path == "Contents/section0.xml"
    assert section.start_character == 0
    assert section.end_character == len(text)


def test_preserves_paragraphs_and_spine_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spine-order.hwpx"
    first = "First paragraph in reading order."
    second = "Second paragraph in the same section."
    last = "Last section despite lexical filename order."
    manifest = [
        ("zero", "Contents/section0.xml"),
        ("one", "Contents/section1.xml"),
    ]
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (last,),
            "Contents/section1.xml": (first, second),
        },
        manifest=manifest,
        spine=["one", "zero"],
    )

    result = LocalHwpxTextExtractor().extract(path)

    first_section = f"{first}{SECTION_SEPARATOR}{second}"
    assert result.content == (
        f"{first_section}{SECTION_SEPARATOR}{last}"
    )
    assert [section.package_path for section in result.sections] == [
        "Contents/section1.xml",
        "Contents/section0.xml",
    ]
    assert result.sections[0].start_character == 0
    assert result.sections[0].end_character == len(first_section)
    assert result.sections[1].start_character == (
        len(first_section) + len(SECTION_SEPARATOR)
    )
    assert result.sections[1].end_character == len(result.content)
    for section in result.sections:
        assert result.content[
            section.start_character:section.end_character
        ] == section.content



def test_real_style_spine_excludes_header_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "header-and-body.hwpx"
    body = "Actual body text from section zero."
    manifest = [
        ("header", "Contents/header.xml"),
        ("section0", "Contents/section0.xml"),
        ("settings", "settings.xml"),
    ]
    write_hwpx(
        path,
        sections={"Contents/section0.xml": (body,)},
        manifest=manifest,
        spine=["header", "section0"],
        extra_members={
            "Contents/header.xml": header_xml(
                "Header text must not become body evidence."
            ),
            "settings.xml": "<settings/>",
        },
    )

    result = LocalHwpxTextExtractor().extract(path)

    assert result.content == body
    assert result.total_section_count == 1
    assert result.sections[0].section_index == 1
    assert result.sections[0].package_path == (
        "Contents/section0.xml"
    )
    assert "Header text" not in result.content


def test_body_sections_keep_order_across_non_body_spine_items(
    tmp_path: Path,
) -> None:
    path = tmp_path / "interleaved-spine.hwpx"
    first = "First body section."
    second = "Second body section."
    manifest = [
        ("section0", "Contents/section0.xml"),
        ("header", "Contents/header.xml"),
        ("section1", "Contents/section1.xml"),
    ]
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (first,),
            "Contents/section1.xml": (second,),
        },
        manifest=manifest,
        spine=["section0", "header", "section1"],
        extra_members={
            "Contents/header.xml": header_xml("Ignored."),
        },
    )

    result = LocalHwpxTextExtractor().extract(path)

    assert result.content == f"{first}{SECTION_SEPARATOR}{second}"
    assert [section.section_index for section in result.sections] == [1, 2]
    assert [section.package_path for section in result.sections] == [
        "Contents/section0.xml",
        "Contents/section1.xml",
    ]


def test_rejects_spine_without_body_sections(
    tmp_path: Path,
) -> None:
    path = tmp_path / "header-only.hwpx"
    manifest = [("header", "Contents/header.xml")]
    write_hwpx(
        path,
        sections={},
        manifest=manifest,
        spine=["header"],
        extra_members={
            "Contents/header.xml": header_xml("Not body text."),
        },
        content_hpf_text=content_hpf(manifest, ["header"]),
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="no body section documents",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_blank_section_preserves_spine_position_without_text_span(
    tmp_path: Path,
) -> None:
    path = tmp_path / "blank-section.hwpx"
    first = "Readable first section."
    third = "Readable third section."
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (first,),
            "Contents/section1.xml": (),
            "Contents/section2.xml": (third,),
        },
    )

    result = LocalHwpxTextExtractor().extract(path)

    assert result.content == f"{first}{SECTION_SEPARATOR}{third}"
    assert result.total_section_count == 3
    blank = result.sections[1]
    assert blank.section_index == 2
    assert blank.package_path == "Contents/section1.xml"
    assert blank.content == ""
    assert blank.start_character == len(first)
    assert blank.end_character == len(first)
    assert result.content[
        blank.start_character:blank.end_character
    ] == blank.content


def test_rejects_document_without_body_text(tmp_path: Path) -> None:
    path = tmp_path / "no-text.hwpx"
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": (),
            "Contents/section1.xml": (),
        },
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="no extractable nonblank body text",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_missing_content_hpf(tmp_path: Path) -> None:
    path = tmp_path / "missing-content.hwpx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "Contents/section0.xml",
            section_xml("Text."),
        )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="missing Contents/content.hpf",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_malformed_content_hpf(tmp_path: Path) -> None:
    path = tmp_path / "malformed-content.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
        content_hpf_text="<package>",
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="malformed or unsafe: Contents/content.hpf",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_malformed_section_xml(tmp_path: Path) -> None:
    path = tmp_path / "malformed-section.hwpx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            CONTENT_HPF_PATH,
            content_hpf(
                [("section", "section0.xml")],
                ["section"],
            ),
        )
        archive.writestr("Contents/section0.xml", "<section>")

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="malformed or unsafe: Contents/section0.xml",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_invalid_zip(tmp_path: Path) -> None:
    path = tmp_path / "invalid.hwpx"
    path.write_bytes(b"not a ZIP archive")

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="not a valid ZIP archive",
    ):
        LocalHwpxTextExtractor().extract(path)


@pytest.mark.parametrize(
    ("path_factory", "message"),
    [
        (lambda root: "not-a-path", "path must be a Path"),
        (
            lambda root: root / "missing.hwpx",
            "HWPX path does not exist",
        ),
        (lambda root: root, "HWPX path is not a file"),
    ],
)
def test_rejects_invalid_path(
    tmp_path: Path,
    path_factory: Callable[[Path], object],
    message: str,
) -> None:
    path = path_factory(tmp_path)

    with pytest.raises(LocalHwpxTextExtractionError, match=message):
        LocalHwpxTextExtractor().extract(path)  # type: ignore[arg-type]


def test_rejects_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "document.zip"
    with ZipFile(path, "w"):
        pass

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match=r"must have a \.hwpx suffix",
    ):
        LocalHwpxTextExtractor().extract(path)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.xml",
        "/absolute.xml",
        "Contents/../../outside.xml",
        "\\absolute-windows-style.xml",
    ],
)
def test_rejects_unsafe_archive_member_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    path = tmp_path / "unsafe-path.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
        extra_members={unsafe_path: "unsafe"},
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="unsafe member path",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_member_count_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "too-many-members.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
        extra_members={"extra.xml": "extra"},
    )
    monkeypatch.setattr(
        "app.research.local_hwpx_text_extractor."
        "MAXIMUM_ARCHIVE_MEMBER_COUNT",
        2,
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="member count exceeds safety limit",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_individual_member_over_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "large-member.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
    )
    monkeypatch.setattr(
        "app.research.local_hwpx_text_extractor."
        "MAXIMUM_MEMBER_UNCOMPRESSED_BYTES",
        8,
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="member exceeds uncompressed size limit",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_total_uncompressed_size_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "large-total.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
    )
    monkeypatch.setattr(
        "app.research.local_hwpx_text_extractor."
        "MAXIMUM_TOTAL_UNCOMPRESSED_BYTES",
        16,
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="total uncompressed size exceeds safety limit",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_resolves_package_root_top_level_href() -> None:
    member = ZipInfo("settings.xml")

    result = LocalHwpxTextExtractor._resolve_manifest_href(
        href="settings.xml",
        members={"settings.xml": member},
    )

    assert result == "settings.xml"


def test_resolves_unambiguous_content_hpf_relative_href(
    tmp_path: Path,
) -> None:
    path = tmp_path / "relative-href.hwpx"
    text = "Relative manifest href compatibility."
    write_hwpx(
        path,
        sections={"Contents/section0.xml": (text,)},
        manifest=[("section", "section0.xml")],
        spine=["section"],
    )

    result = LocalHwpxTextExtractor().extract(path)

    assert result.content == text
    assert result.sections[0].package_path == (
        "Contents/section0.xml"
    )


def test_rejects_ambiguous_manifest_href(tmp_path: Path) -> None:
    path = tmp_path / "ambiguous-href.hwpx"
    write_hwpx(
        path,
        sections={
            "Contents/section0.xml": ("Contents candidate.",),
        },
        manifest=[("section", "section0.xml")],
        spine=["section"],
        extra_members={
            "section0.xml": section_xml("Root candidate."),
        },
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="spine target is ambiguous: section0.xml",
    ):
        LocalHwpxTextExtractor().extract(path)


def test_rejects_traversal_manifest_href(tmp_path: Path) -> None:
    path = tmp_path / "traversal-href.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
        manifest=[("section", "../section0.xml")],
        spine=["section"],
    )

    with pytest.raises(
        LocalHwpxTextExtractionError,
        match="spine target is unsafe",
    ):
        LocalHwpxTextExtractor().extract(path)


@pytest.mark.parametrize(
    ("manifest", "spine", "message"),
    [
        (
            [("section", "missing.xml")],
            ["section"],
            "spine target is invalid or missing",
        ),
        (
            [("section", "section0.xml")],
            ["missing-id"],
            "spine references a missing manifest item",
        ),
        (
            [("section", "section0.xml")],
            [],
            "no valid spine references",
        ),
    ],
)
def test_rejects_invalid_spine(
    tmp_path: Path,
    manifest: list[tuple[str, str]],
    spine: list[str],
    message: str,
) -> None:
    path = tmp_path / "invalid-spine.hwpx"
    write_hwpx(
        path,
        sections={"Contents/section0.xml": ("Text.",)},
        manifest=manifest,
        spine=spine,
        content_hpf_text=content_hpf(manifest, spine),
    )

    with pytest.raises(LocalHwpxTextExtractionError, match=message):
        LocalHwpxTextExtractor().extract(path)
