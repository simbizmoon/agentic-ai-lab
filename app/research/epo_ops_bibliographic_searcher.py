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
    EpoOpsCpcClassification,
    EpoOpsDocumentIdType,
    EpoOpsIpcClassification,
    EpoOpsPartyRepresentation,
    EpoOpsPriorityClaim,
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
        family_id = cls._family_id(document)
        priority_claims = cls._priority_claims(bibliographic)
        ipc_classifications = cls._ipc_classifications(bibliographic)
        cpc_classifications = cls._cpc_classifications(bibliographic)
        applicants = cls._party_representations(bibliographic, role="applicant")
        inventors = cls._party_representations(bibliographic, role="inventor")

        return EpoOpsBibliographicRecord(
            publication_number=publication_number,
            publication_docdb=publication_docdb,
            title=title,
            publication_date=publication_date,
            source_endpoint=source_endpoint,
            document_id_type=EpoOpsDocumentIdType.DOCDB,
            application_number=application_number,
            family_id=family_id,
            title_language=title_language,
            priority_claims=priority_claims,
            ipc_classifications=ipc_classifications,
            cpc_classifications=cpc_classifications,
            applicants=applicants,
            inventors=inventors,
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

    @classmethod
    def _publication_date(cls, document_id) -> date | None:
        return cls._optional_date(
            document_id.findtext("exchange:date", namespaces=NAMESPACES),
            field_name="publication date",
        )

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
    def _family_id(document) -> str | None:
        """Preserve the provider-supplied DOCDB simple-family identifier."""

        value = document.get("family-id")
        if value is None:
            return None
        if not value.strip():
            raise EpoOpsBibliographicResponseError(
                "EPO OPS exchange-document contained a blank family-id."
            )
        return value.strip()

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
    def _ipc_classifications(
        bibliographic,
    ) -> tuple[EpoOpsIpcClassification, ...]:
        """Preserve classification-ipcr text without parsing ST.8 subfields."""

        container = bibliographic.find(
            "exchange:classifications-ipcr",
            NAMESPACES,
        )
        if container is None:
            return ()

        values: list[EpoOpsIpcClassification] = []
        for element in container.findall(
            "exchange:classification-ipcr",
            NAMESPACES,
        ):
            raw_text = element.findtext(
                "exchange:text",
                namespaces=NAMESPACES,
            )
            if raw_text is None or not raw_text.strip():
                raise EpoOpsBibliographicResponseError(
                    "EPO OPS IPC classification contained blank text."
                )

            sequence = element.get("sequence")
            values.append(
                EpoOpsIpcClassification(
                    text=raw_text.strip(),
                    sequence=(
                        sequence.strip()
                        if sequence is not None and sequence.strip()
                        else None
                    ),
                )
            )

        return tuple(values)

    @staticmethod
    def _cpc_classifications(
        bibliographic,
    ) -> tuple[EpoOpsCpcClassification, ...]:
        """Select CPCI patent-classification records and preserve components."""

        container = bibliographic.find(
            "exchange:patent-classifications",
            NAMESPACES,
        )
        if container is None:
            return ()

        values: list[EpoOpsCpcClassification] = []
        for element in container.findall(
            "exchange:patent-classification",
            NAMESPACES,
        ):
            scheme = element.find(
                "exchange:classification-scheme",
                NAMESPACES,
            )
            if scheme is None:
                continue

            raw_scheme = scheme.get("scheme")
            if raw_scheme is None or raw_scheme.casefold() != "cpci":
                continue

            def required_text(source_element, name: str) -> str:
                value = source_element.findtext(
                    f"exchange:{name}",
                    namespaces=NAMESPACES,
                )
                if value is None or not value.strip():
                    raise EpoOpsBibliographicResponseError(
                        f"EPO OPS CPCI classification contained blank {name}."
                    )
                return value.strip()

            def optional_text(source_element, name: str) -> str | None:
                value = source_element.findtext(
                    f"exchange:{name}",
                    namespaces=NAMESPACES,
                )
                if value is None or not value.strip():
                    return None
                return value.strip()

            sequence = element.get("sequence")
            scheme_office = scheme.get("office")
            values.append(
                EpoOpsCpcClassification(
                    section=required_text(element, "section"),
                    class_number=required_text(element, "class"),
                    subclass=required_text(element, "subclass"),
                    main_group=required_text(element, "main-group"),
                    subgroup=required_text(element, "subgroup"),
                    sequence=(
                        sequence.strip()
                        if sequence is not None and sequence.strip()
                        else None
                    ),
                    classification_value=optional_text(element, "classification-value"),
                    scheme_office=(
                        scheme_office.strip()
                        if scheme_office is not None and scheme_office.strip()
                        else None
                    ),
                    generating_office=optional_text(element, "generating-office"),
                )
            )

        return tuple(values)

    @staticmethod
    def _party_representations(
        bibliographic,
        *,
        role: str,
    ) -> tuple[EpoOpsPartyRepresentation, ...]:
        """Preserve applicant/inventor representations without identity merging."""

        if role not in {"applicant", "inventor"}:
            raise ValueError("role must be applicant or inventor")

        parties = bibliographic.find("exchange:parties", NAMESPACES)
        if parties is None:
            return ()

        container = parties.find(f"exchange:{role}s", NAMESPACES)
        if container is None:
            return ()

        values: list[EpoOpsPartyRepresentation] = []
        for element in container.findall(f"exchange:{role}", NAMESPACES):
            raw_name = element.findtext(
                f"exchange:{role}-name/exchange:name",
                namespaces=NAMESPACES,
            )
            if raw_name is None or not raw_name.strip():
                raise EpoOpsBibliographicResponseError(
                    f"EPO OPS {role} contained a blank name."
                )

            sequence = element.get("sequence")
            data_format = element.get("data-format")
            values.append(
                EpoOpsPartyRepresentation(
                    name=raw_name.strip(),
                    sequence=(
                        sequence.strip()
                        if sequence is not None and sequence.strip()
                        else None
                    ),
                    data_format=(
                        data_format.strip()
                        if data_format is not None and data_format.strip()
                        else None
                    ),
                )
            )

        return tuple(values)

    @classmethod
    def _priority_claims(
        cls,
        bibliographic,
    ) -> tuple[EpoOpsPriorityClaim, ...]:
        """Parse EPODOC priority claims without inferring legal validity.

        A priority-claim element may contain multiple document-id representations.
        The current provider contract selects EPODOC when present and preserves an
        ORIGINAL number only when it occurs inside that same claim element. Claims
        that do not expose EPODOC are outside this first bounded contract and are
        not promoted.
        """

        container = bibliographic.find(
            "exchange:priority-claims",
            NAMESPACES,
        )
        if container is None:
            return ()

        claims: list[EpoOpsPriorityClaim] = []
        for claim in container.findall("exchange:priority-claim", NAMESPACES):
            epodoc = claim.find(
                "exchange:document-id[@document-id-type='epodoc']",
                NAMESPACES,
            )
            if epodoc is None:
                continue

            number = epodoc.findtext(
                "exchange:doc-number",
                namespaces=NAMESPACES,
            )
            if number is None or not number.strip():
                raise EpoOpsBibliographicResponseError(
                    "EPO OPS priority claim contained a blank EPODOC number."
                )

            priority_date = cls._optional_date(
                epodoc.findtext(
                    "exchange:date",
                    namespaces=NAMESPACES,
                ),
                field_name="priority date",
            )

            original = claim.find(
                "exchange:document-id[@document-id-type='original']",
                NAMESPACES,
            )
            original_number = None
            if original is not None:
                raw_original = original.findtext(
                    "exchange:doc-number",
                    namespaces=NAMESPACES,
                )
                if raw_original is not None and raw_original.strip():
                    original_number = raw_original.strip()

            sequence = claim.get("sequence")
            claim_kind = claim.get("kind")
            claims.append(
                EpoOpsPriorityClaim(
                    priority_number="".join(number.split()).upper(),
                    priority_date=priority_date,
                    sequence=sequence.strip()
                    if sequence and sequence.strip()
                    else None,
                    claim_kind=(
                        claim_kind.strip()
                        if claim_kind and claim_kind.strip()
                        else None
                    ),
                    original_number=original_number,
                )
            )

        return tuple(claims)

    @staticmethod
    def _optional_date(
        value: str | None,
        *,
        field_name: str,
    ) -> date | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if (
            len(normalized) != 8
            or not normalized.isascii()
            or not normalized.isdecimal()
        ):
            raise EpoOpsBibliographicResponseError(
                f"EPO OPS result contained an invalid {field_name}."
            )
        try:
            return date.fromisoformat(
                f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
            )
        except ValueError:
            raise EpoOpsBibliographicResponseError(
                f"EPO OPS result contained an invalid {field_name}."
            ) from None

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
