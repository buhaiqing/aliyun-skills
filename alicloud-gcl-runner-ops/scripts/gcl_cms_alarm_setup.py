#!/usr/bin/env python3
"""
gcl_cms_alarm_setup.py — Phase 3-B + Phase 4: Create / update CMS alarm rules for
GCL phantom-op findings AND real pass-rate metrics.

Idempotent: creates alarms only if they don't exist, updates only if
threshold changes, deletes if the issue is resolved. Run after
`gcl_actiontrail_crosscheck.py` in the same cron pipeline.

USAGE
-----
    python3 scripts/gcl_cms_alarm_setup.py \
      --report-dir audit-results/ \
      --contact-group gcl-oncall \
      --region cn-hangzhou

    # Dry-run mode (print intended actions without calling PutMetricAlarm)
    python3 scripts/gcl_cms_alarm_setup.py \
      --report-dir audit-results/ \
      --dry-run

EXIT CODES
----------
    0  CLEAN          — all alarms in desired state (no action needed)
    1  CREATED        — at least one alarm was created
    2  UPDATED        — at least one alarm threshold was updated
    3  DELETED        — at least one resolved alarm was deleted
    4  ERROR          — API call failed
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

#: Alarm definitions (alarm name → config)
#: These MUST match the rubric §2.2 alarm thresholds.
ALARMS: list[dict[str, Any]] = [
    {
        "name": "GCL-Phantom-Pass",
        "json_path": ("summary", "by_finding_type", "PHANTOM_PASS"),
        "threshold": 0,  # > 0 (any finding)
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P1",
    },
    {
        "name": "GCL-Phantom-Fail",
        "json_path": ("summary", "by_finding_type", "PHANTOM_FAIL"),
        "threshold": 0,  # > 0 (any finding)
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P1",
    },
    {
        "name": "GCL-Resource-Mismatch",
        "json_path": ("summary", "by_finding_type", "RESOURCE_MISMATCH"),
        "threshold": 0,  # > 0 (any mismatch)
        "comparison_operator": ">",
        "evaluation_count": 2,
        "severity": "P2",
    },
    {
        "name": "GCL-Api-Errors",
        "json_path": ("summary", "api_errors"),
        "threshold": 5,  # > 5
        "comparison_operator": ">",
        "evaluation_count": 3,
        "severity": "P3",
    },
    {
        "name": "GCL-Timing-Anomaly",
        "json_path": ("summary", "by_finding_type", "TIMING_ANOMALY"),
        "threshold": 10,  # > 10
        "comparison_operator": ">",
        "evaluation_count": 3,
        "severity": "P4",
    },
    # ── Phase 4: Real pass-rate alarms ──────────────────────────────────────
    {
        "name": "GCL-Safety-Fail-Rate",
        "json_path_metric": "gcl_safety_fail_count",
        "namespace": "acs_custom_gcl",
        "threshold": 1,  # > 1 SAFETY_FAIL in window
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P1",
    },
    {
        "name": "GCL-Correctness-Drop",
        "json_path_metric": "gcl_global_pass_rate_correctness",
        "namespace": "acs_custom_gcl",
        "threshold": 90,  # < 90% (operator: "<")
        "comparison_operator": "<",
        "evaluation_count": 2,
        "severity": "P2",
    },
    {
        "name": "GCL-Traceability-Gap",
        "json_path_metric": "gcl_global_pass_rate_traceability",
        "namespace": "acs_custom_gcl",
        "threshold": 80,  # < 80% (operator: "<")
        "comparison_operator": "<",
        "evaluation_count": 2,
        "severity": "P3",
    },
]

EXIT_CLEAN = 0
EXIT_CREATED = 1
EXIT_UPDATED = 2
EXIT_DELETED = 3
EXIT_ERROR = 4


# ---------------------------------------------------------------------------
# Report parsing
# ---------------------------------------------------------------------------


def load_latest_report(report_dir: Path) -> dict[str, Any] | None:
    """Find the most recent crosscheck-report-*.json and parse it."""
    if not report_dir.is_dir():
        return None
    files = sorted(report_dir.glob("crosscheck-report-*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def extract_metric_value(report: dict[str, Any], json_path: tuple[str, ...]) -> int:
    """Traverse the report dict along json_path and return the value (or 0).

    Used by Phase 3-B phantom alarms to extract finding counts from
    crosscheck reports.
    """
    current: Any = report
    for key in json_path:
        if isinstance(current, dict):
            current = current.get(key, 0)
        else:
            return 0
    return int(current) if isinstance(current, int | float) else 0


def is_passrate_alarm(alarm: dict[str, Any]) -> bool:
    """Return True if this is a Phase 4 pass-rate alarm (metric-based)."""
    return "json_path_metric" in alarm


# ---------------------------------------------------------------------------
# CMS API calls
# ---------------------------------------------------------------------------


def call_describe_alarm_list(name: str, region: str) -> list[dict[str, Any]]:
    """Call `aliyun cms DescribeMetricAlarmList` for a specific alarm name."""
    proc = subprocess.run(
        [
            "aliyun", "cms", "DescribeMetricAlarmList",
            "--AlarmName", name,
            "--RegionId", region,
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout or "{}")
        return data.get("AlarmList", [])
    except (json.JSONDecodeError, TypeError):
        return []


def call_put_metric_alarm(config: dict[str, Any], region: str) -> int:
    """Call `aliyun cms PutMetricAlarm` with the given config.

    Supports two alarm types:
    - Phantom alarms (Phase 3-B): use ``json_path`` to fetch value from crosscheck report
    - Pass-rate alarms (Phase 4): use ``json_path_metric`` + ``namespace`` for custom metrics

    Returns exit code.
    """
    namespace = config.get("namespace", "acs_custom")
    metric_name = config.get("json_path_metric") or config["name"].lower().replace("-", "_")
    statistics = "Average" if config.get("json_path_metric") else "Average"

    args = [
        "aliyun", "cms", "PutMetricAlarm",
        "--RegionId", region,
        "--AlarmName", config["name"],
        "--MetricName", metric_name,
        "--Namespace", namespace,
        "--Statistics", statistics,
        "--ComparisonOperator", config["comparison_operator"],
        "--Threshold", str(config["threshold"]),
        "--Period", "300",
        "--EvaluationCount", str(config["evaluation_count"]),
        "--ContactGroups", json.dumps([config["contact_group"]]),
        "--EffectiveInterval", "00:00-23:59",
    ]
    if config.get("webhook"):
        args.extend(["--Webhook", config["webhook"]])

    proc = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0:
        print(f"[ERROR] PutMetricAlarm failed for {config['name']}: {proc.stderr[:200]}")
    return proc.returncode


def call_delete_metric_alarm(name: str, region: str) -> int:
    """Call `aliyun cms DeleteMetricAlarm`."""
    proc = subprocess.run(
        [
            "aliyun", "cms", "DeleteMetricAlarm",
            "--AlarmName", name,
            "--RegionId", region,
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return proc.returncode


# ---------------------------------------------------------------------------
# Main reconciliation logic
# ---------------------------------------------------------------------------


def reconcile(
    report: dict[str, Any],
    contact_group: str,
    region: str,
    webhook: str | None = None,
    dry_run: bool = False,
) -> int:
    """Reconcile the desired alarm state against existing CMS alarms.

    Returns one of EXIT_CLEAN / EXIT_CREATED / EXIT_UPDATED / EXIT_DELETED / EXIT_ERROR.
    """
    global_exit = EXIT_CLEAN

    for alarm in ALARMS:
        name = alarm["name"]
        is_pr = is_passrate_alarm(alarm)

        if is_pr:
            # Phase 4 pass-rate alarm: always desired (CMS evaluates metric stream)
            value = 0
            should_exist = True
        else:
            # Phase 3-B phantom alarm: create only if finding count exceeds threshold
            value = extract_metric_value(report, alarm["json_path"])
            should_exist = value > alarm["threshold"]

        # Check current state in CMS
        existing = call_describe_alarm_list(name, region)
        exists = len(existing) > 0

        action = None  # None, "create", "update", "delete"

        if should_exist and not exists:
            action = "create"
        elif should_exist and exists:
            # Check if threshold changed (update)
            current_alarm = existing[0]
            current_threshold = float(current_alarm.get("Threshold", -1))
            if current_threshold != alarm["threshold"]:
                action = "update"
        elif not should_exist and exists:
            action = "delete"

        if action is None:
            continue

        if dry_run:
            print(f"[DRY-RUN] {name}: action={action} value={value} threshold={alarm['threshold']}")
            if action in ("create", "update"):
                print(f"  PutMetricAlarm: threshold={alarm['threshold']} operator={alarm['comparison_operator']}")
            elif action == "delete":
                print(f"  DeleteMetricAlarm: {name}")
            continue

        # Execute
        alarm_config = dict(alarm)
        alarm_config["contact_group"] = contact_group
        alarm_config["webhook"] = webhook

        if action == "create":
            ec = call_put_metric_alarm(alarm_config, region)
            if ec == 0:
                print(f"[CREATED] {name}: threshold={alarm['threshold']} value={value}")
                global_exit = max(global_exit, EXIT_CREATED)
            else:
                print(f"[ERROR] {name}: PutMetricAlarm exit={ec}")
                global_exit = max(global_exit, EXIT_ERROR)
        elif action == "update":
            ec = call_put_metric_alarm(alarm_config, region)
            if ec == 0:
                print(f"[UPDATED] {name}: threshold={alarm['threshold']} value={value}")
                global_exit = max(global_exit, EXIT_UPDATED)
            else:
                print(f"[ERROR] {name}: PutMetricAlarm update exit={ec}")
                global_exit = max(global_exit, EXIT_ERROR)
        elif action == "delete":
            ec = call_delete_metric_alarm(name, region)
            if ec == 0:
                print(f"[DELETED] {name}: threshold={alarm['threshold']} value={value} — issue resolved")
                global_exit = max(global_exit, EXIT_DELETED)
            else:
                print(f"[ERROR] {name}: DeleteMetricAlarm exit={ec}")
                global_exit = max(global_exit, EXIT_ERROR)

    return global_exit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_cms_alarm_setup.py",
        description=(
            "Phase 3-B: Create / update CMS alarm rules for GCL phantom-op "
            "findings. Reads crosscheck-report-*.json; idempotent."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Normal run (creates/updates/deletes alarms)
              python3 scripts/gcl_cms_alarm_setup.py \\
                --report-dir audit-results/ \\
                --contact-group gcl-oncall

              # Dry-run (show intended actions)
              python3 scripts/gcl_cms_alarm_setup.py \\
                --report-dir audit-results/ \\
                --dry-run
            """
        ),
    )
    p.add_argument("--report-dir", type=Path,
                   default=Path(os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT", Path(__file__).resolve().parent.parent.parent / ".runtime")) / "audit" / "gcl-runner-ops",
                   help="Directory with crosscheck-report-*.json files (Sprint 19: default = ${RUNTIME_ROOT}/audit/gcl-runner-ops)")
    p.add_argument("--contact-group", default="gcl-oncall", help="CMS contact group for alarm notifications (default: gcl-oncall)")
    p.add_argument("--region", default="cn-hangzhou", help="Alarm region (default: cn-hangzhou)")
    p.add_argument("--webhook", default=None, help="Webhook URL for alarm (PagerDuty / Slack)")
    p.add_argument("--dry-run", action="store_true", help="Show intended actions without calling CMS API")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    report = load_latest_report(args.report_dir)
    if report is None:
        print(f"[INFO] no crosscheck-report-*.json found in {args.report_dir}")
        return EXIT_CLEAN

    return reconcile(
        report=report,
        contact_group=args.contact_group,
        region=args.region,
        webhook=args.webhook,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
