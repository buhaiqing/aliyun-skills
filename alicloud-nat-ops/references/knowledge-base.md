# NAT Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for NAT Gateway. Each pattern follows the standardized schema.

## NAT-001 — SNAT 连接耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | MaxConnection > 80% 上限 |
| 触发阈值 | 连接 > 80% 上限持续 10 min |
| 典型特征 | 内网实例无法访问外部服务，SNAT 超时 |
| 关联指标 | DropConnection 非零、OutRatePercent 正常 |
| 根因 | 1. 单 EIP 连接容量 ~30K 已达上限 2. 连接泄漏 3. 并发请求过多 |
| 诊断步骤 | 1. DescribeNatGateways 查状态 2. 统计连接分布 3. 查异常实例 |
| 修复方案 | 1. 添加更多 EIP 绑定到 NAT 2. 优化连接池和超时 |
| 预防措施 | 连接数 70% 预警、EIP 扩容预案 |

## NAT-002 — DNAT 端口映射不通

| 属性 | 内容 |
|------|------|
| 触发指标 | External IP:Port 无响应 |
| 触发阈值 | DNAT 目标端口不可达 > 3 min |
| 典型特征 | 外部无法通过 DNAT 访问内部服务，但内部服务正常 |
| 关联指标 | Internal IP 健康，外部 IP 无入流量 |
| 根因 | 1. DNAT 配置错误 2. 后端安全组阻止 3. ECS 防火墙阻止 |
| 诊断步骤 | 1. DescribeForwardTableEntries 查配置 2. 查 ECS 安全组 3. 从 VPC 内部访问验证 |
| 修复方案 | 修正 DNAT 配置、调整安全组 |
| 预防措施 | DNAT 配置测试流程、变更后验证 |

## NAT-003 — NAT 带宽饱和

| 属性 | 内容 |
|------|------|
| 触发指标 | OutRatePercent > 90% 持续 5 min |
| 触发阈值 | 带宽 > 90% 规格限制 |
| 典型特征 | 出站请求超时，内部服务调用外部超时 |
| 关联指标 | NewConnection 下降（超时导致）、DropPacketTX 上升 |
| 根因 | 1. 大文件上传 2. 批量数据同步 3. 爬虫对外请求 |
| 诊断步骤 | 1. FlowLog 分析外部目标 2. 统计 Top 内部源 3. 确认业务是否异常 |
| 修复方案 | 1. 升级 NAT 规格 2. 限流 |
| 预防措施 | 带宽 80% 预警、业务流量基线 |

## NAT-004 — EIP 解绑后 SNAT 失效

| 属性 | 内容 |
|------|------|
| 触发指标 | SNAT 流量突降至 0 |
| 触发阈值 | SNAT 流量突降 > 90% |
| 典型特征 | 内网实例突然无法访问互联网 |
| 关联指标 | EIP 解绑事件、SNAT 流量同时归零 |
| 根因 | 1. 误操作解绑 EIP 2. EIP 被其他服务占用 3. 自动脚本逻辑错误 |
| 诊断步骤 | 1. DescribeSnatTableEntries 查状态 2. DescribeEipAddresses 查 EIP 绑定状态 |
| 修复方案 | 1. 重新绑定 EIP 2. 验证 SNAT 恢复 |
| 预防措施 | EIP 解绑操作审批、SNAT 依赖告警 |

## NAT-005 — NAT 网关规格不匹配

| 属性 | 内容 |
|------|------|
| 触发指标 | 规格 CPU > 80% 持续 30 min |
| 触发阈值 | CPU > 80% 或 CU > 规格上限 |
| 典型特征 | 延迟增加、连接建立慢、部分超时 |
| 关联指标 | 延迟指标上升、吞吐量接近上限 |
| 根因 | 1. 业务增长后规格未升级 2. 规格选型过低 3. 突发流量 |
| 诊断步骤 | 1. 查历史 CPU/连接趋势 2. 对比规格限制 |
| 修复方案 | 升级 NAT 规格（Small → Medium → Large → XLarge） |
| 预防措施 | 定期规格评估、自动扩缩容 |

## Cross-Product — NAT 连接耗尽 → RDS 无法拉取外部依赖

**场景：** NAT 连接耗尽 → 内部服务无法连接外网拉取镜像/依赖 → 部署失败

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | NAT 连接耗尽，SNAT 超时 | `alicloud-nat-ops` |
| T1 | +1 min | ACK 集群无法拉取镜像 | `alicloud-ack-ops` |
| T2 | +5 min | 部署失败，Pod Pending | `alicloud-ack-ops` |
| T3 | +10 min | HPA 无法扩容，服务不可用 | `alicloud-slb-ops` |

**诊断顺序：** ACK Pod Pending → ACK 报 ImagePull → NAT SNAT → NAT 连接数