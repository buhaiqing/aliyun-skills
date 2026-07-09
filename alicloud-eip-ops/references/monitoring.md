# Monitoring EIP

> **Purpose:** EIP monitoring metrics, alerts, and best practices.

## Key Metrics (Cloud Monitor CMS)

| Metric | Description | Unit | Alarm Threshold (suggested) |
|--------|-------------|------|----------------------------|
| `IntranetIn` | Inbound traffic to EIP | bytes/s | Monitor, threshold depends on workload |
| `IntranetOut` | Outbound traffic from EIP | bytes/s | Monitor, threshold depends on workload |
| `InternetIn` | Inbound internet traffic | bytes/s | Alert if > 80% bandwidth |
| `InternetOut` | Outbound internet traffic | bytes/s | Alert if > 80% bandwidth |
| `ActiveConnection` | Active connections on EIP | count | High = may need more EIPs or bandwidth upgrade |
| `NewConnection` | New connections per second | rate/s | Sudden spikes may indicate DDoS |
| `DropPacketRX` | Dropped inbound packets | count/s | Non-zero may indicate firewall/security group blocking |
| `DropPacketTX` | Dropped outbound packets | count/s | Non-zero may indicate bandwidth saturation |
| `DropConnection` | Dropped connections | count/s | Indicates connection limit reached |
| `DropPacketBlackHole` | Packets dropped due to blackhole | count/s | DDoS protection triggered |
| `BPS` (bits per second) | Bandwidth utilization | bps | Alert if > 85% of purchased bandwidth |
| `PPS` (packets per second) | Packet rate | pps | Monitor for anomaly detection |

**CMS Namespace:** `acs_eip` or `acs_eip_intl_internet` (international)

## Alert Configuration Example

```bash
# Create alarm rule for bandwidth utilization > 80%
aliyun cms PutAlarmRule \
  --Name "EIP-Bandwidth-Warning" \
  --Namespace acs_eip \
  --MetricName InternetOut \
  --ComparisonOperator GreaterThanOrEqualToThreshold \
  --Threshold 80 \
  --Statistics Average \
  --EvaluationCount 3 \
  --Level WARN \
  --ContactGroups "ops-team"
```

## Monitoring Best Practices

1. **Bandwidth trending:** Track daily peak bandwidth to right-size EIP capacity
2. **Connection count:** Monitor active connections per EIP (limit ~30K per IP)
3. **Packet drops:** Investigate non-zero DropPacket metrics for potential issues
4. **Cost optimization:** For PayByTraffic EIPs with low utilization, consider PayByBandwidth
5. **Blackhole alerts:** Set up immediate alerts for blackhole events (DDoS indicator)
6. **Dashboard:** Create CMS dashboard combining EIP bandwidth, connections, and drops by resource group

## Multi-Metric Anomaly Inspection

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| 带宽-连接双高压 | `InternetOut` + `ActiveConnection` | 带宽 > 85% AND 连接 > 25K | Critical | EIP 接近容量和连接双上限，需扩容或分流 |
| 流量突降异常 | `InternetOut` + `NewConnection` + `ActiveConnection` | 流量较 1h 均值下降 > 70% AND 连接骤降 | Warning | 可能 ECS/NAT/SLB 异常、安全组变更、或 DNS 变更 |
| Blackhole DDoS | `DropPacketBlackHole` + `InternetIn` | Blackhole > 0 AND 入流量突增 5x+ | Critical | 遭遇 DDoS 攻击，流量已触发黑洞阈值 |
| 丢包-连接背离 | `DropConnection` + `ActiveConnection` | 丢连接数高但活跃连接低 | Warning | 可能连接耗尽、客户端超时重试、或后端服务不可达 |
| 带宽突增 | `BPS` + `InternetOut` | 带宽 5 min 内从 <30% 到 >90% | Warning | 可能异常流量、爬虫、或大文件下载激增 |
| 丢包持续增长 | `DropPacketTX` (6h 趋势) | 丢包率线性增长 | Critical | 带宽饱和趋势，即将影响业务 |

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| 带宽-连接双高 | `alicloud-eip-ops` | — | 升级带宽或添加新 EIP |
| 流量突降 | `alicloud-eip-ops` | `alicloud-ecs-ops` / `alicloud-slb-ops` | 检查绑定目标资源健康 |
| Blackhole DDoS | `alicloud-eip-ops` | `alicloud-cms-ops` (DDoS 告警) | 启用 DDoS 高防或 WAF |
| 带宽突增 | `alicloud-eip-ops` | `alicloud-ecs-ops` (排查应用) | 排查异常应用/爬虫 |

## Alert Storm Handling

1. **Aggregate by EIP AllocationId**: Multiple metric alarms on same EIP → single event
2. **Identify root**: Blackhole always takes priority; it's the symptom, not the root cause
3. **Suppress by bandwidth plan**: If EIPs share a bandwidth plan, plan-level alarms suppress per-EIP alarms
