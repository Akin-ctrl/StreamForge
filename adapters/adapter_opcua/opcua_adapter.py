"""OPC UA adapter implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any

from adapters.adapter_base.base_adapter import BaseAdapter


@dataclass(frozen=True)
class MonitoredItemSpec:
    node_id: str
    parameter: str
    unit: str
    asset_id: str | None


class _SubscriptionHandler:
    def __init__(self, adapter: "OpcUaAdapter") -> None:
        self._adapter = adapter

    def datachange_notification(self, node, value, data) -> None:
        self._adapter._ingest_datachange(node, value, data)


class OpcUaAdapter(BaseAdapter):
    """Telemetry-first OPC UA adapter using monitored item subscriptions."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._client = None
        self._subscription = None
        self._subscription_handles: list[object] = []
        self._queue: Queue[dict[str, Any]] = Queue()
        self._connected = False
        self._monitored_items = self._load_monitored_items()
        self._health.update(
            {
                "transport": "opcua",
                "endpoint": str(config.get("endpoint", "")),
                "security_mode": str(config.get("security_mode", "None")),
                "security_policy": str(config.get("security_policy", "None")),
                "monitored_item_count": len(self._monitored_items),
                "received_updates": 0,
                "parsed_updates": 0,
                "parse_failures": 0,
                "last_node_id": None,
                "last_message_type": "telemetry",
            }
        )

    def connect(self) -> None:
        """Connect to an OPC UA server and subscribe to monitored items."""
        endpoint = str(self.config.get("endpoint") or "").strip()
        if not endpoint:
            raise RuntimeError("OPC UA adapter requires 'endpoint'")

        security_mode = str(self.config.get("security_mode", "None"))
        security_policy = str(self.config.get("security_policy", "None"))
        if security_mode != "None" or security_policy != "None":
            raise RuntimeError("OPC UA adapter V1 supports only security_mode=None and security_policy=None")

        client = self._create_client(endpoint)
        username = str(self.config.get("username", "") or "")
        password = str(self.config.get("password", "") or "")
        if username:
            if hasattr(client, "set_user"):
                client.set_user(username)
            if hasattr(client, "set_password"):
                client.set_password(password)

        client.connect()
        subscription = client.create_subscription(
            int(self.config.get("subscription_interval_ms", 1000)),
            _SubscriptionHandler(self),
        )
        handles: list[object] = []
        for spec in self._monitored_items:
            node = client.get_node(spec.node_id)
            handle = subscription.subscribe_data_change(node)
            handles.append(handle)

        self._client = client
        self._subscription = subscription
        self._subscription_handles = handles
        self._connected = True
        self._health["connected"] = True

    def disconnect(self) -> None:
        if self._subscription is not None:
            try:
                if self._subscription_handles and hasattr(self._subscription, "unsubscribe"):
                    self._subscription.unsubscribe(self._subscription_handles)
            except Exception:
                pass
            try:
                if hasattr(self._subscription, "delete"):
                    self._subscription.delete()
            except Exception:
                pass
            self._subscription = None
            self._subscription_handles = []

        if self._client is not None:
            try:
                self._client.disconnect()
            finally:
                self._client = None
        self._connected = False
        self._health["connected"] = False

    def run(self) -> None:
        previous_handlers = self._install_signal_handlers()
        try:
            self._set_status("starting", connected=False, running=False, last_error=None)
            self.connect()
            self._set_status("healthy", connected=True, running=True, last_error=None)
            while not self._stop_event.is_set():
                raw = self.poll()
                if raw is None:
                    continue
                self._health["last_poll_at"] = self._utcnow()
                message = self.transform(raw)
                self.publish(message)
                self._health["last_publish_at"] = self._utcnow()
                self._set_status("healthy", connected=True, running=True, last_error=None)
        except Exception as exc:
            self._set_status("failed", running=False, last_error=str(exc))
            raise
        finally:
            try:
                self.disconnect()
            finally:
                if self._publisher is not None:
                    self._publisher.close()
                status = "stopped" if self._health.get("status") != "failed" else "failed"
                self._set_status(status, connected=False, running=False)
                self._restore_signal_handlers(previous_handlers)

    def poll(self) -> dict[str, Any] | None:
        while not self._stop_event.is_set():
            try:
                return self._queue.get(timeout=0.5)
            except Empty:
                continue
        return None

    def transform(self, raw: dict[str, Any]) -> dict[str, object]:
        return {
            "asset_id": raw["asset_id"],
            "gateway_time": datetime.now(timezone.utc).isoformat(),
            "readings": [
                {
                    "parameter": raw["parameter"],
                    "value": raw["value"],
                    "unit": raw["unit"],
                    "quality": "GOOD",
                    "device_time": raw.get("device_time"),
                }
            ],
        }

    def _load_monitored_items(self) -> tuple[MonitoredItemSpec, ...]:
        specs: list[MonitoredItemSpec] = []
        for item in self.config.get("monitored_items", []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id", "")).strip()
            parameter = str(item.get("parameter", "")).strip()
            if not node_id or not parameter:
                continue
            specs.append(
                MonitoredItemSpec(
                    node_id=node_id,
                    parameter=parameter,
                    unit=str(item.get("unit", "")),
                    asset_id=str(item["asset_id"]) if item.get("asset_id") else None,
                )
            )
        if not specs:
            raise RuntimeError("OPC UA adapter requires at least one monitored_item")
        return tuple(specs)

    def _ingest_datachange(self, node, value, data) -> None:
        node_id = self._node_id(node)
        spec = self._spec_for_node(node_id)
        if spec is None:
            self._health["parse_failures"] = int(self._health.get("parse_failures", 0)) + 1
            self._health["last_error"] = f"Unmapped OPC UA node: {node_id}"
            self._set_status("degraded", connected=self._connected, running=bool(self._health.get("running")), last_error=self._health["last_error"])
            return

        self._health["received_updates"] = int(self._health.get("received_updates", 0)) + 1
        self._health["parsed_updates"] = int(self._health.get("parsed_updates", 0)) + 1
        self._health["last_node_id"] = node_id
        self._queue.put(
            {
                "asset_id": spec.asset_id or self.config.get("output", {}).get("asset_id") or self._adapter_id,
                "parameter": spec.parameter,
                "unit": spec.unit,
                "value": value,
                "device_time": self._extract_device_time(data),
            }
        )

    def _spec_for_node(self, node_id: str) -> MonitoredItemSpec | None:
        for spec in self._monitored_items:
            if spec.node_id == node_id:
                return spec
        return None

    @staticmethod
    def _node_id(node) -> str:
        nodeid = getattr(node, "nodeid", None)
        return str(nodeid if nodeid is not None else node)

    @staticmethod
    def _extract_device_time(data) -> str | None:
        candidates = [
            getattr(data, "source_timestamp", None),
            getattr(data, "SourceTimestamp", None),
        ]
        monitored_value = getattr(data, "monitored_item", None) or getattr(data, "monitored_item_value", None)
        if monitored_value is not None:
            candidates.extend(
                [
                    getattr(monitored_value, "SourceTimestamp", None),
                    getattr(getattr(monitored_value, "Value", None), "SourceTimestamp", None),
                ]
            )
        for candidate in candidates:
            if isinstance(candidate, datetime):
                if candidate.tzinfo is None:
                    return candidate.replace(tzinfo=timezone.utc).isoformat()
                return candidate.astimezone(timezone.utc).isoformat()
        return None

    @staticmethod
    def _create_client(endpoint: str):
        try:
            from asyncua.sync import Client  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("asyncua is required for OpcUaAdapter") from exc

        return Client(endpoint)
