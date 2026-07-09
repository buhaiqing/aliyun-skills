#!/usr/bin/env python3
"""execution_trace 单元测试"""

import json
import tempfile
import unittest
from pathlib import Path

from execution_trace import (
    CommandRecord,
    ExecutionTraceWriter,
    parse_plan_summary,
    persist_dry_run_trace,
)


class TestExecutionTrace(unittest.TestCase):
    def test_parse_plan_summary(self):
        stdout = """
Terraform will perform the following actions:
  # alicloud_vpc.main will be created
  # alicloud_ecs_instance.web will be created

Plan: 5 to add, 0 to change, 0 to destroy
"""
        summary = parse_plan_summary(stdout)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["add"], 5)
        self.assertEqual(summary["change"], 0)
        self.assertEqual(summary["destroy"], 0)
        self.assertIn("alicloud_vpc.main", summary["resources_to_create"])

    def test_persist_dry_run_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_dir = Path(tmp) / "audit-results"
            records = [
                CommandRecord(
                    phase="INIT",
                    command="terraform init -backend=false",
                    working_directory="/tmp/tf",
                    exit_code=0,
                    stdout_excerpt="ok",
                    stderr_excerpt="",
                    duration_ms=100,
                ),
            ]
            path = persist_dry_run_trace(
                operation="nl2hcl",
                environment="int",
                region="cn-hangzhou",
                request="创建一台1核2G的ECS",
                work_dir=Path("/tmp/tf"),
                command_records=records,
                success=True,
                plan_stdout="Plan: 5 to add, 0 to change, 0 to destroy",
                intent={"resources": ["vpc", "ecs"], "instance_type": "ecs.t6-c1m2.large"},
                session_id="session-test-001",
                trace_dir=trace_dir,
            )
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["skill"], "alicloud-terraform-ops")
            self.assertEqual(data["session_id"], "session-test-001")
            self.assertEqual(data["generator"]["plan_summary"]["add"], 5)
            self.assertEqual(len(data["generator"]["commands"]), 1)
            self.assertEqual(data["critic"]["scores"]["safety"], 1)

    def test_writer_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = ExecutionTraceWriter(Path(tmp) / "nested" / "audit")
            from execution_trace import ExecutionTrace

            path = writer.write(ExecutionTrace(operation="plan"))
            self.assertTrue(path.parent.exists())
            self.assertTrue(path.name.startswith("gcl-trace-plan-"))


if __name__ == "__main__":
    unittest.main()
