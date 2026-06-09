#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wizard_cli.py — Terraform IaC 交互式向导

实现 references/interactive-wizard.md 规范的向导 CLI:
  wizard nl2hcl | import | resume
  wizard history | show | diagnose | export

会话存储: ~/.aliyun-terraform/sessions/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime_paths import default_import_output, default_nl2hcl_output

try:
    from nl2hcl_generator import NL2HCLGenerator, Colors, print_dry_run_banner, log_dry_run
    from reverse_engineering import ReverseEngineering
    from execution_trace import build_critic_scores, parse_plan_summary, persist_dry_run_trace
except ImportError:
    from scripts.nl2hcl_generator import NL2HCLGenerator, Colors, print_dry_run_banner, log_dry_run  # type: ignore
    from scripts.reverse_engineering import ReverseEngineering  # type: ignore
    from scripts.execution_trace import build_critic_scores, parse_plan_summary, persist_dry_run_trace  # type: ignore


WIZARD_VERSION = "1.0.0"
SESSION_DIR = Path.home() / ".aliyun-terraform" / "sessions"

QUICK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "vpc-basic": {
        "request": "创建一个 VPC，包含两个可用区的交换机",
        "environment": "dev",
        "region": "cn-hangzhou",
    },
    "web-stack": {
        "request": "创建 VPC、2台 ECS、SLB 和 RDS MySQL",
        "environment": "dev",
        "region": "cn-hangzhou",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_session_id() -> str:
    return f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


@dataclass
class WizardStep:
    step: int
    name: str
    input: Any
    output: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=now_iso)
    validation: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "step": self.step,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "timestamp": self.timestamp,
        }
        if self.validation is not None:
            d["validation"] = self.validation
        return d


@dataclass
class WizardSession:
    wizard_version: str = WIZARD_VERSION
    session_id: str = ""
    user_id: str = ""
    workflow_type: str = "nl2hcl"
    started_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    current_step: int = 1
    status: str = "running"
    params: Dict[str, Any] = field(default_factory=dict)
    steps: List[WizardStep] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wizard_version": self.wizard_version,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "workflow_type": self.workflow_type,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_step": self.current_step,
            "status": self.status,
            "params": self.params,
            "steps": [s.to_dict() for s in self.steps],
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WizardSession":
        steps = [
            WizardStep(
                step=s["step"],
                name=s["name"],
                input=s.get("input"),
                output=s.get("output", {}),
                timestamp=s.get("timestamp", now_iso()),
                validation=s.get("validation"),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            wizard_version=data.get("wizard_version", WIZARD_VERSION),
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            workflow_type=data.get("workflow_type", "nl2hcl"),
            started_at=data.get("started_at", now_iso()),
            completed_at=data.get("completed_at"),
            current_step=data.get("current_step", 1),
            status=data.get("status", "running"),
            params=data.get("params", {}),
            steps=steps,
            artifacts=data.get("artifacts", {}),
        )


class WizardStore:
    """会话持久化"""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or SESSION_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: WizardSession) -> Path:
        path = self.base_dir / f"{session.session_id}.json"
        path.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> WizardSession:
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"会话不存在: {session_id}")
        return WizardSession.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_sessions(self, limit: int = 10) -> List[WizardSession]:
        files = sorted(
            self.base_dir.glob("session-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        sessions = []
        for f in files[:limit]:
            try:
                sessions.append(
                    WizardSession.from_dict(json.loads(f.read_text(encoding="utf-8")))
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(130)
    return value or default


def _prompt_choice(label: str, choices: List[str], default: str) -> str:
    print(f"{label}:")
    for i, c in enumerate(choices, 1):
        mark = "❯" if c == default else "○"
        print(f"  {mark} {c}")
    value = _prompt("选择", default)
    return value if value in choices else default


def _load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError:
            print(f"{Colors.RED}需要 PyYAML 解析 {path}{Colors.END}")
            sys.exit(1)
        return yaml.safe_load(text) or {}
    return json.loads(text)


class WizardRunner:
    """向导执行器"""

    def __init__(self, store: Optional[WizardStore] = None, output_dir: Optional[Path] = None):
        self.store = store or WizardStore()
        self.output_dir = output_dir or default_nl2hcl_output()

    def run_nl2hcl(
        self,
        quick: bool = False,
        template: Optional[str] = None,
        config_path: Optional[Path] = None,
        environment: Optional[str] = None,
        region: Optional[str] = None,
        request: Optional[str] = None,
        dry_run: bool = True,
    ) -> WizardSession:
        session = WizardSession(
            session_id=new_session_id(),
            user_id=os.environ.get("USER", "unknown"),
            workflow_type="nl2hcl",
        )
        params: Dict[str, Any] = {}

        if config_path:
            params = _load_config(config_path)
        elif quick and template:
            params = dict(QUICK_TEMPLATES.get(template, QUICK_TEMPLATES["vpc-basic"]))
        elif quick:
            params = dict(QUICK_TEMPLATES["vpc-basic"])

        if environment:
            params["environment"] = environment
        if region:
            params["region"] = region
        if request:
            params["request"] = request

        # Step 1: 意图识别
        if not quick and not params.get("request"):
            print(f"\n{Colors.BOLD}Step 1: 意图识别{Colors.END}")
            params["request"] = _prompt("描述基础设施需求")
        req = params.get("request", "")
        if not req:
            print(f"{Colors.RED}错误: 未提供需求描述{Colors.END}")
            sys.exit(1)

        generator = NL2HCLGenerator(
            environment=params.get("environment", "dev"),
            region=params.get("region", "cn-hangzhou"),
        )
        intent = generator.parse_intent(req)
        session.steps.append(WizardStep(
            step=1, name="intent_recognition",
            input=req,
            output={
                "intent": f"nl2hcl_{'_'.join(intent['resources'][:2])}",
                "confidence": 0.9,
                "resources": intent["resources"],
                "instance_type": intent.get("instance_type"),
                "parsed_intent": intent,
            },
        ))
        session.current_step = 2
        self.store.save(session)

        # Step 2: 参数收集
        if not quick:
            print(f"\n{Colors.BOLD}Step 2: 参数收集{Colors.END}")
            params["environment"] = _prompt_choice(
                "环境", ["int", "dev", "uat", "performance", "prod"],
                params.get("environment", "dev"),
            )
            params["region"] = _prompt("区域", params.get("region", "cn-hangzhou"))
            generator.environment = params["environment"]
            generator.region = params["region"]

        session.steps.append(WizardStep(
            step=2, name="parameter_collection",
            input=params,
            validation={"passed": True, "warnings": []},
        ))
        session.params = params
        session.current_step = 3
        self.store.save(session)

        # Step 3: 生成 + Dry-run
        print(f"\n{Colors.BOLD}Step 3: 配置生成与 Dry-Run{Colors.END}")
        print_dry_run_banner()
        t0 = time.time()
        validation_ok = True
        validation_msg = ""

        with tempfile.TemporaryDirectory(prefix="tf-wizard-") as tmpdir:
            work_dir = Path(tmpdir)
            files = generator.generate(req, output_dir=work_dir)
            for name, content in files.items():
                (work_dir / name).write_text(content, encoding="utf-8")
                log_dry_run("WRITE", f"生成 {name}")

            try:
                from nl2hcl_generator import DryRunExecutor
            except ImportError:
                from scripts.nl2hcl_generator import DryRunExecutor  # type: ignore
            executor = DryRunExecutor(work_dir)
            dry_result = executor.execute()
            validation_ok = dry_result.success
            validation_msg = dry_result.stderr or ""

            trace_path = persist_dry_run_trace(
                operation="nl2hcl",
                environment=params.get("environment", "dev"),
                region=params.get("region", "cn-hangzhou"),
                request=req,
                work_dir=work_dir,
                command_records=dry_result.command_records,
                success=dry_result.success,
                plan_stdout=dry_result.plan_stdout,
                intent=intent,
                session_id=session.session_id,
            )

        elapsed_ms = int((time.time() - t0) * 1000)
        plan_summary = parse_plan_summary(dry_result.plan_stdout)
        critic = build_critic_scores(validation_ok)
        session.steps.append(WizardStep(
            step=3, name="dry_run",
            input={"dry_run": dry_run},
            output={
                "gcl_trace": {
                    "scores": critic["scores"],
                    "execution_time_ms": elapsed_ms,
                    "plan_summary": plan_summary,
                    "terraform_commands": [
                        {"phase": c.phase, "command": c.command, "exit_code": c.exit_code, "duration_ms": c.duration_ms}
                        for c in dry_result.command_records
                    ],
                },
                "validation_passed": validation_ok,
                "error": validation_msg[:500] if not validation_ok else None,
            },
            validation={"passed": validation_ok, "warnings": [] if validation_ok else [validation_msg[:200]]},
        ))
        session.current_step = 4
        session.artifacts["generated_hcl"] = files.get("main.tf", "")[:2000]
        session.artifacts["gcl_trace_file"] = str(trace_path)
        self.store.save(session)

        print(f"{Colors.CYAN}执行轨迹: {session.artifacts['gcl_trace_file']}{Colors.END}")

        if not validation_ok:
            print(f"{Colors.RED}Dry-run 验证失败{Colors.END}")
            session.status = "failed"
            self.store.save(session)
            return session

        # Step 4: 确认执行
        if not quick:
            print(f"\n{Colors.BOLD}Step 4: 确认执行{Colors.END}")
            print("检测到资源:", ", ".join(intent["resources"]))
            confirm = _prompt("写入文件到输出目录? [Y/n]", "Y").lower()
            if confirm not in ("y", "yes", ""):
                session.status = "paused"
                self.store.save(session)
                print(f"会话已保存: {session.session_id}")
                print(f"恢复: terraform-ops wizard resume {session.session_id}")
                return session

        self.output_dir.mkdir(parents=True, exist_ok=True)
        generator.generate(req, output_dir=self.output_dir)
        for name, content in files.items():
            (self.output_dir / name).write_text(content, encoding="utf-8")

        session.steps.append(WizardStep(
            step=4, name="execution",
            input={"confirmed": True},
            output={"status": "success", "output_dir": str(self.output_dir)},
        ))
        session.status = "completed"
        session.completed_at = now_iso()
        self.store.save(session)

        print(f"\n{Colors.GREEN}✓ 向导完成，文件已写入 {self.output_dir}{Colors.END}")
        return session

    def run_import(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        region: str = "cn-hangzhou",
        discover: bool = True,
        dry_run: bool = True,
    ) -> WizardSession:
        session = WizardSession(
            session_id=new_session_id(),
            user_id=os.environ.get("USER", "unknown"),
            workflow_type="import",
        )

        print(f"\n{Colors.BOLD}Reverse Engineering 向导{Colors.END}")
        rtype = resource_type or _prompt("资源类型 (vpc/ecs/rds/mongodb/...)", "vpc")
        rid = resource_id or _prompt("资源 ID")

        session.steps.append(WizardStep(
            step=1, name="intent_recognition",
            input={"resource_type": rtype, "resource_id": rid},
            output={"intent": "reverse_engineering"},
        ))
        session.params = {"resource_type": rtype, "resource_id": rid, "region": region}
        self.store.save(session)

        engine = ReverseEngineering(region=region, output_dir=self.output_dir)
        success, resources = engine.run(
            resource_type=rtype,
            resource_ids=[rid],
            dry_run=dry_run,
            discover_associated=discover,
        )

        session.steps.append(WizardStep(
            step=2, name="dry_run",
            input={"discover_associated": discover},
            output={
                "success": success,
                "resources": [{"type": r["type"], "id": r["id"]} for r in resources],
            },
            validation={"passed": success, "warnings": []},
        ))

        if success and not dry_run:
            session.status = "completed"
            session.completed_at = now_iso()
        elif success:
            session.status = "paused"
            session.current_step = 3
        else:
            session.status = "failed"

        self.store.save(session)
        return session

    def resume(self, session_id: str) -> WizardSession:
        session = self.store.load(session_id)
        print(f"恢复会话: {session_id} (步骤 {session.current_step}, 状态 {session.status})")

        if session.status == "completed":
            print("会话已完成，无需恢复")
            return session

        if session.workflow_type == "nl2hcl" and session.current_step >= 3:
            params = session.params
            self.output_dir.mkdir(parents=True, exist_ok=True)
            req = params.get("request", "")
            generator = NL2HCLGenerator(
                environment=params.get("environment", "dev"),
                region=params.get("region", "cn-hangzhou"),
            )
            files = generator.generate(req, output_dir=self.output_dir)
            for name, content in files.items():
                (self.output_dir / name).write_text(content, encoding="utf-8")
            session.status = "completed"
            session.completed_at = now_iso()
            session.steps.append(WizardStep(
                step=session.current_step + 1, name="execution",
                input={"resumed": True},
                output={"status": "success", "output_dir": str(self.output_dir)},
            ))
            self.store.save(session)
            print(f"{Colors.GREEN}✓ 已从断点恢复并写入 {self.output_dir}{Colors.END}")

        elif session.workflow_type == "import" and session.status == "paused":
            params = session.params
            engine = ReverseEngineering(region=params.get("region", "cn-hangzhou"), output_dir=self.output_dir)
            success, _ = engine.run(
                resource_type=params["resource_type"],
                resource_ids=[params["resource_id"]],
                dry_run=False,
                discover_associated=params.get("discover_associated", True),
            )
            session.status = "completed" if success else "failed"
            session.completed_at = now_iso() if success else None
            self.store.save(session)

        return session


def cmd_history(args: argparse.Namespace) -> None:
    store = WizardStore()
    sessions = store.list_sessions(limit=args.limit)
    if not sessions:
        print("无历史会话")
        return
    print(f"{'SESSION ID':<30} {'TYPE':<10} {'STATUS':<10} {'STARTED'}")
    print("-" * 70)
    for s in sessions:
        print(f"{s.session_id:<30} {s.workflow_type:<10} {s.status:<10} {s.started_at}")


def cmd_show(args: argparse.Namespace) -> None:
    session = WizardStore().load(args.session_id)
    print(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))


def cmd_diagnose(args: argparse.Namespace) -> None:
    session = WizardStore().load(args.session_id)
    print(f"会话: {session.session_id}")
    print(f"状态: {session.status} | 当前步骤: {session.current_step}")
    for step in session.steps:
        print(f"\nStep {step.step} ({step.name}) @ {step.timestamp}")
        if step.validation and not step.validation.get("passed", True):
            for w in step.validation.get("warnings", []):
                print(f"  ⚠ warning: {w}")
        if step.output.get("error"):
            print(f"  ✗ error: {step.output['error']}")
            print(f"  Recommendation: 检查配置参数后重新运行 dry-run")
        if step.name == "dry_run" and step.output.get("gcl_trace"):
            scores = step.output["gcl_trace"].get("scores", {})
            failed = [k for k, v in scores.items() if v < 1]
            if failed:
                print(f"  GCL 未通过维度: {', '.join(failed)}")


def cmd_export(args: argparse.Namespace) -> None:
    session = WizardStore().load(args.session_id)
    out = Path(args.output)
    if args.format == "json":
        out.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        lines = [
            f"# Wizard Session Report: {session.session_id}",
            f"- Workflow: {session.workflow_type}",
            f"- Status: {session.status}",
            f"- Started: {session.started_at}",
            f"- Completed: {session.completed_at or 'N/A'}",
            "",
            "## Steps",
        ]
        for step in session.steps:
            lines.append(f"### Step {step.step}: {step.name}")
            lines.append(f"- Time: {step.timestamp}")
            lines.append(f"- Input: {json.dumps(step.input, ensure_ascii=False)[:200]}")
            lines.append("")
        out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已导出到 {out}")


def add_wizard_commands(subparsers: argparse._SubParsersAction) -> None:
    """注册 wizard 子命令 (nl2hcl / import / resume / history / ...)"""
    nl2hcl = subparsers.add_parser("nl2hcl", help="NL2HCL 向导")
    nl2hcl.add_argument("--quick", action="store_true", help="快速模式")
    nl2hcl.add_argument("--template", choices=list(QUICK_TEMPLATES.keys()))
    nl2hcl.add_argument("--config", type=Path, help="YAML/JSON 参数文件")
    nl2hcl.add_argument("--environment", "-e")
    nl2hcl.add_argument("--region", "-r")
    nl2hcl.add_argument("--request")
    nl2hcl.add_argument("--output-dir", "-o", type=Path, default=None)
    nl2hcl.add_argument("--no-dry-run", action="store_true")

    imp = subparsers.add_parser("import", help="逆向工程向导")
    imp.add_argument("--type", "-t", dest="resource_type")
    imp.add_argument("--id", "-i", dest="resource_id")
    imp.add_argument("--region", "-r", default="cn-hangzhou")
    imp.add_argument("--no-discover", action="store_true")
    imp.add_argument("--output-dir", "-o", type=Path, default=None)

    resume = subparsers.add_parser("resume", help="恢复会话")
    resume.add_argument("session_id")

    hist = subparsers.add_parser("history", help="查看历史会话")
    hist.add_argument("--limit", type=int, default=10)

    show = subparsers.add_parser("show", help="查看会话详情")
    show.add_argument("session_id")

    diag = subparsers.add_parser("diagnose", help="诊断会话问题")
    diag.add_argument("session_id")

    export = subparsers.add_parser("export", help="导出会话报告")
    export.add_argument("session_id")
    export.add_argument("--format", choices=["json", "md"], default="md")
    export.add_argument("--output", "-o", required=True)


def build_wizard_parser(subparsers: argparse._SubParsersAction) -> None:
    """在统一 CLI 下注册 wizard 命令组"""
    wizard = subparsers.add_parser("wizard", help="交互式向导")
    add_wizard_commands(wizard.add_subparsers(dest="wizard_cmd", required=True))


def run_wizard_command(args: argparse.Namespace) -> int:
    out = getattr(args, "output_dir", None)
    if args.wizard_cmd == "nl2hcl" and out is None:
        out = default_nl2hcl_output(args.environment or "dev")
    if args.wizard_cmd == "import" and out is None:
        out = default_import_output()
    runner = WizardRunner(output_dir=out)

    if args.wizard_cmd == "nl2hcl":
        runner.run_nl2hcl(
            quick=args.quick or bool(args.config),
            template=args.template,
            config_path=args.config,
            environment=args.environment,
            region=args.region,
            request=args.request,
            dry_run=not args.no_dry_run,
        )
        return 0

    if args.wizard_cmd == "import":
        runner.run_import(
            resource_type=args.resource_type,
            resource_id=args.resource_id,
            region=args.region,
            discover=not args.no_discover,
        )
        return 0

    if args.wizard_cmd == "resume":
        runner.resume(args.session_id)
        return 0

    if args.wizard_cmd == "history":
        cmd_history(args)
        return 0

    if args.wizard_cmd == "show":
        cmd_show(args)
        return 0

    if args.wizard_cmd == "diagnose":
        cmd_diagnose(args)
        return 0

    if args.wizard_cmd == "export":
        cmd_export(args)
        return 0

    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="aliyun-terraform",
        description="Terraform IaC Wizard (aliyun-terraform wizard)",
    )
    add_wizard_commands(parser.add_subparsers(dest="wizard_cmd", required=True))
    sys.exit(run_wizard_command(parser.parse_args()))
