#!/usr/bin/env python3
"""TEL Phase 5 — aggregate runtime LLM token usage from traces into .runtime/token/.

Reads wrapper traces (.runtime/traces/<skill>/ and legacy alicloud-*-ops/.runtime/traces/), GCL audit traces, and
optional session JSON. Writes gitignored rollup artifacts under .runtime/token/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROLLUP_VERSION = "1.5.0"
INCREMENTAL_STATE_VERSION = "1.0.0"
WASTE_GCL_STATUSES = frozenset({"MAX_ITER", "SAFETY_FAIL", "HALLUCINATION_ABORT"})
L1_MIN_SAMPLES = int(os.environ.get("TOKEN_L1_MIN_SAMPLES", os.environ.get("STRATEGY_MIN_SAMPLES", "10")))
L2_WASTE_CATEGORIES = frozenset({"cli_parameter", "runtime", "max_iter", "cross_skill"})


def _log(msg: str) -> None:
    print(f"[token_rollup] {msg}", file=sys.stderr)


def resolve_repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    for key in ("ALIYUN_SKILLS_ROOT", "SKILLS_DIR"):
        val = os.environ.get(key)
        if val:
            return Path(val).expanduser().resolve()
    return Path.cwd().resolve()


def token_root(repo_root: Path) -> Path:
    return repo_root / ".runtime" / "token"


def incremental_state_path(repo_root: Path) -> Path:
    return token_root(repo_root) / "current" / "incremental-state.json"


def records_cache_path(repo_root: Path) -> Path:
    return token_root(repo_root) / "cache" / "normalized-records.jsonl"


def _parse_ts(raw: Any, fallback: datetime | None = None) -> datetime | None:
    if raw is None or raw == "":
        return fallback
    if isinstance(raw, int | float):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return fallback
    text = str(raw).strip()
    if not text:
        return fallback
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d-%H%M%S",
    ):
        try:
            if fmt.endswith("%z") and text.endswith("Z"):
                text = text[:-1] + "+0000"
            dt = datetime.strptime(text.replace(":", "", 1) if False else text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return fallback


def _usage_dict(obj: dict[str, Any] | None) -> dict[str, int]:
    if not obj:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    prompt = int(obj.get("prompt_tokens") or 0)
    completion = int(obj.get("completion_tokens") or 0)
    total = obj.get("total_tokens")
    if total is None:
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int(total),
    }


def _add_usage(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    return {
        "prompt_tokens": a.get("prompt_tokens", 0) + b.get("prompt_tokens", 0),
        "completion_tokens": a.get("completion_tokens", 0) + b.get("completion_tokens", 0),
        "total_tokens": a.get("total_tokens", 0) + b.get("total_tokens", 0),
    }


def _sum_generations(generations: list[dict[str, Any]]) -> dict[str, int]:
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for gen in generations:
        total = _add_usage(total, _usage_dict(gen))
    return total


def _critic_tokens_from_generations(generations: list[dict[str, Any]]) -> int:
    critic = 0
    for gen in generations:
        role = str(gen.get("role") or "")
        source = str(gen.get("source") or "")
        if role in ("critic", "gcl_critic") or source in ("gcl_critic", "critic"):
            critic += _usage_dict(gen)["total_tokens"]
    return critic


def _agent_turn_tokens(generations: list[dict[str, Any]]) -> int:
    total = 0
    for gen in generations:
        if str(gen.get("role") or "") == "agent_turn":
            total += _usage_dict(gen)["total_tokens"]
    return total


def _primary_agent_model(trace: dict[str, Any], generations: list[dict[str, Any]]) -> tuple[str, str]:
    agent = trace.get("coding_agent")
    if not agent or agent == "null":
        agent = None
    model = None
    for gen in generations:
        if str(gen.get("role") or "") == "agent_turn":
            agent = agent or gen.get("coding_agent")
            model = gen.get("model")
            break
    if not agent and generations:
        agent = generations[0].get("coding_agent")
        model = model or generations[0].get("model")
    return str(agent or "unknown"), str(model or "unknown")


@dataclass
class NormalizedRecord:
    source: str
    trace_id: str
    session_id: str
    skill: str
    operation: str
    status: str
    success: bool
    waste: bool
    timestamp: datetime | None
    coding_agent: str
    model: str
    llm_usage: dict[str, int]
    critic_tokens: int
    agent_turn_tokens: int
    mcp: dict[str, Any] | None = None
    error_code: str = ""
    l2_category_hint: str = ""
    trace_path: str = ""
    agent_turn_id: str = ""


def record_to_dict(rec: NormalizedRecord) -> dict[str, Any]:
    return {
        "trace_path": rec.trace_path,
        "source": rec.source,
        "trace_id": rec.trace_id,
        "session_id": rec.session_id,
        "skill": rec.skill,
        "operation": rec.operation,
        "status": rec.status,
        "success": rec.success,
        "waste": rec.waste,
        "timestamp": rec.timestamp.isoformat().replace("+00:00", "Z") if rec.timestamp else None,
        "coding_agent": rec.coding_agent,
        "model": rec.model,
        "llm_usage": rec.llm_usage,
        "critic_tokens": rec.critic_tokens,
        "agent_turn_tokens": rec.agent_turn_tokens,
        "mcp": rec.mcp,
        "error_code": rec.error_code,
        "l2_category_hint": rec.l2_category_hint,
        "agent_turn_id": rec.agent_turn_id,
    }


def record_from_dict(data: dict[str, Any]) -> NormalizedRecord | None:
    try:
        ts = _parse_ts(data.get("timestamp"))
        return NormalizedRecord(
            source=str(data.get("source") or "unknown"),
            trace_id=str(data.get("trace_id") or ""),
            session_id=str(data.get("session_id") or ""),
            skill=str(data.get("skill") or "unknown"),
            operation=str(data.get("operation") or "unknown"),
            status=str(data.get("status") or "unknown"),
            success=bool(data.get("success")),
            waste=bool(data.get("waste")),
            timestamp=ts,
            coding_agent=str(data.get("coding_agent") or "unknown"),
            model=str(data.get("model") or "unknown"),
            llm_usage=_usage_dict(data.get("llm_usage")),
            critic_tokens=int(data.get("critic_tokens") or 0),
            agent_turn_tokens=int(data.get("agent_turn_tokens") or 0),
            mcp=data.get("mcp") if isinstance(data.get("mcp"), dict) else None,
            error_code=str(data.get("error_code") or ""),
            l2_category_hint=str(data.get("l2_category_hint") or ""),
            trace_path=str(data.get("trace_path") or ""),
            agent_turn_id=str(data.get("agent_turn_id") or ""),
        )
    except (TypeError, ValueError):
        return None


def load_incremental_state(repo_root: Path) -> dict[str, Any] | None:
    return _load_json(incremental_state_path(repo_root))


def save_incremental_state(repo_root: Path, state: dict[str, Any]) -> None:
    _atomic_write(incremental_state_path(repo_root), state)


def load_records_cache(repo_root: Path, since: datetime) -> dict[str, NormalizedRecord]:
    """Load cache keyed by trace_path; drop rows outside the rollup window."""
    path = records_cache_path(repo_root)
    out: dict[str, NormalizedRecord] = {}
    if not path.is_file():
        return out
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        rec = record_from_dict(raw)
        if rec is None or not rec.trace_path:
            continue
        ts = rec.timestamp
        if ts is None or ts < since:
            continue
        out[rec.trace_path] = rec
    return out


def save_records_cache(repo_root: Path, records: dict[str, NormalizedRecord]) -> None:
    path = records_cache_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record_to_dict(rec), ensure_ascii=False, sort_keys=True) for rec in records.values()]
    _atomic_write(path, "\n".join(lines) + ("\n" if lines else ""))


def resolve_rollup_mode(repo_root: Path, full: bool, incremental: bool) -> str:
    if full:
        return "full"
    if incremental:
        return "incremental"
    if incremental_state_path(repo_root).is_file():
        return "incremental"
    return "full"


def normalize_wrapper_trace(trace: dict[str, Any], path: Path) -> NormalizedRecord | None:
    generations = list(trace.get("llm_generations") or [])
    usage = _usage_dict(trace.get("llm_usage"))
    if usage["total_tokens"] == 0 and generations:
        usage = _sum_generations(generations)
    status = str(trace.get("status") or "unknown")
    success = status == "success"
    agent, model = _primary_agent_model(trace, generations)
    mcp = (trace.get("context_metadata") or {}).get("mcp")
    if mcp is not None and not isinstance(mcp, dict):
        mcp = None
    ts = _parse_ts(
        trace.get("end_time") or trace.get("start_time"),
        fallback=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
    )
    error_code = str(trace.get("error_code") or "")
    l2_hint = "cli_parameter" if error_code else ""
    return NormalizedRecord(
        source="wrapper",
        trace_id=str(trace.get("trace_id") or path.stem),
        session_id=str(trace.get("session_id") or ""),
        skill=str(trace.get("skill") or "unknown"),
        operation=str(trace.get("action") or trace.get("operation") or "unknown"),
        status=status,
        success=success,
        waste=not success,
        timestamp=ts,
        coding_agent=agent,
        model=model,
        llm_usage=usage,
        critic_tokens=_critic_tokens_from_generations(generations),
        agent_turn_tokens=_agent_turn_tokens(generations),
        mcp=mcp,
        error_code=error_code,
        l2_category_hint=l2_hint,
        agent_turn_id=str(trace.get("agent_turn_id") or ""),
    )


def _gcl_critic_tokens(trace: dict[str, Any]) -> int:
    total = 0
    for it in trace.get("iterations") or []:
        critic = (it.get("critic") or {}).get("critic_meta") or {}
        usage = critic.get("llm_usage")
        if usage:
            total += _usage_dict(usage)["total_tokens"]
    return total


def normalize_gcl_trace(trace: dict[str, Any], path: Path) -> NormalizedRecord | None:
    final = trace.get("final") or {}
    status = str(final.get("status") or "unknown")
    success = status == "PASS"
    waste = (not success) or status in WASTE_GCL_STATUSES
    critic_tokens = _gcl_critic_tokens(trace)
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": critic_tokens}
    last_meta: dict[str, Any] = {}
    iters = trace.get("iterations") or []
    if iters:
        last_meta = (iters[-1].get("critic") or {}).get("critic_meta") or {}
    agent = str(last_meta.get("coding_agent") or trace.get("coding_agent") or "harness_cli")
    model = str(last_meta.get("model") or "unknown")
    ts = _parse_ts(
        trace.get("started_at") or trace.get("timestamp"),
        fallback=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
    )
    fp = trace.get("failure_pattern") or {}
    l2_hint = str(fp.get("category") or "")
    if not l2_hint and status == "MAX_ITER":
        l2_hint = "max_iter"
    return NormalizedRecord(
        source="gcl-runner",
        trace_id=str(trace.get("trace_id") or path.stem),
        session_id=str(trace.get("session_id") or ""),
        skill=str(trace.get("skill") or "unknown"),
        operation=str(trace.get("operation") or trace.get("op") or "unknown"),
        status=status,
        success=success,
        waste=waste,
        timestamp=ts,
        coding_agent=agent,
        model=model,
        llm_usage=usage,
        critic_tokens=critic_tokens,
        agent_turn_tokens=0,
        mcp=None,
        error_code="",
        l2_category_hint=l2_hint,
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def memory_root(repo_root: Path) -> Path:
    mem = os.environ.get("GCL_MEMORY_ROOT", ".runtime/memory")
    path = Path(mem)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _l1_entry_passed(entry: dict[str, Any]) -> bool:
    if entry.get("rubric_pass"):
        return True
    exit_code = entry.get("exit_code")
    return exit_code == 0


def scan_l1_skill_stats(repo_root: Path, since: datetime) -> dict[str, Any]:
    """Scan Layer 1 JSONL within the same time window as trace rollup (X-1)."""
    root = memory_root(repo_root)
    if not root.is_dir():
        return {"available": False, "memory_root": str(root), "skill_stats": {}}

    skill_stats: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "pass": 0, "fail": 0})
    files_scanned = 0
    entries_in_window = 0

    for jsonl in sorted(root.glob("alicloud-*-ops/*.jsonl")):
        skill = jsonl.parent.name
        files_scanned += 1
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
            ts = _parse_ts(entry.get("timestamp"))
            if ts is None or ts < since:
                continue
            entries_in_window += 1
            st = skill_stats[skill]
            st["total"] += 1
            if _l1_entry_passed(entry):
                st["pass"] += 1
            else:
                st["fail"] += 1

    out: dict[str, Any] = {}
    for skill, st in skill_stats.items():
        total = st["total"]
        if total == 0:
            continue
        pass_rate = round(st["pass"] / total, 4)
        out[skill] = {
            "execution_count": total,
            "pass_count": st["pass"],
            "fail_count": st["fail"],
            "rubric_pass_rate": pass_rate,
            "confidence": "high" if total >= L1_MIN_SAMPLES else "low",
        }

    return {
        "available": bool(out),
        "memory_root": str(root.relative_to(repo_root)) if root.is_relative_to(repo_root) else str(root),
        "files_scanned": files_scanned,
        "entries_in_window": entries_in_window,
        "skill_stats": out,
    }


def join_l1_into_rollup(agg: dict[str, Any], l1_scan: dict[str, Any]) -> dict[str, Any]:
    """Enrich by_skill with L1 rubric_pass_rate and expensive-unstable score (X-1)."""
    l1_stats: dict[str, Any] = l1_scan.get("skill_stats") or {}
    by_skill: dict[str, Any] = dict(agg.get("by_skill") or {})
    ranking: list[dict[str, Any]] = []

    for skill, bucket in by_skill.items():
        l1 = l1_stats.get(skill)
        if not l1:
            bucket["l1"] = {"available": False}
            continue
        tps = float(bucket.get("tokens_per_success") or 0)
        rpr = float(l1["rubric_pass_rate"])
        unstable = round(1.0 - rpr, 4)
        score = round(tps * unstable, 2) if tps > 0 else 0.0
        bucket["l1"] = {"available": True, **l1}
        bucket["expensive_unstable_score"] = score
        ranking.append(
            {
                "skill": skill,
                "tokens_per_success": tps,
                "rubric_pass_rate": rpr,
                "expensive_unstable_score": score,
                "l1_confidence": l1.get("confidence", "low"),
            }
        )

    for skill, l1 in l1_stats.items():
        if skill in by_skill:
            continue
        by_skill[skill] = {
            "trace_count": 0,
            "success_count": 0,
            "waste_count": 0,
            "llm_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "tokens_per_success": 0.0,
            "waste_ratio": 0.0,
            "critic_overhead_ratio": 0.0,
            "agent_skill_load_ratio": 0.0,
            "unknown_agent_ratio": 0.0,
            "unknown_model_ratio": 0.0,
            "l1": {"available": True, **l1},
            "expensive_unstable_score": 0.0,
            "token_only": True,
        }

    ranking.sort(key=lambda row: row["expensive_unstable_score"], reverse=True)
    skills_joined = sum(1 for s in by_skill.values() if (s.get("l1") or {}).get("available"))

    l1_join = {
        "available": l1_scan.get("available", False),
        "degraded": not l1_scan.get("available", False),
        "memory_root": l1_scan.get("memory_root"),
        "files_scanned": l1_scan.get("files_scanned", 0),
        "entries_in_window": l1_scan.get("entries_in_window", 0),
        "skills_with_l1": len(l1_stats),
        "skills_joined": skills_joined,
        "expensive_unstable_ranking": ranking[:15],
    }
    return {**agg, "by_skill": dict(sorted(by_skill.items())), "l1_join": l1_join}


def reflexion_root(repo_root: Path) -> Path:
    root = os.environ.get("GCL_REFLEXION_ROOT", ".runtime/reflexion")
    path = Path(root)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _operation_from_aliyun_command(command: str) -> str:
    parts = str(command or "").split()
    if len(parts) >= 3 and parts[0] == "aliyun":
        return parts[2]
    return ""


def _l2_pattern_in_window(pattern: dict[str, Any], since: datetime) -> bool:
    ts = _parse_ts(pattern.get("last_seen")) or _parse_ts(pattern.get("first_seen"))
    return ts is not None and ts >= since


def _l2_pattern_skill_operation(category: str, pattern: dict[str, Any]) -> tuple[str, str]:
    skill = str(pattern.get("skill") or pattern.get("source_skill") or "")
    if category == "cli_parameter":
        op = _operation_from_aliyun_command(str(pattern.get("command") or ""))
        return skill, op
    if category == "cross_skill":
        return str(pattern.get("source_skill") or ""), str(pattern.get("target_skill") or "")
    return skill, str(pattern.get("operation") or "")


def _l2_trap_label(category: str, pattern: dict[str, Any]) -> str:
    if category == "cli_parameter":
        return str(pattern.get("error") or pattern.get("error_pattern") or "cli_parameter")
    if category == "max_iter":
        return str(pattern.get("failing_dimensions") or "max_iter")
    if category == "runtime":
        return str(pattern.get("failure_pattern") or "runtime")
    if category == "cross_skill":
        return str(pattern.get("failure_pattern") or "cross_skill")
    return category


def _l2_fix_hint(category: str, pattern: dict[str, Any]) -> str:
    for key in ("fix", "prevention", "resolution", "fix_pattern"):
        val = pattern.get(key)
        if val:
            return str(val)[:200]
    return ""


def scan_l2_patterns(repo_root: Path, since: datetime) -> dict[str, Any]:
    """Load Layer 2 reflexion store and index by (skill, operation) (X-2)."""
    root = reflexion_root(repo_root)
    store_path = root / "reflexion.json"
    if not store_path.is_file():
        return {"available": False, "reflexion_root": str(root), "index": {}, "patterns_in_window": 0}

    store = _load_json(store_path)
    if not store:
        return {"available": False, "reflexion_root": str(root), "index": {}, "patterns_in_window": 0}

    index: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    patterns_in_window = 0

    for category, rows in store.items():
        if category not in L2_WASTE_CATEGORIES or not isinstance(rows, list):
            continue
        for pattern in rows:
            if not isinstance(pattern, dict):
                continue
            if not _l2_pattern_in_window(pattern, since):
                continue
            patterns_in_window += 1
            skill, op = _l2_pattern_skill_operation(category, pattern)
            if not skill:
                continue
            index[(skill, op)].append(
                {
                    "category": category,
                    "trap_label": _l2_trap_label(category, pattern),
                    "fix": _l2_fix_hint(category, pattern),
                    "l2_count": int(pattern.get("count") or 1),
                    "last_seen": pattern.get("last_seen") or pattern.get("first_seen"),
                    "pattern": pattern,
                }
            )

    for key in index:
        index[key].sort(key=lambda row: row.get("l2_count", 0), reverse=True)

    rel_root = str(root.relative_to(repo_root)) if root.is_relative_to(repo_root) else str(root)
    return {
        "available": patterns_in_window > 0,
        "reflexion_root": rel_root,
        "patterns_in_window": patterns_in_window,
        "index": {f"{skill}|{op}": rows for (skill, op), rows in index.items()},
    }


def _pick_l2_match(
    candidates: list[dict[str, Any]],
    category_hint: str,
    error_code: str,
) -> dict[str, Any] | None:
    if not candidates:
        return None
    pool = candidates
    if category_hint:
        hinted = [c for c in candidates if c["category"] == category_hint]
        if hinted:
            pool = hinted
    if error_code:
        code_matches = [
            c
            for c in pool
            if c["category"] == "cli_parameter" and error_code in str(c.get("trap_label") or "")
        ]
        if code_matches:
            pool = code_matches
    best = max(pool, key=lambda c: (c.get("l2_count", 0), c["category"] == "cli_parameter"))
    return {
        "category": best["category"],
        "trap_label": best["trap_label"],
        "fix": best.get("fix") or "",
        "l2_count": best.get("l2_count", 0),
        "confidence": "high" if best.get("l2_count", 0) >= 3 else "low",
    }


def build_waste_events(records: Iterable[NormalizedRecord]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for rec in records:
        if not rec.waste:
            continue
        ts = rec.timestamp.isoformat().replace("+00:00", "Z") if rec.timestamp else None
        events.append(
            {
                "trace_id": rec.trace_id,
                "skill": rec.skill,
                "operation": rec.operation,
                "source": rec.source,
                "status": rec.status,
                "waste_tokens": rec.llm_usage["total_tokens"],
                "critic_tokens": rec.critic_tokens,
                "error_code": rec.error_code,
                "l2_category_hint": rec.l2_category_hint,
                "timestamp": ts,
                "l2_match": None,
            }
        )
    return events


def attribute_waste_events(
    waste_events: list[dict[str, Any]],
    l2_scan: dict[str, Any],
) -> list[dict[str, Any]]:
    index: dict[str, list[dict[str, Any]]] = l2_scan.get("index") or {}
    for event in waste_events:
        key = f"{event['skill']}|{event['operation']}"
        match = _pick_l2_match(
            index.get(key, []),
            str(event.get("l2_category_hint") or ""),
            str(event.get("error_code") or ""),
        )
        if match:
            event["l2_match"] = match
    return waste_events


def build_l2_join(
    waste_events: list[dict[str, Any]],
    l2_scan: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate waste events by L2 (skill, op, category) trap (X-2)."""
    traps: defaultdict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "waste_event_count": 0,
            "waste_tokens": 0,
            "critic_tokens": 0,
            "l2_count": 0,
            "fix": "",
        }
    )
    attributed = 0
    for event in waste_events:
        match = event.get("l2_match")
        if not match:
            continue
        attributed += 1
        cat = str(match["category"])
        trap = str(match["trap_label"])
        key = (event["skill"], event["operation"], cat, trap)
        row = traps[key]
        row["skill"] = event["skill"]
        row["operation"] = event["operation"]
        row["category"] = cat
        row["trap_label"] = trap
        row["waste_event_count"] += 1
        row["waste_tokens"] += int(event.get("waste_tokens") or 0)
        row["critic_tokens"] += int(event.get("critic_tokens") or 0)
        row["l2_count"] = max(row["l2_count"], int(match.get("l2_count") or 0))
        if not row["fix"] and match.get("fix"):
            row["fix"] = match["fix"]

    by_trap: list[dict[str, Any]] = []
    for row in traps.values():
        narrative = (
            f"{row['category']} trap ({row['trap_label']}) → "
            f"{row['waste_event_count']} waste trace(s), {row['critic_tokens']} critic tokens"
        )
        by_trap.append({**row, "narrative": narrative})
    by_trap.sort(key=lambda r: (r["critic_tokens"], r["waste_tokens"]), reverse=True)

    total = len(waste_events)
    return {
        "available": l2_scan.get("available", False),
        "degraded": not l2_scan.get("available", False),
        "reflexion_root": l2_scan.get("reflexion_root"),
        "patterns_in_window": l2_scan.get("patterns_in_window", 0),
        "waste_events_total": total,
        "waste_events_attributed": attributed,
        "attribution_rate": round(attributed / max(total, 1), 4),
        "by_trap": by_trap[:20],
    }


def join_l2_into_rollup(
    agg: dict[str, Any],
    records: list[NormalizedRecord],
    l2_scan: dict[str, Any],
) -> dict[str, Any]:
    waste_events = attribute_waste_events(build_waste_events(records), l2_scan)
    l2_join = build_l2_join(waste_events, l2_scan)
    return {**agg, "waste_events": waste_events, "l2_join": l2_join}


def mcp_context_sidecar_path(repo_root: Path) -> Path:
    return token_root(repo_root) / "context" / "mcp-context-latest.json"


def load_mcp_sidecar_snapshot(repo_root: Path, since: datetime) -> dict[str, Any] | None:
    """Read IDE MCP sidecar when fresh (X-18 supplemental source)."""
    path = mcp_context_sidecar_path(repo_root)
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if mtime < since:
        return None
    data = _load_json(path)
    if not data or not isinstance(data, dict):
        return None
    if "mcp_tools_loaded" not in data:
        return None
    return data


def _mcp_tool_sets(mcp: dict[str, Any]) -> tuple[set[str], set[str]]:
    loaded = {str(x) for x in (mcp.get("mcp_tools_loaded") or []) if x}
    invoked = {str(x) for x in (mcp.get("mcp_tools_invoked") or []) if x}
    return loaded, invoked


def _mcp_metrics_block(
    util_samples: list[float],
    waste_tokens: int,
    confidence: set[str],
    trace_count: int,
    total_traces: int,
) -> dict[str, Any]:
    return {
        "mcp_trace_count": trace_count,
        "mcp_trace_coverage_ratio": round(trace_count / max(total_traces, 1), 4),
        "mcp_tool_utilization": round(sum(util_samples) / max(len(util_samples), 1), 4)
        if util_samples
        else 0.0,
        "mcp_schema_waste_tokens": waste_tokens,
        "attribution_confidence": _merge_confidence(confidence),
    }


def join_mcp_into_rollup(
    agg: dict[str, Any],
    records: list[NormalizedRecord],
    sidecar: dict[str, Any] | None,
) -> dict[str, Any]:
    """Complete MCP dimension rollup across global / by_skill / by_agent_model (X-18)."""
    total_traces = len(records)
    mcp_records = [r for r in records if r.mcp]
    util_samples = [float(r.mcp["mcp_tool_utilization"]) for r in mcp_records if isinstance(r.mcp.get("mcp_tool_utilization"), int | float)]
    waste_total = sum(int(r.mcp.get("mcp_schema_waste_tokens") or 0) for r in mcp_records)
    confidence: set[str] = set()
    for rec in mcp_records:
        conf = rec.mcp.get("attribution_confidence")
        if conf:
            confidence.add(str(conf))

    loaded_all: set[str] = set()
    invoked_all: set[str] = set()
    low_util: list[dict[str, Any]] = []
    for rec in mcp_records:
        assert rec.mcp is not None
        loaded, invoked = _mcp_tool_sets(rec.mcp)
        loaded_all |= loaded
        invoked_all |= invoked
        util = float(rec.mcp.get("mcp_tool_utilization") or 0)
        waste = int(rec.mcp.get("mcp_schema_waste_tokens") or 0)
        if util < 0.5 or waste > 0:
            low_util.append(
                {
                    "skill": rec.skill,
                    "operation": rec.operation,
                    "coding_agent": rec.coding_agent,
                    "mcp_tool_utilization": round(util, 4),
                    "mcp_schema_waste_tokens": waste,
                    "tools_loaded": len(loaded),
                    "tools_invoked": len(invoked),
                    "tools_unused": sorted(loaded - invoked)[:8],
                }
            )
    low_util.sort(key=lambda row: (row["mcp_schema_waste_tokens"], 1 - row["mcp_tool_utilization"]), reverse=True)

    sidecar_used = sidecar is not None
    if sidecar:
        s_loaded, s_invoked = _mcp_tool_sets(sidecar)
        loaded_all |= s_loaded
        invoked_all |= s_invoked
        if isinstance(sidecar.get("mcp_tool_utilization"), int | float):
            util_samples.append(float(sidecar["mcp_tool_utilization"]))
        waste_total += int(sidecar.get("mcp_schema_waste_tokens") or 0)
        conf = sidecar.get("attribution_confidence")
        if conf:
            confidence.add(str(conf))

    pooled_util = round(len(invoked_all) / max(len(loaded_all), 1), 4) if loaded_all else 0.0
    available = bool(mcp_records or sidecar_used)

    global_mcp = _mcp_metrics_block(util_samples, waste_total, confidence, len(mcp_records), total_traces)
    global_mcp["pooled_tool_utilization"] = pooled_util
    global_mcp["tools_loaded_distinct"] = len(loaded_all)
    global_mcp["tools_invoked_distinct"] = len(invoked_all)
    global_mcp["tools_unused_distinct"] = max(len(loaded_all) - len(invoked_all), 0)

    by_skill_mcp: dict[str, Any] = {}
    for skill, bucket in (agg.get("by_skill") or {}).items():
        if bucket.get("mcp_trace_count", 0) > 0 or bucket.get("mcp_schema_waste_tokens", 0) > 0:
            by_skill_mcp[skill] = {
                "mcp_tool_utilization": bucket.get("mcp_tool_utilization", 0.0),
                "mcp_schema_waste_tokens": bucket.get("mcp_schema_waste_tokens", 0),
                "mcp_trace_count": bucket.get("mcp_trace_count", 0),
                "attribution_confidence": bucket.get("attribution_confidence", "estimated"),
            }

    mcp_join = {
        "available": available,
        "degraded": not available,
        "sidecar_used": sidecar_used,
        "sidecar_path": ".runtime/token/context/mcp-context-latest.json",
        "traces_with_mcp": len(mcp_records),
        "mcp_trace_coverage_ratio": round(len(mcp_records) / max(total_traces, 1), 4),
        "global": global_mcp,
        "by_skill": by_skill_mcp,
        "low_utilization_ranking": low_util[:15],
        "unused_tools_distinct": sorted(loaded_all - invoked_all)[:20],
    }

    global_block = dict(agg.get("global") or {})
    if available:
        global_block["mcp"] = global_mcp

    return {**agg, "global": global_block, "mcp_join": mcp_join}


def discover_trace_files(repo_root: Path) -> list[tuple[Path, str]]:
    seen: set[Path] = set()
    out: list[tuple[Path, str]] = []

    def _add(path: Path, kind: str) -> None:
        key = path.resolve()
        if key in seen:
            return
        seen.add(key)
        out.append((path, kind))

    # Legacy per-skill layout (pre-centralization)
    for skill_dir in sorted(repo_root.glob("alicloud-*-ops")):
        if not skill_dir.is_dir():
            continue
        trace_dir = skill_dir / ".runtime" / "traces"
        if trace_dir.is_dir():
            for path in sorted(trace_dir.glob("*.json")):
                _add(path, "wrapper")
    # Centralized layout: .runtime/traces/<skill>/trace-*.json
    repo_traces = repo_root / ".runtime" / "traces"
    if repo_traces.is_dir():
        for path in sorted(repo_traces.glob("*.json")):
            _add(path, "wrapper")
        for path in sorted(repo_traces.glob("*/*.json")):
            _add(path, "wrapper")
    legacy = repo_root / "audit-results"
    if legacy.is_dir():
        for path in sorted(legacy.glob("gcl-trace-*.json")):
            _add(path, "gcl")
    audit_root = repo_root / ".runtime" / "audit"
    if audit_root.is_dir():
        for path in sorted(audit_root.rglob("gcl-trace-*.json")):
            _add(path, "gcl")
    return out


def discover_session_files(repo_root: Path) -> list[Path]:
    out: list[Path] = []
    runtime = repo_root / ".runtime"
    if runtime.is_dir():
        out.extend(sorted(runtime.glob("skillopt-session-*.json")))
        sessions_root = runtime / "sessions"
        if sessions_root.is_dir():
            out.extend(sorted(sessions_root.glob("*/*.json")))
    for skill_dir in sorted(repo_root.glob("alicloud-*-ops")):
        if not skill_dir.is_dir():
            continue
        legacy_rt = skill_dir / ".runtime"
        if legacy_rt.is_dir():
            out.extend(sorted(legacy_rt.glob("skillopt-session-*.json")))
    seen: set[Path] = set()
    deduped: list[Path] = []
    for path in out:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


@dataclass
class Bucket:
    trace_count: int = 0
    success_count: int = 0
    waste_count: int = 0
    waste_tokens: int = 0
    llm_usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    critic_tokens: int = 0
    agent_turn_tokens: int = 0
    unknown_agent_count: int = 0
    unknown_model_count: int = 0
    mcp_util_samples: list[float] = field(default_factory=list)
    mcp_waste_tokens: int = 0
    mcp_confidence: set[str] = field(default_factory=set)
    mcp_trace_count: int = 0

    def add(self, rec: NormalizedRecord) -> None:
        self.trace_count += 1
        if rec.success:
            self.success_count += 1
        if rec.waste:
            self.waste_count += 1
            self.waste_tokens += rec.llm_usage["total_tokens"]
        self.llm_usage = _add_usage(self.llm_usage, rec.llm_usage)
        self.critic_tokens += rec.critic_tokens
        self.agent_turn_tokens += rec.agent_turn_tokens
        if rec.coding_agent == "unknown":
            self.unknown_agent_count += 1
        if rec.model == "unknown":
            self.unknown_model_count += 1
        if rec.mcp:
            self.mcp_trace_count += 1
            util = rec.mcp.get("mcp_tool_utilization")
            if isinstance(util, int | float):
                self.mcp_util_samples.append(float(util))
            waste = rec.mcp.get("mcp_schema_waste_tokens")
            if isinstance(waste, int):
                self.mcp_waste_tokens += waste
            conf = rec.mcp.get("attribution_confidence")
            if conf:
                self.mcp_confidence.add(str(conf))

    def to_dict(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        total = self.llm_usage["total_tokens"]
        success = max(self.success_count, 1)
        payload: dict[str, Any] = {
            "trace_count": self.trace_count,
            "success_count": self.success_count,
            "waste_count": self.waste_count,
            "llm_usage": dict(self.llm_usage),
            "tokens_per_success": round(total / success, 2) if total else 0.0,
            "waste_ratio": round(self.waste_tokens / max(total, 1), 4) if total else 0.0,
            "critic_overhead_ratio": round(self.critic_tokens / max(total, 1), 4) if total else 0.0,
            "agent_skill_load_ratio": round(self.agent_turn_tokens / max(self.llm_usage["prompt_tokens"], 1), 4)
            if self.llm_usage["prompt_tokens"]
            else 0.0,
            "unknown_agent_ratio": round(self.unknown_agent_count / max(self.trace_count, 1), 4),
            "unknown_model_ratio": round(self.unknown_model_count / max(self.trace_count, 1), 4),
        }
        if self.mcp_util_samples or self.mcp_waste_tokens or self.mcp_trace_count:
            payload["mcp_trace_count"] = self.mcp_trace_count
            payload["mcp_trace_coverage_ratio"] = round(
                self.mcp_trace_count / max(self.trace_count, 1), 4
            )
            payload["mcp_tool_utilization"] = round(
                sum(self.mcp_util_samples) / max(len(self.mcp_util_samples), 1), 4
            ) if self.mcp_util_samples else 0.0
            payload["mcp_schema_waste_tokens"] = self.mcp_waste_tokens
            payload["attribution_confidence"] = _merge_confidence(self.mcp_confidence)
        if extra:
            payload.update(extra)
        return payload


def _merge_confidence(conf: set[str]) -> str:
    if not conf:
        return "estimated"
    if len(conf) == 1:
        return next(iter(conf))
    if conf == {"estimated"}:
        return "estimated"
    if conf <= {"estimated", "observed"}:
        return "mixed"
    return "mixed"


def _bucket_key_agent_model(rec: NormalizedRecord) -> str:
    return f"{rec.coding_agent}|{rec.model}"


def aggregate_records(records: Iterable[NormalizedRecord]) -> dict[str, Any]:
    global_b = Bucket()
    by_skill: defaultdict[str, Bucket] = defaultdict(Bucket)
    by_op: defaultdict[str, Bucket] = defaultdict(Bucket)
    by_agent_model: defaultdict[str, Bucket] = defaultdict(Bucket)
    by_turn: defaultdict[str, Bucket] = defaultdict(Bucket)
    agent_model_meta: dict[str, dict[str, str]] = {}

    for rec in records:
        global_b.add(rec)
        by_skill[rec.skill].add(rec)
        by_op[rec.operation].add(rec)
        key = _bucket_key_agent_model(rec)
        by_agent_model[key].add(rec)
        agent_model_meta[key] = {"coding_agent": rec.coding_agent, "model": rec.model}
        if rec.agent_turn_id:
            by_turn[rec.agent_turn_id].add(rec)

    out: dict[str, Any] = {
        "global": global_b.to_dict(),
        "by_skill": {k: v.to_dict() for k, v in sorted(by_skill.items())},
        "by_op": {k: v.to_dict() for k, v in sorted(by_op.items())},
        "by_agent_model": {
            k: v.to_dict(extra=agent_model_meta.get(k, {}))
            for k, v in sorted(by_agent_model.items())
        },
    }
    if by_turn:
        out["by_turn"] = {k: v.to_dict() for k, v in sorted(by_turn.items())}
    return out


def build_coverage(
    records: list[NormalizedRecord],
    sessions_scanned: int,
    l1_scan: dict[str, Any] | None = None,
    l2_scan: dict[str, Any] | None = None,
    mcp_join: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = len(records)
    with_usage = sum(1 for r in records if r.llm_usage["total_tokens"] > 0)
    with_mcp = sum(1 for r in records if r.mcp)
    unknown_agent = sum(1 for r in records if r.coding_agent == "unknown")
    unknown_model = sum(1 for r in records if r.model == "unknown")
    l1 = l1_scan or {}
    l2 = l2_scan or {}
    mcp = mcp_join or {}
    return {
        "version": ROLLUP_VERSION,
        "traces_scanned": total,
        "sessions_scanned": sessions_scanned,
        "traces_with_llm_usage": with_usage,
        "traces_with_mcp_metadata": with_mcp,
        "unknown_agent_traces": unknown_agent,
        "unknown_model_traces": unknown_model,
        "agent_coverage_ratio": round((total - unknown_agent) / max(total, 1), 4),
        "model_coverage_ratio": round((total - unknown_model) / max(total, 1), 4),
        "llm_usage_coverage_ratio": round(with_usage / max(total, 1), 4),
        "l1_join": {
            "available": l1.get("available", False),
            "entries_in_window": l1.get("entries_in_window", 0),
            "skills_with_l1": len(l1.get("skill_stats") or {}),
        },
        "l2_join": {
            "available": l2.get("available", False),
            "patterns_in_window": l2.get("patterns_in_window", 0),
        },
        "mcp_join": {
            "available": mcp.get("available", False),
            "traces_with_mcp": mcp.get("traces_with_mcp", 0),
            "sidecar_used": mcp.get("sidecar_used", False),
        },
    }


def enrich_records_from_sessions(
    records: list[NormalizedRecord],
    repo_root: Path,
    since: datetime,
) -> int:
    """Merge session-level MCP metadata when trace lacks mcp (non-fatal)."""
    sessions_scanned = 0
    session_mcp_by_id: dict[str, dict[str, Any]] = {}
    for path in discover_session_files(repo_root):
        data = _load_json(path)
        if not data:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < since:
            continue
        sessions_scanned += 1
        sid = str(data.get("session_id") or "")
        mcp = (data.get("context_metadata") or {}).get("mcp")
        if sid and isinstance(mcp, dict):
            session_mcp_by_id[sid] = mcp
    if not session_mcp_by_id:
        return sessions_scanned
    for rec in records:
        if rec.mcp or not rec.session_id:
            continue
        mcp = session_mcp_by_id.get(rec.session_id)
        if mcp:
            rec.mcp = mcp
    return sessions_scanned


def collect_records(
    repo_root: Path,
    since_days: int,
    *,
    mode: str = "full",
) -> tuple[list[NormalizedRecord], dict[str, Any]]:
    since = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
    counts: dict[str, Any] = {
        "wrapper_traces": 0,
        "gcl_traces": 0,
        "skipped_stale": 0,
        "skipped_invalid": 0,
        "incremental_mode": mode,
        "files_discovered": 0,
        "files_parsed": 0,
        "files_skipped": 0,
        "cache_records": 0,
    }

    cache: dict[str, NormalizedRecord] = {}
    indexed_files: dict[str, float] = {}
    discovered_rel: set[str] = set()
    prev_state = load_incremental_state(repo_root) or {}
    if mode == "incremental":
        cache = load_records_cache(repo_root, since)
        indexed_files = dict(prev_state.get("indexed_files") or {})
        counts["cache_records"] = len(cache)

    for path, kind in discover_trace_files(repo_root):
        counts["files_discovered"] += 1
        try:
            rel_path = str(path.relative_to(repo_root))
        except ValueError:
            rel_path = str(path)
        discovered_rel.add(rel_path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        mtime_ts = mtime.timestamp()

        if mode == "incremental":
            prev_mtime = indexed_files.get(rel_path)
            if prev_mtime is not None and abs(prev_mtime - mtime_ts) < 0.001 and rel_path in cache:
                counts["files_skipped"] += 1
                continue

        data = _load_json(path)
        if not data:
            counts["skipped_invalid"] += 1
            continue
        if kind == "wrapper":
            rec = normalize_wrapper_trace(data, path)
            counts["wrapper_traces"] += 1
        else:
            rec = normalize_gcl_trace(data, path)
            counts["gcl_traces"] += 1
        if rec is None:
            counts["skipped_invalid"] += 1
            continue
        ts = rec.timestamp or mtime
        if ts < since:
            counts["skipped_stale"] += 1
            if rel_path in cache:
                del cache[rel_path]
            indexed_files.pop(rel_path, None)
            continue
        rec.timestamp = ts
        rec.trace_path = rel_path
        cache[rel_path] = rec
        indexed_files[rel_path] = mtime_ts
        counts["files_parsed"] += 1

    for rel_path in list(cache.keys()):
        if rel_path not in discovered_rel:
            del cache[rel_path]
            indexed_files.pop(rel_path, None)

    indexed_files = {k: v for k, v in indexed_files.items() if k in cache}

    records = sorted(cache.values(), key=lambda r: r.timestamp or datetime.min.replace(tzinfo=timezone.utc))
    sessions = enrich_records_from_sessions(records, repo_root, since)
    counts["sessions_enriched"] = sessions
    counts["cache_records"] = len(cache)

    counts["incremental_state"] = {
        "version": INCREMENTAL_STATE_VERSION,
        "indexed_files": indexed_files,
        "last_mode": mode,
    }
    return records, counts


def build_baseline(repo_root: Path, current_global: dict[str, Any], since_days: int) -> dict[str, Any]:
    history_dir = token_root(repo_root) / "history"
    snapshots: list[dict[str, Any]] = []
    now = datetime.now(tz=timezone.utc)
    if history_dir.is_dir():
        for path in sorted(history_dir.glob("rollup-*.json")):
            data = _load_json(path)
            if not data:
                continue
            updated = _parse_ts(data.get("updated_at"))
            if updated and updated >= now - timedelta(days=30):
                snapshots.append(data)
    def _avg_global(days: int) -> dict[str, Any]:
        cutoff = now - timedelta(days=days)
        vals: list[dict[str, Any]] = []
        for snap in snapshots:
            updated = _parse_ts(snap.get("updated_at"))
            if updated and updated >= cutoff:
                g = (snap.get("rollup") or snap).get("global") or snap.get("global")
                if g:
                    vals.append(g)
        if not vals:
            return dict(current_global)
        keys = ("tokens_per_success", "waste_ratio", "critic_overhead_ratio")
        out: dict[str, Any] = {"sample_count": len(vals), "period_days": days}
        for key in keys:
            nums = [float(v.get(key) or 0) for v in vals]
            out[key] = round(sum(nums) / len(nums), 4)
        return out

    return {
        "version": ROLLUP_VERSION,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "baseline_7d": _avg_global(7),
        "baseline_30d": _avg_global(30),
        "current": {
            "tokens_per_success": current_global.get("tokens_per_success"),
            "waste_ratio": current_global.get("waste_ratio"),
            "critic_overhead_ratio": current_global.get("critic_overhead_ratio"),
        },
    }


def render_report(rollup: dict[str, Any], coverage: dict[str, Any]) -> str:
    g = rollup.get("global") or {}
    lines = [
        "# Token Efficiency Weekly Report",
        "",
        f"- Updated: {rollup.get('updated_at', 'n/a')}",
        f"- Window: last {rollup.get('since_days', 7)} days",
        "",
        "## Global",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Total tokens | {g.get('llm_usage', {}).get('total_tokens', 0)} |",
        f"| Traces | {g.get('trace_count', 0)} |",
        f"| tokens_per_success | {g.get('tokens_per_success', 0)} |",
        f"| waste_ratio | {g.get('waste_ratio', 0)} |",
        f"| critic_overhead_ratio | {g.get('critic_overhead_ratio', 0)} |",
        "",
        "## Coverage",
        "",
        f"- Agent coverage: {coverage.get('agent_coverage_ratio', 0)}",
        f"- Model coverage: {coverage.get('model_coverage_ratio', 0)}",
        f"- MCP metadata traces: {coverage.get('traces_with_mcp_metadata', 0)}",
        "",
        "## Top skills by tokens",
        "",
    ]
    by_skill = rollup.get("by_skill") or {}
    ranked = sorted(
        by_skill.items(),
        key=lambda kv: (kv[1].get("llm_usage") or {}).get("total_tokens", 0),
        reverse=True,
    )[:10]
    for skill, stats in ranked:
        tok = (stats.get("llm_usage") or {}).get("total_tokens", 0)
        lines.append(f"- `{skill}`: {tok} tokens ({stats.get('trace_count', 0)} traces)")
    lines.append("")

    l1_join = rollup.get("l1_join") or {}
    if l1_join.get("available"):
        lines.extend(
            [
                "## Expensive & unstable (L1 join)",
                "",
                "Score = `tokens_per_success × (1 - rubric_pass_rate)` — higher = costlier failures.",
                "",
            ]
        )
        for row in l1_join.get("expensive_unstable_ranking") or []:
            if row.get("expensive_unstable_score", 0) <= 0:
                continue
            lines.append(
                f"- `{row['skill']}`: score={row['expensive_unstable_score']} "
                f"(tps={row['tokens_per_success']}, pass_rate={row['rubric_pass_rate']})"
            )
        lines.append("")
    elif l1_join:
        lines.extend(["## L1 join", "", "- Layer 1 memory unavailable or empty in window (degraded).", ""])

    l2_join = rollup.get("l2_join") or {}
    if l2_join.get("waste_events_total", 0) > 0:
        lines.extend(
            [
                "## Waste attribution (L2 join)",
                "",
                f"- Attributed {l2_join.get('waste_events_attributed', 0)}/"
                f"{l2_join.get('waste_events_total', 0)} waste traces "
                f"(rate={l2_join.get('attribution_rate', 0)})",
                "",
            ]
        )
        for row in l2_join.get("by_trap") or []:
            lines.append(
                f"- `{row['skill']}` / `{row['operation']}`: {row['narrative']}"
            )
            if row.get("fix"):
                lines.append(f"  - fix: {row['fix'][:120]}")
        lines.append("")
    elif l2_join and not l2_join.get("available"):
        lines.extend(["## L2 join", "", "- Layer 2 reflexion unavailable or empty in window (degraded).", ""])

    mcp_join = rollup.get("mcp_join") or {}
    if mcp_join.get("available"):
        gm = mcp_join.get("global") or {}
        lines.extend(
            [
                "## MCP schema waste (X-18)",
                "",
                f"- Trace coverage: {mcp_join.get('traces_with_mcp', 0)} traces "
                f"({mcp_join.get('mcp_trace_coverage_ratio', 0)})",
                f"- Pooled utilization: {gm.get('pooled_tool_utilization', 0)} "
                f"({gm.get('tools_invoked_distinct', 0)}/{gm.get('tools_loaded_distinct', 0)} tools)",
                f"- Schema waste tokens: {gm.get('mcp_schema_waste_tokens', 0)}",
                "",
            ]
        )
        if mcp_join.get("sidecar_used"):
            lines.append("- Sidecar: `.runtime/token/context/mcp-context-latest.json` merged")
            lines.append("")
        for row in mcp_join.get("low_utilization_ranking") or []:
            lines.append(
                f"- `{row['skill']}` / `{row['operation']}`: util={row['mcp_tool_utilization']}, "
                f"waste_tokens={row['mcp_schema_waste_tokens']}"
            )
        unused = mcp_join.get("unused_tools_distinct") or []
        if unused:
            lines.append("")
            lines.append(f"- Unused tools (sample): {', '.join(unused[:8])}")
        lines.append("")
    elif mcp_join:
        lines.extend(["## MCP join", "", "- No MCP metadata in window (degraded).", ""])

    return "\n".join(lines)


def _atomic_write(path: Path, payload: dict[str, Any] | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(payload, str):
        tmp.write_text(payload, encoding="utf-8")
    else:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def rollup_apply(
    repo_root: Path,
    since_days: int = 7,
    apply: bool = False,
    *,
    full: bool = False,
    incremental: bool = False,
) -> dict[str, Any]:
    since = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
    mode = resolve_rollup_mode(repo_root, full, incremental)
    records, source_counts = collect_records(repo_root, since_days, mode=mode)
    agg = aggregate_records(records)
    l1_scan = scan_l1_skill_stats(repo_root, since)
    l2_scan = scan_l2_patterns(repo_root, since)
    agg = join_l1_into_rollup(agg, l1_scan)
    agg = join_l2_into_rollup(agg, records, l2_scan)
    sidecar = load_mcp_sidecar_snapshot(repo_root, since)
    agg = join_mcp_into_rollup(agg, records, sidecar)
    coverage = build_coverage(
        records,
        source_counts.get("sessions_enriched", 0),
        l1_scan,
        l2_scan,
        agg.get("mcp_join"),
    )
    now = datetime.now(tz=timezone.utc)
    rollup = {
        "version": ROLLUP_VERSION,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "since_days": since_days,
        "window": {
            "start": (now - timedelta(days=since_days)).isoformat().replace("+00:00", "Z"),
            "end": now.isoformat().replace("+00:00", "Z"),
        },
        "incremental": {
            "mode": mode,
            "files_parsed": int(source_counts.get("files_parsed") or 0),
            "files_skipped": int(source_counts.get("files_skipped") or 0),
            "cache_records": int(source_counts.get("cache_records") or 0),
        },
        "source_counts": source_counts,
        **agg,
    }
    baseline = build_baseline(repo_root, agg["global"], since_days)
    report_md = render_report(rollup, coverage)

    result = {
        "rollup": rollup,
        "baseline": baseline,
        "coverage": coverage,
        "report": report_md,
        "trace_records": len(records),
    }

    if not apply:
        joined = (agg.get("l1_join") or {}).get("skills_joined", 0)
        l2_attr = (agg.get("l2_join") or {}).get("waste_events_attributed", 0)
        waste_n = (agg.get("l2_join") or {}).get("waste_events_total", 0)
        mcp_n = (agg.get("mcp_join") or {}).get("traces_with_mcp", 0)
        _log(
            f"dry-run: {len(records)} trace records ({mode}), "
            f"{rollup['global']['llm_usage']['total_tokens']} total tokens, "
            f"L1 join {joined} skill(s), L2 waste attributed {l2_attr}/{waste_n}, "
            f"MCP traces {mcp_n}, skipped {rollup['incremental']['files_skipped']} file(s)"
        )
        return result

    root = token_root(repo_root)
    stamp = now.strftime("%Y%m%d")
    _atomic_write(root / "current" / "rollup.json", rollup)
    _atomic_write(root / "current" / "baseline.json", baseline)
    _atomic_write(root / "current" / "coverage.json", coverage)
    _atomic_write(root / "history" / f"rollup-{stamp}.json", {"updated_at": rollup["updated_at"], "rollup": rollup})
    _atomic_write(root / "reports" / f"efficiency-{stamp}.md", report_md)
    cache_by_path = {rec.trace_path: rec for rec in records if rec.trace_path}
    save_records_cache(repo_root, cache_by_path)
    inc_state = dict(source_counts.get("incremental_state") or {})
    inc_state["last_rollup_at"] = rollup["updated_at"]
    inc_state["rollup_version"] = ROLLUP_VERSION
    save_incremental_state(repo_root, inc_state)
    _log(
        f"applied: current/rollup.json ({len(records)} traces, {mode}, "
        f"{rollup['global']['llm_usage']['total_tokens']} tokens, "
        f"skipped {rollup['incremental']['files_skipped']} file(s))"
    )
    return result


def maintain_token_artifacts(repo_root: Path, history_keep_days: int = 30, apply: bool = False) -> dict[str, Any]:
    root = token_root(repo_root)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=history_keep_days)
    removed: list[str] = []
    for sub in ("history", "reports"):
        dir_path = root / sub
        if not dir_path.is_dir():
            continue
        for path in sorted(dir_path.iterdir()):
            if not path.is_file():
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                removed.append(str(path.relative_to(repo_root)))
                if apply:
                    path.unlink(missing_ok=True)
    _log(f"maintain: {'removed' if apply else 'would remove'} {len(removed)} token artifact(s)")
    return {"removed": removed, "history_keep_days": history_keep_days, "apply": apply}


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TEL Phase 5 — runtime token rollup")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("rollup", help="Aggregate traces into .runtime/token/current/")
    pr.add_argument("--repo-root", type=Path, default=None)
    pr.add_argument("--since-days", type=int, default=int(os.environ.get("TOKEN_ROLLUP_SINCE_DAYS", "7")))
    pr.add_argument("--apply", action="store_true", help="Write artifacts (default dry-run)")
    pr.add_argument("--full", action="store_true", help="Force full scan (rebuild incremental cache)")
    pr.add_argument(
        "--incremental",
        action="store_true",
        help="Force incremental scan (skip unchanged trace files when state exists)",
    )

    pm = sub.add_parser("maintain", help="Prune old token history/reports")
    pm.add_argument("--repo-root", type=Path, default=None)
    pm.add_argument(
        "--history-keep-days",
        type=int,
        default=int(os.environ.get("TOKEN_HISTORY_KEEP_DAYS", "30")),
    )
    pm.add_argument("--apply", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = resolve_repo_root(args.repo_root)
    if args.command == "rollup":
        rollup_apply(
            repo_root,
            since_days=args.since_days,
            apply=args.apply,
            full=args.full,
            incremental=args.incremental,
        )
        return 0
    if args.command == "maintain":
        maintain_token_artifacts(repo_root, history_keep_days=args.history_keep_days, apply=args.apply)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
