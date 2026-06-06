#!/usr/bin/env python3
"""
capacity-planning.py — 容量规划检查 (v1.1.0)

使用:  python3 capacity-planning.py --resource-group-id rg-xxx
      python3 capacity-planning.py --describe
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

from _shared import *

# (name, cli, api, id_field, cms_ns, jq_path, {metric:{w,c}})
PRODUCTS = [
    (
        "ECS",
        "ecs",
        "DescribeInstances",
        "InstanceId",
        "acs_ecs_dashboard",
        "Instances.Instance",
        {"DiskUsage": {W: 75, C: 90}, "CPUUtilization": {W: 70, C: 85}},
    ),
    (
        "RDS",
        "rds",
        "DescribeDBInstances",
        "DBInstanceId",
        "acs_rds_dashboard",
        "Items.DBInstance",
        {"DiskUsage": {W: 75, C: 90}, "CpuUsage": {W: 75, C: 85}},
    ),
    (
        "PolarDB",
        "polardb",
        "DescribeDBClusters",
        "DBClusterId",
        "acs_polardb_dashboard",
        "DBClusters",
        {"DiskUsage": {W: 75, C: 90}, "MemoryUsage": {W: 80, C: 90}},
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
    (
        "MongoDB",
        "dds",
        "DescribeDBInstances",
        "DBInstanceId",
        "acs_mongodb_dashboard",
        "Items.DBInstance",
        {"DiskUsage": {W: 75, C: 90}, "MemoryUsage": {W: 80, C: 90}},
    ),
]


def _trend_one(pname, cli, api, idf, ns, jq_path, mdefs, region, d7, end):
    raw = q([cli, api, "--RegionId", region])
    if not raw:
        return (pname, [])
    items = dig(raw, jq_path)
    pdata = []
    for res in items:
        rid = res.get(idf, "")
        rname = (
            res.get("DBInstanceDescription", "")
            or res.get("InstanceName", "")
            or res.get("DBClusterDescription", "")
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
                    d7,
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
            if not isinstance(dps, list) or len(dps) < 2:
                continue
            vals = [p.get("Average", 0) for p in dps if isinstance(p, dict)]
            if len(vals) < 2:
                continue
            first, last = vals[0], vals[-1]
            growth = (last - first) / 7.0
            days = int((mt["c"] - last) / growth) if growth > 0 else 9999
            pdata.append(
                {
                    "id": rid,
                    "name": rname,
                    "metric": mk,
                    "first": round(first, 2),
                    "last": round(last, 2),
                    "growth": round(growth, 4),
                    "days": days,
                    "threshold": mt,
                }
            )
            log("DIAG", f"{pname}/{rname} {mk}: {first}% → {last}% g={growth:.2f}/d")
    return (pname, pdata)


def collect_trends(region):
    now = datetime.now(UTC)
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        fmap = {pool.submit(_trend_one, *p, region, d7, end): p[0] for p in PRODUCTS}
        for fut in as_completed(fmap):
            try:
                pn, pd = fut.result()
                if pd:
                    results[pn] = pd
                    log("DIAG", f"trend {pn}={len(pd)}")
            except Exception as e:
                err("E099", f"trend: {e}")
    return results


def finops_check(region):
    log("DIAG", "finops_check")
    suggestions = []
    items = dig(q(["ecs", "DescribeInstances", "--RegionId", region]), "Instances.Instance")
    for inst in items:
        iid = inst.get("InstanceId", "")
        itype = inst.get("InstanceType", "")
        if not iid:
            continue
        data = q(
            [
                "cms",
                "DescribeMetricList",
                "--Namespace",
                "acs_ecs_dashboard",
                "--MetricName",
                "CPUUtilization",
                "--Dimensions",
                json.dumps([{"instanceId": iid}]),
                "--Period",
                "3600",
                "--StartTime",
                (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        vals = [p.get("Average", 0) for p in dps if isinstance(p, dict)]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        if avg < 20:
            suggestions.append({"id": iid, "type": itype, "cpu_7d_avg": round(avg, 1), "suggestion": "建议评估降配"})
    return suggestions


def report(trends, finops, args):
    rid = f"capacity-{args.customer or 'x'}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)
    md = os.path.join(args.output_dir, f"{rid}.md")
    js = os.path.join(args.output_dir, f"{rid}.json")
    with open(md, "w") as f:
        f.write(f"# 容量规划报告\n客户={args.customer} 周期=7天\n\n")
        if not trends:
            f.write("当前资源组未发现可监控的数据库/计算资源，无趋势数据。\n")
        else:
            f.write("## 趋势预测\n| 产品 | 资源 | 指标 | 当前 | 增长/天 | 预计达阈 |\n|------|------|------|------|--------|--------|\n")
            for pn, pd in sorted(trends.items()):
                for p in pd:
                    dd = f"{p['days']}天" if p["days"] < 90 else ">90天无忧"
                    f.write(f"| {pn} | {p['name'][:16]} | {p['metric']} | {p['last']} | {p['growth']} | {dd} |\n")
        if finops:
            f.write("\n## FinOps\n| 资源 | 规格 | 7天CPU均值 | 建议 |\n|------|------|----------|------|\n")
            for fn in finops:
                f.write(f"| {fn['id']} | {fn['type']} | {fn['cpu_7d_avg']}% | {fn['suggestion']} |\n")
    with open(js, "w") as f:
        json.dump(
            {"report_id": rid, "customer": args.customer, "trends": trends, "finops": finops}, f, indent=2, default=str
        )
    log("RESULT", f"report={md}")
    return md


def main():
    ap = argparse.ArgumentParser(description="容量规划")
    ap.add_argument("--resource-group-id", help="限定范围 (当前为全量扫描)")
    ap.add_argument("--tag-key")
    ap.add_argument("--tag-value")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--customer", default="")
    ap.add_argument("--output-dir", default="audit-results")
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()
    if args.describe:
        print("趋势采集 → 线性预测 → FinOps → 报告")
        return
    if not gate(args.region):
        sys.exit(1)
    if args.resource_group_id or args.tag_key:
        log("DIAG", f"scope: rg={args.resource_group_id} tag={args.tag_key}={args.tag_value}")
    trends = collect_trends(args.region)
    finops = finops_check(args.region)
    md = report(trends, finops, args)
    print(f"\n{'=' * 50}\n  完成: {md}\n{'=' * 50}")
    sys.exit(exit_code(bool(trends), 0))


if __name__ == "__main__":
    main()
