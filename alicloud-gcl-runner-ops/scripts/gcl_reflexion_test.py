#!/usr/bin/env python3
"""Unit tests for gcl_reflexion.py — Layer 2: Reflexion Memory."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the parent directory is on sys.path for import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcl_reflexion import (
    CATEGORY_CONFIG,
    GENERALIZED_CLI_CATEGORY,
    MIN_PATTERN_COUNT,
    REMEDIATION_K_MAX,
    REMEDIATION_K_MIN,
    _load_store,
    _load_success_store,
    _save_store,
    _store_path,
    _success_patterns_path,
    _time_weighted_score,
    compute_command_hash,
    format_success_patterns,
    remediation_apply_from_trace,
    remediation_confirm_window_k,
    remediation_record_opportunities,
    remediation_record_success_streak,
    reflexion_aggregate_generalized,
    normalize_error_pattern,
    reflexion_extract,
    reflexion_extract_wrapper_lite,
    reflexion_maintain,
    reflexion_promote_from_memory,
    reflexion_report,
    reflexion_retrieve,
    reflexion_store,
    reflexion_store_wrapper_lite,
    success_report,
    success_retrieve,
    success_store,
    wrapper_error_eligible,
)


class ReflexionExtractTests(unittest.TestCase):
    """Tests for reflexion_extract()."""

    def test_none_when_no_failure_pattern(self):
        trace = {"final": {"status": "PASS"}}
        self.assertIsNone(reflexion_extract(trace))

    def test_extracts_valid_pattern(self):
        trace = {
            "failure_pattern": {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DeleteInstance",
                "error": "MissingParam: InstanceId",
                "fix": "Add .N suffix",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["category"], "cli_parameter")
        self.assertEqual(pattern["command"], "aliyun ecs DeleteInstance")
        self.assertEqual(pattern["count"], 1)
        self.assertIn("first_seen", pattern)

    def test_unknown_category_returns_none(self):
        trace = {"failure_pattern": {"category": "weird_category", "command": "test"}}
        pattern = reflexion_extract(trace)
        self.assertIsNone(pattern)

    def test_empty_failure_pattern_returns_none(self):
        trace = {"failure_pattern": {}}
        pattern = reflexion_extract(trace)
        # Empty pattern has no actionable data to learn from
        self.assertIsNone(pattern)

    def test_skill_generation_category(self):
        trace = {
            "failure_pattern": {
                "category": "skill_generation",
                "issue_type": "Missing YAML frontmatter",
                "fix_pattern": "Always start with --- block",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "skill_generation")
        self.assertEqual(pattern["issue_type"], "Missing YAML frontmatter")

    def test_cross_skill_category(self):
        trace = {
            "failure_pattern": {
                "category": "cross_skill",
                "source_skill": "redis-ops",
                "target_skill": "ecs-ops",
                "failure_pattern": "RunCommand encoding fails",
                "resolution": "Use base64 encoding",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "cross_skill")
        self.assertEqual(pattern["source_skill"], "redis-ops")

    def test_runtime_category(self):
        trace = {
            "failure_pattern": {
                "category": "runtime",
                "skill": "ecs-ops",
                "operation": "StopInstance",
                "failure_pattern": "Stuck in Stopping state",
                "root_cause": "Dependent services not stopped",
                "prevention": "Check processes before stop",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "runtime")
        self.assertEqual(pattern["operation"], "StopInstance")

    def test_token_efficiency_category(self):
        trace = {
            "failure_pattern": {
                "category": "token_efficiency",
                "te_rule": "TE-1",
                "common_violation": "Hardcoded region lists",
                "fix": "Use aliyun regions query",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "token_efficiency")
        self.assertEqual(pattern["te_rule"], "TE-1")

    def test_max_iter_category(self):
        trace = {
            "failure_pattern": {
                "category": "max_iter",
                "skill": "alicloud-ecs-ops",
                "operation": "DeleteInstance",
                "failing_dimensions": "correctness, traceability",
                "best_score": "2.5",
                "fix": "Review failing dimensions",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "max_iter")
        self.assertEqual(pattern["skill"], "alicloud-ecs-ops")
        self.assertEqual(pattern["failing_dimensions"], "correctness, traceability")
        self.assertEqual(pattern["count"], 1)
        self.assertIn("first_seen", pattern)
        self.assertIn("last_seen", pattern)

    def test_near_miss_category(self):
        trace = {
            "failure_pattern": {
                "category": "near_miss",
                "skill": "alicloud-ecs-ops",
                "operation": "DescribeInstances",
                "low_dimensions": "safety",
                "scores": "safety=0.5",
                "fix": "Monitor low-scoring dimensions",
            }
        }
        pattern = reflexion_extract(trace)
        self.assertEqual(pattern["category"], "near_miss")
        self.assertEqual(pattern["low_dimensions"], "safety")
        self.assertEqual(pattern["scores"], "safety=0.5")


class ReflexionStoreTests(unittest.TestCase):
    """Tests for reflexion_store()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _pattern(self, category="cli_parameter", **kw):
        base = {"category": category, "count": 1}
        base.update(kw)
        return base

    def test_store_none_is_noop(self):
        rc = reflexion_store(None, root=self.root)
        self.assertEqual(rc, 0)
        store = _load_store(self.root)
        self.assertEqual(sum(len(v) for v in store.values()), 0)

    def test_store_new_pattern(self):
        pat = self._pattern(skill="ecs-ops", command="aliyun ecs DeleteInstance",
                            error="MissingParam", fix="Add suffix", root_cause="Missing .N")
        rc = reflexion_store(pat, root=self.root)
        self.assertEqual(rc, 0)
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 1)
        self.assertEqual(store["cli_parameter"][0]["count"], 1)

    def test_store_dedup_increments_count(self):
        pat = self._pattern(skill="ecs-ops", command="aliyun ecs DeleteInstance",
                            error="MissingParam", fix="Add suffix", root_cause="Missing .N")
        reflexion_store(pat, root=self.root)
        reflexion_store(pat, root=self.root)
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 1)
        self.assertEqual(store["cli_parameter"][0]["count"], 2)

    def test_different_errors_are_separate(self):
        pat1 = self._pattern(skill="ecs-ops", command="aliyun ecs DeleteInstance",
                             error="MissingParam", fix="Add suffix", root_cause="Missing .N")
        pat2 = self._pattern(skill="ecs-ops", command="aliyun ecs DeleteInstance",
                             error="InvalidParam", fix="Use JSON", root_cause="Wrong format")
        reflexion_store(pat1, root=self.root)
        reflexion_store(pat2, root=self.root)
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 2)

    def test_cross_skill_dedup(self):
        pat = self._pattern(category="cross_skill", source_skill="redis-ops",
                            target_skill="ecs-ops", failure_pattern="Encoding fails",
                            resolution="Use base64")
        reflexion_store(pat, root=self.root)
        reflexion_store(pat, root=self.root)
        store = _load_store(self.root)
        self.assertEqual(len(store["cross_skill"]), 1)
        self.assertEqual(store["cross_skill"][0]["count"], 2)

    def test_persistence_across_loads(self):
        pat = self._pattern(skill="ecs-ops", command="test", error="err", fix="fix", root_cause="rc")
        reflexion_store(pat, root=self.root)
        # Reload from disk
        store2 = _load_store(self.root)
        self.assertEqual(len(store2["cli_parameter"]), 1)
        self.assertEqual(store2["cli_parameter"][0]["error"], "err")


def _sample_success_pattern(**overrides) -> dict:
    cmd = "aliyun ecs DeleteInstance --InstanceId.1 i-abc123 --RegionId cn-hangzhou"
    base = {
        "skill": "alicloud-ecs-ops",
        "operation": "DeleteInstance",
        "command_excerpt": cmd[:120],
        "command_hash": compute_command_hash(cmd),
        "capture_reason": "multi_iter",
        "iterations": 2,
        "scores_summary": "correctness=1.0 safety=1.0",
        "scores_min": 0.85,
        "preflight_had_traps": False,
        "trap_count": 0,
        "hint": "Use --InstanceId.1 RepeatList suffix",
        "source": "gcl-runner",
    }
    base.update(overrides)
    return base


class SuccessPatternStoreTests(unittest.TestCase):
    """R4: success_store() / dedup / persistence."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_store_none_is_noop(self):
        rc = success_store(None, root=self.root)
        self.assertEqual(rc, 0)
        store = _load_success_store(self.root)
        self.assertEqual(store["patterns"], [])

    def test_store_new_pattern(self):
        pat = _sample_success_pattern()
        rc = success_store(pat, root=self.root)
        self.assertEqual(rc, 0)
        store = _load_success_store(self.root)
        self.assertEqual(len(store["patterns"]), 1)
        self.assertEqual(store["patterns"][0]["count"], 1)
        self.assertEqual(store["patterns"][0]["skill"], "alicloud-ecs-ops")

    def test_dedup_increments_count(self):
        pat = _sample_success_pattern()
        success_store(pat, root=self.root)
        success_store(pat, root=self.root)
        store = _load_success_store(self.root)
        self.assertEqual(len(store["patterns"]), 1)
        self.assertEqual(store["patterns"][0]["count"], 2)

    def test_different_capture_reason_separate_rows(self):
        pat1 = _sample_success_pattern(capture_reason="multi_iter")
        pat2 = _sample_success_pattern(capture_reason="traps_informed")
        success_store(pat1, root=self.root)
        success_store(pat2, root=self.root)
        store = _load_success_store(self.root)
        self.assertEqual(len(store["patterns"]), 2)

    def test_hint_refresh_when_scores_min_improves(self):
        pat = _sample_success_pattern(scores_min=0.7, hint="old hint")
        success_store(pat, root=self.root)
        improved = _sample_success_pattern(scores_min=0.95, hint="better hint")
        success_store(improved, root=self.root)
        row = _load_success_store(self.root)["patterns"][0]
        self.assertEqual(row["count"], 2)
        self.assertEqual(row["scores_min"], 0.95)
        self.assertEqual(row["hint"], "better hint")

    def test_masked_secret_skipped(self):
        pat = _sample_success_pattern(hint="token=<masked>")
        rc = success_store(pat, root=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(_load_success_store(self.root)["patterns"], [])

    def test_persistence_and_atomic_file(self):
        pat = _sample_success_pattern()
        success_store(pat, root=self.root)
        sp = _success_patterns_path(self.root)
        self.assertTrue(sp.exists())
        self.assertFalse(sp.with_suffix(sp.suffix + ".tmp").exists())
        store2 = _load_success_store(self.root)
        self.assertEqual(len(store2["patterns"]), 1)
        self.assertEqual(store2["version"], "1.0.0")


class SuccessPatternRetrieveTests(unittest.TestCase):
    """R4: success_retrieve() filtering and ranking."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_retrieve_filters_skill_and_operation(self):
        success_store(_sample_success_pattern(), root=self.root)
        success_store(
            _sample_success_pattern(
                skill="alicloud-redis-ops",
                operation="DeleteInstance",
            ),
            root=self.root,
        )
        hits = success_retrieve("alicloud-ecs-ops", operation="DeleteInstance", root=self.root)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["skill"], "alicloud-ecs-ops")

    def test_top_k_limit(self):
        for reason in ("multi_iter", "traps_informed", "score_recovery"):
            success_store(_sample_success_pattern(capture_reason=reason), root=self.root)
        hits = success_retrieve("alicloud-ecs-ops", top_k=2, root=self.root)
        self.assertEqual(len(hits), 2)
        for row in hits:
            self.assertIn("_score", row)

    def test_min_count_filter(self):
        pat = _sample_success_pattern()
        success_store(pat, root=self.root)
        self.assertEqual(
            success_retrieve("alicloud-ecs-ops", min_count=2, root=self.root),
            [],
        )
        success_store(pat, root=self.root)
        self.assertEqual(
            len(success_retrieve("alicloud-ecs-ops", min_count=2, root=self.root)),
            1,
        )

    def test_format_success_patterns_empty_and_nonempty(self):
        empty = format_success_patterns([])
        self.assertIn("none", empty.lower())
        pat = _sample_success_pattern()
        success_store(pat, root=self.root)
        hits = success_retrieve("alicloud-ecs-ops", root=self.root)
        text = format_success_patterns(hits, max_chars=600)
        self.assertIn("multi_iter", text)
        self.assertLessEqual(len(text), 600)


class TimeWeightedScoreTests(unittest.TestCase):
    """Tests for _time_weighted_score()."""

    def test_full_weight_when_no_timestamp(self):
        score = _time_weighted_score({"count": 10}, decay_days=90)
        self.assertEqual(score, 10.0)

    def _fixed_now(self):
        """Return a fixed datetime (2026-06-20T12:00:00Z) so time tests are deterministic."""
        from datetime import datetime
        return datetime.fromisoformat("2026-06-20T12:00:00+00:00")

    def test_recent_pattern_full_weight(self):
        score = _time_weighted_score(
            {"count": 5, "last_seen": "2026-06-20T12:00:00Z"},
            now=self._fixed_now(),
            decay_days=90,
        )
        self.assertAlmostEqual(score, 5.0, delta=0.001)

    def test_old_pattern_half_weight(self):
        score = _time_weighted_score(
            {"count": 5, "last_seen": "2026-03-20T12:00:00Z"},
            now=self._fixed_now(),
            decay_days=90,
        )
        self.assertAlmostEqual(score, 2.5, delta=0.3)

    def test_mid_age_pattern_partial_decay(self):
        score = _time_weighted_score(
            {"count": 10, "last_seen": "2026-05-20T12:00:00Z"},
            now=self._fixed_now(),
            decay_days=90,
        )
        self.assertAlmostEqual(score, 8.3, delta=0.5)

    def test_low_count_recent_beats_high_count_old(self):
        recent = _time_weighted_score(
            {"count": 6, "last_seen": "2026-06-19T12:00:00Z"},
            now=self._fixed_now(),
            decay_days=90,
        )
        ancient = _time_weighted_score(
            {"count": 10, "last_seen": "2026-01-01T12:00:00Z"},
            now=self._fixed_now(),
            decay_days=90,
        )
        self.assertGreater(recent, ancient)


class ReflexionMaintainTests(unittest.TestCase):
    """Tests for reflexion_maintain()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self._seed()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _seed(self):
        store = {cat: [] for cat in CATEGORY_CONFIG}
        store["cli_parameter"] = [
            {"skill": "ecs-ops", "command": "Del", "error": "E1", "fix": "F1",
             "root_cause": "R1", "count": 5},
            {"skill": "ecs-ops", "command": "Del", "error": "E2", "fix": "F2",
             "root_cause": "R2", "count": 1},  # below MIN_PATTERN_COUNT
            {"skill": "ecs-ops", "command": "Del", "error": "E3", "fix": "F3",
             "root_cause": "R3", "count": 2},  # below MIN_PATTERN_COUNT
        ]
        store["cross_skill"] = [
            {"source_skill": "redis-ops", "target_skill": "ecs-ops",
             "failure_pattern": "Encoding", "resolution": "base64", "count": 7},
            {"source_skill": "rds-ops", "target_skill": "ecs-ops",
             "failure_pattern": "Timeout", "resolution": "chunk", "count": 1},  # below
        ]
        _save_store(store, self.root)

    def test_dry_run_reports_counts(self):
        result = reflexion_maintain(root=self.root, apply=False)
        self.assertEqual(result["total_before"], 5)
        self.assertEqual(result["total_pruned"], 3)  # 2 cli + 1 cross_skill
        self.assertEqual(result["total_after"], 2)
        self.assertFalse(result["applied"])
        # Store unchanged on disk
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 3)

    def test_apply_prunes_low_count(self):
        result = reflexion_maintain(root=self.root, apply=True)
        self.assertEqual(result["total_pruned"], 3)
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 1)  # only count >= 3
        self.assertEqual(len(store["cross_skill"]), 1)
        self.assertEqual(store["cli_parameter"][0]["count"], 5)

    def test_custom_min_count(self):
        result = reflexion_maintain(root=self.root, min_count=5, apply=True)
        self.assertEqual(result["total_pruned"], 3)  # cli:1 kept(5>=5)+2 pruned + cross:1 kept(7>=5)+1 pruned

    def test_empty_store(self):
        empty_root = Path(tempfile.mkdtemp())
        result = reflexion_maintain(root=empty_root, apply=True)
        self.assertEqual(result["total_before"], 0)
        self.assertEqual(result["total_pruned"], 0)

    def _seed_decay_store(self):
        """Seed with patterns at various ages for decay tests."""
        from gcl_reflexion import _now_iso
        now = _now_iso()
        # Use the temp root from setUp
        store = {cat: [] for cat in CATEGORY_CONFIG}
        store["cli_parameter"] = [
            # recent (not pruned by decay)
            {"skill": "ecs-ops", "command": "Del", "error": "E1", "fix": "F1",
             "root_cause": "R1", "count": 5, "last_seen": "2026-06-20T12:00:00Z"},
            # old (pruned by decay)
            {"skill": "ecs-ops", "command": "Del", "error": "E2", "fix": "F2",
             "root_cause": "R2", "count": 5, "last_seen": "2025-01-01T12:00:00Z"},
            # low count (pruned by count)
            {"skill": "ecs-ops", "command": "Del", "error": "E3", "fix": "F3",
             "root_cause": "R3", "count": 1, "last_seen": "2026-06-20T12:00:00Z"},
        ]
        return store, now

    def test_decay_dry_run_reports_decay_prunes(self):
        store, _ = self._seed_decay_store()
        _save_store(store, self.root)
        result = reflexion_maintain(root=self.root, min_count=3, decay_days=90, apply=False)
        # E1 (count=5, recent) kept, E2 (count=5, old) pruned by decay, E3 (count=1) pruned by count
        self.assertEqual(result["total_before"], 3)
        self.assertEqual(result["total_pruned"], 2)
        self.assertGreater(result["pruned_by_decay"], 0)
        self.assertGreater(result["pruned_by_count"], 0)
        # Store unchanged on disk (dry-run)
        store_disk = _load_store(self.root)
        self.assertEqual(len(store_disk["cli_parameter"]), 3)

    def test_decay_apply_prunes_old_patterns(self):
        store, _ = self._seed_decay_store()
        _save_store(store, self.root)
        result = reflexion_maintain(root=self.root, min_count=3, decay_days=90, apply=True)
        self.assertEqual(result["total_pruned"], 2)
        store_after = _load_store(self.root)
        self.assertEqual(len(store_after["cli_parameter"]), 1)
        self.assertEqual(store_after["cli_parameter"][0]["error"], "E1")


class ReflexionReportTests(unittest.TestCase):
    """Tests for reflexion_report()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.output_dir = Path(self.tmpdir.name) / "output"
        self.output_path = self.output_dir / "failure-patterns.md"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _seed(self):
        store = {cat: [] for cat in CATEGORY_CONFIG}
        store["cli_parameter"] = [
            {"skill": "ecs-ops", "command": "DeleteInstance", "error": "MissingParam",
             "fix": "Add .N suffix", "root_cause": "Missing .N", "count": 5},
            {"skill": "redis-ops", "command": "DeleteInstance", "error": "MissingParam",
             "fix": "Add .N suffix", "root_cause": "Missing .N", "count": 3},
        ]
        store["cross_skill"] = [
            {"source_skill": "redis-ops", "target_skill": "ecs-ops",
             "failure_pattern": "Encoding", "resolution": "base64", "count": 3},
        ]
        _save_store(store, self.root)

    def test_generates_markdown(self):
        self._seed()
        rc = reflexion_report(root=self.root, output_path=self.output_path)
        self.assertEqual(rc, 0)
        self.assertTrue(self.output_path.exists())
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("CLI Parameter Errors", content)
        self.assertIn("ecs-ops", content)
        self.assertIn("Cross-Skill Composition Failures", content)
        self.assertIn("Encoding", content)

    def test_markdown_includes_correct_table(self):
        self._seed()
        reflexion_report(root=self.root, output_path=self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        # Table header includes the new Last Seen column
        self.assertIn("|Skill|Command|Error Pattern|Root Cause|Fix|Count|Last Seen|", content)
        # Table rows
        self.assertIn("|ecs-ops|DeleteInstance|MissingParam|Missing .N|Add .N suffix|5|", content)
        # Usage guidelines
        self.assertIn("Usage Guidelines", content)
        self.assertIn("gcl_reflexion.py report", content)

    def test_empty_store_produces_no_category_tables(self):
        rc = reflexion_report(root=self.root, output_path=self.output_path)
        self.assertEqual(rc, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("Failure Patterns", content)
        # No CLI Parameter Errors table since store is empty
        self.assertNotIn("CLI Parameter Errors", content)

    def test_sorted_by_count_descending(self):
        store = {cat: [] for cat in CATEGORY_CONFIG}
        store["cli_parameter"] = [
            {"skill": "b", "command": "c", "error": "e1", "fix": "f",
             "root_cause": "r", "count": 1},
            {"skill": "a", "command": "c", "error": "e2", "fix": "f",
             "root_cause": "r", "count": 10},
        ]
        _save_store(store, self.root)
        reflexion_report(root=self.root, output_path=self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        # a (count=10) should appear before b (count=1)
        a_pos = content.index("|a|")
        b_pos = content.index("|b|")
        self.assertLess(a_pos, b_pos, "higher count should appear first")


class SuccessReportTests(unittest.TestCase):
    """R4 4.5: success_report() → docs/success-patterns.md."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.output_path = Path(self.tmpdir.name) / "success-patterns.md"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_empty_store_generates_header_only(self):
        rc = success_report(root=self.root, output_path=self.output_path)
        self.assertEqual(rc, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("Success Patterns", content)
        self.assertIn("Usage Guidelines", content)
        self.assertIn("success-report", content)
        self.assertNotIn("Multi-Iteration Recovery", content)

    def test_generates_grouped_tables(self):
        success_store(_sample_success_pattern(), root=self.root)
        success_store(
            _sample_success_pattern(capture_reason="traps_informed"),
            root=self.root,
        )
        rc = success_report(root=self.root, output_path=self.output_path)
        self.assertEqual(rc, 0)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("Multi-Iteration Recovery", content)
        self.assertIn("Trap-Informed Pass", content)
        self.assertIn("alicloud-ecs-ops", content)
        self.assertIn("|Skill|Operation|Command|Hint|Count|Scores Min|Last Seen|", content)


class ErrorNormalizeTests(unittest.TestCase):
    """R5.1: normalize_error_pattern() cross-skill grouping keys."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_missing_param_colon_param(self):
        norm = normalize_error_pattern("MissingParam: InstanceId")
        self.assertEqual(norm["error_code"], "MissingParam")
        self.assertEqual(norm["param"], "InstanceId")
        self.assertEqual(norm["normalized_key"], "MissingParam:InstanceId")
        self.assertEqual(norm["semantic"], "repeatlist_suffix")

    def test_same_key_across_products(self):
        cases = [
            ("MissingParam: InstanceId", "aliyun ecs DeleteInstance --RegionId cn-hangzhou"),
            ("MissingParam: InstanceId", "aliyun rds DeleteDBInstance --DBInstanceId rm-abc"),
            ("missingparam: instanceid", "aliyun r-kvstore DeleteInstance --InstanceId r-abc"),
        ]
        keys = {normalize_error_pattern(err, cmd)["normalized_key"] for err, cmd in cases}
        self.assertEqual(keys, {"MissingParam:InstanceId"})

    def test_invalid_parameter_region(self):
        norm = normalize_error_pattern("InvalidParameter: RegionId is invalid")
        self.assertEqual(norm["normalized_key"], "InvalidParameter:RegionId")
        self.assertEqual(norm["semantic"], "region_format")

    def test_empty_error_is_noop(self):
        norm = normalize_error_pattern("")
        self.assertEqual(norm["normalized_key"], "")

    def test_unknown_text_no_false_group(self):
        norm = normalize_error_pattern("something went wrong unexpectedly")
        self.assertEqual(norm["normalized_key"], "")

    def test_store_enriches_cli_parameter(self):
        pat = {
            "category": "cli_parameter",
            "skill": "alicloud-ecs-ops",
            "command": "aliyun ecs DeleteInstance --RegionId cn-hangzhou",
            "error": "MissingParam: InstanceId",
            "fix": "Use .N suffix",
            "root_cause": "repeatlist",
            "count": 1,
        }
        reflexion_store(pat, root=self.root)
        store = _load_store(self.root)
        row = store["cli_parameter"][0]
        self.assertEqual(row["normalized_key"], "MissingParam:InstanceId")
        self.assertEqual(row["semantic"], "repeatlist_suffix")


class RemediationTests(unittest.TestCase):
    """R6: remediation confirmation and stability tracking."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _trap_row(self) -> dict:
        reflexion_store(
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DeleteInstance --RegionId cn-hangzhou",
                "error": "MissingParam: InstanceId",
                "fix": "Use --InstanceId.1",
                "root_cause": "repeatlist",
                "count": 10,
            },
            root=self.root,
        )
        hits = reflexion_retrieve("alicloud-ecs-ops", root=self.root)
        self.assertEqual(len(hits), 1)
        return hits[0]

    def test_confirm_window_k_scales_with_frequency(self):
        row = {"count": 3, "total_opportunities": 0}
        self.assertEqual(remediation_confirm_window_k(row), REMEDIATION_K_MIN)
        row = {"count": 8, "total_opportunities": 3}
        self.assertEqual(remediation_confirm_window_k(row), 4)
        row = {"count": 15, "total_opportunities": 10}
        self.assertEqual(remediation_confirm_window_k(row), REMEDIATION_K_MAX)

    def test_success_streak_confirms_remediation(self):
        trap = self._trap_row()
        k = remediation_confirm_window_k(
            _load_store(self.root)["cli_parameter"][0]
        )
        for _ in range(k):
            remediation_record_opportunities([trap], root=self.root)
            remediation_record_success_streak([trap], root=self.root)
        row = _load_store(self.root)["cli_parameter"][0]
        self.assertTrue(row["remediated"])
        self.assertTrue(row["remediated_at"])
        self.assertEqual(row["total_opportunities"], k)
        self.assertEqual(row["consecutive_successes"], k)

    def test_failure_unmarks_remediation(self):
        self._trap_row()
        store_row = _load_store(self.root)["cli_parameter"][0]
        store_row["remediated"] = True
        store_row["remediated_at"] = "2026-06-21T00:00:00Z"
        store_row["consecutive_successes"] = 5
        _save_store(_load_store(self.root), self.root)
        reflexion_store(
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DeleteInstance --RegionId cn-hangzhou",
                "error": "MissingParam: InstanceId",
                "fix": "Use --InstanceId.1",
                "root_cause": "repeatlist",
            },
            root=self.root,
        )
        row = _load_store(self.root)["cli_parameter"][0]
        self.assertFalse(row["remediated"])
        self.assertEqual(row["consecutive_successes"], 0)
        self.assertGreaterEqual(row["recent_failures"], 1)

    def test_remediated_deprioritized_in_retrieve(self):
        self._trap_row()
        reflexion_store(
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                "error": "InvalidParameter: RegionId",
                "fix": "Check region",
                "root_cause": "region",
                "count": 15,
            },
            root=self.root,
        )
        store = _load_store(self.root)
        for row in store["cli_parameter"]:
            if row.get("error") == "MissingParam: InstanceId":
                row["remediated"] = True
        _save_store(store, self.root)
        hits = reflexion_retrieve("alicloud-ecs-ops", top_k=2, root=self.root)
        self.assertEqual(hits[0]["error"], "InvalidParameter: RegionId")

    def test_apply_from_trace_pass(self):
        trap = self._trap_row()
        trace = {
            "memory_preflight": {"known_traps": [trap]},
            "final": {"status": "PASS"},
        }
        result = remediation_apply_from_trace(trace, root=self.root)
        self.assertTrue(result["opportunities_recorded"])
        self.assertEqual(result["success_streak"]["updated"], 1)
        row = _load_store(self.root)["cli_parameter"][0]
        self.assertEqual(row["total_opportunities"], 1)
        self.assertEqual(row["consecutive_successes"], 1)


class CrossSkillAggregateTests(unittest.TestCase):
    """R5.2–5.3: generalized_cli aggregate + tiered retrieve."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _store_missing_param(self, skill: str, fix: str, count: int = 3) -> None:
        reflexion_store(
            {
                "category": "cli_parameter",
                "skill": skill,
                "command": f"aliyun x DeleteThing --RegionId cn-hangzhou",
                "error": "MissingParam: InstanceId",
                "fix": fix,
                "root_cause": "repeatlist",
                "count": count,
            },
            root=self.root,
        )

    def test_aggregate_requires_min_skills(self):
        self._store_missing_param("alicloud-ecs-ops", "fix-ecs")
        self._store_missing_param("alicloud-rds-ops", "fix-rds")
        result = reflexion_aggregate_generalized(root=self.root, min_skills=3, apply=True)
        self.assertEqual(result["generalized_after"], 0)
        store = _load_store(self.root)
        self.assertEqual(store[GENERALIZED_CLI_CATEGORY], [])

    def test_aggregate_builds_generalized_row(self):
        for skill, fix in (
            ("alicloud-ecs-ops", "Use .N suffix"),
            ("alicloud-rds-ops", "Use .N suffix"),
            ("alicloud-redis-ops", "Use .N suffix"),
        ):
            self._store_missing_param(skill, fix)
        result = reflexion_aggregate_generalized(root=self.root, min_skills=3, apply=True)
        self.assertEqual(result["generalized_after"], 1)
        row = _load_store(self.root)[GENERALIZED_CLI_CATEGORY][0]
        self.assertEqual(row["normalized_key"], "MissingParam:InstanceId")
        self.assertEqual(row["skill_count"], 3)
        self.assertIn("alicloud-ecs-ops", row["skills"])

    def test_retrieve_prefers_specific_over_generalized(self):
        for skill in ("alicloud-ecs-ops", "alicloud-rds-ops", "alicloud-redis-ops"):
            self._store_missing_param(skill, "Use .N suffix", count=10)
        reflexion_aggregate_generalized(root=self.root, min_skills=3, apply=True)
        store = _load_store(self.root)
        store["cli_parameter"] = [
            p for p in store["cli_parameter"] if p.get("skill") != "alicloud-ecs-ops"
        ]
        _save_store(store, self.root)
        reflexion_store(
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DeleteInstance --RegionId cn-hangzhou",
                "error": "MissingParam: InstanceId",
                "fix": "ECS-specific fix",
                "root_cause": "repeatlist",
                "count": 1,
            },
            root=self.root,
        )
        hits = reflexion_retrieve("alicloud-ecs-ops", top_k=3, root=self.root)
        self.assertGreaterEqual(len(hits), 2)
        self.assertEqual(hits[0]["category"], "cli_parameter")
        self.assertEqual(hits[0].get("_tier"), 0)
        gen = [h for h in hits if h["category"] == GENERALIZED_CLI_CATEGORY]
        self.assertEqual(len(gen), 1)
        self.assertEqual(gen[0].get("_tier"), 1)
        self.assertLess(hits.index(gen[0]), len(hits))


class ReflexionRetrieveTests(unittest.TestCase):
    """Tests for reflexion_retrieve() — R2 pre-flight read path."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_retrieve_filters_by_skill_and_operation(self) -> None:
        from gcl_reflexion import _save_store, format_known_traps, reflexion_retrieve

        store = {
            "cli_parameter": [
                {
                    "skill": "alicloud-ecs-ops",
                    "command": "aliyun ecs DeleteInstance",
                    "error": "E1",
                    "fix": "F1",
                    "root_cause": "RC",
                    "count": 5,
                    "last_seen": "2026-06-20T12:00:00Z",
                },
                {
                    "skill": "alicloud-rds-ops",
                    "command": "aliyun rds DeleteDBInstance",
                    "error": "E2",
                    "fix": "F2",
                    "root_cause": "RC",
                    "count": 3,
                    "last_seen": "2026-06-20T12:00:00Z",
                },
            ],
        }
        for cat in ("skill_generation", "cross_skill", "runtime", "token_efficiency", "max_iter", "near_miss"):
            store.setdefault(cat, [])
        _save_store(store, self.root)

        hits = reflexion_retrieve(
            "alicloud-ecs-ops",
            operation="DeleteInstance",
            top_k=3,
            root=self.root,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["error"], "E1")

        text = format_known_traps(hits)
        self.assertIn("E1", text)
        self.assertIn("count=5", text)

    def test_format_known_traps_filters_low_quality(self) -> None:
        from gcl_reflexion import format_known_traps

        patterns = [
            {
                "category": "cli_parameter",
                "error": "E1",
                "fix": "F1",
                "root_cause": "RC1",
                "count": 5,
            },
            {
                "category": "cli_parameter",
                "error": "E2",
                "fix": "F2",
                "root_cause": "",  # empty root_cause -> filtered
                "count": 5,
            },
            {
                "category": "cli_parameter",
                "error": "E3",
                "fix": "F3",
                "root_cause": "RC3",
                "count": 1,  # low count -> filtered
            },
        ]
        text = format_known_traps(patterns)
        self.assertIn("E1", text)
        self.assertNotIn("E2", text)
        self.assertNotIn("E3", text)


class CLITests(unittest.TestCase):
    """Smoke tests for the CLI entry point."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_extract_no_pattern(self):
        trace = {"final": {"status": "PASS"}}
        trace_path = self.root / "trace.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        from gcl_reflexion import main as reflexion_main
        rc = reflexion_main(["extract", "--trace", str(trace_path)])
        self.assertEqual(rc, 0)

    def test_extract_with_pattern(self):
        trace = {"failure_pattern": {"category": "cli_parameter", "skill": "ecs-ops",
                                      "command": "test", "error": "E1", "fix": "F1"}}
        trace_path = self.root / "trace2.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        from gcl_reflexion import main as reflexion_main
        rc = reflexion_main(["extract", "--trace", str(trace_path)])
        self.assertEqual(rc, 0)

    def test_store_from_trace(self):
        trace = {"failure_pattern": {"category": "cli_parameter", "skill": "ecs-ops",
                                      "command": "test", "error": "E1", "fix": "F1"}}
        trace_path = self.root / "trace3.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        from gcl_reflexion import main as reflexion_main
        rc = reflexion_main([
            "store", "--trace", str(trace_path),
            "--reflexion-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        store = _load_store(self.root)
        self.assertEqual(len(store["cli_parameter"]), 1)

    def test_report_and_maintain(self):
        # Seed via store, then report (in tmpdir to avoid cwd pollution)
        pat = {"category": "cli_parameter", "skill": "ecs-ops", "command": "test",
               "error": "E1", "fix": "F1", "root_cause": "RC"}
        reflexion_store(pat, root=self.root)
        from gcl_reflexion import main as reflexion_main
        output = self.root / "report.md"
        # Override SKILLS_DIR so report writes inside tmpdir, not cwd
        old_env = os.environ.get("SKILLS_DIR")
        os.environ["SKILLS_DIR"] = str(self.root)
        try:
            rc = reflexion_main(["report", "--reflexion-root", str(self.root)])
            # report without --output-path won't use our path, but shouldn't crash
            self.assertEqual(rc, 0)
        finally:
            if old_env is None:
                os.environ.pop("SKILLS_DIR", None)
            else:
                os.environ["SKILLS_DIR"] = old_env
        # maintain dry-run
        rc2 = reflexion_main(["maintain", "--reflexion-root", str(self.root)])
        self.assertEqual(rc2, 0)
        # maintain apply
        rc3 = reflexion_main(["maintain", "--apply", "--reflexion-root", str(self.root)])
        self.assertEqual(rc3, 0)

    def test_report_writes_both_failure_and_success_files(self):
        """A1.5: `report` subcommand writes both docs/failure-patterns.md AND docs/success-patterns.md."""
        # Seed both stores
        reflexion_store(
            {"category": "cli_parameter", "skill": "ecs-ops", "command": "test",
             "error": "E1", "fix": "F1", "root_cause": "RC"},
            root=self.root,
        )
        success_store(
            {
                "skill": "ecs-ops",
                "operation": "DescribeInstances",
                "command_excerpt": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                "command_hash": "sha256:" + "0" * 64,
                "capture_reason": "multi_iter",
                "iterations": 2,
                "scores_summary": "correctness=1.0,safety=1.0",
                "scores_min": 1.0,
                "preflight_had_traps": False,
                "trap_count": 0,
                "hint": "Used --RegionId explicitly to skip pre-flight prompt",
                "source": "test",
            },
            root=self.root,
        )
        # Redirect SKILLS_DIR to tmpdir so report writes inside our root
        import os
        old_env = os.environ.get("SKILLS_DIR")
        os.environ["SKILLS_DIR"] = str(self.root)
        try:
            from gcl_reflexion import main as reflexion_main
            rc = reflexion_main(["report", "--reflexion-root", str(self.root)])
            self.assertEqual(rc, 0)
            self.assertTrue(
                (self.root / "docs/failure-patterns.md").exists(),
                "docs/failure-patterns.md should be written by `report`",
            )
            self.assertTrue(
                (self.root / "docs/success-patterns.md").exists(),
                "docs/success-patterns.md should be written by `report`",
            )
            # Verify success-patterns.md actually contains our seeded pattern
            success_content = (self.root / "docs/success-patterns.md").read_text(encoding="utf-8")
            self.assertIn("DescribeInstances", success_content)
        finally:
            if old_env is None:
                os.environ.pop("SKILLS_DIR", None)
            else:
                os.environ["SKILLS_DIR"] = old_env


class WrapperLiteL2Tests(unittest.TestCase):
    """Plan B + C: wrapper failure → Layer 2."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.memory_root = self.root / "memory"
        self.reflexion_root = self.root / "reflexion"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_wrapper_error_eligible_allow_deny(self):
        self.assertTrue(wrapper_error_eligible("InvalidParameter"))
        self.assertFalse(wrapper_error_eligible("Throttling"))
        self.assertFalse(wrapper_error_eligible("exit_code_1"))
        self.assertFalse(wrapper_error_eligible(""))

    def test_denylist_extract_returns_none(self):
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DescribeInstances",
            command="aliyun ecs DescribeInstances",
            error_code="Throttling",
            output={"Code": "Throttling"},
        )
        self.assertIsNone(pattern)

    def test_promote_skipped_below_min_count(self):
        skill_dir = self.memory_root / "alicloud-ecs-ops"
        skill_dir.mkdir(parents=True)
        jsonl = skill_dir / "DescribeInstances.jsonl"
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        entries = [
            json.dumps({
                "source": "skillopt-wrapper",
                "skill": "alicloud-ecs-ops",
                "operation": "DescribeInstances",
                "command": cmd,
                "exit_code": 1,
                "rubric_pass": False,
                "error_code": "InvalidParameter",
            }, sort_keys=True)
            for _ in range(2)
        ]
        jsonl.write_text("\n".join(entries) + "\n", encoding="utf-8")
        result = reflexion_promote_from_memory(
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
            min_count=MIN_PATTERN_COUNT,
            apply=True,
        )
        self.assertEqual(result["promoted"], 0)
        self.assertEqual(result["skipped_low_count"], 1)
        self.assertEqual(len(_load_store(self.reflexion_root).get("cli_parameter", [])), 0)

    def test_reconcile_after_hot_path_does_not_double_count(self):
        trace = {
            "product": "ecs",
            "action": "DescribeInstances",
            "params": "--RegionId cn-hangzhou",
            "error_code": "InvalidParameter",
            "output": {"Code": "InvalidParameter"},
        }
        trace_path = self.root / "trace-hot.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)
        reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)

        skill_dir = self.memory_root / "alicloud-ecs-ops"
        skill_dir.mkdir(parents=True)
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        entries = [
            json.dumps({
                "source": "skillopt-wrapper",
                "skill": "alicloud-ecs-ops",
                "operation": "DescribeInstances",
                "command": cmd,
                "exit_code": 1,
                "rubric_pass": False,
                "error_code": "InvalidParameter",
            }, sort_keys=True)
            for _ in range(5)
        ]
        (skill_dir / "DescribeInstances.jsonl").write_text("\n".join(entries) + "\n", encoding="utf-8")

        result = reflexion_promote_from_memory(
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
            min_count=MIN_PATTERN_COUNT,
            apply=True,
        )
        self.assertEqual(result["reconciled"], 1)
        store = _load_store(self.reflexion_root)
        self.assertEqual(store["cli_parameter"][0]["count"], 5)

    def test_extract_wrapper_lite_from_output_code(self):
        output = json.dumps({"Code": "Forbidden", "Message": "No permission"})
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DeleteInstance",
            command="aliyun ecs DeleteInstance --RegionId cn-hangzhou",
            error_code="exit_code_1",
            output=output,
        )
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["category"], "cli_parameter")
        self.assertIn("Forbidden", pattern["error"])

    def test_store_wrapper_lite_skips_denylist(self):
        trace = {
            "product": "ecs",
            "action": "DescribeInstances",
            "params": "--RegionId cn-hangzhou",
            "error_code": "Throttling",
            "output": {"Code": "Throttling", "Message": "Rate exceeded"},
        }
        trace_path = self.root / "trace-deny.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        rc = reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)
        self.assertEqual(rc, 0)
        store = _load_store(self.reflexion_root)
        self.assertEqual(len(store.get("cli_parameter", [])), 0)

    def test_store_wrapper_lite_skips_exit_code_only(self):
        trace = {
            "product": "ecs",
            "action": "DescribeInstances",
            "params": "--RegionId cn-hangzhou",
            "error_code": "exit_code_1",
            "output": "plain text without json code",
        }
        trace_path = self.root / "trace-noise.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        rc = reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)
        self.assertEqual(rc, 0)
        store = _load_store(self.reflexion_root)
        self.assertEqual(len(store.get("cli_parameter", [])), 0)

    def test_store_wrapper_lite_increments(self):
        trace = {
            "product": "ecs",
            "action": "DescribeInstances",
            "params": "--RegionId cn-hangzhou",
            "error_code": "InvalidParameter",
            "output": {"Code": "InvalidParameter", "Message": "RegionId"},
        }
        trace_path = self.root / "trace.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
        rc1 = reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)
        rc2 = reflexion_store_wrapper_lite("alicloud-ecs-ops", trace_path, root=self.reflexion_root)
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        store = _load_store(self.reflexion_root)
        self.assertEqual(len(store["cli_parameter"]), 1)
        self.assertEqual(store["cli_parameter"][0]["count"], 2)

    def test_promote_from_memory_reconciles_count(self):
        skill_dir = self.memory_root / "alicloud-ecs-ops"
        skill_dir.mkdir(parents=True)
        jsonl = skill_dir / "DescribeInstances.jsonl"
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        entries = []
        for _ in range(4):
            entries.append(json.dumps({
                "source": "skillopt-wrapper",
                "skill": "alicloud-ecs-ops",
                "operation": "DescribeInstances",
                "command": cmd,
                "exit_code": 1,
                "rubric_pass": False,
                "error_code": "InvalidParameter",
            }, sort_keys=True))
        jsonl.write_text("\n".join(entries) + "\n", encoding="utf-8")

        result = reflexion_promote_from_memory(
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
            min_count=MIN_PATTERN_COUNT,
            apply=True,
        )
        self.assertEqual(result["promoted"], 1)
        store = _load_store(self.reflexion_root)
        self.assertEqual(store["cli_parameter"][0]["count"], 4)

        # Second promote with same L1 data must not inflate beyond L1 count
        result2 = reflexion_promote_from_memory(
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
            min_count=MIN_PATTERN_COUNT,
            apply=True,
        )
        self.assertEqual(result2["promoted"], 0)
        self.assertEqual(result2["reconciled"], 0)
        store2 = _load_store(self.reflexion_root)
        self.assertEqual(store2["cli_parameter"][0]["count"], 4)


class SuccessPatternPreflightTests(unittest.TestCase):
    """R4 4.6: {{success_patterns}} slot via preflight_retrieve."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_preflight_success_patterns_slot(self):
        from memory_preflight import preflight_retrieve

        reflexion_root = self.root / "reflexion"
        reflexion_root.mkdir(parents=True)
        success_store(_sample_success_pattern(), root=reflexion_root)

        result = preflight_retrieve(
            skill="alicloud-ecs-ops",
            operation="DeleteInstance",
            skills_root=self.root,
            reflexion_root=reflexion_root,
        )
        self.assertEqual(len(result["success_patterns"]), 1)
        self.assertIn("success_patterns", result["slots"])
        self.assertIn("multi_iter", result["slots"]["success_patterns"])
        self.assertFalse(result["empty"])

    def test_preflight_success_patterns_empty_fallback(self):
        from memory_preflight import preflight_retrieve

        result = preflight_retrieve(
            skill="alicloud-ecs-ops",
            operation="DeleteInstance",
            skills_root=self.root,
            reflexion_root=self.root / "empty-reflexion",
        )
        self.assertEqual(result["success_patterns"], [])
        self.assertIn("none", result["slots"]["success_patterns"].lower())


class WrapperTrapR2PreflightTests(unittest.TestCase):
    """Non-pilot skills: wrapper-lite L2 patterns surface in R2 {{known_traps}}."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_vpc_and_slb_preflight_known_traps(self):
        from memory_preflight import preflight_retrieve

        cases = [
            ("alicloud-vpc-ops", "vpc", "DescribeVpcs"),
            ("alicloud-slb-ops", "slb", "DescribeLoadBalancers"),
        ]
        for skill, product, action in cases:
            with self.subTest(skill=skill, action=action):
                skills_root = self.root / skill
                reflexion_root = skills_root / ".runtime" / "reflexion"
                reflexion_root.mkdir(parents=True)
                command = f"aliyun {product} {action} --RegionId cn-hangzhou"
                pattern = reflexion_extract_wrapper_lite(
                    skill=skill,
                    product=product,
                    action=action,
                    command=command,
                    error_code="InvalidParameter",
                    output={"Code": "InvalidParameter", "Message": "RegionId"},
                )
                self.assertIsNotNone(pattern)
                pattern["count"] = 3
                reflexion_store(pattern, root=reflexion_root)

                result = preflight_retrieve(
                    skill=skill,
                    operation=action,
                    skills_root=skills_root,
                    reflexion_root=reflexion_root,
                )
                self.assertGreater(len(result["known_traps"]), 0)
                self.assertIn("InvalidParameter", result["slots"]["known_traps"])
                self.assertNotIn(
                    "(none — no matching failure patterns",
                    result["slots"]["known_traps"],
                )


if __name__ == "__main__":
    unittest.main()
