#!/usr/bin/env python3
"""Tests for build_dataset.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from build_dataset import assign_splits, build_dataset_rows

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class BuildDatasetTests(unittest.TestCase):
    def test_assign_splits_heldout_tail(self) -> None:
        positives = [{"query": f"q{i}"} for i in range(4)]
        rows = assign_splits(positives, [])
        splits = [r["split"] for r in rows]
        self.assertEqual(splits.count("train"), 2)
        self.assertEqual(splits.count("heldout"), 2)

    def test_build_dataset_rows_includes_negatives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            eval_path = FIXTURES / "eval_queries_ecs.json"
            traj_path = Path(tmp) / "trajectories.jsonl"
            traj_path.write_text(
                json.dumps({"schema_version": "1.0", "skill": "alicloud-ecs-ops"}) + "\n",
                encoding="utf-8",
            )
            rows = build_dataset_rows(eval_path, traj_path, "alicloud-ecs-ops")
            splits = {r["split"] for r in rows}
            self.assertIn("train", splits)
            self.assertIn("heldout", splits)
            self.assertIn("heldout_trigger", splits)
            ecs_rows = [r for r in rows if r["expected_skill"] == "alicloud-ecs-ops"]
            self.assertTrue(all(r["trajectory_count"] == 1 for r in ecs_rows))


if __name__ == "__main__":
    unittest.main()
