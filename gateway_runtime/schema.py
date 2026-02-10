"""Serialization strategy for adapter output."""

import json


class SchemaManager:
    """
    Handles serialization format for adapter output.

    Phase 1: JSON or Avro (configurable).
    Phase 2: Schema Registry integration.
    """

    def encode(self, message: dict) -> bytes:
        """Serialize message into bytes."""
        return json.dumps(message).encode("utf-8")
