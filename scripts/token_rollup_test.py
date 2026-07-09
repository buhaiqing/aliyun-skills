#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for scripts/token_rollup.py (TEL Phase 5)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import token_rollup as tr  # noqa: E402

FIXTURES = SCRIPT_DIR / "fixtures" / "token-rollup"


class TokenRollupTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="token-rollup-test-")
        self.root = Path(self._tmp)
        self.traces = self.root / "alicloud-ecs-ops" / ".runtime" / "traces"
        self.traces.mkdir(parents=True)
        self.audit = self.root / "audit-results"
        self.audit.mkdir(parents=True)
        self.runtime = self.root / ".runtime"
        self.runtime.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _touch_recent(self, path: Path) -> None:
        import os

        now = datetime.now(tz=timezone.utc).timestamp()
        os.utime(path, (now, now))

    def test_normalize_wrapper_trace_mcp_and_agent_turn(self) -> None:
        data = json.loads((FIXTURES / "wrapper-success.json").read_text(encoding="utf-8"))
        rec = tr.normalize_wrapper_trace(data, FIXTURES / "wrapper-success.json")
        assert rec is not None
        self.assertEqual(rec.llm_usage["total_tokens"], 1000)
        self.assertEqual(rec.agent_turn_tokens, 600)
        self.assertEqual(rec.coding_agent, "cursor")
        self.assertEqual(rec.model, "claude-sonnet-4")
        self.assertIsNotNone(rec.mcp)
        self.assertEqual(rec.mcp["mcp_tool_utilization"], 0.5)

    def test_normalize_gcl_trace_critic_tokens(self) -> None:
        data = json.loads((FIXTURES / "gcl-max-iter.json").read_text(encoding="utf-8"))
        rec = tr.normalize_gcl_trace(data, FIXTURES / "gcl-max-iter.json")
        assert rec is not None
        self.assertEqual(rec.critic_tokens, 430)
        self.assertEqual(rec.llm_usage["total_tokens"], 430)
        self.assertTrue(rec.waste)
        self.assertEqual(rec.status, "MAX_ITER")

    def test_discover_centralized_trace_and_session_layout(self) -> None:
        central_traces = self.runtime / "traces" / "alicloud-ecs-ops"
        central_traces.mkdir(parents=True)
        central_sessions = self.runtime / "sessions" / "alicloud-ecs-ops"
        central_sessions.mkdir(parents=True)
        trace_path = central_traces / "trace-central.json"
        session_path = central_sessions / "skillopt-session-sess-central.json"
        shutil.copy(FIXTURES / "wrapper-success.json", trace_path)
        shutil.copy(FIXTURES / "session-mcp.json", session_path)
        self._touch_recent(trace_path)
        self._touch_recent(session_path)

        trace_hits = {p.resolve() for p, _ in tr.discover_trace_files(self.root)}
        self.assertIn(trace_path.resolve(), trace_hits)
        session_hits = {p.resolve() for p in tr.discover_session_files(self.root)}
        self.assertIn(session_path.resolve(), session_hits)

    def test_rollup_apply_writes_current_and_history(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        shutil.copy(FIXTURES / "wrapper-failed.json", self.traces / "trace-2.json")
        shutil.copy(FIXTURES / "gcl-max-iter.json", self.audit / "gcl-trace-test.json")
        for p in self.traces.glob("*.json"):
            self._touch_recent(p)
        self._touch_recent(self.audit / "gcl-trace-test.json")

        result = tr.rollup_apply(self.root, since_days=7, apply=True)
        self.assertEqual(result["trace_records"], 3)
        rollup_path = tr.token_root(self.root) / "current" / "rollup.json"
        self.assertTrue(rollup_path.is_file())
        rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
        self.assertEqual(rollup["global"]["llm_usage"]["total_tokens"], 1580)
        self.assertIn("alicloud-ecs-ops", rollup["by_skill"])
        agent_key = "cursor|claude-sonnet-4"
        self.assertIn(agent_key, rollup["by_agent_model"])
        self.assertEqual(rollup["by_agent_model"][agent_key]["mcp_schema_waste_tokens"], 120)
        self.assertTrue((tr.token_root(self.root) / "reports").glob("efficiency-*.md"))

    def test_session_mcp_enrichment(self) -> None:
        trace_path = self.traces / "trace-session-only.json"
        trace_path.write_text(
            json.dumps(
                {
                    "trace_id": "t-sess",
                    "session_id": "sess-token-rollup-3",
                    "skill": "alicloud-ecs-ops",
                    "action": "DescribeInstances",
                    "status": "success",
                    "llm_usage": {"total_tokens": 10, "prompt_tokens": 8, "completion_tokens": 2},
                    "llm_generations": [],
                }
            ),
            encoding="utf-8",
        )
        session_path = self.runtime / "skillopt-session-sess-token-rollup-3.json"
        shutil.copy(FIXTURES / "session-mcp.json", session_path)
        self._touch_recent(trace_path)
        self._touch_recent(session_path)

        records, _ = tr.collect_records(self.root, since_days=7)
        self.assertEqual(len(records), 1)
        self.assertIsNotNone(records[0].mcp)
        self.assertEqual(records[0].mcp["mcp_schema_waste_tokens"], 80)

    def test_maintain_prunes_old_history(self) -> None:
        hist = tr.token_root(self.root) / "history"
        hist.mkdir(parents=True)
        old = hist / "rollup-20200101.json"
        old.write_text("{}", encoding="utf-8")
        import os
        from datetime import timedelta

        stale = (datetime.now(tz=timezone.utc) - timedelta(days=60)).timestamp()
        os.utime(old, (stale, stale))
        result = tr.maintain_token_artifacts(self.root, history_keep_days=30, apply=True)
        self.assertIn(".runtime/token/history/rollup-20200101.json", result["removed"])
        self.assertFalse(old.exists())

    def test_waste_ratio_counts_failed_traces(self) -> None:
        success = tr.normalize_wrapper_trace(
            json.loads((FIXTURES / "wrapper-success.json").read_text(encoding="utf-8")),
            FIXTURES / "wrapper-success.json",
        )
        failed = tr.normalize_wrapper_trace(
            json.loads((FIXTURES / "wrapper-failed.json").read_text(encoding="utf-8")),
            FIXTURES / "wrapper-failed.json",
        )
        assert success and failed
        agg = tr.aggregate_records([success, failed])
        g = agg["global"]
        self.assertEqual(g["llm_usage"]["total_tokens"], 1150)
        self.assertAlmostEqual(g["waste_ratio"], 150 / 1150, places=4)

    def _seed_l1_memory(self) -> None:
        mem = self.runtime / "memory"
        ecs_dir = mem / "alicloud-ecs-ops"
        cms_dir = mem / "alicloud-cms-ops"
        ecs_dir.mkdir(parents=True)
        cms_dir.mkdir(parents=True)
        lines = (FIXTURES / "l1-ecs-cms.jsonl").read_text(encoding="utf-8").splitlines()
        (ecs_dir / "DescribeInstances.jsonl").write_text(lines[0] + "\n" + lines[1] + "\n" + lines[2] + "\n", encoding="utf-8")
        (cms_dir / "DescribeMetricList.jsonl").write_text(lines[3] + "\n", encoding="utf-8")

    def test_l1_join_enriches_by_skill(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        self._seed_l1_memory()
        self._touch_recent(self.traces / "trace-1.json")

        result = tr.rollup_apply(self.root, since_days=7, apply=False)
        rollup = result["rollup"]
        self.assertTrue(rollup["l1_join"]["available"])
        ecs = rollup["by_skill"]["alicloud-ecs-ops"]
        self.assertTrue(ecs["l1"]["available"])
        self.assertEqual(ecs["l1"]["execution_count"], 3)
        self.assertAlmostEqual(ecs["l1"]["rubric_pass_rate"], 2 / 3, places=4)
        expected_score = round(1000 * (1 - 2 / 3), 2)
        self.assertAlmostEqual(ecs["expensive_unstable_score"], expected_score, places=1)
        cms = rollup["by_skill"]["alicloud-cms-ops"]
        self.assertTrue(cms["l1"]["available"])
        self.assertTrue(cms.get("token_only"))
        self.assertEqual(cms["l1"]["rubric_pass_rate"], 1.0)

    def test_l1_join_degrades_when_memory_missing(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        self._touch_recent(self.traces / "trace-1.json")
        result = tr.rollup_apply(self.root, since_days=7, apply=False)
        l1_join = result["rollup"]["l1_join"]
        self.assertFalse(l1_join["available"])
        self.assertTrue(l1_join["degraded"])
        self.assertFalse(result["rollup"]["by_skill"]["alicloud-ecs-ops"]["l1"]["available"])

    def _seed_l2_reflexion(self) -> None:
        reflex = self.runtime / "reflexion"
        reflex.mkdir(parents=True)
        shutil.copy(FIXTURES / "reflexion-l2.json", reflex / "reflexion.json")

    def test_l2_join_attributes_waste_events(self) -> None:
        shutil.copy(FIXTURES / "wrapper-failed.json", self.traces / "trace-fail.json")
        shutil.copy(FIXTURES / "gcl-max-iter.json", self.audit / "gcl-trace-test.json")
        self._seed_l2_reflexion()
        self._touch_recent(self.traces / "trace-fail.json")
        self._touch_recent(self.audit / "gcl-trace-test.json")

        result = tr.rollup_apply(self.root, since_days=7, apply=False)
        rollup = result["rollup"]
        l2 = rollup["l2_join"]
        self.assertTrue(l2["available"])
        self.assertEqual(l2["waste_events_total"], 2)
        self.assertEqual(l2["waste_events_attributed"], 2)
        events = rollup["waste_events"]
        self.assertEqual(len(events), 2)
        ecs_event = next(e for e in events if e["skill"] == "alicloud-ecs-ops")
        self.assertEqual(ecs_event["l2_match"]["category"], "max_iter")
        self.assertEqual(ecs_event["critic_tokens"], 430)
        cms_event = next(e for e in events if e["skill"] == "alicloud-cms-ops")
        self.assertEqual(cms_event["l2_match"]["category"], "cli_parameter")
        self.assertIn("MissingParameter", cms_event["l2_match"]["trap_label"])
        traps = {row["category"]: row for row in l2["by_trap"]}
        self.assertIn("max_iter", traps)
        self.assertIn("cli_parameter", traps)
        self.assertIn("critic tokens", traps["max_iter"]["narrative"])

    def test_l2_join_degrades_without_reflexion(self) -> None:
        shutil.copy(FIXTURES / "wrapper-failed.json", self.traces / "trace-fail.json")
        self._touch_recent(self.traces / "trace-fail.json")
        rollup = tr.rollup_apply(self.root, since_days=7, apply=False)["rollup"]
        self.assertFalse(rollup["l2_join"]["available"])
        self.assertTrue(rollup["l2_join"]["degraded"])
        self.assertIsNone(rollup["waste_events"][0]["l2_match"])

    def test_mcp_join_global_by_skill_and_report(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        self._touch_recent(self.traces / "trace-1.json")
        result = tr.rollup_apply(self.root, since_days=7, apply=True)
        rollup = result["rollup"]
        mcp = rollup["mcp_join"]
        self.assertTrue(mcp["available"])
        self.assertFalse(mcp["degraded"])
        self.assertEqual(mcp["traces_with_mcp"], 1)
        self.assertIn("mcp", rollup["global"])
        self.assertEqual(rollup["global"]["mcp"]["mcp_schema_waste_tokens"], 120)
        self.assertEqual(
            rollup["by_skill"]["alicloud-ecs-ops"]["mcp_schema_waste_tokens"],
            120,
        )
        self.assertIn("alicloud-ecs-ops", mcp["by_skill"])
        self.assertTrue(mcp["low_utilization_ranking"])
        report = result["report"]
        self.assertIn("MCP schema waste", report)

    def test_mcp_sidecar_supplements_join(self) -> None:
        ctx = self.runtime / "token" / "context"
        ctx.mkdir(parents=True)
        sidecar = {
            "mcp_tools_loaded": ["user-context7/search", "user-context7/fetch", "plugin/foo"],
            "mcp_tools_invoked": ["user-context7/search"],
            "mcp_tool_utilization": 0.3333,
            "mcp_schema_waste_tokens": 200,
            "attribution_confidence": "estimated",
        }
        (ctx / "mcp-context-latest.json").write_text(json.dumps(sidecar), encoding="utf-8")
        self._touch_recent(ctx / "mcp-context-latest.json")

        rollup = tr.rollup_apply(self.root, since_days=7, apply=False)["rollup"]
        mcp = rollup["mcp_join"]
        self.assertTrue(mcp["available"])
        self.assertTrue(mcp["sidecar_used"])
        self.assertEqual(mcp["global"]["mcp_schema_waste_tokens"], 200)
        self.assertEqual(mcp["global"]["tools_loaded_distinct"], 3)
        self.assertIn("plugin/foo", mcp["unused_tools_distinct"])

    def test_mcp_join_degrades_without_metadata(self) -> None:
        rollup = tr.rollup_apply(self.root, since_days=7, apply=False)["rollup"]
        mcp = rollup["mcp_join"]
        self.assertFalse(mcp["available"])
        self.assertTrue(mcp["degraded"])
        self.assertNotIn("mcp", rollup.get("global") or {})

    def test_resolve_rollup_mode_defaults(self) -> None:
        self.assertEqual(tr.resolve_rollup_mode(self.root, full=False, incremental=False), "full")
        state_path = tr.incremental_state_path(self.root)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text('{"version":"1.0.0"}', encoding="utf-8")
        self.assertEqual(tr.resolve_rollup_mode(self.root, full=False, incremental=False), "incremental")
        self.assertEqual(tr.resolve_rollup_mode(self.root, full=True, incremental=False), "full")
        self.assertEqual(tr.resolve_rollup_mode(self.root, full=False, incremental=True), "incremental")

    def test_incremental_second_run_skips_unchanged(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        shutil.copy(FIXTURES / "wrapper-failed.json", self.traces / "trace-2.json")
        for p in self.traces.glob("*.json"):
            self._touch_recent(p)

        first = tr.rollup_apply(self.root, since_days=7, apply=True, full=True)
        self.assertEqual(first["rollup"]["incremental"]["mode"], "full")
        self.assertEqual(first["rollup"]["incremental"]["files_parsed"], 2)

        second = tr.rollup_apply(self.root, since_days=7, apply=False, incremental=True)
        inc = second["rollup"]["incremental"]
        self.assertEqual(inc["mode"], "incremental")
        self.assertEqual(inc["files_skipped"], 2)
        self.assertEqual(inc["files_parsed"], 0)
        self.assertEqual(second["trace_records"], 2)

    def test_incremental_picks_up_new_trace(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        self._touch_recent(self.traces / "trace-1.json")
        tr.rollup_apply(self.root, since_days=7, apply=True, full=True)

        shutil.copy(FIXTURES / "wrapper-failed.json", self.traces / "trace-2.json")
        self._touch_recent(self.traces / "trace-2.json")

        result = tr.rollup_apply(self.root, since_days=7, apply=False, incremental=True)
        inc = result["rollup"]["incremental"]
        self.assertEqual(inc["files_skipped"], 1)
        self.assertEqual(inc["files_parsed"], 1)
        self.assertEqual(result["trace_records"], 2)

    def test_full_rebuild_after_incremental(self) -> None:
        shutil.copy(FIXTURES / "wrapper-success.json", self.traces / "trace-1.json")
        self._touch_recent(self.traces / "trace-1.json")
        tr.rollup_apply(self.root, since_days=7, apply=True, full=True)

        result = tr.rollup_apply(self.root, since_days=7, apply=True, full=True)
        inc = result["rollup"]["incremental"]
        self.assertEqual(inc["mode"], "full")
        self.assertEqual(inc["files_parsed"], 1)
        cache_path = tr.records_cache_path(self.root)
        self.assertTrue(cache_path.is_file())
        self.assertEqual(len(cache_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_by_turn_aggregation(self) -> None:
        data = json.loads((FIXTURES / "wrapper-success.json").read_text(encoding="utf-8"))
        data["agent_turn_id"] = "turn-rollup-1"
        rec = tr.normalize_wrapper_trace(data, FIXTURES / "wrapper-success.json")
        assert rec is not None
        self.assertEqual(rec.agent_turn_id, "turn-rollup-1")
        agg = tr.aggregate_records([rec])
        self.assertIn("turn-rollup-1", agg["by_turn"])
        self.assertEqual(agg["by_turn"]["turn-rollup-1"]["llm_usage"]["total_tokens"], 1000)


if __name__ == "__main__":
    unittest.main()
