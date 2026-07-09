#!/usr/bin/env python3
"""Integration tests for strategy_github_notify.py — PR body + Issue via gh CLI."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import strategy_github_notify  # noqa: E402
import strategy_notify  # noqa: E402


def _sample_baseline() -> dict:
    return {
        "generated_at": "2026-06-21T12:00:00Z",
        "since_days": 7,
        "git_signals_summary": {"commit_count": 5, "bugfix_count": 1, "hot_skills": []},
        "runtime_signals_summary": {"pattern_count": 0},
        "actionable_items": [{
            "id": "A1-test",
            "severity": "high",
            "skill": "alicloud-ecs-ops",
            "reason": "failure rate spike",
            "actions": ["Review cli-usage.md"],
        }],
        "rule_proposals": [],
        "skill_trends": {},
        "high_frequency_patterns": [],
        "memory_available": False,
    }


class StrategyGithubIntegrationTests(unittest.TestCase):
    def _write_files(self, tmp: str, baseline: dict | None = None) -> tuple[Path, Path, Path]:
        root = Path(tmp)
        baseline_path = root / "baseline.json"
        report_path = root / "report.md"
        work_dir = root / "work"
        baseline_path.write_text(json.dumps(baseline or _sample_baseline(), indent=2), encoding="utf-8")
        report_path.write_text(
            "# Strategy Report\n\n## Weekly Summary\n\n- Actionable items: **1**\n",
            encoding="utf-8",
        )
        return baseline_path, report_path, work_dir

    def test_pr_body_includes_report_and_ai_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, report_path, work_dir = self._write_files(tmp)
            pr_out = work_dir / "pr-body.md"
            rc = strategy_github_notify.github_notify(
                baseline_path=baseline_path,
                report_path=report_path,
                pr_body_out=pr_out,
                work_dir=work_dir,
                apply=False,
            )
            self.assertEqual(rc, 0)
            body = pr_out.read_text(encoding="utf-8")
            self.assertIn("Weekly Layer 3 Strategy Review", body)
            self.assertIn("# Strategy Report", body)
            self.assertIn("document_type: layer3_strategy_review", body)
            self.assertIn("A1-test", body)

            saved = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["notification"]["channel"], "github")
            self.assertFalse(saved["notification"]["issue_created"])

    @mock.patch.object(strategy_github_notify, "create_github_issue")
    def test_creates_issue_when_actionable(self, mock_create: mock.Mock) -> None:
        mock_create.return_value = "https://github.com/org/repo/issues/42"
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, report_path, work_dir = self._write_files(tmp)
            rc = strategy_github_notify.github_notify(
                baseline_path=baseline_path,
                report_path=report_path,
                work_dir=work_dir,
                apply=True,
            )
            self.assertEqual(rc, 0)
            mock_create.assert_called_once()
            title = mock_create.call_args[0][0]
            self.assertIn("1 actionable item", title)

            saved = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertTrue(saved["notification"]["issue_created"])
            self.assertEqual(saved["notification"]["issue_url"], "https://github.com/org/repo/issues/42")

    def test_skips_issue_without_actionable(self) -> None:
        baseline = _sample_baseline()
        baseline["actionable_items"] = []
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, report_path, work_dir = self._write_files(tmp, baseline)
            with mock.patch.object(strategy_github_notify, "create_github_issue") as mock_create:
                rc = strategy_github_notify.github_notify(
                    baseline_path=baseline_path,
                    report_path=report_path,
                    work_dir=work_dir,
                    apply=True,
                )
            self.assertEqual(rc, 0)
            mock_create.assert_not_called()
            saved = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["notification"]["reason"], "no_actionable_items")

    @mock.patch.object(strategy_github_notify, "create_github_issue")
    def test_retries_without_label_when_label_missing(self, mock_create: mock.Mock) -> None:
        mock_create.side_effect = [
            RuntimeError("could not add label: layer3-strategy-review"),
            "https://github.com/org/repo/issues/99",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path, report_path, work_dir = self._write_files(tmp)
            rc = strategy_github_notify.github_notify(
                baseline_path=baseline_path,
                report_path=report_path,
                work_dir=work_dir,
                apply=True,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(mock_create.call_count, 2)
            self.assertIsNone(mock_create.call_args_list[1].kwargs.get("label"))

    def test_build_issue_body_ai_structured(self) -> None:
        baseline = _sample_baseline()
        md = strategy_notify.build_strategy_ai_brief(baseline)
        body = strategy_github_notify.build_issue_body(baseline, md, "actionable_items=1")
        self.assertIn("document_type: layer3_strategy_issue", body)
        self.assertIn("## Machine-readable queue", body)
        self.assertIn('"document_type": "layer3_strategy_issue"', body)
        self.assertIn("A1-test", body)
        self.assertIn("failure rate spike", body)
        self.assertIn("Review cli-usage.md", body)
        self.assertIn("## Suggested agent workflow", body)
        self.assertIn("document_type: layer3_strategy_review", body)  # AI Brief appended inline

    def test_issue_machine_payload_fields(self) -> None:
        baseline = _sample_baseline()
        payload = strategy_github_notify._issue_machine_payload(baseline, "actionable_items=1")
        self.assertEqual(payload["document_type"], "layer3_strategy_issue")
        self.assertEqual(len(payload["actionable_items"]), 1)
        self.assertEqual(payload["actionable_items"][0]["id"], "A1-test")
        self.assertIn("actions", payload["actionable_items"][0])


if __name__ == "__main__":
    unittest.main()
