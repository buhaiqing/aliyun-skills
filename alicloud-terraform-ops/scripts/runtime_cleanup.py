#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""集中清理 alicloud-terraform-ops 运行时产物（默认 dry-run）。"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from runtime_paths import (
    audit_dir,
    get_skill_runtime_root,
    legacy_runtime_dirs,
    runtime_layout_doc,
)


@dataclass
class CleanupItem:
    path: Path
    reason: str
    size_bytes: int = 0


@dataclass
class CleanupReport:
    items: List[CleanupItem] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(i.size_bytes for i in self.items)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def collect_targets(*, include_legacy: bool) -> List[CleanupItem]:
    root = get_skill_runtime_root()
    targets = [
        CleanupItem(root / "nl2hcl", "NL2HCL 生成物"),
        CleanupItem(root / "import", "逆向工程 HCL + import.sh"),
        CleanupItem(root / "environments", "apply/destroy 工作区"),
        CleanupItem(root / "pr-store", "HITL Mode B 本地 PR"),
        CleanupItem(audit_dir(), "执行轨迹 / dry-run trace"),
    ]
    if include_legacy:
        for legacy in legacy_runtime_dirs():
            targets.append(CleanupItem(legacy, "迁移前 skill 内遗留目录"))
    for item in targets:
        item.size_bytes = _dir_size(item.path)
    return [t for t in targets if t.path.exists()]


def run_cleanup(*, apply: bool, include_legacy: bool) -> CleanupReport:
    report = CleanupReport()
    for item in collect_targets(include_legacy=include_legacy):
        if apply:
            if item.path.is_dir():
                shutil.rmtree(item.path, ignore_errors=True)
            elif item.path.is_file():
                item.path.unlink(missing_ok=True)
        else:
            report.items.append(item)
    if not apply:
        return report

    # post-apply: recreate empty skill runtime root skeleton
    get_skill_runtime_root().mkdir(parents=True, exist_ok=True)
    return report


def _format_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="清理 alicloud-terraform-ops 运行时目录（默认 dry-run）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际删除（默认仅预览）",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="同时清理 skill 内遗留的 generated/、output/",
    )
    parser.add_argument(
        "--show-layout",
        action="store_true",
        help="打印运行时目录布局",
    )
    args = parser.parse_args(argv)

    if args.show_layout:
        print(runtime_layout_doc())
        return 0

    report = run_cleanup(apply=args.apply, include_legacy=args.legacy)
    if args.apply:
        print("已清理 alicloud-terraform-ops 运行时目录。")
        print(runtime_layout_doc())
        return 0

    if not report.items:
        print("未发现可清理的运行时目录。")
        print(runtime_layout_doc())
        return 0

    print("以下路径将被清理（dry-run，添加 --apply 执行）：")
    for item in report.items:
        print(f"  - {item.path}  ({_format_bytes(item.size_bytes)})  # {item.reason}")
    print(f"合计约 {_format_bytes(report.total_bytes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
