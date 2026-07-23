#!/usr/bin/env python3
"""
memory_preflight_test_rg.py — Independent test file for WT-6 preflight
RG/Tags filter. Does NOT modify existing memory_preflight test paths.

Covers:
- preflight_retrieve with no RG/Tags filter (regression)
- preflight_retrieve with RG filter pass-through
- format_recent_executions with RG/Tags filter and scope annotation
- format_strategy_hints with RG annotation

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from memory_preflight import (  # noqa: E402
    _entry_matches_rg,
    _matches_tag_filter,
    _parse_tag_filter,
    _scope_prefix,
    format_recent_executions,
    format_strategy_hints,
    preflight_retrieve,
)


class PreflightRetrieveNoFilterRegressionTests(unittest.TestCase):
    """test_preflight_no_filter (regression) — same shape as before."""

    def test_preflight_no_filter(self) -> None:
        """preflight_retrieve without RG/Tags produces identical structure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create enough dir structure so that baseline is a valid empty
            # baseline, and memory/reflexion dirs exist (empty).
            (root / ".runtime" / "memory" / "alicloud-ecs-ops").mkdir(parents=True)
            (root / ".runtime" / "reflexion").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            baseline = root / "docs" / "strategy-baseline.json"
            baseline.write_text(
                json.dumps({
                    "version": "2.0.0",
                    "skill_trends": {
                        "alicloud-ecs-ops": {
                            "risk_score": 0.5,
                            "failure_rate": 0.2,
                            "confidence": "high",
                        },
                    },
                    "actionable_items": [],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )

            out = preflight_retrieve(
                "alicloud-ecs-ops",
                skills_root=root,
            )
            # Core structural fields unchanged
            self.assertEqual(out["version"], "1.0.0")
            self.assertEqual(out["skill"], "alicloud-ecs-ops")
            self.assertIsNone(out["operation"])
            # "scope" key should be present with no filter
            self.assertIn("scope", out)
            self.assertIsNone(out["scope"]["resource_group_id"])
            self.assertIsNone(out["scope"]["tag_filter"])
            # strategy_hints should have skill_risk (from baseline)
            self.assertEqual(
                out["strategy_hints"]["skill_risk"]["risk_score"], 0.5,
            )


class PreflightRetrieveRGPassThroughTests(unittest.TestCase):
    """test_preflight_with_rg_filter_passes_through."""

    def test_preflight_with_rg_filter_passes_through(self) -> None:
        """RG/Tags are threaded through to strategy_retrieve and slots."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".runtime" / "memory" / "alicloud-ecs-ops").mkdir(parents=True)
            (root / ".runtime" / "reflexion").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            baseline = root / "docs" / "strategy-baseline.json"
            baseline.write_text(
                json.dumps({
                    "version": "2.0.0",
                    "skill_trends": {},
                    "actionable_items": [],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )

            out = preflight_retrieve(
                "alicloud-ecs-ops",
                resource_group_id="rg-prod",
                tag_filter={"env": "prod"},
                skills_root=root,
            )
            # Scope in result
            self.assertEqual(out["scope"]["resource_group_id"], "rg-prod")
            self.assertEqual(out["scope"]["tag_filter"], {"env": "prod"})
            # strategy_hints should carry rg_context
            self.assertEqual(
                out["strategy_hints"].get("rg_context"), "rg-prod",
            )


class PreflightSlotRGAnnotationTests(unittest.TestCase):
    """test_preflight_slot_includes_rg_annotation."""

    def test_preflight_slot_includes_rg_annotation(self) -> None:
        """Formatted {{recent_executions}} and {{strategy_hints}} include scope lines
        when RG/Tags are provided."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".runtime" / "memory" / "alicloud-ecs-ops").mkdir(parents=True)
            (root / ".runtime" / "reflexion").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            baseline = root / "docs" / "strategy-baseline.json"
            baseline.write_text(
                json.dumps({
                    "version": "2.0.0",
                    "skill_trends": {
                        "alicloud-ecs-ops": {
                            "risk_score": 0.4,
                            "failure_rate": 0.15,
                            "confidence": "medium",
                        },
                    },
                    "actionable_items": [],
                    "rule_proposals": [],
                }),
                encoding="utf-8",
            )

            out = preflight_retrieve(
                "alicloud-ecs-ops",
                resource_group_id="rg-staging",
                tag_filter={"tier": "web"},
                skills_root=root,
            )
            slots = out["slots"]
            # strategy_hints should contain scope line
            strategy_text = slots["strategy_hints"]
            self.assertIn("scope:", strategy_text)
            self.assertIn("rg=rg-staging", strategy_text)
            self.assertIn("tags={", strategy_text)
            # recent_executions should contain scope line (empty memory → fallback string)
            recent_text = slots["recent_executions"]
            self.assertIn("scope:", recent_text)
            self.assertIn("rg=rg-staging", recent_text)


class PreflightFormatKnownTrapsRGAwareTests(unittest.TestCase):
    """test_preflight_format_known_traps_rg_aware / format helpers."""

    def test_preflight_format_known_traps_rg_aware(self) -> None:
        """_entry_matches_rg correctly filters Layer 1/2 entries."""
        # Entry with explicit RG
        entry_matching = {"resource_group_id": "rg-prod", "operation": "Describe"}
        entry_non_matching = {"resource_group_id": "rg-staging", "operation": "Describe"}
        entry_no_rg = {"operation": "Describe"}  # no RG field → repo-wide

        self.assertTrue(_entry_matches_rg(entry_matching, "rg-prod"))
        self.assertFalse(_entry_matches_rg(entry_non_matching, "rg-prod"))
        self.assertTrue(_entry_matches_rg(entry_no_rg, "rg-prod"))
        # No RG filter → always matches
        self.assertTrue(_entry_matches_rg(entry_matching, None))
        self.assertTrue(_entry_matches_rg(entry_non_matching, None))

    def test_matches_tag_filter(self) -> None:
        """_matches_tag_filter correctly filters by key=value pairs."""
        entry_tags = [{"key": "env", "value": "prod"}, {"key": "tier", "value": "web"}]
        self.assertTrue(_matches_tag_filter(entry_tags, {"env": "prod"}))
        self.assertTrue(_matches_tag_filter(entry_tags, {"env": "prod", "tier": "web"}))
        self.assertFalse(_matches_tag_filter(entry_tags, {"env": "staging"}))
        self.assertTrue(_matches_tag_filter([], None))  # no filter
        self.assertTrue(_matches_tag_filter([], {}))  # empty filter

    def test_parse_tag_filter(self) -> None:
        """_parse_tag_filter CLI arg → dict."""
        result = _parse_tag_filter("env=prod,tier=web")
        self.assertEqual(result, {"env": "prod", "tier": "web"})
        self.assertIsNone(_parse_tag_filter(""))
        self.assertIsNone(_parse_tag_filter(None))

    def test_scope_prefix(self) -> None:
        """_scope_prefix builds correct header lines."""
        self.assertEqual(_scope_prefix(None, None), "")
        self.assertEqual(_scope_prefix("rg-prod", None), "scope: rg=rg-prod")
        self.assertIn("tags={", _scope_prefix(None, {"env": "prod"}))
        self.assertIn("env:prod", _scope_prefix(None, {"env": "prod"}))
        scope = _scope_prefix("rg-x", {"a": "1", "b": "2"})
        self.assertIn("rg=rg-x", scope)
        self.assertIn("a:1", scope)
        self.assertIn("b:2", scope)

    def test_format_recent_executions_with_empty(self) -> None:
        """Empty entry list + RG filter returns annotated none string."""
        result = format_recent_executions(
            [],
            resource_group_id="rg-prod",
        )
        self.assertIn("scope:", result)
        self.assertIn("rg=rg-prod", result)

    def test_format_strategy_hints_rg_annotated(self) -> None:
        """Existing strategy hints with rg-context produce scope line."""
        hints = {
            "empty": False,
            "skill_risk": {"risk_score": 0.5, "failure_rate": 0.2, "confidence": "high"},
            "preventive_actions": ["use pagination"],
            "rg_context": "rg-prod",
        }
        text = format_strategy_hints(hints, resource_group_id="rg-prod")
        self.assertIn("scope:", text)
        self.assertIn("rg=rg-prod", text)
        self.assertIn("risk_score=0.5", text)
        self.assertIn("use pagination", text)

    def test_format_strategy_hints_per_rg_data_false(self) -> None:
        """When per_rg_data is False, a hint line is emitted."""
        hints = {
            "empty": False,
            "skill_risk": {"risk_score": 0.3, "failure_rate": 0.1, "confidence": "low"},
            "per_rg_data": False,
            "rg_context": "rg-nodata",
            "preventive_actions": ["general hint"],
        }
        text = format_strategy_hints(hints, resource_group_id="rg-nodata")
        self.assertIn("per-RG data", text)
        self.assertIn("falling back", text)
        self.assertIn("general hint", text)


if __name__ == "__main__":
    unittest.main()
