"""Run the AIRA single document-statistics tool workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import load_settings
from app.services.document_statistics_tool_calling import (
    ToolCallingError,
    ToolCallingErrorCode,
    answer_with_document_statistics_tool,
)
from app.services.openai_client import create_openai_client


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Ask AIRA to use a local Tool to calculate "
            "document statistics."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help="UTF-8 text document to analyze.",
    )
    return parser.parse_args()


def exit_code_for_tool_error(error: ToolCallingError) -> int:
    """Map a classified Tool Calling error to a CLI exit code."""

    if error.code in {
        ToolCallingErrorCode.TOOL_CALL_FAILED,
        ToolCallingErrorCode.TOOL_CORRECTION_FAILED,
    }:
        return 3

    if error.code in {
        ToolCallingErrorCode.INVALID_RESPONSE,
        ToolCallingErrorCode.MULTIPLE_TOOL_CALLS,
        ToolCallingErrorCode.INVALID_FUNCTION_CALL,
        ToolCallingErrorCode.MISSING_FINAL_TEXT,
    }:
        return 4

    return 1


def main() -> int:
    """Run the single-tool workflow."""

    args = parse_args()

    try:
        document_text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"Failed to read document: {exc}", file=sys.stderr)
        return 2

    if not document_text.strip():
        print(
            "Document must contain non-whitespace text.",
            file=sys.stderr,
        )
        return 2

    try:
        settings = load_settings()
        client = create_openai_client(settings)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    user_request = (
        "Use the document statistics tool to report the exact "
        "character, word, and line counts for this document.\n\n"
        f"<document>\n{document_text}\n</document>"
    )

    try:
        answer = answer_with_document_statistics_tool(
            client=client,
            model=settings.openai_model,
            user_request=user_request,
        )
    except ToolCallingError as exc:
        print(
            f"Tool workflow failed [{exc.code.value}]: "
            f"{exc.safe_message}",
            file=sys.stderr,
        )
        return exit_code_for_tool_error(exc)
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
