#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run terraform init/validate/plan for HITL CP3 and NL2HCL dry-run."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from execution_trace import CommandRecord, parse_plan_summary


@dataclass
class PlanRunResult:
    success: bool
    plan_stdout: str = ""
    plan_stderr: str = ""
    init_exit: int = 0
    validate_exit: int = 0
    plan_exit: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    commands: List[CommandRecord] = field(default_factory=list)
    error: Optional[str] = None


def summary_from_plan_stdout(plan_stdout: str) -> Dict[str, Any]:
    """Map parse_plan_summary keys to HITL render_plan_summary shape."""
    parsed = parse_plan_summary(plan_stdout) or {}
    create = parsed.get("add", 0)
    update = parsed.get("change", 0)
    delete = parsed.get("destroy", 0)
    risks: List[str] = []
    if delete:
        risks.append(f"Plan 将销毁 {delete} 个资源")
    return {
        "create": create,
        "update": update,
        "delete": delete,
        "resources_to_create": parsed.get("resources_to_create", []),
        "risks": risks,
        "source": "terraform plan",
    }


class TerraformPlanRunner:
    """Execute terraform init -backend=false → validate → plan in work_dir."""

    def __init__(
        self,
        init_timeout: int = 60,
        validate_timeout: int = 30,
        plan_timeout: int = 120,
    ):
        self.init_timeout = init_timeout
        self.validate_timeout = validate_timeout
        self.plan_timeout = plan_timeout

    def run(self, work_dir: Path) -> PlanRunResult:
        work_dir = work_dir.resolve()
        if not work_dir.is_dir():
            return PlanRunResult(
                success=False,
                error=f"工作目录不存在: {work_dir}",
            )

        terraform = shutil.which("terraform")
        if not terraform:
            return PlanRunResult(
                success=False,
                error="未找到 terraform CLI（请安装 >= 1.5.0）",
            )

        commands: List[CommandRecord] = []
        steps = [
            ("INIT", [terraform, "init", "-backend=false", "-input=false"], self.init_timeout),
            ("VALIDATE", [terraform, "validate"], self.validate_timeout),
            ("PLAN", [terraform, "plan", "-input=false", "-no-color"], self.plan_timeout),
        ]

        init_exit = validate_exit = plan_exit = 0
        plan_stdout = ""
        plan_stderr = ""

        for phase, cmd, timeout in steps:
            started = time.time()
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                duration_ms = int((time.time() - started) * 1000)
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                commands.append(
                    CommandRecord(
                        phase=phase,
                        command=" ".join(cmd),
                        working_directory=str(work_dir),
                        exit_code=124,
                        stdout_excerpt=stdout[:2000],
                        stderr_excerpt=stderr[:2000],
                        duration_ms=duration_ms,
                    )
                )
                return PlanRunResult(
                    success=False,
                    plan_stdout=stdout,
                    plan_stderr=stderr,
                    init_exit=init_exit,
                    validate_exit=validate_exit,
                    plan_exit=plan_exit,
                    commands=commands,
                    error=f"{phase} 超时 ({timeout}s)",
                )

            duration_ms = int((time.time() - started) * 1000)
            commands.append(
                CommandRecord(
                    phase=phase,
                    command=" ".join(cmd),
                    working_directory=str(work_dir),
                    exit_code=proc.returncode,
                    stdout_excerpt=(proc.stdout or "")[:2000],
                    stderr_excerpt=(proc.stderr or "")[:2000],
                    duration_ms=duration_ms,
                )
            )

            if phase == "INIT":
                init_exit = proc.returncode
            elif phase == "VALIDATE":
                validate_exit = proc.returncode
            else:
                plan_exit = proc.returncode
                plan_stdout = proc.stdout or ""
                plan_stderr = proc.stderr or ""

            if proc.returncode != 0:
                err_tail = (proc.stderr or proc.stdout or "").strip().splitlines()
                err_msg = err_tail[-1] if err_tail else f"{phase} failed"
                return PlanRunResult(
                    success=False,
                    plan_stdout=plan_stdout,
                    plan_stderr=plan_stderr or (proc.stderr or ""),
                    init_exit=init_exit,
                    validate_exit=validate_exit,
                    plan_exit=plan_exit,
                    commands=commands,
                    error=f"{phase} 失败 (exit {proc.returncode}): {err_msg}",
                )

        summary = summary_from_plan_stdout(plan_stdout)
        return PlanRunResult(
            success=True,
            plan_stdout=plan_stdout,
            plan_stderr=plan_stderr,
            init_exit=init_exit,
            validate_exit=validate_exit,
            plan_exit=plan_exit,
            summary=summary,
            commands=commands,
        )
