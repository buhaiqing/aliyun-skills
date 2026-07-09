#!/usr/bin/env python3
"""
memory_preflight.py — Unified R2 pre-flight memory retrieval (Layers 1–3).

Single entry point for orchestrators and gcl_runner.py to fetch:
  - recent_executions  (Layer 1 — memory_retrieve)
  - known_traps        (Layer 2 — reflexion_retrieve → {{known_traps}})
  - success_patterns   (Layer 2+ — success_retrieve → {{success_patterns}})
  - strategy_hints     (Layer 3 — strategy_retrieve → {{strategy_hints}})

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_memory import DEFAULT_MEMORY_ROOT, memory_retrieve  # noqa: E402
from gcl_reflexion import (  # noqa: E402
    format_known_traps,
    format_success_patterns,
    reflexion_retrieve,
    success_retrieve,
)
from gcl_strategy import BASELINE_PATH, strategy_retrieve  # noqa: E402

PREFLIGHT_VERSION = "1.0.0"
DEFAULT_TRAPS_MAX_CHARS = int(os.environ.get("GCL_KNOWN_TRAPS_MAX_CHARS", "800"))
DEFAULT_STRATEGY_MAX_CHARS = int(os.environ.get("GCL_STRATEGY_HINTS_MAX_CHARS", "800"))
DEFAULT_RECENT_MAX_CHARS = int(os.environ.get("GCL_RECENT_EXECUTIONS_MAX_CHARS", "600"))
DEFAULT_SUCCESS_MAX_CHARS = int(os.environ.get("GCL_SUCCESS_PATTERNS_MAX_CHARS", "600"))


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [MEMORY-PREFLIGHT] {msg}", file=sys.stderr)


def _resolve_skills_root(skills_root: Path | None) -> Path:
    if skills_root is not None:
        return skills_root
    env = os.environ.get("ALIYUN_SKILLS_ROOT")
    if env:
        return Path(env)
    candidate = _SCRIPT_DIR.parent.parent
    if (candidate / "alicloud-gcl-runner-ops" / "scripts" / "gcl_runner.py").is_file():
        return candidate
    return _SCRIPT_DIR.parent


def _matches_tag_filter(entry_tags: list[dict[str, Any]], tag_filter: dict[str, str] | None) -> bool:
    """Return True if entry tags satisfy all key=value pairs in tag_filter.

    Empty/None filter matches everything (zero-regression for callers that
    don't supply a tag filter).
    """
    if not tag_filter:
        return True
    if not entry_tags:
        return False
    flat = {str(t.get("key", "")): str(t.get("value", "")) for t in entry_tags if isinstance(t, dict)}
    for k, v in tag_filter.items():
        if flat.get(str(k)) != str(v):
            return False
    return True


def _entry_matches_rg(entry: dict[str, Any], resource_group_id: str | None) -> bool:
    """Layer 1/2 entries without RG are repo-wide and match any RG filter.

    Only entries that explicitly record a different RG are excluded. This
    preserves the legacy "no RG info → include" behaviour and avoids zero-data
    surprises on first rollouts.
    """
    if not resource_group_id:
        return True
    entry_rg = entry.get("resource_group_id")
    if entry_rg is None or entry_rg == "":
        return True
    return str(entry_rg) == str(resource_group_id)


def _scope_prefix(
    resource_group_id: str | None,
    tag_filter: dict[str, str] | None,
) -> str:
    """Build a short ``scope: rg=..., tags={k:v}`` header line."""
    if not resource_group_id and not tag_filter:
        return ""
    parts: list[str] = []
    if resource_group_id:
        parts.append(f"rg={resource_group_id}")
    if tag_filter:
        tag_repr = ",".join(f"{k}:{v}" for k, v in sorted(tag_filter.items()))
        parts.append(f"tags={{ {tag_repr} }}")
    return f"scope: {', '.join(parts)}"


def format_recent_executions(
    entries: list[dict[str, Any]],
    max_chars: int = DEFAULT_RECENT_MAX_CHARS,
    resource_group_id: str | None = None,
    tag_filter: dict[str, str] | None = None,
) -> str:
    """Format Layer 1 entries as prompt-ready text.

    When ``resource_group_id`` / ``tag_filter`` are provided and at least one
    matching entry survives the filter, the text is prefixed with a ``scope:``
    line so downstream prompts can show "you asked for this scope".
    """
    if not entries:
        scope = _scope_prefix(resource_group_id, tag_filter)
        if scope:
            return f"{scope}\n(none — no recent executions in Layer 1 memory)"
        return "(none — no recent executions in Layer 1 memory)"

    filtered: list[dict[str, Any]] = []
    for e in entries:
        if not _entry_matches_rg(e, resource_group_id):
            continue
        if not _matches_tag_filter(e.get("tags") or [], tag_filter):
            continue
        filtered.append(e)

    if not filtered:
        scope = _scope_prefix(resource_group_id, tag_filter)
        if scope:
            return f"{scope}\n(none — no Layer 1 entries match this scope)"
        return "(none — no recent executions in Layer 1 memory)"

    lines: list[str] = []
    scope = _scope_prefix(resource_group_id, tag_filter)
    if scope:
        lines.append(scope)
    for e in filtered:
        status = e.get("gcl_status", "?")
        op = e.get("operation", "?")
        ts = e.get("timestamp", "")[:19]
        iters = e.get("iterations", 0)
        passed = e.get("rubric_pass", False)
        line = f"- {ts} op={op} status={status} pass={passed} iter={iters}"
        scores = e.get("scores") or {}
        if scores:
            low = [k for k, v in scores.items() if isinstance(v, (int, float)) and v < 0.8]
            if low:
                line += f" low_dims={','.join(low)}"
        lines.append(line)

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rsplit("\n", 1)[0] + "..."


def format_strategy_hints(
    hints: dict[str, Any],
    max_chars: int = DEFAULT_STRATEGY_MAX_CHARS,
    resource_group_id: str | None = None,
    tag_filter: dict[str, str] | None = None,
) -> str:
    """Format Layer 3 strategy_retrieve output as ``{{strategy_hints}}`` text.

    When ``resource_group_id`` is set and ``strategy_retrieve`` returned a
    non-empty result, a ``scope:`` line is prepended so the LLM can see the
    requested RG scope.
    """
    if hints.get("empty"):
        return "(none — strategy baseline not available)"

    lines: list[str] = []
    rg = hints.get("rg_context") or resource_group_id
    scope = _scope_prefix(rg, tag_filter)
    has_content = bool(hints.get("skill_risk") or hints.get("preventive_actions")
                       or hints.get("rule_hints"))
    if scope and has_content:
        lines.append(scope)
    risk = hints.get("skill_risk")
    if risk:
        lines.append(
            f"- risk_score={risk.get('risk_score')} "
            f"failure_rate={risk.get('failure_rate')} "
            f"confidence={risk.get('confidence')}"
        )
    for act in hints.get("preventive_actions") or []:
        lines.append(f"- action: {act}")
    for hint in hints.get("rule_hints") or []:
        lines.append(f"- rule_hint: {hint}")
    if hints.get("per_rg_data") is False:
        lines.append("- (no per-RG data — falling back to general hints)")
    if hints.get("truncated"):
        lines.append("- (truncated to fit token budget)")

    if not lines:
        return "(none — no strategy hints for this skill/operation)"

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rsplit("\n", 1)[0] + "..."


def _parse_tag_filter(raw: str | None) -> dict[str, str] | None:
    """Parse ``--tag-filter k1=v1,k2=v2`` into a dict (or None)."""
    if not raw:
        return None
    out: dict[str, str] = {}
    for chunk in str(raw).split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        k, _, v = chunk.partition("=")
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out or None


def preflight_retrieve(
    skill: str,
    operation: str | None = None,
    skills_root: Path | None = None,
    memory_top_k: int = 3,
    traps_top_k: int = 5,
    success_top_k: int = 3,
    traps_max_chars: int = DEFAULT_TRAPS_MAX_CHARS,
    success_max_chars: int = DEFAULT_SUCCESS_MAX_CHARS,
    strategy_max_chars: int = DEFAULT_STRATEGY_MAX_CHARS,
    recent_max_chars: int = DEFAULT_RECENT_MAX_CHARS,
    baseline_path: Path | None = None,
    memory_root: Path | None = None,
    reflexion_root: Path | None = None,
    resource_group_id: str | None = None,
    tag_filter: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Unified pre-flight retrieval for R2 injection.

    When ``resource_group_id`` and/or ``tag_filter`` are provided, results
    from Layers 1/2 are filtered to that scope and the formatted slots
    include a ``scope:`` line so the LLM can see what was requested.
    """
    root = _resolve_skills_root(skills_root)
    mem_root = memory_root or root / DEFAULT_MEMORY_ROOT
    baseline = baseline_path or root / BASELINE_PATH
    refl_root = reflexion_root or root / ".runtime" / "reflexion"

    # Pull a wider window when RG/Tags are in play so we still have a chance
    # of producing matches after filtering. Bounded to keep memory pressure
    # predictable; callers can still override the top_k knobs.
    fetch_top_k = memory_top_k
    if resource_group_id or tag_filter:
        fetch_top_k = max(memory_top_k, memory_top_k * 4)

    recent = memory_retrieve(
        skill,
        operation=operation,
        top_k=fetch_top_k,
        memory_root=mem_root,
    )
    traps = reflexion_retrieve(
        skill,
        operation=operation,
        top_k=traps_top_k,
        root=refl_root,
    )
    successes = success_retrieve(
        skill,
        operation=operation,
        top_k=success_top_k,
        root=refl_root,
    )
    strategy = strategy_retrieve(
        skill,
        operation=operation,
        max_chars=strategy_max_chars,
        baseline_path=baseline,
        resource_group_id=resource_group_id,
    )

    slots = {
        "known_traps": format_known_traps(traps, max_chars=traps_max_chars),
        "success_patterns": format_success_patterns(
            successes, max_chars=success_max_chars
        ),
        "strategy_hints": format_strategy_hints(
            strategy, max_chars=strategy_max_chars,
            resource_group_id=resource_group_id,
            tag_filter=tag_filter,
        ),
        "recent_executions": format_recent_executions(
            recent, max_chars=recent_max_chars,
            resource_group_id=resource_group_id,
            tag_filter=tag_filter,
        ),
    }

    return {
        "version": PREFLIGHT_VERSION,
        "skill": skill,
        "operation": operation,
        "scope": {
            "resource_group_id": resource_group_id,
            "tag_filter": tag_filter or None,
        },
        "empty": not recent and not traps and not successes and strategy.get("empty", False),
        "recent_executions": recent,
        "known_traps": traps,
        "success_patterns": successes,
        "strategy_hints": strategy,
        "slots": slots,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="R2 unified memory pre-flight retrieval (Layers 1–3)",
    )
    parser.add_argument("--skill", required=True, help="Skill name (e.g. alicloud-ecs-ops)")
    parser.add_argument("--operation", default=None, help="Optional operation filter")
    parser.add_argument("--skills-root", type=Path, default=None)
    parser.add_argument("--memory-top-k", type=int, default=3)
    parser.add_argument("--traps-top-k", type=int, default=5)
    parser.add_argument("--success-top-k", type=int, default=3)
    parser.add_argument(
        "--resource-group-id",
        default=None,
        help="Optional RG filter — Layer 1/2 entries outside this RG are "
             "excluded and {{strategy_hints}} is filtered to RG-tagged rows.",
    )
    parser.add_argument(
        "--tag-filter",
        default=None,
        help="Optional tag filter (k1=v1,k2=v2) — only Layer 1 entries whose "
             "tags match every key=value pair are returned.",
    )
    parser.add_argument("--format", choices=["json", "slots"], default="json",
                        help="'slots' prints R2 prompt slots including {{success_patterns}}")
    args = parser.parse_args(argv)

    result = preflight_retrieve(
        skill=args.skill,
        operation=args.operation,
        skills_root=args.skills_root,
        memory_top_k=args.memory_top_k,
        traps_top_k=args.traps_top_k,
        success_top_k=args.success_top_k,
        resource_group_id=args.resource_group_id,
        tag_filter=_parse_tag_filter(args.tag_filter),
    )

    if args.format == "slots":
        print("=== {{recent_executions}} ===")
        print(result["slots"]["recent_executions"])
        print("=== {{known_traps}} ===")
        print(result["slots"]["known_traps"])
        print("=== {{success_patterns}} ===")
        print(result["slots"]["success_patterns"])
        print("=== {{strategy_hints}} ===")
        print(result["slots"]["strategy_hints"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    _log(
        f"event=preflight_retrieve skill={args.skill} op={args.operation or 'all'} "
        f"recent={len(result['recent_executions'])} traps={len(result['known_traps'])} "
        f"success={len(result['success_patterns'])} empty={result['empty']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
