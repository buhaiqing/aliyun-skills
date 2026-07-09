#!/usr/bin/env python3
"""Unit tests for Layer 3 Strategy Memory (gcl_strategy.py, git_collect.py, strategy_notify.py)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import gcl_strategy as strategy  # noqa: E402
import git_collect  # noqa: E402
import strategy_notify  # noqa: E402
import strategy_synthesize  # noqa: E402


class ParseFailurePatternsTests(unittest.TestCase):
    def test_parses_table_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "failure-patterns.md"
            p.write_text(
                "## CLI Parameter Errors\n\n"
                "|Skill|Command|Error|Root Cause|Fix|Count|Last Seen|\n"
                "|---|---|---|---|---|---|---|\n"
                "|ecs-ops|cmd|err|rc|fix|12|2026-01-01|\n",
                encoding="utf-8",
            )
            result = strategy._parse_failure_patterns(p)
            self.assertEqual(result["pattern_count"], 1)
            self.assertEqual(result["patterns"][0]["skill"], "alicloud-ecs-ops")
            self.assertEqual(result["high_frequency"][0]["count"], 12)

    def test_normalize_skill_name(self) -> None:
        self.assertEqual(strategy.normalize_skill_name("ecs-ops"), "alicloud-ecs-ops")
        self.assertEqual(strategy.normalize_skill_name("alicloud-ecs-ops"), "alicloud-ecs-ops")

    def test_missing_file_returns_empty(self) -> None:
        result = strategy._parse_failure_patterns(Path("/nonexistent/failure-patterns.md"))
        self.assertEqual(result["pattern_count"], 0)


class GitCollectNameOnlyTests(unittest.TestCase):
    def test_parse_commit_header(self) -> None:
        sep = git_collect.GIT_FIELD_SEP
        line = f"COMMIT:abc123{sep}fix bug{sep}Author{sep}a@b.c{sep}2026-01-01"
        parsed = git_collect._parse_commit_header(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], "abc123")
        self.assertEqual(parsed[1], "fix bug")


class GitCollectHeuristicTests(unittest.TestCase):
    def test_classify_bugfix(self) -> None:
        cats = git_collect._classify_commit("fix(ecs): InvalidParameter", ["alicloud-ecs-ops/SKILL.md"])
        self.assertIn("bugfix", cats)

    def test_parse_log_line_with_pipe_in_subject(self) -> None:
        sep = git_collect.GIT_FIELD_SEP
        line = f"abc123{sep}fix| pipe in subject{sep}Author{sep}a@b.c{sep}2026-01-01"
        parsed = git_collect._parse_log_line(line)
        self.assertIsNotNone(parsed)
        sha, subject, author, _email, _date = parsed  # type: ignore[misc]
        self.assertEqual(sha, "abc123")
        self.assertEqual(subject, "fix| pipe in subject")
        self.assertEqual(author, "Author")

    def test_infer_skills(self) -> None:
        skills = git_collect._infer_skills(["alicloud-rds-ops/references/cli-usage.md"])
        self.assertEqual(skills, ["alicloud-rds-ops"])

    def test_infer_themes_cli(self) -> None:
        themes = git_collect._infer_themes("fix cli parameter", [])
        self.assertIn("cli_parameter", themes)


class DiffVsBaselineTests(unittest.TestCase):
    def test_git_hot_bugfix_actionable(self) -> None:
        current = {
            "since_days": 7,
            "git_signals_summary": {
                "hot_skills": [{"skill": "alicloud-ecs-ops", "commit_count": 5, "bugfix_count": 3}],
                "theme_clusters": {},
            },
            "skill_trends": {},
            "high_frequency_patterns": [],
        }
        delta = strategy.diff_vs_baseline(current, None)
        self.assertGreaterEqual(delta["actionable_count"], 1)
        self.assertEqual(current["actionable_items"][0]["type"], "git_hot_bugfix")

    def test_no_actionable_when_quiet(self) -> None:
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {},
            "high_frequency_patterns": [],
        }
        delta = strategy.diff_vs_baseline(current, None)
        self.assertEqual(delta["actionable_count"], 0)

    def test_failure_rate_delta(self) -> None:
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {
                "alicloud-ecs-ops": {
                    "failure_rate": 0.5,
                    "risk_score": 0.4,
                    "confidence": "high",
                },
            },
            "high_frequency_patterns": [],
        }
        baseline = {
            "skill_trends": {
                "alicloud-ecs-ops": {"failure_rate": 0.2, "risk_score": 0.2},
            },
        }
        delta = strategy.diff_vs_baseline(current, baseline)
        types = [i["type"] for i in current["actionable_items"]]
        self.assertIn("failure_rate_worsening", types)

    def test_new_skill_uses_zero_baseline(self) -> None:
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {
                "alicloud-new-ops": {
                    "failure_rate": 0.5,
                    "risk_score": 0.4,
                    "confidence": "high",
                },
            },
            "high_frequency_patterns": [],
        }
        baseline = {"skill_trends": {}}
        strategy.diff_vs_baseline(current, baseline)
        types = [i["type"] for i in current["actionable_items"]]
        self.assertIn("failure_rate_worsening", types)

    def test_low_confidence_skipped_for_high_severity(self) -> None:
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {
                "alicloud-agentrun-ops": {
                    "failure_rate": 1.0,
                    "risk_score": 0.5,
                    "confidence": "low",
                },
            },
            "high_frequency_patterns": [],
        }
        baseline = {"skill_trends": {}}
        strategy.diff_vs_baseline(current, baseline)
        self.assertEqual(current["actionable_items"], [])


class MultiWeekBaselineTests(unittest.TestCase):
    def _trend(self, failure_rate: float) -> dict:
        return {
            "failure_rate": failure_rate,
            "risk_score": failure_rate * 0.8,
            "confidence": "high",
            "total": 20,
        }

    def test_history_append_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            entry = strategy.history_compact_entry({
                "generated_at": "2026-06-01T00:00:00Z",
                "since_days": 7,
                "skill_trends": {"alicloud-ecs-ops": self._trend(0.1)},
                "git_signals_summary": {"commit_count": 1, "bugfix_count": 0},
            })
            strategy.history_append(entry, path=path)
            strategy.history_append(entry, path=path)
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)

    def test_multiweek_median_spike(self) -> None:
        history = [
            {"skill_trends": {"alicloud-ecs-ops": self._trend(0.1)}},
            {"skill_trends": {"alicloud-ecs-ops": self._trend(0.12)}},
        ]
        # Baseline close to current so WoW (±10%) does not fire; multi-week median should.
        baseline = {"skill_trends": {"alicloud-ecs-ops": self._trend(0.26)}}
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {"alicloud-ecs-ops": self._trend(0.35)},
            "high_frequency_patterns": [],
        }
        delta = strategy.diff_vs_baseline(current, baseline, history=history)
        types = [i["type"] for i in current["actionable_items"]]
        self.assertNotIn("failure_rate_worsening", types)
        self.assertIn("failure_rate_above_rolling_median", types)
        self.assertGreaterEqual(delta["delta_summary"]["multiweek_items"], 1)

    def test_multiweek_skips_when_insufficient_history(self) -> None:
        history = [{"skill_trends": {"alicloud-ecs-ops": self._trend(0.1)}}]
        baseline = {"skill_trends": {"alicloud-ecs-ops": self._trend(0.12)}}
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {"alicloud-ecs-ops": self._trend(0.5)},
            "high_frequency_patterns": [],
        }
        strategy.diff_vs_baseline(current, baseline, history=history)
        types = [i["type"] for i in current["actionable_items"]]
        self.assertNotIn("failure_rate_above_rolling_median", types)

    def test_wow_takes_priority_over_multiweek(self) -> None:
        history = [
            {"skill_trends": {"alicloud-ecs-ops": self._trend(0.1)}},
            {"skill_trends": {"alicloud-ecs-ops": self._trend(0.12)}},
        ]
        baseline = {"skill_trends": {"alicloud-ecs-ops": self._trend(0.15)}}
        current = {
            "since_days": 7,
            "git_signals_summary": {"hot_skills": [], "theme_clusters": {}},
            "skill_trends": {"alicloud-ecs-ops": self._trend(0.5)},
            "high_frequency_patterns": [],
        }
        strategy.diff_vs_baseline(current, baseline, history=history)
        ids = [i["id"] for i in current["actionable_items"]]
        self.assertIn("A1-alicloud-ecs-ops", ids)
        self.assertNotIn("A2-median-alicloud-ecs-ops", ids)


class StrategyRetrieveTests(unittest.TestCase):
    def test_retrieve_empty_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = strategy.strategy_retrieve("alicloud-ecs-ops", baseline_path=Path(tmp) / "missing.json")
            self.assertTrue(out.get("empty"))

    def test_retrieve_skill_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps({
                    "skill_trends": {
                        "alicloud-ecs-ops": {"risk_score": 0.7, "failure_rate": 0.3, "confidence": "high"},
                    },
                    "actionable_items": [],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )
            out = strategy.strategy_retrieve("alicloud-ecs-ops", baseline_path=baseline)
            self.assertEqual(out["skill_risk"]["risk_score"], 0.7)

    def test_retrieve_excludes_repo_wide_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps({
                    "skill_trends": {},
                    "actionable_items": [
                        {
                            "id": "theme-1",
                            "type": "git_theme_cluster",
                            "reason": "repo wide",
                            "actions": ["audit all skills"],
                        },
                        {
                            "id": "ecs-1",
                            "skill": "alicloud-ecs-ops",
                            "reason": "ecs only",
                            "actions": ["fix ecs"],
                        },
                    ],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )
            out = strategy.strategy_retrieve("alicloud-rds-ops", baseline_path=baseline)
            self.assertNotIn("preventive_actions", out)
            out_ecs = strategy.strategy_retrieve("alicloud-ecs-ops", baseline_path=baseline)
            self.assertEqual(out_ecs.get("preventive_actions"), ["fix ecs"])

    def test_retrieve_matches_normalized_skill_in_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            baseline.write_text(
                json.dumps({
                    "skill_trends": {},
                    "actionable_items": [{
                        "id": "A4-ecs",
                        "skill": "ecs-ops",
                        "reason": "pattern",
                        "actions": ["fix cli"],
                    }],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )
            out = strategy.strategy_retrieve("alicloud-ecs-ops", baseline_path=baseline)
            self.assertEqual(out.get("preventive_actions"), ["fix cli"])


class StrategyNotifyTests(unittest.TestCase):
    def test_should_notify_with_actionable(self) -> None:
        baseline = {"actionable_items": [{"severity": "high", "reason": "test"}], "rule_proposals": []}
        do_send, reason = strategy_notify.should_notify(baseline)
        self.assertTrue(do_send)

    def test_ai_brief_contains_frontmatter(self) -> None:
        baseline = {
            "generated_at": "2026-06-21T00:00:00Z",
            "since_days": 7,
            "git_signals_summary": {"commit_count": 1, "bugfix_count": 0, "hot_skills": []},
            "runtime_signals_summary": {"pattern_count": 0},
            "actionable_items": [{
                "id": "A1-test",
                "severity": "high",
                "type": "test",
                "reason": "test reason",
                "actions": ["do something"],
            }],
            "rule_proposals": [],
            "skill_trends": {},
            "high_frequency_patterns": [],
        }
        md = strategy_notify.build_strategy_ai_brief(baseline)
        self.assertIn("document_type: layer3_strategy_review", md)
        self.assertIn("## Actionable Items", md)
        self.assertIn("A1-test", md)
        self.assertIn("## Suggested AI Workflow", md)

    def test_write_ai_brief_attachment(self) -> None:
        baseline = {
            "generated_at": "2026-06-21T00:00:00Z",
            "since_days": 7,
            "git_signals_summary": {},
            "runtime_signals_summary": {},
            "actionable_items": [{"id": "x", "severity": "low", "reason": "r", "actions": []}],
            "rule_proposals": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = strategy_notify.write_ai_brief_attachment(baseline, output_dir=Path(tmp))
            self.assertTrue(path.exists())
            self.assertIn("doctor-review-ai-brief-2026-06-21.md", path.name)

    def test_preview_ai_brief_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "baseline.json"
            p.write_text(
                json.dumps({
                    "generated_at": "2026-06-21T00:00:00Z",
                    "git_signals_summary": {"commit_count": 1, "bugfix_count": 1},
                    "actionable_items": [{"severity": "high", "reason": "test reason", "actions": ["fix it"]}],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )
            with mock.patch("sys.stdout"):
                rc = strategy_notify.preview_ai_brief(baseline_path=p)
            self.assertEqual(rc, 0)


class StrategySynthesizeTests(unittest.TestCase):
    def test_sanitize_rejects_patch_content(self) -> None:
        raw = [{
            "id": "p1",
            "target_skill": "alicloud-ecs-ops",
            "title": "bad",
            "suggested_action": "apply this ```diff patch",
            "confidence": "high",
        }]
        clean = strategy_synthesize._sanitize_proposals(raw)
        self.assertEqual(clean, [])

    def test_sanitize_keeps_valid_proposal(self) -> None:
        raw = [{
            "id": "p1",
            "target_skill": "alicloud-ecs-ops",
            "target_file": "references/cli-usage.md",
            "title": "Document RepeatList",
            "confidence": "medium",
            "rationale": "recurring error",
        }]
        clean = strategy_synthesize._sanitize_proposals(raw)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["confidence"], "medium")


class StrategyReportTests(unittest.TestCase):
    def test_report_line_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            snapshot = {
                "generated_at": "2026-06-21T00:00:00Z",
                "since_days": 7,
                "git_signals_summary": {"commit_count": 0, "bugfix_count": 0, "hot_skills": []},
                "runtime_signals_summary": {"pattern_count": 0},
                "memory_available": False,
                "actionable_items": [],
                "skill_trends": {},
                "rule_proposals": [],
            }
            strategy.strategy_report(snapshot, {"actionable_count": 0}, output_path=out)
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), strategy.MAX_REPORT_LINES)


class MemoryTrendTests(unittest.TestCase):
    def test_scan_memory_trends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mem = Path(tmp) / "memory" / "alicloud-ecs-ops"
            mem.mkdir(parents=True)
            entry = {
                "timestamp": "2099-06-21T00:00:00Z",
                "rubric_pass": False,
                "exit_code": 1,
                "iterations": 2,
            }
            (mem / "DescribeInstances.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
            result = strategy._scan_memory_trends(Path(tmp) / "memory", since_days=30)
            self.assertTrue(result["available"])
            self.assertIn("alicloud-ecs-ops", result["skill_trends"])


class WeeklyAggregateTests(unittest.TestCase):
    def test_weekly_aggregate_structure(self) -> None:
        git_signals = {
            "commit_count": 2,
            "bugfix_commits": [],
            "hot_skills": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "failure-patterns.md").write_text("# empty\n", encoding="utf-8")
            snap = strategy.weekly_aggregate(git_signals=git_signals, repo_root=root)
            self.assertEqual(snap["version"], strategy.STRATEGY_VERSION)
            self.assertEqual(snap["review_type"], "weekly")


class RuntimeRollupTests(unittest.TestCase):
    def test_rollup_writes_from_memory_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            mem = root / ".runtime" / "memory" / "alicloud-ecs-ops"
            mem.mkdir(parents=True)
            entry = {
                "timestamp": "2099-06-21T00:00:00Z",
                "rubric_pass": True,
                "exit_code": 0,
                "iterations": 1,
            }
            (mem / "DescribeInstances.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
            rc = strategy.runtime_rollup_apply(root, since_days=30)
            self.assertEqual(rc, 0)
            rollup = json.loads((root / "docs" / "runtime-rollup.json").read_text(encoding="utf-8"))
            self.assertEqual(rollup["source"], "memory_scan")
            self.assertIn("alicloud-ecs-ops", rollup["skill_trends"])

    def test_rollup_fallback_when_memory_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            existing = {
                "version": "1.0.0",
                "skill_trends": {"alicloud-ecs-ops": {"total": 5, "failure_rate": 0.1}},
            }
            (root / "docs" / "runtime-rollup.json").write_text(
                json.dumps(existing), encoding="utf-8"
            )
            rc = strategy.runtime_rollup_apply(root, since_days=7)
            self.assertEqual(rc, 0)
            rollup = json.loads((root / "docs" / "runtime-rollup.json").read_text(encoding="utf-8"))
            self.assertEqual(rollup["source"], "committed_carry_forward")

    def test_weekly_aggregate_uses_rollup_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "failure-patterns.md").write_text("# empty\n", encoding="utf-8")
            (root / "docs" / "runtime-rollup.json").write_text(
                json.dumps(
                    {
                        "skill_trends": {
                            "alicloud-ecs-ops": {
                                "total": 12,
                                "pass": 10,
                                "fail": 2,
                                "failure_rate": 0.1667,
                                "risk_score": 0.2,
                                "confidence": "high",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            snap = strategy.weekly_aggregate(
                git_signals={"commit_count": 0, "bugfix_commits": [], "hot_skills": []},
                repo_root=root,
            )
            self.assertEqual(snap["memory_source"], "runtime_rollup")
            self.assertIn("alicloud-ecs-ops", snap["skill_trends"])


class GitOnlyWeeklyTests(unittest.TestCase):
    def test_git_only_apply_skips_baseline_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True)
            baseline = root / "docs" / "strategy-baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "version": "2.0.0",
                        "skill_trends": {"alicloud-ecs-ops": {"risk_score": 0.1}},
                        "actionable_items": [],
                    }
                ),
                encoding="utf-8",
            )
            before = baseline.read_text(encoding="utf-8")
            rc = strategy.run_weekly(
                apply=True,
                since_days=7,
                repo_root=root,
                git_only=True,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(baseline.read_text(encoding="utf-8"), before)
            git_report = root / "docs" / "strategy-git-review.md"
            self.assertTrue(git_report.is_file())
            snap_path = root / strategy.GIT_WEEKLY_SNAPSHOT_WORK
            self.assertTrue(snap_path.is_file())
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            self.assertEqual(snap["write_authority"], strategy.WRITE_AUTHORITY_GHA_GIT)
            self.assertEqual(snap["baseline_write"], "forbidden")


if __name__ == "__main__":
    unittest.main()
