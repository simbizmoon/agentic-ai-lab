"""Offline CLI-to-artifact E2E test for explicit patent comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.cli import main
from app.research.patent_multi_patent_comparison_cli_handler import (
    PatentMultiPatentComparisonCliHandler,
)
from app.research.patent_multi_patent_comparison_factory import (
    build_openai_epo_patent_multi_patent_comparison_workflow,
)
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import PatentClaim
from app.schemas.patent_multi_patent_comparison import PatentMultiPatentComparison
from app.schemas.patent_multi_patent_comparison_request import (
    PatentMultiPatentComparisonRequest,
)


@dataclass
class OfflineClaimsRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        self.calls.append(record.publication_number)
        return EpoOpsClaimsRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            source_endpoint="https://ops.epo.org/offline/target/claims",
            claim_sets=(
                EpoOpsClaimSet(
                    language="EN",
                    claims=(
                        EpoOpsClaimText(
                            position=1,
                            text="1. A system comprising a sensor and controller.",
                        ),
                    ),
                ),
            ),
        )


@dataclass
class OfflineAbstractRetriever:
    calls: list[str]

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        self.calls.append(record.publication_number)
        return EpoOpsAbstractRecord(
            publication_number=record.publication_number,
            publication_docdb=record.publication_docdb,
            abstract_text=(
                f"A sensor and controller from publication {record.publication_number}."
            ),
            abstract_language="en",
            source_endpoint=(
                f"https://ops.epo.org/offline/{record.publication_docdb}/abstract"
            ),
        )


@dataclass(frozen=True)
class DecompositionResult:
    decomposition: PatentClaimDecomposition


@dataclass
class OfflineDecomposer:
    calls: list[str]

    def decompose(self, claim: PatentClaim) -> DecompositionResult:
        self.calls.append(claim.text)
        return DecompositionResult(
            decomposition=PatentClaimDecomposition(
                claim_number=claim.claim_number,
                provider_position=claim.provider_position,
                original_claim_text=claim.text,
                elements=(PatentClaimElement(element_number=1, text=claim.text),),
            )
        )


@dataclass(frozen=True)
class EvaluationResult:
    judgment: EvidenceRelevanceJudgment


@dataclass
class OfflineEvaluator:
    calls: list[tuple[str, str]]

    def evaluate(self, *, element_text: str, evidence_excerpt: str) -> EvaluationResult:
        self.calls.append((element_text, evidence_excerpt))
        return EvaluationResult(
            judgment=EvidenceRelevanceJudgment(
                relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                relevance_score=0.7,
                rationale="Deterministic offline CLI E2E judgment.",
                issues=["Semantic quality is not evaluated by this test double."],
            )
        )


def _arguments(output_dir: Path) -> list[str]:
    return [
        "research-patent-compare",
        "--target-publication",
        "EP1000000B1",
        "--comparison-publication",
        "EP2000000A1",
        "--comparison-publication",
        "EP3000000A1",
        "--maximum-claim-elements",
        "1",
        "--maximum-mapping-calls",
        "2",
        "--maximum-bytes",
        "4096",
        "--output-dir",
        str(output_dir),
    ]


def _forbidden_fields(value: object) -> set[str]:
    forbidden = {
        "winner",
        "best_patent",
        "rank",
        "coverage_percentage",
        "novelty",
        "obviousness",
        "infringement",
        "legal_conclusion",
    }
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(forbidden.intersection(value))
        for child in value.values():
            found.update(_forbidden_fields(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_fields(child))
    return found


def test_cli_offline_e2e_persists_exact_bounded_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    claims = OfflineClaimsRetriever(calls=[])
    abstracts = OfflineAbstractRetriever(calls=[])
    decomposer = OfflineDecomposer(calls=[])
    evaluator = OfflineEvaluator(calls=[])

    def runtime_factory(request: PatentMultiPatentComparisonRequest):
        return build_openai_epo_patent_multi_patent_comparison_workflow(
            request,
            claims_retriever=claims,
            abstract_retriever=abstracts,
            claim_decomposer=decomposer,
            mapping_evaluator=evaluator,
        )

    handler = PatentMultiPatentComparisonCliHandler(
        runtime_factory=runtime_factory,
        request_id_factory=lambda: "cli-e2e-request-001",
        execution_id_factory=lambda: "cli-e2e-execution-001",
    )

    assert main(_arguments(tmp_path), patent_comparison_handler=handler) == 0

    output = capsys.readouterr().out
    assert "planned_maximum_mapping_calls=2" in output
    assert "actual_mapping_calls=2" in output
    assert "This is a technical multi-patent comparison only." in output
    assert "It does not determine novelty" in output
    assert claims.calls == ["EP1000000B1"]
    assert abstracts.calls == ["EP2000000A1", "EP3000000A1"]
    assert len(decomposer.calls) == 1
    assert len(evaluator.calls) == 2

    json_paths = tuple(tmp_path.rglob("*.json"))
    markdown_paths = tuple(tmp_path.rglob("*.md"))
    assert len(json_paths) == 1
    assert len(markdown_paths) == 1

    json_text = json_paths[0].read_text(encoding="utf-8")
    raw = json.loads(json_text)
    comparison = PatentMultiPatentComparison.model_validate_json(json_text)
    assert comparison.target_publication_number == "EP1000000B1"
    assert comparison.prior_art_publications == (
        "EP2000000A1",
        "EP3000000A1",
    )
    cells = comparison.claim_sets[0].claims[0].rows[0].publications
    assert tuple(cell.publication_number for cell in cells) == (
        "EP2000000A1",
        "EP3000000A1",
    )
    assert tuple(cell.evaluations[0].evidence_id for cell in cells) == (
        "patent-comparison-evidence-001",
        "patent-comparison-evidence-002",
    )
    assert tuple(cell.evaluations[0].start_character for cell in cells) == (0, 0)
    assert tuple(cell.evaluations[0].end_character for cell in cells) == tuple(
        len(call[1]) for call in evaluator.calls
    )
    assert _forbidden_fields(raw) == set()

    markdown = markdown_paths[0].read_text(encoding="utf-8")
    assert "EP2000000A1" in markdown
    assert "EP3000000A1" in markdown
    assert "patent-comparison-evidence-001" in markdown
    assert "patent-comparison-evidence-002" in markdown
