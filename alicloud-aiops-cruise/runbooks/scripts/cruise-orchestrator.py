"""cruise-orchestrator.py — 双引擎主调度器 (Sprint 13 Stage 3 D1)

职责:
- 接收 cron/event 触发
- 根据场景选 runbook + 引擎 (workflow/agent)
- 路由到 workflow-runner.py 或 agent-fallback.py
- 统一输出 audit 格式

触发场景:
- cron 每日 9:00    -> daily-health-check (workflow)
- cron 每周日 9:00  -> capacity-planning (workflow)
- cron 大促前 7 天  -> pre-launch-check (workflow)
- 5xx 告警 webhook  -> emergency-troubleshoot (agent)
- 巡检 N+ critical  -> 升级 agent
- 用户提问         -> agent

双引擎分工:
- workflow-runner (90%): 已知 runbook, 已知输入, 毫秒级
- agent-fallback (10%): 异常场景, 智能分析 + 解释
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from _shared import log, _resolve_runbooks_output_dir

__all__ = ["Orchestrator", "DispatchDecision", "route_dispatch"]


# 路由决策树
class DispatchDecision:
    """dispatch 决策."""

    def __init__(self, runbook: str, engine: str, reason: str, priority: int = 5):
        self.runbook = runbook
        self.engine = engine  # "workflow" | "agent"
        self.reason = reason
        self.priority = priority  # 1=最高, 9=最低

    def __repr__(self):
        return f"<DispatchDecision runbook={self.runbook} engine={self.engine} priority={self.priority} reason={self.reason[:50]}>"

    def to_dict(self):
        return {
            "runbook": self.runbook,
            "engine": self.engine,
            "reason": self.reason,
            "priority": self.priority,
        }


# 场景到 runbook 的映射
SCENARIO_MAP = {
    "daily_check": ("daily-health-check.py", "workflow"),
    "weekly_capacity": ("capacity-planning.py", "workflow"),
    "pre_launch": ("pre-launch-check.py", "workflow"),
    "emergency": ("emergency-troubleshoot.py", "agent"),
    "user_query": ("emergency-troubleshoot.py", "agent"),  # 复用
    "post_mortem": ("emergency-troubleshoot.py", "agent"),
}


def route_dispatch(scenario: str, critical_count: int = 0, source: str = "cron") -> DispatchDecision:
    """根据场景选 runbook + 引擎.

    Args:
        scenario: 场景名 (daily_check/weekly_capacity/pre_launch/emergency/user_query/post_mortem)
        critical_count: 当前 critical 数 (巡检升级判定)
        source: 触发源 (cron/webhook/user/event)

    Returns:
        DispatchDecision
    """
    # 巡检发现 ≥ 3 critical -> 升级到 agent 分析
    if scenario == "daily_check" and critical_count >= 3:
        return DispatchDecision(
            runbook="daily-health-check.py",
            engine="agent",  # 升级
            reason=f"巡检发现 {critical_count} critical, 升级到 agent 根因分析",
            priority=2,
        )

    # 正常路由
    if scenario not in SCENARIO_MAP:
        return DispatchDecision(
            runbook="daily-health-check.py",
            engine="workflow",
            reason=f"未知场景 {scenario}, fallback 到 daily-health-check",
            priority=5,
        )

    runbook, engine = SCENARIO_MAP[scenario]
    reason = f"场景 {scenario} 路由到 {runbook} ({engine})"
    priority_map = {
        "emergency": 1,  # 紧急排查最高优先级
        "user_query": 2,
        "post_mortem": 3,
        "pre_launch": 4,
        "daily_check": 5,
        "weekly_capacity": 6,
    }
    return DispatchDecision(runbook=runbook, engine=engine, reason=reason, priority=priority_map.get(scenario, 5))


class Orchestrator:
    """双引擎编排器."""

    def __init__(self, scripts_dir: str = None, output_dir: str = "audit-results"):
        self.scripts_dir = Path(scripts_dir or Path(__file__).parent)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dispatch_log = self.output_dir / "dispatch-log.jsonl"

    def dispatch(self, scenario: str, args: dict, critical_count: int = 0, source: str = "cron") -> dict:
        """分发一个任务.

        Args:
            scenario: 场景名
            args: 传给 runbook 的参数 (e.g. {"customer": "rg-xxx", "region": "cn-hangzhou"})
            critical_count: critical 数 (用于升级判定)
            source: 触发源

        Returns:
            dict 含 runbook_path, engine, exit_code, duration, output
        """
        decision = route_dispatch(scenario, critical_count, source)
        log("DIAG", f"dispatch scenario={scenario} -> {decision}")

        t0 = time.time()
        runbook_path = self.scripts_dir / decision.runbook
        if not runbook_path.exists():
            return {
                "decision": decision.to_dict(),
                "exit_code": -1,
                "duration_seconds": 0,
                "error": f"runbook not found: {runbook_path}",
            }

        # 构造命令行参数
        cmd = ["python3", str(runbook_path)]
        for k, v in args.items():
            if isinstance(v, bool) and v:
                cmd.append(f"--{k.replace('_', '-')}")
            elif not isinstance(v, bool):
                cmd.extend([f"--{k.replace('_', '-')}", str(v)])
        # 总是加 non-interactive
        if "non_interactive" not in args and "describe" not in args:
            cmd.append("--non-interactive")

        # 引擎分流
        if decision.engine == "workflow":
            # workflow: 直接执行, 无 LLM
            log("DIAG", f"workflow engine: {' '.join(cmd)}")
            # Sprint 13: 不同 scenario 不同 lock key
            env = {**os.environ, "CRUISE_LOCK_KEY": f"orch-{scenario}-{decision.runbook}"}
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=900, env=env
                )
                exit_code = result.returncode
                output = result.stdout[-2000:]  # 截取最后 2KB
            except subprocess.TimeoutExpired:
                exit_code = 124  # timeout
                output = "[TIMEOUT after 900s]"
        else:
            # agent: 委托给 agent-fallback.py
            log("DIAG", f"agent engine: 委托给 agent-fallback.py")
            agent_cmd = ["python3", str(self.scripts_dir / "agent-fallback.py"),
                         "--scenario", scenario, "--runbook", str(runbook_path)]
            for k, v in args.items():
                agent_cmd.extend([f"--{k.replace('_', '-')}", str(v)])
            env = {**os.environ, "CRUISE_LOCK_KEY": f"orch-agent-{scenario}"}
            try:
                result = subprocess.run(
                    agent_cmd, capture_output=True, text=True, timeout=900, env=env
                )
                exit_code = result.returncode
                output = result.stdout[-2000:]
            except subprocess.TimeoutExpired:
                exit_code = 124
                output = "[AGENT TIMEOUT]"

        duration = time.time() - t0
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "scenario": scenario,
            "source": source,
            "decision": decision.to_dict(),
            "command": cmd,
            "exit_code": exit_code,
            "duration_seconds": round(duration, 2),
            "output_tail": output,
        }
        # 写 dispatch log
        with open(self.dispatch_log, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def cron_daily_check(self, customer: str, region: str, **kwargs) -> dict:
        """每日健康巡检 (固化工作流)."""
        return self.dispatch("daily_check", {
            "customer": customer, "region": region,
            "resource_group_id": kwargs.get("resource_group_id", ""),
            "output_dir": str(self.output_dir),
        }, source="cron")

    def cron_weekly_capacity(self, customer: str, region: str, **kwargs) -> dict:
        """每周容量预测 (固化工作流)."""
        return self.dispatch("weekly_capacity", {
            "customer": customer, "region": region,
            "resource_group_id": kwargs.get("resource_group_id", ""),
            "output_dir": str(self.output_dir),
        }, source="cron")

    def cron_pre_launch(self, customer: str, region: str, multiplier: float = 3.0) -> dict:
        """大促前预检 (固化工作流)."""
        return self.dispatch("pre_launch", {
            "customer": customer, "region": region,
            "resource_group_id": "",
            "multiplier": multiplier,
            "output_dir": str(self.output_dir),
        }, source="cron")

    def agent_emergency(self, customer: str, reported_time: str, **kwargs) -> dict:
        """故障应急排查 (Agent 兜底)."""
        return self.dispatch("emergency", {
            "customer": customer,
            "reported_time": reported_time,
            "region": kwargs.get("region", "cn-hangzhou"),
            "output_dir": str(self.output_dir),
        }, source="webhook")

    def agent_user_query(self, customer: str, query: str, **kwargs) -> dict:
        """用户提问 (Agent 兜底)."""
        return self.dispatch("user_query", {
            "customer": customer,
            "reported_time": query,  # 用户提问作为 reported_time
            "region": kwargs.get("region", "cn-hangzhou"),
            "output_dir": str(self.output_dir),
        }, source="user")


def main():
    ap = argparse.ArgumentParser(description="Cruise 双引擎编排器 (Stage 3 D1)", allow_abbrev=False)
    ap.add_argument("--scenario",
                    choices=["daily_check", "weekly_capacity", "pre_launch", "emergency", "user_query", "post_mortem"])
    ap.add_argument("--customer")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--resource-group-id", default="")
    ap.add_argument("--reported-time", help="emergency 场景必填")
    ap.add_argument("--multiplier", type=float, default=3.0, help="pre_launch 场景")
    ap.add_argument("--output-dir", default=_resolve_runbooks_output_dir())
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()

    print(f"\n{'=' * 50}\n  Cruise Orchestrator v1.0.0 (Stage 3 D1)\n{'=' * 50}")

    if args.describe:
        print("双引擎架构:")
        print("  - workflow (90%): 已知 cron/runbook, 毫秒级响应, 不经过 LLM")
        print("  - agent    (10%): 异常场景, 智能分析 + 解释")
        print()
        print("路由决策:")
        for s, (rb, eng) in SCENARIO_MAP.items():
            print(f"  {s:<20} -> {rb:<35} ({eng})")
        print()
        print("升级规则:")
        print("  - daily_check 发现 ≥ 3 critical -> 升级到 agent")
        return

    # 校验必填
    if not args.scenario or not args.customer:
        print("[ERROR] --scenario 和 --customer 必填 (或用 --describe)")
        sys.exit(2)

    orch = Orchestrator(output_dir=args.output_dir)

    if args.scenario == "daily_check":
        record = orch.cron_daily_check(args.customer, args.region,
                                       resource_group_id=args.resource_group_id)
    elif args.scenario == "weekly_capacity":
        record = orch.cron_weekly_capacity(args.customer, args.region,
                                           resource_group_id=args.resource_group_id)
    elif args.scenario == "pre_launch":
        record = orch.cron_pre_launch(args.customer, args.region, args.multiplier)
    elif args.scenario == "emergency":
        if not args.reported_time:
            print("[ERROR] emergency 场景需 --reported-time")
            sys.exit(2)
        record = orch.agent_emergency(args.customer, args.reported_time, region=args.region)
    elif args.scenario == "user_query":
        if not args.reported_time:
            print("[ERROR] user_query 场景需 --reported-time 作为 query")
            sys.exit(2)
        record = orch.agent_user_query(args.customer, args.reported_time, region=args.region)
    elif args.scenario == "post_mortem":
        record = orch.dispatch("post_mortem", {
            "customer": args.customer, "reported_time": args.reported_time or "",
            "region": args.region, "output_dir": args.output_dir,
        }, source="user")
    else:
        print(f"[ERROR] 未知场景 {args.scenario}")
        sys.exit(2)

    print(f"\n{'=' * 50}")
    print(f"  决策: {record.get('decision', {}).get('engine', '?')} engine")
    print(f"  runbook: {record.get('decision', {}).get('runbook', '?')}")
    print(f"  exit_code: {record.get('exit_code', '?')}")
    print(f"  duration: {record.get('duration_seconds', 0)}s")
    print(f"  dispatch log: {orch.dispatch_log}")
    print(f"{'=' * 50}")

    sys.exit(record.get("exit_code", 0))


if __name__ == "__main__":
    main()
