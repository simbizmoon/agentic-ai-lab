"""OpenAI-backed bounded synthesis for patent technical findings."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.schemas.patent_technical_report import PatentTechnicalResearchReport
from app.schemas.patent_technical_synthesis import (
    PATENT_ZERO_FINDING_OVERALL_SUMMARY,
    PatentTechnicalSynthesis,
)
from app.services.structured_analysis import has_refusal
from app.services.text_generation import TokenUsage, extract_token_usage

PATENT_TECHNICAL_SYNTHESIS_INSTRUCTIONS = """
Summarize only the supplied patent technical findings.

Use only:
- the supplied research question and objective;
- the supplied finding IDs;
- the supplied publication metadata;
- the supplied relevance labels and rationales;
- the supplied evidence excerpts.

Do not use outside knowledge.
Do not search for additional information.
Do not invent patent numbers, dates, applicants, inventors, claims, features, or facts.
Do not infer beyond the supplied evidence excerpts.

The task is technical synthesis only.

Allowed wording includes:
- technically relevant;
- potentially relevant prior art;
- the cited excerpt appears to describe or disclose a technical feature;
- verified publication metadata.

Do NOT make legal conclusions, including:
- novelty or lack of novelty;
- anticipation;
- obviousness or inventive step;
- validity or invalidity;
- infringement;
- freedom to operate;
- current legal status.

For every supplied finding, return exactly one finding summary with the exact
finding_id copied unchanged.

Each technical_summary must remain a cautious paraphrase of that finding's
supplied evidence and relevance rationale. Do not strengthen the source.

overall_summary must summarize the supplied findings as a group without adding
new technical facts or legal conclusions.

limitations should state meaningful constraints of the supplied material, such
as abstract-only evidence, bounded search scope, or unevaluated evidence when
those constraints are present in the input. Do not invent limitations that are
not supported by the input.

If there are zero findings, return an overall summary stating that no
semantically evaluated relevant finding was available in this bounded run,
return finding_summaries as an empty list, and describe any supplied
unevaluated-evidence limitation.

Return only a valid structured answer.
""".strip()


class ResponsesParseResource(Protocol):
    """Subset of the Responses API required by this synthesizer."""

    def parse(self, **kwargs: Any) -> Any:
        """Return one parsed Responses API result."""


class PatentTechnicalSynthesisOpenAIClient(Protocol):
    """Injected OpenAI client exposing Responses parsing."""

    responses: ResponsesParseResource


@dataclass(frozen=True)
class PatentTechnicalSynthesisGenerationResult:
    """One bounded synthesis plus execution metadata."""

    synthesis: PatentTechnicalSynthesis
    response_id: str | None
    request_id: str | None
    usage: TokenUsage | None
    elapsed_seconds: float


class OpenAIPatentTechnicalSynthesizer:
    """Generate bounded prose from an existing deterministic patent report."""

    def __init__(
        self,
        *,
        client: PatentTechnicalSynthesisOpenAIClient,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")

        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        """Return the configured model."""

        return self._model

    def synthesize(
        self,
        report: PatentTechnicalResearchReport,
    ) -> PatentTechnicalSynthesisGenerationResult:
        """Synthesize only the supplied finding/evidence material."""

        if not report.findings:
            return PatentTechnicalSynthesisGenerationResult(
                synthesis=PatentTechnicalSynthesis(
                    overall_summary=PATENT_ZERO_FINDING_OVERALL_SUMMARY,
                    finding_summaries=[],
                    limitations=(
                        [
                            (
                                "One or more evidence items remained "
                                "unevaluated because semantic evaluation "
                                "did not complete within the bounded run."
                            )
                        ]
                        if report.unevaluated_evidence_ids
                        else []
                    ),
                ),
                response_id=None,
                request_id=None,
                usage=None,
                elapsed_seconds=0.0,
            )

        payload = {
            "question": report.question,
            "objective": report.objective,
            "prior_art_cutoff_date": (
                report.prior_art_cutoff_date.isoformat()
                if report.prior_art_cutoff_date is not None
                else None
            ),
            "executed_query_purpose": report.executed_query_purpose,
            "executed_cql": report.executed_cql,
            "scope_notice": report.scope_notice,
            "unevaluated_evidence_ids": report.unevaluated_evidence_ids,
            "findings": [
                {
                    "finding_id": finding.finding_id,
                    "publication_number": finding.publication_number,
                    "application_number": finding.application_number,
                    "priority_claims": [
                        {
                            "priority_number": claim.priority_number,
                            "priority_date": (
                                claim.priority_date.isoformat()
                                if claim.priority_date is not None
                                else None
                            ),
                        }
                        for claim in finding.priority_claims
                    ],
                    "ipc_classifications": [
                        {"text": classification.text}
                        for classification in finding.ipc_classifications
                    ],
                    "cpc_classifications": [
                        {
                            "section": classification.section,
                            "class_number": classification.class_number,
                            "subclass": classification.subclass,
                            "main_group": classification.main_group,
                            "subgroup": classification.subgroup,
                        }
                        for classification in finding.cpc_classifications
                    ],
                    "applicants": [
                        {"name": party.name} for party in finding.applicants
                    ],
                    "inventors": [{"name": party.name} for party in finding.inventors],
                    "title": finding.title,
                    "publication_date": (
                        finding.publication_date.isoformat()
                        if finding.publication_date is not None
                        else None
                    ),
                    "source_family": finding.source_family.value,
                    "metadata_verification_state": (
                        finding.metadata_verification_state.value
                    ),
                    "relevance_level": finding.relevance_level.value,
                    "relevance_score": finding.relevance_score,
                    "relevance_rationale": finding.relevance_rationale,
                    "evidence_excerpt": finding.evidence.excerpt,
                }
                for finding in report.findings
            ],
        }

        started = time.perf_counter()

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=PATENT_TECHNICAL_SYNTHESIS_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=PatentTechnicalSynthesis,
                store=False,
            )
        except ValidationError as exc:
            elapsed_seconds = max(
                0.0,
                time.perf_counter() - started,
            )
            raise StructuredResponseValidationError(
                "patent technical synthesis response failed schema validation",
                elapsed_seconds=elapsed_seconds,
                attempts=1,
            ) from exc

        elapsed_seconds = max(
            0.0,
            time.perf_counter() - started,
        )

        status = getattr(response, "status", None)

        if status == "incomplete":
            raise StructuredResponseIncompleteError(
                "patent technical synthesis response was incomplete"
            )

        if status != "completed":
            raise StructuredResponseStatusError(
                "patent technical synthesis response was not completed"
            )

        if has_refusal(response):
            raise StructuredResponseRefusalError(
                "OpenAI refused patent technical synthesis"
            )

        parsed = getattr(response, "output_parsed", None)

        if parsed is None:
            raise StructuredResponseParseError(
                "patent technical synthesis response was empty"
            )

        if not isinstance(parsed, PatentTechnicalSynthesis):
            raise StructuredResponseParseError(
                "patent technical synthesis response has invalid type"
            )

        expected_ids = [finding.finding_id for finding in report.findings]
        returned_ids = [item.finding_id for item in parsed.finding_summaries]

        expected_folded = [value.casefold() for value in expected_ids]
        returned_folded = [value.casefold() for value in returned_ids]

        if (
            len(returned_ids) != len(expected_ids)
            or len(set(returned_folded)) != len(returned_folded)
            or set(returned_folded) != set(expected_folded)
        ):
            raise StructuredResponseParseError(
                "patent technical synthesis finding IDs did not match report"
            )

        by_folded = {
            item.finding_id.casefold(): item for item in parsed.finding_summaries
        }
        ordered = [by_folded[finding_id.casefold()] for finding_id in expected_ids]

        synthesis = PatentTechnicalSynthesis(
            overall_summary=parsed.overall_summary,
            finding_summaries=ordered,
            limitations=parsed.limitations,
        )

        return PatentTechnicalSynthesisGenerationResult(
            synthesis=synthesis,
            response_id=str(response.id),
            request_id=getattr(response, "_request_id", None),
            usage=extract_token_usage(response),
            elapsed_seconds=elapsed_seconds,
        )
