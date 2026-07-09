#!/usr/bin/env python3
"""Map natural-language eval queries to harness wrapper operations."""

from __future__ import annotations

import re
from typing import Any

# (pattern, operation, extra_argv, is_mutating)
_ECS_RULES: list[tuple[re.Pattern[str], str, list[str], bool]] = [
    (re.compile(r"创建|新建|开通"), "CreateInstance", [], True),
    (re.compile(r"停止|关机"), "StopInstance", [], True),
    (re.compile(r"启动|开机"), "StartInstance", [], True),
    (re.compile(r"删除|释放"), "DeleteInstance", [], True),
    (re.compile(r"快照"), "CreateSnapshot", [], True),
    (re.compile(r"镜像|更换操作系统|重装"), "ReplaceSystemDisk", [], True),
    (re.compile(r"云助手|执行命令|RunCommand"), "RunCommand", [], True),
    (re.compile(r"安全组|规则"), "DescribeSecurityGroups", ["--PageSize", "10"], False),
    (re.compile(r"云盘|磁盘|扩容"), "DescribeDisks", ["--PageSize", "10"], False),
    (re.compile(r"实例|ECS|服务器|查看|列出|Describe"), "DescribeInstances", ["--PageSize", "10"], False),
]

_DEFAULT_ECS = ("DescribeInstances", ["--PageSize", "10"], False)

_SKILL_RULES: dict[str, list[tuple[re.Pattern[str], str, list[str], bool]]] = {
    "alicloud-ecs-ops": _ECS_RULES,
}


def resolve_from_trajectories(
    query: str,
    skill: str,
    trajectories: list[dict[str, Any]] | None,
) -> tuple[str, list[str], bool] | None:
    """Pick operation from prior L1 trajectories when query tokens overlap."""
    if not trajectories:
        return None
    query_l = query.lower()
    best: tuple[str, list[str], bool] | None = None
    best_score = 0
    for traj in trajectories:
        if traj.get("skill") != skill:
            continue
        op = str(traj.get("operation") or "")
        if not op or op == "unknown":
            continue
        cmd = str(traj.get("command") or "")
        score = sum(1 for tok in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", query_l) if tok.lower() in cmd.lower())
        if traj.get("rubric_pass"):
            score += 1
        if score > best_score:
            best_score = score
            argv = _argv_from_command(cmd, op)
            mutating = _is_mutating_operation(op)
            best = (op, argv, mutating)
    return best if best_score > 0 else None


def _argv_from_command(command: str, operation: str) -> list[str]:
    if not command:
        return ["--PageSize", "10"] if operation.startswith("Describe") else []
    parts = command.split()
    try:
        idx = parts.index(operation)
    except ValueError:
        return ["--PageSize", "10"] if operation.startswith("Describe") else []
    argv: list[str] = []
    i = idx + 1
    while i < len(parts):
        token = parts[i]
        if token in {"aliyun", "ecs", "rds", "slb"}:
            break
        if token.startswith("-"):
            argv.append(token)
            if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                argv.append(parts[i + 1])
                i += 1
        i += 1
    return argv or (["--PageSize", "10"] if operation.startswith("Describe") else [])


def _is_mutating_operation(operation: str) -> bool:
    prefixes = ("Create", "Delete", "Stop", "Start", "Replace", "Modify", "Run", "Put")
    return any(operation.startswith(p) for p in prefixes) and not operation.startswith("Describe")


def resolve_operation(
    query: str,
    skill: str = "alicloud-ecs-ops",
    *,
    trajectories: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str], bool]:
    """Return (operation, wrapper_argv, is_mutating) for a benchmark query."""
    rules = _SKILL_RULES.get(skill)
    if rules:
        for pattern, operation, argv, mutating in rules:
            if pattern.search(query):
                return operation, list(argv), mutating
        from_traj = resolve_from_trajectories(query, skill, trajectories)
        if from_traj is not None:
            return from_traj
        op, argv, mut = _DEFAULT_ECS
        return op, list(argv), mut

    from_traj = resolve_from_trajectories(query, skill, trajectories)
    if from_traj is not None:
        return from_traj
    return "unknown", [], False

