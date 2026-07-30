#!/usr/bin/env python3
"""Unit tests for scripts/langfuse_token_report.py.

Validates the window-resolution and aggregation logic without requiring
network access to Langfuse. Use these tests as a guardrail when evolving
the report schema or time-window semantics.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "langfuse_token_report.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("langfuse_token_report", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec_module so dataclass introspection
    # (which uses sys.modules[cls.__module__]) can find the module.
    sys.modules["langfuse_token_report"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestResolvePeriod(unittest.TestCase):
    """--since-minutes N must produce a [now-N, now] window."""

    def test_since_minutes_30_yields_30_min_window(self):
        mod = _load_module()
        ns = mod.build_parser().parse_args(["pull", "--since-minutes", "30"])
        from_ts, to_ts = mod._resolve_period(ns)
        # Both ISO-8601 Z timestamps
        self.assertRegex(from_ts, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertRegex(to_ts, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        from_dt = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
        delta = to_dt - from_dt
        # Allow 1s tolerance for rounding/clock-skew
        self.assertGreaterEqual(delta.total_seconds(), 30 * 60 - 1)
        self.assertLessEqual(delta.total_seconds(), 30 * 60 + 1)

    def test_since_minutes_60(self):
        mod = _load_module()
        ns = mod.build_parser().parse_args(["pull", "--since-minutes", "60"])
        from_ts, to_ts = mod._resolve_period(ns)
        from_dt = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
        delta = to_dt - from_dt
        self.assertGreaterEqual(delta.total_seconds(), 60 * 60 - 1)
        self.assertLessEqual(delta.total_seconds(), 60 * 60 + 1)


class TestAggregateBySession(unittest.TestCase):
    """Verify session aggregation matches expected Langfuse response shape."""

    def test_groups_by_session_id_and_aggregates_tokens(self):
        mod = _load_module()
        traces = [
            {
                "id": "trace-1",
                "timestamp": "2026-07-30T05:00:00Z",
                "metadata": {
                    "skill": "alicloud-ecs-ops",
                    "session_id": "sess-A",
                    "user_id": "alice",
                    "has_llm_usage": True,
                    "llm_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                },
            },
            {
                "id": "trace-2",
                "timestamp": "2026-07-30T05:10:00Z",
                "metadata": {
                    "skill": "alicloud-ecs-ops",
                    "session_id": "sess-A",  # same session
                    "user_id": "alice",
                    "has_llm_usage": True,
                    "llm_usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
                },
            },
            {
                "id": "trace-3",
                "timestamp": "2026-07-30T05:20:00Z",
                "metadata": {
                    "skill": "alicloud-rds-ops",
                    "session_id": "sess-B",  # different session
                    "user_id": "bob",
                    "has_llm_usage": False,
                    "llm_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                },
            },
        ]
        sessions, skipped = mod.aggregate_by_session(traces)
        # 2 unique sessions; 1 trace has no LLM usage (trace-3)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(skipped, 1)

        # Sort by total_tokens desc
        self.assertEqual(sessions[0].session_id, "sess-A")
        self.assertEqual(sessions[0].total_tokens, 450)
        self.assertEqual(sessions[0].prompt_tokens, 300)
        self.assertEqual(sessions[0].completion_tokens, 150)
        self.assertEqual(sessions[0].trace_count, 2)
        self.assertEqual(sessions[0].skill_set, {"alicloud-ecs-ops"})

        self.assertEqual(sessions[1].session_id, "sess-B")
        self.assertEqual(sessions[1].trace_count, 1)
        self.assertEqual(sessions[1].total_tokens, 0)

    def test_session_without_session_id_bucket(self):
        """Traces without session_id fall into (no-session)."""
        mod = _load_module()
        traces = [
            {
                "id": "t1",
                "timestamp": "2026-07-30T05:00:00Z",
                "metadata": {
                    "skill": "alicloud-ecs-ops",
                    "has_llm_usage": True,
                    "llm_usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
                    # no session_id
                },
            }
        ]
        sessions, _ = mod.aggregate_by_session(traces)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, "(no-session)")
        self.assertEqual(sessions[0].total_tokens, 75)


class TestBuildReport(unittest.TestCase):
    def test_summary_aggregates_all_sessions(self):
        mod = _load_module()
        # Synthesize two sessions
        from dataclasses import replace
        sess_a = mod.SessionAggregate(
            session_id="sess-A", trace_count=3, skill_set={"alicloud-ecs-ops"},
            user_id="alice", prompt_tokens=300, completion_tokens=150,
            total_tokens=450,
        )
        sess_b = mod.SessionAggregate(
            session_id="sess-B", trace_count=1, skill_set={"alicloud-rds-ops"},
            user_id="bob", prompt_tokens=100, completion_tokens=50,
            total_tokens=150,
        )
        report = mod.build_report(
            [sess_a, sess_b],
            from_ts="2026-07-30T05:00:00Z",
            to_ts="2026-07-30T05:30:00Z",
            total_traces=4,
        )
        summary = report["summary"]
        self.assertEqual(summary["total_sessions"], 2)
        self.assertEqual(summary["traces_in_sessions"], 4)
        self.assertEqual(summary["total_prompt_tokens"], 400)
        self.assertEqual(summary["total_completion_tokens"], 200)
        self.assertEqual(summary["total_tokens"], 600)


class TestRenderTable(unittest.TestCase):
    def test_render_table_with_data(self):
        mod = _load_module()
        sess = mod.SessionAggregate(
            session_id="sess-A", trace_count=2, skill_set={"alicloud-ecs-ops"},
            user_id="alice", prompt_tokens=100, completion_tokens=50,
            total_tokens=150,
        )
        report = mod.build_report([sess], "2026-07-30T05:00:00Z", "2026-07-30T05:30:00Z")
        text = mod.render_table(report)
        self.assertIn("Langfuse Token Consumption Report", text)
        self.assertIn("sess-A", text)
        self.assertIn("150", text)
        self.assertIn("alice", text)


class TestHasLlmUsage(unittest.TestCase):
    """Tolerant of both boolean True and truthy string 'true' from older curl paths."""

    def test_boolean_true(self):
        mod = _load_module()
        self.assertTrue(mod._has_llm_usage({
            "metadata": {"has_llm_usage": True, "llm_usage": {"total_tokens": 0}}
        }))

    def test_truthy_string(self):
        mod = _load_module()
        self.assertTrue(mod._has_llm_usage({
            "metadata": {"has_llm_usage": "true", "llm_usage": {"total_tokens": 0}}
        }))

    def test_total_tokens_nonzero(self):
        mod = _load_module()
        self.assertTrue(mod._has_llm_usage({
            "metadata": {"has_llm_usage": False, "llm_usage": {"total_tokens": 1}}
        }))

    def test_no_usage(self):
        mod = _load_module()
        self.assertFalse(mod._has_llm_usage({
            "metadata": {"has_llm_usage": False, "llm_usage": {"total_tokens": 0}}
        }))


if __name__ == "__main__":
    unittest.main()
