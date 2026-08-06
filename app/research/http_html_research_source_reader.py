"""Safe HTTP/HTML implementation of the research source reader port."""

from __future__ import annotations

import socket
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import ClassVar
from urllib.parse import urljoin, urlsplit

import httpx

from app.research.research_source_reader import ResearchSourceReader
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentStatus,
)

Resolver = Callable[[str, int | None], list[str]]

_ALLOWED_CONTENT_TYPES = {
    "text/html": ResearchSourceContentType.HTML,
    "application/xhtml+xml": ResearchSourceContentType.HTML,
    "text/plain": ResearchSourceContentType.TEXT,
    "text/markdown": ResearchSourceContentType.MARKDOWN,
}


class _VisibleTextParser(HTMLParser):
    """Extract visible text while ignoring executable or hidden elements."""

    _BLOCK_TAGS: ClassVar[set[str]] = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }
    _IGNORED_TAGS: ClassVar[set[str]] = {
        "script",
        "style",
        "noscript",
        "template",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs

        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return

        if self._ignored_depth == 0 and tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        """Return normalized visible text."""

        raw = "".join(self._parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]

        paragraphs: list[str] = []
        current: list[str] = []

        for line in lines:
            if line:
                current.append(line)
                continue

            if current:
                paragraphs.append(" ".join(current))
                current = []

        if current:
            paragraphs.append(" ".join(current))

        return "\n\n".join(paragraphs).strip()


class HttpHtmlResearchSourceReader(ResearchSourceReader):
    """Read public HTTP/HTTPS sources with strict safety limits."""

    def __init__(
        self,
        *,
        config: HttpHtmlReaderConfig | None = None,
        client: httpx.Client | None = None,
        resolver: Resolver | None = None,
        name: str = "http-html-reader",
    ) -> None:
        if not name.strip():
            raise ValueError("name must not be blank")

        self._config = config or HttpHtmlReaderConfig()
        self._client = client
        self._resolver = resolver or self._default_resolver
        self._name = name

    @property
    def name(self) -> str:
        """Return the reader name."""

        return self._name

    def read(
        self,
        candidate: ResearchSourceCandidate,
    ) -> ResearchSourceDocument:
        """Read one public HTTP/HTTPS source."""

        try:
            response, redirect_count, body = self._fetch(
                candidate.url
            )
            content_type = self._content_type(response)

            if content_type not in _ALLOWED_CONTENT_TYPES:
                return self._failed_document(
                    candidate=candidate,
                    error_type="UnsupportedContentType",
                    message=(
                        "Source content type is not supported "
                        "by the HTTP/HTML reader."
                    ),
                    retryable=False,
                    metadata={
                        "http_status": str(response.status_code),
                        "content_type": content_type or "missing",
                    },
                )

            text = self._decode(response, body)
            normalized_type = _ALLOWED_CONTENT_TYPES[content_type]

            if normalized_type is ResearchSourceContentType.HTML:
                text = self._html_to_text(text)

            text = text.strip()
            if not text:
                return self._failed_document(
                    candidate=candidate,
                    error_type="EmptyDocument",
                    message="Source document contains no readable text.",
                    retryable=False,
                    metadata={
                        "http_status": str(response.status_code),
                        "content_type": content_type,
                    },
                )

            sections = self._build_sections(text)

            return ResearchSourceDocument(
                document_id=self._document_id(candidate),
                candidate=candidate,
                status=ResearchSourceDocumentStatus.READ,
                content_type=normalized_type,
                content=text,
                language=None,
                sections=sections,
                word_count=len(text.split()),
                character_count=len(text),
                reader=self.name,
                error=None,
                metadata={
                    "transport": "http",
                    "http_status": str(response.status_code),
                    "content_type": content_type,
                    "final_url": str(response.url),
                    "redirect_count": str(redirect_count),
                    "received_bytes": str(len(body)),
                },
            )
        except _UnsafeSourceError:
            return self._failed_document(
                candidate=candidate,
                error_type="UnsafeSourceUrl",
                message=(
                    "Source URL is not allowed by the "
                    "HTTP reader safety policy."
                ),
                retryable=False,
            )
        except _RedirectLimitError:
            return self._failed_document(
                candidate=candidate,
                error_type="RedirectLimitExceeded",
                message="Source exceeded the configured redirect limit.",
                retryable=False,
            )
        except _DocumentTooLargeError:
            return self._failed_document(
                candidate=candidate,
                error_type="DocumentTooLarge",
                message="Source document exceeds the configured size limit.",
                retryable=False,
            )
        except httpx.TimeoutException:
            return self._failed_document(
                candidate=candidate,
                error_type="DocumentReadTimeout",
                message="Source reading timed out.",
                retryable=True,
            )
        except httpx.RequestError:
            return self._failed_document(
                candidate=candidate,
                error_type="DocumentNetworkError",
                message="Source could not be reached.",
                retryable=True,
            )
        except httpx.HTTPStatusError as exc:
            return self._http_failure(
                candidate=candidate,
                response=exc.response,
            )
        except (UnicodeDecodeError, LookupError):
            return self._failed_document(
                candidate=candidate,
                error_type="DocumentDecodeError",
                message="Source text encoding could not be decoded.",
                retryable=False,
            )

    def _fetch(
        self,
        url: str,
    ) -> tuple[httpx.Response, int, bytes]:
        """Fetch a source while enforcing redirect and size limits."""

        current_url = url
        redirects = 0

        with self._client_context() as client:
            while True:
                self._validate_public_url(current_url)

                with client.stream(
                    "GET",
                    current_url,
                    headers={
                        "User-Agent": self._config.user_agent,
                        "Accept": (
                            "text/html,application/xhtml+xml,"
                            "text/plain,text/markdown;q=0.9"
                        ),
                    },
                    timeout=self._config.timeout_seconds,
                    follow_redirects=False,
                ) as response:
                    if response.status_code in {
                        301,
                        302,
                        303,
                        307,
                        308,
                    }:
                        if (
                            redirects
                            >= self._config.maximum_redirects
                        ):
                            raise _RedirectLimitError

                        location = response.headers.get(
                            "Location"
                        )

                        if (
                            location is None
                            or not location.strip()
                        ):
                            response.raise_for_status()

                        current_url = urljoin(
                            current_url,
                            location.strip(),
                        )
                        redirects += 1
                        continue

                    response.raise_for_status()
                    self._validate_declared_size(response)

                    body = bytearray()

                    for chunk in response.iter_bytes():
                        body.extend(chunk)

                        if (
                            len(body)
                            > self._config.maximum_bytes
                        ):
                            raise _DocumentTooLargeError

                    return (
                        response,
                        redirects,
                        bytes(body),
                    )

    def _client_context(
        self,
    ) -> AbstractContextManager[httpx.Client]:
        """Return a managed or injected HTTP client context."""

        if self._client is not None:
            return nullcontext(self._client)

        return httpx.Client()

    def _validate_public_url(self, url: str) -> None:
        """Reject malformed, local, private, and special-use destinations."""

        parsed = urlsplit(url.strip())

        if parsed.scheme.casefold() not in {"http", "https"}:
            raise _UnsafeSourceError
        if not parsed.hostname:
            raise _UnsafeSourceError
        if parsed.username is not None or parsed.password is not None:
            raise _UnsafeSourceError

        hostname = parsed.hostname.casefold().rstrip(".")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise _UnsafeSourceError

        try:
            direct_ip = ip_address(hostname)
        except ValueError:
            addresses = self._resolver(hostname, parsed.port)
        else:
            addresses = [str(direct_ip)]

        if not addresses:
            raise _UnsafeSourceError

        for address in addresses:
            try:
                resolved = ip_address(address)
            except ValueError as exc:
                raise _UnsafeSourceError from exc

            if not resolved.is_global:
                raise _UnsafeSourceError

    def _validate_declared_size(self, response: httpx.Response) -> None:
        """Reject a declared response larger than the configured maximum."""

        value = response.headers.get("Content-Length")
        if value is None:
            return

        try:
            declared = int(value)
        except ValueError:
            return

        if declared > self._config.maximum_bytes:
            raise _DocumentTooLargeError

    def _content_type(self, response: httpx.Response) -> str:
        """Return the normalized MIME type."""

        value = response.headers.get("Content-Type", "")
        return value.split(";", 1)[0].strip().casefold()

    @staticmethod
    def _decode(response: httpx.Response, body: bytes) -> str:
        """Decode response bytes using HTTPX encoding resolution."""

        encoding = response.encoding or "utf-8"
        return body.decode(encoding)

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Extract normalized visible text from HTML."""

        parser = _VisibleTextParser()
        parser.feed(html)
        parser.close()
        return parser.text()

    @staticmethod
    def _build_sections(
        content: str,
    ) -> list[ResearchSourceDocumentSection]:
        """Convert nonblank paragraphs into ordered sections."""

        sections: list[ResearchSourceDocumentSection] = []
        search_position = 0

        for paragraph in content.split("\n\n"):
            if not paragraph.strip():
                search_position += len(paragraph) + 2
                continue

            start = content.find(paragraph, search_position)
            if start < 0:
                raise ValueError(
                    "paragraph could not be located within document content"
                )

            end = start + len(paragraph)
            order = len(sections) + 1

            sections.append(
                ResearchSourceDocumentSection(
                    section_id=f"section-{order:03d}",
                    heading=None,
                    content=paragraph,
                    order=order,
                    start_character=start,
                    end_character=end,
                )
            )
            search_position = end + 2

        return sections

    @staticmethod
    def _document_id(candidate: ResearchSourceCandidate) -> str:
        """Return a deterministic document ID."""

        return (
            f"{candidate.request_id.strip()}-document-"
            f"{candidate.source_id.strip()}"
        )

    def _http_failure(
        self,
        *,
        candidate: ResearchSourceCandidate,
        response: httpx.Response,
    ) -> ResearchSourceDocument:
        """Map an HTTP status failure to a document error."""

        status = response.status_code
        retryable = status == 429 or status >= 500

        return self._failed_document(
            candidate=candidate,
            error_type="DocumentHttpError",
            message=f"Source request failed with HTTP status {status}.",
            retryable=retryable,
            metadata={"http_status": str(status)},
        )

    def _failed_document(
        self,
        *,
        candidate: ResearchSourceCandidate,
        error_type: str,
        message: str,
        retryable: bool,
        metadata: dict[str, str] | None = None,
    ) -> ResearchSourceDocument:
        """Create one structured failed document."""

        return ResearchSourceDocument(
            document_id=self._document_id(candidate),
            candidate=candidate,
            status=ResearchSourceDocumentStatus.FAILED,
            content_type=ResearchSourceContentType.OTHER,
            content="",
            language=None,
            sections=[],
            word_count=0,
            character_count=0,
            reader=self.name,
            error=ResearchSourceDocumentError(
                error_type=error_type,
                message=message,
                retryable=retryable,
            ),
            metadata={
                "transport": "http",
                **(metadata or {}),
            },
        )

    @staticmethod
    def _default_resolver(
        hostname: str,
        port: int | None,
    ) -> list[str]:
        """Resolve all destination addresses."""

        return sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(
                    hostname,
                    port or 443,
                    type=socket.SOCK_STREAM,
                )
            }
        )


class _UnsafeSourceError(ValueError):
    """Raised when a source violates the URL safety policy."""


class _RedirectLimitError(ValueError):
    """Raised when a source exceeds the redirect limit."""


class _DocumentTooLargeError(ValueError):
    """Raised when a source exceeds the configured size limit."""
