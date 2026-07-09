#!/usr/bin/env python3
"""Integration smoke test — fixture dataset → mock rollout → scorer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_BENCH_DIR = Path(__file__).resolve().parent / "benchmark" / "alicloud_ops"
sys.path.insert(0, str(_BENCH_DIR))

from dataloader import load_dataset  # noqa: E402
from rollout import run_rollout  # noqa: E402
from scorer import score_rollout  # noqa: E402
from trajectories import load_trajectories  # noqa: E402

_FIXTURE_DATASET = _BENCH_DIR / "fixtures" / "dataset.jsonl"
_FIXTURE_SEED = _BENCH_DIR / "fixtures" / "trainable_seed.md"
_FIXTURE_TRAJ = _BENCH_DIR / "fixtures" / "trajectories.jsonl"
_DEFAULT_SEED = "# benchmark trainable seed\n"


class BenchmarkSmokeTests(unittest.TestCase):
    def test_train_rows_mock_rollout_scores_in_unit_interval(self) -> None:
        data = load_dataset(_FIXTURE_DATASET)
        skill_md = (
            _FIXTURE_SEED.read_text(encoding="utf-8")
            if _FIXTURE_SEED.is_file()
            else _DEFAULT_SEED
        )
        trajectories = load_trajectories(_FIXTURE_TRAJ)

        self.assertGreater(len(data["train"]), 0, "fixture must have train rows")

        for row in data["train"]:
            query = row["query"]
            expected_skill = row.get("expected_skill", "alicloud-ecs-ops")
            rollout = run_rollout(
                query,
                skill_md,
                mock=True,
                skill=expected_skill,
                trajectories=trajectories,
            )
            score = score_rollout(rollout, expected_skill)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
            self.assertEqual(rollout["status"], "mock")
            self.assertIn("trajectory_memory_context", rollout)
            if trajectories:
                self.assertIn("Layer-1", rollout["trajectory_memory_context"])


if __name__ == "__main__":
    unittest.main()
