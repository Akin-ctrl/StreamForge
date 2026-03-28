"""Shared adapter base classes."""

from .base_adapter import BaseAdapter
from .kafka_publisher import KafkaPublisher

__all__ = ["BaseAdapter", "KafkaPublisher"]
