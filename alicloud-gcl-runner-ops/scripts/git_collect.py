#!/usr/bin/env python3
"""
git_collect.py — Layer 3 artifact-evolution signals from Git history.

Scans recent commits touching alicloud-*-ops skills and classifies bugfixes,
tests, runbook, skillopt, reflexion, and governance changes.

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent

GIT_FIELD_SEP = "\x1f"
"""Field separator for git log pretty-format (must not appear in commit metadata)."""

BUGFIX_RE = re.compile(r"\b(fix|bug|repair|hotfix|patch)\b", re.I)
SKILL_DIR_RE = re.compile(r"^(alicloud-[a-z0-9-]+-ops)/")
THEME_KEYWORDS: dict[str, re.Pattern[str]] = {
    "cli_parameter": re.compile(r"cli|parameter|InvalidParameter|RepeatList", re.I),
    "skillopt": re.compile(r"skillopt|wrapper", re.I),
    "rubric": re.compile(r"rubric|gcl|critic", re.I),
    "test": re.compile(r"test|unittest", re.I),
    "reflexion": re.compile(r"reflexion|failure-pattern", re.I),
}


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [STRATEGY] {msg}", file=sys.stderr)


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _infer_skills(files: list[str]) -> list[str]:
    skills: set[str] = set()
    for f in files:
        m = SKILL_DIR_RE.match(f.replace("\\", "/"))
        if m:
            skills.add(m.group(1))
    return sorted(skills)


def _infer_themes(subject: str, files: list[str]) -> list[str]:
    blob = subject + " " + " ".join(files)
    themes = [name for name, pat in THEME_KEYWORDS.items() if pat.search(blob)]
    return themes or ["general"]


def _parse_log_line(line: str) -> tuple[str, str, str, str, str] | None:
    """Parse one git log line using GIT_FIELD_SEP delimiter."""
    parts = line.split(GIT_FIELD_SEP, 4)
    if len(parts) < 5:
        return None
    return parts[0], parts[1], parts[2], parts[3], parts[4]


def _classify_commit(subject: str, files: list[str]) -> list[str]:
    categories: list[str] = []
    if BUGFIX_RE.search(subject):
        categories.append("bugfix")
    joined = " ".join(files).lower()
    if "test" in joined or subject.lower().startswith("test"):
        categories.append("test")
    if any(f.endswith("SKILL.md") or "/references/" in f for f in files):
        categories.append("runbook")
    if any("skillopt" in f for f in files):
        categories.append("skillopt")
    if any("failure-patterns" in f or "gcl_reflexion" in f for f in files):
        categories.append("reflexion")
    if any("rubric.md" in f or "prompt-templates.md" in f for f in files):
        categories.append("governance")
    if not categories:
        categories.append("other")
    return categories


def _parse_commit_header(line: str) -> tuple[str, str, str, str, str] | None:
    """Parse a git log header line: COMMIT:%H\\x1f%s\\x1f%an\\x1f%ae\\x1f%ad."""
    if not line.startswith("COMMIT:"):
        return None
    return _parse_log_line(line[len("COMMIT:") :])


def _diff_stat(sha: str, repo_root: Path) -> str:
    try:
        out = _run_git(["show", "--format=", "--stat", "--oneline", sha], cwd=repo_root)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        return lines[-1] if lines else ""
    except RuntimeError:
        return ""


def collect_git_signals(
    since_days: int = 7,
    repo_root: Path | None = None,
    pathspecs: list[str] | None = None,
) -> dict[str, Any]:
    """Collect Git signals for the last *since_days* days."""
    root = repo_root or Path.cwd()
    specs = pathspecs or [
        "alicloud-*-ops/",
        "docs/failure-patterns.md",
        "docs/gcl-spec.md",
        "AGENTS.md",
    ]
    since = f"{since_days} days ago"
    sep = GIT_FIELD_SEP
    log_format = f"COMMIT:%H{sep}%s{sep}%an{sep}%ae{sep}%ad"
    try:
        raw = _run_git(
            [
                "log",
                f"--since={since}",
                f"--pretty=format:{log_format}",
                "--name-only",
                "--date=iso-strict",
                "--",
                *specs,
            ],
            cwd=root,
        )
    except RuntimeError as exc:
        _log(f"event=git_collect result=failed reason={exc}")
        return {
            "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "since_days": since_days,
            "commit_count": 0,
            "bugfix_commits": [],
            "hot_skills": [],
            "error": str(exc),
        }

    bugfix_commits: list[dict[str, Any]] = []
    skill_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"commit_count": 0, "bugfix_count": 0})

    parsed_commits: list[tuple[str, str, str, str, str, list[str]]] = []
    pending_meta: tuple[str, str, str, str, str] | None = None
    pending_files: list[str] = []

    def _flush_pending() -> None:
        nonlocal pending_meta, pending_files
        if pending_meta is None:
            return
        parsed_commits.append((*pending_meta, list(pending_files)))
        pending_meta = None
        pending_files = []

    for line in raw.splitlines():
        header = _parse_commit_header(line)
        if header is not None:
            _flush_pending()
            pending_meta = header
            continue
        if line.strip() and pending_meta is not None:
            pending_files.append(line.strip())
    _flush_pending()

    for sha, subject, author, _email, _date, files in parsed_commits:
        categories = _classify_commit(subject, files)
        skills = _infer_skills(files)
        themes = _infer_themes(subject, files)
        for sk in skills:
            skill_counts[sk]["commit_count"] += 1
            if "bugfix" in categories:
                skill_counts[sk]["bugfix_count"] += 1

        entry = {
            "sha": sha[:12],
            "subject": subject,
            "author": author,
            "files": files[:20],
            "diff_stat": _diff_stat(sha, root),
            "categories": categories,
            "inferred_skills": skills,
            "inferred_themes": themes,
        }
        if "bugfix" in categories:
            bugfix_commits.append(entry)

    hot_skills = sorted(
        (
            {"skill": sk, **counts}
            for sk, counts in skill_counts.items()
        ),
        key=lambda x: (x["bugfix_count"], x["commit_count"]),
        reverse=True,
    )

    return {
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "since_days": since_days,
        "commit_count": len(parsed_commits),
        "bugfix_commits": bugfix_commits,
        "hot_skills": hot_skills,
    }


def _load_reflexion_cleanup_preview(reflexion_root: Path) -> dict[str, Any]:
    """Dry-run preview of reflexion patterns that would be pruned.

    ponytail: delegates to reflexion_maintain(apply=False) — single source of truth.
    """
    from gcl_reflexion import reflexion_maintain
    try:
        result = reflexion_maintain(root=reflexion_root, apply=False, decay_days=90)
    except Exception as exc:
        return {"reflexion_root": str(reflexion_root), "load_error": str(exc)}
    return {
        "reflexion_root": str(reflexion_root),
        "store_present": result.get("total_before", 0) > 0 or result.get("pruned_by_count", 0) > 0,
        "min_count": result.get("min_count", 3),
        "decay_days": result.get("decay_days", 90),
        "total_before": result.get("total_before", 0),
        "total_after": result.get("total_after", 0),
        "pruned_by_count": result.get("pruned_by_count", 0),
        "pruned_by_decay": result.get("pruned_by_decay", 0),
        "categories": result.get("categories", {}),
    }


def _print_dry_run_summary(signals: dict[str, Any], reflexion_root: Path) -> None:
    print("=== git_collect.py --dry-run summary ===")
    print(f"collected_at: {signals.get('collected_at', '?')}")
    print(f"since_days:   {signals.get('since_days', '?')}")
    print(f"commit_count: {signals.get('commit_count', 0)}")
    print(f"bugfix_commits: {len(signals.get('bugfix_commits', []))}")
    hot = signals.get("hot_skills") or []
    print(f"hot_skills:   {len(hot)}")
    for h in hot[:5]:
        print(f"  - {h.get('skill')}: commits={h.get('commit_count')} bugfixes={h.get('bugfix_count')}")
    err = signals.get("error")
    if err:
        print(f"error:        {err}")
    print()
    print("=== pending cleanup (reflexion store) ===")
    preview = _load_reflexion_cleanup_preview(reflexion_root)
    print(f"reflexion_root: {preview['reflexion_root']}")
    print(f"store_present:  {preview['store_present']}")
    if not preview["store_present"]:
        print("  (no reflexion store on disk — nothing to clean up)")
    elif "load_error" in preview:
        print(f"  load_error: {preview['load_error']}")
    else:
        print(
            f"total_before:   {preview['total_before']}\n"
            f"pruned_by_count: {preview['pruned_by_count']} (count < {preview['min_count']})\n"
            f"pruned_by_decay: {preview['pruned_by_decay']} (last_seen >= {preview['decay_days']}d)"
        )
        cats = preview.get("categories") or {}
        if cats:
            print("  by category:")
            for cat, c in cats.items():
                print(
                    f"    - {cat}: before={c['before']} "
                    f"pruned_by_count={c['pruned_by_count']} "
                    f"pruned_by_decay={c['pruned_by_decay']}"
                )
        else:
            print("  (nothing pending)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Git signals for Layer 3 WSR")
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a summary (git signals + pending reflexion cleanup) "
             "without writing the output file.",
    )
    parser.add_argument(
        "--reflexion-root",
        type=Path,
        default=None,
        help="Override reflexion store location for the cleanup preview. "
             "Defaults to <skills-root>/.runtime/reflexion.",
    )
    args = parser.parse_args()

    if args.output is None and not args.dry_run:
        from gcl_strategy import WORK_DIR  # noqa: E402

        args.output = WORK_DIR / "git_signals.json"

    signals = collect_git_signals(since_days=args.since_days, repo_root=args.repo_root)

    if args.dry_run:
        reflexion_root = args.reflexion_root
        if reflexion_root is None:
            env = os.environ.get("GCL_REFLEXION_ROOT") or os.environ.get("ALIYUN_SKILLS_ROOT")
            if env:
                reflexion_root = Path(env) / ".runtime" / "reflexion"
            else:
                reflexion_root = args.repo_root / ".runtime" / "reflexion"
        _print_dry_run_summary(signals, reflexion_root)
        _log(
            f"event=git_collect result=dry_run commits={signals['commit_count']} "
            f"bugfixes={len(signals['bugfix_commits'])}"
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(signals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _log(
        f"event=git_collect result=success commits={signals['commit_count']} "
        f"bugfixes={len(signals['bugfix_commits'])} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
