"""Bounded scholarly metadata workflow runtime."""

from __future__ import annotations

from hashlib import sha256

from app.research.scholarly_identifier_normalizer import (
    group_duplicate_scholarly_works,
    scholarly_identifier_identity_key,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import ScholarlySearchRequest
from app.schemas.scholarly_search_workflow import (
    ScholarlyDuplicateGroup,
    ScholarlySearchWorkflowArtifact,
)
from app.schemas.scholarly_work import ScholarlyWork


class ScholarlySearchWorkflowContractError(RuntimeError):
    """Raised when an injected provider violates the workflow contract."""


class BoundedScholarlySearchWorkflow:
    """Execute one provider search and annotate exact duplicates."""

    def __init__(self, *, provider: ScholarlyMetadataProvider) -> None:
        if not provider.name.strip():
            raise ValueError("provider name must not be blank")
        self._provider = provider

    def run(
        self,
        request: ScholarlySearchRequest,
    ) -> ScholarlySearchWorkflowArtifact:
        """Run exactly one bounded provider operation."""

        result = self._provider.search(request)
        if result.request != request:
            raise ScholarlySearchWorkflowContractError(
                "provider result request does not match workflow request"
            )
        if result.provider.strip().casefold() != self._provider.name.strip().casefold():
            raise ScholarlySearchWorkflowContractError(
                "provider result name does not match injected provider"
            )
        groups = self._duplicate_groups(result.works)
        return ScholarlySearchWorkflowArtifact(
            artifact_id=f"scholarly-search-{request.request_id}",
            result=result,
            duplicate_groups=groups,
            distinct_identity_group_count=len(result.works)
            - sum(len(group.member_work_ids) - 1 for group in groups),
        )

    @staticmethod
    def _duplicate_groups(
        works: tuple[ScholarlyWork, ...],
    ) -> tuple[ScholarlyDuplicateGroup, ...]:
        grouped = group_duplicate_scholarly_works(works)
        duplicates: list[ScholarlyDuplicateGroup] = []
        for members in grouped:
            if len(members) < 2:
                continue
            shared_keys = BoundedScholarlySearchWorkflow._shared_keys(members)
            member_ids = tuple(work.work_id for work in members)
            digest_input = "\n".join(
                work_id.strip().casefold() for work_id in member_ids
            )
            duplicates.append(
                ScholarlyDuplicateGroup(
                    group_id=f"duplicate-{sha256(digest_input.encode()).hexdigest()[:16]}",
                    member_work_ids=member_ids,
                    shared_identity_keys=shared_keys,
                )
            )
        return tuple(duplicates)

    @staticmethod
    def _shared_keys(works: tuple[ScholarlyWork, ...]) -> tuple[str, ...]:
        key_sets = [
            {
                "|".join(scholarly_identifier_identity_key(identifier))
                for identifier in work.identifiers
            }
            for work in works
        ]
        counts: dict[str, int] = {}
        for keys in key_sets:
            for key in keys:
                counts[key] = counts.get(key, 0) + 1
        return tuple(sorted(key for key, count in counts.items() if count >= 2))
