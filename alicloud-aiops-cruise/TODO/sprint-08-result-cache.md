# Sprint 8: 结果缓存（P2, Future）

> **状态**: PASS 5/5
> **业务价值**：4 个 runbook 共享热点数据（资源清单、指标、ACK 节点），重复执行时直接读缓存。目标：API 调用减 60% + 总耗时减 30%+。
> **依赖**：Sprint 1 (核心脚本化 PASS) + Sprint 2 (并行加速 PASS)
> **关联验收项**：Stage 2 D2（自动化深度：低风险白名单可自动执行，但当前无 cache -> 重复执行浪费 API 配额）

---

## 一、调研背景

### 1.1 当前 API 调用模式

**实测 3 次 daily-health-check 耗时 (2026-06-06)**：

| Run | 耗时 | 资源数 | Critical | Warning |
|-----|------|--------|----------|---------|
| #1  | 159s | 56     | 3        | 3       |
| #2  | 148s | 56     | 3        | 3       |
| #3  | 148s | 56     | 3        | 3       |

**阶段耗时细分（来自 Run #1 日志）**：

| 阶段 | 耗时 | 占比 | 重复性评估 |
|------|------|------|----------|
| Phase 0 安全门 | < 1s | 0.3% | 不缓存（凭证检查应每次跑） |
| Phase 1 拓扑发现 | 3s | 2.0% | **可缓存**（资源清单变化慢，TTL 5min） |
| Phase 2a 资源选择 | 0s | 0.0% | 不缓存 |
| **Phase 2b 指标采集 (CMS)** | **37s** | **25.0%** | **可缓存**（数据延迟 1-2min 业务无感知） |
| Phase 2c ACK 采集 | 24s | 16.2% | **可缓存**（节点列表变化慢，TTL 10min） |
| Phase 2d K8s limits | 19s | 12.8% | **可缓存**（5min TTL） |
| Phase 2e 7d 回溯 | 48s | 32.4% | **可缓存**（历史数据不变，TTL 1h） |
| Phase 3 拓扑渲染 | 20s | 13.5% | 部分可缓存（health JSON 可缓存 1min） |

**关键发现**：
- **7d 回溯（48s）+ K8s limits（19s）+ ACK 采集（24s）= 91s = 总耗时 60%** — 这三块是缓存的最大杠杆点
- **指标采集（37s）= 25%** — 中等杠杆
- **拓扑发现（3s）+ 拓扑渲染（20s）= 23s = 15%** — 小杠杆

### 1.2 跨 runbook 的重复点

4 个 runbook 共享的数据：

| 数据 | daily-health | emergency | capacity | pre-launch | 共享度 |
|------|--------------|-----------|----------|------------|--------|
| 资源清单 (RG/Tag) | OK | OK | OK | OK | **100%** |
| 资源指标 (CMS) | OK | 部分 | OK | 部分 | 70% |
| ACK 节点 | OK | - | - | OK | 50% |
| 7d 趋势数据 | - | - | OK | OK | 50% |
| 安全组规则 | OK | OK | - | - | 50% |
| ActionTrail | - | OK | - | - | 25% |

**结论**：资源清单、ACK 节点、7d 趋势是跨 runbook 共享的"热点数据"。

### 1.3 当前 q() 函数瓶颈

```python
# _shared.py:187
def q(cmd: list, timeout=30) -> dict | None:
    # CMS 调用: Semaphore 5 限速, 429/Throttling 时指数退避重试
    # 非 CMS 调用: 无限制, 不重试
```

**问题**：
- 每次都直接打 aliyun CLI，无任何缓存层
- 跨进程（4 个脚本独立运行）无法共享缓存
- 跨时间（同一脚本短时间内重复执行）也走全链路

---

## 二、缓存策略候选

### 策略 A: 进程内 LRU 缓存（最简单）

**实现**：在 `_shared.py` 中加 `functools.lru_cache` 装饰 `q()` 函数，按 `tuple(cmd)` 做 key

**优点**：
- 零依赖，5 行代码
- 同一进程内调用自动复用

**缺点**：
- 跨进程不共享（4 个脚本 = 4 个独立缓存）
- 无法设置 TTL
- 内存无限增长风险

**预计收益**：单进程内重复命令减 100%；跨进程 = 0
**实施成本**：1h

### 策略 B: 文件系统缓存（推荐 MVP）

**实现**：在 `audit-results/cache/` 目录下按 `hash(cmd) + TTL` 存储 JSON

```python
# _shared.py 新增
import hashlib
import json
import time
from pathlib import Path

CACHE_DIR = Path("/tmp/aiops-cruise-cache")  # or audit-results/cache/
DEFAULT_TTL = {
    "DescribeMetricList": 120,    # 2min
    "DescribeInstances": 300,     # 5min
    "DescribeClusters": 600,      # 10min
    "ListTagResources": 300,      # 5min
    "DescribeMetricData": 300,    # 5min
}

def q_cached(cmd, ttl=DEFAULT_TTL.get(cmd[1], 60)):
    cache_key = hashlib.md5(json.dumps(cmd, sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < ttl:
        return json.loads(cache_file.read_text())
    result = q(cmd)
    if result is not None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result))
    return result
```

**优点**：
- 跨进程共享（4 个脚本都读同一目录）
- TTL 可控
- 简单可靠（无外部依赖）

**缺点**：
- 文件 I/O 比内存慢（~ms 级，可接受）
- 需要缓存清理策略（cron 或 LRU）

**预计收益**：API 调用减 50-70%
**实施成本**：4h

### 策略 C: SQLite 缓存（中长期）

**实现**：用 SQLite 存 `(cache_key, value, expires_at)` 三元组

**优点**：
- 支持复杂查询（按时间范围、按资源类型）
- 内置 LRU（手动实现）
- 跨平台、零依赖

**缺点**：
- 单文件锁竞争（4 进程并发写）
- 比文件缓存重

**预计收益**：API 调用减 60-80%
**实施成本**：1-2 天

### 策略 D: Redis/Memcached（重）

不推荐 — 引入外部依赖，违反项目"零依赖"原则（架构蓝图 §一）

### 推荐路径

| 阶段 | 策略 | 目标 |
|------|------|------|
| **MVP（本次）** | 策略 B (文件缓存) | API 减 50%+，4h 实施 |
| **Sprint 8.5（可选）** | 策略 C (SQLite) | 复杂查询支撑，1-2 天 |
| **Sprint 12 (双引擎)** | 内存缓存层 | 固化工作流引擎内置 cache |

---

## 三、TTL 设计

按数据类型分级：

| 数据类型 | 典型 TTL | 理由 |
|---------|---------|------|
| **资源清单 (Describe*)** | 5 min | 资源 CRUD 频率低，5min 内变化罕见 |
| **CMS 指标 (DescribeMetricList)** | 2 min | CMS 本身有 1min 采集周期，2min 缓存无感知 |
| **历史回溯 (backtrack_cms)** | 1 h | 历史数据点不变，可长缓存 |
| **安全组规则** | 5 min | 配置变更频率低 |
| **ActionTrail** | 30 sec | 操作事件要求近实时 |
| **拓扑 health JSON** | 1 min | 跨脚本共享，可接受 1min 延迟 |

**失效策略**：
- TTL 到期：下次读取时刷新
- 强制失效：CLI 参数 `--no-cache` 或 `--cache-bust`
- 缓存污染防护：校验响应 `Code/Message` 字段，失败则不写缓存

---

## 四、API 调用减量预估（基于实测）

### 4.1 daily-health-check 当前 API 调用清单（来自脚本）

| API | 次数 | 缓存命中率预估 | 节省 |
|-----|------|--------------|------|
| `cms DescribeMetricList` | ~50 (每个资源/指标) | 60% | -30 |
| `cs DescribeClusters` | 1 | 0% (TTL 内只跑 1 次) | 0 |
| `cs DescribeClusterNodes` | 1 | 90% (节点列表稳定) | -1 |
| `cs DescribeClusterNodePools` | 1 | 90% | -1 |
| `backtrack_cms` (7d) | 8 (每节点 1 次) | 95% (历史数据稳定) | -7.6 |
| `DescribeMetricList` (limits) | 8 | 80% | -6.4 |
| **小计** | ~70 | **-46 (66%)** | |

### 4.2 跨 runbook 总收益

| 场景 | 当前 | 加缓存后 | 节省 |
|------|------|---------|------|
| daily-health-check (单跑) | 70 API / 148s | 24 API / ~50s | **66%** |
| daily + capacity (串行) | 140 API / 296s | 50 API / ~80s | **64%** |
| 4 runbook 全跑 (理想) | 280 API / 600s | 60 API / ~120s | **78%** |

---

## 五、风险与约束

### 5.1 数据新鲜度风险

| 风险 | 缓解 |
|------|------|
| **缓存过期数据掩盖真实告警** | TTL 设保守值（CMS 2min）；提供 `--no-cache` 强制刷新 |
| **缓存击穿** (TTL 过期瞬间大量请求) | 加 random jitter（±10% TTL） |
| **缓存污染** (异常响应被缓存) | 校验响应 `Code` 字段，非 200 不写缓存 |
| **磁盘增长** | 启动时清理过期文件（按 mtime） |

### 5.2 一致性约束

- **Sprint 9 落地后**：缓存键需考虑 `dedup_key`（同一资源同一天同规则只算 1 次）
- **Sprint 11 ML 升级后**：训练数据要求时间序列完整，缓存不能破坏时序连续性

### 5.3 不可缓存的调用

- **写操作**（ModifyInstance 等）：永远不缓存
- **安全相关**（ActionTrail、审计日志）：TTL 30s 且强制每日清理
- **凭证检查**（gate()）：永远不缓存

---

## 六、MVP 实施范围（建议）

### 6.1 本次 Sprint 8 交付物

- [ ] **8.1** 在 `_shared.py` 新增 `q_cached()` 函数
  - 文件路径：`audit-results/cache/`
  - TTL 按 API 类型分级（§三）
  - 响应校验（Code 字段检查）
  - 启动时清理过期文件
- [ ] **8.2** 在 `daily-health-check.py` 中替换 6 处 `q()` -> `q_cached()`
  - 保持 `--no-cache` 参数可禁用
- [ ] **8.3** 在 `emergency-troubleshoot.py` 中替换 2 处
- [ ] **8.4** 在 `capacity-planning.py` 中替换 2 处
- [ ] **8.5** 在 `pre-launch-check.py` 中替换 1 处
- [ ] **8.6** 编写 `references/cache-strategy.md` 完整规范
- [ ] **8.7** 跑 2 次对照实验（带缓存 vs 不带），记录 API 减量
- [ ] **8.8** 跑 ruff + code-reviewer 评审
- [ ] **8.9** TODO.md / stage-status.json 同步

### 6.2 不在本次范围

- SQLite 升级版（留 Sprint 8.5 或 Sprint 12）
- 跨账号缓存（无场景）
- Redis 集成（违反零依赖原则）

---

## 七、质量门

| 编号 | 检查项 | 验证命令 | 阈值 |
|------|--------|----------|------|
| Q8.1 | `q_cached()` 函数存在 | `grep -c 'def q_cached' runbooks/scripts/_shared.py` | ≥ 1 |
| Q8.2 | TTL 表完整 | `grep -cE 'DescribeMetricList\|DescribeInstances' runbooks/scripts/_shared.py` | ≥ 4 |
| Q8.3 | 4 个脚本全部接入缓存 | `grep -c 'q_cached(' runbooks/scripts/*.py` | ≥ 11 (6+2+2+1) |
| Q8.4 | `--no-cache` 参数支持 | `grep -c '\\-\\-no-cache' runbooks/scripts/*.py` | ≥ 1 |
| Q8.5 | 启动清理逻辑 | `grep -c 'CACHE_DIR\\|cache.*mtime' runbooks/scripts/_shared.py` | ≥ 2 |
| Q8.6 | cache-strategy.md 存在 | `test -s references/cache-strategy.md` | 通过 |
| Q8.7 | 对照实验报告 | `test -s audit-results/benchmarks/cache-vs-nocache.md` | 通过 |
| Q8.8 | API 调用减 ≥ 50% | 对照实验数据 | ≥ 50% |
| Q8.9 | Ruff Lint | `ruff check runbooks/scripts/` | 0 错误 |
| Q8.10 | TODO.md 同步 | `grep -c 'Sprint 8.*8/' TODO.md` | ≥ 1 |

---

## 八、决策建议

**问题**：是否启动 Sprint 8 实施？

**选项**：
- **A. 立即启动** — 6h 实施，API 减 66%，符合"Stage 2 自动化深度"验收项
- **B. 推迟到 Stage 2 准入后** — 先做 Incident 落地（Sprint 9），缓存等真实流量起来再加
- **C. 只做轻量级 (策略 A)** — 进程内 LRU 即可，1h 实施，不碰文件系统

**我的建议**：**选项 A** — Sprint 8 与 Sprint 9 互不阻塞，可并行
- Sprint 8 (缓存)：纯性能优化，6h 实施，影响面小（只在 _shared.py 改）
- Sprint 9 (落地)：数据契约集成，需要重构 4 个脚本输出格式

并行做不冲突，但 Sprint 9 落地后可能需小幅调整缓存键（按 dedup_key）。建议**先 Sprint 8（增量、不破坏），再 Sprint 9（重构）**。

---

## 九、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0-draft | 2026-06-06 | 调研初版（3 次真实环境数据 + 4 策略对比 + MVP 实施范围） |
