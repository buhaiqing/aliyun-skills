#!/usr/bin/env python3
"""Langfuse Token Consumption Report — pull traces from Langfuse, aggregate by sessionID.

Provides two subcommands:
- pull: aggregate traces by session_id across a time period
- session: drill down on a single session_id

Data source: Langfuse HTTP API (GET /api/public/traces).
Filter: only traces with metadata.has_llm_usage=true or llm_usage.total_tokens > 0.

Exit codes:
    0  success
    1  missing credentials
    2  network error
    3  auth error (401/403)
    4  rate limited (429)
    5  invalid argument
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPORT_VERSION = "1.0.0"
EXIT_OK = 0
EXIT_NO_CREDS = 1
EXIT_NETWORK = 2
EXIT_AUTH = 3
EXIT_RATE = 4
EXIT_USAGE = 5


# ---------------------------------------------------------------------------
# Credential loading (reuse pattern from test-langfuse-reporting.sh)
# ---------------------------------------------------------------------------


def load_credentials() -> tuple[str, str, str]:
    """Load Langfuse credentials from .env or environment variables.

    Returns:
        (host, public_key, secret_key)

    Exits with EXIT_NO_CREDS if missing.
    """
    env_file = os.environ.get("LANGFUSE_ENV_FILE")
    if env_file and Path(env_file).is_file():
        for line in Path(env_file).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    host = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", "")
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not host or not pk or not sk:
        print(
            "[BLOCKED:no-credentials] LANGFUSE_HOST/LANGFUSE_PUBLIC_KEY/"
            "LANGFUSE_SECRET_KEY missing. Set them in .env or as environment variables.",
            file=sys.stderr,
        )
        sys.exit(EXIT_NO_CREDS)

    return host.rstrip("/"), pk, sk


# ---------------------------------------------------------------------------
# Langfuse API client
# ---------------------------------------------------------------------------


class LangfuseAPIError(Exception):
    """Raised when Langfuse API returns an error."""

    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class LangfuseClient:
    """Minimal Langfuse v2 API client."""

    host: str
    public_key: str
    secret_key: str
    timeout: int = 30
    max_retries: int = 3

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self.public_key}:{self.secret_key}".encode()).decode()
        return f"Basic {token}"

    def fetch_traces_page(self, page: int, limit: int, from_ts: str | None = None,
                          to_ts: str | None = None) -> dict[str, Any]:
        """Fetch one page of traces from Langfuse.

        Raises LangfuseAPIError on auth/network/rate errors.
        """
        params = [f"page={page}", f"limit={limit}"]
        if from_ts:
            params.append(f"fromTimestamp={from_ts}")
        if to_ts:
            params.append(f"toTimestamp={to_ts}")
        url = f"{self.host}/api/public/traces?{'&'.join(params)}"

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"Authorization": self._auth_header()},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise LangfuseAPIError(f"auth error: HTTP {e.code}", EXIT_AUTH) from e
                if e.code == 429:
                    if attempt < self.max_retries - 1:
                        wait = 2 ** attempt
                        time.sleep(wait)
                        continue
                    raise LangfuseAPIError("rate limited", EXIT_RATE) from e
                if 500 <= e.code < 600 and attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise LangfuseAPIError(f"HTTP {e.code}: {e.reason}", EXIT_NETWORK) from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

        raise LangfuseAPIError(f"network error: {last_err}", EXIT_NETWORK)

    def iter_traces(self, from_ts: str, to_ts: str, page_size: int = 100) -> list[dict]:
        """Iterate all trace pages in [from_ts, to_ts] time range."""
        all_traces: list[dict] = []
        page = 1
        while True:
            resp = self.fetch_traces_page(page, page_size, from_ts, to_ts)
            data = resp.get("data", [])
            all_traces.extend(data)
            meta = resp.get("meta", {})
            total_pages = meta.get("totalPages", 1)
            if page >= total_pages or not data:
                break
            page += 1
        return all_traces


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class SessionAggregate:
    session_id: str
    trace_count: int = 0
    skill_set: set = field(default_factory=set)
    user_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    first_trace_at: str = ""
    last_trace_at: str = ""


def _has_llm_usage(trace: dict) -> bool:
    """Return True if trace has any token consumption."""
    metadata = trace.get("metadata", {})
    if metadata.get("has_llm_usage") is True:
        return True
    usage = metadata.get("llm_usage", {})
    return usage.get("total_tokens", 0) > 0


def aggregate_by_session(traces: list[dict]) -> list[SessionAggregate]:
    """Aggregate token usage grouped by session_id.

    Only traces with token consumption are included.
    Missing session_id is bucketed as "(no-session)".
    """
    buckets: dict[str, SessionAggregate] = {}
    for trace in traces:
        if not _has_llm_usage(trace):
            continue
        metadata = trace.get("metadata", {})
        session_id = metadata.get("session_id") or "(no-session)"
        usage = metadata.get("llm_usage", {})
        ts = trace.get("timestamp", "")

        if session_id not in buckets:
            buckets[session_id] = SessionAggregate(session_id=session_id)
        b = buckets[session_id]
        b.trace_count += 1
        b.skill_set.add(metadata.get("skill", "unknown"))
        b.user_id = b.user_id or metadata.get("user_id", "")
        b.prompt_tokens += usage.get("prompt_tokens", 0) or 0
        b.completion_tokens += usage.get("completion_tokens", 0) or 0
        b.total_tokens += usage.get("total_tokens", 0) or 0
        if ts:
            if not b.first_trace_at or ts < b.first_trace_at:
                b.first_trace_at = ts
            if not b.last_trace_at or ts > b.last_trace_at:
                b.last_trace_at = ts

    # Sort by total_tokens descending
    sorted_buckets = sorted(buckets.values(), key=lambda b: -b.total_tokens)
    return sorted_buckets


def build_report(sessions: list[SessionAggregate], from_ts: str, to_ts: str) -> dict:
    """Build the full JSON report structure."""
    total_traces = sum(s.trace_count for s in sessions)
    total_prompt = sum(s.prompt_tokens for s in sessions)
    total_completion = sum(s.completion_tokens for s in sessions)
    total_tokens = sum(s.total_tokens for s in sessions)

    return {
        "version": REPORT_VERSION,
        "period": {
            "from": from_ts,
            "to": to_ts,
            "days": (
                datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
                - datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
            ).days
            if from_ts and to_ts
            else 0,
        },
        "summary": {
            "total_sessions": len(sessions),
            "total_traces": total_traces,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
        },
        "sessions": [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "trace_count": s.trace_count,
                "skill_count": len(s.skill_set),
                "skills": sorted(s.skill_set),
                "prompt_tokens": s.prompt_tokens,
                "completion_tokens": s.completion_tokens,
                "total_tokens": s.total_tokens,
                "first_trace_at": s.first_trace_at,
                "last_trace_at": s.last_trace_at,
            }
            for s in sessions
        ],
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_table(report: dict) -> str:
    """Render the report as a CLI table."""
    period = report["period"]
    summary = report["summary"]
    sessions = report["sessions"]

    lines = []
    lines.append("=== Langfuse Token Consumption Report ===")
    lines.append(
        f"Period: {period['from']} → {period['to']} "
        f"({period['days']} days)"
    )
    lines.append(
        f"Total Sessions: {summary['total_sessions']}   "
        f"Total Traces: {summary['total_traces']}   "
        f"Total Tokens: {summary['total_tokens']:,}"
    )
    lines.append("-" * 95)

    if not sessions:
        lines.append("(no session records with token consumption in this period)")
        return "\n".join(lines)

    lines.append(
        f"{'Session ID':<35} {'Traces':>7} {'Prompt':>10} "
        f"{'Completion':>11} {'Total':>10} {'User':<14}"
    )
    lines.append("-" * 95)
    for s in sessions:
        sid = s["session_id"][:33] + ".." if len(s["session_id"]) > 35 else s["session_id"]
        lines.append(
            f"{sid:<35} {s['trace_count']:>7} "
            f"{s['prompt_tokens']:>10,} "
            f"{s['completion_tokens']:>11,} "
            f"{s['total_tokens']:>10,} "
            f"{s['user_id'][:14]:<14}"
        )
    lines.append("-" * 95)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_period(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve from/to timestamps from CLI args."""
    now = datetime.now(timezone.utc)
    if args.from_date and args.to_date:
        from_dt = datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
        to_dt = datetime.fromisoformat(args.to_date).replace(tzinfo=timezone.utc)
    else:
        days = args.since_days if args.since_days is not None else 7
        from_dt = now - timedelta(days=days)
        to_dt = now
    return (
        from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def cmd_pull(args: argparse.Namespace) -> int:
    """Aggregate token consumption by sessionID across a period."""
    host, pk, sk = load_credentials()
    from_ts, to_ts = _resolve_period(args)
    client = LangfuseClient(host=host, public_key=pk, secret_key=sk)

    try:
        print(f"[langfuse-token-report] fetching traces from {from_ts} to {to_ts}...", file=sys.stderr)
        traces = client.iter_traces(from_ts, to_ts)
    except LangfuseAPIError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code

    print(f"[langfuse-token-report] {len(traces)} traces pulled", file=sys.stderr)
    sessions = aggregate_by_session(traces)
    report = build_report(sessions, from_ts, to_ts)

    output = args.output
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2)
    elif args.format == "csv":
        text = _render_csv(report)
    else:
        text = render_table(report)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"[langfuse-token-report] written to {output}", file=sys.stderr)
    else:
        print(text)
    return EXIT_OK


def _render_csv(report: dict) -> str:
    """Render the report as CSV."""
    lines = ["session_id,user_id,trace_count,skill_count,prompt_tokens,completion_tokens,total_tokens,first_trace_at,last_trace_at"]
    for s in report["sessions"]:
        lines.append(
            f"{s['session_id']},{s['user_id']},{s['trace_count']},"
            f"{s['skill_count']},{s['prompt_tokens']},"
            f"{s['completion_tokens']},{s['total_tokens']},"
            f"{s['first_trace_at']},{s['last_trace_at']}"
        )
    return "\n".join(lines)


def cmd_session(args: argparse.Namespace) -> int:
    """Drill down on a single session_id."""
    host, pk, sk = load_credentials()
    from_ts, to_ts = _resolve_period(args)
    client = LangfuseClient(host=host, public_key=pk, secret_key=sk)

    try:
        traces = client.iter_traces(from_ts, to_ts)
    except LangfuseAPIError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code

    matching = [
        t for t in traces
        if t.get("metadata", {}).get("session_id") == args.session_id
    ]
    if not matching:
        print(f"no traces found for session_id={args.session_id}", file=sys.stderr)
        return EXIT_OK

    print(f"=== Session: {args.session_id} ===")
    print(f"Traces: {len(matching)}")
    print("-" * 90)
    for t in matching:
        meta = t.get("metadata", {})
        usage = meta.get("llm_usage", {})
        ts = t.get("timestamp", "")
        print(
            f"{ts}  skill={meta.get('skill','?'):<25} "
            f"prompt={usage.get('prompt_tokens',0):>6,} "
            f"completion={usage.get('completion_tokens',0):>5,} "
            f"total={usage.get('total_tokens',0):>6,}"
        )
    print("-" * 90)

    total = sum(t.get("metadata", {}).get("llm_usage", {}).get("total_tokens", 0) for t in matching)
    print(f"Total Tokens: {total:,}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="langfuse_token_report",
        description="Pull token consumption report from Langfuse.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--since-days", type=int, default=None,
        help="Last N days (default: 7). Conflicts with --from/--to.",
    )
    common.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    common.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    common.add_argument("--limit", type=int, default=100, help="Page size (default: 100)")

    pull = sub.add_parser("pull", parents=[common], help="Aggregate by session_id across period")
    pull.add_argument("--format", choices=["table", "json", "csv"], default="table")
    pull.add_argument("--output", "-o", type=str, default=None, help="Output file (default: stdout)")
    pull.set_defaults(func=cmd_pull)

    session = sub.add_parser("session", parents=[common], help="Drill down on one session_id")
    session.add_argument("--session-id", required=True, help="Target session_id")
    session.set_defaults(func=cmd_session)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
