from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.document_analysis import (
    DocumentAnalysis,
    DocumentFinding,
    FindingSeverity,
)


def valid_analysis() -> DocumentAnalysis:
    return DocumentAnalysis(
        summary="문서의 핵심 내용과 주요 위험을 분석했다.",
        key_findings=[
            DocumentFinding(
                title="검토가 필요한 조건",
                evidence="문서에 책임 범위가 명확하지 않은 조항이 있다.",
                severity=FindingSeverity.HIGH,
            ),
        ],
        recommended_actions=[
            "책임 범위를 구체적으로 명시한다.",
        ],
        needs_human_review=True,
    )


def test_valid_document_analysis() -> None:
    analysis = valid_analysis()

    assert analysis.summary == "문서의 핵심 내용과 주요 위험을 분석했다."
    assert analysis.key_findings[0].severity is FindingSeverity.HIGH
    assert analysis.needs_human_review is True


def test_document_analysis_normalizes_text() -> None:
    analysis = DocumentAnalysis(
        summary="  문서 요약  ",
        key_findings=[
            {
                "title": "  핵심 발견  ",
                "evidence": "  구체적인 근거  ",
                "severity": "medium",
            },
        ],
        recommended_actions=["  추가 검토  "],
        needs_human_review=True,
    )

    assert analysis.summary == "문서 요약"
    assert analysis.key_findings[0].title == "핵심 발견"
    assert analysis.key_findings[0].evidence == "구체적인 근거"
    assert analysis.recommended_actions == ["추가 검토"]


def test_document_analysis_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        DocumentFinding(
            title="발견",
            evidence="근거",
            severity="critical",
        )


def test_document_analysis_requires_at_least_one_finding() -> None:
    with pytest.raises(ValidationError):
        DocumentAnalysis(
            summary="문서 요약",
            key_findings=[],
            recommended_actions=[],
            needs_human_review=False,
        )


def test_document_analysis_rejects_duplicate_actions() -> None:
    with pytest.raises(ValidationError):
        DocumentAnalysis(
            summary="문서 요약",
            key_findings=[
                {
                    "title": "발견",
                    "evidence": "근거",
                    "severity": "low",
                },
            ],
            recommended_actions=[
                "추가 검토",
                "추가 검토",
            ],
            needs_human_review=True,
        )


def test_document_analysis_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentAnalysis.model_validate(
            {
                "summary": "문서 요약",
                "key_findings": [
                    {
                        "title": "발견",
                        "evidence": "근거",
                        "severity": "low",
                    },
                ],
                "recommended_actions": [],
                "needs_human_review": False,
                "unexpected": "not allowed",
            },
        )


def test_document_analysis_requires_strict_boolean() -> None:
    with pytest.raises(ValidationError):
        DocumentAnalysis(
            summary="문서 요약",
            key_findings=[
                {
                    "title": "발견",
                    "evidence": "근거",
                    "severity": "low",
                },
            ],
            recommended_actions=[],
            needs_human_review="true",
        )
