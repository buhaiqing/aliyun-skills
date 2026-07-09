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

## Multi-Metric Anomaly Inspection

Execute joint巡检 on SLB instances to identify compound anomaly patterns. Anomaly patterns below use ≥2 metrics combined with detection logic for higher signal-to-noise ratio.

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity | Interpretation |
|---------|-----------------|-----------------|----------|----------------|
| 5xx 异常风暴 | `InstanceUpstreamCode5xx` + `InstanceStatusCode5xx` + `InstanceRt` | 5xx > 50/min AND Rt > 10s 持续 3 min | Critical | 后端服务大面积故障，可能数据库/依赖服务不可用 |
| 连接数-丢包正相关 | `InstanceActiveConnection` + `InstanceDropConnection` | 连接数 > 80% 上限 AND DropConn > 100/min | Critical | SLB 达到连接上限，需扩容规格或启用多实例 |
| 流量-带宽饱和 | `InstanceTrafficTX` + `InstanceDropTrafficTX` | 带宽 > 85% 规格限制 AND Drop 上升 | Warning | 带宽成为瓶颈，需升级规格 |
| 健康检查异常联动 | `BackendServerHealthCheck` + `InstanceUpstreamCode5xx` | 不健康后端 > 30% AND 5xx 突增 | Critical | 后端实例批量异常，可能发布失败或资源过载 |
| RT-QPS 背离 | `InstanceRt` + `InstanceQps` | QPS 不变或下降但 RT 突增 3x+ | Warning | 后端性能退化，可能数据库慢查询/锁等待 |
| 4xx 异常突增 | `InstanceStatusCode4xx` + `InstanceUpstreamCode4xx` | 4xx > 200/min 持续 5 min | Warning | 可能配置错误、证书过期、或客户端行为异常 |

### Execution — CLI

```bash
# Fetch instance-level metrics
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceStatusCode5xx \
  --Dimensions '{"instanceId":"lb-xxx","port":"80","protocol":"http"}' \
  --_period 300 --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"

# Fetch backend health status
aliyun slb DescribeHealthStatus \
  --LoadBalancerId lb-xxx \
  --ListenerPort 80
```

### Recovery & Cross-Skill Delegation

| Pattern | Primary Skill | Delegated Skill | Action |
|---------|--------------|-----------------|--------|
| 5xx 异常风暴 | `alicloud-slb-ops` | `alicloud-ecs-ops` (后端排查) | 检查后端 ECS 健康状态 |
| 连接饱和 | `alicloud-slb-ops` | — | 升级 SLB 规格或启用多实例 |
| 健康检查异常 | `alicloud-slb-ops` | `alicloud-ecs-ops` + `alicloud-vpc-ops` | 检查 ECS 状态 + 网络连通性 |
| RT 突增 | `alicloud-slb-ops` | `alicloud-rds-ops` (如后端为数据库) | 排查数据库慢查询 |

## Alert Storm Handling

When >10 SLB alarms trigger within 5 minutes, enter storm mode:

1. **Aggregate by instanceId + listener**: Coalesce multiple metric alarms of same listener into single event
2. **Identify root resource**: Check if backend servers (ECS) are the root cause (health check failures often cascade)
3. **Suppress duplicates**: Group alarms by listener; suppress per-metric secondary alarms
4. **Focus diagnosis**: If ≥50% of alarms share the same SLB instance, focus on that instance's backend health
5. **Cross-Skill trigger**: If backend-related, immediately delegate to `alicloud-ecs-ops` for instance-level diagnosis

## Alert-Driven Diagnostic Decision Tree

```
[SLB Alarm Fires]
    │
    ├── Step 1: Verify alarm validity — Current metric vs threshold
    │
    ├── Step 2: Check SLB instance status — InstanceState (running/stopped)
    │
    ├── Step 3: Check backend health — DescribeHealthStatus for affected listener
    │       └── If >50% backends abnormal → Root cause = backend health issue
    │
    ├── Step 4: Multi-metric correlation — 5xx + RT + Connection joint analysis
    │       └── Match anomaly pattern from table above
    │
    ├── Step 5: Cross-Skill diagnosis
    │       ├── If backend unhealthy → Delegate to `alicloud-ecs-ops`
    │       ├── If network error → Delegate to `alicloud-vpc-ops`
    │       └── If 5xx from RDS → Delegate to `alicloud-rds-ops`
    │
    └── Step 6: Generate unified diagnostic report
```

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
