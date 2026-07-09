# API 调用计数集成模板

阿里云 API 调用计数与统计模板。

## 1. 调用拦截器模板

### Go 实现 (中间件模式)

```go
package apicounter

import (
    "context"
    "sync"
    "sync/atomic"
    "time"
)

// CallInterceptor API 调用拦截器
type CallInterceptor struct {
    counters    map[string]*APICounter
    mu          sync.RWMutex
    storage     Storage
    reporter    Reporter
}

// APICounter 单个 API 计数器
type APICounter struct {
    ServiceName   string
    APIName       string
    TotalCalls    int64
    SuccessCalls  int64
    FailedCalls   int64
    LatencySum    int64  // 总延迟(ms)
    LatencyCount  int64
    LastCallTime  time.Time
}

// NewInterceptor 创建拦截器
func NewInterceptor(storage Storage, reporter Reporter) *CallInterceptor {
    return &CallInterceptor{
        counters: make(map[string]*APICounter),
        storage:  storage,
        reporter: reporter,
    }
}

// Intercept 拦截 API 调用
func (ci *CallInterceptor) Intercept(ctx context.Context, 
    serviceName, apiName string,
    fn func() error) error {
    
    start := time.Now()
    counter := ci.getCounter(serviceName, apiName)
    
    // 增加总调用计数
    atomic.AddInt64(&counter.TotalCalls, 1)
    counter.LastCallTime = time.Now()
    
    // 执行实际调用
    err := fn()
    
    // 记录结果
    latency := time.Since(start).Milliseconds()
    atomic.AddInt64(&counter.LatencySum, latency)
    atomic.AddInt64(&counter.LatencyCount, 1)
    
    if err != nil {
        atomic.AddInt64(&counter.FailedCalls, 1)
        ci.recordError(serviceName, apiName, err)
    } else {
        atomic.AddInt64(&counter.SuccessCalls, 1)
    }
    
    return err
}

// getCounter 获取或创建计数器
func (ci *CallInterceptor) getCounter(serviceName, apiName string) *APICounter {
    key := serviceName + ":" + apiName
    
    ci.mu.RLock()
    if counter, ok := ci.counters[key]; ok {
        ci.mu.RUnlock()
        return counter
    }
    ci.mu.RUnlock()
    
    ci.mu.Lock()
    defer ci.mu.Unlock()
    
    // 双重检查
    if counter, ok := ci.counters[key]; ok {
        return counter
    }
    
    counter := &APICounter{
        ServiceName: serviceName,
        APIName:     apiName,
    }
    ci.counters[key] = counter
    return counter
}

// recordError 记录错误详情
func (ci *CallInterceptor) recordError(serviceName, apiName string, err error) {
    errorRecord := &ErrorRecord{
        Time:        time.Now(),
        ServiceName: serviceName,
        APIName:     apiName,
        Error:       err.Error(),
    }
    
    if ci.storage != nil {
        ci.storage.StoreError(errorRecord)
    }
}

// GetStats 获取统计信息
func (ci *CallInterceptor) GetStats(serviceName, apiName string) *APIStats {
    key := serviceName + ":" + apiName
    
    ci.mu.RLock()
    counter, ok := ci.counters[key]
    ci.mu.RUnlock()
    
    if !ok {
        return nil
    }
    
    total := atomic.LoadInt64(&counter.TotalCalls)
    success := atomic.LoadInt64(&counter.SuccessCalls)
    failed := atomic.LoadInt64(&counter.FailedCalls)
    latencySum := atomic.LoadInt64(&counter.LatencySum)
    latencyCount := atomic.LoadInt64(&counter.LatencyCount)
    
    avgLatency := 0
    if latencyCount > 0 {
        avgLatency = int(latencySum / latencyCount)
    }
    
    return &APIStats{
        ServiceName:  serviceName,
        APIName:      apiName,
        TotalCalls:   total,
        SuccessCalls: success,
        FailedCalls:  failed,
        SuccessRate:  float64(success) / float64(total) * 100,
        AvgLatency:   avgLatency,
        LastCallTime: counter.LastCallTime,
    }
}

// 辅助类型定义
type ErrorRecord struct {
    Time        time.Time
    ServiceName string
    APIName     string
    Error       string
}

type APIStats struct {
    ServiceName  string
    APIName      string
    TotalCalls   int64
    SuccessCalls int64
    FailedCalls  int64
    SuccessRate  float64
    AvgLatency   int
    LastCallTime time.Time
}

type Storage interface {
    StoreError(record *ErrorRecord) error
    GetErrors(serviceName, apiName string, since time.Time) ([]*ErrorRecord, error)
}

type Reporter interface {
    Report(stats []*APIStats) error
}
```

### Python 实现 (装饰器模式)

```python
#!/usr/bin/env python3
"""
API 调用计数装饰器模板
"""
import functools
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import threading


@dataclass
class APICallRecord:
    """API 调用记录"""
    service_name: str
    api_name: str
    timestamp: float
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    extra_tags: Dict = field(default_factory=dict)


@dataclass
class APIStats:
    """API 统计信息"""
    service_name: str
    api_name: str
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    latency_count: int = 0
    last_call_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.success_calls / self.total_calls) * 100
    
    @property
    def avg_latency_ms(self) -> float:
        if self.latency_count == 0:
            return 0.0
        return self.total_latency_ms / self.latency_count
    
    @property
    def p99_latency_ms(self) -> float:
        # 需要存储所有延迟值才能计算
        return 0.0


class APICallInterceptor:
    """API 调用拦截器"""
    
    def __init__(self, storage=None, reporter=None):
        self._counters: Dict[str, APIStats] = {}
        self._records: List[APICallRecord] = []
        self._lock = threading.RLock()
        self._storage = storage
        self._reporter = reporter
        self._latency_histograms: Dict[str, List[float]] = defaultdict(list)
    
    def intercept(self, service_name: str, api_name: str):
        """装饰器：拦截 API 调用"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                error_msg = None
                success = True
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    raise
                finally:
                    latency_ms = (time.time() - start_time) * 1000
                    self._record_call(
                        service_name=service_name,
                        api_name=api_name,
                        latency_ms=latency_ms,
                        success=success,
                        error_message=error_msg
                    )
            
            return wrapper
        return decorator
    
    def _record_call(self, service_name: str, api_name: str,
                    latency_ms: float, success: bool,
                    error_message: Optional[str] = None):
        """记录调用"""
        key = f"{service_name}:{api_name}"
        timestamp = time.time()
        
        with self._lock:
            # 初始化或更新计数器
            if key not in self._counters:
                self._counters[key] = APIStats(
                    service_name=service_name,
                    api_name=api_name
                )
            
            stats = self._counters[key]
            stats.total_calls += 1
            stats.total_latency_ms += latency_ms
            stats.latency_count += 1
            stats.last_call_time = timestamp
            
            if success:
                stats.success_calls += 1
            else:
                stats.failed_calls += 1
            
            # 记录延迟分布
            self._latency_histograms[key].append(latency_ms)
            # 限制存储数量
            if len(self._latency_histograms[key]) > 10000:
                self._latency_histograms[key] = self._latency_histograms[key][-5000:]
            
            # 创建调用记录
            record = APICallRecord(
                service_name=service_name,
                api_name=api_name,
                timestamp=timestamp,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message
            )
            self._records.append(record)
            
            # 存储到持久化
            if self._storage:
                self._storage.store(record)
    
    def get_stats(self, service_name: str = None, 
                  api_name: str = None) -> List[APIStats]:
        """获取统计信息"""
        with self._lock:
            results = []
            for key, stats in self._counters.items():
                if service_name and stats.service_name != service_name:
                    continue
                if api_name and stats.api_name != api_name:
                    continue
                results.append(stats)
            return results
    
    def get_latency_percentile(self, service_name: str, 
                               api_name: str, 
                               percentile: float = 0.99) -> float:
        """获取延迟百分位数"""
        key = f"{service_name}:{api_name}"
        with self._lock:
            latencies = sorted(self._latency_histograms.get(key, []))
            if not latencies:
                return 0.0
            idx = int(len(latencies) * percentile)
            return latencies[min(idx, len(latencies) - 1)]
    
    def reset(self, service_name: str = None, api_name: str = None):
        """重置计数器"""
        with self._lock:
            if service_name is None and api_name is None:
                self._counters.clear()
                self._records.clear()
                self._latency_histograms.clear()
            else:
                key = f"{service_name}:{api_name}"
                if key in self._counters:
                    del self._counters[key]
                if key in self._latency_histograms:
                    del self._latency_histograms[key]
                self._records = [
                    r for r in self._records 
                    if not (r.service_name == service_name and 
                           r.api_name == api_name)
                ]


# 使用示例
interceptor = APICallInterceptor()

class MyService:
    @interceptor.intercept("ECS", "DescribeInstances")
    def describe_instances(self):
        # 实际调用
        pass
    
    @interceptor.intercept("ECS", "CreateInstance")
    def create_instance(self):
        # 实际调用
        pass
```

## 2. 统计存储模板

### Redis 存储实现

```python
#!/usr/bin/env python3
"""
API 调用统计 Redis 存储模板
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis


class RedisStorage:
    """Redis 统计存储"""
    
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = redis.Redis(host=host, port=port, db=db)
        self.key_prefix = "api:counter"
    
    def store(self, record: 'APICallRecord'):
        """存储调用记录"""
        key = f"{self.key_prefix}:calls:{record.service_name}:{record.api_name}"
        
        # 存储到 sorted set，按时间排序
        score = record.timestamp
        value = json.dumps({
            'latency_ms': record.latency_ms,
            'success': record.success,
            'error_message': record.error_message
        })
        
        self.client.zadd(key, {value: score})
        
        # 设置过期时间 (7天)
        self.client.expire(key, 7 * 24 * 3600)
        
        # 更新实时计数器
        self._update_counters(record)
    
    def _update_counters(self, record: 'APICallRecord'):
        """更新计数器"""
        # 总调用数
        total_key = f"{self.key_prefix}:total:{record.service_name}:{record.api_name}"
        self.client.incr(total_key)
        
        # 成功/失败计数
        if record.success:
            success_key = f"{self.key_prefix}:success:{record.service_name}:{record.api_name}"
            self.client.incr(success_key)
        else:
            failed_key = f"{self.key_prefix}:failed:{record.service_name}:{record.api_name}"
            self.client.incr(failed_key)
        
        # 延迟统计
        latency_key = f"{self.key_prefix}:latency:{record.service_name}:{record.api_name}"
        self.client.lpush(latency_key, record.latency_ms)
        self.client.ltrim(latency_key, 0, 9999)  # 保留最近10000条
    
    def get_stats(self, service_name: str, api_name: str,
                  since: Optional[datetime] = None) -> Dict:
        """获取统计信息"""
        total_key = f"{self.key_prefix}:total:{service_name}:{api_name}"
        success_key = f"{self.key_prefix}:success:{service_name}:{api_name}"
        failed_key = f"{self.key_prefix}:failed:{service_name}:{api_name}"
        latency_key = f"{self.key_prefix}:latency:{service_name}:{api_name}"
        
        total = int(self.client.get(total_key) or 0)
        success = int(self.client.get(success_key) or 0)
        failed = int(self.client.get(failed_key) or 0)
        
        # 获取延迟列表
        latencies = [float(x) for x in self.client.lrange(latency_key, 0, -1)]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            'service_name': service_name,
            'api_name': api_name,
            'total_calls': total,
            'success_calls': success,
            'failed_calls': failed,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'avg_latency_ms': avg_latency,
            'p99_latency_ms': self._percentile(latencies, 0.99),
            'p95_latency_ms': self._percentile(latencies, 0.95)
        }
    
    def _percentile(self, data: List[float], p: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p)
        return sorted_data[min(idx, len(sorted_data) - 1)]
    
    def get_top_apis(self, limit: int = 10) -> List[Dict]:
        """获取调用量最高的 API"""
        pattern = f"{self.key_prefix}:total:*"
        keys = self.client.scan_iter(match=pattern)
        
        api_counts = []
        for key in keys:
            key_str = key.decode('utf-8')
            parts = key_str.split(':')
            if len(parts) >= 5:
                service = parts[3]
                api = parts[4]
                count = int(self.client.get(key) or 0)
                api_counts.append({
                    'service': service,
                    'api': api,
                    'count': count
                })
        
        return sorted(api_counts, key=lambda x: x['count'], reverse=True)[:limit]
```

### InfluxDB 时序存储

```python
#!/usr/bin/env python3
"""
API 调用统计 InfluxDB 存储模板
"""
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


class InfluxDBStorage:
    """InfluxDB 统计存储"""
    
    def __init__(self, url, token, org, bucket):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        self.bucket = bucket
        self.org = org
    
    def store(self, record: 'APICallRecord'):
        """存储调用记录"""
        point = Point("api_call") \
            .tag("service_name", record.service_name) \
            .tag("api_name", record.api_name) \
            .tag("success", str(record.success).lower()) \
            .field("latency_ms", record.latency_ms) \
            .time(datetime.fromtimestamp(record.timestamp))
        
        if record.error_message:
            point = point.tag("error", "true")
        
        self.write_api.write(bucket=self.bucket, record=point)
    
    def get_stats(self, service_name: str = None, 
                  api_name: str = None,
                  time_range: str = "-1h") -> List[Dict]:
        """获取统计信息"""
        
        # 构建查询
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {time_range})
            |> filter(fn: (r) => r._measurement == "api_call")
        '''
        
        if service_name:
            query += f'|> filter(fn: (r) => r.service_name == "{service_name}")'
        if api_name:
            query += f'|> filter(fn: (r) => r.api_name == "{api_name}")'
        
        query += '''
            |> group(columns: ["service_name", "api_name"])
            |> aggregateWindow(every: 1m, fn: count)
        '''
        
        tables = self.query_api.query(query, org=self.org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    'time': record.get_time(),
                    'service': record.values.get('service_name'),
                    'api': record.values.get('api_name'),
                    'count': record.get_value()
                })
        
        return results
    
    def get_latency_stats(self, service_name: str, api_name: str,
                         time_range: str = "-1h") -> Dict:
        """获取延迟统计"""
        
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {time_range})
            |> filter(fn: (r) => r._measurement == "api_call")
            |> filter(fn: (r) => r.service_name == "{service_name}")
            |> filter(fn: (r) => r.api_name == "{api_name}")
            |> filter(fn: (r) => r._field == "latency_ms")
            |> group()
            |> stats(fn: percentile, percentile: 99)
        '''
        
        tables = self.query_api.query(query, org=self.org)
        
        # 解析结果
        stats = {}
        for table in tables:
            for record in table.records:
                stats[record.get_field()] = record.get_value()
        
        return stats
```

## 3. 报表生成模板

### Markdown 报表生成器

```python
#!/usr/bin/env python3
"""
API 调用统计报表生成器
"""
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class ReportConfig:
    """报表配置"""
    title: str
    time_range: str = "-24h"
    include_charts: bool = True
    include_errors: bool = True
    top_n: int = 20


class APIReportGenerator:
    """API 统计报表生成器"""
    
    def __init__(self, storage):
        self.storage = storage
    
    def generate(self, config: ReportConfig) -> str:
        """生成报表"""
        lines = []
        
        # 标题
        lines.append(f"# {config.title}")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"统计周期: {config.time_range}\n")
        
        # 概览
        lines.append(self._generate_overview(config))
        
        # Top API
        lines.append(self._generate_top_apis(config))
        
        # 服务统计
        lines.append(self._generate_service_stats(config))
        
        # 错误分析
        if config.include_errors:
            lines.append(self._generate_error_analysis(config))
        
        # 延迟分析
        lines.append(self._generate_latency_analysis(config))
        
        return "\n".join(lines)
    
    def _generate_overview(self, config: ReportConfig) -> str:
        """生成概览"""
        # 获取总体统计
        stats = self.storage.get_overall_stats(config.time_range)
        
        lines = [
            "## 总体概览\n",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总调用次数 | {stats.get('total_calls', 0):,} |",
            f"| 成功次数 | {stats.get('success_calls', 0):,} |",
            f"| 失败次数 | {stats.get('failed_calls', 0):,} |",
            f"| 成功率 | {stats.get('success_rate', 0):.2f}% |",
            f"| 平均延迟 | {stats.get('avg_latency', 0):.2f}ms |",
            f"| P99 延迟 | {stats.get('p99_latency', 0):.2f}ms |",
            "\n"
        ]
        
        return "\n".join(lines)
    
    def _generate_top_apis(self, config: ReportConfig) -> str:
        """生成 Top API"""
        top_apis = self.storage.get_top_apis(limit=config.top_n)
        
        lines = [
            f"## Top {config.top_n} API 调用\n",
            "| 排名 | 服务 | API | 调用次数 | 成功率 | 平均延迟 |",
            "|------|------|-----|----------|--------|----------|"
        ]
        
        for i, api in enumerate(top_apis, 1):
            lines.append(
                f"| {i} | {api['service']} | {api['api']} | "
                f"{api['count']:,} | {api.get('success_rate', 0):.2f}% | "
                f"{api.get('avg_latency', 0):.2f}ms |"
            )
        
        lines.append("\n")
        return "\n".join(lines)
    
    def _generate_service_stats(self, config: ReportConfig) -> str:
        """生成服务统计"""
        service_stats = self.storage.get_service_stats(config.time_range)
        
        lines = [
            "## 服务调用统计\n",
            "| 服务 | 调用次数 | 成功次数 | 失败次数 | 成功率 | 平均延迟 |",
            "|------|----------|----------|----------|--------|----------|"
        ]
        
        for service in sorted(service_stats, key=lambda x: x['total_calls'], reverse=True):
            lines.append(
                f"| {service['name']} | {service['total_calls']:,} | "
                f"{service['success_calls']:,} | {service['failed_calls']:,} | "
                f"{service['success_rate']:.2f}% | {service['avg_latency']:.2f}ms |"
            )
        
        lines.append("\n")
        return "\n".join(lines)
    
    def _generate_error_analysis(self, config: ReportConfig) -> str:
        """生成错误分析"""
        errors = self.storage.get_error_stats(config.time_range)
        
        lines = [
            "## 错误分析\n",
            "### 错误类型分布\n",
            "| 错误类型 | 次数 | 占比 | 最近服务 |",
            "|----------|------|------|----------|"
        ]
        
        for error in errors.get('types', []):
            lines.append(
                f"| {error['type']} | {error['count']:,} | "
                f"{error['percentage']:.2f}% | {error.get('recent_service', 'N/A')} |"
            )
        
        lines.extend([
            "\n### 错误率最高的 API\n",
            "| 服务 | API | 错误次数 | 错误率 |",
            "|------|-----|----------|--------|"
        ])
        
        for api in errors.get('top_error_apis', []):
            lines.append(
                f"| {api['service']} | {api['api']} | "
                f"{api['error_count']:,} | {api['error_rate']:.2f}% |"
            )
        
        lines.append("\n")
        return "\n".join(lines)
    
    def _generate_latency_analysis(self, config: ReportConfig) -> str:
        """生成延迟分析"""
        latency_data = self.storage.get_latency_distribution(config.time_range)
        
        lines = [
            "## 延迟分析\n",
            "### 延迟分布\n",
            "| 延迟区间 | 调用次数 | 占比 |",
            "|----------|----------|------|"
        ]
        
        buckets = [
            ("< 100ms", 0, 100),
            ("100-500ms", 100, 500),
            ("500ms-1s", 500, 1000),
            ("1-3s", 1000, 3000),
            ("> 3s", 3000, float('inf'))
        ]
        
        for label, low, high in buckets:
            count = sum(1 for l in latency_data if low <= l < high)
            pct = (count / len(latency_data) * 100) if latency_data else 0
            lines.append(f"| {label} | {count:,} | {pct:.2f}% |")
        
        lines.extend([
            "\n### 慢调用 Top 10\n",
            "| 服务 | API | 平均延迟 | P99 延迟 |",
            "|------|-----|----------|----------|"
        ])
        
        for api in self.storage.get_slow_apis(limit=10):
            lines.append(
                f"| {api['service']} | {api['api']} | "
                f"{api['avg_latency']:.2f}ms | {api['p99_latency']:.2f}ms |"
            )
        
        lines.append("\n")
        return "\n".join(lines)
    
    def save(self, report: str, filepath: str):
        """保存报表"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
```

### JSON/API 格式导出

```python
#!/usr/bin/env python3
"""
API 统计 JSON 导出模板
"""
import json
from datetime import datetime
from typing import Dict, Any


class APIStatsExporter:
    """API 统计导出器"""
    
    def __init__(self, storage):
        self.storage = storage
    
    def export_summary(self, time_range: str = "-24h") -> Dict[str, Any]:
        """导出摘要"""
        return {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "time_range": time_range,
                "version": "1.0"
            },
            "summary": self.storage.get_overall_stats(time_range),
            "top_apis": self.storage.get_top_apis(limit=20),
            "service_summary": self.storage.get_service_stats(time_range)
        }
    
    def export_detailed(self, service_name: str, api_name: str,
                       time_range: str = "-24h") -> Dict[str, Any]:
        """导出详细数据"""
        return {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "service": service_name,
                "api": api_name,
                "time_range": time_range
            },
            "stats": self.storage.get_stats(service_name, api_name, time_range),
            "hourly_breakdown": self.storage.get_hourly_stats(
                service_name, api_name, time_range
            ),
            "error_details": self.storage.get_error_details(
                service_name, api_name, time_range
            ),
            "latency_histogram": self.storage.get_latency_histogram(
                service_name, api_name, time_range
            )
        }
    
    def export_prometheus_format(self, time_range: str = "-24h") -> str:
        """导出 Prometheus 格式"""
        lines = []
        
        # 获取所有 API 统计
        stats_list = self.storage.get_all_stats(time_range)
        
        for stats in stats_list:
            service = stats['service_name']
            api = stats['api_name']
            
            # 总调用数
            lines.append(
                f'api_calls_total{{service="{service}",api="{api}"}} {stats["total_calls"]}'
            )
            
            # 成功调用
            lines.append(
                f'api_calls_success{{service="{service}",api="{api}"}} {stats["success_calls"]}'
            )
            
            # 失败调用
            lines.append(
                f'api_calls_failed{{service="{service}",api="{api}"}} {stats["failed_calls"]}'
            )
            
            # 延迟
            lines.append(
                f'api_latency_avg{{service="{service}",api="{api}"}} {stats["avg_latency"]}'
            )
            lines.append(
                f'api_latency_p99{{service="{service}",api="{api}"}} {stats["p99_latency"]}'
            )
        
        return "\n".join(lines)
    
    def save_json(self, data: Dict, filepath: str):
        """保存为 JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_prometheus(self, data: str, filepath: str):
        """保存 Prometheus 格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# API Call Statistics\n")
            f.write(f"# Generated at {datetime.now().isoformat()}\n\n")
            f.write(data)


# 配置文件模板
CONFIG_TEMPLATE = '''
# api-counter-config.yaml

# 存储配置
storage:
  type: redis  # redis / influxdb / mysql
  redis:
    host: localhost
    port: 6379
    db: 0
  influxdb:
    url: http://localhost:8086
    token: your-token
    org: your-org
    bucket: api-calls

# 报表配置
report:
  default_time_range: "-24h"
  output_format: markdown  # markdown / json / prometheus
  include_charts: true
  
# 告警阈值
alerts:
  error_rate_threshold: 5.0  # %
  latency_threshold: 1000    # ms
  qps_threshold: 1000
  
# 采样配置
sampling:
  enabled: true
  rate: 1.0  # 1.0 = 100%
'''
```

## 使用指南

1. **选择拦截方式**: 中间件模式或装饰器模式
2. **配置存储后端**: Redis/InfluxDB/MySQL
3. **设置采样率**: 根据调用量调整
4. **生成报表**: 定期导出统计报告
