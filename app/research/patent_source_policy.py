"""Exact source-family policy for the first patent vertical slice."""

from __future__ import annotations

from urllib.parse import urlsplit

WIPO_PATENTSCOPE_SOURCE_FAMILY = "wipo_patentscope"
WIPO_PATENTSCOPE_HOSTNAME = "patentscope.wipo.int"
EPO_OPS_SOURCE_FAMILY = "epo_ops"
EPO_OPS_HOSTNAME = "ops.epo.org"

_SOURCE_FAMILY_BY_HOSTNAME = {
    WIPO_PATENTSCOPE_HOSTNAME: WIPO_PATENTSCOPE_SOURCE_FAMILY,
    EPO_OPS_HOSTNAME: EPO_OPS_SOURCE_FAMILY,
}


def source_family_for_url(source_url: str) -> str:
    """Return the accepted patent source family for one safe HTTPS URL.

    This is a syntactic source policy only. It performs no network request and
    does not turn a discovered URL into verified patent metadata.
    """

    if not isinstance(source_url, str):
        raise TypeError("source_url must be a string")
    if not source_url.strip():
        raise ValueError("source_url must not be blank")
    if source_url != source_url.strip():
        raise ValueError("source_url must not contain surrounding whitespace")

    parsed = urlsplit(source_url)
    if parsed.scheme.casefold() != "https":
        raise ValueError("patent source URL must use https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("patent source URL must not contain credentials")
    if parsed.port is not None:
        raise ValueError("patent source URL must not contain a port")

    hostname = (parsed.hostname or "").casefold()
    source_family = _SOURCE_FAMILY_BY_HOSTNAME.get(hostname)
    if source_family is None:
        raise ValueError("patent source URL host is not accepted")

    return source_family


def validate_patent_source_url(source_url: str) -> None:
    """Validate one URL against the exact accepted patent-source policy."""

    source_family_for_url(source_url)
