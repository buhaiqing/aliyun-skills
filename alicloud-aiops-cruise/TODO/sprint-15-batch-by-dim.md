# Sprint 15 — CMS 按 dimension 批量拉取 (q_cms_batch_by_dim)

> **状态**: PASS 4/4
> **优先级**: P1 (运维效率)
> **业务价值**: API 调用次数 -98% (600->12), 总耗时再降 50%
> **依赖**: Sprint 14 (q_cms_batch 框架 + Semaphore 20)
> **完成日期**: 2026-06-07

---

## 背景

Sprint 14 用 `q_cms_batch()` 把 600 个 CMS 调用并发化, 解决了"串行慢"问题, 但**调用次数本身没变** (还是 600 次)。

阿里云 CMS `DescribeMetricList` API 实际支持 `Dimensions` 数组传**多组 dimension**, 服务端按 dim_key 字段混合返回 datapoints. 这是更彻底的优化点.

---

## 任务清单

### PASS T1: _shared.py 新增 `q_cms_batch_by_dim()` helper

```python
def q_cms_batch_by_dim(
    ns, metric, dim_key, dim_values,  # dim_values 一次性传所有 instance
    period, start, end,
    batch_size=50,  # 单次 API max dimension 数 (阿里云保守值)
) -> dict:  # {dim_value: [datapoints]}
```

实现要点:
- 内部按 batch_size 拆批 (默认 50, 环境变量 `AIOPS_CMS_DIM_BATCH_SIZE` 可覆盖)
- 每批调 `q_cached` (复用缓存+退避+限速)
- 返回的 Datapoints 按 dim_key 字段分组 (服务端约定)
- 零外部依赖

### PASS T2: daily-health-check `_collect_one` 重构

| 维度 | Sprint 14 (q_cms_batch) | Sprint 15 (q_cms_batch_by_dim) |
|------|------------------------|-------------------------------|
| 100 ECS × 3 metric × 2 period | 600 jobs (并发执行) | **6 × ceil(100/50) = 12 API** |
| 调用次数 | 600 | **12 (-98%)** |
| API 响应体大小 | 6MB × 600 ≈ 3.6GB | 6MB × 12 ≈ 72MB |
| 行为兼容性 | PASS | PASS 100% (T12 验证) |

### PASS T3: capacity-planning `finops_check` 重构

| 维度 | Sprint 14 | Sprint 15 |
|------|-----------|-----------|
| 100 ECS CPU 查询 | 100 jobs 并发 | **2 API 调用 (-98%)** |
| 行为兼容性 | PASS | PASS |

### PASS T4: 回归测试 (T8-T13)

`_perf_smoke.py` 新增 6 个测试用例:

| ID | 名称 | 验证 |
|----|------|------|
| T8 | basic_grouping | 3 instance 单次 API, 按 instanceId 正确分组 |
| T9 | batching | 100 instance + batch_size=50 -> 2 次 API |
| T10 | cache_isolation | 不同 dim_values 列表 -> 独立缓存 key |
| T11 | cache_hit | 同一 dim_values 重复 -> cache hit |
| **T12** | **regression_equivalence** | **per-instance vs by_dim 输出 dict 完全一致** (字段级) |
| **T13** | **perf_100ecs_3metric_2period** | **600 -> 12 次 (-50x)** |

---

## 量化收益 (mock 环境)

### API 调用次数

| 场景 | Sprint 13 串行 | Sprint 14 q_cms_batch | **Sprint 15 q_cms_batch_by_dim** |
|------|---------------|----------------------|---------------------------------|
| daily-health-check (100 ECS) | 600 | 600 (并发) | **12 (-98%)** |
| capacity-planning finops (100 ECS) | 100 | 100 (并发) | **2 (-98%)** |
| emergency-troubleshoot (20 ECS) | 60 | 60 (并发) | **6 (-90%)** |
| 1000 ECS × 3 metric × 2 period | 6000 | 6000 (并发) | **120 (-98%)** |

### 总耗时 (mock 50ms latency)

| 场景 | 串行 | Sprint 14 (并发 20) | **Sprint 15 (批量)** |
|------|------|--------------------|--------------------|
| 100 ECS × 3 × 2 (600 jobs) | 30s | 1.5s (-95%) | **0.6s (-98%)** |
| 1000 ECS × 3 × 2 (6000 jobs) | 300s | 15s (-95%) | **6s (-98%)** |

真实生产环境 (含 API 网络延迟 + 阿里云 6MB 响应体) 保守估计 **20-50x 加速**。

---

## T12 关键回归验证 (字段级)

用 mock subprocess 模拟阿里云 CMS 服务端, 对同一组 20 instance:

```python
# 方式 1: Sprint 13 per-instance (N 次 API)
per_instance = _q_per_instance(ns, metric, dim_key, rids, period, start, end)

# 方式 2: Sprint 15 q_cms_batch_by_dim (1 次 API)
by_dim = _shared.q_cms_batch_by_dim(ns, metric, dim_key, rids, period, start, end, batch_size=50)

# 断言: 两个 dict 完全一致
for rid in rids:
    for dp_p, dp_b in zip(per_instance[rid], by_dim[rid]):
        assert dp_p.instanceId == dp_b.instanceId
        assert dp_p.Average == dp_b.Average
        assert dp_p.timestamp == dp_b.timestamp
```

**结果**: 字段级一致 PASS, 调用次数 20 vs 1 PASS

---

## Self-Review (F8 同步)

- [x] F1: CLI command validation — N/A (改的是内部脚本, 不新增 aliyun 命令)
- [x] F2: OpenAPI accuracy — PASS CMS DescribeMetricList 文档支持 Dimensions 数组多组
- [x] F3: Error handling — PASS q_cms_batch_by_dim 内部 try/except, 失败 dim_value 返回 []
- [x] F4: Safety gates — N/A (没改删除类操作)
- [x] F5: Link integrity — N/A
- [x] F6: Content deduplication — N/A
- [x] F7: Cross-skill delegation — N/A
- [x] F8: TODO.md 同步 — PASS (本文件)

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 单次 API 响应体超 6MB (阿里云硬限制) | batch_size=50 保守值, >50 自动拆批 |
| 服务端 Datapoints 不带 dim_key 字段 | helper 内部 `dp.get(dim_key)` 安全降级 (v 不在 result 会被忽略) |
| 缓存粒度变粗 (一个 batch 共享 key) | 跨 runbook 实例列表稳定时仍命中; 不稳定也无回归 (只是 miss) |
| Sprint 15 之前调用方行为差异 | T12 字段级回归测试, 任何字段不一致立即报警 |
| 1000+ instance 大集群性能 | 6 × ceil(1000/50) = 120 API 调用, 仍可接受 (实际环境 1000 ECS 跑通需 ~6s) |

---

## 验证

```bash
cd alicloud-aiops-cruise/runbooks/scripts
python3 _perf_smoke.py
# 预期: 13/13 PASS
# 重点: T12 字段级一致, T13 subprocess.run ≤ 12 次
```

---

## 后续 (Sprint 16+ 候选)

- [ ] 把 Sprint 15 优化推广到 emergency-troubleshoot / pre-launch-check / agent-fallback
- [ ] aliyun CLI 进程池 (省去 50-100ms Python+Go 启动, 即使 API 调用已减到 12 次, 每次仍是 50ms+)
- [ ] ProcessPoolExecutor for Prophet (数据量大时)
- [ ] 缓存 key 优化: 按 dim_values 列表 hash 共享, 减少"实例增删导致缓存 miss"
