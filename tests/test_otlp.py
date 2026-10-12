# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for OpenTelemetry (OTLP) HTTP/JSON trace emitter."""

from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _lib.otlp import (
    build_resource_spans,
    build_span,
    export_otlp_json,
    format_attribute_value,
    generate_span_id,
    generate_trace_id,
    send_otlp_http,
)


class OTLPTraceTests(unittest.TestCase):
    def test_trace_and_span_id_generation(self) -> None:
        t1 = generate_trace_id()
        t2 = generate_trace_id()
        self.assertEqual(len(t1), 32)
        self.assertEqual(len(t2), 32)
        self.assertNotEqual(t1, t2)

        s1 = generate_span_id()
        s2 = generate_span_id()
        self.assertEqual(len(s1), 16)
        self.assertEqual(len(s2), 16)
        self.assertNotEqual(s1, s2)

    def test_deterministic_ids_with_seed(self) -> None:
        seed = "eval-run-42"
        t_seed1 = generate_trace_id(seed)
        t_seed2 = generate_trace_id(seed)
        self.assertEqual(t_seed1, t_seed2)
        self.assertEqual(len(t_seed1), 32)

        s_seed1 = generate_span_id(seed)
        s_seed2 = generate_span_id(seed)
        self.assertEqual(s_seed1, s_seed2)
        self.assertEqual(len(s_seed1), 16)

    def test_format_attribute_value(self) -> None:
        self.assertEqual(format_attribute_value(True), {"boolValue": True})
        self.assertEqual(format_attribute_value(False), {"boolValue": False})
        self.assertEqual(format_attribute_value(123), {"intValue": "123"})
        self.assertEqual(format_attribute_value(3.14), {"doubleValue": 3.14})
        self.assertEqual(format_attribute_value("hello"), {"stringValue": "hello"})
        self.assertEqual(
            format_attribute_value([1, "a"]),
            {"arrayValue": {"values": [{"intValue": "1"}, {"stringValue": "a"}]}},
        )

    def test_build_span(self) -> None:
        trace_id = generate_trace_id("t")
        span_id = generate_span_id("s")
        span = build_span(
            name="skill_verification",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="parent1234567890",
            start_time_ns=1000,
            end_time_ns=2000,
            attributes={"skill.name": "writing-plans", "status.passed": True},
            status_code=1,
            status_message="OK",
        )
        self.assertEqual(span["name"], "skill_verification")
        self.assertEqual(span["traceId"], trace_id)
        self.assertEqual(span["spanId"], span_id)
        self.assertEqual(span["parentSpanId"], "parent1234567890")
        self.assertEqual(span["startTimeUnixNano"], "1000")
        self.assertEqual(span["endTimeUnixNano"], "2000")
        self.assertEqual(span["status"]["code"], 1)
        self.assertEqual(span["status"]["message"], "OK")
        self.assertEqual(len(span["attributes"]), 2)

    def test_build_span_defaults(self) -> None:
        trace_id = generate_trace_id("d")
        span_id = generate_span_id("d")
        span = build_span(name="check", trace_id=trace_id, span_id=span_id)
        self.assertNotIn("parentSpanId", span)
        self.assertNotIn("message", span["status"])
        self.assertTrue(int(span["startTimeUnixNano"]) > 0)
        self.assertTrue(int(span["endTimeUnixNano"]) > 0)

    def test_build_resource_spans_and_export_json(self) -> None:
        span = build_span(name="eval", trace_id="0" * 32, span_id="0" * 16)
        container = build_resource_spans(
            [span],
            service_name="custom-service",
            service_version="1.2.3",
            resource_attributes={"deployment.environment": "ci"},
        )
        self.assertEqual(len(container["resourceSpans"]), 1)
        res_attrs = container["resourceSpans"][0]["resource"]["attributes"]
        attr_dict = {a["key"]: a["value"]["stringValue"] for a in res_attrs}
        self.assertEqual(attr_dict["service.name"], "custom-service")
        self.assertEqual(attr_dict["service.version"], "1.2.3")
        self.assertEqual(attr_dict["deployment.environment"], "ci")

        json_str = export_otlp_json([span])
        parsed = json.loads(json_str)
        self.assertIn("resourceSpans", parsed)

    @patch("urllib.request.urlopen")
    def test_send_otlp_http_success(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        span = build_span(name="test", trace_id="0" * 32, span_id="0" * 16)
        res = send_otlp_http(
            "http://localhost:4318",
            {"resourceSpans": [{"scopeSpans": [{"spans": [span]}]}]},
            headers={"Authorization": "Bearer token"},
        )
        self.assertTrue(res)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://localhost:4318/v1/traces")
        self.assertEqual(req.headers["Authorization"], "Bearer token")
        self.assertEqual(req.headers["Content-type"], "application/json")

    @patch("urllib.request.urlopen")
    def test_send_otlp_http_failures(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        self.assertFalse(send_otlp_http("http://localhost:4318/v1/traces", "{}"))

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        self.assertFalse(send_otlp_http("http://localhost:4318", "{}"))

        mock_urlopen.side_effect = TimeoutError()
        self.assertFalse(send_otlp_http("http://localhost:4318", "{}"))


if __name__ == "__main__":
    unittest.main()
