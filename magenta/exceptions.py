"""Custom exceptions for the Magenta framework."""


class MagentaError(Exception):
    """Base exception for all Magenta errors."""


class StorageError(MagentaError):
    """Raised when a storage operation fails."""


class MissionError(MagentaError):
    """Raised when a mission operation fails."""


class MissionNotFoundError(MissionError):
    """Raised when a mission ID is not found."""


class ModelError(MagentaError):
    """Raised when an AI model call fails."""


class ModelTimeout(ModelError):  # noqa: N818
    """Raised when a model call times out."""


class AgentError(MagentaError):
    """Raised when an agent operation fails."""


class PlaybookError(MagentaError):
    """Raised when a playbook operation fails."""


class ConfigurationError(MagentaError):
    """Raised when configuration is invalid."""


class IdempotencyError(MagentaError):
    """Raised when an idempotent action is replayed with different params."""


class ApprovalError(MagentaError):
    """Raised when an approval gate rejects an action."""


class IntegrationError(MagentaError):
    """Raised when an external integration fails."""


class RegistryError(MagentaError):
    """Raised when a registry write operation fails."""


class DuplicateActionError(MagentaError):
    """Raised when an idempotent action is re-executed for the same alert+action+target."""


class WebhookError(MagentaError):
    """Raised when a webhook handler fails."""
