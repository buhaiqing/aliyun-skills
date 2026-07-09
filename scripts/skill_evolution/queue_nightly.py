#!/usr/bin/env python3
"""Nightly queue builder — scan L1/L2/L3 artifacts and produce a sorted skill queue.

M3.1: Reads Layer 1 (execution memory JSONL), Layer 2 (reflexion.json), and
optionally Layer 3 (strategy-baseline.json) to compute a per-skill queue score,
then outputs a priority-ordered queue.

Output is consumed by ``run_milestone_c.sh``.

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
L1_RECENCY_DAYS = 7

# Weights for the composite queue score
W_L1 = 0.3
W_L2 = 0.5
W_L3 = 0.2

# Time decay params for L2 patterns (mirrors gcl_reflexion._time_weighted_score)
L2_DECAY_DAYS = 90.0


# ---------------------------------------------------------------------------
# L1 scanning — execution memory JSONL
# ---------------------------------------------------------------------------


def _is_failure(entry: dict[str, Any]) -> bool:
    """Determine if an L1 entry represents a failure."""
    gcl_status = entry.get("gcl_status", "")
    if gcl_status in ("PASS", "LIGHTWEIGHT"):
        return False
    if not entry.get("rubric_pass", True):
        return True
    if entry.get("failure_pattern") is not None:
        return True
    return False


def scan_l1_failures(
    memory_root: Path,
    skill: str,
    *,
    recency_days: int = L1_RECENCY_DAYS,
) -> int:
    """Count failure entries for ``skill`` in L1 memory JSONL within ``recency_days``.

    Reads all JSONL files under ``memory_root / skill /``.
    """
    skill_dir = memory_root / skill
    if not skill_dir.is_dir():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)
    count = 0

    for jsonl_file in sorted(skill_dir.glob("*.jsonl")):
        for line in jsonl_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Recency filter
            ts = entry.get("timestamp", "")
            if not ts:
                continue
            try:
                entry_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if entry_dt < cutoff:
                continue
            # Failure check
            if _is_failure(entry):
                count += 1

    return count


# ---------------------------------------------------------------------------
# L2 scanning — reflexion.json patterns
# ---------------------------------------------------------------------------


def _time_weighted_score(
    pattern: dict[str, Any],
    *,
    decay_days: float = L2_DECAY_DAYS,
    now: datetime | None = None,
) -> float:
    """Compute a time-weighted score for a single pattern (mirrors gcl_reflexion).

    ``score = count * (1 - min(elapsed_days / decay_days, 1) * 0.5)``
    """
    count = pattern.get("count", 0)
    last_seen_str = pattern.get("last_seen", "")
    if not last_seen_str:
        return float(count)
    now_dt = now if now is not None else datetime.now(timezone.utc)
    try:
        last_seen_dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
        elapsed = (now_dt - last_seen_dt).total_seconds() / 86400.0
        decay = min(elapsed / decay_days, 1.0)
        return count * (1.0 - decay * 0.5)
    except (ValueError, TypeError):
        return float(count)


def scan_l2_patterns(
    reflexion_root: Path,
    skill: str,
    *,
    decay_days: float = L2_DECAY_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan reflexion.json for ``skill`` patterns, returning aggregate stats.

    Returns:
        ``{"pattern_count": int, "pattern_score": float, "top_patterns": list[dict]}``
    """
    reflexion_path = reflexion_root / "reflexion.json"
    if not reflexion_path.exists():
        return {"pattern_count": 0, "pattern_score": 0.0, "top_patterns": []}

    try:
        store = json.loads(reflexion_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pattern_count": 0, "pattern_score": 0.0, "top_patterns": []}

    if not isinstance(store, dict):
        return {"pattern_count": 0, "pattern_score": 0.0, "top_patterns": []}

    total_score = 0.0
    pattern_count = 0
    top_patterns: list[dict[str, Any]] = []
    normed_skill = normalize_skill_name(skill)

    for _cat, patterns in store.items():
        if not isinstance(patterns, list):
            continue
        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue
            # Match skill
            pattern_skill = str(pattern.get("skill") or "")
            if pattern_skill and normalize_skill_name(pattern_skill) != normed_skill:
                continue
            # Match via skills list (generalized_cli)
            skills_list = pattern.get("skills")
            if isinstance(skills_list, list) and normed_skill not in [
                normalize_skill_name(s) for s in skills_list
            ]:
                continue
            if not pattern_skill and not skills_list:
                continue

            score = _time_weighted_score(pattern, decay_days=decay_days, now=now)
            total_score += score
            pattern_count += int(pattern.get("count", 0))

            top_patterns.append({
                "category": str(pattern.get("category", pattern.get("_tier", "unknown"))),
                "error": str(
                    pattern.get("error")
                    or pattern.get("failure_pattern")
                    or pattern.get("normalized_key", "")
                )[:120],
                "count": int(pattern.get("count", 0)),
                "normalized_key": str(pattern.get("normalized_key", "")),
            })

    # Sort by count descending, keep top 10
    top_patterns.sort(key=lambda p: p["count"], reverse=True)
    top_patterns = top_patterns[:10]

    return {
        "pattern_count": pattern_count,
        "pattern_score": round(total_score, 2),
        "top_patterns": top_patterns,
    }


def normalize_skill_name(skill: str) -> str:
    """Normalize skill name for comparison (mirrors gcl_strategy.normalize_skill_name)."""
    s = skill.strip()
    if s.startswith("alicloud-") and s.endswith("-ops"):
        return s
    if s.endswith("-ops"):
        return f"alicloud-{s}"
    return s


# ---------------------------------------------------------------------------
# L3 scanning — strategy-baseline.json
# ---------------------------------------------------------------------------


def scan_l3_strategy(
    strategy_path: Path,
    skill: str,
) -> dict[str, Any]:
    """Read Layer 3 strategy baseline for ``skill``.

    Returns:
        ``{"failure_rate": float, "severity": str, "has_actionable": bool}``
    """
    if not strategy_path.exists():
        return {"failure_rate": 0.0, "severity": "none", "has_actionable": False}

    try:
        baseline = json.loads(strategy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"failure_rate": 0.0, "severity": "none", "has_actionable": False}

    if not isinstance(baseline, dict):
        return {"failure_rate": 0.0, "severity": "none", "has_actionable": False}

    normed_skill = normalize_skill_name(skill)
    result: dict[str, Any] = {
        "failure_rate": 0.0,
        "severity": "none",
        "has_actionable": False,
    }

    # Check per-skill entries
    skills_data = baseline.get("skills", baseline.get("skill_trends", {}))
    if isinstance(skills_data, dict):
        for key, data in skills_data.items():
            if normalize_skill_name(key) == normed_skill and isinstance(data, dict):
                result["failure_rate"] = float(data.get("failure_rate", data.get("fr", 0)))
                result["severity"] = str(
                    data.get("severity", data.get("alert_level", "none"))
                )
                action_items = data.get("action_items", data.get("recommendations", []))
                result["has_actionable"] = bool(action_items)
                break

    # Fallback: check top-level stats
    if result["failure_rate"] == 0.0:
        top_fr = baseline.get("overall_failure_rate", baseline.get("failure_rate", 0))
        result["failure_rate"] = float(top_fr)

    return result


# ---------------------------------------------------------------------------
# Queue building
# ---------------------------------------------------------------------------


def _eval_priority(score: float) -> str:
    """Map queue score to priority label."""
    if score >= 30:
        return "P0"
    if score >= 15:
        return "P1"
    return "P2"


def discover_skills(memory_root: Path) -> list[str]:
    """Discover skill names from L1 memory directory structure."""
    if not memory_root.is_dir():
        return []
    return sorted(
        d.name for d in memory_root.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def build_queue(
    memory_root: Path,
    reflexion_root: Path,
    strategy_path: Path | None = None,
    *,
    min_l1_failures: int = 1,
    min_l2_count: int = 0,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Build a priority-ordered skill queue from L1/L2/L3 data.

    Args:
        memory_root: Root of Layer 1 execution memory (contains skill subdirs).
        reflexion_root: Root containing ``reflexion.json`` (Layer 2).
        strategy_path: Path to Layer 3 ``strategy-baseline.json`` (optional).
        min_l1_failures: Minimum L1 failures to include a skill.
        min_l2_count: Minimum L2 pattern count to include a skill.
        top_k: Maximum number of skills in the queue.

    Returns:
        A list of queue entry dicts, sorted by ``queue_score`` descending.
    """
    skills = discover_skills(memory_root)
    entries: list[dict[str, Any]] = []

    for skill in skills:
        l1_count = scan_l1_failures(memory_root, skill)
        l2_info = scan_l2_patterns(reflexion_root, skill)
        l2_score = l2_info["pattern_score"]
        l2_count = l2_info["pattern_count"]

        l3_info: dict[str, Any] = {"failure_rate": 0.0, "severity": "none", "has_actionable": False}
        if strategy_path is not None:
            l3_info = scan_l3_strategy(strategy_path, skill)

        # Filter thresholds
        if l1_count < min_l1_failures:
            continue
        if l2_count < min_l2_count:
            continue

        l3_failure_rate = l3_info.get("failure_rate", 0.0)
        queue_score = (
            l1_count * W_L1
            + l2_score * W_L2
            + l3_failure_rate * W_L3
        )

        entry: dict[str, Any] = {
            "skill": skill,
            "queue_score": round(queue_score, 1),
            "l1_failure_score": l1_count,
            "l2_pattern_score": l2_score,
            "l3_strategy_score": l3_failure_rate,
            "l1_failure_count": l1_count,
            "l2_pattern_count": l2_count,
            "l3_has_actionable": l3_info.get("has_actionable", False),
            "l3_severity": l3_info.get("severity", "none"),
            "top_patterns": l2_info.get("top_patterns", []),
            "eval_priority": _eval_priority(queue_score),
        }
        entries.append(entry)

    entries.sort(key=lambda e: e["queue_score"], reverse=True)

    if top_k is not None and top_k > 0:
        entries = entries[:top_k]

    return entries


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_json(
    entries: list[dict[str, Any]],
    total_scanned: int,
) -> dict[str, Any]:
    """Format the queue as the canonical JSON output."""
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": SCHEMA_VERSION,
        "total_skills_scanned": total_scanned,
        "total_skills_queued": len(entries),
        "queue": entries,
    }


def format_text(entries: list[dict[str, Any]], total_scanned: int) -> str:
    """Format the queue as human-readable text."""
    lines: list[str] = [
        f"Nightly Queue — generated_at={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Scanned={total_scanned} Queued={len(entries)}",
        "",
    ]
    if not entries:
        lines.append("(empty queue — no skills met the threshold)")
        return "\n".join(lines) + "\n"

    for entry in entries:
        top = entry.get("top_patterns", [])
        top_summary = ""
        if top:
            samples = [f"{p['error'][:40]} (x{p['count']})" for p in top[:3]]
            top_summary = f"  top: {'; '.join(samples)}"

        lines.append(
            f"#{entry.get('eval_priority', 'P2')} "
            f"{entry['skill']:30s} "
            f"score={entry['queue_score']:6.1f}  "
            f"L1={entry['l1_failure_count']:3d}  "
            f"L2={entry['l2_pattern_score']:6.1f}  "
            f"L3={entry['l3_strategy_score']:.2f}  "
            f"sev={entry.get('l3_severity', 'none')}"
        )
        if top_summary:
            lines.append(top_summary)

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="M3.1: Build nightly skill evolution queue from L1/L2/L3 data",
    )
    p.add_argument("--skills-root", default=None, help="Aliyun skills root (default: repo root)")
    p.add_argument("--memory-root", default=None, help="Override L1 memory root")
    p.add_argument("--reflexion-root", default=None, help="Override L2 reflexion root")
    p.add_argument("--strategy-baseline", default=None, help="Path to L3 strategy-baseline.json")
    p.add_argument("--min-l1-failures", type=int, default=1, help="Min L1 failures to queue (default: 1)")
    p.add_argument("--min-l2-count", type=int, default=0, help="Min L2 pattern count to queue (default: 0)")
    p.add_argument("--top-k", type=int, default=None, help="Limit queue to top K entries")
    p.add_argument("--out", default=None, help="Output path (default: stdout)")
    p.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    return p


def resolve_memory_root(memory_root: str | None, skills_root: Path) -> Path:
    if memory_root and memory_root != "None":
        p = Path(memory_root)
        return p if p.is_absolute() else (skills_root / p)
    return skills_root / ".runtime" / "memory"


def resolve_reflexion_root(reflexion_root: str | None, skills_root: Path) -> Path:
    if reflexion_root and reflexion_root != "None":
        p = Path(reflexion_root)
        return p if p.is_absolute() else (skills_root / p)
    return skills_root / ".runtime" / "reflexion"


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    skills_root = Path(__file__).resolve().parents[2]
    memory_root = resolve_memory_root(args.memory_root, skills_root)
    reflexion_root = resolve_reflexion_root(args.reflexion_root, skills_root)

    strategy_path: Path | None = None
    if args.strategy_baseline:
        strategy_path = Path(args.strategy_baseline)
        if not strategy_path.is_absolute():
            strategy_path = skills_root / strategy_path

    entries = build_queue(
        memory_root,
        reflexion_root,
        strategy_path,
        min_l1_failures=args.min_l1_failures,
        min_l2_count=args.min_l2_count,
        top_k=args.top_k,
    )

    total_scanned = len(discover_skills(memory_root))

    if args.format == "json":
        output = json.dumps(
            format_json(entries, total_scanned),
            indent=2,
            ensure_ascii=False,
        )
    else:
        output = format_text(entries, total_scanned)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[SUMMARY] queue written to {out_path}  entries={len(entries)}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
