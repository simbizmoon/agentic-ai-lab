"""Project-specific exception hierarchy."""


class AgenticAILabError(Exception):
    """Base exception for Agentic AI Lab errors."""


class StructuredAnalysisError(AgenticAILabError):
    """Base exception for structured analysis errors."""


class StructuredResponseIncompleteError(StructuredAnalysisError):
    """Raised when a structured response is incomplete."""


class StructuredResponseRefusalError(StructuredAnalysisError):
    """Raised when a structured response contains a refusal."""


class StructuredResponseParseError(StructuredAnalysisError):
    """Raised when a structured response cannot be parsed."""


class StructuredResponseStatusError(StructuredAnalysisError):
    """Raised when a structured response has an unexpected status."""


class StructuredResponseValidationError(StructuredAnalysisError):
    """Raised when a structured response fails schema validation."""

    def __init__(
        self,
        message: str,
        *,
        elapsed_seconds: float = 0.0,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.elapsed_seconds = elapsed_seconds
        self.attempts = attempts


class ExecutionBudgetError(AgenticAILabError):
    """Base exception for execution budget errors."""


class AttemptBudgetExceededError(ExecutionBudgetError):
    """Raised when the execution attempt budget is exceeded."""


class TokenBudgetExceededError(ExecutionBudgetError):
    """Raised when the recorded token budget is exceeded."""


class TimeBudgetExceededError(ExecutionBudgetError):
    """Raised when the execution time budget is exceeded."""


class AuditLogError(AgenticAILabError):
    """Raised when an audit log event cannot be written."""


class AuditLogReadError(AuditLogError):
    """Raised when an audit log cannot be read."""


class AuditLogParseError(AuditLogError):
    """Raised when an audit log line is not valid JSON."""


class UnsupportedAuditSchemaError(AuditLogError):
    """Raised when an audit log event uses an unsupported schema."""


class InvalidAuditEventError(AuditLogError):
    """Raised when an audit log event is structurally invalid."""


class AuditReportValidationError(AuditLogError):
    """Raised when an audit report output contract is invalid."""


class SchemaCompatibilityError(AgenticAILabError):
    """Raised when a published schema contract changes unexpectedly."""


class SchemaMigrationError(AgenticAILabError):
    """Base exception for schema migration errors."""


class InvalidSchemaVersionError(SchemaMigrationError):
    """Raised when a schema version is invalid."""


class UnsupportedSchemaVersionError(SchemaMigrationError):
    """Raised when a schema version is no longer supported."""


class SchemaDowngradeError(SchemaMigrationError):
    """Raised when a downgrade migration is requested."""


class InvalidMigrationRegistryError(SchemaMigrationError):
    """Raised when a migration registry is structurally invalid."""


class MissingSchemaMigrationError(SchemaMigrationError):
    """Raised when a required migration step is not registered."""


class SchemaMigrationStepError(SchemaMigrationError):
    """Raised when a migration step fails or returns an invalid result."""


class ReportExportError(AgenticAILabError):
    """Base exception for audit report export errors."""


class InvalidReportExportPathError(ReportExportError):
    """Raised when an audit report export path is invalid."""


class ReportExportWriteError(ReportExportError):
    """Raised when an audit report cannot be written safely."""


class ReportIntegrityError(AgenticAILabError):
    """Base exception for audit report integrity errors."""


class ReportIntegrityReadError(ReportIntegrityError):
    """Raised when an audit report or checksum cannot be read."""


class InvalidChecksumFormatError(ReportIntegrityError):
    """Raised when a checksum sidecar has an invalid format."""


class ChecksumFilenameMismatchError(ReportIntegrityError):
    """Raised when a checksum sidecar references a different report filename."""


class ReportIntegrityMismatchError(ReportIntegrityError):
    """Raised when an audit report checksum does not match."""


class ChecksumExportError(ReportIntegrityError):
    """Raised when a checksum sidecar cannot be written safely."""


class ReportAuthenticityError(AgenticAILabError):
    """Base exception for audit report authenticity errors."""


class MissingAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key is missing."""


class InvalidAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key is invalid."""


class InvalidAuthenticationKeyIdError(ReportAuthenticityError):
    """Raised when an authentication key ID is invalid."""




class AuthenticationTrustError(ReportAuthenticityError):
    """Base exception for authentication trust policy errors."""


class AuthenticationKeyringError(AuthenticationTrustError):
    """Base exception for authentication keyring configuration errors."""


class MissingAuthenticationKeyringError(AuthenticationKeyringError):
    """Raised when an authentication keyring is missing."""


class InvalidAuthenticationKeyringError(AuthenticationKeyringError):
    """Raised when an authentication keyring is invalid."""


class DuplicateAuthenticationKeyIdError(AuthenticationKeyringError):
    """Raised when authentication key IDs are duplicated."""


class ActiveAuthenticationKeyNotFoundError(AuthenticationKeyringError):
    """Raised when the active authentication key is not registered."""


class InvalidAuthenticationTrustStoreError(AuthenticationTrustError):
    """Raised when an authentication trust store is invalid."""


class NoActiveAuthenticationKeyError(AuthenticationTrustError):
    """Raised when no key is active for signing at the requested time."""


class MultipleActiveAuthenticationKeysError(AuthenticationTrustError):
    """Raised when more than one key is active for signing."""


class AuthenticationKeyNotValidAtSigningTimeError(AuthenticationTrustError):
    """Raised when a key was not valid at authentication time."""


class RejectedAuthenticationKeyError(AuthenticationTrustError):
    """Raised when trust policy rejects an authentication key."""


class AuthenticationFromFutureError(AuthenticationTrustError):
    """Raised when authenticated_at is too far in the future."""


class ReportAuthenticationReadError(ReportAuthenticityError):
    """Raised when an authentication sidecar or report cannot be read."""


class InvalidAuthenticationFormatError(ReportAuthenticityError):
    """Raised when an authentication sidecar has an invalid format."""


class AuthenticationFilenameMismatchError(ReportAuthenticityError):
    """Raised when an authentication sidecar references a different report."""


class UnknownAuthenticationKeyError(ReportAuthenticityError):
    """Raised when an authentication key ID is not available."""


class ReportAuthenticityMismatchError(ReportAuthenticityError):
    """Raised when an authentication code does not match."""


class AuthenticationExportError(ReportAuthenticityError):
    """Raised when an authentication sidecar cannot be written safely."""


class ReportBundleError(AgenticAILabError):
    """Base exception for audit report bundle errors."""


class ReportBundleManifestValidationError(ReportBundleError):
    """Raised when a bundle manifest contract is invalid."""


class ReportBundleReadError(ReportBundleError):
    """Raised when a bundle manifest cannot be read."""


class ReportBundleExportError(ReportBundleError):
    """Raised when a bundle manifest cannot be written safely."""


class IncompleteReportBundleError(ReportBundleError):
    """Raised when a required bundle file is missing."""


class BundleReportFilenameMismatchError(ReportBundleError):
    """Raised when a manifest references a different report filename."""


class ReportBundleDigestMismatchError(ReportBundleError):
    """Raised when a bundle file digest does not match the manifest."""


class ReportBundleMetadataMismatchError(ReportBundleError):
    """Raised when bundle metadata is inconsistent with verified files."""

class ReportArchiveError(AgenticAILabError):
    """Base exception for audit report archive errors."""


class InvalidReportArchivePathError(ReportArchiveError):
    """Raised when an audit report archive path is invalid."""


class ReportArchiveExportError(ReportArchiveError):
    """Raised when an audit report archive cannot be written safely."""


class ReportArchiveReadError(ReportArchiveError):
    """Raised when archive input files or a ZIP archive cannot be read."""


class InvalidReportArchiveError(ReportArchiveError):
    """Raised when a ZIP archive is structurally invalid."""


class UnsafeReportArchiveMemberError(ReportArchiveError):
    """Raised when a ZIP member is unsafe to process."""


class DuplicateReportArchiveMemberError(ReportArchiveError):
    """Raised when a ZIP archive contains duplicate member names."""


class UnexpectedReportArchiveMemberError(ReportArchiveError):
    """Raised when a ZIP archive contains unexpected members."""


class MissingReportArchiveMemberError(ReportArchiveError):
    """Raised when a ZIP archive is missing required members."""


class ReportArchiveSizeLimitError(ReportArchiveError):
    """Raised when a ZIP archive exceeds configured size limits."""


class InvalidReportArchiveMemberError(ReportArchiveError):
    """Raised when a ZIP member cannot be decoded or parsed safely."""


class ReportArchiveDigestMismatchError(ReportArchiveError):
    """Raised when archive member digests do not match expected values."""


class ReportArchiveMetadataMismatchError(ReportArchiveError):
    """Raised when archive metadata is inconsistent across members."""


class ArchiveAuthenticityError(AgenticAILabError):
    """Base exception for audit report archive authenticity errors."""


class ArchiveAuthenticationReadError(ArchiveAuthenticityError):
    """Raised when archive authentication data cannot be read."""


class InvalidArchiveAuthenticationFormatError(ArchiveAuthenticityError):
    """Raised when an archive authentication sidecar has an invalid format."""


class ArchiveAuthenticationFilenameMismatchError(ArchiveAuthenticityError):
    """Raised when an archive authentication sidecar references another archive."""


class ArchiveAuthenticationFormatVersionMismatchError(ArchiveAuthenticityError):
    """Raised when archive authentication uses a different archive format."""


class ArchiveAuthenticityMismatchError(ArchiveAuthenticityError):
    """Raised when an archive authentication code does not match."""


class ArchiveAuthenticationExportError(ArchiveAuthenticityError):
    """Raised when an archive authentication sidecar cannot be written safely."""


class ArchiveAuthenticationMetadataMismatchError(ArchiveAuthenticityError):
    """Raised when archive authentication metadata is inconsistent."""


class ArchiveSignatureError(AgenticAILabError):
    """Base exception for audit report archive signature errors."""


class MissingArchiveSigningPrivateKeyError(ArchiveSignatureError):
    """Raised when an archive signing private key is missing."""


class InvalidArchiveSigningPrivateKeyError(ArchiveSignatureError):
    """Raised when an archive signing private key is invalid."""


class InvalidArchiveSigningKeyIdError(ArchiveSignatureError):
    """Raised when an archive signing key ID is invalid."""


class InvalidArchiveSignatureTrustStoreError(ArchiveSignatureError):
    """Raised when an archive signature trust store is invalid."""


class DuplicateArchiveSigningKeyIdError(ArchiveSignatureError):
    """Raised when archive signing key IDs are duplicated."""


class UnknownArchiveSigningKeyError(ArchiveSignatureError):
    """Raised when an archive signing key ID is not trusted."""


class ArchiveSigningKeyNotActiveError(ArchiveSignatureError):
    """Raised when an archive signing key is not active for signing."""


class ArchiveSigningKeyNotValidError(ArchiveSignatureError):
    """Raised when an archive signing key is not valid for the signing time."""


class RejectedArchiveSigningKeyError(ArchiveSignatureError):
    """Raised when policy rejects a revoked archive signing key."""


class ArchiveSignatureFromFutureError(ArchiveSignatureError):
    """Raised when an archive signature time is too far in the future."""


class ArchiveSigningKeyFingerprintMismatchError(ArchiveSignatureError):
    """Raised when an archive signing key fingerprint does not match."""


class ArchiveSignatureReadError(ArchiveSignatureError):
    """Raised when archive signature inputs cannot be read."""


class ArchiveSignatureValidationError(ArchiveSignatureError):
    """Raised when an archive signature sidecar fails validation."""


class ArchiveSignatureFilenameMismatchError(ArchiveSignatureError):
    """Raised when an archive signature sidecar references another archive."""


class ArchiveSignatureArchiveDigestMismatchError(ArchiveSignatureError):
    """Raised when a signature sidecar archive digest does not match."""


class ArchiveSignatureVerificationError(ArchiveSignatureError):
    """Raised when an archive signature cannot be verified."""


class ArchiveSignatureExportError(ArchiveSignatureError):
    """Raised when an archive signature sidecar cannot be written safely."""


class RootSignatureTrustError(AgenticAILabError):
    """Base exception for archive signing root key trust errors."""


class MissingRootSigningPrivateKeyError(RootSignatureTrustError):
    """Raised when the root signing private key is missing."""


class InvalidRootSigningPrivateKeyError(RootSignatureTrustError):
    """Raised when the root signing private key is invalid."""


class MissingRootSigningPublicKeyError(RootSignatureTrustError):
    """Raised when the trusted root public key is missing."""


class InvalidRootSigningPublicKeyError(RootSignatureTrustError):
    """Raised when the trusted root public key is invalid."""


class RootSigningKeyIdError(RootSignatureTrustError):
    """Raised when a root signing key ID is invalid."""


class RootSigningKeyMismatchError(RootSignatureTrustError):
    """Raised when root private and public keys do not match."""


class TransparencyLogStateError(AgenticAILabError):
    """Base exception for transparency log state errors."""


class TransparencyLogStateReadError(TransparencyLogStateError):
    """Raised when transparency log state cannot be read."""


class TransparencyLogStateValidationError(TransparencyLogStateError):
    """Raised when transparency log state is invalid."""


class TransparencyLogStateExportError(TransparencyLogStateError):
    """Raised when transparency log state cannot be written safely."""


class TransparencyLogError(AgenticAILabError):
    """Base exception for transparency log errors."""


class TransparencyLogReadError(TransparencyLogError):
    """Raised when transparency log cannot be read."""


class TransparencyLogValidationError(TransparencyLogError):
    """Raised when transparency log structure is invalid."""


class TransparencyLogWriteError(TransparencyLogError):
    """Raised when transparency log cannot be appended safely."""


class TransparencyLogDivergenceError(TransparencyLogError):
    """Raised when log and state diverge."""


class TransparencyLogStateMismatchError(TransparencyLogError):
    """Raised when transparency log state does not match log tip."""


class TransparencyLogConflictError(TransparencyLogError):
    """Raised when an artifact conflicts with a logged artifact."""


class RootTransitionTransparencyConflictError(TransparencyLogConflictError):
    """Raised when a root transition conflicts with the transparency log."""


class SigningKeyManifestTransparencyConflictError(TransparencyLogConflictError):
    """Raised when a signing key manifest conflicts with the transparency log."""


class UnloggedRootTransitionError(TransparencyLogError):
    """Raised when a root transition is not registered in transparency log."""


class UnloggedSigningKeyManifestError(TransparencyLogError):
    """Raised when a signing key manifest is not registered in transparency log."""


class TransparencyMerkleError(AgenticAILabError):
    """Base exception for transparency Merkle proof errors."""


class TransparencyMerkleProofReadError(TransparencyMerkleError):
    """Raised when a transparency Merkle proof cannot be read."""


class TransparencyMerkleProofValidationError(TransparencyMerkleError):
    """Raised when a transparency Merkle proof is structurally invalid."""


class TransparencyMerkleProofExportError(TransparencyMerkleError):
    """Raised when a transparency Merkle proof cannot be exported safely."""


class TransparencyInclusionProofMismatchError(TransparencyMerkleError):
    """Raised when a transparency inclusion proof does not match a checkpoint."""


class TransparencyConsistencyProofMismatchError(TransparencyMerkleError):
    """Raised when a transparency consistency proof does not match checkpoints."""


class TransparencyWitnessError(AgenticAILabError):
    """Base exception for transparency witness errors."""


class TransparencyWitnessConfigurationError(TransparencyWitnessError):
    """Raised when transparency witness key configuration is invalid."""


class TransparencyWitnessSignatureError(TransparencyWitnessError):
    """Raised when a transparency witness signature is invalid."""


class TransparencyWitnessStateError(TransparencyWitnessError):
    """Raised when transparency witness state cannot be handled safely."""


class TransparencyWitnessRollbackError(TransparencyWitnessError):
    """Raised when a witness checkpoint would roll back tree size."""


class TransparencyWitnessSplitViewError(TransparencyWitnessError):
    """Raised when a witness observes conflicting checkpoint roots."""


class TransparencyWitnessEquivocationError(TransparencyWitnessError):
    """Raised when one witness signs conflicting checkpoints."""


class TransparencyWitnessTrustStoreError(TransparencyWitnessError):
    """Raised when a witness trust store is invalid or unsafe."""


class TransparencyWitnessQuorumError(TransparencyWitnessError):
    """Raised when witness quorum verification fails."""


class TransparencyWitnessQuorumNotSatisfiedError(TransparencyWitnessQuorumError):
    """Raised when not enough unique trusted witnesses verify a checkpoint."""


class TransparencySplitViewEvidenceError(AgenticAILabError):
    """Base exception for transparency split-view evidence errors."""


class TransparencySplitViewEvidenceConflictError(TransparencySplitViewEvidenceError):
    """Raised when split-view evidence conflicts with an existing file."""


class TransparencyCheckpointError(AgenticAILabError):
    """Base exception for transparency checkpoint errors."""


class TransparencyCheckpointReadError(TransparencyCheckpointError):
    """Raised when a transparency checkpoint cannot be read."""


class TransparencyCheckpointValidationError(TransparencyCheckpointError):
    """Raised when a transparency checkpoint is invalid."""


class TransparencyCheckpointSignatureError(TransparencyCheckpointError):
    """Raised when a transparency checkpoint signature is invalid."""


class TransparencyCheckpointExportError(TransparencyCheckpointError):
    """Raised when a transparency checkpoint cannot be exported safely."""


class TransparencyCheckpointLogMismatchError(TransparencyCheckpointError):
    """Raised when a transparency checkpoint does not match the JSONL log."""


class TransparencyCheckpointStateError(AgenticAILabError):
    """Base exception for transparency checkpoint state errors."""


class TransparencyCheckpointStateReadError(TransparencyCheckpointStateError):
    """Raised when checkpoint state cannot be read."""


class TransparencyCheckpointStateValidationError(TransparencyCheckpointStateError):
    """Raised when checkpoint state is invalid."""


class TransparencyCheckpointStateExportError(TransparencyCheckpointStateError):
    """Raised when checkpoint state cannot be exported safely."""


class TransparencyCheckpointStateLockError(TransparencyCheckpointStateError):
    """Raised when checkpoint state cannot be locked."""


class TransparencyCheckpointRollbackError(TransparencyCheckpointStateError):
    """Raised when a checkpoint would roll back the witnessed tree size."""


class TransparencyCheckpointSplitViewError(TransparencyCheckpointStateError):
    """Raised when a checkpoint conflicts at an already witnessed tree size."""


class TransparencyCheckpointConsistencyRequiredError(TransparencyCheckpointStateError):
    """Raised when a larger checkpoint lacks a consistency proof."""


class RootTransitionError(AgenticAILabError):
    """Base exception for root key transition errors."""


class RootTransitionReadError(RootTransitionError):
    """Raised when a root transition file cannot be read."""


class RootTransitionValidationError(RootTransitionError):
    """Raised when a root transition contract is invalid."""


class RootTransitionExportError(RootTransitionError):
    """Raised when a root transition file cannot be written safely."""


class RootTransitionSignatureVerificationError(RootTransitionError):
    """Raised when a root transition signature cannot be verified."""


class RootTransitionDigestMismatchError(RootTransitionError):
    """Raised when root transition digest metadata does not match."""


class RootTransitionMetadataMismatchError(RootTransitionError):
    """Raised when root transition metadata is inconsistent."""


class RootTransitionExpiredError(RootTransitionError):
    """Raised when a root transition has expired."""


class RootTransitionFromFutureError(RootTransitionError):
    """Raised when a root transition time is too far in the future."""


class RootTransitionNotYetValidError(RootTransitionError):
    """Raised when a root transition is not active for application."""


class RootTrustStateError(AgenticAILabError):
    """Base exception for persistent root trust state errors."""


class RootTrustStateReadError(RootTrustStateError):
    """Raised when root trust state cannot be read."""


class RootTrustStateValidationError(RootTrustStateError):
    """Raised when root trust state is invalid."""


class RootTrustStateExportError(RootTrustStateError):
    """Raised when root trust state cannot be written safely."""


class RootTrustStateLockError(RootTrustStateError):
    """Raised when root trust state cannot be locked safely."""


class RootTrustStateAlreadyExistsError(RootTrustStateError):
    """Raised when initial root trust state already exists."""


class MissingRootTrustStateError(RootTrustStateError):
    """Raised when required root trust state is missing."""


class RootTrustStateEpochError(RootTrustStateError):
    """Raised when root trust state epoch policy is violated."""


class ActiveManifestTrustStateBlocksRootTransitionError(RootTrustStateError):
    """Raised when an active signing key manifest state blocks root transition."""


class ManifestTrustStateError(AgenticAILabError):
    """Base exception for signing key manifest trust state errors."""


class ManifestTrustStateReadError(ManifestTrustStateError):
    """Raised when signing key manifest trust state cannot be read."""


class ManifestTrustStateValidationError(ManifestTrustStateError):
    """Raised when signing key manifest trust state is invalid."""


class ManifestTrustStateExportError(ManifestTrustStateError):
    """Raised when signing key manifest trust state cannot be written safely."""


class ManifestTrustStateLockError(ManifestTrustStateError):
    """Raised when signing key manifest trust state cannot be locked safely."""


class MissingManifestTrustStateError(ManifestTrustStateError):
    """Raised when required signing key manifest trust state is missing."""


class ManifestTrustStateRootMismatchError(ManifestTrustStateError):
    """Raised when trust state belongs to another root trust domain."""


class ManifestTrustStateGenerationConflictError(ManifestTrustStateError):
    """Raised when the same generation has a different manifest digest."""


class ManifestTrustStatePathError(ManifestTrustStateError):
    """Raised when a trust state path is required but unavailable."""


class ManifestTrustStateRetirementError(ManifestTrustStateError):
    """Raised when signing key manifest trust state cannot be retired safely."""


class SigningKeyManifestError(AgenticAILabError):
    """Base exception for archive signing key manifest errors."""


class SigningKeyManifestReadError(SigningKeyManifestError):
    """Raised when a signing key manifest cannot be read."""


class SigningKeyManifestValidationError(SigningKeyManifestError):
    """Raised when a signing key manifest contract is invalid."""


class SigningKeyManifestExportError(SigningKeyManifestError):
    """Raised when a signing key manifest cannot be written safely."""


class SigningKeyManifestSignatureVerificationError(SigningKeyManifestError):
    """Raised when a signing key manifest root signature cannot be verified."""


class SigningKeyManifestDigestMismatchError(SigningKeyManifestError):
    """Raised when a signing key manifest digest does not match."""


class SigningKeyManifestMetadataMismatchError(SigningKeyManifestError):
    """Raised when signing key manifest metadata is inconsistent."""


class SigningKeyManifestRollbackError(SigningKeyManifestError):
    """Raised when a signing key manifest generation is too old."""


class SigningKeyManifestExpiredError(SigningKeyManifestError):
    """Raised when a signing key manifest is expired."""


class SigningKeyManifestNotYetValidError(SigningKeyManifestError):
    """Raised when a signing key manifest is not yet valid."""


class SigningKeyManifestFromFutureError(SigningKeyManifestError):
    """Raised when a signing key manifest time is too far in the future."""

class TransparencyGossipBundleError(AgenticAILabError):
    """Base exception for transparency gossip bundle errors."""


class TransparencyGossipBundleConfigurationError(TransparencyGossipBundleError):
    """Raised when gossip bundle signing configuration is invalid."""


class TransparencyGossipBundleSignatureError(TransparencyGossipBundleError):
    """Raised when a gossip bundle signature is invalid."""


class TransparencyGossipBundleStructureError(TransparencyGossipBundleError):
    """Raised when a gossip bundle ZIP structure is unsafe or invalid."""


class TransparencyGossipBundleConflictError(TransparencyGossipBundleError):
    """Raised when a gossip bundle conflicts with an existing file."""


class TransparencyArtifactBindingError(TransparencyGossipBundleError):
    """Raised when transparency artifact binding is invalid."""


class TransparencyOfflineVerificationError(AgenticAILabError):
    """Raised when offline transparency verification fails."""


class TransparencyDecisionReceiptError(AgenticAILabError):
    """Base exception for transparency trust decision receipt errors."""


class TransparencyDecisionReceiptSignatureError(TransparencyDecisionReceiptError):
    """Raised when a decision receipt signature is invalid."""


class TransparencyDecisionReceiptConflictError(TransparencyDecisionReceiptError):
    """Raised when a decision receipt conflicts with an existing file."""


class TransparencyDecisionPolicyError(TransparencyDecisionReceiptError):
    """Raised when a trust decision receipt does not satisfy policy."""
