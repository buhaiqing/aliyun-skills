# API 调用计数框架实现

> **Purpose:** 实现阿里云 Skill 的 API 调用计数与成本追踪，支持成本优化和预算管理
> **Version:** 1.0.0
> **Last Updated:** 2026-05-20
> **Status:** P0 - 高优先级

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [架构设计](#2-架构设计)
3. [拦截器实现](#3-拦截器实现)
4. [统计存储](#4-统计存储)
5. [报表生成](#5-报表生成)
6. [成本预算联动](#6-成本预算联动)
7. [实现示例](#7-实现示例)
8. [度量与验证](#8-度量与验证)

---

## 1. 执行摘要

### 1.1 目标指标

| 指标 | 当前状态 | 目标状态 |
|------|----------|----------|
| API 调用计数 | 无 | 全量追踪 |
| 分产品统计 | 无 | 按产品明细 |
| 成本归因 | 无 | 按用户/任务 |
| 报表生成 | 无 | 每日/每周自动 |

### 1.2 核心功能

```yaml
API 调用计数框架:
  - 调用拦截器: CLI/SDK 调用前自动计数
  - 统计存储: JSON 文件 + SQLite 双模式
  - 报表生成: 每日/每周/每月汇总
  - 成本预算联动: 超阈值预警与限流
```

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Skill 调用层                           │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│   │ ECS Skill │  │ RDS Skill │  │ CMS Skill │              │
│   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
└─────────┼──────────────┼──────────────┼─────────────────────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   API 调用拦截器                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  统一拦截层 (CLI Wrapper / SDK Hook)                  │  │
│  │  - 调用前: 计数 + 1                                  │  │
│  │  - 调用后: 记录耗时 + 状态码                         │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ 内存缓冲    │ │ 统计文件    │ │ SQLite DB   │
    │ (RingBuffer)│ │ (JSON)      │ │ (可选)      │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 2.2 数据流

```
调用发起
    │
    ▼
┌─────────────┐
│ 拦截器拦截  │
└─────────────┘
    │
    ├───> 计数器 +1
    │
    ├───> 记录元数据 (产品, 操作, 时间戳, Region)
    │
    ├───> 检查预算阈值
    │
    ▼
原始调用执行 (CLI/SDK)
    │
    ▼
┌─────────────┐
│ 异步写入    │
└─────────────┘
    │
    ├───> 内存缓冲 (实时)
    │
    ├───> 统计文件 (批量 flush)
    │
    └───> SQLite (可选, 复杂查询)
```

---

## 3. 拦截器实现

### 3.1 CLI Wrapper 方案

```bash
#!/bin/bash
# file: ~/.local/bin/aliyun-wrapped
# 阿里云 CLI 包装脚本 - 用于调用计数

ALICLOUD_BIN="/usr/local/bin/aliyun"
COUNTER_DIR="${HOME}/.cache/aliyun-skills/call-stats"

# 解析命令行参数
PRODUCT="$1"
OPERATION="$2"
shift 2

# 生成调用记录
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CALL_ID=$(uuidgen)

# 预调用计数
increment_counter() {
    local product=$1
    local operation=$2
    local date_key=$(date +%Y-%m-%d)
    
    mkdir -p "${COUNTER_DIR}/${date_key}"
    
    # 使用文件锁保证原子性
    (
        flock -x 200
        local counter_file="${COUNTER_DIR}/${date_key}/${product}.json"
        
        # 初始化或更新计数
        if [[ ! -f "$counter_file" ]]; then
            echo "{}" > "$counter_file"
        fi
        
        # 使用 jq 更新计数
        jq --arg op "$operation" \
           --arg ts "$TIMESTAMP" \
           --arg id "$CALL_ID" \
           '
           .[$op].count = (.[$op].count // 0) + 1 |
           .[$op].last_called = $ts |
           .[$op].calls += [{"id": $id, "time": $ts}]
           ' "$counter_file" > "${counter_file}.tmp" && \
        mv "${counter_file}.tmp" "$counter_file"
    ) 200>"${COUNTER_DIR}/.lock"
}

# 执行计数
increment_counter "$PRODUCT" "$OPERATION"

# 执行原始命令并记录耗时
START_TIME=$(date +%s%N)
"$ALICLOUD_BIN" "$PRODUCT" "$OPERATION" "$@"
EXIT_CODE=$?
END_TIME=$(date +%s%N)

# 计算耗时 (毫秒)
DURATION=$(( (END_TIME - START_TIME) / 1000000 ))

# 记录结果
record_result() {
    local exit_code=$1
    local duration=$2
    
    (
        flock -x 200
        local result_file="${COUNTER_DIR}/${date_key}/${PRODUCT}-results.json"
        
        jq --arg op "$OPERATION" \
           --arg id "$CALL_ID" \
           --arg exit "$exit_code" \
           --argjson dur "$duration" \
           --arg ts "$TIMESTAMP" \
           '
           .[$op] += [{
             "call_id": $id,
             "exit_code": ($exit | tonumber),
             "duration_ms": $dur,
             "timestamp": $ts
           }]
           ' "$result_file" > "${result_file}.tmp" && \
        mv "${result_file}.tmp" "$result_file"
    ) 200>"${COUNTER_DIR}/.lock"
}

record_result "$EXIT_CODE" "$DURATION"

exit $EXIT_CODE
```

### 3.2 SDK Hook 方案 (Go)

```go
// file: pkg/counter/sdk_hook.go
package counter

import (
    "context"
    "encoding/json"
    "os"
    "path/filepath"
    "sync"
    "time"
)

// CallRecord 单次调用记录
type CallRecord struct {
    CallID      string            `json:"call_id"`
    Product     string            `json:"product"`
    Operation   string            `json:"operation"`
    Region      string            `json:"region"`
    Timestamp   time.Time         `json:"timestamp"`
    Duration    int64             `json:"duration_ms"`
    ExitCode    int               `json:"exit_code"`
    RequestSize int               `json:"request_size_bytes"`
    ResponseSize int              `json:"response_size_bytes"`
    Metadata    map[string]string `json:"metadata"`
}

// Counter 调用计数器
type Counter struct {
    dataDir     string
    buffer      chan *CallRecord
    flushInterval time.Duration
    mu          sync.RWMutex
    dailyStats  map[string]*ProductStats
}

// ProductStats 产品级统计
type ProductStats struct {
    Product      string              `json:"product"`
    Date         string              `json:"date"`
    TotalCalls   int64               `json:"total_calls"`
    SuccessCalls int64               `json:"success_calls"`
    FailedCalls  int64               `json:"failed_calls"`
    Operations   map[string]*OpStats `json:"operations"`
    LastUpdated  time.Time           `json:"last_updated"`
}

// OpStats 操作级统计
type OpStats struct {
    Operation     string    `json:"operation"`
    Count         int64     `json:"count"`
    SuccessCount  int64     `json:"success_count"`
    FailedCount   int64     `json:"failed_count"`
    AvgDuration   float64   `json:"avg_duration_ms"`
    MaxDuration   int64     `json:"max_duration_ms"`
    MinDuration   int64     `json:"min_duration_ms"`
    TotalDuration int64     `json:"total_duration_ms"`
    LastCalled    time.Time `json:"last_called"`
}

// NewCounter 创建计数器
func NewCounter(dataDir string) *Counter {
    c := &Counter{
        dataDir:       dataDir,
        buffer:        make(chan *CallRecord, 1000),
        flushInterval: 30 * time.Second,
        dailyStats:    make(map[string]*ProductStats),
    }
    
    // 启动后台 flush
    go c.backgroundFlush()
    
    return c
}

// Record 记录一次调用
func (c *Counter) Record(ctx context.Context, record *CallRecord) error {
    // 异步写入缓冲
    select {
    case c.buffer <- record:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    default:
        // 缓冲区满，直接写入文件
        return c.flushRecord(record)
    }
}

// Increment 快速计数 (仅计数，不记录详情)
func (c *Counter) Increment(product, operation, region string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    dateKey := time.Now().Format("%Y-%m-%d")
    key := product + ":" + dateKey
    
    stats, exists := c.dailyStats[key]
    if !exists {
        stats = &ProductStats{
            Product:     product,
            Date:        dateKey,
            Operations:  make(map[string]*OpStats),
            LastUpdated: time.Now(),
        }
        c.dailyStats[key] = stats
    }
    
    stats.TotalCalls++
    stats.LastUpdated = time.Now()
    
    opStats, exists := stats.Operations[operation]
    if !exists {
        opStats = &OpStats{
            Operation: operation,
            MinDuration: -1, // 初始值
        }
        stats.Operations[operation] = opStats
    }
    
    opStats.Count++
    opStats.LastCalled = time.Now()
}

// backgroundFlush 后台 flush
func (c *Counter) backgroundFlush() {
    ticker := time.NewTicker(c.flushInterval)
    defer ticker.Stop()
    
    for {
        select {
        case record := <-c.buffer:
            c.processRecord(record)
        case <-ticker.C:
            c.flushToDisk()
        }
    }
}

// processRecord 处理单条记录
func (c *Counter) processRecord(record *CallRecord) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    dateKey := record.Timestamp.Format("%Y-%m-%d")
    key := record.Product + ":" + dateKey
    
    stats := c.dailyStats[key]
    if stats == nil {
        return // 应该在 Increment 时已创建
    }
    
    opStats := stats.Operations[record.Operation]
    if opStats == nil {
        return
    }
    
    // 更新统计
    if record.ExitCode == 0 {
        stats.SuccessCalls++
        opStats.SuccessCount++
    } else {
        stats.FailedCalls++
        opStats.FailedCount++
    }
    
    // 更新耗时统计
    opStats.TotalDuration += record.Duration
    opStats.AvgDuration = float64(opStats.TotalDuration) / float64(opStats.Count)
    
    if record.Duration > opStats.MaxDuration {
        opStats.MaxDuration = record.Duration
    }
    if opStats.MinDuration == -1 || record.Duration < opStats.MinDuration {
        opStats.MinDuration = record.Duration
    }
}

// flushToDisk 持久化到磁盘
func (c *Counter) flushToDisk() error {
    c.mu.RLock()
    defer c.mu.RUnlock()
    
    for key, stats := range c.dailyStats {
        parts := strings.Split(key, ":")
        product := parts[0]
        dateKey := parts[1]
        
        dir := filepath.Join(c.dataDir, dateKey)
        if err := os.MkdirAll(dir, 0755); err != nil {
            return err
        }
        
        filePath := filepath.Join(dir, product+".json")
        
        data, err := json.MarshalIndent(stats, "", "  ")
        if err != nil {
            return err
        }
        
        if err := os.WriteFile(filePath, data, 0644); err != nil {
            return err
        }
    }
    
    return nil
}

// GetStats 获取指定日期和产品的统计
func (c *Counter) GetStats(product, date string) (*ProductStats, error) {
    filePath := filepath.Join(c.dataDir, date, product+".json")
    
    data, err := os.ReadFile(filePath)
    if err != nil {
        return nil, err
    }
    
    var stats ProductStats
    if err := json.Unmarshal(data, &stats); err != nil {
        return nil, err
    }
    
    return &stats, nil
}

// 全局计数器实例
var defaultCounter *Counter

func init() {
    cacheDir := os.Getenv("HOME") + "/.cache/aliyun-skills"
    defaultCounter = NewCounter(filepath.Join(cacheDir, "call-stats"))
}

// RecordCall 快捷函数
func RecordCall(product, operation, region string) *CallRecord {
    return &CallRecord{
        CallID:    uuid.New().String(),
        Product:   product,
        Operation: operation,
        Region:    region,
        Timestamp: time.Now(),
    }
}
```

---

## 4. 统计存储

### 4.1 JSON 文件存储

```json
// ~/.cache/aliyun-skills/call-stats/2026-05-20/ecs.json
{
  "product": "ecs",
  "date": "2026-05-20",
  "total_calls": 1523,
  "success_calls": 1498,
  "failed_calls": 25,
  "last_updated": "2026-05-20T23:45:00Z",
  "operations": {
    "DescribeInstances": {
      "operation": "DescribeInstances",
      "count": 856,
      "success_count": 850,
      "failed_count": 6,
      "avg_duration_ms": 245.5,
      "max_duration_ms": 3200,
      "min_duration_ms": 120,
      "total_duration_ms": 210148,
      "last_called": "2026-05-20T23:40:15Z"
    },
    "StartInstance": {
      "operation": "StartInstance",
      "count": 45,
      "success_count": 42,
      "failed_count": 3,
      "avg_duration_ms": 5200.0,
      "max_duration_ms": 15000,
      "min_duration_ms": 3000,
      "total_duration_ms": 234000,
      "last_called": "2026-05-20T23:35:00Z"
    },
    "StopInstance": {
      "operation": "StopInstance",
      "count": 38,
      "success_count": 37,
      "failed_count": 1,
      "avg_duration_ms": 4800.0,
      "max_duration_ms": 12000,
      "min_duration_ms": 2800,
      "total_duration_ms": 182400,
      "last_called": "2026-05-20T23:30:00Z"
    }
  }
}
```

### 4.2 SQLite Schema (可选)

```sql
-- ~/.cache/aliyun-skills/call-stats/stats.db

-- 产品表
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 操作表
CREATE TABLE IF NOT EXISTS operations (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL,
    name        VARCHAR(100) NOT NULL,
    free_tier   INTEGER DEFAULT 0,  -- 免费额度
    cost_per_1k DECIMAL(10, 4),    -- 每千次调用成本
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE(product_id, name)
);

-- 调用记录表
CREATE TABLE IF NOT EXISTS call_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id         VARCHAR(36) NOT NULL UNIQUE,
    product_id      INTEGER NOT NULL,
    operation_id    INTEGER NOT NULL,
    region          VARCHAR(50),
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms     INTEGER,
    exit_code       INTEGER,
    request_size    INTEGER,
    response_size   INTEGER,
    user_id         VARCHAR(50),
    session_id      VARCHAR(100),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (operation_id) REFERENCES operations(id)
);

-- 每日统计视图
CREATE VIEW IF NOT EXISTS daily_stats AS
SELECT 
    p.name as product,
    DATE(cr.timestamp) as date,
    o.name as operation,
    COUNT(*) as call_count,
    SUM(CASE WHEN cr.exit_code = 0 THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN cr.exit_code != 0 THEN 1 ELSE 0 END) as fail_count,
    AVG(cr.duration_ms) as avg_duration,
    MAX(cr.duration_ms) as max_duration,
    MIN(cr.duration_ms) as min_duration
FROM call_records cr
JOIN products p ON cr.product_id = p.id
JOIN operations o ON cr.operation_id = o.id
GROUP BY p.name, DATE(cr.timestamp), o.name;

-- 索引
CREATE INDEX IF NOT EXISTS idx_call_records_timestamp ON call_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_call_records_product ON call_records(product_id);
CREATE INDEX IF NOT EXISTS idx_call_records_operation ON call_records(operation_id);
CREATE INDEX IF NOT EXISTS idx_call_records_region ON call_records(region);
```

---

## 5. 报表生成

### 5.1 报表格式

```markdown
# API 调用统计日报表

**报表日期:** 2026-05-20
**生成时间:** 2026-05-20 23:59:59
**报表周期:** 2026-05-20 00:00:00 - 2026-05-20 23:59:59

---

## 概览

| 指标 | 数值 |
|------|------|
| 总调用次数 | 15,234 |
| 成功次数 | 14,892 (97.8%) |
| 失败次数 | 342 (2.2%) |
| 平均耗时 | 285ms |
| 涉及产品数 | 8 |
| 涉及操作数 | 42 |

---

## 分产品统计

| Product | Total Calls | Success | Failed | Avg Duration | Free Tier | Cost (CNY) |
|---------|-------------|---------|--------|--------------|-----------|------------|
| ECS | 5,234 | 5,100 | 134 | 245ms | - | ¥0.00 |
| RDS | 3,456 | 3,400 | 56 | 320ms | - | ¥0.00 |
| CMS | 4,567 | 4,500 | 67 | 180ms | 1,000,000 | ¥0.00 |
| DAS | 1,234 | 1,200 | 34 | 450ms | - | ¥12.34 |
| ACK | 743 | 692 | 51 | 280ms | - | ¥0.00 |

---

## 热门操作 Top 10

| Rank | Product | Operation | Count | Avg Duration | Trend |
|------|---------|-----------|-------|--------------|-------|
| 1 | ECS | DescribeInstances | 2,456 | 245ms | ↗ +12% |
| 2 | CMS | DescribeMetricList | 2,100 | 180ms | → 0% |
| 3 | RDS | DescribeDBInstances | 1,890 | 320ms | ↘ -5% |
| 4 | ECS | DescribeInstanceStatus | 1,234 | 120ms | → 0% |
| 5 | DAS | CreateDiagnosticReport | 890 | 450ms | ↗ +8% |

---

## 异常分析

| 问题类型 | 次数 | 占比 | 建议 |
|----------|------|------|------|
| 超时错误 | 156 | 45.6% | 增加超时时间或重试 |
| 权限错误 | 98 | 28.7% | 检查 RAM 权限配置 |
| 限流错误 | 45 | 13.2% | 降低调用频率 |
| 参数错误 | 43 | 12.5% | 检查请求参数 |

---

## 成本分析

| Product | Budget (CNY) | Actual (CNY) | Usage % | Status |
|---------|--------------|--------------|---------|--------|
| CMS | ¥300.00 | ¥0.00 | 0% | ✅ 正常 |
| DAS | ¥400.00 | ¥12.34 | 3.1% | ✅ 正常 |
| Others | ¥300.00 | ¥0.00 | 0% | ✅ 正常 |
| **Total** | **¥1,000.00** | **¥12.34** | **1.2%** | **✅ 正常** |

---

*本报表由 Aliyun Skill API Call Counter 自动生成*
```

### 5.2 报表生成脚本

```bash
#!/bin/bash
# file: ~/.local/bin/skill-generate-report

DATA_DIR="${HOME}/.cache/aliyun-skills/call-stats"
REPORT_DIR="${HOME}/.cache/aliyun-skills/reports"
DATE=$(date +%Y-%m-%d)

generate_daily_report() {
    local report_date=$1
    local report_file="${REPORT_DIR}/daily-${report_date}.md"
    
    mkdir -p "$REPORT_DIR"
    
    # 生成 Markdown 报表
    cat > "$report_file" << EOF
# API 调用统计日报表

**报表日期:** $report_date
**生成时间:** $(date '+%Y-%m-%d %H:%M:%S')

---

## 概览

| 指标 | 数值 |
|------|------|
| 总调用次数 | $(get_total_calls "$report_date") |
| 成功次数 | $(get_success_calls "$report_date") |
| 失败次数 | $(get_failed_calls "$report_date") |

## 分产品统计

| Product | Total Calls | Free Tier | Cost (CNY) |
|---------|-------------|-----------|------------|
$(generate_product_table "$report_date")

---

*自动生成于 $(date)*
EOF
    
    echo "报表已生成: $report_file"
}

# 辅助函数
get_total_calls() {
    local date=$1
    local total=0
    for f in "${DATA_DIR}/${date}"/*.json; do
        if [[ -f "$f" ]]; then
            count=$(jq '.total_calls' "$f")
            total=$((total + count))
        fi
    done
    echo $total
}

generate_product_table() {
    local date=$1
    for f in "${DATA_DIR}/${date}"/*.json; do
        if [[ -f "$f" ]]; then
            local product=$(jq -r '.product' "$f")
            local calls=$(jq '.total_calls' "$f")
            local success=$(jq '.success_calls' "$f")
            local failed=$(jq '.failed_calls' "$f")
            echo "| $product | $calls | $success | $failed | - | ¥0.00 |"
        fi
    done
}

# 主入口
case "$1" in
    daily)
        generate_daily_report "${2:-$DATE}"
        ;;
    weekly)
        # 生成周报逻辑
        ;;
    monthly)
        # 生成月报逻辑
        ;;
    *)
        echo "Usage: $0 {daily|weekly|monthly} [date]"
        exit 1
        ;;
esac
```

---

## 6. 成本预算联动

### 6.1 预算检查逻辑

```go
// file: pkg/counter/budget.go
package counter

import (
    "encoding/json"
    "fmt"
    "os"
    "path/filepath"
)

// BudgetConfig 预算配置
type BudgetConfig struct {
    MonthlyBudget int            `json:"monthly_budget"` // CNY
    Thresholds    Thresholds     `json:"thresholds"`
    Allocations   map[string]int `json:"allocations"`  // 百分比
}

type Thresholds struct {
    Warning  int `json:"warning"`  // 百分比
    Critical int `json:"critical"` // 百分比
}

// BudgetChecker 预算检查器
type BudgetChecker struct {
    config    *BudgetConfig
    dataDir   string
    counter   *Counter
}

// CheckResult 检查结果
type CheckResult struct {
    Product       string  `json:"product"`
    CurrentMonth  int64   `json:"current_month_calls"`
    BudgetLimit   int64   `json:"budget_limit_calls"`
    UsagePercent  float64 `json:"usage_percent"`
    Status        string  `json:"status"` // ok, warning, critical, exceeded
    Action        string  `json:"action"`
}

// NewBudgetChecker 创建预算检查器
func NewBudgetChecker(configPath string, counter *Counter) (*BudgetChecker, error) {
    data, err := os.ReadFile(configPath)
    if err != nil {
        return nil, err
    }
    
    var config BudgetConfig
    if err := json.Unmarshal(data, &config); err != nil {
        return nil, err
    }
    
    return &BudgetChecker{
        config:  &config,
        dataDir: filepath.Dir(configPath),
        counter: counter,
    }, nil
}

// Check 检查预算状态
func (bc *BudgetChecker) Check(product string) (*CheckResult, error) {
    // 获取本月调用量
    monthKey := time.Now().Format("%Y-%m")
    monthCalls := bc.getMonthlyCalls(product, monthKey)
    
    // 计算预算限额
    allocation := bc.config.Allocations[product]
    if allocation == 0 {
        allocation = bc.config.Allocations["others"]
    }
    
    // 假设每千次调用成本固定
    costPer1k := bc.getCostPer1k(product)
    budgetCalls := int64(bc.config.MonthlyBudget * allocation / 100 * 1000 / costPer1k)
    
    usagePercent := float64(monthCalls) / float64(budgetCalls) * 100
    
    result := &CheckResult{
        Product:      product,
        CurrentMonth: monthCalls,
        BudgetLimit:  budgetCalls,
        UsagePercent: usagePercent,
    }
    
    // 判断状态
    if usagePercent >= 100 {
        result.Status = "exceeded"
        result.Action = "暂停非关键调用，通知管理员"
    } else if usagePercent >= float64(bc.config.Thresholds.Critical) {
        result.Status = "critical"
        result.Action = "降低调用频率，启用限流"
    } else if usagePercent >= float64(bc.config.Thresholds.Warning) {
        result.Status = "warning"
        result.Action = "监控调用量，准备限流策略"
    } else {
        result.Status = "ok"
        result.Action = "正常"
    }
    
    return result, nil
}

// ShouldThrottle 是否需要限流
func (bc *BudgetChecker) ShouldThrottle(product string) bool {
    result, err := bc.Check(product)
    if err != nil {
        return false
    }
    return result.Status == "critical" || result.Status == "exceeded"
}
```

---

## 7. 实现示例

### 7.1 集成到 Skill 调用

```go
// 示例: 在 Skill 中集成调用计数
func (s *ECSSkill) DescribeInstances(ctx context.Context, req *DescribeInstancesRequest) (*DescribeInstancesResponse, error) {
    // 1. 记录调用开始
    callRecord := counter.RecordCall("ecs", "DescribeInstances", req.RegionId)
    startTime := time.Now()
    
    // 2. 检查预算
    if budgetChecker.ShouldThrottle("ecs") {
        return nil, fmt.Errorf("API call throttled due to budget constraint")
    }
    
    // 3. 执行原始调用
    resp, err := s.client.DescribeInstances(req)
    
    // 4. 记录调用结果
    callRecord.Duration = time.Since(startTime).Milliseconds()
    if err != nil {
        callRecord.ExitCode = 1
    } else {
        callRecord.ExitCode = 0
    }
    
    // 5. 异步写入统计
    counter.Default().Record(ctx, callRecord)
    
    return resp, err
}
```

---

## 8. 度量与验证

### 8.1 测试验证

```bash
# 测试 1: 计数准确性
echo "=== 测试计数准确性 ==="
for i in {1..100}; do
    aliyun-wrapped ecs DescribeInstances --RegionId cn-hangzhou >/dev/null 2>&1
done

# 验证计数
cat ~/.cache/aliyun-skills/call-stats/$(date +%Y-%m-%d)/ecs.json | jq '.operations.DescribeInstances.count'

# 测试 2: 报表生成
echo "=== 测试报表生成 ==="
skill-generate-report daily
ls -la ~/.cache/aliyun-skills/reports/

# 测试 3: 预算检查
echo "=== 测试预算检查 ==="
skill-budget-check ecs
```

### 8.2 监控指标

```yaml
监控指标:
  - api_call_total           # 总调用次数
  - api_call_by_product      # 分产品调用次数
  - api_call_by_operation    # 分操作调用次数
  - api_call_duration        # 调用耗时分布
  - api_call_error_rate      # 错误率
  - api_budget_usage         # 预算使用率
  - api_throttle_count       # 限流次数
```

---

## 附录 A: 相关文档

- [optimization-analysis-enhanced.md](optimization-analysis-enhanced.md) - 三维优化分析
- [cost-budget-template.yaml](../assets/cost-budget-template.yaml) - 成本预算模板

---

*文档版本: v1.0.0 | 最后更新: 2026-05-20*
