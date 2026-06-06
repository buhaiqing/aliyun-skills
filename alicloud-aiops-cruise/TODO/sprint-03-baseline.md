# Sprint 3: 动态基线完善（P0）

> 业务价值: 从固定阈值升级为"固定阈值+动态基线"双判定
> 交付物: `runbooks/01-daily-health-check.md` (含 Step 2.9 + 报告模板)
> 前置条件: 无 (B-01 已完成)
> 关联验收项: S1-D2

### 任务

- [x] **3.0** Step 2.9 动态基线异常评分 (已完成)
- [ ] **3.1** 指标按方法映射 | CPU→ZScore, IOPS→P95, 磁盘→ZScore+固定阈值双重判定
- [ ] **3.2** 降噪逻辑 | 连续 2+ 超标才标记，单次突刺忽略
- [ ] **3.3** 报告模板增加「异常评分摘要」表格
- [ ] **3.4** JSON schema 增加 `anomaly_scores` 数组

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q3.1 | 双判定取最高 | CPU 85% 同时触发阈值 Warning 和基线 Critical | 最终取 Critical |
| Q3.2 | 降噪有效 | 单次 CPU 突刺 > 3σ 仅 1 个采样点 | 不标记异常 |
| Q3.3 | JSON 合法 | `python3 -c "import json; json.load(open('report.json'))"` | 无异常 |
| Q3.4 | 报告可读 | `grep -c 'Z-Score' report.md` | >= 1 行 |