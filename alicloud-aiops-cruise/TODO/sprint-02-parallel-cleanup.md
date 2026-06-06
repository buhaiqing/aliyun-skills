# Sprint 2: 并行加速 + 代码审查修缮（P1）

> 业务价值: 5min → 1min，同时完成 Sprint 1 代码审查遗留项修复
> 交付物: `runbooks/scripts/` 共享模块化重构
> 前置条件: Sprint 1 完成
> 关联验收项: 无

### 任务

- [x] **2.1** 🎯 提取共享 `_shared.py` 模块，4个脚本统一复用（F-001）
- [x] **2.2** 🎯 capacity/pre-launch 统一产品注册表结构 + `jq_path` 字段（F-007/F-010）
- [x] **2.3** 🎯 capacity/pre-launch 增加 `--resource-group-id` / `--tag-key` 支持（F-005/F-008）
- [x] **2.4** 🎯 capacity/pre-launch 统一退出码 `exit_code()`（F-011）
- [x] **2.5** 并行采集: daily-health 的产品发现 + 指标采集均用 `ThreadPoolExecutor`

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q2.1 | 无重复提取逻辑 | `grep -c 'def dig' scripts/*.py` | 只有 1 处定义 |
| Q2.2 | 参数一致性 | `python3 script.py --help` | 4 个脚本统一支持 --resource-group-id |
| Q2.3 | 并行加速比 | `time python3 script.py` | 全量扫描 < 2min |
| Q2.4 | 退出码规范 | 脚本结束时 `$?` | 0=正常, 1=Critical, 2=无资源 |