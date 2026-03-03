"""Serialization strategy for adapter output."""

import json


class SchemaManager:
    """
    Handles serialization format for adapter output.
    """

    def encode(self, message: dict) -> bytes:
        """Serialize message into bytes."""
        return json.dumps(message).encode("utf-8")
