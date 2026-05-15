# SLB Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for SLB. Each pattern follows the standardized schema.

## SLB-001 — 后端服务 5xx 风暴

| 属性 | 内容 |
|------|------|
| 触发指标 | `InstanceUpstreamCode5xx` + `InstanceStatusCode5xx` > 50/min |
| 触发阈值 | 5xx > 50/min 持续 3 min |
| 典型特征 | 后端健康检查大量异常，5xx 错误率突增，RT 飙升 |
| 关联指标 | `InstanceRt` > 10s、`BackendServerHealthCheck` abnormal |
| 根因 | 1. 后端应用崩溃 2. 数据库不可用 3. 依赖服务故障 |
| 诊断步骤 | 1. DescribeHealthStatus 查后端 2. 查异常 ECS |
| 修复方案 | 1. 临时：将异常后端移出 SLB 2. 长期：修复后端服务 |
| 预防措施 | 健康检查间隔 ≤ 5s，异常阈值 ≤ 3 次 |

## SLB-002 — 连接数耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | `InstanceMaxConnection` > 80% 规格上限 |
| 触发阈值 | 活跃连接 > 80% 上限 持续 10 min |
| 典型特征 | 新连接被丢弃，`InstanceDropConnection` 上升 |
| 关联指标 | `InstanceDropPacketTX` 同步上升 |
| 根因 | 1. 流量突增 2. 慢连接泄漏 3. 规格选型过低 |
| 诊断步骤 | 1. 查连接趋势 2. 区分新/旧连接比例 |
| 修复方案 | 1. 临时：临时扩容 2. 长期：升级 SLB 规格 |
| 预防措施 | 监控连接数趋势，预测性扩容 |

## SLB-003 — SSL 证书过期

| 属性 | 内容 |
|------|------|
| 触发指标 | HTTPS 监听 5xx 突增，客户端证书错误 |
| 触发阈值 | 证书过期日 < 7 天 |
| 典型特征 | 客户端报告 SSL_ERROR 或证书不安全警告 |
| 关联指标 | `InstanceStatusCode5xx` + 客户端侧 SSL 错误 |
| 根因 | 1. 证书到期未续费 2. 手动更换了无效证书 |
| 诊断步骤 | 1. 检查 SSL 证书有效期 2. 确认证书域名匹配 |
| 修复方案 | 1. 上传新证书 2. 重新关联 HTTPS 监听 |
| 预防措施 | 证书到期 30/7/1 天三级告警，自动化更新 |

## SLB-004 — 带宽饱和

| 属性 | 内容 |
|------|------|
| 触发指标 | `InstanceTrafficTX` + `InstanceDropTrafficTX` 同步上升 |
| 触发阈值 | 带宽 > 85% 规格限制 持续 5 min |
| 典型特征 | 响应变慢，丢流量上升，客户端超时 |
| 关联指标 | `InstanceRt` 同步上升 |
| 根因 | 1. 大文件下载 2. 爬虫抓取 3. 配置变更未限流 |
| 诊断步骤 | 1. 查各后端流量分布 2. 识别大流量源 |
| 修复方案 | 1. 临时：启用 CDN 分流 2. 长期：升级带宽规格 |
| 预防措施 | 设置带宽 80% 预警 |

## SLB-005 — 后端健康检查误判

| 属性 | 内容 |
|------|------|
| 触发指标 | `BackendServerHealthCheck` 频繁切换 normal↔abnormal |
| 触发阈值 | 健康状态 5 min 内切换 > 3 次 |
| 典型特征 | 后端频繁进出/进出，SLB 转发间歇性中断 |
| 关联指标 | `InstanceStatusCode5xx` 周期性突增 |
| 根因 | 1. 健康检查路径返回慢 2. GC 导致响应超时 3. 检查间隔过短 |
| 诊断步骤 | 1. 检查健康检查配置 2. 手动访问健康检查路径 |
| 修复方案 | 1. 调整检查间隔 ≥ 5s 2. 超时时间 > 响应时间 |
| 预防措施 | 健康检查路径需轻量快速 |

## Cross-Product — SLB → RDS 数据库级联故障

**场景：** 后端应用连接池泄漏 → RDS 连接耗尽 → 5xx 爆发

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | ECS 应用连接池持续增长 | `alicloud-ecs-ops` |
| T1 | +5 min | RDS 活跃连接接近上限 | `alicloud-rds-ops` |
| T2 | +10 min | 数据库拒绝新连接，应用返回 500 | `alicloud-slb-ops` (5xx 告警) |
| T3 | +30 min | SLB 大量 5xx，用户完全不可用 | `alicloud-rds-ops` + `alicloud-ecs-ops` |

**诊断顺序：** SLB 5xx → 查后端 ECS → ECS 连接 RDS 失败 → 查 RDS 连接数 → 定位连接泄漏应用

## Cross-Product — SLB → ECS 批量摘除

**场景：** 安全组变更导致 SLB 无法到达后端 → 全部摘除

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | VPC 安全组规则被修改（如通过 `alicloud-actiontrail-ops` 发现） | `alicloud-vpc-ops` |
| T1 | +1 min | SLB 健康检查全部失败 | `alicloud-slb-ops` |
| T2 | +3 min | 所有后端标记异常，SLB 无可用后端 | `alicloud-slb-ops` |

**诊断顺序：** SLB 无后端 → 查安全组规则 → 对比 ActionTrail 变更历史 → 恢复安全组
