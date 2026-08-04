"""Schemas for research search queries and query sets."""

from __future__ import annotations

from datetime import date
from enum import IntEnum, StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_request import ResearchSourceType
from app.schemas.research_task import ResearchTaskGraph


class ResearchSearchQueryType(StrEnum):
    """Purpose of one research search query."""

    BROAD = "broad"
    FOCUSED = "focused"
    EXACT = "exact"
    OFFICIAL = "official"
    PRIMARY_SOURCE = "primary_source"
    CONTRADICTING = "contradicting"
    RECENCY = "recency"


class ResearchSearchQueryPriority(IntEnum):
    """Execution priority for one search query."""

    LOW = 10
    MEDIUM = 20
    HIGH = 30
    CRITICAL = 40


class ResearchSearchQuery(BaseModel):
    """One validated search query for a research task."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    query_id: str
    request_id: str
    task_id: str
    query_text: str
    query_type: ResearchSearchQueryType = (
        ResearchSearchQueryType.FOCUSED
    )
    priority: ResearchSearchQueryPriority = (
        ResearchSearchQueryPriority.MEDIUM
    )
    preferred_source_types: list[
        ResearchSourceType
    ] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    maximum_results: int = Field(
        default=10,
        ge=1,
        le=100,
    )
    exact_phrase: bool = False
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate one research search query."""

        required_text = {
            "query_id": self.query_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "query_text": self.query_text,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if len(set(self.preferred_source_types)) != len(
            self.preferred_source_types
        ):
            raise ValueError(
                "preferred_source_types must not "
                "contain duplicates"
            )

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError(
                "start_date must not be after end_date"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    def normalized_query_text(self) -> str:
        """Return normalized query text for duplicate checks."""

        return " ".join(
            self.query_text.strip().casefold().split()
        )


class ResearchSearchQuerySet(BaseModel):
    """Validated set of search queries for a task graph."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    task_graph: ResearchTaskGraph
    queries: list[ResearchSearchQuery] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_query_set(self) -> Self:
        """Validate query identity and task references."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        if self.task_graph.request_id != self.request_id:
            raise ValueError(
                "task graph request_id must match "
                "query set request_id"
            )

        normalized_query_ids = [
            query.query_id.strip().casefold()
            for query in self.queries
        ]

        if len(set(normalized_query_ids)) != len(
            normalized_query_ids
        ):
            raise ValueError(
                "query IDs must be unique"
            )

        if any(
            query.request_id != self.request_id
            for query in self.queries
        ):
            raise ValueError(
                "all query request IDs must match "
                "the query set request_id"
            )

        task_ids = {
            task.task_id.strip().casefold()
            for task in self.task_graph.tasks
        }

        if any(
            query.task_id.strip().casefold()
            not in task_ids
            for query in self.queries
        ):
            raise ValueError(
                "all queries must reference existing tasks"
            )

        query_keys = [
            (
                query.task_id.strip().casefold(),
                query.normalized_query_text(),
            )
            for query in self.queries
        ]

        if len(set(query_keys)) != len(query_keys):
            raise ValueError(
                "queries for the same task must not "
                "contain duplicate query text"
            )

        return self

    def ordered_queries(
        self,
    ) -> list[ResearchSearchQuery]:
        """Return queries in deterministic execution order."""

        original_position = {
            query.query_id: position
            for position, query in enumerate(self.queries)
        }

        return sorted(
            self.queries,
            key=lambda query: (
                -int(query.priority),
                original_position[query.query_id],
            ),
        )

    def queries_for_task(
        self,
        task_id: str,
    ) -> list[ResearchSearchQuery]:
        """Return ordered queries assigned to one task."""

        if not task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        normalized_task_id = (
            task_id.strip().casefold()
        )

        return [
            query
            for query in self.ordered_queries()
            if query.task_id.strip().casefold()
            == normalized_task_id
        ]
