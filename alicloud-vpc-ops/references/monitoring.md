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

| Pattern | Detection | Severity | Delegated | Action |
|---------|-----------|----------|-----------|--------|
| NAT 带宽饱和 | Out/InRatePercent > 85% for 5min | Critical | — | 升级 NAT 规格或带宽 |
| NAT 连接耗尽 | MaxConnection > 80% for 10min | Critical | `alicloud-eip-ops` | 添加更多 EIP 扩容 |
| EIP 流量突降 | 流量突降 > 70% + 连接下降 | Warning | `alicloud-ecs-ops` | 检查 ECS 实例健康状态 |
| 丢包-带宽背离 | 丢包高但总流量低 | Warning | `alicloud-ecs-ops` (安全组) | 排查安全组/NACL 规则 |

## Alert Storm Handling

1. **Aggregate by resource type**: Separate VPC/EIP/NAT alarms
2. **Identify root**: NAT failures often cascade to connectivity issues; check NAT status first
3. **Suppress duplicates**: Group alarms by VPC ID; per-resource secondary alarms are suppressed

## Advanced Observability

For Metrics→Logs→Traces linkage and FlowLog deep-dive queries, see [advanced/observability.md](advanced/observability.md).
