# API 调用计数器

> **Purpose:** 追踪 ACK Skill 执行过程中的 API 调用次数，用于性能监控、成本预估和限流控制。

## 计数器设计

### 计数维度

| 维度 | 说明 | 示例 |
|------|------|------|
| `product` | 阿里云产品 | `cs`, `ecs`, `cms` |
| `operation` | API 操作名称 | `DescribeClusters`, `GetClusterNodes` |
| `region` | 地域 | `cn-hangzhou`, `cn-beijing` |
| `status` | 调用状态 | `success`, `error`, `throttled` |
| `duration_ms` | 调用耗时 | 150 |

### 计数器接口

```go
// APICallCounter API 调用计数器接口
type APICallCounter interface {
    // Increment 增加指定操作的计数
    Increment(product, operation string)

    // IncrementWithDuration 增加计数并记录耗时
    IncrementWithDuration(product, operation string, durationMs int64)

    // GetCount 获取指定操作的调用次数
    GetCount(product, operation string) int64

    // GetTotal 获取总调用次数
    GetTotal() int64

    // GetSummary 获取调用摘要报告
    GetSummary() APICallSummary

    // Reset 重置计数器
    Reset()
}

// APICallSummary API 调用摘要
type APICallSummary struct {
    TotalCalls    int64                      `json:"total_calls"`
    SuccessCount  int64                      `json:"success_count"`
    ErrorCount    int64                      `json:"error_count"`
    ThrottledCount int64                     `json:"throttled_count"`
    TotalDuration int64                      `json:"total_duration_ms"`
    ByProduct     map[string]ProductSummary  `json:"by_product"`
    Timestamp     string                     `json:"timestamp"`
}

// ProductSummary 产品级摘要
type ProductSummary struct {
    Product       string          `json:"product"`
    CallCount     int64           `json:"call_count"`
    SuccessRate   float64         `json:"success_rate"`
    AvgDurationMs float64         `json:"avg_duration_ms"`
    Operations    []OperationSummary `json:"operations"`
}

// OperationSummary 操作级摘要
type OperationSummary struct {
    Operation     string  `json:"operation"`
    Count         int64   `json:"count"`
    SuccessCount  int64   `json:"success_count"`
    ErrorCount    int64   `json:"error_count"`
    AvgDurationMs float64 `json:"avg_duration_ms"`
}
```

## 在 SKILL.md 中的使用

### 执行前初始化

```go
// 初始化计数器
counter := NewAPICallCounter()
counter.Reset()

// 记录开始时间
startTime := time.Now()
```

### API 调用时记录

```go
// 包装 API 调用并记录
func callAPIWithCounter(counter APICallCounter, product, operation string, fn func() error) error {
    start := time.Now()
    err := fn()
    duration := time.Since(start).Milliseconds()

    status := "success"
    if err != nil {
        if isThrottledError(err) {
            status = "throttled"
        } else {
            status = "error"
        }
    }

    counter.IncrementWithStatus(product, operation, status, duration)
    return err
}

// 使用示例
callAPIWithCounter(counter, "cs", "DescribeClusters", func() error {
    resp, err := client.DescribeClusters(request)
    // ...
    return err
})
```

### 执行后输出报告

```go
// 生成并输出报告
summary := counter.GetSummary()
report := map[string]interface{}{
    "execution_summary": map[string]interface{}{
        "total_duration_ms": time.Since(startTime).Milliseconds(),
        "api_calls": summary,
    },
}

jsonReport, _ := json.MarshalIndent(report, "", "  ")
fmt.Println(string(jsonReport))
```

## 输出示例

```json
{
  "execution_summary": {
    "total_duration_ms": 15320,
    "api_calls": {
      "total_calls": 15,
      "success_count": 14,
      "error_count": 0,
      "throttled_count": 1,
      "total_duration_ms": 8200,
      "by_product": {
        "cs": {
          "product": "cs",
          "call_count": 10,
          "success_rate": 100.0,
          "avg_duration_ms": 450,
          "operations": [
            {
              "operation": "DescribeClusterDetail",
              "count": 3,
              "success_count": 3,
              "error_count": 0,
              "avg_duration_ms": 380
            },
            {
              "operation": "DescribeClusterNodes",
              "count": 5,
              "success_count": 5,
              "error_count": 0,
              "avg_duration_ms": 420
            },
            {
              "operation": "ScaleOutCluster",
              "count": 2,
              "success_count": 2,
              "error_count": 0,
              "avg_duration_ms": 580
            }
          ]
        },
        "ecs": {
          "product": "ecs",
          "call_count": 3,
          "success_rate": 66.7,
          "avg_duration_ms": 620,
          "operations": [
            {
              "operation": "DescribeInstances",
              "count": 3,
              "success_count": 2,
              "error_count": 0,
              "throttled_count": 1,
              "avg_duration_ms": 620
            }
          ]
        },
        "cms": {
          "product": "cms",
          "call_count": 2,
          "success_rate": 100.0,
          "avg_duration_ms": 210,
          "operations": [
            {
              "operation": "DescribeMetricList",
              "count": 2,
              "success_count": 2,
              "error_count": 0,
              "avg_duration_ms": 210
            }
          ]
        }
      },
      "timestamp": "2026-05-20T10:00:00Z"
    }
  }
}
```

## 集成到巡检报告

在 [SKILL.md](../SKILL.md) 的智能巡检章节中，API 调用计数器输出作为执行摘要的一部分：

```yaml
# 巡检报告结构
inspection_report:
  metadata:
    cluster_id: "c-xxx"
    inspection_time: "2026-05-20T10:00:00Z"
    duration_ms: 15320
  score: 85
  dimensions: [...]
  api_calls:  # <-- 引用 api-call-counter.md 输出
    total_calls: 15
    success_rate: 93.3%
    by_product:
      cs: { call_count: 10, avg_duration_ms: 450 }
      ecs: { call_count: 3, avg_duration_ms: 620 }
      cms: { call_count: 2, avg_duration_ms: 210 }
```

## Bash 实现参考

```bash
#!/bin/bash
# api-call-counter.sh
# 简单的 API 调用计数器实现

COUNTER_FILE="/tmp/api_counter_$$.json"

# 初始化计数器
init_counter() {
    echo '{"calls":[],"start_time":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$COUNTER_FILE"
}

# 记录 API 调用
record_call() {
    local product="$1"
    local operation="$2"
    local status="${3:-success}"
    local duration_ms="${4:-0}"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    local entry=$(jq -n \
        --arg product "$product" \
        --arg operation "$operation" \
        --arg status "$status" \
        --argjson duration "$duration_ms" \
        --arg timestamp "$timestamp" \
        '{product: $product, operation: $operation, status: $status, duration_ms: $duration, timestamp: $timestamp}')

    jq --argjson entry "$entry" '.calls += [$entry]' "$COUNTER_FILE" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"
}

# 获取摘要
get_summary() {
    jq '{
        total_calls: (.calls | length),
        success_count: ([.calls[] | select(.status == "success")] | length),
        error_count: ([.calls[] | select(.status == "error")] | length),
        throttled_count: ([.calls[] | select(.status == "throttled")] | length),
        by_product: (group_by(.product) | map({
            product: .[0].product,
            call_count: length,
            avg_duration_ms: (map(.duration_ms) | add / length)
        }))
    }' "$COUNTER_FILE"
}

# 清理
cleanup() {
    rm -f "$COUNTER_FILE"
}

# 使用示例
init_counter

# 记录调用示例
record_call "cs" "DescribeClusters" "success" 450
record_call "cs" "DescribeClusterNodes" "success" 420
record_call "ecs" "DescribeInstances" "throttled" 1000

# 输出摘要
get_summary

cleanup
```
