# Monitoring NAT

> **Purpose:** NAT Gateway monitoring metrics, anomaly patterns, and alerts.

## Key Metrics (Cloud Monitor CMS)

| Metric | Namespace | Description | Unit | Alarm Threshold |
|--------|-----------|-------------|------|-----------------|
| `ActiveConnection` | `acs_nat` | Active connections on NAT | count | Based on spec capacity |
| `NewConnection` | `acs_nat` | New connections/sec | count/s | Alert on sudden drops |
| `DropConnection` | `acs_nat` | Dropped connections | count/s | Non-zero = issue |
| `MaxConnection` | `acs_nat` | Peak connections | count | Alert if > 80% capacity |
| `OutRatePercent` | `acs_nat` | Outbound bandwidth utilization | % | Alert > 80% |
| `InRatePercent` | `acs_nat` | Inbound bandwidth utilization | % | Alert > 80% |

**CMS Namespace:** `acs_nat`

## Multi-Metric Anomaly Inspection

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| 带宽-连接双高压 | `OutRatePercent` + `MaxConnection` | 带宽 > 85% AND 连接 > 80% 上限 | Critical | NAT 规格和带宽双瓶颈，需升级 |
| 流量突降异常 | `InRatePercent` + `OutRatePercent` + `NewConnection` | 流量较 1h 均值下降 > 70% | Warning | 可能 VPC 路由变更、后端服务异常、或 EIP 解绑 |
| 连接耗尽趋势 | `MaxConnection` (6h 趋势) | 连接数线性增长接近上限 | Warning | DNAT/ SNAT 连接泄漏，需排查后端服务 |
| 丢包-带宽背离 | `DropConnection` + `OutRatePercent` | 丢连接但带宽使用低 | Warning | 可能连接数限制而非带宽瓶颈；后端响应慢或超时 |
| Inbound 异常突增 | `InRatePercent` + `NewConnection` | 入流量突增 3x+ | Warning | 可能 DDoS、爬虫、或异常扫描 |

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| 带宽-连接双高 | `alicloud-nat-ops` | `alicloud-eip-ops` | 升级 NAT 规格 + 添加 EIP |
| 流量突降 | `alicloud-nat-ops` | `alicloud-vpc-ops` (检查路由) | 检查 VPC 路由表/EIP 状态 |
| 连接耗尽趋势 | `alicloud-nat-ops` | — | 优化后端服务连接池 |
| 入流量异常 | `alicloud-nat-ops` | `alicloud-cms-ops` | 检查 DNAT 映射，启用 WAF/高防 |

## Alert Storm Handling

1. **Aggregate by NatGatewayId**: Multiple metric alarms on same NAT → single event
2. **Identify root**: Connection exhaustion often causes cascading timeout failures
3. **Suppress by SNAT/DNAT**: Group backend-related alarms; check if issue is source (SNAT) or destination (DNAT)

## FinOps Monitoring Metrics

### Cost-Related Metrics

| Metric | Namespace | Description | Unit | Alarm Threshold | FinOps Relevance |
|--------|-----------|-------------|------|-----------------|------------------|
| `MaxConnection` | `acs_nat` | Peak connections (proxy for CU) | count | < 20% of spec limit for 7d → underutilized | Right-sizing signal |
| `OutRatePercent` | `acs_nat` | Outbound bandwidth utilization | % | < 30% for 30d → over-provisioned | Bandwidth optimization |
| `InRatePercent` | `acs_nat` | Inbound bandwidth utilization | % | < 30% for 30d → over-provisioned | Bandwidth optimization |
| `ActiveConnection` | `acs_nat` | Active connections | count | = 0 for 7d → idle NAT | Idle resource detection |

### Cost Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| 闲置 NAT 网关 | `ActiveConnection` + `MaxConnection` | 连接 = 0 持续 7 天 | Warning | NAT 无业务流量，持续产生实例费和 EIP 费 |
| 规格过度配置 | `MaxConnection` (30d 趋势) | CU 利用率 < 20% 持续 30 天 | Info | NAT 规格过大，可降配节省成本 |
| 带宽过度配置 | `OutRatePercent` + `InRatePercent` (30d) | 带宽利用率 < 30% 持续 30 天 | Info | EIP 带宽过大，可降配或切换计费模式 |
| EIP 计费不匹配 | `OutRatePercent` (30d) + 计费模式 | PayByBandwidth 但利用率 < 30% | Info | 应切换为 PayByTraffic 或使用 CBWP |

### FinOps Recovery & Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| 闲置 NAT | `alicloud-nat-ops` | `alicloud-eip-ops` | 删除 NAT + 释放 EIP |
| 规格过度 | `alicloud-nat-ops` | — | 降配 NAT 规格 |
| 带宽过度 | `alicloud-nat-ops` | `alicloud-eip-ops` | 降配 EIP 带宽或切换计费模式 |
| EIP 计费不匹配 | `alicloud-nat-ops` | `alicloud-eip-ops` | 切换计费模式或创建 CBWP |

## SecurityOps Monitoring Metrics

### Security-Related Metrics

| Metric | Namespace | Description | Unit | Alarm Threshold | Security Relevance |
|--------|-----------|-------------|------|-----------------|-------------------|
| `NewConnection` | `acs_nat` | New connections/sec | count/s | Sudden 5x+ spike on DNAT | Possible DDoS or port scan |
| `InRatePercent` | `acs_nat` | Inbound bandwidth utilization | % | Sudden 3x+ spike | Possible attack on exposed DNAT |
| `DropConnection` | `acs_nat` | Dropped connections | count/s | Non-zero on DNAT NAT | Security group or connection limit blocking |
| `DropPacketBlackHole` | `acs_nat` | Blackhole drops (DDoS) | count/s | Non-zero | DDoS attack triggered blackhole |

### Security Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| DNAT 入流量突增 | `InRatePercent` + `NewConnection` | 入流量突增 3x+ AND DNAT 存在 | Critical | 可能是对暴露端口的攻击 |
| DNAT 黑洞触发 | `DropPacketBlackHole` + `InRatePercent` | 黑洞 > 0 AND 入流量突增 | Critical | DDoS 攻击触发黑洞，DNAT 服务不可用 |
| DNAT 连接异常 | `NewConnection` + `DropConnection` | 新连接骤降 + 丢连接增加 | Warning | 可能安全组变更或后端异常 |
| SNAT 出流量异常 | `OutRatePercent` + `NewConnection` | 出流量突增 5x+ | Warning | 可能内网实例被入侵后对外发起攻击 |

### SecurityOps Recovery & Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| DNAT 入流量突增 | `alicloud-nat-ops` | `alicloud-cms-ops` | 检查 DNAT 高危端口，启用 WAF/高防 |
| DNAT 黑洞 | `alicloud-nat-ops` | `alicloud-eip-ops` | 启用 DDoS 高防，临时切换 EIP |
| DNAT 连接异常 | `alicloud-nat-ops` | `alicloud-ecs-ops` | 检查后端 ECS 安全组和服务状态 |
| SNAT 出流量异常 | `alicloud-nat-ops` | `alicloud-ecs-ops` | 排查内网实例是否被入侵 |
