# Sprint 1: 核心脚本化（P0）

> 业务价值: 巡检速度提升 50%+，Agent 从"读 MD 推理"变为"直接调脚本"
> 交付物: `runbooks/scripts/` (4 个 Python 脚本)
> 前置条件: 无
> 关联验收项: S1-D1

### 任务

- [x] **1.0** 架构决策 | 最终采用 Python（原计划 Bash，经评估 Python 更优）
- [x] **1.1** 创建 `runbooks/scripts/` 目录
- [x] **1.2** 提取 `daily-health-check.py` ← 核心脚本
- [x] **1.3** 提取 `emergency-troubleshoot.py`
- [x] **1.4** 提取 `capacity-planning.py`
- [x] **1.5** 提取 `pre-launch-check.py`
- [x] **1.6** 更新 4 个 runbook MD，顶部加脚本引用行
- [x] **1.7** 幂等入口: 每个脚本 `--describe` 预检
- [x] **1.8** 升级钩子: Critical 时写 `audit-results/.need_escalation`
- [x] **1.9** 凭证加固: 纯 env 变量，输出无 AK，自动加载 `.env`
- [x] **✅ 集成测试通过** (2026-06-06, cn-hangzhou, default RG, 55个资源)

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q1.1 | Python 语法 | `python3 -m py_compile scripts/*.py` | ✅ 全部通过 |
| Q1.2 | 参数解析 | `python3 script.py --help` | 输出版本号+参数列表 ✅ |
| Q1.3 | 凭证不泄露 | `grep -E 'LTAI|AKIA|SecretKey|secret' scripts/*.py` | ✅ 0 匹配 (纯 os.environ) |
| Q1.4 | 幂等生效 | `python3 script.py --describe` | ✅ 输出执行计划，不实际执行 |
| Q1.5 | 自动加载 `.env` | 脚本自动搜索 `../../.env` | ✅ 无需手动 source |
| Q1.6 | 无硬编码 | `grep -E 'region.*cn-|PageSize.*=' scripts/*.py` | ✅ 所有值用变量/环境变量 |