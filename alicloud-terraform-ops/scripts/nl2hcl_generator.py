#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nl2hcl_generator.py — Natural Language to Terraform HCL Generator

Implements NL2HCL feature for alicloud-terraform-ops skill.
Converts natural language infrastructure descriptions into Terraform HCL.

Features:
- Natural language intent parsing
- HCL code generation with best practices
- Dry-run mode for offline HCL generation/lint; optional Terraform validate/plan gates
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
    Python 3.10+ stdlib only. Optional: terraform CLI (>= 1.5.0) for --with-validate/--with-plan
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
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from execution_trace import CommandRecord, persist_dry_run_trace
from module_catalog import (
    copy_modules,
    modules_for_trace,
    plan_modules,
    render_main_tf,
    render_outputs_tf,
)


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


# ─────────────────────────────────────────────────────────
# 凭证探测 + 离线 HCL Lint — dry-run 不调 terraform binary
# ─────────────────────────────────────────────────────────

def detect_credentials() -> dict:
    """按优先级探测 AK/SK 凭证,返回 {mode, ak_masked, sk_masked, source}。
    mode ∈ {env, aliyun-cli, ram-role, none}。
    dry-run 模式不强制凭证,仅信息提示。"""
    import os
    ak = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    if ak and sk:
        return {"mode": "env", "ak": ak[:4] + "****", "sk": "****", "source": "ALIBABA_CLOUD_*_KEY_* env"}
    cfg = Path.home() / ".aliyun" / "config.json"
    if cfg.exists():
        try:
            import json as _j
            data = _j.loads(cfg.read_text())
            profiles = data.get("profiles", [data] if "access_key_id" in data else [])
            for p in profiles:
                if p.get("access_key_id"):
                    return {
                        "mode": "aliyun-cli",
                        "ak": p["access_key_id"][:4] + "****",
                        "sk": "****",
                        "source": str(cfg),
                    }
        except Exception:
            pass
    return {"mode": "none", "ak": None, "sk": None, "source": None}


def lint_hcl(work_dir: Path) -> dict:
    """离线 HCL Lint — 不调 terraform,纯 Python 语法/结构检查。
    返回 {ok, errors:[{file,line,msg}], warnings:[...]}。
    检查项:花括号配平、provider 块、resource 块、module 块、变量引用闭合。"""
    import re as _re
    errors, warnings = [], []
    tf_files = sorted(work_dir.glob("**/*.tf"))
    if not tf_files:
        return {"ok": False, "errors": [{"file": "(dir)", "line": 0, "msg": "未发现 .tf 文件"}], "warnings": []}
    # 先收集所有 variables.tf 中定义的变量(含 modules/ 下的)
    all_defined_vars = set()
    for vf in tf_files:
        if vf.name == "variables.tf":
            try:
                t = _re.sub(r"#.*", "", vf.read_text(encoding="utf-8"))
                all_defined_vars.update(_re.findall(r'variable\s+"([^"]+)"', t))
            except Exception:
                pass
    for tf in tf_files:
        try:
            text = tf.read_text(encoding="utf-8")
        except Exception as e:
            errors.append({"file": str(tf), "line": 0, "msg": f"读取失败: {e}"})
            continue
        # 1) 花括号配平
        cleaned = _re.sub(r"#.*", "", text)
        cleaned = _re.sub(r'""".*?"""', "", cleaned, flags=_re.DOTALL)
        opens, closes = cleaned.count("{"), cleaned.count("}")
        if opens != closes:
            errors.append({"file": str(tf), "line": 0, "msg": f"花括号不配平: {{ x {opens}, }} x {closes}"})
        # 2) resource 块检查: 仅对 main.tf 与 modules/*/main.tf 报错, variables.tf/outputs.tf/versions.tf 跳过
        fname = tf.name
        is_resource_file = fname == "main.tf"
        if is_resource_file and not _re.search(r'resource\s+"[^"]+"\s+"[^"]+"\s*\{', cleaned) and not _re.search(r'module\s+"[^"]+"\s*\{', cleaned):
            warnings.append({"file": str(tf), "line": 0, "msg": "main.tf 缺少 resource 或 module 块"})
        # 3) var.X 引用必须已定义(全工程范围)
        var_refs = set(_re.findall(r"var\.([A-Za-z_][A-Za-z0-9_]*)", cleaned))
        undefined = var_refs - all_defined_vars
        for u in sorted(undefined):
            warnings.append({"file": str(tf), "line": 0, "msg": f"var.{u} 引用了未定义的变量"})
        # 4) required_providers 块: 仅在包含 alicloud resource/module 的文件中检查
        uses_alicloud = bool(_re.search(r'(alicloud_[a-z_]+|aliyun/alicloud)', cleaned))
        has_required_providers = bool(_re.search(r'required_providers\s*\{[^}]*aliyun/alicloud', cleaned, _re.DOTALL))
        if uses_alicloud and not has_required_providers and "/modules/" not in str(tf).replace(str(work_dir), ""):
            # 根目录的 .tf 缺 required_providers 提示
            warnings.append({"file": str(tf), "line": 0, "msg": "引用了 alicloud 但缺少 required_providers { aliyun/alicloud }"})
        # modules/ 下的 .tf 继承根目录的 provider, 不需重复声明
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "files_checked": len(tf_files)}


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


# ─────────────────────────────────────────────────────────
# 流式子进程执行器 — 逐行打印 stdout/stderr + 耗时 + 心跳
# ─────────────────────────────────────────────────────────

def stream_cmd(phase: str, cmd: list, cwd: Path, timeout: int = 60) -> CommandRecord:
    """执行子进程并逐行流式输出 stdout/stderr。
    返回 CommandRecord 对象。
    每 5 秒打一次心跳,超时 kill。
    自动设置 TF_PLUGIN_CACHE_DIR 复用已下载的 provider 插件。
    使用 select + 非阻塞读,确保超时检查不被 readline 阻塞。"""
    import select as _select
    t0 = time.time()
    cmd_str = " ".join(cmd)
    print(f"{Colors.CYAN}│{Colors.END}   $ {cmd_str}  (timeout={timeout}s)", flush=True)
    # Terraform 插件缓存
    env = os.environ.copy()
    cache_dir = os.path.join(os.path.expanduser("~"), ".terraform.d", "plugin-cache")
    if "TF_PLUGIN_CACHE_DIR" not in env:
        env["TF_PLUGIN_CACHE_DIR"] = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        cached_plugins = list(Path(cache_dir).rglob("*terraform*provider*")) if Path(cache_dir).exists() else []
        if cached_plugins:
            print(f"{Colors.CYAN}│{Colors.END}   💾 插件缓存命中: {cache_dir} ({len(cached_plugins)} 个文件)", flush=True)
            # 缓存命中时把 plugin-cache 当作 filesystem mirror 使用；
            # 不能同时作为 TF_PLUGIN_CACHE_DIR，否则 Terraform 会尝试“安装到自身”。
            env.pop("TF_PLUGIN_CACHE_DIR", None)
            cli_config = cwd / ".terraformrc"
            cli_config.write_text(textwrap.dedent(f"""\
                provider_installation {{
                  filesystem_mirror {{
                    path    = "{cache_dir}"
                    include = ["registry.terraform.io/aliyun/alicloud"]
                  }}
                  direct {{
                    exclude = ["registry.terraform.io/aliyun/alicloud"]
                  }}
                }}
            """), encoding="utf-8")
            env["TF_CLI_CONFIG_FILE"] = str(cli_config)
            print(f"{Colors.CYAN}│{Colors.END}   🔌 本地 provider mirror 已启用: {cli_config}", flush=True)
        else:
            print(f"{Colors.CYAN}│{Colors.END}   📦 首次运行,插件将下载到缓存: {cache_dir}", flush=True)
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=0,
        env=env
    )
    last_beat = t0
    lines = []
    fd = proc.stdout.fileno()
    while True:
        now = time.time()
        remaining = timeout - (now - t0)
        if remaining <= 0:
            proc.kill()
            print(f"{Colors.RED}│{Colors.END}   ✗ 超时 {timeout}s,已 kill", flush=True)
            break
        if now - last_beat > 5:
            elapsed = int(now - t0)
            print(f"{Colors.CYAN}│{Colors.END}   ⏱ 仍在运行... {elapsed}s", flush=True)
            last_beat = now
        r, _, _ = _select.select([fd], [], [], min(1.0, remaining))
        if r:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            lines.append(line)
            if line.strip():
                print(f"{Colors.CYAN}│{Colors.END}   {line}", flush=True)
        if proc.poll() is not None:
            for rest in proc.stdout.readlines():
                rest = rest.rstrip()
                lines.append(rest)
                if rest.strip():
                    print(f"{Colors.CYAN}│{Colors.END}   {rest}", flush=True)
            break
    elapsed_ms = int((time.time() - t0) * 1000)
    full_out = "\n".join(lines)
    return CommandRecord(
        phase=phase,
        command=cmd_str,
        working_directory=str(cwd),
        exit_code=proc.returncode if proc.poll() is not None else -1,
        stdout_excerpt=full_out[:2000],
        stderr_excerpt="",
        duration_ms=elapsed_ms,
    )


def check_registry() -> bool:
    """检查 Terraform registry 是否可达。
    返回 True=可达, False=不可达(跳过 terraform 步骤)。"""
    import socket as _socket
    try:
        _socket.create_connection(("registry.terraform.io", 443), timeout=3).close()
        return True
    except Exception:
        return False


RESOURCE_TYPE_LABELS = {
    "alicloud_vpc": "vpc",
    "alicloud_vswitch": "vswitch",
    "alicloud_instance": "ecs",
    "alicloud_db_instance": "rds",
    "alicloud_kvstore_instance": "redis",
    "alicloud_slb": "slb",
    "alicloud_nat_gateway": "nat",
    "alicloud_eip": "eip",
    "alicloud_security_group": "security_group",
    "alicloud_route_table": "route_table",
    "alicloud_disk": "disk",
}


def intent_to_hitl_resources(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将 parse_intent 结果转为 HITL Mode A ResourceInfo 兼容结构."""
    resources: List[Dict[str, Any]] = []
    for tf_type in intent.get("resources", []):
        label = RESOURCE_TYPE_LABELS.get(tf_type, tf_type.replace("alicloud_", ""))
        attrs: Dict[str, Any] = {}
        if tf_type == "alicloud_instance":
            attrs["count"] = intent.get("count", 1)
            if intent.get("instance_type"):
                attrs["instance_type"] = intent["instance_type"]
            if intent.get("data_disk_size"):
                attrs["data_disk_size"] = intent["data_disk_size"]
        if tf_type == "alicloud_vpc" and intent.get("az_count"):
            attrs["az_count"] = intent["az_count"]
        resources.append({
            "type": label,
            "name": label,
            "status": "pending",
            "attributes": attrs,
        })
    return resources


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
        r"route.?table|路由表": "alicloud_route_table",
        r"独立云盘|独立磁盘|standalone\s*disk|单独.*云盘": "alicloud_disk",
    }

    # 1c1g / 1核1G / 1c1m1 常见规格 → 阿里云规格族映射
    INSTANCE_TYPE_PATTERNS = [
        # (regex, instance_type, description)
        (r"1\s*核\s*1\s*[gG]|1c\s*1g|1c1m1|一核一[gG]|1c1g", "ecs.t6-c1m1.large", "突发性能 t6 (1 vCPU / 1 GiB / baseline 20%)"),
        (r"1\s*核\s*2\s*[gG]|1c\s*2g|1c1m2", "ecs.t6-c1m2.large", "突发性能 t6 (1 vCPU / 2 GiB / baseline 20%)"),
        (r"2\s*核\s*4\s*[gG]|2c\s*4g|2c2g|2c2m4", "ecs.t6-c2m4.large", "突发性能 t6 (2 vCPU / 4 GiB / baseline 20%)"),
        (r"2\s*核\s*8\s*[gG]|2c\s*8g|2c2m8", "ecs.g7.large", "通用型 g7 (2 vCPU / 8 GiB)"),
        (r"4\s*核\s*8\s*[gG]|4c\s*8g|4c4m8|均衡.*4\s*核", "ecs.g6.xlarge", "通用型 g6 (4 vCPU / 8 GiB)"),
        (r"4\s*核\s*16\s*[gG]|4c\s*16g|4c4m16", "ecs.g7.xlarge", "通用型 g7 (4 vCPU / 16 GiB)"),
        (r"8\s*核\s*16\s*[gG]|8c\s*16g|8c8m16", "ecs.c7.2xlarge", "计算型 c7 (8 vCPU / 16 GiB)"),
    ]

    # Default configurations per environment
    ENV_DEFAULTS = {
        "int": {
            "vpc_cidr": "10.128.0.0/16",
            "instance_type": "ecs.t6-c1m2.large",
            "rds_class": "rds.mysql.t1.small",
        },
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
        "production": {
            "vpc_cidr": "10.2.0.0/16",
            "instance_type": "ecs.g7.2xlarge",
            "rds_class": "rds.mysql.x4.large",
        },
    }

    def __init__(self, environment: str = "dev", region: str = "cn-hangzhou"):
        self.environment = environment
        self.region = region
        self.defaults = self.ENV_DEFAULTS.get(environment, self.ENV_DEFAULTS["dev"])
        self.resources: List[Dict[str, Any]] = []  # module-first 轨迹用
        self.module_plan = None

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

        # 数据盘大小 (ECS 内联 data_disks)
        data_disk_size = None
        for pattern in (
            r"(\d+)\s*(?:gb?|g|G)\s*(?:的)?\s*数据盘",
            r"数据盘\s*(\d+)\s*(?:gb?|g|G)?",
            r"(\d+)\s*(?:gb?|g|G)\s*(?:的)?\s*(?:独立)?云盘",
            r"云盘\s*(\d+)\s*(?:gb?|g|G)?",
            r"data\s*disk\s*(\d+)",
        ):
            m = re.search(pattern, request_lower, re.IGNORECASE)
            if m:
                data_disk_size = int(m.group(1))
                break

        # 独立云盘 vs ECS 内联数据盘
        wants_standalone_disk = "alicloud_disk" in detected_resources
        if data_disk_size and "alicloud_instance" in detected_resources:
            wants_standalone_disk = False
            if "alicloud_disk" in detected_resources:
                detected_resources = [r for r in detected_resources if r != "alicloud_disk"]

        # 实例规格（查表匹配 + 未命中时收集候选给用户挑）
        instance_type = None
        matched_spec_description = None
        for pattern, ecs_type, desc in self.INSTANCE_TYPE_PATTERNS:
            if re.search(pattern, request_lower, re.IGNORECASE):
                instance_type = ecs_type
                matched_spec_description = desc
                break

        # 未识别时提示候选
        spec_candidates = []
        if not instance_type and "alicloud_instance" in detected_resources:
            # 尝试提取用户给的核数/内存数
            cpu_match = re.search(r"(\d+)\s*核", request_lower)
            mem_match = re.search(r"(\d+)\s*[gG]", request_lower)
            if cpu_match or mem_match:
                # 用户给了数字,展示全表前 4 个
                spec_candidates = self.INSTANCE_TYPE_PATTERNS[:4]
            else:
                spec_candidates = self.INSTANCE_TYPE_PATTERNS[:4]

        return {
            "resources": detected_resources,
            "count": count,
            "az_count": az_count,
            "data_disk_size": data_disk_size,
            "wants_standalone_disk": wants_standalone_disk,
            "instance_type": instance_type,
            "spec_candidates": spec_candidates,
            "raw_request": request,
        }

    def generate_provider(self) -> str:
        """Generate provider.tf with aliyun CLI profile fallback.
        使用精确版本号避免 registry 版本解析耗时。"""
        return textwrap.dedent(f"""\
            terraform {{
              required_providers {{
                alicloud = {{
                  source  = "aliyun/alicloud"
                  version = "= 1.281.0"
                }}
              }}
            }}

            provider "alicloud" {{
              region  = var.region
              profile = "default"
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

    def generate(self, request: str, output_dir: Optional[Path] = None) -> Dict[str, str]:
        """Generate module-first root Terraform configuration from request."""
        intent = self.parse_intent(request)
        self.resources = []
        self.module_plan = plan_modules(intent, self.defaults)

        files: Dict[str, str] = {}
        files["main.tf"] = render_main_tf(self.module_plan, self.environment, self.region)
        files["provider.tf"] = self.generate_provider()
        files["variables.tf"] = self.generate_variables()
        files["outputs.tf"] = render_outputs_tf(self.module_plan)
        files["terraform.tfvars"] = textwrap.dedent(f"""\
            environment = "{self.environment}"
            region      = "{self.region}"
        """)

        self.resources = modules_for_trace(self.module_plan)

        if output_dir is not None:
            copy_modules(output_dir)

        return files


@dataclass
class DryRunResult:
    success: bool
    stdout: str
    stderr: str
    command_records: List[CommandRecord]
    plan_stdout: str = ""


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

    def execute(self) -> DryRunResult:
        """Execute terraform dry-run steps with per-command trace records."""
        steps = [
            ("INIT", ["terraform", "init", "-backend=false"]),
            ("VALIDATE", ["terraform", "validate"]),
            ("PLAN", ["terraform", "plan", "-input=false", "-no-color"]),
        ]

        all_stdout: List[str] = []
        all_stderr: List[str] = []
        command_records: List[CommandRecord] = []
        plan_stdout = ""

        for phase, cmd in steps:
            log_dry_run(phase, f"执行 {' '.join(cmd)}")
            t0 = time.time()

            result = self._run_terraform_safe(cmd)

            stdout = result.stdout if isinstance(result.stdout, str) else (result.stdout or "").decode("utf-8", errors="replace")
            stderr = result.stderr if isinstance(result.stderr, str) else (result.stderr or "").decode("utf-8", errors="replace")
            duration_ms = int((time.time() - t0) * 1000)

            command_records.append(CommandRecord(
                phase=phase,
                command=" ".join(cmd),
                working_directory=str(self.work_dir),
                exit_code=result.returncode,
                stdout_excerpt=stdout[:2000],
                stderr_excerpt=stderr[:2000],
                duration_ms=duration_ms,
            ))

            all_stdout.append(f"=== {phase} ===\n{stdout}")
            all_stderr.append(f"=== {phase} ===\n{stderr}")
            if phase == "PLAN":
                plan_stdout = stdout

            if result.returncode != 0:
                log_dry_run(phase, f"失败 (exit code: {result.returncode})", is_error=True)
                return DryRunResult(
                    success=False,
                    stdout="\n".join(all_stdout),
                    stderr="\n".join(all_stderr),
                    command_records=command_records,
                    plan_stdout=plan_stdout,
                )

            log_dry_run(phase, "成功 ✓")

        return DryRunResult(
            success=True,
            stdout="\n".join(all_stdout),
            stderr="\n".join(all_stderr),
            command_records=command_records,
            plan_stdout=plan_stdout,
        )


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
        choices=["dev", "staging", "production", "int", "uat", "performance"],
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
        default=True,
        help="Dry-run mode (default): 仅生成 HCL + 离线 lint, 不调 terraform binary"
    )
    parser.add_argument(
        "--with-validate",
        action="store_true",
        help="在 dry-run 基础上额外跑 terraform init -backend=false + validate (需 terraform binary)"
    )
    parser.add_argument(
        "--with-plan",
        action="store_true",
        help="在 dry-run 基础上额外跑 terraform plan (需 AK 凭证, 慎用)"
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

    print(f"\n{Colors.BOLD}┌─ Step 1 解析意图{Colors.END}", flush=True)
    print(f"{Colors.CYAN}│{Colors.END} 请求: {args.request}", flush=True)
    intent = generator.parse_intent(args.request)
    print(f"{Colors.CYAN}│{Colors.END} 资源: {', '.join(intent['resources']) or '(未识别)'}", flush=True)
    print(f"{Colors.CYAN}│{Colors.END} 数量: {intent['count']}  可用区: {intent['az_count']}", flush=True)
    print(f"{Colors.CYAN}│{Colors.END} 实例规格: {intent.get('instance_type') or '(未识别,见下方候选)'}", flush=True)

    # 规格未识别 -> 打印候选提示
    spec_cands = intent.get("spec_candidates") or []
    if spec_cands:
        print(f"\n{Colors.YELLOW}│ ⚠ 未识别明确规格,候选清单:{Colors.END}", flush=True)
        for i, (pat, etype, desc) in enumerate(spec_cands, 1):
            print(f"{Colors.YELLOW}│   [{i}] {etype:<24} {desc}{Colors.END}", flush=True)
            print(f"{Colors.YELLOW}│        (匹配表达示例: {pat}){Colors.END}", flush=True)
        print(f"{Colors.YELLOW}│   请调整 --request 表述后重跑, 或手动编辑生成产物中的 main.tf{Colors.END}", flush=True)

    # 凭证探测仅在可能访问云端/provider 的路径执行；默认 dry-run 保持完全离线。
    if not args.dry_run or args.with_plan:
        cred = detect_credentials()
        cred_icon = {"env": "🔑 env", "aliyun-cli": "🔑 aliyun-cli", "ram-role": "🛡  ram-role", "none": "🚫 无"}.get(cred["mode"], "?")
        print(f"{Colors.CYAN}│{Colors.END} 凭证: {cred_icon}  (来源: {cred['source'] or 'N/A'})", flush=True)
    else:
        print(f"{Colors.CYAN}│{Colors.END} 凭证: ⏭ 默认 dry-run 离线模式跳过探测", flush=True)

    # Safety Gate: 破坏性关键词检测
    DESTRUCTIVE_KEYWORDS = ["删除", "销毁", "释放", "destroy", "delete", "drop", "terminate", "tear down", "rm -rf"]
    req_lower = args.request.lower()
    for kw in DESTRUCTIVE_KEYWORDS:
        if kw in req_lower:
            print(f"\n{Colors.RED}┌─ ⛔ SAFETY GATE 拦截{Colors.END}", flush=True)
            print(f"{Colors.RED}│{Colors.END}   检测到破坏性关键词: [{kw}]", flush=True)
            print(f"{Colors.RED}│{Colors.END}   请求: {args.request}", flush=True)
            print(f"{Colors.RED}│{Colors.END}   dry-run 模式下禁止生成破坏性配置。", flush=True)
            print(f"{Colors.RED}│{Colors.END}   如需确认操作,请使用 --confirm-destructive 显式声明。", flush=True)
            sys.exit(4)

    # Dry-run mode: 默认仅生成 HCL + 离线 lint；Terraform 步骤由 --with-validate/--with-plan 显式开启。
    if args.dry_run:
        print_dry_run_banner()
        t0 = time.time()
        print(f"\n{Colors.BOLD}┌─ Step 2 生成 HCL{Colors.END}", flush=True)

        with tempfile.TemporaryDirectory(prefix="tf-dryrun-") as tmpdir:
            work_dir = Path(tmpdir)
            files = generator.generate(args.request, output_dir=work_dir)
            for filename, content in files.items():
                file_path = work_dir / filename
                file_path.write_text(content, encoding="utf-8")
                print(f"{Colors.CYAN}│{Colors.END}   [WRITE] {filename:<20} ({len(content):>5} B)", flush=True)

            # 复制 modules/
            src_modules = Path(__file__).parent.parent / "modules"
            if src_modules.exists():
                import shutil
                dst_modules = work_dir / "modules"
                if dst_modules.exists():
                    shutil.rmtree(dst_modules)
                shutil.copytree(src_modules, dst_modules)
                mod_count = sum(1 for _ in dst_modules.rglob("*.tf"))
                print(f"{Colors.CYAN}│{Colors.END}   [WRITE] modules/          ({mod_count} tf files)", flush=True)

            # Step 3: 离线 lint (快速, 不调 terraform)
            print(f"\n{Colors.BOLD}┌─ Step 3 离线 HCL Lint{Colors.END}", flush=True)
            lint = lint_hcl(work_dir)
            for e in lint["errors"]:
                print(f"{Colors.RED}│{Colors.END}   [ERROR] {e['file']}: {e['msg']}", flush=True)
            for w in lint["warnings"]:
                print(f"{Colors.YELLOW}│{Colors.END}   [WARN]  {w['file']}: {w['msg']}", flush=True)
            if lint["ok"] and not lint["warnings"]:
                print(f"{Colors.GREEN}│{Colors.END}   ✓ 检查 {lint['files_checked']} 个 .tf 文件, 0 错 0 警", flush=True)
            elif lint["ok"]:
                print(f"{Colors.GREEN}│{Colors.END}   ✓ 通过 (有 {len(lint['warnings'])} 个警告, 见上)", flush=True)
            else:
                print(f"{Colors.RED}│{Colors.END}   ✗ {len(lint['errors'])} 个错误", flush=True)

            # Step 4-6: Terraform 步骤仅在显式 flag 下执行。默认 dry-run 不做 registry/terraform/凭证访问。
            tf_commands: List[CommandRecord] = []
            init_ok = True
            validate_ok = True
            plan_ok = True
            plan_stdout = ""
            terraform_requested = args.with_validate or args.with_plan
            registry_ok = True

            if terraform_requested:
                registry_ok = check_registry()
                if not registry_ok:
                    print(f"\n{Colors.YELLOW}┌─ 网络诊断{Colors.END}", flush=True)
                    print(f"{Colors.YELLOW}│{Colors.END}   ⚠ registry.terraform.io 不可达 (TLS 超时)", flush=True)
                    print(f"{Colors.YELLOW}│{Colors.END}   terraform init/validate/plan 将跳过", flush=True)
                    print(f"{Colors.YELLOW}│{Colors.END}   如需运行 terraform 步骤,请确保网络连通", flush=True)

                if registry_ok:
                    print(f"\n{Colors.BOLD}┌─ Step 4 terraform init -backend=false (timeout=60s){Colors.END}", flush=True)
                    init_rec = stream_cmd("INIT", ["terraform", "init", "-backend=false"], work_dir, timeout=60)
                    tf_commands.append(init_rec)
                    print(f"{Colors.CYAN}│{Colors.END}   ── exit={init_rec.exit_code} 耗时={init_rec.duration_ms}ms", flush=True)
                    init_ok = init_rec.exit_code == 0

                    if init_ok:
                        print(f"\n{Colors.BOLD}┌─ Step 5 terraform validate (timeout=60s){Colors.END}", flush=True)
                        val_rec = stream_cmd("VALIDATE", ["terraform", "validate"], work_dir, timeout=60)
                        tf_commands.append(val_rec)
                        print(f"{Colors.CYAN}│{Colors.END}   ── exit={val_rec.exit_code} 耗时={val_rec.duration_ms}ms", flush=True)
                        validate_ok = val_rec.exit_code == 0
                    else:
                        print(f"{Colors.YELLOW}│{Colors.END}   ⏭ init 失败,跳过 validate", flush=True)
                        validate_ok = False

                    if args.with_plan:
                        if init_ok and validate_ok:
                            print(f"\n{Colors.BOLD}┌─ Step 6 terraform plan -input=false -no-color (timeout=60s){Colors.END}", flush=True)
                            plan_rec = stream_cmd("PLAN", ["terraform", "plan", "-input=false", "-no-color"], work_dir, timeout=60)
                            plan_stdout = plan_rec.stdout_excerpt
                            tf_commands.append(plan_rec)
                            print(f"{Colors.CYAN}│{Colors.END}   ── exit={plan_rec.exit_code} 耗时={plan_rec.duration_ms}ms", flush=True)
                            if plan_rec.exit_code != 0:
                                stderr = plan_rec.stdout_excerpt or ""
                                if any(k in stderr for k in ("NoCredential","InvalidAccessKeyId","credentials","Unauthorized","access key")):
                                    print(f"{Colors.YELLOW}│{Colors.END}   分类: 凭证问题 (HCL OK, 需 AK)", flush=True)
                                elif any(k in stderr for k in ("Error:","Invalid","Unsupported")):
                                    print(f"{Colors.RED}│{Colors.END}   分类: HCL 错误,需修复", flush=True)
                                else:
                                    print(f"{Colors.YELLOW}│{Colors.END}   分类: 其他错误 (见上方输出)", flush=True)
                                plan_ok = False
                            else:
                                plan_ok = True
                        else:
                            print(f"{Colors.YELLOW}│{Colors.END}   ⏭ init/validate 未全部通过,跳过 plan", flush=True)
                            plan_ok = False
                    else:
                        print(f"{Colors.YELLOW}│{Colors.END}   ⏭ 未设置 --with-plan,跳过 terraform plan", flush=True)
                        plan_ok = True
                else:
                    print(f"\n{Colors.YELLOW}┌─ Step 4-6 terraform 步骤 (跳过 - registry 不可达){Colors.END}", flush=True)
            else:
                print(f"\n{Colors.CYAN}┌─ Step 4 Terraform 步骤{Colors.END}", flush=True)
                print(f"{Colors.CYAN}│{Colors.END}   ⏭ 默认 dry-run 离线模式: 未调用 terraform/registry/凭证探测", flush=True)

            # Step 7: 写 GCL trace
            elapsed_ms = int((time.time() - t0) * 1000)
            terraform_ok = (not terraform_requested) or (registry_ok and init_ok and validate_ok and plan_ok)
            overall_ok = lint["ok"] and terraform_ok
            if overall_ok:
                conclusion = "✅ 通过"
                if terraform_requested:
                    conclusion_detail = "HCL 生成、Lint 与请求的 Terraform 步骤均通过"
                else:
                    conclusion_detail = "HCL 生成与离线 Lint 通过（未调用 terraform）"
                conclusion_color = Colors.GREEN
            elif lint["ok"] and not terraform_ok:
                conclusion = "⚠️ 部分通过"
                conclusion_detail = "HCL 生成与 Lint 通过，但 Terraform 步骤未全部通过"
                conclusion_color = Colors.YELLOW
            else:
                conclusion = "❌ 未通过"
                conclusion_detail = "HCL 生成或 Lint 存在错误"
                conclusion_color = Colors.RED

            trace_path = persist_dry_run_trace(
                operation="nl2hcl",
                environment=args.environment,
                region=args.region,
                request=args.request,
                work_dir=work_dir,
                command_records=tf_commands,
                success=overall_ok,
                plan_stdout=plan_stdout,
                intent=intent,
            )

            # 同步把 HCL 写一份到 --output-dir
            if args.output_dir:
                args.output_dir.mkdir(parents=True, exist_ok=True)
                for fname, content in files.items():
                    (args.output_dir / fname).write_text(content, encoding="utf-8")
                if (work_dir / "modules").exists():
                    import shutil
                    dst_m = args.output_dir / "modules"
                    if dst_m.exists():
                        shutil.rmtree(dst_m)
                    shutil.copytree(work_dir / "modules", dst_m)

            # 最终摘要 — 结论先行
            print(f"\n{conclusion_color}┌─ 结论: {conclusion}{Colors.END}", flush=True)
            print(f"{conclusion_color}│{Colors.END}   {conclusion_detail}", flush=True)
            print(f"{Colors.CYAN}│{Colors.END}   HCL:     {args.output_dir.absolute()}", flush=True)
            print(f"{Colors.CYAN}│{Colors.END}   Trace:   {trace_path}", flush=True)
            print(f"{Colors.CYAN}│{Colors.END}   总耗时:  {elapsed_ms} ms", flush=True)
            if tf_commands:
                for rec in tf_commands:
                    ok = rec.exit_code == 0
                    icon = "✓" if ok else "✗"
                    print(f"{Colors.CYAN}│{Colors.END}   {rec.phase:<8} {icon} ({rec.duration_ms}ms)", flush=True)
            elif terraform_requested and not registry_ok:
                print(f"{Colors.YELLOW}│{Colors.END}   terraform 步骤: ⏭ 跳过 (registry 不可达)", flush=True)
                print(f"{Colors.YELLOW}│{Colors.END}   请求的 Terraform 校验未执行: registry.terraform.io 不可达", flush=True)
            else:
                print(f"{Colors.CYAN}│{Colors.END}   terraform 步骤: ⏭ 默认 dry-run 离线跳过", flush=True)
            print(f"{conclusion_color}│{Colors.END}   结果: {conclusion} ({conclusion_detail}){Colors.END}", flush=True)

            if terraform_requested and not terraform_ok:
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

    else:
        print_exec_banner()

        args.output_dir.mkdir(parents=True, exist_ok=True)
        files = generator.generate(args.request, output_dir=args.output_dir)

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
