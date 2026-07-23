#!/usr/bin/env python3
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
import statistics
import subprocess
import sys
import textwrap
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


def parse_iso_timestamp(ts_str: str) -> datetime | None:
    """Parse ISO 8601 timestamp from trace filename or embedded timestamp."""
    # Try embedded timestamp in trace JSON first
    if ts_str and isinstance(ts_str, str):
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


def load_traces(trace_dir: Path, since_hours: int) -> list[dict[str, Any]]:
    """Load GCL trace JSON files from trace_dir, filtered by recency.

    Returns traces whose mtime is within ``since_hours`` of now.
    Damaged files are skipped with a warning.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours)
    traces: list[dict[str, Any]] = []

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


def extract_metrics(trace: dict[str, Any]) -> dict[str, Any] | None:
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
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate pass-rates by skill and by dimension.

    Returns dict shaped for CMS custom metric reporting.
    """
    # per-skill: {skill: {dim: {"pass": int, "total": int}}}
    skill_data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {d: {"pass": 0.0, "total": 0.0} for d in DIMENSIONS}
    )
    # overall totals (across all skills)
    overall: dict[str, dict[str, float]] = {
        d: {"pass": 0.0, "total": 0.0} for d in DIMENSIONS
    }
    by_decision: dict[str, int] = defaultdict(int)

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
            if score is None or not isinstance(score, int | float):
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
    report: dict[str, Any],
    region: str,
    dry_run: bool = False,
) -> int:
    """Push per-skill pass-rates as CMS custom metrics via ``aliyun cms PutCustomMetric``.

    Returns EXIT_CLEAN on success, EXIT_ERROR on failure.
    """
    # Build a list of MetricList items
    metrics: list[dict[str, Any]] = []
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
# Phase B3: Pass-rate anomaly detection from Layer-1 memory traces
# ---------------------------------------------------------------------------


def load_memory_entries(memory_root: Path, window_days: int = 90) -> list[dict[str, Any]]:
    """Load Layer-1 memory trace entries from ``.runtime/memory/`` JSONL files.

    Returns entries whose ``timestamp`` is within *window_days* of now.
    Damaged or unparseable files are skipped with a warning.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    entries: list[dict[str, Any]] = []

    if not memory_root.is_dir():
        print(f"[WARN] memory-root not found: {memory_root}")
        return entries

    for jsonl_path in sorted(memory_root.rglob("*.jsonl")):
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_str = entry.get("timestamp")
                    if ts_str:
                        ts = parse_iso_timestamp(ts_str)
                        if ts is None or ts < cutoff:
                            continue
                    entries.append(entry)
        except OSError as exc:
            print(f"[WARN] skipping {jsonl_path}: {exc}")
            continue

    return entries


def _iso_year_week(dt: datetime) -> str:
    """Return ISO year-week string, e.g. ``2026-W28``."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def compute_weekly_pass_rates(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Group memory entries by skill and ISO week, compute pass-rate per group.

    Returns ``{skill: {week_key: {"pass": int, "total": int, "rate": float}}}``.
    Entries without a parseable timestamp are skipped.
    """
    # skill -> week -> {pass, total}
    data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"pass": 0, "total": 0})
    )

    for entry in entries:
        skill: str = entry.get("skill", "unknown")
        rubric_pass: bool = bool(entry.get("rubric_pass", False))
        ts_str: str = entry.get("timestamp", "")
        ts = parse_iso_timestamp(ts_str)
        if ts is None:
            continue
        week = _iso_year_week(ts)
        data[skill][week]["total"] += 1
        if rubric_pass:
            data[skill][week]["pass"] += 1

    result: dict[str, dict[str, dict[str, float]]] = {}
    for skill, weeks in data.items():
        result[skill] = {}
        for week, counts in weeks.items():
            total = counts["total"]
            result[skill][week] = {
                "pass": counts["pass"],
                "total": total,
                "rate": round(counts["pass"] / total * 100, 2) if total > 0 else 0.0,
            }

    return result


def _week_date_range(week_key: str) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for an ISO week key like ``2026-W28``.

    Start = Monday 00:00:00 UTC, End = Sunday 23:59:59 UTC.
    """
    year_str, week_str = week_key.split("-W")
    year = int(year_str)
    week = int(week_str)
    jan4 = date(year, 1, 4)
    # Monday of ISO week 1
    start = jan4 - timedelta(days=jan4.isocalendar()[2] - 1)
    # Offset to the requested week
    start_of_week = start + timedelta(weeks=week - 1)
    end_of_week = start_of_week + timedelta(days=6)
    return (
        datetime.combine(start_of_week, datetime.min.time(), tzinfo=timezone.utc),
        datetime.combine(end_of_week, datetime.max.time(), tzinfo=timezone.utc),
    )


def _collect_affected_operations(
    entries: list[dict[str, Any]], skill: str, week_key: str
) -> list[str]:
    """Collect unique operation names for a (skill, week) group."""
    ops: set[str] = set()
    for entry in entries:
        if entry.get("skill") != skill:
            continue
        ts_str = entry.get("timestamp", "")
        ts = parse_iso_timestamp(ts_str)
        if ts is None:
            continue
        if _iso_year_week(ts) == week_key:
            op = entry.get("operation", "unknown")
            ops.add(op)
    return sorted(ops)


def detect_anomaly(
    memory_root: Path,
    output_dir: Path,
    window_days: int = 90,
    threshold_stddev: float = 3.0,
    threshold_relative: float = 0.5,
) -> list[dict[str, Any]]:
    """Detect pass-rate anomalies per skill from Layer-1 memory traces.

    Groups entries by skill and ISO week.  For each skill's most recent
    completed week, compares the observed pass-rate against the rolling
    baseline of all previous weeks.

    Anomaly triggers (first matching criterion wins):
    - **3sigma**: current rate < baseline mean - (threshold_stddev * stddev)
    - **Relative 50%%**: current rate < baseline mean * threshold_relative

    Args:
        memory_root: Path to the ``.runtime/memory/`` directory (or parent).
        output_dir: Directory for per-skill anomaly JSON reports.
        window_days: Maximum age of entries to consider (default 90).
        threshold_stddev: Sigma multiplier for the 3sigma test (default 3.0).
        threshold_relative: Relative decline factor (default 0.5 = 50%%).

    Returns:
        List of anomaly report dicts (one per anomalous skill).  Each report
        is also written to ``{output_dir}/{skill}-{timestamp}.json``.
    """
    output_dir = Path(output_dir)
    entries = load_memory_entries(memory_root, window_days)
    if not entries:
        print(f"[INFO] No memory entries found in {memory_root}")
        return []

    weekly = compute_weekly_pass_rates(entries)
    anomalies: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    ts_file = now.strftime("%Y%m%dT%H%M%S")

    for skill, weeks in weekly.items():
        sorted_weeks = sorted(weeks.keys())  # lexicographic sort matches ISO order
        if len(sorted_weeks) < 2:
            continue  # need at least 2 weeks for a baseline

        current_week = sorted_weeks[-1]
        current = weeks[current_week]
        current_rate: float = current["rate"]

        # Baseline = all completed weeks before the current one
        baseline_weeks = sorted_weeks[:-1]
        baseline_rates: list[float] = [weeks[w]["rate"] for w in baseline_weeks]

        if len(baseline_rates) < 2:
            continue  # need at least 2 baseline weeks for a meaningful stddev

        baseline_mean: float = statistics.mean(baseline_rates)
        baseline_stddev: float = statistics.pstdev(baseline_rates)

        # Check 3sigma trigger
        sigma_threshold = baseline_mean - threshold_stddev * baseline_stddev
        is_3sigma = baseline_stddev > 0 and current_rate < sigma_threshold

        # Check relative decline trigger
        relative_threshold = baseline_mean * threshold_relative
        is_relative = current_rate < relative_threshold

        if not is_3sigma and not is_relative:
            continue

        decline_type: str
        severity: str
        if is_3sigma:
            decline_type = "3sigma"
            severity = "HIGH"
        else:
            decline_type = "relative_50pct"
            severity = "MEDIUM"

        window_start, window_end = _week_date_range(current_week)
        affected_ops = _collect_affected_operations(entries, skill, current_week)

        report: dict[str, Any] = {
            "skill": skill,
            "current_week_pass_rate": current_rate,
            "baseline_pass_rate": round(baseline_mean, 2),
            "baseline_stddev": round(baseline_stddev, 4),
            "decline_type": decline_type,
            "severity": severity,
            "sample_size": current["total"],
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "affected_operations": affected_ops,
            "generated_at": now.isoformat(),
        }

        safe_skill = skill.replace("/", "_")
        out_path = output_dir / f"{safe_skill}-{ts_file}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[ANOMALY] {skill}: {decline_type} drop (rate={current_rate}, baseline={round(baseline_mean, 2)}), written to {out_path}")

        anomalies.append(report)

    if not anomalies:
        print("[INFO] No anomalies detected.")

    return anomalies


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_passrate_reporter.py",
        description=(
            "Phase 4: Aggregate GCL trace pass-rates and report to CMS"
            " custom metrics.  Phase B3: detect pass-rate anomalies from"
            " Layer-1 memory traces."
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

              # Detect anomaly (default 90d window)
              python3 scripts/gcl_passrate_reporter.py \\
                --detect-anomaly --memory-root .runtime/memory/ \\
                --output-dir .runtime/anomaly/

              # Detect anomaly, custom thresholds
              python3 scripts/gcl_passrate_reporter.py \\
                --detect-anomaly \\
                --anomaly-threshold-stddev 2.5 \\
                --anomaly-threshold-relative 0.4
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
    # ---- Phase B3 anomaly detection args ----
    p.add_argument(
        "--detect-anomaly", action="store_true",
        help="Run pass-rate anomaly detection from Layer-1 memory traces",
    )
    p.add_argument(
        "--memory-root", type=Path, default=None,
        help=(
            "Path to .runtime/memory/ for anomaly detection"
            " (default: <repo-root>/.runtime/memory/)"
        ),
    )
    p.add_argument(
        "--output-dir", type=Path, default=None,
        help="Directory for anomaly report JSON files (default: <repo-root>/.runtime/anomaly/)",
    )
    p.add_argument(
        "--anomaly-threshold-stddev", type=float, default=3.0,
        help="Sigma multiplier for 3sigma anomaly detection (default: 3.0)",
    )
    p.add_argument(
        "--anomaly-threshold-relative", type=float, default=0.5,
        help="Relative decline factor for 50%% anomaly detection (default: 0.5)",
    )
    return p


def parse_since(since_str: str) -> int:
    """Parse time-window string like '24h', '7d', '168h' into hours."""
    if since_str.endswith("h"):
        return int(since_str[:-1])
    if since_str.endswith("d"):
        return int(since_str[:-1]) * 24
    return 24


def _resolve_runtime_root() -> Path:
    """Resolve the repo root path for default runtime directories."""
    return Path(os.environ.get(
        "ALIYUN_SKILLS_RUNTIME_ROOT",
        Path(__file__).resolve().parent.parent.parent / ".runtime",
    ))


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # ---- Phase B3: anomaly detection mode ----
    if args.detect_anomaly:
        runtime_root = _resolve_runtime_root()
        memory_root: Path = args.memory_root or (runtime_root / "memory")
        output_dir: Path = args.output_dir or (runtime_root / "anomaly")

        anomalies = detect_anomaly(
            memory_root=memory_root,
            output_dir=output_dir,
            threshold_stddev=args.anomaly_threshold_stddev,
            threshold_relative=args.anomaly_threshold_relative,
        )

        if anomalies:
            print(
                f"[RESULT] Detected {len(anomalies)} anomalous skill(s):"
                f" {[a['skill'] for a in anomalies]}"
            )
        return EXIT_CLEAN

    # ---- Normal pass-rate reporting mode ----
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
