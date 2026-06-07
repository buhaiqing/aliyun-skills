# Monitoring & Alerts — ALB

> Version: 1.0.0 | Last Updated: 2026-06-07

## Key Metrics

ALB metrics are reported under the `acs_alb` namespace in CloudMonitor (CMS).

| Metric | Unit | Description | Statistic |
|--------|------|-------------|-----------|
| `ActiveConnection` | count | Number of active connections | Avg, Sum |
| `InactiveConnection` | count | Number of idle connections | Avg, Sum |
| `NewConnection` | count/s | New connections per second | Avg |
| `MaxConnection` | count | Peak concurrent connections | Max |
| `PacketRX` | bytes | Inbound traffic | Sum |
| `PacketTX` | bytes | Outbound traffic | Sum |
| `HealthyHostCount` | count | Number of healthy backend servers | Avg, Min |
| `UnHealthyHostCount` | count | Number of unhealthy backend servers | Avg, Max |
| `RequestCount` | count | Total request count | Sum |
| `QPS` | count/s | Queries per second (for HTTP/HTTPS) | Avg |
| `ResponseLatency` | ms | Request response latency | Avg, P50, P90, P99 |
| `HTTPCode2XX` | count | Count of 2xx responses | Sum |
| `HTTPCode3XX` | count | Count of 3xx responses | Sum |
| `HTTPCode4XX` | count | Count of 4xx responses | Sum |
| `HTTPCode5XX` | count | Count of 5xx responses | Sum |
| `ServerGroupQPS` | count/s | QPS per server group | Avg |
| `ServerGroupResponseLatency` | ms | Response latency per server group | Avg, P99 |
| `RuleQPS` | count/s | QPS per forwarding rule | Avg |
| `ListenerQPS` | count/s | QPS per listener | Avg |
| `ListenerResponseLatency` | ms | Response latency per listener | Avg, P99 |

**Note:** For per-listener and per-rule metrics, the listener/rule ID must be used as a dimension filter.

## Default Alert Thresholds

| Alert Name | Metric | Threshold | Duration | Severity |
|------------|--------|-----------|----------|----------|
| ALB - High 5XX Error Rate | `HTTPCode5XX` | > 10/min | 5 min | Critical |
| ALB - High Latency | `ResponseLatency` (P99) | > 5000ms | 5 min | Critical |
| ALB - No Healthy Backends | `HealthyHostCount` | = 0 | 1 min | Critical |
| ALB - High Unhealthy Hosts | `UnHealthyHostCount` | > 50% of total | 5 min | Warning |
| ALB - Traffic Spike | `RequestCount` | > 200% of baseline | 5 min | Warning |
| ALB - Low Traffic | `RequestCount` | < 50% of baseline | 10 min | Info |

## Dashboard Recommendations

1. **ALB Overview Dashboard:**
   - QPS trend, active connections, unhealthy host count
   - 5XX error rate, P99/P90 latency
   - Inbound/outbound traffic volume

2. **Per-Listener Dashboard:**
   - QPS per listener, response latency per listener
   - HTTP status code distribution per listener
   - Health check status per server group

3. **Per-Server Group Dashboard:**
   - Health status per server
   - Request distribution across servers
   - Weight vs. actual traffic ratio

## Monitoring Commands

```bash
# Query ALB instance-level metrics via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_alb \
  --MetricName ActiveConnection \
  --Dimensions "[{\\"LoadBalancerId\\":\\"{{lb_id}}\\"}]" \
  --StartTime "{{start_time}}" \
  --EndTime "{{end_time}}"

# Query per-listener metrics
aliyun cms DescribeMetricList \
  --Namespace acs_alb \
  --MetricName ListenerQPS \
  --Dimensions "[{\\"LoadBalancerId\\":\\"{{lb_id}}\\",\\"ListenerId\\":\\"{{listener_id}}\\"}]" \
  --StartTime "{{start_time}}" \
  --EndTime "{{end_time}}"

# Query per-server-group health metrics
aliyun cms DescribeMetricList \
  --Namespace acs_alb \
  --MetricName UnHealthyHostCount \
  --Dimensions "[{\\"LoadBalancerId\\":\\"{{lb_id}}\\",\\"ServerGroupId\\":\\"{{sg_id}}\\"}]" \
  --StartTime "{{start_time}}" \
  --EndTime "{{end_time}}"
```

## Anomaly Indicators

| Indicator | Normal Range | Anomaly | Likely Cause |
|-----------|-------------|---------|-------------|
| HealthyHostCount | ≥ 1 | 0 | Backend service down or network issue |
| UnhealthyHostCount | < 20% of total | > 50% | Health check misconfiguration or backend pressure |
| ResponseLatency P99 | < 1000ms | > 5000ms | Backend server overload or slow queries |
| HTTP 5XX Rate | < 1% of requests | > 5% | Backend server errors or gateway issues |
| HTTP 4XX Rate | < 5% of requests | > 20% | Client errors, invalid requests, or ACL blocking |
| QPS vs Baseline | ± 30% | > 200% | Traffic surge or DDoS; < 50% traffic drop |
| ActiveConnection | < 80% max | > 90% max | Connection pool exhaustion