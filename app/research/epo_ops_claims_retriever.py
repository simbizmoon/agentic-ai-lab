"""Safe EPO OPS raw patent-claim retrieval for one DOCDB publication."""

from __future__ import annotations

import re
from urllib.parse import quote
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from app.research.epo_ops_bibliographic_searcher import OPS_NAMESPACE
from app.research.epo_ops_client import EpoOpsClient, EpoOpsHttpResponse
from app.schemas.epo_ops_bibliographic import EpoOpsBibliographicRecord
from app.schemas.epo_ops_claims import (
    EpoOpsClaimSet,
    EpoOpsClaimsRecord,
    EpoOpsClaimText,
)

EPO_OPS_CLAIMS_ACCEPT = "application/fulltext+xml"
EPO_OPS_PUBLICATION_DOCDB_BASE = (
    "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb"
)
FULLTEXT_NAMESPACE = "http://www.epo.org/fulltext"
NAMESPACES = {"ftxt": FULLTEXT_NAMESPACE}

_DOCDB_INPUT_PATTERN = re.compile(
    r"[A-Z]{2}\.[A-Z0-9]+\.[A-Z][A-Z0-9]?",
    re.ASCII,
)


class EpoOpsClaimsError(RuntimeError):
    """Base error for source-specific OPS claim retrieval."""


class EpoOpsClaimsXmlParseError(EpoOpsClaimsError):
    """OPS returned malformed or unsafe claims XML."""


class EpoOpsClaimsResponseError(EpoOpsClaimsError):
    """OPS returned XML outside the accepted raw-claims contract."""


class EpoOpsClaimsRetriever:
    """Retrieve raw language-specific claims for one exact DOCDB publication."""

    def __init__(self, *, client: EpoOpsClient) -> None:
        self._client = client

    def retrieve(self, record: EpoOpsBibliographicRecord) -> EpoOpsClaimsRecord:
        """Return raw claims whose publication identity matches the search record."""

        endpoint = self._claims_endpoint(record.publication_docdb)
        response = self._client.authenticated_get_response(
            endpoint=endpoint,
            accept=EPO_OPS_CLAIMS_ACCEPT,
        )
        self._validate_xml_content(response)
        return self._parse_record(
            response.body,
            expected_publication_number=record.publication_number,
            expected_publication_docdb=record.publication_docdb,
            source_endpoint=endpoint,
        )

    @staticmethod
    def _claims_endpoint(publication_docdb: str) -> str:
        normalized = publication_docdb.strip().upper()
        if _DOCDB_INPUT_PATTERN.fullmatch(normalized) is None:
            raise EpoOpsClaimsResponseError(
                "EPO OPS bibliographic record contained an invalid DOCDB input."
            )
        return f"{EPO_OPS_PUBLICATION_DOCDB_BASE}/{quote(normalized, safe='.')}/claims"

    @staticmethod
    def _validate_xml_content(response: EpoOpsHttpResponse) -> None:
        content_type, *parameters = response.content_type.split(";")
        if content_type.strip().casefold() != EPO_OPS_CLAIMS_ACCEPT:
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response did not use the accepted XML MIME type."
            )

        for parameter in parameters:
            name, separator, value = parameter.strip().partition("=")
            if (
                not separator
                or name.casefold() != "charset"
                or value.strip('"').casefold() != "utf-8"
            ):
                raise EpoOpsClaimsResponseError(
                    "EPO OPS claims response used an unsupported MIME parameter."
                )

        if not response.body.strip():
            raise EpoOpsClaimsResponseError("EPO OPS claims response body was blank.")

    @classmethod
    def _parse_record(
        cls,
        body: bytes,
        *,
        expected_publication_number: str,
        expected_publication_docdb: str,
        source_endpoint: str,
    ) -> EpoOpsClaimsRecord:
        try:
            root = DefusedElementTree.fromstring(body)
        except (DefusedXmlException, ParseError):
            raise EpoOpsClaimsXmlParseError(
                "EPO OPS claims response XML was malformed or unsafe."
            ) from None

        if root.tag != f"{{{OPS_NAMESPACE}}}world-patent-data":
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response root was unexpected."
            )

        documents = root.findall(".//ftxt:fulltext-document", NAMESPACES)
        matching: list[tuple[object, str]] = []
        for document in documents:
            publication_id = document.find(
                ("ftxt:bibliographic-data/ftxt:publication-reference/ftxt:document-id"),
                NAMESPACES,
            )
            if publication_id is None:
                continue
            publication_number, publication_docdb = cls._docdb_identity(publication_id)
            if publication_number == expected_publication_number:
                matching.append((document, publication_docdb))

        if len(matching) != 1:
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response did not contain exactly one matching publication."
            )

        document, actual_docdb = matching[0]
        if actual_docdb != expected_publication_docdb:
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response DOCDB identity did not match the request."
            )

        claim_sets = cls._claim_sets(document)
        return EpoOpsClaimsRecord(
            publication_number=expected_publication_number,
            publication_docdb=expected_publication_docdb,
            source_endpoint=source_endpoint,
            claim_sets=claim_sets,
        )

    @staticmethod
    def _docdb_identity(document_id) -> tuple[str, str]:
        def required(name: str) -> str:
            value = document_id.findtext(
                f"ftxt:{name}",
                namespaces=NAMESPACES,
            )
            if value is None or not value.strip():
                raise EpoOpsClaimsResponseError(
                    "EPO OPS claims response contained an incomplete DOCDB identity."
                )
            return value.strip().upper()

        country = required("country")
        number = required("doc-number")
        kind = required("kind")
        dotted = f"{country}.{number}.{kind}"
        if _DOCDB_INPUT_PATTERN.fullmatch(dotted) is None:
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response contained an invalid DOCDB identity."
            )
        return f"{country}{number}{kind}", dotted

    @staticmethod
    def _claim_sets(document) -> tuple[EpoOpsClaimSet, ...]:
        containers = document.findall("ftxt:claims", NAMESPACES)
        if not containers:
            raise EpoOpsClaimsResponseError(
                "EPO OPS claims response omitted claim containers."
            )

        claim_sets: list[EpoOpsClaimSet] = []
        for container in containers:
            language = container.get("lang")
            if language is None or not language.strip():
                raise EpoOpsClaimsResponseError(
                    "EPO OPS claims container omitted a nonblank language."
                )

            raw_claims = container.findall(".//ftxt:claim-text", NAMESPACES)
            if not raw_claims:
                raise EpoOpsClaimsResponseError(
                    "EPO OPS claims container omitted claim-text items."
                )

            claims: list[EpoOpsClaimText] = []
            for position, element in enumerate(raw_claims, start=1):
                text = " ".join("".join(element.itertext()).split())
                if not text:
                    raise EpoOpsClaimsResponseError(
                        "EPO OPS claim-text item was blank."
                    )
                claims.append(
                    EpoOpsClaimText(
                        position=position,
                        text=text,
                    )
                )

            claim_sets.append(
                EpoOpsClaimSet(
                    language=language.strip().upper(),
                    claims=tuple(claims),
                )
            )

        return tuple(claim_sets)
