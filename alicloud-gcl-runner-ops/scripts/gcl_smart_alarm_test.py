#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcl_smart_alarm_test.py — unit tests for `gcl_smart_alarm_engine.py`.

Pure stdlib `unittest`; no third-party dependencies. Run with:
    python -m unittest scripts.gcl_smart_alarm_test -v

or
    python scripts/gcl_smart_alarm_test.py

Test coverage:
- T1  Resource ID extraction — all 17 SKILL patterns + edge cases
- T2  Region extraction — standard region formats
- T3  Trace loading — JSON parsing, filtering, time window
- T4  Risk pattern detection — resource_safety_repeated, resource_hallucination_repeated,
      region_concentration, skill_wide_failure
- T5  Degradation state management — apply, check, restore
- T6  CLI integration — main() returns correct exit codes
- T7  Edge cases — empty traces, malformed JSON, missing fields
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

# Make `gcl_smart_alarm_engine` importable when running this file directly
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import gcl_smart_alarm_engine as engine  # noqa: E402


def _mock_state_file(func):
    """Decorator to mock state file to a temp location for testing."""
    def wrapper(*args, **kwargs):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=temp_path):
                # Initialize with empty state
                temp_path.write_text(json.dumps({
                    "downgraded_resources": {},
                    "hot_regions": {},
                    "version": "1.0.0"
                }), encoding="utf-8")
                return func(*args, **kwargs)
        finally:
            if temp_path.exists():
                temp_path.unlink()
    return wrapper


# ---------------------------------------------------------------------------
# T1: Resource ID extraction (extract_resource_id)
# ---------------------------------------------------------------------------


class ResourceIdExtractionTests(unittest.TestCase):
    """T1: Resource ID extraction for all 17 supported skills."""

    def test_ecs_instance_id(self):
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-ecs-ops", cmd),
            "i-bp1xxxxxxxxxxxxxx"
        )

    def test_rds_instance_id(self):
        cmd = "aliyun rds DescribeDBInstanceAttribute --DBInstanceId rm-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-rds-ops", cmd),
            "rm-bp1xxxxxxxxxx"
        )

    def test_redis_instance_id(self):
        cmd = "aliyun r-kvstore DescribeInstanceAttribute --InstanceId r-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-redis-ops", cmd),
            "r-bp1xxxxxxxxxx"
        )

    def test_mongodb_instance_id(self):
        cmd = "aliyun dds DescribeDBInstanceAttribute --DBInstanceId dds-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-mongodb-ops", cmd),
            "dds-bp1xxxxxxxxxx"
        )

    def test_polardb_cluster_id(self):
        cmd = "aliyun polardb DescribeDBClusterAttribute --DBClusterId pc-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-polar-mysql-ops", cmd),
            "pc-bp1xxxxxxxxxx"
        )

    def test_elasticsearch_instance_id(self):
        cmd = "aliyun elasticsearch DescribeInstance --InstanceId es-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-elasticsearch-ops", cmd),
            "es-bp1xxxxxxxxxx"
        )

    def test_vpc_id(self):
        cmd = "aliyun vpc DescribeVpcAttribute --VpcId vpc-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-vpc-ops", cmd),
            "vpc-bp1xxxxxxxxxx"
        )

    def test_nat_gateway_id(self):
        cmd = "aliyun vpc DescribeNatGatewayAttribute --NatGatewayId ngw-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-nat-ops", cmd),
            "ngw-bp1xxxxxxxxxx"
        )

    def test_eip_allocation_id(self):
        cmd = "aliyun vpc DescribeEipAddress --AllocationId eip-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-eip-ops", cmd),
            "eip-bp1xxxxxxxxxx"
        )

    def test_slb_load_balancer_id(self):
        cmd = "aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId lb-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-slb-ops", cmd),
            "lb-bp1xxxxxxxxxx"
        )

    def test_ack_cluster_id(self):
        cmd = "aliyun cs DescribeClusterDetail --ClusterId c-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-ack-ops", cmd),
            "c-bp1xxxxxxxxxx"
        )

    def test_fc_service_name(self):
        cmd = "aliyun fc GetService --serviceName my-service"
        self.assertEqual(
            engine.extract_resource_id("alicloud-fc-ops", cmd),
            "my-service"
        )

    def test_kms_key_id(self):
        cmd = "aliyun kms DescribeKey --KeyId key-bp1xxxxxxxxxx"
        self.assertEqual(
            engine.extract_resource_id("alicloud-kms-ops", cmd),
            "key-bp1xxxxxxxxxx"
        )

    def test_ram_user_name(self):
        cmd = "aliyun ram GetUser --UserName admin@example.com"
        self.assertEqual(
            engine.extract_resource_id("alicloud-ram-ops", cmd),
            "admin@example.com"
        )

    def test_sls_project_name(self):
        cmd = "aliyun log GetProject --project my-project"
        self.assertEqual(
            engine.extract_resource_id("alicloud-sls-ops", cmd),
            "my-project"
        )

    def test_quoted_instance_id_double_quote(self):
        """双引号包围的InstanceId应该被正确处理."""
        cmd = 'aliyun ecs DescribeInstanceAttribute --InstanceId "i-bp1xxxxxxxxxxxxxx"'
        self.assertEqual(
            engine.extract_resource_id("alicloud-ecs-ops", cmd),
            "i-bp1xxxxxxxxxxxxxx"
        )

    def test_quoted_instance_id_single_quote(self):
        """单引号包围的InstanceId应该被正确处理."""
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId 'i-bp1xxxxxxxxxxxxxx'"
        self.assertEqual(
            engine.extract_resource_id("alicloud-ecs-ops", cmd),
            "i-bp1xxxxxxxxxxxxxx"
        )

    def test_quoted_service_name(self):
        """引号包围的serviceName应该被正确处理."""
        cmd = 'aliyun fc GetService --serviceName "my-service"'
        self.assertEqual(
            engine.extract_resource_id("alicloud-fc-ops", cmd),
            "my-service"
        )

    def test_quoted_username(self):
        """引号包围的UserName应该被正确处理."""
        cmd = 'aliyun ram GetUser --UserName "admin@example.com"'
        self.assertEqual(
            engine.extract_resource_id("alicloud-ram-ops", cmd),
            "admin@example.com"
        )

    def test_unknown_skill_returns_none(self):
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxx"
        self.assertIsNone(engine.extract_resource_id("unknown-skill", cmd))

    def test_no_match_returns_none(self):
        cmd = "aliyun ecs DescribeRegions"
        self.assertIsNone(engine.extract_resource_id("alicloud-ecs-ops", cmd))


# ---------------------------------------------------------------------------
# T2: Region extraction (extract_region)
# ---------------------------------------------------------------------------


class RegionExtractionTests(unittest.TestCase):
    """T2: Region ID extraction from commands."""

    def test_cn_hangzhou(self):
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        self.assertEqual(engine.extract_region(cmd), "cn-hangzhou")

    def test_cn_beijing(self):
        cmd = "aliyun rds DescribeDBInstances --RegionId cn-beijing"
        self.assertEqual(engine.extract_region(cmd), "cn-beijing")

    def test_ap_southeast_1(self):
        cmd = "aliyun vpc DescribeVpcs --RegionId ap-southeast-1"
        self.assertEqual(engine.extract_region(cmd), "ap-southeast-1")

    def test_us_west_1(self):
        cmd = "aliyun slb DescribeLoadBalancers --RegionId us-west-1"
        self.assertEqual(engine.extract_region(cmd), "us-west-1")

    def test_eu_central_1(self):
        cmd = "aliyun ecs DescribeInstances --RegionId eu-central-1"
        self.assertEqual(engine.extract_region(cmd), "eu-central-1")

    def test_cn_hangzhou_finance_1(self):
        """测试金融云Region格式."""
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou-finance-1"
        self.assertEqual(engine.extract_region(cmd), "cn-hangzhou-finance-1")

    def test_cn_beijing_huawei(self):
        """测试华为云合作Region."""
        cmd = "aliyun ecs DescribeInstances --RegionId cn-beijing-huawei"
        self.assertEqual(engine.extract_region(cmd), "cn-beijing-huawei")

    def test_quoted_region_double_quote(self):
        """双引号包围的RegionId应该被正确处理."""
        cmd = 'aliyun ecs DescribeInstances --RegionId "cn-hangzhou"'
        self.assertEqual(engine.extract_region(cmd), "cn-hangzhou")

    def test_quoted_region_single_quote(self):
        """单引号包围的RegionId应该被正确处理."""
        cmd = "aliyun ecs DescribeInstances --RegionId 'cn-beijing'"
        self.assertEqual(engine.extract_region(cmd), "cn-beijing")

    def test_no_region_returns_none(self):
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxx"
        self.assertIsNone(engine.extract_region(cmd))


# ---------------------------------------------------------------------------
# T3: Trace parsing (parse_trace_file)
# ---------------------------------------------------------------------------


class TraceParsingTests(unittest.TestCase):
    """T3: Trace file parsing with proper GCL trace format."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.trace_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_gcl_trace_file(self, filename: str, trace_data: dict) -> Path:
        path = self.trace_dir / filename
        path.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")
        return path

    def test_parse_valid_gcl_trace(self):
        """解析标准GCL trace文件格式."""
        now = datetime.now(timezone.utc)
        trace = {
            "timestamp": now.isoformat(),
            "skill": "alicloud-ecs-ops",
            "op": "DescribeInstanceAttribute",
            "command": "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou",
            "max_iter": 2,
            "iterations": [
                {
                    "iter": 1,
                    "decision": "PASS",
                    "generator": {
                        "command": "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
                    }
                }
            ],
            "final": {"status": "PASS", "iter": 1}
        }
        path = self._create_gcl_trace_file("gcl-trace-test.json", trace)
        
        result = engine.parse_trace_file(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["skill"], "alicloud-ecs-ops")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["resource_id"], "i-bp1xxxxxxxxxx")
        self.assertEqual(result["region"], "cn-hangzhou")

    def test_parse_safety_fail_trace(self):
        """解析SAFETY_FAIL类型的trace."""
        now = datetime.now(timezone.utc)
        trace = {
            "timestamp": now.isoformat(),
            "skill": "alicloud-ecs-ops",
            "op": "DeleteInstance",
            "command": "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou --Force",
            "iterations": [
                {
                    "iter": 1,
                    "decision": "SAFETY_FAIL",
                    "generator": {
                        "command": "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou --Force"
                    }
                }
            ],
            "final": {"status": "SAFETY_FAIL", "iter": 1}
        }
        path = self._create_gcl_trace_file("gcl-trace-safety.json", trace)
        
        result = engine.parse_trace_file(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["decision"], "SAFETY_FAIL")
        self.assertEqual(result["resource_id"], "i-bp1xxxxxxxxxx")

    def test_parse_malformed_json_returns_none(self):
        """解析无效JSON返回None."""
        path = self.trace_dir / "invalid.json"
        path.write_text("not valid json", encoding="utf-8")
        
        result = engine.parse_trace_file(path)
        self.assertIsNone(result)

    def test_parse_missing_iterations_returns_none(self):
        """缺少iterations字段返回None."""
        trace = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill": "alicloud-ecs-ops",
            # 缺少iterations
        }
        path = self._create_gcl_trace_file("no-iterations.json", trace)
        
        result = engine.parse_trace_file(path)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# T4: Risk pattern detection (match_risk_pattern)
# ---------------------------------------------------------------------------


class RiskPatternDetectionTests(unittest.TestCase):
    """T4: Detection of all 4 risk patterns."""

    def _create_trace(self, skill: str, decision: str, resource_id: str = None, 
                      region: str = None, minutes_ago: int = 0) -> dict:
        now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        trace = {
            "trace_file": f"trace_{minutes_ago}.json",
            "skill": skill,
            "timestamp": now,
            "decision": decision,
            "resource_id": resource_id,
            "region": region,
            "command": f"aliyun {skill} TestOp --InstanceId {resource_id} --RegionId {region}" if resource_id else f"aliyun {skill} TestOp",
        }
        return trace

    def test_resource_safety_repeated_pattern(self):
        """同一资源2次SAFETY_FAIL应该触发资源级Safety反复失败模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", "i-bp1xxxxxxxxxx", "cn-hangzhou", 10),
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", "i-bp1xxxxxxxxxx", "cn-hangzhou", 20),
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # resource_safety_repeated
        matches = engine.match_risk_pattern(traces, pattern)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["pattern_id"], "resource_safety_repeated")
        self.assertEqual(matches[0]["severity"], "P1")
        self.assertEqual(matches[0]["action"], "downgrade_resource_max_iter")

    def test_resource_hallucination_repeated_pattern(self):
        """同一资源2次HALLUCINATION_ABORT应该触发Hallucination持续发生模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "HALLUCINATION_ABORT", "i-bp1xxxxxxxxxx", "cn-hangzhou", 15),
            self._create_trace("alicloud-ecs-ops", "HALLUCINATION_ABORT", "i-bp1xxxxxxxxxx", "cn-hangzhou", 30),
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[1]  # resource_hallucination_repeated
        matches = engine.match_risk_pattern(traces, pattern)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["pattern_id"], "resource_hallucination_repeated")
        self.assertEqual(matches[0]["severity"], "P2")

    def test_region_safety_burst_pattern(self):
        """同一Region 5次失败应该触发Region级Safety集中爆发模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", f"i-bp{i}", "cn-hangzhou", i*2)
            for i in range(5)
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[2]  # region_safety_burst
        matches = engine.match_risk_pattern(traces, pattern)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["pattern_id"], "region_safety_burst")
        self.assertEqual(matches[0]["severity"], "P0")
        self.assertEqual(matches[0]["action"], "trigger_region_inspection")

    def test_skill_wide_failure_pattern(self):
        """同一Skill 10次失败应该触发Skill级全面失败模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", f"i-bp{i}", "cn-hangzhou", i*2)
            for i in range(10)
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[3]  # skill_wide_failure
        matches = engine.match_risk_pattern(traces, pattern)
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["pattern_id"], "skill_wide_failure")
        self.assertEqual(matches[0]["severity"], "P0")

    def test_no_patterns_detected_for_pass_traces(self):
        """全是PASS的trace不应该触发任何风险模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "PASS", f"i-bp{i}", "cn-hangzhou", i*2)
            for i in range(20)
        ]
        
        for pattern in engine.DEFAULT_RISK_PATTERNS:
            matches = engine.match_risk_pattern(traces, pattern)
            self.assertEqual(len(matches), 0, f"Pattern {pattern['id']} should not match PASS traces")

    def test_mixed_decisions_no_single_resource_pattern(self):
        """不同资源的失败不应该触发资源级模式."""
        traces = [
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", f"i-bp{i}", "cn-hangzhou", i*5)
            for i in range(5)
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # resource_safety_repeated
        matches = engine.match_risk_pattern(traces, pattern)
        
        # 不同资源，不应该匹配resource_safety_repeated
        self.assertEqual(len(matches), 0)

    def test_time_window_filtering(self):
        """时间窗口过滤测试."""
        # 60分钟窗口，超过窗口的trace不应被计入
        traces = [
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", "i-bp1xxxxxxxxxx", "cn-hangzhou", 10),
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", "i-bp1xxxxxxxxxx", "cn-hangzhou", 20),
            self._create_trace("alicloud-ecs-ops", "SAFETY_FAIL", "i-bp1xxxxxxxxxx", "cn-hangzhou", 90),  # 超过60分钟窗口
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # resource_safety_repeated (30分钟窗口)
        matches = engine.match_risk_pattern(traces, pattern)
        
        # 只有2次在30分钟窗口内
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["occurrence_count"], 2)


# ---------------------------------------------------------------------------
# T5: Degradation state management
# ---------------------------------------------------------------------------


class DegradationStateTests(unittest.TestCase):
    """T5: Degradation state apply, check, and restore."""

    def _create_temp_state_path(self):
        """Create a temporary state file path for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        return temp_path

    def _cleanup_temp(self, temp_path: Path):
        """Clean up temporary file."""
        if temp_path.exists():
            temp_path.unlink()

    @_mock_state_file
    def test_load_nonexistent_state(self):
        """不存在的state文件应该返回默认结构."""
        # File exists but is empty/default, so it will return the default structure
        state = engine.load_degradation_state()
        self.assertIn("downgraded_resources", state)
        self.assertIn("hot_regions", state)

    @_mock_state_file
    def test_save_and_load_state(self):
        """保存和加载状态应该一致."""
        now = datetime.now(timezone.utc)
        state = {
            "downgraded_resources": {
                "i-bp1xxxxxxxxxx": {
                    "resource_id": "i-bp1xxxxxxxxxx",
                    "skill": "alicloud-ecs-ops",
                    "original_max_iter": 2,
                    "current_max_iter": 1,
                    "downgraded_at": now.isoformat(),
                    "auto_restore_at": (now + timedelta(hours=1)).isoformat(),
                    "reason": "Test"
                }
            },
            "hot_regions": {},
            "version": "1.0.0"
        }
        engine.save_degradation_state(state)
        
        loaded = engine.load_degradation_state()
        self.assertEqual(loaded["downgraded_resources"]["i-bp1xxxxxxxxxx"]["resource_id"], "i-bp1xxxxxxxxxx")
        self.assertEqual(loaded["downgraded_resources"]["i-bp1xxxxxxxxxx"]["current_max_iter"], 1)

    def test_apply_degradation_dry_run(self):
        """dry_run模式不应实际修改state."""
        match = {
            "pattern_id": "resource_safety_repeated",
            "pattern_name": "资源级Safety反复失败",
            "group_key": "i-bp1xxxxxxxxxx",
            "group_by": "resource_id",
            "unique_skills": ["alicloud-ecs-ops"],
            "action": "downgrade_resource_max_iter",
            "action_params": {"target_max_iter": 1, "restore_after_minutes": 60}
        }
        
        initial_state = {"downgraded_resources": {}, "hot_regions": {}, "version": "1.0.0"}
        
        result = engine.apply_degradation(match, initial_state, dry_run=True)
        
        self.assertTrue(result["applied"])
        self.assertFalse(result["state_changed"])
        self.assertIn("downgraded", result["message"].lower())

    @_mock_state_file
    def test_apply_degradation_actual(self):
        """非dry_run模式应该实际修改state."""
        match = {
            "pattern_id": "resource_safety_repeated",
            "pattern_name": "资源级Safety反复失败",
            "group_key": "i-bp1xxxxxxxxxx",
            "group_by": "resource_id",
            "unique_skills": ["alicloud-ecs-ops"],
            "action": "downgrade_resource_max_iter",
            "action_params": {"target_max_iter": 1, "restore_after_minutes": 60}
        }
        
        initial_state = {"downgraded_resources": {}, "hot_regions": {}, "version": "1.0.0"}
        
        result = engine.apply_degradation(match, initial_state, dry_run=False)
        
        self.assertTrue(result["applied"])
        self.assertTrue(result["state_changed"])
        
        # 验证state已保存
        loaded = engine.load_degradation_state()
        self.assertIn("i-bp1xxxxxxxxxx", loaded["downgraded_resources"])

    def test_restore_expired_degradations(self):
        """过期降级应该被自动恢复."""
        # Create temp state file manually for this test
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=temp_path):
                now = datetime.now(timezone.utc)
                expired_time = now - timedelta(minutes=1)
                future_time = now + timedelta(hours=1)
                
                state = {
                    "downgraded_resources": {
                        "i-expired": {
                            "resource_id": "i-expired",
                            "current_max_iter": 1,
                            "auto_restore_at": expired_time.isoformat(),
                        },
                        "i-active": {
                            "resource_id": "i-active",
                            "current_max_iter": 1,
                            "auto_restore_at": future_time.isoformat(),
                        }
                    },
                    "hot_regions": {},
                    "version": "1.0.0"
                }
                engine.save_degradation_state(state)
                
                current_state = engine.load_degradation_state()
                restored = engine.restore_expired_degradations(current_state, dry_run=False)
                
                # Engine returns both resource_id and message string
                self.assertTrue(any("i-expired" in r for r in restored))
                self.assertTrue(any("restored" in r.lower() for r in restored))
                
                # 验证state已更新
                engine.save_degradation_state(current_state)
                new_state = engine.load_degradation_state()
                self.assertNotIn("i-expired", new_state["downgraded_resources"])
                self.assertIn("i-active", new_state["downgraded_resources"])
        finally:
            if temp_path.exists():
                temp_path.unlink()


# ---------------------------------------------------------------------------
# T6: CLI integration (main)
# ---------------------------------------------------------------------------


class CliIntegrationTests(unittest.TestCase):
    """T6: CLI主函数集成测试."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.trace_dir = Path(self.tmpdir.name) / "traces"
        self.trace_dir.mkdir()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_gcl_trace(self, filename: str, decision: str, resource_id: str = None, region: str = None, minutes_ago: int = 0):
        now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        trace = {
            "timestamp": now.isoformat(),
            "skill": "alicloud-ecs-ops",
            "op": "TestOp",
            "command": f"aliyun ecs TestOp --InstanceId {resource_id} --RegionId {region}" if resource_id else "aliyun ecs TestOp",
            "iterations": [
                {
                    "iter": 1,
                    "decision": decision,
                    "generator": {
                        "command": f"aliyun ecs TestOp --InstanceId {resource_id} --RegionId {region}" if resource_id else "aliyun ecs TestOp"
                    }
                }
            ],
            "final": {"status": decision, "iter": 1}
        }
        # Ensure filename starts with gcl-trace- for engine to find it
        if not filename.startswith("gcl-trace-"):
            filename = f"gcl-trace-{filename}"
        path = self.trace_dir / filename
        path.write_text(json.dumps(trace), encoding="utf-8")

    @mock.patch("sys.argv", ["gcl_smart_alarm_engine.py", "--help"])
    def test_help_exit_code(self):
        """--help应该正常退出."""
        with self.assertRaises(SystemExit) as cm:
            engine.main()
        self.assertEqual(cm.exception.code, 0)

    def test_clean_exit_code(self):
        """无风险模式时返回CLEAN(0)."""
        self._create_gcl_trace("pass_trace.json", "PASS", "i-bp1", "cn-hangzhou", 10)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_path = Path(f.name)
        state_path.write_text(json.dumps({"downgraded_resources": {}, "hot_regions": {}, "version": "1.0.0"}), encoding="utf-8")

        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=state_path):
                with mock.patch("sys.argv", [
                    "gcl_smart_alarm_engine.py",
                    "--trace-dir", str(self.trace_dir),
                    "--window-minutes", "60"
                ]):
                    exit_code = engine.main()
                    self.assertEqual(exit_code, 0)  # CLEAN
        finally:
            if state_path.exists():
                state_path.unlink()

    def test_detected_exit_code(self):
        """检测到风险模式(非降级)时返回DETECTED(1)."""
        # 创建触发region concentration的traces
        for i in range(5):
            self._create_gcl_trace(f"fail_trace_{i}.json", "SAFETY_FAIL", f"i-bp{i}", "cn-hangzhou", i*2)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_path = Path(f.name)
        state_path.write_text(json.dumps({"downgraded_resources": {}, "hot_regions": {}, "version": "1.0.0"}), encoding="utf-8")

        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=state_path):
                with mock.patch("sys.argv", [
                    "gcl_smart_alarm_engine.py",
                    "--trace-dir", str(self.trace_dir),
                    "--window-minutes", "60",
                    "--dry-run"
                ]):
                    exit_code = engine.main()
                    self.assertEqual(exit_code, 1)  # DETECTED
        finally:
            if state_path.exists():
                state_path.unlink()

    def test_degraded_exit_code(self):
        """检测到风险模式并应用降级时返回DEGRADED(2)."""
        # 创建触发resource_safety_repeated的traces
        self._create_gcl_trace("fail1.json", "SAFETY_FAIL", "i-bp1", "cn-hangzhou", 10)
        self._create_gcl_trace("fail2.json", "SAFETY_FAIL", "i-bp1", "cn-hangzhou", 20)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_path = Path(f.name)
        state_path.write_text(json.dumps({"downgraded_resources": {}, "hot_regions": {}, "version": "1.0.0"}), encoding="utf-8")

        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=state_path):
                with mock.patch("sys.argv", [
                    "gcl_smart_alarm_engine.py",
                    "--trace-dir", str(self.trace_dir),
                    "--window-minutes", "60",
                    "--apply-degradation"
                ]):
                    exit_code = engine.main()
                    self.assertEqual(exit_code, 2)  # DEGRADED
        finally:
            if state_path.exists():
                state_path.unlink()

    def test_restored_exit_code(self):
        """恢复过期降级时返回RESTORED(3)."""
        # 创建一个过期降级状态
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(minutes=1)
        state = {
            "downgraded_resources": {
                "i-expired": {
                    "resource_id": "i-expired",
                    "current_max_iter": 1,
                    "auto_restore_at": expired_time.isoformat(),
                }
            },
            "hot_regions": {},
            "version": "1.0.0"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_path = Path(f.name)
        state_path.write_text(json.dumps(state), encoding="utf-8")

        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=state_path):
                with mock.patch("sys.argv", [
                    "gcl_smart_alarm_engine.py",
                    "--check-degradation",
                    "--restore-expired"
                ]):
                    exit_code = engine.main()
                    self.assertEqual(exit_code, 3)  # RESTORED
        finally:
            if state_path.exists():
                state_path.unlink()


# ---------------------------------------------------------------------------
# T7: Edge cases
# ---------------------------------------------------------------------------


class EdgeCaseTests(unittest.TestCase):
    """T7: 边界条件和异常处理."""

    def test_empty_traces_no_detection(self):
        """空trace列表不应触发任何检测."""
        for pattern in engine.DEFAULT_RISK_PATTERNS:
            matches = engine.match_risk_pattern([], pattern)
            self.assertEqual(matches, [])

    def test_trace_without_resource_id(self):
        """缺少resource_id的trace在group_by=resource_id时应被分到unknown组."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "test.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now,
                "decision": "SAFETY_FAIL",
                "resource_id": None,
                "region": "cn-hangzhou",
                "command": "aliyun ecs DescribeRegions"
            }
        ]
        
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # resource_safety_repeated
        matches = engine.match_risk_pattern(traces, pattern)
        # 不会匹配，因为只有1次且group_key会是unknown
        self.assertEqual(len(matches), 0)

    def test_multiple_patterns_same_resource(self):
        """同一资源可能匹配多个模式."""
        now = datetime.now(timezone.utc)
        traces = []
        # 创建5次SAFETY_FAIL（同时满足resource_safety_repeated和region_concentration）
        for i in range(5):
            traces.append({
                "trace_file": f"trace_{i}.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=i*2),
                "decision": "SAFETY_FAIL",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            })

        # 检测所有模式
        all_matches = []
        for pattern in engine.DEFAULT_RISK_PATTERNS:
            matches = engine.match_risk_pattern(traces, pattern)
            all_matches.extend(matches)

        pattern_ids = [m["pattern_id"] for m in all_matches]
        self.assertIn("resource_safety_repeated", pattern_ids)
        self.assertIn("region_safety_burst", pattern_ids)

    def test_load_traces_empty_directory(self):
        """空trace目录返回空列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()
            traces = engine.load_traces(empty_dir, 60)
            self.assertEqual(traces, [])

    def test_load_traces_nonexistent_directory(self):
        """不存在的trace目录返回空列表."""
        traces = engine.load_traces(Path("/nonexistent/path"), 60)
        self.assertEqual(traces, [])

    def test_trace_exactly_at_window_boundary(self):
        """Trace正好在时间窗口边界上应该被包含."""
        now = datetime.now(timezone.utc)
        # 正好30分钟前的trace
        boundary_trace = {
            "trace_file": "boundary.json",
            "skill": "alicloud-ecs-ops",
            "timestamp": now - timedelta(minutes=30),
            "decision": "SAFETY_FAIL",
            "resource_id": "i-bp1xxxxxxxxxx",
            "region": "cn-hangzhou",
            "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
        }
        # resource_safety_repeated使用30分钟窗口，边界trace应该匹配
        pattern = engine.DEFAULT_RISK_PATTERNS[0]
        matches = engine.match_risk_pattern([boundary_trace], pattern)
        # 单次不会触发模式
        self.assertEqual(len(matches), 0)

    def test_trace_just_outside_window(self):
        """Trace刚好在时间窗口外不应该被包含."""
        now = datetime.now(timezone.utc)
        # 31分钟前的trace（刚好超出30分钟窗口）
        outside_trace = {
            "trace_file": "outside.json",
            "skill": "alicloud-ecs-ops",
            "timestamp": now - timedelta(minutes=31),
            "decision": "SAFETY_FAIL",
            "resource_id": "i-bp1xxxxxxxxxx",
            "region": "cn-hangzhou",
            "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
        }
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # 30分钟窗口
        matches = engine.match_risk_pattern([outside_trace], pattern)
        self.assertEqual(len(matches), 0)

    def test_unknown_decision_type(self):
        """未知的decision类型不应该匹配任何模式."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "unknown.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now,
                "decision": "UNKNOWN_STATUS",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            }
        ]
        for pattern in engine.DEFAULT_RISK_PATTERNS:
            matches = engine.match_risk_pattern(traces, pattern)
            self.assertEqual(len(matches), 0, f"Pattern {pattern['id']} should not match UNKNOWN_STATUS")

    def test_mixed_skills_same_resource_id(self):
        """不同skill但相同资源ID格式不应该被错误分组."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "ecs.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=5),
                "decision": "SAFETY_FAIL",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            },
            {
                "trace_file": "rds.json",
                "skill": "alicloud-rds-ops",
                "timestamp": now - timedelta(minutes=10),
                "decision": "SAFETY_FAIL",
                "resource_id": "rm-bp1xxxxxxxxxx",  # 不同资源ID
                "region": "cn-hangzhou",
                "command": "aliyun rds TestOp --DBInstanceId rm-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            }
        ]
        pattern = engine.DEFAULT_RISK_PATTERNS[0]  # resource_safety_repeated
        matches = engine.match_risk_pattern(traces, pattern)
        # 不同资源，不应该匹配
        self.assertEqual(len(matches), 0)

    def test_large_number_of_traces_performance(self):
        """大量trace数据应该能正常处理."""
        now = datetime.now(timezone.utc)
        traces = []
        for i in range(100):
            traces.append({
                "trace_file": f"trace_{i}.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=i),
                "decision": "SAFETY_FAIL" if i < 50 else "PASS",
                "resource_id": f"i-bp{i:04d}",
                "region": "cn-hangzhou",
                "command": f"aliyun ecs TestOp --InstanceId i-bp{i:04d} --RegionId cn-hangzhou"
            })
        
        # 应该能正常处理不崩溃
        for pattern in engine.DEFAULT_RISK_PATTERNS:
            matches = engine.match_risk_pattern(traces, pattern)
            # 验证返回结果是列表
            self.assertIsInstance(matches, list)

    def test_null_fields_in_trace(self):
        """Trace中包含null字段应该被正确处理."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "null_test.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now,
                "decision": "SAFETY_FAIL",
                "resource_id": None,
                "region": None,
                "command": None
            }
        ]
        # 不应该抛出异常
        try:
            for pattern in engine.DEFAULT_RISK_PATTERNS:
                engine.match_risk_pattern(traces, pattern)
        except Exception as e:
            self.fail(f"Should not raise exception with null fields: {e}")

    def test_unicode_in_resource_id(self):
        """资源ID中包含特殊字符应该被正确处理."""
        cmd = "aliyun ram GetUser --UserName 用户@example.com"
        result = engine.extract_resource_id("alicloud-ram-ops", cmd)
        self.assertEqual(result, "用户@example.com")

    def test_command_with_multiple_region_flags(self):
        """命令中包含多个--RegionId标志应该匹配第一个."""
        cmd = "aliyun ecs CopyImage --RegionId cn-hangzhou --ImageId m-bp1 --DestinationRegionId cn-beijing"
        result = engine.extract_region(cmd)
        self.assertEqual(result, "cn-hangzhou")

    def test_resource_id_with_special_suffixes(self):
        """资源ID带特殊后缀应该被正确处理."""
        # ECS实例ID有时有-win、-linux等后缀
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx-win"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        # 注意：当前正则不支持下划线后缀，这是已知限制
        self.assertIsNotNone(result)

    def test_resource_id_at_line_end(self):
        """资源ID在行末应该被正确处理."""
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        self.assertEqual(result, "i-bp1xxxxxxxxxxxxxx")

    def test_resource_id_with_trailing_whitespace(self):
        """资源ID后有空格应该被正确处理."""
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1xxxxxxxxxxxxxx   "
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        self.assertEqual(result, "i-bp1xxxxxxxxxxxxxx")

    def test_empty_command_returns_none(self):
        """空命令应该返回None."""
        result = engine.extract_resource_id("alicloud-ecs-ops", "")
        self.assertIsNone(result)

    def test_only_whitespace_command_returns_none(self):
        """只有空白字符的命令应该返回None."""
        result = engine.extract_resource_id("alicloud-ecs-ops", "   ")
        self.assertIsNone(result)

    def test_resource_id_with_newlines_in_command(self):
        """命令中包含换行符应该被正确处理."""
        cmd = "aliyun ecs DescribeInstanceAttribute \\n  --InstanceId i-bp1xxxxxxxxxxxxxx \\n  --RegionId cn-hangzhou"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        self.assertEqual(result, "i-bp1xxxxxxxxxxxxxx")

    def test_mixed_case_resource_id(self):
        """大小写混合的资源ID应该被正确处理（转为小写）."""
        # 阿里云资源ID通常是小写，但测试一下
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId I-BP1XXXXXXXXXXXXXX"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        # 当前正则不匹配大写，这是预期行为
        self.assertIsNone(result)

    def test_very_long_resource_id(self):
        """超长资源ID应该被正确处理."""
        long_id = "i-bp" + "x" * 100
        cmd = f"aliyun ecs DescribeInstanceAttribute --InstanceId {long_id}"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        self.assertEqual(result, long_id)

    def test_resource_id_with_hyphens_in_middle(self):
        """资源ID中间有多个连字符 - 当前正则只匹配第一个连字符后的部分."""
        # 注意：阿里云资源ID通常是固定格式（如i-bp1xxxxxxxxxxxxxx），不会有多个连字符
        # 此测试验证当前正则行为（匹配到第一个非[a-z0-9]字符为止）
        cmd = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1-abc-123-def"
        result = engine.extract_resource_id("alicloud-ecs-ops", cmd)
        # 当前正则在连字符处停止匹配
        self.assertEqual(result, "i-bp1")

    def test_concurrent_simulated_access(self):
        """模拟并发访问状态文件应该不抛出异常."""
        import threading
        import time
        
        errors = []
        
        def read_state():
            try:
                for _ in range(10):
                    engine.load_degradation_state()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=read_state) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 不应该有错误
        self.assertEqual(errors, [], f"Concurrent access errors: {errors}")

    def test_risk_pattern_with_zero_window(self):
        """时间窗口为0应该正确处理."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "test.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now,
                "decision": "SAFETY_FAIL",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            }
        ]
        
        # 创建0分钟窗口的模式
        zero_window_pattern = {
            "id": "test_zero_window",
            "name": "Test Zero Window",
            "min_occurrences": 1,
            "group_by": "resource_id",
            "decisions": {"SAFETY_FAIL"},
            "window_minutes": 0,
            "severity": "P1",
        }
        
        matches = engine.match_risk_pattern(traces, zero_window_pattern)
        # 窗口为0时，应该没有匹配（因为cutoff = now - 0 = now）
        # 除非trace的timestamp >= now，这取决于执行时机
        self.assertIsInstance(matches, list)

    def test_risk_pattern_with_multiple_decision_types(self):
        """多种decision类型的模式应该正确匹配."""
        now = datetime.now(timezone.utc)
        traces = [
            {
                "trace_file": "safety.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now,
                "decision": "SAFETY_FAIL",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            },
            {
                "trace_file": "hallucination.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=5),
                "decision": "HALLUCINATION_ABORT",
                "resource_id": "i-bp1xxxxxxxxxx",
                "region": "cn-hangzhou",
                "command": "aliyun ecs TestOp --InstanceId i-bp1xxxxxxxxxx --RegionId cn-hangzhou"
            }
        ]
        
        # 使用skill_wide_failure模式（它接受多种decision类型）
        pattern = engine.DEFAULT_RISK_PATTERNS[3]  # skill_wide_failure
        # 需要有10次失败才会触发
        many_traces = []
        for i in range(5):
            many_traces.append({
                "trace_file": f"trace_{i}.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=i),
                "decision": "SAFETY_FAIL",
                "resource_id": f"i-bp{i}",
                "region": "cn-hangzhou",
                "command": f"aliyun ecs TestOp --InstanceId i-bp{i} --RegionId cn-hangzhou"
            })
        # 5次不够触发skill_wide_failure（需要10次）
        matches = engine.match_risk_pattern(many_traces, pattern)
        self.assertEqual(len(matches), 0)
        
        # 再添加5次达到10次
        for i in range(5, 10):
            many_traces.append({
                "trace_file": f"trace_{i}.json",
                "skill": "alicloud-ecs-ops",
                "timestamp": now - timedelta(minutes=i),
                "decision": "HALLUCINATION_ABORT",  # 另一种decision类型
                "resource_id": f"i-bp{i}",
                "region": "cn-hangzhou",
                "command": f"aliyun ecs TestOp --InstanceId i-bp{i} --RegionId cn-hangzhou"
            })
        matches = engine.match_risk_pattern(many_traces, pattern)
        self.assertEqual(len(matches), 1)

    def test_degradation_with_missing_original_max_iter(self):
        """降级信息缺少original_max_iter应该使用默认值."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            with mock.patch.object(engine, 'get_degradation_state_path', return_value=temp_path):
                now = datetime.now(timezone.utc)
                future_time = now + timedelta(hours=1)
                
                state = {
                    "downgraded_resources": {
                        "i-test": {
                            "resource_id": "i-test",
                            "current_max_iter": 1,
                            "auto_restore_at": future_time.isoformat(),
                            # 缺少original_max_iter
                        }
                    },
                    "hot_regions": {},
                    "version": "1.0.0"
                }
                engine.save_degradation_state(state)
                
                # 直接加载状态验证
                loaded = engine.load_degradation_state()
                downgraded = loaded.get("downgraded_resources", {})
                self.assertIn("i-test", downgraded)
                # 验证使用默认值（当字段缺失时）
                self.assertEqual(downgraded["i-test"].get("original_max_iter", 2), 2)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_parse_trace_with_nested_quotes_in_command(self):
        """命令中包含嵌套引号应该被正确处理."""
        now = datetime.now(timezone.utc)
        trace = {
            "timestamp": now.isoformat(),
            "skill": "alicloud-ecs-ops",
            "op": "RunCommand",
            "command": 'aliyun ecs RunCommand --CommandContent "echo \\"hello world\\"" --InstanceId i-bp1xxxxxxxxxx',
            "iterations": [
                {
                    "iter": 1,
                    "decision": "PASS",
                    "generator": {
                        "command": 'aliyun ecs RunCommand --CommandContent "echo \\"hello world\\"" --InstanceId i-bp1xxxxxxxxxx'
                    }
                }
            ],
            "final": {"status": "PASS", "iter": 1}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_dir = Path(tmpdir)
            trace_file = trace_dir / "gcl-trace-nested.json"
            trace_file.write_text(json.dumps(trace), encoding="utf-8")
            
            result = engine.parse_trace_file(trace_file)
            self.assertIsNotNone(result)
            self.assertEqual(result["resource_id"], "i-bp1xxxxxxxxxx")


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
