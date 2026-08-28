"""Offline tests for exact cache observation and bounded savings estimates."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.rag.caching_embedding_provider import CachingEmbeddingProvider
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.file_embedding_cache import FileEmbeddingCache
from app.research.cache_savings_observer import (
    ObservedEmbeddingCache,
    ObservedParsedDocumentCache,
    build_cache_savings_report,
)
from app.research.deterministic_provider_cost_calculator import (
    DeterministicPriceRegistry,
    DeterministicProviderCostCalculator,
)
from app.research.file_parsed_document_cache import FileParsedDocumentCache
from app.research.parsed_document_cache import (
    ParsedDocumentCacheIdentity,
    ParsedDocumentParserIdentity,
)
from app.schemas.cache_savings_observation import CacheAccessObservation, CacheWorkUnit
from app.schemas.document_embedding import TextEmbedding
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.persistent_cache_status import CacheKind
from app.schemas.provider_cost import (
    ModelPriceEntry,
    PriceRate,
    ProviderUsageEvent,
    UsageQuantity,
    UsageUnit,
    UsageValueKind,
)
from app.schemas.research_source_document import ResearchSourceContentType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class _Provider(EmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return "offline-embedding-model"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(self, texts: object) -> list[TextEmbedding]:
        values = list(texts)  # type: ignore[arg-type]
        self.calls.append(values)
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=[float(len(text)), 1.0],
            )
            for text in values
        ]


def _observation(**updates: object) -> CacheAccessObservation:
    values: dict[str, object] = {
        "observation_id": "cache-observation-001",
        "execution_id": "execution-001",
        "stage_name": "stage8-step6",
        "cache_kind": CacheKind.EMBEDDING,
        "cache_identity": "embedding-cache-v1",
        "work_unit": CacheWorkUnit.EMBEDDING_TEXT,
        "lookup_count": 2,
        "hit_count": 1,
        "miss_count": 1,
        "write_count": 1,
        "hit_input_bytes": 10,
        "miss_input_bytes": 12,
    }
    values.update(updates)
    return CacheAccessObservation.model_validate(values)


def test_observation_rejects_inconsistent_lookup_counts() -> None:
    with pytest.raises(ValidationError, match="lookup count"):
        _observation(lookup_count=3)


def test_observation_rejects_cache_kind_work_unit_mismatch() -> None:
    with pytest.raises(ValidationError, match="work unit"):
        _observation(work_unit=CacheWorkUnit.PARSED_DOCUMENT)


def test_embedding_wrapper_observes_real_miss_write_and_hit(tmp_path: object) -> None:
    cache = ObservedEmbeddingCache(
        FileEmbeddingCache(directory=tmp_path / "embedding-cache"),  # type: ignore[operator]
        cache_identity="file-embedding-cache-v1",
    )
    provider = _Provider()
    caching = CachingEmbeddingProvider(provider=provider, cache=cache)

    first = caching.embed_text("한글 cache input")
    second = caching.embed_text("한글 cache input")
    observation = cache.snapshot(
        observation_id="embedding-observation",
        execution_id="execution-001",
        stage_name="stage8-step6",
    )

    assert first == second
    assert provider.calls == [["한글 cache input"]]
    assert observation.lookup_count == 2
    assert observation.hit_count == 1
    assert observation.miss_count == 1
    assert observation.write_count == 1
    assert observation.hit_input_bytes == len("한글 cache input".encode())
    assert observation.avoided_work_unit_count == 1


def test_parsed_wrapper_observes_locked_recheck_and_later_hit(tmp_path: object) -> None:
    identity = ParsedDocumentCacheIdentity(
        raw_content_sha256="a" * 64,
        raw_file_size_bytes=15,
        parser=ParsedDocumentParserIdentity(
            content_type=ResearchSourceContentType.TEXT,
            parser_id="offline-parser",
            parser_revision=1,
            configuration_identity="exact-v1",
        ),
    )
    parsed = ParsedLocalDocument(
        content="cached content",
        content_type=ResearchSourceContentType.TEXT,
    )
    cache = ObservedParsedDocumentCache(
        FileParsedDocumentCache(directory=tmp_path / "parsed-cache"),  # type: ignore[operator]
        cache_identity="file-parsed-cache-v1",
    )

    assert cache.get(identity) is None
    with cache.exclusive_entry(identity) as entry:
        assert entry.get() is None
        entry.put(parsed)
    assert cache.get(identity) == parsed
    observation = cache.snapshot(
        observation_id="parsed-observation",
        execution_id="execution-001",
        stage_name="stage8-step6",
    )

    assert (observation.lookup_count, observation.hit_count) == (3, 1)
    assert (observation.miss_count, observation.write_count) == (2, 1)
    assert observation.hit_input_bytes == 15
    assert observation.miss_input_bytes == 30


def test_report_without_counterfactual_makes_no_cost_or_call_claim() -> None:
    report = build_cache_savings_report(_observation())

    assert report.estimated_avoided_cost is None
    assert report.provider_calls_avoided is None
    assert report.exact_provider_token_savings_validated is False
    assert report.exact_billed_cost_savings_validated is False


def test_report_estimates_only_from_explicit_planned_usage_and_price() -> None:
    usage = ProviderUsageEvent(
        usage_event_id="counterfactual-usage-001",
        execution_id="execution-001",
        stage_name="stage8-step6",
        provider_name="ExampleProvider",
        model_name="offline-embedding-model",
        operation="embedding",
        observed_at=NOW,
        value_kind=UsageValueKind.PLANNED,
        quantities=(
            UsageQuantity(unit=UsageUnit.EMBEDDING_TOKEN, quantity=Decimal(250)),
        ),
    )
    price = ModelPriceEntry(
        price_entry_id="example-embedding-price-2026",
        registry_version="offline-test-v1",
        provider_name="ExampleProvider",
        model_name="offline-embedding-model",
        operation="embedding",
        effective_from=date(2026, 1, 1),
        source_reference="offline test fixture; not current provider pricing",
        rates=(
            PriceRate(
                usage_unit=UsageUnit.EMBEDDING_TOKEN,
                unit_size=Decimal(1000),
                rate_amount=Decimal("0.02"),
                currency="USD",
            ),
        ),
    )
    calculator = DeterministicProviderCostCalculator(
        DeterministicPriceRegistry([price])
    )

    report = build_cache_savings_report(
        _observation(),
        counterfactual_usage=usage,
        calculator=calculator,
        cost_record_id="estimated-avoided-cost-001",
    )

    assert report.estimated_avoided_cost is not None
    assert report.estimated_avoided_cost.cost_record.amount == Decimal("0.005")
    assert report.estimated_avoided_cost.cost_record.currency == "USD"
    assert report.estimated_avoided_cost.price_entry.source_reference.startswith(
        "offline test fixture"
    )
    assert report.exact_billed_cost_savings_validated is False


def test_partial_estimation_arguments_are_rejected() -> None:
    with pytest.raises(ValueError, match="are required"):
        build_cache_savings_report(
            _observation(),
            cost_record_id="missing-counterfactual-and-calculator",
        )
