# RAM Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for RAM (访问控制). Each pattern follows the standardized schema.

## RAM-001 — 权限拒绝（Forbidden）

| 属性 | 内容 |
|------|------|
| 触发指标 | API 返回 `Forbidden.RAM` 错误 |
| 触发阈值 | 权限拒绝 > 5/min 持续 2 min |
| 典型特征 | 应用无法执行 API 操作，日志中有 AccessDenied 错误 |
| 关联指标 | 操作成功率下降、应用错误率上升 |
| 根因 | 1. 策略被修改/删除 2. RAM 用户/角色被禁用 3. STS Token 过期 |
| 诊断步骤 | 1. `aliyun ram GetUserPolicy` 2. 对比历史权限 3. ActionTrail 查变更 |
| 修复方案 | 1. 恢复丢失的策略 2. 重新生成 STS Token |
| 预防措施 | 权限变更审批、策略版本管理、STS Token 自动续期 |

## RAM-002 — STS Token 过期

| 属性 | 内容 |
|------|------|
| 触发指标 | API 返回 `SecurityTokenExpired` |
| 触发阈值 | Token 过期导致操作失败 |
| 典型特征 | 临时凭证失效，自动化任务中断 |
| 关联指标 | 批量 API 调用失败 |
| 根因 | 1. Token 未续期 2. 实例角色异常 3. 时间偏移导致提前过期 |
| 诊断步骤 | 1. 查 Token 过期时间 2. 检查 STS 策略是否被修改 |
| 修复方案 | 1. 重新获取 STS Token 2. 修复角色信任策略 |
| 预防措施 | Token 自动续期机制、过期前告警 |

## RAM-003 — 策略冲突

| 属性 | 内容 |
|------|------|
| 触发指标 | 用户对同一资源同时有 Allow 和 Deny |
| 触发阈值 | 权限评估返回拒绝 |
| 典型特征 | 新策略生效旧功能中断，权限表现不确定 |
| 关联指标 | 权限评估日志中出现 Deny Override |
| 根因 | 1. 多个策略冲突 2. 新策略未充分考虑旧权限 3. 边界条件策略错误 |
| 诊断步骤 | 1. `SimulatePolicyAction` 2. 列出所有生效策略 3. 逐条评估 |
| 修复方案 | 1. 修正 Deny 策略 2. 清理冗余策略 |
| 预防措施 | 策略发布前模拟评估、策略审计 |

## Cross-Product — RAM 权限异常 → 多产品操作失败

**场景：** RAM 策略误删 → ECS/RDS/SLB/AliMonitor 全部 API 拒绝

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | RAM 策略被删除 | `alicloud-actiontrail-ops` |
| T1 | +1 min | ECS/RDS/SLB 操作失败 | 各产品 Skill |
| T2 | +5 min | 监控/自动化全部中断 | `alicloud-cms-ops` |

**诊断顺序：** 多产品同时报 Forbidden → 查 RAM 策略变更 → 恢复权限
