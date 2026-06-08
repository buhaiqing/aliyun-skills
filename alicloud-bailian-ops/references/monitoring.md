# Monitoring — Bailian

## CloudMonitor (CMS) Metrics

### Model Inference Metrics

| Metric | Namespace | Unit | Description |
|--------|-----------|------|-------------|
| `InferenceLatency` | acs_bailian | ms | End-to-end inference latency |
| `TokenInputRate` | acs_bailian | tokens/min | Input token consumption rate |
| `TokenOutputRate` | acs_bailian | tokens/min | Output token consumption rate |
| `RequestRate` | acs_bailian | requests/min | Request throughput |
| `ErrorRate` | acs_bailian | % | Error rate percentage |
| `ThrottledRequests` | acs_bailian | count/min | Rate-limited request count |

### Agent Metrics

| Metric | Namespace | Unit | Description |
|--------|-----------|------|-------------|
| `AgentInvocationLatency` | acs_bailian | ms | Agent response latency |
| `AgentSessionCount` | acs_bailian | count | Active sessions |
| `AgentToolCalls` | acs_bailian | count/min | Tool invocation rate |
| `AgentKnowledgeRetrievals` | acs_bailian | count/min | KB query rate |

### Knowledge Base Metrics

| Metric | Namespace | Unit | Description |
|--------|-----------|------|-------------|
| `IndexingLatency` | acs_bailian | ms | Document indexing time |
| `RetrievalLatency` | acs_bailian | ms | Vector search latency |
| `RetrievalPrecision` | acs_bailian | % | Top-K relevance score |
| `KBStorageUsed` | acs_bailian | MB | Knowledge base size |

## Metric Queries (aliyun CLI)

```bash
# Query inference latency
aliyun cms DescribeMetricList \
  --Namespace "acs_bailian" \
  --MetricName "InferenceLatency" \
  --StartTime "2026-06-01T00:00:00Z" \
  --EndTime "2026-06-08T00:00:00Z" \
  --Dimensions '[{"ModelId":"qwen-turbo"}]'

# Query token consumption
aliyun cms DescribeMetricList \
  --Namespace "acs_bailian" \
  --MetricName "TokenInputRate" \
  --Period 3600

# Query error rate
aliyun cms DescribeMetricList \
  --Namespace "acs_bailian" \
  --MetricName "ErrorRate" \
  --Period 300
```

## Alert Rules

### Critical Alerts (P1)

| Alert | Condition | Notification |
|-------|-----------|--------------|
| High Error Rate | ErrorRate > 5% for 5min | SMS + Email + DingTalk |
| High Latency | P99 Latency > 5000ms for 10min | Email + DingTalk |
| Rate Limiting | ThrottledRequests > 10/min | Email |
| Quota Exhaustion | Quota usage > 80% | Email |

### Warning Alerts (P2)

| Alert | Condition | Notification |
|-------|-----------|--------------|
| Elevated Latency | P99 Latency > 2000ms for 10min | Email |
| Token Spike | Token usage > 2x baseline | Email |
| KB Indexing Failure | Failed index tasks > 0 | Email |

## Log Service (SLS) Integration

### Log Collection

```bash
# Create log project for Bailian
aliyun log createProject --project-name "bailian-logs" --description "Bailian audit logs"

# Create logstore
aliyun log createLogstore --project-name "bailian-logs" --logstore-name "inference-logs" --ttl 30
```

### Key Log Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique request identifier |
| `model_id` | string | Model used |
| `input_tokens` | int | Input token count |
| `output_tokens` | int | Output token count |
| `latency_ms` | int | Response time |
| `status_code` | int | HTTP status |
| `error_code` | string | Error code if failed |
| `user_id` | string | Caller identity |
| `timestamp` | datetime | Request timestamp |

### Sample Log Queries

```sql
-- Error analysis
* | SELECT error_code, COUNT(*) as count 
    WHERE status_code >= 400 
    GROUP BY error_code 
    ORDER BY count DESC

-- Latency percentiles
* | SELECT 
    approx_percentile(latency_ms, 0.50) as p50,
    approx_percentile(latency_ms, 0.99) as p99,
    AVG(latency_ms) as avg
    WHERE status_code = 200

-- Token consumption by model
* | SELECT model_id, 
    SUM(input_tokens) as total_input,
    SUM(output_tokens) as total_output,
    COUNT(*) as request_count
    GROUP BY model_id

-- Error trend
* | SELECT date_trunc('hour', timestamp) as hour,
    COUNT(*) as error_count
    WHERE status_code >= 400
    GROUP BY hour
    ORDER BY hour
```

## Dashboards

### Overview Dashboard

```json
{
  "title": "Bailian Overview",
  "widgets": [
    {"type": "line", "metric": "RequestRate", "title": "Requests/min"},
    {"type": "line", "metric": "TokenInputRate", "title": "Input Tokens/min"},
    {"type": "line", "metric": "TokenOutputRate", "title": "Output Tokens/min"},
    {"type": "gauge", "metric": "ErrorRate", "title": "Error Rate %"},
    {"type": "heatmap", "metric": "InferenceLatency", "title": "Latency Distribution"}
  ]
}
```

### Cost Dashboard

| Widget | Metric | Aggregation |
|--------|--------|-------------|
| Daily Cost | TokenInputRate * Price + TokenOutputRate * Price | SUM/day |
| Cost by Model | Token consumption per model | GROUP BY ModelId |
| Cost Trend | 7-day rolling cost | SUM |
| Budget Alert | Projected monthly cost | Forecast |

## Tracing

### Distributed Trace Fields

| Field | Description |
|-------|-------------|
| `trace_id` | End-to-end trace identifier |
| `span_id` | Current operation span |
| `parent_span_id` | Parent operation reference |
| `operation` | API operation name |
| `start_time` | Span start timestamp |
| `duration_ms` | Span duration |

### Trace Instrumentation

```go
// Add trace headers to requests
headers := map[string]*string{
    "X-Trace-Id": tea.String(traceId),
    "X-Span-Id":  tea.String(spanId),
}
```

## Observability Best Practices

1. **RequestId Propagation**: Always log and propagate RequestId across service calls
2. **Token Monitoring**: Set up alerts for unusual token consumption spikes
3. **Latency Baselines**: Establish P50/P99 baselines per model and alert on deviation
4. **Error Classification**: Distinguish between user errors (4xx) and system errors (5xx)
5. **Cost Attribution**: Tag requests with user/project for chargeback
