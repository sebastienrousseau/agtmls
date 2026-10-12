# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""OpenTelemetry (OTLP) HTTP/JSON trace emitter for AgtMLS.

Encodes agent steps, skill evaluations, and validation gate events into
standard OTLP/HTTP v1 traces (Trace JSON Schema) for ingestion by
OpenTelemetry-compatible collectors (Grafana Tempo, Datadog, Langfuse).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

OTLP_VERSION = "1.0.0"
SPAN_KIND_INTERNAL = 1
STATUS_CODE_UNSET = 0
STATUS_CODE_OK = 1
STATUS_CODE_ERROR = 2


def generate_trace_id(seed: str = "") -> str:
    """Generate a valid 16-byte (32 hex char) OpenTelemetry trace ID."""
    if seed:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"https://agtmls.dev/traces/{seed}").hex
    return uuid.uuid4().hex


def generate_span_id(seed: str = "") -> str:
    """Generate a valid 8-byte (16 hex char) OpenTelemetry span ID."""
    if seed:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"https://agtmls.dev/spans/{seed}").hex[:16]
    return uuid.uuid4().hex[:16]


def format_attribute_value(val: Any) -> dict[str, Any]:
    """Map Python primitives to OTLP AnyValue representation."""
    if isinstance(val, bool):
        return {"boolValue": val}
    if isinstance(val, int):
        return {"intValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, (list, tuple)):
        return {"arrayValue": {"values": [format_attribute_value(v) for v in val]}}
    return {"stringValue": str(val)}


def build_span(
    name: str,
    trace_id: str,
    span_id: str,
    parent_span_id: str = "",
    kind: int = SPAN_KIND_INTERNAL,
    start_time_ns: int = 0,
    end_time_ns: int = 0,
    attributes: dict[str, Any] | None = None,
    status_code: int = STATUS_CODE_OK,
    status_message: str = "",
) -> dict[str, Any]:
    """Build a compliant OTLP Span JSON object."""
    now_ns = time.time_ns()
    start_ns = start_time_ns or now_ns
    end_ns = end_time_ns or now_ns

    attrs_list = [
        {"key": k, "value": format_attribute_value(v)}
        for k, v in (attributes or {}).items()
    ]

    status: dict[str, Any] = {"code": status_code}
    if status_message:
        status["message"] = status_message

    span: dict[str, Any] = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": attrs_list,
        "status": status,
    }
    if parent_span_id:
        span["parentSpanId"] = parent_span_id
    return span


def build_resource_spans(
    spans: list[dict[str, Any]],
    service_name: str = "agtmls",
    service_version: str = "0.0.23",
    resource_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap spans in an OTLP ResourceSpans container."""
    res_attrs = {"service.name": service_name, "service.version": service_version}
    if resource_attributes:
        res_attrs.update(resource_attributes)

    formatted_res_attrs = [
        {"key": k, "value": format_attribute_value(v)}
        for k, v in res_attrs.items()
    ]

    return {
        "resourceSpans": [
            {
                "resource": {"attributes": formatted_res_attrs},
                "scopeSpans": [
                    {
                        "scope": {"name": "agtmls.telemetry", "version": service_version},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def export_otlp_json(
    spans: list[dict[str, Any]],
    service_name: str = "agtmls",
    service_version: str = "0.0.23",
    indent: int | None = 2,
) -> str:
    """Serialize resource spans to standard OTLP JSON format."""
    payload = build_resource_spans(spans, service_name, service_version)
    return json.dumps(payload, indent=indent, sort_keys=True)


def send_otlp_http(
    endpoint: str,
    payload: dict[str, Any] | str,
    headers: dict[str, str] | None = None,
    timeout: float = 3.0,
) -> bool:
    """Send OTLP trace JSON to an HTTP/HTTPS collector endpoint."""
    url = endpoint.rstrip("/")
    if not url.endswith("/v1/traces"):
        url = f"{url}/v1/traces"

    body = payload if isinstance(payload, str) else json.dumps(payload)
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(
        url=url,
        data=body.encode("utf-8"),
        headers=req_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False
