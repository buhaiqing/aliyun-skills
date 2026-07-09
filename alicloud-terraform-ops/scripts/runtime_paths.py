#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""alicloud-terraform-ops 运行时路径 — 统一写入 ${SKILLS_DIR}/.runtime/terraform-ops/。

Committed templates: alicloud-terraform-ops/environments/ (in Git).
All generated HCL / local workspaces: .runtime/terraform-ops/ (gitignored).

Layout (≤2 levels under skill runtime root):
  .runtime/terraform-ops/
    nl2hcl/<env>/          NL2HCL 生成物（main.tf + modules/）
    import/<batch>/        逆向工程 HCL + import.sh
    environments/<env>/    apply/destroy 工作区（从 templates seed）
    pr-store/              HITL Mode B
  .runtime/audit/terraform-ops/   执行轨迹
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_KEY = "terraform-ops"


def get_skills_dir() -> Path:
    env = os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return SKILL_DIR.parent


def get_global_runtime_root() -> Path:
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return get_skills_dir() / ".runtime"


def get_skill_runtime_root() -> Path:
    return get_global_runtime_root() / SKILL_KEY


def audit_dir() -> Path:
    return get_global_runtime_root() / "audit" / SKILL_KEY


def template_env_root() -> Path:
    return SKILL_DIR / "environments"


def pr_store_dir() -> Path:
    return get_skill_runtime_root() / "pr-store"


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sanitize_slug(value: str, fallback: str = "run") -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return slug[:48] or fallback


def nl2hcl_output_dir(environment: str = "dev", run: str | None = None) -> Path:
    """NL2HCL 输出：.runtime/terraform-ops/nl2hcl/<env>/[run]。"""
    base = get_skill_runtime_root() / "nl2hcl" / _sanitize_slug(environment, "dev")
    return base / _sanitize_slug(run, new_run_id()) if run else base


def import_output_dir(batch: str | None = None) -> Path:
    """逆向工程输出：.runtime/terraform-ops/import/<batch>/。"""
    name = _sanitize_slug(batch, "default") if batch else "default"
    return get_skill_runtime_root() / "import" / name


def env_runtime_dir(environment: str) -> Path:
    """apply/destroy 工作区：.runtime/terraform-ops/environments/<env>/。"""
    return get_skill_runtime_root() / "environments" / _sanitize_slug(environment, "dev")


def resolve_output_dir(
    explicit: Path | str | None,
    *,
    kind: str,
    environment: str = "dev",
    batch: str | None = None,
) -> Path:
    """解析 CLI --output-dir；未指定时使用 .runtime 默认路径。"""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    if kind == "nl2hcl":
        return nl2hcl_output_dir(environment)
    if kind == "import":
        return import_output_dir(batch)
    if kind == "env":
        return env_runtime_dir(environment)
    raise ValueError(f"unknown kind: {kind}")


# Backward-compatible aliases
def default_nl2hcl_output(environment: str = "dev") -> Path:
    return nl2hcl_output_dir(environment)


def default_import_output(batch: str | None = None) -> Path:
    return import_output_dir(batch)


def default_env_runtime(environment: str) -> Path:
    return env_runtime_dir(environment)


def legacy_runtime_dirs() -> list[Path]:
    return [
        SKILL_DIR / "generated",
        SKILL_DIR / "output",
        get_skill_runtime_root() / "generated",  # old layout
    ]


def ensure_skill_runtime_dirs() -> None:
    root = get_skill_runtime_root()
    for path in (
        root / "nl2hcl",
        root / "import",
        root / "environments",
        pr_store_dir(),
        audit_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)


def runtime_layout_doc() -> str:
    root = get_skill_runtime_root()
    return (
        f"Skill runtime: {root}\n"
        f"  nl2hcl/<env>/       NL2HCL HCL + modules/\n"
        f"  import/<batch>/    reverse-engineering HCL + import.sh\n"
        f"  environments/<env>/ apply/destroy workspaces\n"
        f"  pr-store/          HITL Mode B\n"
        f"Audit traces: {audit_dir()}\n"
        f"Templates (Git): {template_env_root()}/\n"
        f"Cleanup: make runtime-clean  (repo root Makefile)\n"
    )
