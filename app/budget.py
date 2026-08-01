"""Pure execution budget helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.exceptions import (
    AttemptBudgetExceededError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
)


@dataclass(frozen=True)
class ExecutionBudget:
    max_attempts: int
    max_recorded_tokens: int
    max_elapsed_seconds: float

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.max_recorded_tokens < 1:
            raise ValueError("max_recorded_tokens must be at least 1")
        if self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds must be greater than 0")


@dataclass(frozen=True)
class BudgetUsage:
    attempts: int = 0
    recorded_tokens: int = 0
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("attempts must not be negative")
        if self.recorded_tokens < 0:
            raise ValueError("recorded_tokens must not be negative")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must not be negative")


def ensure_can_start_attempt(
    *,
    budget: ExecutionBudget,
    usage: BudgetUsage,
) -> None:
    if usage.attempts >= budget.max_attempts:
        raise AttemptBudgetExceededError("Execution attempt budget exceeded")
    if usage.recorded_tokens >= budget.max_recorded_tokens:
        raise TokenBudgetExceededError("Execution token budget exceeded")
    if usage.elapsed_seconds >= budget.max_elapsed_seconds:
        raise TimeBudgetExceededError("Execution time budget exceeded")


def record_attempt(
    *,
    usage: BudgetUsage,
    recorded_tokens: int,
    elapsed_seconds: float,
) -> BudgetUsage:
    if recorded_tokens < 0:
        raise ValueError("recorded_tokens must not be negative")
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must not be negative")

    return BudgetUsage(
        attempts=usage.attempts + 1,
        recorded_tokens=usage.recorded_tokens + recorded_tokens,
        elapsed_seconds=usage.elapsed_seconds + elapsed_seconds,
    )


def ensure_within_budget(
    *,
    budget: ExecutionBudget,
    usage: BudgetUsage,
) -> None:
    if usage.attempts > budget.max_attempts:
        raise AttemptBudgetExceededError("Execution attempt budget exceeded")
    if usage.recorded_tokens > budget.max_recorded_tokens:
        raise TokenBudgetExceededError("Execution token budget exceeded")
    if usage.elapsed_seconds > budget.max_elapsed_seconds:
        raise TimeBudgetExceededError("Execution time budget exceeded")
