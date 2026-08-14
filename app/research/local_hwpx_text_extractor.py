"""Safely extract normalized text from local HWPX packages."""

from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath
from typing import Final, Self
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile, ZipInfo

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException
from pydantic import BaseModel, ConfigDict, Field, model_validator

SECTION_SEPARATOR: Final[str] = "\n\n"
CONTENT_HPF_PATH: Final[str] = "Contents/content.hpf"
MAXIMUM_ARCHIVE_MEMBER_COUNT: Final[int] = 2_048
MAXIMUM_MEMBER_UNCOMPRESSED_BYTES: Final[int] = 16 * 1024 * 1024
MAXIMUM_TOTAL_UNCOMPRESSED_BYTES: Final[int] = 128 * 1024 * 1024


class LocalHwpxTextExtractionError(ValueError):
    """Raised when a local HWPX cannot produce safe readable text."""


class LocalHwpxTextSection(BaseModel):
    """Text and normalized range for one spine-ordered HWPX section."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    section_index: int = Field(ge=1)
    package_path: str
    content: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_section(self) -> Self:
        """Validate package provenance and range semantics."""

        if not self.package_path.strip():
            raise ValueError("package_path must not be blank")
        if self.content:
            if not self.content.strip():
                raise ValueError(
                    "section content must be normalized or empty"
                )
            if self.end_character <= self.start_character:
                raise ValueError(
                    "nonblank section range must not be empty"
                )
            if self.end_character - self.start_character != len(
                self.content
            ):
                raise ValueError(
                    "section range length must match content length"
                )
        elif self.end_character != self.start_character:
            raise ValueError("blank section range must be empty")

        return self


class LocalHwpxTextExtractionResult(BaseModel):
    """Normalized HWPX text with spine-ordered section provenance."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    content: str
    sections: list[LocalHwpxTextSection]
    total_section_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate section count, order, and exact offsets."""

        if not self.content.strip():
            raise ValueError(
                "HWPX extraction content must not be blank"
            )
        if len(self.sections) != self.total_section_count:
            raise ValueError(
                "total_section_count must match sections"
            )
        if [section.section_index for section in self.sections] != list(
            range(1, self.total_section_count + 1)
        ):
            raise ValueError("HWPX sections must preserve spine order")

        for section in self.sections:
            if section.end_character > len(self.content):
                raise ValueError(
                    "section range must be within document content"
                )
            if self.content[
                section.start_character:section.end_character
            ] != section.content:
                raise ValueError(
                    "section content must match its document range"
                )

        return self


class LocalHwpxTextExtractor:
    """Extract safe plain text from a local HWPX package."""

    def extract(
        self,
        path: Path,
    ) -> LocalHwpxTextExtractionResult:
        """Return normalized body text and exact section provenance."""

        self._validate_path(path)

        try:
            with ZipFile(path) as archive:
                members = self._validate_archive(archive.infolist())
                section_paths = self._section_paths(
                    archive=archive,
                    members=members,
                )
                extracted = [
                    self._section_text(
                        archive=archive,
                        package_path=package_path,
                    )
                    for package_path in section_paths
                ]
        except BadZipFile as exc:
            raise LocalHwpxTextExtractionError(
                f"HWPX is not a valid ZIP archive: {path}"
            ) from exc
        except OSError as exc:
            raise LocalHwpxTextExtractionError(
                f"HWPX could not be opened: {path}"
            ) from exc

        if not any(extracted):
            raise LocalHwpxTextExtractionError(
                "HWPX contains no extractable nonblank body text"
            )

        sections: list[LocalHwpxTextSection] = []
        content_parts: list[str] = []
        cursor = 0

        for section_index, (package_path, content) in enumerate(
            zip(section_paths, extracted, strict=True),
            start=1,
        ):
            if content:
                if content_parts:
                    content_parts.append(SECTION_SEPARATOR)
                    cursor += len(SECTION_SEPARATOR)
                start_character = cursor
                content_parts.append(content)
                cursor += len(content)
                end_character = cursor
            else:
                start_character = cursor
                end_character = cursor

            sections.append(
                LocalHwpxTextSection(
                    section_index=section_index,
                    package_path=package_path,
                    content=content,
                    start_character=start_character,
                    end_character=end_character,
                )
            )

        return LocalHwpxTextExtractionResult(
            content="".join(content_parts),
            sections=sections,
            total_section_count=len(sections),
        )

    @staticmethod
    def _validate_path(path: Path) -> None:
        """Validate a local HWPX path before archive parsing."""

        if not isinstance(path, Path):
            raise LocalHwpxTextExtractionError("path must be a Path")
        if not path.exists():
            raise LocalHwpxTextExtractionError(
                f"HWPX path does not exist: {path}"
            )
        if not path.is_file():
            raise LocalHwpxTextExtractionError(
                f"HWPX path is not a file: {path}"
            )
        if path.suffix.casefold() != ".hwpx":
            raise LocalHwpxTextExtractionError(
                "path must have a .hwpx suffix"
            )

    @classmethod
    def _validate_archive(
        cls,
        infos: list[ZipInfo],
    ) -> dict[str, ZipInfo]:
        """Validate archive paths, uniqueness, and declared sizes."""

        if len(infos) > MAXIMUM_ARCHIVE_MEMBER_COUNT:
            raise LocalHwpxTextExtractionError(
                "HWPX archive member count exceeds safety limit"
            )

        members: dict[str, ZipInfo] = {}
        total_size = 0
        for info in infos:
            package_path = info.filename.replace("\\", "/")
            parts = PurePosixPath(package_path).parts
            if (
                PurePosixPath(package_path).is_absolute()
                or ".." in parts
            ):
                raise LocalHwpxTextExtractionError(
                    "HWPX archive contains an unsafe member path: "
                    f"{info.filename}"
                )
            if package_path in members:
                raise LocalHwpxTextExtractionError(
                    "HWPX archive contains duplicate member paths: "
                    f"{package_path}"
                )
            if info.file_size > MAXIMUM_MEMBER_UNCOMPRESSED_BYTES:
                raise LocalHwpxTextExtractionError(
                    "HWPX archive member exceeds uncompressed "
                    f"size limit: {package_path}"
                )
            total_size += info.file_size
            if total_size > MAXIMUM_TOTAL_UNCOMPRESSED_BYTES:
                raise LocalHwpxTextExtractionError(
                    "HWPX archive total uncompressed size exceeds "
                    "safety limit"
                )
            members[package_path] = info

        return members

    @classmethod
    def _section_paths(
        cls,
        *,
        archive: ZipFile,
        members: dict[str, ZipInfo],
    ) -> list[str]:
        """Resolve body section members from manifest and spine order."""

        if CONTENT_HPF_PATH not in members:
            raise LocalHwpxTextExtractionError(
                f"HWPX package is missing {CONTENT_HPF_PATH}"
            )

        root = cls._parse_xml(
            archive.read(CONTENT_HPF_PATH),
            package_path=CONTENT_HPF_PATH,
        )
        manifest: dict[str, str] = {}
        for element in root.iter():
            if cls._local_name(element.tag) != "item":
                continue
            item_id = element.attrib.get("id", "").strip()
            href = element.attrib.get("href", "").strip()
            if item_id and href:
                manifest[item_id] = href

        idrefs = [
            element.attrib.get("idref", "").strip()
            for element in root.iter()
            if cls._local_name(element.tag) == "itemref"
        ]
        if not idrefs or any(not item_id for item_id in idrefs):
            raise LocalHwpxTextExtractionError(
                "HWPX package has no valid spine references"
            )

        section_paths: list[str] = []
        for item_id in idrefs:
            href = manifest.get(item_id)
            if href is None:
                raise LocalHwpxTextExtractionError(
                    "HWPX spine references a missing manifest item: "
                    f"{item_id}"
                )
            package_path = cls._resolve_manifest_href(
                href=href,
                members=members,
            )
            target_root = cls._parse_xml(
                archive.read(package_path),
                package_path=package_path,
            )
            if cls._local_name(target_root.tag) == "sec":
                section_paths.append(package_path)

        if not section_paths:
            raise LocalHwpxTextExtractionError(
                "HWPX package contains no body section documents"
            )

        return section_paths

    @staticmethod
    def _resolve_manifest_href(
        *,
        href: str,
        members: dict[str, ZipInfo],
    ) -> str:
        """Resolve one safe, unambiguous manifest href."""

        normalized_href = href.replace("\\", "/")
        href_path = PurePosixPath(normalized_href)
        if href_path.is_absolute() or ".." in href_path.parts:
            raise LocalHwpxTextExtractionError(
                f"HWPX spine target is unsafe: {href}"
            )

        root_candidate = posixpath.normpath(normalized_href)
        relative_candidate = posixpath.normpath(
            posixpath.join(
                posixpath.dirname(CONTENT_HPF_PATH),
                normalized_href,
            )
        )
        matches = {
            candidate
            for candidate in (root_candidate, relative_candidate)
            if candidate in members
        }
        if not matches:
            raise LocalHwpxTextExtractionError(
                "HWPX spine target is invalid or missing: "
                f"{href}"
            )
        if len(matches) > 1:
            raise LocalHwpxTextExtractionError(
                f"HWPX spine target is ambiguous: {href}"
            )

        return matches.pop()

    @classmethod
    def _section_text(
        cls,
        *,
        archive: ZipFile,
        package_path: str,
    ) -> str:
        """Extract paragraph-preserving plain text from one section XML."""

        root = cls._parse_xml(
            archive.read(package_path),
            package_path=package_path,
        )
        paragraphs: list[str] = []
        for paragraph in root.iter():
            if cls._local_name(paragraph.tag) != "p":
                continue
            text = "".join(
                "".join(element.itertext())
                for element in paragraph.iter()
                if cls._local_name(element.tag) == "t"
            ).strip()
            if text:
                paragraphs.append(text)

        if paragraphs:
            return SECTION_SEPARATOR.join(paragraphs)

        text = "".join(
            "".join(element.itertext())
            for element in root.iter()
            if cls._local_name(element.tag) == "t"
        ).strip()
        return text

    @staticmethod
    def _parse_xml(data: bytes, *, package_path: str):
        """Parse untrusted package XML with defusedxml."""

        try:
            return DefusedElementTree.fromstring(data)
        except (DefusedXmlException, ParseError) as exc:
            raise LocalHwpxTextExtractionError(
                f"HWPX XML is malformed or unsafe: {package_path}"
            ) from exc

    @staticmethod
    def _local_name(tag: str) -> str:
        """Return an XML tag's namespace-independent local name."""

        return tag.rsplit("}", maxsplit=1)[-1]
