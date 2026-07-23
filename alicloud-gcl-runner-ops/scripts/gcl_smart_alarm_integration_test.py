#!/usr/bin/env python3
"""
gcl_smart_alarm_integration_test.py — Integration tests for Smart Alert + Runner.

Tests the end-to-end workflow:
  1. gcl_runner generates traces (--adaptive mode)
  2. gcl_smart_alarm_engine detects patterns and applies degradation
  3. gcl_runner respects degraded max_iter in subsequent runs

Run with:
    python -m unittest scripts.gcl_smart_alarm_integration_test -v

Or directly:
    python scripts/gcl_smart_alarm_integration_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# Make modules importable when running this file directly
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import gcl_runner as runner
import gcl_smart_alarm_engine as engine


class IntegrationTestBase(unittest.TestCase):
    """Base class for integration tests with temp directories."""

    def setUp(self):
        """Set up temporary directories for each test."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.trace_dir = Path(self.tmpdir.name) / "traces"
        self.trace_dir.mkdir()
        self.state_path = Path(self.tmpdir.name) / "degradation-state.json"

        # Initialize empty state
        self.state_path.write_text(json.dumps({
            "downgraded_resources": {},
            "hot_regions": {},
            "version": "1.0.0"
        }), encoding="utf-8")

    def tearDown(self):
        """Clean up temporary directories."""
        self.tmpdir.cleanup()

    def _create_gcl_trace(self, skill: str, decision: str, resource_id: str = None,
                          region: str = "cn-hangzhou", minutes_ago: int = 0,
                          command: str = None) -> Path:
        """Create a GCL trace file matching gcl_runner output format."""
        now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

        if command is None:
            if skill == "alicloud-ecs-ops" and resource_id:
                command = f"aliyun ecs DescribeInstanceAttribute --InstanceId {resource_id} --RegionId {region}"
            else:
                command = f"aliyun {skill.replace('alicloud-', '').replace('-ops', '')} TestOp"

        trace = {
            "skill": skill,
            "request": "test-request",
            "rubric_version": "1.0.0",
            "timestamp": now.isoformat(),
            "iterations": [
                {
                    "iter": 1,
                    "generator": {
                        "command": command,
                        "exit_code": 0 if decision == "PASS" else 1,
                        "stdout": "test output",
                        "stderr": "",
                        "result_excerpt": "test",
                        "request_id": "test-req-001",
                        "duration_ms": 100
                    },
                    "critic": {
                        "scores": {
                            "correctness": 1.0 if decision == "PASS" else 0.0,
                            "safety": 0.0 if decision == "SAFETY_FAIL" else 1.0,
                            "idempotency": 1.0,
                            "traceability": 1.0,
                            "spec_compliance": 1.0,
                            "region_compliance": 1.0,
                            "credential_hygiene": 1.0,
                            "well_architected": 1.0
                        },
                        "suggestions": [],
                        "matched_regexes": [],
                        "blocking": decision == "SAFETY_FAIL"
                    },
                    "decision": decision
                }
            ],
            "final": {
                "status": decision,
                "iter": 1,
                "output": f"exit_code={0 if decision == 'PASS' else 1} request_id=test-req-001 duration=100ms"
            }
        }

        # Generate unique filename
        ts = now.strftime("%Y%m%d-%H%M%S")
        suffix = f"{minutes_ago:04d}"
        path = self.trace_dir / f"gcl-trace-{skill}-{ts}-{suffix}.json"
        path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
        return path


class EndToEndWorkflowTests(IntegrationTestBase):
    """I1: End-to-end workflow tests."""

    def test_e2e_resource_degradation_workflow(self):
        """完整流程：生成trace → 检测风险 → 应用降级 → 后续runner使用降级max_iter."""
        resource_id = "i-bp1xxxxxxxxxxxxxx"
        skill = "alicloud-ecs-ops"

        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            # Step 1: Create traces that trigger resource_safety_repeated pattern
            # Need 2 SAFETY_FAIL within 30 minutes for the same resource
            self._create_gcl_trace(skill, "SAFETY_FAIL", resource_id, minutes_ago=10)
            self._create_gcl_trace(skill, "SAFETY_FAIL", resource_id, minutes_ago=20)

            # Also create some PASS traces for other resources (noise)
            self._create_gcl_trace(skill, "PASS", "i-bp2xxxxxxxxxxxxxx", minutes_ago=5)
            self._create_gcl_trace(skill, "PASS", "i-bp3xxxxxxxxxxxxxx", minutes_ago=15)

            # Step 2: Run alarm engine to detect patterns and apply degradation
            with mock.patch.object(engine, 'load_traces', return_value=engine.load_traces(self.trace_dir, 60)):
                traces = engine.load_traces(self.trace_dir, 60)
                self.assertEqual(len(traces), 4)

                # Detect patterns
                state = engine.load_degradation_state()
                all_findings = []
                for pattern in engine.DEFAULT_RISK_PATTERNS:
                    matches = engine.match_risk_pattern(traces, pattern)
                    for match in matches:
                        result = engine.apply_degradation(match, state, dry_run=False)
                        match["degradation_result"] = result
                        all_findings.append(match)

                # Verify resource_safety_repeated was detected
                pattern_ids = [f["pattern_id"] for f in all_findings]
                self.assertIn("resource_safety_repeated", pattern_ids)

                # Verify degradation was applied
                self.assertIn(resource_id, state["downgraded_resources"])
                downgraded_info = state["downgraded_resources"][resource_id]
                self.assertEqual(downgraded_info["current_max_iter"], 1)
                self.assertEqual(downgraded_info["original_max_iter"], 2)

            # Step 3: Verify gcl_runner respects the degradation
            command = f"aliyun ecs DescribeInstanceAttribute --InstanceId {resource_id} --RegionId cn-hangzhou"

            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                adaptive_max_iter, reason = runner.get_adaptive_max_iter(skill, command, base_max_iter=2)

                # Should return degraded max_iter (1)
                self.assertEqual(adaptive_max_iter, 1)
                self.assertIsNotNone(reason)
                self.assertIn(resource_id, reason)
                self.assertIn("downgraded", reason.lower())

    def test_e2e_region_burst_detection(self):
        """Region级集中爆发检测流程."""
        skill = "alicloud-ecs-ops"
        region = "cn-hangzhou"

        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            # Create 5 SAFETY_FAIL traces for different resources in same region
            for i in range(5):
                self._create_gcl_trace(
                    skill, "SAFETY_FAIL",
                    f"i-bp{i}xxxxxxxxxxxxxx",
                    region=region,
                    minutes_ago=i*2
                )

            # Load and analyze traces
            traces = engine.load_traces(self.trace_dir, 60)
            self.assertEqual(len(traces), 5)

            # Detect region_safety_burst pattern
            pattern = [p for p in engine.DEFAULT_RISK_PATTERNS if p["id"] == "region_safety_burst"][0]
            matches = engine.match_risk_pattern(traces, pattern)

            # Should detect region burst
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["pattern_id"], "region_safety_burst")
            self.assertEqual(matches[0]["group_key"], region)
            self.assertEqual(matches[0]["occurrence_count"], 5)

            # Apply degradation (should mark region for inspection)
            state = engine.load_degradation_state()
            result = engine.apply_degradation(matches[0], state, dry_run=False)

            self.assertTrue(result["applied"])
            self.assertIn(region, state["hot_regions"])

    def test_e2e_auto_restore_workflow(self):
        """自动恢复过期降级的完整流程."""
        resource_id = "i-bp1xxxxxxxxxxxxxx"

        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            # Manually create an expired degradation
            now = datetime.now(timezone.utc)
            expired_time = now - timedelta(minutes=1)  # 1 minute ago (expired)

            state = {
                "downgraded_resources": {
                    resource_id: {
                        "resource_id": resource_id,
                        "skill": "alicloud-ecs-ops",
                        "original_max_iter": 2,
                        "current_max_iter": 1,
                        "downgraded_at": (now - timedelta(hours=2)).isoformat(),
                        "auto_restore_at": expired_time.isoformat(),
                        "reason": "Test expiration"
                    }
                },
                "hot_regions": {},
                "version": "1.0.0"
            }
            engine.save_degradation_state(state)

            # Verify runner sees the degradation before restore
            command = f"aliyun ecs DescribeInstanceAttribute --InstanceId {resource_id} --RegionId cn-hangzhou"

            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                adaptive_max_iter, reason = runner.get_adaptive_max_iter("alicloud-ecs-ops", command, 2)
                self.assertEqual(adaptive_max_iter, 1)  # Still degraded

            # Run restore_expired_degradations
            current_state = engine.load_degradation_state()
            restored = engine.restore_expired_degradations(current_state, dry_run=False)

            # Verify restoration
            self.assertTrue(any(resource_id in r for r in restored))
            self.assertNotIn(resource_id, current_state["downgraded_resources"])

            # Verify runner no longer sees degradation after restore
            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                engine.save_degradation_state(current_state)  # Save the restored state
                adaptive_max_iter, reason = runner.get_adaptive_max_iter("alicloud-ecs-ops", command, 2)
                self.assertEqual(adaptive_max_iter, 2)  # Restored to original
                self.assertIsNone(reason)


class AdaptiveModeIntegrationTests(IntegrationTestBase):
    """I2: Adaptive mode integration tests."""

    def test_runner_adaptive_mode_reads_degradation_state(self):
        """Runner的--adaptive模式正确读取engine的降级状态."""
        resource_id = "i-bp1xxxxxxxxxxxxxx"
        skill = "alicloud-ecs-ops"
        command = f"aliyun ecs DescribeInstanceAttribute --InstanceId {resource_id} --RegionId cn-hangzhou"

        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                # Initially no degradation
                max_iter, reason = runner.get_adaptive_max_iter(skill, command, base_max_iter=2)
                self.assertEqual(max_iter, 2)
                self.assertIsNone(reason)

                # Create degradation via engine
                state = engine.load_degradation_state()
                state["downgraded_resources"][resource_id] = {
                    "resource_id": resource_id,
                    "skill": skill,
                    "original_max_iter": 2,
                    "current_max_iter": 1,
                    "downgraded_at": datetime.now(timezone.utc).isoformat(),
                    "auto_restore_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "reason": "Integration test"
                }
                engine.save_degradation_state(state)

                # Runner should now see the degradation
                max_iter, reason = runner.get_adaptive_max_iter(skill, command, base_max_iter=2)
                self.assertEqual(max_iter, 1)
                self.assertIsNotNone(reason)
                self.assertIn("downgraded", reason.lower())

    def test_runner_adaptive_mode_unknown_resource(self):
        """Runner的--adaptive模式对未知资源返回base_max_iter."""
        skill = "alicloud-ecs-ops"
        command = "aliyun ecs DescribeRegions"  # No resource ID

        with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
            max_iter, reason = runner.get_adaptive_max_iter(skill, command, base_max_iter=2)
            # Should return base since no resource ID can be extracted
            self.assertEqual(max_iter, 2)
            self.assertIsNone(reason)

    def test_runner_resource_id_extraction_matches_engine(self):
        """Runner和Engine的资源ID提取逻辑一致."""
        test_cases = [
            ("alicloud-ecs-ops", "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx", "i-bp1xxxxxxxxxxxxxx"),
            ("alicloud-rds-ops", "aliyun rds DescribeDBInstanceAttribute --DBInstanceId rm-bp1xxxxxxxxxx", "rm-bp1xxxxxxxxxx"),
            ("alicloud-redis-ops", "aliyun r-kvstore DescribeInstanceAttribute --InstanceId r-bp1xxxxxxxxxx", "r-bp1xxxxxxxxxx"),
        ]

        for skill, command, expected_id in test_cases:
            with self.subTest(skill=skill):
                # Engine extraction
                engine_id = engine.extract_resource_id(skill, command)
                # Runner extraction
                runner_id = runner._extract_resource_id(skill, command)

                self.assertEqual(engine_id, expected_id, f"Engine extraction failed for {skill}")
                self.assertEqual(runner_id, expected_id, f"Runner extraction failed for {skill}")
                self.assertEqual(engine_id, runner_id, f"Engine and Runner extraction mismatch for {skill}")


class TraceFormatCompatibilityTests(IntegrationTestBase):
    """I3: Trace format compatibility tests."""

    def test_engine_parses_runner_trace_format(self):
        """Engine能正确解析Runner生成的trace格式."""
        # Create a trace matching gcl_runner output format
        trace = {
            "skill": "alicloud-ecs-ops",
            "request": "test operation",
            "rubric_version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iterations": [
                {
                    "iter": 1,
                    "generator": {
                        "command": "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx --RegionId cn-hangzhou",
                        "exit_code": 0,
                        "stdout": '{"Instances": {"Instance": []}}',
                        "stderr": "",
                        "result_excerpt": '{"Instances":',
                        "request_id": "test-req-001",
                        "duration_ms": 150
                    },
                    "critic": {
                        "scores": {
                            "correctness": 1.0,
                            "safety": 1.0,
                            "idempotency": 1.0,
                            "traceability": 1.0,
                            "spec_compliance": 1.0,
                            "region_compliance": 1.0,
                            "credential_hygiene": 1.0,
                            "well_architected": 1.0
                        },
                        "suggestions": [],
                        "matched_regexes": [],
                        "blocking": False
                    },
                    "decision": "PASS"
                }
            ],
            "final": {
                "status": "PASS",
                "iter": 1,
                "output": "exit_code=0 request_id=test-req-001 duration=150ms"
            }
        }

        path = self.trace_dir / "gcl-trace-test.json"
        path.write_text(json.dumps(trace), encoding="utf-8")

        # Engine should parse this correctly
        parsed = engine.parse_trace_file(path)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["skill"], "alicloud-ecs-ops")
        self.assertEqual(parsed["decision"], "PASS")
        self.assertEqual(parsed["resource_id"], "i-bp1xxxxxxxxxxxxxx")
        self.assertEqual(parsed["region"], "cn-hangzhou")

    def test_engine_handles_hallucination_abort_traces(self):
        """Engine能正确处理HALLUCINATION_ABORT类型的trace."""
        trace = {
            "skill": "alicloud-ecs-ops",
            "request": "test",
            "rubric_version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iterations": [
                {
                    "iter": 1,
                    "hallucination_detector": {
                        "status": "FAIL",
                        "checks": {
                            "cli_parameters": {"status": "FAIL", "unrecognized": ["--UnknownFlag"]}
                        }
                    },
                    "regenerated": False,
                    "generator": {
                        "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxxxxxx --RegionId cn-hangzhou",
                        "exit_code": -1,
                        "result_excerpt": ""
                    },
                    "critic": {
                        "scores": {k: 0.0 for k in ["correctness", "safety", "idempotency", "traceability", "spec_compliance", "region_compliance", "credential_hygiene", "well_architected"]},
                        "suggestions": ["HALLUCINATION_ABORT: Unrecognized CLI parameters"],
                        "matched_regexes": [],
                        "blocking": True
                    },
                    "decision": "HALLUCINATION_ABORT"
                }
            ],
            "final": {
                "status": "HALLUCINATION_ABORT",
                "iter": 1
            }
        }

        path = self.trace_dir / "gcl-trace-hallucination.json"
        path.write_text(json.dumps(trace), encoding="utf-8")

        parsed = engine.parse_trace_file(path)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["decision"], "HALLUCINATION_ABORT")
        self.assertEqual(parsed["resource_id"], "i-bp1xxxxxxxxxxxxxx")


class StateFileCompatibilityTests(IntegrationTestBase):
    """I4: State file compatibility tests."""

    def test_runner_and_engine_use_same_state_file_path(self):
        """Runner和Engine使用相同的状态文件路径."""
        # Test with environment variable set
        with mock.patch.dict(os.environ, {"ALIYUN_SKILLS_RUNTIME_ROOT": "/test/runtime"}):
            engine_path = engine.get_degradation_state_path()
            runner_path = runner._get_degradation_state_path()

            self.assertEqual(engine_path, runner_path)
            self.assertEqual(engine_path, Path("/test/runtime/gcl-degradation-state.json"))

        # Test without environment variable (fallback)
        with mock.patch.dict(os.environ, {}, clear=True):
            engine_path = engine.get_degradation_state_path()
            runner_path = runner._get_degradation_state_path()

            self.assertEqual(engine_path, runner_path)

    def test_runner_reads_engine_written_state(self):
        """Runner能正确读取Engine写入的状态."""
        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                # Engine writes state
                state = {
                    "downgraded_resources": {
                        "i-bp1xxxxxxxxxxxxxx": {
                            "resource_id": "i-bp1xxxxxxxxxxxxxx",
                            "skill": "alicloud-ecs-ops",
                            "original_max_iter": 2,
                            "current_max_iter": 1,
                            "downgraded_at": datetime.now(timezone.utc).isoformat(),
                            "auto_restore_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                            "reason": "Test"
                        }
                    },
                    "hot_regions": {
                        "cn-hangzhou": {
                            "region": "cn-hangzhou",
                            "detected_at": datetime.now(timezone.utc).isoformat()
                        }
                    },
                    "version": "1.0.0"
                }
                engine.save_degradation_state(state)

                # Runner reads state
                runner_state = runner._load_degradation_state()

                self.assertIn("i-bp1xxxxxxxxxxxxxx", runner_state["downgraded_resources"])
                self.assertEqual(runner_state["downgraded_resources"]["i-bp1xxxxxxxxxxxxxx"]["current_max_iter"], 1)


class MultipleResourceScenarioTests(IntegrationTestBase):
    """I5: Multiple resource scenario tests."""

    def test_multiple_resources_partial_degradation(self):
        """多个资源中部分被降级的场景."""
        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                # Degrade only resource 1 and 3
                state = engine.load_degradation_state()
                state["downgraded_resources"]["i-bp1xxxxxxxxxxxxxx"] = {
                    "resource_id": "i-bp1xxxxxxxxxxxxxx",
                    "current_max_iter": 1,
                    "auto_restore_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                }
                state["downgraded_resources"]["i-bp3xxxxxxxxxxxxxx"] = {
                    "resource_id": "i-bp3xxxxxxxxxxxxxx",
                    "current_max_iter": 1,
                    "auto_restore_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                }
                engine.save_degradation_state(state)

                # Test each resource
                resources = [
                    ("i-bp1xxxxxxxxxxxxxx", 1),  # Degraded
                    ("i-bp2xxxxxxxxxxxxxx", 2),  # Not degraded
                    ("i-bp3xxxxxxxxxxxxxx", 1),  # Degraded
                    ("i-bp4xxxxxxxxxxxxxx", 2),  # Not degraded
                ]

                for resource_id, expected_max_iter in resources:
                    command = f"aliyun ecs DescribeInstanceAttribute --InstanceId {resource_id} --RegionId cn-hangzhou"
                    max_iter, reason = runner.get_adaptive_max_iter("alicloud-ecs-ops", command, 2)

                    self.assertEqual(max_iter, expected_max_iter,
                                     f"Resource {resource_id} should have max_iter={expected_max_iter}")

    def test_degradation_isolation_between_skills(self):
        """不同skill之间的降级隔离."""
        with mock.patch.object(engine, 'get_degradation_state_path', return_value=self.state_path):
            with mock.patch.object(runner, '_get_degradation_state_path', return_value=self.state_path):
                # Degrade ECS resource
                state = engine.load_degradation_state()
                state["downgraded_resources"]["i-bp1xxxxxxxxxxxxxx"] = {
                    "resource_id": "i-bp1xxxxxxxxxxxxxx",
                    "skill": "alicloud-ecs-ops",
                    "current_max_iter": 1
                }
                engine.save_degradation_state(state)

                # RDS resource with similar ID pattern should not be affected
                rds_command = "aliyun rds DescribeDBInstanceAttribute --DBInstanceId rm-bp1xxxxxxxxxx --RegionId cn-hangzhou"
                max_iter, reason = runner.get_adaptive_max_iter("alicloud-rds-ops", rds_command, 2)

                self.assertEqual(max_iter, 2)  # Not degraded
                self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
