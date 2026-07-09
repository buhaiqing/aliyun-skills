#!/usr/bin/env python3
"""Execute benchmark query against a skill (mock or harness wrapper rollout)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_EVOLUTION_DIR = Path(__file__).resolve().parents[2]
if str(_EVOLUTION_DIR) not in sys.path:
    sys.path.insert(0, str(_EVOLUTION_DIR))
from export_trajectories import sanitize_command  # noqa: E402

from query_resolver import resolve_operation
from trajectories import (
    build_trajectory_memory_context,
    load_trajectories,
    resolve_trajectories_path,
    select_for_query,
)

_WRAPPER_GLOB = "*-harness-wrapper.sh"
_ROLLOUT_TIMEOUT_S = 120
_READONLY_OP_PREFIXES = ("Describe", "List", "Get", "Query")


def _redact_text(text: str, limit: int | None = None) -> str:
    out = sanitize_command(text or "")
    return out[:limit] if limit is not None else out


def _sanitize_rollout_record(rollout: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets before persisting rollout artifacts."""
    out = dict(rollout)
    for key in ("stdout_preview", "stderr_preview", "message"):
        if key in out and out[key]:
            limit = 500 if key == "stdout_preview" else 300 if key == "stderr_preview" else None
            out[key] = _redact_text(str(out[key]), limit)
    return out


def _rubric_pass_for_operation(operation: str, harness: dict[str, Any]) -> bool:
    """Pass on API Code 200; exit 0 without JSON only for read-only operations."""
    if harness.get("rubric_pass"):
        return True
    if harness.get("exit_code") != 0:
        return False
    if harness.get("api_payload"):
        return False
    return operation.startswith(_READONLY_OP_PREFIXES)


def resolve_skills_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ALIYUN_SKILLS_ROOT") or os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[4]


def _is_mock(mock: bool | None) -> bool:
    if mock is True:
        return True
    if mock is False:
        return False
    return os.environ.get("SKILL_EVOLUTION_MOCK_ROLLOUT") == "1"


def _find_harness_wrapper(skills_root: Path, skill: str) -> Path | None:
    scripts_dir = skills_root / skill / "scripts"
    if not scripts_dir.is_dir():
        return None
    matches = sorted(scripts_dir.glob(_WRAPPER_GLOB))
    return matches[0] if matches else None


def _parse_wrapper_json(stdout: str) -> tuple[bool, dict[str, Any]]:
    text = (stdout or "").strip()
    if not text:
        return False, {}
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                code = payload.get("Code", payload.get("code"))
                if code == 200 or str(code) == "200":
                    return True, payload
                return False, payload
    return False, {}


def _run_harness(
    wrapper: Path,
    skills_root: Path,
    skill: str,
    operation: str,
    argv: list[str],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    cmd = ["bash", str(wrapper), operation, *argv]
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    run_env.setdefault("SKILLOPT_ENABLED", "false")
    run_env.setdefault("HARNESS_ENABLED", "false")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_ROLLOUT_TIMEOUT_S,
            cwd=str(skills_root / skill),
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": "rollout timed out",
            "rubric_pass": False,
        }
    except OSError as exc:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "rubric_pass": False,
        }
    rubric_pass, payload = _parse_wrapper_json(proc.stdout)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "rubric_pass": rubric_pass,
        "api_payload": payload,
    }


def run_rollout(
    query: str,
    skill_md: str,
    *,
    skill: str = "alicloud-ecs-ops",
    mock: bool | None = None,
    skills_root: str | Path | None = None,
    trajectories: list[dict[str, Any]] | None = None,
    trajectories_path: str | Path | None = None,
    allow_mutating: bool | None = None,
) -> dict[str, Any]:
    skill_loaded = bool(skill_md.strip())
    root = resolve_skills_root(skills_root)
    if trajectories is None and trajectories_path is not None:
        trajectories = load_trajectories(Path(trajectories_path))
    elif trajectories is None:
        trajectories = load_trajectories(resolve_trajectories_path(None, root, skill))

    traj_ctx = build_trajectory_memory_context(trajectories, query=query, skill=skill)
    prior = select_for_query(trajectories, query, skill, top_k=3)
    operation, argv, is_mutating = resolve_operation(query, skill, trajectories=trajectories)

    if _is_mock(mock):
        return {
            "status": "mock",
            "skill_loaded": skill_loaded,
            "query": query,
            "skill": skill,
            "operation": operation,
            "wrapper_argv": argv,
            "is_mutating": is_mutating,
            "trajectory_count": len(prior),
            "trajectory_memory_context": traj_ctx,
            "rubric_pass": skill_loaded,
        }

    if operation == "unknown":
        return {
            "status": "skipped",
            "skill_loaded": skill_loaded,
            "query": query,
            "skill": skill,
            "operation": operation,
            "trajectory_count": len(prior),
            "trajectory_memory_context": traj_ctx,
            "message": f"rollout pilot does not support skill {skill}",
        }

    wrapper = _find_harness_wrapper(root, skill)
    if wrapper is None:
        return {
            "status": "failed",
            "skill_loaded": skill_loaded,
            "query": query,
            "skill": skill,
            "operation": operation,
            "trajectory_count": len(prior),
            "trajectory_memory_context": traj_ctx,
            "message": f"harness wrapper not found: {root / skill / 'scripts' / _WRAPPER_GLOB}",
        }

    if is_mutating:
        allow = allow_mutating
        if allow is None:
            allow = os.environ.get("SKILL_EVOLUTION_ALLOW_MUTATING", "").lower() in {"1", "true", "yes"}
        if not allow:
            return {
                "status": "failed",
                "skill_loaded": skill_loaded,
                "query": query,
                "skill": skill,
                "operation": operation,
                "wrapper_path": str(wrapper),
                "trajectory_count": len(prior),
                "trajectory_memory_context": traj_ctx,
                "message": (
                    "mutating operation blocked — set SKILL_EVOLUTION_ALLOW_MUTATING=1 "
                    f"to run {operation}"
                ),
            }

    harness = _run_harness(wrapper, root, skill, operation, argv)
    rubric_pass = _rubric_pass_for_operation(operation, harness)
    ok = rubric_pass and harness["exit_code"] == 0
    err_msg = harness["stderr"] if not ok else ""
    return _sanitize_rollout_record(
        {
            "status": "ok" if ok else "failed",
            "skill_loaded": skill_loaded,
            "query": query,
            "skill": skill,
            "operation": operation,
            "wrapper_argv": argv,
            "is_mutating": is_mutating,
            "wrapper_path": str(wrapper),
            "exit_code": harness["exit_code"],
            "rubric_pass": rubric_pass,
            "stdout_preview": (harness["stdout"] or "")[:500],
            "stderr_preview": (harness["stderr"] or "")[:300],
            "trajectory_count": len(prior),
            "trajectory_memory_context": traj_ctx,
            "message": err_msg,
        }
    )


def _item_id(item: dict[str, Any], index: int) -> str:
    if item.get("id"):
        return str(item["id"])
    query = str(item.get("question") or item.get("query") or "")
    return f"{item.get('expected_skill', 'skill')}-{index}-{hash(query) & 0xFFFF:04x}"


def process_one(
    item: dict[str, Any],
    skill_content: str,
    out_root: str | Path,
    *,
    index: int = 0,
    mock: bool | None = None,
    skills_root: str | Path | None = None,
    trajectories: list[dict[str, Any]] | None = None,
    trajectories_path: str | Path | None = None,
) -> dict[str, Any]:
    from scorer import score_rollout

    query = str(item.get("question") or item.get("query") or "")
    skill = str(item.get("expected_skill") or "alicloud-ecs-ops")
    rollout = run_rollout(
        query,
        skill_content,
        skill=skill,
        mock=mock,
        skills_root=skills_root,
        trajectories=trajectories,
        trajectories_path=trajectories_path,
    )
    soft = score_rollout(rollout, expected_skill=skill)
    hard = 1 if soft >= 0.8 or rollout.get("rubric_pass") else 0
    item_id = _item_id(item, index)
    pred_dir = Path(out_root) / "predictions" / item_id
    pred_dir.mkdir(parents=True, exist_ok=True)
    safe_rollout = _sanitize_rollout_record(rollout)
    (pred_dir / "rollout.json").write_text(json.dumps(safe_rollout, ensure_ascii=False, indent=2), encoding="utf-8")
    conversation = [
        {"role": "user", "content": query},
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "operation": rollout.get("operation"),
                    "status": rollout.get("status"),
                    "rubric_pass": rollout.get("rubric_pass"),
                    "trajectory_memory_context": rollout.get("trajectory_memory_context", ""),
                },
                ensure_ascii=False,
            ),
        },
    ]
    if rollout.get("message"):
        conversation.append({"role": "system", "content": str(rollout["message"])})
    (pred_dir / "conversation.json").write_text(json.dumps(conversation, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "id": item_id,
        "hard": hard,
        "soft": soft,
        "query": query,
        "question": query,
        "expected_skill": skill,
        "task_type": str(item.get("task_type") or "alicloud_ops"),
        "operation": rollout.get("operation"),
        "status": rollout.get("status"),
        "rubric_pass": rollout.get("rubric_pass"),
        "trajectory_memory_context": rollout.get("trajectory_memory_context", ""),
        "fail_reason": rollout.get("message") or ("" if hard else f"soft={soft:.2f}"),
    }


def run_batch(
    items: list[dict],
    skill_content: str,
    out_root: str,
    *,
    mock: bool | None = None,
    skills_root: str | Path | None = None,
    trajectories_path: str | Path | None = None,
) -> list[dict]:
    """SkillOpt-compatible batch rollout (sequential)."""
    root = resolve_skills_root(skills_root)
    if not items:
        os.makedirs(out_root, exist_ok=True)
        Path(out_root, "rollouts.json").write_text("[]", encoding="utf-8")
        return []
    traj_path = trajectories_path or resolve_trajectories_path(None, root, str(items[0].get("expected_skill") or "alicloud-ecs-ops"))
    trajectories = load_trajectories(Path(traj_path))
    os.makedirs(out_root, exist_ok=True)
    results = [
        process_one(
            item,
            skill_content,
            out_root,
            index=idx,
            mock=mock,
            skills_root=root,
            trajectories=trajectories,
            trajectories_path=traj_path,
        )
        for idx, item in enumerate(items)
    ]
    Path(out_root, "rollouts.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
