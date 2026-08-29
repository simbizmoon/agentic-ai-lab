"""Offline import of the human-locked Stage 9 dataset into repository case types."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.evals.evaluation_case_definition import (
    EvaluationCaseDefinition,
    EvaluationInput,
)
from app.evals.evaluation_dataset import (
    EvaluationDifficulty,
    ExpectedEvidence,
    ExpectedSource,
)
from app.evals.evaluation_expected_outcome import EvaluationExpectedOutcome
from app.schemas.stage9_evaluation_manifest import (
    Stage9DatasetPartition,
    Stage9EvaluationCase,
    Stage9EvaluationDomain,
)

DEVELOPMENT_IDS = frozenset({"tech-01", "academic-01", "patent-01", "cross-01"})
EXPECTED_CASE_IDS = (
    "tech-01",
    "tech-02",
    "academic-01",
    "academic-02",
    "patent-01",
    "patent-02",
    "patent-03",
    "cross-01",
    "cross-02",
    "cross-03",
)


class LockedDatasetImportError(ValueError):
    """The locked input is incomplete, changed, or inconsistent."""


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _verify_input(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    sidecar = Path(str(path) + ".sha256")
    expected_file_hash = sidecar.read_text(encoding="ascii").split()[0]
    if hashlib.sha256(raw).hexdigest() != expected_file_hash:
        raise LockedDatasetImportError("locked dataset file checksum mismatch")
    data = json.loads(raw)
    payload = {
        key: data[key]
        for key in (
            "dataset_id",
            "dataset_version",
            "catalog_id",
            "catalog_version",
            "case_order",
            "cases",
        )
    }
    if hashlib.sha256(_canonical_bytes(payload)).hexdigest() != data["dataset_sha256"]:
        raise LockedDatasetImportError("locked dataset semantic checksum mismatch")
    if tuple(data["case_order"]) != EXPECTED_CASE_IDS or len(data["cases"]) != 10:
        raise LockedDatasetImportError("locked case order or count mismatch")
    if tuple(item["case_id"] for item in data["cases"]) != EXPECTED_CASE_IDS:
        raise LockedDatasetImportError("case payload order mismatch")
    return data


def _build_case(item: dict[str, Any]) -> Stage9EvaluationCase:
    review = item["human_review"]
    if item["partition"] != "locked" or review["decision"] != "locked":
        raise LockedDatasetImportError(f"{item['case_id']}: human lock is missing")
    sources = review["source_reviews"]
    expected_sources = [
        ExpectedSource(
            source_id=source["source_id"],
            title=source["source_id"],
            canonical_url=source["source_url"],
            metadata={
                "human_identity_verified": "true",
                "original_content_accessed": "true",
            },
        )
        for source in sources
    ]
    expected_evidence = [
        ExpectedEvidence(
            evidence_id=f"{item['case_id']}-evidence-{index:02d}",
            source_id=source["source_id"],
            expected_text=source["evidence_excerpt"],
            location_hint=source["evidence_location"],
            semantic_match_allowed=False,
            metadata={"excerpt_sha256": source["evidence_excerpt_sha256"]},
        )
        for index, source in enumerate(sources, start=1)
    ]
    definition = EvaluationCaseDefinition(
        case_id=item["case_id"],
        name=f"Stage 9 locked case {item['case_id']}",
        description="Human-reviewed real-research evaluation case with exact source evidence.",
        difficulty=EvaluationDifficulty.MEDIUM,
        evaluation_input=EvaluationInput(
            research_question=item["research_question"],
            constraints=[*item["prohibited_claims"], *item["expected_uncertainties"]],
            metadata={
                "human_review_decision": "locked",
                "review_sheet_sha256": review["review_sheet_sha256"],
            },
        ),
        expected_outcome=EvaluationExpectedOutcome(
            outcome_id=f"{item['case_id']}-expected-outcome",
            name=f"Expected grounded boundary for {item['case_id']}",
            description="Use the reviewed sources, preserve exact evidence, and disclose limitations.",
            expected_sources=expected_sources,
            expected_evidence=expected_evidence,
            required_report_elements=[
                "Evidence-linked answer",
                "Uncertainty and limitation disclosure",
            ],
            forbidden_report_elements=list(item["prohibited_claims"]),
            metadata={
                "reviewer_id": review["reviewer_id"],
                "reviewed_at": review["reviewed_at"],
            },
        ),
        tags=["stage9", item["domain"], "human-locked"],
        metadata={
            "review_id": review["review_id"],
            "disclosed_limitations": " | ".join(review["disclosed_limitations"]),
        },
    )
    partition = (
        Stage9DatasetPartition.DEVELOPMENT
        if item["case_id"] in DEVELOPMENT_IDS
        else Stage9DatasetPartition.LOCKED
    )
    return Stage9EvaluationCase(
        definition=definition,
        domain=Stage9EvaluationDomain(item["domain"]),
        partition=partition,
        prohibited_claims=tuple(item["prohibited_claims"]),
        expected_uncertainties=tuple(item["expected_uncertainties"]),
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(input_path: Path, output_directory: Path) -> Path:
    locked = _verify_input(input_path)
    cases = tuple(_build_case(item) for item in locked["cases"])
    development = tuple(
        case.definition.case_id
        for case in cases
        if case.partition is Stage9DatasetPartition.DEVELOPMENT
    )
    holdout = tuple(
        case.definition.case_id
        for case in cases
        if case.partition is Stage9DatasetPartition.LOCKED
    )
    if (
        development != ("tech-01", "academic-01", "patent-01", "cross-01")
        or len(holdout) != 6
    ):
        raise LockedDatasetImportError("development/holdout split mismatch")
    if {
        case.domain.value
        for case in cases
        if case.partition is Stage9DatasetPartition.DEVELOPMENT
    } != {"general_technical", "academic", "patent", "cross_source"}:
        raise LockedDatasetImportError("development partition must cover every domain")
    artifact = {
        "artifact_type": "stage9_typed_evaluation_cases",
        "source_dataset_id": locked["dataset_id"],
        "source_dataset_sha256": locked["dataset_sha256"],
        "case_order": list(EXPECTED_CASE_IDS),
        "development_case_ids": list(development),
        "locked_holdout_case_ids": list(holdout),
        "cases": [case.model_dump(mode="json") for case in cases],
        "manifest_status": "runtime_provider_model_price_and_budget_not_yet_locked",
        "external_requests": 0,
    }
    content = (
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )
    output = output_directory / "stage9-typed-evaluation-cases-v1.json"
    _atomic_write(output, content)
    _atomic_write(
        Path(str(output) + ".sha256"),
        f"{hashlib.sha256(content).hexdigest()}  {output.name}\n".encode("ascii"),
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path.home()
        / "다운로드"
        / "aira-stage9-locked-golden-dataset-v1"
        / "stage9-locked-golden-dataset-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / "다운로드" / "aira-stage9-typed-evaluation-cases-v1",
    )
    args = parser.parse_args()
    output = run(args.input, args.output)
    print("=== AIRA Stage 9 locked dataset typed import ===")
    print("source_locked_cases=10")
    print("typed_cases=10")
    print("development_cases=4")
    print("locked_holdout_cases=6")
    print("development_domain_coverage=4/4")
    print("human_lock_status_preserved=true")
    print("manifest_status=RUNTIME_FIELDS_NOT_YET_LOCKED")
    print("repository_files_modified=0")
    print("openai_requests=0")
    print("external_requests=0")
    print(f"output_path={output}")
    print("STAGE9_LOCKED_DATASET_TYPED_IMPORT_RESULT=PASS")


if __name__ == "__main__":
    main()
