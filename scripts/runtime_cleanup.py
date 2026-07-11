#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repo-wide runtime cleanup for aliyun-skills (all skills).

Default: dry-run. Use --apply to delete.

Targets:
  - ${SKILLS_DIR}/.runtime/          (unified runtime root)
  - Legacy per-skill paths (generated/, output/, audit-results/, ...)
  - Repo-root audit-results/, infra-baseline/
  - Nested **/.pr-store/ under repo (not home dir)

Age-based retention for .runtime/ baseline|audit|logs|traces|cache delegates to
alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py when --retain is set.
"""

from __future__ import annotations

import argparse
import json
import os
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


# ---------------------------------------------------------------------------
# Selective fixture purge: remove test-fixture entries from .runtime/memory/
# ---------------------------------------------------------------------------
# Rationale: gcl_runner_test.CriticModeEnvTests previously leaked fixture
# traces into .runtime/memory/<skill>/aliyun.jsonl because the test ran
# gcl_runner.main() without isolating memory_root. The _GCLRunnerMemoryIsolated
# mixin now prevents this in-process, but defense-in-depth cleanup is needed
# to remove any historical residue and any future leak that bypasses the mixin
# (e.g. a test runner run without setUp ordering, or an out-of-tree caller).
#
# Identification rule: a JSONL entry is a test fixture iff its trace_path
# starts with `/var/folders/` (macOS system tmpdir, where tempfile.mkdtemp()
# creates per-test scratch dirs). Real GCL runs persist traces to the
# user-supplied --output-dir (e.g. .runtime/audit/gcl-runner-ops/) and
# wrapper-lite entries have no trace_path at all. Zero overlap.
#
# Side effect: empty JSONL files are unlinked so the directory tree stays clean.
# ---------------------------------------------------------------------------
_FIXTURE_TRACE_PATH_PREFIX = "/var/folders/"


@dataclass
class MemoryPurgeReport:
    files_scanned: int = 0
    entries_removed: int = 0
    files_unlinked: int = 0
    bytes_reclaimed: int = 0


def _is_fixture_entry(entry: dict) -> bool:
    """Return True if a memory JSONL entry looks like a test fixture.

    Heuristic: the trace_path (when present) points at macOS system tmpdir,
    which only tempfile.mkdtemp()-based test fixtures can produce.
    """
    trace_path = entry.get("trace_path")
    if not isinstance(trace_path, str):
        return False
    return trace_path.startswith(_FIXTURE_TRACE_PATH_PREFIX)


def purge_memory_fixtures(*, skills_dir: Path, apply: bool) -> MemoryPurgeReport:
    """Remove test-fixture entries from .runtime/memory/ without touching
    real wrapper-lite or GCL traces.

    Args:
        skills_dir: repo root.
        apply: if False, scan and report only; if True, rewrite files.

    Returns:
        MemoryPurgeReport with counts.
    """
    report = MemoryPurgeReport()
    memory_root = skills_dir / ".runtime" / "memory"
    if not memory_root.is_dir():
        return report

    for jsonl in sorted(memory_root.rglob("*.jsonl")):
        report.files_scanned += 1
        try:
            text = jsonl.read_text(encoding="utf-8")
        except OSError:
            continue

        kept_lines: List[str] = []
        removed_here = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                # Preserve unparseable lines — never lose data silently
                kept_lines.append(line)
                continue
            if _is_fixture_entry(entry):
                removed_here += 1
            else:
                kept_lines.append(line)

        if removed_here == 0:
            continue

        report.entries_removed += removed_here

        if apply:
            if kept_lines:
                new_text = "\n".join(kept_lines) + "\n"
                report.bytes_reclaimed += len(text) - len(new_text)
                jsonl.write_text(new_text, encoding="utf-8")
            else:
                # All entries were fixtures — unlink the empty file
                report.bytes_reclaimed += jsonl.stat().st_size
                jsonl.unlink()
                report.files_unlinked += 1
        else:
            # Dry-run: estimate bytes (best-effort, single-line entries)
            report.bytes_reclaimed += removed_here * 200  # ~200 bytes/entry

    return report


def run_trace_layer_maintain(skills_dir: Path, apply: bool) -> int:
    """TTL cleanup for SkillOpt local trace JSON + session index files."""
    aiops_script = skills_dir / "alicloud-aiops-cruise" / "scripts" / "lib" / "runtime_cleanup.py"
    if not aiops_script.is_file():
        print(f"[WARN] trace cleanup unavailable: {aiops_script} not found", file=sys.stderr)
        return 0
    keep_days = int(os.environ.get("TRACE_KEEP_DAYS", "7"))
    cmd = [
        sys.executable,
        str(aiops_script),
        "--traces-only",
        "--traces-keep-days",
        str(keep_days),
    ]
    if apply:
        cmd.append("--apply")
    env = os.environ.copy()
    env["SKILLS_DIR"] = str(skills_dir)
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def run_memory_layer_maintain(skills_dir: Path, apply: bool) -> int:
    """Run Layer 1 TTL + Layer 2 reflexion + local trace TTL (lightweight, non-fatal)."""
    keep_days = int(os.environ.get("MEMORY_KEEP_DAYS", "30"))
    decay_days = int(os.environ.get("REFLEXION_DECAY_DAYS", "90"))
    gcl_scripts = skills_dir / "alicloud-gcl-runner-ops" / "scripts"
    rc = 0

    memory_py = gcl_scripts / "gcl_memory.py"
    if memory_py.is_file():
        cmd = [
            sys.executable,
            str(memory_py),
            "maintain",
            "--keep-days",
            str(keep_days),
            "--memory-root",
            str(skills_dir / ".runtime" / "memory"),
        ]
        if apply:
            cmd.append("--apply")
        proc = subprocess.run(cmd)
        rc = max(rc, proc.returncode)

    reflexion_py = gcl_scripts / "gcl_reflexion.py"
    if reflexion_py.is_file():
        cmd = [
            sys.executable,
            str(reflexion_py),
            "maintain",
            "--decay-days",
            str(decay_days),
            "--success-decay-days",
            str(decay_days),
            "--reflexion-root",
            str(skills_dir / ".runtime" / "reflexion"),
        ]
        if apply:
            cmd.append("--apply")
        proc = subprocess.run(cmd)
        rc = max(rc, proc.returncode)

        promote_cmd = [
            sys.executable,
            str(reflexion_py),
            "promote-from-memory",
            "--memory-root",
            str(skills_dir / ".runtime" / "memory"),
            "--reflexion-root",
            str(skills_dir / ".runtime" / "reflexion"),
        ]
        if apply:
            promote_cmd.append("--apply")
        proc = subprocess.run(promote_cmd)
        rc = max(rc, proc.returncode)

        if apply and _env_truthy("GCL_REFLEXION_REPORT_ON_MAINTAIN"):
            sort_by = os.environ.get("GCL_REFLEXION_REPORT_SORT_BY", "weighted")
            if sort_by not in ("weighted", "count"):
                sort_by = "weighted"
            report_cmd = [
                sys.executable,
                str(reflexion_py),
                "report",
                "--reflexion-root",
                str(skills_dir / ".runtime" / "reflexion"),
                "--sort-by",
                sort_by,
            ]
            proc = subprocess.run(report_cmd, cwd=str(skills_dir))
            rc = max(rc, proc.returncode)
            success_report_cmd = [
                sys.executable,
                str(reflexion_py),
                "success-report",
                "--reflexion-root",
                str(skills_dir / ".runtime" / "reflexion"),
                "--sort-by",
                sort_by,
            ]
            proc = subprocess.run(success_report_cmd, cwd=str(skills_dir))
            rc = max(rc, proc.returncode)
            agg_cmd = [
                sys.executable,
                str(reflexion_py),
                "aggregate-generalized",
                "--reflexion-root",
                str(skills_dir / ".runtime" / "reflexion"),
                "--apply",
            ]
            proc = subprocess.run(agg_cmd, cwd=str(skills_dir))
            rc = max(rc, proc.returncode)

    rc = max(rc, run_trace_layer_maintain(skills_dir, apply))
    rc = max(rc, run_token_layer_maintain(skills_dir, apply))

    return rc


def run_token_layer_maintain(skills_dir: Path, apply: bool) -> int:
    """Prune .runtime/token/history and reports older than TOKEN_HISTORY_KEEP_DAYS."""
    token_py = skills_dir / "scripts" / "token_rollup.py"
    if not token_py.is_file():
        return 0
    keep_days = int(os.environ.get("TOKEN_HISTORY_KEEP_DAYS", "30"))
    cmd = [
        sys.executable,
        str(token_py),
        "maintain",
        "--repo-root",
        str(skills_dir),
        "--history-keep-days",
        str(keep_days),
    ]
    if apply:
        cmd.append("--apply")
    proc = subprocess.run(cmd)
    return proc.returncode


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
    parser.add_argument(
        "--purge-memory-fixtures",
        action="store_true",
        help="remove test-fixture entries from .runtime/memory/ (identified by "
        "trace_path starting with /var/folders/). Preserves real wrapper-lite "
        "and GCL trace entries. Use with --apply to actually delete.",
    )
    parser.add_argument(
        "--maintain-memory",
        action="store_true",
        help="run Layer 1 memory_maintain + Layer 2 reflexion_maintain + promote-from-memory "
        "+ local trace TTL (optional report: GCL_REFLEXION_REPORT_ON_MAINTAIN=true with --apply)",
    )
    args = parser.parse_args(argv)

    skills_dir = get_skills_dir()

    if args.maintain_memory:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"=== memory layer maintain ({mode}) ===")
        print(f"SKILLS_DIR: {skills_dir}\n")
        return run_memory_layer_maintain(skills_dir, apply=args.apply)

    if args.show_layout:
        tf_paths = skills_dir / "alicloud-terraform-ops" / "scripts" / "runtime_paths.py"
        if tf_paths.is_file():
            sys.path.insert(0, str(tf_paths.parent))
            from runtime_paths import runtime_layout_doc

            print(runtime_layout_doc())
        else:
            print(f".runtime/ root: {skills_dir / '.runtime'}")
        return 0

    if args.purge_memory_fixtures:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"=== memory fixture purge ({mode}) ===")
        print(f"SKILLS_DIR: {skills_dir}")
        print(f"Identifier: trace_path starts with '{_FIXTURE_TRACE_PATH_PREFIX}'")
        print()
        report = purge_memory_fixtures(skills_dir=skills_dir, apply=args.apply)
        if args.apply:
            print(
                f"Done. files_scanned={report.files_scanned} "
                f"entries_removed={report.entries_removed} "
                f"files_unlinked={report.files_unlinked} "
                f"bytes_reclaimed={report.bytes_reclaimed}"
            )
        elif report.entries_removed == 0:
            print("No fixture entries found.")
        else:
            print(
                f"Would remove {report.entries_removed} fixture entries across "
                f"{report.files_scanned} files (~{_format_bytes(report.bytes_reclaimed)}). "
                f"Re-run with --apply to execute."
            )
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
    else:
        # Lightweight Layer 1/2 maintenance (default 30d / 90d decay)
        run_memory_layer_maintain(skills_dir, apply=args.apply)

    return 0


if __name__ == "__main__":
    sys.exit(main())
