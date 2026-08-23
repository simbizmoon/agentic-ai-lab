"""Offline CLI-to-artifact E2E tests for scholarly exact evidence."""

from __future__ import annotations

import json
from pathlib import Path

from app.cli import main
from app.research.scholarly_evidence_cli_handler import ScholarlyEvidenceCliHandler
from app.research.scholarly_evidence_factory import (
    build_openalex_scholarly_evidence_workflow,
)
from app.research.scholarly_identifier_normalizer import (
    normalize_scholarly_identifier,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import (
    ScholarlyProviderUsage,
    ScholarlyRecordFailure,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)
from app.schemas.scholarly_work import (
    ScholarlyAbstract,
    ScholarlyAccess,
    ScholarlyAccessState,
    ScholarlyIdentifierType,
    ScholarlyProviderProvenance,
    ScholarlyVersionType,
    ScholarlyWork,
    ScholarlyWorkType,
)


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self) -> None:
        self.calls: list[ScholarlySearchRequest] = []

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.calls.append(request)
        works = (
            _work(
                "work-with-doi",
                openalex_id="W1001",
                abstract="Exact scholarly abstract with DOI.",
                doi="10.1234/aira.e2e.1",
                digest="a" * 64,
            ),
            _work(
                "work-without-doi",
                openalex_id="W1002",
                abstract="Exact scholarly abstract without DOI.",
                doi=None,
                digest="b" * 64,
            ),
            _work(
                "work-without-abstract",
                openalex_id="W1003",
                abstract=None,
                doi=None,
                digest="c" * 64,
            ),
        )
        failure = ScholarlyRecordFailure(
            provider_position=4,
            provider_record_id="malformed-record-004",
            error_type="RecordValidationError",
            message="Malformed fixture provider record.",
        )
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=ScholarlySearchStatus.PARTIAL,
            works=works,
            record_failures=(failure,),
            usage=ScholarlyProviderUsage(
                request_count=1,
                records_received=4,
                records_accepted=3,
                records_rejected=1,
                duration_ms=1.0,
            ),
        )


def _work(
    work_id: str,
    *,
    openalex_id: str,
    abstract: str | None,
    doi: str | None,
    digest: str,
) -> ScholarlyWork:
    identifiers = [
        normalize_scholarly_identifier(ScholarlyIdentifierType.OPENALEX, openalex_id)
    ]
    if doi is not None:
        identifiers.append(
            normalize_scholarly_identifier(ScholarlyIdentifierType.DOI, doi)
        )
    return ScholarlyWork(
        work_id=work_id,
        title=f"Fixture {work_id}",
        work_type=ScholarlyWorkType.JOURNAL_ARTICLE,
        version_type=ScholarlyVersionType.UNKNOWN,
        identifiers=tuple(identifiers),
        abstract=(
            ScholarlyAbstract(
                text=abstract,
                language="en",
                provider="fixture-provider",
                provider_record_id=openalex_id,
                source_url=f"https://api.example.test/works/{openalex_id}",
            )
            if abstract is not None
            else None
        ),
        access=ScholarlyAccess(
            state=ScholarlyAccessState.METADATA_ONLY,
            landing_page_url=f"https://example.test/works/{openalex_id}",
        ),
        provenance=ScholarlyProviderProvenance(
            provider="fixture-provider",
            provider_record_id=openalex_id,
            request_url=f"https://api.example.test/works/{openalex_id}",
            retrieved_at="2026-08-23T12:00:00+09:00",
            response_sha256=digest,
        ),
    )


def _arguments(output_dir: Path) -> list[str]:
    return [
        "research-scholarly-evidence",
        "--query",
        "bounded scholarly evidence",
        "--maximum-results",
        "4",
        "--maximum-provider-requests",
        "1",
        "--output-dir",
        str(output_dir),
    ]


def _run(tmp_path: Path, provider: FixtureProvider, capsys):
    output_dir = tmp_path / "reports"
    handler = ScholarlyEvidenceCliHandler(
        runtime_factory=lambda request: build_openalex_scholarly_evidence_workflow(
            request, provider=provider
        ),
        request_id_factory=lambda: "e2e-request-001",
        execution_id_factory=lambda: "e2e-execution-001",
    )
    status = main(
        _arguments(output_dir),
        scholarly_evidence_handler=handler,
    )
    return status, output_dir, capsys.readouterr()


def test_cli_to_private_artifacts_preserves_exact_evidence(tmp_path, capsys) -> None:
    provider = FixtureProvider()
    status, output_dir, captured = _run(tmp_path, provider, capsys)
    assert status == 0
    assert len(provider.calls) == 1
    assert provider.calls[0].maximum_provider_requests == 1

    execution_dir = output_dir / "e2e-execution-001"
    markdown_path = execution_dir / "evidence.md"
    json_path = execution_dir / "evidence.json"
    assert execution_dir.stat().st_mode & 0o777 == 0o700
    assert markdown_path.stat().st_mode & 0o777 == 0o600
    assert json_path.stat().st_mode & 0o777 == 0o600

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    evidence = payload["adaptation"]["evidence_set"]["evidence"]
    assert len(evidence) == 2
    for item in evidence:
        assert item["start_character"] == 0
        assert item["end_character"] == len(item["excerpt"])
        assert item["evidence_id"]
        assert item["source_id"]
        assert item["document_id"]
    assert payload["actual_provider_requests"] == 1
    assert payload["records_rejected"] == 1
    assert payload["works_omitted_without_abstract"] == 1
    assert "openai_requests=0" in captured.out
    assert "actual_provider_requests=1" in captured.out
    assert captured.err == ""


def test_markdown_distinguishes_doi_absence_omission_and_rejection(
    tmp_path, capsys
) -> None:
    status, output_dir, _captured = _run(tmp_path, FixtureProvider(), capsys)
    assert status == 0
    markdown = (output_dir / "e2e-execution-001" / "evidence.md").read_text(
        encoding="utf-8"
    )
    assert "DOI: 10.1234/aira.e2e.1" in markdown
    assert "DOI: ABSENT" in markdown
    assert "Abstract evidence: OMITTED (abstract absent)" in markdown
    assert "Provider record ID: malformed-record-004" in markdown
    assert "Error type: RecordValidationError" in markdown
    assert "Response SHA-256: " + "a" * 64 in markdown
    assert "Response SHA-256: " + "b" * 64 in markdown


def test_artifacts_add_no_quality_ranking_or_legal_conclusion(tmp_path, capsys) -> None:
    status, output_dir, _captured = _run(tmp_path, FixtureProvider(), capsys)
    assert status == 0
    markdown = (output_dir / "e2e-execution-001" / "evidence.md").read_text(
        encoding="utf-8"
    )
    payload = json.loads(
        (output_dir / "e2e-execution-001" / "evidence.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(payload).casefold()
    for forbidden in (
        '"winner"',
        '"best_work"',
        '"paper_quality_score"',
        '"citation_impact_score"',
        '"legal_conclusion"',
        '"systematic_review_complete"',
    ):
        assert forbidden not in serialized
    for item in payload["adaptation"]["evidence_set"]["evidence"]:
        assert item["metadata"]["paper_quality_assessment"] == "not_performed"
        assert item["metadata"]["citation_impact_assessment"] == "not_performed"
    assert "does not assess semantic relevance" in markdown
    assert "permission to obtain or use full text" in markdown


def test_invalid_cli_budget_stops_before_provider_and_artifact(
    tmp_path, capsys
) -> None:
    provider = FixtureProvider()
    output_dir = tmp_path / "reports"
    arguments = _arguments(output_dir)
    arguments[arguments.index("--maximum-provider-requests") + 1] = "2"
    status = main(
        arguments,
        scholarly_evidence_handler=ScholarlyEvidenceCliHandler(
            runtime_factory=lambda request: build_openalex_scholarly_evidence_workflow(
                request, provider=provider
            )
        ),
    )
    assert status == 2
    assert provider.calls == []
    assert not output_dir.exists()
    assert "must be exactly 1" in capsys.readouterr().err
