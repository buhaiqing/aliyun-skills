# ActionTrail Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for ActionTrail (操作审计). Each pattern follows the standardized schema.

## AT-001 — Trail 日志投递中断

| 属性 | 内容 |
|------|------|
| 触发指标 | Trail `IsLogging` = false 或 `LatestDeliveryTime` > 1 小时前 |
| 触发阈值 | 日志投递中断 > 1 小时 |
| 典型特征 | SLS/OSS 中无新事件，Trail 状态异常 |
| 关联指标 | Trail 投递失败数增长 |
| 根因 | 1. SLS Project/OSS Bucket 被删除 2. RAM 权限变更 3. Trail 配置被篡改 |
| 诊断步骤 | 1. GetTrailStatus 查看状态 2. DescribeTrails 查配置 3. 检查 SLS/OSS 权限 |
| 修复方案 | 1. 重新配置 Trail 投递目标 2. 恢复 RAM 权限 |
| 预防措施 | Trail 状态持续监控、SLS/OSS 权限定期审计 |

## AT-002 — Insight 告警风暴

| 属性 | 内容 |
|------|------|
| 触发指标 | 多个 Insight 类型（Ip/Ak/ErrorRate）同时触发 |
| 触发阈值 | 5 min 内 > 5 个 Insight 事件 |
| 典型特征 | 多个安全告警同时出现，可能来自同一用户/IP |
| 关联指标 | 审计事件量突增 |
| 根因 | 1. AK 泄漏被恶意使用 2. 内部人员违规操作 3. 自动化脚本失控 |
| 诊断步骤 | 1. LookupInsightEvents 查详情 2. 按 userIdentity 聚合 3. 时间线分析 |
| 修复方案 | 1. 禁用可疑 AK 2. 重置密码 3. 审计所有关联操作 |
| 预防措施 | AK 自动轮换、权限最小化、操作审批 |

## AT-003 — 批量资源删除

| 属性 | 内容 |
|------|------|
| 触发指标 | Delete 系列事件 > 10/5 min |
| 触发阈值 | 删除事件频率超过基线 3 倍 |
| 典型特征 | 多个资源同时被删除，覆盖 ECS/RDS/SLB 等 |
| 关联指标 | 跨产品的审计事件突增 |
| 根因 | 1. 误操作脚本 2. 恶意攻击 3. 自动化配置错误 |
| 诊断步骤 | 1. 按 eventName LIKE 'Delete%' 聚合 2. 查操作者身份 3. 确认是否预期 |
| 修复方案 | 1. 停止操作源 2. 从备份恢复资源 3. 审计权限 |
| 预防措施 | 资源删除审批流程、防删除保护、定期备份 |

## AT-004 — 权限滥用

| 属性 | 内容 |
|------|------|
| 触发指标 | `PolicyChangeInsight` + `AttachPolicyToUser` 高频出现 |
| 触发阈值 | 策略变更 > 3/10 min |
| 典型特征 | 用户/角色被赋予异常权限 |
| 关联指标 | RAM 相关审计事件突增 |
| 根因 | 1. 攻击者提权 2. 误配置 3. 内部人员违规 |
| 诊断步骤 | 1. 查策略变更时间线 2. 对比历史权限 3. 确认操作者 |
| 修复方案 | 1. 回滚变更 2. 禁用异常权限 3. 审计影响范围 |
| 预防措施 | RAM 变更审批、权限基线对比、异常变更自动告警 |

## AT-005 — Root 账户异常活动

| 属性 | 内容 |
|------|------|
| 触发指标 | Root 账户登录 + API 调用来自新 IP |
| 触发阈值 | Root 登录 + 新 IP + 非工作时间 |
| 典型特征 | Root 账户在非正常时间从陌生 IP 登录 |
| 关联指标 | 登录成功后立即执行敏感操作（创建 AK、修改策略） |
| 根因 | 1. Root 密码泄漏 2. 内鬼操作 3. 凭证被窃取 |
| 诊断步骤 | 1. 查事件时间线 2. 确认 IP 归属 3. 验证操作者身份 |
| 修复方案 | 1. 立即禁用 Root 密码 2. 重置 AK 3. 审计所有操作 |
| 预防措施 | Root 密码 MFA、Root 操作审计、非 Root 最佳实践 |

## Cross-Product — ActionTrail → ECS → SLB 攻击链

**场景：** AK 泄漏 → 创建新 ECS → 安装后门 → 修改 SLB 路由

| 级联阶段 | 时间 | 现象 | 关联 Skill |
|----------|------|------|------------|
| T0 | 00:00 | AK 从新 IP 登录，创建 ECS | `alicloud-actiontrail-ops` |
| T1 | +5 min | 新 ECS 安装异常软件 | `alicloud-ecs-ops` |
| T2 | +15 min | SLB 配置被修改，流量指向新 ECS | `alicloud-slb-ops` |
| T3 | +30 min | 数据被窃取 | 安全事件 |

**诊断顺序：** SLB 变更 → ActionTrail 查变更历史 → ECS 异常创建 → 确认 AK 泄漏并阻断

## Cross-Product — ActionTrail → RAM 权限提升 → 资源删除

**场景：** 攻击者获取低权限 AK → 提权策略 → 删除资源

| 级联阶段 | 时间 | 现象 | 关联 Skill |
|----------|------|------|------------|
| T0 | 00:00 | AkInsight 触发异常 | `alicloud-actiontrail-ops` |
| T1 | +2 min | 策略被修改，权限提升 | `alicloud-ram-ops` |
| T2 | +10 min | 批量删除 ECS/RDS 资源 | `alicloud-ecs-ops` + `alicloud-rds-ops` |
| T3 | +30 min | 业务中断 | 应急响应 |

**诊断顺序：** 资源删除 → ActionTrail 追踪操作链 → RAM 权限变更 → 禁用 AK + 恢复权限
