from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import openai
import pytest
from pydantic import ValidationError

from app.budget import ExecutionBudget
from app.exceptions import (
    AttemptBudgetExceededError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
)
from app.schemas.text_analysis import Sentiment, TextAnalysis
from app.services import structured_analysis as service
from app.services.structured_analysis import StructuredAnalysisExecution
from app.services.text_generation import TokenUsage

DEFAULT_OUTPUT = object()


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
class FakeRefusalContent:
    refusal: str


@dataclass(frozen=True)
class FakeOutputMessage:
    content: list[object]


@dataclass(frozen=True)
class FakeParsedResponse:
    output_parsed: object | None
    status: str = "completed"
    id: str = "resp_structured"
    _request_id: str | None = "req_structured"
    usage: FakeUsage | None = None
    output: list[object] = field(default_factory=list)


@dataclass
class FakeResponses:
    outcomes: list[FakeParsedResponse | BaseException]
    calls: list[dict[str, object]] = field(default_factory=list)
    next_outcome_index: int = 0

    def parse(self, **kwargs: object) -> FakeParsedResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes[self.next_outcome_index]
        self.next_outcome_index += 1

        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class FakeOpenAIClient:
    outcomes: list[FakeParsedResponse | BaseException]

    def __post_init__(self) -> None:
        self.responses = FakeResponses(self.outcomes)


def valid_analysis() -> TextAnalysis:
    return TextAnalysis(
        topic="착석 알림",
        summary="장시간 착석을 감지해 진동으로 알려 주는 시스템이다.",
        sentiment=Sentiment.NEUTRAL,
        keywords=["착석", "진동", "알림"],
        requires_review=False,
        review_reason=None,
    )


def fake_usage(
    *,
    input_tokens: int = 8,
    cached_input_tokens: int = 2,
    output_tokens: int = 12,
    reasoning_tokens: int = 3,
) -> FakeUsage:
    return FakeUsage(
        input_tokens=input_tokens,
        input_tokens_details=FakeInputTokenDetails(cached_tokens=cached_input_tokens),
        output_tokens=output_tokens,
        output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=reasoning_tokens),
        total_tokens=input_tokens + output_tokens,
    )


def token_usage(
    *,
    input_tokens: int = 8,
    cached_input_tokens: int = 2,
    output_tokens: int = 12,
    reasoning_tokens: int = 3,
) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def make_response(
    *,
    output_parsed: object = DEFAULT_OUTPUT,
    status: str = "completed",
    response_id: str = "resp_structured",
    request_id: str | None = "req_structured",
    usage: FakeUsage | None = None,
    output: list[object] | None = None,
) -> FakeParsedResponse:
    parsed = valid_analysis() if output_parsed is DEFAULT_OUTPUT else output_parsed
    return FakeParsedResponse(
        output_parsed=parsed,
        status=status,
        id=response_id,
        _request_id=request_id,
        usage=usage,
        output=[] if output is None else output,
    )


def make_client(
    *,
    output_parsed: object = DEFAULT_OUTPUT,
    status: str = "completed",
    request_id: str | None = "req_structured",
    usage: FakeUsage | None = None,
    output: list[object] | None = None,
    outcomes: list[FakeParsedResponse | BaseException] | None = None,
) -> FakeOpenAIClient:
    if outcomes is not None:
        return FakeOpenAIClient(outcomes)

    response = make_response(
        output_parsed=output_parsed,
        status=status,
        request_id=request_id,
        usage=usage,
        output=output,
    )
    return FakeOpenAIClient([response])


def make_validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis.model_validate(
            {
                "topic": "",
                "summary": "요약",
                "sentiment": "neutral",
                "keywords": ["착석"],
                "requires_review": False,
                "review_reason": None,
            }
        )
    return exc_info.value


def make_api_connection_error() -> openai.APIConnectionError:
    request = httpx.Request("POST", "https://example.test/responses")
    return openai.APIConnectionError(message="connection failed", request=request)


def set_perf_counter(monkeypatch: pytest.MonkeyPatch, values: list[float]) -> None:
    perf_values = iter(values)
    monkeypatch.setattr(service.time, "perf_counter", lambda: next(perf_values))


def test_combine_token_usage_returns_none_when_all_missing() -> None:
    assert service.combine_token_usage((None, None)) is None


def test_combine_token_usage_returns_single_usage_values() -> None:
    usage = token_usage()

    assert service.combine_token_usage((usage,)) == usage


def test_combine_token_usage_sums_two_usages() -> None:
    first = token_usage(
        input_tokens=2,
        cached_input_tokens=1,
        output_tokens=3,
        reasoning_tokens=1,
    )
    second = token_usage(
        input_tokens=5,
        cached_input_tokens=2,
        output_tokens=7,
        reasoning_tokens=3,
    )

    assert service.combine_token_usage((first, second)) == TokenUsage(
        input_tokens=7,
        cached_input_tokens=3,
        output_tokens=10,
        reasoning_tokens=4,
        total_tokens=17,
    )


def test_combine_token_usage_ignores_missing_values() -> None:
    usage = token_usage()

    assert service.combine_token_usage((None, usage, None)) == usage


def test_combine_token_usage_does_not_modify_original_usage() -> None:
    usage = token_usage()

    service.combine_token_usage((usage, usage))

    assert usage == token_usage()


def test_analyze_text_returns_text_analysis_object() -> None:
    result = service.analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert isinstance(result.analysis, TextAnalysis)
    assert result.analysis.topic == "착석 알림"
    assert result.analysis.sentiment is Sentiment.NEUTRAL
    assert result.analysis.review_reason is None


def test_analyze_text_returns_response_and_request_ids() -> None:
    result = service.analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.response_id == "resp_structured"
    assert result.request_id == "req_structured"


def test_analyze_text_converts_usage() -> None:
    result = service.analyze_text(
        make_client(usage=fake_usage()),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.usage == token_usage()


def test_analyze_text_records_non_negative_elapsed_seconds() -> None:
    result = service.analyze_text(
        make_client(),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.elapsed_seconds >= 0


def test_analyze_text_calls_parse_once_with_expected_arguments() -> None:
    client = make_client()

    service.analyze_text(
        client,
        model="test-model",
        user_input="  착석 감지 시스템  ",
    )

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["input"] == "착석 감지 시스템"
    assert call["text_format"] is TextAnalysis
    assert isinstance(call["instructions"], str)
    assert call["instructions"]


def test_analyze_text_rejects_empty_input_without_api_call() -> None:
    client = make_client()

    with pytest.raises(ValueError, match="user_input"):
        service.analyze_text(client, model="test-model", user_input="   ")

    assert client.responses.calls == []


def test_analyze_text_rejects_incomplete_status() -> None:
    client = make_client(status="incomplete")

    with pytest.raises(StructuredResponseIncompleteError, match="incomplete"):
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_other_non_completed_status() -> None:
    client = make_client(status="failed")

    with pytest.raises(StructuredResponseStatusError, match="not completed"):
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_missing_output_parsed() -> None:
    client = make_client(output_parsed=None)

    with pytest.raises(StructuredResponseParseError, match="response was empty"):
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_rejects_output_parsed_with_wrong_type() -> None:
    client = make_client(output_parsed={"topic": "착석"})

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_allows_missing_usage() -> None:
    result = service.analyze_text(
        make_client(usage=None),
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert result.usage is None


def test_analyze_text_rejects_refusal_response() -> None:
    refusal_output = [FakeOutputMessage(content=[FakeRefusalContent("hidden")])]
    client = make_client(output=refusal_output)

    with pytest.raises(StructuredResponseRefusalError, match="refused"):
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")


def test_analyze_text_converts_validation_error_and_calls_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation_error = make_validation_error()
    client = make_client(outcomes=[validation_error])
    set_perf_counter(monkeypatch, [1.0, 1.25])

    with pytest.raises(
        StructuredResponseValidationError,
        match="schema validation",
    ) as exc_info:
        service.analyze_text(client, model="test-model", user_input="착석 감지 시스템")

    assert len(client.responses.calls) == 1
    assert exc_info.value.__cause__ is validation_error
    assert exc_info.value.elapsed_seconds == 0.25
    assert exc_info.value.attempts == 1


def test_analyze_text_with_correction_first_success_returns_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage())
    set_perf_counter(monkeypatch, [10.0, 10.5])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert isinstance(execution, StructuredAnalysisExecution)
    assert execution.result.analysis == valid_analysis()
    assert execution.attempts == 1
    assert execution.correction_attempted is False
    assert execution.total_usage == token_usage()
    assert execution.total_elapsed_seconds == 0.5
    assert execution.response_ids == ("resp_structured",)
    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_succeeds_after_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(
        outcomes=[
            make_validation_error(),
            make_response(response_id="resp_corrected", usage=fake_usage()),
        ]
    )
    set_perf_counter(monkeypatch, [1.0, 1.25, 2.0, 2.5])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    assert execution.result.analysis == valid_analysis()
    assert execution.attempts == 2
    assert execution.correction_attempted is True
    assert execution.total_elapsed_seconds == 0.75
    assert execution.total_usage == token_usage()
    assert execution.response_ids == ("resp_corrected",)
    assert len(client.responses.calls) == 2


def test_correction_request_instructions_include_stable_rules() -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])

    service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    second_instructions = client.responses.calls[1]["instructions"]
    assert isinstance(second_instructions, str)
    assert "교정 요청" in second_instructions
    assert "모든 필드" in second_instructions
    assert "추가 필드" in second_instructions
    assert "topic과 summary" in second_instructions
    assert "keywords는 1개 이상 5개 이하" in second_instructions
    assert "대소문자를 무시해 중복" in second_instructions
    assert "review_reason" in second_instructions


def test_correction_request_does_not_include_full_validation_error() -> None:
    validation_error = make_validation_error()
    client = make_client(outcomes=[validation_error, make_response()])

    service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
    )

    second_instructions = client.responses.calls[1]["instructions"]
    assert isinstance(second_instructions, str)
    assert str(validation_error) not in second_instructions


def test_analyze_text_with_correction_reraises_second_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(outcomes=[make_validation_error(), make_validation_error()])
    set_perf_counter(monkeypatch, [1.0, 1.25, 2.0, 2.5])

    with pytest.raises(
        StructuredResponseValidationError,
        match="after correction",
    ) as exc_info:
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert exc_info.value.attempts == 2
    assert exc_info.value.elapsed_seconds == 0.75
    assert isinstance(exc_info.value.__cause__, StructuredResponseValidationError)
    assert len(client.responses.calls) == 2


def test_analyze_text_with_correction_does_not_retry_refusal() -> None:
    refusal_output = [FakeOutputMessage(content=[FakeRefusalContent("hidden")])]
    client = make_client(output=refusal_output)

    with pytest.raises(StructuredResponseRefusalError, match="refused"):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_incomplete() -> None:
    client = make_client(status="incomplete")

    with pytest.raises(StructuredResponseIncompleteError, match="incomplete"):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_parse_error() -> None:
    client = make_client(output_parsed=None)

    with pytest.raises(StructuredResponseParseError, match="response was empty"):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_does_not_retry_api_connection_error() -> None:
    client = make_client(outcomes=[make_api_connection_error()])

    with pytest.raises(openai.APIConnectionError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
        )

    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_without_budget_keeps_success_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage())
    set_perf_counter(monkeypatch, [1.0, 1.5])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
        budget=None,
    )

    assert execution.attempts == 1
    assert execution.correction_attempted is False
    assert execution.total_usage == token_usage()
    assert execution.total_elapsed_seconds == 0.5
    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_budget_allows_first_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage())
    set_perf_counter(monkeypatch, [1.0, 1.25])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
        budget=ExecutionBudget(
            max_attempts=2,
            max_recorded_tokens=100,
            max_elapsed_seconds=1.0,
        ),
    )

    assert execution.attempts == 1
    assert execution.total_usage == token_usage()
    assert execution.total_elapsed_seconds == 0.25
    assert len(client.responses.calls) == 1


def test_analyze_text_with_correction_budget_allows_max_attempts_one_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage())
    set_perf_counter(monkeypatch, [1.0, 1.25])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=100,
            max_elapsed_seconds=1.0,
        ),
    )

    assert execution.attempts == 1
    assert len(client.responses.calls) == 1


def test_budget_blocks_correction_after_validation_when_attempt_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])
    set_perf_counter(monkeypatch, [1.0, 1.25])

    with pytest.raises(AttemptBudgetExceededError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
            budget=ExecutionBudget(
                max_attempts=1,
                max_recorded_tokens=100,
                max_elapsed_seconds=1.0,
            ),
        )

    assert len(client.responses.calls) == 1


def test_budget_rejects_success_when_recorded_tokens_exceed_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage(input_tokens=6, output_tokens=5))
    set_perf_counter(monkeypatch, [1.0, 1.25])

    with pytest.raises(TokenBudgetExceededError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
        )

    assert len(client.responses.calls) == 1


def test_budget_rejects_success_when_elapsed_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(usage=fake_usage())
    set_perf_counter(monkeypatch, [1.0, 1.6])

    with pytest.raises(TimeBudgetExceededError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=100,
                max_elapsed_seconds=0.5,
            ),
        )

    assert len(client.responses.calls) == 1


def test_budget_blocks_correction_when_validation_elapsed_reaches_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])
    set_perf_counter(monkeypatch, [1.0, 1.5])

    with pytest.raises(TimeBudgetExceededError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=100,
                max_elapsed_seconds=0.5,
            ),
        )

    assert len(client.responses.calls) == 1


def test_budget_allows_validation_failure_then_correction_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(
        outcomes=[
            make_validation_error(),
            make_response(response_id="resp_corrected", usage=fake_usage()),
        ]
    )
    set_perf_counter(monkeypatch, [1.0, 1.25, 2.0, 2.5])

    execution = service.analyze_text_with_correction(
        client,
        model="test-model",
        user_input="착석 감지 시스템",
        budget=ExecutionBudget(
            max_attempts=2,
            max_recorded_tokens=100,
            max_elapsed_seconds=1.0,
        ),
    )

    assert execution.attempts == 2
    assert execution.correction_attempted is True
    assert execution.total_elapsed_seconds == 0.75
    assert execution.total_usage == token_usage()
    assert execution.response_ids == ("resp_corrected",)
    assert len(client.responses.calls) == 2


def test_budget_exceeded_after_validation_prevents_extra_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(outcomes=[make_validation_error(), make_response()])
    set_perf_counter(monkeypatch, [1.0, 1.25])

    with pytest.raises(AttemptBudgetExceededError):
        service.analyze_text_with_correction(
            client,
            model="test-model",
            user_input="착석 감지 시스템",
            budget=ExecutionBudget(
                max_attempts=1,
                max_recorded_tokens=100,
                max_elapsed_seconds=1.0,
            ),
        )

    assert len(client.responses.calls) == 1
