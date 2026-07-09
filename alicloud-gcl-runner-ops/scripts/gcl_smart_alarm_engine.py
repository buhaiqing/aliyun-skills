#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcl_smart_alarm_engine.py — GCL 智能告警闭环引擎 (Smart Alert Loop)

实现模式驱动的智能告警，替代传统阈值告警：
- 资源级风险模式识别（同一资源反复失败）
- 动态阈值调整（Region级集中爆发检测）
- 自动降级控制（自动降低高风险资源的max_iter）

USAGE
-----
    # 分析最近30分钟trace，识别风险模式
    python3 gcl_smart_alarm_engine.py \
      --trace-dir .runtime/audit/gcl-runner-ops/ \
      --window-minutes 30 \
      --apply-degradation

    # 仅检测模式，不执行降级（dry-run）
    python3 gcl_smart_alarm_engine.py \
      --trace-dir .runtime/audit/gcl-runner-ops/ \
      --window-minutes 30 \
      --dry-run

    # 检查降级状态并自动恢复过期降级
    python3 gcl_smart_alarm_engine.py \
      --check-degradation \
      --restore-expired

EXIT CODES
----------
    0  CLEAN       — 无风险模式 detected
    1  DETECTED    — 检测到风险模式，已告警
    2  DEGRADED    — 检测到风险模式，已执行降级
    3  RESTORED    — 过期降级已恢复
    4  ERROR       — 执行错误
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

#: 资源ID提取模式（按skill）
# 支持引号包围的值（单引号、双引号）
RESOURCE_PATTERNS: Dict[str, str] = {
    "alicloud-ecs-ops": r"--InstanceId\s+['\"]?(i-[a-z0-9]+)['\"]?",
    "alicloud-rds-ops": r"--DBInstanceId\s+['\"]?(rm-[a-z0-9]+)['\"]?",
    "alicloud-redis-ops": r"--InstanceId\s+['\"]?(r-[a-z0-9]+)['\"]?",
    "alicloud-mongodb-ops": r"--DBInstanceId\s+['\"]?(dds-[a-z0-9]+)['\"]?",
    "alicloud-polar-mysql-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-polar-postgresql-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-polar-oracle-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-elasticsearch-ops": r"--InstanceId\s+['\"]?(es-[a-z0-9]+)['\"]?",
    "alicloud-vpc-ops": r"--VpcId\s+['\"]?(vpc-[a-z0-9]+)['\"]?",
    "alicloud-nat-ops": r"--NatGatewayId\s+['\"]?(ngw-[a-z0-9]+)['\"]?",
    "alicloud-eip-ops": r"--AllocationId\s+['\"]?(eip-[a-z0-9]+)['\"]?",
    "alicloud-slb-ops": r"--LoadBalancerId\s+['\"]?(lb-[a-z0-9]+)['\"]?",
    "alicloud-ack-ops": r"--ClusterId\s+['\"]?(c-[a-z0-9]+)['\"]?",
    "alicloud-fc-ops": r"--serviceName\s+['\"]?([^\s'\"]+)['\"]?",
    "alicloud-kms-ops": r"--KeyId\s+['\"]?(key-[a-z0-9]+)['\"]?",
    "alicloud-ram-ops": r"--UserName\s+['\"]?([^\s'\"]+)['\"]?",
    "alicloud-sls-ops": r"--project\s+['\"]?([^\s'\"]+)['\"]?",
}

#: Region提取模式（支持数字和引号，如 cn-hangzhou-finance-1, ap-southeast-1）
REGION_PATTERN = r"--RegionId\s+['\"]?(cn-[a-z0-9-]+|ap-[a-z0-9-]+|eu-[a-z0-9-]+|us-[a-z0-9-]+)['\"]?"

#: 风险模式定义
RiskPattern = Dict[str, Any]

DEFAULT_RISK_PATTERNS: List[RiskPattern] = [
    {
        "id": "resource_safety_repeated",
        "name": "资源级Safety反复失败",
        "description": "同一资源在窗口期内多次Safety失败，表明该资源可能存在结构性问题",
        "min_occurrences": 2,
        "group_by": "resource_id",
        "decisions": {"SAFETY_FAIL"},
        "window_minutes": 30,
        "severity": "P1",
        "action": "downgrade_resource_max_iter",
        "action_params": {"target_max_iter": 1, "restore_after_minutes": 60},
    },
    {
        "id": "resource_hallucination_repeated",
        "name": "资源级Hallucination持续发生",
        "description": "同一资源多次触发Hallucination检测失败，可能存在模型漂移",
        "min_occurrences": 2,
        "group_by": "resource_id",
        "decisions": {"HALLUCINATION_ABORT"},
        "window_minutes": 60,
        "severity": "P2",
        "action": "downgrade_resource_max_iter",
        "action_params": {"target_max_iter": 1, "restore_after_minutes": 30},
    },
    {
        "id": "region_safety_burst",
        "name": "Region级Safety集中爆发",
        "description": "同一Region内多个资源短时间内Safety失败，可能存在区域性故障",
        "min_occurrences": 5,
        "group_by": "region",
        "decisions": {"SAFETY_FAIL"},
        "window_minutes": 15,
        "severity": "P0",
        "action": "trigger_region_inspection",
        "action_params": {},
    },
    {
        "id": "skill_wide_failure",
        "name": "Skill级全面失败",
        "description": "同一Skill在窗口期内多次失败，可能存在Skill配置或API变更问题",
        "min_occurrences": 10,
        "group_by": "skill",
        "decisions": {"SAFETY_FAIL", "HALLUCINATION_ABORT", "MAX_ITER"},
        "window_minutes": 20,
        "severity": "P0",
        "action": "alert_skill_maintainer",
        "action_params": {},
    },
]

#: 默认max_iter映射（来自gcl_runner.py）
DEFAULT_SKILL_MAX_ITER = {
    "alicloud-ecs-ops": 2,
    "alicloud-redis-ops": 2,
    "alicloud-rds-ops": 2,
    "alicloud-ram-ops": 2,
    "alicloud-kms-ops": 2,
    "alicloud-eip-ops": 2,
    "alicloud-vpc-ops": 2,
    "alicloud-nat-ops": 2,
    "alicloud-mongodb-ops": 2,
    "alicloud-elasticsearch-ops": 2,
    "alicloud-polar-mysql-ops": 2,
    "alicloud-polar-postgresql-ops": 2,
    "alicloud-polar-oracle-ops": 2,
    "alicloud-dts-ops": 2,
    "alicloud-waf-ops": 2,
    "alicloud-sls-ops": 2,
    "alicloud-terraform-ops": 2,
    "alicloud-slb-ops": 3,
    "alicloud-ack-ops": 3,
    "alicloud-ask-ops": 3,
    "alicloud-fc-ops": 3,
    "alicloud-eci-ops": 3,
    "alicloud-cms-ops": 3,
    "alicloud-actiontrail-ops": 5,
    "alicloud-billing-ops": 5,
    "alicloud-das-ops": 5,
    "alicloud-resourcemanager-ops": 5,
    "alicloud-agentrun-ops": 5,
}

EXIT_CLEAN = 0
EXIT_DETECTED = 1
EXIT_DEGRADED = 2
EXIT_RESTORED = 3
EXIT_ERROR = 4


def get_degradation_state_path() -> Path:
    """获取降级状态文件路径。"""
    runtime_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if runtime_root:
        return Path(runtime_root) / "gcl-degradation-state.json"
    # fallback
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent / ".runtime" / "gcl-degradation-state.json"


def load_degradation_state() -> Dict[str, Any]:
    """加载当前降级状态。"""
    path = get_degradation_state_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "downgraded_resources": {},
        "hot_regions": {},
        "version": "1.0.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def save_degradation_state(state: Dict[str, Any]) -> None:
    """保存降级状态。"""
    path = get_degradation_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_resource_id(skill: str, command: str) -> Optional[str]:
    """从命令中提取资源唯一标识。"""
    pattern = RESOURCE_PATTERNS.get(skill)
    if not pattern:
        return None
    m = re.search(pattern, command)
    return m.group(1) if m else None


def extract_region(command: str) -> Optional[str]:
    """从命令中提取Region。"""
    m = re.search(REGION_PATTERN, command)
    return m.group(1) if m else None


def parse_trace_file(path: Path) -> Optional[Dict[str, Any]]:
    """解析单个trace文件，提取关键字段。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # 基础字段
    skill = data.get("skill", "unknown")
    timestamp_str = data.get("timestamp") or data.get("generated_at")
    timestamp = None
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    if timestamp is None:
        # 使用文件mtime
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    # 取最后一次迭代的结果
    iterations = data.get("iterations", [])
    if not iterations:
        return None

    last_iter = iterations[-1]
    decision = last_iter.get("decision", "UNKNOWN")

    # 提取命令
    generator = last_iter.get("generator", {})
    command = generator.get("command", "")

    # 提取资源ID和Region
    resource_id = extract_resource_id(skill, command)
    region = extract_region(command)

    return {
        "trace_file": path.name,
        "skill": skill,
        "timestamp": timestamp,
        "decision": decision,
        "resource_id": resource_id,
        "region": region,
        "command": command[:200],  # 截断避免过大
    }


def load_traces(trace_dir: Path, window_minutes: int) -> List[Dict[str, Any]]:
    """加载指定时间窗口内的所有trace。"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)

    traces = []
    if not trace_dir.is_dir():
        return traces

    for path in trace_dir.glob("gcl-trace-*.json"):
        trace = parse_trace_file(path)
        if trace and trace["timestamp"] >= cutoff:
            traces.append(trace)

    return sorted(traces, key=lambda x: x["timestamp"])


def match_risk_pattern(
    traces: List[Dict[str, Any]], pattern: RiskPattern
) -> List[Dict[str, Any]]:
    """
    检测是否匹配风险模式。
    返回匹配该模式的资源组列表，每组包含触发告警的详细信息。
    """
    window = timedelta(minutes=pattern["window_minutes"])
    now = datetime.now(timezone.utc)
    cutoff = now - window

    # 过滤时间窗口内的trace
    window_traces = [t for t in traces if t["timestamp"] >= cutoff]

    # 过滤指定的decision类型
    decision_filter = pattern.get("decisions", set())
    filtered_traces = [t for t in window_traces if t["decision"] in decision_filter]

    if not filtered_traces:
        return []

    # 按group_by分组
    group_by = pattern["group_by"]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for t in filtered_traces:
        key = t.get(group_by) or "unknown"
        if key:
            groups[key].append(t)

    # 检查每组是否达到阈值
    min_occurrences = pattern["min_occurrences"]
    matches = []

    for key, group_traces in groups.items():
        if len(group_traces) >= min_occurrences:
            # 去重资源（同一资源多次触发只算一个）
            unique_resources = set(t.get("resource_id") for t in group_traces if t.get("resource_id"))
            unique_skills = set(t.get("skill") for t in group_traces)
            unique_regions = set(t.get("region") for t in group_traces if t.get("region"))

            matches.append({
                "pattern_id": pattern["id"],
                "pattern_name": pattern["name"],
                "severity": pattern["severity"],
                "group_key": key,
                "group_by": group_by,
                "occurrence_count": len(group_traces),
                "unique_resources": list(unique_resources),
                "unique_skills": list(unique_skills),
                "unique_regions": list(unique_regions),
                "first_seen": min(t["timestamp"] for t in group_traces).isoformat(),
                "last_seen": max(t["timestamp"] for t in group_traces).isoformat(),
                "action": pattern.get("action"),
                "action_params": pattern.get("action_params", {}),
            })

    return matches


def apply_degradation(
    match: Dict[str, Any], state: Dict[str, Any], dry_run: bool = False
) -> Dict[str, Any]:
    """
    执行降级动作。
    返回执行结果描述。
    """
    action = match.get("action")
    params = match.get("action_params", {})
    group_key = match["group_key"]
    group_by = match["group_by"]

    result = {
        "action": action,
        "applied": False,
        "message": "",
        "state_changed": False,
    }

    if action == "downgrade_resource_max_iter":
        if group_by != "resource_id":
            result["message"] = f"Action {action} requires group_by=resource_id, got {group_by}"
            return result

        target_max_iter = params.get("target_max_iter", 1)
        restore_after = params.get("restore_after_minutes", 60)

        # 找到该资源对应的skill
        skills = match.get("unique_skills", [])
        skill = skills[0] if skills else "unknown"
        original_max_iter = DEFAULT_SKILL_MAX_ITER.get(skill, 2)

        if not dry_run:
            state["downgraded_resources"][group_key] = {
                "resource_id": group_key,
                "skill": skill,
                "original_max_iter": original_max_iter,
                "current_max_iter": target_max_iter,
                "downgraded_at": datetime.now(timezone.utc).isoformat(),
                "auto_restore_at": (datetime.now(timezone.utc) + timedelta(minutes=restore_after)).isoformat(),
                "reason": match["pattern_name"],
                "triggered_by": match["pattern_id"],
            }
            save_degradation_state(state)
            result["state_changed"] = True

        result["applied"] = True
        result["message"] = (
            f"Resource {group_key} max_iter downgraded: "
            f"{original_max_iter} → {target_max_iter} "
            f"(restore at +{restore_after}min)"
        )

    elif action == "trigger_region_inspection":
        if group_by != "region":
            result["message"] = f"Action {action} requires group_by=region, got {group_by}"
            return result

        if not dry_run:
            state["hot_regions"][group_key] = {
                "region": group_key,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "occurrence_count": match["occurrence_count"],
                "affected_skills": match.get("unique_skills", []),
            }
            save_degradation_state(state)
            result["state_changed"] = True

        result["applied"] = True
        result["message"] = (
            f"Region {group_key} marked for inspection: "
            f"{match['occurrence_count']} occurrences detected"
        )

    elif action == "alert_skill_maintainer":
        # 仅告警，不修改状态
        result["applied"] = True
        result["message"] = (
            f"Skill {group_key} requires maintainer attention: "
            f"{match['occurrence_count']} failures in window"
        )

    else:
        result["message"] = f"Unknown action: {action}"

    return result


def restore_expired_degradations(state: Dict[str, Any], dry_run: bool = False) -> List[str]:
    """
    检查并恢复已过期的降级。
    返回已恢复的资源ID列表。
    """
    now = datetime.now(timezone.utc)
    restored = []

    downgraded = state.get("downgraded_resources", {})
    to_restore = []

    for resource_id, info in list(downgraded.items()):
        restore_at_str = info.get("auto_restore_at")
        if restore_at_str:
            try:
                restore_at = datetime.fromisoformat(restore_at_str)
                if restore_at <= now:
                    to_restore.append(resource_id)
            except (ValueError, TypeError):
                pass

    for resource_id in to_restore:
        info = downgraded[resource_id]
        original = info.get("original_max_iter", 2)

        if not dry_run:
            del downgraded[resource_id]
            restored.append(resource_id)

        restored.append(
            f"{resource_id}: max_iter restored to {original} "
            f"(was downgraded at {info.get('downgraded_at')})"
        )

    if restored and not dry_run:
        save_degradation_state(state)

    return restored


def format_alert_output(findings: List[Dict[str, Any]], restored: List[str]) -> str:
    """格式化告警输出。"""
    lines = []
    lines.append("=" * 70)
    lines.append("GCL Smart Alert Engine — Detection Report")
    lines.append("=" * 70)
    lines.append(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    if findings:
        lines.append(f"🚨 DETECTED {len(findings)} RISK PATTERN(S):")
        lines.append("")
        for i, finding in enumerate(findings, 1):
            lines.append(f"  [{i}] {finding['pattern_name']} ({finding['severity']})")
            lines.append(f"      Group: {finding['group_by']}={finding['group_key']}")
            lines.append(f"      Occurrences: {finding['occurrence_count']}")
            if finding.get('unique_resources'):
                lines.append(f"      Resources: {', '.join(finding['unique_resources'][:5])}")
            if finding.get('unique_regions'):
                lines.append(f"      Regions: {', '.join(finding['unique_regions'])}")
            lines.append(f"      Action: {finding.get('action', 'none')}")
            if finding.get('degradation_result'):
                result = finding['degradation_result']
                status = "✅ Applied" if result['applied'] else "❌ Failed"
                lines.append(f"      Degradation: {status} — {result.get('message', '')}")
            lines.append("")
    else:
        lines.append("✅ No risk patterns detected in the analysis window.")
        lines.append("")

    if restored:
        lines.append(f"♻️  RESTORED {len(restored)} EXPIRED DEGRADATION(S):")
        for r in restored:
            lines.append(f"    - {r}")
        lines.append("")

    # 当前降级状态摘要
    state = load_degradation_state()
    downgraded = state.get("downgraded_resources", {})
    hot_regions = state.get("hot_regions", {})

    if downgraded:
        lines.append(f"📊 CURRENTLY DEGRADED RESOURCES ({len(downgraded)}):")
        for rid, info in list(downgraded.items())[:5]:  # 最多显示5个
            lines.append(
                f"    - {rid}: max_iter={info.get('current_max_iter')} "
                f"(restore at {info.get('auto_restore_at', 'unknown')[:16]})"
            )
        if len(downgraded) > 5:
            lines.append(f"    ... and {len(downgraded) - 5} more")
        lines.append("")

    if hot_regions:
        lines.append(f"🔥 HOT REGIONS ({len(hot_regions)}):")
        for region, info in hot_regions.items():
            lines.append(f"    - {region}: detected at {info.get('detected_at', 'unknown')[:16]}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_smart_alarm_engine.py",
        description="GCL 智能告警闭环引擎 — 模式驱动的动态告警与自动降级",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # 分析最近30分钟，检测风险模式
              python3 gcl_smart_alarm_engine.py --window-minutes 30

              # 检测并执行自动降级
              python3 gcl_smart_alarm_engine.py --window-minutes 30 --apply-degradation

              # 仅检测，不执行降级（dry-run）
              python3 gcl_smart_alarm_engine.py --window-minutes 30 --dry-run

              # 检查并恢复过期降级
              python3 gcl_smart_alarm_engine.py --check-degradation --restore-expired
            """
        ),
    )
    p.add_argument(
        "--trace-dir",
        type=Path,
        default=Path(os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT", Path(__file__).resolve().parent.parent.parent / ".runtime")) / "audit" / "gcl-runner-ops",
        help="GCL trace文件目录 (default: ${RUNTIME_ROOT}/audit/gcl-runner-ops)",
    )
    p.add_argument(
        "--window-minutes",
        type=int,
        default=30,
        help="分析时间窗口（分钟） (default: 30)",
    )
    p.add_argument(
        "--apply-degradation",
        action="store_true",
        help="检测到风险模式时执行自动降级",
    )
    p.add_argument(
        "--check-degradation",
        action="store_true",
        help="仅检查当前降级状态",
    )
    p.add_argument(
        "--restore-expired",
        action="store_true",
        help="恢复已过期的降级",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟执行，不实际修改状态",
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="将结果保存为JSON文件",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # 仅检查降级状态模式
    if args.check_degradation:
        state = load_degradation_state()
        restored = []
        if args.restore_expired:
            restored = restore_expired_degradations(state, dry_run=args.dry_run)
        print(format_alert_output([], restored))
        return EXIT_RESTORED if restored else EXIT_CLEAN

    # 加载trace并分析
    traces = load_traces(args.trace_dir, args.window_minutes)
    if not traces:
        print(f"[INFO] No traces found in {args.trace_dir} for last {args.window_minutes} minutes")
        return EXIT_CLEAN

    print(f"[INFO] Loaded {len(traces)} traces from last {args.window_minutes} minutes")

    # 检测风险模式
    state = load_degradation_state()
    all_findings = []

    for pattern in DEFAULT_RISK_PATTERNS:
        matches = match_risk_pattern(traces, pattern)
        for match in matches:
            # 执行降级（如果启用）
            if args.apply_degradation:
                result = apply_degradation(match, state, dry_run=args.dry_run)
                match["degradation_result"] = result
            all_findings.append(match)

    # 恢复过期降级
    restored = []
    if args.restore_expired:
        restored = restore_expired_degradations(state, dry_run=args.dry_run)

    # 输出结果
    output = format_alert_output(all_findings, restored)
    print(output)

    # 保存JSON报告
    if args.output_json:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": args.window_minutes,
            "traces_analyzed": len(traces),
            "findings": all_findings,
            "restored": restored,
            "current_state": {
                "downgraded_resources": state.get("downgraded_resources", {}),
                "hot_regions": state.get("hot_regions", {}),
            },
        }
        args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[INFO] Report saved to {args.output_json}")

    # 返回码
    if all_findings and args.apply_degradation:
        return EXIT_DEGRADED
    elif all_findings:
        return EXIT_DETECTED
    elif restored:
        return EXIT_RESTORED
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
