#!/usr/bin/env python3
"""
git_collect_test.py — Unit tests for git_collect.py.

Covers A3.2 dry-run behaviour:
  - --dry-run exits 0 and prints summary
  - --dry-run does NOT write the output file
  - normal run still writes the output file
  - pending cleanup preview enumerates reflexion patterns below min_count
    or older than 90 days

Pure stdlib unittest. Python 3.10+ compatible.
Run: python3 -m unittest git_collect_test -v
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import git_collect  # noqa: E402


class DryRunCLITests(unittest.TestCase):
    """End-to-end CLI checks against the installed scripts/ dir."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=_SCRIPT_DIR,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )

    def _run_cli(self, *extra: str, output: Path | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(_SCRIPT_DIR / "git_collect.py"),
            "--repo-root",
            str(self.repo_root),
            "--since-days",
            "7",
            *extra,
        ]
        if output is not None:
            cmd.extend(["--output", str(output)])
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_dry_run_exits_zero(self) -> None:
        proc = self._run_cli("--dry-run")
        self.assertEqual(
            proc.returncode, 0,
            msg=f"stderr={proc.stderr!r}\nstdout={proc.stdout!r}",
        )
        self.assertIn("git_collect.py --dry-run summary", proc.stdout)

    def test_dry_run_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "should-not-exist.json"
            proc = self._run_cli("--dry-run", output=out)
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(out.exists(), "dry-run must not write --output")

    def test_normal_run_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "git_signals.json"
            proc = self._run_cli(output=out)
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(out.exists(), "normal run must write --output")
            payload = json.loads(out.read_text(encoding="utf-8"))
            for key in ("collected_at", "commit_count", "bugfix_commits", "hot_skills"):
                self.assertIn(key, payload)


class PendingCleanupPreviewTests(unittest.TestCase):
    """Unit tests for _load_reflexion_cleanup_preview()."""

    def _write_store(self, root: Path, patterns: dict[str, list[dict]]) -> None:
        (root / "reflexion.json").write_text(
            json.dumps(patterns, ensure_ascii=False), encoding="utf-8"
        )

    def test_missing_store_reports_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preview = git_collect._load_reflexion_cleanup_preview(Path(tmp))
            self.assertFalse(preview["store_present"])
            self.assertEqual(preview["total_before"], 0)

    def test_counts_low_count_and_old_patterns(self) -> None:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        # reflexion_maintain uses an adaptive decay window: 90d + count*7d
        # (capped at 365d). count=5 → window=125d; use 200d to clearly exceed it.
        old_ts = (now - timedelta(days=200)).isoformat().replace("+00:00", "Z")
        fresh_ts = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        with tempfile.TemporaryDirectory() as tmp:
            self._write_store(Path(tmp), {
                "cli_parameter": [
                    {"count": 1, "last_seen": fresh_ts},   # pruned_by_count
                    {"count": 5, "last_seen": old_ts},     # pruned_by_decay
                    {"count": 7, "last_seen": fresh_ts},   # kept
                ],
                "skill_generation": [],
                "cross_skill": [],
                "runtime": [],
                "token_efficiency": [
                    {"count": 2, "last_seen": fresh_ts},  # pruned_by_count
                ],
            })
            preview = git_collect._load_reflexion_cleanup_preview(Path(tmp))
            self.assertTrue(preview["store_present"])
            self.assertEqual(preview["total_before"], 4)
            self.assertEqual(preview["pruned_by_count"], 2)
            self.assertEqual(preview["pruned_by_decay"], 1)
            self.assertIn("cli_parameter", preview["categories"])
            self.assertIn("token_efficiency", preview["categories"])

    def test_healthy_store_reports_nothing_pending(self) -> None:
        from datetime import datetime, timedelta, timezone

        fresh_ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat().replace("+00:00", "Z")
        with tempfile.TemporaryDirectory() as tmp:
            self._write_store(Path(tmp), {
                "cli_parameter": [
                    {"count": 5, "last_seen": fresh_ts},
                    {"count": 9, "last_seen": fresh_ts},
                ],
                "skill_generation": [],
                "cross_skill": [],
                "runtime": [],
                "token_efficiency": [],
            })
            preview = git_collect._load_reflexion_cleanup_preview(Path(tmp))
            self.assertEqual(preview["pruned_by_count"], 0)
            self.assertEqual(preview["pruned_by_decay"], 0)
            # reflexion_maintain populates categories for every category,
            # so verify the "nothing pending" semantic: no per-category pruning.
            for cat_data in preview["categories"].values():
                self.assertEqual(cat_data.get("pruned_by_count", 0), 0)
                self.assertEqual(cat_data.get("pruned_by_decay", 0), 0)


class DryRunPrintTests(unittest.TestCase):
    """Smoke test the dry-run printer (no I/O outside stdout)."""

    def test_prints_summary_sections(self) -> None:
        buf = io.StringIO()
        signals = {
            "collected_at": "2026-07-12T00:00:00Z",
            "since_days": 7,
            "commit_count": 3,
            "bugfix_commits": [{"sha": "abc"}],
            "hot_skills": [{"skill": "alicloud-ecs-ops", "commit_count": 3, "bugfix_count": 1}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(buf):
                git_collect._print_dry_run_summary(signals, Path(tmp))
        out = buf.getvalue()
        self.assertIn("git_collect.py --dry-run summary", out)
        self.assertIn("commit_count: 3", out)
        self.assertIn("bugfix_commits: 1", out)
        self.assertIn("hot_skills:   1", out)
        self.assertIn("pending cleanup (reflexion store)", out)


if __name__ == "__main__":
    unittest.main()
