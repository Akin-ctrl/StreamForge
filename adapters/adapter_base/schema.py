"""Serialization utilities shared by adapter containers."""

from __future__ import annotations

import json


class SchemaManager:
    """Serialize adapter output using the repo's current JSON message path."""

    def encode(self, message: dict[str, object]) -> bytes:
        """Serialize a normalized adapter message into Kafka bytes."""
        return json.dumps(message).encode("utf-8")
