"""Error classes for Agent CLI."""

class AgentCLIError(Exception):
    """Base class for Agent CLI errors."""
    pass


class APIError(AgentCLIError):
    """Error from API communication."""
    pass


class ConfigError(AgentCLIError):
    """Error in configuration."""
    pass