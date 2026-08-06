"""Command-line interface for the AIRA application."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from app.research.live_research_handler import (
    LiveResearchHandler,
)
from app.research.local_research_handler import (
    LocalResearchHandler,
)

ResearchHandler = Callable[
    [str, str, tuple[Path, ...], Path],
    int,
]
LiveResearchHandlerType = Callable[
    [str, str, int, int, Path],
    int,
]

_SUPPORTED_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
    }
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the AIRA command-line parser."""

    parser = argparse.ArgumentParser(
        prog="aira",
        description=(
            "AIRA — Agentic Intelligence Research Assistant"
        ),
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
            "Markdown or text documents."
        ),
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
            "Local Markdown or text source path. "
            "Repeat this option to provide multiple sources."
        ),
    )
    research_parser.add_argument(
        "--output-dir",
        default="reports",
        metavar="PATH",
        help="Directory in which research results are stored.",
    )

    live_parser = subparsers.add_parser(
        "research-live",
        help="Create a grounded report from live web sources.",
        description=(
            "Run grounded research using Tavily search and "
            "the safe HTTP source reader."
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
        raise ValueError(
            "question must contain at least 10 characters"
        )

    return normalized


def validate_objective(
    value: str | None,
    *,
    question: str,
) -> str:
    """Validate or generate the research objective."""

    normalized = (
        value.strip()
        if value is not None
        else default_objective(question)
    )

    if len(normalized) < 15:
        raise ValueError(
            "objective must contain at least 15 characters"
        )

    if " ".join(normalized.casefold().split()) == (
        " ".join(question.casefold().split())
    ):
        raise ValueError(
            "objective must not repeat the question"
        )

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
            raise ValueError(
                f"source does not exist: {source}"
            )

        if not source.is_file():
            raise ValueError(
                f"source is not a file: {source}"
            )

        if source.suffix.casefold() not in (
            _SUPPORTED_SOURCE_SUFFIXES
        ):
            raise ValueError(
                "source must be a Markdown or text file: "
                f"{source}"
            )

        resolved = source.resolve()

        if resolved in normalized_paths:
            raise ValueError(
                f"duplicate source path: {source}"
            )

        normalized_paths.add(resolved)
        sources.append(resolved)

    return tuple(sources)


def validate_output_dir(value: str) -> Path:
    """Validate and normalize the output directory."""

    output_dir = Path(value).expanduser()

    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(
            f"output path is not a directory: {output_dir}"
        )

    return output_dir.resolve()


def validate_positive_integer(
    value: int,
    *,
    name: str,
) -> int:
    """Require a positive CLI integer."""

    if value < 1:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


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
    output_dir = validate_output_dir(namespace.output_dir)

    return research_handler(
        question,
        objective,
        sources,
        output_dir,
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
        raise ValueError(
            "maximum_bytes must be at least 1024"
        )
    output_dir = validate_output_dir(namespace.output_dir)

    return live_research_handler(
        question,
        objective,
        maximum_sources,
        maximum_bytes,
        output_dir,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    research_handler: ResearchHandler | None = None,
    live_research_handler: (
        LiveResearchHandlerType | None
    ) = None,
) -> int:
    """Run the AIRA command-line interface."""

    parser = build_parser()
    namespace = parser.parse_args(argv)

    try:
        if namespace.command == "research":
            return run_research_command(
                namespace,
                research_handler=(
                    research_handler
                    or LocalResearchHandler()
                ),
            )

        if namespace.command == "research-live":
            return run_live_research_command(
                namespace,
                live_research_handler=(
                    live_research_handler
                    or LiveResearchHandler()
                ),
            )

        parser.error(
            f"unsupported command: {namespace.command}"
        )
    except (RuntimeError, ValueError) as error:
        print(
            f"aira: error: {error}",
            file=sys.stderr,
        )
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
