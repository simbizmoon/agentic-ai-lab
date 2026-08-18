"""Command-line interface for the AIRA application."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from app.persistent_cache_maintenance import (
    PersistentCacheMaintenanceService,
    PersistentCachePruneError,
)
from app.rag.embedding_cache_directory import resolve_embedding_cache_directory
from app.research.integrated_research_handler import IntegratedResearchHandler
from app.research.live_research_handler import (
    LiveResearchHandler,
)
from app.research.local_document_access_policy import (
    LocalDocumentAccessGate,
    LocalDocumentAccessPolicy,
    LocalDocumentAccessResult,
)
from app.research.local_external_send_approval import (
    LocalExternalSendApproval,
    LocalExternalSendApprovalError,
)
from app.research.local_research_handler import (
    DEFAULT_MAXIMUM_LOCAL_SOURCE_BYTES,
    LocalResearchHandler,
    SemanticLocalResearchHandler,
)
from app.research.parsed_document_cache_directory import (
    resolve_parsed_document_cache_directory,
)
from app.research.patent_research_cli_handler import PatentResearchCliHandler
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.persistent_cache_status import (
    CacheKind,
    CachePruneOutcome,
    CachePrunePlan,
    CacheStatus,
)

ResearchHandler = Callable[
    [
        str,
        str,
        tuple[LocalDocumentAccessResult, ...],
        Path,
        LocalDocumentAccessPolicy,
        LocalExternalSendApproval | None,
    ],
    int,
]
LiveResearchHandlerType = Callable[
    [str, str, int, int, Path],
    int,
]
IntegratedResearchHandlerType = Callable[
    [
        str,
        str,
        tuple[LocalDocumentAccessResult, ...],
        int,
        int,
        Path,
        LocalDocumentAccessPolicy,
        LocalExternalSendApproval | None,
    ],
    int,
]

PatentResearchHandlerType = Callable[[PatentResearchRequest], int]

_SUPPORTED_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".hwpx",
        ".pdf",
        ".txt",
    }
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the AIRA command-line parser."""

    parser = argparse.ArgumentParser(
        prog="aira",
        description=("AIRA — Agentic Intelligence Research Assistant"),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    research_parser = subparsers.add_parser(
        "research",
        help="Create a grounded report from local documents.",
        description=(
            "Run grounded research using one or more local "
            "Markdown, text, PDF, or HWPX documents."
        ),
    )

    research_parser.add_argument(
        "--mode",
        choices=("deterministic", "semantic"),
        default="deterministic",
        help="Local research analysis mode.",
    )
    research_parser.add_argument(
        "--question",
        required=True,
        help="Research question to answer.",
    )
    research_parser.add_argument(
        "--objective",
        help=(
            "Desired research outcome. When omitted, AIRA "
            "creates a default objective from the question."
        ),
    )
    research_parser.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="PATH",
        help=(
            "Local Markdown, text, PDF, or HWPX source path. "
            "Repeat this option to provide multiple sources."
        ),
    )
    research_parser.add_argument(
        "--allowed-root",
        action="append",
        metavar="PATH",
        help=(
            "Trusted directory containing local research sources. "
            "Repeat this option to allow multiple roots."
        ),
    )
    research_parser.add_argument(
        "--approve-external-send",
        action="store_true",
        help=(
            "Approve sending content derived from the validated local "
            "sources to external AI providers for this semantic execution."
        ),
    )
    research_parser.add_argument(
        "--output-dir",
        default="reports",
        metavar="PATH",
        help="Directory in which research results are stored.",
    )

    integrated_parser = subparsers.add_parser(
        "research-integrated",
        help="Create one grounded report from Web and Local sources.",
        description=(
            "Run semantic research over live Web sources and approved "
            "local Markdown, text, PDF, or HWPX documents."
        ),
    )
    integrated_parser.add_argument(
        "--question", required=True, help="Research question to answer."
    )
    integrated_parser.add_argument(
        "--objective", required=True, help="Desired research outcome."
    )
    integrated_parser.add_argument(
        "--source",
        action="append",
        required=True,
        metavar="PATH",
        help="Approved local source path. Repeat for multiple sources.",
    )
    integrated_parser.add_argument(
        "--allowed-root",
        action="append",
        required=True,
        metavar="PATH",
        help="Trusted local source directory. Repeat for multiple roots.",
    )
    integrated_parser.add_argument(
        "--approve-external-send",
        action="store_true",
        required=True,
        help=(
            "Approve sending content derived from the validated local "
            "sources to external AI providers for this execution."
        ),
    )
    integrated_parser.add_argument(
        "--maximum-sources",
        type=int,
        default=3,
        metavar="COUNT",
        help="Maximum final Web and Local research sources.",
    )
    integrated_parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
        metavar="BYTES",
        help="Maximum response size accepted per Web source.",
    )
    integrated_parser.add_argument(
        "--output-dir",
        default="reports/integrated",
        metavar="PATH",
        help="Directory in which integrated results are stored.",
    )

    live_parser = subparsers.add_parser(
        "research-live",
        help="Create a grounded report from live web sources.",
        description=(
            "Run grounded research using Tavily search and the safe HTTP source reader."
        ),
    )
    live_parser.add_argument(
        "--question",
        required=True,
        help="Research question to answer.",
    )
    live_parser.add_argument(
        "--objective",
        help=(
            "Desired research outcome. When omitted, AIRA "
            "creates a default objective from the question."
        ),
    )
    live_parser.add_argument(
        "--maximum-sources",
        type=int,
        default=3,
        metavar="COUNT",
        help="Maximum number of live sources to read.",
    )
    live_parser.add_argument(
        "--maximum-bytes",
        type=int,
        default=1_000_000,
        metavar="BYTES",
        help="Maximum response size accepted per source.",
    )
    live_parser.add_argument(
        "--output-dir",
        default="reports/live",
        metavar="PATH",
        help="Directory in which live research results are stored.",
    )

    patent_parser = subparsers.add_parser(
        "research-patent",
        help="Run bounded technical-relevance research over patent publications.",
        description=(
            "Search EPO patent publications, evaluate technical relevance, "
            "synthesize evidence-supported findings, and verify the synthesis. "
            "This command does not make patent-law conclusions."
        ),
    )
    patent_parser.add_argument("--question", required=True)
    patent_parser.add_argument("--objective")
    patent_parser.add_argument("--prior-art-cutoff-date", metavar="YYYY-MM-DD")
    patent_parser.add_argument(
        "--maximum-search-results", type=int, default=8, metavar="COUNT"
    )
    patent_parser.add_argument(
        "--maximum-sources", type=int, default=4, metavar="COUNT"
    )
    patent_parser.add_argument(
        "--maximum-bytes", type=int, default=1_000_000, metavar="BYTES"
    )

    cache_parser = subparsers.add_parser(
        "cache",
        help="Inspect or prune persistent AIRA caches.",
        description="Inspect or prune persistent embedding and parsed caches.",
    )
    cache_subparsers = cache_parser.add_subparsers(
        dest="cache_command",
        required=True,
    )
    cache_subparsers.add_parser(
        "status",
        help="Display read-only persistent cache inventory.",
    )
    prune_parser = cache_subparsers.add_parser(
        "prune",
        help="Plan or execute oldest-successful-write-first cache pruning.",
    )
    prune_kind = prune_parser.add_mutually_exclusive_group(required=True)
    prune_kind.add_argument(
        "--embedding",
        action="store_true",
        help="Prune valid final embedding cache entries.",
    )
    prune_kind.add_argument(
        "--parsed",
        action="store_true",
        help="Prune valid final parsed-document cache entries.",
    )
    prune_parser.add_argument(
        "--target-bytes",
        required=True,
        type=int,
        metavar="BYTES",
        help="Target total bytes for valid final cache entries.",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display the deterministic plan without deleting entries.",
    )

    return parser


def default_objective(question: str) -> str:
    """Create a valid default research objective."""

    normalized_question = question.strip()

    return (
        "Produce a grounded answer with traceable evidence "
        f"for the following question: {normalized_question}"
    )


def validate_question(value: str) -> str:
    """Validate and normalize a research question."""

    normalized = value.strip()

    if len(normalized) < 10:
        raise ValueError("question must contain at least 10 characters")

    return normalized


def validate_objective(
    value: str | None,
    *,
    question: str,
) -> str:
    """Validate or generate the research objective."""

    normalized = value.strip() if value is not None else default_objective(question)

    if len(normalized) < 15:
        raise ValueError("objective must contain at least 15 characters")

    if " ".join(normalized.casefold().split()) == (
        " ".join(question.casefold().split())
    ):
        raise ValueError("objective must not repeat the question")

    return normalized


def validate_sources(
    values: Sequence[str],
) -> tuple[Path, ...]:
    """Validate local research source paths."""

    sources: list[Path] = []
    normalized_paths: set[Path] = set()

    for value in values:
        source = Path(value).expanduser()

        if not source.exists():
            raise ValueError(f"source does not exist: {source}")

        if not source.is_file():
            raise ValueError(f"source is not a file: {source}")

        if source.suffix.casefold() not in (_SUPPORTED_SOURCE_SUFFIXES):
            raise ValueError(
                f"source must be a Markdown, text, PDF, or HWPX file: {source}"
            )

        resolved = source.resolve()

        if resolved in normalized_paths:
            raise ValueError(f"duplicate source path: {source}")

        normalized_paths.add(resolved)
        sources.append(source)

    return tuple(sources)


def validate_local_access_policy(
    values: Sequence[str] | None,
) -> LocalDocumentAccessPolicy:
    """Build the explicit Local Research source trust policy."""

    if not values:
        raise ValueError("at least one allowed root is required")

    return LocalDocumentAccessPolicy(
        allowed_roots=tuple(Path(value).expanduser() for value in values),
        maximum_file_bytes=DEFAULT_MAXIMUM_LOCAL_SOURCE_BYTES,
    )


def validate_output_dir(value: str) -> Path:
    """Validate and normalize the output directory."""

    output_dir = Path(value).expanduser()

    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output path is not a directory: {output_dir}")

    return output_dir.resolve()


def validate_optional_iso_date(
    value: str | None,
    *,
    name: str,
) -> date | None:
    """Parse an optional ISO date."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    try:
        return date.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{name} must use YYYY-MM-DD format") from error


def validate_positive_integer(
    value: int,
    *,
    name: str,
) -> int:
    """Require a positive CLI integer."""

    if value < 1:
        raise ValueError(f"{name} must be greater than zero")

    return value


def validate_nonnegative_integer(value: int, *, name: str) -> int:
    """Require a nonnegative CLI integer without boolean coercion."""

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def run_cache_status_command(
    *, maintenance_service: PersistentCacheMaintenanceService
) -> int:
    """Display read-only inventory for both persistent caches."""

    for cache_kind, directory in (
        (CacheKind.EMBEDDING, resolve_embedding_cache_directory()),
        (CacheKind.PARSED, resolve_parsed_document_cache_directory()),
    ):
        status = maintenance_service.status(
            cache_kind=cache_kind,
            directory=directory,
        )
        _print_cache_status(status)
    return 0


def run_cache_prune_command(
    namespace: argparse.Namespace,
    *,
    maintenance_service: PersistentCacheMaintenanceService,
) -> int:
    """Plan or execute pruning through the maintenance domain service."""

    target_bytes = validate_nonnegative_integer(
        namespace.target_bytes,
        name="target_bytes",
    )
    cache_kind = CacheKind.EMBEDDING if namespace.embedding else CacheKind.PARSED
    directory = (
        resolve_embedding_cache_directory()
        if cache_kind is CacheKind.EMBEDDING
        else resolve_parsed_document_cache_directory()
    )
    status = maintenance_service.status(cache_kind=cache_kind, directory=directory)
    plan = maintenance_service.plan_prune(
        status=status,
        target_entry_bytes_total=target_bytes,
    )
    if namespace.dry_run:
        print(f"AIRA cache prune dry-run plan: {cache_kind.value}")
        _print_prune_plan(plan)
        print("files_deleted=0")
        return 0

    try:
        result = maintenance_service.execute_prune(plan=plan)
    except PersistentCachePruneError as error:
        state = "partial-failure" if error.deleted_entry_count else "failure"
        print(f"AIRA cache prune {state}: {cache_kind.value}", file=sys.stderr)
        print(
            f"deleted_entries={error.deleted_entry_count}",
            file=sys.stderr,
        )
        print(f"deleted_bytes={error.deleted_entry_bytes}", file=sys.stderr)
        raise

    post_status = maintenance_service.status(
        cache_kind=cache_kind,
        directory=directory,
    )
    print(f"AIRA cache prune result: {cache_kind.value}")
    print(f"planned_entries={result.planned_entry_count}")
    print(f"planned_bytes={result.planned_entry_bytes}")
    print(f"deleted_entries={result.deleted_entry_count}")
    print(f"deleted_bytes={result.deleted_entry_bytes}")
    print(f"skipped_entries={result.skipped_entry_count}")
    outcomes = Counter(item.outcome for item in result.items)
    for outcome in CachePruneOutcome:
        print(f"outcome_{outcome.value}={outcomes[outcome]}")
    print(f"post_valid_entries={post_status.valid_entry_count}")
    print(f"post_valid_bytes={post_status.valid_entry_bytes}")
    return 0


def _print_cache_status(status: CacheStatus) -> None:
    print(f"AIRA cache status: {status.cache_kind.value}")
    print(f"directory={status.directory}")
    print(f"directory_exists={str(status.directory_exists).lower()}")
    print(f"valid_entries={status.valid_entry_count}")
    print(f"valid_bytes={status.valid_entry_bytes}")
    print(f"corrupt_entries={status.corrupt_entry_count}")
    print(f"corrupt_bytes={status.corrupt_entry_bytes}")
    print(f"lock_files={status.lock_file_count}")
    print(f"lock_bytes={status.lock_file_bytes}")
    print(f"temporary_files={status.temporary_file_count}")
    print(f"temporary_bytes={status.temporary_file_bytes}")
    print(f"unknown_targets={status.unknown_target_count}")
    print(f"unknown_bytes={status.unknown_target_bytes}")
    oldest = status.oldest_valid_entry_mtime_ns
    newest = status.newest_valid_entry_mtime_ns
    oldest_value = str(oldest) if oldest is not None else "none"
    newest_value = str(newest) if newest is not None else "none"
    print(f"oldest_valid_entry_mtime_ns={oldest_value}")
    print(f"newest_valid_entry_mtime_ns={newest_value}")


def _print_prune_plan(plan: CachePrunePlan) -> None:
    print(f"observed_valid_entries={plan.observed_valid_entry_count}")
    print(f"observed_valid_bytes={plan.observed_valid_entry_bytes}")
    print(f"target_bytes={plan.target_entry_bytes_total}")
    print(f"selected_entries={plan.selected_entry_count}")
    print(f"selected_bytes={plan.selected_entry_bytes}")
    print(
        f"expected_remaining_valid_entries={plan.expected_remaining_valid_entry_count}"
    )
    print(f"expected_remaining_valid_bytes={plan.expected_remaining_valid_entry_bytes}")


def run_research_command(
    namespace: argparse.Namespace,
    *,
    research_handler: ResearchHandler,
) -> int:
    """Validate and execute one local research command."""

    question = validate_question(namespace.question)
    objective = validate_objective(
        namespace.objective,
        question=question,
    )
    sources = validate_sources(namespace.source)
    access_policy = validate_local_access_policy(namespace.allowed_root)
    access_gate = LocalDocumentAccessGate(access_policy)
    access_results = tuple(access_gate.validate(source) for source in sources)
    external_send_approval: LocalExternalSendApproval | None = None
    if namespace.approve_external_send:
        if namespace.mode != "semantic":
            raise LocalExternalSendApprovalError(
                "--approve-external-send is only valid with --mode semantic"
            )
        external_send_approval = LocalExternalSendApproval.for_semantic_local_research(
            access_results
        )
    elif namespace.mode == "semantic":
        raise LocalExternalSendApprovalError(
            "explicit external-send approval is required for semantic local research"
        )
    output_dir = validate_output_dir(namespace.output_dir)

    return research_handler(
        question,
        objective,
        access_results,
        output_dir,
        access_policy,
        external_send_approval,
    )


def run_live_research_command(
    namespace: argparse.Namespace,
    *,
    live_research_handler: LiveResearchHandlerType,
) -> int:
    """Validate and execute one live research command."""

    question = validate_question(namespace.question)
    objective = validate_objective(
        namespace.objective,
        question=question,
    )
    maximum_sources = validate_positive_integer(
        namespace.maximum_sources,
        name="maximum_sources",
    )
    maximum_bytes = validate_positive_integer(
        namespace.maximum_bytes,
        name="maximum_bytes",
    )

    if maximum_bytes < 1_024:
        raise ValueError("maximum_bytes must be at least 1024")
    output_dir = validate_output_dir(namespace.output_dir)

    return live_research_handler(
        question,
        objective,
        maximum_sources,
        maximum_bytes,
        output_dir,
    )


def run_patent_research_command(
    namespace: argparse.Namespace,
    *,
    patent_research_handler: PatentResearchHandlerType,
) -> int:
    """Validate and execute one bounded patent technical research command."""

    question = validate_question(namespace.question)
    objective = validate_objective(namespace.objective, question=question)
    request = PatentResearchRequest(
        question=question,
        objective=objective,
        prior_art_cutoff_date=validate_optional_iso_date(
            namespace.prior_art_cutoff_date,
            name="prior_art_cutoff_date",
        ),
        maximum_search_results=validate_positive_integer(
            namespace.maximum_search_results,
            name="maximum_search_results",
        ),
        maximum_sources=validate_positive_integer(
            namespace.maximum_sources,
            name="maximum_sources",
        ),
        maximum_bytes=validate_positive_integer(
            namespace.maximum_bytes,
            name="maximum_bytes",
        ),
    )
    return patent_research_handler(request)


def run_integrated_research_command(
    namespace: argparse.Namespace,
    *,
    integrated_research_handler: IntegratedResearchHandlerType,
) -> int:
    """Validate and execute one approved integrated research command."""
    question = validate_question(namespace.question)
    objective = validate_objective(namespace.objective, question=question)
    sources = validate_sources(namespace.source)
    access_policy = validate_local_access_policy(namespace.allowed_root)
    access_gate = LocalDocumentAccessGate(access_policy)
    access_results = tuple(access_gate.validate(source) for source in sources)
    if not namespace.approve_external_send:
        raise LocalExternalSendApprovalError(
            "explicit external-send approval is required for integrated research"
        )
    approval = LocalExternalSendApproval.for_integrated_web_local_research(
        access_results
    )
    maximum_sources = validate_positive_integer(
        namespace.maximum_sources, name="maximum_sources"
    )
    maximum_bytes = validate_positive_integer(
        namespace.maximum_bytes, name="maximum_bytes"
    )
    if maximum_bytes < 1_024:
        raise ValueError("maximum_bytes must be at least 1024")
    output_dir = validate_output_dir(namespace.output_dir)
    return integrated_research_handler(
        question,
        objective,
        access_results,
        maximum_sources,
        maximum_bytes,
        output_dir,
        access_policy,
        approval,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    research_handler: ResearchHandler | None = None,
    semantic_research_handler: ResearchHandler | None = None,
    live_research_handler: (LiveResearchHandlerType | None) = None,
    integrated_research_handler: (IntegratedResearchHandlerType | None) = None,
    patent_research_handler: (PatentResearchHandlerType | None) = None,
    cache_maintenance_service: PersistentCacheMaintenanceService | None = None,
) -> int:
    """Run the AIRA command-line interface."""

    parser = build_parser()
    namespace = parser.parse_args(argv)

    try:
        if namespace.command == "research":
            return run_research_command(
                namespace,
                research_handler=(
                    (semantic_research_handler or SemanticLocalResearchHandler())
                    if namespace.mode == "semantic"
                    else (research_handler or LocalResearchHandler())
                ),
            )

        if namespace.command == "research-integrated":
            return run_integrated_research_command(
                namespace,
                integrated_research_handler=(
                    integrated_research_handler or IntegratedResearchHandler()
                ),
            )

        if namespace.command == "research-live":
            return run_live_research_command(
                namespace,
                live_research_handler=(live_research_handler or LiveResearchHandler()),
            )

        if namespace.command == "research-patent":
            return run_patent_research_command(
                namespace,
                patent_research_handler=(
                    patent_research_handler or PatentResearchCliHandler()
                ),
            )

        if namespace.command == "cache":
            maintenance_service = (
                cache_maintenance_service or PersistentCacheMaintenanceService()
            )
            if namespace.cache_command == "status":
                return run_cache_status_command(
                    maintenance_service=maintenance_service,
                )
            if namespace.cache_command == "prune":
                return run_cache_prune_command(
                    namespace,
                    maintenance_service=maintenance_service,
                )

        parser.error(f"unsupported command: {namespace.command}")
    except (RuntimeError, ValueError) as error:
        print(
            f"aira: error: {error}",
            file=sys.stderr,
        )
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
