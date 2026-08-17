"""Bounded CQL search and safe bibliographic XML parsing for EPO OPS."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote, urlencode
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from app.research.epo_ops_client import EpoOpsClient, EpoOpsHttpResponse
from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsBibliographicSearchResult,
    EpoOpsDocumentIdType,
    EpoOpsSearchRequest,
)

EPO_OPS_SEARCH_URL = (
    "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
)
EPO_OPS_SEARCH_ACCEPT = "application/exchange+xml"

OPS_NAMESPACE = "http://ops.epo.org"
EXCHANGE_NAMESPACE = "http://www.epo.org/exchange"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
NAMESPACES = {
    "ops": OPS_NAMESPACE,
    "exchange": EXCHANGE_NAMESPACE,
}

_DOCDB_COUNTRY_PATTERN = re.compile(r"[A-Z]{2}", re.ASCII)
_DOCDB_NUMBER_PATTERN = re.compile(r"[A-Z0-9]+", re.ASCII)
_DOCDB_KIND_PATTERN = re.compile(r"[A-Z][A-Z0-9]?", re.ASCII)


class EpoOpsSearchError(RuntimeError):
    """Base error for the EPO bibliographic search boundary."""


class EpoOpsXmlParseError(EpoOpsSearchError):
    """OPS returned malformed or unsafe XML."""


class EpoOpsBibliographicResponseError(EpoOpsSearchError):
    """OPS returned XML outside the accepted bibliographic contract."""


class EpoOpsBibliographicSearcher:
    """Execute bounded OPS CQL search and parse unverified records."""

    def __init__(self, *, client: EpoOpsClient) -> None:
        self._client = client

    def search(
        self,
        request: EpoOpsSearchRequest,
    ) -> EpoOpsBibliographicSearchResult:
        """Return parsed bibliographic records without VERIFIED product mapping."""

        endpoint = self._search_endpoint(request)
        response = self._client.authenticated_get_response(
            endpoint=endpoint,
            accept=EPO_OPS_SEARCH_ACCEPT,
            extra_headers={"X-OPS-Range": f"1-{request.maximum_results}"},
        )
        self._validate_xml_content(response)
        records = self._parse_records(response.body, source_endpoint=endpoint)
        return EpoOpsBibliographicSearchResult(
            request=request,
            records=records,
        )

    @staticmethod
    def _search_endpoint(request: EpoOpsSearchRequest) -> str:
        query = urlencode(
            {"q": request.cql_query.strip()},
            quote_via=quote,
        )
        return f"{EPO_OPS_SEARCH_URL}?{query}"

    @staticmethod
    def _validate_xml_content(response: EpoOpsHttpResponse) -> None:
        content_type, *parameters = response.content_type.split(";")
        if content_type.strip().casefold() != EPO_OPS_SEARCH_ACCEPT:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS search response did not use the accepted XML MIME type."
            )

        for parameter in parameters:
            name, separator, value = parameter.strip().partition("=")
            if (
                not separator
                or name.casefold() != "charset"
                or value.strip('"').casefold() != "utf-8"
            ):
                raise EpoOpsBibliographicResponseError(
                    "EPO OPS search response used an unsupported MIME parameter."
                )

        if not response.body.strip():
            raise EpoOpsBibliographicResponseError(
                "EPO OPS search response body was blank."
            )

    @classmethod
    def _parse_records(
        cls,
        body: bytes,
        *,
        source_endpoint: str,
    ) -> tuple[EpoOpsBibliographicRecord, ...]:
        try:
            root = DefusedElementTree.fromstring(body)
        except (DefusedXmlException, ParseError):
            raise EpoOpsXmlParseError(
                "EPO OPS search response XML was malformed or unsafe."
            ) from None

        if root.tag != f"{{{OPS_NAMESPACE}}}world-patent-data":
            raise EpoOpsBibliographicResponseError(
                "EPO OPS search response root was unexpected."
            )

        search_result = root.find(
            "ops:biblio-search/ops:search-result",
            NAMESPACES,
        )
        if search_result is None:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS search response omitted the bibliographic result."
            )

        documents = search_result.findall(
            "exchange:exchange-documents/exchange:exchange-document",
            NAMESPACES,
        )
        records: list[EpoOpsBibliographicRecord] = []
        seen_identities: set[str] = set()
        for document in documents:
            record = cls._parse_document(
                document,
                source_endpoint=source_endpoint,
            )
            identity = normalize_patent_publication_number(record.publication_number)
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            records.append(record)

        return tuple(records)

    @classmethod
    def _parse_document(
        cls,
        document,
        *,
        source_endpoint: str,
    ) -> EpoOpsBibliographicRecord:
        bibliographic = document.find("exchange:bibliographic-data", NAMESPACES)
        if bibliographic is None:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result omitted bibliographic data."
            )

        publication_id = bibliographic.find(
            (
                "exchange:publication-reference/"
                "exchange:document-id[@document-id-type='docdb']"
            ),
            NAMESPACES,
        )
        if publication_id is None:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result omitted DOCDB publication identity."
            )

        publication_number, publication_docdb = cls._docdb_publication_identity(
            publication_id
        )
        publication_date = cls._publication_date(publication_id)
        title, title_language = cls._select_title(bibliographic)
        application_number = cls._application_number(bibliographic)

        return EpoOpsBibliographicRecord(
            publication_number=publication_number,
            publication_docdb=publication_docdb,
            title=title,
            publication_date=publication_date,
            source_endpoint=source_endpoint,
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=application_number,
            title_language=title_language,
        )

    @classmethod
    def _docdb_publication_identity(cls, document_id) -> tuple[str, str]:
        country = cls._required_child_text(document_id, "country").upper()
        number = cls._required_child_text(document_id, "doc-number").upper()
        kind = cls._required_child_text(document_id, "kind").upper()
        if (
            _DOCDB_COUNTRY_PATTERN.fullmatch(country) is None
            or _DOCDB_NUMBER_PATTERN.fullmatch(number) is None
            or _DOCDB_KIND_PATTERN.fullmatch(kind) is None
        ):
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result contained an invalid DOCDB publication identity."
            )
        return f"{country}{number}{kind}", f"{country}.{number}.{kind}"

    @staticmethod
    def _publication_date(document_id) -> date | None:
        value = document_id.findtext("exchange:date", namespaces=NAMESPACES)
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if (
            len(normalized) != 8
            or not normalized.isascii()
            or not normalized.isdecimal()
        ):
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result contained an invalid publication date."
            )
        try:
            return date.fromisoformat(
                f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
            )
        except ValueError:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result contained an invalid publication date."
            ) from None

    @staticmethod
    def _select_title(bibliographic) -> tuple[str, str | None]:
        candidates: list[tuple[str, str | None]] = []
        for element in bibliographic.findall(
            "exchange:invention-title",
            NAMESPACES,
        ):
            text = " ".join("".join(element.itertext()).split())
            if not text:
                continue
            language = element.get(f"{{{XML_NAMESPACE}}}lang") or element.get("lang")
            normalized_language = language.strip().casefold() if language else None
            candidates.append((text, normalized_language))

        if not candidates:
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result omitted a nonblank invention title."
            )

        return next(
            (candidate for candidate in candidates if candidate[1] == "en"),
            candidates[0],
        )

    @staticmethod
    def _application_number(bibliographic) -> str | None:
        application_id = bibliographic.find(
            (
                "exchange:application-reference/"
                "exchange:document-id[@document-id-type='epodoc']"
            ),
            NAMESPACES,
        )
        if application_id is None:
            return None
        value = application_id.findtext(
            "exchange:doc-number",
            namespaces=NAMESPACES,
        )
        if value is None or not value.strip():
            return None
        return "".join(value.split()).upper()

    @staticmethod
    def _required_child_text(element, child_name: str) -> str:
        value = element.findtext(
            f"exchange:{child_name}",
            namespaces=NAMESPACES,
        )
        if value is None or not value.strip():
            raise EpoOpsBibliographicResponseError(
                "EPO OPS result contained an incomplete publication identity."
            )
        return value.strip()
