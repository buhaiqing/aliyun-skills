#!/usr/bin/env python3
"""Tests for export_trajectories.py (Milestone A)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from export_trajectories import export_from_memory_dir, sanitize_command, to_trajectory_record

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ExportTrajectoriesTests(unittest.TestCase):
    def test_sanitize_command_masks_secrets(self) -> None:
        raw = "aliyun ecs DescribeInstances --AccessKeySecret LTAIbogusSecret123"
        self.assertNotIn("LTAIbogus", sanitize_command(raw))
        self.assertIn("****", sanitize_command(raw))

    def test_export_writes_schema_version_and_redacts_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill = "alicloud-ecs-ops"
            skill_dir = Path(tmp) / skill
            skill_dir.mkdir(parents=True)
            (skill_dir / "DescribeInstances.jsonl").write_text(
                (FIXTURES / "memory_ecs.jsonl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            out = export_from_memory_dir(Path(tmp), skill)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["schema_version"], "1.0")
            self.assertEqual(out[0]["operation"], "DescribeInstances")
            self.assertNotIn("LTAIbogus", out[0]["command"])

    def test_missing_memory_dir_returns_empty_list(self) -> None:
        self.assertEqual(export_from_memory_dir(Path("/nonexistent-path-xyz"), "alicloud-ecs-ops"), [])

    def test_to_trajectory_record_infers_wrapper_source(self) -> None:
        entry = json.loads((FIXTURES / "memory_ecs.jsonl").read_text(encoding="utf-8").splitlines()[0])
        rec = to_trajectory_record(entry)
        self.assertEqual(rec["source"], "skillopt-wrapper")
        self.assertTrue(rec["rubric_pass"])


if __name__ == "__main__":
    unittest.main()
