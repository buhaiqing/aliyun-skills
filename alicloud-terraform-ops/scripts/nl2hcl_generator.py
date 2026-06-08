#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl2hcl_generator.py — Natural Language to Terraform HCL Generator

Implements NL2HCL feature for alicloud-terraform-ops skill.
Converts natural language infrastructure descriptions into Terraform HCL.

Features:
- Natural language intent parsing
- HCL code generation with best practices
- Dry-run mode for validation (terraform init -backend=false / validate / plan)
- GCL integration via gcl_runner.py

USAGE
-----
    # Generate HCL from natural language
    python nl2hcl_generator.py \\
        --request "创建一个VPC，包含两个可用区的交换机" \\
        --environment dev \\
        --output-dir ./generated

    # Dry-run mode (validate without creating resources)
    python nl2hcl_generator.py \\
        --request "创建一个VPC" \\
        --environment dev \\
        --dry-run \\
        --gcl-check  # Enable GCL quality gate

    # Interactive wizard mode
    python nl2hcl_generator.py --wizard

EXIT CODES
----------
    0  SUCCESS
    1  GENERATION_ERROR
    2  VALIDATION_ERROR
    3  DRY_RUN_ERROR
    4  GCL_REJECT
    5  USER_CANCEL

REQUIREMENTS
------------
    Python 3.10+ stdlib only. External: terraform CLI (>= 1.5.0)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ANSI color codes for terminal output
# Allowed terraform subcommands during dry-run mode. All others are mocked.
TERRAFORM_DRY_RUN_ALLOWED = frozenset({"init", "validate", "plan"})

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
    """Print clear dry-run mode banner."""
    banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，不会创建或修改任何资源            ║
╚════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def print_exec_banner():
    """Print execution mode banner."""
    banner = f"""
{Colors.YELLOW}╔════════════════════════════════════════════════════════════════╗
║                    ⚡ EXECUTION MODE (执行模式)                  ║
║              此执行将实际创建/修改阿里云资源                      ║
╚════════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def log_dry_run(phase: str, message: str, is_error: bool = False):
    """Log message with dry-run prefix."""
    prefix = f"{Colors.CYAN}[DRY-RUN]{Colors.END}"
    color = Colors.RED if is_error else Colors.END
    timestamp = subprocess.check_output(["date", "+%H:%M:%S"]).decode().strip()
    print(f"{prefix} [{timestamp}] [{phase}] {color}{message}{Colors.END}")


def log_exec(phase: str, message: str):
    """Log message with execution prefix."""
    prefix = f"{Colors.YELLOW}[EXEC]{Colors.END}"
    timestamp = subprocess.check_output(["date", "+%H:%M:%S"]).decode().strip()
    print(f"{prefix} [{timestamp}] [{phase}] {message}")


class NL2HCLGenerator:
    """Generator for converting natural language to Terraform HCL."""

    # Resource type mappings from natural language keywords
    RESOURCE_PATTERNS = {
        r"vpc|虚拟私有云|专有网络": "alicloud_vpc",
        r"vswitch|交换机|子网": "alicloud_vswitch",
        r"ecs|云服务器|实例": "alicloud_instance",
        r"rds|mysql|数据库": "alicloud_db_instance",
        r"redis|缓存|kvstore": "alicloud_kvstore_instance",
        r"slb|负载均衡": "alicloud_slb",
        r"nat|网关": "alicloud_nat_gateway",
        r"eip|弹性ip": "alicloud_eip",
        r"security.?group|安全组": "alicloud_security_group",
    }

    # Default configurations per environment
    ENV_DEFAULTS = {
        "dev": {
            "vpc_cidr": "10.0.0.0/16",
            "instance_type": "ecs.g7.large",
            "rds_class": "rds.mysql.s1.small",
        },
        "staging": {
            "vpc_cidr": "10.1.0.0/16",
            "instance_type": "ecs.g7.xlarge",
            "rds_class": "rds.mysql.s2.large",
        },
        "prod": {
            "vpc_cidr": "10.2.0.0/16",
            "instance_type": "ecs.g7.2xlarge",
            "rds_class": "rds.mysql.x4.large",
        },
    }

    def __init__(self, environment: str = "dev", region: str = "cn-hangzhou"):
        self.environment = environment
        self.region = region
        self.defaults = self.ENV_DEFAULTS.get(environment, self.ENV_DEFAULTS["dev"])
        self.resources: List[Dict[str, Any]] = []

    def parse_intent(self, request: str) -> Dict[str, Any]:
        """Parse natural language request to identify resources."""
        request_lower = request.lower()
        detected_resources = []

        for pattern, resource_type in self.RESOURCE_PATTERNS.items():
            if re.search(pattern, request_lower, re.IGNORECASE):
                detected_resources.append(resource_type)

        # Extract count (e.g., "3台ECS" -> 3)
        count_match = re.search(r"(\d+)\s*(?:台|个|台ecs|个实例)", request_lower)
        count = int(count_match.group(1)) if count_match else 1

        # Extract availability zone count
        az_match = re.search(r"(\d+)\s*个?\s*(?:可用区|az)", request_lower)
        az_count = int(az_match.group(1)) if az_match else 2

        return {
            "resources": detected_resources,
            "count": count,
            "az_count": az_count,
            "raw_request": request,
        }

    def generate_vpc(self, name: str = "main") -> str:
        """Generate VPC HCL."""
        return textwrap.dedent(f"""\
            resource "alicloud_vpc" "{name}" {{
              vpc_name   = "{self.environment}-vpc"
              cidr_block = "{self.defaults['vpc_cidr']}"

              tags = {{
                Environment = "{self.environment}"
                ManagedBy   = "terraform"
              }}
            }}
        """)

    def generate_vswitch(self, vpc_name: str = "main", az_index: int = 0) -> str:
        """Generate vSwitch HCL."""
        az_list = ["a", "b", "c", "d", "e", "f", "g", "h"]
        az_suffix = az_list[az_index % len(az_list)]
        subnet = az_index + 1

        return textwrap.dedent(f"""\
            resource "alicloud_vswitch" "{vpc_name}_az_{az_suffix}" {{
              vpc_id     = alicloud_vpc.{vpc_name}.id
              cidr_block = cidrsubnet(alicloud_vpc.{vpc_name}.cidr_block, 8, {subnet})
              zone_id    = "{self.region}-{az_suffix}"
              vswitch_name = "{self.environment}-vswitch-{az_suffix}"

              tags = {{
                Environment = "{self.environment}"
                ManagedBy   = "terraform"
              }}
            }}
        """)

    def generate_ecs(self, name: str = "web", count: int = 1) -> str:
        """Generate ECS instance HCL."""
        return textwrap.dedent(f"""\
            resource "alicloud_instance" "{name}" {{
              count         = {count}
              image_id      = data.alicloud_images.ubuntu.images[0].id
              instance_type = "{self.defaults['instance_type']}"

              instance_name = "{self.environment}-{name}-${{count.index + 1}}"

              system_disk_category = "cloud_essd"
              system_disk_size     = 40

              vswitch_id = alicloud_vswitch.main_az_a.id

              internet_max_bandwidth_out = 10

              tags = {{
                Environment = "{self.environment}"
                ManagedBy   = "terraform"
              }}
            }}

            data "alicloud_images" "ubuntu" {{
              most_recent = true
              owners      = "system"
              name_regex  = "^ubuntu_22"
            }}
        """)

    def generate_variables(self) -> str:
        """Generate variables.tf."""
        return textwrap.dedent(f"""\
            variable "environment" {{
              description = "Deployment environment"
              type        = string
              default     = "{self.environment}"
            }}

            variable "region" {{
              description = "Alibaba Cloud region"
              type        = string
              default     = "{self.region}"
            }}
        """)

    def generate_outputs(self) -> str:
        """Generate outputs.tf."""
        outputs = []
        for resource in self.resources:
            if resource["type"] == "alicloud_vpc":
                outputs.append(textwrap.dedent(f"""\
                    output "vpc_id" {{
                      description = "The ID of the VPC"
                      value       = alicloud_vpc.main.id
                    }}

                    output "vpc_cidr" {{
                      description = "The CIDR block of the VPC"
                      value       = alicloud_vpc.main.cidr_block
                    }}
                """))
        return "\n".join(outputs)

    def generate(self, request: str) -> Dict[str, str]:
        """Generate complete HCL configuration from request."""
        intent = self.parse_intent(request)
        files = {}

        main_tf = []

        # Generate VPC if requested
        if "alicloud_vpc" in intent["resources"]:
            main_tf.append(self.generate_vpc())
            self.resources.append({"type": "alicloud_vpc", "name": "main"})

            # Generate vSwitches
            for i in range(intent["az_count"]):
                main_tf.append(self.generate_vswitch(az_index=i))
                self.resources.append({"type": "alicloud_vswitch", "index": i})

        # Generate ECS if requested
        if "alicloud_instance" in intent["resources"]:
            main_tf.append(self.generate_ecs(count=intent["count"]))
            self.resources.append({
                "type": "alicloud_instance",
                "count": intent["count"]
            })

        files["main.tf"] = "\n".join(main_tf)
        files["variables.tf"] = self.generate_variables()
        files["outputs.tf"] = self.generate_outputs()

        # Generate terraform.tfvars
        files["terraform.tfvars"] = textwrap.dedent(f"""\
            environment = "{self.environment}"
            region      = "{self.region}"
        """)

        return files


class DryRunExecutor:
    """Execute terraform in dry-run mode. Only init/validate/plan allowed."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def _run_terraform_safe(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """
        Run terraform with dry-run safety guard.
        Only init/validate/plan are executed. All other commands are mocked.
        """
        subcommand = cmd[1] if len(cmd) > 1 else ""
        cmd_str = " ".join(cmd)

        if subcommand not in TERRAFORM_DRY_RUN_ALLOWED:
            log_dry_run("MOCK", f"⛔ 已阻止非白名单命令: {cmd_str}", is_error=True)
            log_dry_run("MOCK", "dry-run 模式下仅允许 init/validate/plan 三种操作。如需执行 apply/destroy/import，请退出 dry-run 模式。", is_error=True)
            # Return mock success — command was not executed
            return subprocess.CompletedProcess(
                cmd, returncode=0,
                stdout=f"[DRY-RUN] 模拟: {cmd_str}\n[DRY-RUN] 操作已阻止，未实际执行\n",
                stderr=""
            )

        return subprocess.run(
            cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True
        )

    def execute(self) -> Tuple[bool, str, str]:
        """
        Execute terraform dry-run steps.
        Returns: (success, stdout, stderr)
        """
        steps = [
            ("INIT", ["terraform", "init", "-backend=false"]),
            ("VALIDATE", ["terraform", "validate"]),
            ("PLAN", ["terraform", "plan", "-input=false"]),
        ]

        all_stdout = []
        all_stderr = []

        for phase, cmd in steps:
            log_dry_run(phase, f"执行 {' '.join(cmd)}")

            result = self._run_terraform_safe(cmd)

            stdout = result.stdout if isinstance(result.stdout, str) else (result.stdout or "").decode("utf-8", errors="replace")
            stderr = result.stderr if isinstance(result.stderr, str) else (result.stderr or "").decode("utf-8", errors="replace")

            all_stdout.append(f"=== {phase} ===\n{stdout}")
            all_stderr.append(f"=== {phase} ===\n{stderr}")

            if result.returncode != 0:
                log_dry_run(phase, f"失败 (exit code: {result.returncode})", is_error=True)
                return False, "\n".join(all_stdout), "\n".join(all_stderr)

            log_dry_run(phase, "成功 ✓")

        return True, "\n".join(all_stdout), "\n".join(all_stderr)


def run_gcl_check(
    skill: str,
    operation: str,
    command: str,
    rubric_path: Path,
    max_iter: int = 2
) -> Tuple[bool, Dict]:
    """
    Run GCL quality gate check via gcl_runner.py.
    Returns: (passed, trace)
    """
    gcl_runner = Path(__file__).parent.parent.parent / "alicloud-gcl-runner-ops" / "scripts" / "gcl_runner.py"

    if not gcl_runner.exists():
        print(f"{Colors.YELLOW}Warning: gcl_runner.py not found, skipping GCL check{Colors.END}")
        return True, {}

    cmd = [
        sys.executable,
        str(gcl_runner),
        "--skill", skill,
        "--op", operation,
        "--command", command,
        "--rubric", str(rubric_path),
        "--max-iter", str(max_iter),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse trace output
    trace = {}
    try:
        trace_match = re.search(r'GCL_TRACE:\s*(\{.*\})', result.stdout)
        if trace_match:
            trace = json.loads(trace_match.group(1))
    except Exception:
        pass

    return result.returncode == 0, trace


def main():
    parser = argparse.ArgumentParser(
        description="Natural Language to Terraform HCL Generator"
    )
    parser.add_argument(
        "--request", "-r",
        help="Natural language infrastructure request"
    )
    parser.add_argument(
        "--environment", "-e",
        default="dev",
        choices=["dev", "staging", "prod", "int", "uat", "performance"],
        help="Target environment"
    )
    parser.add_argument(
        "--region", "-R",
        default="cn-hangzhou",
        help="Alibaba Cloud region"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("./generated"),
        help="Output directory for generated files"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Enable dry-run mode (validate without creating)"
    )
    parser.add_argument(
        "--gcl-check",
        action="store_true",
        help="Enable GCL quality gate check"
    )
    parser.add_argument(
        "--wizard", "-w",
        action="store_true",
        help="Interactive wizard mode"
    )

    args = parser.parse_args()

    # Wizard mode
    if args.wizard or not args.request:
        print(f"{Colors.BOLD}🧙 Terraform NL2HCL 交互式向导{Colors.END}")
        print("请输入基础设施需求描述:")
        args.request = input("> ").strip()
        if not args.request:
            print("错误: 未提供请求描述")
            sys.exit(1)

    # Generate HCL
    generator = NL2HCLGenerator(
        environment=args.environment,
        region=args.region
    )

    print(f"\n{Colors.BOLD}解析请求: {args.request}{Colors.END}")
    intent = generator.parse_intent(args.request)
    print(f"检测到资源类型: {', '.join(intent['resources'])}")
    print(f"数量: {intent['count']}, 可用区: {intent['az_count']}")

    files = generator.generate(args.request)

    # Dry-run mode
    if args.dry_run:
        print_dry_run_banner()

        with tempfile.TemporaryDirectory(prefix="tf-dryrun-") as tmpdir:
            work_dir = Path(tmpdir)

            # Write files
            for filename, content in files.items():
                file_path = work_dir / filename
                file_path.write_text(content, encoding="utf-8")
                log_dry_run("WRITE", f"生成 {filename}")

            # Execute dry-run
            executor = DryRunExecutor(work_dir)
            success, stdout, stderr = executor.execute()

            if success:
                log_dry_run("SUMMARY", "✅ 所有验证通过")
                print(f"\n{Colors.GREEN}Dry-run 成功！配置有效。{Colors.END}")
                print(f"\n{Colors.CYAN}生成的资源配置:{Colors.END}")
                for resource in generator.resources:
                    print(f"  + {resource['type']}")
            else:
                log_dry_run("SUMMARY", "❌ 验证失败", is_error=True)
                print(f"\n{Colors.RED}Dry-run 失败，请检查配置。{Colors.END}")
                if stderr:
                    print(f"\n{Colors.RED}错误输出:\n{stderr}{Colors.END}")
                sys.exit(3)

            # GCL check
            if args.gcl_check:
                rubric_path = Path(__file__).parent.parent / "references" / "rubric.md"
                passed, trace = run_gcl_check(
                    "alicloud-terraform-ops",
                    "nl2hcl_generation",
                    f"nl2hcl: {args.request}",
                    rubric_path
                )
                if not passed:
                    print(f"\n{Colors.RED}GCL 质量检查未通过{Colors.END}")
                    sys.exit(4)
                else:
                    print(f"\n{Colors.GREEN}GCL 质量检查通过 ✓{Colors.END}")

    # Normal mode - write to output directory
    else:
        print_exec_banner()

        args.output_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in files.items():
            file_path = args.output_dir / filename
            file_path.write_text(content, encoding="utf-8")
            log_exec("WRITE", f"生成 {file_path}")

        print(f"\n{Colors.GREEN}文件已生成到: {args.output_dir.absolute()}{Colors.END}")
        print(f"\n执行以下命令继续:")
        print(f"  cd {args.output_dir}")
        print(f"  terraform init")
        print(f"  terraform plan")


if __name__ == "__main__":
    main()
