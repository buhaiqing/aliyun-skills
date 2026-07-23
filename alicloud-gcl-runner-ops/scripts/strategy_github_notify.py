#!/usr/bin/env python3
"""
strategy_github_notify.py — Layer 3 GitHub-native notification.

Uses GitHub notifications (PR + optional Issue) instead of SMTP email:
  - PR body: full strategy-report.md + collapsible AI Brief
  - Issue: created only when actionable_items > 0 (or high-confidence proposals)

Requires `gh` CLI and GH_TOKEN (or GITHUB_TOKEN) when --apply is set.

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_strategy import WORK_DIR, strategy_store  # noqa: E402
from strategy_notify import (  # noqa: E402
    should_notify,
    write_ai_brief_attachment,
)

DEFAULT_BASELINE = Path("docs") / "strategy-baseline.json"
DEFAULT_REPORT = Path("docs") / "strategy-report.md"
DEFAULT_WORK_DIR = WORK_DIR
ISSUE_LABEL = "layer3-strategy-review"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [STRATEGY] {msg}", file=sys.stderr)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _persist_notification(
    baseline: dict[str, Any],
    baseline_path: Path,
    notification: dict[str, Any],
) -> None:
    baseline["notification"] = notification
    strategy_store(baseline, path=baseline_path)


def build_pr_body(report_path: Path, baseline: dict[str, Any], ai_brief_md: str) -> str:
    """Build Pull Request body with full report + AI Brief."""
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "_Report file missing._"
    generated = baseline.get("generated_at", "unknown")
    actionable_count = len(baseline.get("actionable_items", []))

    lines = [
        "## Weekly Layer 3 Strategy Review",
        "",
        "> GitHub notifies repository **watchers** when this PR is opened or updated.",
        f"> Generated: `{generated}` · Actionable items: **{actionable_count}**",
        "",
        "### Human-readable report",
        "",
        report_text.rstrip(),
        "",
        "<details>",
        "<summary><strong>AI Brief</strong> (machine-readable — for agents)</summary>",
        "",
        ai_brief_md.rstrip(),
        "",
        "</details>",
        "",
        "---",
        "",
        "Artifacts in this PR:",
        "",
        "- `docs/strategy-baseline.json`",
        "- `docs/strategy-report.md`",
        "",
    ]
    return "\n".join(lines) + "\n"


def _issue_machine_payload(baseline: dict[str, Any], reason: str) -> dict[str, Any]:
    """Compact JSON-serializable payload for AI agent consumption."""
    actionable = baseline.get("actionable_items", [])
    high_proposals = [
        {
            "id": p.get("id"),
            "target_skill": p.get("target_skill"),
            "title": p.get("title"),
            "confidence": p.get("confidence"),
            "rationale": p.get("rationale"),
            "suggested_action": p.get("suggested_action"),
            "evidence_refs": p.get("evidence_refs", [])[:5],
        }
        for p in baseline.get("rule_proposals", [])
        if p.get("confidence") == "high"
    ]
    queue = []
    for item in actionable:
        queue.append({
            "id": item.get("id"),
            "severity": item.get("severity"),
            "type": item.get("type"),
            "skill": item.get("skill"),
            "theme": item.get("theme"),
            "operation": item.get("operation"),
            "reason": item.get("reason"),
            "delta": item.get("delta"),
            "count": item.get("count"),
            "actions": item.get("actions", [])[:5],
        })
    return {
        "document_type": "layer3_strategy_issue",
        "format_version": "1.0.0",
        "generated_at": baseline.get("generated_at"),
        "review_window_days": baseline.get("since_days", 7),
        "trigger": reason,
        "actionable_count": len(actionable),
        "high_confidence_proposal_count": len(high_proposals),
        "baseline_path": "docs/strategy-baseline.json",
        "report_path": "docs/strategy-report.md",
        "actionable_items": queue,
        "rule_proposals_high_confidence": high_proposals,
    }


def build_issue_body(baseline: dict[str, Any], ai_brief_md: str, reason: str) -> str:
    """Build Issue body optimized for AI agents (frontmatter + JSON queue + human summary)."""
    generated = baseline.get("generated_at", "unknown")
    actionable = baseline.get("actionable_items", [])
    high_proposals = [
        p for p in baseline.get("rule_proposals", [])
        if p.get("confidence") == "high"
    ]
    payload = _issue_machine_payload(baseline, reason)
    payload_json = json.dumps(payload, indent=2, ensure_ascii=False)

    lines = [
        "---",
        "document_type: layer3_strategy_issue",
        "format_version: 1.0.0",
        f"generated_at: {generated}",
        f"trigger: {reason}",
        f"actionable_count: {len(actionable)}",
        "purpose: ai_agent_triage",
        "audience: human,ai_agent",
        "---",
        "",
        "# Layer 3 Strategy Review — Action Required",
        "",
        "> **AI agents:** Start with YAML frontmatter above, then **`## Machine-readable queue`** (JSON).",
        "> Use stable `id` fields to reference items. Do not auto-merge runbook changes — open a PR for human review.",
        "",
        "## Machine-readable queue",
        "",
        "```json",
        payload_json,
        "```",
        "",
        "## Actionable items (human view)",
        "",
    ]

    if actionable:
        for item in actionable:
            item_id = item.get("id", "unknown")
            sev = item.get("severity", "info").upper()
            lines.append(f"### `{item_id}` · {sev}")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for key in ("type", "skill", "theme", "operation", "reason", "delta", "count"):
                if item.get(key) is not None:
                    lines.append(f"| {key} | {item[key]} |")
            actions = item.get("actions", [])
            if actions:
                lines.append("")
                lines.append("**actions:**")
                for act in actions:
                    lines.append(f"- {act}")
            lines.append("")
    else:
        lines.append("_No actionable items; high-confidence rule proposals triggered this issue._")
        lines.append("")

    if high_proposals:
        lines.extend(["## High-confidence rule proposals", ""])
        for p in high_proposals:
            lines.append(f"### `{p.get('id', p.get('title', 'proposal'))}`")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            for key in ("target_skill", "target_file", "title", "confidence", "rationale", "suggested_action"):
                if p.get(key):
                    lines.append(f"| {key} | {p[key]} |")
            lines.append("")

    lines.extend([
        "## Suggested agent workflow",
        "",
        "1. Load JSON queue — triage by `severity` (high → medium → low).",
        "2. For each item, open `alicloud-*-ops/` skill directory referenced in `skill`.",
        "3. Cross-check `docs/failure-patterns.md` and Layer 1 memory under `.runtime/memory/`.",
        "4. Draft PR edits to `references/cli-usage.md`, `rubric.md`, or `SKILL.md`.",
        "5. Comment on this issue with item `id` + planned fix; close when done or deferred.",
        "",
        "## Full AI Brief",
        "",
        ai_brief_md.rstrip(),
        "",
        "---",
        "",
        "_Automated weekly Layer 3 review. Repository watchers receive GitHub notifications when this issue is created._",
        "",
    ])
    return "\n".join(lines) + "\n"


def _issue_title(baseline: dict[str, Any], reason: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    actionable_count = len(baseline.get("actionable_items", []))
    if actionable_count:
        return f"[Strategy Review] {actionable_count} actionable item(s) — {date_str}"
    return f"[Strategy Review] high-confidence proposals — {date_str}"


def _run_gh(args: list[str], repo: str | None = None) -> str:
    cmd = ["gh", *args]
    if repo:
        cmd.extend(["--repo", repo])
    env = os.environ.copy()
    token = env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")
    if token:
        env["GH_TOKEN"] = token
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "gh command failed")
    return result.stdout.strip()


def create_github_issue(
    title: str,
    body_path: Path,
    *,
    repo: str | None = None,
    label: str | None = ISSUE_LABEL,
) -> str:
    """Create a GitHub Issue; return issue URL."""
    args = ["issue", "create", "--title", title, "--body-file", str(body_path)]
    if label:
        args.extend(["--label", label])
    url = _run_gh(args, repo=repo)
    if not url.startswith("http"):
        raise RuntimeError(f"unexpected gh output: {url!r}")
    return url


def github_notify(
    baseline_path: Path = DEFAULT_BASELINE,
    report_path: Path = DEFAULT_REPORT,
    pr_body_out: Path | None = None,
    work_dir: Path = DEFAULT_WORK_DIR,
    *,
    apply: bool = False,
    dry_run: bool = False,
    repo: str | None = None,
) -> int:
    baseline = _load_json(baseline_path)
    if baseline is None:
        _log("event=strategy_github_notify decision=skip reason=missing_baseline")
        return 0

    work_dir.mkdir(parents=True, exist_ok=True)
    ai_brief_path = write_ai_brief_attachment(baseline, output_dir=work_dir)
    ai_brief_md = ai_brief_path.read_text(encoding="utf-8")

    pr_body = build_pr_body(report_path, baseline, ai_brief_md)
    out_pr = pr_body_out or (work_dir / "pr-body.md")
    out_pr.parent.mkdir(parents=True, exist_ok=True)
    out_pr.write_text(pr_body, encoding="utf-8")
    _log(f"event=strategy_github_notify pr_body=written path={out_pr} bytes={len(pr_body.encode('utf-8'))}")

    do_issue, reason = should_notify(baseline)
    issue_url: str | None = None

    if do_issue:
        issue_body = build_issue_body(baseline, ai_brief_md, reason)
        issue_body_path = work_dir / "issue-body.md"
        issue_body_path.write_text(issue_body, encoding="utf-8")
        title = _issue_title(baseline, reason)

        if dry_run:
            _log(f"event=strategy_github_notify decision=dry_run issue=would_create reason={reason}")
            print(f"--- Issue title ---\n{title}\n")
            print(f"--- Issue body ({issue_body_path}) ---\n")
            print(issue_body[:3000])
            if len(issue_body) > 3000:
                print("\n... (truncated) ...")
        elif apply:
            try:
                issue_url = create_github_issue(title, issue_body_path, repo=repo)
                _log(f"event=strategy_github_notify issue=created url={issue_url} reason={reason}")
            except RuntimeError as exc:
                err = str(exc)
                if "could not add label" in err.lower() or "label" in err.lower():
                    _log("event=strategy_github_notify issue=retry reason=label_missing")
                    issue_url = create_github_issue(title, issue_body_path, repo=repo, label=None)
                    _log(f"event=strategy_github_notify issue=created url={issue_url} reason={reason}")
                else:
                    _log(f"event=strategy_github_notify issue=failed reason={exc}")
                    return 1
        else:
            _log(f"event=strategy_github_notify issue=skipped reason=apply_not_set actionable={reason}")
    else:
        _log("event=strategy_github_notify issue=skipped reason=no_actionable_items")

    notification: dict[str, Any] = {
        "channel": "github",
        "reason": reason if do_issue else "no_actionable_items",
        "pr_body_path": str(out_pr),
        "ai_brief_path": str(ai_brief_path),
        "issue_created": bool(issue_url),
    }
    if issue_url:
        notification["issue_url"] = issue_url

    _persist_notification(baseline, baseline_path, notification)

    if dry_run:
        print(f"\n--- PR body ({out_pr}) preview ---\n")
        print(pr_body[:2500])
        if len(pr_body) > 2500:
            print("\n... (truncated) ...")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Layer 3 GitHub-native notification (PR body + Issue)")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--pr-body-out", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--repo", type=str, default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--apply", action="store_true", help="Create GitHub Issue via gh CLI")
    parser.add_argument("--dry-run", action="store_true", help="Print bodies; do not call gh")
    args = parser.parse_args()

    return github_notify(
        baseline_path=args.baseline,
        report_path=args.report,
        pr_body_out=args.pr_body_out,
        work_dir=args.work_dir,
        apply=args.apply,
        dry_run=args.dry_run,
        repo=args.repo,
    )


if __name__ == "__main__":
    sys.exit(main())
