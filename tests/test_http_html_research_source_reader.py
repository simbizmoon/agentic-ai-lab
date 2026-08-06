"""Tests for the safe HTTP/HTML research source reader."""

import httpx

from app.research.http_html_research_source_reader import (
    HttpHtmlResearchSourceReader,
)
from app.research.research_source_reader_validator import (
    ResearchSourceReaderValidator,
)
from app.schemas.http_html_reader_config import HttpHtmlReaderConfig
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentStatus,
)


def candidate(
    *,
    url: str = "https://example.com/source",
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        source_id="source-001",
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Example source",
        url=url,
        source_type=ResearchSourceType.OTHER,
        rank=1,
    )


def public_resolver(
    hostname: str,
    port: int | None,
) -> list[str]:
    del hostname, port
    return ["93.184.216.34"]


def reader_for(
    transport: httpx.MockTransport,
    *,
    config: HttpHtmlReaderConfig | None = None,
    resolver=public_resolver,
) -> HttpHtmlResearchSourceReader:
    return HttpHtmlResearchSourceReader(
        config=config,
        client=httpx.Client(transport=transport),
        resolver=resolver,
    )


def test_reader_extracts_visible_html_text() -> None:
    html = """
    <html>
      <head>
        <style>hidden style</style>
        <script>hidden script</script>
      </head>
      <body>
        <main>
          <h1>Agent Memory</h1>
          <p>Memory stores useful context.</p>
          <p>Episodic memory stores experiences.</p>
        </main>
      </body>
    </html>
    """
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=html.encode(),
            request=request,
        )
    )

    document = reader_for(transport).read(candidate())

    assert document.status is ResearchSourceDocumentStatus.READ
    assert document.content_type is ResearchSourceContentType.HTML
    assert "Agent Memory" in document.content
    assert "Memory stores useful context." in document.content
    assert "hidden script" not in document.content
    assert "hidden style" not in document.content
    assert len(document.sections) == 3


def test_reader_reads_plain_text() -> None:
    body = "First paragraph.\n\nSecond paragraph."
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=body.encode(),
            request=request,
        )
    )

    document = reader_for(transport).read(candidate())

    assert document.status is ResearchSourceDocumentStatus.READ
    assert document.content_type is ResearchSourceContentType.TEXT
    assert document.content == body
    assert len(document.sections) == 2


def test_reader_follows_valid_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/source":
            return httpx.Response(
                302,
                headers={"Location": "/final"},
                request=request,
            )

        return httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=b"Final source.",
            request=request,
        )

    document = reader_for(
        httpx.MockTransport(handler)
    ).read(candidate())

    assert document.status is ResearchSourceDocumentStatus.READ
    assert document.metadata["redirect_count"] == "1"
    assert document.metadata["final_url"] == (
        "https://example.com/final"
    )


def test_reader_blocks_private_and_local_destinations() -> None:
    def private_resolver(
        hostname: str,
        port: int | None,
    ) -> list[str]:
        del hostname, port
        return ["127.0.0.1"]

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=b"Should not be requested.",
            request=request,
        )
    )

    private = reader_for(
        transport,
        resolver=private_resolver,
    ).read(candidate())

    assert private.status is ResearchSourceDocumentStatus.FAILED
    assert private.error is not None
    assert private.error.error_type == "UnsafeSourceUrl"

    local = reader_for(transport).read(
        candidate(url="http://localhost/source")
    )

    assert local.error is not None
    assert local.error.error_type == "UnsafeSourceUrl"


def test_reader_validates_redirect_destination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/private"},
            request=request,
        )

    document = reader_for(
        httpx.MockTransport(handler)
    ).read(candidate())

    assert document.error is not None
    assert document.error.error_type == "UnsafeSourceUrl"


def test_reader_rejects_redirect_limit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"Location": "/again"},
            request=request,
        )
    )
    config = HttpHtmlReaderConfig(maximum_redirects=1)

    document = reader_for(
        transport,
        config=config,
    ).read(candidate())

    assert document.error is not None
    assert document.error.error_type == "RedirectLimitExceeded"


def test_reader_rejects_large_documents() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=b"A" * 2_000,
            request=request,
        )
    )
    config = HttpHtmlReaderConfig(maximum_bytes=1_024)

    document = reader_for(
        transport,
        config=config,
    ).read(candidate())

    assert document.error is not None
    assert document.error.error_type == "DocumentTooLarge"


def test_reader_rejects_declared_large_documents() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={
                "Content-Type": "text/plain",
                "Content-Length": "2000",
            },
            content=b"small",
            request=request,
        )
    )
    config = HttpHtmlReaderConfig(maximum_bytes=1_024)

    document = reader_for(
        transport,
        config=config,
    ).read(candidate())

    assert document.error is not None
    assert document.error.error_type == "DocumentTooLarge"


def test_reader_rejects_unsupported_and_empty_content() -> None:
    unsupported = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF",
            request=request,
        )
    )

    document = reader_for(unsupported).read(candidate())
    assert document.error is not None
    assert document.error.error_type == "UnsupportedContentType"

    empty = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            content=b"<script>only hidden text</script>",
            request=request,
        )
    )

    document = reader_for(empty).read(candidate())
    assert document.error is not None
    assert document.error.error_type == "EmptyDocument"


def test_reader_maps_http_timeout_and_network_errors() -> None:
    status_transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            request=request,
        )
    )
    document = reader_for(status_transport).read(candidate())
    assert document.error is not None
    assert document.error.error_type == "DocumentHttpError"
    assert document.error.retryable is True

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    document = reader_for(
        httpx.MockTransport(timeout_handler)
    ).read(candidate())
    assert document.error is not None
    assert document.error.error_type == "DocumentReadTimeout"

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network", request=request)

    document = reader_for(
        httpx.MockTransport(network_handler)
    ).read(candidate())
    assert document.error is not None
    assert document.error.error_type == "DocumentNetworkError"


def test_reader_output_satisfies_existing_contract() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            content=b"Readable source.",
            request=request,
        )
    )
    reader = reader_for(transport)
    source = candidate()
    document = reader.read(source)

    ResearchSourceReaderValidator().validate_document(
        reader=reader,
        candidate=source,
        document=document,
    )

class CountingByteStream(httpx.SyncByteStream):
    """Track how many response chunks were consumed."""

    def __init__(self) -> None:
        self.chunks_yielded = 0

    def __iter__(self):
        for chunk in [
            b"A" * 600,
            b"B" * 600,
            b"C" * 600,
        ]:
            self.chunks_yielded += 1
            yield chunk


def test_reader_stops_stream_when_size_limit_is_exceeded() -> None:
    stream = CountingByteStream()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            stream=stream,
            request=request,
        )
    )
    config = HttpHtmlReaderConfig(
        maximum_bytes=1_024
    )

    document = reader_for(
        transport,
        config=config,
    ).read(candidate())

    assert document.error is not None
    assert document.error.error_type == "DocumentTooLarge"
    assert stream.chunks_yielded == 2
