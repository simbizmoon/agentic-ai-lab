"""Deterministic scholarly identifier normalization and deduplication."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit

from app.schemas.scholarly_work import (
    ScholarlyIdentifier,
    ScholarlyIdentifierType,
    ScholarlyWork,
)


class ScholarlyIdentifierNormalizationError(ValueError):
    """Raised when an identifier cannot be normalized safely."""


_DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ARXIV_MODERN_PATTERN = re.compile(r"\d{4}\.\d{4,5}(?:v\d+)?", re.IGNORECASE)
_ARXIV_LEGACY_PATTERN = re.compile(
    r"[a-z][a-z0-9.-]*/\d{7}(?:v\d+)?",
    re.IGNORECASE,
)
_DIGITS_PATTERN = re.compile(r"\d+")
_PMCID_PATTERN = re.compile(r"PMC\d+", re.IGNORECASE)
_OPENALEX_PATTERN = re.compile(r"W\d+", re.IGNORECASE)


def normalize_scholarly_identifier(
    identifier_type: ScholarlyIdentifierType,
    value: str,
    *,
    provider: str | None = None,
) -> ScholarlyIdentifier:
    """Return a strict identifier with a deterministic normalized value."""

    raw = value.strip()
    if not raw:
        raise ScholarlyIdentifierNormalizationError(
            "identifier value must not be blank"
        )

    normalizers = {
        ScholarlyIdentifierType.DOI: _normalize_doi,
        ScholarlyIdentifierType.ARXIV: _normalize_arxiv,
        ScholarlyIdentifierType.PMID: _normalize_pmid,
        ScholarlyIdentifierType.PMCID: _normalize_pmcid,
        ScholarlyIdentifierType.OPENALEX: _normalize_openalex,
    }

    if identifier_type in normalizers:
        if provider is not None:
            raise ScholarlyIdentifierNormalizationError(
                "provider is only valid for provider identifiers"
            )
        normalized = normalizers[identifier_type](raw)
    elif identifier_type is ScholarlyIdentifierType.PROVIDER:
        if provider is None or not provider.strip():
            raise ScholarlyIdentifierNormalizationError(
                "provider identifier requires provider"
            )
        normalized = raw
        provider = provider.strip()
    elif identifier_type is ScholarlyIdentifierType.OTHER:
        if provider is not None:
            raise ScholarlyIdentifierNormalizationError(
                "provider is only valid for provider identifiers"
            )
        normalized = raw
    else:  # pragma: no cover - exhaustive guard for future enum values
        raise ScholarlyIdentifierNormalizationError(
            f"unsupported identifier type: {identifier_type}"
        )

    return ScholarlyIdentifier(
        identifier_type=identifier_type,
        value=raw,
        normalized_value=normalized,
        provider=provider,
    )


def scholarly_identifier_identity_key(
    identifier: ScholarlyIdentifier,
) -> tuple[str, ...]:
    """Return the exact key used for deterministic duplicate matching."""

    if identifier.identifier_type is ScholarlyIdentifierType.PROVIDER:
        if identifier.provider is None:  # protected by the schema
            raise ScholarlyIdentifierNormalizationError(
                "provider identifier requires provider"
            )
        return (
            identifier.identifier_type.value,
            identifier.provider.strip().casefold(),
            identifier.normalized_value.strip(),
        )

    return (
        identifier.identifier_type.value,
        identifier.normalized_value.strip().casefold(),
    )


def are_scholarly_works_duplicates(
    left: ScholarlyWork,
    right: ScholarlyWork,
) -> bool:
    """Return true only when two records share an exact identity key."""

    left_keys = {
        scholarly_identifier_identity_key(identifier) for identifier in left.identifiers
    }
    right_keys = {
        scholarly_identifier_identity_key(identifier)
        for identifier in right.identifiers
    }
    return bool(left_keys & right_keys)


def group_duplicate_scholarly_works(
    works: Iterable[ScholarlyWork],
) -> tuple[tuple[ScholarlyWork, ...], ...]:
    """Group works by exact identifiers, including transitive matches."""

    ordered = tuple(works)
    work_ids = [work.work_id.strip().casefold() for work in ordered]
    if len(set(work_ids)) != len(work_ids):
        raise ValueError("work IDs must be unique")

    parents = list(range(len(ordered)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    owner_by_key: dict[tuple[str, ...], int] = {}
    for index, work in enumerate(ordered):
        for identifier in work.identifiers:
            key = scholarly_identifier_identity_key(identifier)
            previous = owner_by_key.setdefault(key, index)
            union(previous, index)

    members_by_root: dict[int, list[ScholarlyWork]] = defaultdict(list)
    for index, work in enumerate(ordered):
        members_by_root[find(index)].append(work)

    return tuple(tuple(members) for members in members_by_root.values())


def _normalize_doi(value: str) -> str:
    candidate = unquote(value).strip()
    lowered = candidate.casefold()
    if lowered.startswith("doi:"):
        candidate = candidate[4:].strip()
    else:
        parsed = urlsplit(candidate)
        if parsed.scheme or parsed.netloc:
            host = (parsed.hostname or "").casefold()
            if parsed.scheme.casefold() not in {"http", "https"}:
                raise ScholarlyIdentifierNormalizationError("DOI URL must use HTTP(S)")
            if host not in {"doi.org", "dx.doi.org"}:
                raise ScholarlyIdentifierNormalizationError(
                    "DOI URL must use doi.org or dx.doi.org"
                )
            candidate = unquote(parsed.path).lstrip("/").strip()
    normalized = candidate.casefold()
    if not _DOI_PATTERN.fullmatch(normalized):
        raise ScholarlyIdentifierNormalizationError("invalid DOI")
    return normalized


def _normalize_arxiv(value: str) -> str:
    candidate = unquote(value).strip()
    lowered = candidate.casefold()
    if lowered.startswith("arxiv:"):
        candidate = candidate[6:].strip()
    else:
        parsed = urlsplit(candidate)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme.casefold() not in {"http", "https"}:
                raise ScholarlyIdentifierNormalizationError(
                    "arXiv URL must use HTTP(S)"
                )
            if (parsed.hostname or "").casefold() not in {
                "arxiv.org",
                "www.arxiv.org",
            }:
                raise ScholarlyIdentifierNormalizationError(
                    "arXiv URL must use arxiv.org"
                )
            path = unquote(parsed.path).strip("/")
            if path.casefold().startswith("abs/"):
                candidate = path[4:]
            elif path.casefold().startswith("pdf/"):
                candidate = path[4:]
                if candidate.casefold().endswith(".pdf"):
                    candidate = candidate[:-4]
            else:
                raise ScholarlyIdentifierNormalizationError(
                    "arXiv URL must contain /abs/ or /pdf/"
                )
    normalized = candidate.casefold()
    if not (
        _ARXIV_MODERN_PATTERN.fullmatch(normalized)
        or _ARXIV_LEGACY_PATTERN.fullmatch(normalized)
    ):
        raise ScholarlyIdentifierNormalizationError("invalid arXiv identifier")
    return normalized


def _normalize_pmid(value: str) -> str:
    candidate = value.strip()
    if candidate.casefold().startswith("pmid:"):
        candidate = candidate[5:].strip()
    if not _DIGITS_PATTERN.fullmatch(candidate):
        raise ScholarlyIdentifierNormalizationError("invalid PMID")
    return candidate.lstrip("0") or "0"


def _normalize_pmcid(value: str) -> str:
    candidate = value.strip()
    if candidate.casefold().startswith("pmcid:"):
        candidate = candidate[6:].strip()
    if not candidate.casefold().startswith("pmc"):
        candidate = f"PMC{candidate}"
    normalized = candidate.upper()
    if not _PMCID_PATTERN.fullmatch(normalized):
        raise ScholarlyIdentifierNormalizationError("invalid PMCID")
    digits = normalized[3:].lstrip("0") or "0"
    return f"PMC{digits}"


def _normalize_openalex(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme.casefold() not in {"http", "https"}:
            raise ScholarlyIdentifierNormalizationError("OpenAlex URL must use HTTP(S)")
        if (parsed.hostname or "").casefold() != "openalex.org":
            raise ScholarlyIdentifierNormalizationError(
                "OpenAlex URL must use openalex.org"
            )
        candidate = parsed.path.strip("/")
    normalized = candidate.upper()
    if not _OPENALEX_PATTERN.fullmatch(normalized):
        raise ScholarlyIdentifierNormalizationError("invalid OpenAlex work ID")
    return normalized
