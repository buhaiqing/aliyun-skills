#!/usr/bin/env python3
"""WT-5: Unit tests for RG/Tags context propagation and hard-filtering in Layer 2.

Tests:
- test_extract_writes_context_with_rg
- test_extract_writes_context_missing_dimensions
- test_extract_no_context_when_no_dims_provided (regression)
- test_retrieve_filter_by_rg
- test_retrieve_filter_no_match_returns_empty
- test_retrieve_no_filter_returns_all (regression — confirms default behaviour)
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the parent directory is on sys.path for import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcl_reflexion import (
    _empty_reflexion_store,
    _empty_success_store,
    _save_store,
    _save_success_store,
    _store_path,
    _success_patterns_path,
    is_mapped_in_repair_table,
    parse_repair_table_codes,
    reflexion_extract,
    reflexion_extract_wrapper_lite,
    reflexion_retrieve,
    reflexion_store,
    success_retrieve,
    success_store,
)


class ReflexionExtractContextTests(unittest.TestCase):
    """Tests for context-field propagation in reflexion_extract_wrapper_lite."""

    def test_extract_writes_context_with_rg(self):
        """When resource_group_id is explicitly passed, context.resource_group_id is set."""
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DeleteInstance",
            command="aliyun ecs DeleteInstance --ResourceGroupId rg-1",
            error_code="InvalidParameter",
            output={"Code": "InvalidParameter", "Message": "bad rg"},
            resource_group_id="rg-1",
        )
        self.assertIsNotNone(pattern)
        self.assertIn("context", pattern)
        ctx = pattern["context"]
        self.assertEqual(ctx["resource_group_id"], "rg-1")
        self.assertEqual(ctx["tags"], [])
        # missing_dimensions defaults to False because rg is provided.
        self.assertFalse(ctx["missing_dimensions"])

    def test_extract_writes_context_with_tags(self):
        """When tags are passed, context.tags is set."""
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DescribeInstances",
            command="aliyun ecs DescribeInstances --Tag.1.Key env --Tag.1.Value prod",
            error_code="Forbidden",
            output='{"Code":"Forbidden"}',
            resource_group_id="rg-2",
            tags=["env:prod", "team:alpha"],
        )
        self.assertIsNotNone(pattern)
        self.assertIn("context", pattern)
        ctx = pattern["context"]
        self.assertEqual(ctx["resource_group_id"], "rg-2")
        self.assertEqual(ctx["tags"], ["env:prod", "team:alpha"])
        self.assertFalse(ctx["missing_dimensions"])

    def test_extract_writes_context_missing_dimensions(self):
        """When missing_dimensions=True is explicitly passed, context.missing_dimensions=True."""
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="CreateInstance",
            command="aliyun ecs CreateInstance --ImageId img-x",
            error_code="QuotaExceeded",
            output='{"Code":"QuotaExceeded"}',
            resource_group_id=None,
            tags=None,
            missing_dimensions=True,
        )
        self.assertIsNotNone(pattern)
        self.assertIn("context", pattern)
        ctx = pattern["context"]
        self.assertIsNone(ctx["resource_group_id"])
        self.assertEqual(ctx["tags"], [])
        self.assertTrue(ctx["missing_dimensions"])

    def test_extract_no_context_when_no_dims_provided(self):
        """Regression: when no RG/Tags/missing_dimensions are passed, NO context field exists."""
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DescribeInstances",
            command="aliyun ecs DescribeInstances",
            error_code="ResourceNotFound",
            output='{"Code":"ResourceNotFound"}',
        )
        self.assertIsNotNone(pattern)
        self.assertNotIn("context", pattern)


class ReflexionExtractGCLTraceTests(unittest.TestCase):
    """Tests for reflexion_extract reading trace['resource_dimensions']."""

    def test_gcl_extract_propagates_resource_dimensions(self):
        """When trace['resource_dimensions'] is present, pattern carries context."""
        trace = {
            "failure_pattern": {
                "category": "cli_parameter",
                "skill": "alicloud-rds-ops",
                "command": "aliyun rds DescribeDBInstances",
                "error": "InvalidParameter: RegionId",
                "fix": "Use cn-hangzhou",
            },
            "resource_dimensions": {
                "resource_group_id": "rg-rds-1",
                "tags": ["env:staging"],
                "missing_dimensions": False,
            },
        }
        pattern = reflexion_extract(trace)
        self.assertIsNotNone(pattern)
        self.assertIn("context", pattern)
        ctx = pattern["context"]
        self.assertEqual(ctx["resource_group_id"], "rg-rds-1")
        self.assertEqual(ctx["tags"], ["env:staging"])
        self.assertFalse(ctx["missing_dimensions"])

    def test_gcl_extract_no_context_when_trace_lacks_resource_dimensions(self):
        """Regression: legacy traces without resource_dimensions get NO context field."""
        trace = {
            "failure_pattern": {
                "category": "cli_parameter",
                "skill": "alicloud-rds-ops",
                "command": "aliyun rds DescribeDBInstances",
                "error": "InvalidParameter",
                "fix": "Fix param",
            },
        }
        pattern = reflexion_extract(trace)
        self.assertIsNotNone(pattern)
        self.assertNotIn("context", pattern)


class ReflexionRetrieveFilterTests(unittest.TestCase):
    """Tests for hard-filtering by RG/Tags in reflexion_retrieve / success_retrieve."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Seed a reflexion store with 3 patterns: rg-1+env:prod, rg-2+team:alpha, no-context.
        store = _empty_reflexion_store()
        store["cli_parameter"] = [
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DeleteInstance",
                "error": "InvalidParameter: param1",
                "fix": "Fix param1",
                "count": 5,
                "first_seen": "2026-06-01T00:00:00Z",
                "last_seen": "2026-06-20T00:00:00Z",
                "source": "wrapper-lite",
                "context": {
                    "resource_group_id": "rg-1",
                    "tags": ["env:prod"],
                    "missing_dimensions": False,
                },
            },
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs StopInstance",
                "error": "QuotaExceeded",
                "fix": "Reduce batch",
                "count": 3,
                "first_seen": "2026-06-02T00:00:00Z",
                "last_seen": "2026-06-21T00:00:00Z",
                "source": "wrapper-lite",
                "context": {
                    "resource_group_id": "rg-2",
                    "tags": ["team:alpha", "env:staging"],
                    "missing_dimensions": False,
                },
            },
            {
                "category": "cli_parameter",
                "skill": "alicloud-ecs-ops",
                "command": "aliyun ecs DescribeInstances",
                "error": "ResourceNotFound",
                "fix": "Verify instance",
                "count": 2,
                "first_seen": "2026-06-03T00:00:00Z",
                "last_seen": "2026-06-22T00:00:00Z",
                "source": "wrapper-lite",
            },
        ]
        _save_store(store, root=self.root)
        # Seed a success store.
        success = _empty_success_store()
        success["patterns"] = [
            {
                "skill": "alicloud-ecs-ops",
                "operation": "DescribeInstances",
                "command_excerpt": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                "command_hash": "sha256:abc",
                "capture_reason": "multi_iter",
                "iterations": 2,
                "scores_summary": "all>0.8",
                "scores_min": 0.85,
                "preflight_had_traps": False,
                "trap_count": 0,
                "hint": "Use cn-hangzhou for prod rg-1",
                "count": 1,
                "first_seen": "2026-06-15T00:00:00Z",
                "last_seen": "2026-06-22T00:00:00Z",
                "source": "gcl-runner",
                "context": {
                    "resource_group_id": "rg-1",
                    "tags": ["env:prod"],
                    "missing_dimensions": False,
                },
            },
        ]
        _save_success_store(success, root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_retrieve_filter_by_rg(self):
        """resource_group_id filter restricts to patterns matching that RG."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-1",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["context"]["resource_group_id"], "rg-1")
        self.assertEqual(result[0]["command"], "aliyun ecs DeleteInstance")

    def test_retrieve_filter_by_tags(self):
        """tag_filter (list of {Key,Value}) restricts to patterns containing those tags."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            tag_filter=[{"Key": "env", "Value": "prod"}],
        )
        self.assertEqual(len(result), 1)
        self.assertIn("env:prod", result[0]["context"]["tags"])

    def test_retrieve_filter_by_rg_and_tags(self):
        """Combined RG + tag filter applies both constraints."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-2",
            tag_filter=[{"Key": "team", "Value": "alpha"}],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["command"], "aliyun ecs StopInstance")

    def test_retrieve_filter_no_match_returns_empty(self):
        """Filter with no matching RG returns empty list (no fallback to unfiltered)."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-nonexistent",
        )
        self.assertEqual(result, [])

    def test_retrieve_no_filter_returns_all(self):
        """Regression: default behaviour (no filter) returns all patterns incl. legacy."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
        )
        self.assertEqual(len(result), 3)
        # The legacy (no-context) pattern is still returned.
        cmds = sorted(p["command"] for p in result)
        self.assertIn("aliyun ecs DescribeInstances", cmds)
        self.assertIn("aliyun ecs DeleteInstance", cmds)
        self.assertIn("aliyun ecs StopInstance", cmds)

    def test_retrieve_filter_excludes_legacy_patterns(self):
        """When filter is active, patterns without context are excluded (no fallback)."""
        result = reflexion_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-1",
        )
        # Legacy "DescribeInstances" (no context) is excluded.
        cmds = [p["command"] for p in result]
        self.assertNotIn("aliyun ecs DescribeInstances", cmds)

    def test_success_retrieve_filter_by_rg(self):
        """success_retrieve supports the same RG filter."""
        result = success_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-1",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["context"]["resource_group_id"], "rg-1")

    def test_success_retrieve_filter_no_match_returns_empty(self):
        """success_retrieve with unmatched RG returns empty list."""
        result = success_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
            resource_group_id="rg-nonexistent",
        )
        self.assertEqual(result, [])

    def test_success_retrieve_no_filter_returns_all(self):
        """Regression: success_retrieve with no filter returns all patterns."""
        result = success_retrieve(
            skill="alicloud-ecs-ops",
            top_k=10,
            root=self.root,
        )
        self.assertEqual(len(result), 1)


class ReflexionExtractWrapperLiteNoContextRegression(unittest.TestCase):
    """Regression: existing callers without RG/Tags kwargs must still work."""

    def test_extract_wrapper_lite_no_kwargs_signature(self):
        """Verify positional/legacy callers (no new kwargs) still produce a pattern
        without the context field."""
        pattern = reflexion_extract_wrapper_lite(
            "alicloud-ecs-ops",
            "ecs",
            "DescribeInstances",
            "aliyun ecs DescribeInstances",
            "ResourceNotFound",
            '{"Code":"ResourceNotFound"}',
        )
        self.assertIsNotNone(pattern)
        self.assertNotIn("context", pattern)

    def test_extract_returns_none_for_denied_error(self):
        """Throttling (denylist) still returns None even with RG passed."""
        pattern = reflexion_extract_wrapper_lite(
            skill="alicloud-ecs-ops",
            product="ecs",
            action="DescribeInstances",
            command="aliyun ecs DescribeInstances",
            error_code="Throttling",
            output='{"Code":"Throttling"}',
            resource_group_id="rg-x",
        )
        self.assertIsNone(pattern)


_FAKE_OVERLAY_TXT = """\
#!/bin/bash
skillopt_repair_error() {
    local error_code="$1"
    case "$error_code" in
        Throttling.User|InvalidParameter|ResourceNotFound)
            ;;
        esac
}
"""


class RepairTableCoverageTests(unittest.TestCase):
    """Phase 1: parse_repair_table_codes / is_mapped_in_repair_table / unmapped_in_repair flag."""

    def _write_overlay(self, root: Path) -> None:
        skill_dir = root / "alicloud-ecs-ops" / "scripts"
        skill_dir.mkdir(parents=True)
        (skill_dir / "harness-lib.sh").write_text(_FAKE_OVERLAY_TXT, encoding="utf-8")

    def test_parse_repair_table_codes_extracts_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "harness-lib.sh"
            path.write_text(_FAKE_OVERLAY_TXT, encoding="utf-8")
            codes = parse_repair_table_codes(path)
            self.assertEqual(
                codes,
                {"Throttling.User", "InvalidParameter", "ResourceNotFound"},
            )

    def test_is_mapped_in_repair_table_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_overlay(Path(tmp))
            self.assertTrue(
                is_mapped_in_repair_table(
                    "alicloud-ecs-ops", "Throttling.User", skills_root=Path(tmp)
                )
            )

    def test_is_mapped_in_repair_table_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_overlay(Path(tmp))
            self.assertFalse(
                is_mapped_in_repair_table(
                    "alicloud-ecs-ops",
                    "IdempotentProcessingInProgress",
                    skills_root=Path(tmp),
                )
            )

    def test_is_mapped_in_repair_table_unknown_skill_fails_open(self):
        # Skill not in the registry must NOT throw or false-positive.
        self.assertTrue(is_mapped_in_repair_table("alicloud-foo-ops", "Any.Code"))

    def test_extract_wrapper_lite_sets_unmapped_in_repair_true_for_unknown_code(self):
        """Pattern for a code absent from the overlay must carry unmapped_in_repair=True.

        Uses ``NoPermission`` because it sits in ``WRAPPER_L2_ALLOWLIST`` (so
        ``wrapper_error_eligible`` passes) but is not present in the fake
        overlay (so ``is_mapped_in_repair_table`` returns False).
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write_overlay(Path(tmp))
            # Run from the temp skills_root so _REPAIR_TABLE_PATH resolves.
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                pattern = reflexion_extract_wrapper_lite(
                    skill="alicloud-ecs-ops",
                    product="ecs",
                    action="DescribeInstances",
                    command="aliyun ecs DescribeInstances",
                    error_code="NoPermission",
                    output='{"Code":"NoPermission"}',
                )
            finally:
                os.chdir(cwd)
        self.assertIsNotNone(pattern)
        self.assertTrue(pattern["unmapped_in_repair"])
        self.assertEqual(pattern["error_code"], "NoPermission")

    def test_extract_wrapper_lite_sets_unmapped_in_repair_false_for_known_code(self):
        """Pattern for a code present in the overlay must carry unmapped_in_repair=False."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_overlay(Path(tmp))
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                pattern = reflexion_extract_wrapper_lite(
                    skill="alicloud-ecs-ops",
                    product="ecs",
                    action="DescribeInstances",
                    command="aliyun ecs DescribeInstances",
                    error_code="InvalidParameter",
                    output='{"Code":"InvalidParameter"}',
                )
            finally:
                os.chdir(cwd)
        self.assertIsNotNone(pattern)
        self.assertFalse(pattern["unmapped_in_repair"])


if __name__ == "__main__":
    unittest.main()