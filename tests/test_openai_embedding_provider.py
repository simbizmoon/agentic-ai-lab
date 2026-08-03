"""Tests for the OpenAI embedding provider."""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.embedding_provider import EmbeddingProviderError
from app.rag.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)


class FakeEmbeddings:
    """Return predefined embedding API responses."""

    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)

        if not self._responses:
            raise RuntimeError("no fake response available")

        response = self._responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


class FakeClient:
    """Minimal fake OpenAI client."""

    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self.embeddings = FakeEmbeddings(responses)


def embedding_response(
    vectors: list[list[float]],
) -> object:
    """Build a fake OpenAI embedding response."""

    return SimpleNamespace(
        data=[
            SimpleNamespace(
                index=index,
                embedding=vector,
            )
            for index, vector in enumerate(vectors)
        ]
    )


def test_provider_exposes_configuration() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient([]),
        model_name="test-embedding-model",
        dimensions=3,
    )

    assert provider.model_name == "test-embedding-model"
    assert provider.dimensions == 3


def test_provider_sends_expected_api_request() -> None:
    client = FakeClient(
        [
            embedding_response(
                [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                ]
            )
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=client,
        model_name="test-model",
        dimensions=3,
    )

    provider.embed_texts(
        [
            "first text",
            "second text",
        ]
    )

    assert client.embeddings.calls == [
        {
            "model": "test-model",
            "input": [
                "first text",
                "second text",
            ],
            "dimensions": 3,
            "encoding_format": "float",
        }
    ]


def test_provider_returns_text_embeddings() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                embedding_response(
                    [
                        [0.1, 0.2, 0.3],
                        [0.4, 0.5, 0.6],
                    ]
                )
            ]
        ),
        model_name="test-model",
        dimensions=3,
    )

    embeddings = provider.embed_texts(
        [
            "first text",
            "second text",
        ]
    )

    assert len(embeddings) == 2
    assert embeddings[0].model_name == "test-model"
    assert embeddings[0].dimensions == 3
    assert embeddings[0].vector == [
        0.1,
        0.2,
        0.3,
    ]
    assert embeddings[1].vector == [
        0.4,
        0.5,
        0.6,
    ]


def test_provider_embed_text_uses_single_input() -> None:
    client = FakeClient(
        [
            embedding_response(
                [
                    [0.6, 0.8],
                ]
            )
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=client,
        dimensions=2,
    )

    embedding = provider.embed_text("single text")

    assert embedding.vector == [0.6, 0.8]
    assert client.embeddings.calls[0]["input"] == [
        "single text"
    ]


def test_provider_returns_empty_for_no_texts() -> None:
    client = FakeClient([])
    provider = OpenAIEmbeddingProvider(
        client=client,
        dimensions=3,
    )

    embeddings = provider.embed_texts([])

    assert embeddings == []
    assert client.embeddings.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_provider_rejects_blank_text(
    text: str,
) -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient([]),
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="must not be blank",
    ):
        provider.embed_text(text)


@pytest.mark.parametrize(
    "model_name",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_provider_rejects_blank_model_name(
    model_name: str,
) -> None:
    with pytest.raises(
        EmbeddingProviderError,
        match="model_name must not be blank",
    ):
        OpenAIEmbeddingProvider(
            client=FakeClient([]),
            model_name=model_name,
        )


@pytest.mark.parametrize(
    "dimensions",
    [
        0,
        -1,
    ],
)
def test_provider_rejects_invalid_dimensions(
    dimensions: int,
) -> None:
    with pytest.raises(
        EmbeddingProviderError,
        match="greater than zero",
    ):
        OpenAIEmbeddingProvider(
            client=FakeClient([]),
            dimensions=dimensions,
        )


def test_provider_wraps_api_failure() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                RuntimeError("API unavailable"),
            ]
        ),
        dimensions=3,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="request failed",
    ):
        provider.embed_text("example text")


def test_provider_rejects_missing_response_data() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                SimpleNamespace(),
            ]
        ),
        dimensions=3,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="did not contain data",
    ):
        provider.embed_text("example text")


def test_provider_rejects_wrong_embedding_count() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                embedding_response([]),
            ]
        ),
        dimensions=3,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="unexpected embedding count",
    ):
        provider.embed_text("example text")


def test_provider_reorders_items_by_index() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=1,
                embedding=[0.0, 1.0],
            ),
            SimpleNamespace(
                index=0,
                embedding=[1.0, 0.0],
            ),
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=FakeClient([response]),
        dimensions=2,
    )

    embeddings = provider.embed_texts(
        [
            "first",
            "second",
        ]
    )

    assert embeddings[0].vector == [1.0, 0.0]
    assert embeddings[1].vector == [0.0, 1.0]


def test_provider_rejects_invalid_item_index() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=-1,
                embedding=[1.0, 0.0],
            )
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=FakeClient([response]),
        dimensions=2,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="invalid index",
    ):
        provider.embed_text("example")


def test_provider_rejects_missing_vector() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
            )
        ]
    )
    provider = OpenAIEmbeddingProvider(
        client=FakeClient([response]),
        dimensions=2,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="did not contain a vector",
    ):
        provider.embed_text("example")


def test_provider_rejects_dimension_mismatch() -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                embedding_response(
                    [
                        [1.0, 0.0],
                    ]
                )
            ]
        ),
        dimensions=3,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="dimensions did not match",
    ):
        provider.embed_text("example")


@pytest.mark.parametrize(
    "invalid_value",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_provider_rejects_invalid_vector_values(
    invalid_value: float,
) -> None:
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(
            [
                embedding_response(
                    [
                        [1.0, invalid_value],
                    ]
                )
            ]
        ),
        dimensions=2,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="invalid values",
    ):
        provider.embed_text("example")
