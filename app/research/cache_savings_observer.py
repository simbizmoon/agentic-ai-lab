"""Observational decorators for existing AIRA persistent cache contracts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

from app.rag.embedding_cache import EmbeddingCache
from app.research.deterministic_provider_cost_calculator import (
    DeterministicProviderCostCalculator,
)
from app.research.parsed_document_cache import (
    ParsedDocumentCache,
    ParsedDocumentCacheEntryAccess,
    ParsedDocumentCacheIdentity,
)
from app.schemas.cache_savings_observation import (
    CacheAccessObservation,
    CacheSavingsReport,
    CacheWorkUnit,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.parsed_local_document import ParsedLocalDocument
from app.schemas.persistent_cache_status import CacheKind
from app.schemas.provider_cost import ProviderUsageEvent

_LIMITATIONS = (
    "Cache hits prove avoided work items, not avoided provider calls.",
    "Provider token savings are not exact unless separately provider-reported.",
    "Avoided monetary cost is an estimate from explicit counterfactual usage and price data.",
)


class _Counters:
    def __init__(self) -> None:
        self.lookups = 0
        self.hits = 0
        self.misses = 0
        self.writes = 0
        self.hit_bytes = 0
        self.miss_bytes = 0

    def record_lookup(self, *, hit: bool, input_bytes: int) -> None:
        self.lookups += 1
        if hit:
            self.hits += 1
            self.hit_bytes += input_bytes
        else:
            self.misses += 1
            self.miss_bytes += input_bytes


class ObservedEmbeddingCache(EmbeddingCache):
    """Measure exact embedding-cache activity while delegating storage unchanged."""

    def __init__(self, cache: EmbeddingCache, *, cache_identity: str) -> None:
        if not isinstance(cache, EmbeddingCache):
            raise TypeError("cache must be an EmbeddingCache")
        if not cache_identity.strip() or cache_identity != cache_identity.strip():
            raise ValueError("cache_identity must be normalized and nonblank")
        self._cache = cache
        self._cache_identity = cache_identity
        self._counters = _Counters()

    def get(
        self, *, text: str, model_name: str, dimensions: int
    ) -> TextEmbedding | None:
        value = self._cache.get(text=text, model_name=model_name, dimensions=dimensions)
        self._counters.record_lookup(
            hit=value is not None, input_bytes=len(text.encode("utf-8"))
        )
        return value

    def put(self, *, text: str, embedding: TextEmbedding) -> None:
        self._cache.put(text=text, embedding=embedding)
        self._counters.writes += 1

    def snapshot(
        self, *, observation_id: str, execution_id: str, stage_name: str
    ) -> CacheAccessObservation:
        return _snapshot(
            counters=self._counters,
            observation_id=observation_id,
            execution_id=execution_id,
            stage_name=stage_name,
            cache_kind=CacheKind.EMBEDDING,
            cache_identity=self._cache_identity,
            work_unit=CacheWorkUnit.EMBEDDING_TEXT,
        )


class _ObservedParsedEntry(ParsedDocumentCacheEntryAccess):
    def __init__(
        self,
        entry: ParsedDocumentCacheEntryAccess,
        identity: ParsedDocumentCacheIdentity,
        counters: _Counters,
    ) -> None:
        self._entry = entry
        self._identity = identity
        self._counters = counters

    def get(self) -> ParsedLocalDocument | None:
        value = self._entry.get()
        self._counters.record_lookup(
            hit=value is not None, input_bytes=self._identity.raw_file_size_bytes
        )
        return value

    def put(self, parsed_document: ParsedLocalDocument) -> None:
        self._entry.put(parsed_document)
        self._counters.writes += 1


class ObservedParsedDocumentCache(ParsedDocumentCache):
    """Measure parsed-cache activity including the locked recheck path."""

    def __init__(self, cache: ParsedDocumentCache, *, cache_identity: str) -> None:
        if not isinstance(cache, ParsedDocumentCache):
            raise TypeError("cache must be a ParsedDocumentCache")
        if not cache_identity.strip() or cache_identity != cache_identity.strip():
            raise ValueError("cache_identity must be normalized and nonblank")
        self._cache = cache
        self._cache_identity = cache_identity
        self._counters = _Counters()

    def get(self, identity: ParsedDocumentCacheIdentity) -> ParsedLocalDocument | None:
        value = self._cache.get(identity)
        self._counters.record_lookup(
            hit=value is not None, input_bytes=identity.raw_file_size_bytes
        )
        return value

    def put(
        self,
        identity: ParsedDocumentCacheIdentity,
        parsed_document: ParsedLocalDocument,
    ) -> None:
        self._cache.put(identity, parsed_document)
        self._counters.writes += 1

    @contextmanager
    def exclusive_entry(
        self, identity: ParsedDocumentCacheIdentity
    ) -> Iterator[ParsedDocumentCacheEntryAccess]:
        with self._cache.exclusive_entry(identity) as entry:
            yield _ObservedParsedEntry(entry, identity, self._counters)

    def snapshot(
        self, *, observation_id: str, execution_id: str, stage_name: str
    ) -> CacheAccessObservation:
        return _snapshot(
            counters=self._counters,
            observation_id=observation_id,
            execution_id=execution_id,
            stage_name=stage_name,
            cache_kind=CacheKind.PARSED,
            cache_identity=self._cache_identity,
            work_unit=CacheWorkUnit.PARSED_DOCUMENT,
        )


def build_cache_savings_report(
    observation: CacheAccessObservation,
    *,
    counterfactual_usage: ProviderUsageEvent | None = None,
    calculator: DeterministicProviderCostCalculator | None = None,
    cost_record_id: str | None = None,
    pricing_date: date | None = None,
    recorded_at: datetime | None = None,
) -> CacheSavingsReport:
    """Attach an estimate only when every required counterfactual input exists."""

    estimate_arguments = (counterfactual_usage, calculator, cost_record_id)
    if any(value is not None for value in estimate_arguments) and not all(
        value is not None for value in estimate_arguments
    ):
        raise ValueError(
            "counterfactual usage, calculator, and cost record ID are required"
        )
    calculation = None
    if counterfactual_usage is not None:
        assert calculator is not None and cost_record_id is not None
        calculation = calculator.calculate(
            counterfactual_usage,
            cost_record_id=cost_record_id,
            pricing_date=pricing_date,
            recorded_at=recorded_at,
        )
    return CacheSavingsReport(
        observation=observation,
        counterfactual_usage=counterfactual_usage,
        estimated_avoided_cost=calculation,
        provider_calls_avoided=None,
        exact_provider_token_savings_validated=False,
        exact_billed_cost_savings_validated=False,
        limitations=_LIMITATIONS,
    )


def _snapshot(
    *,
    counters: _Counters,
    observation_id: str,
    execution_id: str,
    stage_name: str,
    cache_kind: CacheKind,
    cache_identity: str,
    work_unit: CacheWorkUnit,
) -> CacheAccessObservation:
    return CacheAccessObservation(
        observation_id=observation_id,
        execution_id=execution_id,
        stage_name=stage_name,
        cache_kind=cache_kind,
        cache_identity=cache_identity,
        work_unit=work_unit,
        lookup_count=counters.lookups,
        hit_count=counters.hits,
        miss_count=counters.misses,
        write_count=counters.writes,
        hit_input_bytes=counters.hit_bytes,
        miss_input_bytes=counters.miss_bytes,
    )
