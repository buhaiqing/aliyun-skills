#!/usr/bin/env python3
"""Unit tests for queue_nightly.py — L1/L2/L3 scanning, queue sorting, format output."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure the parent directory is on sys.path so we can import queue_nightly
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import queue_nightly as qn  # noqa: E402


def _make_l1_entry(
    skill: str = "alicloud-ecs-ops",
    gcl_status: str = "SAFETY_FAIL",
    rubric_pass: bool = False,
    days_ago: int = 1,
    failure_pattern: dict[str, Any] | None = None,
) -> str:
    """Create a single L1 JSONL line."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    entry: dict[str, Any] = {
        "timestamp": ts,
        "skill": skill,
        "operation": "DescribeInstances",
        "gcl_status": gcl_status,
        "rubric_pass": rubric_pass,
    }
    if failure_pattern is not None:
        entry["failure_pattern"] = failure_pattern
    return json.dumps(entry, ensure_ascii=False)


def _make_reflexion_store(
    patterns: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Create a minimal reflexion.json store."""
    return {
        "cli_parameter": patterns or [],
        "runtime": [],
        "max_iter": [],
        "near_miss": [],
        "cross_skill": [],
        "skill_generation": [],
        "token_efficiency": [],
        "generalized_cli": [],
    }


def _make_l2_pattern(
    skill: str = "alicloud-ecs-ops",
    error: str = "MissingParam: InstanceId",
    count: int = 5,
    days_ago: int = 1,
    category: str = "cli_parameter",
) -> dict[str, Any]:
    """Create a reflexion store pattern entry."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "category": category,
        "skill": skill,
        "command": "aliyun ecs DescribeInstances --InstanceId i-bp1",
        "error": error,
        "fix": "Use --InstanceId with correct value",
        "count": count,
        "last_seen": ts,
        "first_seen": ts,
        "normalized_key": error.replace(": ", ":"),
    }


def _make_strategy_baseline(
    skill: str = "alicloud-ecs-ops",
    failure_rate: float = 0.35,
    severity: str = "high",
) -> dict[str, Any]:
    """Create a strategy-baseline.json dict."""
    return {
        "skills": {
            skill: {
                "failure_rate": failure_rate,
                "severity": severity,
                "action_items": [
                    {"description": "Review ECS DescribeInstances parameters"}
                ],
            }
        },
        "overall_failure_rate": 0.2,
    }


class TestL1Scan(unittest.TestCase):
    """Tests for L1 memory scanning."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.skill_dir = self.tmpdir / "alicloud-ecs-ops"
        self.skill_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_l1(self, lines: list[str]) -> None:
        self.skill_dir.joinpath("traces.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def test_l1_scan_finds_failures(self) -> None:
        """L1 scan counts failure entries correctly."""
        self._write_l1([
            _make_l1_entry(gcl_status="SAFETY_FAIL", rubric_pass=False),
            _make_l1_entry(gcl_status="SAFETY_FAIL", rubric_pass=False),
        ])
        count = qn.scan_l1_failures(self.tmpdir, "alicloud-ecs-ops")
        self.assertEqual(count, 2)

    def test_l1_scan_skips_pass(self) -> None:
        """Entries with gcl_status=PASS should not count."""
        self._write_l1([
            _make_l1_entry(gcl_status="PASS", rubric_pass=True),
            _make_l1_entry(gcl_status="SAFETY_FAIL", rubric_pass=False),
        ])
        count = qn.scan_l1_failures(self.tmpdir, "alicloud-ecs-ops")
        self.assertEqual(count, 1)

    def test_l1_scan_filters_by_recency(self) -> None:
        """Entries older than recency_days should be excluded."""
        self._write_l1([
            _make_l1_entry(gcl_status="SAFETY_FAIL", rubric_pass=False, days_ago=10),
            _make_l1_entry(gcl_status="SAFETY_FAIL", rubric_pass=False, days_ago=1),
        ])
        count = qn.scan_l1_failures(self.tmpdir, "alicloud-ecs-ops", recency_days=7)
        self.assertEqual(count, 1)

    def test_l1_scan_handles_missing_skill_dir(self) -> None:
        """Non-existent skill directory returns 0."""
        count = qn.scan_l1_failures(self.tmpdir, "nonexistent-skill")
        self.assertEqual(count, 0)


class TestL2Scan(unittest.TestCase):
    """Tests for L2 reflexion scanning."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.reflexion_dir = self.tmpdir / "reflexion"
        self.reflexion_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_reflexion(self, store: dict[str, Any]) -> None:
        self.reflexion_dir.joinpath("reflexion.json").write_text(
            json.dumps(store, indent=2), encoding="utf-8"
        )

    def test_l2_scan_counts_patterns(self) -> None:
        """L2 scan returns correct pattern count and weighted score."""
        self._write_reflexion(
            _make_reflexion_store([
                _make_l2_pattern(count=5, days_ago=1),
                _make_l2_pattern(count=3, days_ago=2),
            ])
        )
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 8)
        # Score should be close to count (recent patterns, minimal decay)
        self.assertGreater(info["pattern_score"], 7.0)
        self.assertEqual(len(info["top_patterns"]), 2)

    def test_l2_scan_handles_missing_store(self) -> None:
        """Missing reflexion.json returns zero stats."""
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 0)
        self.assertEqual(info["pattern_score"], 0.0)

    def test_l2_scan_handles_empty_store(self) -> None:
        """Empty store returns zero stats."""
        self._write_reflexion({})
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 0)
        self.assertEqual(info["pattern_score"], 0.0)

    def test_l2_scan_filters_other_skill(self) -> None:
        """Patterns for other skills should not contribute."""
        self._write_reflexion(
            _make_reflexion_store([
                _make_l2_pattern(skill="alicloud-rds-ops", count=10, days_ago=1),
            ])
        )
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 0)
        self.assertEqual(info["pattern_score"], 0.0)

    def test_l2_scan_generalized_cli_matches_skills_list(self) -> None:
        """generalized_cli patterns match via skills list."""
        ts = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        patterns = [
            {
                "category": "generalized_cli",
                "skills": ["alicloud-ecs-ops", "alicloud-rds-ops"],
                "error": "MissingRegion",
                "count": 7,
                "last_seen": ts,
                "normalized_key": "MissingRegion",
            }
        ]
        store = _make_reflexion_store()
        store["generalized_cli"] = patterns
        self._write_reflexion(store)

        # Should match when skill is in the list
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 7)
        self.assertGreater(info["pattern_score"], 0)

    def test_l2_scan_generalized_cli_filters_other_skill(self) -> None:
        """generalized_cli patterns filter when skill not in skills list."""
        ts = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        patterns = [
            {
                "category": "generalized_cli",
                "skills": ["alicloud-rds-ops"],
                "error": "MissingRegion",
                "count": 7,
                "last_seen": ts,
                "normalized_key": "MissingRegion",
            }
        ]
        store = _make_reflexion_store()
        store["generalized_cli"] = patterns
        self._write_reflexion(store)

        # Should NOT match when skill is NOT in the list
        info = qn.scan_l2_patterns(self.reflexion_dir, "alicloud-ecs-ops")
        self.assertEqual(info["pattern_count"], 0)
        self.assertEqual(info["pattern_score"], 0.0)


class TestL3Scan(unittest.TestCase):
    """Tests for L3 strategy baseline scanning."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.strategy_path = self.tmpdir / "strategy-baseline.json"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_strategy(self, data: dict[str, Any]) -> None:
        self.strategy_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def test_l3_scan_reads_actionable(self) -> None:
        """L3 scan extracts severity and actionable status."""
        self._write_strategy(_make_strategy_baseline())
        info = qn.scan_l3_strategy(self.strategy_path, "alicloud-ecs-ops")
        self.assertEqual(info["failure_rate"], 0.35)
        self.assertEqual(info["severity"], "high")
        self.assertTrue(info["has_actionable"])

    def test_l3_scan_reads_trends(self) -> None:
        """L3 scan reads skill_trends structure."""
        data = {
            "skill_trends": {
                "alicloud-ecs-ops": {
                    "fr": 0.5,
                    "alert_level": "critical",
                    "recommendations": ["Upgrade ECS API calls"],
                }
            }
        }
        self._write_strategy(data)
        info = qn.scan_l3_strategy(self.strategy_path, "alicloud-ecs-ops")
        self.assertEqual(info["failure_rate"], 0.5)
        self.assertEqual(info["severity"], "critical")
        self.assertTrue(info["has_actionable"])

    def test_l3_scan_missing_file(self) -> None:
        """Missing strategy file returns defaults."""
        info = qn.scan_l3_strategy(self.tmpdir / "nonexistent.json", "alicloud-ecs-ops")
        self.assertEqual(info["failure_rate"], 0.0)
        self.assertEqual(info["severity"], "none")
        self.assertFalse(info["has_actionable"])


class TestBuildQueue(unittest.TestCase):
    """Tests for queue building and sorting."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.memory_root = self.tmpdir / "memory"
        self.reflexion_root = self.tmpdir / "reflexion"
        self.reflexion_root.mkdir(parents=True)
        self.strategy_path = self.tmpdir / "strategy-baseline.json"

    def _setup_skill(
        self,
        skill: str,
        l1_count: int,
        l2_patterns: list[dict[str, Any]] | None = None,
        l3_data: dict[str, Any] | None = None,
    ) -> None:
        """Create mock L1/L2/L3 data for a skill."""
        # L1
        skill_dir = self.memory_root / skill
        skill_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            _make_l1_entry(skill=skill, gcl_status="SAFETY_FAIL", rubric_pass=False)
            for _ in range(l1_count)
        ]
        skill_dir.joinpath("traces.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

        # L2
        if l2_patterns is not None:
            reflexion_path = self.reflexion_root / "reflexion.json"
            if reflexion_path.exists():
                store = json.loads(reflexion_path.read_text(encoding="utf-8"))
            else:
                store = _make_reflexion_store()
            for cat in store:
                if cat in [p.get("category", "cli_parameter") for p in l2_patterns]:
                    store[cat] = [p for p in l2_patterns if p.get("category", "cli_parameter") == cat]
            reflexion_path.write_text(json.dumps(store, indent=2), encoding="utf-8")

        # L3
        if l3_data is not None:
            if self.strategy_path.exists():
                existing = json.loads(self.strategy_path.read_text(encoding="utf-8"))
            else:
                existing = {"skills": {}, "overall_failure_rate": 0.0}
            existing.setdefault("skills", {})[skill] = l3_data
            self.strategy_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_queue_ranks_by_score(self) -> None:
        """Queue entries should be sorted by queue_score descending."""
        # Skill A: 10 L1 failures, L2 patterns with score ~20
        l2_a = [_make_l2_pattern(skill="alicloud-ecs-ops", count=10, days_ago=1)]
        self._setup_skill("alicloud-ecs-ops", l1_count=10, l2_patterns=l2_a)

        # Skill B: 2 L1 failures, L2 patterns with score ~3
        l2_b = [_make_l2_pattern(skill="alicloud-rds-ops", count=3, days_ago=5)]
        self._setup_skill("alicloud-rds-ops", l1_count=2, l2_patterns=l2_b)

        entries = qn.build_queue(
            self.memory_root, self.reflexion_root, self.strategy_path,
            min_l1_failures=1,
        )
        self.assertEqual(len(entries), 2)
        self.assertGreater(entries[0]["queue_score"], entries[1]["queue_score"])

    def test_build_queue_respects_top_k(self) -> None:
        """top_k limits the number of entries."""
        self._setup_skill("alicloud-ecs-ops", l1_count=5)
        self._setup_skill("alicloud-rds-ops", l1_count=3)
        self._setup_skill("alicloud-slb-ops", l1_count=2)

        entries = qn.build_queue(
            self.memory_root, self.reflexion_root, None,
            min_l1_failures=1, top_k=2,
        )
        self.assertEqual(len(entries), 2)

    def test_build_queue_filters_low_l1(self) -> None:
        """Skills below min_l1_failures should be excluded."""
        self._setup_skill("alicloud-ecs-ops", l1_count=5)
        self._setup_skill("alicloud-rds-ops", l1_count=1)

        entries = qn.build_queue(
            self.memory_root, self.reflexion_root, None,
            min_l1_failures=3,
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["skill"], "alicloud-ecs-ops")


class TestFormatOutput(unittest.TestCase):
    """Tests for output formatting."""

    def test_format_json_output(self) -> None:
        """JSON output has the correct schema."""
        entries = [
            {
                "skill": "alicloud-ecs-ops",
                "queue_score": 42.5,
                "l1_failure_score": 15,
                "l2_pattern_score": 68.3,
                "l3_strategy_score": 0.35,
                "l1_failure_count": 15,
                "l2_pattern_count": 12,
                "l3_has_actionable": True,
                "l3_severity": "high",
                "top_patterns": [
                    {
                        "category": "cli_parameter",
                        "error": "MissingParam: InstanceId",
                        "count": 8,
                        "normalized_key": "MissingParam:InstanceId",
                    }
                ],
                "eval_priority": "P0",
            }
        ]
        output = qn.format_json(entries, total_scanned=10)
        self.assertEqual(output["version"], "1.0")
        self.assertEqual(output["total_skills_scanned"], 10)
        self.assertEqual(output["total_skills_queued"], 1)
        self.assertEqual(len(output["queue"]), 1)
        self.assertEqual(output["queue"][0]["eval_priority"], "P0")

    def test_format_text_output(self) -> None:
        """Text output is a non-empty string."""
        entries = [
            {
                "skill": "alicloud-ecs-ops",
                "queue_score": 42.5,
                "l1_failure_score": 15,
                "l2_pattern_score": 68.3,
                "l3_strategy_score": 0.35,
                "l1_failure_count": 15,
                "l2_pattern_count": 12,
                "l3_has_actionable": True,
                "l3_severity": "high",
                "top_patterns": [
                    {
                        "category": "cli_parameter",
                        "error": "MissingParam: InstanceId",
                        "count": 8,
                        "normalized_key": "MissingParam:InstanceId",
                    }
                ],
                "eval_priority": "P0",
            }
        ]
        text = qn.format_text(entries, total_scanned=5)
        self.assertIn("alicloud-ecs-ops", text)
        self.assertIn("P0", text)
        self.assertIn("MissingParam", text)

    def test_format_text_empty(self) -> None:
        """Text output for empty queue should note emptiness."""
        text = qn.format_text([], total_scanned=3)
        self.assertIn("empty", text.lower())


class TestCLI(unittest.TestCase):
    """Integration-style CLI tests."""

    def test_cli_basic(self) -> None:
        """CLI runs without error with --help."""
        with self.assertRaises(SystemExit) as ctx:
            qn.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
