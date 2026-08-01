from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.recovery import RecoveryAction, RecoveryDecision
from app.schemas.text_analysis import Sentiment, TextAnalysis
from app.services.structured_analysis import StructuredAnalysisResult
from app.services.text_generation import TokenUsage
from scripts import analyze_text as script

SECRET_TEXT = "sk-test-secret-value"
USER_INPUT_TEXT = script.ANALYSIS_INPUT


@dataclass(frozen=True)
class FakeSettings:
    openai_model: str = "test-model"


@dataclass
class FakeClient:
    closed: bool = False

    def close(self) -> None:
        self.closed = True


def make_success_result() -> StructuredAnalysisResult:
    return StructuredAnalysisResult(
        analysis=TextAnalysis(
            topic="착석 알림",
            summary="장시간 착석을 감지해 사용자에게 진동으로 알린다.",
            sentiment=Sentiment.NEUTRAL,
            keywords=["착석", "진동"],
            requires_review=False,
            review_reason=None,
        ),
        response_id="resp_test",
        request_id="req_test",
        usage=TokenUsage(
            input_tokens=10,
            cached_input_tokens=1,
            output_tokens=20,
            reasoning_tokens=2,
            total_tokens=30,
        ),
        elapsed_seconds=0.1234,
    )


def configure_common_dependencies(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    fake_client = FakeClient()

    monkeypatch.setattr(script, "load_settings", lambda: FakeSettings())
    monkeypatch.setattr(script, "create_openai_client", lambda settings: fake_client)

    return fake_client


@pytest.mark.parametrize(
    ("action", "expected_code"),
    [
        (RecoveryAction.MODIFY_REQUEST, 1),
        (RecoveryAction.RETRY_LATER, 2),
        (RecoveryAction.FIX_CONFIGURATION, 3),
        (RecoveryAction.HUMAN_REVIEW, 4),
        (RecoveryAction.ABORT, 5),
    ],
)
def test_exit_code_for_recovery_maps_actions(
    action: RecoveryAction,
    expected_code: int,
) -> None:
    decision = RecoveryDecision(
        retryable=False,
        action=action,
        reason="stable reason",
    )

    assert script.exit_code_for_recovery(decision) == expected_code


def test_print_recovery_decision_outputs_expected_format(capsys: pytest.CaptureFixture[str]) -> None:
    decision = RecoveryDecision(
        retryable=True,
        action=RecoveryAction.RETRY_LATER,
        reason="Retry later safely.",
    )

    script.print_recovery_decision(decision)

    assert capsys.readouterr().out == (
        "[ERROR] Structured analysis failed\n"
        "Action: retry_later\n"
        "Retryable: true\n"
        "Reason: Retry later safely.\n"
    )


def test_print_recovery_decision_outputs_retryable_true(capsys: pytest.CaptureFixture[str]) -> None:
    decision = RecoveryDecision(
        retryable=True,
        action=RecoveryAction.RETRY_LATER,
        reason="Retry later safely.",
    )

    script.print_recovery_decision(decision)

    assert "Retryable: true" in capsys.readouterr().out


def test_print_recovery_decision_outputs_retryable_false(capsys: pytest.CaptureFixture[str]) -> None:
    decision = RecoveryDecision(
        retryable=False,
        action=RecoveryAction.ABORT,
        reason="Abort safely.",
    )

    script.print_recovery_decision(decision)

    assert "Retryable: false" in capsys.readouterr().out


def test_main_returns_zero_and_closes_client_on_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_client = configure_common_dependencies(monkeypatch)

    def fake_analyze_text(
        client: FakeClient,
        *,
        model: str,
        user_input: str,
    ) -> StructuredAnalysisResult:
        assert client is fake_client
        assert model == "test-model"
        assert user_input == USER_INPUT_TEXT
        return make_success_result()

    monkeypatch.setattr(script, "analyze_text", fake_analyze_text)

    exit_code = script.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert fake_client.closed is True
    assert "[OK] Structured analysis received" in output


@pytest.mark.parametrize(
    ("action", "retryable", "expected_code"),
    [
        (RecoveryAction.MODIFY_REQUEST, False, 1),
        (RecoveryAction.RETRY_LATER, True, 2),
        (RecoveryAction.FIX_CONFIGURATION, False, 3),
        (RecoveryAction.HUMAN_REVIEW, False, 4),
        (RecoveryAction.ABORT, False, 5),
    ],
)
def test_main_returns_exit_code_for_recovery_action_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    action: RecoveryAction,
    retryable: bool,
    expected_code: int,
) -> None:
    fake_client = configure_common_dependencies(monkeypatch)
    reason = "Policy selected a safe recovery action."

    def fake_analyze_text(
        client: FakeClient,
        *,
        model: str,
        user_input: str,
    ) -> StructuredAnalysisResult:
        raise ValueError(f"{SECRET_TEXT} {user_input}")

    def fake_decide_recovery(error: BaseException) -> RecoveryDecision:
        assert isinstance(error, ValueError)
        return RecoveryDecision(retryable=retryable, action=action, reason=reason)

    monkeypatch.setattr(script, "analyze_text", fake_analyze_text)
    monkeypatch.setattr(script, "decide_recovery", fake_decide_recovery)

    exit_code = script.main()
    output = capsys.readouterr().out

    assert exit_code == expected_code
    assert fake_client.closed is True
    assert "[ERROR] Structured analysis failed" in output
    assert f"Action: {action.value}" in output
    assert f"Retryable: {str(retryable).lower()}" in output
    assert f"Reason: {reason}" in output
    assert SECRET_TEXT not in output
    assert USER_INPUT_TEXT not in output


def test_main_success_keeps_analysis_output_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_common_dependencies(monkeypatch)
    monkeypatch.setattr(script, "analyze_text", lambda *args, **kwargs: make_success_result())

    exit_code = script.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Analysis:" in output
    assert "  Topic: 착석 알림" in output
    assert "  Summary: 장시간 착석을 감지해 사용자에게 진동으로 알린다." in output
    assert "  Sentiment: neutral" in output
    assert "  Keywords:" in output
    assert "    - 착석" in output
    assert "    - 진동" in output
    assert "  Requires Review: false" in output
    assert "  Review Reason: unavailable" in output
