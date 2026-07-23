"""workflow-runner.py — 固化工作流引擎 (Sprint 13 Stage 3 D1)

职责: 执行 90% 已知 runbook, 不经过 LLM 推理
特点: 毫秒级响应, 零 LLM 成本, 高确定性

执行模式:
- 同步 (foreground): 等待 runbook 完成
- 异步 (background): fork 后立即返回
- 链式 (chain): runbook A -> runbook B -> runbook C
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from _shared import _resolve_runbooks_output_dir, log

__all__ = ["WorkflowRunner", "Workflow", "run_workflow"]


class Workflow:
    """定义一个工作流: 1+ 个 step 顺序执行."""

    def __init__(self, name: str, steps: list, description: str = ""):
        self.name = name
        self.steps = steps  # [{"runbook": "...", "args": {...}, "continue_on_error": False}]
        self.description = description

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
        }


# 预定义工作流
WORKFLOWS = {
    "daily_routine": Workflow(
        name="daily_routine",
        description="每日固定巡检: daily + capacity",
        steps=[
            {"runbook": "daily-health-check.py", "args": {"non_interactive": True}},
            {"runbook": "capacity-planning.py", "args": {"non_interactive": True}, "continue_on_error": True},
        ],
    ),
    "weekly_routine": Workflow(
        name="weekly_routine",
        description="每周固定巡检: daily + capacity + topology",
        steps=[
            {"runbook": "daily-health-check.py", "args": {"non_interactive": True}},
            {"runbook": "capacity-planning.py", "args": {"non_interactive": True}, "continue_on_error": True},
        ],
    ),
    "pre_launch_routine": Workflow(
        name="pre_launch_routine",
        description="大促前: pre_launch -> daily -> capacity",
        steps=[
            {"runbook": "pre-launch-check.py", "args": {"non_interactive": True, "multiplier": 3.0}},
            {"runbook": "daily-health-check.py", "args": {"non_interactive": True}, "continue_on_error": True},
        ],
    ),
}


class WorkflowRunner:
    """固化工作流执行器."""

    def __init__(self, scripts_dir: str = None, output_dir: str = "audit-results"):
        self.scripts_dir = Path(scripts_dir or Path(__file__).parent)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_log = self.output_dir / "workflow-run-log.jsonl"

    def _run_step(self, step: dict, common_args: dict, workflow_name: str = "ad-hoc") -> dict:
        """执行单个 step."""
        runbook = step["runbook"]
        step_args = step.get("args", {})
        runbook_path = self.scripts_dir / runbook
        if not runbook_path.exists():
            return {"runbook": runbook, "exit_code": -1, "error": "not found"}

        # 合并参数: common_args < step_args
        merged = {**common_args, **step_args}
        # Sprint 13: 同一 workflow 内不同 step 独立 lock key, 避免串行时冲突
        lock_key = merged.get("cruise_lock_key", f"workflow-{workflow_name}-{runbook}")
        env = {**os.environ, "CRUISE_LOCK_KEY": lock_key}
        cmd = ["python3", str(runbook_path)]
        for k, v in merged.items():
            if isinstance(v, bool) and v:
                cmd.append(f"--{k.replace('_', '-')}")
            elif not isinstance(v, bool):
                cmd.extend([f"--{k.replace('_', '-')}", str(v)])

        log("DIAG", f"workflow step: {runbook} lock_key={lock_key}")
        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env)
            exit_code = result.returncode
            stderr_tail = result.stderr[-500:] if result.stderr else ""
        except subprocess.TimeoutExpired:
            exit_code = 124
            stderr_tail = "[TIMEOUT]"
        duration = time.time() - t0

        return {
            "runbook": runbook,
            "command_tail": cmd[-3:],
            "exit_code": exit_code,
            "duration_seconds": round(duration, 2),
            "stderr_tail": stderr_tail,
        }

    def run(self, workflow_name: str, common_args: dict = None) -> dict:
        """执行一个预定义工作流.

        Args:
            workflow_name: 工作流名 (e.g. "daily_routine")
            common_args: 所有 step 共享的公共参数 (e.g. customer/region)

        Returns:
            dict 含 workflow_name, steps (每个 step 结果), total_duration
        """
        common_args = common_args or {}
        if workflow_name not in WORKFLOWS:
            return {
                "workflow_name": workflow_name,
                "error": f"未知工作流 {workflow_name}, 可用: {list(WORKFLOWS.keys())}",
            }
        wf = WORKFLOWS[workflow_name]
        log("DIAG", f"workflow start: {workflow_name} ({len(wf.steps)} steps)")

        t0 = time.time()
        step_results = []
        failed = False
        for i, step in enumerate(wf.steps):
            if failed and not step.get("continue_on_error"):
                log("DIAG", f"step {i+1} 跳过 (前序失败)")
                step_results.append({"skipped": True, "reason": "前序失败"})
                continue
            result = self._run_step(step, common_args, workflow_name)
            step_results.append(result)
            if result.get("exit_code", 0) != 0 and not step.get("continue_on_error"):
                failed = True
                log("DIAG", f"step {i+1} 失败, 终止 workflow")
        total_duration = time.time() - t0

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow_name": workflow_name,
            "description": wf.description,
            "common_args": common_args,
            "steps": step_results,
            "total_duration_seconds": round(total_duration, 2),
            "success": not failed,
        }
        with open(self.run_log, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        log("DIAG", f"workflow done: {workflow_name} success={not failed} duration={total_duration:.1f}s")
        return record


def run_workflow(name: str, customer: str, region: str, **kwargs) -> dict:
    """便捷函数: 启动一个工作流."""
    runner = WorkflowRunner(output_dir=kwargs.get("output_dir", "audit-results"))
    return runner.run(name, {
        "customer": customer,
        "region": region,
        "resource_group_id": kwargs.get("resource_group_id", ""),
        "output_dir": kwargs.get("output_dir", "audit-results"),
    })


def main():
    ap = argparse.ArgumentParser(description="Workflow Runner (固化工作流引擎)", allow_abbrev=False)
    ap.add_argument("--workflow", choices=list(WORKFLOWS.keys()))
    ap.add_argument("--customer")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--resource-group-id", default="")
    ap.add_argument("--output-dir", default=_resolve_runbooks_output_dir())
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()

    print(f"\n{'=' * 50}\n  Workflow Runner v1.0.0 (Stage 3 D1)\n{'=' * 50}")

    if args.describe:
        print("预定义工作流:")
        for name, wf in WORKFLOWS.items():
            print(f"\n  [{name}] {wf.description}")
            for i, step in enumerate(wf.steps, 1):
                ce = " (continue on error)" if step.get("continue_on_error") else ""
                print(f"    {i}. {step['runbook']}{ce}")
        return

    if not args.workflow or not args.customer:
        print("[ERROR] --workflow 和 --customer 必填 (或用 --describe)")
        sys.exit(2)

    record = run_workflow(
        args.workflow, args.customer, args.region,
        resource_group_id=args.resource_group_id,
        output_dir=args.output_dir,
    )

    print(f"\n{'=' * 50}")
    print(f"  Workflow: {record.get('workflow_name', '?')}")
    print(f"  Success: {record.get('success', False)}")
    print(f"  Duration: {record.get('total_duration_seconds', 0)}s")
    print(f"  Steps: {len(record.get('steps', []))}")
    for i, s in enumerate(record.get("steps", []), 1):
        if "skipped" in s:
            print(f"    {i}. SKIPPED ({s['skipped']})")
        else:
            print(f"    {i}. {s.get('runbook', '?')}: exit={s.get('exit_code', '?')} dur={s.get('duration_seconds', 0)}s")
    print(f"{'=' * 50}")
    sys.exit(0 if record.get("success") else 1)


if __name__ == "__main__":
    main()
