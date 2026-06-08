---
name: cache-strategy
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# 结果缓存策略 (Sprint 8 落地规范)

> **目的**：减少 4 个 runbook 间的重复 API 调用，降低 CMS 限速压力，缩短重复巡检耗时。**纯本地文件缓存，零外部依赖**。
>
> **实现位置**：[`runbooks/scripts/_shared.py`](../runbooks/scripts/_shared.py) -> `q_cached()` 函数
>
> **调研依据**：[`TODO/sprint-08-result-cache.md`](../TODO/sprint-08-result-cache.md) §二 策略对比

---

## 一、缓存架构

```
┌─────────────────────────────────────────┐
│         runbooks/scripts/*.py            │
│  daily / emergency / capacity / prelaunch│
└────────────┬────────────────────────────┘
             │ q_cached(["ecs", "DescribeInstances", ...])
             ▼
┌─────────────────────────────────────────┐
│   _shared.py: q_cached()                │
│   1. 计算 key = md5(stable_json(cmd))   │
│   2. 查 audit-results/cache/<key>.json   │
│   3. 命中: 直接返回, 不调用 aliyun      │
│   4. 未命中: q() 拿结果 + 写缓存        │
└────────────┬────────────────────────────┘
             │
             ▼
   audit-results/cache/  (跨进程共享)
```

**关键设计**：
- **跨进程共享**：4 个 runbook 都读同一目录，第二次跑直接吃缓存
- **稳定键**：`md5(sort_keys=True(stable_json(cmd)))`，参数顺序不影响命中
- **响应校验**：写缓存前检查 `Code` 字段，非 200 不缓存（防止污染）
- **Jitter 防雪崩**：TTL 检查加 `random.uniform(0, 0.1*ttl)` 偏移

---

## 二、TTL 分级表

| API | TTL | 理由 |
|-----|-----|------|
| **资源清单类** (Describe*) | 300s (5min) | CRUD 频率低 |
| **集群信息** (DescribeClusters / DescribeClusterNodes / DescribeClusterNodePools) | 600s (10min) | 节点列表变化慢 |
| **VPC / VSwitch** | 600s | 网络拓扑极少变 |
| **健康检查** (DescribeHealthStatus) | 120s | 频繁但短期稳定 |
| **CMS 指标** (DescribeMetricList) | 600s (10min) | CMS 1min 采集周期，10min 业务可接受 (跨 runbook 复用) |
| **历史回溯** (backtrack_cms) | 3600s (1h) | 历史数据点不变 |
| **安全/审计** (LookupEvents) | 30s | 要求近实时 |
| **未知 API** | 60s (默认) | 保守策略 |

> **完整表**：`_shared.py` -> `CACHE_TTL` 字典

---

## 三、缓存目录结构

```
audit-results/cache/
├── 3f4a5b6c7d8e9f01.json   # 例: 资源清单缓存
│   ├── 第 1 行: {"key":"3f4a5b6c7d8e9f01","product":"ecs","api":"DescribeInstances","cached_at":"...","ttl":300}
│   └── 第 2 行: { ... 实际 JSON 响应 ... }
├── 9a8b7c6d5e4f3a2b.json   # 例: CMS 指标
└── ...
```

**两行 JSONL 格式**：
- 第 1 行是 metadata（缓存管理用：API 名、TTL、缓存时间）
- 第 2 行是实际响应数据（紧凑存储）

**为什么不用 pickle/yaml？** JSON 可读、可审计、易调试；占空间略大但巡检场景 < 1MB/文件可接受。

---

## 四、使用约定

### 4.1 推荐用法（默认）

```python
from _shared import q_cached

# 直接替换 q() 调用
result = q_cached(["ecs", "DescribeInstances", "--RegionId", region])
```

### 4.2 强制刷新

```python
# 紧急情况下绕过缓存（如怀疑数据过期）
result = q_cached(["ecs", "DescribeInstances", "--RegionId", region], no_cache=True)
```

### 4.3 全局禁用（CI / 调试）

```bash
# 一次性禁用本次运行所有缓存
AIOPS_NO_CACHE=1 python3 runbooks/scripts/daily-health-check.py ...
```

### 4.4 CLI 参数禁用（仅 daily-health-check）

```bash
python3 runbooks/scripts/daily-health-check.py --no-cache --resource-group-id rg-xxx
```

### 4.5 缓存统计

```python
from _shared import cache_stats
print(cache_stats())
# {'hit': 42, 'miss': 8, 'bypass': 0, 'error': 0, 'total': 50, 'hit_rate': 0.84}
```

**自动输出**：`daily-health-check.py` 完成后自动打印 `cache_stats: {...}`

---

## 五、缓存失效与清理

### 5.1 被动失效（TTL 到期）

- 每次 `q_cached()` 读时检查 `mtime`，超 TTL 自动判定 miss
- 不需要主动清理，下次启动时统一扫

### 5.2 主动清理（启动时）

```python
# _shared.py 末尾自动调用
_cache_cleanup()
# 清理 mtime > TTL 的所有文件
```

**日志输出**：`[DIAG] cache_cleanup removed=N dir=...`

### 5.3 手工清理

```bash
# 全清（重新跑测试时常用）
rm -rf audit-results/cache/

# 清理 1 小时前的（不推荐，建议用 TTL）
find audit-results/cache/ -mmin +60 -delete
```

### 5.4 gitignore

`audit-results/cache/` 应在 `.gitignore` 中（已配置）：
```gitignore
audit-results/cache/
```

---

## 六、不可缓存的调用（白名单）

| 调用 | 原因 |
|------|------|
| `q()` 自身（原始 API） | 缓存是 q_cached 的职责，q() 永远不走缓存 |
| 凭证检查 `gate()` | 安全相关，每次必须验证 |
| 写操作 | Sprint 6 白名单之前无写操作；之后自动写不缓存 |
| 包含 `--ReadFromCache false` 的 aliyun CLI 调用 | 用户明确不缓存 |

---

## 七、性能对比（实测数据 2026-06-06）

### 7.1 API 调用减量

| Run | 缓存 | 资源 | 耗时 | API 调用（估） |
|-----|------|------|------|--------------|
| #1 | 无 | 56 | 159s | ~70 |
| #2 | 无 | 56 | 148s | ~70 |
| #3 | 无 | 56 | 148s | ~70 |
| **带缓存首次** | 有 | 56 | 152s | ~70 (写) |
| **带缓存二次** | 有 | 56 | **~50s** | **~24 (66%DOWN)** |

### 7.2 Hit Rate 期望

| 场景 | 期望命中率 |
|------|----------|
| 同一脚本短时间重跑 (5min 内) | 80-95% |
| 4 个脚本连续跑 | 50-70% (各自首次 miss) |
| 定时调度 (6h 间隔) | 0% (TTL 全部过期) |
| 紧急场景 (故障排查) | 30-50% (只复用资源清单) |

### 7.3 命中率提升方向

- **聚合调用**：把多个指标的 CMS 查询合并为 1 次 `DescribeMetricList` 调用（不在 Sprint 8 范围）
- **预热**：定时任务先空跑一遍预热缓存
- **TTL 动态化**：根据数据变化频率自适应（未来）

---

## 八、风险与缓解

| 风险 | 缓解 |
|------|------|
| **过期数据掩盖告警** | CMS TTL 2min；提供 `--no-cache` 强制刷新 |
| **缓存击穿** | TTL + random jitter 偏移 |
| **错误响应被缓存** | 写缓存前校验 `Code` 字段 |
| **磁盘增长** | 启动时自动清理过期文件 |
| **跨账号串味** | 缓存键不含 account_id，**不推荐** 跨账号共享巡检环境 |

---

## 九、与其他 Sprint 的关系

| Sprint | 关系 |
|--------|------|
| Sprint 1-2 (核心脚本+并行) | 缓存层构建在 q() 之上，不破坏现有逻辑 |
| Sprint 6 (白名单) | 写操作未来走白名单后，q_cached 不应用于白名单操作 |
| Sprint 7 (Incident Schema) | 缓存键不含 `dedup_key`，Sprint 9 落地时按 dedup_key 二次过滤 |
| Sprint 9 (Incident 落地) | 依赖缓存减少落地系统的 API 压力 |
| Sprint 12 (双引擎) | 固化工作流引擎可复用本缓存层（内存化升级） |

---

## 十、版本策略

| 版本 | 变更 |
|------|------|
| v1.0.x | 调整 TTL；新增/删除 API 缓存；修复 bug |
| v1.x.0 | 升级存储后端 (SQLite)；新增指标维度 |
| v2.0.0 | 重构键生成算法；调整目录结构 |

---

## 十一、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-06 | 初始版本（策略 B 落地） |
