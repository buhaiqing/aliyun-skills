# Sprint 3: 动态基线完善（P0）

> **状态**: PASS 4/4
> 业务价值: 从固定阈值升级为"固定阈值+动态基线"双判定
> 交付物: `runbooks/01-daily-health-check.md` (含 Step 2.9 + 报告模板)
> 前置条件: 无 (B-01 已完成)
> 关联验收项: S1-D2

### 任务

- [x] **3.0** Step 2.9 动态基线异常评分 (已完成)
- [x] **3.1** 指标按方法映射 | CPU->ZScore, IOPS->P95, 磁盘->ZScore+固定阈值双重判定
    实现: `_shared.py` 新增 `METRIC_ANOMALY_METHOD` 映射表 (26个指标),
    `_get_anomaly_method()`, `compute_anomaly_score_zscore()`, `compute_anomaly_score_percentile()` 函数
- [x] **3.2** 降噪逻辑 | 连续 2+ 超标才标记，单次突刺忽略
    实现: `_shared.py` 新增 `_has_consecutive_anomaly()` 函数,
    支持 Z-Score 和 Percentile 两种方法的连续超标检测 (`ANOMALY_MIN_CONSECUTIVE=2`)
- [x] **3.3** 报告模板增加「异常评分摘要」表格
    实现: `_shared.py` 新增 `format_anomaly_scores_table()`, 输出格式化的 Markdown 表格；
    更新 `daily-health-check.py` 的 `report()` 函数, 在 MD 报告中输出异常评分摘要；
    更新 `deep-report-template.md` 增加异常评分章节
- [x] **3.4** JSON schema 增加 `anomaly_scores` 数组
    实现: `daily-health-check.py` 的 `report()` 函数构建 `anomaly_scores` JSON 结构，
    包含 instance_id/metric/current_value/baseline_mean/baseline_std/z_score/level/method/window_days
    完整字段，符合 delivery-standards.md 的 JSON schema 要求

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q3.1 | 双判定取最高 | CPU 85% 同时触发阈值 Warning 和基线 Critical | 最终取 Critical |
| Q3.2 | 降噪有效 | 单次 CPU 突刺 > 3σ 仅 1 个采样点 | 不标记异常 |
| Q3.3 | JSON 合法 | `python3 -c "import json; json.load(open('report.json'))"` | 无异常 |
| Q3.4 | 报告可读 | `grep -c 'Z-Score' report.md` | >= 1 行 |
| Q3.5 | 方法映射完整 | `python3 -c "from _shared import METRIC_ANOMALY_METHOD; print(len(METRIC_ANOMALY_METHOD))"` | >= 16 个指标 |
| Q3.6 | 降噪连续检查 | 模拟 3 个连续超标点 -> 标记异常；仅 1 个 -> 忽略 | 行为正确 |
| Q3.7 | Percentile 方法 | Percentile 指标(IOPS) 使用 P95/P99 而非 Z-Score | 函数分支覆盖 |
| Q3.8 | Dual 方法 | DiskUsage 同时启用 Z-Score 和固定阈值 | 函数调用链正确 |
| Q3.9 | 基线数据不足 | 采集 < 24 个数据点 | 回退到固定阈值，不抛异常 |