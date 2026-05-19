"""Tests for recent runtime log capture helpers."""

from __future__ import annotations

import logging
import unittest

from gateway_runtime.logging_utils import RecentLogBufferHandler, clear_recent_log_entries, configure_json_logging, recent_log_entries


class RecentLogCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_recent_log_entries()

    def tearDown(self) -> None:
        clear_recent_log_entries()

    def test_recent_log_entries_capture_structured_runtime_logs(self) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        original_level = root.level

        try:
            configure_json_logging("INFO")
            logger = logging.getLogger("gateway_runtime.validator")
            logger.warning("validator warning", extra={"component": "validator"})
        finally:
            root.handlers.clear()
            for handler in original_handlers:
                root.addHandler(handler)
            root.setLevel(original_level)

        entries = recent_log_entries(default_gateway_id="gw-edge-01")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["gateway_id"], "gw-edge-01")
        self.assertEqual(entries[0]["component"], "validator")
        self.assertEqual(entries[0]["message"], "validator warning")
        self.assertEqual(entries[0]["level"], "WARNING")

    def test_recent_log_entries_use_logger_suffix_when_component_is_missing(self) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        original_level = root.level

        try:
            configure_json_logging("INFO")
            logger = logging.getLogger("gateway_runtime.aggregator")
            logger.info("aggregate complete")
        finally:
            root.handlers.clear()
            for handler in original_handlers:
                root.addHandler(handler)
            root.setLevel(original_level)

        entries = recent_log_entries()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["component"], "aggregator")
        self.assertEqual(entries[0]["message"], "aggregate complete")

    def test_recent_log_entries_keep_only_bounded_tail(self) -> None:
        handler = RecentLogBufferHandler()

        for index in range(550):
            handler.emit(
                logging.LogRecord(
                    name="gateway_runtime.validator",
                    level=logging.INFO,
                    pathname=__file__,
                    lineno=0,
                    msg=f"message {index}",
                    args=(),
                    exc_info=None,
                )
            )

        entries = recent_log_entries(limit=600, default_gateway_id="gw-edge-01")

        self.assertEqual(len(entries), 500)
        self.assertEqual(entries[0]["message"], "message 50")
        self.assertEqual(entries[-1]["message"], "message 549")
        self.assertEqual(entries[-1]["gateway_id"], "gw-edge-01")

    def test_recent_log_entries_capture_formatted_exceptions(self) -> None:
        handler = RecentLogBufferHandler()
        try:
            raise RuntimeError("validator exploded")
        except RuntimeError:
            record = logging.LogRecord(
                name="gateway_runtime.validator",
                level=logging.ERROR,
                pathname=__file__,
                lineno=0,
                msg="validator failure",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )
        handler.emit(record)

        entries = recent_log_entries(limit=1)

        self.assertEqual(entries[0]["message"], "validator failure")
        self.assertIn("RuntimeError: validator exploded", str(entries[0]["exception"]))
