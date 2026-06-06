#!/usr/bin/env python3
"""
emergency-troubleshoot.py — 故障应急排查 (v1.1.0)

使用:  python3 emergency-troubleshoot.py --customer NAME --reported-time "2026-06-06T10:00:00Z"
      python3 emergency-troubleshoot.py --resource-group-id rg-xxx --customer NAME --reported-time ...
      python3 emergency-troubleshoot.py --describe
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta

from _shared import *


def parse_time(s):
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y%m%dT%H%M%SZ"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    return (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def troubleshoot(args):
    region = args.region or os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou")
    customer = args.customer
    reported = parse_time(args.reported_time or "")
    log("DIAG", f"customer={customer} window={reported}")
    findings = {"critical": [], "warning": [], "root_cause": "", "evidence": "", "actiontrail": []}
    six_h = (datetime.now(UTC) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")

    log("DIAG", "S1: ActionTrail")
    events = q(
        [
            "actiontrail",
            "LookupEvents",
            "--StartTime",
            six_h,
            "--EndTime",
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "--MaxResults",
            "50",
        ]
    )
    if events:
        es = [{"time": e.get("eventTime", ""), "name": e.get("eventName", "")} for e in events.get("Events", [])]
        findings["actiontrail"] = es
        log("RESULT", f"events={len(es)}")

    for prod, cli, api, path, ns, mid, mk, mt in [
        ("SLB", "slb", "DescribeLoadBalancers", ["LoadBalancers", "LoadBalancer"], None, None, None, None),
        (
            "ECS",
            "ecs",
            "DescribeInstances",
            ["Instances", "Instance"],
            "acs_ecs_dashboard",
            "InstanceId",
            "CPUUtilization",
            70,
        ),
        (
            "RDS",
            "rds",
            "DescribeDBInstances",
            ["Items", "DBInstance"],
            "acs_rds_dashboard",
            "DBInstanceId",
            "CpuUsage",
            70,
        ),
        (
            "NAT",
            "vpc",
            "DescribeNatGateways",
            ["NatGateways", "NatGateway"],
            "acs_nat_gateway",
            "NatGatewayId",
            "EniPacketsDropPortAllocationFail",
            0,
        ),
    ]:
        if findings["root_cause"] and prod != "SLB":
            break
        log("DIAG", f"S: {prod}")
        raw = q([cli, api, "--RegionId", region])
        if not raw:
            continue
        cur = raw
        for k in path:
            if isinstance(cur, dict):
                cur = cur.get(k, {})
            else:
                break
        items = cur if isinstance(cur, list) else []
        for res in items if isinstance(items, list) else []:
            rid = res.get(mid, "") if mid else (res.get("LoadBalancerId", "") if prod == "SLB" else "")
            if not rid:
                continue
            if prod == "SLB":
                health = q(["slb", "DescribeHealthStatus", "--RegionId", region, "--LoadBalancerId", rid])
                if health:
                    backs = health.get("BackendServers", {}).get("BackendServer", [])
                    unhealthy = [b for b in backs if b.get("ServerHealthStatus") != "normal"]
                    if unhealthy:
                        findings["warning"].append({"type": "SLB", "id": rid, "detail": f"{len(unhealthy)}后端异常"})
                        findings["root_cause"] = "SLB健康检查异常"
                        findings["evidence"] += f"SLB {rid}: {len(unhealthy)}个异常; "
                        warn("E050", f"SLB {rid} {len(unhealthy)} unhealthy")
                continue
            data = q(
                [
                    "cms",
                    "DescribeMetricList",
                    "--Namespace",
                    ns,
                    "--MetricName",
                    mk,
                    "--Dimensions",
                    json.dumps([{"instanceId": rid}]),
                    "--Period",
                    "300",
                    "--StartTime",
                    reported,
                    "--EndTime",
                    datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            vals = [p.get("Average" if prod != "NAT" else "Maximum", 0) for p in dps if isinstance(p, dict)]
            if not vals:
                continue
            peak = max(vals)
            if prod == "NAT":
                if peak > 0:
                    findings["critical"].append({"type": "NAT", "id": rid, "metric": mk, "value": peak})
                    findings["root_cause"] = "NAT端口耗尽"
                    findings["evidence"] += f"NAT {rid} 端口分配失败!; "
                    err("E030", f"NAT {rid} 端口分配失败!")
                    break
            elif peak > mt:
                lvl = "critical" if peak > (mt + 15) else "warning"
                sug = {"suggestion": "DAS慢查询分析"} if prod == "RDS" else {}
                findings[lvl].append({"type": prod, "id": rid, "metric": mk, "value": peak, **sug})
                findings["root_cause"] = f"{prod}指标飙高"
                findings["evidence"] += f"{prod} {rid} {mk}={peak}%; "
                warn("E030", f"{prod} {rid} {mk}={peak}%")

    if not findings["root_cause"]:
        findings["root_cause"] = "全链路正常"
        findings["evidence"] = "阿里云基础设施正常, 建议查应用层或外部依赖"
    return findings


def make_report(findings, args):
    rid = f"troubleshoot-{args.customer or 'x'}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)
    md = os.path.join(args.output_dir, f"{rid}.md")
    js = os.path.join(args.output_dir, f"{rid}.json")
    with open(md, "w") as f:
        f.write(
            f"# 故障排查报告\n客户={args.customer} 报障={args.reported_time}\n\n## 根因\n{findings['root_cause']}\n{findings['evidence']}\n\n## 问题\n"
        )
        for c in findings.get("critical", []):
            f.write(f"- 🔴 {c['type']}/{c['id']} {c.get('metric', '')}={c.get('value', '')}\n")
        for w in findings.get("warning", []):
            f.write(
                f"- 🟡 {w['type']}/{w['id']} {w.get('metric', '')}={w.get('value', '')} {w.get('suggestion', '')}\n"
            )
        f.write("\n## 操作事件\n")
        for e in findings.get("actiontrail", []):
            f.write(f"- {e['time']} {e['name']}\n")
    rpt = {"report_id": rid, **findings}
    with open(js, "w") as f:
        json.dump(rpt, f, indent=2)
    if findings.get("critical"):
        with open(os.path.join(args.output_dir, ".need_escalation"), "w") as f:
            f.write(f"report_id={rid}\ncritical={len(findings['critical'])}\n")
    log("RESULT", f"report={md}")
    return md


def main():
    ap = argparse.ArgumentParser(description="故障应急排查")
    ap.add_argument("--resource-group-id", help="限定排查范围")
    ap.add_argument("--customer", required=True)
    ap.add_argument("--reported-time", required=True)
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--output-dir", default="audit-results")
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()
    if args.describe:
        print("S1:ActionTrail → SLB → ECS → RDS → NAT → 根因报告")
        return
    if not gate(args.region):
        sys.exit(1)
    findings = troubleshoot(args)
    md = make_report(findings, args)
    print(f"\n{'=' * 50}\n  完成: {md}\n{'=' * 50}")
    sys.exit(exit_code(bool(findings["root_cause"]), len(findings.get("critical", []))))


if __name__ == "__main__":
    main()
