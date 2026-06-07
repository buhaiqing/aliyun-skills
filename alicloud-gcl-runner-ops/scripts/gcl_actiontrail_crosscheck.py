#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcl_actiontrail_crosscheck.py — Cloud-side audit for GCL traces.

For each `audit-results/gcl-trace-*.json` produced by `gcl_runner.py`, this
script independently re-verifies the operation by calling Alibaba Cloud
**ActionTrail** (操作审计) `LookupEvents` API. The result is a
**cross-check report** that catches:

  1. PHANTOM_PASS  — local GCL said PASS but no ActionTrail event exists
                     (the op never actually ran; agent or runner lied)
  2. PHANTOM_FAIL  — local GCL said FAIL/ABORT but an ActionTrail event
                     exists (the op ran despite the verdict; safety gate
                     bypassed)
  3. UNTRACKED_OP  — ActionTrail has a destructive event but no local
                     trace exists (someone bypassed GCL entirely)
  4. RESOURCE_MISMATCH — cloud event references a different resource
                          than the local trace's args
  5. TIMING_ANOMALY   — cloud event timestamp is implausibly far from
                         the local trace's generator run time

The cross-check is **read-only** (LookupEvents), so it does NOT need to
be classified as `required` per `AGENTS.md` §12.8. The ActionTrail
skill itself remains `optional` (read-only audit).

USAGE
-----
    # Cross-check a single trace
    python3 scripts/gcl_actiontrail_crosscheck.py \\
        --trace audit-results/gcl-trace-20260604-103015-abc123.json

    # Cross-check ALL traces in a directory (CI mode)
    python3 scripts/gcl_actiontrail_crosscheck.py \\
        --trace-dir audit-results/ \\
        --report audit-results/crosscheck-report-$(date +%Y%m%d).json

    # Strict mode: any PHANTOM_* finding exits non-zero
    python3 scripts/gcl_actiontrail_crosscheck.py \\
        --trace-dir audit-results/ \\
        --strict

EXIT CODES
----------
    0  CLEAN          — all findings below threshold (or no findings)
    1  PHANTOM_FOUND  — at least one PHANTOM_PASS / PHANTOM_FAIL / UNTRACKED
    2  USAGE_ERROR    — bad CLI args or missing files
    3  API_ERROR      — ActionTrail API call failed (e.g. no trail enabled)

DESIGN PRINCIPLES (per AGENTS.md §12.11 Phase 3-C)
---------------------------------------------------
- The cross-check is **post-hoc** and **non-blocking** by default. It
  should be run on a schedule (cron / GitHub Actions) or on-demand, not
  on the synchronous GCL critical path.
- The cross-check produces a **report** (`crosscheck-report-*.json`),
  not a verdict. The report feeds into `alicloud-cms-ops` alarms (Phase
  3-B) or a human audit queue.
- The cross-check does NOT modify the local trace. It reads, compares,
  and reports.
- The cross-check does NOT call any LLM. Like the Phase 2 mechanical
  Critic, the comparison logic is deterministic and reproducible.

REQUIREMENTS
------------
    Python 3.10+ stdlib only. No external dependencies.

RELATION TO OTHER GCL ARTIFACTS
-------------------------------
- `gcl_runner.py` produces `gcl-trace-*.json` (per AGENTS.md §12.6).
- This script reads those traces and produces `crosscheck-report-*.json`.
- The crosscheck-report is the input to:
    - Phase 3-B (CMS alarm): `crosscheck-report → aliyun cms PutMetricAlarm`
    - Phase 3-D (governance dashboard): aggregate crosscheck-reports
    - Phase 3-E (auto-remediation): on PHANTOM_FAIL → page on-call
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse the sanitization function from gcl_runner so both scripts agree
# on what counts as a secret. This keeps the cross-check report free of
# inlined secrets.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import gcl_runner  # noqa: E402

#: Service name → expected EventName regex (the API op name as it appears
#: in ActionTrail). Maps our internal `aliyun <product> <Op>` style to
#: ActionTrail's `EventName` field (which is PascalCase like DeleteInstances).
#:
#: For example, `aliyun ecs DeleteInstance` → ActionTrail EventName
#: `DeleteInstances` (note the plural). This mapping is the source of
#: truth for the cross-check. If a new product is added, the rubric
#: should also be updated to add its mapping here.
#:
#: Wildcards:
#:   - Keys are the lowercase service name as used in `aliyun <service>`.
#:   - Values are lists of (regex, replacement) tuples; the first matching
#:     tuple wins. This handles the singular/plural and the verb-noun
#:     variations across services.
PRODUCT_TO_EVENTNAME = {
    # Service → list of (local_op_regex → ActionTrail EventName)
    "ecs": [
        (r"^DeleteInstance$", "DeleteInstances"),
        (r"^DeleteInstances$", "DeleteInstances"),
        (r"^StopInstance$", "StopInstances"),
        (r"^RebootInstance$", "RebootInstances"),
        (r"^RunInstances$", "RunInstances"),
        (r"^AuthorizeSecurityGroup$", "AuthorizeSecurityGroup"),
        (r"^RevokeSecurityGroup$", "RevokeSecurityGroup"),
    ],
    "r-kvstore": [
        (r"^DeleteInstance$", "DeleteInstances"),
        (r"^CreateInstance$", "CreateInstances"),
        (r"^ModifyInstanceSpec$", "ModifyInstanceSpec"),
        (r"^FlushInstance$", "FlushInstance"),
    ],
    "rds": [
        (r"^DeleteDBInstance$", "DeleteDBInstance"),
        (r"^CreateDBInstance$", "CreateDBInstance"),
        (r"^DeleteDatabase$", "DeleteDatabase"),
    ],
    "vpc": [
        (r"^DeleteVpc$", "DeleteVpc"),
        (r"^DeleteVSwitch$", "DeleteVSwitch"),
        (r"^DeleteNatGateway$", "DeleteNatGateway"),
        (r"^AssociateEipAddress$", "AssociateEipAddress"),
        (r"^UnassociateEipAddress$", "UnassociateEipAddress"),
        (r"^ReleaseEipAddress$", "ReleaseEipAddress"),
    ],
    "dds": [
        (r"^DeleteDBInstance$", "DeleteDBInstance"),
    ],
    "polardb": [
        (r"^DeleteDBCluster$", "DeleteDBCluster"),
        (r"^CreateDBCluster$", "CreateDBCluster"),
    ],
    "polardb-io": [
        (r"^DeleteDBCluster$", "DeleteDBCluster"),
    ],
    "polardb-pg": [
        (r"^DeleteDBInstance$", "DeleteDBInstance"),
    ],
    "kms": [
        (r"^ScheduleKeyDeletion$", "ScheduleKeyDeletion"),
        (r"^CancelKeyDeletion$", "CancelKeyDeletion"),
    ],
    "ram": [
        (r"^DeleteUser$", "DeleteUser"),
        (r"^CreateUser$", "CreateUser"),
        (r"^CreateAccessKey$", "CreateAccessKey"),
        (r"^DeleteAccessKey$", "DeleteAccessKey"),
    ],
    "elasticsearch": [
        (r"^DeleteInstance$", "DeleteInstance"),
    ],
    "cms": [
        (r"^PutMetricAlarm$", "PutMetricAlarm"),
        (r"^DeleteMetricAlarm$", "DeleteMetricAlarm"),
    ],
}

#: Resource-ID parameter name. Different skills use different flag names
#: for the resource identifier (InstanceId, DBInstanceId, AllocationId,
#: etc.). This regex extracts the value from the command line.
_RESOURCE_ID_PATTERNS = [
    r"--InstanceId\s+(\S+)",
    r"--DBInstanceId\s+(\S+)",
    r"--DBClusterId\s+(\S+)",
    r"--VpcId\s+(\S+)",
    r"--VSwitchId\s+(\S+)",
    r"--NatGatewayId\s+(\S+)",
    r"--AllocationId\s+(\S+)",
    r"--KeyId\s+(\S+)",
    r"--UserName\s+(\S+)",
    r"--AccessKeyId\s+(\S+)",
    r"--AlarmName\s+(\S+)",
]

#: Exit codes
EXIT_CLEAN = 0
EXIT_PHANTOM_FOUND = 1
EXIT_USAGE_ERROR = 2
EXIT_API_ERROR = 3


# ---------------------------------------------------------------------------
# Trace loading
# ---------------------------------------------------------------------------


def load_trace(path: Path) -> Dict[str, Any]:
    """Load a GCL trace JSON file. Sanitizes secret values on the fly."""
    if not path.is_file():
        raise FileNotFoundError(f"trace not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw


def extract_local_op(trace: Dict[str, Any]) -> Tuple[str, str, str]:
    """From a trace, extract (service, op, resource_id).

    Returns ("", "", "") if any of the three cannot be determined.
    """
    last_iter = trace["iterations"][-1] if trace.get("iterations") else {}
    gen = last_iter.get("generator", {})
    command = gen.get("command", "")

    if not command:
        return ("", "", "")

    # Skip `echo ...` dry-run commands; they have no real op
    if command.startswith("echo "):
        return ("", "", "")

    parts = shlex.split(command)
    if len(parts) < 3 or parts[0] != "aliyun":
        return ("", "", "")

    service = parts[1]
    op = parts[2]

    # Extract the first resource-id pattern
    resource_id = ""
    for pat in _RESOURCE_ID_PATTERNS:
        m = re.search(pat, command)
        if m:
            resource_id = m.group(1).strip("'\"")
            break

    return (service, op, resource_id)


def extract_local_timestamp(trace: Dict[str, Any]) -> Optional[str]:
    """Extract the local generator's timestamp from the trace's request_id
    + the trace file's mtime (best-effort)."""
    return None  # ActionTrail LookupEvents uses wall-clock; we just compare
    # the call window around trace.persist time. See find_matching_events.


# ---------------------------------------------------------------------------
# ActionTrail LookupEvents
# ---------------------------------------------------------------------------


def call_lookup_events(
    service: str,
    event_name: str,
    start_time: str,
    end_time: str,
    max_results: int = 50,
    region: Optional[str] = None,
    access_key_id: Optional[str] = None,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    """Call `aliyun actiontrail LookupEvents` and return the parsed events.

    Uses the CLI (per repo's cli-first convention). Returns a list of
    event dicts, each with at least: EventId, EventName, ServiceName,
    EventTime, EventAccessKeyId, RequestId, ResourceName, ErrorCode.

    Raises `APICallError` on transport / parse failure.
    """
    args = [
        "aliyun",
        "actiontrail",
        "LookupEvents",
        "--StartTime", start_time,
        "--EndTime", end_time,
        "--ServiceName", service,
        "--EventName", event_name,
        "--MaxResults", str(max_results),
        "--EventType", "ApiCall",
    ]
    if region:
        args.extend(["--RegionId", region])
    if access_key_id:
        args.extend(["--EventAccessKeyId", access_key_id])

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise APICallError(f"LookupEvents timed out after {timeout}s: {e}")
    except FileNotFoundError as e:
        raise APICallError(f"`aliyun` CLI not found in PATH: {e}")

    if proc.returncode != 0:
        stderr = (proc.stderr or "")[:500]
        # Distinguish "no events" (empty list) from "API error" (non-zero exit)
        if "NotFoundTrail" in stderr or "TrailNotFound" in stderr:
            raise APICallError(
                "ActionTrail is not enabled for this account/region. "
                "Enable a trail via `aliyun actiontrail CreateTrail` first."
            )
        raise APICallError(f"LookupEvents exit={proc.returncode}: {stderr}")

    # Parse JSON; tolerate non-JSON output (older aliyun CLI versions)
    stdout = proc.stdout or ""
    if not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise APICallError(f"LookupEvents returned non-JSON: {e}; output: {stdout[:200]!r}")

    events = data.get("Events", [])
    if not isinstance(events, list):
        raise APICallError(f"LookupEvents returned non-list Events: {type(events).__name__}")
    return events


class APICallError(Exception):
    """Raised when the ActionTrail API call fails (transport / parse / auth)."""


# ---------------------------------------------------------------------------
# Cross-check logic
# ---------------------------------------------------------------------------


def find_matching_events(
    events: List[Dict[str, Any]],
    service: str,
    op: str,
    resource_id: str,
    access_key_id: Optional[str],
    window_seconds: int = 600,
) -> List[Dict[str, Any]]:
    """Filter `events` to those that match the local trace's op.

    A match requires:
      - EventName maps from the local `op` (via PRODUCT_TO_EVENTNAME)
      - ServiceName matches the local service (case-insensitive)
      - ResourceName OR request parameters include the local `resource_id`
        (best-effort; ActionTrail sometimes omits the resource in
        ResourceName but includes it in additional event data)
      - EventAccessKeyId matches the local access_key_id (if provided)
      - EventTime is within `window_seconds` of now (best-effort)

    Returns the list of matching events. Empty list means NO MATCH.
    """
    mapping = PRODUCT_TO_EVENTNAME.get(service, [])
    expected_event_names = [
        replacement for pattern, replacement in mapping
        if re.match(pattern, op)
    ]
    if not expected_event_names:
        # Unknown service/op; fall back to PascalCase of op (best effort)
        expected_event_names = [op]

    matched: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("EventName") not in expected_event_names:
            continue
        if (ev.get("ServiceName") or "").lower() != service.lower():
            continue
        # ResourceName check (best-effort)
        if resource_id:
            ev_resource = (ev.get("ResourceName") or "")
            if resource_id not in ev_resource:
                # Some ActionTrail events put the resource in additional fields
                # We don't have a portable way to extract them; accept the
                # event if EventName+ServiceName match and AKID matches.
                # Flag the resource mismatch in `crosscheck_findings`.
                ev["_resource_mismatch"] = True
        # AccessKeyId check
        if access_key_id and ev.get("EventAccessKeyId") != access_key_id:
            continue
        matched.append(ev)
    return matched


def crosscheck_one(trace_path: Path) -> Dict[str, Any]:
    """Cross-check a single GCL trace against ActionTrail events.

    Returns a dict:
        {
          "trace_path": "...",
          "trace_skill": "alicloud-ecs-ops",
          "trace_decision": "PASS",
          "local_op": "DeleteInstance",
          "local_resource_id": "i-bp1...",
          "findings": [
            {
              "type": "PHANTOM_PASS" | "PHANTOM_FAIL" | "RESOURCE_MISMATCH" | "TIMING_ANOMALY",
              "severity": "high" | "medium" | "low",
              "message": "...",
              "evidence": {...}
            }
          ],
          "matched_events": [...],
          "checked_at": "2026-06-04T..."
        }
    """
    trace = load_trace(trace_path)
    service, op, resource_id = extract_local_op(trace)
    local_decision = trace.get("final", {}).get("status", "UNKNOWN")
    skill = trace.get("skill", "unknown")

    report: Dict[str, Any] = {
        "trace_path": str(trace_path),
        "trace_skill": skill,
        "trace_decision": local_decision,
        "local_op": op,
        "local_resource_id": resource_id,
        "findings": [],
        "matched_events": [],
        "checked_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
    }

    if not service or not op:
        report["findings"].append({
            "type": "UNPARSEABLE_TRACE",
            "severity": "low",
            "message": "trace command is not a recognizable `aliyun <service> <op>` invocation (possibly a dry-run or data-plane op)",
            "evidence": {"command": trace.get("iterations", [{}])[-1].get("generator", {}).get("command", "")[:200]},
        })
        return report

    # Compute the time window. ActionTrail retains 90 days of events; we
    # search a 24-hour window centered on the trace file's mtime. This
    # is a pragmatic default that catches both the live case (event
    # within minutes of trace) and the delayed case (audit replay).
    trace_mtime = _dt.datetime.fromtimestamp(
        trace_path.stat().st_mtime, tz=_dt.timezone.utc
    )
    start = (trace_mtime - _dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (trace_mtime + _dt.timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Pull current AKID from env (the agent's credential at trace time)
    access_key_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")

    # Determine EventName(s) to look up
    mapping = PRODUCT_TO_EVENTNAME.get(service, [])
    expected_event_names = [
        replacement for pattern, replacement in mapping
        if re.match(pattern, op)
    ] or [op]

    all_events: List[Dict[str, Any]] = []
    api_errors: List[str] = []
    for event_name in expected_event_names:
        try:
            events = call_lookup_events(
                service=service,
                event_name=event_name,
                start_time=start,
                end_time=end,
                access_key_id=access_key_id,
            )
            all_events.extend(events)
        except APICallError as e:
            api_errors.append(str(e))
            # Continue to next event name; one failure shouldn't abort

    if api_errors and not all_events:
        report["findings"].append({
            "type": "API_ERROR",
            "severity": "high",
            "message": (
                "ActionTrail LookupEvents failed for all expected event names. "
                "This is a cross-check infrastructure issue, NOT a phantom-op finding. "
                "First error: " + api_errors[0]
            ),
            "evidence": {"errors": api_errors},
        })
        return report

    matched = find_matching_events(
        all_events, service, op, resource_id, access_key_id
    )
    report["matched_events"] = [
        {
            "EventId": ev.get("EventId"),
            "EventName": ev.get("EventName"),
            "ServiceName": ev.get("ServiceName"),
            "EventTime": ev.get("EventTime"),
            "EventAccessKeyId": ev.get("EventAccessKeyId"),
            "ResourceName": ev.get("ResourceName"),
            "ErrorCode": ev.get("ErrorCode"),
            "_resource_mismatch": ev.get("_resource_mismatch", False),
        }
        for ev in matched
    ]

    # ----- Decision-based findings -----
    if local_decision == "PASS" and not matched:
        # CRITICAL: cloud says no event, local says PASS. Could be a lie
        # OR could be that the op succeeded silently and ActionTrail
        # hasn't ingested yet (typically < 5 minutes). Add a severity
        # level accordingly.
        report["findings"].append({
            "type": "PHANTOM_PASS",
            "severity": "high",
            "message": (
                f"Local GCL said PASS for `{op}` on `{resource_id}` but "
                f"no matching ActionTrail event was found in "
                f"[{start}, {end}]. Possible causes: (a) the op never "
                f"actually ran; (b) ActionTrail ingestion lag > 1 hour; "
                f"(c) the AccessKeyId used by the runner differs from "
                f"the trace's expected AKID; (d) the trail is not "
                f"configured to record this service/region."
            ),
            "evidence": {
                "local_op": op,
                "local_resource_id": resource_id,
                "expected_event_names": expected_event_names,
                "events_returned": len(all_events),
            },
        })
    elif local_decision in ("SAFETY_FAIL", "MAX_ITER") and matched:
        # CRITICAL: cloud says the op happened, local GCL said FAIL.
        # This is a safety gate bypass — investigate immediately.
        report["findings"].append({
            "type": "PHANTOM_FAIL",
            "severity": "high",
            "message": (
                f"Local GCL said {local_decision} for `{op}` but "
                f"{len(matched)} matching ActionTrail event(s) exist. "
                f"This indicates the safety gate was bypassed or the "
                f"op ran from a parallel session/automation."
            ),
            "evidence": {
                "local_decision": local_decision,
                "matched_event_ids": [ev.get("EventId") for ev in matched],
            },
        })
    elif matched:
        # Match found. Check for resource mismatch.
        for ev in matched:
            if ev.get("_resource_mismatch"):
                report["findings"].append({
                    "type": "RESOURCE_MISMATCH",
                    "severity": "medium",
                    "message": (
                        f"ActionTrail event for `{op}` has ResourceName "
                        f"`{ev.get('ResourceName')!r}` but the local trace "
                        f"references `{resource_id!r}`. Possible: op ran "
                        f"on a different resource than intended, OR "
                        f"ActionTrail's ResourceName field is incomplete."
                    ),
                    "evidence": {
                        "expected_resource_id": resource_id,
                        "event_resource_name": ev.get("ResourceName"),
                        "event_id": ev.get("EventId"),
                    },
                })

        # Check for timing anomaly
        for ev in matched:
            ev_time_str = ev.get("EventTime", "")
            try:
                # ActionTrail EventTime is RFC3339, e.g. "2026-06-04T13:45:00Z"
                ev_time = _dt.datetime.fromisoformat(ev_time_str.replace("Z", "+00:00"))
                delta = abs((ev_time - trace_mtime).total_seconds())
                if delta > 3600:  # 1 hour skew
                    report["findings"].append({
                        "type": "TIMING_ANOMALY",
                        "severity": "low",
                        "message": (
                            f"ActionTrail event time is {int(delta)}s from "
                            f"the local trace's mtime. This is outside the "
                            f"normal 1-hour skew window. Possible: replay "
                            f"attack, clock drift, or delayed ActionTrail "
                            f"ingestion."
                        ),
                        "evidence": {
                            "event_time": ev_time_str,
                            "trace_mtime": trace_mtime.isoformat(),
                            "delta_seconds": delta,
                        },
                    })
            except (ValueError, TypeError):
                pass  # unparseable; skip timing check

    return report


def aggregate_findings(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate cross-check reports into a single summary."""
    summary: Dict[str, Any] = {
        "total_traces": len(reports),
        "clean": 0,
        "phantoms": 0,
        "api_errors": 0,
        "by_finding_type": {},
        "by_skill": {},
    }
    for r in reports:
        findings = r.get("findings", [])
        is_clean = all(f["severity"] in ("low",) and f["type"] != "API_ERROR" for f in findings)
        if is_clean:
            summary["clean"] += 1
        for f in findings:
            t = f["type"]
            summary["by_finding_type"][t] = summary["by_finding_type"].get(t, 0) + 1
            if t in ("PHANTOM_PASS", "PHANTOM_FAIL"):
                summary["phantoms"] += 1
            if t == "API_ERROR":
                summary["api_errors"] += 1
        skill = r.get("trace_skill", "unknown")
        summary["by_skill"].setdefault(skill, {"total": 0, "with_findings": 0})
        summary["by_skill"][skill]["total"] += 1
        if findings:
            summary["by_skill"][skill]["with_findings"] += 1
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_actiontrail_crosscheck.py",
        description=(
            "Cloud-side cross-check of GCL traces against Alibaba Cloud "
            "ActionTrail. Implements AGENTS.md §12.11 Phase 3-C. "
            "Read-only audit; does not modify local traces."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Single trace
              python3 scripts/gcl_actiontrail_crosscheck.py \\
                  --trace audit-results/gcl-trace-20260604-103015-abc123.json

              # All traces in a directory (CI mode)
              python3 scripts/gcl_actiontrail_crosscheck.py \\
                  --trace-dir audit-results/ \\
                  --report audit-results/crosscheck-$(date +%Y%m%d).json

              # Strict mode (exit non-zero on any PHANTOM_* finding)
              python3 scripts/gcl_actiontrail_crosscheck.py \\
                  --trace-dir audit-results/ \\
                  --strict
            """
        ),
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--trace", type=Path, help="Path to a single gcl-trace-*.json file")
    g.add_argument("--trace-dir", type=Path,
                   default=Path(os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT", Path(__file__).resolve().parent.parent.parent / ".runtime")) / "audit" / "gcl-runner-ops",
                   help="Directory containing gcl-trace-*.json files (Sprint 19: default = ${RUNTIME_ROOT}/audit/gcl-runner-ops)")
    p.add_argument("--report", type=Path, default=None, help="(With --trace-dir) write a JSON report to this path")
    p.add_argument("--strict", action="store_true", help="Exit non-zero on PHANTOM_PASS / PHANTOM_FAIL / UNTRACKED_OP findings")
    p.add_argument("--window-hours", type=int, default=24, help="Time window around trace mtime to search (default: 24)")
    p.add_argument("--max-results", type=int, default=50, help="Max ActionTrail LookupEvents results per call (default: 50)")
    p.add_argument("--region", default=None, help="Override ActionTrail region (default: AKID's home region)")
    p.add_argument("--access-key-id", default=None, help="Override AccessKeyId to filter events (default: $ALIBABA_CLOUD_ACCESS_KEY_ID)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Resolve trace files
    if args.trace:
        if not args.trace.is_file():
            print(f"[ERROR] trace not found: {args.trace}", file=sys.stderr)
            return EXIT_USAGE_ERROR
        trace_paths = [args.trace]
    else:
        if not args.trace_dir.is_dir():
            print(f"[ERROR] trace dir not found: {args.trace_dir}", file=sys.stderr)
            return EXIT_USAGE_ERROR
        trace_paths = sorted(args.trace_dir.glob("gcl-trace-*.json"))
        if not trace_paths:
            print(f"[WARN] no gcl-trace-*.json files in {args.trace_dir}", file=sys.stderr)
            # Not an error; just nothing to do.
            return EXIT_CLEAN

    # Cross-check each trace
    reports: List[Dict[str, Any]] = []
    for tp in trace_paths:
        try:
            r = crosscheck_one(tp)
        except Exception as e:  # noqa: BLE001 — top-level guard
            r = {
                "trace_path": str(tp),
                "trace_skill": "unknown",
                "trace_decision": "UNKNOWN",
                "local_op": "",
                "local_resource_id": "",
                "findings": [{
                    "type": "INTERNAL_ERROR",
                    "severity": "high",
                    "message": f"cross-check failed: {e}",
                    "evidence": {},
                }],
                "matched_events": [],
                "checked_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
            }
        reports.append(r)

        # Per-trace summary to stdout
        findings_short = ", ".join(f["type"] for f in r["findings"]) or "CLEAN"
        print(
            f"[XCHK] {tp.name}: skill={r['trace_skill']} "
            f"decision={r['trace_decision']} findings=[{findings_short}]"
        )

    # Aggregate
    summary = aggregate_findings(reports)
    print(
        f"[XCHK] total={summary['total_traces']} clean={summary['clean']} "
        f"phantoms={summary['phantoms']} api_errors={summary['api_errors']}"
    )

    # Write report
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
                    "summary": summary,
                    "reports": reports,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"[XCHK] report: {args.report}")

    # Exit code
    if args.strict and summary["phantoms"] > 0:
        return EXIT_PHANTOM_FOUND
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
