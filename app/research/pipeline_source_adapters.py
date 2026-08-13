"""Set-level adapters for pipeline source search and reading."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.research.research_source_reader import (
    ResearchSourceReader,
)
from app.research.research_source_search_tool import (
    ResearchSourceSearchTool,
)
from app.schemas.research_search_budget import (
    ResearchSearchBudget,
    ResearchSearchUsage,
)
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_source_document import (
    ResearchSourceDocumentSet,
)


class PipelineSourceSearchAdapter:
    """Run a single-query search tool across a query set."""

    def __init__(
        self,
        search_tool: ResearchSourceSearchTool,
        *,
        maximum_candidates: int | None = None,
        minimum_results_per_query: int | None = None,
        budget: ResearchSearchBudget | None = None,
    ) -> None:
        if (
            maximum_candidates is not None
            and maximum_candidates < 1
        ):
            raise ValueError(
                "maximum_candidates must be greater than zero"
            )
        if (
            minimum_results_per_query is not None
            and minimum_results_per_query < 1
        ):
            raise ValueError(
                "minimum_results_per_query must be "
                "greater than zero"
            )

        self._search_tool = search_tool
        self._maximum_candidates = maximum_candidates
        self._minimum_results_per_query = (
            minimum_results_per_query
        )
        self._budget = budget
        self._usage = ResearchSearchUsage()

    @property
    def search_tool(self) -> ResearchSourceSearchTool:
        """Return the wrapped search tool."""

        return self._search_tool

    @property
    def search_budget(
        self,
    ) -> ResearchSearchBudget | None:
        """Return the configured search budget."""

        return self._budget

    @property
    def search_usage(self) -> ResearchSearchUsage:
        """Return accumulated provider usage."""

        return self._usage

    def search(
        self,
        query_set: ResearchSearchQuerySet,
    ) -> ResearchSourceCandidateSet:
        """Search all queries and return unique candidates."""

        candidates: list[ResearchSourceCandidate] = []
        seen_source_ids: set[str] = set()

        for query in query_set.queries:
            if not self._can_start_provider_call():
                self._usage = self._usage.model_copy(
                    update={
                        "blocked_query_count": (
                            self._usage.blocked_query_count
                            + 1
                        )
                    }
                )
                break

            search_query = query

            if self._minimum_results_per_query is not None:
                search_query = query.model_copy(
                    update={
                        "maximum_results": max(
                            query.maximum_results,
                            self._minimum_results_per_query,
                        )
                    }
                )

            result = self._search_tool.search(search_query)
            self._record_provider_result(result)

            for candidate in result.candidates:
                source_key = (
                    candidate.source_id.strip().casefold()
                )

                if source_key in seen_source_ids:
                    continue

                seen_source_ids.add(source_key)
                candidates.append(candidate)

                if (
                    self._maximum_candidates is not None
                    and len(candidates)
                    >= self._maximum_candidates
                ):
                    break

            if (
                self._maximum_candidates is not None
                and len(candidates)
                >= self._maximum_candidates
            ):
                break

        return ResearchSourceCandidateSet(
            request_id=query_set.request_id,
            query_set=query_set,
            candidates=candidates,
        )

    def _can_start_provider_call(self) -> bool:
        """Return whether one more provider call is allowed."""

        if self._budget is None:
            return True

        if (
            self._usage.provider_call_count
            >= self._budget.maximum_provider_calls
        ):
            return False

        if (
            self._usage.credit_used
            + self._budget.default_credit_per_call
            > self._budget.maximum_credits
        ):
            return False

        return (
            self._usage.latency_used_ms
            < self._budget.maximum_latency_ms
        )

    def _record_provider_result(
        self,
        result: object,
    ) -> None:
        """Accumulate one provider result into search usage."""

        duration_ms = int(result.duration_ms)
        metadata = result.metadata
        raw_credit = metadata.get("usage_credits")
        credit_reported = raw_credit is not None

        if credit_reported:
            try:
                credit = float(raw_credit)
            except (TypeError, ValueError):
                credit_reported = False
                credit = self._default_credit()
        else:
            credit = self._default_credit()

        self._usage = self._usage.model_copy(
            update={
                "provider_call_count": (
                    self._usage.provider_call_count + 1
                ),
                "credit_used": (
                    self._usage.credit_used + credit
                ),
                "latency_used_ms": (
                    self._usage.latency_used_ms
                    + duration_ms
                ),
                "unreported_credit_call_count": (
                    self._usage.unreported_credit_call_count
                    + (0 if credit_reported else 1)
                ),
            }
        )

    def _default_credit(self) -> float:
        """Return fallback credit for an unreported call."""

        if self._budget is None:
            return 0.0

        return self._budget.default_credit_per_call


class PipelineSourceReaderAdapter:
    """Run a single-candidate reader across a candidate set."""

    def __init__(
        self,
        reader: ResearchSourceReader,
        *,
        maximum_concurrency: int = 1,
    ) -> None:
        if isinstance(maximum_concurrency, bool):
            raise TypeError("maximum_concurrency must be an integer")
        if maximum_concurrency < 1:
            raise ValueError(
                "maximum_concurrency must be greater than zero"
            )

        self._reader = reader
        self._maximum_concurrency = maximum_concurrency

    @property
    def reader(self) -> ResearchSourceReader:
        """Return the wrapped source reader."""

        return self._reader

    @property
    def maximum_concurrency(self) -> int:
        """Return the configured source-read concurrency."""

        return self._maximum_concurrency

    def read(
        self,
        candidate_set: ResearchSourceCandidateSet,
    ) -> ResearchSourceDocumentSet:
        """Read every candidate and preserve candidate order."""

        candidates = list(candidate_set.candidates)
        if self._maximum_concurrency == 1 or len(candidates) <= 1:
            documents = [
                self._reader.read(candidate)
                for candidate in candidates
            ]
        else:
            with ThreadPoolExecutor(
                max_workers=min(
                    self._maximum_concurrency,
                    len(candidates),
                )
            ) as executor:
                documents = list(
                    executor.map(
                        self._reader.read,
                        candidates,
                    )
                )

        return ResearchSourceDocumentSet(
            request_id=candidate_set.request_id,
            documents=documents,
        )
