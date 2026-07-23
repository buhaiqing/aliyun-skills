#!/usr/bin/env python3
"""
execution_trace.py — 统一执行轨迹持久化

符合 references/rubric.md §4.1 与 interactive-wizard.md §6.1。
输出: .runtime/audit/terraform-ops/gcl-trace-{operation}-YYYYMMDD-HHMMSS.json
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_VERSION = "1.0.0"


def default_trace_dir() -> Path:
    from runtime_paths import audit_dir
    return audit_dir()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _excerpt(text: str, limit: int = 2000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


@dataclass
class CommandRecord:
    phase: str
    command: str
    working_directory: str
    exit_code: int
    stdout_excerpt: str
    stderr_excerpt: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionTrace:
    trace_version: str = TRACE_VERSION
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=now_iso)
    skill: str = "alicloud-terraform-ops"
    operation: str = "nl2hcl"
    environment: str = "dev"
    region: str = "cn-hangzhou"
    request: str = ""
    dry_run: bool = True
    success: bool = False
    session_id: str | None = None
    commands: list[CommandRecord] = field(default_factory=list)
    plan_summary: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None
    critic: dict[str, Any] | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_version": self.trace_version,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "skill": self.skill,
            "operation": self.operation,
            "environment": self.environment,
            "region": self.region,
            "request": self.request,
            "dry_run": self.dry_run,
            "success": self.success,
            "session_id": self.session_id,
            "generator": {
                "commands": [c.to_dict() for c in self.commands],
                "plan_summary": self.plan_summary,
            },
            "intent": self.intent,
            "critic": self.critic,
            "artifacts": self.artifacts,
        }


def parse_plan_summary(plan_stdout: str) -> dict[str, Any] | None:
    """从 terraform plan 输出解析变更摘要."""
    if not plan_stdout:
        return None
    m = re.search(
        r"Plan:\s*(\d+)\s+to add,\s*(\d+)\s+to change,\s*(\d+)\s+to destroy",
        plan_stdout,
    )
    if not m:
        return None
    resources = re.findall(
        r'#\s+(alicloud_\S+\.\S+(?:\[\d+\])?) will be created',
        plan_stdout,
    )
    return {
        "add": int(m.group(1)),
        "change": int(m.group(2)),
        "destroy": int(m.group(3)),
        "resources_to_create": resources[:20],
    }


def build_critic_scores(success: bool) -> dict[str, Any]:
    return {
        "scores": {
            "correctness": 1 if success else 0,
            "safety": 1,
            "idempotency": 1,
            "traceability": 1,
            "spec_compliance": 1 if success else 0,
        },
        "suggestions": [] if success else ["检查 terraform init/validate/plan 输出"],
        "blocking": not success,
    }


class ExecutionTraceWriter:
    """写入 audit-results 目录."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or default_trace_dir()

    def write(self, trace: ExecutionTrace) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.base_dir / f"gcl-trace-{trace.operation}-{ts}.json"
        path.write_text(
            json.dumps(trace.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def persist_dry_run_trace(
    *,
    operation: str,
    environment: str,
    region: str,
    request: str,
    work_dir: Path,
    command_records: list[CommandRecord],
    success: bool,
    plan_stdout: str = "",
    intent: dict[str, Any] | None = None,
    session_id: str | None = None,
    output_dir: str | None = None,
    trace_dir: Path | None = None,
) -> Path:
    """构建并持久化 dry-run 执行轨迹."""
    trace = ExecutionTrace(
        operation=operation,
        environment=environment,
        region=region,
        request=request,
        dry_run=True,
        success=success,
        session_id=session_id,
        commands=command_records,
        plan_summary=parse_plan_summary(plan_stdout),
        intent=intent,
        critic=build_critic_scores(success),
        artifacts={
            "working_directory": str(work_dir),
            **({"output_dir": output_dir} if output_dir else {}),
        },
    )
    path = ExecutionTraceWriter(trace_dir).write(trace)
    return path
