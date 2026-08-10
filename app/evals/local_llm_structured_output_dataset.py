"""Structured-output benchmark cases for local LLM evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class StructuredOutputMode(StrEnum):
    """Constraint mode used for one structured-output run."""

    PROMPT_ONLY = "prompt_only"
    JSON = "json"
    JSON_SCHEMA = "json_schema"


class CityTemperature(BaseModel):
    """Strict city-temperature output."""

    model_config = ConfigDict(extra="forbid", strict=True)

    city: str
    temperature: int


class ServiceStatus(BaseModel):
    """Strict service-status output."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: str
    retry_count: int
    owner: str


class SeatSchedule(BaseModel):
    """Strict nested seat-behavior schedule output."""

    model_config = ConfigDict(extra="forbid", strict=True)

    focus_minutes: int
    rest_minutes: int
    alerts: list[str]


type StructuredModel = type[BaseModel]


@dataclass(frozen=True)
class StructuredOutputCase:
    """One structured extraction case."""

    case_id: str
    prompt: str
    schema: StructuredModel
    expected: dict[str, Any]


@dataclass(frozen=True)
class StructuredOutputScore:
    """Deterministic structured-output score."""

    json_parse_passed: bool
    schema_passed: bool
    exact_value_passed: bool
    failure: str | None


def structured_output_cases() -> tuple[StructuredOutputCase, ...]:
    """Return the fixed Phase 5B-2 dataset."""
    return (
        StructuredOutputCase(
            case_id="city-temp-001",
            prompt=(
                "다음 정보에서 값을 추출해 JSON object 하나만 반환하라.\n"
                "도시: 서울\n"
                "온도: 24\n"
                "필드 이름과 타입:\n"
                '- "city": string\n'
                '- "temperature": integer\n'
                "추가 필드는 허용하지 않는다."
            ),
            schema=CityTemperature,
            expected={"city": "서울", "temperature": 24},
        ),
        StructuredOutputCase(
            case_id="service-status-001",
            prompt=(
                "다음 기록을 JSON object로 구조화하라.\n"
                "상태=정상, 재시도=0, 담당자=민수\n"
                "필드 이름과 타입:\n"
                '- "status": string\n'
                '- "retry_count": integer\n'
                '- "owner": string\n'
                "JSON 외의 설명을 추가하지 마라."
            ),
            schema=ServiceStatus,
            expected={
                "status": "정상",
                "retry_count": 0,
                "owner": "민수",
            },
        ),
        StructuredOutputCase(
            case_id="seat-schedule-001",
            prompt=(
                "착석 행동관리 설정을 JSON object로 반환하라.\n"
                "집중시간 45분, 휴식시간 5분, "
                "알림 방식은 진동과 LED이다.\n"
                "필드 이름과 타입:\n"
                '- "focus_minutes": integer\n'
                '- "rest_minutes": integer\n'
                '- "alerts": array[string]\n'
                'alerts 값은 ["진동", "LED"] 순서로 반환하라.'
            ),
            schema=SeatSchedule,
            expected={
                "focus_minutes": 45,
                "rest_minutes": 5,
                "alerts": ["진동", "LED"],
            },
        ),
    )


def response_format_for(
    case: StructuredOutputCase,
    mode: StructuredOutputMode,
) -> str | dict[str, Any] | None:
    """Return Ollama response format for one mode."""
    if mode is StructuredOutputMode.PROMPT_ONLY:
        return None
    if mode is StructuredOutputMode.JSON:
        return "json"
    return case.schema.model_json_schema()


def evaluate_structured_output(
    case: StructuredOutputCase,
    response: str,
) -> StructuredOutputScore:
    """Parse, validate, and compare one full response."""
    try:
        parsed_json = json.loads(response)
    except json.JSONDecodeError as error:
        return StructuredOutputScore(
            json_parse_passed=False,
            schema_passed=False,
            exact_value_passed=False,
            failure=f"json_parse_error: {error.msg}",
        )

    try:
        validated = case.schema.model_validate(parsed_json)
    except ValidationError as error:
        return StructuredOutputScore(
            json_parse_passed=True,
            schema_passed=False,
            exact_value_passed=False,
            failure=f"schema_validation_error: {error.errors()}",
        )

    actual = validated.model_dump(mode="python")
    exact = actual == case.expected
    return StructuredOutputScore(
        json_parse_passed=True,
        schema_passed=True,
        exact_value_passed=exact,
        failure=None if exact else f"value_mismatch: {actual!r}",
    )
