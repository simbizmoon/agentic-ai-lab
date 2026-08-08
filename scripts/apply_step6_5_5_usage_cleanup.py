from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    citation = ROOT / "app/research/semantic_citation_verification_service.py"
    text = citation.read_text(encoding="utf-8")

    text = text.replace(
        "        usage = BudgetUsage()\n        usage = BudgetUsage()\n",
        "        usage = BudgetUsage()\n",
        1,
    )

    duplicate_record = '''                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(result.usage.total_tokens if result.usage is not None else 0),
                    elapsed_seconds=result.elapsed_seconds,
                )
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(result.usage.total_tokens if result.usage is not None else 0),
                    elapsed_seconds=result.elapsed_seconds,
                )
'''
    single_record = '''                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(
                        result.usage.total_tokens
                        if result.usage is not None
                        else 0
                    ),
                    elapsed_seconds=result.elapsed_seconds,
                )
'''
    if duplicate_record not in text:
        raise RuntimeError("duplicate citation usage block not found")
    text = text.replace(duplicate_record, single_record, 1)

    text = text.replace(
        "        self._last_usage = usage\n        self._last_usage = usage\n",
        "        self._last_usage = usage\n",
        1,
    )
    citation.write_text(text, encoding="utf-8")

    relevance = ROOT / "app/research/claim_relevance_evaluation_service.py"
    text = relevance.read_text(encoding="utf-8")
    text = text.replace(
        "        self._last_usage = usage\n        self._last_usage = usage\n",
        "        self._last_usage = usage\n",
        1,
    )
    relevance.write_text(text, encoding="utf-8")

    print("Step 6.5.5 usage cleanup applied.")


if __name__ == "__main__":
    main()
