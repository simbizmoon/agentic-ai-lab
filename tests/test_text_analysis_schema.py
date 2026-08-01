from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.text_analysis import Sentiment, TextAnalysis


def valid_analysis_data() -> dict[str, object]:
    return {
        "topic": "Agent 설계",
        "summary": "Agent와 Workflow의 차이를 요약했다.",
        "sentiment": "neutral",
        "keywords": ["Agent", "Workflow"],
        "requires_review": False,
        "review_reason": None,
    }


def error_locations(exc: ValidationError) -> set[tuple[str, ...]]:
    return {tuple(str(part) for part in error["loc"]) for error in exc.errors()}


def resolve_schema_ref(schema: dict[str, object], ref: str) -> dict[str, object]:
    current: object = schema
    for part in ref.removeprefix("#/").split("/"):
        assert isinstance(current, dict)
        current = current[part]
    assert isinstance(current, dict)
    return current


def sentiment_property_schema(schema: dict[str, object]) -> dict[str, object]:
    properties = schema["properties"]
    assert isinstance(properties, dict)
    sentiment_schema = properties["sentiment"]
    assert isinstance(sentiment_schema, dict)

    if "$ref" in sentiment_schema:
        ref = sentiment_schema["$ref"]
        assert isinstance(ref, str)
        return resolve_schema_ref(schema, ref)

    all_of = sentiment_schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            if isinstance(item, dict) and isinstance(item.get("$ref"), str):
                return resolve_schema_ref(schema, item["$ref"])

    return sentiment_schema


def schema_types(schema_fragment: dict[str, object]) -> set[str]:
    types: set[str] = set()
    schema_type = schema_fragment.get("type")
    if isinstance(schema_type, str):
        types.add(schema_type)

    for key in ("anyOf", "oneOf", "allOf"):
        nested = schema_fragment.get(key)
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    types.update(schema_types(item))

    return types


def test_text_analysis_accepts_valid_input() -> None:
    analysis = TextAnalysis(**valid_analysis_data())

    assert analysis.topic == "Agent 설계"
    assert analysis.summary == "Agent와 Workflow의 차이를 요약했다."
    assert analysis.sentiment is Sentiment.NEUTRAL
    assert analysis.keywords == ["Agent", "Workflow"]
    assert analysis.requires_review is False
    assert analysis.review_reason is None


def test_text_analysis_converts_neutral_string_to_enum() -> None:
    analysis = TextAnalysis(**valid_analysis_data())

    assert analysis.sentiment is Sentiment.NEUTRAL


def test_text_analysis_rejects_unknown_sentiment() -> None:
    data = valid_analysis_data()
    data["sentiment"] = "good"

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("sentiment",) in error_locations(exc_info.value)


def test_text_analysis_rejects_empty_topic() -> None:
    data = valid_analysis_data()
    data["topic"] = ""

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("topic",) in error_locations(exc_info.value)


def test_text_analysis_trims_topic_whitespace() -> None:
    data = valid_analysis_data()
    data["topic"] = "  Agent 설계  "

    analysis = TextAnalysis(**data)

    assert analysis.topic == "Agent 설계"


def test_text_analysis_rejects_whitespace_only_topic() -> None:
    data = valid_analysis_data()
    data["topic"] = "   "

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("topic",) in error_locations(exc_info.value)


def test_text_analysis_rejects_topic_longer_than_100_characters() -> None:
    data = valid_analysis_data()
    data["topic"] = "a" * 101

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("topic",) in error_locations(exc_info.value)


def test_text_analysis_rejects_empty_summary() -> None:
    data = valid_analysis_data()
    data["summary"] = ""

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("summary",) in error_locations(exc_info.value)


def test_text_analysis_trims_summary_whitespace() -> None:
    data = valid_analysis_data()
    data["summary"] = "  Agent와 Workflow의 차이를 요약했다.  "

    analysis = TextAnalysis(**data)

    assert analysis.summary == "Agent와 Workflow의 차이를 요약했다."


def test_text_analysis_rejects_whitespace_only_summary() -> None:
    data = valid_analysis_data()
    data["summary"] = "   "

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("summary",) in error_locations(exc_info.value)


def test_text_analysis_rejects_empty_keywords() -> None:
    data = valid_analysis_data()
    data["keywords"] = []

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_more_than_five_keywords() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["one", "two", "three", "four", "five", "six"]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_empty_keyword() -> None:
    data = valid_analysis_data()
    data["keywords"] = [""]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert exc_info.value.errors()[0]["loc"] == ("keywords", 0)


def test_text_analysis_trims_keyword_whitespace() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["  Agent  ", "  Workflow  "]

    analysis = TextAnalysis(**data)

    assert analysis.keywords == ["Agent", "Workflow"]


def test_text_analysis_rejects_whitespace_only_keyword() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["   "]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_duplicate_keywords() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["AI", "AI"]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_case_insensitive_duplicate_keywords() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["AI", "ai"]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_whitespace_normalized_duplicate_keywords() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["AI", " ai "]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("keywords",) in error_locations(exc_info.value)


def test_text_analysis_rejects_keyword_longer_than_50_characters() -> None:
    data = valid_analysis_data()
    data["keywords"] = ["a" * 51]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert exc_info.value.errors()[0]["loc"] == ("keywords", 0)


def test_text_analysis_rejects_missing_requires_review() -> None:
    data = valid_analysis_data()
    del data["requires_review"]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("requires_review",) in error_locations(exc_info.value)


def test_text_analysis_rejects_string_requires_review() -> None:
    data = valid_analysis_data()
    data["requires_review"] = "false"

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("requires_review",) in error_locations(exc_info.value)


def test_text_analysis_rejects_integer_requires_review() -> None:
    data = valid_analysis_data()
    data["requires_review"] = 0

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("requires_review",) in error_locations(exc_info.value)


def test_text_analysis_accepts_false_requires_review() -> None:
    data = valid_analysis_data()
    data["requires_review"] = False

    analysis = TextAnalysis(**data)

    assert analysis.requires_review is False


def test_text_analysis_accepts_true_requires_review() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "사용자 안전 검토가 필요하다."

    analysis = TextAnalysis(**data)

    assert analysis.requires_review is True


def test_text_analysis_allows_false_requires_review_with_no_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = False
    data["review_reason"] = None

    analysis = TextAnalysis(**data)

    assert analysis.requires_review is False
    assert analysis.review_reason is None


def test_text_analysis_allows_true_requires_review_with_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "안전 관련 판단이 필요하다."

    analysis = TextAnalysis(**data)

    assert analysis.requires_review is True
    assert analysis.review_reason == "안전 관련 판단이 필요하다."


def test_text_analysis_rejects_true_requires_review_without_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = None

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert exc_info.value.errors()[0]["loc"] == ()


def test_text_analysis_rejects_true_requires_review_with_empty_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = ""

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("review_reason",) in error_locations(exc_info.value)


def test_text_analysis_rejects_true_requires_review_with_whitespace_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "   "

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("review_reason",) in error_locations(exc_info.value)


def test_text_analysis_rejects_false_requires_review_with_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = False
    data["review_reason"] = "검토 사유가 없어야 한다."

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert exc_info.value.errors()[0]["loc"] == ()


def test_text_analysis_trims_review_reason_whitespace() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "  안전성 검토 필요  "

    analysis = TextAnalysis(**data)

    assert analysis.review_reason == "안전성 검토 필요"


def test_text_analysis_rejects_review_reason_longer_than_300_characters() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "a" * 301

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("review_reason",) in error_locations(exc_info.value)


def test_text_analysis_rejects_missing_review_reason() -> None:
    data = valid_analysis_data()
    del data["review_reason"]

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("review_reason",) in error_locations(exc_info.value)


def test_text_analysis_model_dump_json_mode_includes_none_review_reason() -> None:
    analysis = TextAnalysis(**valid_analysis_data())

    dumped = analysis.model_dump(mode="json")

    assert "review_reason" in dumped
    assert dumped["review_reason"] is None


def test_text_analysis_model_dump_json_mode_includes_string_review_reason() -> None:
    data = valid_analysis_data()
    data["requires_review"] = True
    data["review_reason"] = "안전성 검토 필요"
    analysis = TextAnalysis(**data)

    dumped = analysis.model_dump(mode="json")

    assert dumped["review_reason"] == "안전성 검토 필요"


def test_text_analysis_rejects_extra_field() -> None:
    data = valid_analysis_data()
    data["extra_field"] = "not allowed"

    with pytest.raises(ValidationError) as exc_info:
        TextAnalysis(**data)

    assert ("extra_field",) in error_locations(exc_info.value)


def test_text_analysis_model_dump_json_mode_uses_enum_value() -> None:
    analysis = TextAnalysis(**valid_analysis_data())

    dumped = analysis.model_dump(mode="json")

    assert dumped["sentiment"] == "neutral"


def test_text_analysis_json_schema_contains_core_structure() -> None:
    schema = TextAnalysis.model_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "topic",
        "summary",
        "sentiment",
        "keywords",
        "requires_review",
        "review_reason",
    }

    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == {
        "topic",
        "summary",
        "sentiment",
        "keywords",
        "requires_review",
        "review_reason",
    }

    sentiment_schema = sentiment_property_schema(schema)
    assert set(sentiment_schema["enum"]) == {"positive", "neutral", "negative"}
    requires_review_schema = properties["requires_review"]
    assert isinstance(requires_review_schema, dict)
    assert requires_review_schema["type"] == "boolean"
    review_reason_schema = properties["review_reason"]
    assert isinstance(review_reason_schema, dict)
    assert {"string", "null"}.issubset(schema_types(review_reason_schema))
