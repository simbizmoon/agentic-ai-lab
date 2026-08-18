"""Deterministic EPO OPS CQL rendering from grounded patent concepts."""

from __future__ import annotations

from datetime import date

from app.research.patent_search_query_planner import PatentSearchQueryPlanner
from app.schemas.patent_search_query import PatentSearchQueryPlan
from app.schemas.patent_technical_concept import PatentTechnicalConceptPlan

_EPO_CQL_UNSAFE_TERM_CHARACTERS = frozenset({'"', "*", "?", "#"})


class EpoOpsPatentCqlPlanner:
    """Render grounded technical concepts into bounded EPO OPS CQL."""

    def __init__(
        self,
        *,
        query_planner: PatentSearchQueryPlanner | None = None,
    ) -> None:
        self._query_planner = query_planner or PatentSearchQueryPlanner()

    def plan(
        self,
        concept_plan: PatentTechnicalConceptPlan,
    ) -> PatentSearchQueryPlan:
        """Render one CQL candidate per concept and validate the final plan."""

        cql_queries = tuple(
            self._render_concept_query(
                terms=concept.terms,
                cutoff_date=concept_plan.request.prior_art_cutoff_date,
            )
            for concept in concept_plan.concepts
        )

        return self._query_planner.plan(
            request=concept_plan.request,
            cql_queries=cql_queries,
        )

    @staticmethod
    def _render_concept_query(
        *,
        terms: tuple[str, ...],
        cutoff_date: date | None,
    ) -> str:
        clauses = [EpoOpsPatentCqlPlanner._render_term_clause(term) for term in terms]

        if cutoff_date is not None:
            date_text = cutoff_date.strftime("%Y%m%d")
            clauses.append(f"pd < {date_text}")

        return " and ".join(clauses)

    @staticmethod
    def _render_term_clause(term: str) -> str:
        if not term.isascii():
            raise ValueError(
                "EPO OPS first-slice CQL planning requires ASCII technical "
                "terms because the ta index targets English title/abstract "
                "content and automatic translation is not enabled"
            )

        unsafe = sorted(set(term) & _EPO_CQL_UNSAFE_TERM_CHARACTERS)
        if unsafe:
            rendered = ", ".join(repr(character) for character in unsafe)
            raise ValueError(
                "patent technical term contains EPO CQL metacharacters "
                f"that are unsupported by the first slice: {rendered}"
            )

        return f'ta all "{term}"'
