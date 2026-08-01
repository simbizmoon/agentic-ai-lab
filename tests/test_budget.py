from dataclasses import FrozenInstanceError

import pytest

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    ensure_within_budget,
    record_attempt,
)
from app.exceptions import (
    AttemptBudgetExceededError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
)


def test_execution_budget_accepts_valid_values() -> None:
    budget = ExecutionBudget(
        max_attempts=1,
        max_recorded_tokens=1,
        max_elapsed_seconds=0.1,
    )

    assert budget.max_attempts == 1
    assert budget.max_recorded_tokens == 1
    assert budget.max_elapsed_seconds == 0.1


def test_execution_budget_rejects_zero_max_attempts() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        ExecutionBudget(max_attempts=0, max_recorded_tokens=1, max_elapsed_seconds=1.0)


def test_execution_budget_rejects_zero_max_recorded_tokens() -> None:
    with pytest.raises(ValueError, match="max_recorded_tokens"):
        ExecutionBudget(max_attempts=1, max_recorded_tokens=0, max_elapsed_seconds=1.0)


def test_execution_budget_rejects_zero_max_elapsed_seconds() -> None:
    with pytest.raises(ValueError, match="max_elapsed_seconds"):
        ExecutionBudget(max_attempts=1, max_recorded_tokens=1, max_elapsed_seconds=0)


def test_execution_budget_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        ExecutionBudget(max_attempts=-1, max_recorded_tokens=1, max_elapsed_seconds=1.0)
    with pytest.raises(ValueError):
        ExecutionBudget(max_attempts=1, max_recorded_tokens=-1, max_elapsed_seconds=1.0)
    with pytest.raises(ValueError):
        ExecutionBudget(max_attempts=1, max_recorded_tokens=1, max_elapsed_seconds=-1.0)


def test_execution_budget_is_frozen() -> None:
    budget = ExecutionBudget(
        max_attempts=1,
        max_recorded_tokens=1,
        max_elapsed_seconds=1.0,
    )

    with pytest.raises(FrozenInstanceError):
        budget.max_attempts = 2


def test_budget_usage_defaults_to_zero() -> None:
    usage = BudgetUsage()

    assert usage.attempts == 0
    assert usage.recorded_tokens == 0
    assert usage.elapsed_seconds == 0.0


def test_budget_usage_rejects_negative_attempts() -> None:
    with pytest.raises(ValueError, match="attempts"):
        BudgetUsage(attempts=-1)


def test_budget_usage_rejects_negative_recorded_tokens() -> None:
    with pytest.raises(ValueError, match="recorded_tokens"):
        BudgetUsage(recorded_tokens=-1)


def test_budget_usage_rejects_negative_elapsed_seconds() -> None:
    with pytest.raises(ValueError, match="elapsed_seconds"):
        BudgetUsage(elapsed_seconds=-0.1)


def test_budget_usage_is_frozen() -> None:
    usage = BudgetUsage()

    with pytest.raises(FrozenInstanceError):
        usage.attempts = 1


def test_ensure_can_start_attempt_allows_initial_usage() -> None:
    ensure_can_start_attempt(
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=1,
            max_elapsed_seconds=1.0,
        ),
        usage=BudgetUsage(),
    )


def test_ensure_can_start_attempt_rejects_attempts_at_maximum() -> None:
    with pytest.raises(AttemptBudgetExceededError):
        ensure_can_start_attempt(
            budget=ExecutionBudget(
                max_attempts=1,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(attempts=1),
        )


def test_ensure_can_start_attempt_rejects_tokens_at_maximum() -> None:
    with pytest.raises(TokenBudgetExceededError):
        ensure_can_start_attempt(
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(recorded_tokens=10),
        )


def test_ensure_can_start_attempt_rejects_elapsed_at_maximum() -> None:
    with pytest.raises(TimeBudgetExceededError):
        ensure_can_start_attempt(
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(elapsed_seconds=1.0),
        )


def test_record_attempt_increments_attempts() -> None:
    usage = record_attempt(
        usage=BudgetUsage(),
        recorded_tokens=0,
        elapsed_seconds=0.0,
    )

    assert usage.attempts == 1


def test_record_attempt_accumulates_tokens() -> None:
    usage = record_attempt(
        usage=BudgetUsage(recorded_tokens=2),
        recorded_tokens=3,
        elapsed_seconds=0.0,
    )

    assert usage.recorded_tokens == 5


def test_record_attempt_accumulates_elapsed_seconds() -> None:
    usage = record_attempt(
        usage=BudgetUsage(elapsed_seconds=0.25),
        recorded_tokens=0,
        elapsed_seconds=0.5,
    )

    assert usage.elapsed_seconds == 0.75


def test_record_attempt_does_not_modify_original_usage() -> None:
    original = BudgetUsage()

    record_attempt(usage=original, recorded_tokens=1, elapsed_seconds=0.1)

    assert original == BudgetUsage()


def test_record_attempt_rejects_negative_tokens() -> None:
    with pytest.raises(ValueError, match="recorded_tokens"):
        record_attempt(usage=BudgetUsage(), recorded_tokens=-1, elapsed_seconds=0.0)


def test_record_attempt_rejects_negative_elapsed_seconds() -> None:
    with pytest.raises(ValueError, match="elapsed_seconds"):
        record_attempt(usage=BudgetUsage(), recorded_tokens=0, elapsed_seconds=-0.1)


def test_ensure_within_budget_allows_values_equal_to_limit() -> None:
    ensure_within_budget(
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=10,
            max_elapsed_seconds=1.0,
        ),
        usage=BudgetUsage(attempts=1, recorded_tokens=10, elapsed_seconds=1.0),
    )


def test_ensure_within_budget_rejects_attempts_over_limit() -> None:
    with pytest.raises(AttemptBudgetExceededError):
        ensure_within_budget(
            budget=ExecutionBudget(
                max_attempts=1,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(attempts=2),
        )


def test_ensure_within_budget_rejects_tokens_over_limit() -> None:
    with pytest.raises(TokenBudgetExceededError):
        ensure_within_budget(
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(recorded_tokens=11),
        )


def test_ensure_within_budget_rejects_elapsed_over_limit() -> None:
    with pytest.raises(TimeBudgetExceededError):
        ensure_within_budget(
            budget=ExecutionBudget(
                max_attempts=2,
                max_recorded_tokens=10,
                max_elapsed_seconds=1.0,
            ),
            usage=BudgetUsage(elapsed_seconds=1.1),
        )
