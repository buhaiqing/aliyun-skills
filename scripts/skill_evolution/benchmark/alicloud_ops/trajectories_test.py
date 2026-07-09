#!/usr/bin/env python3
"""Tests for trajectories.py reflect context."""

from __future__ import annotations

import unittest
from pathlib import Path

from trajectories import build_trajectory_memory_context, load_trajectories, select_for_query

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "trajectories.jsonl"


class TrajectoriesTests(unittest.TestCase):
    def test_load_fixture(self) -> None:
        rows = load_trajectories(_FIXTURE)
        self.assertEqual(len(rows), 2)

    def test_select_for_create_query(self) -> None:
        rows = load_trajectories(_FIXTURE)
        picked = select_for_query(rows, "创建一台 ECS", "alicloud-ecs-ops", top_k=2)
        self.assertGreater(len(picked), 0)
        ops = {r.get("operation") for r in picked}
        self.assertIn("CreateInstance", ops)

    def test_memory_context_nonempty(self) -> None:
        rows = load_trajectories(_FIXTURE)
        ctx = build_trajectory_memory_context(rows, query="创建 ECS", skill="alicloud-ecs-ops")
        self.assertIn("Layer-1", ctx)
        self.assertIn("CreateInstance", ctx)


if __name__ == "__main__":
    unittest.main()
