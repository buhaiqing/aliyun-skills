# Sprint 21: 统一风险模型 + ML 灰度增强

> **状态**: PASS 5/5
> **业务价值**: 将阈值、持续时间、趋势预测、动态基线和 ML 灰度旁路统一为可解释风险证据链，降低误报并提升预测可信度。
> **依赖**: Sprint 3 动态基线、Sprint 9 Incident Schema、Sprint 11 ML 调研

---

## 一、交付物

| 编号 | 交付物 | 状态 |
|---|---|---|
| S21-D1 | `references/risk-model.md` 统一风险模型规范 | [x] |
| S21-D2 | `_shared.py` 风险证据生成函数：阈值 + 持续时间 + 趋势 + 动态基线 + ML shadow | [x] |
| S21-D3 | `daily-health-check.py` 输出 `risk_evidence[]`、`ml_policy` 和 Markdown Risk Evidence 表 | [x] |
| S21-D4 | ML 灰度环境变量：`AIOPS_ML_MODE` / `AIOPS_ML_GRAY_PERCENT` / `AIOPS_ML_MIN_CONFIDENCE` | [x] |
| S21-D5 | Incident metadata 写入 `risk_evidence` / `ml_shadow_result` | [x] |
| S21-D6 | 只读集成验证修复：脚本入口补 `import _shared`，`q_cms_batch_by_dim` 加入 `__all__` | [x] |
| S21-D7 | 单资源只读回归修复：`--resource-id` 在 `confirm()` 阶段按产品 ID 字段过滤到单个资源 | [x] |
| S21-D8 | 单资源报告修复：`--resource-id` 时跳过账号级 topo-discovery 合并，改写单资源拓扑说明，避免全局资源清单误导 | [x] |
| S21-D9 | 发现范围优化：`discover()` 在提交查询任务前应用 `--include/--skip`，避免单 ECS 回归扫描无关产品 | [x] |

---

## 二、质量门

| 编号 | 检查 | 命令 | 状态 |
|---|---|---|---|
| Q21.1 | 风险模型纯函数可导入 | `python3 - <<'PY' ... build_metric_risk_evidence(...) ... PY` | [x] |
| Q21.2 | ML 灰度默认关闭 | `python3 - <<'PY' ... get_ml_policy()['mode']=='off' ... PY` | [x] |
| Q21.3 | 灰度选择稳定 | `should_enable_ml_shadow('i-1','CPUUtilization', {'mode':'shadow','gray_percent':100}) == True` | [x] |
| Q21.4 | Python 语法检查 | `python3 -m py_compile alicloud-aiops-cruise/runbooks/scripts/_shared.py alicloud-aiops-cruise/runbooks/scripts/daily-health-check.py` | [x] |
| Q21.5 | 代码审查 | `code-reviewer` 复审 Sprint 21 风险模型 + ML 灰度逻辑 | [x] |
| Q21.6 | 离线报告集成 | 模拟 `metrics/anomalies/baseline_data` 调用 `report()` + `_write_topology_health_json()` | [x] |
| Q21.7 | 真实只读集成 | `daily-health-check.py --include ECS --non-interactive --output-dir .runtime/tmp/...`，仅执行 Describe/List/GET/CMS 查询类读操作 | [x] |
| Q21.8 | ML shadow 集成 | `AIOPS_ML_MODE=shadow AIOPS_ML_GRAY_PERCENT=100` 验证 `ml_shadow_result` 入报告且不改变最终等级 | [x] |
| Q21.9 | 单 ECS 只读回归 | `--include ECS --resource-id i-bp15ygqmyb51od3swbll --non-interactive`，验证 `selected total=1`、`resources={'ECS': 1}`、`risk_evidence` 仅包含目标实例 | [x] |
| Q21.10 | 单资源拓扑修复回归 | 验证单 ECS 报告不再包含 `阿里云网络拓扑与资源清单` 全局标题，包含 `单资源巡检范围` 说明 | [x] |
| Q21.11 | 发现范围真实只读回归 | `--include ECS --resource-id i-bp15ygqmyb51od3swbll` 验证 `discovery scope=ECS`、`discovery total=10 types=1`、`selected total=1`，报告仅含目标 ECS | [x] |

> 说明：`ruff check` 在 `_shared.py` / `daily-health-check.py` 上仍会命中历史遗留 lint 债（重复函数定义、旧 ACK 段一行多语句等），本 Sprint 未扩散修复无关旧代码；新增风险模型路径已通过 `py_compile`、纯函数 smoke、shadow/advisory/active 行为回归、code-reviewer 复审、离线报告集成和真实只读 ECS 集成验证。

---

## 三、后续增强

- [ ] 接入 5min 实时采样点，替换当前基于 1h 基线的持续时间估算。
- [ ] 增加 ML shadow 结果落盘明细，用于统计误报率/漏报率/提前预警时间。
- [ ] 对 `capacity-planning.py` 复用同一 `risk_evidence` schema。
- [ ] 增加 `--ml-mode` CLI 参数，当前先使用环境变量以减少交互复杂度。
