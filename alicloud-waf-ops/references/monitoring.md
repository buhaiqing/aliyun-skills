# Monitoring — Alibaba Cloud WAF

## CloudMonitor Integration

WAF sends events to Alibaba Cloud Monitor (CMS). Agent can poll or subscribe to alarms.

## Key Metrics

| Metric | Type | Unit | Threshold | Action |
|--------|------|------|-----------|--------|
| `waf_Access_Total` | Gauge | Count/s | Normal traffic | Informational |
| `waf_CCPRequest_Total` | Gauge | Count/s | > 100 | Investigate CC attack |
| `waf_Auth_Bypass` | Gauge | Count/s | > 0 | Check if bypasses are intentional |
| `waf_DDoS_Bandwidth` | Gauge | bps | > 10Mbps | May indicate DDoS attack |
| `waf_InboundBlock_Total` | Gauge | Count/s | > 50 | Review blocked requests |
| `waf_RuleHit_Total` | Gauge | Count/s | > 100 | Review defense rules |

## Metric Query Pattern

```bash
# Query WAF metrics from CloudMonitor
aliyun cms DescribeMetricList \
  --Namespace acs_waf \
  --MetricName waf_Access_Total \
  --Dimensions '[{"instanceId":"waf_xxx"}]' \
  --StartTime 2024-01-01T00:00:00Z \
  --EndTime 2024-01-01T01:00:00Z \
  --Period 60
```

## Alarm Rules

### High Traffic Volume Alert

```bash
# Create alarm for high traffic
aliyun cms PutMetricRuleTargets \
  --RuleId waf-high-traffic \
  --Namespace acs_waf \
  --MetricName waf_Access_Total \
  --Operator GreaterThanThreshold \
  --Threshold 1000 \
  --Period 300
```

### CC Attack Alert

```bash
# Create alarm for potential CC attack
aliyun cms PutMetricRuleTargets \
  --RuleId waf-cc-attack \
  --Namespace acs_waf \
  --MetricName waf_CCPRequest_Total \
  --Operator GreaterThanThreshold \
  --Threshold 100 \
  --Period 300
```

## Log Analytics (SLS Integration)

### Query WAF Logs via SLS

WAF logs can be delivered to SLS for advanced analytics:

```bash
# Query WAF access logs from SLS
aliyun logs GetLogs \
  --project sls-project \
  --logstore waf-access-log \
  --topic "" \
  --from 2024-01-01T00:00:00+08:00 \
  --to 2024-01-01T01:00:00+08:00 \
  --query "status: 500 | SELECT * LIMIT 100"
```

### Common Log Queries

```sql
-- Blocked requests by IP
* AND action: block | SELECT client_ip, COUNT(*) as blocked_count GROUP BY client_ip ORDER BY blocked_count DESC LIMIT 20

-- High-risk requests
* AND severity: high | SELECT timestamp, rule_name, client_ip, uri

-- CC attack patterns
* AND rule_name: cc_attack | SELECT client_ip, uri, COUNT(*) as request_count GROUP BY client_ip, uri HAVING request_count > 50
```

## Dashboard Metrics

| Dashboard | Key Metrics | Refresh Rate |
|-----------|-------------|--------------|
| WAF Overview | Total requests, blocked requests, top IPs | 1 min |
| Defense Analysis | Rule hits by type, attack patterns | 5 min |
| Domain Performance | Request rate, error rate per domain | 1 min |
| Threat Intelligence | Top attackers, blocked IPs, geo distribution | 5 min |

## Health Check Integration

WAF can integrate with SLB health checks to ensure origin availability:

```bash
# Check SLB health for origin servers
aliyun slb DescribeHealthStatus \
  --LoadBalancerId lb_xxx \
  --RegionId cn-hangzhou
```
