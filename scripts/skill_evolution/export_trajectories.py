#!/usr/bin/env python3
"""Export Layer 1 memory JSONL to sanitized SkillOpt trajectory records (Milestone A)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_MEMORY_ROOT = Path(".runtime") / "memory"

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(ALIBABA_CLOUD_ACCESS_KEY_SECRET|AccessKeySecret|SecretKey)\s*[=:]\s*\S+", re.I), r"\1=****"),
    (re.compile(r"\bLTAI[A-Za-z0-9]{12,}\b"), "LTAI****"),
    (re.compile(r"\bsk-lf-[A-Za-z0-9_-]+\b"), "sk-lf-****"),
    (re.compile(r"\bpk-lf-[A-Za-z0-9_-]+\b"), "pk-lf-****"),
]


def resolve_skills_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ALIYUN_SKILLS_ROOT") or os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def resolve_memory_root(memory_root: str | Path | None, skills_root: Path) -> Path:
    if memory_root is not None and str(memory_root) != "None":
        p = Path(memory_root)
        return p if p.is_absolute() else (skills_root / p)
    env = os.environ.get("GCL_MEMORY_ROOT")
    if env and env != "None":
        p = Path(env)
        return p if p.is_absolute() else (skills_root / p)
    return skills_root / DEFAULT_MEMORY_ROOT


def sanitize_command(command: str) -> str:
    out = command or ""
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def _infer_source(entry: dict[str, Any]) -> str:
    if entry.get("source") == "skillopt-wrapper":
        return "skillopt-wrapper"
    if entry.get("source") == "gcl-runner":
        return "gcl-runner"
    if entry.get("gcl_status") == "LIGHTWEIGHT":
        return "skillopt-wrapper"
    return "gcl-runner"


def to_trajectory_record(entry: dict[str, Any]) -> dict[str, Any]:
    fp = entry.get("failure_pattern")
    failure_pattern = None
    if isinstance(fp, dict):
        failure_pattern = {
            "category": fp.get("category"),
            "fix": fp.get("fix", ""),
        }
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "skill": entry.get("skill", "unknown"),
        "operation": entry.get("operation", "unknown"),
        "timestamp": entry.get("timestamp", ""),
        "source": _infer_source(entry),
        "gcl_status": entry.get("gcl_status", "UNKNOWN"),
        "rubric_pass": bool(entry.get("rubric_pass", False)),
        "scores": dict(entry.get("scores") or {}),
        "command": sanitize_command(str(entry.get("command", ""))),
        "duration_ms": int(entry.get("duration_ms") or 0),
        "failure_pattern": failure_pattern,
    }
    error_code = entry.get("error_code")
    if error_code:
        record["error_code"] = str(error_code)
    trace_path = entry.get("trace_path")
    if trace_path:
        record["trace_path"] = str(trace_path)
    return record


def load_memory_entries_from_file(jsonl_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    return entries


def export_from_memory_dir(
    memory_dir: Path,
    skill: str,
) -> list[dict[str, Any]]:
    """Read all JSONL under memory_dir/skill/ and return trajectory records."""
    skill_dir = memory_dir / skill
    if not skill_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for jsonl_file in sorted(skill_dir.glob("*.jsonl")):
        for entry in load_memory_entries_from_file(jsonl_file):
            if entry.get("skill") != skill:
                continue
            records.append(to_trajectory_record(entry))
    records.sort(key=lambda r: r.get("timestamp", ""))
    return records


def write_trajectories(records: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export Layer 1 memory to SkillOpt trajectories JSONL")
    p.add_argument("--skill", required=True, help="e.g. alicloud-ecs-ops")
    p.add_argument("--skills-root", default=None, help="Repo root (default: ALIYUN_SKILLS_ROOT)")
    p.add_argument("--memory-root", default=None, help="Override .runtime/memory root")
    p.add_argument("--out", default=None, help="Output JSONL path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    skills_root = resolve_skills_root(args.skills_root)
    memory_root = resolve_memory_root(args.memory_root, skills_root)
    out = (
        Path(args.out)
        if args.out
        else skills_root / ".runtime" / "skill-evolution" / args.skill / "trajectories.jsonl"
    )
    records = export_from_memory_dir(memory_root, args.skill)
    write_trajectories(records, out)
    print(f"[SUMMARY] skill={args.skill} trajectories={len(records)} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
