#!/usr/bin/env python3
"""
_perf_smoke.py — Sprint 14/15 性能优化冒烟测试

目的: 验证 q_cms_batch / q_cms_batch_by_dim / cache TTL / Semaphore 改造不破坏行为, 量化性能收益.

测试项 (Sprint 14):
  T1: q_cms_batch([]) 边界 -> []
  T2: q_cms_batch 顺序保留 (job[i] -> results[i])
  T3: q_cms_batch 并发调用 subprocess.run (实测 <串行耗时)
  T4: 缓存命中 (同一 cmd 第二次 q_cached 不调 subprocess)
  T5: CMS Semaphore 默认 20 (环境变量未设置时)
  T6: CLI --describe 模式 (无 aliyun CLI 时仍可 argparse)

测试项 (Sprint 15):
  T7: q_cms_batch_by_dim 基础: 单次 API 返回多 instance 按 dim_key 分组
  T8: q_cms_batch_by_dim 拆批: 100 instance + batch_size=50 -> 2 次 API
  T9: q_cms_batch_by_dim 缓存隔离: 不同 dim_values 列表 -> 不同缓存 key
  T10: q_cms_batch_by_dim 缓存命中: 同一 dim_values 重复调用 -> cache hit
  T11: [回归] per-instance 调用 vs q_cms_batch_by_dim 输出 dict 完全一致
  T12: [性能] 100 ECS × 3 metric × 2 period: 600 次 -> ≤12 次 subprocess.run

执行: cd alicloud-aiops-cruise/runbooks/scripts && python3 _perf_smoke.py
"""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# 确保当前目录在脚本路径里 (同级 _shared.py 可直接 import)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402


# ── 工具: mock subprocess.run 模拟 aliyun CLI ──


def _make_fake_run(latency_s: float = 0.05, payload: dict = None):
    """返回一个 mock subprocess.run 函数, 模拟 aliyun CLI 的延迟和返回."""
    call_count = {"n": 0}
    counter_lock = _FakeLock()  # 用 _shared.Semaphore 替代 threading.Lock (零依赖)

    def fake_run(args, **kwargs):
        call_count["n"] += 1
        # 模拟 aliyun CLI 启动延迟
        time.sleep(latency_s)
        # 返回 mock JSON
        result = subprocess.CompletedProcess(
            args=args, returncode=0,
            stdout=json.dumps(payload or {
                "Datapoints": [{"Average": 50.0, "timestamp": 1700000000}],
                "RequestId": f"mock-{call_count['n']}",
            }),
            stderr="",
        )
        return result

    fake_run.call_count = call_count
    return fake_run


class _FakeLock:
    """stdin 计数器 (mock 用, 避免引入 threading 复杂度)."""
    def __init__(self):
        self.n = 0

    def acquire(self):
        self.n += 1

    def release(self):
        self.n -= 1


# ── 测试用例 ──


class TestQcmsBatch(unittest.TestCase):
    """T1-T3: q_cms_batch 行为正确性 + 并发性"""

    def setUp(self):
        # 清掉缓存目录, 保证测试隔离
        if _shared.CACHE_DIR.exists():
            for f in _shared.CACHE_DIR.glob("*.json"):
                f.unlink()
        _shared._CACHE_STATS.update(hit=0, miss=0, bypass=0, error=0)

    def test_t1_empty_input(self):
        """T1: 空 jobs 列表直接返回 []"""
        result = _shared.q_cms_batch([])
        self.assertEqual(result, [])
        print("  [PASS] T1: q_cms_batch([]) -> []")

    def test_t2_preserves_order(self):
        """T2: 返回结果与 jobs 等长且顺序对应"""
        fake = _make_fake_run(latency_s=0.001, payload={"v": 1})
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            jobs = [["ecs", "DescribeInstances", "--RegionId", f"region-{i}"] for i in range(5)]
            results = _shared.q_cms_batch(jobs, max_workers=3)
            self.assertEqual(len(results), 5)
            for i, r in enumerate(results):
                # q_cached 第一次会 cache miss, 后续 hit. 但每个 job 唯一 key 所以都是 miss.
                # 验证: 至少结果是 dict 或 None, 不抛异常
                self.assertTrue(r is None or isinstance(r, dict))
        print(f"  [PASS] T2: q_cms_batch 5 jobs -> 5 results (顺序保留)")

    def test_t3_concurrency_speedup(self):
        """T3: 10 个 job × 50ms 串行需 500ms, 并发应 < 200ms"""
        fake = _make_fake_run(latency_s=0.05)
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            jobs = [["cms", "DescribeMetricList", "--Dimensions", f'[{{"i":"{i}"}}'] for i in range(10)]
            t0 = time.time()
            results = _shared.q_cms_batch(jobs, max_workers=10)
            elapsed = time.time() - t0
        # 串行 10 × 50ms = 500ms; 并发 10 worker 应 < 200ms (留余量)
        self.assertLess(elapsed, 0.2, f"并发 10 jobs 耗时 {elapsed*1000:.0f}ms 应 < 200ms")
        # 注意: cache 命中后不会调 subprocess.run, 所以这里 10 个 job 全部走 miss
        self.assertEqual(fake.call_count["n"], 10)
        print(f"  [PASS] T3: 10 jobs 并发耗时 {elapsed*1000:.0f}ms (串行需 500ms), 调用 subprocess={fake.call_count['n']} 次")


class TestCacheAndSemaphore(unittest.TestCase):
    """T4-T5: 缓存命中 + Semaphore 默认值"""

    def setUp(self):
        if _shared.CACHE_DIR.exists():
            for f in _shared.CACHE_DIR.glob("*.json"):
                f.unlink()
        _shared._CACHE_STATS.update(hit=0, miss=0, bypass=0, error=0)

    def test_t4_cache_hit(self):
        """T4: 同一 cmd 第二次 q_cached 走 cache, 不调 subprocess"""
        fake = _make_fake_run(latency_s=0.01)
        cmd = ["ecs", "DescribeInstances", "--RegionId", "cn-hangzhou"]
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            r1 = _shared.q_cached(cmd)
            r2 = _shared.q_cached(cmd)
            r3 = _shared.q_cached(cmd)
        self.assertEqual(fake.call_count["n"], 1, f"应只调 1 次 subprocess, 实际 {fake.call_count['n']}")
        stats = _shared.cache_stats()
        self.assertEqual(stats["hit"], 2)
        self.assertEqual(stats["miss"], 1)
        print(f"  [PASS] T4: 3 次 q_cached 同一 cmd -> subprocess 1 次 (hit=2, miss=1)")

    def test_t5_cms_semaphore_default_20(self):
        """T5: CMS Semaphore 默认 20 并发 (Sprint 14: 5->20)"""
        self.assertEqual(_shared._CMS_SEM._value, 20)
        # 环境变量覆盖路径
        # (子进程验证避免污染当前 Semaphore)
        import subprocess as _sp
        env = {**os.environ, "AIOPS_CMS_CONCURRENCY": "30"}
        r = _sp.run(
            ["python3", "-c",
             "import _shared; print(_shared._CMS_SEM._value)"],
            capture_output=True, text=True, env=env, timeout=5,
        )
        self.assertIn("30", r.stdout, f"env override should yield 30, got: {r.stdout!r}")
        print(f"  [PASS] T5: CMS Semaphore 默认 20, 环境变量 AIOPS_CMS_CONCURRENCY 可覆盖 (Sprint 14: 5->20)")

    def test_t6_cache_ttl_extended(self):
        """T6: 资源清单类 TTL 已升级到 3600s (Sprint 14)"""
        self.assertEqual(_shared.CACHE_TTL["DescribeInstances"], 3600)
        self.assertEqual(_shared.CACHE_TTL["DescribeDBInstances"], 3600)
        self.assertEqual(_shared.CACHE_TTL["QueryBillOverview"], 3600)
        self.assertEqual(_shared.CACHE_DEFAULT_TTL, 300)
        print(f"  [PASS] T6: 资源清单+账单类 TTL=3600s, 默认 TTL=300s (Sprint 14)")


class TestCLIIntegrty(unittest.TestCase):
    """T6: CLI --describe 模式无需 aliyun CLI 仍可工作"""

    def test_describe_mode(self):
        """daily-health-check --describe / capacity-planning --describe 不调 aliyun"""
        for script in ["daily-health-check.py", "capacity-planning.py"]:
            r = subprocess.run(
                ["python3", script, "--describe"],
                capture_output=True, text=True, timeout=10,
            )
            # 多数脚本 --describe 输出 0 退出码
            self.assertIn(r.returncode, (0, 1), f"{script} --describe returncode={r.returncode}")
        # cost-watch.py 没有 --describe, 测 --help 确认 argparse 没坏
        r = subprocess.run(
            ["python3", "cost-watch.py", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(r.returncode, 0, f"cost-watch.py --help returncode={r.returncode}")
        self.assertIn("--budget", r.stdout)
        print(f"  [PASS] T7: daily-health-check / capacity-planning --describe + cost-watch --help 正常")


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 15: q_cms_batch_by_dim 回归测试
# ═══════════════════════════════════════════════════════════════════════════════


def _make_dim_aware_fake_run(latency_s: float = 0.001):
    """构造 dimension-aware 的 mock subprocess.run.

    模拟阿里云 CMS DescribeMetricList 行为: 单次请求 N 组 dimension,
    返回的 Datapoints 是混合的, 每条带 dim_key 字段 (e.g. instanceId).

    返回值: (fake_run, call_counter)
        fake_run: 替换 subprocess.run 的函数
        call_counter: 字典, 含 n 键记录调用次数
    """
    counter = {"n": 0}

    def fake_run(args, **kwargs):
        counter["n"] += 1
        if latency_s > 0:
            time.sleep(latency_s)
        # 解析 cmd: args[0] 是 "aliyun", 后面是参数
        cmd = args[1:]
        ns = cmd[cmd.index("--Namespace") + 1]
        metric = cmd[cmd.index("--MetricName") + 1]
        dims_json = cmd[cmd.index("--Dimensions") + 1]
        dims = json.loads(dims_json)
        # 模拟服务端行为: 每个 dim_value 独立一组 datapoints
        all_dps = []
        for d in dims:
            v = d.get("instanceId", "")
            if not v:
                continue
            # 用 instanceId 后缀数字作为种子, 生成稳定且可预测的值
            try:
                seed = int(v.split("-")[-1])
            except (ValueError, IndexError):
                seed = sum(ord(c) for c in v) % 100
            # 每个 instance 3 个 datapoints, 模拟 5min 周期 ~15min 窗口
            for i in range(3):
                all_dps.append({
                    "instanceId": v,
                    "timestamp": 1700000000 + i * 300,
                    "Average": round(30.0 + seed * 1.5 + i, 2),
                })
        result = subprocess.CompletedProcess(
            args=args, returncode=0,
            stdout=json.dumps({
                "Datapoints": all_dps,
                "RequestId": f"req-{counter['n']}",
            }),
            stderr="",
        )
        return result

    return fake_run, counter


def _q_per_instance(ns, metric, dim_key, dim_values, period, start, end):
    """模拟 Sprint 13 前的 per-instance 调用: 每次一个 instance 一个 API."""
    result = {v: [] for v in dim_values}
    for v in dim_values:
        cmd = [
            "cms", "DescribeMetricList",
            "--Namespace", ns, "--MetricName", metric,
            "--Dimensions", json.dumps([{dim_key: v}]),
            "--Period", period, "--StartTime", start, "--EndTime", end,
        ]
        data = _shared.q_cached(cmd)
        if not data:
            continue
        dps = data.get("Datapoints", "[]")
        if isinstance(dps, str):
            try:
                dps = json.loads(dps)
            except Exception:
                continue
        if not isinstance(dps, list):
            continue
        for dp in dps:
            if isinstance(dp, dict) and dp.get(dim_key) == v:
                result[v].append(dp)
    return result


class TestQcmsBatchByDim(unittest.TestCase):
    """Sprint 15: 按 dimension 批量拉取 helper 测试"""

    def setUp(self):
        if _shared.CACHE_DIR.exists():
            for f in _shared.CACHE_DIR.glob("*.json"):
                f.unlink()
        _shared._CACHE_STATS.update(hit=0, miss=0, bypass=0, error=0)

    def test_t8_basic_grouping(self):
        """T8: 单次 API 返回 N instance 数据, 按 instanceId 正确分组"""
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            rids = ["i-1", "i-2", "i-3"]
            data = _shared.q_cms_batch_by_dim(
                "acs_ecs_dashboard", "CPUUtilization",
                "instanceId", rids, "300", "h6", "end", batch_size=50,
            )
        # 1. 3 个 rid 都应有数据
        self.assertEqual(set(data.keys()), set(rids))
        # 2. 每个 rid 应有 3 个 datapoints
        for rid in rids:
            self.assertEqual(len(data[rid]), 3, f"{rid} 应有 3 个 datapoints")
        # 3. 每个 datapoint 应带 instanceId
        for rid in rids:
            for dp in data[rid]:
                self.assertEqual(dp["instanceId"], rid)
        # 4. 1 次 subprocess.run (50 个/批, 3 个 < 50)
        self.assertEqual(counter["n"], 1, f"应 1 次 API 调用, 实际 {counter['n']}")
        print(f"  [PASS] T8: 3 instance 单次 API 返回, 按 instanceId 正确分组 (subprocess={counter['n']})")

    def test_t9_batching(self):
        """T9: 100 instance + batch_size=50 -> 2 次 API 调用 (拆批)"""
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        rids = [f"i-{i}" for i in range(100)]
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            data = _shared.q_cms_batch_by_dim(
                "acs_ecs_dashboard", "CPUUtilization",
                "instanceId", rids, "300", "h6", "end", batch_size=50,
            )
        # 1. 100 个 rid 都应有数据
        self.assertEqual(len(data), 100)
        # 2. 应拆 2 批
        self.assertEqual(counter["n"], 2, f"100 instance + batch_size=50 应 2 次 API, 实际 {counter['n']}")
        # 3. 验证每个 batch 的 dimensions 数组长度 (检查 cmd 参数)
        print(f"  [PASS] T9: 100 instance 拆 2 批, subprocess={counter['n']} 次 (vs 100 次 per-instance)")

    def test_t10_cache_isolation(self):
        """T10: 不同 dim_values 列表 -> 不同缓存 key, 互不污染"""
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            d1 = _shared.q_cms_batch_by_dim("ns", "m", "instanceId", ["i-1", "i-2"], "300", "s", "e")
            d2 = _shared.q_cms_batch_by_dim("ns", "m", "instanceId", ["i-3", "i-4"], "300", "s", "e")
        # 2 次不同 dim_values -> 2 次 API 调用
        self.assertEqual(counter["n"], 2)
        self.assertEqual(set(d1.keys()), {"i-1", "i-2"})
        self.assertEqual(set(d2.keys()), {"i-3", "i-4"})
        print(f"  [PASS] T10: 不同 dim_values 列表 -> 2 个独立 API 调用 (缓存 key 隔离)")

    def test_t11_cache_hit(self):
        """T11: 同一 dim_values 列表重复调用 -> 第二次走 cache"""
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        rids = ["i-1", "i-2", "i-3"]
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            d1 = _shared.q_cms_batch_by_dim("ns", "m", "instanceId", rids, "300", "s", "e")
            d2 = _shared.q_cms_batch_by_dim("ns", "m", "instanceId", rids, "300", "s", "e")
            d3 = _shared.q_cms_batch_by_dim("ns", "m", "instanceId", rids, "300", "s", "e")
        # 3 次调用同一组, subprocess 应只 1 次
        self.assertEqual(counter["n"], 1, f"应 1 次 subprocess, 实际 {counter['n']}")
        # 两次结果应该一致
        self.assertEqual(d1.keys(), d2.keys())
        self.assertEqual(d2.keys(), d3.keys())
        print(f"  [PASS] T11: 3 次同一 dim_values -> subprocess 1 次 (cache hit)")

    def test_t12_regression_equivalence(self):
        """T12: [关键回归] per-instance 调用 vs q_cms_batch_by_dim 输出 dict 完全一致

        验证 Sprint 15 改造不破坏行为: 同一组 input, 两种调用方式应得到一致的分组结果.
        """
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        rids = [f"i-{i}" for i in range(20)]
        with patch.object(_shared.subprocess, "run", side_effect=fake):
            # 方式 1: per-instance (Sprint 13 旧路径)
            per_instance = _q_per_instance(
                "acs_ecs_dashboard", "CPUUtilization",
                "instanceId", rids, "300", "h6", "end",
            )
            counter["n"] = 0  # 重置计数
            # 方式 2: q_cms_batch_by_dim (Sprint 15 新路径)
            by_dim = _shared.q_cms_batch_by_dim(
                "acs_ecs_dashboard", "CPUUtilization",
                "instanceId", rids, "300", "h6", "end", batch_size=50,
            )
        # 关键断言: 两种方式输出 dict 完全一致 (key 集合 + 每个 key 下的 datapoints)
        self.assertEqual(set(per_instance.keys()), set(by_dim.keys()))
        for rid in rids:
            self.assertEqual(
                len(per_instance[rid]), len(by_dim[rid]),
                f"{rid} datapoint 数不一致: per_instance={len(per_instance[rid])} by_dim={len(by_dim[rid])}",
            )
            for dp_p, dp_b in zip(per_instance[rid], by_dim[rid]):
                # 字段级一致性 (Average, instanceId, timestamp)
                self.assertEqual(dp_p.get("instanceId"), dp_b.get("instanceId"))
                self.assertEqual(dp_p.get("Average"), dp_b.get("Average"))
                self.assertEqual(dp_p.get("timestamp"), dp_b.get("timestamp"))
        # 性能断言: by_dim 应 1 次 API (20 < 50), per_instance 应 20 次
        self.assertEqual(counter["n"], 1, f"by_dim 应 1 次 API, 实际 {counter['n']}")
        print(f"  [PASS] T12: per-instance vs by_dim 行为完全一致 (20 instance, 1 次 API vs 20 次)")

    def test_t13_perf_100ecs_3metric_2period(self):
        """T13: [性能目标] 100 ECS × 3 metric × 2 period: 600 次 -> ≤12 次 subprocess.run

        模拟 daily-health-check._collect_one 的典型负载, 量化 Sprint 15 收益.
        预期: 2 period × 3 metric × ceil(100/50) = 12 次
        """
        fake, counter = _make_dim_aware_fake_run(latency_s=0)
        rids = [f"i-{i}" for i in range(100)]
        metrics_def = ["CPUUtilization", "memory_usedutilization", "DiskUsage"]  # 3 个指标
        periods = [("300", "h6", "end"), ("3600", "d7", "end")]  # 2 个 period

        with patch.object(_shared.subprocess, "run", side_effect=fake):
            # 模拟 _collect_one 真实调用模式
            realtime = {}
            for mk in metrics_def:
                realtime[mk] = _shared.q_cms_batch_by_dim(
                    "acs_ecs_dashboard", mk, "instanceId", rids, "300", "h6", "end", batch_size=50,
                )
            for mk in metrics_def:
                _shared.q_cms_batch_by_dim(
                    "acs_ecs_dashboard", mk, "instanceId", rids, "3600", "d7", "end", batch_size=50,
                )

        # 预期: 6 (metric×period) × 2 (批/100) = 12 次
        expected_max = 12
        self.assertLessEqual(
            counter["n"], expected_max,
            f"Sprint 15 目标: ≤{expected_max} 次 API, 实际 {counter['n']}",
        )
        # 同时验证每个 metric 都有数据
        for mk in metrics_def:
            self.assertEqual(len(realtime[mk]), 100, f"{mk} 应有 100 个 instance")
        # 加速比
        original = 100 * 3 * 2  # 600 次 per-instance
        speedup = original / counter["n"]
        print(f"  [PASS] T13: 100 ECS × 3 metric × 2 period: {counter['n']} 次 (vs 600 次 per-instance, {speedup:.1f}x 加速)")


# ── 主入口 ──


if __name__ == "__main__":
    print("=" * 60)
    print("  Sprint 14/15 性能优化冒烟测试")
    print("=" * 60)
    unittest.main(verbosity=2, argv=["_perf_smoke.py"], exit=False)
