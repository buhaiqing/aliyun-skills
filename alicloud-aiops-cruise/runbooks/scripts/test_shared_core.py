#!/usr/bin/env python3
"""
_shared.py 核心功能单元测试套件

测试范围:
- F-001: subprocess 超时保护
- F-003: Semaphore 非阻塞获取
- F-004: incident-schema 转换器

运行方式:
    python3 test_shared_core.py -v
"""

import sys
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

# 添加脚本目录到路径
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import _shared


class TestSubprocessTimeout(unittest.TestCase):
    """F-001: subprocess.run 超时保护测试"""

    def test_gate_has_timeout(self):
        """gate() 函数中的 subprocess.run 必须有 timeout 参数"""
        import inspect
        source = inspect.getsource(_shared.gate)
        self.assertIn('timeout=', source,
                     "gate() function missing timeout parameter in subprocess.run")

    def test_all_subprocess_calls_have_timeout(self):
        """所有 subprocess.run 调用都应该有 timeout 参数"""
        import inspect
        import re
        
        source = inspect.getsource(_shared)
        pattern = r'subprocess\.run\([^)]+\)'
        matches = re.findall(pattern, source, re.DOTALL)
        
        calls_with_timeout = sum(1 for m in matches if 'timeout=' in m)
        total_calls = len(matches)
        
        self.assertEqual(calls_with_timeout, total_calls,
                        f"{total_calls - calls_with_timeout} subprocess.run calls missing timeout")


class TestSemaphoreNonBlocking(unittest.TestCase):
    """F-003: Semaphore 非阻塞获取测试"""

    def test_q_uses_nonblocking_acquire(self):
        """q() 函数应该使用 acquire(timeout=...) 而非阻塞获取"""
        import inspect
        source = inspect.getsource(_shared.q)
        
        self.assertIn('acquire(timeout=', source,
                     "q() should use non-blocking acquire with timeout")
        self.assertIn('semaphore timeout', source.lower(),
                     "q() should warn on semaphore timeout")

    def test_semaphore_timeout_value(self):
        """Semaphore 超时值应该与命令 timeout 一致"""
        import inspect
        source = inspect.getsource(_shared.q)
        
        # 检查是否使用了 timeout 参数
        self.assertRegex(source, r'acquire\(timeout=\w+\)',
                        "Semaphore acquire should use dynamic timeout value")


class TestIncidentSchemaConverter(unittest.TestCase):
    """F-004: incident-schema 转换器测试"""

    def setUp(self):
        """准备测试数据"""
        self.finding_critical = {
            'r': 'rm-test-001',
            't': 'RDS',
            'm': 'DiskUsage',
            'v': 95.5,
            'th': '75/90'
        }
        
        self.finding_warning = {
            'r': 'i-test-002',
            't': 'ECS',
            'm': 'CPUUtilization',
            'v': 78.0,
            'th': '70/85'
        }
        
        self.common_params = {
            'customer': 'test-customer',
            'run_id': 'test-run-id',
            'region': 'cn-hangzhou',
            'runbook_id': '01-daily-health-check',
            'runbook_version': '1.0.0',
            'scenario': 'daily_check',
            'report_path': '/tmp/test.json'
        }

    def test_timestamp_format_iso8601(self):
        """timestamp 应该是标准 ISO8601 格式(无微秒)"""
        incident = _shared.to_incident(
            self.finding_critical, **self.common_params
        )
        
        ts = incident['timestamp']
        
        # 检查格式: YYYY-MM-DDTHH:MM:SSZ
        self.assertIn('T', ts, "timestamp should contain 'T' separator")
        self.assertTrue(ts.endswith('Z'), "timestamp should end with 'Z'")
        self.assertNotIn('.', ts, "timestamp should not have microseconds")
        
        # 验证可以解析
        try:
            datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            self.fail(f"timestamp format invalid: {ts}")

    def test_dedup_key_present_for_critical(self):
        """CRITICAL 级别 incident 必须有 dedup_key"""
        incident = _shared.to_incident(
            self.finding_critical, **self.common_params
        )
        
        self.assertEqual(incident['level'], 'CRITICAL')
        self.assertIsNotNone(incident['dedup_key'])
        self.assertGreater(len(incident['dedup_key']), 0,
                          "CRITICAL incident must have non-empty dedup_key")

    def test_dedup_key_present_for_warning(self):
        """WARNING 级别 incident 必须有 dedup_key"""
        incident = _shared.to_incident(
            self.finding_warning, **self.common_params
        )
        
        self.assertEqual(incident['level'], 'WARNING')
        self.assertIsNotNone(incident['dedup_key'])
        self.assertGreater(len(incident['dedup_key']), 0)

    def test_dedup_key_format(self):
        """dedup_key 应该符合规范格式"""
        incident = _shared.to_incident(
            self.finding_critical, **self.common_params
        )
        
        dedup_key = incident['dedup_key']
        parts = dedup_key.split(':')
        
        self.assertEqual(len(parts), 5,
                        f"dedup_key should have 5 parts: {dedup_key}")
        self.assertEqual(parts[0], 'test-customer')
        self.assertEqual(parts[1], 'RDS')
        self.assertEqual(parts[2], 'rm-test-001')
        # parts[3] 是 rule_id, parts[4] 是日期

    def test_missing_required_fields_raises_error(self):
        """缺少必填字段时应该抛出异常"""
        bad_finding = {
            'r': '',  # resource_id 为空
            't': 'RDS',
            'm': 'DiskUsage',
            'v': 95.5,
            'th': '75/90'
        }
        
        # CRITICAL/WARNING 必须有 dedup_key,如果 resource_id 为空会失败
        with self.assertRaises(ValueError):
            _shared.to_incident(bad_finding, **self.common_params)

    def test_schema_version(self):
        """incident 应该包含正确的 schema_version"""
        incident = _shared.to_incident(
            self.finding_critical, **self.common_params
        )
        
        self.assertEqual(incident['schema_version'], '1.0.0')

    def test_required_fields_present(self):
        """incident 应该包含所有必填字段"""
        incident = _shared.to_incident(
            self.finding_critical, **self.common_params
        )
        
        required_fields = [
            'incident_id', 'schema_version', 'customer', 'timestamp',
            'run_id', 'level', 'resource_type', 'resource_id', 'region',
            'rule_id', 'title', 'dedup_key', 'impact', 'suggestion', 'trace'
        ]
        
        for field in required_fields:
            self.assertIn(field, incident,
                         f"Required field '{field}' missing from incident")


class TestIdempotentUtils(unittest.TestCase):
    """lib_idempotent 工具函数测试"""

    def setUp(self):
        """导入 lib_idempotent 模块"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "lib_idempotent",
            SCRIPT_DIR / "lib_idempotent.py"
        )
        self.lib_idempotent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.lib_idempotent)

    def test_safe_append_creates_file(self):
        """safe_append 应该创建不存在的文件"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            tmp_path = f.name
        
        try:
            self.lib_idempotent.safe_append(tmp_path, "test line")
            
            with open(tmp_path, 'r') as f:
                content = f.read()
            
            self.assertIn('test line', content)
            self.assertIn('[', content)  # 应该有时间戳前缀
        finally:
            os.unlink(tmp_path)

    def test_safe_append_multiple_lines(self):
        """safe_append 应该追加多行而不覆盖"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            tmp_path = f.name
        
        try:
            self.lib_idempotent.safe_append(tmp_path, "line 1")
            self.lib_idempotent.safe_append(tmp_path, "line 2")
            self.lib_idempotent.safe_append(tmp_path, "line 3")
            
            with open(tmp_path, 'r') as f:
                lines = f.readlines()
            
            self.assertEqual(len(lines), 3)
            self.assertIn('line 1', lines[0])
            self.assertIn('line 2', lines[1])
            self.assertIn('line 3', lines[2])
        finally:
            os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
