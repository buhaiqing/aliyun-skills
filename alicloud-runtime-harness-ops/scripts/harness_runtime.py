#!/usr/bin/env python3
import argparse
import base64
import json
import os
import urllib.request
from typing import Any


def load_json(value: str, default: Any) -> Any:
    if value == "" or value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def post(endpoint: str, payload: dict[str, Any]) -> None:
    if os.environ.get("SKILLOPT_LANGFUSE_ENABLED") != "true":
        return
    host = os.environ.get("LANGFUSE_HOST", "")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not host or not public_key or not secret_key:
        return
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{host}{endpoint}",
        data=data,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        return


def event(event_id: str, event_type: str, timestamp: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"id": event_id, "type": event_type, "timestamp": timestamp, "body": body}


def cmd_span_create(args: argparse.Namespace) -> None:
    metadata = load_json(args.metadata_json, {})
    if args.status:
        metadata = {**metadata, "status": args.status}
    body = {
        "id": args.span_id,
        "traceId": args.trace_id,
        "name": args.name,
        "startTime": args.timestamp,
        "metadata": metadata,
    }
    if args.end_time:
        body["endTime"] = args.end_time
    if args.parent_id and args.parent_id != args.span_id:
        body["parentObservationId"] = args.parent_id
    if args.input_json != "":
        body["input"] = load_json(args.input_json, None)
    if args.output_json != "":
        body["output"] = load_json(args.output_json, None)
    if args.level:
        body["level"] = args.level
    if args.status_message != "":
        body["statusMessage"] = args.status_message
    post("/api/public/ingestion", {"batch": [event(args.span_id, "span-create", args.timestamp, body)]})


def cmd_generation_create(args: argparse.Namespace) -> None:
    metadata = load_json(args.metadata_json, {})
    usage: dict[str, int] = {}
    if args.prompt_tokens:
        usage["promptTokens"] = int(args.prompt_tokens)
    if args.completion_tokens:
        usage["completionTokens"] = int(args.completion_tokens)
    if args.total_tokens:
        usage["totalTokens"] = int(args.total_tokens)
    body: dict[str, Any] = {
        "id": args.generation_id,
        "traceId": args.trace_id,
        "name": args.name,
        "startTime": args.timestamp,
        "model": args.model,
        "metadata": metadata,
    }
    if args.end_time:
        body["endTime"] = args.end_time
    if usage:
        body["usage"] = usage
    if args.parent_id:
        body["parentObservationId"] = args.parent_id
    post(
        "/api/public/ingestion",
        {"batch": [event(args.generation_id, "generation-create", args.timestamp, body)]},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("span-create")
    p.add_argument("--span-id", required=True)
    p.add_argument("--trace-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--end-time", default="")
    p.add_argument("--parent-id", default="")
    p.add_argument("--input-json", default="")
    p.add_argument("--output-json", default="")
    p.add_argument("--metadata-json", default="{}")
    p.add_argument("--status", default="")
    p.add_argument("--level", default="")
    p.add_argument("--status-message", default="")
    p.set_defaults(func=cmd_span_create)
    g = sub.add_parser("generation-create")
    g.add_argument("--generation-id", required=True)
    g.add_argument("--trace-id", required=True)
    g.add_argument("--name", required=True)
    g.add_argument("--timestamp", required=True)
    g.add_argument("--model", required=True)
    g.add_argument("--prompt-tokens", default="0")
    g.add_argument("--completion-tokens", default="0")
    g.add_argument("--total-tokens", default="0")
    g.add_argument("--end-time", default="")
    g.add_argument("--parent-id", default="")
    g.add_argument("--metadata-json", default="{}")
    g.set_defaults(func=cmd_generation_create)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
