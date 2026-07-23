#!/usr/bin/env python3
"""
gcl_strategy_test_rg.py — Independent test file for WT-6 Layer 3 RG/Tags
filter. Does NOT modify the existing gcl_strategy_test.py (zero-regression
on the existing tests).

Covers:
- strategy_retrieve with no RG filter (regression)
- strategy_retrieve filtered by RG (per-RG baseline)
- strategy_retrieve with RG filtering falling back to general hints
- strategy_retrieve on unknown RG returns general hints annotated

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

import gcl_strategy as strategy  # noqa: E402


class StrategyRetrieveRGTests(unittest.TestCase):
    """Layer 3 strategy_retrieve RG/Tags filter tests."""

    def _make_baseline(
        self,
        tmp: Path,
        *,
        skill_trends: dict | None = None,
        actionable_items: list[dict] | None = None,
        rule_proposals: list[dict] | None = None,
    ) -> Path:
        bp = tmp / "baseline.json"
        data: dict = {
            "version": "2.0.0",
            "skill_trends": skill_trends or {},
            "actionable_items": actionable_items or [],
            "rule_proposals": rule_proposals or [],
        }
        bp.write_text(json.dumps(data), encoding="utf-8")
        return bp

    # ------------------------------------------------------------------
    # 1. test_retrieve_no_filter_returns_all (regression)
    # ------------------------------------------------------------------

    def test_retrieve_no_filter_returns_all(self) -> None:
        """No resource_group_id → identical to pre-WT-6 behaviour."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                skill_trends={
                    "alicloud-ecs-ops": {
                        "risk_score": 0.5,
                        "failure_rate": 0.2,
                        "confidence": "high",
                    },
                },
                actionable_items=[
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances",
                        "actions": ["check pagination"],
                        "resource_groups": ["rg-prod"],
                    },
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DeleteInstance",
                        "actions": ["verify safety"],
                    },
                ],
            )
            out = strategy.strategy_retrieve("alicloud-ecs-ops", baseline_path=bp)
            self.assertFalse(out.get("empty"))
            self.assertEqual(out["skill_risk"]["risk_score"], 0.5)
            self.assertEqual(out["skill_risk"]["failure_rate"], 0.2)
            self.assertEqual(len(out.get("preventive_actions", [])), 2)
            self.assertNotIn("rg_context", out)

    # ------------------------------------------------------------------
    # 2. test_retrieve_filter_by_rg
    # ------------------------------------------------------------------

    def test_retrieve_filter_by_rg(self) -> None:
        """RG filter keeps only entries tagged with that RG."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                actionable_items=[
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances",
                        "actions": ["check pagination"],
                        "resource_groups": ["rg-prod"],
                    },
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DeleteInstance",
                        "actions": ["verify safety"],
                        "resource_groups": ["rg-staging"],
                    },
                ],
            )
            out = strategy.strategy_retrieve(
                "alicloud-ecs-ops",
                baseline_path=bp,
                resource_group_id="rg-prod",
            )
            self.assertIn("rg_context", out)
            self.assertEqual(out["rg_context"], "rg-prod")
            self.assertEqual(
                out.get("preventive_actions"),
                ["check pagination"],
            )
            # "verify safety" is tagged with rg-staging, not rg-prod → excluded
            self.assertNotIn("verify safety", out.get("preventive_actions", []))

    # ------------------------------------------------------------------
    # 3. test_retrieve_filter_rg_with_no_baseline_match_falls_back_to_general
    # ------------------------------------------------------------------

    def test_retrieve_filter_rg_with_no_baseline_match_falls_back_to_general(self) -> None:
        """RG not found in per-RG data → falls back to general hints."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                actionable_items=[
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances",
                        "actions": ["check pagination"],
                        "resource_groups": ["rg-prod"],
                    },
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DeleteInstance",
                        "actions": ["verify safety"],
                        # No resource_groups → general item, should still match
                    },
                ],
            )
            out = strategy.strategy_retrieve(
                "alicloud-ecs-ops",
                baseline_path=bp,
                resource_group_id="rg-unknown",
            )
            # The "verify safety" item has no resource_groups (general), so it
            # matches any RG. The "check pagination" item is rg-prod only and
            # is excluded for rg-unknown.
            self.assertIn("rg_context", out)
            self.assertEqual(out["rg_context"], "rg-unknown")
            self.assertEqual(
                out.get("preventive_actions"),
                ["verify safety"],
            )
            # per_rg_data should be True since at least one item has resource_groups
            self.assertNotIn("per_rg_data", out)

    # ------------------------------------------------------------------
    # 4. test_retrieve_unknown_rg_returns_general_hints_annotated
    # ------------------------------------------------------------------

    def test_retrieve_unknown_rg_returns_general_hints_annotated(self) -> None:
        """Baseline with no per-RG data at all → general hints plus rg_context
        and per_rg_data=False annotation."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                skill_trends={
                    "alicloud-ecs-ops": {
                        "risk_score": 0.3,
                        "failure_rate": 0.1,
                        "confidence": "medium",
                    },
                },
                actionable_items=[
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances",
                        "actions": ["use pagination"],
                        # No resource_groups key → legacy baseline
                    },
                ],
            )
            out = strategy.strategy_retrieve(
                "alicloud-ecs-ops",
                baseline_path=bp,
                resource_group_id="rg-any",
            )
            self.assertIn("rg_context", out)
            self.assertEqual(out["rg_context"], "rg-any")
            self.assertTrue(out.get("per_rg_data") is False)
            # General hints still returned (no per-RG exclusion applies)
            self.assertIn("use pagination", out.get("preventive_actions", []))
            self.assertEqual(out["skill_risk"]["risk_score"], 0.3)

    # ------------------------------------------------------------------
    # 5. test_retrieve_same_as_no_filter_when_rg_unset
    # ------------------------------------------------------------------

    def test_retrieve_same_as_no_filter_when_rg_unset(self) -> None:
        """Explicit resource_group_id=None produces identical output to
        omitting the kwarg."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                skill_trends={
                    "alicloud-ecs-ops": {
                        "risk_score": 0.5,
                        "failure_rate": 0.2,
                        "confidence": "high",
                    },
                },
                actionable_items=[
                    {
                        "skill": "alicloud-ecs-ops",
                        "operation": "DescribeInstances",
                        "actions": ["check pagination"],
                    },
                ],
            )
            without = strategy.strategy_retrieve(
                "alicloud-ecs-ops", baseline_path=bp,
            )
            with_none = strategy.strategy_retrieve(
                "alicloud-ecs-ops", baseline_path=bp,
                resource_group_id=None,
            )
            self.assertEqual(without, with_none)
            self.assertNotIn("rg_context", with_none)

    # ------------------------------------------------------------------
    # 6. test_retrieve_rg_filter_rule_proposals
    # ------------------------------------------------------------------

    def test_retrieve_rg_filter_rule_proposals(self) -> None:
        """Rule proposals are also filtered by RG when specified."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = self._make_baseline(
                Path(tmp),
                rule_proposals=[
                    {
                        "target_skill": "alicloud-ecs-ops",
                        "title": "ECP: add pagination check",
                        "resource_groups": ["rg-prod"],
                    },
                    {
                        "target_skill": "alicloud-ecs-ops",
                        "title": "ECP: general safety rule",
                        # No resource_groups → general, matches any RG
                    },
                ],
            )
            out = strategy.strategy_retrieve(
                "alicloud-ecs-ops",
                baseline_path=bp,
                resource_group_id="rg-prod",
            )
            self.assertEqual(len(out.get("rule_hints", [])), 2)
            out_staging = strategy.strategy_retrieve(
                "alicloud-ecs-ops",
                baseline_path=bp,
                resource_group_id="rg-staging",
            )
            # staging only gets the general entry (no per-RG)
            self.assertEqual(
                out_staging.get("rule_hints"),
                ["ECP: general safety rule"],
            )


if __name__ == "__main__":
    unittest.main()
