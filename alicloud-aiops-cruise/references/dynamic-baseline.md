---
name: dynamic-baseline-scoring
version: "1.0.0"
parent: alicloud-aiops-cruise
---

# 动态基线异常评分标准

> **将 AIOps 从"固定阈值"升级到"智能基线"的核心规范。**
> 所有巡检指标同时使用 ① 固定阈值（传统方式）和 ② 动态基线异常评分，取两者中最高等级。

## [NOTE] 为什么需要动态基线

固定阈值的问题：

```
固定阈值:  CPU > 70% = Warning
  ├─ 白天高峰期 CPU 65% -> 正常，但未被警告 -> 漏报
  ├─ 凌晨备份 CPU 30% -> 比基线 10% 飙升 200%，但不到阈值 -> 漏报
  └─ 不同业务（电商 vs 后台）需要不同基线 -> 固定阈值无法自适应

动态基线:  |current - μ| / σ > 2.0 = Warning
  ├─ 白天 CPU 65%（μ=55%, σ=5%) -> Z=2.0->Warning PASS 凌晨 CPU 30%（μ=10%, σ=3%) -> Z=6.7->Critical PASS
  └─ 自动适应不同业务的"正常值"
```

## 异常检测方法

### 方法 1: Z-Score（适用于正态分布指标）

**适用指标**: CPUUtilization, memory_usage, CpuUsage, DiskUsage

```
Z = (current_value - μ) / σ

其中:
  μ = mean(history_7d)   # 过去 7 天均值
  σ = stddev(history_7d)  # 过去 7 天标准差

判定:
  Z > 3.0 -> Critical
  Z > 2.0 -> Warning
  Z > 1.0 -> Info（记录，不告警）
  Z ≤ 1.0 -> Normal
```

**Agent 实现公式**（纯 jq + bc，无需 Python）：

```bash
# 从 CloudMonitor 获取 7 天 1h 粒度数据
HISTORY=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions "[{\"instanceId\":\"i-xxx\"}]" \
  --Period 3600 \
  --StartTime "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  | jq '.Datapoints | fromjson | [.[].Average]')

# μ
MEAN=$(echo "$HISTORY" | jq 'add / length')

# σ = sqrt(Σ(x - μ)² / n)
STD=$(echo "$HISTORY" | jq --argjson m "$MEAN" '(map(. - $m | . * .) | add / length | sqrt) // 0')

# 当前值 = 最新采样点
CURRENT=$(echo "$HISTORY" | jq '.[-1]')

# Z-Score
if [ "$(echo "$STD > 0" | bc -l)" = "1" ]; then
  Z=$(echo "scale=2; ($CURRENT - $MEAN) / $STD" | bc -l)
else
  Z="0"
fi
```

### 方法 2: 分位数偏离（适用于突发特征指标）

**适用指标**: DiskReadIOPS, DiskWriteIOPS, ActiveConnection, NewConnection, SlowQueryCount

```
判定:
  current > P99 -> Critical
  current > P95 -> Warning
  current > P75 -> Info
  current ≤ P75 -> Normal
```

**Agent 实现**：

```bash
# P95 分位数
P95=$(echo "$HISTORY" | jq 'sort | .[(length * 0.95 | floor)] // 0')
P99=$(echo "$HISTORY" | jq 'sort | .[(length * 0.99 | floor)] // 0')
CURRENT=$(echo "$HISTORY" | jq 'max // 0')

if [ "$(echo "$CURRENT > $P99" | bc -l)" = "1" ]; then echo "CRITICAL CRITICAL"
elif [ "$(echo "$CURRENT > $P95" | bc -l)" = "1" ]; then echo "WARNING WARNING"
else echo "PASS OK"; fi
```

### 方法 3: 时序分解（适用于强周期性指标）

**适用指标**: SlowQueryCount, SnatConnection, NewConnection（日周期性明显时）

> [FAST] 本方法有三个实现层级，按可用环境和精度需求选择。

#### Level 1: 按小时分桶（无额外依赖，jq + bash 即可）

按 hour-of-day 对历史数据分组，每个小时独立计算 μ 和 σ：

```bash
# 对过去 7 天的数据，按 (hour-of-day) 分组
# bucket[hour] = [value1, value2, ..., value7]
# μ[hour] = mean(bucket[hour])
# σ[hour] = stddev(bucket[hour])
# 当前小时 h 的异常分: Z = (current - μ[h]) / σ[h]
```

**局限**: jq 做分桶逻辑复杂，7×24=168 数据点尚可，30天就吃力了。

#### Level 2: Python + statsmodels（需 Python 3.8+ 和 statsmodels 库）

使用 STL (Seasonal-Trend-Loess) 分解，分离趋势、季节性和残差：

```python
import statsmodels.api as sm
import numpy as np

# 输入: 30 天 1h 粒度时序数据 (720 点)
data = [...]  # np.array, shape=(720,)

# STL 分解
stl = sm.tsa.STL(data, period=24, seasonal=7)
result = stl.fit()

# 残差 = 原始 - 趋势 - 季节性
residual = result.resid

# 异常分 = 当前残差 / 残差标准差
threshold = 3.0 * np.std(residual)
anomaly = np.abs(residual[-1]) > threshold
```

**优势**: 自动分离日周期和趋势，比纯 Z-Score 精准 30-50%。
**依赖**: `pip install statsmodels pandas numpy`

#### Level 3: Prophet + scikit-learn（需 Python + ML 库）

使用 Prophet 做包含节假日效应的预测：

```python
from prophet import Prophet
import pandas as pd

# 构建训练数据
df = pd.DataFrame({'ds': timestamps, 'y': values})

# 训练 Prophet 模型
model = Prophet(
    yearly_seasonality=False,
    weekly_seasonality=True,
    daily_seasonality=True,
    holidays=holidays  # 中国节假日列表
)
model.fit(df)

# 预测下一个时间点
future = model.make_future_dataframe(periods=1, freq='H')
forecast = model.predict(future)

# 异常分 = (实际值 - 预测值) / 预测区间宽度
actual = latest_value
predicted = forecast['yhat'].iloc[-1]
lower = forecast['yhat_lower'].iloc[-1]
upper = forecast['yhat_upper'].iloc[-1]

if actual > upper or actual < lower:
    anomaly_level = 'CRITICAL'
elif abs(actual - predicted) > 1.5 * (upper - lower) / 2:
    anomaly_level = 'WARNING'
```

**优势**: 处理节假日效应（春节/双11流量变化），支持多季节性。
**依赖**: `pip install prophet scikit-learn pandas`

#### Level 4: Go 编译版本（零运行时依赖，生产级）

将 Level 2/3 的算法用 Go 重写，编译为独立二进制：

```bash
# 一次编译，到处运行
go build -o bin/baseline-scorer scripts/baseline-scorer.go

# 输入 JSON -> 输出 anomaly score
cat metrics.json | ./bin/baseline-scorer --method stl --period 24
```

**优势**: 无 Python 运行时依赖，适合容器化/CI/CD 场景，延迟 < 10ms。
**依赖**: Go 1.21+（仅编译时需要，运行时不需要）

#### 方法 3 选型决策树

```
环境有 Python + statsmodels?
├─ 是 -> 团队熟悉 ML？
│   ├─ 是 -> 用 Prophet（Level 3），精度最高
│   └─ 否 -> 用 STL（Level 2），精度足够
└─ 否 -> 环境有 Go 编译器？
    ├─ 是 -> 编译 Go 版 scorer（Level 4）
    └─ 否 -> 用 jq 分桶（Level 1），精度有限
```

## 指标 -> 方法映射表

| 指标 | Namespace | 推荐方法 | 基线窗口 | 备注 |
|---|---|---|---|---|
| CPUUtilization | acs_ecs_dashboard | Z-Score / STL | 7d / 30d | 推荐 STL 分桶，CPU 有日周期 |
| memory_usage | acs_ecs_dashboard | Z-Score | 7d | 需安装 CloudMonitor Agent |
| DiskReadIOPS | acs_ecs_dashboard | 分位数(P95/P99) | 7d | 突刺特征，不适用 STL |
| DiskWriteIOPS | acs_ecs_dashboard | 分位数(P95/P99) | 7d | 突刺特征 |
| InternetInRate | acs_ecs_dashboard | STL 分解 | 30d | 带宽有强烈日周期 |
| ActiveConnection | acs_slb_dashboard | 分位数(P95/P99) | 7d | 连接数有突刺 |
| NewConnection | acs_slb_dashboard | Z-Score / STL | 7d | 新建连接有周周期 |
| CpuUsage | acs_rds_dashboard | STL 分解 | 30d | RDS CPU 有业务周期 |
| DiskUsage | acs_rds_dashboard | Z-Score + 固定阈值 | 7d | 递增趋势，两者结合 |
| SlowQueryCount | acs_rds_dashboard | 分位数(P95/P99) | 7d | 突发特征 |
| memory_usage | acs_redis_dashboard | Z-Score | 7d | 内存使用平稳 |
| UsedConnection | acs_redis_dashboard | 分位数(P95/P99) | 7d | 连接数有突刺 |
| SnatConnection | acs_nat_gateway | Z-Score | 7d | 变化缓慢，适合 Z-Score |

## 异常等级定义

| 等级 | Z-Score | 分位数 | 颜色 | 报告行为 | 建议行动 |
|---|---|---|---|---|---|
| Critical | Z > 3.0 | > P99 | CRITICAL | 列入 Critical 清单 | 立即介入排查 |
| Warning | Z > 2.0 | > P95 | WARNING | 列入 Warning 清单 | 关注趋势 |
| Info | Z > 1.0 | > P75 | INFO | 仅在异常评分摘要中展示 | 记录，不告警 |
| Normal | Z ≤ 1.0 | ≤ P75 | PASS | 不展示 | 无操作 |

## 基线窗口策略

| 策略 | 窗口 | Agent 实现 | 适用阶段 |
|---|---|---|---|
| 快速上线 | 7 天 × 1h = 168 点 | `date -u -v-7d` | 新接入环境 |
| 标准（推荐） | 30 天 × 1h = 720 点 | `date -u -v-30d` | 正式生产 |
| 含节假日 | 90 天 × 1h = 2160 点 | `date -u -v-90d` | 有季节性业务 |

> Baseline **不**需要每次巡检都重新计算。可复用上一次巡检的计算结果（JSON 持久化到 `audit-results/`）。重新计算的触发条件：
> - 首次巡检（无缓存）
> - 距离上次计算超过 6 小时
> - 阈值配置文件更新

## 与固定阈值的关系

```
最终判定 = max(固定阈值等级, 动态基线等级)

例 1: CPU 当前 25%, 固定阈值 -> PASS OK, Z-Score = 3.5 -> Critical
  最终 -> Critical（基线发现异常，阈值漏报）

例 2: CPU 当前 75%, 固定阈值 -> Warning, Z-Score = 1.5 -> PASS OK
  最终 -> Warning（阈值发现异常，基线认为是业务高峰期正常波动）

例 3: CPU 当前 90%, 固定阈值 -> Critical, Z-Score = 5.0 -> Critical
  最终 -> Critical（两者一致）
```

## 报告输出格式

每条异常记录必须包含以下字段（JSON 持久化）：

```json
{
  "instance_id": "i-xxx",
  "metric": "CPUUtilization",
  "current_value": 85.0,
  "baseline_mean": 25.0,
  "baseline_std": 5.0,
  "z_score": 12.0,
  "anomaly_level": "CRITICAL",
  "method": "z-score",
  "window_days": 7,
  "bucket_strategy": "global"
}
```

## 实现层选型指南

| 层级 | 技术栈 | 精度 | 依赖 | 适用阶段 |
|------|--------|------|------|---------|
| Level 1 | jq + bc（当前） | *** | 无 | 快速验证 |
| Level 2 | Python + statsmodels | **** | `pip install statsmodels pandas` | 正式生产 |
| Level 3 | Python + Prophet | ***** | `pip install prophet scikit-learn` | 高精度需求 |
| Level 4 | Go 编译二进制 | **** | Go 编译器(仅编译时需要) | 生产级/容器化 |

> 本 skill 的代码仓库中：
> - `scripts/baseline-scorer.py` — Level 2/3 的 Python 实现
> - `scripts/baseline-scorer.go` — Level 4 的 Go 实现（编译后无依赖）

## 异常降噪

| 场景 | 策略 | 实现 |
|---|---|---|
| 短期突刺 | 连续 2+ 个采样点超标才标记 | `evaluation_count > 1` |
| 指标重设 | 重启/变更后基线重置 | 检测到 ActionTrail 变更事件后清除缓存 |
| 数据不足 | < 24h 数据回退到固定阈值 | `if history_length < 24: use fixed threshold` |
| 零值容忍 | IOPS 可能为零（无流量），不标记异常 | `if max(history) == 0: skip` |