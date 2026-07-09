#!/usr/bin/env python3
"""
E2E test for Layer 3 weekly pipeline (mirrors strategy-weekly.yml).

Runs: git_collect → weekly --apply → synthesize → report → github_notify
Validates artifacts and notification schema (channel=github, no SMTP fields).

Issue creation is exercised with a mocked `gh` subprocess when actionable items exist.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "alicloud-gcl-runner-ops" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import strategy_github_notify  # noqa: E402


def _run(cmd: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(
        cmd,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def _assert_no_smtp_fields(obj: dict) -> None:
    notification = obj.get("notification", {})
    assert "sent" not in notification, "legacy notification.sent field present"
    assert notification.get("channel") == "github", f"expected channel=github, got {notification!r}"
    blob = json.dumps(obj)
    for token in ("STRATEGY_SMTP", "missing_smtp", "STRATEGY_NOTIFY_TO"):
        assert token not in blob, f"unexpected SMTP/email artifact: {token}"


class StrategyWeeklyE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._backup_baseline = (_REPO_ROOT / "docs" / "strategy-baseline.json").read_text(encoding="utf-8")
        cls._backup_report = (_REPO_ROOT / "docs" / "strategy-report.md").read_text(encoding="utf-8")
        cls._empty_memory = tempfile.mkdtemp(prefix="gcl-memory-e2e-")
        cls._work = _REPO_ROOT / ".runtime" / "strategy" / "e2e-work"
        cls._work.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        (_REPO_ROOT / "docs" / "strategy-baseline.json").write_text(cls._backup_baseline, encoding="utf-8")
        (_REPO_ROOT / "docs" / "strategy-report.md").write_text(cls._backup_report, encoding="utf-8")
        shutil.rmtree(cls._empty_memory, ignore_errors=True)

    def _env(self) -> dict[str, str]:
        return {"GCL_MEMORY_ROOT": self._empty_memory}

    def test_weekly_pipeline_no_actionable_github_notify(self) -> None:
        git_out = self._work / "git_signals.json"
        _run([
            sys.executable,
            str(_SCRIPTS / "git_collect.py"),
            "--since-days", "7",
            "--repo-root", str(_REPO_ROOT),
            "--output", str(git_out),
        ], env=self._env())

        _run([
            sys.executable,
            str(_SCRIPTS / "gcl_strategy.py"),
            "weekly", "--apply", "--since-days", "7",
            "--repo-root", str(_REPO_ROOT),
        ], env=self._env())

        _run([
            sys.executable,
            str(_SCRIPTS / "strategy_synthesize.py"),
            "--baseline", str(_REPO_ROOT / "docs" / "strategy-baseline.json"),
        ], env=self._env())

        _run([
            sys.executable,
            str(_SCRIPTS / "gcl_strategy.py"),
            "report",
            "--baseline", str(_REPO_ROOT / "docs" / "strategy-baseline.json"),
            "--output", str(_REPO_ROOT / "docs" / "strategy-report.md"),
        ], env=self._env())

        pr_body = self._work / "pr-body-e2e.md"
        rc = strategy_github_notify.github_notify(
            baseline_path=_REPO_ROOT / "docs" / "strategy-baseline.json",
            report_path=_REPO_ROOT / "docs" / "strategy-report.md",
            pr_body_out=pr_body,
            work_dir=self._work,
            apply=False,
        )
        self.assertEqual(rc, 0)
        self.assertTrue(pr_body.exists())

        body = pr_body.read_text(encoding="utf-8")
        self.assertIn("Weekly Layer 3 Strategy Review", body)
        self.assertIn("Strategy Report", body)
        self.assertIn("document_type: layer3_strategy_review", body)

        baseline = json.loads((_REPO_ROOT / "docs" / "strategy-baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["notification"]["channel"], "github")
        self.assertNotIn("sent", baseline["notification"])
        self.assertFalse(baseline["notification"].get("issue_created", False))
        _assert_no_smtp_fields(baseline)

        report = (_REPO_ROOT / "docs" / "strategy-report.md").read_text(encoding="utf-8")
        self.assertNotIn("notification email", report.lower())
        self.assertIn("strategy_github_notify.py", report)

    @mock.patch.object(strategy_github_notify, "create_github_issue")
    def test_github_notify_creates_issue_when_actionable(self, mock_issue: mock.Mock) -> None:
        mock_issue.return_value = "https://github.com/example/org/issues/1"
        baseline_path = _REPO_ROOT / "docs" / "strategy-baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline["actionable_items"] = [{
            "id": "E2E-1",
            "severity": "high",
            "skill": "alicloud-ecs-ops",
            "reason": "E2E actionable probe",
            "actions": ["Verify cli-usage.md"],
        }]
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

        pr_body = self._work / "pr-body-e2e-actionable.md"
        rc = strategy_github_notify.github_notify(
            baseline_path=baseline_path,
            report_path=_REPO_ROOT / "docs" / "strategy-report.md",
            pr_body_out=pr_body,
            work_dir=self._work,
            apply=True,
        )
        self.assertEqual(rc, 0)
        mock_issue.assert_called_once()

        saved = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["notification"]["issue_created"])
        self.assertEqual(saved["notification"]["channel"], "github")
        self.assertIn("issue_url", saved["notification"])
        _assert_no_smtp_fields(saved)


if __name__ == "__main__":
    unittest.main()
