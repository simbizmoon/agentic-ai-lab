"""Adapters and immutable append operations for unified usage/cost accounting."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.schemas.bounded_research_agent_loop import ResearchAgentLoopUsage
from app.schemas.provider_cost import (
    CostKind,
    CostRecord,
    ProviderUsageEvent,
    UsageQuantity,
    UsageUnit,
    UsageValueKind,
)
from app.schemas.provider_cost_calculation import ProviderCostCalculation
from app.schemas.provider_cost_ledger import (
    CostLedgerTotal,
    ExecutionUsageCostLedger,
    UsageCostLedgerEntry,
)
from app.schemas.research_search_budget import ResearchSearchUsage
from app.schemas.scholarly_provider import ScholarlyProviderUsage
from app.services.text_generation import TokenUsage


class UsageCollectionError(ValueError):
    """Raised when raw usage cannot be preserved without guessing."""


class UnifiedUsageCollector:
    """Convert existing repository usage types into provider-neutral events."""

    @staticmethod
    def from_openai_tokens(
        usage: TokenUsage,
        *,
        usage_event_id: str,
        execution_id: str,
        stage_name: str,
        provider_name: str,
        model_name: str,
        operation: str,
        observed_at: datetime,
        request_id: str | None = None,
        response_id: str | None = None,
    ) -> ProviderUsageEvent:
        return ProviderUsageEvent(
            usage_event_id=usage_event_id,
            execution_id=execution_id,
            stage_name=stage_name,
            provider_name=provider_name,
            model_name=model_name,
            operation=operation,
            request_id=request_id,
            response_id=response_id,
            observed_at=observed_at,
            value_kind=UsageValueKind.PROVIDER_REPORTED,
            quantities=(
                _integer_quantity(UsageUnit.REQUEST, 1),
                _integer_quantity(UsageUnit.INPUT_TOKEN, usage.input_tokens),
                _integer_quantity(
                    UsageUnit.CACHED_INPUT_TOKEN, usage.cached_input_tokens
                ),
                _integer_quantity(UsageUnit.OUTPUT_TOKEN, usage.output_tokens),
                _integer_quantity(UsageUnit.REASONING_TOKEN, usage.reasoning_tokens),
                _integer_quantity(UsageUnit.TOTAL_TOKEN, usage.total_tokens),
            ),
        )

    @staticmethod
    def from_search_usage(
        usage: ResearchSearchUsage,
        *,
        usage_event_id: str,
        execution_id: str,
        stage_name: str,
        provider_name: str,
        operation: str,
        observed_at: datetime,
    ) -> ProviderUsageEvent:
        return ProviderUsageEvent(
            usage_event_id=usage_event_id,
            execution_id=execution_id,
            stage_name=stage_name,
            provider_name=provider_name,
            operation=operation,
            observed_at=observed_at,
            value_kind=UsageValueKind.OBSERVED,
            quantities=(
                _integer_quantity(UsageUnit.REQUEST, usage.provider_call_count),
                UsageQuantity(
                    unit=UsageUnit.SEARCH_CREDIT,
                    quantity=Decimal(str(usage.credit_used)),
                ),
            ),
        )

    @staticmethod
    def from_scholarly_usage(
        usage: ScholarlyProviderUsage,
        *,
        usage_event_id: str,
        execution_id: str,
        stage_name: str,
        provider_name: str,
        operation: str,
        observed_at: datetime,
    ) -> ProviderUsageEvent:
        return ProviderUsageEvent(
            usage_event_id=usage_event_id,
            execution_id=execution_id,
            stage_name=stage_name,
            provider_name=provider_name,
            operation=operation,
            observed_at=observed_at,
            value_kind=UsageValueKind.OBSERVED,
            quantities=(_integer_quantity(UsageUnit.REQUEST, usage.request_count),),
        )

    @staticmethod
    def from_agent_loop_usage(
        usage: ResearchAgentLoopUsage,
        *,
        usage_event_id: str,
        execution_id: str,
        stage_name: str,
        observed_at: datetime,
    ) -> ProviderUsageEvent:
        return ProviderUsageEvent(
            usage_event_id=usage_event_id,
            execution_id=execution_id,
            stage_name=stage_name,
            provider_name="AIRA",
            operation="bounded_research_agent_loop",
            observed_at=observed_at,
            value_kind=UsageValueKind.OBSERVED,
            quantities=(
                _integer_quantity(UsageUnit.AGENT_ROUND, usage.rounds),
                _integer_quantity(UsageUnit.TOOL_CALL, usage.tool_calls),
                _integer_quantity(UsageUnit.PROVIDER_CALL, usage.provider_calls),
                _integer_quantity(UsageUnit.RECORDED_TOKEN, usage.recorded_tokens),
                _integer_quantity(UsageUnit.EXTERNAL_REQUEST, usage.external_requests),
                UsageQuantity(
                    unit=UsageUnit.LOCAL_COMPUTE_SECOND,
                    quantity=Decimal(str(usage.elapsed_seconds)),
                ),
            ),
        )

    @staticmethod
    def provider_reported_cost(
        usage_event: ProviderUsageEvent,
        *,
        cost_record_id: str,
        amount_text: str,
        currency: str,
        source_reference: str,
        recorded_at: datetime,
    ) -> CostRecord:
        try:
            amount = Decimal(amount_text)
        except InvalidOperation as error:
            raise UsageCollectionError(
                "provider-reported cost must be a decimal string"
            ) from error
        if not amount.is_finite() or amount < 0:
            raise UsageCollectionError(
                "provider-reported cost must be finite and non-negative"
            )
        return CostRecord(
            cost_record_id=cost_record_id,
            execution_id=usage_event.execution_id,
            usage_event_id=usage_event.usage_event_id,
            cost_kind=CostKind.PROVIDER_REPORTED,
            amount=amount,
            currency=currency,
            source_reference=source_reference,
            recorded_at=recorded_at,
        )

    @staticmethod
    def unavailable_cost(
        usage_event: ProviderUsageEvent,
        *,
        cost_record_id: str,
        recorded_at: datetime,
    ) -> CostRecord:
        return CostRecord(
            cost_record_id=cost_record_id,
            execution_id=usage_event.execution_id,
            usage_event_id=usage_event.usage_event_id,
            cost_kind=CostKind.UNAVAILABLE,
            recorded_at=recorded_at,
        )

    @staticmethod
    def not_applicable_cost(
        usage_event: ProviderUsageEvent,
        *,
        cost_record_id: str,
        recorded_at: datetime,
    ) -> CostRecord:
        return CostRecord(
            cost_record_id=cost_record_id,
            execution_id=usage_event.execution_id,
            usage_event_id=usage_event.usage_event_id,
            cost_kind=CostKind.NOT_APPLICABLE,
            recorded_at=recorded_at,
        )


class ImmutableUsageCostLedger:
    """Return a new validated ledger snapshot for every append."""

    @staticmethod
    def empty(*, ledger_id: str, execution_id: str) -> ExecutionUsageCostLedger:
        return ExecutionUsageCostLedger(
            ledger_id=ledger_id,
            execution_id=execution_id,
        )

    @staticmethod
    def append(
        ledger: ExecutionUsageCostLedger,
        *,
        usage_event: ProviderUsageEvent,
        cost_record: CostRecord,
    ) -> ExecutionUsageCostLedger:
        entry = UsageCostLedgerEntry(
            usage_event=usage_event,
            cost_record=cost_record,
        )
        entries = ledger.entries + (entry,)
        return ExecutionUsageCostLedger(
            ledger_id=ledger.ledger_id,
            execution_id=ledger.execution_id,
            entries=entries,
            totals=_totals(entries),
        )

    @classmethod
    def append_calculation(
        cls,
        ledger: ExecutionUsageCostLedger,
        calculation: ProviderCostCalculation,
    ) -> ExecutionUsageCostLedger:
        return cls.append(
            ledger,
            usage_event=calculation.usage_event,
            cost_record=calculation.cost_record,
        )


def _integer_quantity(unit: UsageUnit, value: int) -> UsageQuantity:
    return UsageQuantity(unit=unit, quantity=Decimal(value))


def _totals(entries: tuple[UsageCostLedgerEntry, ...]) -> tuple[CostLedgerTotal, ...]:
    values: dict[tuple[CostKind, str], Decimal] = {}
    for entry in entries:
        cost = entry.cost_record
        if cost.amount is None or cost.currency is None:
            continue
        key = (cost.cost_kind, cost.currency)
        values[key] = values.get(key, Decimal(0)) + cost.amount
    return tuple(
        CostLedgerTotal(cost_kind=kind, currency=currency, amount=amount)
        for (kind, currency), amount in sorted(
            values.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )
