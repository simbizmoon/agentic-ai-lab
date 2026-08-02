"""Print a local report from structured analysis audit logs."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.archive_authenticity import (
    REPORT_ARCHIVE_FORMAT_VERSION,
    archive_authentication_path_for,
    verify_archive_authenticity,
)
from app.archive_signature import (
    archive_signature_path_for,
    verify_archive_signature,
)
from app.audit_report import (
    AuditReportFilter,
    AuditReportFormat,
    AuditStatusFilter,
    build_audit_report,
    filter_audit_events,
    read_audit_events,
    render_audit_report,
)
from app.authentication_trust import (
    RevokedKeyPolicy,
    load_authentication_trust_store,
)
from app.exceptions import (
    ArchiveAuthenticityError,
    ArchiveSignatureError,
    AuditLogError,
    ManifestTrustStateError,
    ManifestTrustStateValidationError,
    ReportArchiveError,
    ReportAuthenticityError,
    ReportBundleError,
    ReportExportError,
    ReportIntegrityError,
    RootSignatureTrustError,
    RootTransitionError,
    RootTrustStateError,
    SigningKeyManifestError,
    SigningKeyManifestReadError,
    SigningKeyManifestValidationError,
    TransparencyCheckpointError,
    TransparencyCheckpointStateError,
    TransparencyDecisionReceiptError,
    TransparencyGossipBundleError,
    TransparencyLogError,
    TransparencyLogStateError,
    TransparencyMerkleError,
    TransparencyOfflineVerificationError,
    TransparencySplitViewEvidenceError,
    TransparencyWitnessError,
)
from app.manifest_trust_state import (
    MANIFEST_TRUST_STATE_ENV_NAME,
    ManifestTrustStateDecision,
    ManifestTrustStateMode,
    apply_manifest_trust_state,
    load_manifest_trust_state,
    retire_manifest_trust_state,
)
from app.recovery import decide_recovery
from app.report_archive import (
    archive_path_for,
    verify_archive_signature_with_root_state_and_transparency,
    verify_authenticated_report_archive,
    verify_signed_authenticated_report_archive_with_root_state_and_transparency,
)
from app.report_authenticity import (
    authentication_path_for,
    verify_report_authenticity,
)
from app.report_bundle import manifest_path_for, verify_report_bundle
from app.report_export import (
    export_json_report_archive,
    export_json_report_bundle,
    export_json_report_signed_archive_with_root_state_and_transparency,
    export_json_report_with_checksum,
)
from app.report_integrity import (
    checksum_path_for,
    verify_report_integrity,
)
from app.root_signature_trust import (
    ensure_root_key_pair_matches,
    load_next_root_signing_private_key,
    load_next_trusted_root_public_key,
    load_root_signing_private_key,
    load_trusted_root_public_key,
)
from app.root_transition import (
    build_root_transition_manifest,
    export_root_transition_manifest,
    export_root_transition_signature,
    next_root_signature_path_for,
    previous_root_signature_path_for,
    sign_root_transition,
    verify_root_transition,
)
from app.root_trust_state import (
    ROOT_TRUST_STATE_ENV_NAME,
    apply_root_transition_with_transparency,
    initialize_root_trust_state,
    load_root_trust_state,
    trusted_root_public_key_from_state,
)
from app.signature_trust import (
    RevokedSignatureKeyPolicy,
    load_archive_signature_trust_store,
    load_archive_signing_private_key,
)
from app.signing_key_manifest import (
    MIN_SIGNING_KEY_MANIFEST_GENERATION_ENV_NAME,
    SIGNING_KEY_MANIFEST_PATH_ENV_NAME,
    build_signing_key_manifest,
    export_signing_key_manifest,
    export_signing_key_manifest_signature,
    sign_signing_key_manifest,
    signing_key_manifest_signature_path_for,
    verify_signing_key_manifest,
    verify_signing_key_manifest_with_root_state,
    verify_signing_key_manifest_with_root_state_and_transparency,
)
from app.transparency_checkpoint import (
    TransparencyCheckpointVerificationMode,
    checkpoint_signature_path_for,
    create_transparency_checkpoint,
    generate_checkpoint_consistency_proof,
    generate_checkpoint_inclusion_proof,
    verify_checkpoint_consistency_proof,
    verify_checkpoint_inclusion_proof,
    verify_transparency_checkpoint,
)
from app.transparency_checkpoint_state import (
    apply_verified_checkpoint_to_state,
    load_transparency_checkpoint_state,
)
from app.transparency_decision_receipt import (
    build_trusted_decision_receipt,
    create_transparency_trust_decision_receipt,
    load_decision_receipt_trust_store,
    verify_transparency_trust_decision_receipt,
)
from app.transparency_gossip import (
    create_transparency_split_view_evidence,
    verify_transparency_split_view_evidence,
)
from app.transparency_gossip_bundle import (
    create_transparency_gossip_bundle,
    load_gossip_bundle_signing_trust_store,
    load_transparency_gossip_bundle,
)
from app.transparency_log import (
    TRANSPARENCY_LOG_PATH_ENV_NAME,
    TRANSPARENCY_LOG_STATE_PATH_ENV_NAME,
    TransparencyLogAppendResult,
    TransparencyLogInclusionResult,
    TransparencyLogMode,
    register_verified_artifact,
    require_transparency_entry,
    transparency_artifact_from_verified_root_transition,
    verify_transparency_log,
)
from app.transparency_merkle import (
    export_transparency_consistency_proof,
    export_transparency_inclusion_proof,
    load_transparency_consistency_proof,
    load_transparency_inclusion_proof,
)
from app.transparency_offline_verifier import verify_transparency_gossip_bundle_offline
from app.transparency_quorum import verify_transparency_witness_quorum
from app.transparency_witness import (
    create_transparency_witness_statement,
    verify_transparency_witness_statement,
)
from app.transparency_witness_trust import (
    RevokedWitnessPolicy,
    load_transparency_witness_trust_store,
)

_MONKEYPATCH_COMPATIBILITY_EXPORTS = (
    export_json_report_archive,
    verify_archive_signature,
    verify_authenticated_report_archive,
)

AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "structured_analysis.jsonl"


def parse_cli_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("datetime must be ISO 8601 with timezone") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must include timezone")
    return parsed.astimezone(UTC)


def parse_model_filter(value: str) -> str:
    model = value.strip()
    if not model:
        raise argparse.ArgumentTypeError("model must not be empty")
    return model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a local structured analysis audit report."
    )
    parser.add_argument("--since", type=parse_cli_datetime)
    parser.add_argument("--until", type=parse_cli_datetime)
    parser.add_argument("--model", type=parse_model_filter)
    parser.add_argument(
        "--status",
        choices=[status.value for status in AuditStatusFilter],
        default=AuditStatusFilter.ALL.value,
    )
    parser.add_argument(
        "--format",
        choices=[report_format.value for report_format in AuditReportFormat],
        default=AuditReportFormat.TEXT.value,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--authenticate", action="store_true")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--verify-authenticity", type=Path)
    parser.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--verify-archive", type=Path)
    parser.add_argument("--verify-archive-authenticity", type=Path)
    parser.add_argument("--verify-archive-signature", type=Path)
    parser.add_argument("--create-signing-key-manifest", type=Path)
    parser.add_argument("--verify-signing-key-manifest", type=Path)
    parser.add_argument("--signing-key-manifest", type=Path)
    parser.add_argument("--manifest-generation", type=int)
    parser.add_argument("--manifest-valid-from", type=parse_cli_datetime)
    parser.add_argument("--manifest-valid-until", type=parse_cli_datetime)
    parser.add_argument("--minimum-manifest-generation", type=int)
    parser.add_argument("--manifest-state", type=Path)
    parser.add_argument("--no-update-manifest-state", action="store_true")
    parser.add_argument("--require-existing-manifest-state", action="store_true")
    parser.add_argument("--show-manifest-state", type=Path)
    parser.add_argument("--initialize-manifest-state", type=Path)
    parser.add_argument("--initialize-root-trust-state", type=Path)
    parser.add_argument("--initial-root-epoch", type=int)
    parser.add_argument("--show-root-trust-state", type=Path)
    parser.add_argument("--create-root-transition", type=Path)
    parser.add_argument("--previous-root-epoch", type=int)
    parser.add_argument("--next-root-epoch", type=int)
    parser.add_argument("--root-transition-valid-from", type=parse_cli_datetime)
    parser.add_argument("--root-transition-valid-until", type=parse_cli_datetime)
    parser.add_argument("--verify-root-transition", type=Path)
    parser.add_argument("--apply-root-transition", type=Path)
    parser.add_argument("--root-trust-state", type=Path)
    parser.add_argument("--retire-manifest-state", type=Path)
    parser.add_argument("--transparency-log", type=Path)
    parser.add_argument("--transparency-log-state", type=Path)
    parser.add_argument("--verify-transparency-log", type=Path)
    parser.add_argument("--show-transparency-log", type=Path)
    parser.add_argument("--register-transparency-entry", action="store_true")
    parser.add_argument("--require-transparency-entry", action="store_true")
    parser.add_argument("--transparency-log-id")
    parser.add_argument("--create-transparency-checkpoint", type=Path)
    parser.add_argument("--verify-transparency-checkpoint", type=Path)
    parser.add_argument("--transparency-checkpoint", type=Path)
    parser.add_argument("--show-transparency-checkpoint", type=Path)
    parser.add_argument("--checkpoint-state", type=Path)
    parser.add_argument("--update-checkpoint-state", action="store_true")
    parser.add_argument("--no-update-checkpoint-state", action="store_true")
    parser.add_argument("--create-inclusion-proof", type=Path)
    parser.add_argument("--verify-inclusion-proof", type=Path)
    parser.add_argument("--artifact-identifier")
    parser.add_argument("--create-consistency-proof", type=Path)
    parser.add_argument("--verify-consistency-proof", type=Path)
    parser.add_argument("--consistency-proof", type=Path)
    parser.add_argument("--old-checkpoint", type=Path)
    parser.add_argument("--new-checkpoint", type=Path)
    parser.add_argument("--witness-trust-store", type=Path)
    parser.add_argument("--create-witness-statement", type=Path)
    parser.add_argument("--verify-witness-statement", type=Path)
    parser.add_argument("--witness-state", type=Path)
    parser.add_argument("--witness-statement", type=Path, action="append")
    parser.add_argument("--verify-witness-quorum", type=Path)
    parser.add_argument("--minimum-witness-quorum", type=int)
    parser.add_argument("--create-split-view-evidence", type=Path)
    parser.add_argument("--verify-split-view-evidence", type=Path)
    parser.add_argument("--conflicting-checkpoint", type=Path)
    parser.add_argument("--create-gossip-bundle", type=Path)
    parser.add_argument("--verify-gossip-bundle", type=Path)
    parser.add_argument("--show-gossip-bundle", type=Path)
    parser.add_argument("--target-artifact", type=Path)
    parser.add_argument("--artifact-type")
    parser.add_argument("--inclusion-proof", type=Path)
    parser.add_argument("--bundle-signing-trust-store", type=Path)
    parser.add_argument("--decision-receipt", type=Path)
    parser.add_argument("--create-decision-receipt", type=Path)
    parser.add_argument("--verify-decision-receipt", type=Path)
    parser.add_argument("--decision-receipt-trust-store", type=Path)
    parser.add_argument("--verification-policy-id", default="default")
    parser.add_argument(
        "--revoked-key-policy",
        choices=[policy.value for policy in RevokedKeyPolicy],
        default=RevokedKeyPolicy.REJECT.value,
    )
    parser.add_argument(
        "--revoked-signature-key-policy",
        choices=[policy.value for policy in RevokedSignatureKeyPolicy],
        default=RevokedSignatureKeyPolicy.REJECT.value,
    )
    parser.add_argument(
        "--revoked-witness-policy",
        choices=[policy.value for policy in RevokedWitnessPolicy],
        default=RevokedWitnessPolicy.REJECT.value,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_mode_args(parser, args)

    if args.create_transparency_checkpoint is not None:
        return _run_create_transparency_checkpoint(args, parser)
    if args.verify_transparency_checkpoint is not None:
        return _run_verify_transparency_checkpoint_file(args, parser)
    if args.show_transparency_checkpoint is not None:
        return _run_show_transparency_checkpoint(args, parser)
    if args.create_inclusion_proof is not None:
        return _run_create_inclusion_proof(args, parser)
    if args.verify_inclusion_proof is not None:
        return _run_verify_inclusion_proof(args, parser)
    if args.create_consistency_proof is not None:
        return _run_create_consistency_proof(args, parser)
    if args.verify_consistency_proof is not None:
        return _run_verify_consistency_proof(args, parser)
    if args.create_witness_statement is not None:
        return _run_create_witness_statement(args, parser)
    if args.verify_witness_statement is not None:
        return _run_verify_witness_statement(args, parser)
    if args.verify_witness_quorum is not None:
        return _run_verify_witness_quorum(args, parser)
    if args.create_split_view_evidence is not None:
        return _run_create_split_view_evidence(args, parser)
    if args.verify_split_view_evidence is not None:
        return _run_verify_split_view_evidence(args, parser)
    if args.create_gossip_bundle is not None:
        return _run_create_gossip_bundle(args, parser)
    if args.verify_gossip_bundle is not None:
        return _run_verify_gossip_bundle(args, parser)
    if args.show_gossip_bundle is not None:
        return _run_show_gossip_bundle(args, parser)
    if args.verify_decision_receipt is not None:
        return _run_verify_decision_receipt(args, parser)
    if args.show_transparency_log is not None:
        return _run_show_transparency_log(args.show_transparency_log, args, parser)
    if args.verify_transparency_log is not None:
        return _run_verify_transparency_log(args.verify_transparency_log, args, parser)
    if args.show_root_trust_state is not None:
        return _run_show_root_trust_state(args.show_root_trust_state)
    if args.initialize_root_trust_state is not None:
        return _run_initialize_root_trust_state(args, parser)
    if args.create_root_transition is not None:
        return _run_create_root_transition(args, parser)
    if args.verify_root_transition is not None:
        return _run_verify_root_transition(args, parser)
    if args.retire_manifest_state is not None:
        return _run_retire_manifest_state(args, parser)
    if args.apply_root_transition is not None:
        return _run_apply_root_transition(args, parser)
    if args.show_manifest_state is not None:
        return _run_show_manifest_state(args.show_manifest_state)
    if args.initialize_manifest_state is not None:
        return _run_initialize_manifest_state(args, parser)
    if args.create_signing_key_manifest is not None:
        return _run_create_signing_key_manifest(args, parser)
    if args.verify_signing_key_manifest is not None:
        return _run_verify_signing_key_manifest(args, parser)

    if args.verify is not None:
        return _run_verify(args.verify)
    if args.verify_authenticity is not None:
        return _run_verify_authenticity(
            args.verify_authenticity,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_bundle is not None:
        return _run_verify_bundle(
            args.verify_bundle,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_archive_authenticity is not None:
        return _run_verify_archive_authenticity(
            args.verify_archive_authenticity,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
        )
    if args.verify_archive_signature is not None:
        return _run_verify_archive_signature(
            args.verify_archive_signature,
            manifest_path=_resolve_signing_key_manifest_path(args, parser),
            minimum_generation=_resolve_minimum_manifest_generation(args, parser),
            state_path=_resolve_manifest_state_path(args),
            root_state_path=args.root_trust_state,
            transparency_log_path=_resolve_transparency_log_path(args, parser),
            transparency_state_path=_resolve_transparency_state_path(args, parser),
            state_mode=_resolve_manifest_state_mode(args),
            require_existing_state=args.require_existing_manifest_state,
            revoked_signature_key_policy=RevokedSignatureKeyPolicy(
                args.revoked_signature_key_policy
            ),
            witness_args=args,
        )
    if args.verify_archive is not None:
        return _run_verify_archive(
            args.verify_archive,
            manifest_path=_resolve_signing_key_manifest_path(args, parser),
            minimum_generation=_resolve_minimum_manifest_generation(args, parser),
            state_path=_resolve_manifest_state_path(args),
            root_state_path=args.root_trust_state,
            transparency_log_path=_resolve_transparency_log_path(args, parser),
            transparency_state_path=_resolve_transparency_state_path(args, parser),
            state_mode=_resolve_manifest_state_mode(args),
            require_existing_state=args.require_existing_manifest_state,
            revoked_key_policy=RevokedKeyPolicy(args.revoked_key_policy),
            revoked_signature_key_policy=RevokedSignatureKeyPolicy(
                args.revoked_signature_key_policy
            ),
            witness_args=args,
        )

    return _run_report_generation(args, parser)


def _validate_mode_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    verify_modes = (
        args.verify,
        args.verify_authenticity,
        args.verify_bundle,
        args.verify_archive_authenticity,
        args.verify_archive_signature,
        args.verify_signing_key_manifest,
        args.create_signing_key_manifest,
        args.show_manifest_state,
        args.initialize_manifest_state,
        args.show_root_trust_state,
        args.initialize_root_trust_state,
        args.create_root_transition,
        args.verify_root_transition,
        args.retire_manifest_state,
        args.apply_root_transition,
        args.verify_transparency_log,
        args.show_transparency_log,
        args.create_transparency_checkpoint,
        args.verify_transparency_checkpoint,
        args.show_transparency_checkpoint,
        args.create_inclusion_proof,
        args.verify_inclusion_proof,
        args.create_consistency_proof,
        args.verify_consistency_proof,
        args.create_witness_statement,
        args.verify_witness_statement,
        args.verify_witness_quorum,
        args.create_split_view_evidence,
        args.verify_split_view_evidence,
        args.create_gossip_bundle,
        args.verify_gossip_bundle,
        args.show_gossip_bundle,
        args.verify_decision_receipt,
        args.verify_archive,
    )
    if sum(value is not None for value in verify_modes) > 1:
        parser.error("only one verify mode can be used at a time")
    if args.register_transparency_entry and args.require_transparency_entry:
        parser.error("transparency register and require modes are mutually exclusive")

    root_mode = (
        args.show_root_trust_state,
        args.initialize_root_trust_state,
        args.create_root_transition,
        args.verify_root_transition,
        args.retire_manifest_state,
        args.apply_root_transition,
    )
    if args.show_transparency_log is not None or args.verify_transparency_log is not None:
        option_name = "--show-transparency-log" if args.show_transparency_log is not None else "--verify-transparency-log"
        _validate_common_verify_args(parser, args, option_name)
        if args.signing_key_manifest is not None or args.minimum_manifest_generation is not None:
            parser.error(f"{option_name} cannot be used with signing key manifest options")
        if args.manifest_state is not None or args.no_update_manifest_state or args.require_existing_manifest_state:
            parser.error(f"{option_name} cannot be used with manifest state options")
        if args.root_trust_state is not None:
            parser.error(f"{option_name} cannot be used with --root-trust-state")
        if args.register_transparency_entry or args.require_transparency_entry:
            parser.error(f"{option_name} cannot register or require an artifact")
        return

    if any(value is not None for value in root_mode):
        if args.output is not None or args.authenticate or args.archive:
            parser.error("root trust modes cannot be used with report export options")
        if args.since is not None or args.until is not None or args.model is not None:
            parser.error("root trust modes cannot be used with report filters")
        if args.status != AuditStatusFilter.ALL.value or args.format == AuditReportFormat.JSON.value:
            parser.error("root trust modes cannot be used with report filters")
        if args.signing_key_manifest is not None and args.retire_manifest_state is None:
            parser.error("--signing-key-manifest is only valid with manifest modes")

    hmac_policy_used = args.revoked_key_policy != RevokedKeyPolicy.REJECT.value
    signature_policy_used = (
        args.revoked_signature_key_policy != RevokedSignatureKeyPolicy.REJECT.value
    )
    witness_policy_used = args.revoked_witness_policy != RevokedWitnessPolicy.REJECT.value
    if args.show_manifest_state is not None:
        if any(value is not None for value in (args.verify, args.verify_authenticity, args.verify_bundle, args.verify_archive_authenticity, args.verify_archive_signature, args.verify_archive, args.create_signing_key_manifest, args.verify_signing_key_manifest, args.since, args.until, args.model, args.signing_key_manifest, args.minimum_manifest_generation)):
            parser.error("--show-manifest-state cannot be combined with report or verify options")
        if args.output is not None or args.authenticate or args.archive:
            parser.error("--show-manifest-state cannot be used with report export options")
        if args.status != AuditStatusFilter.ALL.value or args.format == AuditReportFormat.JSON.value:
            parser.error("--show-manifest-state cannot be used with report filters")
        if args.manifest_state is not None or args.no_update_manifest_state or args.require_existing_manifest_state:
            parser.error("--show-manifest-state cannot be used with manifest state options")
        if hmac_policy_used or signature_policy_used:
            parser.error("--show-manifest-state cannot be used with revoked key policies")
        return
    if args.initialize_manifest_state is not None:
        if args.signing_key_manifest is None:
            parser.error("--initialize-manifest-state requires --signing-key-manifest")
        if args.output is not None or args.authenticate or args.archive:
            parser.error("--initialize-manifest-state cannot be used with report export options")
        if any(value is not None for value in (args.verify, args.verify_authenticity, args.verify_bundle, args.verify_archive_authenticity, args.verify_archive_signature, args.verify_archive, args.create_signing_key_manifest, args.verify_signing_key_manifest, args.since, args.until, args.model)):
            parser.error("--initialize-manifest-state cannot be combined with report or verify options")
        if args.status != AuditStatusFilter.ALL.value or args.format == AuditReportFormat.JSON.value:
            parser.error("--initialize-manifest-state cannot be used with report filters")
        if args.manifest_state is not None or args.no_update_manifest_state or args.require_existing_manifest_state:
            parser.error("--initialize-manifest-state cannot be used with manifest state options")
        if hmac_policy_used or signature_policy_used:
            parser.error("--initialize-manifest-state cannot be used with revoked key policies")
        _validate_manifest_creation_options_absent(parser, args, "--initialize-manifest-state")
        return
    if args.create_signing_key_manifest is not None:
        if args.manifest_state is not None or args.no_update_manifest_state or args.require_existing_manifest_state:
            parser.error("--create-signing-key-manifest cannot be used with manifest state options")
        if args.output is not None or args.authenticate or args.archive:
            parser.error("--create-signing-key-manifest cannot be used with report export options")
        if any(value is not None for value in (args.verify, args.verify_authenticity, args.verify_bundle, args.verify_archive_authenticity, args.verify_archive_signature, args.verify_archive, args.since, args.until, args.model, args.signing_key_manifest)):
            parser.error("--create-signing-key-manifest cannot be combined with report or verify options")
        if args.status != AuditStatusFilter.ALL.value or args.format == AuditReportFormat.JSON.value:
            parser.error("--create-signing-key-manifest cannot be used with report filters")
        if args.minimum_manifest_generation is not None:
            parser.error("--create-signing-key-manifest cannot be used with --minimum-manifest-generation")
        return
    if args.verify_signing_key_manifest is not None:
        _validate_common_verify_args(parser, args, "--verify-signing-key-manifest")
        if args.signing_key_manifest is not None:
            parser.error("--verify-signing-key-manifest cannot be used with --signing-key-manifest")
        _validate_manifest_creation_options_absent(parser, args, "--verify-signing-key-manifest")
        if hmac_policy_used or signature_policy_used:
            parser.error("--verify-signing-key-manifest cannot be used with revoked key policies")
        return

    if args.verify is not None:
        _validate_common_verify_args(parser, args, "--verify")
        _validate_manifest_creation_options_absent(parser, args, "--verify")
        if args.signing_key_manifest is not None or args.minimum_manifest_generation is not None:
            parser.error("--verify cannot be used with signing key manifest options")
        if hmac_policy_used:
            parser.error("--verify cannot be used with --revoked-key-policy")
        if signature_policy_used:
            parser.error("--verify cannot be used with --revoked-signature-key-policy")
    elif args.verify_authenticity is not None:
        _validate_common_verify_args(parser, args, "--verify-authenticity")
        _validate_manifest_creation_options_absent(parser, args, "--verify-authenticity")
        if args.signing_key_manifest is not None or args.minimum_manifest_generation is not None:
            parser.error("--verify-authenticity cannot be used with signing key manifest options")
        if signature_policy_used:
            parser.error(
                "--verify-authenticity cannot be used with --revoked-signature-key-policy"
            )
    elif args.verify_bundle is not None:
        _validate_common_verify_args(parser, args, "--verify-bundle")
        _validate_manifest_creation_options_absent(parser, args, "--verify-bundle")
        if args.signing_key_manifest is not None or args.minimum_manifest_generation is not None:
            parser.error("--verify-bundle cannot be used with signing key manifest options")
        if signature_policy_used:
            parser.error("--verify-bundle cannot be used with --revoked-signature-key-policy")
    elif args.verify_archive_authenticity is not None:
        _validate_common_verify_args(parser, args, "--verify-archive-authenticity")
        _validate_manifest_creation_options_absent(parser, args, "--verify-archive-authenticity")
        if args.signing_key_manifest is not None or args.minimum_manifest_generation is not None:
            parser.error("--verify-archive-authenticity cannot be used with signing key manifest options")
        if signature_policy_used:
            parser.error(
                "--verify-archive-authenticity cannot be used with --revoked-signature-key-policy"
            )
    elif args.verify_archive_signature is not None:
        _validate_common_verify_args(parser, args, "--verify-archive-signature")
        _validate_manifest_creation_options_absent(parser, args, "--verify-archive-signature")
        if hmac_policy_used:
            parser.error("--verify-archive-signature cannot be used with --revoked-key-policy")
    elif args.verify_archive is not None:
        _validate_common_verify_args(parser, args, "--verify-archive")
        _validate_manifest_creation_options_absent(parser, args, "--verify-archive")
    elif hmac_policy_used:
        parser.error("--revoked-key-policy can only be used with verify modes")
    elif signature_policy_used:
        parser.error("--revoked-signature-key-policy can only be used with signature verify modes")

    state_options_used = (
        args.manifest_state is not None
        or args.no_update_manifest_state
        or args.require_existing_manifest_state
    )
    state_capable_mode = (
        args.verify_signing_key_manifest is not None
        or args.verify_archive_signature is not None
        or args.verify_archive is not None
        or (args.archive and args.authenticate and args.output is not None)
    )
    if state_options_used and not state_capable_mode:
        parser.error("manifest state options require a signing manifest mode")

    transparency_options_used = (
        args.transparency_log is not None
        or args.transparency_log_state is not None
        or args.transparency_log_id is not None
        or args.register_transparency_entry
        or args.require_transparency_entry
    )
    transparency_capable_mode = (
        args.verify_root_transition is not None
        or args.apply_root_transition is not None
        or args.verify_signing_key_manifest is not None
        or args.verify_archive_signature is not None
        or args.verify_archive is not None
        or (args.archive and args.authenticate and args.output is not None)
        or args.create_transparency_checkpoint is not None
        or args.verify_transparency_checkpoint is not None
        or args.show_transparency_checkpoint is not None
        or args.create_inclusion_proof is not None
        or args.verify_inclusion_proof is not None
        or args.create_consistency_proof is not None
        or args.verify_consistency_proof is not None
        or args.create_witness_statement is not None
        or args.verify_witness_statement is not None
        or args.verify_witness_quorum is not None
        or args.create_split_view_evidence is not None
        or args.verify_split_view_evidence is not None
        or args.create_gossip_bundle is not None
        or args.verify_gossip_bundle is not None
        or args.show_gossip_bundle is not None
    )
    if transparency_options_used and not transparency_capable_mode:
        parser.error("transparency log options require a transparency-capable mode")
    register_capable_mode = (
        args.verify_root_transition is not None
        or args.apply_root_transition is not None
        or args.verify_signing_key_manifest is not None
    )
    if args.register_transparency_entry and not register_capable_mode:
        parser.error("--register-transparency-entry cannot be used in this mode")

    witness_modes_used = (
        args.create_witness_statement is not None
        or args.verify_witness_statement is not None
        or args.verify_witness_quorum is not None
        or args.create_split_view_evidence is not None
        or args.verify_split_view_evidence is not None
    )
    witness_options_used = (
        args.witness_trust_store is not None
        or args.witness_state is not None
        or args.witness_statement is not None
        or args.minimum_witness_quorum is not None
        or args.conflicting_checkpoint is not None
    )
    witness_quorum_capable_mode = (
        args.verify_root_transition is not None
        or args.apply_root_transition is not None
        or args.verify_signing_key_manifest is not None
        or args.verify_archive_signature is not None
        or args.verify_archive is not None
    )
    gossip_bundle_mode = (
        args.create_gossip_bundle is not None
        or args.verify_gossip_bundle is not None
    )
    if args.transparency_checkpoint is not None and (
        args.create_inclusion_proof is None
        and args.verify_inclusion_proof is None
        and args.create_witness_statement is None
        and args.verify_witness_statement is None
        and args.verify_witness_quorum is None
        and args.create_split_view_evidence is None
        and args.verify_split_view_evidence is None
        and args.create_gossip_bundle is None
        and not witness_quorum_capable_mode
    ):
        parser.error(
            "--transparency-checkpoint can only be used with "
            "proof, witness, split-view, or gossip-bundle modes"
        )
    if args.create_inclusion_proof is not None:
        if args.transparency_checkpoint is None:
            parser.error("--create-inclusion-proof requires --transparency-checkpoint")
        if args.transparency_log is None:
            parser.error("--create-inclusion-proof requires --transparency-log")
        if args.transparency_log_state is None:
            parser.error("--create-inclusion-proof requires --transparency-log-state")
        if args.artifact_identifier is None:
            parser.error("--create-inclusion-proof requires --artifact-identifier")
    if args.verify_inclusion_proof is not None and args.transparency_checkpoint is None:
        parser.error("--verify-inclusion-proof requires --transparency-checkpoint")

    if args.consistency_proof is not None:
        if args.no_update_checkpoint_state:
            parser.error("--consistency-proof cannot be used with --no-update-checkpoint-state")
        if args.verify_transparency_checkpoint is None:
            parser.error("--consistency-proof can only be used with checkpoint state update")
        if args.checkpoint_state is None:
            parser.error("--consistency-proof requires --checkpoint-state")
        if not args.update_checkpoint_state:
            parser.error("--consistency-proof requires --update-checkpoint-state")

    if witness_policy_used and not (witness_modes_used or witness_options_used):
        parser.error("--revoked-witness-policy can only be used with witness verify modes")
    if witness_options_used and not (
        witness_modes_used
        or witness_quorum_capable_mode
        or gossip_bundle_mode
    ):
        parser.error(
            "witness options require a witness-capable "
            "or gossip-bundle mode"
        )
    if witness_modes_used:
        _validate_common_verify_args(parser, args, "witness mode")
    if witness_options_used and (
        witness_quorum_capable_mode
        or args.create_gossip_bundle is not None
    ):
        if args.transparency_checkpoint is None:
            parser.error("witness quorum requires --transparency-checkpoint")
        if args.witness_trust_store is None:
            parser.error("witness quorum requires --witness-trust-store")
        if not args.witness_statement:
            parser.error("witness quorum requires --witness-statement")
    if args.create_witness_statement is not None:
        if args.transparency_checkpoint is None:
            parser.error("--create-witness-statement requires --transparency-checkpoint")
        if args.witness_state is None:
            parser.error("--create-witness-statement requires --witness-state")
    if args.verify_witness_statement is not None:
        if args.transparency_checkpoint is None:
            parser.error("--verify-witness-statement requires --transparency-checkpoint")
        if args.witness_trust_store is None:
            parser.error("--verify-witness-statement requires --witness-trust-store")
    if args.verify_witness_quorum is not None:
        if args.witness_trust_store is None:
            parser.error("--verify-witness-quorum requires --witness-trust-store")
        if not args.witness_statement:
            parser.error("--verify-witness-quorum requires --witness-statement")
    if args.create_split_view_evidence is not None:
        if args.transparency_checkpoint is None:
            parser.error("--create-split-view-evidence requires --transparency-checkpoint")
        if args.conflicting_checkpoint is None:
            parser.error("--create-split-view-evidence requires --conflicting-checkpoint")
    if args.verify_split_view_evidence is not None and args.witness_trust_store is None:
        parser.error("--verify-split-view-evidence requires --witness-trust-store")

    gossip_modes_used = (
        args.create_gossip_bundle is not None
        or args.verify_gossip_bundle is not None
        or args.show_gossip_bundle is not None
    )
    gossip_options_used = (
        args.target_artifact is not None
        or args.artifact_type is not None
        or args.inclusion_proof is not None
        or args.bundle_signing_trust_store is not None
        or args.create_decision_receipt is not None
    )
    if args.create_gossip_bundle is not None:
        _validate_common_verify_args(parser, args, "--create-gossip-bundle")
        if args.target_artifact is None:
            parser.error("--create-gossip-bundle requires --target-artifact")
        if args.artifact_type is None:
            parser.error("--create-gossip-bundle requires --artifact-type")
        if args.artifact_identifier is None:
            parser.error("--create-gossip-bundle requires --artifact-identifier")
        if args.transparency_checkpoint is None:
            parser.error("--create-gossip-bundle requires --transparency-checkpoint")
        if args.inclusion_proof is None:
            parser.error("--create-gossip-bundle requires --inclusion-proof")
        if args.witness_trust_store is None:
            parser.error("--create-gossip-bundle requires --witness-trust-store")
        if not args.witness_statement:
            parser.error("--create-gossip-bundle requires --witness-statement")
    elif args.verify_gossip_bundle is not None:
        _validate_common_verify_args(parser, args, "--verify-gossip-bundle")
        if args.target_artifact is None:
            parser.error("--verify-gossip-bundle requires --target-artifact")
        if args.bundle_signing_trust_store is None:
            parser.error("--verify-gossip-bundle requires --bundle-signing-trust-store")
    elif args.show_gossip_bundle is not None:
        _validate_common_verify_args(parser, args, "--show-gossip-bundle")
    elif gossip_options_used:
        parser.error("gossip bundle options require a gossip bundle mode")

    if args.verify_decision_receipt is not None:
        _validate_common_verify_args(parser, args, "--verify-decision-receipt")
        if args.decision_receipt_trust_store is None:
            parser.error("--verify-decision-receipt requires --decision-receipt-trust-store")
    elif args.decision_receipt is not None:
        parser.error("--decision-receipt requires a receipt-capable mode")
    elif (
        args.decision_receipt_trust_store is not None
        and not (
            args.verify_gossip_bundle is not None
            and args.create_decision_receipt is not None
        )
    ):
        parser.error(
            "--decision-receipt-trust-store requires "
            "a receipt-capable mode"
        )
    elif args.verification_policy_id != "default" and not gossip_modes_used:
        parser.error("--verification-policy-id requires a receipt-capable mode")

    if not args.archive and (args.signing_key_manifest is not None or args.minimum_manifest_generation is not None):
        parser.error("signing key manifest options require --archive")
    if args.manifest_generation is not None or args.manifest_valid_from is not None or args.manifest_valid_until is not None:
        parser.error("manifest creation options require --create-signing-key-manifest")
    if args.archive and args.output is None:
        parser.error("--archive requires --output")
    if args.archive and not args.authenticate:
        parser.error("--archive requires --authenticate")
    if args.authenticate and args.output is None:
        parser.error("--authenticate requires --output")
    if args.output is not None and args.format != AuditReportFormat.JSON.value:
        parser.error("--output requires --format json")


def _validate_manifest_creation_options_absent(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    option_name: str,
) -> None:
    if args.manifest_generation is not None:
        parser.error(f"{option_name} cannot be used with --manifest-generation")
    if args.manifest_valid_from is not None:
        parser.error(f"{option_name} cannot be used with --manifest-valid-from")
    if args.manifest_valid_until is not None:
        parser.error(f"{option_name} cannot be used with --manifest-valid-until")


def _validate_common_verify_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    option_name: str,
) -> None:
    if args.output is not None:
        parser.error(f"{option_name} cannot be used with --output")
    if args.authenticate:
        parser.error(f"{option_name} cannot be used with --authenticate")
    if args.archive:
        parser.error(f"{option_name} cannot be used with --archive")
    if args.since is not None:
        parser.error(f"{option_name} cannot be used with --since")
    if args.until is not None:
        parser.error(f"{option_name} cannot be used with --until")
    if args.model is not None:
        parser.error(f"{option_name} cannot be used with --model")
    if args.status != AuditStatusFilter.ALL.value:
        parser.error(f"{option_name} cannot be used with --status")
    if args.format == AuditReportFormat.JSON.value:
        parser.error(f"{option_name} cannot be used with --format json")


def _run_report_generation(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        report_filter = AuditReportFilter(
            since=args.since,
            until=args.until,
            model=args.model,
            status=AuditStatusFilter(args.status),
        )
    except ValueError as error:
        parser.error(str(error))

    try:
        events = read_audit_events(AUDIT_LOG_PATH)
        filtered_events = filter_audit_events(events=events, report_filter=report_filter)
        report = build_audit_report(filtered_events)
        rendered_report = render_audit_report(
            report=report,
            report_filter=report_filter,
            report_format=AuditReportFormat(args.format),
        )
        if args.output is None:
            print(rendered_report)
            return 0
        if args.authenticate:
            return _export_authenticated_report(args, parser, rendered_report)
        checksum = export_json_report_with_checksum(path=args.output, json_text=rendered_report)
        print("Audit report exported successfully.")
        print(f"Output: {args.output}")
        print(f"Checksum: {checksum_path_for(args.output)}")
        print(f"SHA-256: {checksum.digest}")
        return 0
    except (
        ArchiveAuthenticityError,
        ArchiveSignatureError,
        AuditLogError,
        ManifestTrustStateError,
        ManifestTrustStateValidationError,
        ReportArchiveError,
        ReportAuthenticityError,
        ReportBundleError,
        ReportExportError,
        ReportIntegrityError,
        RootSignatureTrustError,
        RootTrustStateError,
        SigningKeyManifestError,
        TransparencyLogError,
        TransparencyLogStateError,
    ) as error:
        _print_recovery_error(header="[ERROR] Audit report generation failed", error=error)
        return 5


def _export_authenticated_report(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    rendered_report: str,
) -> int:
    exported_at = datetime.now(UTC)
    trust_store = load_authentication_trust_store(environ=os.environ)
    if args.archive:
        signing_key = load_archive_signing_private_key(environ=os.environ)
        root_state = _load_current_root_state(args, None)
        (
            checksum,
            authentication,
            manifest,
            archive,
            archive_authentication,
            signature,
            state_decision,
            transparency_inclusion,
        ) = export_json_report_signed_archive_with_root_state_and_transparency(
            path=args.output,
            json_text=rendered_report,
            trust_store=trust_store,
            authenticated_at=exported_at,
            signing_key=signing_key,
            manifest_path=_resolve_signing_key_manifest_path(args, parser),
            root_state=root_state,
            state_path=_resolve_manifest_state_path(args),
            transparency_log_path=_resolve_transparency_log_path(args, parser),
            transparency_state_path=_resolve_transparency_state_path(args, parser),
            signed_at=exported_at,
            minimum_generation=_resolve_minimum_manifest_generation(args, parser),
            state_mode=_resolve_manifest_state_mode(args),
            require_existing_state=args.require_existing_manifest_state,
        )
    else:
        checksum, authentication, manifest = export_json_report_bundle(
            path=args.output,
            json_text=rendered_report,
            trust_store=trust_store,
            authenticated_at=exported_at,
        )
        archive = None
        archive_authentication = None
        signature = None
        state_decision = None
        transparency_inclusion = None

    print("Audit report exported successfully.")
    print(f"Output: {args.output}")
    print(f"Checksum: {checksum_path_for(args.output)}")
    print(f"SHA-256: {checksum.digest}")
    print(f"Authentication: {authentication_path_for(args.output)}")
    print(f"Manifest: {manifest_path_for(args.output)}")
    print(f"Manifest Version: {manifest.manifest_version}")
    print(f"Algorithm: {authentication.algorithm}")
    print(f"Key ID: {authentication.key_id}")
    print(f"Authenticated At: {authentication.authenticated_at.isoformat()}")
    print(f"HMAC: {authentication.digest}")
    if archive is not None and archive_authentication is not None and signature is not None:
        archive_path = archive_path_for(args.output)
        print(f"Archive: {archive_path}")
        print(f"Archive Format Version: {REPORT_ARCHIVE_FORMAT_VERSION}")
        print(f"Archive Members: {archive.member_count}")
        print(f"Archive SHA-256: {archive.archive_sha256}")
        print(f"Archive Authentication: {archive_authentication_path_for(archive_path)}")
        print(f"Archive Authentication Algorithm: {archive_authentication.algorithm}")
        print(
            "Archive Authentication Protocol Version: "
            f"{archive_authentication.protocol_version}"
        )
        print(f"Archive Authentication Key ID: {archive_authentication.key_id}")
        print(f"Archive Authenticated At: {archive_authentication.authenticated_at.isoformat()}")
        print(f"Archive HMAC: {archive_authentication.digest}")
        if state_decision is not None:
            _print_manifest_state_decision(args, state_decision)
        if transparency_inclusion is not None:
            _print_transparency_inclusion(transparency_inclusion)
        print(f"Signature: {archive_signature_path_for(archive_path)}")
        print(f"Signature Algorithm: {signature.algorithm}")
        print(f"Signature Protocol Version: {signature.signature_version}")
        print(f"Signature Key ID: {signature.key_id}")
        print(f"Signature Public Key Fingerprint: {signature.public_key_fingerprint}")
        print(f"Signed At: {signature.signed_at.isoformat()}")
        print(f"Signature Archive SHA-256: {signature.archive_sha256}")
    return 0


def _resolve_signing_key_manifest_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
) -> Path:
    if args.signing_key_manifest is not None:
        return args.signing_key_manifest
    env_value = os.environ.get(SIGNING_KEY_MANIFEST_PATH_ENV_NAME)
    if env_value:
        return Path(env_value)
    if parser is not None:
        parser.error("--signing-key-manifest is required")
    raise SigningKeyManifestReadError("Failed to read the archive signing key manifest.")


def _resolve_minimum_manifest_generation(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
) -> int:
    if args.minimum_manifest_generation is not None:
        value = args.minimum_manifest_generation
    else:
        env_value = os.environ.get(MIN_SIGNING_KEY_MANIFEST_GENERATION_ENV_NAME)
        if env_value is None or env_value == "":
            return 1
        try:
            value = int(env_value)
        except ValueError:
            if parser is not None:
                parser.error("minimum manifest generation must be a positive integer")
            raise SigningKeyManifestValidationError(
                "The archive signing key manifest failed validation."
            )
    if value < 1:
        if parser is not None:
            parser.error("minimum manifest generation must be a positive integer")
        raise SigningKeyManifestValidationError("The archive signing key manifest failed validation.")
    return value


def _resolve_manifest_state_path(args: argparse.Namespace) -> Path | None:
    if args.manifest_state is not None:
        return args.manifest_state
    env_value = os.environ.get(MANIFEST_TRUST_STATE_ENV_NAME)
    if env_value:
        return Path(env_value)
    return None


def _resolve_manifest_state_mode(args: argparse.Namespace) -> ManifestTrustStateMode:
    if args.no_update_manifest_state:
        return ManifestTrustStateMode.READ_ONLY
    return ManifestTrustStateMode.UPDATE


def _resolve_transparency_log_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
) -> Path:
    if args.transparency_log is not None:
        return args.transparency_log
    env_value = os.environ.get(TRANSPARENCY_LOG_PATH_ENV_NAME)
    if env_value:
        return Path(env_value)
    if parser is not None:
        parser.error("--transparency-log is required")
    raise TransparencyLogError("The transparency log is required.")


def _resolve_transparency_state_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
) -> Path:
    if args.transparency_log_state is not None:
        return args.transparency_log_state
    env_value = os.environ.get(TRANSPARENCY_LOG_STATE_PATH_ENV_NAME)
    if env_value:
        return Path(env_value)
    if parser is not None:
        parser.error("--transparency-log-state is required")
    raise TransparencyLogStateError("The transparency log state is required.")


def _resolve_transparency_mode(args: argparse.Namespace) -> TransparencyLogMode | None:
    if args.register_transparency_entry:
        return TransparencyLogMode.REGISTER_IF_MISSING
    if args.require_transparency_entry:
        return TransparencyLogMode.REQUIRE_EXISTING
    return None


def _print_transparency_inclusion(inclusion: TransparencyLogInclusionResult) -> None:
    print(f"Transparency Sequence: {inclusion.sequence}")
    print(f"Transparency Entry Hash: {inclusion.entry_hash}")
    print(f"Transparency Recorded At: {inclusion.recorded_at.isoformat()}")


def _print_transparency_append_result(result: TransparencyLogAppendResult) -> None:
    print(f"Transparency Entry Registered: {str(result.entry_registered).lower()}")
    _print_transparency_inclusion(result.inclusion)


def _print_manifest_state_decision(
    args: argparse.Namespace,
    decision: ManifestTrustStateDecision,
) -> None:
    _print_manifest_state_decision_for_values(
        state_path=_resolve_manifest_state_path(args),
        state_mode=_resolve_manifest_state_mode(args),
        decision=decision,
    )


def _print_manifest_state_decision_for_values(
    *,
    state_path: Path | None,
    state_mode: ManifestTrustStateMode,
    decision: ManifestTrustStateDecision,
) -> None:
    stored_generation = (
        str(decision.stored_state.highest_generation)
        if decision.stored_state is not None
        else "none"
    )
    print(f"Manifest State: {state_path if state_path is not None else 'unavailable'}")
    print(f"Manifest State Mode: {state_mode.value}")
    print(f"Stored Generation: {stored_generation}")
    print(f"Effective Minimum Generation: {decision.effective_minimum_generation}")
    print(f"State Updated: {str(decision.state_updated).lower()}")


def _resolve_root_trust_state_path(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
) -> Path:
    if args.root_trust_state is not None:
        return args.root_trust_state
    env_value = os.environ.get(ROOT_TRUST_STATE_ENV_NAME)
    if env_value:
        return Path(env_value)
    if parser is not None:
        parser.error("--root-trust-state is required")
    raise RootTrustStateError("The root trust state is missing.")


def _load_current_root_state(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
):
    state = load_root_trust_state(path=_resolve_root_trust_state_path(args, parser))
    if state is None:
        raise RootTrustStateError("The root trust state is missing.")
    return state


def _resolve_transparency_log_id(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.transparency_log_id:
        return args.transparency_log_id
    env_value = os.environ.get("AUDIT_REPORT_TRANSPARENCY_LOG_ID")
    if env_value:
        return env_value
    parser.error("--transparency-log-id is required")
    raise AssertionError("unreachable")


def _run_create_transparency_checkpoint(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        result = create_transparency_checkpoint(
            output_path=args.create_transparency_checkpoint,
            log_path=_resolve_transparency_log_path(args, parser),
            log_state_path=_resolve_transparency_state_path(args, parser),
            log_id=_resolve_transparency_log_id(args, parser),
            issued_at=datetime.now(UTC),
        )
    except (TransparencyCheckpointError, TransparencyLogError, TransparencyLogStateError) as error:
        _print_recovery_error(header="[ERROR] Transparency checkpoint generation failed", error=error)
        return 5
    print("Transparency checkpoint created.")
    print(f"Checkpoint: {args.create_transparency_checkpoint}")
    print(f"Signature: {checkpoint_signature_path_for(args.create_transparency_checkpoint)}")
    print(f"Log ID: {result.checkpoint.log_id}")
    print(f"Tree Size: {result.checkpoint.tree_size}")
    print(f"Root Hash: {result.checkpoint.root_hash}")
    print(f"Last Sequence: {result.checkpoint.last_sequence}")
    print(f"Issued At: {result.checkpoint.issued_at.isoformat()}")
    print(f"Log Signing Key ID: {result.checkpoint.log_signing_key_id}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")
    return 0


def _run_verify_transparency_checkpoint_file(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        mode = (
            TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG
            if args.transparency_log is not None or os.environ.get(TRANSPARENCY_LOG_PATH_ENV_NAME)
            else TransparencyCheckpointVerificationMode.SIGNATURE_ONLY
        )
        result = verify_transparency_checkpoint(
            checkpoint_path=args.verify_transparency_checkpoint,
            log_path=_resolve_transparency_log_path(args, parser) if mode is TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG else None,
            log_state_path=_resolve_transparency_state_path(args, parser) if mode is TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG else None,
            mode=mode,
        )
        state_result = None
        if args.update_checkpoint_state:
            if args.checkpoint_state is None:
                parser.error("--checkpoint-state is required")
            consistency = None
            stored_checkpoint_state = load_transparency_checkpoint_state(
                path=args.checkpoint_state,
            )
            if args.consistency_proof is not None:
                if stored_checkpoint_state is None:
                    parser.error("--consistency-proof requires existing --checkpoint-state")
                if result.tree_size > stored_checkpoint_state.highest_tree_size:
                    old = SimpleNamespace(
                        log_id=stored_checkpoint_state.log_id,
                        tree_size=stored_checkpoint_state.highest_tree_size,
                        root_hash=stored_checkpoint_state.highest_root_hash,
                    )
                    proof = load_transparency_consistency_proof(
                        path=args.consistency_proof,
                    )
                    consistency = verify_checkpoint_consistency_proof(
                        old_checkpoint=old,
                        new_checkpoint=result,
                        proof=proof,
                    )
            state_result = apply_verified_checkpoint_to_state(
                state_path=args.checkpoint_state,
                checkpoint=result,
                consistency_proof=consistency,
                updated_at=datetime.now(UTC),
            )
    except (TransparencyCheckpointError, TransparencyCheckpointStateError, TransparencyLogError, TransparencyLogStateError, TransparencyMerkleError) as error:
        _print_recovery_error(header="[ERROR] Transparency checkpoint verification failed", error=error)
        return 5
    _print_checkpoint_result("Transparency checkpoint verified.", result)
    if state_result is not None:
        print(f"Checkpoint State Updated: {str(state_result.state_updated).lower()}")
    return 0


def _run_show_transparency_checkpoint(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        result = verify_transparency_checkpoint(
            checkpoint_path=args.show_transparency_checkpoint,
            log_path=None,
            log_state_path=None,
            mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
        )
    except TransparencyCheckpointError as error:
        _print_recovery_error(header="[ERROR] Transparency checkpoint inspection failed", error=error)
        return 5
    _print_checkpoint_result("Transparency checkpoint.", result)
    return 0


def _print_checkpoint_result(header: str, result) -> None:
    print(header)
    print(f"Log ID: {result.log_id}")
    print(f"Tree Size: {result.tree_size}")
    print(f"Root Hash: {result.root_hash}")
    print(f"Last Entry Hash: {result.last_entry_hash}")
    print(f"Issued At: {result.issued_at.isoformat()}")
    print(f"Log Signing Key ID: {result.log_signing_key_id}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")


def _verify_optional_witness_quorum(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    if not (
        args.witness_trust_store is not None
        or args.witness_statement is not None
        or args.minimum_witness_quorum is not None
    ):
        return
    checkpoint = verify_transparency_checkpoint(
        checkpoint_path=args.transparency_checkpoint,
        log_path=None,
        log_state_path=None,
        mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
    )
    trust_store = load_transparency_witness_trust_store(path=args.witness_trust_store)
    verify_transparency_witness_quorum(
        checkpoint=checkpoint,
        statement_paths=tuple(args.witness_statement),
        trust_store=trust_store,
        verification_time=datetime.now(UTC),
        required_quorum=args.minimum_witness_quorum,
        revoked_witness_policy=RevokedWitnessPolicy(args.revoked_witness_policy),
    )


def _run_create_inclusion_proof(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        checkpoint = verify_transparency_checkpoint(
            checkpoint_path=args.transparency_checkpoint,
            log_path=_resolve_transparency_log_path(args, parser),
            log_state_path=_resolve_transparency_state_path(args, parser),
            mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG,
        )
        verification = verify_transparency_log(log_path=_resolve_transparency_log_path(args, parser), state_path=_resolve_transparency_state_path(args, parser))
        inclusion = verification.entries_by_identifier.get(args.artifact_identifier)
        if inclusion is None:
            raise TransparencyMerkleError("The transparency inclusion proof does not match.")
        proof = generate_checkpoint_inclusion_proof(
            checkpoint=checkpoint,
            log_path=_resolve_transparency_log_path(args, parser),
            log_state_path=_resolve_transparency_state_path(args, parser),
            inclusion=inclusion,
            issued_at=datetime.now(UTC),
        )
        export_transparency_inclusion_proof(path=args.create_inclusion_proof, proof=proof)
    except (TransparencyCheckpointError, TransparencyLogError, TransparencyLogStateError, TransparencyMerkleError) as error:
        _print_recovery_error(header="[ERROR] Transparency inclusion proof generation failed", error=error)
        return 5
    print("Transparency inclusion proof created.")
    print(f"Proof: {args.create_inclusion_proof}")
    print(f"Artifact Identifier: {args.artifact_identifier}")
    print(f"Tree Size: {proof.tree_size}")
    print(f"Sequence: {proof.sequence}")
    return 0


def _run_verify_inclusion_proof(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        checkpoint = verify_transparency_checkpoint(
            checkpoint_path=args.transparency_checkpoint,
            log_path=None,
            log_state_path=None,
            mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
        )
        proof = load_transparency_inclusion_proof(path=args.verify_inclusion_proof)
        result = verify_checkpoint_inclusion_proof(checkpoint=checkpoint, proof=proof)
    except (TransparencyCheckpointError, TransparencyMerkleError) as error:
        _print_recovery_error(header="[ERROR] Transparency inclusion proof verification failed", error=error)
        return 5
    print("Transparency inclusion proof verified.")
    print(f"Log ID: {result.log_id}")
    print(f"Tree Size: {result.tree_size}")
    print(f"Sequence: {result.sequence}")
    return 0


def _run_create_consistency_proof(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.old_checkpoint is None or args.new_checkpoint is None:
        parser.error("--create-consistency-proof requires --old-checkpoint and --new-checkpoint")
    try:
        old = verify_transparency_checkpoint(checkpoint_path=args.old_checkpoint, log_path=None, log_state_path=None, mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY)
        new = verify_transparency_checkpoint(checkpoint_path=args.new_checkpoint, log_path=_resolve_transparency_log_path(args, parser), log_state_path=_resolve_transparency_state_path(args, parser), mode=TransparencyCheckpointVerificationMode.VERIFY_AGAINST_LOG)
        proof = generate_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=new, log_path=_resolve_transparency_log_path(args, parser), log_state_path=_resolve_transparency_state_path(args, parser), issued_at=datetime.now(UTC))
        export_transparency_consistency_proof(path=args.create_consistency_proof, proof=proof)
    except (TransparencyCheckpointError, TransparencyLogError, TransparencyLogStateError, TransparencyMerkleError) as error:
        _print_recovery_error(header="[ERROR] Transparency consistency proof generation failed", error=error)
        return 5
    print("Transparency consistency proof created.")
    print(f"Proof: {args.create_consistency_proof}")
    print(f"Old Tree Size: {proof.old_tree_size}")
    print(f"New Tree Size: {proof.new_tree_size}")
    return 0


def _run_verify_consistency_proof(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.old_checkpoint is None or args.new_checkpoint is None:
        parser.error("--verify-consistency-proof requires --old-checkpoint and --new-checkpoint")
    try:
        old = verify_transparency_checkpoint(checkpoint_path=args.old_checkpoint, log_path=None, log_state_path=None, mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY)
        new = verify_transparency_checkpoint(checkpoint_path=args.new_checkpoint, log_path=None, log_state_path=None, mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY)
        proof = load_transparency_consistency_proof(path=args.verify_consistency_proof)
        result = verify_checkpoint_consistency_proof(old_checkpoint=old, new_checkpoint=new, proof=proof)
    except (TransparencyCheckpointError, TransparencyMerkleError) as error:
        _print_recovery_error(header="[ERROR] Transparency consistency proof verification failed", error=error)
        return 5
    print("Transparency consistency proof verified.")
    print(f"Log ID: {result.log_id}")
    print(f"Old Tree Size: {result.old_tree_size}")
    print(f"New Tree Size: {result.new_tree_size}")
    return 0


def _run_create_witness_statement(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        result = create_transparency_witness_statement(
            checkpoint_path=args.transparency_checkpoint,
            output_path=args.create_witness_statement,
            witness_state_path=args.witness_state,
            observed_at=datetime.now(UTC),
            consistency_proof_path=args.consistency_proof,
            log_path=args.transparency_log,
            log_state_path=args.transparency_log_state,
            environ=os.environ,
        )
    except (
        TransparencyCheckpointError,
        TransparencyCheckpointStateError,
    TransparencyDecisionReceiptError,
    TransparencyGossipBundleError,
        TransparencyLogError,
        TransparencyLogStateError,
        TransparencyMerkleError,
        TransparencyWitnessError,
    ) as error:
        _print_recovery_error(
            header="[ERROR] Transparency witness statement generation failed",
            error=error,
        )
        return 5
    print("Transparency witness statement created.")
    print(f"Statement: {args.create_witness_statement}")
    print(f"Witness ID: {result.envelope.statement.witness_id}")
    print(f"Tree Size: {result.envelope.statement.tree_size}")
    print(f"Checkpoint SHA-256: {result.envelope.statement.checkpoint_sha256}")
    print(f"State Updated: {str(result.state_updated).lower()}")
    return 0


def _run_verify_witness_statement(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        checkpoint = verify_transparency_checkpoint(
            checkpoint_path=args.transparency_checkpoint,
            log_path=None,
            log_state_path=None,
            mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
        )
        trust_store = load_transparency_witness_trust_store(path=args.witness_trust_store)
        result = verify_transparency_witness_statement(
            statement_path=args.verify_witness_statement,
            checkpoint=checkpoint,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_witness_policy=RevokedWitnessPolicy(args.revoked_witness_policy),
        )
    except (TransparencyCheckpointError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency witness statement verification failed",
            error=error,
        )
        return 5
    print("Transparency witness statement verified.")
    print(f"Witness ID: {result.witness_id}")
    print(f"Tree Size: {result.tree_size}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")
    return 0


def _run_verify_witness_quorum(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        checkpoint = verify_transparency_checkpoint(
            checkpoint_path=args.verify_witness_quorum,
            log_path=None,
            log_state_path=None,
            mode=TransparencyCheckpointVerificationMode.SIGNATURE_ONLY,
        )
        trust_store = load_transparency_witness_trust_store(path=args.witness_trust_store)
        result = verify_transparency_witness_quorum(
            checkpoint=checkpoint,
            statement_paths=tuple(args.witness_statement),
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            required_quorum=args.minimum_witness_quorum,
            revoked_witness_policy=RevokedWitnessPolicy(args.revoked_witness_policy),
        )
    except (TransparencyCheckpointError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency witness quorum verification failed",
            error=error,
        )
        return 5
    print("Transparency witness quorum verified.")
    print(f"Required Quorum: {result.required_quorum}")
    print(f"Valid Witness Count: {result.valid_witness_count}")
    print(f"Valid Witness IDs: {', '.join(result.valid_witness_ids)}")
    print(f"Quorum Satisfied: {str(result.quorum_satisfied).lower()}")
    return 0


def _run_create_split_view_evidence(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        envelope = create_transparency_split_view_evidence(
            checkpoint_path=args.transparency_checkpoint,
            conflicting_checkpoint_path=args.conflicting_checkpoint,
            output_path=args.create_split_view_evidence,
            detected_at=datetime.now(UTC),
            environ=os.environ,
        )
    except (TransparencyCheckpointError, TransparencyWitnessError, TransparencySplitViewEvidenceError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency split-view evidence generation failed",
            error=error,
        )
        return 5
    print("Transparency split-view evidence created.")
    print(f"Evidence: {args.create_split_view_evidence}")
    print(f"Witness ID: {envelope.evidence.detected_by_witness_id}")
    print(f"Tree Size: {envelope.evidence.tree_size}")
    return 0


def _run_verify_split_view_evidence(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        trust_store = load_transparency_witness_trust_store(path=args.witness_trust_store)
        result = verify_transparency_split_view_evidence(
            evidence_path=args.verify_split_view_evidence,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_witness_policy=RevokedWitnessPolicy(args.revoked_witness_policy),
        )
    except (TransparencyWitnessError, TransparencySplitViewEvidenceError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency split-view evidence verification failed",
            error=error,
        )
        return 5
    print("Transparency split-view evidence verified.")
    print(f"Evidence ID: {result.evidence_id}")
    print(f"Witness ID: {result.witness_id}")
    print(f"Tree Size: {result.tree_size}")
    return 0



def _run_create_gossip_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        result = create_transparency_gossip_bundle(
            output_path=args.create_gossip_bundle,
            target_artifact_path=args.target_artifact,
            artifact_type=args.artifact_type,
            artifact_identifier=args.artifact_identifier,
            checkpoint_path=args.transparency_checkpoint,
            inclusion_proof_path=args.inclusion_proof,
            witness_trust_store_path=args.witness_trust_store,
            witness_statement_paths=tuple(args.witness_statement),
            required_witness_quorum=args.minimum_witness_quorum,
            created_at=datetime.now(UTC),
            consistency_proof_path=args.consistency_proof,
            environ=os.environ,
        )
    except (
        TransparencyCheckpointError,
        TransparencyGossipBundleError,
        TransparencyLogError,
        TransparencyLogStateError,
        TransparencyMerkleError,
        TransparencyWitnessError,
    ) as error:
        _print_recovery_error(
            header="[ERROR] Transparency gossip bundle generation failed",
            error=error,
        )
        return 5
    print("Transparency gossip bundle created.")
    print(f"Bundle: {args.create_gossip_bundle}")
    print(f"Bundle ID: {result.bundle_id}")
    print(f"Bundle SHA-256: {result.bundle_sha256}")
    print(f"Artifact Identifier: {result.artifact_identifier}")
    print(f"Artifact SHA-256: {result.artifact_sha256}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")
    print(f"Witness Count: {result.witness_count}")
    print(f"Bundle Reused: {str(result.bundle_reused).lower()}")
    return 0


def _run_verify_gossip_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        trust_store = load_gossip_bundle_signing_trust_store(
            path=args.bundle_signing_trust_store,
            environ=os.environ,
        )
        result = verify_transparency_gossip_bundle_offline(
            bundle_path=args.verify_gossip_bundle,
            target_artifact_path=args.target_artifact,
            bundle_signing_trust_store=trust_store,
            verification_time=datetime.now(UTC),
            local_minimum_quorum=args.minimum_witness_quorum,
            revoked_witness_policy=RevokedWitnessPolicy(args.revoked_witness_policy),
        )
        receipt_path = args.create_decision_receipt
        if receipt_path is not None:
            receipt = build_trusted_decision_receipt(
                result=result,
                policy_id=args.verification_policy_id,
                verifier_version="agentic-ai-lab-cli",
                verified_at=datetime.now(UTC),
            )
            receipt_trust_store = (
                load_decision_receipt_trust_store(
                    path=args.decision_receipt_trust_store,
                    environ=os.environ,
                )
                if args.decision_receipt_trust_store is not None
                else None
            )
            create_transparency_trust_decision_receipt(
                output_path=receipt_path,
                receipt=receipt,
                signed_at=datetime.now(UTC),
                trust_store=receipt_trust_store,
                environ=os.environ,
            )
    except (
        TransparencyCheckpointError,
        TransparencyDecisionReceiptError,
        TransparencyGossipBundleError,
        TransparencyMerkleError,
        TransparencyOfflineVerificationError,
        TransparencyWitnessError,
    ) as error:
        _print_recovery_error(
            header="[ERROR] Transparency gossip bundle verification failed",
            error=error,
        )
        return 5
    print("Transparency gossip bundle verified.")
    print(f"Bundle: {args.verify_gossip_bundle}")
    print(f"Bundle ID: {result.bundle_id}")
    print(f"Bundle SHA-256: {result.bundle_sha256}")
    print(f"Artifact Identifier: {result.artifact_identifier}")
    print(f"Artifact SHA-256: {result.artifact_sha256}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")
    print(f"Tree Size: {result.tree_size}")
    print(f"Required Quorum: {result.required_witness_quorum}")
    print(f"Valid Witness Count: {result.valid_witness_count}")
    print(f"Valid Witness IDs: {', '.join(result.valid_witness_ids)}")
    print(f"Quorum Satisfied: {str(result.quorum_satisfied).lower()}")
    if args.create_decision_receipt is not None:
        print("Decision: trusted")
        print(f"Receipt: {args.create_decision_receipt}")
    return 0


def _run_show_gossip_bundle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        loaded = load_transparency_gossip_bundle(path=args.show_gossip_bundle)
    except TransparencyGossipBundleError as error:
        _print_recovery_error(
            header="[ERROR] Transparency gossip bundle inspection failed",
            error=error,
        )
        return 5
    manifest = loaded.manifest
    print("Transparency gossip bundle.")
    print(f"Bundle: {args.show_gossip_bundle}")
    print(f"Bundle ID: {manifest.bundle_id}")
    print(f"Log ID: {manifest.log_id}")
    print(f"Artifact Identifier: {manifest.artifact_identifier}")
    print(f"Artifact SHA-256: {manifest.artifact_sha256}")
    print(f"Checkpoint SHA-256: {manifest.checkpoint_sha256}")
    print(f"Required Quorum: {manifest.required_witness_quorum}")
    print(f"Witness Statements: {len(manifest.witness_statement_sha256s)}")
    return 0


def _run_verify_decision_receipt(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        trust_store = load_decision_receipt_trust_store(
            path=args.decision_receipt_trust_store,
            environ=os.environ,
        )
        result = verify_transparency_trust_decision_receipt(
            receipt_path=args.verify_decision_receipt,
            trust_store=trust_store,
        )
    except TransparencyDecisionReceiptError as error:
        _print_recovery_error(
            header="[ERROR] Transparency trust decision receipt verification failed",
            error=error,
        )
        return 5
    print("Transparency trust decision receipt verified.")
    print(f"Decision: {result.decision.value}")
    print(f"Bundle ID: {result.bundle_id}")
    print(f"Artifact Identifier: {result.artifact_identifier}")
    print(f"Artifact SHA-256: {result.artifact_sha256}")
    print(f"Checkpoint SHA-256: {result.checkpoint_sha256}")
    if result.rejection_code is not None:
        print(f"Rejection Code: {result.rejection_code.value}")
    return 0

def _run_verify_transparency_log(
    log_path: Path,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        result = verify_transparency_log(
            log_path=log_path,
            state_path=_resolve_transparency_state_path(args, parser),
        )
    except (TransparencyLogError, TransparencyLogStateError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency log verification failed",
            error=error,
        )
        return 5
    print("Transparency log verified.")
    print(f"Log Version: {result.log_version}")
    print(f"Entry Count: {result.entry_count}")
    print(f"First Sequence: {result.first_sequence if result.first_sequence is not None else 'none'}")
    print(f"Last Sequence: {result.last_sequence if result.last_sequence is not None else 'none'}")
    print(f"Last Entry Hash: {result.last_entry_hash if result.last_entry_hash is not None else 'none'}")
    print(f"Root Transition Entries: {result.root_transition_count}")
    print(f"Signing Key Manifest Entries: {result.signing_key_manifest_count}")
    return 0


def _run_show_transparency_log(
    log_path: Path,
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        result = verify_transparency_log(
            log_path=log_path,
            state_path=_resolve_transparency_state_path(args, parser),
        )
    except (TransparencyLogError, TransparencyLogStateError) as error:
        _print_recovery_error(
            header="[ERROR] Transparency log inspection failed",
            error=error,
        )
        return 5
    print("Transparency log.")
    print(f"Log Version: {result.log_version}")
    print(f"Entry Count: {result.entry_count}")
    for inclusion in result.entries_by_identifier.values():
        print(
            "Entry: "
            f"sequence={inclusion.sequence} "
            f"type={inclusion.artifact_type.value} "
            f"identifier={inclusion.artifact_identifier} "
            f"recorded_at={inclusion.recorded_at.isoformat()}"
        )
    return 0


def _run_show_root_trust_state(state_path: Path) -> int:
    try:
        state = load_root_trust_state(path=state_path)
    except RootTrustStateError as error:
        _print_recovery_error(
            header="[ERROR] Root trust state inspection failed",
            error=error,
        )
        return 5
    if state is None:
        print("Root trust state is missing.")
        print(f"State: {state_path}")
        return 0
    print("Root trust state.")
    print(f"State: {state_path}")
    print(f"State Version: {state.state_version}")
    print(f"Current Root Epoch: {state.current_root_epoch}")
    print(f"Current Root Key ID: {state.current_root_key_id}")
    print(f"Last Transition Generation: {state.last_transition_generation}")
    if state.last_transition_sha256 is not None:
        print(f"Last Transition SHA-256: {state.last_transition_sha256}")
    print(f"Updated At: {state.updated_at.isoformat()}")
    return 0


def _run_initialize_root_trust_state(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.initial_root_epoch is None:
        parser.error("--initial-root-epoch is required")
    try:
        initialized_at = datetime.now(UTC)
        root_public_key = load_trusted_root_public_key(environ=os.environ)
        state = initialize_root_trust_state(
            path=args.initialize_root_trust_state,
            root_public_key=root_public_key,
            root_epoch=args.initial_root_epoch,
            initialized_at=initialized_at,
        )
    except (RootSignatureTrustError, RootTrustStateError) as error:
        _print_recovery_error(
            header="[ERROR] Root trust state initialization failed",
            error=error,
        )
        return 5
    print("Root trust state initialized.")
    print(f"State: {args.initialize_root_trust_state}")
    print(f"Current Root Epoch: {state.current_root_epoch}")
    print(f"Current Root Key ID: {state.current_root_key_id}")
    return 0


def _run_create_root_transition(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.previous_root_epoch is None:
        parser.error("--previous-root-epoch is required")
    if args.next_root_epoch is None:
        parser.error("--next-root-epoch is required")
    if args.root_transition_valid_from is None:
        parser.error("--root-transition-valid-from is required")
    if args.root_transition_valid_until is None:
        parser.error("--root-transition-valid-until is required")
    try:
        previous_private = load_root_signing_private_key(environ=os.environ)
        previous_public = load_trusted_root_public_key(environ=os.environ)
        next_private = load_next_root_signing_private_key(environ=os.environ)
        next_public = load_next_trusted_root_public_key(environ=os.environ)
        ensure_root_key_pair_matches(private_key=previous_private, public_key=previous_public)
        ensure_root_key_pair_matches(private_key=next_private, public_key=next_public)
        issued_at = datetime.now(UTC)
        transition = build_root_transition_manifest(
            issued_at=issued_at,
            valid_from=args.root_transition_valid_from,
            valid_until=args.root_transition_valid_until,
            previous_root_public_key=previous_public,
            previous_root_epoch=args.previous_root_epoch,
            next_root_public_key=next_public,
            next_root_epoch=args.next_root_epoch,
        )
        previous_signature, next_signature = sign_root_transition(
            transition=transition,
            previous_root_private_key=previous_private,
            next_root_private_key=next_private,
            signed_at=issued_at,
            filename=args.create_root_transition.name,
        )
        export_root_transition_manifest(path=args.create_root_transition, transition=transition)
        previous_path = previous_root_signature_path_for(args.create_root_transition)
        next_path = next_root_signature_path_for(args.create_root_transition)
        export_root_transition_signature(path=previous_path, signature=previous_signature)
        export_root_transition_signature(path=next_path, signature=next_signature)
    except (RootSignatureTrustError, RootTransitionError) as error:
        _print_recovery_error(
            header="[ERROR] Root transition generation failed",
            error=error,
        )
        return 5
    print("Root transition created.")
    print(f"Transition: {args.create_root_transition}")
    print(f"Previous Root Signature: {previous_path}")
    print(f"Next Root Signature: {next_path}")
    print(f"Previous Root Epoch: {transition.previous_root.epoch}")
    print(f"Next Root Epoch: {transition.next_root.epoch}")
    print(f"Previous Root Key ID: {transition.previous_root.key_id}")
    print(f"Next Root Key ID: {transition.next_root.key_id}")
    return 0


def _run_verify_root_transition(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        root_state = _load_current_root_state(args, parser)
        verification_time = datetime.now(UTC)
        _verify_optional_witness_quorum(args, parser)
        result = verify_root_transition(
            transition_path=args.verify_root_transition,
            current_root=trusted_root_public_key_from_state(root_state),
            current_root_epoch=root_state.current_root_epoch,
            verification_time=verification_time,
        )
        transparency_result = None
        transparency_inclusion = None
        transparency_mode = _resolve_transparency_mode(args)
        if transparency_mode is not None:
            artifact = transparency_artifact_from_verified_root_transition(result)
            if transparency_mode is TransparencyLogMode.REGISTER_IF_MISSING:
                transparency_result = register_verified_artifact(
                    log_path=_resolve_transparency_log_path(args, parser),
                    state_path=_resolve_transparency_state_path(args, parser),
                    artifact=artifact,
                    recorded_at=verification_time,
                )
                transparency_inclusion = transparency_result.inclusion
            else:
                verification = verify_transparency_log(
                    log_path=_resolve_transparency_log_path(args, parser),
                    state_path=_resolve_transparency_state_path(args, parser),
                )
                transparency_inclusion = require_transparency_entry(
                    verification_result=verification,
                    artifact=artifact,
                )
    except (RootTransitionError, RootTrustStateError, TransparencyLogError, TransparencyLogStateError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Root transition verification failed",
            error=error,
        )
        return 5
    print("Root transition verified.")
    print(f"Transition: {args.verify_root_transition}")
    print(f"Previous Root Epoch: {result.previous_root_epoch}")
    print(f"Next Root Epoch: {result.next_root_epoch}")
    print(f"Previous Root Key ID: {result.previous_root_key_id}")
    print(f"Next Root Key ID: {result.next_root_key_id}")
    print(f"Active For Application: {str(result.is_active_for_application).lower()}")
    if transparency_result is not None:
        _print_transparency_append_result(transparency_result)
    elif transparency_inclusion is not None:
        _print_transparency_inclusion(transparency_inclusion)
    return 0


def _run_retire_manifest_state(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        root_state = _load_current_root_state(args, parser)
        retired_path = retire_manifest_trust_state(
            state_path=args.retire_manifest_state,
            current_root_state=root_state,
        )
    except (ManifestTrustStateError, RootTrustStateError) as error:
        _print_recovery_error(
            header="[ERROR] Signing key manifest trust state retirement failed",
            error=error,
        )
        return 5
    print("Signing key manifest trust state retired.")
    print(f"Retired State: {retired_path}")
    print(f"Root Epoch: {root_state.current_root_epoch}")
    return 0


def _run_apply_root_transition(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        application_time = datetime.now(UTC)
        _verify_optional_witness_quorum(args, parser)
        transition_mode = _resolve_transparency_mode(args) or TransparencyLogMode.REQUIRE_EXISTING
        result, transparency_inclusion = apply_root_transition_with_transparency(
            transition_path=args.apply_root_transition,
            state_path=_resolve_root_trust_state_path(args, parser),
            application_time=application_time,
            active_manifest_state_path=_resolve_manifest_state_path(args),
            transparency_log_path=_resolve_transparency_log_path(args, parser),
            transparency_state_path=_resolve_transparency_state_path(args, parser),
            transparency_mode=transition_mode,
        )
    except (ManifestTrustStateError, RootTransitionError, RootTrustStateError, TransparencyLogError, TransparencyLogStateError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Root transition application failed",
            error=error,
        )
        return 5
    print("Root transition applied.")
    print(f"Transition: {args.apply_root_transition}")
    print(f"Previous Root Epoch: {result.previous_root_epoch}")
    print(f"Next Root Epoch: {result.next_root_epoch}")
    print(f"Previous Root Key ID: {result.previous_root_key_id}")
    print(f"Next Root Key ID: {result.next_root_key_id}")
    print(f"State Updated: {str(result.state_updated).lower()}")
    _print_transparency_inclusion(transparency_inclusion)
    return 0


def _run_show_manifest_state(state_path: Path) -> int:
    try:
        state = load_manifest_trust_state(path=state_path)
    except ManifestTrustStateError as error:
        _print_recovery_error(
            header="[ERROR] Signing key manifest trust state inspection failed",
            error=error,
        )
        return 5
    if state is None:
        print("Signing key manifest trust state is missing.")
        print(f"State: {state_path}")
        return 0
    print("Signing key manifest trust state.")
    print(f"State: {state_path}")
    print(f"State Version: {state.state_version}")
    print(f"Root Key ID: {state.root_key_id}")
    print(f"Highest Generation: {state.highest_generation}")
    print(f"Manifest SHA-256: {state.manifest_sha256}")
    print(f"Manifest Issued At: {state.manifest_issued_at.isoformat()}")
    print(f"Verified At: {state.verified_at.isoformat()}")
    return 0


def _run_initialize_manifest_state(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.initialize_manifest_state.exists():
        _print_recovery_error(
            header="[ERROR] Signing key manifest trust state initialization failed",
            error=ManifestTrustStateValidationError(
                "The signing key manifest trust state is invalid."
            ),
        )
        return 5
    try:
        verification_time = datetime.now(UTC)
        root_state = _load_current_root_state(args, parser)
        verified = verify_signing_key_manifest(
            manifest_path=_resolve_signing_key_manifest_path(args, parser),
            root_public_key=trusted_root_public_key_from_state(root_state),
            verification_time=verification_time,
            minimum_generation=_resolve_minimum_manifest_generation(args, parser),
        )
        decision = apply_manifest_trust_state(
            verified_manifest=verified,
            state_path=args.initialize_manifest_state,
            verified_at=verification_time,
            configured_minimum_generation=_resolve_minimum_manifest_generation(args, parser),
            mode=ManifestTrustStateMode.UPDATE,
            require_existing_state=False,
        )
    except (ManifestTrustStateError, RootSignatureTrustError, RootTrustStateError, SigningKeyManifestError) as error:
        _print_recovery_error(
            header="[ERROR] Signing key manifest trust state initialization failed",
            error=error,
        )
        return 5
    print("Signing key manifest trust state initialized.")
    print(f"State: {args.initialize_manifest_state}")
    print(f"Generation: {verified.result.generation}")
    print(f"Root Key ID: {verified.result.root_key_id}")
    print(f"State Updated: {str(decision.state_updated).lower()}")
    return 0


def _run_create_signing_key_manifest(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    if args.manifest_generation is None:
        parser.error("--manifest-generation is required")
    if args.manifest_valid_from is None:
        parser.error("--manifest-valid-from is required")
    if args.manifest_valid_until is None:
        parser.error("--manifest-valid-until is required")
    try:
        root_private_key = load_root_signing_private_key(environ=os.environ)
        root_public_key = load_trusted_root_public_key(environ=os.environ)
        ensure_root_key_pair_matches(private_key=root_private_key, public_key=root_public_key)
        raw_trust_store = load_archive_signature_trust_store(environ=os.environ)
        created_at = datetime.now(UTC)
        manifest = build_signing_key_manifest(
            generation=args.manifest_generation,
            issued_at=created_at,
            valid_from=args.manifest_valid_from,
            valid_until=args.manifest_valid_until,
            root_public_key=root_public_key,
            keys=raw_trust_store.keys,
        )
        signature = sign_signing_key_manifest(
            manifest=manifest,
            root_private_key=root_private_key,
            signed_at=created_at,
            filename=args.create_signing_key_manifest.name,
        )
        export_signing_key_manifest(path=args.create_signing_key_manifest, manifest=manifest)
        signature_path = signing_key_manifest_signature_path_for(args.create_signing_key_manifest)
        export_signing_key_manifest_signature(path=signature_path, signature=signature)
    except (ArchiveSignatureError, ManifestTrustStateError, RootSignatureTrustError, SigningKeyManifestError) as error:
        _print_recovery_error(
            header="[ERROR] Archive signing key manifest generation failed",
            error=error,
        )
        return 5
    print("Archive signing key manifest created.")
    print(f"Manifest: {args.create_signing_key_manifest}")
    print(f"Signature: {signature_path}")
    print(f"Manifest Version: {manifest.manifest_version}")
    print(f"Generation: {manifest.generation}")
    print(f"Root Key ID: {root_public_key.key_id}")
    print(f"Active Key ID: {next(key.key_id for key in raw_trust_store.keys if key.status.value == 'active')}")
    return 0


def _run_verify_signing_key_manifest(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    try:
        verification_time = datetime.now(UTC)
        root_state = _load_current_root_state(args, parser)
        _verify_optional_witness_quorum(args, parser)
        transparency_mode = _resolve_transparency_mode(args)
        if transparency_mode is None:
            verified, state_decision = verify_signing_key_manifest_with_root_state(
                manifest_path=args.verify_signing_key_manifest,
                root_state=root_state,
                verification_time=verification_time,
                state_path=_resolve_manifest_state_path(args),
                minimum_generation=_resolve_minimum_manifest_generation(args, parser),
                state_mode=_resolve_manifest_state_mode(args),
                require_existing_state=args.require_existing_manifest_state,
            )
            transparency_inclusion = None
        else:
            verified, state_decision, transparency_inclusion = verify_signing_key_manifest_with_root_state_and_transparency(
                manifest_path=args.verify_signing_key_manifest,
                root_state=root_state,
                verification_time=verification_time,
                state_path=_resolve_manifest_state_path(args),
                transparency_log_path=_resolve_transparency_log_path(args, parser),
                transparency_state_path=_resolve_transparency_state_path(args, parser),
                transparency_mode=transparency_mode,
                minimum_generation=_resolve_minimum_manifest_generation(args, parser),
                state_mode=_resolve_manifest_state_mode(args),
                require_existing_state=args.require_existing_manifest_state,
            )
    except (ManifestTrustStateError, RootSignatureTrustError, RootTrustStateError, SigningKeyManifestError, TransparencyLogError, TransparencyLogStateError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Archive signing key manifest verification failed",
            error=error,
        )
        return 5
    print("Archive signing key manifest verified.")
    print(f"Manifest: {args.verify_signing_key_manifest}")
    print(f"Signature: {signing_key_manifest_signature_path_for(args.verify_signing_key_manifest)}")
    print(f"Manifest Version: {verified.result.manifest_version}")
    print(f"Generation: {verified.result.generation}")
    print(f"Root Key ID: {verified.result.root_key_id}")
    print(f"Active Key ID: {verified.result.active_key_id}")
    print(f"Key Count: {verified.result.key_count}")
    _print_manifest_state_decision(args, state_decision)
    if transparency_inclusion is not None:
        _print_transparency_inclusion(transparency_inclusion)
    return 0


def _run_verify(verify_path: Path) -> int:
    try:
        result = verify_report_integrity(report_path=verify_path)
    except (AuditLogError, ReportIntegrityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report integrity verification failed",
            error=error,
        )
        return 5
    print("Audit report integrity verified.")
    print(f"File: {verify_path}")
    print(f"Checksum: {checksum_path_for(verify_path)}")
    print(f"SHA-256: {result.digest}")
    return 0


def _run_verify_authenticity(verify_path: Path, *, revoked_key_policy: RevokedKeyPolicy) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_report_authenticity(
            report_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_key_policy,
        )
    except (AuditLogError, ReportAuthenticityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report authenticity verification failed",
            error=error,
        )
        return 5
    print("Audit report authenticity verified.")
    print(f"File: {verify_path}")
    print(f"Authentication: {authentication_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    print(f"HMAC: {result.digest}")
    return 0


def _run_verify_bundle(verify_path: Path, *, revoked_key_policy: RevokedKeyPolicy) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_report_bundle(
            report_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            revoked_key_policy=revoked_key_policy,
        )
    except (AuditLogError, ReportAuthenticityError, ReportBundleError, ReportIntegrityError) as error:
        _print_recovery_error(header="[ERROR] Audit report bundle verification failed", error=error)
        return 5
    print("Audit report bundle verified.")
    print(f"File: {verify_path}")
    print(f"Manifest: {manifest_path_for(verify_path)}")
    print(f"Manifest Version: {result.manifest_version}")
    print(f"Report Schema Version: {result.report_schema_version}")
    print(f"Authentication Protocol Version: {result.authentication_protocol_version}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    return 0


def _run_verify_archive_authenticity(
    verify_path: Path,
    *,
    revoked_key_policy: RevokedKeyPolicy,
) -> int:
    try:
        trust_store = load_authentication_trust_store(environ=os.environ)
        result = verify_archive_authenticity(
            archive_path=verify_path,
            trust_store=trust_store,
            verification_time=datetime.now(UTC),
            expected_archive_format_version=REPORT_ARCHIVE_FORMAT_VERSION,
            revoked_key_policy=revoked_key_policy,
        )
    except (ArchiveAuthenticityError, ReportAuthenticityError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report archive authenticity verification failed",
            error=error,
        )
        return 5
    print("Audit report archive authenticity verified.")
    print(f"Archive: {verify_path}")
    print(f"Authentication: {archive_authentication_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Protocol Version: {result.protocol_version}")
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Key ID: {result.key_id}")
    print(f"Authenticated At: {result.authenticated_at.isoformat()}")
    print(f"Archive HMAC: {result.digest}")
    return 0


def _run_verify_archive_signature(
    verify_path: Path,
    *,
    manifest_path: Path,
    minimum_generation: int,
    state_path: Path | None,
    root_state_path: Path | None,
    transparency_log_path: Path,
    transparency_state_path: Path,
    state_mode: ManifestTrustStateMode,
    require_existing_state: bool,
    revoked_signature_key_policy: RevokedSignatureKeyPolicy,
    witness_args: argparse.Namespace | None = None,
) -> int:
    try:
        verification_time = datetime.now(UTC)
        if witness_args is not None:
            _verify_optional_witness_quorum(witness_args, argparse.ArgumentParser())
        root_state = _load_current_root_state(argparse.Namespace(root_trust_state=root_state_path), None)
        result, _verified_manifest, state_decision, transparency_inclusion = verify_archive_signature_with_root_state_and_transparency(
            archive_path=verify_path,
            manifest_path=manifest_path,
            root_state=root_state,
            verification_time=verification_time,
            state_path=state_path,
            transparency_log_path=transparency_log_path,
            transparency_state_path=transparency_state_path,
            minimum_generation=minimum_generation,
            state_mode=state_mode,
            require_existing_state=require_existing_state,
            revoked_signature_key_policy=revoked_signature_key_policy,
        )
    except (ArchiveSignatureError, ManifestTrustStateError, RootSignatureTrustError, RootTrustStateError, SigningKeyManifestError, TransparencyLogError, TransparencyLogStateError, TransparencyWitnessError) as error:
        _print_recovery_error(
            header="[ERROR] Audit report archive signature verification failed",
            error=error,
        )
        return 5
    print("Audit report archive signature verified.")
    print(f"Archive: {verify_path}")
    print(f"Signature: {archive_signature_path_for(verify_path)}")
    print(f"Algorithm: {result.algorithm}")
    print(f"Protocol Version: {result.protocol_version}")
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Key ID: {result.key_id}")
    print(f"Public Key Fingerprint: {result.public_key_fingerprint}")
    print(f"Signed At: {result.signed_at.isoformat()}")
    print(f"Archive SHA-256: {result.archive_sha256}")
    _print_manifest_state_decision_for_values(
        state_path=state_path,
        state_mode=state_mode,
        decision=state_decision,
    )
    _print_transparency_inclusion(transparency_inclusion)
    return 0


def _run_verify_archive(
    verify_path: Path,
    *,
    manifest_path: Path,
    minimum_generation: int,
    state_path: Path | None,
    root_state_path: Path | None,
    transparency_log_path: Path,
    transparency_state_path: Path,
    state_mode: ManifestTrustStateMode,
    require_existing_state: bool,
    revoked_key_policy: RevokedKeyPolicy,
    revoked_signature_key_policy: RevokedSignatureKeyPolicy,
    witness_args: argparse.Namespace | None = None,
) -> int:
    try:
        verification_time = datetime.now(UTC)
        if witness_args is not None:
            _verify_optional_witness_quorum(witness_args, argparse.ArgumentParser())
        trust_store = load_authentication_trust_store(environ=os.environ)
        root_state = _load_current_root_state(argparse.Namespace(root_trust_state=root_state_path), None)
        result, verified_manifest, state_decision, transparency_inclusion = verify_signed_authenticated_report_archive_with_root_state_and_transparency(
            archive_path=verify_path,
            trust_store=trust_store,
            manifest_path=manifest_path,
            root_state=root_state,
            verification_time=verification_time,
            state_path=state_path,
            transparency_log_path=transparency_log_path,
            transparency_state_path=transparency_state_path,
            minimum_generation=minimum_generation,
            state_mode=state_mode,
            require_existing_state=require_existing_state,
            revoked_key_policy=revoked_key_policy,
            revoked_signature_key_policy=revoked_signature_key_policy,
        )
    except (
        ArchiveAuthenticityError,
        ArchiveSignatureError,
        AuditLogError,
        ManifestTrustStateError,
        ManifestTrustStateValidationError,
        ReportArchiveError,
        ReportAuthenticityError,
        ReportBundleError,
        ReportIntegrityError,
        RootSignatureTrustError,
        RootTrustStateError,
        SigningKeyManifestError,
        TransparencyLogError,
        TransparencyLogStateError,
        TransparencyWitnessError,
    ) as error:
        _print_recovery_error(header="[ERROR] Audit report archive verification failed", error=error)
        return 5
    print("Audit report archive verified.")
    print(f"Archive: {verify_path}")
    print(f"Signature Algorithm: {result.signature_algorithm}")
    print(f"Signature Protocol Version: {result.signature_protocol_version}")
    print(f"Signature Key ID: {result.signature_key_id}")
    print(f"Signature Public Key Fingerprint: {result.signature_public_key_fingerprint}")
    print(f"Signed At: {result.signature_signed_at.isoformat()}")
    print(f"Signature Archive SHA-256: {result.signature_archive_sha256}")
    print(f"Signing Key Manifest Generation: {verified_manifest.result.generation}")
    _print_manifest_state_decision_for_values(
        state_path=state_path,
        state_mode=state_mode,
        decision=state_decision,
    )
    _print_transparency_inclusion(transparency_inclusion)
    print(f"Archive Format Version: {result.archive_format_version}")
    print(f"Archive SHA-256: {result.archive_sha256}")
    print(f"Members: {result.member_count}")
    print(f"Manifest Version: {result.manifest_version}")
    print(f"Report Schema Version: {result.report_schema_version}")
    print(f"Archive Authentication Protocol Version: {result.archive_authentication_protocol_version}")
    print(f"Archive Authentication Algorithm: {result.archive_algorithm}")
    print(f"Archive Authentication Key ID: {result.archive_key_id}")
    print(f"Archive Authenticated At: {result.archive_authenticated_at.isoformat()}")
    print(f"Archive HMAC: {result.archive_digest}")
    print(f"Authentication Protocol Version: {result.report_authentication_protocol_version}")
    print(f"Algorithm: {result.report_algorithm}")
    print(f"Key ID: {result.report_key_id}")
    print(f"Authenticated At: {result.report_authenticated_at.isoformat()}")
    print(f"Report Filename: {result.report_filename}")
    return 0


def _print_recovery_error(*, header: str, error: BaseException) -> None:
    decision = decide_recovery(error)
    print(header)
    print(f"Action: {decision.action.value}")
    print(f"Retryable: {str(decision.retryable).lower()}")
    print(f"Reason: {decision.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
