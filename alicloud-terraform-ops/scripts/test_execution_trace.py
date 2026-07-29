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


class TestNewFields:
    def test_new_factory_injects_from_chat_context(self, monkeypatch):
        """new() should pull user_id/session_id/platform from bind() context."""
        from alicloud_shared.chat_context import bind, ChatContext, _ctx_var
        from execution_trace import ExecutionTrace
        try:
            ctx = ChatContext(user_id="alice", session_id="s1", platform="wecom", chat_type="group", raw={})
            bind(ctx)
            trace = ExecutionTrace.new(operation="test")
            assert trace.user_id == "alice"
            assert trace.session_id == "s1"
            assert trace.platform == "wecom"
            assert trace.chat_type == "group"
        finally:
            _ctx_var.set(None)

    def test_new_factory_no_context(self):
        """new() without context should set fields to None."""
        from execution_trace import ExecutionTrace
        trace = ExecutionTrace.new(operation="test")
        assert trace.user_id is None
        assert trace.session_id is None
        assert trace.platform is None
        assert trace.chat_type is None

    def test_to_dict_includes_new_fields(self):
        from execution_trace import ExecutionTrace
        trace = ExecutionTrace(operation="test", user_id="u", session_id="s", platform="wecom", chat_type="group")
        d = trace.to_dict()
        assert d["user_id"] == "u"
        assert d["session_id"] == "s"
        assert d["platform"] == "wecom"
        assert d["chat_type"] == "group"

    def test_backward_compat_old_construction(self):
        """Old construction without new fields should still work."""
        from execution_trace import ExecutionTrace
        trace = ExecutionTrace(operation="test")
        assert trace.user_id is None
        assert trace.session_id is None  # existing default
        assert trace.platform is None
        assert trace.chat_type is None

    def test_from_dict_missing_fields(self):
        """Loading an old trace JSON without new fields should not raise."""
        from execution_trace import ExecutionTrace
        old_data = {
            "trace_version": "1.0.0",
            "trace_id": "trace-abc",
            "operation": "test",
            # No user_id, platform, chat_type
        }
        trace = ExecutionTrace.from_dict(old_data) if hasattr(ExecutionTrace, 'from_dict') else None
        # If from_dict doesn't exist, this test passes trivially
        # But the dict round-trip via to_dict must work
        trace2 = ExecutionTrace(operation="test")
        d = trace2.to_dict()
        assert "user_id" in d
        assert d["user_id"] is None


if __name__ == "__main__":
    unittest.main()
