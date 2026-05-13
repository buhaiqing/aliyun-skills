# Monitoring Alibaba Cloud SLB

## Key Metrics

SLB metrics are available through CloudMonitor (CMS). The metric namespace is `acs_slb`.

### Instance-Level Metrics

| Metric Name | Description | Unit | Dimensions |
|-------------|-------------|------|------------|
| `InstanceActiveConnection` | Active connections | Count | instanceId, port, protocol |
| `InstanceDropConnection` | Dropped connections | Count | instanceId, port, protocol |
| `InstanceDropPacketRX` | Dropped inbound packets | Count | instanceId, port, protocol |
| `InstanceDropPacketTX` | Dropped outbound packets | Count | instanceId, port, protocol |
| `InstanceDropTrafficRX` | Dropped inbound traffic | bits/s | instanceId, port, protocol |
| `InstanceDropTrafficTX` | Dropped outbound traffic | bits/s | instanceId, port, protocol |
| `InstanceInactiveConnection` | Inactive connections | Count | instanceId, port, protocol |
| `InstanceMaxConnection` | Maximum connections | Count | instanceId, port, protocol |
| `InstanceNewConnection` | New connections per second | Count/s | instanceId, port, protocol |
| `InstancePacketRX` | Inbound packets per second | Count/s | instanceId, port, protocol |
| `InstancePacketTX` | Outbound packets per second | Count/s | instanceId, port, protocol |
| `InstanceQps` | Queries per second (HTTP/HTTPS) | Count/s | instanceId, port, protocol |
| `InstanceRt` | Average response time (HTTP/HTTPS) | ms | instanceId, port, protocol |
| `InstanceStatusCode2xx` | 2xx status code count | Count/s | instanceId, port, protocol |
| `InstanceStatusCode3xx` | 3xx status code count | Count/s | instanceId, port, protocol |
| `InstanceStatusCode4xx` | 4xx status code count | Count/s | instanceId, port, protocol |
| `InstanceStatusCode5xx` | 5xx status code count | Count/s | instanceId, port, protocol |
| `InstanceTrafficRX` | Inbound bandwidth | bits/s | instanceId, port, protocol |
| `InstanceTrafficTX` | Outbound bandwidth | bits/s | instanceId, port, protocol |
| `InstanceUpstreamCode4xx` | Backend 4xx count | Count/s | instanceId, port, protocol |
| `InstanceUpstreamCode5xx` | Backend 5xx count | Count/s | instanceId, port, protocol |
| `InstanceUpstreamRt` | Backend response time | ms | instanceId, port, protocol |

### Backend Server Metrics

| Metric Name | Description | Unit | Dimensions |
|-------------|-------------|------|------------|
| `BackendServerConnection` | Connections to backend | Count | instanceId, port, protocol, backendServer |
| `BackendServerHealthCheck` | Health check status | - | instanceId, port, protocol, backendServer |
| `BackendServerQps` | QPS to backend | Count/s | instanceId, port, protocol, backendServer |
| `BackendServerRt` | Backend response time | ms | instanceId, port, protocol, backendServer |

## Querying Metrics via CLI

```bash
# Query instance traffic (requires CloudMonitor access)
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceTrafficRX \
  --Dimensions '{"instanceId":"lb-bp67acfmxazb4ph***"}' \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z"

# Query QPS for a specific listener
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceQps \
  --Dimensions '{"instanceId":"lb-bp67acfmxazb4ph***","port":"80","protocol":"http"}' \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z"
```

> **Note:** CloudMonitor metrics require the `alicloud-cms-ops` skill for detailed
> metric queries and alert configuration.

## Health Check Monitoring

```bash
# Check backend server health status
aliyun slb DescribeHealthStatus \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80

# Output fields:
# $.BackendServers.BackendServer[].ServerId - Backend server ID
# $.BackendServers.BackendServer[].Port - Backend port
# $.BackendServers.BackendServer[].HealthStatus - normal / abnormal
```

## Alert Recommendations

| Alert | Metric | Threshold | Severity |
|-------|--------|-----------|----------|
| High backend 5xx rate | `InstanceUpstreamCode5xx` | > 10/min | Critical |
| High response time | `InstanceRt` | > 5000ms | Warning |
| Backend unhealthy | `BackendServerHealthCheck` | abnormal | Critical |
| High connection drops | `InstanceDropConnection` | > 100/min | Warning |
| Bandwidth saturation | `InstanceTrafficTX` | > 80% of limit | Warning |
| SSL certificate expiry | Certificate expire time | < 30 days | Warning |

## Access Logs

SLB supports access log delivery to OSS:

```bash
# Enable access logs (requires OSS bucket)
aliyun slb SetAccessLogsDownloadAttribute \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --LogsDownloadStatus on \
  --LogProject slb-log-project \
  --LogStore slb-log-store
```

> **Note:** Access log configuration requires the `alicloud-oss-ops` skill for
> OSS bucket management.

## Fine-Grained Monitoring

Enable second-level monitoring for more granular metrics:

```bash
# Enable high-definition monitor
aliyun slb EnableHighDefinationMonitor --RegionId cn-hangzhou

# Modify monitor configuration
aliyun slb ModifyHighDefinationMonitor \
  --RegionId cn-hangzhou \
  --LogProject slb-monitor \
  --LogStore slb-monitor-store
```
