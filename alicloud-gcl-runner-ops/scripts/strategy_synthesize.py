#!/usr/bin/env python3
"""
strategy_synthesize.py — Optional LLM synthesis of Layer 3 rule proposals.

When DOCTOR_LLM_ENABLED != true or API key is missing, writes empty proposals
and exits 0 (non-blocking for weekly job).

Python 3.10+ stdlib only (HTTP via urllib).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_strategy import _atomic_write_json, normalize_skill_name, refresh_report_from_baseline  # noqa: E402
from gcl_strategy import WRITE_AUTHORITY_GHA_GIT, WORK_DIR  # noqa: E402

DEFAULT_BASELINE = Path("docs") / "strategy-baseline.json"
DEFAULT_OUTPUT = WORK_DIR / "rule_proposals.json"

PROPOSAL_ALLOWED_KEYS = frozenset({
    "id", "target_skill", "target_file", "proposal_type", "title",
    "rationale", "evidence_refs", "confidence", "suggested_action",
})
ALLOWED_CONFIDENCE = frozenset({"low", "medium", "high"})
_PATCH_RE = re.compile(r"\b(diff|patch|```)\b", re.I)


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [STRATEGY] {msg}", file=sys.stderr)


def _doctor_env(name: str, *, legacy: str | None = None, default: str = "") -> str:
    """Read Doctor LLM env; fall back to legacy STRATEGY_LLM_* names."""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    if legacy:
        return os.environ.get(legacy, default).strip()
    return default


def _heuristic_proposals(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback proposals without LLM."""
    proposals: list[dict[str, Any]] = []
    for i, item in enumerate(baseline.get("actionable_items", [])[:5]):
        skill = item.get("skill") or "repo-wide"
        target = normalize_skill_name(skill) if skill != "repo-wide" else "alicloud-ecs-ops"
        if not target.startswith("alicloud-"):
            target = "alicloud-ecs-ops"
        proposals.append({
            "id": f"prop-heuristic-{i + 1:03d}",
            "target_skill": target,
            "target_file": "references/cli-usage.md",
            "proposal_type": item.get("type", "pre-flight"),
            "title": f"Address: {item.get('reason', '')[:80]}",
            "rationale": item.get("reason", ""),
            "evidence_refs": [f"actionable:{item.get('id', '')}"],
            "confidence": "medium" if item.get("severity") == "high" else "low",
            "suggested_action": "; ".join(item.get("actions", [])[:2]),
        })
    return _sanitize_proposals(proposals)


def _sanitize_proposals(raw: list[Any]) -> list[dict[str, Any]]:
    """Whitelist fields and reject patch-like LLM output."""
    clean: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        blob = json.dumps(item, ensure_ascii=False)
        if _PATCH_RE.search(blob):
            _log("event=strategy_synthesize sanitize=skip reason=patch_like_content")
            continue
        row: dict[str, Any] = {}
        for key in PROPOSAL_ALLOWED_KEYS:
            if key not in item:
                continue
            val = item[key]
            if key == "confidence":
                conf = str(val).lower()
                if conf not in ALLOWED_CONFIDENCE:
                    continue
                row[key] = conf
            elif key == "evidence_refs":
                if isinstance(val, list):
                    row[key] = [str(v) for v in val[:10]]
            elif key == "target_skill":
                normalized = normalize_skill_name(str(val))
                row[key] = normalized if normalized else str(val)[:500]
            else:
                row[key] = str(val)[:500]
        if row.get("title") and row.get("target_skill"):
            clean.append(row)
    return clean[:5]


def _llm_proposals(baseline: dict[str, Any], endpoint: str, api_key: str, model: str) -> list[dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You produce 0-5 rule proposals as JSON array. Each object must have: "
                    "id, target_skill, target_file, proposal_type, title, rationale, "
                    "evidence_refs, confidence, suggested_action. No patch diffs."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "actionable_items": baseline.get("actionable_items", [])[:10],
                    "git_summary": baseline.get("git_signals_summary", {}),
                }, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if isinstance(parsed, dict) and "proposals" in parsed:
        return _sanitize_proposals(parsed["proposals"])
    if isinstance(parsed, list):
        return _sanitize_proposals(parsed)
    return []


def synthesize(
    baseline_path: Path = DEFAULT_BASELINE,
    output_path: Path = DEFAULT_OUTPUT,
) -> int:
    if not baseline_path.exists():
        _log("event=strategy_synthesize decision=skip reason=missing_baseline")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not baseline.get("actionable_items"):
        _log("event=strategy_synthesize decision=skip reason=no_actionable_items")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"proposals": []}\n', encoding="utf-8")
        return 0

    enabled = _doctor_env("DOCTOR_LLM_ENABLED", legacy="STRATEGY_LLM_ENABLED").lower() == "true"
    api_key = _doctor_env("DOCTOR_LLM_API_KEY", legacy="STRATEGY_LLM_API_KEY")
    endpoint = _doctor_env(
        "DOCTOR_LLM_ENDPOINT",
        legacy="STRATEGY_LLM_ENDPOINT",
        default="https://api.openai.com/v1/chat/completions",
    )
    model = _doctor_env("DOCTOR_LLM_MODEL", legacy="STRATEGY_LLM_MODEL", default="gpt-4o-mini")

    proposals: list[dict[str, Any]] = []
    if enabled and api_key:
        try:
            proposals = _llm_proposals(baseline, endpoint, api_key, model)
            _log(f"event=strategy_synthesize result=success source=llm count={len(proposals)}")
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as exc:
            _log(f"event=strategy_synthesize result=fallback reason={exc}")
            proposals = _heuristic_proposals(baseline)
    else:
        proposals = _heuristic_proposals(baseline)
        _log(f"event=strategy_synthesize result=success source=heuristic count={len(proposals)}")

    baseline["rule_proposals"] = proposals
    _atomic_write_json(baseline_path, baseline)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"proposals": proposals, "generated_at": datetime.now(timezone.utc).isoformat()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    report_path = baseline_path.parent / "strategy-report.md"
    if baseline.get("write_authority") == WRITE_AUTHORITY_GHA_GIT:
        _log("event=strategy_synthesize report=skipped reason=gha_git_review_no_baseline_write")
    else:
        refresh_report_from_baseline(baseline_path, output_path=report_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize Layer 3 rule proposals")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    return synthesize(baseline_path=args.baseline, output_path=args.output)


if __name__ == "__main__":
    sys.exit(main())
