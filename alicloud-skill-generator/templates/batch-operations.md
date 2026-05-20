# 批量并行操作模板

通用批量操作模板，支持阿里云资源批量管理。

## 1. 模板结构

```
batch-operation/
├── config/
│   ├── batch.yaml          # 批处理配置
│   └── resources.yaml      # 资源清单
├── scripts/
│   ├── parallel_cli.sh     # CLI 并行脚本
│   ├── parallel_sdk.py     # SDK 并行脚本
│   └── parallel_go.go      # Go SDK 并行脚本
├── output/
│   ├── success.json        # 成功记录
│   ├── failed.json         # 失败记录
│   └── report.md           # 执行报告
└── README.md
```

## 2. CLI 并行示例 (xargs -P)

### Bash 模板

```bash
#!/bin/bash
# parallel_cli.sh - 阿里云资源批量操作模板

# 配置参数
MAX_PARALLEL=${MAX_PARALLEL:-10}
REGION=${REGION:-cn-hangzhou}
INPUT_FILE="${1:-resources.txt}"
OUTPUT_DIR="${OUTPUT_DIR:-./output}"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 并行执行函数
process_resource() {
    local resource_id=$1
    local operation=$2
    local log_file="$OUTPUT_DIR/${resource_id}.log"
    
    echo "[$(date)] Processing: $resource_id"
    
    # 执行操作 (示例: 查询实例状态)
    if aliyun ecs DescribeInstances \
        --RegionId "$REGION" \
        --InstanceIds "[\"$resource_id\"]" \
        --output cols=InstanceId,Status rows=Instances.Instance[] > "$log_file" 2>&1; then
        echo "$resource_id" >> "$OUTPUT_DIR/success.txt"
        echo "[SUCCESS] $resource_id"
    else
        echo "$resource_id" >> "$OUTPUT_DIR/failed.txt"
        echo "[FAILED] $resource_id"
    fi
}

export -f process_resource
export REGION OUTPUT_DIR

# 使用 xargs 并行执行
cat "$INPUT_FILE" | xargs -P "$MAX_PARALLEL" -I {} bash -c 'process_resource "$@"' _ {}

# 生成报告
echo "# Batch Operation Report" > "$OUTPUT_DIR/report.md"
echo "Time: $(date)" >> "$OUTPUT_DIR/report.md"
echo "Parallel: $MAX_PARALLEL" >> "$OUTPUT_DIR/report.md"
echo "Success: $(wc -l < "$OUTPUT_DIR/success.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/report.md"
echo "Failed: $(wc -l < "$OUTPUT_DIR/failed.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/report.md"
```

### GNU Parallel 模板 (高级)

```bash
#!/bin/bash
# 使用 GNU Parallel 进行更精细的并行控制

# 配置
JOBS=${JOBS:-10}
MEM_LIMIT=${MEM_LIMIT:-1G}
TIMEOUT=${TIMEOUT:-300}

cat resources.txt | parallel \
    --jobs "$JOBS" \
    --memfree "$MEM_LIMIT" \
    --timeout "$TIMEOUT" \
    --joblog output/parallel.log \
    --results output/ \
    --progress \
    --bar \
    ./process_single.sh {}
```

## 3. SDK Goroutine + Semaphore 示例

### Go 模板

```go
package main

import (
    "context"
    "fmt"
    "os"
    "sync"
    "time"

    "github.com/aliyun/alibaba-cloud-sdk-go/services/ecs"
    "golang.org/x/sync/semaphore"
)

// BatchConfig 批处理配置
type BatchConfig struct {
    MaxConcurrency int64
    Timeout        time.Duration
    RetryCount     int
    RegionID       string
}

// BatchResult 批量操作结果
type BatchResult struct {
    ResourceID string
    Success    bool
    Error      error
    Duration   time.Duration
}

// BatchProcessor 批处理器
type BatchProcessor struct {
    client    *ecs.Client
    config    *BatchConfig
    sem       *semaphore.Weighted
    results   []BatchResult
    mu        sync.Mutex
}

// NewBatchProcessor 创建批处理器
func NewBatchProcessor(config *BatchConfig) (*BatchProcessor, error) {
    client, err := ecs.NewClientWithAccessKey(
        config.RegionID,
        os.Getenv("ALICLOUD_ACCESS_KEY"),
        os.Getenv("ALICLOUD_SECRET_KEY"),
    )
    if err != nil {
        return nil, err
    }

    return &BatchProcessor{
        client: client,
        config: config,
        sem:    semaphore.NewWeighted(config.MaxConcurrency),
    }, nil
}

// Process 处理资源列表
func (bp *BatchProcessor) Process(ctx context.Context, resourceIDs []string) []BatchResult {
    var wg sync.WaitGroup
    bp.results = make([]BatchResult, 0, len(resourceIDs))

    for _, id := range resourceIDs {
        wg.Add(1)
        go func(resourceID string) {
            defer wg.Done()
            
            // 获取信号量，控制并发
            if err := bp.sem.Acquire(ctx, 1); err != nil {
                bp.addResult(BatchResult{
                    ResourceID: resourceID,
                    Success:    false,
                    Error:      fmt.Errorf("semaphore acquire failed: %v", err),
                })
                return
            }
            defer bp.sem.Release(1)

            // 执行操作
            result := bp.executeOperation(ctx, resourceID)
            bp.addResult(result)
        }(id)
    }

    wg.Wait()
    return bp.results
}

// executeOperation 执行单个资源操作
func (bp *BatchProcessor) executeOperation(ctx context.Context, resourceID string) BatchResult {
    start := time.Now()
    
    // 创建带超时的上下文
    ctx, cancel := context.WithTimeout(ctx, bp.config.Timeout)
    defer cancel()

    // 示例: 查询实例状态
    request := ecs.CreateDescribeInstancesRequest()
    request.InstanceIds = fmt.Sprintf("[\"%s\"]", resourceID)
    
    response, err := bp.client.DescribeInstances(request)
    
    duration := time.Since(start)
    
    if err != nil {
        // 重试逻辑
        for i := 0; i < bp.config.RetryCount; i++ {
            time.Sleep(time.Second * time.Duration(i+1))
            response, err = bp.client.DescribeInstances(request)
            if err == nil {
                break
            }
        }
    }

    return BatchResult{
        ResourceID: resourceID,
        Success:    err == nil && len(response.Instances.Instance) > 0,
        Error:      err,
        Duration:   duration,
    }
}

func (bp *BatchProcessor) addResult(result BatchResult) {
    bp.mu.Lock()
    bp.results = append(bp.results, result)
    bp.mu.Unlock()
}

// 使用示例
func main() {
    config := &BatchConfig{
        MaxConcurrency: 10,
        Timeout:        30 * time.Second,
        RetryCount:     3,
        RegionID:       "cn-hangzhou",
    }

    processor, err := NewBatchProcessor(config)
    if err != nil {
        panic(err)
    }

    resourceIDs := []string{"i-xxx1", "i-xxx2", "i-xxx3"}
    
    ctx := context.Background()
    results := processor.Process(ctx, resourceIDs)

    // 输出结果
    var success, failed int
    for _, r := range results {
        if r.Success {
            success++
            fmt.Printf("[OK] %s (%.2fs)\n", r.ResourceID, r.Duration.Seconds())
        } else {
            failed++
            fmt.Printf("[FAIL] %s: %v\n", r.ResourceID, r.Error)
        }
    }
    
    fmt.Printf("\nSummary: Success=%d, Failed=%d\n", success, failed)
}
```

### Python 模板 ( asyncio + semaphore )

```python
#!/usr/bin/env python3
"""
Python 批量操作模板 - 使用 asyncio + semaphore
"""
import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta
import aiohttp


@dataclass
class BatchConfig:
    max_concurrency: int = 10
    timeout: int = 30
    retry_count: int = 3
    region_id: str = "cn-hangzhou"


@dataclass
class BatchResult:
    resource_id: str
    success: bool
    error: Optional[Exception] = None
    duration: timedelta = timedelta(0)


class BatchProcessor:
    def __init__(self, config: BatchConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrency)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def process(self, resource_ids: List[str]) -> List[BatchResult]:
        tasks = [
            self._process_single(rid) for rid in resource_ids
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_single(self, resource_id: str) -> BatchResult:
        async with self.semaphore:
            start = datetime.now()
            
            # 重试逻辑
            error = None
            for attempt in range(self.config.retry_count + 1):
                try:
                    # 执行操作
                    await self._execute_operation(resource_id)
                    return BatchResult(
                        resource_id=resource_id,
                        success=True,
                        duration=datetime.now() - start
                    )
                except Exception as e:
                    error = e
                    if attempt < self.config.retry_count:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
            
            return BatchResult(
                resource_id=resource_id,
                success=False,
                error=error,
                duration=datetime.now() - start
            )
    
    async def _execute_operation(self, resource_id: str):
        """执行具体操作，由子类实现"""
        # 这里调用阿里云 SDK
        pass


# 使用示例
async def main():
    config = BatchConfig(max_concurrency=10)
    resource_ids = ["i-xxx1", "i-xxx2", "i-xxx3"]
    
    async with BatchProcessor(config) as processor:
        results = await processor.process(resource_ids)
        
        success = sum(1 for r in results if isinstance(r, BatchResult) and r.success)
        failed = len(results) - success
        
        print(f"Summary: Success={success}, Failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
```

## 4. 并发控制参数模板

### 配置文件 (batch.yaml)

```yaml
# 批处理配置模板
batch:
  name: "ecs-batch-operation"
  description: "批量操作 ECS 实例"
  
  # 并发控制
  concurrency:
    max_parallel: 10          # 最大并行数
    max_qps: 50               # 最大 QPS
    semaphore_size: 10        # 信号量大小
    
  # 超时设置
  timeout:
    operation_timeout: 30s    # 单次操作超时
    total_timeout: 10m        # 总超时
    
  # 重试策略
  retry:
    max_retries: 3
    backoff_strategy: exponential  # exponential / linear / fixed
    initial_delay: 1s
    max_delay: 30s
    
  # 熔断配置
  circuit_breaker:
    enabled: true
    failure_threshold: 50%    # 失败率阈值
    reset_timeout: 60s        # 重置时间
    
  # 限流配置
  rate_limit:
    enabled: true
    requests_per_second: 50
    burst_size: 10
    
  # 资源限制
  resource_limits:
    max_memory: 1GB
    max_cpu: 2
```

## 5. 失败隔离策略

### 失败处理模板

```go
// FailureIsolation 失败隔离策略
type FailureIsolation struct {
    failedResources map[string]int
    circuitOpen     bool
    mu             sync.RWMutex
}

// IsCircuitOpen 检查熔断状态
func (fi *FailureIsolation) IsCircuitOpen() bool {
    fi.mu.RLock()
    defer fi.mu.RUnlock()
    return fi.circuitOpen
}

// RecordFailure 记录失败
func (fi *FailureIsolation) RecordFailure(resourceID string) bool {
    fi.mu.Lock()
    defer fi.mu.Unlock()
    
    fi.failedResources[resourceID]++
    
    // 检查是否触发熔断
    totalFailures := 0
    for _, count := range fi.failedResources {
        totalFailures += count
    }
    
    // 如果失败率超过阈值，打开熔断
    if totalFailures > threshold {
        fi.circuitOpen = true
        return true
    }
    return false
}

// SkipOnFailure 失败时跳过策略
func SkipOnFailure(resourceID string, err error) bool {
    // 记录失败但不影响其他任务
    log.Printf("[SKIP] Resource %s failed: %v", resourceID, err)
    return true
}

// AbortOnCriticalFailure 关键失败时中止
func AbortOnCriticalFailure(err error) bool {
    // 检查是否为关键错误
    if isCriticalError(err) {
        log.Fatal("[ABORT] Critical error occurred, aborting batch operation")
        return false
    }
    return true
}
```

### 失败重试队列

```yaml
# 失败处理配置
failure_handling:
  # 立即重试
  immediate_retry:
    enabled: true
    max_attempts: 3
    
  # 延迟重试队列
  delayed_retry:
    enabled: true
    queue_type: redis  # redis / memory / file
    retry_intervals:
      - 30s
      - 5m
      - 30m
      - 2h
      
  # 死信队列
  dead_letter:
    enabled: true
    max_age: 7d
    storage: s3  # s3 / local / db
    
  # 失败通知
  notification:
    enabled: true
    channels:
      - webhook
      - email
      - sms
```

## 使用指南

1. **选择并行工具**: 
   - 简单场景: `xargs -P`
   - 复杂场景: GNU Parallel
   - SDK 集成: Goroutine + Semaphore

2. **配置并发参数**:
   - 根据 API 限制调整 `max_parallel`
   - 设置合理的超时时间
   - 配置熔断保护

3. **失败处理**:
   - 启用重试机制
   - 配置死信队列
   - 设置失败通知
