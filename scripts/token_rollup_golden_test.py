#!/usr/bin/env python3
"""Golden integration tests for token_rollup.py — end-to-end pipeline validation.

Each scenario uses realistic golden fixtures and validates ALL 4 metadata
fields (trace_id, session_id, user_id, llm_usage) at every pipeline stage.

These are regression tests: if someone later drops or renames a metadata
field in any pipeline layer, these tests catch it.

Run:  python3 -m unittest token_rollup_golden_test -v
"""

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

GOLDEN = SCRIPT_DIR / "fixtures" / "golden"


class GoldenIntegrationTests(unittest.TestCase):
    """Golden dataset integration tests — full pipeline with metadata validation."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="golden-token-rollup-")
        self.root = Path(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── helpers ──

    def _touch_recent(self, path: Path) -> None:
        import os
        now = datetime.now(tz=timezone.utc).timestamp()
        os.utime(path, (now, now))

    def _assert_has_4_metadata(self, record: tr.NormalizedRecord, *,
                               trace_id: str, session_id: str, user_id: str,
                               min_tokens: int = 0) -> None:
        """Assert all 4 metadata fields are present and correct."""
        self.assertEqual(record.trace_id, trace_id, "trace_id mismatch")
        self.assertEqual(record.session_id, session_id, "session_id mismatch")
        self.assertEqual(record.user_id, user_id, "user_id mismatch")
        self.assertGreaterEqual(
            record.llm_usage.get("total_tokens", 0), min_tokens,
            f"llm_usage.total_tokens too low: got {record.llm_usage.get('total_tokens')} < {min_tokens}"
        )

    def _assert_dict_has_4_metadata(self, d: dict, *,
                                     trace_id: str, session_id: str, user_id: str) -> None:
        """Assert dict (from record_to_dict / read from disk) has all 4 metadata fields."""
        self.assertEqual(d.get("trace_id"), trace_id, "dict trace_id mismatch")
        self.assertEqual(d.get("session_id"), session_id, "dict session_id mismatch")
        self.assertEqual(d.get("user_id"), user_id, "dict user_id mismatch")
        self.assertIn("llm_usage", d, "dict missing llm_usage")
        self.assertIsInstance(d["llm_usage"], dict, "llm_usage not a dict")

    # ── Scenario G1: Normalize → Serialize → Deserialize ──

    def test_g1_normalize_serialize_deserialize(self) -> None:
        """G1: Wrapper trace through normalize→to_dict→from_dict→aggregate preserves all metadata."""
        path = GOLDEN / "G1-single-wrapper.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        fake_path = Path(self._tmp) / "traces" / "G1.json"
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

        # Stage 1: normalize_wrapper_trace
        rec = tr.normalize_wrapper_trace(data, fake_path)
        self.assertIsNotNone(rec)
        self._assert_has_4_metadata(rec,
                                     trace_id="golden-trace-g1",
                                     session_id="golden-sess-g1",
                                     user_id="golden-user-g1",
                                     min_tokens=500)
        self.assertEqual(rec.skill, "alicloud-ecs-ops")
        self.assertEqual(rec.operation, "DescribeInstances")
        self.assertEqual(rec.status, "success")
        self.assertTrue(rec.success)
        self.assertFalse(rec.waste)
        self.assertEqual(rec.coding_agent, "cursor")
        self.assertEqual(rec.model, "claude-sonnet-4")
        self.assertEqual(rec.agent_turn_tokens, 350)
        self.assertEqual(rec.agent_turn_id, "turn-g1-001")
        self.assertIsNotNone(rec.mcp)
        self.assertEqual(rec.mcp["mcp_tool_utilization"], 1.0)

        # Stage 2: record_to_dict
        d = tr.record_to_dict(rec)
        self._assert_dict_has_4_metadata(d,
                                          trace_id="golden-trace-g1",
                                          session_id="golden-sess-g1",
                                          user_id="golden-user-g1")
        self.assertEqual(d["llm_usage"]["total_tokens"], 500)
        self.assertEqual(d["agent_turn_id"], "turn-g1-001")

        # Stage 3: record_from_dict (roundtrip)
        restored = tr.record_from_dict(d)
        self.assertIsNotNone(restored)
        self._assert_has_4_metadata(restored,
                                     trace_id="golden-trace-g1",
                                     session_id="golden-sess-g1",
                                     user_id="golden-user-g1",
                                     min_tokens=500)
        self.assertEqual(restored.agent_turn_id, "turn-g1-001")
        self.assertEqual(restored.skill, "alicloud-ecs-ops")

        # Stage 4: aggregate_records
        agg = tr.aggregate_records([rec])
        self.assertIn("global", agg)
        g = agg["global"]
        self.assertEqual(g["trace_count"], 1)
        self.assertEqual(g["success_count"], 1)
        self.assertEqual(g["llm_usage"]["total_tokens"], 500)
        self.assertEqual(g["llm_usage"]["prompt_tokens"], 400)
        self.assertEqual(g["llm_usage"]["completion_tokens"], 100)
        self.assertIn("alicloud-ecs-ops", agg["by_skill"])
        self.assertIn("DescribeInstances", agg["by_op"])
        self.assertIn("cursor|claude-sonnet-4", agg["by_agent_model"])

    # ── Scenario G2: Waste wrapper trace → waste events ──

    def test_g2_waste_wrapper_preserves_user_id(self) -> None:
        """G2: Failed wrapper trace → normalize → build_waste_events preserves user_id."""
        path = GOLDEN / "G2-multi-user-waste.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        fake_path = Path(self._tmp) / "traces" / "G2.json"
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

        rec = tr.normalize_wrapper_trace(data, fake_path)
        self.assertIsNotNone(rec)
        self._assert_has_4_metadata(rec,
                                     trace_id="golden-trace-g2-waste",
                                     session_id="golden-sess-g2",
                                     user_id="golden-user-g2",
                                     min_tokens=250)
        # Waste trace assertions
        self.assertFalse(rec.success)
        self.assertTrue(rec.waste)
        self.assertEqual(rec.status, "failed")
        self.assertEqual(rec.error_code, "InvalidInstanceId.NotFound")
        self.assertEqual(rec.l2_category_hint, "cli_parameter")

        # build_waste_events
        events = tr.build_waste_events([rec])
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["trace_id"], "golden-trace-g2-waste")
        self.assertEqual(ev["session_id"], "golden-sess-g2")
        self.assertEqual(ev["user_id"], "golden-user-g2")
        self.assertEqual(ev["waste_tokens"], 250)
        self.assertEqual(ev["error_code"], "InvalidInstanceId.NotFound")
        self.assertEqual(ev["l2_category_hint"], "cli_parameter")
        self.assertEqual(ev["source"], "wrapper")

    # ── Scenario G3: GCL waste trace → normalize → waste events ──

    def test_g3_gcl_waste_preserves_all_metadata(self) -> None:
        """G3: GCL MAX_ITER trace → normalize → build_waste_events preserves metadata."""
        path = GOLDEN / "G3-gcl-iter-max.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        fake_path = Path(self._tmp) / "audit" / "G3.json"
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

        rec = tr.normalize_gcl_trace(data, fake_path)
        self.assertIsNotNone(rec)
        self._assert_has_4_metadata(rec,
                                     trace_id="golden-trace-g3-gcl",
                                     session_id="golden-sess-g3",
                                     user_id="golden-user-g3",
                                     min_tokens=870)  # sum of 3 critic iterations
        # GCL-specific assertions
        self.assertEqual(rec.critic_tokens, 870)  # 350+290+230
        self.assertEqual(rec.llm_usage["total_tokens"], 870)
        self.assertTrue(rec.waste)
        self.assertEqual(rec.status, "MAX_ITER")
        self.assertEqual(rec.source, "gcl-runner")
        self.assertEqual(rec.l2_category_hint, "max_iter")

        # build_waste_events
        events = tr.build_waste_events([rec])
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["trace_id"], "golden-trace-g3-gcl")
        self.assertEqual(ev["session_id"], "golden-sess-g3")
        self.assertEqual(ev["user_id"], "golden-user-g3")
        self.assertEqual(ev["waste_tokens"], 870)
        self.assertEqual(ev["critic_tokens"], 870)
        self.assertEqual(ev["l2_category_hint"], "max_iter")

    # ── Scenario G4: Session MCP enrichment preserves user_id ──

    def test_g4_session_mcp_enrichment_preserves_user_id(self) -> None:
        """G4: Trace without MCP gets enriched from session file; user_id preserved in rollup."""
        # Set up: trace dir + session dir
        traces_dir = self.root / ".runtime" / "traces" / "alicloud-rds-ops"
        traces_dir.mkdir(parents=True)
        sessions_dir = self.root / ".runtime" / "sessions" / "alicloud-rds-ops"
        sessions_dir.mkdir(parents=True)

        # Copy trace (no MCP metadata) and session (has MCP)
        trace_path = traces_dir / "trace-g4.json"
        session_path = sessions_dir / "skillopt-session-sess-g4.json"
        shutil.copy(GOLDEN / "G4-session-mcp-supplement.json", trace_path)
        shutil.copy(GOLDEN / "G4-supplement-session.json", session_path)
        self._touch_recent(trace_path)
        self._touch_recent(session_path)

        # Full rollup
        result = tr.rollup_apply(self.root, since_days=7, apply=False, full=True)
        self.assertEqual(result["trace_records"], 1)

        # Verify the trace was enriched with session MCP
        records, _ = tr.collect_records(self.root, since_days=7, mode="full")
        self.assertEqual(len(records), 1)
        rec = records[0]
        self._assert_has_4_metadata(rec,
                                     trace_id="golden-trace-g4-no-mcp",
                                     session_id="golden-sess-g4",
                                     user_id="golden-user-g4",
                                     min_tokens=230)
        # MCP enrichment should have happened
        self.assertIsNotNone(rec.mcp, "MCP enrichment from session should have populated rec.mcp")
        self.assertEqual(rec.mcp["mcp_tool_utilization"], 0.3333)
        self.assertEqual(rec.mcp["mcp_schema_waste_tokens"], 200)

        # Verify rollup aggregation contains the enriched MCP data
        rollup = result["rollup"]
        mcp_join = rollup["mcp_join"]
        self.assertTrue(mcp_join["available"])
        # Note: sidecar_used refers to the IDE sidecar file (mcp-context-latest.json)
        # which we did NOT create — session-level MCP enrichment is separate.
        # The record.mcp was populated via enrich_records_from_sessions instead.
        self.assertFalse(mcp_join["sidecar_used"],
                         "sidecar_used should be False — no mcp-context-latest.json was provided")
        # But MCP data IS present via session enrichment
        self.assertEqual(mcp_join["traces_with_mcp"], 1,
                         "Session-enriched MCP should count as traces_with_mcp=1")

    # ── Scenario G5: Full rollup across multiple traces ──

    def test_g5_full_rollup_multi_trace_preserves_metadata(self) -> None:
        """G5: Multiple traces (wrapper success, waste, GCL) → full rollup preserves metadata."""
        # Set up trace files on disk simulating real layout
        traces_dir = self.root / ".runtime" / "traces" / "alicloud-ecs-ops"
        traces_dir.mkdir(parents=True)
        audit_dir = self.root / ".runtime" / "audit"
        audit_dir.mkdir(parents=True)

        # Copy 3 golden fixtures as trace files
        shutil.copy(GOLDEN / "G1-single-wrapper.json", traces_dir / "trace-g1.json")
        shutil.copy(GOLDEN / "G2-multi-user-waste.json", traces_dir / "trace-g2.json")
        shutil.copy(GOLDEN / "G3-gcl-iter-max.json", audit_dir / "gcl-trace-g3.json")
        # Also add a different-user trace for user_id diversity
        shutil.copy(GOLDEN / "G5-multi-skill-user.json", traces_dir / "trace-g5.json")

        for p in traces_dir.glob("*.json"):
            self._touch_recent(p)
        self._touch_recent(audit_dir / "gcl-trace-g3.json")

        # Full rollup with apply=True (writes to disk)
        result = tr.rollup_apply(self.root, since_days=7, apply=True, full=True)
        self.assertEqual(result["trace_records"], 4,
                         "Expected 4 trace records (G1 wrapper + G2 waste + G3 GCL + G5 multi-skill)")

        rollup = result["rollup"]

        # Validate coverage
        coverage = result["coverage"]
        self.assertEqual(coverage["traces_scanned"], 4, "Coverage should count 4 traces")
        self.assertEqual(coverage["version"], tr.ROLLUP_VERSION)

        # Validate global aggregation
        g = rollup["global"]
        self.assertEqual(g["trace_count"], 4)
        total_tokens = g["llm_usage"]["total_tokens"]
        # G1: 500, G2: 250, G3: 870, G5: 750 = 2370
        self.assertEqual(total_tokens, 2370,
                         f"Expected 2370 total tokens, got {total_tokens}")
        self.assertEqual(g["waste_count"], 2,
                         "Expected 2 waste traces (G2 failed wrapper + G3 MAX_ITER)")
        # waste_tokens is not directly serialized in to_dict; derive from waste_ratio
        # waste_ratio = waste_tokens / max(total, 1)
        # G2(250) + G3(870) = 1120 waste / 2370 total ≈ 0.4726
        expected_waste_ratio = round(1120 / 2370, 4)
        self.assertAlmostEqual(g["waste_ratio"], expected_waste_ratio, places=4,
                               msg=f"Expected waste_ratio ~{expected_waste_ratio}, got {g['waste_ratio']}")

        # Validate by_skill
        by_skill = rollup["by_skill"]
        self.assertIn("alicloud-ecs-ops", by_skill, "by_skill missing alicloud-ecs-ops")
        ecs = by_skill["alicloud-ecs-ops"]
        # G1(ecs) + G2(ecs) + G3(ecs) = 3 traces
        self.assertEqual(ecs["trace_count"], 3, "Expected 3 ecs traces")
        self.assertIn("alicloud-slb-ops", by_skill, "by_skill missing alicloud-slb-ops")
        slb = by_skill["alicloud-slb-ops"]
        self.assertEqual(slb["trace_count"], 1, "Expected 1 slb trace")

        # Validate by_agent_model
        by_am = rollup["by_agent_model"]
        self.assertIn("cursor|claude-sonnet-4", by_am)
        self.assertIn("harness_cli|gpt-4o-mini", by_am)

        # Validate rollup written to disk
        rollup_path = tr.token_root(self.root) / "current" / "rollup.json"
        self.assertTrue(rollup_path.is_file(), "rollup.json should exist after apply=True")
        disk_rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
        self.assertEqual(disk_rollup["global"]["trace_count"], 4)

        # Validate incremental state file
        state_path = tr.incremental_state_path(self.root)
        self.assertTrue(state_path.is_file(), "incremental-state.json should exist")
        state = tr.load_incremental_state(self.root)
        self.assertIsNotNone(state)
        # Should have indexed 4 files
        indexed = (state or {}).get("indexed_files", {})
        self.assertEqual(len(indexed), 4, f"Expected 4 indexed files, got {len(indexed)}")


if __name__ == "__main__":
    unittest.main()
