"""Custom exceptions for gateway runtime."""


class ConfigError(Exception):
    """Raised when config is invalid or missing."""


class AdapterStartError(Exception):
    """Raised when adapter fails to start."""


class KafkaError(Exception):
    """Raised when Kafka manager fails."""
