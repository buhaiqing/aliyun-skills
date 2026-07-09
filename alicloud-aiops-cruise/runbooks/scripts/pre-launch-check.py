#!/usr/bin/env python3
"""
pre-launch-check.py — 大促前预检 (v1.1.0)

使用:  python3 pre-launch-check.py --resource-group-id rg-xxx [--multiplier 3.0]
      python3 pre-launch-check.py --describe
"""

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from _shared import *

PRODUCTS = [
    (
        "ECS",
        "ecs",
        "DescribeInstances",
        "InstanceId",
        "acs_ecs_dashboard",
        "Instances.Instance",
        {"CPUUtilization": {W: 70, C: 85}, "DiskUsage": {W: 75, C: 90}},
    ),
    (
        "SLB",
        "slb",
        "DescribeLoadBalancers",
        "LoadBalancerId",
        "acs_slb_dashboard",
        "LoadBalancers.LoadBalancer",
        {"ActiveConnection": {W: 60, C: 80}},
    ),
    (
        "RDS",
        "rds",
        "DescribeDBInstances",
        "DBInstanceId",
        "acs_rds_dashboard",
        "Items.DBInstance",
        {"CpuUsage": {W: 75, C: 85}, "DiskUsage": {W: 75, C: 90}},
    ),
    (
        "PolarDB",
        "polardb",
        "DescribeDBClusters",
        "DBClusterId",
        "acs_polardb_dashboard",
        "DBClusters",
        {"CpuUsage": {W: 75, C: 85}, "DiskUsage": {W: 75, C: 90}},
    ),
    (
        "Redis",
        "r-kvstore",
        "DescribeInstances",
        "InstanceId",
        "acs_redis_dashboard",
        "Instances.KVStoreInstance",
        {"memory_usage": {W: 75, C: 85}},
    ),
]


def stress_test(region, multiplier):
    now = datetime.now(UTC)
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    d30 = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log("DIAG", f"stress_test multiplier={multiplier}x")
    results = {}
    for pname, cli, api, idf, ns, jq_path, mdefs in PRODUCTS:
        items = dig(q_cached([cli, api, "--RegionId", region]), jq_path)
        if not items:
            continue
        pdata = []
        for res in items:
            rid = res.get(idf, "")
            rname = (
                res.get("DBInstanceDescription", "")
                or res.get("InstanceName", "")
                or res.get("LoadBalancerName", "")
                or rid
            )
            if not rid:
                continue
            for mk, mt in mdefs.items():
                dims = json.dumps([{"instanceId": rid}])
                data = q(
                    [
                        "cms",
                        "DescribeMetricList",
                        "--Namespace",
                        ns,
                        "--MetricName",
                        mk,
                        "--Dimensions",
                        dims,
                        "--Period",
                        "3600",
                        "--StartTime",
                        d30,
                        "--EndTime",
                        end,
                    ]
                )
                if not data:
                    continue
                dps = data.get("Datapoints", "[]")
                if isinstance(dps, str):
                    try:
                        dps = json.loads(dps)
                    except Exception:
                        dps = []
                vals = [p.get("Maximum", 0) for p in dps if isinstance(p, dict)]
                if not vals:
                    continue
                baseline = max(vals)
                stressed = round(baseline * multiplier, 2)
                safe = stressed < mt[W]
                pdata.append(
                    {
                        "id": rid,
                        "name": rname,
                        "metric": mk,
                        "baseline": baseline,
                        "stressed": stressed,
                        "threshold": f"{mt[W]}/{mt[C]}",
                        "safe": safe,
                        "action": "PASS 余量充足" if safe else "WARN 建议升配(需人工确认)",
                    }
                )
                log("DIAG", f"{pname}/{rname} {mk}: {baseline}×{multiplier}={stressed} {'OK' if safe else 'WARN'}")
        if pdata:
            results[pname] = pdata
    return results


def report(stress, multiplier, args):
    rid = f"prelaunch-{args.customer or 'x'}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)
    md = os.path.join(args.output_dir, f"{rid}.md")
    js = os.path.join(args.output_dir, f"{rid}.json")
    upgrades = [u for pdata in stress.values() for u in pdata if not u["safe"]]
    with open(md, "w") as f:
        f.write(f"# 大促前预检\n客户={args.customer} 倍数={multiplier}x\n\n")
        if not stress:
            f.write("当前资源组未发现 ECS/SLB/RDS/PolarDB/Redis 资源，无压力模拟数据。\n")
        else:
            for pn, pd in sorted(stress.items()):
                f.write(
                    f"\n## {pn}\n| 资源 | 指标 | 基线 | ×{multiplier} | 阈值 | 状态 | 操作 |\n|------|------|------|---------|------|------|------|\n"
                )
                for p in pd:
                    f.write(
                        f"| {p['name'][:16]} | {p['metric']} | {p['baseline']} | {p['stressed']} | {p['threshold']} | {'PASS' if p['safe'] else 'WARN'} | {p['action']} |\n"
                    )
        if upgrades:
            f.write("\n##  升配建议 (需人工确认)\n")
            for i, u in enumerate(upgrades, 1):
                f.write(f"{i}. {u['name']}: {u['baseline']}×{multiplier}={u['stressed']} > {u['threshold']}\n")
    rpt = {"report_id": rid, "multiplier": multiplier, "resources": stress, "upgrade_count": len(upgrades)}
    # Sprint 9: 增 incidents[] - 预检中需升配的资源 = CRITICAL (大促前必须处理)
    if upgrades:
        incidents = [to_incident({
            "r": u.get("id", ""),
            "t": u.get("type", "OTHER"),
            "m": "StressTest",
            "v": u.get("stressed", 0),
            "th": f"{u.get('threshold', 0)}/0",
            "impact": f"大促 {multiplier}x 压力下，{u.get('name', u.get('id', ''))} 资源预测 {u.get('stressed', 0)}>{u.get('threshold', 0)}",
            "suggestion": "升配或扩容, 参见 [AUTO-CONFIRM] 名单",
        }, customer=args.customer, run_id=str(uuid.uuid4()),
            region=args.region, runbook_id="04-pre-launch-check",
            runbook_version="1.0.0", scenario="pre_launch", report_path=js,
            level_override="CRITICAL") for u in upgrades]
        rpt["incidents"] = incidents
        rpt["incidents_meta"] = {
            "schema_version": "1.0.0",
            "total": len(incidents),
            "critical": len(incidents),
            "warning": 0,
        }
    with open(js, "w") as f:
        json.dump(rpt, f, indent=2, default=str)
    # Sprint 9: MD 报告增 Incidents 章节
    if rpt.get("incidents"):
        with open(md, "a") as f:
            f.write(format_incidents_section_md(rpt))
    if upgrades:
        # Sprint 12: safe_append 不覆盖
        from lib_idempotent import safe_append
        safe_append(os.path.join(args.output_dir, ".need_escalation"),
                    f"report_id={rid} 注意: 升配建议需人工确认后执行")
    log("RESULT", f"report={md}")
    return md


def main():
    # Sprint 12 Stage 2 D1: 重入检查
    from lib_idempotent import acquire_lock, release_lock
    lock_name = f"pre-launch-check.{os.environ.get('CRUISE_LOCK_KEY', 'default')}"
    if not acquire_lock(lock_name, ttl=900):
        print(f"[ERROR] TYPE=LOCKED FIX=有其他 pre-launch-check 正在运行")
        sys.exit(10)
    try:
        _main_locked()
    finally:
        release_lock(lock_name)


def _main_locked():
    ap = argparse.ArgumentParser(description="大促前预检")
    ap.add_argument("--resource-group-id", help="限定范围 (当前为全量)")
    ap.add_argument("--tag-key")
    ap.add_argument("--tag-value")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--customer", default="")
    ap.add_argument("--multiplier", type=float, default=3.0)
    ap.add_argument("--output-dir", default=_shared._resolve_runbooks_output_dir())
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()
    if args.describe:
        print(f"30天基线 ×{args.multiplier} -> 升配建议(需人工确认)")
        return
    if not gate(args.region):
        sys.exit(1)
    stress = stress_test(args.region, args.multiplier)
    md = report(stress, args.multiplier, args)
    print(f"\n{'=' * 50}\n  完成: {md}\n{'=' * 50}")
    sys.exit(exit_code(bool(stress), 0))


if __name__ == "__main__":
    main()
