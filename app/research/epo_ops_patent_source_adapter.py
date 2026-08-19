"""Map matching EPO OPS records into verified patent-source product data."""

from __future__ import annotations

from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
)
from app.schemas.epo_ops_abstract import (
    EpoOpsAbstractRecord,
    EpoOpsVerifiedPatentRecord,
)
from app.schemas.epo_ops_bibliographic import (
    EpoOpsBibliographicRecord,
    EpoOpsPartyRepresentation,
)
from app.schemas.patent_source_metadata import (
    PatentCpcClassification,
    PatentIpcClassification,
    PatentMetadataVerificationState,
    PatentParty,
    PatentPriorityClaim,
    PatentSourceFamily,
    PatentSourceMetadata,
)


class EpoOpsPatentSourceMappingError(RuntimeError):
    """Bibliographic and abstract records could not form one verified source."""


def _select_product_parties(
    representations: tuple[EpoOpsPartyRepresentation, ...],
) -> tuple[PatentParty, ...]:
    """Select one display representation per provider party sequence.

    This is a presentation mapping, not a legal identity determination.
    ORIGINAL is preferred, then EPODOC, then the first available representation.
    Representations without sequence are kept independently and are never merged.
    """

    grouped: dict[str, list[EpoOpsPartyRepresentation]] = {}
    order: list[tuple[str, str | int]] = []
    unsequenced: list[EpoOpsPartyRepresentation] = []

    for representation in representations:
        if representation.sequence is None:
            index = len(unsequenced)
            unsequenced.append(representation)
            order.append(("unsequenced", index))
            continue

        if representation.sequence not in grouped:
            grouped[representation.sequence] = []
            order.append(("sequence", representation.sequence))
        grouped[representation.sequence].append(representation)

    selected: list[PatentParty] = []
    for kind, key in order:
        if kind == "unsequenced":
            representation = unsequenced[int(key)]
            selected.append(PatentParty(name=representation.name))
            continue

        candidates = grouped[str(key)]
        representation = next(
            (
                value
                for value in candidates
                if value.data_format is not None
                and value.data_format.casefold() == "original"
            ),
            None,
        )
        if representation is None:
            representation = next(
                (
                    value
                    for value in candidates
                    if value.data_format is not None
                    and value.data_format.casefold() == "epodoc"
                ),
                candidates[0],
            )
        selected.append(PatentParty(name=representation.name))

    return tuple(selected)


def build_verified_epo_patent_record(
    *,
    bibliographic: EpoOpsBibliographicRecord,
    abstract: EpoOpsAbstractRecord,
) -> EpoOpsVerifiedPatentRecord:
    """Create VERIFIED metadata only after exact source-specific identity matching."""

    biblio_identity = normalize_patent_publication_number(
        bibliographic.publication_number
    )
    abstract_identity = normalize_patent_publication_number(abstract.publication_number)
    if biblio_identity != abstract_identity:
        raise EpoOpsPatentSourceMappingError(
            "EPO OPS bibliographic and abstract publication identities differ."
        )
    if bibliographic.publication_docdb != abstract.publication_docdb:
        raise EpoOpsPatentSourceMappingError(
            "EPO OPS bibliographic and abstract DOCDB identities differ."
        )

    metadata = PatentSourceMetadata(
        source_family=PatentSourceFamily.EPO_OPS,
        publication_number=bibliographic.publication_number,
        title=bibliographic.title,
        source_url=abstract.source_endpoint,
        metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
        publication_date=bibliographic.publication_date,
        application_number=bibliographic.application_number,
        priority_claims=tuple(
            PatentPriorityClaim(
                priority_number=claim.priority_number,
                priority_date=claim.priority_date,
            )
            for claim in bibliographic.priority_claims
        ),
        ipc_classifications=tuple(
            PatentIpcClassification(text=classification.text)
            for classification in bibliographic.ipc_classifications
        ),
        cpc_classifications=tuple(
            PatentCpcClassification(
                section=classification.section,
                class_number=classification.class_number,
                subclass=classification.subclass,
                main_group=classification.main_group,
                subgroup=classification.subgroup,
            )
            for classification in bibliographic.cpc_classifications
        ),
        applicants=_select_product_parties(bibliographic.applicants),
        inventors=_select_product_parties(bibliographic.inventors),
    )
    return EpoOpsVerifiedPatentRecord(
        metadata=metadata,
        abstract_text=abstract.abstract_text,
        abstract_language=abstract.abstract_language,
    )
