#!/usr/bin/env python3
"""Tests for scorer.py."""

from __future__ import annotations

import unittest

from scorer import score_rollout


class ScorerTests(unittest.TestCase):
    def test_mock_loaded_scores_one(self) -> None:
        rollout = {"status": "mock", "skill_loaded": True, "query": "q"}
        self.assertEqual(score_rollout(rollout), 1.0)

    def test_mock_empty_scores_zero(self) -> None:
        rollout = {"status": "mock", "skill_loaded": False, "query": "q"}
        self.assertEqual(score_rollout(rollout), 0.0)

    def test_failed_rollout_scores_zero(self) -> None:
        rollout = {"status": "failed", "message": "no wrapper"}
        self.assertEqual(score_rollout(rollout), 0.0)

    def test_ok_rollout_scores_in_range(self) -> None:
        rollout = {
            "status": "ok",
            "skill_loaded": True,
            "skill": "alicloud-ecs-ops",
            "wrapper_path": "/tmp/ecs-harness-wrapper.sh",
        }
        score = score_rollout(rollout, expected_skill="alicloud-ecs-ops")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(score, 1.0)

    def test_rubric_pass_bumps_mock_score(self) -> None:
        rollout = {
            "status": "mock",
            "skill_loaded": False,
            "metadata": {"rubric_pass": True},
        }
        self.assertEqual(score_rollout(rollout), 0.2)

    def test_rubric_pass_top_level(self) -> None:
        rollout = {"status": "mock", "skill_loaded": True, "rubric_pass": True}
        self.assertEqual(score_rollout(rollout), 1.0)


if __name__ == "__main__":
    unittest.main()
