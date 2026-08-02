#!/usr/bin/env python3
"""
trace_query.py — P3b: Unified GCL trace query CLI.

Provides a single entry point for querying GCL traces across multiple
dimensions: by skill, operation, decision, time range, correlation,
and failure pattern.

USAGE
-----
    # List recent traces for a skill
    python3 scripts/trace_query.py --skill alicloud-ecs-ops --limit 10

    # Filter by decision
    python3 scripts/trace_query.py --decision SAFETY_FAIL --since 7d

    # Query by correlation session
    python3 scripts/trace_query.py --session-id abc123

    # Full-text search in failure patterns
    python3 scripts/trace_query.py --grep "InvalidParameter"

    # JSON output for piping
    python3 scripts/trace_query.py --skill alicloud-rds-ops --json

EXIT CODES
----------
    0  Success (results found or empty set)
    1  Error (e.g. trace dir not found)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [TRACE-QUERY] {msg}", file=sys.stderr)


def _filename_timestamp(path: Path) -> datetime | None:
    """Extract timestamp from trace filename (gcl-trace-YYYYMMDD-HHMMSS-*.json)."""
    m = re.match(r"gcl-trace-(\d{8})-(\d{6})-", path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_since(since_str: str) -> int:
    """Parse time-window string like '24h', '7d' into hours."""
    if since_str.endswith("h"):
        return int(since_str[:-1])
    if since_str.endswith("d"):
        return int(since_str[:-1]) * 24
    return 24 * 7  # default 7d


def load_traces(
    trace_dir: Path,
    since_hours: int | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Load trace files, optionally filtered by filename timestamp pre-filter."""
    if not trace_dir.is_dir():
        return []

    cutoff: datetime | None = None
    if since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    results: list[tuple[Path, dict[str, Any]]] = []
    for fpath in sorted(trace_dir.glob("gcl-trace-*.json"), reverse=True):
        if cutoff:
            fname_ts = _filename_timestamp(fpath)
            if fname_ts is not None and fname_ts < cutoff:
                continue
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        results.append((fpath, data))

    return results


def query_traces(
    trace_dir: Path,
    *,
    skill: str | None = None,
    operation: str | None = None,
    decision: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    grep: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query traces with multiple filter dimensions.

    Returns list of summary dicts for matching traces.
    """
    since_hours = parse_since(since) if since else None
    all_traces = load_traces(trace_dir, since_hours)

    matches: list[dict[str, Any]] = []

    for fpath, trace in all_traces:
        # Skill filter
        if skill and trace.get("skill") != skill:
            continue

        # Decision filter (check final status or iteration decisions)
        if decision:
            final_status = trace.get("final", {}).get("status", "")
            iter_decisions = [it.get("decision", "") for it in trace.get("iterations", [])]
            if decision != final_status and decision not in iter_decisions:
                continue

        # Operation filter (check iterations for command containing op)
        if operation:
            found_op = False
            for it in trace.get("iterations", []):
                cmd = it.get("generator", {}).get("command", "")
                if operation in cmd:
                    found_op = True
                    break
            if not found_op:
                continue

        # Correlation: session_id filter
        if session_id:
            corr = trace.get("correlation", {})
            if corr.get("session_id") != session_id:
                continue

        # Correlation: user_id filter
        if user_id:
            corr = trace.get("correlation", {})
            if corr.get("user_id") != user_id:
                continue

        # Full-text grep in failure_pattern
        if grep:
            fp = trace.get("failure_pattern")
            fp_str = json.dumps(fp, ensure_ascii=False) if fp else ""
            trace_str = json.dumps(trace.get("final", {}), ensure_ascii=False)
            if grep.lower() not in fp_str.lower() and grep.lower() not in trace_str.lower():
                continue

        # Build summary
        final = trace.get("final", {})
        corr = trace.get("correlation", {})
        iterations = trace.get("iterations", [])
        summary: dict[str, Any] = {
            "file": fpath.name,
            "timestamp": trace.get("timestamp", ""),
            "skill": trace.get("skill", ""),
            "schema_version": trace.get("schema_version", ""),
            "status": final.get("status", ""),
            "iterations": len(iterations),
            "session_id": corr.get("session_id", ""),
            "wrapper_trace_id": corr.get("wrapper_trace_id", ""),
        }

        # Include failure pattern summary if present
        fp = trace.get("failure_pattern")
        if fp and isinstance(fp, dict):
            summary["failure_category"] = fp.get("category", "")
            summary["failure_skill"] = fp.get("skill", "")

        matches.append(summary)

        if len(matches) >= limit:
            break

    return matches


def format_table(results: list[dict[str, Any]]) -> str:
    """Format results as a compact ASCII table."""
    if not results:
        return "(no matching traces)"

    lines: list[str] = []
    header = f"{'FILE':<45} {'SKILL':<25} {'STATUS':<18} {'ITERS':<6} {'TIMESTAMP':<22}"
    lines.append(header)
    lines.append("-" * len(header))

    for r in results:
        ts = r.get("timestamp", "")[:19]
        lines.append(
            f"{r['file']:<45} {r['skill']:<25} {r['status']:<18} "
            f"{r['iterations']:<6} {ts:<22}"
        )

    lines.append(f"\n({len(results)} trace(s))")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_query.py",
        description="P3b: Unified GCL trace query tool.",
    )
    parser.add_argument(
        "--trace-dir", type=Path,
        default=Path(os.environ.get(
            "ALIYUN_SKILLS_RUNTIME_ROOT",
            Path(__file__).resolve().parent.parent.parent / ".runtime",
        )) / "audit" / "gcl-runner-ops",
        help="Directory containing gcl-trace-*.json files",
    )
    parser.add_argument("--skill", default=None, help="Filter by skill name")
    parser.add_argument("--operation", default=None, help="Filter by operation name (substring match in command)")
    parser.add_argument("--decision", default=None, help="Filter by decision/status (PASS, SAFETY_FAIL, MAX_ITER, etc.)")
    parser.add_argument("--session-id", default=None, help="Filter by correlation session_id")
    parser.add_argument("--user-id", default=None, help="Filter by correlation user_id")
    parser.add_argument("--grep", default=None, help="Full-text search in failure patterns and final output")
    parser.add_argument("--since", default=None, help="Time window: '24h', '7d', etc. (default: all)")
    parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    parser.add_argument("--json", action="store_true", help="Output as JSON (default: table)")

    args = parser.parse_args(argv)

    if not args.trace_dir.is_dir():
        _log(f"event=query result=error reason=dir_not_found path={args.trace_dir}")
        print(f"Error: trace dir not found: {args.trace_dir}", file=sys.stderr)
        return 1

    results = query_traces(
        trace_dir=args.trace_dir,
        skill=args.skill,
        operation=args.operation,
        decision=args.decision,
        session_id=args.session_id,
        user_id=args.user_id,
        grep=args.grep,
        since=args.since,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_table(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
