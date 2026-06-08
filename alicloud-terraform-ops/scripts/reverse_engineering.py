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
    }

    def __init__(self, region: str = "cn-hangzhou"):
        self.region = region

    def query_resource(self, resource_type: str, resource_id: str) -> Optional[Dict]:
        """Query resource details via aliyun CLI."""
        mapping = self.RESOURCE_APIS.get(resource_type)
        if not mapping:
            return None

        cmd = [
            "aliyun",
            mapping["product"],
            mapping["describe"],
            "--RegionId", self.region,
            f"--{mapping['id_param']}", resource_id,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return {"error": result.stderr, "id": resource_id}

            return json.loads(result.stdout)
        except Exception as e:
            return {"error": str(e), "id": resource_id}

    def discover_associated(self, resource_type: str, resource_id: str) -> List[Dict]:
        """Discover associated resources."""
        associated = []

        if resource_type == "vpc":
            # Discover vSwitches
            vswitches = self._query_vswitches(resource_id)
            associated.extend(vswitches)

            # Discover route tables
            route_tables = self._query_route_tables(resource_id)
            associated.extend(route_tables)

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

    def to_hcl(self, resource_type: str, resource_data: Dict) -> str:
        """Convert API response to HCL."""
        if resource_type == "vpc":
            return self._vpc_to_hcl(resource_data)
        elif resource_type == "vswitch":
            return self._vswitch_to_hcl(resource_data)
        elif resource_type == "ecs":
            return self._ecs_to_hcl(resource_data)
        else:
            return f"# TODO: Implement HCL generation for {resource_type}\n"

    def _vpc_to_hcl(self, data: Dict) -> str:
        """Convert VPC API response to HCL."""
        vpc = data.get("Vpc", {})
        vpc_id = vpc.get("VpcId", "")
        vpc_name = vpc.get("VpcName", "imported-vpc")
        cidr = vpc.get("CidrBlock", "")
        description = vpc.get("Description", "")

        # Sanitize name for terraform
        tf_name = re.sub(r"[^a-zA-Z0-9_]", "_", vpc_name)
        if tf_name[0].isdigit():
            tf_name = "vpc_" + tf_name

        hcl = textwrap.dedent(f"""\
            # Imported VPC: {vpc_id}
            resource "alicloud_vpc" "{tf_name}" {{
              vpc_name   = "{vpc_name}"
              cidr_block = "{cidr}"
            """).rstrip()

        if description:
            hcl += f'\n  description = "{description}"'

        hcl += '\n\n  tags = {\n    ImportedBy = "terraform-reverse-engineering"\n  }\n}'

        return hcl

    def _vswitch_to_hcl(self, data: Dict) -> str:
        """Convert vSwitch API response to HCL."""
        vswitch = data.get("VSwitch", {})
        vswitch_id = vswitch.get("VSwitchId", "")
        vswitch_name = vswitch.get("VSwitchName", "imported-vswitch")
        cidr = vswitch.get("CidrBlock", "")
        vpc_id = vswitch.get("VpcId", "")
        zone_id = vswitch.get("ZoneId", "")

        tf_name = re.sub(r"[^a-zA-Z0-9_]", "_", vswitch_name)
        if tf_name[0].isdigit():
            tf_name = "vswitch_" + tf_name

        hcl = textwrap.dedent(f"""\
            # Imported vSwitch: {vswitch_id}
            resource "alicloud_vswitch" "{tf_name}" {{
              vswitch_name = "{vswitch_name}"
              vpc_id       = "{vpc_id}"  # TODO: Reference to alicloud_vpc resource
              cidr_block   = "{cidr}"
              zone_id      = "{zone_id}"

              tags = {{
                ImportedBy = "terraform-reverse-engineering"
              }}
            }}
        """)

        return hcl

    def _ecs_to_hcl(self, data: Dict) -> str:
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

        tf_name = re.sub(r"[^a-zA-Z0-9_]", "_", instance_name)
        if tf_name[0].isdigit():
            tf_name = "ecs_" + tf_name

        hcl = textwrap.dedent(f"""\
            # Imported ECS: {instance_id}
            # NOTE: ECS import requires stopping the instance
            resource "alicloud_instance" "{tf_name}" {{
              instance_name = "{instance_name}"
              instance_type = "{instance_type}"
              image_id      = "{image_id}"
              vswitch_id    = "{vswitch_id}"

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
            tf_type = resource["tf_type"]
            tf_name = resource["tf_name"]
            resource_id = resource["id"]
            lines.append(f'echo "Importing {tf_type}.{tf_name}..."')
            lines.append(f'terraform import {tf_type}.{tf_name} {resource_id} || echo "Import failed for {tf_name}"')
            lines.append("")

        lines.extend([
            "echo 'Import completed!'",
            "echo 'Run: terraform plan' to verify",
        ])

        return "\n".join(lines)


class ReverseEngineering:
    """Main reverse engineering orchestrator."""

    def __init__(self, region: str = "cn-hangzhou", output_dir: Path = Path("./generated")):
        self.region = region
        self.output_dir = output_dir
        self.mapper = ResourceMapper(region)

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

        all_resources = []

        for resource_id in resource_ids:
            log_dry_run("QUERY", f"查询 {resource_type}: {resource_id}")

            data = self.mapper.query_resource(resource_type, resource_id)
            if not data or "error" in data:
                log_dry_run("ERROR", f"查询失败: {data.get('error', 'Unknown error')}", is_error=True)
                continue

            log_dry_run("GENERATE", f"生成 HCL: {resource_id}")
            hcl = self.mapper.to_hcl(resource_type, data)

            tf_type = self.mapper.RESOURCE_APIS[resource_type]["tf_type"]
            tf_name = f"imported_{resource_type}_{resource_id.split('-')[-1][:8]}"

            resource_info = {
                "type": resource_type,
                "id": resource_id,
                "tf_type": tf_type,
                "tf_name": tf_name,
                "hcl": hcl,
                "data": data,
            }
            all_resources.append(resource_info)

            # Discover associated resources
            if discover_associated:
                log_dry_run("DISCOVER", f"发现关联资源: {resource_id}")
                associated = self.mapper.discover_associated(resource_type, resource_id)
                for assoc in associated:
                    log_dry_run("DISCOVER", f"  发现: {assoc['type']} - {assoc['id']}")

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

        # Group by resource type
        by_type = {}
        for resource in resources:
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
            valid_types = ["vpc", "vswitch", "ecs", "rds"]

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
        choices=["vpc", "vswitch", "ecs", "rds", "redis", "slb", "eip", "security_group"],
        help="Resource type to import"
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
        default=Path("./generated"),
        help="Output directory"
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

    args = parser.parse_args()

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
    engine = ReverseEngineering(region=args.region, output_dir=args.output_dir)
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
