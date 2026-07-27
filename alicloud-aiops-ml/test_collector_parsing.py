"""Tests for collector parsing logic — CMS datapoints, instance parsing, edge cases."""
from __future__ import annotations

import json

import pytest

from ecs_collector import _parse_cms_datapoints, _sum_disk, _get_tag
from db_collector import _parse_rds, _parse_redis
from net_collector import _parse_slb, _parse_oss_line, _parse_k8s_node
from resource_model import Resource


# ------------------------------------------------------------------
# CMS Datapoints Parsing
# ------------------------------------------------------------------

class TestParseCmsDatapoints:
    """Tests for _parse_cms_datapoints — pure function for CMS response parsing."""

    def test_empty_datapoints_returns_zero(self) -> None:
        assert _parse_cms_datapoints({"Datapoints": ""}) == 0.0
        assert _parse_cms_datapoints({}) == 0.0

    def test_parsed_list_with_average(self) -> None:
        data = {
            "Datapoints": [
                {"timestamp": 1784505600000, "Average": 4.5, "Minimum": 3.0, "Maximum": 6.0},
                {"timestamp": 1784592000000, "Average": 5.2, "Minimum": 4.0, "Maximum": 7.0},
            ]
        }
        result = _parse_cms_datapoints(data)
        assert result == pytest.approx(4.85)

    def test_single_datapoint(self) -> None:
        data = {"Datapoints": [{"Average": 10.0}]}
        assert _parse_cms_datapoints(data) == 10.0

    def test_datapoint_missing_average_key(self) -> None:
        data = {"Datapoints": [{"timestamp": 123, "Minimum": 1.0}]}
        assert _parse_cms_datapoints(data) == 0.0

    def test_datapoint_average_is_none(self) -> None:
        data = {"Datapoints": [{"Average": None}]}
        assert _parse_cms_datapoints(data) == 0.0

    def test_string_encoded_json(self) -> None:
        dps_str = json.dumps([
            {"Average": 3.0},
            {"Average": 7.0},
        ])
        data = {"Datapoints": dps_str}
        assert _parse_cms_datapoints(data) == 5.0

    def test_string_encoded_single_value(self) -> None:
        data = {"Datapoints": json.dumps([{"Average": 42.0}])}
        assert _parse_cms_datapoints(data) == 42.0

    def test_dict_type_datapoints(self) -> None:
        data = {"Datapoints": {"key1": 10.0, "key2": 20.0}}
        assert _parse_cms_datapoints(data) == 15.0

    def test_non_numeric_average_skipped(self) -> None:
        data = {
            "Datapoints": [
                {"Average": 5.0},
                {"Average": "N/A"},
                {"Average": 10.0},
            ]
        }
        assert _parse_cms_datapoints(data) == 7.5

    def test_mixed_valid_invalid(self) -> None:
        data = {
            "Datapoints": [
                {"Average": 10.0},
                {"Average": None},
                {"timestamp": 123},
                {"Average": 20.0},
            ]
        }
        assert _parse_cms_datapoints(data) == 15.0

    def test_invalid_json_string(self) -> None:
        data = {"Datapoints": "not valid json"}
        assert _parse_cms_datapoints(data) == 0.0

    def test_empty_list(self) -> None:
        data = {"Datapoints": []}
        assert _parse_cms_datapoints(data) == 0.0


# ------------------------------------------------------------------
# ECS Instance Parsing
# ------------------------------------------------------------------

class TestEcsSumDisk:
    """Tests for _sum_disk — disk size aggregation."""

    def test_single_disk(self) -> None:
        inst = {"Disks": {"Disk": [{"Size": 40}]}}
        assert _sum_disk(inst) == 40.0

    def test_multiple_disks(self) -> None:
        inst = {"Disks": {"Disk": [{"Size": 40}, {"Size": 100}]}}
        assert _sum_disk(inst) == 140.0

    def test_no_disks(self) -> None:
        assert _sum_disk({}) == 0.0
        assert _sum_disk({"Disks": {}}) == 0.0

    def test_size_with_unit(self) -> None:
        inst = {"Disks": {"Disk": [{"Size": "40GiB"}]}}
        assert _sum_disk(inst) == 40.0

    def test_invalid_size_skipped(self) -> None:
        inst = {"Disks": {"Disk": [{"Size": 40}, {"Size": "invalid"}]}}
        assert _sum_disk(inst) == 40.0


class TestEcsGetTag:
    """Tests for _get_tag — tag extraction from ECS Tags array."""

    def test_found(self) -> None:
        inst = {"Tags": {"Tag": [{"Key": "env", "Value": "production"}]}}
        assert _get_tag(inst, "env") == "production"

    def test_not_found(self) -> None:
        inst = {"Tags": {"Tag": [{"Key": "env", "Value": "production"}]}}
        assert _get_tag(inst, "product") == "unknown"

    def test_no_tags(self) -> None:
        assert _get_tag({}, "env") == "unknown"

    def test_multiple_tags(self) -> None:
        inst = {
            "Tags": {
                "Tag": [
                    {"Key": "env", "Value": "production"},
                    {"Key": "product", "Value": "app-x"},
                ]
            }
        }
        assert _get_tag(inst, "env") == "production"
        assert _get_tag(inst, "product") == "app-x"


# ------------------------------------------------------------------
# RDS Instance Parsing
# ------------------------------------------------------------------

class TestParseRds:
    """Tests for _parse_rds — RDS JSON to Resource conversion."""

    def test_basic(self) -> None:
        inst = {
            "DBInstanceId": "rm-xxx",
            "DBInstanceDescription": "test-db",
            "DBInstanceType": "Primary",
            "DBInstanceCPU": 4,
            "DBInstanceMemory": 16384,  # kB
            "DBInstanceStorage": 100,
            "PayType": "Postpaid",
        }
        r = _parse_rds(inst)
        assert r.resource_id == "rm-xxx"
        assert r.resource_type == "rds"
        assert r.instance_name == "test-db"
        assert r.cpu_cores == 4
        assert r.memory_gb == 16.0  # 16384 / 1024
        assert r.disk_gb == 100.0
        assert r.is_prepaid == 0

    def test_prepaid(self) -> None:
        inst = {
            "DBInstanceId": "rm-yyy",
            "DBInstanceType": "Primary",
            "DBInstanceCPU": 2,
            "DBInstanceMemory": 8192,
            "DBInstanceStorage": 50,
            "PayType": "Prepaid",
            "ExpireTime": "2026-12-31T00:00:00Z",
        }
        r = _parse_rds(inst)
        assert r.is_prepaid == 1
        assert r.days_until_expire > 0

    def test_zero_memory(self) -> None:
        inst = {
            "DBInstanceId": "rm-zzz",
            "DBInstanceType": "Primary",
            "DBInstanceCPU": 1,
            "DBInstanceMemory": 0,
            "DBInstanceStorage": 10,
            "PayType": "Postpaid",
        }
        r = _parse_rds(inst)
        assert r.memory_gb == 0.0


# ------------------------------------------------------------------
# Redis Instance Parsing
# ------------------------------------------------------------------

class TestParseRedis:
    """Tests for _parse_redis — Redis JSON to Resource conversion."""

    def test_basic(self) -> None:
        inst = {
            "InstanceId": "r-xxx",
            "InstanceName": "test-redis",
            "InstanceType": "Standard",
            "Capacity": 16384,  # MB
            "InstanceChargeType": "PostPaid",
        }
        r = _parse_redis(inst)
        assert r.resource_id == "r-xxx"
        assert r.resource_type == "redis"
        assert r.memory_gb == 16384.0
        assert r.is_prepaid == 0

    def test_prepaid(self) -> None:
        inst = {
            "InstanceId": "r-yyy",
            "InstanceType": "Cluster",
            "Capacity": 32768,
            "InstanceChargeType": "PrePaid",
            "EndTime": "2026-12-31T00:00:00Z",
        }
        r = _parse_redis(inst)
        assert r.is_prepaid == 1
        assert r.days_until_expire > 0

    def test_capacity_string(self) -> None:
        inst = {
            "InstanceId": "r-zzz",
            "InstanceType": "Standard",
            "Capacity": "8192",
            "InstanceChargeType": "PostPaid",
        }
        r = _parse_redis(inst)
        assert r.memory_gb == 8192.0

    def test_capacity_invalid(self) -> None:
        inst = {
            "InstanceId": "r-xxx",
            "InstanceType": "Standard",
            "Capacity": "N/A",
            "InstanceChargeType": "PostPaid",
        }
        r = _parse_redis(inst)
        assert r.memory_gb == 0.0


# ------------------------------------------------------------------
# SLB Parsing
# ------------------------------------------------------------------

class TestParseSlb:
    """Tests for _parse_slb — SLB JSON to Resource conversion."""

    def test_internet_slb(self) -> None:
        inst = {
            "LoadBalancerId": "lb-xxx",
            "LoadBalancerName": "test-slb",
            "AddressType": "internet",
        }
        r = _parse_slb(inst)
        assert r.resource_id == "lb-xxx"
        assert r.resource_type == "slb"
        assert r.instance_type == "internet"
        assert r.monthly_cost == 100.0

    def test_intranet_slb(self) -> None:
        inst = {
            "LoadBalancerId": "lb-yyy",
            "LoadBalancerName": "internal-slb",
            "AddressType": "intranet",
        }
        r = _parse_slb(inst)
        assert r.monthly_cost == 0.0


# ------------------------------------------------------------------
# OSS Line Parsing
# ------------------------------------------------------------------

class TestParseOssLine:
    """Tests for _parse_oss_line — oss ls text output parsing."""

    def test_basic(self) -> None:
        line = "oss://my-bucket"
        r = _parse_oss_line(line)
        assert r.resource_id == "my-bucket"
        assert r.resource_type == "oss"
        assert r.instance_type == "bucket"

    def test_multiple_tokens(self) -> None:
        line = "oss://my-bucket 2026-01-01 Standard"
        r = _parse_oss_line(line)
        assert r.resource_id == "my-bucket"

    def test_empty_line(self) -> None:
        r = _parse_oss_line("")
        assert r.resource_id == ""


# ------------------------------------------------------------------
# K8s Node Parsing
# ------------------------------------------------------------------

class TestParseK8sNode:
    """Tests for _parse_k8s_node — K8s node JSON to Resource conversion."""

    def test_basic(self) -> None:
        node = {
            "node_id": "node-xxx",
            "name": "worker-1",
            "instance_type": "ecs.n4.large",
            "cpu": 2,
            "memory": 8589934592,  # bytes (8 GiB)
            "disk": 42949672960,   # bytes (40 GiB)
        }
        r = _parse_k8s_node(node)
        assert r.resource_id == "node-xxx"
        assert r.resource_type == "k8s_node"
        assert r.instance_name == "worker-1"
        assert r.cpu_cores == 2
        # 8589934592 / 1024 / 1024 / 1024 = 8.0
        assert r.memory_gb == pytest.approx(8.0, rel=1e-3)
        # 42949672960 / 1024 / 1024 / 1024 = 40.0
        assert r.disk_gb == pytest.approx(40.0, rel=1e-3)

    def test_zero_values(self) -> None:
        node = {
            "node_id": "node-zzz",
            "cpu": 0,
            "memory": 0,
            "disk": 0,
        }
        r = _parse_k8s_node(node)
        assert r.cpu_cores == 0
        assert r.memory_gb == 0.0
        assert r.disk_gb == 0.0

    def test_missing_fields(self) -> None:
        node: dict = {}
        r = _parse_k8s_node(node)
        assert r.resource_id == ""
        assert r.cpu_cores == 0
        assert r.memory_gb == 0.0
