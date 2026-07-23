#!/usr/bin/env python3
"""
gcl_smart_alarm_cms_setup.py — Phase 7: Smart Alert Loop CMS alarm setup

Creates CMS alarm rules for the smart alarm engine's pattern detection output.
Unlike traditional threshold-based alarms (Phase 3-B/4), these alarms monitor
for pattern-based risk indicators from gcl_smart_alarm_engine.py.

This is a companion to gcl_cms_alarm_setup.py — while that script handles
phantom-op and pass-rate alarms, this script handles smart pattern alarms.

USAGE
-----
    # Create/update smart pattern alarms
    python3 gcl_smart_alarm_cms_setup.py \
      --contact-group gcl-oncall \
      --region cn-hangzhou

    # Dry-run mode
    python3 gcl_smart_alarm_cms_setup.py --dry-run

EXIT CODES
----------
    0  CLEAN     — all alarms in desired state
    1  CREATED   — at least one alarm created
    2  UPDATED   — at least one alarm updated
    3  DELETED   — at least one alarm deleted
    4  ERROR     — API call failed
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from typing import Any

#: Smart pattern alarm definitions
#: These alarms monitor custom metrics pushed by gcl_smart_alarm_engine.py
SMART_ALARMS: list[dict[str, Any]] = [
    {
        "name": "GCL-Smart-Resource-Degraded",
        "metric_name": "gcl_smart_resource_degraded_count",
        "namespace": "acs_custom_gcl",
        "description": "Resources automatically downgraded due to repeated Safety/Hallucination failures",
        "threshold": 0,
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P1",
        "period": 300,  # 5 minutes
    },
    {
        "name": "GCL-Smart-Region-Hotspot",
        "metric_name": "gcl_smart_region_hotspot_count",
        "namespace": "acs_custom_gcl",
        "description": "Region-level failure burst detected (possible regional outage)",
        "threshold": 0,
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P0",
        "period": 60,  # 1 minute for fast region-level detection
    },
    {
        "name": "GCL-Smart-Skill-Wide-Failure",
        "metric_name": "gcl_smart_skill_failure_count",
        "namespace": "acs_custom_gcl",
        "description": "Skill-wide failure pattern detected (possible API change or skill bug)",
        "threshold": 0,
        "comparison_operator": ">",
        "evaluation_count": 1,
        "severity": "P0",
        "period": 300,
    },
    {
        "name": "GCL-Smart-Pattern-Detected",
        "metric_name": "gcl_smart_pattern_detected_count",
        "namespace": "acs_custom_gcl",
        "description": "Any risk pattern detected by smart alarm engine (rollup metric)",
        "threshold": 0,
        "comparison_operator": ">",
        "evaluation_count": 2,  # Require 2 consecutive evaluations to reduce noise
        "severity": "P2",
        "period": 300,
    },
    {
        "name": "GCL-Smart-Engine-Not-Running",
        "metric_name": "gcl_smart_engine_heartbeat",
        "namespace": "acs_custom_gcl",
        "description": "Smart alarm engine has not reported heartbeat (engine may be down)",
        "threshold": 1,
        "comparison_operator": "<",
        "evaluation_count": 3,
        "severity": "P1",
        "period": 300,
    },
]

EXIT_CLEAN = 0
EXIT_CREATED = 1
EXIT_UPDATED = 2
EXIT_DELETED = 3
EXIT_ERROR = 4


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
    """Call `aliyun cms PutMetricAlarm` with the given config."""
    args = [
        "aliyun", "cms", "PutMetricAlarm",
        "--RegionId", region,
        "--AlarmName", config["name"],
        "--MetricName", config["metric_name"],
        "--Namespace", config["namespace"],
        "--Statistics", "Average",
        "--ComparisonOperator", config["comparison_operator"],
        "--Threshold", str(config["threshold"]),
        "--Period", str(config["period"]),
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


def reconcile(
    contact_group: str,
    region: str,
    webhook: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Reconcile the desired smart alarm state against existing CMS alarms.

    Unlike Phase 3-B phantom alarms, smart alarms are always desired (not
    conditional on report findings). They monitor the smart engine's output
    metrics continuously.
    """
    global_exit = EXIT_CLEAN

    for alarm in SMART_ALARMS:
        name = alarm["name"]
        existing = call_describe_alarm_list(name, region)
        exists = len(existing) > 0

        action = None
        if not exists:
            action = "create"
        elif exists:
            # Check if config changed
            current = existing[0]
            current_threshold = float(current.get("Threshold", -1))
            if current_threshold != alarm["threshold"]:
                action = "update"

        if action is None:
            print(f"[OK] {name}: already exists with correct configuration")
            continue

        if dry_run:
            print(f"[DRY-RUN] {name}: action={action}")
            if action == "create":
                print(f"  Create: threshold={alarm['threshold']} severity={alarm['severity']}")
            elif action == "update":
                print(f"  Update: threshold={alarm['threshold']} (was {current_threshold})")
            continue

        alarm_config = dict(alarm)
        alarm_config["contact_group"] = contact_group
        alarm_config["webhook"] = webhook

        if action == "create":
            ec = call_put_metric_alarm(alarm_config, region)
            if ec == 0:
                print(f"[CREATED] {name}: threshold={alarm['threshold']} severity={alarm['severity']}")
                global_exit = max(global_exit, EXIT_CREATED)
            else:
                print(f"[ERROR] {name}: PutMetricAlarm exit={ec}")
                global_exit = max(global_exit, EXIT_ERROR)
        elif action == "update":
            ec = call_put_metric_alarm(alarm_config, region)
            if ec == 0:
                print(f"[UPDATED] {name}: threshold={alarm['threshold']}")
                global_exit = max(global_exit, EXIT_UPDATED)
            else:
                print(f"[ERROR] {name}: PutMetricAlarm update exit={ec}")
                global_exit = max(global_exit, EXIT_ERROR)

    return global_exit


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_smart_alarm_cms_setup.py",
        description="Phase 7: Create/update CMS alarm rules for GCL smart alert loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Create/update smart pattern alarms
              python3 gcl_smart_alarm_cms_setup.py \
                --contact-group gcl-oncall \
                --region cn-hangzhou

              # Dry-run (show intended actions)
              python3 gcl_smart_alarm_cms_setup.py --dry-run
            """
        ),
    )
    p.add_argument(
        "--contact-group",
        default="gcl-oncall",
        help="CMS contact group for alarm notifications (default: gcl-oncall)",
    )
    p.add_argument(
        "--region",
        default="cn-hangzhou",
        help="Alarm region (default: cn-hangzhou)",
    )
    p.add_argument(
        "--webhook",
        default=None,
        help="Webhook URL for alarm notifications",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show intended actions without calling CMS API",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    print("=" * 70)
    print("GCL Smart Alert Loop — CMS Alarm Setup (Phase 7)")
    print("=" * 70)
    print(f"Region: {args.region}")
    print(f"Contact Group: {args.contact_group}")
    print("")

    exit_code = reconcile(
        contact_group=args.contact_group,
        region=args.region,
        webhook=args.webhook,
        dry_run=args.dry_run,
    )

    print("")
    if exit_code == EXIT_CLEAN:
        print("✅ All smart alarms are in the desired state.")
    elif exit_code == EXIT_CREATED:
        print("✅ Smart alarms created successfully.")
    elif exit_code == EXIT_UPDATED:
        print("✅ Smart alarms updated successfully.")
    elif exit_code == EXIT_ERROR:
        print("❌ Errors occurred during alarm setup.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
