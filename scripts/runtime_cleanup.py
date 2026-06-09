#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repo-wide runtime cleanup for aliyun-skills (all skills).

Default: dry-run. Use --apply to delete.

Targets:
  - ${SKILLS_DIR}/.runtime/          (unified runtime root)
  - Legacy per-skill paths (generated/, output/, audit-results/, ...)
  - Repo-root audit-results/, infra-baseline/
  - Nested **/.pr-store/ under repo (not home dir)

Age-based retention for .runtime/ baseline|audit|logs|cache delegates to
alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py when --retain is set.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SKILLS_DIR = SCRIPT_DIR.parent


@dataclass
class CleanupTarget:
    path: Path
    reason: str
    size_bytes: int = 0


@dataclass
class CleanupReport:
    targets: List[CleanupTarget] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(t.size_bytes for t in self.targets)


def get_skills_dir() -> Path:
    import os

    env = os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_SKILLS_DIR


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def _collect_legacy_skill_paths(skills_dir: Path) -> List[CleanupTarget]:
    targets: List[CleanupTarget] = []
    for skill_dir in sorted(skills_dir.glob("alicloud-*")):
        if not skill_dir.is_dir():
            continue
        for name, reason in (
            ("generated", "legacy NL2HCL/import output"),
            ("output", "legacy runtime workspace"),
            ("audit-results", "legacy audit traces"),
        ):
            path = skill_dir / name
            if path.exists():
                targets.append(CleanupTarget(path, f"{skill_dir.name}: {reason}"))
        for path in skill_dir.rglob(".pr-store"):
            if path.is_dir():
                targets.append(CleanupTarget(path, f"{skill_dir.name}: HITL Mode B pr-store"))
    return targets


def _collect_repo_legacy(skills_dir: Path) -> List[CleanupTarget]:
    targets: List[CleanupTarget] = []
    for rel, reason in (
        ("audit-results", "repo legacy GCL traces"),
        ("infra-baseline", "repo legacy baselines"),
        ("config", "repo local NL2HCL configs"),
    ):
        path = skills_dir / rel
        if path.exists():
            targets.append(CleanupTarget(path, reason))
    return targets


def collect_full_wipe_targets(skills_dir: Path) -> List[CleanupTarget]:
    targets: List[CleanupTarget] = []
    runtime_root = skills_dir / ".runtime"
    if runtime_root.exists():
        targets.append(CleanupTarget(runtime_root, "unified .runtime/ tree"))
    targets.extend(_collect_repo_legacy(skills_dir))
    targets.extend(_collect_legacy_skill_paths(skills_dir))
    for item in targets:
        item.size_bytes = _dir_size(item.path)
    return [t for t in targets if t.path.exists()]


def run_full_wipe(*, skills_dir: Path, apply: bool) -> CleanupReport:
    report = CleanupReport()
    for item in collect_full_wipe_targets(skills_dir):
        if apply:
            if item.path.is_dir():
                shutil.rmtree(item.path, ignore_errors=True)
            else:
                item.path.unlink(missing_ok=True)
        else:
            report.targets.append(item)
    return report


def run_retention_cleanup(skills_dir: Path, apply: bool, argv: List[str]) -> int:
    aiops_script = skills_dir / "alicloud-aiops-cruise" / "scripts" / "lib" / "runtime_cleanup.py"
    if not aiops_script.is_file():
        print(f"[WARN] retention cleanup unavailable: {aiops_script} not found", file=sys.stderr)
        return 0
    cmd = [sys.executable, str(aiops_script)] + argv
    import os

    env = os.environ.copy()
    env["SKILLS_DIR"] = str(skills_dir)
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def _format_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="aliyun-skills repo-wide runtime cleanup")
    parser.add_argument("--apply", action="store_true", help="actually delete (default dry-run)")
    parser.add_argument(
        "--retain",
        action="store_true",
        help="after wipe, run age-based .runtime/ retention (aiops-cruise script)",
    )
    parser.add_argument("--show-layout", action="store_true", help="show terraform-ops layout")
    args = parser.parse_args(argv)

    skills_dir = get_skills_dir()

    if args.show_layout:
        tf_paths = skills_dir / "alicloud-terraform-ops" / "scripts" / "runtime_paths.py"
        if tf_paths.is_file():
            sys.path.insert(0, str(tf_paths.parent))
            from runtime_paths import runtime_layout_doc

            print(runtime_layout_doc())
        else:
            print(f".runtime/ root: {skills_dir / '.runtime'}")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== aliyun-skills runtime cleanup ({mode}) ===")
    print(f"SKILLS_DIR: {skills_dir}\n")

    report = run_full_wipe(skills_dir=skills_dir, apply=args.apply)
    if args.apply:
        print("Full wipe completed.")
    elif not report.targets:
        print("No runtime directories found to clean.")
    else:
        print("Paths to remove (use --apply to execute):")
        for item in report.targets:
            print(f"  - {item.path}  ({_format_bytes(item.size_bytes)})  # {item.reason}")
        print(f"\nTotal: ~{_format_bytes(report.total_bytes)}")

    if args.retain:
        retain_argv = ["--apply"] if args.apply else []
        rc = run_retention_cleanup(skills_dir, args.apply, retain_argv)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
