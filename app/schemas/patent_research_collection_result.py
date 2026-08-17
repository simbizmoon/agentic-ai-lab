"""Result contract for bounded patent-source collection."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.research.patent_publication_identity import normalize_patent_publication_number
from app.schemas.epo_ops_abstract import EpoOpsVerifiedPatentRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicSearchResult
from app.schemas.patent_research_request import PatentResearchRequest


class PatentResearchCollectionResult(BaseModel):
    """Preserve one request, its structured search, and verified source records."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: PatentResearchRequest
    search_result: EpoOpsBibliographicSearchResult
    verified_records: tuple[EpoOpsVerifiedPatentRecord, ...]

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Bind collected records to the request and searched candidate universe."""

        if (
            self.search_result.request.maximum_results
            != self.request.maximum_search_results
        ):
            raise ValueError(
                "search_result maximum_results must match the patent request"
            )
        if len(self.search_result.records) > self.request.maximum_search_results:
            raise ValueError(
                "search_result records must not exceed maximum_search_results"
            )
        if len(self.verified_records) > self.request.maximum_sources:
            raise ValueError("verified_records must not exceed maximum_sources")

        selected_candidates = self.search_result.records[: self.request.maximum_sources]
        if len(self.verified_records) != len(selected_candidates):
            raise ValueError(
                "successful fail-fast collection must verify every selected candidate"
            )

        selected_identities = tuple(
            normalize_patent_publication_number(record.publication_number)
            for record in selected_candidates
        )
        verified_identities = tuple(
            normalize_patent_publication_number(record.metadata.publication_number)
            for record in self.verified_records
        )
        if verified_identities != selected_identities:
            raise ValueError(
                "verified records must preserve the selected candidate identities and order"
            )
        return self
