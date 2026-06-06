#!/usr/bin/env python3
"""
daily-health-check.py — 全量健康巡检

使用:  python3 daily-health-check.py --resource-group-id rg-xxx
      python3 daily-health-check.py --tag-key customer --tag-value 烟台振华
      python3 daily-health-check.py --describe
版本: 2.3.0  关联: runbooks/01-daily-health-check.md
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

from _shared import *

P = [
    (
        "compute",
        "ECS",
        "ecs",
        "DescribeInstances",
        RG_YES,
        TAG_YES,
        "acs_ecs_dashboard",
        "InstanceId",
        "Instances.Instance",
        {"CPUUtilization": {W: 70, C: 85}, "memory_usage": {W: 80, C: 90}, "DiskUsage": {W: 75, C: 90}},
    ),
    ("compute", "ACK", "csk", "DescribeClusters", RG_YES, TAG_YES, "", "cluster_id", "Clusters", {}),
    (
        "compute",
        "ECI",
        "eci",
        "DescribeContainerGroups",
        RG_YES,
        TAG_YES,
        "acs_eci_dashboard",
        "ContainerGroupId",
        "ContainerGroups",
        {"CPUUtilization": {W: 70, C: 85}},
    ),
    (
        "database",
        "RDS",
        "rds",
        "DescribeDBInstances",
        RG_YES,
        TAG_YES,
        "acs_rds_dashboard",
        "DBInstanceId",
        "Items.DBInstance",
        {"CpuUsage": {W: 75, C: 85}, "DiskUsage": {W: 75, C: 90}, "ConnectionUsage": {W: 70, C: 85}},
    ),
    (
        "database",
        "PolarDB",
        "polardb",
        "DescribeDBClusters",
        RG_YES,
        TAG_YES,
        "acs_polardb_dashboard",
        "DBClusterId",
        "DBClusters",
        {"CpuUsage": {W: 75, C: 85}, "DiskUsage": {W: 75, C: 90}},
    ),
    (
        "database",
        "Redis-Tair",
        "r-kvstore",
        "DescribeInstances",
        RG_NO,
        TAG_YES,
        "acs_redis_dashboard",
        "InstanceId",
        "Instances.KVStoreInstance",
        {"memory_usage": {W: 75, C: 85}},
    ),
    (
        "database",
        "MongoDB",
        "dds",
        "DescribeDBInstances",
        RG_YES,
        TAG_YES,
        "acs_mongodb_dashboard",
        "DBInstanceId",
        "Items.DBInstance",
        {"CpuUsage": {W: 75, C: 85}, "DiskUsage": {W: 75, C: 90}},
    ),
    (
        "database",
        "ES",
        "elasticsearch",
        "DescribeInstances",
        RG_YES,
        TAG_YES,
        "acs_elasticsearch_dashboard",
        "instanceId",
        "Instances",
        {"NodeCPUUtilization": {W: 70, C: 85}, "NodeDiskUtilization": {W: 75, C: 90}},
    ),
    (
        "network",
        "SLB",
        "slb",
        "DescribeLoadBalancers",
        RG_NO,
        TAG_YES,
        "acs_slb_dashboard",
        "LoadBalancerId",
        "LoadBalancers.LoadBalancer",
        {"UnhealthyServerCount": {W: 1, C: 3}, "ActiveConnection": {W: 60, C: 80}},
    ),
    ("network", "VPC", "vpc", "DescribeVpcs", RG_NO, TAG_NO, "", "VpcId", "Vpcs.Vpc", {}),
    (
        "network",
        "NAT",
        "vpc",
        "DescribeNatGateways",
        RG_YES,
        TAG_NO,
        "acs_nat_gateway",
        "NatGatewayId",
        "NatGateways.NatGateway",
        {"SnatConnection": {W: 70, C: 85}, "EniPacketsDropPortAllocationFail": {W: 0, C: 1}},
    ),
    (
        "network",
        "EIP",
        "vpc",
        "DescribeEipAddresses",
        RG_NO,
        TAG_NO,
        "acs_vpc_eip",
        "AllocationId",
        "EipAddresses.EipAddress",
        {"net_in.rate_percentage": {W: 60, C: 80}},
    ),
    (
        "storage",
        "NAS",
        "nas",
        "DescribeFileSystems",
        RG_YES,
        TAG_YES,
        "acs_nas_dashboard",
        "FileSystemId",
        "FileSystems",
        {"FilesetUsage": {W: 75, C: 90}},
    ),
    (
        "security",
        "SecurityGroup",
        "ecs",
        "DescribeSecurityGroups",
        RG_NO,
        TAG_YES,
        "",
        "SecurityGroupId",
        "SecurityGroups.SecurityGroup",
        {},
    ),
]
P_BY_NAME = {p[I_NAME]: p for p in P}


def _list(prod, region, rg_id="", tag_k="", tag_v=""):
    cli = prod[I_CLI]
    api = prod[I_API]
    has_rg = prod[I_RG]
    has_tag = prod[I_TAG]
    jq_path = prod[I_JQ]
    is_full = (not rg_id) or rg_id == "default"
    if not is_full and rg_id and has_rg:
        d = q([cli, api, "--RegionId", region, "--ResourceGroupId", rg_id])
        if d:
            return dig(d, jq_path)
    if not is_full and tag_k and has_tag:
        d = q([cli, api, "--RegionId", region, "--Tag.1.Key", tag_k, "--Tag.1.Value", tag_v])
        if d:
            return dig(d, jq_path)
    d = q([cli, api, "--RegionId", region])
    return dig(d, jq_path) if d else []


def discover(args):
    log("DIAG", f"discovery region={args.region} rg={args.resource_group_id}")
    result = {}
    rg = args.resource_group_id or ""
    tag_k = args.tag_key or ""
    tag_v = args.tag_value or args.customer or ""
    with ThreadPoolExecutor(max_workers=8) as pool:
        fmap = {pool.submit(_list, prod, args.region, rg, tag_k, tag_v): prod for prod in P}
        for fut in as_completed(fmap):
            prod = fmap[fut]
            try:
                items = fut.result()
                if items:
                    result[prod[I_NAME]] = items
                    log("DIAG", f"found {prod[I_NAME]}={len(items)}")
            except Exception as e:
                err("E099", f"discover {prod[I_NAME]}: {e}")
    log("RESULT", f"discovery total={sum(len(v) for v in result.values())} types={len(result)}")
    return result


def confirm(discovered, args):
    total = sum(len(v) for v in discovered.values())
    print(f"\n{'=' * 40}\n  资源发现: {total} 个 ({len(discovered)} 种)\n{'=' * 40}\n")
    selected = {}
    for name, items in sorted(discovered.items()):
        if args.non_interactive:
            inc = not args.include or name.lower() in args.include.lower().split(",")
            skip = args.skip and name.lower() in args.skip.lower().split(",")
            if inc and not skip:
                selected[name] = items
                continue
        ans = input(f"  [x] {name:16s} {len(items):3d} 个 (Y/n): ").strip().lower()
        if not ans or ans[0] == "y":
            selected[name] = items
    log("RESULT", f"selected total={sum(len(v) for v in selected.values())}")
    return selected


def _collect_one(name, resources, ns, id_f, mdefs, h6, d7, end):
    metrics, anomalies = {}, []
    for res in resources:
        rid = res.get(id_f, "")
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
                    "300",
                    "--StartTime",
                    h6,
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
            if not isinstance(dps, list) or not dps:
                continue
            vals = [p.get("Average", 0) for p in dps if isinstance(p, dict)]
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            rk = f"{ns}_{rid}"
            if rk not in metrics:
                metrics[rk] = {"_type": name, "_id": rid}
            metrics[rk][mk] = round(avg, 2)
            if list(mdefs.keys()).index(mk) >= 2:
                continue
            bd = q(
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
            if not bd:
                continue
            bdps = bd.get("Datapoints", "[]")
            if isinstance(bdps, str):
                try:
                    bdps = json.loads(bdps)
                except Exception:
                    bdps = []
            bvals = [p.get("Average", 0) for p in bdps if isinstance(p, dict)]
            if len(bvals) < 10:
                continue
            mean = sum(bvals) / len(bvals)
            std = (sum((v - mean) ** 2 for v in bvals) / len(bvals)) ** 0.5
            if std == 0:
                continue
            recent = bvals[-3:]
            rz = [(v - mean) / std for v in recent]
            if sum(1 for z in rz if z > 2.0) < 2:
                continue
            cz = round(rz[-1], 2)
            if cz > 3.0:
                anomalies.append(
                    {
                        "id": rid,
                        "p": name,
                        "m": mk,
                        "z": cz,
                        "v": round(recent[-1], 2),
                        "mean": round(mean, 2),
                        "l": "CRITICAL",
                    }
                )
                warn("E030", f"{name}/{rid}/{mk} z={cz} CRITICAL")
            elif cz > 2.0:
                anomalies.append(
                    {
                        "id": rid,
                        "p": name,
                        "m": mk,
                        "z": cz,
                        "v": round(recent[-1], 2),
                        "mean": round(mean, 2),
                        "l": "WARNING",
                    }
                )
    return metrics, anomalies


def collect_and_score(selected, region):
    now = datetime.now(UTC)
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    h6 = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics, anomalies = {}, []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for name, resources in selected.items():
            prod = P_BY_NAME.get(name)
            assert prod
            ns, id_f, mdefs = prod[I_CMS], prod[I_ID], prod[I_METRICS]
            if not ns:
                continue
            futures.append(pool.submit(_collect_one, name, resources, ns, id_f, mdefs, h6, d7, end))
        for fut in as_completed(futures):
            try:
                m, a = fut.result()
                metrics.update(m)
                anomalies.extend(a)
            except Exception as e:
                err("E099", f"metrics: {e}")
    return metrics, anomalies


def report(selected, metrics, anomalies, args):
    rid = f"cruise-{args.customer or 'x'}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)
    md = os.path.join(args.output_dir, f"{rid}.md")
    js = os.path.join(args.output_dir, f"{rid}.json")
    criticals, warnings = [], []
    for rk, mdic in metrics.items():
        t = mdic.get("_type", "")
        for mk, mv in mdic.items():
            if mk in ("_type", "_id"):
                continue
            mt = P_BY_NAME.get(t, (0,) * 10 + ({},))[I_METRICS].get(mk, {})
            if mv >= mt.get("c", 999):
                criticals.append(
                    {"r": mdic.get("_id", ""), "t": t, "m": mk, "v": mv, "th": f"{mt.get('w', 0)}/{mt.get('c', 0)}"}
                )
            elif mv >= mt.get("w", 999):
                warnings.append(
                    {"r": mdic.get("_id", ""), "t": t, "m": mk, "v": mv, "th": f"{mt.get('w', 0)}/{mt.get('c', 0)}"}
                )
    with open(md, "w") as f:
        f.write(f"# 巡检报告 {rid}\n客户={args.customer} 区域={args.region}\n\n## 资源\n")
        for n, items in sorted(selected.items()):
            f.write(f"- {n}: {len(items)}\n")
        f.write("\n## Critical\n")
        for c in criticals:
            f.write(f"- {c['r']} {c['t']}/{c['m']}={c['v']} (阈{c['th']})\n")
        f.write("\n## Warning\n")
        for w in warnings:
            f.write(f"- {w['r']} {w['t']}/{w['m']}={w['v']} (阈{w['th']})\n")
        if anomalies:
            f.write("\n## 异常评分\n")
            for a in anomalies:
                f.write(f"- {a['id']} {a['p']}/{a['m']} z={a['z']} v={a['v']} mean={a['mean']} [{a['l']}]\n")
    rpt = {
        "report_id": rid,
        "customer": args.customer,
        "resources": {n: len(items) for n, items in selected.items()},
        "critical": criticals,
        "warning": warnings,
        "anomaly": anomalies,
    }
    with open(js, "w") as f:
        json.dump(rpt, f, indent=2)
    if criticals:
        with open(os.path.join(args.output_dir, ".need_escalation"), "w") as f:
            f.write(f"report_id={rid}\ncritical={len(criticals)}\n")
    return md, js, rpt


def main():
    ap = argparse.ArgumentParser(description="全量健康巡检")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--resource-group-id")
    g.add_argument("--tag-key")
    ap.add_argument("--tag-value")
    ap.add_argument("--resource-id")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", ""))
    ap.add_argument("--customer", default="")
    ap.add_argument("--output-dir", default="audit-results")
    ap.add_argument("--include")
    ap.add_argument("--skip")
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()
    print(f"\n{'=' * 50}\n  {os.path.basename(__file__)} v2.3.0\n{'=' * 50}")
    if args.describe:
        print("Phase 0: 资源发现 → Phase 0.5: 确认 → Phase 1+2: 采集+评分 → Phase 3: 报告")
        return
    if not gate(region := args.region or os.environ.get("ALIBABA_CLOUD_REGION_ID", "")):
        sys.exit(1)
    discovered = discover(args)
    if not discovered:
        print("[WARN] 未发现资源")
        sys.exit(2)
    selected = confirm(discovered, args)
    if not selected:
        sys.exit(0)
    metrics, anomalies = collect_and_score(selected, region)
    md, js, rpt = report(selected, metrics, anomalies, args)
    print(f"\n{'=' * 50}\n  完成: {md}\n{'=' * 50}")
    sys.exit(
        exit_code(
            len(discovered) > 0, len(rpt.get("critical", [])) + sum(1 for a in anomalies if a.get("l") == "CRITICAL")
        )
    )


if __name__ == "__main__":
    main()
