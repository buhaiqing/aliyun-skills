#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reverse_engineering.py — Import Existing Resources to Terraform

Implements Reverse Engineering feature for alicloud-terraform-ops skill.
Queries existing Alibaba Cloud resources and generates Terraform HCL + import scripts.

Features:
- Resource discovery via aliyun CLI
- HCL configuration generation
- terraform import script generation
- Dry-run mode for validation
- GCL integration

USAGE
-----
    # Import single resource
    python reverse_engineering.py \\
        --resource-type vpc \\
        --resource-id vpc-bp1xxxxxxxx \\
        --region cn-hangzhou

    # Import multiple resources
    python reverse_engineering.py \\
        --resource-type vpc \\
        --resource-ids vpc-bp1xxx,vpc-bp2xxx \\
        --region cn-hangzhou

    # Dry-run mode (generate only, no import)
    python reverse_engineering.py \\
        --resource-type vpc \\
        --resource-id vpc-bp1xxxxxxxx \\
        --dry-run

    # Auto-discover associated resources
    python reverse_engineering.py \\
        --resource-type vpc \\
        --resource-id vpc-bp1xxxxxxxx \\
        --discover-associated

EXIT CODES
----------
    0  SUCCESS
    1  RESOURCE_NOT_FOUND
    2  API_ERROR
    3  GENERATION_ERROR
    4  VALIDATION_ERROR
    5  GCL_REJECT

REQUIREMENTS
------------
    Python 3.10+ stdlib. External: aliyun CLI, terraform CLI
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import resource registry for PreFlight checks
from resource_registry import (
    ResourceRegistry, 
    CapabilityChecker, 
    SupportLevel,
    ResourceCapability,
    get_registry
)


# Allowed terraform subcommands during dry-run mode. All others are mocked.
TERRAFORM_DRY_RUN_ALLOWED = frozenset({"init", "validate", "plan"})


# ANSI colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_dry_run_banner():
    """Print dry-run banner."""
    banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║              🔍 DRY-RUN MODE (干运行模式)                        ║
║      此执行仅用于预览和验证，未修改 Terraform 状态              ║
╚════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def log_dry_run(phase: str, message: str, is_error: bool = False):
    """Log with dry-run prefix."""
    prefix = f"{Colors.CYAN}[DRY-RUN]{Colors.END}"
    color = Colors.RED if is_error else Colors.END
    print(f"{prefix} [{phase}] {color}{message}{Colors.END}")


def make_tf_name(resource_type: str, resource_id: str) -> str:
    """与 import.sh 一致的 Terraform resource 块名称。"""
    id_suffix = resource_id.split("-")[-1][:8] if "-" in resource_id else resource_id[:8]
    safe_suffix = re.sub(r"[^a-zA-Z0-9_]", "", id_suffix) or "resource"
    return f"imported_{resource_type}_{safe_suffix}"


class ResourceReferenceRegistry:
    """同一批次导入资源：cloud ID → Terraform 资源引用。"""

    def __init__(self) -> None:
        self._entries: Dict[str, Tuple[str, str]] = {}

    def register(self, cloud_id: str, tf_type: str, tf_name: str) -> None:
        if cloud_id:
            self._entries[cloud_id] = (tf_type, tf_name)

    def reference(self, cloud_id: str, attribute: str = "id") -> Optional[str]:
        if not cloud_id:
            return None
        entry = self._entries.get(cloud_id)
        if not entry:
            return None
        tf_type, tf_name = entry
        return f"{tf_type}.{tf_name}.{attribute}"

    def hcl_value(self, cloud_id: str, attribute: str = "id", mark_external: bool = True) -> str:
        ref = self.reference(cloud_id, attribute)
        if ref:
            return ref
        if cloud_id:
            if mark_external and self._entries:
                return f'"{cloud_id}"  # external: not in import batch'
            return f'"{cloud_id}"'
        return '""'

    def is_registered(self, cloud_id: str) -> bool:
        return bool(cloud_id and cloud_id in self._entries)


class ResourceMapper:
    """Maps Alibaba Cloud API responses to Terraform HCL."""

    # Resource type to API mappings
    RESOURCE_APIS = {
        "vpc": {
            "product": "vpc",
            "describe": "DescribeVpcAttribute",
            "id_param": "VpcId",
            "tf_type": "alicloud_vpc",
        },
        "vswitch": {
            "product": "vpc",
            "describe": "DescribeVSwitchAttributes",
            "id_param": "VSwitchId",
            "tf_type": "alicloud_vswitch",
        },
        "ecs": {
            "product": "ecs",
            "describe": "DescribeInstances",
            "id_param": "InstanceIds",
            "tf_type": "alicloud_instance",
        },
        "rds": {
            "product": "rds",
            "describe": "DescribeDBInstanceAttribute",
            "id_param": "DBInstanceId",
            "tf_type": "alicloud_db_instance",
        },
        "redis": {
            "product": "r-kvstore",
            "describe": "DescribeInstanceAttribute",
            "id_param": "InstanceId",
            "tf_type": "alicloud_kvstore_instance",
        },
        "slb": {
            "product": "slb",
            "describe": "DescribeLoadBalancerAttribute",
            "id_param": "LoadBalancerId",
            "tf_type": "alicloud_slb",
        },
        "eip": {
            "product": "vpc",
            "describe": "DescribeEipAddresses",
            "id_param": "AllocationId",
            "tf_type": "alicloud_eip",
        },
        "security_group": {
            "product": "ecs",
            "describe": "DescribeSecurityGroupAttribute",
            "id_param": "SecurityGroupId",
            "tf_type": "alicloud_security_group",
        },
        "nat_gateway": {
            "product": "vpc",
            "describe": "DescribeNatGateways",
            "id_param": "NatGatewayId",
            "tf_type": "alicloud_nat_gateway",
            "list_key": ("NatGateways", "NatGateway"),
        },
        "mongodb": {
            "product": "dds",
            "describe": "DescribeDBInstanceAttribute",
            "id_param": "DBInstanceId",
            "tf_type": "alicloud_mongodb_instance",
        },
        "polardb": {
            "product": "polardb",
            "describe": "DescribeDBClusterAttribute",
            "id_param": "DBClusterId",
            "tf_type": "alicloud_polardb_cluster",
        },
        "oss": {
            "product": "oss",
            "describe": "GetBucketInfo",
            "id_param": "Bucket",
            "tf_type": "alicloud_oss_bucket",
            "is_bucket": True,
        },
        "disk": {
            "product": "ecs",
            "describe": "DescribeDisks",
            "id_param": "DiskIds",
            "tf_type": "alicloud_disk",
        },
        "route_table": {
            "product": "vpc",
            "describe": "DescribeRouteTableAttribute",
            "id_param": "RouteTableId",
            "tf_type": "alicloud_route_table",
        },
    }

    def __init__(self, region: str = "cn-hangzhou"):
        self.region = region

    @staticmethod
    def extract_cloud_id(resource_type: str, data: Dict) -> str:
        """从 API 响应提取云资源 ID。"""
        if resource_type == "vpc":
            return data.get("Vpc", {}).get("VpcId", "")
        if resource_type == "vswitch":
            return data.get("VSwitch", {}).get("VSwitchId", "")
        if resource_type == "ecs":
            instances = data.get("Instances", {}).get("Instance", [])
            return instances[0].get("InstanceId", "") if instances else ""
        if resource_type == "rds":
            db = data.get("Items", {}).get("DBInstanceAttribute", [{}])[0]
            if not db:
                db = data.get("DBInstanceAttribute", {})
            return db.get("DBInstanceId", "")
        if resource_type == "redis":
            inst = data.get("Instances", {}).get("KVStoreInstance", [{}])[0]
            if not inst:
                inst = data.get("Instance", {})
            return inst.get("InstanceId", "")
        if resource_type == "slb":
            return data.get("LoadBalancer", {}).get("LoadBalancerId", "")
        if resource_type == "eip":
            eips = data.get("EipAddresses", {}).get("EipAddress", [])
            return eips[0].get("AllocationId", "") if eips else ""
        if resource_type == "security_group":
            return data.get("SecurityGroup", {}).get("SecurityGroupId", "")
        if resource_type == "nat_gateway":
            nat = data.get("NatGateway", data)
            return nat.get("NatGatewayId", "")
        if resource_type == "mongodb":
            inst = data.get("DBInstances", {}).get("DBInstance", [{}])[0]
            if not inst:
                inst = data.get("DBInstance", data.get("Items", {}).get("DBInstanceAttribute", [{}])[0])
            return inst.get("DBInstanceId", "")
        if resource_type == "polardb":
            cluster = data.get("Items", {}).get("DBCluster", [{}])[0]
            if not cluster:
                cluster = data.get("DBCluster", data)
            return cluster.get("DBClusterId", "")
        if resource_type == "disk":
            disk = data.get("Disk", data.get("Disks", {}).get("Disk", [{}]))
            if isinstance(disk, list):
                disk = disk[0] if disk else {}
            return disk.get("DiskId", "")
        if resource_type == "route_table":
            rt = data.get("RouteTable", data)
            if isinstance(rt, list):
                rt = rt[0] if rt else {}
            return rt.get("RouteTableId", "")
        if resource_type == "oss":
            return data.get("BucketName", data.get("Bucket", {}).get("Name", ""))
        return data.get("id", "")

    def _sanitize_tf_name(self, name: str, prefix: str) -> str:
        tf_name = re.sub(r"[^a-zA-Z0-9_]", "_", name or "")
        if not tf_name or tf_name[0].isdigit():
            tf_name = f"{prefix}{tf_name}" if tf_name else prefix.rstrip("_")
        return tf_name

    def _hcl_ref(self, refs: Optional[ResourceReferenceRegistry], cloud_id: str) -> str:
        if refs:
            return refs.hcl_value(cloud_id)
        if cloud_id:
            return f'"{cloud_id}"'
        return '""'

    @staticmethod
    def extract_attached_instance_id(data: Dict) -> Optional[str]:
        disk = data.get("Disk", data.get("Disks", {}).get("Disk", [{}]))
        if isinstance(disk, list):
            disk = disk[0] if disk else {}
        instance_id = disk.get("InstanceId")
        if instance_id:
            return instance_id
        attached = disk.get("AttachedTo") or {}
        if isinstance(attached, dict):
            return attached.get("InstanceId")
        return None

    def disk_attachment_to_hcl(
        self,
        disk_id: str,
        instance_id: str,
        disk_tf_name: str,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        attach_tf_name = f"attach_{disk_tf_name.replace('imported_disk_', '', 1)}"
        instance_ref = self._hcl_ref(refs, instance_id)
        return textwrap.dedent(f"""\
            # Disk attachment: {disk_id} -> {instance_id}
            resource "alicloud_disk_attachment" "{attach_tf_name}" {{
              disk_id     = alicloud_disk.{disk_tf_name}.id
              instance_id = {instance_ref}

              lifecycle {{
                prevent_destroy = true
              }}
            }}
        """)

    def query_resource(self, resource_type: str, resource_id: str) -> Optional[Dict]:
        """Query resource details via aliyun CLI."""
        mapping = self.RESOURCE_APIS.get(resource_type)
        if not mapping:
            return None

        cmd = ["aliyun", mapping["product"], mapping["describe"]]

        if mapping.get("is_bucket"):
            cmd.extend([f"--{mapping['id_param']}", resource_id])
        else:
            cmd.extend(["--RegionId", self.region])
            id_val = resource_id
            if resource_type in ("ecs", "disk"):
                id_val = json.dumps([resource_id])
            cmd.extend([f"--{mapping['id_param']}", id_val])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return {"error": result.stderr, "id": resource_id}

            data = json.loads(result.stdout)
            if resource_type == "nat_gateway" and "NatGateways" in data:
                gateways = data.get("NatGateways", {}).get("NatGateway", [])
                if gateways:
                    data = {"NatGateway": gateways[0]}
            if resource_type == "oss":
                data.setdefault("BucketName", resource_id)
            if resource_type == "disk" and "Disks" in data:
                disks = data.get("Disks", {}).get("Disk", [])
                if disks:
                    data = {"Disk": disks[0]}
            if resource_type == "route_table" and "RouteTable" not in data:
                tables = data.get("RouteTables", {}).get("RouteTable", [])
                if tables:
                    data = {"RouteTable": tables[0]}
            return data
        except Exception as e:
            return {"error": str(e), "id": resource_id}

    def discover_associated(self, resource_type: str, resource_id: str) -> List[Dict]:
        """Discover associated resources."""
        associated: List[Dict] = []
        seen: set = set()

        def _add(items: List[Dict]) -> None:
            for item in items:
                key = (item["type"], item["id"])
                if key not in seen and item["type"] in self.RESOURCE_APIS:
                    seen.add(key)
                    associated.append(item)

        if resource_type == "vpc":
            _add(self._query_vswitches(resource_id))
            _add(self._query_route_tables(resource_id))
            _add(self._query_nat_gateways(resource_id))

        elif resource_type == "ecs":
            data = self.query_resource("ecs", resource_id)
            if data and "error" not in data:
                _add(self._discover_from_ecs(data))

        elif resource_type == "slb":
            data = self.query_resource("slb", resource_id)
            if data and "error" not in data:
                _add(self._discover_from_slb(data))

        elif resource_type == "rds":
            data = self.query_resource("rds", resource_id)
            if data and "error" not in data:
                _add(self._discover_from_rds(data))

        return associated

    def _query_vswitches(self, vpc_id: str) -> List[Dict]:
        """Query vSwitches in VPC."""
        cmd = [
            "aliyun", "vpc", "DescribeVSwitches",
            "--RegionId", self.region,
            "--VpcId", vpc_id,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                vswitches = data.get("VSwitches", {}).get("VSwitch", [])
                return [
                    {"type": "vswitch", "id": vs["VSwitchId"], "name": vs.get("VSwitchName", "")}
                    for vs in vswitches
                ]
            else:
                log_dry_run("ERROR", f"查询 VPC {vpc_id} 的 VSwitch 失败: {result.stderr}", is_error=True)
        except subprocess.TimeoutExpired:
            log_dry_run("ERROR", f"查询 VPC {vpc_id} 的 VSwitch 超时", is_error=True)
        except json.JSONDecodeError as e:
            log_dry_run("ERROR", f"解析 VSwitch 响应失败: {e}", is_error=True)
        except Exception as e:
            log_dry_run("ERROR", f"查询 VSwitch 时出错: {e}", is_error=True)

        return []

    def _query_route_tables(self, vpc_id: str) -> List[Dict]:
        """Query route tables in VPC."""
        cmd = [
            "aliyun", "vpc", "DescribeRouteTables",
            "--RegionId", self.region,
            "--VpcId", vpc_id,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                tables = data.get("RouteTables", {}).get("RouteTable", [])
                return [
                    {"type": "route_table", "id": rt["RouteTableId"], "name": rt.get("RouteTableName", "")}
                    for rt in tables
                ]
            else:
                log_dry_run("ERROR", f"查询 VPC {vpc_id} 的 RouteTable 失败: {result.stderr}", is_error=True)
        except subprocess.TimeoutExpired:
            log_dry_run("ERROR", f"查询 VPC {vpc_id} 的 RouteTable 超时", is_error=True)
        except json.JSONDecodeError as e:
            log_dry_run("ERROR", f"解析 RouteTable 响应失败: {e}", is_error=True)
        except Exception as e:
            log_dry_run("ERROR", f"查询 RouteTable 时出错: {e}", is_error=True)

        return []

    def _query_nat_gateways(self, vpc_id: str) -> List[Dict]:
        """Query NAT gateways in VPC."""
        cmd = [
            "aliyun", "vpc", "DescribeNatGateways",
            "--RegionId", self.region,
            "--VpcId", vpc_id,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                gateways = data.get("NatGateways", {}).get("NatGateway", [])
                return [
                    {
                        "type": "nat_gateway",
                        "id": g["NatGatewayId"],
                        "name": g.get("Name", g.get("NatGatewayName", "")),
                    }
                    for g in gateways
                ]
        except Exception as e:
            log_dry_run("ERROR", f"查询 NAT Gateway 失败: {e}", is_error=True)
        return []

    def _discover_from_ecs(self, data: Dict) -> List[Dict]:
        """Discover resources linked to an ECS instance."""
        instances = data.get("Instances", {}).get("Instance", [])
        if not instances:
            return []
        instance = instances[0]
        found: List[Dict] = []

        vswitch_ids = instance.get("VpcAttributes", {}).get("VSwitchId", [])
        for vsid in vswitch_ids:
            if vsid:
                found.append({"type": "vswitch", "id": vsid, "name": ""})

        sg_ids = instance.get("SecurityGroupIds", {}).get("SecurityGroupId", [])
        for sgid in sg_ids:
            if sgid:
                found.append({"type": "security_group", "id": sgid, "name": ""})

        disks = instance.get("Disks", {}).get("Disk", [])
        for disk in disks:
            disk_id = disk.get("DiskId")
            disk_type = (disk.get("Type") or "").lower()
            # 系统盘由 ECS 资源内联管理，仅发现独立数据盘
            if disk_id and disk_type != "system":
                found.append({"type": "disk", "id": disk_id, "name": disk.get("Device", "")})

        return found

    def _discover_from_slb(self, data: Dict) -> List[Dict]:
        """Discover backend servers and network links for SLB."""
        lb = data.get("LoadBalancer", {})
        found: List[Dict] = []
        vswitch_id = lb.get("VSwitchId")
        vpc_id = lb.get("VpcId")
        if vswitch_id:
            found.append({"type": "vswitch", "id": vswitch_id, "name": ""})
        if vpc_id:
            found.append({"type": "vpc", "id": vpc_id, "name": ""})

        backends = data.get("BackendServers", {}).get("BackendServer", [])
        for b in backends:
            server_id = b.get("ServerId")
            if server_id and server_id.startswith("i-"):
                found.append({"type": "ecs", "id": server_id, "name": b.get("ServerIp", "")})
        return found

    def _discover_from_rds(self, data: Dict) -> List[Dict]:
        """Discover network dependencies for RDS."""
        db = data.get("Items", {}).get("DBInstanceAttribute", [{}])[0]
        if not db:
            db = data.get("DBInstanceAttribute", {})
        found: List[Dict] = []
        vswitch_id = db.get("VSwitchId")
        vpc_id = db.get("VpcId")
        if vswitch_id:
            found.append({"type": "vswitch", "id": vswitch_id, "name": ""})
        if vpc_id:
            found.append({"type": "vpc", "id": vpc_id, "name": ""})
        return found

    def to_hcl(
        self,
        resource_type: str,
        resource_data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert API response to HCL."""
        kwargs = {"tf_name": tf_name, "refs": refs}
        if resource_type == "vpc":
            return self._vpc_to_hcl(resource_data, **kwargs)
        elif resource_type == "vswitch":
            return self._vswitch_to_hcl(resource_data, **kwargs)
        elif resource_type == "ecs":
            return self._ecs_to_hcl(resource_data, **kwargs)
        elif resource_type == "rds":
            return self._rds_to_hcl(resource_data, **kwargs)
        elif resource_type == "redis":
            return self._redis_to_hcl(resource_data, **kwargs)
        elif resource_type == "slb":
            return self._slb_to_hcl(resource_data, **kwargs)
        elif resource_type == "eip":
            return self._eip_to_hcl(resource_data, **kwargs)
        elif resource_type == "security_group":
            return self._sg_to_hcl(resource_data, **kwargs)
        elif resource_type == "nat_gateway":
            return self._nat_to_hcl(resource_data, **kwargs)
        elif resource_type == "mongodb":
            return self._mongodb_to_hcl(resource_data, **kwargs)
        elif resource_type == "polardb":
            return self._polardb_to_hcl(resource_data, **kwargs)
        elif resource_type == "oss":
            return self._oss_to_hcl(resource_data, **kwargs)
        elif resource_type == "disk":
            return self._disk_to_hcl(resource_data, **kwargs)
        elif resource_type == "route_table":
            return self._route_table_to_hcl(resource_data, **kwargs)
        else:
            return f"# Unsupported resource type for HCL: {resource_type}\n"

    def _vpc_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert VPC API response to HCL."""
        vpc = data.get("Vpc", {})
        vpc_id = vpc.get("VpcId", "")
        vpc_name = vpc.get("VpcName", "imported-vpc")
        cidr = vpc.get("CidrBlock", "")
        description = vpc.get("Description", "")

        # Sanitize name for terraform
        if not tf_name:
            tf_name = self._sanitize_tf_name(vpc_name, "vpc_")

        hcl_lines = [
            f'# Imported VPC: {vpc_id}',
            f'resource "alicloud_vpc" "{tf_name}" {{',
            f'  vpc_name   = "{vpc_name}"',
            f'  cidr_block = "{cidr}"',
        ]

        if description:
            hcl_lines.append(f'  description = "{description}"')

        hcl_lines.extend([
            '',
            '  # Import only - prevent accidental deletion',
            '  lifecycle {',
            '    prevent_destroy = true',
            '  }',
            '',
            '  tags = {',
            '    ImportedBy = "terraform-reverse-engineering"',
            '  }',
            '}',
        ])

        return "\n".join(hcl_lines)

    def _vswitch_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert vSwitch API response to HCL."""
        vswitch = data.get("VSwitch", {})
        vswitch_id = vswitch.get("VSwitchId", "")
        vswitch_name = vswitch.get("VSwitchName", "imported-vswitch")
        cidr = vswitch.get("CidrBlock", "")
        vpc_id = vswitch.get("VpcId", "")
        zone_id = vswitch.get("ZoneId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(vswitch_name, "vswitch_")
        vpc_ref = self._hcl_ref(refs, vpc_id)

        hcl = textwrap.dedent(f"""\
            # Imported vSwitch: {vswitch_id}
            resource "alicloud_vswitch" "{tf_name}" {{
              vswitch_name = "{vswitch_name}"
              vpc_id       = {vpc_ref}
              cidr_block   = "{cidr}"
              zone_id      = "{zone_id}"

              # Import only - prevent accidental deletion
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _ecs_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert ECS API response to HCL."""
        instances = data.get("Instances", {}).get("Instance", [])
        if not instances:
            return "# No instances found\n"

        instance = instances[0]
        instance_id = instance.get("InstanceId", "")
        instance_name = instance.get("InstanceName", "imported-ecs")
        instance_type = instance.get("InstanceType", "")
        image_id = instance.get("ImageId", "")
        vswitch_id = instance.get("VpcAttributes", {}).get("VSwitchId", [""])[0]

        if not tf_name:
            tf_name = self._sanitize_tf_name(instance_name, "ecs_")
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        sg_ids = instance.get("SecurityGroupIds", {}).get("SecurityGroupId", [])
        if isinstance(sg_ids, str):
            sg_ids = [sg_ids] if sg_ids else []
        sg_block = ""
        if sg_ids:
            if refs:
                sg_values = ", ".join(self._hcl_ref(refs, sgid) for sgid in sg_ids)
                sg_block = f"  security_groups = [{sg_values}]\n"
            else:
                sg_block = f"  security_groups = {json.dumps(sg_ids)}\n"

        hcl = textwrap.dedent(f"""\
            # Imported ECS: {instance_id}
            # NOTE: ECS import requires stopping the instance
            resource "alicloud_instance" "{tf_name}" {{
              instance_name = "{instance_name}"
              instance_type = "{instance_type}"
              image_id      = "{image_id}"
              vswitch_id    = {vswitch_ref}
            {sg_block}
              # Import only - do not manage lifecycle
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _rds_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert RDS API response to HCL."""
        db_instance = data.get("Items", {}).get("DBInstanceAttribute", [{}])[0]
        if not db_instance:
            db_instance = data.get("DBInstanceAttribute", {})

        instance_id = db_instance.get("DBInstanceId", "")
        instance_name = db_instance.get("DBInstanceDescription", "imported-rds")
        engine = db_instance.get("Engine", "MySQL")
        engine_version = db_instance.get("EngineVersion", "8.0")
        instance_type = db_instance.get("DBInstanceClass", "")
        vswitch_id = db_instance.get("VSwitchId", "")
        zone_id = db_instance.get("ZoneId", "")
        storage = db_instance.get("DBInstanceStorage", 20)

        if not tf_name:
            tf_name = self._sanitize_tf_name(instance_name, "rds_")
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        hcl = textwrap.dedent(f"""\
            # Imported RDS: {instance_id}
            resource "alicloud_db_instance" "{tf_name}" {{
              instance_name        = "{instance_name}"
              engine               = "{engine}"
              engine_version       = "{engine_version}"
              instance_type        = "{instance_type}"
              instance_storage     = {storage}
              vswitch_id           = {vswitch_ref}
              zone_id              = "{zone_id}"

              # Import only - prevent accidental deletion
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _redis_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert Redis/Tair API response to HCL."""
        instance = data.get("Instances", {}).get("KVStoreInstance", [{}])[0]
        if not instance:
            instance = data.get("Instance", {})

        instance_id = instance.get("InstanceId", "")
        instance_name = instance.get("InstanceName", "imported-redis")
        instance_class = instance.get("InstanceClass", "")
        engine_version = instance.get("EngineVersion", "")
        vpc_id = instance.get("VpcId", "")
        vswitch_id = instance.get("VSwitchId", "")
        zone_id = instance.get("ZoneId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(instance_name, "redis_")
        vpc_ref = self._hcl_ref(refs, vpc_id)
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        hcl = textwrap.dedent(f"""\
            # Imported Redis: {instance_id}
            resource "alicloud_kvstore_instance" "{tf_name}" {{
              instance_name  = "{instance_name}"
              instance_class = "{instance_class}"
              engine_version = "{engine_version}"
              vpc_id         = {vpc_ref}
              vswitch_id     = {vswitch_ref}
              zone_id        = "{zone_id}"

              # Import only - prevent accidental deletion
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _slb_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert SLB API response to HCL."""
        lb = data.get("LoadBalancer", {})

        lb_id = lb.get("LoadBalancerId", "")
        lb_name = lb.get("LoadBalancerName", "imported-slb")
        lb_spec = lb.get("LoadBalancerSpec", "slb.s1.small")
        address_type = lb.get("AddressType", "intranet")
        vpc_id = lb.get("VpcId", "")
        vswitch_id = lb.get("VSwitchId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(lb_name, "slb_")
        vpc_ref = self._hcl_ref(refs, vpc_id)
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        hcl = textwrap.dedent(f"""\
            # Imported SLB: {lb_id}
            resource "alicloud_slb_load_balancer" "{tf_name}" {{
              load_balancer_name = "{lb_name}"
              load_balancer_spec = "{lb_spec}"
              address_type       = "{address_type}"
              vpc_id             = {vpc_ref}
              vswitch_id         = {vswitch_ref}

              # Import only - prevent accidental deletion
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _eip_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert EIP API response to HCL."""
        eips = data.get("EipAddresses", {}).get("EipAddress", [])
        if not eips:
            return "# No EIP addresses found\n"

        eip = eips[0]
        allocation_id = eip.get("AllocationId", "")
        ip_address = eip.get("IpAddress", "")
        bandwidth = eip.get("Bandwidth", 5)
        isp = eip.get("ISP", "BGP")
        internet_charge_type = eip.get("InternetChargeType", "PayByTraffic")

        tf_name = tf_name or f"eip_{allocation_id.split('-')[-1][:8]}"

        hcl = textwrap.dedent(f"""\
            # Imported EIP: {allocation_id} ({ip_address})
            resource "alicloud_eip_address" "{tf_name}" {{
              address_name         = "imported-eip-{allocation_id.split('-')[-1][:8]}"
              bandwidth            = "{bandwidth}"
              isp                  = "{isp}"
              internet_charge_type = "{internet_charge_type}"

              # Import only - prevent accidental deletion
              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _sg_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert Security Group API response to HCL."""
        sg = data.get("SecurityGroup", {})

        sg_id = sg.get("SecurityGroupId", "")
        sg_name = sg.get("SecurityGroupName", "imported-sg")
        description = sg.get("Description", "Imported security group")
        vpc_id = sg.get("VpcId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(sg_name, "sg_")

        hcl_lines = [
            f'# Imported Security Group: {sg_id}',
            f'resource "alicloud_security_group" "{tf_name}" {{',
            f'  name        = "{sg_name}"',
            f'  description = "{description}"',
        ]

        if vpc_id:
            hcl_lines.append(f'  vpc_id      = {self._hcl_ref(refs, vpc_id)}')

        hcl_lines.extend([
            '',
            '  # Import only - prevent accidental deletion',
            '  lifecycle {',
            '    prevent_destroy = true',
            '  }',
            '',
            '  tags = {',
            '    ImportedBy = "terraform-reverse-engineering"',
            '  }',
            '}',
        ])

        return "\n".join(hcl_lines)

    def _nat_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert NAT Gateway API response to HCL."""
        nat = data.get("NatGateway", data)
        nat_id = nat.get("NatGatewayId", "")
        nat_name = nat.get("Name", nat.get("NatGatewayName", "imported-nat"))
        vpc_id = nat.get("VpcId", "")
        vswitch_id = nat.get("VSwitchId", "")
        spec = nat.get("Spec", "Small")
        nat_type = nat.get("NatType", "Enhanced")

        if not tf_name:
            tf_name = self._sanitize_tf_name(nat_name, "nat_") or f"nat_{nat_id.split('-')[-1][:8]}"
        vpc_ref = self._hcl_ref(refs, vpc_id)
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        return textwrap.dedent(f"""\
            # Imported NAT Gateway: {nat_id}
            resource "alicloud_nat_gateway" "{tf_name}" {{
              nat_gateway_name = "{nat_name}"
              vpc_id           = {vpc_ref}
              vswitch_id       = {vswitch_ref}
              spec             = "{spec}"
              nat_type         = "{nat_type}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def _mongodb_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert MongoDB API response to HCL."""
        instance = data.get("DBInstances", {}).get("DBInstance", [{}])[0]
        if not instance:
            instance = data.get("DBInstance", data.get("Items", {}).get("DBInstanceAttribute", [{}])[0])

        instance_id = instance.get("DBInstanceId", "")
        instance_name = instance.get("DBInstanceDescription", "imported-mongodb")
        engine_version = instance.get("EngineVersion", "4.2")
        instance_class = instance.get("DBInstanceClass", "")
        vpc_id = instance.get("VpcId", "")
        vswitch_id = instance.get("VSwitchId", "")
        zone_id = instance.get("ZoneId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(instance_name, "mongodb_")
        vpc_ref = self._hcl_ref(refs, vpc_id)
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        return textwrap.dedent(f"""\
            # Imported MongoDB: {instance_id}
            resource "alicloud_mongodb_instance" "{tf_name}" {{
              name             = "{instance_name}"
              engine_version   = "{engine_version}"
              db_instance_class = "{instance_class}"
              vpc_id           = {vpc_ref}
              vswitch_id       = {vswitch_ref}
              zone_id          = "{zone_id}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def _polardb_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert PolarDB cluster API response to HCL."""
        cluster = data.get("Items", {}).get("DBCluster", [{}])[0]
        if not cluster:
            cluster = data.get("DBCluster", data)

        cluster_id = cluster.get("DBClusterId", "")
        cluster_name = cluster.get("DBClusterDescription", "imported-polardb")
        db_type = cluster.get("DBType", "MySQL")
        db_version = cluster.get("DBVersion", "8.0")
        vpc_id = cluster.get("VpcId", "")
        vswitch_id = cluster.get("VSwitchId", "")
        zone_id = cluster.get("ZoneId", "")

        if not tf_name:
            tf_name = self._sanitize_tf_name(cluster_name, "polardb_")
        vpc_ref = self._hcl_ref(refs, vpc_id)
        vswitch_ref = self._hcl_ref(refs, vswitch_id)

        return textwrap.dedent(f"""\
            # Imported PolarDB: {cluster_id}
            resource "alicloud_polardb_cluster" "{tf_name}" {{
              description = "{cluster_name}"
              db_type     = "{db_type}"
              db_version  = "{db_version}"
              vpc_id      = {vpc_ref}
              vswitch_id  = {vswitch_ref}
              zone_id     = "{zone_id}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def _disk_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert Disk API response to HCL."""
        disk = data.get("Disk", data.get("Disks", {}).get("Disk", [{}]))
        if isinstance(disk, list):
            disk = disk[0] if disk else {}

        disk_id = disk.get("DiskId", "")
        disk_name = disk.get("DiskName", "imported-disk")
        size = disk.get("Size", 40)
        category = disk.get("Category", "cloud_essd")
        zone_id = disk.get("ZoneId", "")
        disk_type = disk.get("Type", "data")

        if not tf_name:
            tf_name = self._sanitize_tf_name(disk_name, "disk_")
            if not tf_name or tf_name == "disk_":
                tf_name = f"disk_{disk_id.split('-')[-1][:8]}" if disk_id else "imported_disk"

        return textwrap.dedent(f"""\
            # Imported Disk: {disk_id} (type={disk_type})
            # NOTE: 已挂载磁盘需额外 import alicloud_disk_attachment
            resource "alicloud_disk" "{tf_name}" {{
              disk_name = "{disk_name}"
              zone_id   = "{zone_id}"
              size      = {size}
              category  = "{category}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def _route_table_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert Route Table API response to HCL."""
        rt = data.get("RouteTable", data)
        if isinstance(rt, list):
            rt = rt[0] if rt else {}

        rt_id = rt.get("RouteTableId", "")
        rt_name = rt.get("RouteTableName", "imported-rt")
        vpc_id = rt.get("VpcId", "")
        description = rt.get("Description", "Imported route table")

        if not tf_name:
            tf_name = self._sanitize_tf_name(rt_name, "rt_")
            if not tf_name or tf_name == "rt_":
                tf_name = f"rt_{rt_id.split('-')[-1][:8]}" if rt_id else "imported_rt"
        vpc_ref = self._hcl_ref(refs, vpc_id)

        return textwrap.dedent(f"""\
            # Imported Route Table: {rt_id}
            # NOTE: 路由条目 (alicloud_route_entry) 需单独管理
            resource "alicloud_route_table" "{tf_name}" {{
              vpc_id           = {vpc_ref}
              route_table_name = "{rt_name}"
              description      = "{description}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def _oss_to_hcl(
        self,
        data: Dict,
        tf_name: Optional[str] = None,
        refs: Optional[ResourceReferenceRegistry] = None,
    ) -> str:
        """Convert OSS bucket info to HCL."""
        bucket_name = data.get("BucketName", data.get("Bucket", {}).get("Name", "imported-bucket"))
        if isinstance(bucket_name, dict):
            bucket_name = bucket_name.get("Name", "imported-bucket")

        bucket_info = data.get("Bucket", data)
        acl = bucket_info.get("AccessControlList", {}).get("Grant", "private")
        storage_class = bucket_info.get("StorageClass", "Standard")

        if not tf_name:
            tf_name = re.sub(r"[^a-zA-Z0-9_]", "_", bucket_name.replace("-", "_"))
            if tf_name[0].isdigit():
                tf_name = "oss_" + tf_name

        return textwrap.dedent(f"""\
            # Imported OSS Bucket: {bucket_name}
            resource "alicloud_oss_bucket" "{tf_name}" {{
              bucket          = "{bucket_name}"
              acl             = "{acl.lower()}"
              storage_class   = "{storage_class}"

              lifecycle {{
                prevent_destroy = true
              }}

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

    def generate_import_script(self, resources: List[Dict[str, str]]) -> str:
        """Generate terraform import shell script."""
        lines = [
            "#!/bin/bash",
            "# Auto-generated terraform import script",
            "set -e",
            "",
            'cd "$(dirname "$0")"',
            "",
            "echo 'Importing resources to Terraform state...'",
            "",
        ]

        for resource in resources:
            if not resource.get("tf_type"):
                continue
            tf_type = resource["tf_type"]
            tf_name = resource["tf_name"]
            resource_id = resource["id"]
            lines.append(f'echo "Importing {tf_type}.{tf_name}..."')
            lines.append(
                f'terraform import {tf_type}.{tf_name} {resource_id} '
                f'|| echo "Import failed for {tf_name}"'
            )
            lines.append("")

        lines.extend([
            "echo 'Import completed!'",
            "echo 'Run: terraform plan' to verify",
        ])

        return "\n".join(lines)


def import_resources_for_hitl(resources: List[Dict]) -> List[Dict[str, Any]]:
    """Reverse Engineering 产物 → HITL ResourceInfo 兼容结构。"""
    return [
        {
            "type": item["type"],
            "name": item["tf_name"],
            "id": item["id"],
            "status": "pending",
        }
        for item in resources
    ]


def collect_output_previews(output_dir: Path, max_chars: int = 8000) -> Dict[str, str]:
    """读取生成目录中的 .tf / .sh 作为 HITL 配置预览。"""
    previews: Dict[str, str] = {}
    if not output_dir.is_dir():
        return previews
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path.suffix not in (".tf", ".sh"):
            continue
        content = path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n... [truncated {len(content) - max_chars} chars]"
        previews[path.name] = content
    return previews


class ReverseEngineering:
    """Main reverse engineering orchestrator."""

    def __init__(
        self, 
        region: str = "cn-hangzhou", 
        output_dir: Path | None = None,
        skip_preflight: bool = False
    ):
        self.region = region
        if output_dir is None:
            from runtime_paths import default_import_output
            output_dir = default_import_output()
        self.output_dir = output_dir
        self.mapper = ResourceMapper(region)
        self.registry = get_registry()
        self.checker = CapabilityChecker(self.registry)
        self.skip_preflight = skip_preflight

    def run(
        self,
        resource_type: str,
        resource_ids: List[str],
        dry_run: bool = False,
        discover_associated: bool = False
    ) -> Tuple[bool, List[Dict]]:
        """
        Run reverse engineering.
        Returns: (success, generated_resources)
        """
        if dry_run:
            print_dry_run_banner()

        # ==========================================
        # PreFlight Check - 资源能力预检
        # ==========================================
        if not self.skip_preflight:
            print(f"{Colors.CYAN}[PreFlight]{Colors.END} 检查资源类型支持: {resource_type}")
            
            required_caps = {
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE
            }
            if discover_associated:
                required_caps.add(ResourceCapability.ASSOCIATED_DISCOVER)
            
            preflight_result = self.registry.preflight_check(
                resource_type, 
                required_capabilities=required_caps
            )
            
            print(f"  {preflight_result.message}")
            
            if preflight_result.warnings:
                for warning in preflight_result.warnings:
                    print(f"  {Colors.YELLOW}⚠ {warning}{Colors.END}")
            
            if not preflight_result.can_proceed:
                print(f"\n{Colors.RED}[PreFlight] 检查未通过，无法继续{Colors.END}")
                if preflight_result.suggestions:
                    print("\n建议:")
                    for suggestion in preflight_result.suggestions:
                        print(f"  • {suggestion}")
                
                # 显示支持矩阵
                print(f"\n{Colors.CYAN}支持的资源类型:{Colors.END}")
                for name in self.registry.list_supported_names():
                    print(f"  - {name}")
                
                return False, []
            
            if preflight_result.fallback_available:
                print(f"\n{Colors.YELLOW}[PreFlight] 将使用降级模式继续{Colors.END}")
            
            print(f"{Colors.GREEN}[PreFlight] 检查通过 ✓{Colors.END}\n")

        all_resources = []
        pending_resources: List[Dict] = []
        work_queue: List[Tuple[str, str]] = [(resource_type, rid) for rid in resource_ids]
        processed: set = set()

        if discover_associated:
            for rid in resource_ids:
                log_dry_run("DISCOVER", f"发现关联资源: {rid}")
                for assoc in self.mapper.discover_associated(resource_type, rid):
                    log_dry_run("DISCOVER", f"  发现: {assoc['type']} - {assoc['id']}")
                    key = (assoc["type"], assoc["id"])
                    if key not in processed:
                        work_queue.append(key)

        for rtype, resource_id in work_queue:
            key = (rtype, resource_id)
            if key in processed:
                continue
            processed.add(key)

            if rtype not in self.mapper.RESOURCE_APIS:
                log_dry_run("WARN", f"跳过不支持的关联类型: {rtype}", is_error=False)
                continue

            log_dry_run("QUERY", f"查询 {rtype}: {resource_id}")

            data = self.mapper.query_resource(rtype, resource_id)
            if not data or "error" in data:
                log_dry_run("ERROR", f"查询失败: {data.get('error', 'Unknown error')}", is_error=True)
                continue

            tf_type = self.mapper.RESOURCE_APIS[rtype]["tf_type"]
            tf_name = make_tf_name(rtype, resource_id)
            pending_resources.append({
                "type": rtype,
                "id": resource_id,
                "tf_type": tf_type,
                "tf_name": tf_name,
                "data": data,
            })

        if not pending_resources:
            return False, []

        refs = ResourceReferenceRegistry()
        for item in pending_resources:
            refs.register(item["id"], item["tf_type"], item["tf_name"])

        for item in pending_resources:
            log_dry_run("GENERATE", f"生成 HCL: {item['id']}")
            hcl = self.mapper.to_hcl(
                item["type"],
                item["data"],
                tf_name=item["tf_name"],
                refs=refs,
            )
            item["hcl"] = hcl
            all_resources.append(item)

        for item in pending_resources:
            if item["type"] != "disk":
                continue
            instance_id = self.mapper.extract_attached_instance_id(item["data"])
            if not instance_id:
                continue
            attach_hcl = self.mapper.disk_attachment_to_hcl(
                item["id"],
                instance_id,
                item["tf_name"],
                refs=refs,
            )
            item["hcl"] = item["hcl"].rstrip() + "\n\n" + attach_hcl.strip() + "\n"
            attach_tf_name = f"attach_{item['tf_name'].replace('imported_disk_', '', 1)}"
            all_resources.append({
                "type": "disk_attachment",
                "id": f"{item['id']}:{instance_id}",
                "tf_type": "alicloud_disk_attachment",
                "tf_name": attach_tf_name,
                "hcl": "",
                "data": {},
            })
            log_dry_run("GENERATE", f"生成 disk_attachment: {item['id']} -> {instance_id}")

        if not all_resources:
            return False, []

        # Generate output files
        generated_content = self._generate_files(all_resources, dry_run)

        # Validate in dry-run mode (init → validate → plan)
        if dry_run:
            success = self._validate_generated(generated_content)
            return success, all_resources

        # Normal mode: also validate after writing
        self._validate_generated(self.output_dir)

        return True, all_resources

    def _generate_files(self, resources: List[Dict], dry_run: bool) -> Optional[Dict[str, str]]:
        """Generate output files. Returns content dict in dry-run mode."""
        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Group by resource type (skip import-script-only entries with empty hcl)
        by_type = {}
        for resource in resources:
            if not resource.get("hcl"):
                continue
            rtype = resource["type"]
            if rtype not in by_type:
                by_type[rtype] = []
            by_type[rtype].append(resource)

        # For dry-run: collect generated content
        generated_content: Dict[str, str] = {}

        # Generate HCL files per type
        for rtype, rlist in by_type.items():
            filename = f"{rtype}.tf"
            content = "\n\n".join([r["hcl"] for r in rlist])

            if dry_run:
                log_dry_run("WRITE", f"生成 {filename} (dry-run, 不保存)")
                generated_content[filename] = content
            else:
                file_path = self.output_dir / filename
                file_path.write_text(content, encoding="utf-8")
                print(f"  写入: {file_path}")

        # Generate import script
        import_script = self.mapper.generate_import_script(resources)
        if dry_run:
            log_dry_run("WRITE", "生成 import.sh (dry-run, 不保存)")
            generated_content["import.sh"] = import_script
        else:
            script_path = self.output_dir / "import.sh"
            script_path.write_text(import_script, encoding="utf-8")
            script_path.chmod(0o755)
            print(f"  写入: {script_path}")

        return generated_content if dry_run else None

    def _run_terraform_safe(self, cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
        """
        Run terraform with dry-run safety guard.
        Only init/validate/plan are executed. All other commands are mocked.
        """
        subcommand = cmd[1] if len(cmd) > 1 else ""
        cmd_str = " ".join(cmd)

        if subcommand not in TERRAFORM_DRY_RUN_ALLOWED:
            log_dry_run("MOCK", f"⛔ 已阻止非白名单命令: {cmd_str}", is_error=True)
            log_dry_run("MOCK", "dry-run 模式下仅允许 init/validate/plan 三种操作。如需执行 apply/destroy/import，请退出 dry-run 模式。", is_error=True)
            return subprocess.CompletedProcess(
                cmd, returncode=0,
                stdout=f"[DRY-RUN] 模拟: {cmd_str}\n[DRY-RUN] 操作已阻止，未实际执行\n",
                stderr=""
            )

        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True
        )

    def _validate_generated(self, source) -> bool:
        """
        Validate generated HCL.
        source: Dict[str,str] in dry-run mode, or Path to output_dir in normal mode.
        Runs: terraform init → validate → plan. No apply/destroy/import.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            valid_types = list(self.mapper.RESOURCE_APIS.keys())

            # Write files to temp directory
            if isinstance(source, dict):
                # Dry-run mode: source is content dict
                for filename, content in source.items():
                    if filename.endswith(".tf") or filename.endswith(".sh"):
                        (work_dir / filename).write_text(content, encoding="utf-8")
            else:
                # Normal mode: source is Path
                for rtype in valid_types:
                    tf_file = Path(source) / f"{rtype}.tf"
                    if tf_file.exists():
                        (work_dir / f"{rtype}.tf").write_text(
                            tf_file.read_text(), encoding="utf-8"
                        )

            # Create minimal provider config
            provider_tf = work_dir / "provider.tf"
            provider_tf.write_text(textwrap.dedent("""\
                terraform {
                  required_providers {
                    alicloud = {
                      source = "aliyun/alicloud"
                    }
                  }
                }
                provider "alicloud" {
                  region = "cn-hangzhou"
                }
            """))

            steps = [
                ("INIT", ["terraform", "init", "-backend=false"]),
                ("VALIDATE", ["terraform", "validate"]),
                ("PLAN", ["terraform", "plan", "-input=false"]),
            ]

            for phase, cmd in steps:
                log_dry_run(phase, f"执行 {' '.join(cmd)}")
                result = self._run_terraform_safe(cmd, work_dir)

                if result.returncode != 0:
                    log_dry_run(phase, f"失败 (exit code: {result.returncode})", is_error=True)
                    if result.stderr:
                        log_dry_run("ERROR", result.stderr.strip(), is_error=True)
                    return False

                log_dry_run(phase, "成功 ✓")

            log_dry_run("SUMMARY", "✅ 所有验证通过（仅预览，未执行任何导入操作）")
            return True


def main():
    parser = argparse.ArgumentParser(
        description="Reverse Engineer Alibaba Cloud Resources to Terraform"
    )
    parser.add_argument(
        "--resource-type", "-t",
        required=True,
        help="Resource type to import (run with --dry-run to check supported types)"
    )
    parser.add_argument(
        "--resource-id", "-i",
        help="Single resource ID"
    )
    parser.add_argument(
        "--resource-ids",
        help="Comma-separated resource IDs"
    )
    parser.add_argument(
        "--region", "-r",
        default="cn-hangzhou",
        help="Alibaba Cloud region"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=None,
        help="Output directory (default: .runtime/terraform-ops/import/<resource-type>/)",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Dry-run mode (generate only, no import)"
    )
    parser.add_argument(
        "--discover-associated", "-D",
        action="store_true",
        help="Auto-discover associated resources"
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip PreFlight capability check (not recommended)"
    )

    args = parser.parse_args()

    from runtime_paths import resolve_output_dir

    if args.output_dir is None:
        args.output_dir = resolve_output_dir(
            None, kind="import", batch=args.resource_type
        )

    # Parse resource IDs
    resource_ids = []
    if args.resource_id:
        resource_ids.append(args.resource_id)
    if args.resource_ids:
        resource_ids.extend(args.resource_ids.split(","))

    if not resource_ids:
        print(f"{Colors.RED}Error: Must provide --resource-id or --resource-ids{Colors.END}")
        sys.exit(1)

    # Run reverse engineering
    engine = ReverseEngineering(
        region=args.region, 
        output_dir=args.output_dir,
        skip_preflight=args.skip_preflight
    )
    success, resources = engine.run(
        resource_type=args.resource_type,
        resource_ids=resource_ids,
        dry_run=args.dry_run,
        discover_associated=args.discover_associated
    )

    if success:
        print(f"\n{Colors.GREEN}✓ Reverse engineering completed{Colors.END}")
        print(f"\n生成的资源:")
        for r in resources:
            print(f"  - {r['tf_type']}.{r['tf_name']} ({r['id']})")

        if args.dry_run:
            print(f"\n{Colors.CYAN}注意: 当前为 dry-run 模式，未实际导入资源{Colors.END}")
            print(f"{Colors.CYAN}      确认无误后，运行 import.sh 执行导入{Colors.END}")
        else:
            print(f"\n执行导入:")
            print(f"  cd {args.output_dir}")
            print(f"  ./import.sh")
    else:
        print(f"\n{Colors.RED}✗ Reverse engineering failed{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
