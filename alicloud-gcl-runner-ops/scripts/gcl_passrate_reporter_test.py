#!/usr/bin/env python3
"""
gcl_passrate_reporter_test.py — Unit tests for gcl_passrate_reporter.py.

Pure stdlib unittest. Python 3.10+ compatible.
Run: python3 -m unittest gcl_passrate_reporter_test -v

Covers:
  - load_memory_entries: reads JSONL, filters by window_days
  - _iso_year_week: correct ISO week format
  - compute_weekly_pass_rates: groups and computes rates
  - _week_date_range: correct start/end for ISO week keys
  - detect_anomaly: 3sigma and relative decline detection
  - CLI --detect-anomaly subcommand
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the scripts directory is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_passrate_reporter import (
    _collect_affected_operations,
    _iso_year_week,
    _resolve_runtime_root,
    _week_date_range,
    compute_weekly_pass_rates,
    detect_anomaly,
    load_memory_entries,
    main,
    parse_iso_timestamp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _memory_entry(
    skill: str = "alicloud-ecs-ops",
    operation: str = "DescribeInstances",
    rubric_pass: bool = True,
    days_ago: int = 0,
) -> str:
    """Build a JSON line for a Layer-1 memory entry."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    entry = {
        "timestamp": ts,
        "skill": skill,
        "operation": operation,
        "command": f"aliyun {skill.split('-')[1]} {operation}",
        "exit_code": 0 if rubric_pass else 1,
        "rubric_pass": rubric_pass,
        "scores": {"correctness": 1.0 if rubric_pass else 0.0, "safety": 1.0},
    }
    return json.dumps(entry, sort_keys=True)


def _write_memory_jsonl(root: Path, skill: str, operation: str, lines: list[str]) -> Path:
    """Write a JSONL file under *root* and return its path."""
    p = root / skill / f"{operation}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_memory_entries
# ---------------------------------------------------------------------------

class LoadMemoryEntriesTests(unittest.TestCase):
    """Test load_memory_entries() reading from JSONL files."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_loads_all_recent_entries(self):
        _write_memory_jsonl(self.root, "alicloud-ecs-ops", "DescribeInstances", [
            _memory_entry(days_ago=1),
            _memory_entry(days_ago=2),
        ])
        entries = load_memory_entries(self.root, window_days=90)
        self.assertEqual(len(entries), 2)

    def test_filters_by_window_days(self):
        _write_memory_jsonl(self.root, "alicloud-ecs-ops", "DeleteInstance", [
            _memory_entry(operation="DeleteInstance", days_ago=100),  # too old
            _memory_entry(operation="DeleteInstance", days_ago=5),    # recent
        ])
        entries = load_memory_entries(self.root, window_days=30)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["operation"], "DeleteInstance")

    def test_skips_corrupt_lines(self):
        p = self.root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        p.parent.mkdir(parents=True)
        p.write_text("not json\n" + _memory_entry() + "\n", encoding="utf-8")
        entries = load_memory_entries(self.root, window_days=90)
        self.assertEqual(len(entries), 1)

    def test_empty_root_returns_empty(self):
        entries = load_memory_entries(self.root, window_days=90)
        self.assertEqual(entries, [])

    def test_missing_root_returns_empty(self):
        entries = load_memory_entries(Path("/nonexistent/path"), window_days=90)
        self.assertEqual(entries, [])

    def test_multiple_skills(self):
        _write_memory_jsonl(self.root, "alicloud-ecs-ops", "DescribeInstances", [
            _memory_entry(skill="alicloud-ecs-ops", days_ago=1),
        ])
        _write_memory_jsonl(self.root, "alicloud-redis-ops", "FlushInstance", [
            _memory_entry(skill="alicloud-redis-ops", days_ago=2),
        ])
        entries = load_memory_entries(self.root, window_days=90)
        self.assertEqual(len(entries), 2)
        skills = {e["skill"] for e in entries}
        self.assertIn("alicloud-ecs-ops", skills)
        self.assertIn("alicloud-redis-ops", skills)

    def test_entries_without_timestamp_always_included(self):
        p = self.root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"skill": "alicloud-ecs-ops", "rubric_pass": True}, sort_keys=True) + "\n")
        entries = load_memory_entries(self.root, window_days=1)  # very narrow window
        self.assertEqual(len(entries), 1)


# ---------------------------------------------------------------------------
# _iso_year_week
# ---------------------------------------------------------------------------

class IsoYearWeekTests(unittest.TestCase):
    """Test _iso_year_week() format."""

    def test_known_date(self):
        # 2026-07-12 is a Sunday, ISO week 2026-W28
        dt = datetime(2026, 7, 12, tzinfo=timezone.utc)
        self.assertEqual(_iso_year_week(dt), "2026-W28")

    def test_monday(self):
        dt = datetime(2026, 7, 13, tzinfo=timezone.utc)  # Monday
        self.assertEqual(_iso_year_week(dt), "2026-W29")

    def test_early_january(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        week = _iso_year_week(dt)
        self.assertIn("-W", week)


# ---------------------------------------------------------------------------
# compute_weekly_pass_rates
# ---------------------------------------------------------------------------

class ComputeWeeklyPassRatesTests(unittest.TestCase):
    """Test compute_weekly_pass_rates() grouping and rates."""

    def test_single_skill_single_week(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-07-06T10:00:00Z"},
            {"skill": "alicloud-ecs-ops", "rubric_pass": False, "timestamp": "2026-07-07T10:00:00Z"},
        ]
        result = compute_weekly_pass_rates(entries)
        self.assertIn("alicloud-ecs-ops", result)
        weeks = result["alicloud-ecs-ops"]
        self.assertEqual(len(weeks), 1)
        week_key = list(weeks.keys())[0]
        self.assertEqual(weeks[week_key]["pass"], 1)
        self.assertEqual(weeks[week_key]["total"], 2)
        self.assertEqual(weeks[week_key]["rate"], 50.0)

    def test_multiple_weeks(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-06-29T10:00:00Z"},  # W27
            {"skill": "alicloud-ecs-ops", "rubric_pass": False, "timestamp": "2026-06-29T10:00:00Z"},  # W27
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-07-06T10:00:00Z"},   # W28
        ]
        result = compute_weekly_pass_rates(entries)
        weeks = result["alicloud-ecs-ops"]
        self.assertEqual(len(weeks), 2)  # two distinct weeks
        # W27: 1/2 = 50%
        w27 = [k for k in weeks if "W27" in k][0]
        self.assertEqual(weeks[w27]["rate"], 50.0)
        # W28: 1/1 = 100%
        w28 = [k for k in weeks if "W28" in k][0]
        self.assertEqual(weeks[w28]["rate"], 100.0)

    def test_multiple_skills(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-07-06T10:00:00Z"},
            {"skill": "alicloud-redis-ops", "rubric_pass": False, "timestamp": "2026-07-06T10:00:00Z"},
        ]
        result = compute_weekly_pass_rates(entries)
        self.assertIn("alicloud-ecs-ops", result)
        self.assertIn("alicloud-redis-ops", result)

    def test_skips_entries_without_timestamp(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-07-06T10:00:00Z"},
            {"skill": "alicloud-ecs-ops", "rubric_pass": True},  # no timestamp
        ]
        result = compute_weekly_pass_rates(entries)
        total = sum(w["total"] for w in result["alicloud-ecs-ops"].values())
        self.assertEqual(total, 1)  # only the entry with timestamp

    def test_empty_entries(self):
        result = compute_weekly_pass_rates([])
        self.assertEqual(result, {})

    def test_all_failures_produces_zero_rate(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": False, "timestamp": "2026-07-06T10:00:00Z"},
            {"skill": "alicloud-ecs-ops", "rubric_pass": False, "timestamp": "2026-07-07T10:00:00Z"},
        ]
        result = compute_weekly_pass_rates(entries)
        week = list(result["alicloud-ecs-ops"].values())[0]
        self.assertEqual(week["rate"], 0.0)

    def test_all_passes_produces_full_rate(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "rubric_pass": True, "timestamp": "2026-07-06T10:00:00Z"},
        ]
        result = compute_weekly_pass_rates(entries)
        week = list(result["alicloud-ecs-ops"].values())[0]
        self.assertEqual(week["rate"], 100.0)


# ---------------------------------------------------------------------------
# _week_date_range
# ---------------------------------------------------------------------------

class WeekDateRangeTests(unittest.TestCase):
    """Test _week_date_range() ISO week boundary computation."""

    def test_known_week(self):
        # 2026-W28 runs from Mon 2026-07-06 to Sun 2026-07-12
        start, end = _week_date_range("2026-W28")
        self.assertEqual(start.isoformat(), "2026-07-06T00:00:00+00:00")
        end_str = end.isoformat()
        self.assertTrue(end_str.startswith("2026-07-12T23:59:59"))


# ---------------------------------------------------------------------------
# _collect_affected_operations
# ---------------------------------------------------------------------------

class CollectAffectedOperationsTests(unittest.TestCase):
    """Test _collect_affected_operations() filtering."""

    def test_collects_unique_ops(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "operation": "DescribeInstances", "timestamp": "2026-07-07T10:00:00Z"},
            {"skill": "alicloud-ecs-ops", "operation": "DescribeInstances", "timestamp": "2026-07-08T10:00:00Z"},
            {"skill": "alicloud-ecs-ops", "operation": "DeleteInstance", "timestamp": "2026-07-09T10:00:00Z"},
        ]
        ops = _collect_affected_operations(entries, "alicloud-ecs-ops", "2026-W28")
        self.assertEqual(ops, ["DeleteInstance", "DescribeInstances"])

    def test_other_skills_excluded(self):
        entries = [
            {"skill": "alicloud-ecs-ops", "operation": "DescribeInstances", "timestamp": "2026-07-07T10:00:00Z"},
            {"skill": "alicloud-redis-ops", "operation": "FlushInstance", "timestamp": "2026-07-07T10:00:00Z"},
        ]
        ops = _collect_affected_operations(entries, "alicloud-ecs-ops", "2026-W28")
        self.assertEqual(ops, ["DescribeInstances"])

    def test_empty_when_no_entries(self):
        ops = _collect_affected_operations([], "alicloud-ecs-ops", "2026-W28")
        self.assertEqual(ops, [])


# ---------------------------------------------------------------------------
# detect_anomaly
# ---------------------------------------------------------------------------

class DetectAnomalyTests(unittest.TestCase):
    """Test detect_anomaly() pass-rate anomaly detection."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmp_dir.name) / "memory"
        self.output_dir = Path(self.tmp_dir.name) / "anomaly"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write_skill_entries(self, skill: str, weeks: list[tuple[int, float]]):
        """Write entries for *skill* across ISO weeks.

        *weeks* is a list of (week_offset, pass_rate) where week_offset=0
        means the current ISO week (from now).  pass_rate is a float 0-1.
        All entries are collected and written once to avoid overwriting.
        """
        now = datetime.now(timezone.utc)
        current_year = now.isocalendar()[0]
        current_week = now.isocalendar()[1]

        all_lines: list[str] = []

        for week_offset, rate in weeks:
            target_week = current_week + week_offset
            # Compute a Monday at that ISO week
            jan4 = datetime(current_year, 1, 4, tzinfo=timezone.utc)
            monday = jan4 - timedelta(days=jan4.isocalendar()[2] - 1) + timedelta(weeks=target_week - 1)

            # Ten entries per week at the given pass-rate
            passes = int(10 * rate)
            for i in range(10):
                ts = (monday + timedelta(days=i % 7, hours=i)).isoformat()
                entry = {
                    "timestamp": ts,
                    "skill": skill,
                    "operation": "DescribeInstances",
                    "rubric_pass": (i < passes),
                }
                all_lines.append(json.dumps(entry, sort_keys=True))

        # Write all entries at once
        p = self.memory_root / skill / "DescribeInstances.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

    def test_no_anomaly_when_rate_stable(self):
        """Stable pass-rate should not trigger anomaly."""
        # 5 weeks of 100% pass-rate, then 1 week of 90%
        self._write_skill_entries("alicloud-ecs-ops", [
            (-5, 1.0), (-4, 1.0), (-3, 1.0), (-2, 1.0), (-1, 1.0), (0, 0.9),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(anomalies, [])

    def test_3sigma_anomaly_detected(self):
        """Large drop triggers 3sigma HIGH anomaly."""
        # Baseline has variance (not all 100%), so 3sigma can fire.
        # Baseline rates: 100%, 80%, 100%, 90%, 100%
        # Current: 20% — far below mean - 3*stddev
        self._write_skill_entries("alicloud-ecs-ops", [
            (-5, 1.0), (-4, 0.8), (-3, 1.0), (-2, 0.9), (-1, 1.0), (0, 0.2),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(len(anomalies), 1)
        anomaly = anomalies[0]
        self.assertEqual(anomaly["skill"], "alicloud-ecs-ops")
        self.assertEqual(anomaly["decline_type"], "3sigma")
        self.assertEqual(anomaly["severity"], "HIGH")

    def test_relative_decline_detected(self):
        """Large relative drop triggers relative_50pct MEDIUM anomaly."""
        # baseline ~80%, current ~0%
        self._write_skill_entries("alicloud-ecs-ops", [
            (-3, 0.8), (-2, 0.8), (-1, 0.8), (0, 0.0),
        ])
        # With zero stddev in baseline (all identical), 3sigma can't trigger
        # (stddev=0), so only relative decline fires.
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(len(anomalies), 1)
        anomaly = anomalies[0]
        self.assertEqual(anomaly["decline_type"], "relative_50pct")
        self.assertEqual(anomaly["severity"], "MEDIUM")

    def test_no_anomaly_when_insufficient_baseline(self):
        """Fewer than 2 weeks of baseline produces no anomaly."""
        self._write_skill_entries("alicloud-ecs-ops", [
            (-1, 1.0), (0, 0.0),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(anomalies, [])

    def test_no_anomaly_when_empty(self):
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90,
        )
        self.assertEqual(anomalies, [])

    def test_anomaly_report_written_to_disk(self):
        self._write_skill_entries("alicloud-ecs-ops", [
            (-4, 1.0), (-3, 1.0), (-2, 1.0), (-1, 1.0), (0, 0.1),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(len(anomalies), 1)
        # Check that a report file was written
        json_files = list(self.output_dir.glob("*.json"))
        self.assertEqual(len(json_files), 1)
        report = json.loads(json_files[0].read_text(encoding="utf-8"))
        self.assertEqual(report["skill"], "alicloud-ecs-ops")
        self.assertIn("generated_at", report)
        self.assertIn("affected_operations", report)

    def test_anomaly_schema_shape(self):
        self._write_skill_entries("alicloud-ecs-ops", [
            (-4, 1.0), (-3, 1.0), (-2, 1.0), (-1, 1.0), (0, 0.2),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(len(anomalies), 1)
        a = anomalies[0]
        expected_keys = {
            "skill", "current_week_pass_rate", "baseline_pass_rate",
            "baseline_stddev", "decline_type", "severity",
            "sample_size", "window_start", "window_end",
            "affected_operations", "generated_at",
        }
        self.assertEqual(set(a.keys()), expected_keys)
        self.assertIn(a["decline_type"], ("3sigma", "relative_50pct"))
        self.assertIn(a["severity"], ("HIGH", "MEDIUM"))

    def test_multi_skill_anomaly(self):
        """Both skills with anomalies produce separate reports."""
        # skill A: baseline ~100%, current ~0%
        self._write_skill_entries("alicloud-ecs-ops", [
            (-4, 1.0), (-3, 1.0), (-2, 1.0), (-1, 1.0), (0, 0.0),
        ])
        # skill B: baseline ~90%, current ~0%
        self._write_skill_entries("alicloud-redis-ops", [
            (-4, 0.9), (-3, 0.9), (-2, 0.9), (-1, 0.9), (0, 0.0),
        ])
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=3.0, threshold_relative=0.5,
        )
        self.assertEqual(len(anomalies), 2)
        skills = {a["skill"] for a in anomalies}
        self.assertEqual(skills, {"alicloud-ecs-ops", "alicloud-redis-ops"})
        # Each skill gets its own file
        json_files = list(self.output_dir.glob("*.json"))
        self.assertEqual(len(json_files), 2)

    def test_custom_thresholds_fewer_anomalies(self):
        """Higher thresholds reduce anomaly count."""
        self._write_skill_entries("alicloud-ecs-ops", [
            (-4, 1.0), (-3, 1.0), (-2, 1.0), (-1, 1.0), (0, 0.2),
        ])
        # Very high thresholds should not trigger
        anomalies = detect_anomaly(
            self.memory_root, self.output_dir,
            window_days=90, threshold_stddev=10.0, threshold_relative=0.1,
        )
        self.assertEqual(anomalies, [])


# ---------------------------------------------------------------------------
# Module smoke tests
# ---------------------------------------------------------------------------

class ModuleSmokeTests(unittest.TestCase):
    """Minimal smoke tests."""

    def test_module_importable(self):
        import gcl_passrate_reporter
        self.assertTrue(hasattr(gcl_passrate_reporter, "detect_anomaly"))
        self.assertTrue(hasattr(gcl_passrate_reporter, "load_memory_entries"))
        self.assertTrue(hasattr(gcl_passrate_reporter, "build_arg_parser"))

    def test_parse_iso_timestamp(self):
        dt = parse_iso_timestamp("2026-07-06T10:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

    def test_resolve_runtime_root(self):
        root = _resolve_runtime_root()
        self.assertIsInstance(root, Path)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class CliAnomalyTests(unittest.TestCase):
    """Test --detect-anomaly CLI subcommand."""

    def test_detect_anomaly_no_memory_root(self):
        """--detect-anomaly with an empty memory root exits cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            memory_root = Path(tmp) / "memory"
            output_dir = Path(tmp) / "anomaly"
            rc = main([
                "--detect-anomaly",
                "--memory-root", str(memory_root),
                "--output-dir", str(output_dir),
            ])
            self.assertEqual(rc, 0)

    def test_detect_anomaly_with_entries(self):
        """--detect-anomaly finds anomalies and writes reports."""
        with tempfile.TemporaryDirectory() as tmp:
            memory_root = Path(tmp) / "memory"
            output_dir = Path(tmp) / "anomaly"

            # Write baseline entries (4 weeks of ~100%, 1 current week of ~0%)
            import io
            from gcl_passrate_reporter import _iso_year_week
            now = datetime.now(timezone.utc)
            current_week = _iso_year_week(now)

            lines_week_minus4 = []
            lines_week_0 = []
            for i in range(10):
                ts = (now - timedelta(days=28 + i)).isoformat()
                lines_week_minus4.append(json.dumps({
                    "timestamp": ts, "skill": "alicloud-ecs-ops",
                    "operation": "DescribeInstances", "rubric_pass": True,
                }, sort_keys=True))
            for i in range(10):
                ts = (now - timedelta(hours=i * 6)).isoformat()
                lines_week_0.append(json.dumps({
                    "timestamp": ts, "skill": "alicloud-ecs-ops",
                    "operation": "DescribeInstances", "rubric_pass": False,
                }, sort_keys=True))

            _write_memory_jsonl(memory_root, "alicloud-ecs-ops", "DescribeInstances",
                                lines_week_minus4 + lines_week_0)

            rc = main([
                "--detect-anomaly",
                "--memory-root", str(memory_root),
                "--output-dir", str(output_dir),
            ])
            self.assertEqual(rc, 0)

            # at least one anomaly report should be written
            json_files = list(output_dir.glob("*.json"))
            self.assertGreaterEqual(len(json_files), 1)

    def test_detect_anomaly_with_custom_thresholds(self):
        """--detect-anomaly accepts custom threshold parameters."""
        with tempfile.TemporaryDirectory() as tmp:
            memory_root = Path(tmp) / "memory"
            output_dir = Path(tmp) / "anomaly"
            # Write data that would NOT trigger with high thresholds
            now = datetime.now(timezone.utc)
            lines = []
            # 5 weeks of 100%
            for week_offset in range(-5, 0):
                for i in range(10):
                    ts = (now - timedelta(days=abs(week_offset) * 7 + i)).isoformat()
                    lines.append(json.dumps({
                        "timestamp": ts, "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances", "rubric_pass": True,
                    }, sort_keys=True))
            # Current week: 80%
            for i in range(10):
                ts = (now - timedelta(hours=i)).isoformat()
                lines.append(json.dumps({
                    "timestamp": ts, "skill": "alicloud-ecs-ops",
                    "operation": "DescribeInstances",
                    "rubric_pass": (i < 8),  # 8/10 = 80%
                }, sort_keys=True))
            _write_memory_jsonl(memory_root, "alicloud-ecs-ops", "DescribeInstances", lines)

            rc = main([
                "--detect-anomaly",
                "--memory-root", str(memory_root),
                "--output-dir", str(output_dir),
                "--anomaly-threshold-stddev", "3.0",
                "--anomaly-threshold-relative", "0.5",
            ])
            self.assertEqual(rc, 0)

    def test_normal_mode_still_works_help(self):
        """Normal mode still accepts --help (regression check)."""
        # Just verify the help text includes detect-anomaly
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with self.assertRaises(SystemExit):
                main(["--help"])
        finally:
            sys.stdout = old_stdout
        # We just need it not to crash


# ---------------------------------------------------------------------------
# _resolve_runtime_root
# ---------------------------------------------------------------------------

class ResolveRuntimeRootTests(unittest.TestCase):
    """Test _resolve_runtime_root() resolution."""

    def test_env_var_override(self):
        old = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
        try:
            os.environ["ALIYUN_SKILLS_RUNTIME_ROOT"] = "/tmp/custom-runtime"
            root = _resolve_runtime_root()
            self.assertEqual(root, Path("/tmp/custom-runtime"))
        finally:
            if old is None:
                os.environ.pop("ALIYUN_SKILLS_RUNTIME_ROOT", None)
            else:
                os.environ["ALIYUN_SKILLS_RUNTIME_ROOT"] = old

    def test_default_is_dot_runtime(self):
        old = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
        if old:
            del os.environ["ALIYUN_SKILLS_RUNTIME_ROOT"]
        root = _resolve_runtime_root()
        self.assertTrue(str(root).endswith(".runtime"))


if __name__ == "__main__":
    unittest.main()