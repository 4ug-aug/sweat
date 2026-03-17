class SweatError(Exception):
    """Base class for all application errors."""


class AsanaError(SweatError):
    """Raised when an Asana API call fails."""


class GitHubError(SweatError):
    """Raised when a GitHub API or git operation fails."""


class AgentError(SweatError):
    """Raised when the Claude agent SDK fails."""


class TaskSelectorError(SweatError):
    """Raised when the task selector cannot produce a result."""


class ConfigError(SweatError):
    """Raised when configuration is invalid or incomplete."""
