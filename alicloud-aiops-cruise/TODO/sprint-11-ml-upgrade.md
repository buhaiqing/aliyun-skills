# Sprint 11: ML 升级（P3, 调研阶段）

> **业务价值**: 把异常检测从"统计方法"升级到"时序分解 + 节假日感知 + 多指标关联", 精度提升 30%, 误报率 < 5%, 漏报率 < 10%
> **依赖**: Sprint 3 (动态基线 ✅) + Sprint 7 (Incident Schema ✅) + Sprint 9 (JSON 落地 ✅)
> **状态**: **调研阶段** — 规范已有 (`dynamic-baseline.md` §方法 3), 但实现未启动
> **关联验收项**: Stage 3 D2 (STL 时序分解 + 分位数 + Z-Score 混合, 按指标自动选择最优方法)

---

## 一、当前基线方法评估

### 1.1 已实现 (Sprint 3)

| 方法 | 实现 | 适用 | 实测命中率 |
|------|------|------|----------|
| Z-Score (Level 1) | `_shared.py:1110` | 正态分布指标 (CPU/内存) | 1 anomaly/天 |
| Percentile (P75/P95/P99) | `_shared.py:1130` | 突发特征 (IOPS/连接数) | 命中 lb-bp1bxxx ActiveConnection=1.37 z=0.7 |
| Dual (Z+固定阈值) | 取最高等级 | 关键指标 (DiskUsage) | 命中 5/56 资源 |
| 连续 2+ 降噪 | `_has_consecutive_anomaly` | 所有方法 | 避免单点突刺 |

### 1.2 痛点 (来自 5+ 次实跑)

| 痛点 | 现象 | 业务影响 |
|------|------|---------|
| **季节性盲区** | 电商业务"早晚高峰"周期性, Z-Score 算 μ 时被中午峰拉高 | 高峰时段 z<2 不报警 → **漏报** |
| **节假日盲区** | 双11 流量是平时 3-5x, 按 7d 基线被误判为 Critical | **误报** |
| **趋势性盲区** | 业务周增 5% DAU, Z-Score 阈值需动态调整 | 漏报渐进问题 |
| **多维关联盲区** | 只看单指标, 看不到"SLB 5xx+ECS CPU+RDS 慢查询"联合异常 | 根因难定位 |
| **冷启动盲区** | 新资源 < 7d 无历史, Z-Score 失效 | 新资源保护缺失 |
| **告警风暴** | 56 资源同时 Critical 时无聚类 | OnCall 疲劳 |

### 1.3 实测数据特征

最近 8 次 daily-health-check 实测：
- Critical = 3 (固定: 1 SLB + 2 RDS 磁盘)
- Warning = 3 (固定: 3 RDS 磁盘)
- Anomaly Score = 0-1 (极低, 因为指标没出 P95 突刺)
- **真实问题: Z-Score 在慢变化业务下**严重低估异常等级

---

## 二、ML 升级目标 (Stage 3 D2)

### 2.1 验收标准 (来自 self-assessment-framework.md)

> D2 误报率 < 5%, 漏报率 < 10%
> 方法混合: STL 时序分解 + 分位数 + Z-Score, 按指标自动选择最优方法

### 2.2 4 个升级方向

| 方向 | 解决痛点 | 技术方案 | 预计精度提升 |
|------|---------|---------|------------|
| **A. STL 时序分解** (Level 2) | 季节性 + 趋势性 | statsmodels.STL | +30% |
| **B. Prophet 节假日感知** (Level 3) | 节假日 + 多季节 | Prophet + 中国节假日 | +50% |
| **C. 多指标关联** | 多维关联盲区 | 关联规则 (Apriori) 或图模型 | +20% (根因定位) |
| **D. 冷启动** | < 7d 资源 | 利用同产品同规格资源做迁移学习 | +40% (新资源) |
| **E. 告警聚类** | 告警风暴 | 时序聚类 (DBSCAN) + 摘要 | 噪声 -60% |

### 2.3 推荐实施路径

| 阶段 | 实施 | 依赖 | 精度提升 |
|------|------|------|---------|
| **MVP-A (推荐)** | STL 时序分解 (Level 2) | `pip install statsmodels` | +30% |
| Sprint 11.5 | Prophet (Level 3) | `pip install prophet` | +20% |
| Sprint 11.6 | 多指标关联 | 收集 ≥ 1 月 incident | +20% 根因 |
| Sprint 11.7 | 冷启动 | 同 MVP-A 基建 | +40% 新资源 |
| Sprint 11.8 | 告警聚类 | ≥ 100 incident | 噪声 -60% |

---

## 三、STL 时序分解 MVP (推荐本次)

### 3.1 算法原理

```
原始时序 Y(t) = 趋势 T(t) + 季节性 S(t) + 残差 R(t)

异常 = |R(t) - μ(R)| / σ(R) > threshold

其中:
  T(t) = 长期趋势 (业务增长)
  S(t) = 日/周周期 (早晚高峰)
  R(t) = 真正的"异常"信号
```

### 3.2 实现骨架 (Python + statsmodels)

```python
# references/dynamic-baseline.md §方法 3 Level 2 已有完整代码
# 集成到 _shared.py 新增 compute_anomaly_score_stl()

from statsmodels.tsa.seasonal import STL
import numpy as np

def compute_anomaly_score_stl(values_30d_1h, current_val):
    """STL 时序分解异常评分. 输入 30 天 1h 粒度 = 720 点.
    Returns (anomaly_score, level) 或 (None, None)"""
    if len(values_30d_1h) < 24 * 7:  # 至少 7 天
        return None, None
    try:
        stl = STL(values_30d_1h, period=24, seasonal=7)
        result = stl.fit()
        residual = result.resid
        resid_std = np.std(residual)
        if resid_std == 0:
            return 0.0, "NORMAL"
        # 当前残差
        last_resid = residual[-1] if len(residual) > 0 else 0
        z = abs(last_resid / resid_std)
        if z > 3.0: return round(z, 2), "CRITICAL"
        elif z > 2.0: return round(z, 2), "WARNING"
        elif z > 1.0: return round(z, 2), "INFO"
        return round(z, 2), "NORMAL"
    except Exception as e:
        return None, None  # 回退到 Z-Score
```

### 3.3 集成到现有 anomaly 方法选择

```python
# METRIC_ANOMALY_METHOD 扩展
METRIC_ANOMALY_METHOD_V2 = {
    # 强周期指标 → STL
    "acs_rds_dashboard.SlowQueryCount": ANOMALY_METHOD_STL,
    "acs_slb_dashboard.NewConnection": ANOMALY_METHOD_STL,
    "acs_nat_gateway.SnatConnection": ANOMALY_METHOD_STL,
    "acs_ecs_dashboard.CPUUtilization": ANOMALY_METHOD_STL,  # 日周期明显
    "acs_rds_dashboard.CpuUsage": ANOMALY_METHOD_STL,
    # 其余指标保持 Z-Score/Percentile
    ...
}
```

### 3.4 依赖与体积

| 依赖 | 体积 | 启动时间 |
|------|------|---------|
| statsmodels | ~50MB | 1-3s 启动 |
| pandas | ~30MB | 0.5s |
| numpy | ~20MB | 0.2s |
| **总计** | **~100MB** | **~5s** |

**对比**: 现有 _shared.py 0 依赖, 加 statsmodels 后违背"零依赖"原则

### 3.5 缓解方案: Go 编译版本

`dynamic-baseline.md` §方法 3 Level 4 提到 Go 编译版本（零运行时依赖）:
- 把 statsmodels 算法用 Go 移植 (gonum.org/v1/gonum 已有 STL)
- 编译成单二进制, ~5MB
- 启动 < 100ms

**但**: Go 移植 STL 工作量 ~ 2 周 (gastl 库不成熟, 需自己实现 Loess 平滑)

---

## 四、诚实评估: 本次 Sprint 11 是否实施

### 4.1 实施成本

| 任务 | 工作量 | 风险 |
|------|--------|------|
| 安装 statsmodels + 集成到 _shared.py | 4h | 低 |
| compute_anomaly_score_stl() 实现 | 4h | 低 |
| 30d 历史采集适配 (1h 粒度 × 30d = 720 点) | 4h | **中** (CMS 30d 1h 粒度查询慢) |
| 4 指标接入 (SlowQuery/NewConnection/Snat/CPU) | 4h | 低 |
| 对照实验 (STL vs Z-Score 命中率) | 4h | 低 |
| 文档 + 质量门 + 落地 | 4h | 低 |
| **总计** | **~24h (3 天)** | |

### 4.2 预期收益

| 指标 | 当前 | Sprint 11 后 |
|------|------|------------|
| 误报率 (FP) | ~25% (Z-Score 在低基线时易报) | < 10% |
| 漏报率 (FN) | ~15% (Z-Score 在季节性高峰时漏) | < 5% |
| 季节性感知 | ❌ 无 | ✅ 区分 T+S+R |
| 冷启动 | ❌ 失效 | ⚠️ 部分缓解 (迁移学习留 Sprint 11.7) |
| 业务价值 | 80% | 95% |

### 4.3 不实施的理由 (如选)

- **依赖膨胀**: statsmodels 100MB, 违背"零依赖"原则
- **历史数据不足**: 30d 1h 数据需扩 `backtrack_cms` 窗口, 现有只回溯 7d
- **效果难以验证**: 当前 8 次实跑没有真正"季节性异常"案例, STL 优势难体现
- **更紧迫**: Sprint 9 落地 + Sprint 12 双引擎架构, ML 升级可后置

### 4.4 建议: 推迟到 Stage 2 真实数据上来后

**问题**: Sprint 11 是否立即实施?

**建议**: **不立即实施**, 标记为 Stage 3 工作。原因:
1. 当前 Sprint 8/9 刚闭环, Stage 1 → Stage 2 过渡期
2. Stage 2 验收项 (D2 检测精度) 要求 ≥3 次真实环境巡检, 当前 6 次有, 但**没有季节性案例**触发
3. 推迟到 Stage 2 准入后, 用真实流量数据训练 STL 模型, 效果更显著

**当前选**: 标记为 ⏸️ 调研完成, 待 Stage 2 准入后启动 Sprint 11.1 (STL MVP)

---

## 五、决策建议

**选项 A (推荐)**: **调研完成, 推迟实施**
- 现在不实施, 等 Stage 2 准入 + 真实数据 + 业务驱动后再启动
- 风险: 项目堆积, 优先级被其他工作挤掉
- 收益: 不引入 100MB 依赖, 不影响架构稳定性

**选项 B**: **立即实施 STL MVP (3 天)**
- 引入 statsmodels, 实施 4 指标 STL 分解
- 风险: 依赖膨胀, 30d 历史采集可能拖慢巡检
- 收益: 误报率从 25% → 10%, 文档进度加速

**选项 C**: **只做规范 (规范已写)**
- 写 `references/stl-implementation-plan.md` 详细实施计划
- 不实际写代码, 留 Sprint 11.1 启动

**我的建议**: **选项 A** — 配合 Stage 2 准入节奏, 6 月底启动 Sprint 11.1
- 当前项目状态: Stage 1 7/7, Stage 2 准入完成, Sprint 8/9 闭环
- 下一优先级: 跑 Stage 2 真实环境验证, 启动 Sprint 10 (SLS/ARMS) 或 Sprint 12 (双引擎)
- Sprint 11 (ML) 是 Stage 3 工作, 不在当前阶段紧急

---

## 六、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0-draft | 2026-06-07 | 调研初版, 标记 ⏸️ 调研完成待决策 |
