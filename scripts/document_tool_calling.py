"""Run the registered document Tool workflow from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import load_settings
from app.services.document_statistics_tool_calling import (
    ToolCallingError,
    run_document_tool_workflow,
)
from app.services.openai_client import create_openai_client


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Let the model choose one registered document Tool."
        )
    )
    parser.add_argument(
        "document_path",
        type=Path,
        help="UTF-8 text document to analyze.",
    )
    parser.add_argument(
        "--request",
        required=True,
        help=(
            "Instruction describing what should be done "
            "with the document."
        ),
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Print structured Workflow events.",
    )

    return parser.parse_args()


def read_document(path: Path) -> str:
    """Read and validate a UTF-8 text document."""

    if not path.is_file():
        raise ValueError(
            f"document file does not exist: {path}"
        )

    document_text = path.read_text(encoding="utf-8")

    if not document_text.strip():
        raise ValueError("document must not be empty")

    return document_text


def build_user_request(
    *,
    request: str,
    document_text: str,
) -> str:
    """Combine the user's instruction with the document."""

    if not request.strip():
        raise ValueError("request must not be empty")

    return (
        f"{request.strip()}\n\n"
        "Document:\n"
        f"{document_text}"
    )


def print_workflow_events(events: list[object]) -> None:
    """Print structured Workflow events."""

    print("Events:")

    for index, event in enumerate(events, start=1):
        event_type = event.event_type
        event_value = event_type.value
        tool_name = event.tool_name
        details = event.details

        line = (
            f"{index}. {event_value} "
            f"({event.elapsed_ms:.3f} ms)"
        )

        if tool_name is not None:
            line += f" [{tool_name}]"

        print(line)

        if details:
            for key, value in details.items():
                print(f"   - {key}: {value}")

    print()


def main() -> int:
    """Run the document Tool workflow."""

    try:
        args = parse_args()
        document_text = read_document(args.document_path)
        user_request = build_user_request(
            request=args.request,
            document_text=document_text,
        )

        settings = load_settings()
        client = create_openai_client(settings)

        result = run_document_tool_workflow(
            client=client,
            model=settings.openai_model,
            user_request=user_request,
        )

    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except ToolCallingError as exc:
        print(
            f"Tool workflow error [{exc.code.value}]: "
            f"{exc.safe_message}",
            file=sys.stderr,
        )
        return 3
    if args.show_events:
        print_workflow_events(result.events)

    if result.tool_used:
        print("Observation:")
        print(f"- Tool: {result.tool_name}")

        if result.observation is not None:
            for key, value in result.observation.items():
                print(f"- {key}: {value}")

        print()

    print("Final Answer:")
    print(result.final_answer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
