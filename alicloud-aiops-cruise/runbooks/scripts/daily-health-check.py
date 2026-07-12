#!/usr/bin/env python3
"""
daily-health-check.py — 全量健康巡检

使用:  python3 daily-health-check.py --resource-group-id rg-xxx
      python3 daily-health-check.py --tag-key customer --tag-value 烟台振华
      python3 daily-health-check.py --describe
版本: 2.3.1  关联: runbooks/01-daily-health-check.md
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path

import _shared
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
        {"CPUUtilization": {W: 70, C: 85}, "memory_usedutilization": {W: 80, C: 90}, "DiskUsage": {W: 75, C: 90}},
    ),
    ("compute", "ACK", "cs", "DescribeClustersV1", RG_YES, TAG_YES, "", "cluster_id", "clusters", {}),
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
        "acs_elasticsearch",
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
        d = q_cached([cli, api, "--RegionId", region, "--ResourceGroupId", rg_id])
        if d:
            result = dig(d, jq_path)
            # B-1 Blocker: 当 --ResourceGroupId 过滤返回 0 时，可能资源在默认 RG（API 用 "" 而非 "default"）
            # 这是静默数据丢失，改写为显式告警
            if not result:
                log("WARN", f"RG={rg_id} {cli}/{api} returned 0 — "
                    f"resources may be in default RG (API uses empty-string, not 'default')")
            return result
    if not is_full and tag_k and has_tag:
        d = q_cached([cli, api, "--RegionId", region, "--Tag.1.Key", tag_k, "--Tag.1.Value", tag_v])
        if d:
            return dig(d, jq_path)
    d = q_cached([cli, api, "--RegionId", region])
    return dig(d, jq_path) if d else []


def _csv_names(value):
    return {v.strip().lower() for v in (value or "").split(",") if v.strip()}


def _product_in_discovery_scope(name, args):
    include = _csv_names(args.include)
    skip = _csv_names(args.skip)
    lname = name.lower()
    if include and lname not in include:
        return False
    return lname not in skip


def discover(args):
    log("DIAG", f"discovery region={args.region} rg={args.resource_group_id}")
    result = {}
    rg = args.resource_group_id or ""
    tag_k = args.tag_key or ""
    tag_v = args.tag_value or args.customer or ""
    products = [prod for prod in P if _product_in_discovery_scope(prod[I_NAME], args)]
    log("DIAG", "discovery scope=" + ",".join(prod[I_NAME] for prod in products))
    with ThreadPoolExecutor(max_workers=12) as pool:
        fmap = {pool.submit(_list, prod, args.region, rg, tag_k, tag_v): prod for prod in products}
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


def _filter_by_resource_id(name, items, resource_id):
    if not resource_id:
        return items
    prod = P_BY_NAME.get(name)
    id_field = prod[I_ID] if prod else ""
    return [item for item in items if item.get(id_field) == resource_id]


def confirm(discovered, args):
    total = sum(len(v) for v in discovered.values())
    print(f"\n{'=' * 40}\n  资源发现: {total} 个 ({len(discovered)} 种)\n{'=' * 40}\n")
    selected = {}
    for name, items in sorted(discovered.items()):
        filtered_items = _filter_by_resource_id(name, items, args.resource_id)
        if args.non_interactive:
            if _product_in_discovery_scope(name, args) and filtered_items:
                selected[name] = filtered_items
            continue
        ans = input(f"  [x] {name:16s} {len(filtered_items):3d} 个 (Y/n): ").strip().lower()
        if (not ans or ans[0] == "y") and filtered_items:
            selected[name] = filtered_items
    log("RESULT", f"selected total={sum(len(v) for v in selected.values())}")
    return selected


def _preflight_check(selected, region: str, h6: str, end: str) -> dict:
    """Phase 0.5: 数据可用性预检 — 在拓扑发现后、指标采集前执行。

    探测 4 个已知的数据盲区：
      P-A: Redis CloudMonitor 增强监控可用性
      P-B: 告警历史字段完整性
      P-C: SLB 零流量置信度（仅在 TrafficRX_MAX=0 时触发扩展验证）
      P-D: ACK 节点监控可用性（ags-metrics-collector）

    返回: {probes, confidence, confidence_reason, downstream_signals, affected_findings}
    """
    probes: dict = {}
    downstream: dict = {}

    def _p(name: str, result: str, detail: str,
           data_gap_impact: str = "无",
           severity: str = "PASS",
           remediation: str = "") -> dict:
        d = {"probe": name, "result": result, "detail": detail,
             "data_gap_impact": data_gap_impact, "severity": severity}
        if remediation:
            d["remediation"] = remediation
        return d

    # P-A: Redis CloudMonitor 增强监控
    redis_has_enhanced = False
    if "Redis-Tair" in selected and selected["Redis-Tair"]:
        first_redis_id = selected["Redis-Tair"][0].get("InstanceId", "")
        if first_redis_id:
            meta_rt = q(["cms", "DescribeMetricMetaList",
                         "--Namespace", "acs_redis_dashboard",
                         "--MetricName", "memory_usage",
                         "--PageSize", "1"])
            total = meta_rt.get("Total", 0) if meta_rt else 0
            redis_has_enhanced = total > 0
            if redis_has_enhanced:
                probes["redis_cloudmonitor"] = _p(
                    "DescribeMetricMetaList acs_redis_dashboard memory_usage",
                    "PASS",
                    f"增强监控已开通，memory_usage 可用（抽样 {first_redis_id}）")
            else:
                probes["redis_cloudmonitor"] = _p(
                    "DescribeMetricMetaList acs_redis_dashboard memory_usage",
                    "UNAVAILABLE",
                    "增强监控未开通，acs_redis_dashboard 下 memory_usage 不可采集",
                    "memory_usage / memory_used / 内网命中率 全部 data_gap",
                    severity="WARNING",
                    remediation="Redis控制台 → 监控报警 → 开启云监控增强监控")
        else:
            probes["redis_cloudmonitor"] = _p(
                "Redis 增强监控探针", "SKIPPED", "无法获取 Redis 实例 ID，跳过")
    else:
        probes["redis_cloudmonitor"] = _p(
            "Redis 增强监控探针", "SKIPPED", "本次巡检无 Redis 资源")
    downstream["REDIS_MONITORING_AVAILABLE"] = str(redis_has_enhanced).lower()

    # P-B: 告警历史字段完整性
    alert_rt = q(["cms", "DescribeAlertHistoryList",
                  "--StartTime", h6, "--EndTime", end, "--PageSize", "10"])
    alert_items = (alert_rt or {}).get("AlarmHistoryList", {}).get("AlarmHistoryItem", [])
    if not isinstance(alert_items, list):
        alert_items = []
    total = len(alert_items)
    name_null = sum(1 for a in alert_items
                    if not a.get("Name") or a.get("Name") == "null")
    id_null = sum(1 for a in alert_items
                   if not a.get("InstanceId") or a.get("InstanceId") == "null")
    if total == 0:
        probes["alarm_history"] = _p(
            "DescribeAlertHistoryList 过去6h，Name/InstanceId 非空率",
            "NO_ALERTS", "过去6h无告警历史，告警覆盖度验证跳过")
        downstream["ALARM_COVERAGE_MODE"] = "NO_ALERTS"
    else:
        name_null_pct = int(name_null * 100 / total)
        id_null_pct = int(id_null * 100 / total)
        if name_null_pct > 50 or id_null_pct > 50:
            probes["alarm_history"] = _p(
                "DescribeAlertHistoryList 过去6h，Name/InstanceId 非空率",
                "DEGRADED",
                f"Name 空值率={name_null_pct}%({name_null}/{total}) "
                f"InstanceId 空值率={id_null_pct}%({id_null}/{total})",
                "告警覆盖度验证降级为参考级，不参与评分",
                severity="INFO")
            downstream["ALARM_COVERAGE_MODE"] = "DEGRADED"
        else:
            probes["alarm_history"] = _p(
                "DescribeAlertHistoryList 过去6h，Name/InstanceId 非空率",
                "PASS",
                f"Name 空值率={name_null_pct}% InstanceId 空值率={id_null_pct}%")
            downstream["ALARM_COVERAGE_MODE"] = "FULL"

    # P-C: SLB 零流量置信度（Phase 2 完成后补填，此处仅占位）
    if "SLB" in selected and selected["SLB"]:
        probes["slb_traffic"] = _p(
            "SLB 零流量置信度", "PENDING",
            "将在 Phase 2 SLB 采集完成后补填")
    else:
        probes["slb_traffic"] = _p(
            "SLB 零流量置信度", "SKIPPED", "本次巡检无 SLB 资源")
    downstream["SLB_TRAFFIC_CONFIDENCE"] = "PENDING"

    # P-D: ACK 节点监控可用性
    ack_monitoring_available = False
    if "ACK" in selected and selected["ACK"]:
        cluster_id = selected["ACK"][0].get("cluster_id", "")
        if cluster_id:
            probe_rt = q(["cs", "GET",
                          f"/clusters/{cluster_id}/components/ags-metrics-collector"])
            if probe_rt and isinstance(probe_rt, dict) and probe_rt.get("state") == "running":
                probes["ack_monitoring"] = _p(
                    "ags-metrics-collector 状态", "PASS",
                    f"集群 {cluster_id} ags-metrics-collector state=running，节点指标可信")
                ack_monitoring_available = True
            else:
                probes["ack_monitoring"] = _p(
                    "ags-metrics-collector 状态", "UNAVAILABLE",
                    f"集群 {cluster_id} ags-metrics-collector 未安装或未运行，节点级指标 data_gap",
                    "节点 CPU/内存指标 data_gap",
                    severity="WARNING",
                    remediation="ACK 控制台 → 运维管理 → 组件管理 → 安装 ags-metrics-collector")
        else:
            probes["ack_monitoring"] = _p(
                "ags-metrics-collector 状态", "SKIPPED", "无法获取 ACK 集群 ID")
    else:
        probes["ack_monitoring"] = _p(
            "ags-metrics-collector 状态", "SKIPPED", "本次巡检无 ACK 集群")
    downstream["ACK_MONITORING_AVAILABLE"] = str(ack_monitoring_available).lower()

    # 置信度汇总
    unavailable = [k for k, v in probes.items()
                   if v["result"] in ("UNAVAILABLE", "DEGRADED")]
    confidence = "DEGRADED" if unavailable else "FULL"
    confidence_reason = "; ".join(f"{k}={probes[k]['result']}" for k in unavailable) if unavailable else "所有探针 PASS"

    result = {
        "phase": "0.5",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "probes": probes,
        "downstream_signals": downstream,
        "affected_findings": [],   # Phase 2 完成后补填
    }
    log("DIAG", f"Phase 0.5: confidence={confidence} probes={list(probes.keys())}")
    return result


def _collect_one(name, resources, ns, id_f, mdefs, h6, d7, end):
    """Sprint 15 重构: 按 dimension 批量拉取 (q_cms_batch_by_dim).

    演化路径:
      Sprint 13 串行 for-loop: N instance × M metric × 2 period = 2NM 次串行 q()
      Sprint 14 q_cms_batch: 2NM 个 job 并发提交, 限速 20 (-86%)
      Sprint 15 q_cms_batch_by_dim: 2M × ceil(N/50) 次, 维度合并到单次 API (-99%)

    实测 (mock, 100 ECS × 3 metric × 2 period):
      串行:    600 次调用
      Sprint 14: 600 次 (并发执行, 总耗时减半)
      Sprint 15: 6 × ceil(100/50) = 12 次调用 (-98% API 调用次数)

    行为兼容性: 100% (同 metrics/anomalies/baseline_data 结构和 key)
    """
    # 1. 收集所有 instance id
    rid_to_res = {}  # rid -> resource
    for res in resources:
        rid = res.get(id_f, "")
        if rid:
            rid_to_res[rid] = res
    all_rids = list(rid_to_res.keys())

    if not all_rids:
        return {}, [], {}

    log("DIAG", f"_collect_one {name}: instances={len(all_rids)} metrics={len(mdefs)} "
        f"(Sprint 15: 按 dimension 批量, 预期 API 调用 {2 * len(mdefs) * max(1, (len(all_rids) + 49) // 50)} 次)")

    # 2. 对每个 (metric, period) 拉一次批量 API
    #    数据结构: realtime_data[mk][rid] = [datapoints], baseline_data_raw[mk][rid] = [datapoints]
    realtime_data: dict = {}  # mk -> {rid: [dp]}
    baseline_data_raw: dict = {}  # mk -> {rid: [dp]}
    for mk in mdefs:
        # 2a. 实时数据 (5min 粒度, 6h 窗口)
        realtime_data[mk] = q_cms_batch_by_dim(
            ns, mk, "instanceId", all_rids, "300", h6, end, batch_size=50,
        )
        # 2b. 基线数据 (1h 粒度, 7d 窗口)
        baseline_data_raw[mk] = q_cms_batch_by_dim(
            ns, mk, "instanceId", all_rids, "3600", d7, end, batch_size=50,
        )

    # 3. 解析结果, 分离 metrics / anomalies / baseline_data
    metrics, anomalies, baseline_data = {}, [], {}

    for mk in mdefs:
        for rid in all_rids:
            rk = f"{ns}_{rid}"

            # 3a. 实时数据 -> 算 avg -> 写 metrics
            dps_rt = realtime_data[mk].get(rid, [])
            if dps_rt:
                vals = [p.get("Average", 0) for p in dps_rt if isinstance(p, dict)]
                if vals:
                    avg = sum(vals) / len(vals)
                    if rk not in metrics:
                        metrics[rk] = {"_type": name, "_id": rid}
                    metrics[rk][mk] = round(avg, 2)

            # 3b. 基线数据 -> 异常评分
            dps_bl = baseline_data_raw[mk].get(rid, [])
            if not dps_bl:
                continue
            bvals = [p.get("Average", 0) for p in dps_bl if isinstance(p, dict)]
            # Sprint 11.5: 同时保留时间戳供 Prophet 使用
            btimes = [p.get("timestamp", p.get("Timestamp", 0)) for p in dps_bl if isinstance(p, dict)]
            if len(bvals) < BASELINE_MIN_POINTS:
                continue
            # 保存基线数据用于异常评分
            if rk not in baseline_data:
                baseline_data[rk] = {}
            baseline_data[rk][mk] = {"values": bvals, "timestamps": btimes}
            # 按指标方法映射做异常评分
            method = _get_anomaly_method(ns, mk)
            if not method:
                continue
            # 降噪检查
            if not _has_consecutive_anomaly(bvals, method, ANOMALY_WARN_Z):
                continue
            ml_shadow = build_ml_shadow_result(bvals, btimes, bvals[-1], method, rid, mk)
            if method in (ANOMALY_METHOD_ZSCORE, ANOMALY_METHOD_DUAL):
                z, level = compute_anomaly_score_zscore(bvals, bvals[-1])
            elif method == ANOMALY_METHOD_PERCENTILE:
                z, level = compute_anomaly_score_percentile(bvals, bvals[-1])
            elif method == ANOMALY_METHOD_STL:  # Sprint 11
                z, level = compute_anomaly_score_stl(bvals, bvals[-1])
                if z is None:  # 数据不足 fallback
                    z, level = compute_anomaly_score_zscore(bvals, bvals[-1])
            elif method == ANOMALY_METHOD_PROPHET:  # Sprint 11.5
                z, level = compute_anomaly_score_prophet(bvals, btimes, bvals[-1])
                if z is None:  # 数据不足/模型失败 fallback STL -> Z-Score
                    z, level = compute_anomaly_score_stl(bvals, bvals[-1])
                    if z is None:
                        z, level = compute_anomaly_score_zscore(bvals, bvals[-1])
            else:
                continue
            risk_evidence = build_metric_risk_evidence(
                resource_id=rid,
                resource_type=name,
                metric_name=mk,
                current_value=round(bvals[-1], 2),
                warning_threshold=mdefs.get(mk, {}).get(W, 0),
                critical_threshold=mdefs.get(mk, {}).get(C, 0),
                history_values=bvals,
                anomaly={"l": level or "NORMAL"},
                ml_shadow=ml_shadow,
            )
            if level in ("CRITICAL", "WARNING"):
                mean = sum(bvals) / len(bvals)
                std = (sum((v - mean) ** 2 for v in bvals) / len(bvals)) ** 0.5
                anomalies.append(
                    {
                        "id": rid,
                        "p": name,
                        "m": mk,
                        "z": round(z, 2) if z else 0,
                        "v": round(bvals[-1], 2),
                        "mean": round(mean, 2),
                        "std": round(std, 2) if std else 0,
                        "l": level,
                        "method": method,
                        "risk_evidence": risk_evidence,
                        "risk_score": risk_evidence.get("risk_score"),
                        "ml_shadow_result": ml_shadow,
                    }
                )
                log(level, f"{name}/{rid}/{mk} z={z} [{level}] ")
    return metrics, anomalies, baseline_data





def _collect_ack(clusters: list, region: str) -> dict:
    """ACK independent collector for cluster/node-level acs_k8s metrics.
    Node-level metrics (node.cpu.capacity, node.memory.limit, etc.)
    require the ags-metrics-collector addon installed on the cluster."""
    from datetime import datetime, timezone, timedelta
    result = {"metrics": {}, "backtrack": None, "audit": None, "limits": None}
    if not clusters:
        return result
    log("DIAG", "_collect_ack clusters=%d" % len(clusters))
    now = datetime.now(timezone.utc)
    # Sprint 8: 归一化到 5min 桶使 CMS 跨调用命中缓存
    end = normalize_time_to_bucket(now, 5)
    d7s = normalize_time_to_bucket(now - timedelta(days=7), 5)
    for cluster in clusters:
        cid = cluster.get("cluster_id", "")
        cname = cluster.get("name", "") or cid
        if not cid:
            continue
        cl_dims = json.dumps([{"cluster": cid}])
        
        # ------------------------------------------------------------
        # 前置探针: 检测 ags-metrics-collector 是否安装
        # 未安装则跳过所有节点级采集 (backtrack/limits/oversale)，节省 ~70s
        # ------------------------------------------------------------
        probe = q_cached(["cs", "GET", "/clusters/" + cid + "/components/ags-metrics-collector", "--region", region], timeout=10)
        has_node_monitoring = probe is not None and isinstance(probe, dict) and probe.get("state") == "running"
        if not has_node_monitoring:
            log("WARN", "ags-metrics-collector not installed on cluster=%s -> skip node-level CMS backtrack (~70s saved)" % cname)

        for metric, mk in [("CpuUsage", "cpu_util"), ("MemoryUsage", "mem_util")]:
            data = q_cached(["cms", "DescribeMetricList", "--Namespace", "acs_k8s_dashboard", "--MetricName", metric,
                      "--Dimensions", cl_dims, "--Period", "300", "--StartTime", d7s, "--EndTime", end])
            if not data: continue
            dps = data.get("Datapoints", "[]")
            if isinstance(dps, str):
                try: dps = json.loads(dps)
                except Exception: dps = []
            vals = [p.get("Average", 0) for p in dps if isinstance(p, dict)]
            if not vals: continue
            rk = "ack_%s_%s" % (cid, mk)
            result["metrics"][rk] = {"_type": "ACK", "_id": cid}
            result["metrics"][rk][mk] = round(sum(vals) / len(vals), 2)
        raw_nodes = q_cached(["cs", "GET", "/clusters/" + cid + "/nodes", "--region", region])
        if not raw_nodes: continue
        nodes = raw_nodes.get("nodes", [])
        log("DIAG", "  cluster=%s nodes=%d" % (cname, len(nodes)))
        node_names = []
        for node in nodes:
            nname = node.get("node_name", "") or node.get("instance_id", "")
            if not nname: continue
            node_names.append(nname)

        # 节点级采集受 ags-metrics-collector 组件控制
        # 未安装时跳过所有节点级 CMS 回溯以节省 ~70s
        if has_node_monitoring:
            for node in nodes:
                nname = node.get("node_name", "") or node.get("instance_id", "")
                if not nname: continue
                nd = json.dumps([{"cluster": cid, "node": nname}])
                for metric, mk in [("node.cpu.oversale_rate", "cpu_oversale"), ("node.memory.oversale_rate", "mem_oversale")]:
                    data = q_cached(["cms", "DescribeMetricList", "--Namespace", "acs_k8s", "--MetricName", metric,
                              "--Dimensions", nd, "--Period", "300", "--StartTime", d7s, "--EndTime", end])
                    if not data: continue
                    dps = data.get("Datapoints", "[]")
                    if isinstance(dps, str):
                        try: dps = json.loads(dps)
                        except Exception: dps = []
                    vals = [p.get("Average", 0) for p in dps if isinstance(p, dict)]
                    if not vals: continue
                    rk = "ack_%s_%s_%s" % (cid, nname, mk)
                    result["metrics"][rk] = {"_type": "ACK", "_id": "%s/%s" % (cid, nname)}
                    result["metrics"][rk][mk] = round(sum(vals) / len(vals), 2)
            if node_names:
                result["limits"] = _collect_k8s_limits(region, cid, node_names, d7=d7s, end=end)
            result["backtrack"] = backtrack_cms(region, cid, node_names, days=7, end_time=normalize_time_to_bucket(now, 5))
        result["audit"] = check_audit_log_enabled(region, cid)
        # K8s events via local kubectl (non-blocking, permission issues are warnings only)
        result["k8s_events"] = _collect_k8s_events_local(cid, region)
        if result["k8s_events"]["status"] != "OK":
            log("WARN", "k8s_events: %s" % result["k8s_events"]["message"])
    log("RESULT", "_collect_ack metrics=%d" % len(result["metrics"]))
    return result


def collect_and_score(selected, region):
    now = datetime.now(UTC)
    # Sprint 8: 归一化到 5min 桶
    end = normalize_time_to_bucket(now.replace(tzinfo=None), 5)
    h6 = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics, anomalies, baseline_data = {}, [], {}
    ack_data = {"backtrack": None, "audit": None, "limits": None}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = []
        for name, resources in selected.items():
            if name == "ACK":
                continue
            prod = P_BY_NAME.get(name)
            if not prod:
                continue
            ns, id_f, mdefs = prod[I_CMS], prod[I_ID], prod[I_METRICS]
            if not ns:
                continue
            futures.append(pool.submit(_collect_one, name, resources, ns, id_f, mdefs, h6, d7, end))
        for fut in as_completed(futures):
            try:
                m, a, bd = fut.result()
                metrics.update(m)
                anomalies.extend(a)
                baseline_data.update(bd)
            except Exception as e:
                err("E099", "metrics: %s" % e)
    ack_resources = selected.get("ACK", [])
    if ack_resources:
        ack_result = _collect_ack(ack_resources, region)
        metrics.update(ack_result.get("metrics", {}))
        ack_data["backtrack"] = ack_result.get("backtrack")
        ack_data["audit"] = ack_result.get("audit")
        ack_data["limits"] = ack_result.get("limits")
        ack_data["k8s_events"] = ack_result.get("k8s_events")
    return metrics, anomalies, baseline_data, ack_data




def report(selected, metrics, anomalies, args, ack_data=None, baseline_data=None, preflight_data=None):
    rpt = {}  # Sprint 11: 初始化避免 UnboundLocalError
    rid = f"cruise-{args.customer or 'x'}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    os.makedirs(args.output_dir, exist_ok=True)
    md = os.path.join(args.output_dir, f"{rid}.md")
    js = os.path.join(args.output_dir, f"{rid}.json")
    criticals, warnings, risk_evidence = [], [], []
    for rk, mdic in metrics.items():
        t = mdic.get("_type", "")
        rid_static = mdic.get("_id", "")
        for mk, mv in mdic.items():
            if mk in ("_type", "_id"):
                continue
            mt = P_BY_NAME.get(t, (0,) * 10 + ({},))[I_METRICS].get(mk, {})
            history = (baseline_data or {}).get(rk, {}).get(mk, {}).get("values", [])
            evidence = build_metric_risk_evidence(
                resource_id=rid_static,
                resource_type=t,
                metric_name=mk,
                current_value=mv,
                warning_threshold=mt.get("w", 0),
                critical_threshold=mt.get("c", 0),
                history_values=history,
            )
            risk_evidence.append(evidence)
            if mv >= mt.get("c", 999):
                criticals.append(
                    {
                        "r": rid_static,
                        "t": t,
                        "m": mk,
                        "v": mv,
                        "th": f"{mt.get('w', 0)}/{mt.get('c', 0)}",
                        "risk_score": evidence.get("risk_score"),
                        "metadata": {"risk_evidence": evidence},
                    }
                )
            elif mv >= mt.get("w", 999):
                warnings.append(
                    {
                        "r": rid_static,
                        "t": t,
                        "m": mk,
                        "v": mv,
                        "th": f"{mt.get('w', 0)}/{mt.get('c', 0)}",
                        "risk_score": evidence.get("risk_score"),
                        "metadata": {"risk_evidence": evidence},
                    }
                )
    # 构建 anomaly_scores（完整 JSON schema）
    anomaly_scores = []
    for a in anomalies:
        if a.get("risk_evidence"):
            risk_evidence.append(a.get("risk_evidence"))
        score = {
            "instance_id": a.get("id", ""),
            "metric": a.get("m", ""),
            "current_value": a.get("v", 0),
            "baseline_mean": a.get("mean", 0),
            "baseline_std": a.get("std", 0),
            "z_score": a.get("z", 0),
            "level": a.get("l", "WARNING"),
            "method": a.get("method", "z-score"),
            "window_days": 7,
            "bucket_strategy": "global",
            "resource_type": a.get("p", ""),
            "risk_score": a.get("risk_score"),
            "risk_evidence": a.get("risk_evidence"),
            "ml_shadow_result": a.get("ml_shadow_result"),
        }
        anomaly_scores.append(score)
    with open(md, "w") as f:
        # Write DATA-AVAIL section first
        for line in md_lines:
            f.write(line)
        f.write(f"# 巡检报告 {rid}\n客户={args.customer} 区域={args.region}\n\n## 资源\n")
        for n, items in sorted(selected.items()):
            f.write(f"- {n}: {len(items)}\n")
        f.write("\n## Critical\n")
        for c in criticals:
            f.write(f"- {c['r']} {c['t']}/{c['m']}={c['v']} (阈{c['th']})\n")
        f.write("\n## Warning\n")
        for w in warnings:
            f.write(f"- {w['r']} {w['t']}/{w['m']}={w['v']} (阈{w['th']})\n")
        # Sprint 9: Incidents (incident-schema v1.0.0) 摘要
        if rpt.get("incidents_meta"):
            meta = rpt["incidents_meta"]
            f.write(f"\n## Incidents (schema {meta['schema_version']})\n")
            f.write(f"总计: {meta['total']} (CRITICAL={meta['critical']}, WARNING={meta['warning']}, INFO={meta['info']})\n\n")
            f.write("| Level | Rule | Resource | Metric | Value | Title |\n")
            f.write("|:------|:-----|:---------|:-------|------:|:------|\n")
            for i in rpt.get("incidents", []):
                f.write(f"| {i['level']} | `{i['rule_id']}` | {i['resource_type']}/{i['resource_id'][:20]} | {i.get('metric', '-')} | {i.get('current_value', '-')} | {i['title']} |\n")
        # 统一风险证据 + 异常评分摘要表格
        f.write(format_risk_evidence_table(risk_evidence))
        if anomaly_scores:
            f.write("\n" + format_anomaly_scores_table(anomaly_scores) + "\n")
        # ACK report section
        if ack_data:
            ack_resources = selected.get("ACK", [])
            if ack_resources:
                f.write("\n---\n## ACK CLUSTER INSPECTION\n")
                for cl in ack_resources:
                    cname = cl.get("name", cl.get("cluster_id", ""))
                    f.write("\n### %s\n" % cname)
                audit = ack_data.get("audit")
                if audit:
                    f.write("\n**SLS 审计日志**: " + ("ENABLED" if audit.get("audit_enabled") else "DISABLED") + "\n")
                bt = ack_data.get("backtrack")
                if bt:
                    f.write("\n### 7 天回溯分析\n")
                    f.write(format_backtrack_report(bt) + "\n")
                limits = ack_data.get("limits")
                if limits:
                    f.write(format_limits_report(limits) + "\n")
                k8s_events = ack_data.get("k8s_events")
                if k8s_events:
                    f.write(format_k8s_events_report(k8s_events) + "\n")
    # Phase 0.5: data_availability 注入
    data_avail = preflight_data or {}
    confidence = data_avail.get("confidence", "UNKNOWN")
    affected = data_avail.get("affected_findings", []) or []
    # 自动生成 data_gap 发现项（Q2: 自动生成 WARNING 发现项）
    data_gap_warnings = []
    for probe_name, probe in (data_avail.get("probes") or {}).items():
        if probe.get("result") == "UNAVAILABLE" and probe_name in ("redis_cloudmonitor", "ack_monitoring"):
            remediation = probe.get("remediation", "")
            data_gap_warnings.append({
                "id": f"DG-{probe_name}",
                "title": f"监控数据缺失: {probe.get('probe', probe_name)}",
                "severity": "WARNING",
                "rule_id": "DATA-GAP",
                "resources": [{"id": "N/A", "name": probe_name}],
                "impact": probe.get("data_gap_impact", "数据不可用"),
                "suggestion": remediation or "开通相应监控服务",
            })
    # affected_findings 修正（Phase 2 完成后可扩展）
    if affected:
        for af in affected:
            data_gap_warnings.append(af)
    for dw in data_gap_warnings:
        warnings.append(dw)

    # Markdown: data_availability section
    md_lines = [
        f"\n## [DATA-AVAIL] 数据可用性预检\n",
        f"> **置信度: {confidence}** — {data_avail.get("confidence_reason", "")}\n\n",
        "| 探针 | 结果 | 详情 |\n",
        "|:-----|:-----|:-----|\n",
    ]
    for probe_name, probe in sorted((data_avail.get("probes") or {}).items()):
        icon_map = {"PASS": "PASS", "UNAVAILABLE": "UNAVAILABLE", "DEGRADED": "DEGRADED",
                   "NO_ALERTS": "NO_ALERTS", "PENDING": "PENDING", "SKIPPED": "SKIPPED"}
        result_txt = icon_map.get(probe.get("result", ""), probe.get("result", ""))
        detail = probe.get("detail", "").replace("|", "&#124;")
        md_lines.append("| %s | %s | %s |\n" % (probe_name, result_txt, detail))
    if data_gap_warnings:
        md_lines.append("\n### data_gap 影响评估\n\n")
        md_lines.append("| 资源 | 问题 | 说明 |\n")
        md_lines.append("|:-----|:-----|:-----|\n")
        for dw in data_gap_warnings:
            rname = (dw.get("resources", [{}])[0] or {}).get("name", "")
            title = dw.get("title", "").replace("|", "&#124;")
            sugg = dw.get("suggestion", "").replace("|", "&#124;")
            md_lines.append("| %s | %s | %s |\n" % (rname, title, sugg))
    md_lines.append("\n")

    rpt = {
        "report_id": rid,
        "customer": args.customer,
        "resources": {n: len(items) for n, items in selected.items()},
        "critical": criticals,
        "warning": warnings,
        "anomaly_scores": anomaly_scores,
        "risk_evidence": risk_evidence,
        "ml_policy": get_ml_policy(),
        "ack": {
            "backtrack": ack_data.get("backtrack"),
            "audit": ack_data.get("audit"),
            "limits": ack_data.get("limits"),
            "k8s_events": ack_data.get("k8s_events"),
        } if ack_data else None,
        "data_availability": data_avail,
    }
    # Sprint 9: 增 incidents[] 数组 (incident-schema v1.0.0)
    if os.environ.get("AIOPS_INCIDENTS", "1") == "1":
        run_id_uuid = str(uuid.uuid4())
        json_report_path = js  # 后面会被 json.dump 写入
        incidents = findings_to_incidents(
            criticals, warnings,
            customer=args.customer, run_id=run_id_uuid, region=args.region,
            runbook_id="01-daily-health-check", runbook_version="2.3.0",
            scenario="daily_check", report_path=json_report_path,
        )
        # anomalies 转 incidents
        for a in anomaly_scores:
            incidents.append(anomaly_to_incident(
                a, customer=args.customer, run_id=run_id_uuid, region=args.region,
                runbook_id="01-daily-health-check", runbook_version="2.3.0",
                scenario="daily_check", report_path=json_report_path,
            ))
        rpt["incidents"] = incidents
        rpt["incidents_meta"] = {
            "schema_version": "1.0.0",
            "total": len(incidents),
            "critical": sum(1 for i in incidents if i["level"] == "CRITICAL"),
            "warning": sum(1 for i in incidents if i["level"] == "WARNING"),
            "info": sum(1 for i in incidents if i["level"] == "INFO"),
        }
    with open(js, "w") as f:
        json.dump(rpt, f, indent=2, default=str)
    if criticals:
        # Sprint 12: 改用 safe_append 不覆盖,保留历史需升级记录
        from lib_idempotent import safe_append
        safe_append(os.path.join(args.output_dir, ".need_escalation"),
                    f"report_id={rid} critical={len(criticals)}")
    return md, js, rpt





def format_limits_report(limits):
    """Format limits overcommit results as Markdown section.
    Documents ags-metrics-collector dependency for node-level acs_k8s metrics."""
    if not limits or not limits.get("nodes"):
        return ""
    lines = ["\n### \u8282\u70b9\u8d44\u6e90\u5206\u914d\u68c0\u67e5 (Limits \u8d85\u5206\u68c0\u6d4b)\n"]
    has_data = any(n["cpu"].get("capacity") is not None or n["memory"].get("capacity") is not None for n in limits["nodes"])
    if not has_data:
        lines.append("[WARN] \u65e0\u6cd5\u83b7\u53d6\u8282\u70b9\u8d44\u6e90\u6570\u636e\n\n")
        lines.append("\u5df2\u626b\u63cf %d \u4e2a\u8282\u70b9\uff0c\u4f46\u4e91\u76d1\u63a7\uff08CMS\uff09\u6ca1\u6709\u91c7\u96c6\u5230\u8282\u70b9\u7684\u8d44\u6e90\u5bb9\u91cf\u548c\u5df2\u5206\u914d\u91cf\u6570\u636e\u3002\n" % len(limits["nodes"]))
        lines.append("\u8fd9\u662f\u56e0\u4e3a\u5f53\u524d ACK \u96c6\u7fa4\u672a\u5b89\u88c5\u8282\u70b9\u7ea7\u76d1\u63a7\u7ec4\u4ef6 `ags-metrics-collector`\uff0c\u8282\u70b9\u7ea7\u7684\u8d44\u6e90\u6307\u6807\u4e0d\u4f1a\u4e0a\u62a5\u5230\u4e91\u76d1\u63a7\u3002\n\n")
        lines.append("**\u5982\u4f55\u5f00\u542f\u8282\u70b9\u8d44\u6e90\u76d1\u63a7\uff1f**\n\n")
        lines.append("\u5b89\u88c5 `ags-metrics-collector`\uff1a\n\n")
        lines.append("```bash\n")
        lines.append("aliyun cs POST /clusters/{cluster_id}/components/install \\\\\n")
        lines.append("  --region {region} \\\\\n")
        lines.append("  --body '{\"addons\":[{\"name\":\"ags-metrics-collector\"}]}'\n")
        lines.append("```\n\n")
        lines.append("\u9700\u8981 RAM \u6743\u9650 `cs:InstallClusterAddons`\uff0c\u5b89\u88c5\u540e 5-10 \u5206\u949f\u6570\u636e\u5373\u53ef\u4e0a\u62a5\uff0c\u91cd\u65b0\u8fd0\u884c\u5de1\u68c0\u5373\u53ef\u3002\n")
        return "".join(lines)

    lines.append("**\u68c0\u67e5\u539f\u7406**\uff1a\u6bcf\u4e2a\u8282\u70b9\u90fd\u6709\u56fa\u5b9a\u7684\u8d44\u6e90\u603b\u91cf\uff08Capacity\uff09\uff0c")
    lines.append("**\u8d44\u6e90\u5206\u914d\u6bd4\u4f8b** = \u6240\u6709Pod\u7533\u8bf7\u7684Limits\u603b\u548c \u00f7 \u8282\u70b9\u8d44\u6e90\u603b\u91cf \u00d7 100%\u3002\n\n")
    lines.append("| \u8282\u70b9 | CPU\u603b\u91cf(\u6838) | \u5df2\u5206\u914d(\u6838) | \u5206\u914d\u6bd4\u4f8b | \u7ed3\u8bba | \u5185\u5b58\u603b\u91cf(MB) | \u5df2\u5206\u914d(MB) | \u5206\u914d\u6bd4\u4f8b | \u7ed3\u8bba | CPU\u4f7f\u7528\u7387 | \u5185\u5b58\u4f7f\u7528\u7387 |\n")
    lines.append("|------|-----------:|----------:|--------:|:---:|------------:|-----------:|--------:|:---:|:--------:|:--------:|\n")
    for n in limits["nodes"]:
        lines.append("| %s | %s | %s | %s%% | %s | %s | %s | %s%% | %s | %s%% | %s%% |\n" % (
            n["name"][:24], n["cpu"].get("capacity","-"), n["cpu"].get("limit","-"),
            n["cpu"].get("oversale_ratio","-"), n["cpu"].get("level","SAFE"),
            n["memory"].get("capacity","-"), n["memory"].get("limit","-"),
            n["memory"].get("oversale_ratio","-"), n["memory"].get("level","SAFE"),
            n.get("cpu_usage","-"), n.get("mem_usage","-")))
    crit = [n for n in limits["nodes"] if "CRITICAL" in n["cpu"].get("level","") or "CRITICAL" in n["memory"].get("level","")]
    warn = [n for n in limits["nodes"] if "WARNING" in n["cpu"].get("level","") or "WARNING" in n["memory"].get("level","")]
    if crit:
        lines.append("\n### \U0001f534 \u9700\u8981\u7acb\u5373\u5904\u7406\n\n")
        for cn in crit:
            lines.append("**%s**\n" % cn["name"])
            if cn["cpu"].get("oversale_ratio",0) >= 200:
                lines.append("  \u2776 **\u7d27\u6025\u6269\u5bb9**\uff1a\u7acb\u5373\u5411\u8282\u70b9\u6c60\u6dfb\u52a0\u65b0\u8282\u70b9\n")
    if warn:
        lines.append("\n### \U0001f7e1 \u5efa\u8bae\u5173\u6ce8\n\n")
        for wn in warn:
            lines.append("- %s\n" % wn["name"])
    if not crit and not warn:
        lines.append("\n\u2705 **\u6240\u6709\u8282\u70b9\u8d44\u6e90\u5206\u914d\u6b63\u5e38**\uff0c\u65e0\u9700\u5904\u7406\u3002\n\n")
    return "".join(lines)


def _write_topology_health_json(rpt, output_dir):
    """Write simplified health JSON for topo-render.py --health-json."""
    health = {}
    for r in rpt.get("risk_evidence", []):
        rid = r.get("resource_id", "")
        if rid and r.get("risk_level") != "NORMAL":
            health[rid] = {
                "level": r.get("risk_level", "INFO"),
                "type": r.get("resource_type", ""),
                "z_score": r.get("risk_score", 0),
            }
    for c in rpt.get("critical", []):
        health[c["r"]] = {"level": "CRITICAL", "type": c["t"], "z_score": c.get("risk_score", 0)}
    for w in rpt.get("warning", []):
        health[w["r"]] = {"level": "WARNING", "type": w["t"], "z_score": w.get("risk_score", 0)}
    for a in rpt.get("anomaly_scores", []):
        rid = a.get("instance_id", "")
        if rid and rid not in health:
            health[rid] = {"level": a.get("level", "INFO"), "type": a.get("resource_type", ""),
                          "z_score": a.get("z_score", 0)}
    hpath = os.path.join(output_dir, "topology-health.json")
    with open(hpath, "w") as f:
        json.dump(health, f, indent=2, default=str)
    log("RESULT", f"topology health JSON: {len(health)} resources")
    return hpath


def _call_topo_render(health_json_path, output_dir, region):
    """Call topo-scan.sh (from topo-discovery) with health overlay.
    Non-blocking: if topo-scan.sh is missing or fails, log warning and continue."""
    script_dir = Path(__file__).resolve().parent
    topo_sh = script_dir.parent.parent.parent / "alicloud-topo-discovery" / "scripts" / "topo-scan.sh"
    topo_sh = topo_sh.resolve()

    if not topo_sh.exists():
        log("WARN", f"topo-scan.sh not found at {topo_sh}, skipping topology render")
        return None

    topo_output = os.path.abspath(os.path.join(output_dir, "topology"))
    os.makedirs(topo_output, exist_ok=True)

    log("DIAG", f"calling topo-scan.sh --health-json {health_json_path}")
    try:
        # Generate unique tmp dir for concurrent safety
        import tempfile
        topo_tmp = tempfile.mkdtemp(prefix="topo_cruise_", dir="/tmp")
        r = subprocess.run(
            [str(topo_sh), "--mode", "brief", "--health-json", health_json_path,
             "--output-dir", topo_output, "--format", "both", "--region", region,
             "--tmp-dir", topo_tmp],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "TOPO_OUTPUT_DIR": topo_output},
        )
        # Cleanup tmp dir
        import shutil
        shutil.rmtree(topo_tmp, ignore_errors=True)
        if r.returncode != 0:
            log("WARN", f"topo-scan.sh exit={r.returncode}: {r.stderr[:200]}")
            return None
        # Find generated report
        topo_report = os.path.join(topo_output, "report.md")
        if os.path.exists(topo_report):
            with open(topo_report) as f:
                content = f.read()
            log("RESULT", f"topology report: {len(content)} bytes from {topo_report}")
            return content
        else:
            log("WARN", f"topology report not found at {topo_report}")
            return None
    except subprocess.TimeoutExpired:
        log("WARN", "topo-scan.sh timed out after 120s, skipping topology")
        return None
    except Exception as e:
        log("WARN", f"topo-scan.sh error: {e}")
        return None


def _merge_topology_into_report(md_path, topo_content):
    """Merge topology content into the cruise Markdown report."""
    if not topo_content:
        return
    try:
        with open(md_path) as f:
            md = f.read()
        # Insert topology before the last section (optimization suggestions / audit trail)
        marker = "## Critical"
        if marker in md:
            idx = md.index(marker)
            md = md[:idx] + "\n" + topo_content + "\n\n" + md[idx:]
            with open(md_path, "w") as f:
                f.write(md)
            log("RESULT", f"topology merged into {md_path}")
        else:
            log("WARN", "could not find insertion point in report")
    except Exception as e:
        log("WARN", f"merge topology failed: {e}")


def _append_single_resource_topology_note(md_path, resource_id):
    """Avoid merging account-level topology into a single-resource report."""
    try:
        with open(md_path) as f:
            md = f.read()
        marker = "## Critical"
        note = (
            "\n## Topology\n\n"
            f"单资源巡检范围：`{resource_id}`。已跳过账号级拓扑合并，避免将全局 VPC/SLB/EIP 资源清单误认为本次巡检对象。\n\n"
        )
        if marker in md:
            idx = md.index(marker)
            md = md[:idx] + note + md[idx:]
        else:
            md += note
        with open(md_path, "w") as f:
            f.write(md)
        log("RESULT", f"single-resource topology note appended to {md_path}")
    except Exception as e:
        log("WARN", f"append topology note failed: {e}")


def main():
    # Sprint 12 Stage 2 D1: 重入检查 (file lock)
    from lib_idempotent import acquire_lock, release_lock, is_locked
    lock_name = f"daily-health-check.{os.environ.get('CRUISE_LOCK_KEY', 'default')}"
    if not acquire_lock(lock_name, ttl=900):  # 15 分钟
        print(f"[ERROR] TYPE=LOCKED FIX=有其他 daily-health-check 正在运行 (is_locked={is_locked(lock_name)})")
        sys.exit(10)
    try:
        _main_locked()
    finally:
        release_lock(lock_name)


def _main_locked():
    ap = argparse.ArgumentParser(description="全量健康巡检")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--resource-group-id")
    g.add_argument("--tag-key")
    ap.add_argument("--tag-value")
    ap.add_argument("--resource-id")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", ""))
    ap.add_argument("--customer", default="")
    ap.add_argument("--output-dir", default=_shared._resolve_runbooks_output_dir())
    ap.add_argument("--include")
    ap.add_argument("--skip")
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--no-cache", action="store_true", help="Sprint 8: bypass result cache")
    args = ap.parse_args()
    print(f"\n{'=' * 50}\n  {os.path.basename(__file__)} v2.3.1\n{'=' * 50}")
    if args.describe:
        print("Phase 0: 资源发现 -> Phase 0.5: 确认 -> Phase 1+2: 采集+评分 -> Phase 3: 报告")
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
    # Phase 0.5: 数据可用性预检
    now = datetime.now(UTC)
    end_ts = normalize_time_to_bucket(now.replace(tzinfo=None), 5)  # already formatted string
    h6_ts = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    preflight_data = _preflight_check(selected, region, h6_ts, end_ts)
    metrics, anomalies, baseline_data, ack_data = collect_and_score(selected, region)
    md, js, rpt = report(selected, metrics, anomalies, args, ack_data, baseline_data, preflight_data)
    # Phase 4: 拓扑渲染（非阻塞）
    hpath = _write_topology_health_json(rpt, args.output_dir)
    if args.resource_id:
        log("DIAG", f"skip account-level topology render for single resource={args.resource_id}")
        _append_single_resource_topology_note(md, args.resource_id)
    else:
        topo_content = _call_topo_render(hpath, args.output_dir, region)
        _merge_topology_into_report(md, topo_content)
    print(f"\n{'=' * 50}\n  完成: {md}\n{'=' * 50}")
    log("DIAG", f"cache_stats: {cache_stats()}")
    sys.exit(
        exit_code(
            len(discovered) > 0, len(rpt.get("critical", [])) + sum(1 for a in anomalies if a.get("l") == "CRITICAL")
        )
    )


if __name__ == "__main__":
    main()
