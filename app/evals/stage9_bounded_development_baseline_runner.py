"""Sequential controller for the Stage 9 development-only baseline."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.evals.stage9_safe_failure_diagnostics import safe_stage9_failure_code
from app.schemas.provider_cost import CostKind
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment
from app.schemas.stage9_development_baseline_run import (
    Stage9DevelopmentCaseRecord,
    Stage9DevelopmentCaseStatus,
    Stage9DevelopmentRunRequest,
    Stage9DevelopmentRunResult,
    Stage9DevelopmentRunStatus,
    Stage9DevelopmentRunUsage,
)


class Stage9DevelopmentCaseExecutor(Protocol):
    """Execute and persist exactly one case before returning its record."""

    def execute(
        self,
        *,
        case_id: str,
        request: Stage9DevelopmentRunRequest,
    ) -> Stage9DevelopmentCaseRecord: ...


class Stage9DevelopmentBaselineRunnerError(RuntimeError):
    """The locked inputs or executor output violated the run boundary."""


class Stage9DevelopmentCaseExecutionError(RuntimeError):
    """One expected and safely normalized case-execution failure."""


def _aggregate(
    records: tuple[Stage9DevelopmentCaseRecord, ...],
) -> Stage9DevelopmentRunUsage:
    return Stage9DevelopmentRunUsage(
        provider_requests=sum(item.usage.provider_requests for item in records),
        external_requests=sum(item.usage.external_requests for item in records),
        recorded_tokens=sum(item.usage.recorded_tokens for item in records),
        elapsed_seconds=sum(item.usage.elapsed_seconds for item in records),
        estimated_cost=sum((item.usage.estimated_cost for item in records), Decimal(0)),
        currency="USD",
        cost_kind=CostKind.ESTIMATED,
    )


class BoundedStage9DevelopmentBaselineRunner:
    """Run the four disclosed cases in order and never enter the holdout."""

    def __init__(
        self,
        *,
        experiment: Stage9LockedBaselineExperiment,
        executor: Stage9DevelopmentCaseExecutor,
    ) -> None:
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")
        self._experiment = experiment
        self._executor = executor

    def run(
        self,
        request: Stage9DevelopmentRunRequest,
    ) -> Stage9DevelopmentRunResult:
        if not isinstance(request, Stage9DevelopmentRunRequest):
            raise TypeError("request must be a Stage 9 development run request")
        self._validate_lock(request)

        records: list[Stage9DevelopmentCaseRecord] = []
        for case_id in request.case_ids:
            current = _aggregate(tuple(records))
            reached = self._reached_ceiling(current, request)
            if reached is not None:
                return self._terminal(
                    request=request,
                    records=records,
                    status=Stage9DevelopmentRunStatus.STOPPED,
                    budget_exhausted=False,
                    reason=f"phase ceiling reached before next case: {reached}",
                )

            try:
                record = self._executor.execute(case_id=case_id, request=request)
            except Stage9DevelopmentCaseExecutionError as error:
                return self._terminal(
                    request=request,
                    records=records,
                    status=Stage9DevelopmentRunStatus.FAILED,
                    budget_exhausted=False,
                    reason=f"case executor failed safely: {safe_stage9_failure_code(error)}",
                )
            if not isinstance(record, Stage9DevelopmentCaseRecord):
                raise Stage9DevelopmentBaselineRunnerError(
                    "executor must return a Stage9DevelopmentCaseRecord"
                )
            if record.case_id != case_id:
                raise Stage9DevelopmentBaselineRunnerError(
                    "executor returned a record for the wrong case"
                )
            records.append(record)

            usage = _aggregate(tuple(records))
            exceeded = self._exceeded_ceiling(usage, request)
            if exceeded is not None:
                return self._terminal(
                    request=request,
                    records=records,
                    status=Stage9DevelopmentRunStatus.STOPPED,
                    budget_exhausted=True,
                    reason=f"phase ceiling exceeded after persisted case: {exceeded}",
                )
            if record.status is Stage9DevelopmentCaseStatus.FAILED:
                return self._terminal(
                    request=request,
                    records=records,
                    status=Stage9DevelopmentRunStatus.FAILED,
                    budget_exhausted=False,
                    reason=f"case failed: {case_id}",
                )
            if record.status is Stage9DevelopmentCaseStatus.INCOMPLETE:
                return self._terminal(
                    request=request,
                    records=records,
                    status=Stage9DevelopmentRunStatus.INCOMPLETE,
                    budget_exhausted=False,
                    reason=f"case incomplete: {case_id}",
                )

        final_records = tuple(records)
        return Stage9DevelopmentRunResult(
            request=request,
            status=Stage9DevelopmentRunStatus.COMPLETED,
            case_records=final_records,
            usage=_aggregate(final_records),
            budget_exhausted=False,
        )

    def _validate_lock(self, request: Stage9DevelopmentRunRequest) -> None:
        plan = self._experiment.plan
        if request.case_ids != plan.development_case_ids:
            raise Stage9DevelopmentBaselineRunnerError(
                "request does not match the locked development partition"
            )
        if request.repetitions_per_case != plan.manifest.repetitions_per_case:
            raise Stage9DevelopmentBaselineRunnerError(
                "request repetition does not match the locked manifest"
            )
        if request.manifest_sha256 != (
            "60179543f5290136d434d4f4c72598af8f74eb569a1d06b43c7490320d81e191"
        ):
            raise Stage9DevelopmentBaselineRunnerError(
                "request does not identify the approved manifest"
            )
        if request.review_sha256 != (
            "f36c0b7bee7cc9548f2f3a36946e4b49293883b69349b4499f2c80d27190cae7"
        ):
            raise Stage9DevelopmentBaselineRunnerError(
                "request does not identify the approved human review"
            )

    @staticmethod
    def _reached_ceiling(
        usage: Stage9DevelopmentRunUsage,
        request: Stage9DevelopmentRunRequest,
    ) -> str | None:
        budget = request.budget
        checks = (
            (
                "provider_requests",
                usage.provider_requests,
                budget.maximum_provider_requests,
            ),
            (
                "external_requests",
                usage.external_requests,
                budget.maximum_external_requests,
            ),
            ("recorded_tokens", usage.recorded_tokens, budget.maximum_recorded_tokens),
            ("elapsed_seconds", usage.elapsed_seconds, budget.maximum_elapsed_seconds),
            ("estimated_cost", usage.estimated_cost, budget.maximum_estimated_cost),
        )
        return next((name for name, actual, limit in checks if actual >= limit), None)

    @staticmethod
    def _exceeded_ceiling(
        usage: Stage9DevelopmentRunUsage,
        request: Stage9DevelopmentRunRequest,
    ) -> str | None:
        budget = request.budget
        checks = (
            (
                "provider_requests",
                usage.provider_requests,
                budget.maximum_provider_requests,
            ),
            (
                "external_requests",
                usage.external_requests,
                budget.maximum_external_requests,
            ),
            ("recorded_tokens", usage.recorded_tokens, budget.maximum_recorded_tokens),
            ("elapsed_seconds", usage.elapsed_seconds, budget.maximum_elapsed_seconds),
            ("estimated_cost", usage.estimated_cost, budget.maximum_estimated_cost),
        )
        return next((name for name, actual, limit in checks if actual > limit), None)

    @staticmethod
    def _terminal(
        *,
        request: Stage9DevelopmentRunRequest,
        records: list[Stage9DevelopmentCaseRecord],
        status: Stage9DevelopmentRunStatus,
        budget_exhausted: bool,
        reason: str,
    ) -> Stage9DevelopmentRunResult:
        values = tuple(records)
        return Stage9DevelopmentRunResult(
            request=request,
            status=status,
            case_records=values,
            usage=_aggregate(values),
            budget_exhausted=budget_exhausted,
            stop_reason=reason,
        )
