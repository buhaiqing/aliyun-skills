#!/usr/bin/env python3
"""
terraform_ops.py — alicloud-terraform-ops 统一 CLI 入口

用法:
  python terraform_ops.py create --request "创建 VPC" --mode cli
  python terraform_ops.py wizard nl2hcl --quick --template vpc-basic
  python terraform_ops.py import --type vpc --id vpc-xxx --dry-run
  python terraform_ops.py apply -e dev
  python terraform_ops.py create -r "..." -e dev   # → .runtime/terraform-ops/nl2hcl/dev/
  python terraform_ops.py destroy -e dev --dry-run
  python terraform_ops.py pause|resume|list|cleanup
  python terraform_ops.py pr-create|pr-status|pr-apply

别名: aliyun-terraform (见 README)
"""

from __future__ import annotations

import argparse
import os
import shutil
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
        CheckpointStore,
        CheckpointType,
        CLIController,
        UserAbortedError,
        create_checkpoint,
    )
    from module_coverage import check_nl2hcl_coverage, format_coverage_halt
    from nl2hcl_generator import CoverageGapError, NL2HCLGenerator, intent_to_hitl_resources

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = NL2HCLGenerator(environment=args.environment, region=args.region)
    intent = generator.parse_intent(args.request)
    coverage = check_nl2hcl_coverage(intent, args.request)
    if coverage.must_halt:
        print(format_coverage_halt(coverage), file=sys.stderr)
        return 6
    if not intent.get("resources") and not coverage.keyword_hits:
        print("错误: 未能从请求中识别资源，请调整 --request 后重试", file=sys.stderr)
        return 1

    try:
        files = generator.generate(args.request, output_dir=output_dir)
    except CoverageGapError as exc:
        print(str(exc), file=sys.stderr)
        return 6
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


def _parse_import_resource_ids(args: argparse.Namespace) -> list[str]:
    ids: list[str] = []
    if args.resource_id:
        ids.append(args.resource_id)
    if args.resource_ids:
        ids.extend(x.strip() for x in args.resource_ids.split(",") if x.strip())
    return ids


def _run_import_with_hitl(args: argparse.Namespace) -> int:
    """逆向工程生成 HCL 后注入 HITL Mode A IMPORT 检查点（CP1→CP4→CP3）。"""
    from hitl_mode_a import (
        CheckpointStore,
        CheckpointType,
        CLIController,
        UserAbortedError,
        create_checkpoint,
    )
    from reverse_engineering import (
        ReverseEngineering,
        collect_output_previews,
        import_resources_for_hitl,
    )

    resource_ids = _parse_import_resource_ids(args)
    if not resource_ids:
        print("错误: 请指定 --resource-id 或 --resource-ids", file=sys.stderr)
        return 1

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = ReverseEngineering(
        region=args.region,
        output_dir=output_dir,
        skip_preflight=args.skip_preflight,
    )
    success, all_resources = engine.run(
        resource_type=args.resource_type,
        resource_ids=resource_ids,
        discover_associated=args.discover_associated,
        dry_run=False,
    )
    if not success or not all_resources:
        print("错误: 逆向工程未生成资源", file=sys.stderr)
        return 1

    generated_files = collect_output_previews(output_dir)
    hitl_env = _hitl_environment_name(args.environment)
    request = f"导入 {args.resource_type}: {', '.join(resource_ids)}"

    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.IMPORT,
        environment=hitl_env,
        resources=import_resources_for_hitl(all_resources),
        generated_files=generated_files,
        user_inputs={
            "request": request,
            "output_dir": str(output_dir),
            "region": args.region,
            "environment": args.environment,
            "resource_type": args.resource_type,
            "resource_ids": resource_ids,
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


def _maybe_run_gcl(args: argparse.Namespace, operation: str, command: str) -> bool:
    if not getattr(args, "gcl_check", False):
        return True
    from nl2hcl_generator import run_gcl_check

    rubric_path = SCRIPT_DIR.parent / "references" / "rubric.md"
    passed, _trace = run_gcl_check(
        "alicloud-terraform-ops",
        operation,
        command,
        rubric_path,
        max_iter=2,
    )
    if not passed:
        print("GCL 检查未通过，已中止", file=sys.stderr)
        return False
    return True


from runtime_paths import (
    default_env_runtime,
    resolve_output_dir,
    template_env_root,
)


def _resolve_output_dir(args: argparse.Namespace, kind: str) -> None:
    if getattr(args, "output_dir", None) is None:
        batch = getattr(args, "resource_type", None) if kind == "import" else None
        args.output_dir = resolve_output_dir(
            None,
            kind=kind,
            environment=getattr(args, "environment", "dev"),
            batch=batch,
        )


def _ensure_runtime_work_dir(environment: str) -> Path:
    """从 environments/<env> 模板初始化 .runtime/terraform-ops/environments/<env>。"""
    work_dir = default_env_runtime(environment)
    template_dir = template_env_root() / environment
    if not template_dir.is_dir():
        raise FileNotFoundError(
            f"环境模板不存在: {template_dir} "
            f"(可用: dev/staging/prod)"
        )

    if not (work_dir / "main.tf").is_file():
        work_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(template_dir.iterdir()):
            if not item.is_file():
                continue
            dest = work_dir / item.name
            shutil.copy2(item, dest)
            if item.name == "main.tf":
                content = dest.read_text(encoding="utf-8")
                content = content.replace(
                    'source = "../../modules/',
                    'source = "../../../modules/',
                )
                dest.write_text(content, encoding="utf-8")
    return work_dir.resolve()


def _default_work_dir(environment: str) -> Path:
    return _ensure_runtime_work_dir(environment)


def _resolve_work_dir(args: argparse.Namespace) -> Path:
    work_dir = getattr(args, "work_dir", None) or getattr(args, "output_dir", None)
    if work_dir is None:
        return _default_work_dir(args.environment)
    return Path(work_dir).resolve()


def _validate_work_dir(work_dir: Path) -> str | None:
    if not work_dir.is_dir():
        return f"工作目录不存在: {work_dir}"
    tf_files = list(work_dir.glob("*.tf"))
    if not tf_files:
        return f"目录中未找到 *.tf 文件: {work_dir}"
    return None


def _run_apply_with_hitl(args: argparse.Namespace) -> int:
    from hitl_mode_a import (
        CheckpointStatus,
        CheckpointStore,
        CheckpointType,
        CLIController,
        UserAbortedError,
        create_checkpoint,
    )
    from terraform_executor import TerraformExecutor, seed_plan_step_data

    work_dir = _resolve_work_dir(args)
    err = _validate_work_dir(work_dir)
    if err:
        print(f"错误: {err}", file=sys.stderr)
        return 1

    executor = TerraformExecutor()
    plan_result = executor.plan_apply(
        work_dir,
        use_backend=not args.offline,
        plan_out=work_dir / "tfplan",
    )
    if not plan_result.success:
        print(f"错误: {plan_result.error}", file=sys.stderr)
        return 1

    apply_cmd = f"terraform apply {work_dir / 'tfplan'}"
    if not _maybe_run_gcl(args, "Apply", apply_cmd):
        return 5

    hitl_env = _hitl_environment_name(args.environment)
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.APPLY,
        environment=hitl_env,
        resources=[],
        user_inputs={
            "request": f"terraform apply @ {work_dir}",
            "output_dir": str(work_dir),
            "region": args.region,
            "environment": args.environment,
            "plan_file": str(work_dir / "tfplan"),
        },
    )
    if checkpoint.steps:
        checkpoint.steps[0].data.update(seed_plan_step_data(plan_result))

    store = CheckpointStore()
    store.save(checkpoint)
    print(f"HITL 检查点已创建: {checkpoint.id}")

    controller = CLIController(checkpoint, store)
    try:
        checkpoint = controller.run()
    except UserAbortedError:
        return 1

    if checkpoint.status != CheckpointStatus.COMPLETED:
        print("HITL 未完成，跳过 terraform apply", file=sys.stderr)
        return 1

    print("正在执行 terraform apply...")
    apply_result = executor.apply(work_dir, work_dir / "tfplan")
    if not apply_result.success:
        print(f"错误: {apply_result.error}", file=sys.stderr)
        return 1
    print(apply_result.stdout)
    print(f"terraform apply 完成: {work_dir}")
    return 0


def _run_apply(args: argparse.Namespace) -> int:
    from terraform_executor import TerraformExecutor

    work_dir = _resolve_work_dir(args)
    err = _validate_work_dir(work_dir)
    if err:
        print(f"错误: {err}", file=sys.stderr)
        return 1

    executor = TerraformExecutor()
    plan_result = executor.plan_apply(
        work_dir,
        use_backend=not args.offline,
        plan_out=work_dir / "tfplan" if not args.dry_run else None,
    )
    if not plan_result.success:
        print(f"错误: {plan_result.error}", file=sys.stderr)
        return 1
    print(plan_result.plan_stdout)
    if plan_result.plan_stderr:
        print(plan_result.plan_stderr, file=sys.stderr)
    return 0


def _run_destroy_with_hitl(args: argparse.Namespace) -> int:
    from hitl_mode_a import (
        CheckpointStatus,
        CheckpointStore,
        CheckpointType,
        CLIController,
        UserAbortedError,
        create_checkpoint,
    )
    from terraform_executor import TerraformExecutor, plan_summary_to_resources

    work_dir = _resolve_work_dir(args)
    err = _validate_work_dir(work_dir)
    if err:
        print(f"错误: {err}", file=sys.stderr)
        return 1

    executor = TerraformExecutor()
    backup = executor.state_backup(work_dir)
    if not backup.success:
        print(f"错误: {backup.error or 'state 备份失败'}", file=sys.stderr)
        return 1
    print(f"State 已备份: {backup.state_backup}")

    plan_result = executor.plan_destroy(work_dir, use_backend=not args.offline)
    if not plan_result.success:
        print(f"错误: {plan_result.error}", file=sys.stderr)
        return 1

    destroy_cmd = f"terraform destroy -auto-approve @ {work_dir}"
    if not _maybe_run_gcl(args, "Destroy", destroy_cmd):
        return 5

    hitl_env = _hitl_environment_name(args.environment)
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.DESTROY,
        environment=hitl_env,
        resources=plan_summary_to_resources(plan_result.summary),
        user_inputs={
            "request": f"terraform destroy @ {work_dir}",
            "output_dir": str(work_dir),
            "region": args.region,
            "environment": args.environment,
            "destroy_plan": dict(plan_result.summary),
            "state_backup": str(backup.state_backup) if backup.state_backup else None,
        },
    )

    store = CheckpointStore()
    store.save(checkpoint)
    print(f"HITL 检查点已创建: {checkpoint.id}")

    controller = CLIController(checkpoint, store)
    try:
        checkpoint = controller.run()
    except UserAbortedError:
        return 1

    if checkpoint.status != CheckpointStatus.COMPLETED:
        print("HITL 未完成，跳过 terraform destroy", file=sys.stderr)
        return 1

    print("正在执行 terraform destroy...")
    destroy_result = executor.destroy(work_dir)
    if not destroy_result.success:
        print(f"错误: {destroy_result.error}", file=sys.stderr)
        return 1
    print(destroy_result.stdout)
    print(f"terraform destroy 完成: {work_dir}")
    return 0


def _run_destroy(args: argparse.Namespace) -> int:
    from terraform_executor import TerraformExecutor

    work_dir = _resolve_work_dir(args)
    err = _validate_work_dir(work_dir)
    if err:
        print(f"错误: {err}", file=sys.stderr)
        return 1

    executor = TerraformExecutor()
    plan_result = executor.plan_destroy(work_dir, use_backend=not args.offline)
    if not plan_result.success:
        print(f"错误: {plan_result.error}", file=sys.stderr)
        return 1
    print(plan_result.plan_stdout)
    if plan_result.plan_stderr:
        print(plan_result.plan_stderr, file=sys.stderr)
    return 0


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
    from wizard_cli import run_wizard_command
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
    create.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="输出目录（默认 .runtime/terraform-ops/nl2hcl/<env>/）",
    )
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
    imp.add_argument("--environment", "-e", default="dev")
    imp.add_argument("--region", "-r", default="cn-hangzhou")
    imp.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="输出目录（默认 .runtime/terraform-ops/import/<resource-type>/）",
    )
    imp.add_argument("--dry-run", "-d", action="store_true")
    imp.add_argument("--discover-associated", "-D", action="store_true")
    imp.add_argument("--skip-preflight", action="store_true")

    def _add_workflow_parser(name: str, help_text: str):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument(
            "--work-dir", "-w",
            type=Path,
            default=None,
            help="Terraform 工作目录（默认 .runtime/terraform-ops/environments/<env>/）",
        )
        sp.add_argument("--output-dir", "-o", type=Path, default=None, help="同 --work-dir")
        sp.add_argument("--environment", "-e", default="dev")
        sp.add_argument("--region", "-r", default="cn-hangzhou")
        sp.add_argument("--dry-run", "-d", action="store_true", help="仅 plan，不进入 HITL 执行")
        sp.add_argument("--gcl-check", action="store_true", help="执行前运行 GCL 质量门")
        sp.add_argument(
            "--offline",
            action="store_true",
            help="plan 时使用 init -backend=false（无远程 state）",
        )
        return sp

    _add_workflow_parser("apply", "terraform plan + HITL CP3 + apply")
    _add_workflow_parser("destroy", "state 备份 + plan -destroy + HITL CP5 + destroy")

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
        _resolve_output_dir(args, "nl2hcl")
        if args.mode == "cli" and not args.wizard and not args.dry_run:
            return _run_create_with_hitl(args)
        return _run_nl2hcl(args)

    if cmd == "wizard":
        return _run_wizard(args)

    if cmd == "import":
        _resolve_output_dir(args, "import")
        if args.mode == "cli" and not args.dry_run:
            return _run_import_with_hitl(args)
        return _run_import(args)

    if cmd == "apply":
        if getattr(args, "work_dir", None) is None and getattr(args, "output_dir", None) is None:
            args.work_dir = _default_work_dir(args.environment)
        if args.mode == "cli" and not args.dry_run:
            return _run_apply_with_hitl(args)
        return _run_apply(args)

    if cmd == "destroy":
        if getattr(args, "work_dir", None) is None and getattr(args, "output_dir", None) is None:
            args.work_dir = _default_work_dir(args.environment)
        if args.mode == "cli" and not args.dry_run:
            return _run_destroy_with_hitl(args)
        return _run_destroy(args)

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
