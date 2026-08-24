"""Deterministically parse line-bounded answer statements and citation markers."""

from __future__ import annotations

import re

from app.schemas.answer_citation_validation import (
    AnswerCitationValidationRequest,
    AnswerStatement,
)

_CITATION_PATTERN = re.compile(r"\[([A-Za-z]\d+)\]")


class AnswerCitationParseError(ValueError):
    """Raised when the narrow line/marker answer format is invalid."""


class DeterministicAnswerCitationParser:
    """Treat each nonblank answer line as one exact statement."""

    def parse(
        self, *, request: AnswerCitationValidationRequest
    ) -> list[AnswerStatement]:
        if not isinstance(request, AnswerCitationValidationRequest):
            raise TypeError("request must be an AnswerCitationValidationRequest")

        available_ids = {item.citation_id for item in request.context.citations}
        statements: list[AnswerStatement] = []
        offset = 0
        for raw_line in request.answer.splitlines(keepends=True):
            line = raw_line.rstrip("\r\n")
            leading = len(line) - len(line.lstrip())
            stripped_right = line.rstrip()
            if not stripped_right.strip():
                offset += len(raw_line)
                continue
            start = offset + leading
            end = offset + len(stripped_right)
            text = request.answer[start:end]
            cited_ids = [match.group(1) for match in _CITATION_PATTERN.finditer(text)]

            marker_free_text = _CITATION_PATTERN.sub("", text)
            if "[" in marker_free_text or "]" in marker_free_text:
                raise AnswerCitationParseError(
                    "answer statement contains a malformed citation marker"
                )
            if len(cited_ids) != len(set(cited_ids)):
                raise AnswerCitationParseError(
                    "answer statement contains a duplicate citation marker"
                )
            unknown = [value for value in cited_ids if value not in available_ids]
            if unknown:
                raise AnswerCitationParseError(
                    "answer statement references an unknown citation marker"
                )
            statements.append(
                AnswerStatement(
                    statement_id=f"statement-{len(statements) + 1:03d}",
                    text=text,
                    start_character=start,
                    end_character=end,
                    cited_ids=cited_ids,
                )
            )
            if len(statements) > request.budget.maximum_statements:
                raise AnswerCitationParseError(
                    "answer statement count exceeds validation budget"
                )
            offset += len(raw_line)

        if not statements:
            raise AnswerCitationParseError("answer contains no nonblank statements")
        return statements
