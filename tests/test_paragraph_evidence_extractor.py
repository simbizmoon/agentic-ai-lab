"""Tests for query-aware paragraph evidence extraction."""

from app.research.paragraph_evidence_extractor import ParagraphEvidenceExtractor
from app.schemas.research_evidence_extraction import (
    ResearchEvidenceExtractionStatus,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import ResearchSourceCandidate
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


def document(
    content: str,
    *,
    query: str = "OpenAI Responses API official documentation overview",
) -> ResearchSourceDocument:
    candidate = ResearchSourceCandidate(
        source_id="source-001",
        request_id="request-001",
        task_id="task-001",
        query_id="query-001",
        title="OpenAI API overview",
        url="https://developers.example.com/api",
        source_type=ResearchSourceType.OTHER,
        snippet="OpenAI API authentication, request IDs, and Responses",
        rank=1,
        metadata={"search_query_text": query},
    )
    return ResearchSourceDocument(
        document_id="document-001",
        candidate=candidate,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="test-reader",
    )


def excerpts(content: str) -> list[str]:
    result = ParagraphEvidenceExtractor(
        maximum_evidence=5,
        minimum_characters=40,
    ).extract(document(content))
    return [item.excerpt for item in result.evidence]


def test_keeps_query_specific_responses_paragraph() -> None:
    content = (
        "The Responses API supports stateful interactions and built-in "
        "tools such as web search and file search.\n\n"
        "API key revocations take effect within a few seconds.\n\n"
        "The X-Client-Request-Id header can identify requests."
    )
    assert excerpts(content) == [
        (
            "The Responses API supports stateful interactions and built-in "
            "tools such as web search and file search."
        )
    ]


def test_filters_fenced_code_and_execution_instructions() -> None:
    content = (
        "The Responses API supports function calling and conversation "
        "state for multi-turn agent workflows.\n\n"
        "Execute the code with `python example.py`. In a few moments, "
        "you should see the output of your API request.\n\n"
        "```csharp\n"
        "using System.Text.Json;\n"
        "using OpenAI.Responses;\n"
        "#pragma warning disable OPENAI001"
    )
    assert excerpts(content) == [
        (
            "The Responses API supports function calling and conversation "
            "state for multi-turn agent workflows."
        )
    ]


def test_filters_link_index_and_structured_code() -> None:
    content = (
        "For the complete documentation index, see llms.txt.\n\n"
        "- [Quickstart](https://example.com/quickstart)\n"
        "- [Function calling](https://example.com/function)\n\n"
        'tools = [{"type": "function", "name": "weather"}]\n\n'
        "Responses can use previous response identifiers to preserve "
        "conversation state."
    )
    assert excerpts(content) == [
        (
            "Responses can use previous response identifiers to preserve "
            "conversation state."
        )
    ]


def test_hard_filters_unfenced_code_and_single_bullet_noise() -> None:
    content = (
        "The Responses API supports stateful interactions and built-in "
        "tools for agent workflows.\n\n"
        "- OpenAI logs this value internally for endpoints including "
        "responses.\n\n"
        "response = openai.responses.create(\n"
        '  model: "gpt-5.6",\n'
        '  input: [{"role": "user"}]\n'
        ")\n\n"
        "var responses = client.CreateResponseStreamingAsync(\n"
        '    "gpt-5.6", "Hello"\n'
        ");\n\n"
        "await foreach (StreamingResponseUpdate response in responses)\n"
        "{\n"
        "    Console.Write(response);\n"
        "}"
    )

    assert excerpts(content) == [
        (
            "The Responses API supports stateful interactions and built-in "
            "tools for agent workflows."
        )
    ]


def test_returns_no_evidence_status_when_all_chunks_are_filtered() -> None:
    content = (
        "```csharp\n"
        "using System.Text.Json;\n"
        "using OpenAI.Responses;\n"
        "#pragma warning disable OPENAI001\n"
        "```"
    )

    result = ParagraphEvidenceExtractor(
        minimum_characters=20,
    ).extract(document(content))

    assert (
        result.status
        is ResearchEvidenceExtractionStatus.NO_EVIDENCE
    )
    assert result.evidence == []


def test_hard_filters_simple_code_calls_and_link_fragments() -> None:
    content = (
        "The Responses API supports stateful interactions, built-in "
        "tools, and function calling.\n\n"
        "Start building with the Responses API.]"
        "(https://github.com/openai/openai-responses-starter-app)\n\n"
        "var responses = client.CreateResponseStreamingAsync(\n"
        '    "gpt-5.6",\n'
        '    "Say hello."\n'
        ");\n\n"
        "Use server-sent events to stream model responses fast.]"
        "(https://developers.openai.com/api/docs/guides/"
        "streaming-responses)"
    )

    assert excerpts(content) == [
        (
            "The Responses API supports stateful interactions, built-in "
            "tools, and function calling."
        )
    ]


def test_hard_filters_multi_link_document_indexes() -> None:
    content = (
        "The Responses API is the primary interface for model "
        "responses and supports stateful interactions.\n\n"
        "Identify harmful content in text and images.\n"
        "- [Multi-agent](https://example.com/multi-agent): "
        "Enable multi-agent workflows.\n"
        "- [Node reference](https://example.com/nodes): "
        "Explore workflow nodes.\n"
        "- [Orchestration](https://example.com/orchestration): "
        "Learn agent handoffs.\n\n"
        "## Libraries\n"
        "- [SDKs and CLI](https://example.com/sdks): "
        "Discover official SDKs.\n"
        "- [OpenAI CLI](https://example.com/cli): "
        "Install the command-line tool."
    )

    assert excerpts(content) == [
        (
            "The Responses API is the primary interface for model "
            "responses and supports stateful interactions."
        )
    ]

def test_candidate_chunks_expose_semantic_candidate_before_lexical_cutoff() -> None:
    content = (
        "Agent loops and Responses API overview material appear here "
        "with the exact query terminology used by search.\n\n"
        "A callable capability may be registered with a name, description, "
        "and input shape, then selected during execution even when this "
        "paragraph avoids the originating query's exact wording."
    )
    source = document(
        content,
        query="OpenAI Agents SDK tool calling mechanism",
    )
    extractor = ParagraphEvidenceExtractor(
        maximum_evidence=1,
        minimum_characters=40,
        minimum_score=0.22,
    )

    candidates = extractor.candidate_chunks(source)

    assert len(candidates) == 2
    second = candidates[1]
    assert second.text == content[second.start:second.end]
    assert second.lexical_score < 0.22


def test_candidate_chunks_remove_hard_noise_without_score_filtering() -> None:
    content = (
        "A meaningful natural-language paragraph explains runtime behavior "
        "without requiring lexical overlap with the query.\n\n"
        "```python\nclient.responses.create(model='example')\n```"
    )
    source = document(
        content,
        query="completely different vocabulary",
    )
    extractor = ParagraphEvidenceExtractor(
        minimum_characters=20,
    )

    candidates = extractor.candidate_chunks(source)

    assert len(candidates) == 1
    assert "meaningful natural-language" in candidates[0].text
    assert "client.responses.create" not in candidates[0].text


def test_extract_still_applies_lexical_threshold_and_top_n() -> None:
    content = (
        "OpenAI Agents SDK tool calling mechanism tool function "
        "execution provides highly overlapping query terminology.\n\n"
        "A callable capability may be registered using alternate words "
        "that remain semantically useful but have weak lexical overlap."
    )
    source = document(
        content,
        query="OpenAI Agents SDK tool calling mechanism",
    )
    extractor = ParagraphEvidenceExtractor(
        maximum_evidence=1,
        minimum_characters=40,
        minimum_score=0.22,
    )

    candidates = extractor.candidate_chunks(source)
    result = extractor.extract(source)

    assert len(candidates) == 2
    assert len(result.evidence) == 1
    assert result.evidence[0].excerpt == candidates[0].text
