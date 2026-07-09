#!/usr/bin/env python3
"""Tests for reflect.py — trajectory_memory_context injection."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE_TRAJ = Path(__file__).resolve().parent / "fixtures" / "trajectories.jsonl"


@unittest.skipUnless(importlib.util.find_spec("skillopt"), "skillopt not installed")
class ReflectTests(unittest.TestCase):
    @mock.patch("skillopt.gradient.reflect.run_minibatch_reflect")
    def test_reflect_injects_trajectory_memory_context(self, mock_reflect: mock.MagicMock) -> None:
        mock_reflect.return_value = [None]
        from reflect import run_reflect

        with tempfile.TemporaryDirectory() as tmp:
            run_reflect(
                [{"trajectory_memory_context": "Layer-1 CreateInstance prior", "query": "创建 ECS"}],
                "# skill",
                tmp,
                trajectories_path=_FIXTURE_TRAJ,
                skills_root=REPO_ROOT,
                skill="alicloud-ecs-ops",
            )
        mock_reflect.assert_called_once()
        ctx = mock_reflect.call_args.kwargs.get("trajectory_memory_context", "")
        self.assertIn("CreateInstance", ctx)
        self.assertIn("Layer-1", ctx)

    @mock.patch("skillopt.gradient.reflect.run_minibatch_reflect")
    def test_reflect_falls_back_to_fixture_trajectories(self, mock_reflect: mock.MagicMock) -> None:
        mock_reflect.return_value = [None]
        from reflect import run_reflect

        with tempfile.TemporaryDirectory() as tmp:
            run_reflect(
                [{"query": "查看 ECS 实例"}],
                "# skill",
                tmp,
                trajectories_path=_FIXTURE_TRAJ,
                skills_root=REPO_ROOT,
                skill="alicloud-ecs-ops",
            )
        ctx = mock_reflect.call_args.kwargs.get("trajectory_memory_context", "")
        self.assertIn("DescribeInstances", ctx)


if __name__ == "__main__":
    unittest.main()
