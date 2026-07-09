#!/usr/bin/env python3
"""
strategy_notify.py — Layer 3 AI Brief builders and notify gate.

Shared helpers for Layer 3 notification:
  - should_notify() — gate on actionable_items / high-confidence proposals
  - build_strategy_ai_brief() — Markdown attachment for AI agents
  - write_ai_brief_attachment() — persist AI Brief to disk

GitHub-native delivery (PR + Issue): strategy_github_notify.py

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_strategy import WORK_DIR  # noqa: E402

DEFAULT_BASELINE = Path("docs") / "strategy-baseline.json"
DEFAULT_ATTACHMENT_DIR = WORK_DIR
AI_BRIEF_FILENAME_PREFIX = "doctor-review-ai-brief"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [STRATEGY] {msg}", file=sys.stderr)


def _load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_strategy_ai_brief(baseline: dict[str, Any]) -> str:
    """Build AI-consumable Markdown attachment with full structured context."""
    gs = baseline.get("git_signals_summary", {})
    rs = baseline.get("runtime_signals_summary", {})
    generated = baseline.get("generated_at", "unknown")
    since_days = baseline.get("since_days", 7)
    actionable = baseline.get("actionable_items", [])
    proposals = baseline.get("rule_proposals", [])
    trends = baseline.get("skill_trends", {})
    hot = gs.get("hot_skills", [])
    hf_patterns = baseline.get("high_frequency_patterns", [])

    lines: list[str] = [
        "---",
        "document_type: layer3_strategy_review",
        "format_version: 1.0.0",
        f"generated_at: {generated}",
        f"review_window_days: {since_days}",
        f"actionable_count: {len(actionable)}",
        f"rule_proposal_count: {len(proposals)}",
        "purpose: ai_agent_consumption",
        "---",
        "",
        "# Layer 3 Strategy Review — AI Brief",
        "",
        "> Machine-readable weekly review bundle. Feed this file directly to an AI agent",
        "> for triage, rule drafting, or skill runbook updates.",
        "",
        "## Document Map",
        "",
        "| Section | Use |",
        "|---------|-----|",
        "| Actionable Items | Priority work queue — start here |",
        "| Rule Proposals | Candidate runbook / rubric changes (human review required) |",
        "| Git Signals | Recent artifact-evolution context (7d commits) |",
        "| Runtime Trends | Layer 1 execution stats when memory is available |",
        "| High-Frequency Patterns | Layer 2 candidates for H Detector promotion |",
        "| Suggested AI Workflow | Recommended next steps for the agent |",
        "",
        "## Metadata",
        "",
        f"- **generated_at**: `{generated}`",
        f"- **review_window_days**: {since_days}",
        f"- **git_commits**: {gs.get('commit_count', 0)}",
        f"- **git_bugfixes**: {gs.get('bugfix_count', 0)}",
        f"- **failure_patterns_parsed**: {rs.get('pattern_count', 0)}",
        f"- **layer1_memory_scanned**: {baseline.get('memory_available', False)}",
        "",
    ]

    lines.extend(["## Actionable Items", ""])
    if not actionable:
        lines.append("_No actionable items this week._")
    else:
        for i, item in enumerate(actionable, 1):
            lines.append(f"### {i}. {item.get('id', f'item-{i}')}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for key in ("severity", "type", "skill", "theme", "reason"):
                if item.get(key) is not None:
                    lines.append(f"| {key} | {item[key]} |")
            if item.get("delta") is not None:
                lines.append(f"| delta | {item['delta']} |")
            if item.get("count") is not None:
                lines.append(f"| count | {item['count']} |")
            actions = item.get("actions", [])
            if actions:
                lines.append("")
                lines.append("**actions:**")
                for act in actions:
                    lines.append(f"- {act}")
            lines.append("")

    lines.extend(["## Rule Proposals", ""])
    if not proposals:
        lines.append("_No rule proposals._")
    else:
        for p in proposals:
            lines.append(f"### {p.get('id', p.get('title', 'proposal'))}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for key in (
                "target_skill", "target_file", "proposal_type", "title",
                "confidence", "rationale", "suggested_action",
            ):
                if p.get(key):
                    lines.append(f"| {key} | {p[key]} |")
            refs = p.get("evidence_refs", [])
            if refs:
                lines.append("")
                lines.append("**evidence_refs:**")
                for ref in refs:
                    lines.append(f"- `{ref}`")
            lines.append("")

    lines.extend(["## Git Signals", ""])
    theme_clusters = gs.get("theme_clusters", {})
    if theme_clusters:
        lines.append("**theme_clusters:**")
        for theme, count in sorted(theme_clusters.items(), key=lambda x: -x[1]):
            lines.append(f"- `{theme}`: {count}")
        lines.append("")
    if hot:
        lines.append("| skill | commits | bugfixes |")
        lines.append("|-------|--------:|---------:|")
        for hs in hot:
            lines.append(
                f"| {hs.get('skill', '')} | {hs.get('commit_count', 0)} "
                f"| {hs.get('bugfix_count', 0)} |"
            )
        lines.append("")

    lines.extend(["## Runtime Trends (Layer 1)", ""])
    if not trends:
        lines.append("_No Layer 1 memory data in review window._")
    else:
        lines.append("| skill | total | failure_rate | risk_score | confidence |")
        lines.append("|-------|------:|-------------:|-----------:|------------|")
        for skill, t in sorted(trends.items(), key=lambda x: x[1].get("risk_score", 0), reverse=True):
            lines.append(
                f"| {skill} | {t.get('total', 0)} | {t.get('failure_rate', 0)} "
                f"| {t.get('risk_score', 0)} | {t.get('confidence', 'low')} |"
            )
        lines.append("")

    lines.extend(["## High-Frequency Patterns (Layer 2)", ""])
    if not hf_patterns:
        lines.append("_No patterns at promotion threshold._")
    else:
        for p in hf_patterns:
            lines.append(
                f"- **{p.get('skill', '?')}** / {p.get('category', '?')}: count={p.get('count', 0)}"
            )
        lines.append("")

    lines.extend([
        "## Suggested AI Workflow",
        "",
        "1. Triage **Actionable Items** by severity (high → medium → low).",
        "2. For each item, open the referenced skill under `alicloud-*-ops/`.",
        "3. Cross-check **Rule Proposals** against `docs/failure-patterns.md`.",
        "4. Draft PR changes to `references/cli-usage.md`, `rubric.md`, or SKILL.md — do not auto-merge.",
        "5. If H Detector promotion applies, file a follow-up for `gcl-spec.md` §14.",
        "",
        "## Raw Baseline Reference",
        "",
        "Full JSON snapshot: `docs/strategy-baseline.json`",
        "",
    ])
    return "\n".join(lines)


def _attachment_filename(baseline: dict[str, Any]) -> str:
    generated = baseline.get("generated_at", "")
    if generated and len(generated) >= 10:
        date_part = generated[:10]
    else:
        date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{AI_BRIEF_FILENAME_PREFIX}-{date_part}.md"


def write_ai_brief_attachment(
    baseline: dict[str, Any],
    output_dir: Path = DEFAULT_ATTACHMENT_DIR,
) -> Path:
    """Write AI brief Markdown to disk; return path."""
    content = build_strategy_ai_brief(baseline)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _attachment_filename(baseline)
    path.write_text(content, encoding="utf-8")
    _log(f"event=strategy_ai_brief result=success path={path} bytes={len(content.encode('utf-8'))}")
    return path


def should_notify(baseline: dict[str, Any]) -> tuple[bool, str]:
    actionable = baseline.get("actionable_items", [])
    high_proposals = [
        p for p in baseline.get("rule_proposals", [])
        if p.get("confidence") == "high"
    ]
    if actionable:
        return True, f"actionable_items={len(actionable)}"
    if high_proposals:
        return True, f"high_confidence_proposals={len(high_proposals)}"
    return False, "no_actionable_items"


def preview_ai_brief(baseline_path: Path = DEFAULT_BASELINE) -> int:
    """Print AI Brief to stdout (local preview)."""
    baseline = _load_baseline(baseline_path)
    if baseline is None:
        _log("event=strategy_ai_brief decision=skip reason=missing_baseline")
        return 1
    path = write_ai_brief_attachment(baseline)
    print(path.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Layer 3 AI Brief helpers (use strategy_github_notify.py for delivery)",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write and print AI Brief Markdown (no GitHub Issue)",
    )
    args = parser.parse_args()
    if args.dry_run:
        return preview_ai_brief(baseline_path=args.baseline)
    print(
        "Use strategy_github_notify.py for PR/Issue notification.\n"
        "Preview AI Brief: strategy_notify.py --dry-run",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
