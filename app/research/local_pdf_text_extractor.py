"""Extract normalized text and page provenance from local PDF files."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader
from pypdf.errors import PyPdfError

PAGE_SEPARATOR = "\n\n"


class LocalPdfTextExtractionError(ValueError):
    """Raised when a local PDF cannot produce readable text."""


class LocalPdfTextPage(BaseModel):
    """Text and normalized character range for one physical PDF page."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    page_number: int = Field(ge=1)
    content: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        """Validate readable and blank page range semantics."""

        if self.content:
            if not self.content.strip():
                raise ValueError(
                    "page content must be normalized or empty"
                )
            if self.end_character <= self.start_character:
                raise ValueError(
                    "nonblank page range must not be empty"
                )
            if (
                self.end_character - self.start_character
                != len(self.content)
            ):
                raise ValueError(
                    "page range length must match content length"
                )
        elif self.end_character != self.start_character:
            raise ValueError(
                "blank page range must be empty"
            )

        return self


class LocalPdfTextExtractionResult(BaseModel):
    """Normalized PDF text with ordered physical-page provenance."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    content: str
    pages: list[LocalPdfTextPage]
    total_page_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate page count, order, and character provenance."""

        if not self.content.strip():
            raise ValueError(
                "PDF extraction content must not be blank"
            )
        if len(self.pages) != self.total_page_count:
            raise ValueError(
                "total_page_count must match pages"
            )
        if [page.page_number for page in self.pages] != list(
            range(1, self.total_page_count + 1)
        ):
            raise ValueError(
                "PDF pages must preserve physical page order"
            )

        for page in self.pages:
            if page.end_character > len(self.content):
                raise ValueError(
                    "page range must be within document content"
                )
            if page.content and self.content[
                page.start_character:page.end_character
            ] != page.content:
                raise ValueError(
                    "page content must match its document range"
                )

        return self


class LocalPdfTextExtractor:
    """Extract page text from a local text-based PDF."""

    def extract(
        self,
        path: Path,
    ) -> LocalPdfTextExtractionResult:
        """Return normalized page text with exact character offsets."""

        self._validate_path(path)

        try:
            reader = PdfReader(path)
        except (OSError, PyPdfError) as exc:
            raise LocalPdfTextExtractionError(
                f"PDF could not be opened or parsed: {path}"
            ) from exc

        if reader.is_encrypted:
            raise LocalPdfTextExtractionError(
                "encrypted PDF requires credentials"
            )

        extracted_pages: list[str] = []

        try:
            for page in reader.pages:
                extracted_pages.append(
                    (page.extract_text() or "").strip()
                )
        except PyPdfError as exc:
            raise LocalPdfTextExtractionError(
                f"PDF text extraction failed: {path}"
            ) from exc

        if not any(extracted_pages):
            raise LocalPdfTextExtractionError(
                "PDF contains no extractable nonblank text"
            )

        pages: list[LocalPdfTextPage] = []
        content_parts: list[str] = []
        cursor = 0

        for page_number, content in enumerate(
            extracted_pages,
            start=1,
        ):
            if content:
                if content_parts:
                    content_parts.append(PAGE_SEPARATOR)
                    cursor += len(PAGE_SEPARATOR)
                start_character = cursor
                content_parts.append(content)
                cursor += len(content)
                end_character = cursor
            else:
                start_character = cursor
                end_character = cursor

            pages.append(
                LocalPdfTextPage(
                    page_number=page_number,
                    content=content,
                    start_character=start_character,
                    end_character=end_character,
                )
            )

        return LocalPdfTextExtractionResult(
            content="".join(content_parts),
            pages=pages,
            total_page_count=len(extracted_pages),
        )

    @staticmethod
    def _validate_path(path: Path) -> None:
        """Validate the local PDF path before parsing."""

        if not isinstance(path, Path):
            raise LocalPdfTextExtractionError(
                "path must be a Path"
            )
        if not path.exists():
            raise LocalPdfTextExtractionError(
                f"PDF path does not exist: {path}"
            )
        if not path.is_file():
            raise LocalPdfTextExtractionError(
                f"PDF path is not a file: {path}"
            )
        if path.suffix.casefold() != ".pdf":
            raise LocalPdfTextExtractionError(
                "path must have a .pdf suffix"
            )
