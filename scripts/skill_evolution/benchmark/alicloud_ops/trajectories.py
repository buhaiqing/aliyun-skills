#!/usr/bin/env python3
"""Load Milestone A trajectories.jsonl for reflect-stage memory context."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from query_resolver import resolve_operation


def resolve_trajectories_path(
    explicit: str | Path | None,
    skills_root: Path,
    skill: str,
) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else (skills_root / p)
    env = os.environ.get("SKILL_EVOLUTION_TRAJECTORIES")
    if env:
        p = Path(env)
        return p if p.is_absolute() else (skills_root / p)
    return skills_root / ".runtime" / "skill-evolution" / skill / "trajectories.jsonl"


def load_trajectories(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(json.loads(stripped))
    return records


def select_for_query(
    trajectories: list[dict[str, Any]],
    query: str,
    skill: str,
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not trajectories:
        return []
    op, _, _ = resolve_operation(query, skill, trajectories=trajectories)
    matched = [t for t in trajectories if t.get("skill") == skill and t.get("operation") == op]
    if not matched:
        matched = [t for t in trajectories if t.get("skill") == skill]
    matched.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    return matched[:top_k]


def format_trajectory_block(traj: dict[str, Any]) -> str:
    fp = traj.get("failure_pattern") or {}
    fix = fp.get("fix", "") if isinstance(fp, dict) else ""
    lines = [
        f"- op={traj.get('operation')} status={traj.get('gcl_status')} "
        f"rubric_pass={traj.get('rubric_pass')} source={traj.get('source')}",
        f"  command={traj.get('command', '')}",
    ]
    if traj.get("error_code"):
        lines.append(f"  error_code={traj.get('error_code')}")
    if fix:
        lines.append(f"  fix={fix}")
    return "\n".join(lines)


def build_trajectory_memory_context(
    trajectories: list[dict[str, Any]],
    *,
    query: str | None = None,
    skill: str | None = None,
    top_k: int = 8,
) -> str:
    """Format L1 trajectories for SkillOpt reflect ``trajectory_memory_context``."""
    if not trajectories:
        return ""
    if query and skill:
        picked = select_for_query(trajectories, query, skill, top_k=top_k)
    else:
        picked = sorted(trajectories, key=lambda t: t.get("timestamp", ""), reverse=True)[:top_k]
    if not picked:
        return ""
    body = "\n".join(format_trajectory_block(t) for t in picked)
    return f"## Prior Layer-1 execution memory (sanitized)\n{body}"
