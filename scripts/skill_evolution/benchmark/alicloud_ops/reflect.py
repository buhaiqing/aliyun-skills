#!/usr/bin/env python3
"""Reflect stage — pass L1 trajectory context into SkillOpt minibatch reflect."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from rollout import resolve_skills_root
from trajectories import build_trajectory_memory_context, load_trajectories, resolve_trajectories_path


def _trajectory_memory_context(results: list[dict], trajectories_path: Path, skill: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for row in results:
        ctx = str(row.get("trajectory_memory_context") or "").strip()
        if ctx and ctx not in seen:
            parts.append(ctx)
            seen.add(ctx)
    if not parts:
        ctx = build_trajectory_memory_context(load_trajectories(trajectories_path), skill=skill, top_k=12)
        if ctx:
            parts.append(ctx)
    return "\n\n".join(parts[:4])


def run_reflect(
    results: list[dict],
    skill_content: str,
    out_dir: str,
    *,
    trajectories_path: str | Path | None = None,
    skills_root: str | Path | None = None,
    skill: str = "alicloud-ecs-ops",
    **kwargs: Any,
) -> list[dict | None]:
    try:
        from skillopt.gradient.reflect import run_minibatch_reflect
    except ImportError as exc:
        raise RuntimeError("skillopt package required for reflect stage") from exc

    root = resolve_skills_root(skills_root)
    traj_path = resolve_trajectories_path(trajectories_path, root, skill)
    cfg = kwargs.get("cfg") or {}
    return run_minibatch_reflect(
        results=results,
        skill_content=skill_content,
        prediction_dir=kwargs.get("prediction_dir", os.path.join(out_dir, "predictions")),
        patches_dir=kwargs.get("patches_dir", os.path.join(out_dir, "patches")),
        workers=int(kwargs.get("workers", 1)),
        failure_only=bool(kwargs.get("failure_only", False)),
        minibatch_size=int(kwargs.get("minibatch_size", 8)),
        edit_budget=int(kwargs.get("edit_budget", 4)),
        random_seed=kwargs.get("random_seed"),
        error_system=kwargs.get("error_system"),
        success_system=kwargs.get("success_system"),
        step_buffer_context=kwargs.get("step_buffer_context", ""),
        meta_skill_context=kwargs.get("meta_skill_context", ""),
        trajectory_memory_context=_trajectory_memory_context(results, traj_path, skill),
        update_mode=cfg.get("skill_update_mode", "patch"),
    )
