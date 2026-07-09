"""agent-fallback.py — 弹性 Agent 兜底引擎 (Sprint 13 Stage 3 D1)

职责: 10% 异常场景处理, 智能分析 + 解释
特点: 委托给 LLM + 工具, 30s 响应

执行模式 (MVP - 不实际调用 LLM, 提供决策树 + 委托):
- 紧急场景 (emergency): 1 次 emergency-troubleshoot.py + 输出根因 + 解释
- 用户提问 (user_query): 1 次 emergency-troubleshoot.py + 自然语言解释
- 巡检升级 (升级到 agent): 1 次 emergency-troubleshoot.py + 升级分析

后续可扩展: 接入 LLM (Qwen/Claude) 做自然语言解释 + 根因分析
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

__all__ = ["AgentFallback", "agent_dispatch"]


# Agent 决策树 (无 LLM 时的 MVP 规则)
AGENT_DECISION_TREE = {
    "emergency": {
        "actions": [
            "立即调用 emergency-troubleshoot.py",
            "解析根因 + ActionTrail",
            "输出『建议操作』列表 (白名单项 + 人工确认项)",
        ],
        "explain_template": """
## 故障分析 (Agent 兜底)

**触发源**: {source}
**报障时间**: {reported_time}
**客户**: {customer}

### 根因 (来自 runbook)
{root_cause}

### 证据链
{evidence}

### 建议操作 (优先级排序)
{suggested_actions}

### 后续监控
- 启用 backtrack_cms 7d 回溯 (来自 daily-health-check)
- 启用 K8s events 实时监控 (Sprint 5 后续)
- 设置 5xx 告警阈值 (Sprint 10 后续)
""",
    },
    "user_query": {
        "actions": [
            "解析用户提问为场景",
            "调用对应 runbook (默认 emergency-troubleshoot)",
            "用自然语言解释结果",
        ],
        "explain_template": """
## 答疑 (Agent 兜底)

**用户提问**: {query}
**客户**: {customer}

### 排查结果
{analysis}

### 进一步操作建议
{suggested_actions}
""",
    },
    "post_mortem": {
        "actions": [
            "回放最近 7d daily-health-check 结果",
            "回放 incident DB",
            "生成 Post-Mortem 报告",
        ],
    },
}


class AgentFallback:
    """弹性 Agent 兜底引擎 (MVP)."""

    def __init__(self, scripts_dir: str = None, output_dir: str = "audit-results"):
        self.scripts_dir = Path(scripts_dir or Path(__file__).parent)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.agent_log = self.output_dir / "agent-dispatch.jsonl"

    def _run_runbook(self, runbook: str, args: dict) -> dict:
        """调用底层 runbook."""
        runbook_path = self.scripts_dir / runbook
        if not runbook_path.exists():
            return {"exit_code": -1, "error": f"{runbook} not found"}

        cmd = ["python3", str(runbook_path)]
        for k, v in args.items():
            if isinstance(v, bool) and v:
                cmd.append(f"--{k.replace('_', '-')}")
            elif not isinstance(v, bool):
                cmd.extend([f"--{k.replace('_', '-')}", str(v)])

        log("DIAG", f"agent runbook: {runbook}")
        env = {**os.environ, "CRUISE_LOCK_KEY": f"agent-{runbook}"}
        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
            return {
                "runbook": runbook,
                "command": cmd,
                "exit_code": result.returncode,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-500:] if result.stderr else "",
                "duration_seconds": round(time.time() - t0, 2),
            }
        except subprocess.TimeoutExpired:
            return {
                "runbook": runbook,
                "exit_code": 124,
                "error": "TIMEOUT",
                "duration_seconds": 600,
            }

    def _parse_findings(self, runbook_output: dict) -> dict:
        """从 runbook 输出解析根因 (MVP: 简单字符串解析)."""
        stdout = runbook_output.get("stdout_tail", "")
        # 找根因段
        root_cause = "未明确根因"
        evidence = []
        if "根因" in stdout:
            for line in stdout.split("\n"):
                if "根因" in line:
                    root_cause = line.split("根因", 1)[-1].strip(":= ")
                    break
        return {
            "root_cause": root_cause[:500],
            "evidence": evidence or ["见 runbook 报告"],
        }

    def _suggest_actions(self, findings: dict, scenario: str) -> list:
        """基于 findings 给建议操作 (MVP 规则)."""
        actions = []
        if findings.get("root_cause", "").lower().find("5xx") >= 0 or "异常" in findings.get("root_cause", ""):
            actions.append({
                "priority": 1,
                "command": "aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou",
                "label": "READONLY",
                "reason": "列出 SLB 状态",
            })
            actions.append({
                "priority": 2,
                "command": "aliyun cms DescribeMetricList --Namespace acs_slb_dashboard --MetricName UnhealthyServerCount",
                "label": "READONLY",
                "reason": "查后端健康数",
            })
        if "SLB" in findings.get("root_cause", ""):
            actions.append({
                "priority": 3,
                "command": "aliyun slb SetLoadBalancerStatus --LoadBalancerId <id> --LoadBalancerStatus Active",
                "label": "SUGGESTED",
                "reason": "恢复 SLB (需人工确认)",
            })
        # 默认: 至少给一个 READONLY
        if not actions:
            actions.append({
                "priority": 9,
                "command": "aliyun actiontrail LookupEvents --StartTime $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)",
                "label": "READONLY",
                "reason": "查最近 1h 变更事件",
            })
        return actions

    def handle_emergency(self, customer: str, reported_time: str, **kwargs) -> dict:
        """处理 emergency 场景."""
        region = kwargs.get("region", "cn-hangzhou")
        log("DIAG", f"agent emergency: customer={customer} time={reported_time}")

        # 1. 调用 emergency-troubleshoot.py
        runbook_result = self._run_runbook("emergency-troubleshoot.py", {
            "customer": customer,
            "reported_time": reported_time,
            "region": region,
            "resource_group_id": kwargs.get("resource_group_id", ""),
            "output_dir": str(self.output_dir),
            "non_interactive": True,
        })

        # 2. 解析根因
        findings = self._parse_findings(runbook_result)

        # 3. 给建议
        suggested_actions = self._suggest_actions(findings, "emergency")

        # 4. 输出解释
        explain = AGENT_DECISION_TREE["emergency"]["explain_template"].format(
            source=kwargs.get("source", "unknown"),
            reported_time=reported_time,
            customer=customer,
            root_cause=findings["root_cause"],
            evidence="\n".join(f"- {e}" for e in findings["evidence"]),
            suggested_actions="\n".join(
                f"{a['priority']}. [{a['label']}] {a['command']}  ({a['reason']})"
                for a in suggested_actions
            ),
        )

        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "scenario": "emergency",
            "customer": customer,
            "reported_time": reported_time,
            "runbook_result": runbook_result,
            "findings": findings,
            "suggested_actions": suggested_actions,
            "explanation": explain,
        }
        with open(self.agent_log, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        return record

    def handle_user_query(self, customer: str, query: str, **kwargs) -> dict:
        """处理 user_query 场景."""
        region = kwargs.get("region", "cn-hangzhou")
        # 简单解析: 把 user query 当作 reported_time 传给 runbook
        return self.handle_emergency(customer, query[:25] + "Z", region=region)

    def handle_post_mortem(self, customer: str, **kwargs) -> dict:
        """处理 post_mortem 场景: 收集最近 7d 数据生成复盘报告."""
        log("DIAG", f"agent post_mortem: customer={customer}")
        # 找最近 7d cruise 报告
        reports = []
        if self.output_dir.exists():
            for f in sorted(self.output_dir.glob(f"cruise-*.json"), reverse=True)[:7]:
                reports.append(str(f))

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "scenario": "post_mortem",
            "customer": customer,
            "reports_analyzed": reports,
            "todo": "Post-Mortem 模板 (留 Sprint 13.2)",
        }


def agent_dispatch(scenario: str, customer: str, **kwargs) -> dict:
    """便捷函数: agent 分发."""
    agent = AgentFallback(output_dir=kwargs.get("output_dir", "audit-results"))
    # 提取 reported_time 避免冲突
    reported_time = kwargs.pop("reported_time", "")
    query = kwargs.pop("query", "")
    if scenario == "emergency":
        return agent.handle_emergency(customer, reported_time, **kwargs)
    elif scenario == "user_query":
        return agent.handle_user_query(customer, query or reported_time, **kwargs)
    elif scenario == "post_mortem":
        return agent.handle_post_mortem(customer, **kwargs)
    else:
        return {"error": f"未知场景 {scenario}"}


def main():
    ap = argparse.ArgumentParser(description="Agent Fallback (弹性 Agent 兜底)", allow_abbrev=False)
    ap.add_argument("--scenario", choices=["emergency", "user_query", "post_mortem"])
    ap.add_argument("--runbook", help="(orchestrator 调用时传入)")
    ap.add_argument("--customer")
    ap.add_argument("--reported-time", help="emergency 报障时间 / user_query 提问")
    ap.add_argument("--region", default=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"))
    ap.add_argument("--resource-group-id", default="")
    ap.add_argument("--output-dir", default=_resolve_runbooks_output_dir())
    ap.add_argument("--describe", action="store_true")
    args = ap.parse_args()

    print(f"\n{'=' * 50}\n  Agent Fallback v1.0.0 (Stage 3 D1)\n{'=' * 50}")

    if args.describe:
        print("Agent 决策树:")
        for s, info in AGENT_DECISION_TREE.items():
            print(f"\n  [{s}]")
            for a in info.get("actions", []):
                print(f"    - {a}")
        return

    if not args.scenario or not args.customer:
        print("[ERROR] --scenario 和 --customer 必填 (或用 --describe)")
        sys.exit(2)

    if args.scenario == "emergency":
        result = agent_dispatch("emergency", args.customer,
                                reported_time=args.reported_time,
                                region=args.region,
                                resource_group_id=args.resource_group_id,
                                output_dir=args.output_dir)
    elif args.scenario == "user_query":
        result = agent_dispatch("user_query", args.customer,
                                query=args.reported_time,
                                region=args.region,
                                output_dir=args.output_dir)
    elif args.scenario == "post_mortem":
        result = agent_dispatch("post_mortem", args.customer,
                                output_dir=args.output_dir)

    print(f"\n{'=' * 50}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        sys.exit(1)
    print(f"  场景: {result.get('scenario', '?')}")
    print(f"  客户: {result.get('customer', '?')}")
    if "findings" in result:
        f = result["findings"]
        print(f"  根因: {f.get('root_cause', '?')[:80]}")
    if "suggested_actions" in result:
        print(f"  建议操作数: {len(result['suggested_actions'])}")
    if "explanation" in result:
        print(f"\n{result['explanation']}")
    print(f"{'=' * 50}")
    sys.exit(0)


if __name__ == "__main__":
    main()
