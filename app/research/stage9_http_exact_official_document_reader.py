"""Single-request HTTP reader for an already-validated official source URL."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.research.stage9_official_web_acquisition_adapter import (
    Stage9OfficialWebDocument,
)

_MAXIMUM_RESPONSE_BYTES = 5_000_000
_MAXIMUM_EXTRACTED_TEXT_BYTES = 512_000
_MAXIMUM_PDF_PAGES = 100
_ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "application/xhtml+xml"})


class Stage9HttpExactOfficialDocumentReaderError(RuntimeError):
    """An official document read crossed transport or content boundaries."""


class Stage9OfficialDocumentDomainError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact-read URL crossed the official-domain boundary."""


class Stage9OfficialDocumentRedirectError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact read returned a redirect that was not followed."""


class Stage9OfficialDocumentTimeoutError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact official-document request timed out."""


class Stage9OfficialDocumentConnectionError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact official-document request could not connect."""


class Stage9OfficialDocumentHttpStatusError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact official-document request returned a non-success status."""


class Stage9OfficialDocumentContentTypeError(
    Stage9HttpExactOfficialDocumentReaderError
):
    """An exact official document was not a supported text response."""


class Stage9OfficialDocumentContentBoundaryError(
    Stage9HttpExactOfficialDocumentReaderError
):
    """An exact official document was blank or exceeded its byte ceiling."""


class Stage9OfficialDocumentDecodingError(Stage9HttpExactOfficialDocumentReaderError):
    """An exact official document could not be decoded safely."""


class Stage9OfficialDocumentPdfError(Stage9HttpExactOfficialDocumentReaderError):
    """An official PDF could not produce bounded, extractable text."""


class Stage9HttpExactOfficialDocumentReader:
    """Read one official text document without following redirects."""

    def __init__(
        self,
        *,
        allowed_domains: tuple[str, ...],
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not allowed_domains or any(not item.strip() for item in allowed_domains):
            raise ValueError("allowed_domains must contain nonblank domains")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._allowed_domains = allowed_domains
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    def read(self, *, url: str) -> Stage9OfficialWebDocument:
        self._validate_url(url)
        try:
            response = self._get(url)
            if response.is_redirect:
                raise Stage9OfficialDocumentRedirectError(
                    "redirects require separate validation and are not followed"
                )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise Stage9OfficialDocumentTimeoutError(
                "official document read timed out"
            ) from error
        except httpx.RequestError as error:
            raise Stage9OfficialDocumentConnectionError(
                "official document could not be reached"
            ) from error
        except httpx.HTTPStatusError as error:
            raise Stage9OfficialDocumentHttpStatusError(
                "official document returned a non-success status"
            ) from error

        self._validate_url(str(response.url))
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
        if content_type not in {*_ALLOWED_CONTENT_TYPES, "application/pdf"}:
            raise Stage9OfficialDocumentContentTypeError(
                "official document content type is not exact text"
            )
        if not response.content or len(response.content) > _MAXIMUM_RESPONSE_BYTES:
            raise Stage9OfficialDocumentContentBoundaryError(
                "official document crossed the byte boundary"
            )
        content = (
            self._extract_pdf_text(response.content)
            if content_type == "application/pdf"
            else self._decode_text(response)
        )
        if not content.strip():
            raise Stage9OfficialDocumentContentBoundaryError(
                "official document content is blank"
            )
        if len(content.encode("utf-8")) > _MAXIMUM_EXTRACTED_TEXT_BYTES:
            raise Stage9OfficialDocumentContentBoundaryError(
                "official document extracted text crossed the byte boundary"
            )
        return Stage9OfficialWebDocument(
            url=str(response.url),
            title=str(response.url),
            content=content,
            retrieved_at=self._clock().isoformat(),
            response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _decode_text(response: httpx.Response) -> str:
        try:
            return response.content.decode(response.encoding or "utf-8")
        except UnicodeDecodeError as error:
            raise Stage9OfficialDocumentDecodingError(
                "official document text decoding failed"
            ) from error

    @staticmethod
    def _extract_pdf_text(content: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise Stage9OfficialDocumentPdfError(
                    "encrypted official PDF is unsupported"
                )
            if len(reader.pages) > _MAXIMUM_PDF_PAGES:
                raise Stage9OfficialDocumentPdfError(
                    "official PDF crossed the page boundary"
                )
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except Stage9OfficialDocumentPdfError:
            raise
        except (OSError, PyPdfError) as error:
            raise Stage9OfficialDocumentPdfError(
                "official PDF could not be parsed"
            ) from error
        if not any(pages):
            raise Stage9OfficialDocumentPdfError(
                "official PDF contains no extractable text"
            )
        return "\n\n".join(page for page in pages if page)

    def _get(self, url: str) -> httpx.Response:
        kwargs = {"timeout": self._timeout_seconds, "follow_redirects": False}
        if self._client is not None:
            return self._client.get(url, **kwargs)
        with httpx.Client() as client:
            return client.get(url, **kwargs)

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not any(
            host == domain.casefold() or host.endswith(f".{domain.casefold()}")
            for domain in self._allowed_domains
        ):
            raise Stage9OfficialDocumentDomainError(
                "official document URL is outside the allowlist"
            )
