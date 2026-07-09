#!/usr/bin/env python3
"""
gcl_strategy.py — Layer 3: Strategy Memory (Weekly Offline Review).

Aggregates Git artifact-evolution signals and runtime signals (failure-patterns.md,
optional Layer 1 JSONL), produces week-over-week actionable items, and writes
committed baseline + markdown report.

Layer 3 runs weekly via GitHub Actions — NOT on gcl_runner hot path.

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from git_collect import collect_git_signals  # noqa: E402

STRATEGY_VERSION = "2.0.0"
BASELINE_PATH = Path("docs") / "strategy-baseline.json"
BASELINE_HISTORY_PATH = Path("docs") / "strategy-baseline-history.jsonl"
RUNTIME_ROLLUP_PATH = Path("docs") / "runtime-rollup.json"
REPORT_PATH = Path("docs") / "strategy-report.md"
GIT_REVIEW_REPORT_PATH = Path("docs") / "strategy-git-review.md"
FAILURE_PATTERNS_PATH = Path("docs") / "failure-patterns.md"
REFLEXION_STORE_PATH = Path(".runtime") / "reflexion" / "reflexion.json"
WORK_DIR = Path(".runtime") / "doctor" / "work"
LEGACY_WORK_DIR = Path(".runtime") / "strategy" / "work"  # pre-2026-06 doctor rename; not read
GIT_WEEKLY_SNAPSHOT_WORK = WORK_DIR / "git_weekly_snapshot.json"
WRITE_AUTHORITY_LOCAL = "local_maintainer"
WRITE_AUTHORITY_GHA_GIT = "gha_git_review"

STRATEGY_MIN_SAMPLES = int(os.environ.get("STRATEGY_MIN_SAMPLES", "10"))
FAILURE_RATE_DELTA_THRESHOLD = float(os.environ.get("STRATEGY_FAILURE_RATE_DELTA", "0.10"))
RISK_SCORE_DELTA_THRESHOLD = float(os.environ.get("STRATEGY_RISK_SCORE_DELTA", "0.15"))
STRATEGY_HISTORY_MAX_WEEKS = int(os.environ.get("STRATEGY_HISTORY_MAX_WEEKS", "12"))
STRATEGY_HISTORY_MIN_WEEKS = int(os.environ.get("STRATEGY_HISTORY_MIN_WEEKS", "3"))
MULTIWEEK_FAILURE_RATE_MARGIN = float(os.environ.get("STRATEGY_MULTIWEEK_FR_MARGIN", "0.08"))
MULTIWEEK_ZSCORE_THRESHOLD = float(os.environ.get("STRATEGY_MULTIWEEK_ZSCORE", "2.0"))
FAILURE_RATE_STREAK_WEEKS = int(os.environ.get("STRATEGY_FR_STREAK_WEEKS", "3"))
H_DETECTOR_PROMOTION_THRESHOLD = 10
MAX_REPORT_LINES = 150
BUGFIX_HOT_THRESHOLD = 3


def normalize_skill_name(skill: str | None) -> str:
    """Normalize skill id to ``alicloud-{product}-ops`` form."""
    if not skill:
        return ""
    s = str(skill).strip()
    if s.startswith("alicloud-") and s.endswith("-ops"):
        return s
    if s.endswith("-ops"):
        return f"alicloud-{s}"
    return s


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [STRATEGY] {msg}", file=sys.stderr)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return var ** 0.5


def history_compact_entry(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract a compact weekly record for multi-week comparison."""
    trends: dict[str, Any] = {}
    for skill, trend in snapshot.get("skill_trends", {}).items():
        trends[skill] = {
            "total": trend.get("total", 0),
            "failure_rate": trend.get("failure_rate", 0.0),
            "risk_score": trend.get("risk_score", 0.0),
            "confidence": trend.get("confidence", "low"),
        }
    gs = snapshot.get("git_signals_summary", {})
    return {
        "generated_at": snapshot.get("generated_at"),
        "since_days": snapshot.get("since_days", 7),
        "skill_trends": trends,
        "git_signals_summary": {
            "commit_count": gs.get("commit_count", 0),
            "bugfix_count": gs.get("bugfix_count", 0),
        },
    }


def history_load(
    path: Path = BASELINE_HISTORY_PATH,
    max_weeks: int | None = None,
) -> list[dict[str, Any]]:
    """Load compact weekly history entries (oldest → newest)."""
    limit = max_weeks if max_weeks is not None else STRATEGY_HISTORY_MAX_WEEKS
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries[-limit:]


def history_append(
    entry: dict[str, Any],
    path: Path = BASELINE_HISTORY_PATH,
    max_weeks: int | None = None,
) -> None:
    """Append one compact weekly record; trim to *max_weeks* lines."""
    limit = max_weeks if max_weeks is not None else STRATEGY_HISTORY_MAX_WEEKS
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = history_load(path, max_weeks=limit)
    generated = entry.get("generated_at")
    if generated and any(e.get("generated_at") == generated for e in existing):
        return
    existing.append(entry)
    trimmed = existing[-limit:]
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in trimmed) + ("\n" if trimmed else ""),
        encoding="utf-8",
    )
    _log(f"event=strategy_history result=append path={path} weeks={len(trimmed)}")


def _skill_failure_rate_series(
    skill: str,
    history: list[dict[str, Any]],
    baseline: dict[str, Any] | None,
) -> list[float]:
    """Chronological failure_rate series from history + previous baseline (excludes current week)."""
    series: list[float] = []
    for entry in history:
        trend = entry.get("skill_trends", {}).get(skill)
        if not trend or trend.get("confidence") == "low":
            continue
        series.append(float(trend.get("failure_rate", 0.0)))
    if baseline:
        trend = baseline.get("skill_trends", {}).get(skill)
        if trend and trend.get("confidence") != "low":
            series.append(float(trend.get("failure_rate", 0.0)))
    return series


def _build_actionable_from_multiweek(
    current_trends: dict[str, Any],
    history: list[dict[str, Any]],
    baseline: dict[str, Any] | None,
    *,
    skip_skills: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Multi-week rules: rolling median, z-score, consecutive worsening streak."""
    items: list[dict[str, Any]] = []
    blocked = skip_skills or set()

    for skill, cur in current_trends.items():
        if skill in blocked or cur.get("confidence") == "low":
            continue

        cur_fr = float(cur.get("failure_rate", 0.0))
        series = _skill_failure_rate_series(skill, history, baseline)
        if len(series) < STRATEGY_HISTORY_MIN_WEEKS:
            continue

        med = _median(series)
        mean = sum(series) / len(series)
        std = _stddev(series)

        if cur_fr >= med + MULTIWEEK_FAILURE_RATE_MARGIN and (med == 0.0 or cur_fr >= med * 1.05):
            items.append({
                "id": f"A2-median-{skill}",
                "severity": "high" if cur_fr - med >= FAILURE_RATE_DELTA_THRESHOLD else "medium",
                "type": "failure_rate_above_rolling_median",
                "skill": skill,
                "failure_rate": cur_fr,
                "rolling_median": round(med, 4),
                "history_weeks": len(series),
                "reason": (
                    f"{skill} failure_rate {cur_fr:.1%} exceeds {len(series)}-week median "
                    f"{med:.1%} by ≥{MULTIWEEK_FAILURE_RATE_MARGIN:.0%}"
                ),
                "actions": [
                    f"Review {len(series)}-week trend in docs/strategy-baseline-history.jsonl",
                    "Check failure-patterns.md for recurring errors",
                ],
            })
            continue

        if std >= 0.02:
            z = (cur_fr - mean) / std
            if z >= MULTIWEEK_ZSCORE_THRESHOLD:
                items.append({
                    "id": f"A2-zscore-{skill}",
                    "severity": "medium",
                    "type": "failure_rate_zscore_anomaly",
                    "skill": skill,
                    "failure_rate": cur_fr,
                    "z_score": round(z, 2),
                    "history_weeks": len(series),
                    "reason": (
                        f"{skill} failure_rate z-score {z:.1f} vs {len(series)}-week history "
                        f"(mean={mean:.1%}, std={std:.1%})"
                    ),
                    "actions": [
                        f"Inspect Layer 1 memory for {skill}",
                        "Compare with prior weekly baselines before changing rubric",
                    ],
                })
                continue

        streak_rates = series + [cur_fr]
        if len(streak_rates) >= FAILURE_RATE_STREAK_WEEKS:
            tail = streak_rates[-FAILURE_RATE_STREAK_WEEKS:]
            if all(tail[i] < tail[i + 1] for i in range(len(tail) - 1)):
                items.append({
                    "id": f"A2-streak-{skill}",
                    "severity": "medium",
                    "type": "failure_rate_worsening_streak",
                    "skill": skill,
                    "failure_rate": cur_fr,
                    "streak_weeks": FAILURE_RATE_STREAK_WEEKS,
                    "reason": (
                        f"{skill} failure_rate rose {FAILURE_RATE_STREAK_WEEKS} weeks in a row "
                        f"({ ' → '.join(f'{r:.0%}' for r in tail) })"
                    ),
                    "actions": [
                        f"Inspect Layer 1 memory for {skill}",
                        "Open skill runbook PR if root cause is recurring",
                    ],
                })

    return items


def _parse_failure_patterns(path: Path) -> dict[str, Any]:
    """Parse failure-patterns.md tables for pattern counts and high-frequency rows."""
    if not path.exists():
        return {"pattern_count": 0, "patterns": [], "high_frequency": []}

    text = path.read_text(encoding="utf-8")
    patterns: list[dict[str, Any]] = []
    current_category = "unknown"
    current_headers: list[str] = []

    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("## Usage"):
            current_category = line[3:].strip().lower().replace(" ", "_")
            current_headers = []
            continue
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols:
            continue
        if "Skill" in cols[0] or cols[0].lower() == "skill":
            current_headers = [h.lower().replace(" ", "_") for h in cols]
            continue
        if not current_headers:
            continue
        row = dict(zip(current_headers, cols))
        count = 0
        if row.get("count", "").isdigit():
            count = int(row["count"])
        skill = normalize_skill_name(row.get("skill", cols[0] if cols else ""))
        patterns.append({
            "category": current_category,
            "skill": skill,
            "count": count,
            "row": cols,
        })

    high_frequency = [p for p in patterns if p["count"] >= H_DETECTOR_PROMOTION_THRESHOLD]
    return {
        "pattern_count": len(patterns),
        "patterns": patterns,
        "high_frequency": high_frequency,
    }


def _load_reflexion_high_frequency(repo_root: Path) -> list[dict[str, Any]]:
    """Load high-frequency patterns from Layer 2 JSON store when available."""
    path = repo_root / REFLEXION_STORE_PATH
    if not path.exists():
        return []
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    high: list[dict[str, Any]] = []
    for category, patterns in store.items():
        if not isinstance(patterns, list):
            continue
        for p in patterns:
            if not isinstance(p, dict):
                continue
            count = p.get("count", 0)
            if not isinstance(count, int) or count < H_DETECTOR_PROMOTION_THRESHOLD:
                continue
            skill = normalize_skill_name(p.get("skill") or p.get("source_skill") or "unknown")
            high.append({
                "category": category,
                "skill": skill,
                "count": count,
                "source": "reflexion.json",
            })
    return high


def _merge_high_frequency(
    from_md: list[dict[str, Any]],
    from_json: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge high-frequency lists; reflexion.json wins on duplicate skill+category."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for p in from_md:
        key = (str(p.get("skill", "")), str(p.get("category", "")))
        merged[key] = p
    for p in from_json:
        key = (str(p.get("skill", "")), str(p.get("category", "")))
        merged[key] = p
    return sorted(merged.values(), key=lambda x: x.get("count", 0), reverse=True)


def _scan_memory_trends(memory_root: Path, since_days: int) -> dict[str, Any]:
    """Scan Layer 1 JSONL if available (local / artifact upload)."""
    if not memory_root.exists():
        return {"available": False, "skill_trends": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    skill_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "pass": 0, "fail": 0, "iterations": []}
    )

    for jsonl in memory_root.glob("alicloud-*-ops/*.jsonl"):
        skill = jsonl.parent.name
        try:
            lines = jsonl.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = entry.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts < cutoff:
                continue
            st = skill_stats[skill]
            st["total"] += 1
            if entry.get("rubric_pass") or entry.get("exit_code") == 0:
                st["pass"] += 1
            else:
                st["fail"] += 1
            it = entry.get("iterations", 0)
            if isinstance(it, int) and it > 0:
                st["iterations"].append(it)

    skill_trends: dict[str, Any] = {}
    for skill, st in skill_stats.items():
        total = st["total"]
        if total == 0:
            continue
        failure_rate = st["fail"] / total
        avg_iter = sum(st["iterations"]) / len(st["iterations"]) if st["iterations"] else 0.0
        risk_score = min(1.0, 0.5 * failure_rate + 0.2 * min(avg_iter / 5.0, 1.0))
        skill_trends[skill] = {
            "total": total,
            "pass": st["pass"],
            "fail": st["fail"],
            "failure_rate": round(failure_rate, 4),
            "avg_iterations": round(avg_iter, 2),
            "risk_score": round(risk_score, 4),
            "confidence": "high" if total >= STRATEGY_MIN_SAMPLES else "low",
        }

    return {"available": True, "skill_trends": skill_trends}


def runtime_rollup_apply(
    repo_root: Path,
    since_days: int = 7,
    memory_root: Path | None = None,
) -> int:
    """Build or carry forward ``docs/runtime-rollup.json`` for GHA / offline L3.

    When Layer 1 memory exists locally, scan and commit aggregated trends.
    When memory is empty (typical GHA checkout), carry forward the existing rollup.
    """
    root = repo_root
    mem_root = memory_root or Path(os.environ.get("GCL_MEMORY_ROOT", ".runtime/memory"))
    if not mem_root.is_absolute():
        mem_root = root / mem_root

    scan = _scan_memory_trends(mem_root, since_days)
    rollup_path = root / RUNTIME_ROLLUP_PATH
    existing = _load_json(rollup_path) or {}

    if scan.get("skill_trends"):
        rollup: dict[str, Any] = {
            "version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "since_days": since_days,
            "source": "memory_scan",
            "entry_skills": len(scan["skill_trends"]),
            "skill_trends": scan["skill_trends"],
        }
    elif existing.get("skill_trends"):
        rollup = {
            **existing,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "committed_carry_forward",
        }
    else:
        rollup = {
            "version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "since_days": since_days,
            "source": "empty",
            "skill_trends": {},
        }

    _atomic_write_json(rollup_path, rollup)
    _log(
        f"event=runtime_rollup result=success source={rollup['source']} "
        f"skills={len(rollup.get('skill_trends', {}))}"
    )
    return 0


def _memory_trends_with_rollup_fallback(
    memory_root: Path,
    since_days: int,
    repo_root: Path,
) -> dict[str, Any]:
    """Scan Layer 1 JSONL; fall back to committed ``runtime-rollup.json``."""
    memory = _scan_memory_trends(memory_root, since_days)
    if memory.get("skill_trends"):
        memory["source"] = "memory_scan"
        return memory

    rollup = _load_json(repo_root / RUNTIME_ROLLUP_PATH)
    if rollup and rollup.get("skill_trends"):
        return {
            "available": True,
            "skill_trends": rollup["skill_trends"],
            "source": "runtime_rollup",
            "rollup_updated_at": rollup.get("updated_at"),
        }
    return memory


def _theme_bugfix_clusters(bugfix_commits: list[dict[str, Any]]) -> dict[str, int]:
    clusters: dict[str, int] = defaultdict(int)
    for c in bugfix_commits:
        for theme in c.get("inferred_themes", []):
            clusters[theme] += 1
    return dict(clusters)


def weekly_aggregate(
    git_signals: dict[str, Any] | None = None,
    memory_root: Path | None = None,
    reflexion_report_path: Path = FAILURE_PATTERNS_PATH,
    since_days: int = 7,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Merge runtime + git signals into a weekly snapshot."""
    root = repo_root or Path.cwd()
    if git_signals is None:
        git_signals = collect_git_signals(since_days=since_days, repo_root=root)

    runtime = _parse_failure_patterns(root / reflexion_report_path)
    reflexion_hf = _load_reflexion_high_frequency(root)
    high_frequency = _merge_high_frequency(runtime["high_frequency"], reflexion_hf)
    mem_root = memory_root or Path(os.environ.get("GCL_MEMORY_ROOT", ".runtime/memory"))
    if not mem_root.is_absolute():
        mem_root = root / mem_root
    memory = _memory_trends_with_rollup_fallback(mem_root, since_days, root)

    theme_clusters = _theme_bugfix_clusters(git_signals.get("bugfix_commits", []))

    return {
        "version": STRATEGY_VERSION,
        "review_type": "weekly",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "since_days": since_days,
        "git_signals_summary": {
            "commit_count": git_signals.get("commit_count", 0),
            "bugfix_count": len(git_signals.get("bugfix_commits", [])),
            "hot_skills": git_signals.get("hot_skills", [])[:5],
            "theme_clusters": theme_clusters,
        },
        "runtime_signals_summary": {
            "parsed_from": str(reflexion_report_path),
            "pattern_count": runtime["pattern_count"],
            "high_frequency_count": len(high_frequency),
            "reflexion_json_used": len(reflexion_hf) > 0,
        },
        "skill_trends": memory.get("skill_trends", {}),
        "memory_available": memory.get("available", False),
        "memory_source": memory.get("source", "none"),
        "high_frequency_patterns": high_frequency[:10],
        "actionable_items": [],
        "rule_proposals": [],
        "notification": {"channel": "github", "issue_created": False, "reason": "pending_github_notify"},
    }


def _build_actionable_from_git(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    summary = snapshot.get("git_signals_summary", {})
    for hs in summary.get("hot_skills", []):
        if hs.get("bugfix_count", 0) >= BUGFIX_HOT_THRESHOLD:
            items.append({
                "id": f"A3-{hs['skill']}",
                "severity": "medium",
                "type": "git_hot_bugfix",
                "skill": hs["skill"],
                "reason": (
                    f"{hs['bugfix_count']} bugfix commits in {snapshot.get('since_days', 7)}d "
                    f"for {hs['skill']}"
                ),
                "actions": [
                    f"Review recent bugfixes for {hs['skill']}",
                    "Consider updating cli-usage.md or rubric if root cause is recurring",
                ],
            })

    theme_clusters = summary.get("theme_clusters", {})
    for theme, count in theme_clusters.items():
        if theme != "general" and count >= BUGFIX_HOT_THRESHOLD:
            items.append({
                "id": f"A3-theme-{theme}",
                "severity": "medium",
                "type": "git_theme_cluster",
                "theme": theme,
                "reason": f"{count} bugfixes share theme '{theme}' in review window",
                "actions": [f"Audit skills for recurring {theme} issues"],
            })
    return items


def _build_actionable_from_runtime(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in snapshot.get("high_frequency_patterns", []):
        if p.get("count", 0) >= H_DETECTOR_PROMOTION_THRESHOLD:
            skill = normalize_skill_name(p.get("skill"))
            items.append({
                "id": f"A4-{skill or 'unknown'}-{p.get('category', 'pat')}",
                "severity": "medium",
                "type": "h_detector_candidate",
                "skill": skill or None,
                "category": p.get("category"),
                "count": p.get("count"),
                "reason": f"Failure pattern count={p.get('count')} >= {H_DETECTOR_PROMOTION_THRESHOLD}",
                "actions": ["Evaluate promotion to Hallucination Detection rules (gcl-spec §14)"],
            })
    return items


def _build_actionable_from_trends(
    current_trends: dict[str, Any],
    baseline_trends: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for skill, cur in current_trends.items():
        if cur.get("confidence") == "low":
            continue
        if skill not in baseline_trends:
            base_fr = 0.0
            base_risk = 0.0
        else:
            base = baseline_trends[skill]
            base_fr = base.get("failure_rate", 0.0)
            base_risk = base.get("risk_score", 0.0)
        cur_fr = cur.get("failure_rate", 0.0)
        delta = cur_fr - base_fr
        if delta >= FAILURE_RATE_DELTA_THRESHOLD:
            items.append({
                "id": f"A1-{skill}",
                "severity": "high",
                "type": "failure_rate_worsening",
                "skill": skill,
                "failure_rate": cur_fr,
                "delta": round(delta, 4),
                "reason": f"{skill} failure_rate rose {delta:.1%} vs baseline",
                "actions": [
                    f"Inspect Layer 1 memory for {skill}",
                    "Check failure-patterns.md for new recurring errors",
                ],
            })
        cur_risk = cur.get("risk_score", 0.0)
        risk_delta = cur_risk - base_risk
        if risk_delta >= RISK_SCORE_DELTA_THRESHOLD and delta < FAILURE_RATE_DELTA_THRESHOLD:
            items.append({
                "id": f"A1-risk-{skill}",
                "severity": "medium",
                "type": "risk_score_worsening",
                "skill": skill,
                "risk_score": cur_risk,
                "delta": round(risk_delta, 4),
                "reason": f"{skill} risk_score rose {risk_delta:.2f} vs baseline",
                "actions": [f"Review GCL rubric scores and iteration counts for {skill}"],
            })
    return items


def diff_vs_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute actionable items by comparing current snapshot to baseline + multi-week history."""
    git_items = _build_actionable_from_git(current)
    runtime_items = _build_actionable_from_runtime(current)

    baseline_trends = (baseline or {}).get("skill_trends", {})
    trend_items: list[dict[str, Any]] = []
    if baseline is not None:
        trend_items = _build_actionable_from_trends(
            current.get("skill_trends", {}),
            baseline_trends,
        )

    wow_skills = {item.get("skill") for item in trend_items if item.get("skill")}
    multiweek_items: list[dict[str, Any]] = []
    if history or baseline:
        multiweek_items = _build_actionable_from_multiweek(
            current.get("skill_trends", {}),
            history or [],
            baseline,
            skip_skills=wow_skills,
        )

    seen: set[str] = set()
    actionable: list[dict[str, Any]] = []
    for item in trend_items + multiweek_items + git_items + runtime_items:
        iid = item.get("id", "")
        if iid in seen:
            continue
        seen.add(iid)
        actionable.append(item)

    current["actionable_items"] = actionable
    return {
        "actionable_count": len(actionable),
        "actionable_items": actionable,
        "has_baseline": baseline is not None,
        "history_weeks_loaded": len(history or []),
        "delta_summary": {
            "trend_items": len(trend_items),
            "multiweek_items": len(multiweek_items),
            "git_items": len(git_items),
            "runtime_items": len(runtime_items),
        },
    }


def strategy_store(snapshot: dict[str, Any], path: Path = BASELINE_PATH) -> int:
    try:
        _atomic_write_json(path, snapshot)
        _log(f"event=strategy_store result=success path={path}")
        return 0
    except OSError as exc:
        _log(f"event=strategy_store result=failed reason={exc}")
        return 1


def strategy_report(
    snapshot: dict[str, Any],
    delta: dict[str, Any],
    output_path: Path = REPORT_PATH,
) -> int:
    lines: list[str] = [
        "# Strategy Report — Layer 3 Memory",
        "",
        "> Auto-generated by `gcl_strategy.py weekly`. Token budget: ≤150 lines.",
        f"> Generated: {snapshot.get('generated_at', 'unknown')}",
    ]
    if snapshot.get("write_authority") == WRITE_AUTHORITY_GHA_GIT:
        lines.append(
            "> **Git-only review** — does not update `docs/strategy-baseline.json` "
            "(Local-first: baseline owned by `make doctor-weekly-apply`)."
        )
    lines.extend([
        "",
        "## Weekly Summary",
        "",
        f"- Review window: **{snapshot.get('since_days', 7)} days**",
        f"- Git commits: **{snapshot.get('git_signals_summary', {}).get('commit_count', 0)}**",
        f"- Bugfix commits: **{snapshot.get('git_signals_summary', {}).get('bugfix_count', 0)}**",
        f"- Failure patterns parsed: **{snapshot.get('runtime_signals_summary', {}).get('pattern_count', 0)}**",
        f"- Layer 1 memory scanned: **{'yes' if snapshot.get('memory_available') else 'no'}**",
        f"- Actionable items: **{delta.get('actionable_count', 0)}**",
        f"- Multi-week history loaded: **{delta.get('history_weeks_loaded', 0)} weeks**",
        "",
    ])

    actionable = snapshot.get("actionable_items", [])
    if actionable:
        lines.extend(["## Actionable Items", ""])
        for i, item in enumerate(actionable[:15], 1):
            sev = item.get("severity", "info").upper()
            lines.append(f"{i}. **[{sev}]** {item.get('reason', '')}")
            for act in item.get("actions", [])[:2]:
                lines.append(f"   - {act}")
        lines.append("")
    else:
        lines.extend([
            "## Actionable Items",
            "",
            "_No actionable items this week. No GitHub Issue will be opened._",
            "",
        ])

    hot = snapshot.get("git_signals_summary", {}).get("hot_skills", [])
    if hot:
        lines.extend(["## Hot Skills (Git Activity)", "", "| Skill | Commits | Bugfixes |", "|---|---:|---:|"])
        for hs in hot[:8]:
            lines.append(f"| {hs.get('skill', '')} | {hs.get('commit_count', 0)} | {hs.get('bugfix_count', 0)} |")
        lines.append("")

    trends = snapshot.get("skill_trends", {})
    if trends:
        lines.extend(["## Runtime Trends (Layer 1)", "", "| Skill | Total | Fail Rate | Risk |", "|---|---:|---:|---:|"])
        ranked = sorted(trends.items(), key=lambda x: x[1].get("risk_score", 0), reverse=True)
        for skill, t in ranked[:8]:
            lines.append(
                f"| {skill} | {t.get('total', 0)} | {t.get('failure_rate', 0):.1%} "
                f"| {t.get('risk_score', 0):.2f} |"
            )
        lines.append("")

    proposals = snapshot.get("rule_proposals", [])
    if proposals:
        lines.extend(["## Rule Proposals", ""])
        for p in proposals[:5]:
            lines.append(f"- **{p.get('title', '')}** ({p.get('confidence', 'low')}) — {p.get('rationale', '')}")
        lines.append("")

    lines.extend([
        "## Usage",
        "",
        "```bash",
        "python3 alicloud-gcl-runner-ops/scripts/git_collect.py --since-days 7",
        "python3 alicloud-gcl-runner-ops/scripts/gcl_strategy.py weekly --apply",
        "python3 alicloud-gcl-runner-ops/scripts/strategy_github_notify.py --apply",
        "```",
        "",
    ])

    if len(lines) > MAX_REPORT_LINES:
        lines = lines[: MAX_REPORT_LINES - 1] + ["", "_Report truncated to line budget._", ""]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(f"event=strategy_report result=success path={output_path} lines={len(lines)}")
    return 0


def _actionable_matches_skill(item: dict[str, Any], skill: str) -> bool:
    """Return True if item applies to the requested skill."""
    item_skill = item.get("skill")
    if item_skill:
        return normalize_skill_name(str(item_skill)) == normalize_skill_name(skill)
    # Repo-wide items (e.g. theme clusters) are excluded from per-skill retrieve.
    return False


def _actionable_matches_operation(item: dict[str, Any], operation: str | None) -> bool:
    if not operation:
        return True
    item_op = item.get("operation")
    if not item_op:
        return True
    return str(item_op) == operation


def _actionable_matches_rg(item: dict[str, Any], resource_group_id: str | None) -> bool:
    """Return True if item applies to the requested resource group.

    A baseline entry without ``resource_groups`` (legacy baseline, list missing
    or empty) is considered a general/repo-wide hint and therefore matches any
    RG — callers can still fall back to general hints when per-RG data is
    absent. An entry that lists ``resource_groups`` only matches when the
    requested RG appears in that list.
    """
    if not resource_group_id:
        return True
    rgs = item.get("resource_groups")
    if not rgs:
        return True
    if not isinstance(rgs, list):
        return True
    return str(resource_group_id) in {str(r) for r in rgs}


def strategy_retrieve(
    skill: str,
    operation: str | None = None,
    max_chars: int = 800,
    baseline_path: Path = BASELINE_PATH,
    resource_group_id: str | None = None,
) -> dict[str, Any]:
    """Read-only retrieval from committed baseline for R2 {{strategy_hints}}.

    When ``resource_group_id`` is provided, baseline entries are filtered so
    that only items tagged with this RG contribute preventive actions and
    rule hints. When the baseline has no per-RG data (legacy baseline), the
    general hints are still returned and annotated with ``rg-context`` so the
    caller can see the scope it asked for.
    """
    baseline = _load_json(baseline_path)
    if baseline is None:
        return {"truncated": False, "empty": True}

    result: dict[str, Any] = {"truncated": False, "empty": False}
    if resource_group_id:
        result["rg_context"] = str(resource_group_id)
    trends = baseline.get("skill_trends", {})
    if skill in trends:
        result["skill_risk"] = {
            "risk_score": trends[skill].get("risk_score"),
            "failure_rate": trends[skill].get("failure_rate"),
            "confidence": trends[skill].get("confidence"),
        }

    preventive: list[str] = []
    for item in baseline.get("actionable_items", []):
        if not _actionable_matches_skill(item, skill):
            continue
        if not _actionable_matches_operation(item, operation):
            continue
        if not _actionable_matches_rg(item, resource_group_id):
            continue
        for act in item.get("actions", []):
            preventive.append(act)

    if preventive:
        result["preventive_actions"] = preventive[:5]

    for p in baseline.get("rule_proposals", []):
        if normalize_skill_name(p.get("target_skill")) != normalize_skill_name(skill):
            continue
        if not _actionable_matches_rg(p, resource_group_id):
            continue
        result.setdefault("rule_hints", []).append(p.get("title", ""))

    if resource_group_id:
        has_per_rg_data = any(
            isinstance(it, dict) and it.get("resource_groups")
            for it in baseline.get("actionable_items", [])
        )
        if not has_per_rg_data:
            result["per_rg_data"] = False

    encoded = json.dumps(result, ensure_ascii=False)
    if len(encoded) > max_chars:
        result = {"skill_risk": result.get("skill_risk"), "truncated": True}
        if preventive:
            result["preventive_actions"] = preventive[:2]
        if resource_group_id:
            result["rg_context"] = str(resource_group_id)

    return result


def refresh_report_from_baseline(
    baseline_path: Path,
    output_path: Path | None = None,
) -> int:
    """Regenerate markdown report from an existing baseline JSON."""
    baseline = _load_json(baseline_path)
    if baseline is None:
        _log("event=strategy_report result=failed reason=missing_baseline")
        return 1
    delta = {"actionable_count": len(baseline.get("actionable_items", []))}
    out = output_path if output_path is not None else REPORT_PATH
    return strategy_report(baseline, delta, output_path=out)


def run_weekly(
    apply: bool,
    since_days: int,
    repo_root: Path,
    git_only: bool = False,
) -> int:
    git_signals = collect_git_signals(since_days=since_days, repo_root=repo_root)
    if apply:
        git_path = repo_root / WORK_DIR / "git_signals.json"
        git_path.parent.mkdir(parents=True, exist_ok=True)
        git_path.write_text(json.dumps(git_signals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    baseline_path = repo_root / BASELINE_PATH
    history_path = repo_root / BASELINE_HISTORY_PATH
    baseline = _load_json(baseline_path)
    history = history_load(history_path)

    snapshot = weekly_aggregate(
        git_signals=git_signals,
        since_days=since_days,
        repo_root=repo_root,
    )
    delta = diff_vs_baseline(snapshot, baseline, history=history)

    if git_only:
        snapshot["write_authority"] = WRITE_AUTHORITY_GHA_GIT
        snapshot["baseline_write"] = "forbidden"
        snapshot["memory_source"] = snapshot.get("memory_source") or "git_only"
        if baseline and baseline.get("skill_trends"):
            snapshot["skill_trends"] = baseline.get("skill_trends", {})
            snapshot["memory_available"] = bool(baseline.get("skill_trends"))
    else:
        snapshot["write_authority"] = WRITE_AUTHORITY_LOCAL
        snapshot["baseline_write"] = "allowed" if apply else "dry_run"

    if not snapshot["actionable_items"]:
        snapshot["notification"] = {"channel": "github", "issue_created": False, "reason": "no_actionable_items"}
    else:
        snapshot["notification"] = {"channel": "github", "issue_created": False, "reason": "pending_github_notify"}

    snapshot["history_meta"] = {
        "weeks_loaded": len(history),
        "max_weeks": STRATEGY_HISTORY_MAX_WEEKS,
        "min_weeks_for_multiweek": STRATEGY_HISTORY_MIN_WEEKS,
    }

    if apply and git_only:
        work_dir = repo_root / WORK_DIR
        work_dir.mkdir(parents=True, exist_ok=True)
        snap_path = work_dir / GIT_WEEKLY_SNAPSHOT_WORK.name
        snap_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report_path = repo_root / GIT_REVIEW_REPORT_PATH
        strategy_report(snapshot, delta, output_path=report_path)
        _log(
            f"event=weekly_git_review result=success report={report_path} "
            f"snapshot={snap_path} baseline_write=skipped actionable={delta['actionable_count']}"
        )
        return 0

    if apply:
        if baseline is not None:
            history_append(history_compact_entry(baseline), path=history_path)
        strategy_report(snapshot, delta, output_path=repo_root / REPORT_PATH)
        rc = strategy_store(snapshot, path=baseline_path)
        _log(
            f"event=weekly_aggregate result=success write_authority={WRITE_AUTHORITY_LOCAL} "
            f"actionable={delta['actionable_count']} commits={git_signals.get('commit_count', 0)}"
        )
        return rc

    _log(f"event=weekly_aggregate result=dry_run actionable={delta['actionable_count']}")
    print(json.dumps({"delta": delta, "actionable_items": snapshot["actionable_items"]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Layer 3 Strategy Memory — Weekly Offline Review")
    sub = parser.add_subparsers(dest="command")

    p_weekly = sub.add_parser("weekly", help="Run weekly strategy review")
    p_weekly.add_argument("--apply", action="store_true", help="Write outputs (see --git-only for GHA boundary)")
    p_weekly.add_argument(
        "--git-only",
        action="store_true",
        help="GHA git review: write docs/strategy-git-review.md + work snapshot only; "
        "never updates docs/strategy-baseline.json",
    )
    p_weekly.add_argument("--since-days", type=int, default=7)
    p_weekly.add_argument("--repo-root", type=Path, default=Path.cwd())

    p_ret = sub.add_parser("retrieve", help="Retrieve strategy hints for a skill")
    p_ret.add_argument("--skill", required=True)
    p_ret.add_argument("--operation", default=None)
    p_ret.add_argument("--max-chars", type=int, default=800)
    p_ret.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    p_ret.add_argument("--resource-group-id", default=None,
                       help="Optional RG filter — only baseline entries tagged "
                            "with this RG contribute; missing tags fall back "
                            "to general hints (annotates rg-context).")

    p_rep = sub.add_parser("report", help="Regenerate report from existing baseline")
    p_rep.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    p_rep.add_argument("--output", type=Path, default=REPORT_PATH)

    p_rollup = sub.add_parser("rollup", help="Build docs/runtime-rollup.json from Layer 1 memory")
    p_rollup.add_argument("--apply", action="store_true", help="Write rollup file")
    p_rollup.add_argument("--since-days", type=int, default=7)
    p_rollup.add_argument("--repo-root", type=Path, default=Path.cwd())

    args = parser.parse_args()

    if args.command == "weekly":
        return run_weekly(
            apply=args.apply,
            since_days=args.since_days,
            repo_root=args.repo_root,
            git_only=args.git_only,
        )
    if args.command == "retrieve":
        out = strategy_retrieve(
            skill=args.skill,
            operation=args.operation,
            max_chars=args.max_chars,
            baseline_path=args.baseline,
            resource_group_id=args.resource_group_id,
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if args.command == "report":
        return refresh_report_from_baseline(args.baseline, output_path=args.output)
    if args.command == "rollup":
        if not args.apply:
            _log("event=runtime_rollup result=dry_run hint=pass --apply to write")
            return 0
        return runtime_rollup_apply(repo_root=args.repo_root, since_days=args.since_days)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
