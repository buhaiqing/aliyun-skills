"""SLB, OSS, and K8s resource collector."""
from __future__ import annotations

from typing import Any

from resource_model import Resource
from cli_utils import cli_call


def collect_slb_resources(region: str) -> list[Resource]:
    """Collect SLB instances from a region."""
    cmd = f"aliyun slb DescribeLoadBalancers --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    return [_parse_slb(i) for i in data.get("LoadBalancers", {}).get("LoadBalancer", [])]


def collect_oss_buckets(region: str) -> list[Resource]:
    """Collect OSS buckets (region-filtered)."""
    cmd = f"aliyun oss ls --region {region}"
    result = cli_call(cmd, parse_json=False)
    if result is None:
        return []
    return [_parse_oss_line(line) for line in result.splitlines() if line.strip().startswith("oss://")]


def _parse_oss_line(line: str) -> Resource:
    """Parse a single oss ls output line."""
    parts = line.split()
    bucket_name = parts[0].replace("oss://", "") if parts else ""
    return Resource(
        resource_id=bucket_name,
        resource_type="oss",
        instance_name=bucket_name,
        instance_type="bucket",
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=0.0,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=0,
        days_until_expire=0,
    )


def collect_k8s_nodes(region: str) -> list[Resource]:
    """Collect ACK cluster nodes."""
    cmd = f"aliyun cs DescribeClusters --RegionId {region} --output json"
    data = cli_call(cmd) or {}
    clusters = data.get("clusters", [])
    nodes = []
    for cluster in clusters:
        cid = cluster.get("cluster_id")
        if cid:
            nodes.extend(_fetch_cluster_nodes(region, cid))
    return nodes


def _fetch_cluster_nodes(region: str, cluster_id: str) -> list[Resource]:
    cmd = f"aliyun cs DescribeClusterNodes --RegionId {region} --ClusterId {cluster_id} --output json"
    data = cli_call(cmd) or {}
    return [_parse_k8s_node(n) for n in data.get("nodes", [])]


def _parse_slb(inst: dict[str, Any]) -> Resource:
    return Resource(
        resource_id=inst.get("LoadBalancerId", ""),
        resource_type="slb",
        instance_name=inst.get("LoadBalancerName", ""),
        instance_type=inst.get("AddressType", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=0.0,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=0,
        days_until_expire=0,
    )


def _parse_oss(bucket: dict[str, Any]) -> Resource:
    return Resource(
        resource_id=bucket.get("Name", ""),
        resource_type="oss",
        instance_name=bucket.get("Name", ""),
        instance_type="bucket",
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=0,
        memory_gb=0.0,
        disk_gb=0.0,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=0,
        days_until_expire=0,
    )


def _parse_k8s_node(node: dict[str, Any]) -> Resource:
    return Resource(
        resource_id=node.get("node_id", ""),
        resource_type="k8s_node",
        instance_name=node.get("name", ""),
        instance_type=node.get("instance_type", ""),
        product="unknown",
        env="unknown",
        owner="unknown",
        cpu_cores=int(node.get("cpu", 0)),
        memory_gb=float(node.get("memory", 0)) / 1024 / 1024 / 1024,
        disk_gb=float(node.get("disk", 0)) / 1024 / 1024 / 1024,
        cpu_util_avg=0.0,
        mem_util_avg=0.0,
        disk_util_avg=0.0,
        iops_util_avg=0.0,
        net_in_avg=0.0,
        net_out_avg=0.0,
        monthly_cost=0.0,
        is_prepaid=0,
        days_until_expire=0,
    )
