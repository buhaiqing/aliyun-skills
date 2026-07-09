---
name: aiops-risk-model
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# 统一风险模型与 ML 灰度策略

> 目标：把巡检结论从单一阈值判断升级为可解释的风险证据链。默认保持规则引擎为主，ML 仅在灰度策略允许时旁路增强。

## 1. 风险合成公式

每个指标级 finding 生成一条 `risk_evidence`：

```text
risk_score = max(
  static_threshold_score,
  duration_score,
  trend_score,
  dynamic_baseline_score,
  ml_shadow_score * 0.8
)
```

`risk_level` 由 `risk_score` 与最高等级证据共同决定：

| risk_score | risk_level | 语义 |
|---:|---|---|
| `>= 0.75` | `CRITICAL` | 需要立即处理，或 3 天内达到 Critical 阈值 |
| `>= 0.50` | `WARNING` | 需要关注，或 7 天内达到 Critical 阈值 |
| `>= 0.25` | `INFO` | 有偏离/上升趋势，但未形成明确风险 |
| `< 0.25` | `NORMAL` | 无显著风险 |

## 2. 证据字段

`risk_evidence[]` 输出字段：

| 字段 | 说明 |
|---|---|
| `resource_id` / `resource_type` / `metric` | 风险对象 |
| `current_value` | 当前值 |
| `risk_level` / `risk_score` / `confidence` | 最终等级、评分、置信度 |
| `static_level` | 固定阈值判定 |
| `duration.consecutive_points` | 最新连续超阈采样点数 |
| `duration.duration_minutes` | 连续超阈持续时间，基于 1h 基线采样估算 |
| `trend.direction` | `rising` / `falling` / `flat` / `unknown` |
| `trend.daily_growth` | 日增长量 |
| `trend.days_to_warning` / `days_to_critical` | 预计到达阈值天数，无法预测则为 `null` |
| `anomaly_level` | 动态基线等级 |
| `ml_shadow_result` | ML 灰度旁路结果 |
| `detection_methods` | 参与判定的方法列表 |
| `reason` | 人类可读证据摘要 |

## 3. 持续时间规则

默认用基线 1h 采样点估算持续时间：

```text
duration_minutes = consecutive_points * 60
```

当前版本优先作为证据输出，不替代固定阈值规则。后续如接入 5min 实时点，可把 `period_seconds` 降为 300，实现更精细的“持续 X 分钟”判定。

## 4. 趋势预测规则

基础趋势使用可解释线性模型：

```text
daily_growth = (last - first) / window_days
```

等级提升规则：

| 条件 | 趋势等级 |
|---|---|
| `days_to_critical <= 3` | `CRITICAL` |
| `days_to_critical <= 7` | `WARNING` |
| `days_to_warning <= 14` | `INFO` |

## 5. ML 灰度策略

ML 默认关闭，不影响现有巡检结果。通过环境变量启用：

```bash
AIOPS_ML_MODE=off|shadow|advisory|active
AIOPS_ML_ENGINE=auto|stl|prophet
AIOPS_ML_GRAY_PERCENT=10
AIOPS_ML_MIN_CONFIDENCE=0.85
```

| 模式 | 行为 |
|---|---|
| `off` | 默认；不运行 ML |
| `shadow` | 运行 ML 并输出 `ml_shadow_result`，不改变最终等级 |
| `advisory` | 运行 ML 并进入建议/证据链，不改变最终等级 |
| `active` | 仅当 `confidence >= min_confidence` 时，允许 ML 提升等级 |

灰度选择基于 `sha256(resource_id:metric) % 100`，保证同一资源同一指标稳定命中。

## 6. 安全边界

- ML 不允许执行任何资源变更。
- `off/shadow/advisory` 不允许改变最终告警等级。
- `active` 只允许升级风险，不允许降低规则引擎判断。
- 依赖不可用或历史不足时，ML 输出 `status=fallback`，规则路径继续运行。

## 7. 验证命令

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, 'alicloud-aiops-cruise/runbooks/scripts')
from _shared import build_metric_risk_evidence
print(build_metric_risk_evidence('i-1','ECS','CPUUtilization',88,70,85,[60,70,86,87,88])['risk_level'])
PY
```
