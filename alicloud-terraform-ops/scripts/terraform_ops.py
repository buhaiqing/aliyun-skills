#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
terraform_ops.py — alicloud-terraform-ops 统一 CLI 入口

用法:
  python terraform_ops.py create --request "创建 VPC" --mode cli
  python terraform_ops.py wizard nl2hcl --quick --template vpc-basic
  python terraform_ops.py import --type vpc --id vpc-xxx --dry-run
  python terraform_ops.py pause|resume|list|cleanup
  python terraform_ops.py pr-create|pr-status|pr-apply

别名: aliyun-terraform (见 README)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _run_script(script: str, extra_args: list[str]) -> int:
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + extra_args
    return subprocess.call(cmd)


def _run_mode_a(args: argparse.Namespace) -> int:
    cmd = ["--type", args.workflow_type, "--env", args.environment]
    if args.resume:
        cmd.extend(["--resume", args.resume])
    elif args.list:
        cmd.append("--list")
    else:
        if args.request:
            pass  # NL2HCL request handled via wizard/create flow
    return _run_script("hitl_mode_a.py", cmd)


def _run_mode_c(args: argparse.Namespace, command: str) -> int:
    cmd = [command]
    if command == "resume" and args.checkpoint_id:
        cmd.append(args.checkpoint_id)
        if getattr(args, "yes", False):
            cmd.append("--yes")
    elif command == "pause" and args.checkpoint_id:
        cmd.append(args.checkpoint_id)
    elif command == "delete" and args.checkpoint_id:
        cmd.append(args.checkpoint_id)
    elif command == "cleanup":
        if getattr(args, "dry_run", False):
            cmd.append("--dry-run")
    return _run_script("hitl_mode_c.py", cmd)


def _run_mode_b(args: argparse.Namespace, command: str) -> int:
    cmd = [command.replace("pr-", "").replace("_", "-")]
    if command in ("pr-create", "create-pr"):
        cmd = ["create-pr", "--type", args.workflow_type, "--env", args.environment]
        if args.files_dir:
            cmd.extend(["--files-dir", str(args.files_dir)])
    elif command in ("pr-status", "status") and args.pr_id:
        cmd.extend([args.pr_id])
    elif command in ("pr-apply", "merge") and args.pr_id:
        cmd = ["merge", args.pr_id]
    return _run_script("hitl_mode_b.py", cmd)


def _hitl_environment_name(environment: str) -> str:
    """NL2HCL 环境名 → HITL 五级环境（staging 映射 uat）。"""
    if environment == "staging":
        return "uat"
    return environment


def _run_create_with_hitl(args: argparse.Namespace) -> int:
    """NL2HCL 生成后将产物注入 HITL Mode A 检查点并进入 CP1-CP3。"""
    from hitl_mode_a import (
        CLIController,
        CheckpointStore,
        CheckpointType,
        UserAbortedError,
        create_checkpoint,
    )
    from nl2hcl_generator import NL2HCLGenerator, intent_to_hitl_resources

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = NL2HCLGenerator(environment=args.environment, region=args.region)
    intent = generator.parse_intent(args.request)
    if not intent.get("resources"):
        print("错误: 未能从请求中识别资源，请调整 --request 后重试", file=sys.stderr)
        return 1

    files = generator.generate(args.request, output_dir=output_dir)
    for filename, content in files.items():
        (output_dir / filename).write_text(content, encoding="utf-8")

    hitl_env = _hitl_environment_name(args.environment)
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType(args.workflow_type),
        environment=hitl_env,
        resources=intent_to_hitl_resources(intent),
        generated_files=files,
        user_inputs={
            "request": args.request,
            "output_dir": str(output_dir),
            "region": args.region,
            "environment": args.environment,
        },
    )

    store = CheckpointStore()
    store.save(checkpoint)
    print(f"HITL 检查点已创建: {checkpoint.id}")
    print(f"生成目录: {output_dir}")

    controller = CLIController(checkpoint, store)
    try:
        controller.run()
    except UserAbortedError:
        return 1
    return 0


def _run_nl2hcl(args: argparse.Namespace) -> int:
    cmd = [
        "--request", args.request,
        "--environment", args.environment,
        "--region", args.region,
        "--output-dir", str(args.output_dir),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.gcl_check:
        cmd.append("--gcl-check")
    if args.wizard:
        cmd.append("--wizard")
    return _run_script("nl2hcl_generator.py", cmd)


def _run_import(args: argparse.Namespace) -> int:
    cmd = [
        "--resource-type", args.resource_type,
        "--region", args.region,
        "--output-dir", str(args.output_dir),
    ]
    if args.resource_id:
        cmd.extend(["--resource-id", args.resource_id])
    if args.resource_ids:
        cmd.extend(["--resource-ids", args.resource_ids])
    if args.dry_run:
        cmd.append("--dry-run")
    if args.discover_associated:
        cmd.append("--discover-associated")
    if args.skip_preflight:
        cmd.append("--skip-preflight")
    return _run_script("reverse_engineering.py", cmd)


def _run_wizard(args: argparse.Namespace) -> int:
    from wizard_cli import build_wizard_parser, run_wizard_command
    return run_wizard_command(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terraform-ops",
        description="Alibaba Cloud Terraform IaC Operations",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["cli", "pr", "checkpoint"],
        default="cli",
        help="HITL 模式 (默认 cli)",
    )
    parser.add_argument("--config", type=Path, help="HITL 配置文件路径")

    sub = parser.add_subparsers(dest="command", required=True)

    # create — NL2HCL + HITL
    create = sub.add_parser("create", help="自然语言生成 Terraform (NL2HCL)")
    create.add_argument("--request", "-r", required=True, help="自然语言描述")
    create.add_argument("--environment", "-e", default="dev")
    create.add_argument("--region", "-R", default="cn-hangzhou")
    create.add_argument("--output-dir", "-o", type=Path, default=Path("./generated"))
    create.add_argument("--dry-run", "-d", action="store_true")
    create.add_argument("--gcl-check", action="store_true")
    create.add_argument("--wizard", "-w", action="store_true")
    create.add_argument("--workflow-type", "-t", default="nl2hcl", choices=["nl2hcl", "import", "apply", "destroy"])

    # wizard
    from wizard_cli import build_wizard_parser
    build_wizard_parser(sub)

    # import — reverse engineering
    imp = sub.add_parser("import", help="逆向工程导入现有资源")
    imp.add_argument("--resource-type", "-t", required=True)
    imp.add_argument("--resource-id", "-i")
    imp.add_argument("--resource-ids")
    imp.add_argument("--region", "-r", default="cn-hangzhou")
    imp.add_argument("--output-dir", "-o", type=Path, default=Path("./generated"))
    imp.add_argument("--dry-run", "-d", action="store_true")
    imp.add_argument("--discover-associated", "-D", action="store_true")
    imp.add_argument("--skip-preflight", action="store_true")

    # checkpoint commands (Mode C)
    for name, help_text in [
        ("list", "列出活跃检查点"),
        ("pause", "暂停检查点"),
        ("resume", "恢复检查点"),
        ("cleanup", "清理过期检查点"),
        ("delete", "删除检查点"),
    ]:
        sp = sub.add_parser(name, help=help_text)
        if name in ("pause", "resume", "delete"):
            sp.add_argument("checkpoint_id", nargs="?", default=None)
        if name == "resume":
            sp.add_argument("--yes", "-y", action="store_true")
        if name == "cleanup":
            sp.add_argument("--dry-run", action="store_true")

    # PR commands (Mode B)
    pr_create = sub.add_parser("pr-create", help="创建 Terraform PR")
    pr_create.add_argument("--workflow-type", "-t", default="nl2hcl", choices=["nl2hcl", "import", "apply"])
    pr_create.add_argument("--environment", "-e", default="dev")
    pr_create.add_argument("--files-dir", type=Path)

    pr_status = sub.add_parser("pr-status", help="查询 PR 状态")
    pr_status.add_argument("pr_id")

    pr_apply = sub.add_parser("pr-apply", help="合并/应用 PR")
    pr_apply.add_argument("pr_id")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 加载配置 (环境变量由 hitl_common.HITLConfig 自动处理)
    if args.config:
        os.environ["TF_OPS_CONFIG"] = str(args.config)

    cmd = args.command

    if cmd == "create":
        if args.mode == "cli" and not args.wizard and not args.dry_run:
            return _run_create_with_hitl(args)
        return _run_nl2hcl(args)

    if cmd == "wizard":
        return _run_wizard(args)

    if cmd == "import":
        return _run_import(args)

    if cmd in ("list", "pause", "resume", "cleanup", "delete"):
        return _run_mode_c(args, cmd)

    if cmd == "pr-create":
        return _run_mode_b(args, "pr-create")

    if cmd == "pr-status":
        return _run_mode_b(args, "pr-status")

    if cmd == "pr-apply":
        return _run_mode_b(args, "pr-apply")

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
