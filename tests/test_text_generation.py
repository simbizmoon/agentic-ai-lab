from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.services.text_generation import (
    TokenUsage,
    extract_token_usage,
    generate_text,
    validate_token_usage,
)


@dataclass(frozen=True)
class FakeInputTokenDetails:
    cached_tokens: int


@dataclass(frozen=True)
class FakeOutputTokenDetails:
    reasoning_tokens: int


@dataclass(frozen=True)
class FakeUsage:
    input_tokens: int
    input_tokens_details: FakeInputTokenDetails
    output_tokens: int
    output_tokens_details: FakeOutputTokenDetails
    total_tokens: int


@dataclass(frozen=True)
class FakeResponse:
    output_text: str
    id: str
    _request_id: str | None
    usage: FakeUsage | None


@dataclass
class FakeResponses:
    response: FakeResponse
    calls: list[dict[str, object]] = field(default_factory=list)

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeOpenAIClient:
    response: FakeResponse

    def __post_init__(self) -> None:
        self.responses = FakeResponses(self.response)


def make_usage(
    *,
    input_tokens: int = 4,
    cached_input_tokens: int = 1,
    output_tokens: int = 6,
    reasoning_tokens: int = 2,
    total_tokens: int = 10,
) -> FakeUsage:
    return FakeUsage(
        input_tokens=input_tokens,
        input_tokens_details=FakeInputTokenDetails(cached_tokens=cached_input_tokens),
        output_tokens=output_tokens,
        output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=reasoning_tokens),
        total_tokens=total_tokens,
    )


def make_response(
    *,
    output_text: str = " 테스트 응답입니다. ",
    response_id: str = "resp_test",
    request_id: str | None = "req_test",
    usage: FakeUsage | None = None,
) -> FakeResponse:
    return FakeResponse(
        output_text=output_text,
        id=response_id,
        _request_id=request_id,
        usage=usage,
    )


def test_generate_text_returns_text_ids_usage_and_elapsed_seconds() -> None:
    client = FakeOpenAIClient(make_response(usage=make_usage()))

    result = generate_text(
        client,
        model="test-model",
        user_input="Agent와 Workflow의 차이",
    )

    assert result.text == "테스트 응답입니다."
    assert result.response_id == "resp_test"
    assert result.request_id == "req_test"
    assert result.usage == TokenUsage(
        input_tokens=4,
        cached_input_tokens=1,
        output_tokens=6,
        reasoning_tokens=2,
        total_tokens=10,
    )
    assert result.elapsed_seconds >= 0


def test_generate_text_passes_expected_api_arguments_once() -> None:
    client = FakeOpenAIClient(make_response(usage=make_usage()))

    generate_text(
        client,
        model="test-model",
        user_input="  공백 제거 대상  ",
    )

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["input"] == "공백 제거 대상"
    assert isinstance(call["instructions"], str)
    assert call["instructions"]


def test_generate_text_rejects_empty_user_input_without_api_call() -> None:
    client = FakeOpenAIClient(make_response(usage=make_usage()))

    with pytest.raises(ValueError, match="user_input"):
        generate_text(client, model="test-model", user_input="   ")

    assert client.responses.calls == []


def test_generate_text_rejects_empty_output_text() -> None:
    client = FakeOpenAIClient(make_response(output_text="   ", usage=make_usage()))

    with pytest.raises(RuntimeError, match="response text is empty"):
        generate_text(client, model="test-model", user_input="질문")


def test_generate_text_allows_missing_usage_and_request_id() -> None:
    client = FakeOpenAIClient(make_response(request_id=None, usage=None))

    result = generate_text(client, model="test-model", user_input="질문")

    assert result.text == "테스트 응답입니다."
    assert result.usage is None
    assert result.request_id is None


def test_extract_token_usage_returns_none_when_usage_is_missing() -> None:
    response = make_response(usage=None)

    assert extract_token_usage(response) is None


def test_validate_token_usage_rejects_negative_token_value() -> None:
    usage = TokenUsage(
        input_tokens=-1,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        total_tokens=0,
    )

    with pytest.raises(RuntimeError, match="must not be negative"):
        validate_token_usage(usage)


def test_validate_token_usage_rejects_cached_tokens_above_input_tokens() -> None:
    usage = TokenUsage(
        input_tokens=1,
        cached_input_tokens=2,
        output_tokens=0,
        reasoning_tokens=0,
        total_tokens=1,
    )

    with pytest.raises(RuntimeError, match="cached_input_tokens"):
        validate_token_usage(usage)


def test_validate_token_usage_rejects_reasoning_tokens_above_output_tokens() -> None:
    usage = TokenUsage(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=1,
        reasoning_tokens=2,
        total_tokens=1,
    )

    with pytest.raises(RuntimeError, match="reasoning_tokens"):
        validate_token_usage(usage)


def test_validate_token_usage_rejects_incorrect_total_tokens() -> None:
    usage = TokenUsage(
        input_tokens=1,
        cached_input_tokens=0,
        output_tokens=1,
        reasoning_tokens=0,
        total_tokens=3,
    )

    with pytest.raises(RuntimeError, match="total_tokens"):
        validate_token_usage(usage)


def test_validate_token_usage_accepts_zero_boundary_values() -> None:
    usage = TokenUsage(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        total_tokens=0,
    )

    validate_token_usage(usage)
