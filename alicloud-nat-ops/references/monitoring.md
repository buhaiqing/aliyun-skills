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
