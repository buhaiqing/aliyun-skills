# VPC Monitoring

> **Purpose:** VPC monitoring metrics, alerts, and observability patterns.

## VPC-Level Monitoring

VPC itself has no direct CMS metrics, but its components are monitored:

### NAT Gateway Metrics

| Metric | Namespace | Description | Unit | Alarm Threshold |
|--------|-----------|-------------|------|-----------------|
| `ActiveConnection` | `acs_nat` | Active connections on NAT | count | Based on spec capacity |
| `NewConnection` | `acs_nat` | New connections/sec | count/s | Alert on sudden drops |
| `DropConnection` | `acs_nat` | Dropped connections | count/s | Non-zero = issue |
| `MaxConnection` | `acs_nat` | Peak connections | count | Alert if > 80% capacity |
| `OutRatePercent` | `acs_nat` | Outbound bandwidth utilization | % | Alert > 80% |
| `InRatePercent` | `acs_nat` | Inbound bandwidth utilization | % | Alert > 80% |

### EIP Metrics

See `alicloud-eip-ops/references/monitoring.md` for EIP-specific metrics.

### Network ACL Metrics

Network ACLs don't emit CMS metrics directly. Use **FlowLog** to monitor ACL effectiveness:

## FlowLog — Traffic Monitoring

FlowLog captures network traffic metadata to SLS (Simple Log Service):

| Captured Field | Description |
|----------------|-------------|
| Source/Dest IP | Traffic source and destination |
| Source/Dest Port | Port numbers |
| Protocol | TCP/UDP/ICMP |
| Packets/Bytes | Volume metrics |
| Action | ACCEPT/REJECT (ACL decision) |
| Interface ID | Source/destination network interface |
| Traffic direction | Ingress/Egress |

### Enable FlowLog via CLI

```bash
# Create FlowLog on VPC
aliyun vpc CreateFlowLog \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ResourceId "{{user.vpc_id}}" \
  --ResourceType VPC \
  --ProjectName "vpc-flowlog" \
  --LogStoreName "network-traffic" \
  --TrafficMirror "true"
```

## Alert Best Practices

1. **NAT bandwidth saturation:** Monitor `OutRatePercent` > 80% → upgrade bandwidth
2. **NAT connection exhaustion:** Monitor `MaxConnection` approaching spec limit → add EIPs
3. **EIP bandwidth spikes:** Monitor `BPS` > 85% of purchased → upgrade or optimize traffic
4. **Unusual traffic patterns:** Use FlowLog data to detect anomalies
5. **DDoS detection:** Monitor blackhole events and traffic spikes on public-facing resources

## Multi-Metric Anomaly Inspection

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| NAT 带宽饱和 | `OutRatePercent` + `InRatePercent` | Out/In > 85% 持续 5 min | Critical | NAT 网关带宽成为瓶颈，需升级 |
| NAT 连接耗尽 | `MaxConnection` + `ActiveConnection` | 连接 > 80% 规格上限 AND 持续 10 min | Critical | NAT 连接池即将耗尽，需扩容或加 EIP |
| EIP 流量突降 | `InternetOut` (EIP) + `ActiveConnection` | 流量突降 > 70% AND 连接下降 | Warning | 可能 ECS 异常、SLB 摘除、或 VPC 路由变更 |
| 丢包-带宽背离 | `DropPacketTX` + `InternetOut` | 丢包高但总流量低 | Warning | 可能安全组/NACL 规则变更或 DDoS 防护 |

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| NAT 带宽饱和 | `alicloud-vpc-ops` | — | 升级 NAT 规格或带宽 |
| NAT 连接耗尽 | `alicloud-vpc-ops` | `alicloud-eip-ops` | 添加更多 EIP 扩容 |
| EIP 流量异常 | `alicloud-vpc-ops` | `alicloud-ecs-ops` | 检查 ECS 实例健康状态 |
| 丢包异常 | `alicloud-vpc-ops` | `alicloud-ecs-ops` (安全组) | 排查安全组/NACL 规则 |

## Alert Storm Handling

1. **Aggregate by resource type**: Separate VPC/EIP/NAT alarms
2. **Identify root**: NAT failures often cascade to connectivity issues; check NAT status first
3. **Suppress duplicates**: Group alarms by VPC ID; per-resource secondary alarms are suppressed
