#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcl_passrate_reporter.py — Phase 4: Aggregate GCL trace pass-rates and
report to CloudMonitor (CMS) custom metrics.

Scans `audit-results/gcl-trace-*.json` files within a time window,
calculates per-skill and per-dimension pass-rates, and pushes them as
CMS custom metrics via `aliyun cms PutCustomMetric`.

Idempotent: repeated runs with the same time window produce the same
output.

USAGE
-----
    # Report last 24h pass-rates to CMS
    python3 scripts/gcl_passrate_reporter.py \
      --trace-dir audit-results/ \
      --region cn-hangzhou

    # Report last 7d; dry-run
    python3 scripts/gcl_passrate_reporter.py \
      --trace-dir audit-results/ \
      --since 7d \
      --dry-run

EXIT CODES
----------
    0  CLEAN      — all metrics reported successfully (or dry-run)
    1  WARN       — some traces had missing/damaged fields
    2  ERROR      — API call failed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


#: Rubric dimension names (the 5 core + 3 Aliyun extensions from AGENTS.md §12.3)
DIMENSIONS = (
    "correctness",
    "safety",
    "idempotency",
    "traceability",
    "spec_compliance",
    "region_compliance",
    "credential_hygiene",
    "well_architected",
)

#: Decision values we count as "PASS" for pass-rate calculation
PASS_DECISIONS = ("PASS",)

#: The GCL namespace for custom metrics in CMS
METRIC_NAMESPACE = "acs_custom_gcl"

EXIT_CLEAN = 0
EXIT_WARN = 1
EXIT_ERROR = 2


# ---------------------------------------------------------------------------
# Trace loading & parsing
# ---------------------------------------------------------------------------


def parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp from trace filename or embedded timestamp."""
    # Try embedded timestamp in trace JSON first
    if ts_str and isinstance(ts_str, str):
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


def load_traces(trace_dir: Path, since_hours: int) -> List[Dict[str, Any]]:
    """Load GCL trace JSON files from trace_dir, filtered by recency.

    Returns traces whose mtime is within ``since_hours`` of now.
    Damaged files are skipped with a warning.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours)
    traces: List[Dict[str, Any]] = []

    if not trace_dir.is_dir():
        print(f"[WARN] trace-dir not found: {trace_dir}")
        return traces

    for fpath in sorted(trace_dir.glob("gcl-trace-*.json")):
        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            continue
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[WARN] skipping damaged trace {fpath.name}: {exc}")
            continue
        traces.append(data)

    return traces


def extract_metrics(trace: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract skill name, decision, and dimension scores from a single trace.

    Returns a dict with keys: skill, decision, scores (dict of dim→float),
    or None if the trace is unusable.
    """
    # Determine skill name — try skill_md field, then iter 0 generator skill
    skill = (
        trace.get("skill_md")
        or trace.get("skill")
        or trace.get("metadata", {}).get("skill")
        or "unknown"
    )
    # Normalise: strip path prefix, keep the alicloud-xxx-ops name
    m = re.search(r"(alicloud-\w+-ops)", skill)
    if m:
        skill = m.group(1)

    # Take the LAST iteration's critic scores (most recent)
    iterations = trace.get("iterations") or trace.get("loop", [])
    if not iterations or not isinstance(iterations, list):
        # Single-iter trace structure: direct critic.scores
        critic = trace.get("critic", {})
        scores = critic.get("scores", {})
        decision = trace.get("decision", "UNKNOWN")
        return {"skill": skill, "decision": decision, "scores": scores}

    last_iter = iterations[-1]
    critic = last_iter.get("critic", {})
    scores = critic.get("scores", {})
    decision = last_iter.get("decision") or trace.get("decision", "UNKNOWN")
    return {"skill": skill, "decision": decision, "scores": scores}


# ---------------------------------------------------------------------------
# Pass-rate aggregation
# ---------------------------------------------------------------------------


def compute_pass_rates(
    traces: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate pass-rates by skill and by dimension.

    Returns dict shaped for CMS custom metric reporting.
    """
    # per-skill: {skill: {dim: {"pass": int, "total": int}}}
    skill_data: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: {d: {"pass": 0.0, "total": 0.0} for d in DIMENSIONS}
    )
    # overall totals (across all skills)
    overall: Dict[str, Dict[str, float]] = {
        d: {"pass": 0.0, "total": 0.0} for d in DIMENSIONS
    }
    by_decision: Dict[str, int] = defaultdict(int)

    total_traces = 0
    skipped_traces = 0

    for trace in traces:
        metrics = extract_metrics(trace)
        if metrics is None:
            skipped_traces += 1
            continue

        skill = metrics["skill"]
        decision = metrics["decision"]
        scores = metrics["scores"]
        total_traces += 1
        by_decision[decision] += 1

        for dim in DIMENSIONS:
            score = scores.get(dim)
            if score is None or not isinstance(score, (int, float)):
                continue
            # A score >= 0.5 counts as a "pass" for this dimension
            passed = 1.0 if score >= 0.5 else 0.0
            skill_data[skill][dim]["pass"] += passed
            skill_data[skill][dim]["total"] += 1.0
            overall[dim]["pass"] += passed
            overall[dim]["total"] += 1.0

    # Compute rates
    def _rate(ps: float, tl: float) -> float:
        return round(ps / tl * 100, 2) if tl > 0 else 0.0

    skills_report = {}
    for skill, dims in sorted(skill_data.items()):
        skills_report[skill] = {
            dim: {
                "pass": int(dims[dim]["pass"]),
                "total": int(dims[dim]["total"]),
                "rate": _rate(dims[dim]["pass"], dims[dim]["total"]),
            }
            for dim in DIMENSIONS
        }

    overall_report = {
        dim: {
            "pass": int(overall[dim]["pass"]),
            "total": int(overall[dim]["total"]),
            "rate": _rate(overall[dim]["pass"], overall[dim]["total"]),
        }
        for dim in DIMENSIONS
    }

    return {
        "window_hours": None,  # filled by caller
        "total_traces": total_traces,
        "skipped_traces": skipped_traces,
        "by_decision": dict(by_decision),
        "overall": overall_report,
        "by_skill": skills_report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# CMS custom metric reporting
# ---------------------------------------------------------------------------


def push_custom_metrics(
    report: Dict[str, Any],
    region: str,
    dry_run: bool = False,
) -> int:
    """Push per-skill pass-rates as CMS custom metrics via ``aliyun cms PutCustomMetric``.

    Returns EXIT_CLEAN on success, EXIT_ERROR on failure.
    """
    # Build a list of MetricList items
    metrics: List[Dict[str, Any]] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Dimension: d — each dimension sends one metric per skill
    for skill, dims in report.get("by_skill", {}).items():
        for dim, data in dims.items():
            metrics.append({
                "MetricName": f"gcl_pass_rate_{dim}",
                "Dimensions": json.dumps([{"skill": skill}]),
                "Value": data["rate"],
                "Type": 1,  # 1 = Average
                "Time": ts,
            })
        # Also send a composite safety-OK rate
        safety_total = dims.get("safety", {}).get("total", 0)
        safety_pass = dims.get("safety", {}).get("pass", 0)
        metrics.append({
            "MetricName": "gcl_safety_ok",
            "Dimensions": json.dumps([{"skill": skill}]),
            "Value": round(
                (safety_pass / safety_total * 100) if safety_total > 0 else 100.0,
                2,
            ),
            "Type": 1,
            "Time": ts,
        })

    # Global / overall metrics (no skill dimension)
    overall = report.get("overall", {})
    for dim, data in overall.items():
        metrics.append({
            "MetricName": f"gcl_global_pass_rate_{dim}",
            "Dimensions": "[]",
            "Value": data["rate"],
            "Type": 1,
            "Time": ts,
        })

    # Decision distribution
    by_dec = report.get("by_decision", {})
    total = sum(by_dec.values()) or 1
    for decision, count in by_dec.items():
        metrics.append({
            "MetricName": f"gcl_decision_{decision.lower()}",
            "Dimensions": "[]",
            "Value": round(count / total * 100, 2),
            "Type": 1,
            "Time": ts,
        })
    # SAFETY_FAIL abs count
    metrics.append({
        "MetricName": "gcl_safety_fail_count",
        "Dimensions": "[]",
        "Value": by_dec.get("ABORT_SAFETY", 0),
        "Type": 1,
        "Time": ts,
    })

    if dry_run:
        print("[DRY-RUN] Would push these custom metrics:")
        for m in metrics:
            print(
                f"  {m['MetricName']} dims={m['Dimensions']}"
                f" value={m['Value']}"
            )
        print(f"  Total metrics: {len(metrics)}")
        return EXIT_CLEAN

    # Batch metrics — CMS supports up to 100 per call
    batch_size = 100
    global_exit = EXIT_CLEAN

    for i in range(0, len(metrics), batch_size):
        batch = metrics[i : i + batch_size]
        payload = json.dumps({"MetricList": batch})
        proc = subprocess.run(
            [
                "aliyun", "cms", "PutCustomMetric",
                "--RegionId", region,
                "--MetricList", payload,
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if proc.returncode != 0:
            print(
                f"[ERROR] PutCustomMetric batch {i // batch_size}"
                f" failed: {proc.stderr[:300]}"
            )
            global_exit = EXIT_ERROR
        else:
            resp = json.loads(proc.stdout or "{}")
            if resp.get("Code") != "200":
                print(
                    f"[ERROR] PutCustomMetric batch {i // batch_size}"
                    f" API error: {resp.get('Message', 'unknown')}"
                )
                global_exit = EXIT_ERROR

    print(
        f"[RESULT] Pushed {len(metrics)} custom metrics"
        f" ({report['total_traces']} traces,"
        f" {report['skipped_traces']} skipped)"
    )
    return global_exit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_passrate_reporter.py",
        description=(
            "Phase 4: Aggregate GCL trace pass-rates and report to CMS"
            " custom metrics."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Report last 24h
              python3 scripts/gcl_passrate_reporter.py \\
                --trace-dir audit-results/

              # Last 7d, dry-run
              python3 scripts/gcl_passrate_reporter.py \\
                --trace-dir audit-results/ --since 7d --dry-run

              # Custom output (save JSON report)
              python3 scripts/gcl_passrate_reporter.py \\
                --trace-dir audit-results/ --output passrate-report.json
            """
        ),
    )
    p.add_argument(
        "--trace-dir", type=Path,
        default=Path(os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT", Path(__file__).resolve().parent.parent.parent / ".runtime")) / "audit" / "gcl-runner-ops",
        help="Directory with gcl-trace-*.json files (Sprint 19: default = ${RUNTIME_ROOT}/audit/gcl-runner-ops)",
    )
    p.add_argument(
        "--since", default="24h",
        help='Time window: "24h" (default), "7d", "168h", etc.',
    )
    p.add_argument(
        "--region", default="cn-hangzhou",
        help="Region for CMS custom metrics (default: cn-hangzhou)",
    )
    p.add_argument(
        "--output", default=None,
        help="Optional path to write the JSON pass-rate report",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show intended metrics without calling CMS API",
    )
    return p


def parse_since(since_str: str) -> int:
    """Parse time-window string like '24h', '7d', '168h' into hours."""
    if since_str.endswith("h"):
        return int(since_str[:-1])
    if since_str.endswith("d"):
        return int(since_str[:-1]) * 24
    return 24


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    since_hours = parse_since(args.since)

    traces = load_traces(args.trace_dir, since_hours)
    if not traces:
        print(f"[INFO] No GCL traces found in {args.trace_dir} for the last {since_hours}h")
        return EXIT_CLEAN

    report = compute_pass_rates(traces)
    report["window_hours"] = since_hours
    report["trace_dir"] = str(args.trace_dir)

    print(
        f"[INFO] Loaded {len(traces)} traces, {report['skipped_traces']} skipped,"
        f" {report['total_traces']} usable."
    )
    print(f"[INFO] By decision: {report['by_decision']}")

    # Save report locally if --output requested
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[RESULT] Report saved to {out_path}")

    # Push to CMS
    exit_code = push_custom_metrics(report, args.region, dry_run=args.dry_run)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())