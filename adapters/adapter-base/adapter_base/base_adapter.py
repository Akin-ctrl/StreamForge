"""Abstract base adapter class."""

from typing import Dict


class BaseAdapter:
    """
    Abstract base class for all adapters.

    Template Method pattern:
    run() defines lifecycle and calls overridable steps.
    """

    def __init__(self, config: dict) -> None:
        """Initialize adapter with validated config."""

    def run(self) -> None:
        """Run adapter lifecycle: connect → poll → transform → publish."""

    def connect(self) -> None:
        """Connect to device or data source."""

    def poll(self) -> Dict[str, object]:
        """Read raw data from device."""

    def transform(self, raw: Dict[str, object]) -> Dict[str, object]:
        """Normalize raw data into standard message format."""

    def publish(self, message: Dict[str, object]) -> None:
        """Publish normalized message to Kafka."""

    def health(self) -> Dict[str, object]:
        """Return adapter health status."""
