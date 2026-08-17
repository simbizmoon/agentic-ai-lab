"""Safe EPO OPS abstract retrieval for one parsed bibliographic candidate."""

from __future__ import annotations

import re
from urllib.parse import quote
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from app.research.epo_ops_bibliographic_searcher import (
    NAMESPACES,
    OPS_NAMESPACE,
)
from app.research.epo_ops_client import EpoOpsClient, EpoOpsHttpResponse
from app.schemas.epo_ops_abstract import EpoOpsAbstractRecord
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord

EPO_OPS_ABSTRACT_ACCEPT = "application/exchange+xml"
EPO_OPS_PUBLICATION_DOCDB_BASE = (
    "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb"
)

_DOCDB_INPUT_PATTERN = re.compile(
    r"[A-Z]{2}\.[A-Z0-9]+\.[A-Z][A-Z0-9]?",
    re.ASCII,
)


class EpoOpsAbstractError(RuntimeError):
    """Base error for source-specific OPS abstract retrieval."""


class EpoOpsAbstractXmlParseError(EpoOpsAbstractError):
    """OPS returned malformed or unsafe abstract XML."""


class EpoOpsAbstractResponseError(EpoOpsAbstractError):
    """OPS returned XML outside the accepted abstract contract."""


class EpoOpsAbstractRetriever:
    """Retrieve and parse one OPS abstract using the DOCDB identity from search."""

    def __init__(self, *, client: EpoOpsClient) -> None:
        self._client = client

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsAbstractRecord:
        """Return one abstract whose DOCDB identity matches the search record."""

        endpoint = self._abstract_endpoint(record.publication_docdb)
        response = self._client.authenticated_get_response(
            endpoint=endpoint,
            accept=EPO_OPS_ABSTRACT_ACCEPT,
        )
        self._validate_xml_content(response)
        return self._parse_record(
            response.body,
            expected_publication_number=record.publication_number,
            expected_publication_docdb=record.publication_docdb,
            source_endpoint=endpoint,
        )

    @staticmethod
    def _abstract_endpoint(publication_docdb: str) -> str:
        normalized = publication_docdb.strip().upper()
        if _DOCDB_INPUT_PATTERN.fullmatch(normalized) is None:
            raise EpoOpsAbstractResponseError(
                "EPO OPS bibliographic record contained an invalid DOCDB input."
            )
        return (
            f"{EPO_OPS_PUBLICATION_DOCDB_BASE}/{quote(normalized, safe='.')}/abstract"
        )

    @staticmethod
    def _validate_xml_content(response: EpoOpsHttpResponse) -> None:
        content_type, *parameters = response.content_type.split(";")
        if content_type.strip().casefold() != EPO_OPS_ABSTRACT_ACCEPT:
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response did not use the accepted XML MIME type."
            )

        for parameter in parameters:
            name, separator, value = parameter.strip().partition("=")
            if (
                not separator
                or name.casefold() != "charset"
                or value.strip('"').casefold() != "utf-8"
            ):
                raise EpoOpsAbstractResponseError(
                    "EPO OPS abstract response used an unsupported MIME parameter."
                )

        if not response.body.strip():
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response body was blank."
            )

    @classmethod
    def _parse_record(
        cls,
        body: bytes,
        *,
        expected_publication_number: str,
        expected_publication_docdb: str,
        source_endpoint: str,
    ) -> EpoOpsAbstractRecord:
        try:
            root = DefusedElementTree.fromstring(body)
        except (DefusedXmlException, ParseError):
            raise EpoOpsAbstractXmlParseError(
                "EPO OPS abstract response XML was malformed or unsafe."
            ) from None

        if root.tag != f"{{{OPS_NAMESPACE}}}world-patent-data":
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response root was unexpected."
            )

        documents = root.findall(
            ".//exchange:exchange-document",
            NAMESPACES,
        )
        matching: list[tuple[object, str]] = []
        for document in documents:
            publication_id = document.find(
                (
                    "exchange:bibliographic-data/"
                    "exchange:publication-reference/"
                    "exchange:document-id[@document-id-type='docdb']"
                ),
                NAMESPACES,
            )
            if publication_id is None:
                continue
            publication_number, publication_docdb = cls._docdb_identity(publication_id)
            if publication_number == expected_publication_number:
                matching.append((document, publication_docdb))

        if len(matching) != 1:
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response did not contain exactly one matching publication."
            )

        document, actual_docdb = matching[0]
        if actual_docdb != expected_publication_docdb:
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response DOCDB identity did not match the request."
            )

        abstract_text, abstract_language = cls._select_abstract(document)
        return EpoOpsAbstractRecord(
            publication_number=expected_publication_number,
            publication_docdb=expected_publication_docdb,
            abstract_text=abstract_text,
            abstract_language=abstract_language,
            source_endpoint=source_endpoint,
        )

    @staticmethod
    def _docdb_identity(document_id) -> tuple[str, str]:
        def required(name: str) -> str:
            value = document_id.findtext(
                f"exchange:{name}",
                namespaces=NAMESPACES,
            )
            if value is None or not value.strip():
                raise EpoOpsAbstractResponseError(
                    "EPO OPS abstract response contained an incomplete DOCDB identity."
                )
            return value.strip().upper()

        country = required("country")
        number = required("doc-number")
        kind = required("kind")
        dotted = f"{country}.{number}.{kind}"
        if _DOCDB_INPUT_PATTERN.fullmatch(dotted) is None:
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response contained an invalid DOCDB identity."
            )
        return f"{country}{number}{kind}", dotted

    @staticmethod
    def _select_abstract(document) -> tuple[str, str | None]:
        candidates: list[tuple[str, str | None]] = []
        for element in document.findall("exchange:abstract", NAMESPACES):
            text = " ".join("".join(element.itertext()).split())
            if not text:
                continue
            language = element.get("lang")
            normalized_language = language.strip().casefold() if language else None
            candidates.append((text, normalized_language))

        if not candidates:
            raise EpoOpsAbstractResponseError(
                "EPO OPS abstract response omitted a nonblank abstract."
            )

        return next(
            (candidate for candidate in candidates if candidate[1] == "en"),
            candidates[0],
        )
