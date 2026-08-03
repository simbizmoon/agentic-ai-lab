from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.schemas.document_analysis import (
    DocumentAnalysis,
    DocumentFinding,
    FindingSeverity,
)
from app.services import document_analysis as service


@dataclass(frozen=True)
class FakeRefusalContent:
    refusal: str


@dataclass(frozen=True)
class FakeOutputMessage:
    content: list[object]


@dataclass(frozen=True)
class FakeResponse:
    output_parsed: object | None
    status: str = "completed"
    id: str = "resp_document"
    _request_id: str | None = "req_document"
    usage: object | None = None
    output: list[object] = field(default_factory=list)


@dataclass
class FakeResponses:
    outcome: FakeResponse | BaseException
    calls: list[dict[str, object]] = field(default_factory=list)

    def parse(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


@dataclass
class FakeClient:
    outcome: FakeResponse | BaseException

    def __post_init__(self) -> None:
        self.responses = FakeResponses(self.outcome)


def valid_analysis() -> DocumentAnalysis:
    return DocumentAnalysis(
        summary="문서의 핵심 내용과 위험 요소를 분석했다.",
        key_findings=[
            DocumentFinding(
                title="책임 범위가 불명확함",
                evidence="책임 주체와 범위를 정하는 문구가 없다.",
                severity=FindingSeverity.HIGH,
            ),
        ],
        recommended_actions=[
            "책임 주체와 범위를 문서에 명시한다.",
        ],
        needs_human_review=True,
    )


def make_response(
    *,
    output_parsed: object | None = None,
    status: str = "completed",
    output: list[object] | None = None,
) -> FakeResponse:
    return FakeResponse(
        output_parsed=(
            valid_analysis()
            if output_parsed is None
            else output_parsed
        ),
        status=status,
        output=[] if output is None else output,
    )


def make_validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        DocumentAnalysis.model_validate(
            {
                "summary": "",
                "key_findings": [],
                "recommended_actions": [],
                "needs_human_review": False,
            }
        )
    return exc_info.value


def test_analyze_document_returns_validated_result() -> None:
    client = FakeClient(make_response())

    result = service.analyze_document(
        client,
        model="test-model",
        document_text="검토할 문서",
    )

    assert isinstance(result.analysis, DocumentAnalysis)
    assert result.analysis.key_findings[0].severity is FindingSeverity.HIGH
    assert result.response_id == "resp_document"
    assert result.request_id == "req_document"


def test_analyze_document_passes_schema_to_responses_api() -> None:
    client = FakeClient(make_response())

    service.analyze_document(
        client,
        model="test-model",
        document_text="  검토할 문서  ",
    )

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["input"] == "검토할 문서"
    assert call["text_format"] is DocumentAnalysis
    assert isinstance(call["instructions"], str)
    assert call["instructions"]


def test_analyze_document_rejects_empty_input_without_api_call() -> None:
    client = FakeClient(make_response())

    with pytest.raises(ValueError, match="document_text"):
        service.analyze_document(
            client,
            model="test-model",
            document_text="   ",
        )

    assert client.responses.calls == []


def test_analyze_document_wraps_schema_validation_error() -> None:
    client = FakeClient(make_validation_error())

    with pytest.raises(
        StructuredResponseValidationError,
        match="schema validation",
    ) as exc_info:
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )

    assert exc_info.value.attempts == 1


def test_analyze_document_rejects_incomplete_response() -> None:
    client = FakeClient(make_response(status="incomplete"))

    with pytest.raises(StructuredResponseIncompleteError):
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )


def test_analyze_document_rejects_non_completed_response() -> None:
    client = FakeClient(make_response(status="failed"))

    with pytest.raises(StructuredResponseStatusError):
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )


def test_analyze_document_rejects_refusal() -> None:
    client = FakeClient(
        make_response(
            output=[
                FakeOutputMessage(
                    content=[
                        FakeRefusalContent(
                            refusal="cannot comply",
                        ),
                    ],
                ),
            ],
        )
    )

    with pytest.raises(StructuredResponseRefusalError):
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )


def test_analyze_document_rejects_missing_parsed_output() -> None:
    client = FakeClient(
        FakeResponse(
            output_parsed=None,
        )
    )

    with pytest.raises(StructuredResponseParseError, match="empty"):
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )


def test_analyze_document_rejects_wrong_parsed_type() -> None:
    client = FakeClient(
        make_response(
            output_parsed={"summary": "not a model"},
        )
    )

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
        service.analyze_document(
            client,
            model="test-model",
            document_text="검토할 문서",
        )
