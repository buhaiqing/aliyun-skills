#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terraform apply/destroy execution helpers for terraform_ops HITL flows."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from execution_trace import CommandRecord
from terraform_plan_runner import PlanRunResult, TerraformPlanRunner, summary_from_plan_stdout


@dataclass
class ExecRunResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    commands: List[CommandRecord] = field(default_factory=list)
    error: Optional[str] = None
    plan_file: Optional[Path] = None
    state_backup: Optional[Path] = None


class TerraformExecutor:
    """Plan (with backend), apply saved plan, destroy, and state backup."""

    def __init__(
        self,
        plan_runner: Optional[TerraformPlanRunner] = None,
        apply_timeout: int = 600,
        destroy_timeout: int = 600,
        state_pull_timeout: int = 120,
    ):
        self.plan_runner = plan_runner or TerraformPlanRunner()
        self.apply_timeout = apply_timeout
        self.destroy_timeout = destroy_timeout
        self.state_pull_timeout = state_pull_timeout

    def plan_apply(
        self,
        work_dir: Path,
        *,
        use_backend: bool = True,
        plan_out: Optional[Path] = None,
    ) -> PlanRunResult:
        plan_path = plan_out or (work_dir / "tfplan")
        return self.plan_runner.run(
            work_dir,
            use_backend=use_backend,
            destroy=False,
            plan_out=plan_path,
        )

    def plan_destroy(self, work_dir: Path, *, use_backend: bool = True) -> PlanRunResult:
        return self.plan_runner.run(
            work_dir,
            use_backend=use_backend,
            destroy=True,
            plan_out=None,
        )

    def state_backup(self, work_dir: Path) -> ExecRunResult:
        work_dir = work_dir.resolve()
        terraform = shutil.which("terraform")
        if not terraform:
            return ExecRunResult(success=False, error="未找到 terraform CLI")

        backup_name = f"state-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tfstate"
        backup_path = work_dir / backup_name
        cmd = [terraform, "state", "pull"]
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self.state_pull_timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecRunResult(success=False, error="state pull 超时")

        duration_ms = int((time.time() - started) * 1000)
        record = CommandRecord(
            phase="STATE_BACKUP",
            command=" ".join(cmd),
            working_directory=str(work_dir),
            exit_code=proc.returncode,
            stdout_excerpt=(proc.stdout or "")[:2000],
            stderr_excerpt=(proc.stderr or "")[:2000],
            duration_ms=duration_ms,
        )
        if proc.returncode != 0:
            return ExecRunResult(
                success=False,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                commands=[record],
                error="terraform state pull 失败",
            )

        backup_path.write_text(proc.stdout or "", encoding="utf-8")
        return ExecRunResult(
            success=True,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=0,
            commands=[record],
            state_backup=backup_path,
        )

    def apply(self, work_dir: Path, plan_file: Optional[Path] = None) -> ExecRunResult:
        work_dir = work_dir.resolve()
        plan_path = (plan_file or work_dir / "tfplan").resolve()
        if not plan_path.is_file():
            return ExecRunResult(success=False, error=f"Plan 文件不存在: {plan_path}")

        terraform = shutil.which("terraform")
        if not terraform:
            return ExecRunResult(success=False, error="未找到 terraform CLI")

        cmd = [terraform, "apply", "-input=false", "-no-color", str(plan_path)]
        return self._run(cmd, work_dir, phase="APPLY", timeout=self.apply_timeout, plan_file=plan_path)

    def destroy(self, work_dir: Path) -> ExecRunResult:
        work_dir = work_dir.resolve()
        terraform = shutil.which("terraform")
        if not terraform:
            return ExecRunResult(success=False, error="未找到 terraform CLI")

        cmd = [terraform, "destroy", "-input=false", "-no-color", "-auto-approve"]
        return self._run(cmd, work_dir, phase="DESTROY", timeout=self.destroy_timeout)

    def _run(
        self,
        cmd: List[str],
        work_dir: Path,
        *,
        phase: str,
        timeout: int,
        plan_file: Optional[Path] = None,
    ) -> ExecRunResult:
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
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return ExecRunResult(
                success=False,
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
                error=f"{phase} 超时 ({timeout}s)",
                plan_file=plan_file,
            )

        duration_ms = int((time.time() - started) * 1000)
        record = CommandRecord(
            phase=phase,
            command=" ".join(cmd),
            working_directory=str(work_dir),
            exit_code=proc.returncode,
            stdout_excerpt=(proc.stdout or "")[:2000],
            stderr_excerpt=(proc.stderr or "")[:2000],
            duration_ms=duration_ms,
        )
        if proc.returncode != 0:
            err_tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            err_msg = err_tail[-1] if err_tail else f"{phase} failed"
            return ExecRunResult(
                success=False,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                commands=[record],
                error=f"{phase} 失败 (exit {proc.returncode}): {err_msg}",
                plan_file=plan_file,
            )

        return ExecRunResult(
            success=True,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=0,
            commands=[record],
            plan_file=plan_file,
        )


def plan_summary_to_resources(plan_summary: dict) -> List[dict]:
    """Plan 摘要 → HITL ResourceInfo 兼容结构（用于 destroy 预览）。"""
    resources: List[dict] = []
    delete_count = int(plan_summary.get("delete", 0) or 0)
    if delete_count:
        resources.append({
            "type": "terraform",
            "name": f"destroy_{delete_count}_resources",
            "id": None,
            "status": "pending",
            "attributes": {"delete_count": delete_count},
        })
    return resources


def seed_plan_step_data(plan_result: PlanRunResult) -> dict:
    """预填充 CP3 step.data，避免 HITL 内重复 plan。"""
    if plan_result.success:
        return {
            "plan_executed": True,
            "plan": dict(plan_result.summary),
            "plan_stdout": plan_result.plan_stdout,
            "plan_stderr": plan_result.plan_stderr,
            "plan_source": "terraform plan",
            "plan_commands": [c.to_dict() for c in plan_result.commands],
        }
    summary = summary_from_plan_stdout(plan_result.plan_stdout or "")
    summary["plan_error"] = plan_result.error
    return {
        "plan_executed": True,
        "plan": summary,
        "plan_stdout": plan_result.plan_stdout,
        "plan_stderr": plan_result.plan_stderr,
        "plan_source": "resource_estimate",
        "plan_commands": [c.to_dict() for c in plan_result.commands],
    }
