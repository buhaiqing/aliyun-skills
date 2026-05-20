# 可观测性联动模板

阿里云可观测性组件联动规则模板。

## 1. Metrics → Logs 联动规则

### SLS 日志与云监控 Metrics 联动

```yaml
# metrics-to-logs-linkage.yaml
linkage:
  name: "metrics-logs-correlation"
  description: "当 Metrics 触发告警时，自动查询关联日志"
  
  # 触发条件
  trigger:
    metric_source: cloud_monitor
    conditions:
      - metric: CPUUtilization
        threshold: "> 80"
        duration: 5m
      - metric: MemoryUtilization
        threshold: "> 85"
        duration: 3m
        
  # 日志查询联动
  log_query:
    project: "${instance_project}"
    logstore: "${instance_logstore}"
    query_template: |
      __topic__: system_log 
      and (cpu_usage > 80 or mem_usage > 85)
      and host_ip: ${instance_ip}
      | SELECT 
          date_trunc('minute', __time__) as time_bucket,
          COUNT(*) as error_count,
          MAX(cpu_usage) as max_cpu,
          MAX(mem_usage) as max_mem
      GROUP BY time_bucket
      ORDER BY time_bucket DESC
      LIMIT 100
    time_range: "-15m"
    
  # 输出配置
  output:
    destination: sls
    format: markdown_table
```

### 联动查询模板

```python
#!/usr/bin/env python3
"""
Metrics → Logs 联动查询模板
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class MetricsLogsLinkage:
    """Metrics 与 Logs 联动查询器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.metrics_client = None  # 云监控客户端
        self.logs_client = None     # SLS 客户端
    
    def correlate(self, metric_alert: Dict) -> Dict:
        """
        根据 Metrics 告警查询关联日志
        
        Args:
            metric_alert: 云监控告警信息
            
        Returns:
            关联分析结果
        """
        # 1. 解析告警信息
        instance_id = metric_alert.get("instanceId")
        metric_name = metric_alert.get("metricName")
        timestamp = metric_alert.get("timestamp")
        
        # 2. 构建时间范围 (告警前后15分钟)
        time_range = self._build_time_range(timestamp, minutes=15)
        
        # 3. 查询关联日志
        logs = self._query_correlated_logs(
            instance_id=instance_id,
            metric_name=metric_name,
            time_range=time_range
        )
        
        # 4. 分析关联性
        correlation = self._analyze_correlation(
            metric_alert=metric_alert,
            logs=logs
        )
        
        return {
            "metric_alert": metric_alert,
            "correlated_logs": logs,
            "analysis": correlation,
            "suggestions": self._generate_suggestions(correlation)
        }
    
    def _build_time_range(self, timestamp: int, minutes: int) -> tuple:
        """构建查询时间范围"""
        alert_time = datetime.fromtimestamp(timestamp)
        start_time = alert_time - timedelta(minutes=minutes)
        end_time = alert_time + timedelta(minutes=minutes)
        return (start_time, end_time)
    
    def _query_correlated_logs(self, instance_id: str, 
                               metric_name: str,
                               time_range: tuple) -> List[Dict]:
        """查询关联日志"""
        
        # SLS 查询语句模板
        query_templates = {
            "CPUUtilization": f"""
                __topic__: system_log 
                AND instance_id: {instance_id}
                AND (cpu_usage > 80 OR process_cpu_high)
                | SELECT 
                    date_format(__time__, '%Y-%m-%d %H:%i:%s') as time,
                    host_ip,
                    process_name,
                    cpu_usage,
                    mem_usage,
                    message
                ORDER BY __time__ DESC
                LIMIT 100
            """,
            "MemoryUtilization": f"""
                __topic__: system_log 
                AND instance_id: {instance_id}
                AND (mem_usage > 85 OR oom_event)
                | SELECT 
                    date_format(__time__, '%Y-%m-%d %H:%i:%s') as time,
                    host_ip,
                    process_name,
                    mem_usage,
                    mem_available,
                    message
                ORDER BY __time__ DESC
                LIMIT 100
            """,
            "DiskUtilization": f"""
                __topic__: system_log 
                AND instance_id: {instance_id}
                AND (disk_usage > 90 OR disk_full OR io_high)
                | SELECT 
                    date_format(__time__, '%Y-%m-%d %H:%i:%s') as time,
                    host_ip,
                    mount_point,
                    disk_usage,
                    io_util,
                    message
                ORDER BY __time__ DESC
                LIMIT 100
            """,
            "LoadAverage": f"""
                __topic__: system_log 
                AND instance_id: {instance_id}
                AND (load_average > {self.config.get('load_threshold', 10)}
                | SELECT 
                    date_format(__time__, '%Y-%m-%d %H:%i:%s') as time,
                    host_ip,
                    load_1m,
                    load_5m,
                    load_15m,
                    running_processes
                ORDER BY __time__ DESC
                LIMIT 100
            """
        }
        
        query = query_templates.get(metric_name, f"""
            __topic__: system_log 
            AND instance_id: {instance_id}
            | SELECT * 
            ORDER BY __time__ DESC 
            LIMIT 100
        """)
        
        # 执行查询
        return self._execute_sls_query(query, time_range)
    
    def _analyze_correlation(self, metric_alert: Dict, 
                            logs: List[Dict]) -> Dict:
        """分析 Metrics 与 Logs 关联性"""
        analysis = {
            "correlation_score": 0.0,
            "root_cause_candidates": [],
            "patterns": []
        }
        
        if not logs:
            analysis["correlation_score"] = 0.0
            return analysis
        
        # 计算关联分数
        error_logs = [l for l in logs if self._is_error_log(l)]
        analysis["correlation_score"] = len(error_logs) / len(logs)
        
        # 识别根因候选
        for log in error_logs[:10]:  # 分析前10条错误日志
            root_cause = self._identify_root_cause(log)
            if root_cause:
                analysis["root_cause_candidates"].append(root_cause)
        
        # 识别模式
        analysis["patterns"] = self._identify_patterns(logs)
        
        return analysis
    
    def _is_error_log(self, log: Dict) -> bool:
        """判断是否为错误日志"""
        error_keywords = ['error', 'exception', 'fatal', 'panic', 'oom', 'crash']
        message = str(log.get('message', '')).lower()
        return any(kw in message for kw in error_keywords)
    
    def _identify_root_cause(self, log: Dict) -> Optional[Dict]:
        """识别根因"""
        message = str(log.get('message', ''))
        
        # 根因模式匹配
        patterns = [
            (r"Out of memory", "OOM_KILL", "内存溢出，进程被杀死"),
            (r"No space left", "DISK_FULL", "磁盘空间不足"),
            (r"Too many open files", "FD_LIMIT", "文件描述符耗尽"),
            (r"Connection refused", "CONN_REFUSED", "连接被拒绝"),
            (r"Connection timeout", "CONN_TIMEOUT", "连接超时"),
        ]
        
        for pattern, code, desc in patterns:
            if pattern.lower() in message.lower():
                return {
                    "code": code,
                    "description": desc,
                    "evidence": log
                }
        
        return None
    
    def _identify_patterns(self, logs: List[Dict]) -> List[Dict]:
        """识别日志模式"""
        patterns = []
        
        # 时间聚集分析
        time_buckets = {}
        for log in logs:
            hour = log.get('time', '')[:13]  # 按小时聚合
            time_buckets[hour] = time_buckets.get(hour, 0) + 1
        
        if time_buckets:
            peak_hour = max(time_buckets, key=time_buckets.get)
            patterns.append({
                "type": "time_burst",
                "description": f"日志峰值出现在 {peak_hour}",
                "count": time_buckets[peak_hour]
            })
        
        return patterns
    
    def _generate_suggestions(self, correlation: Dict) -> List[str]:
        """生成建议"""
        suggestions = []
        
        candidates = correlation.get("root_cause_candidates", [])
        score = correlation.get("correlation_score", 0)
        
        if score > 0.7:
            suggestions.append("高关联度：Metrics 异常与日志错误高度相关")
        
        for candidate in candidates:
            code = candidate.get("code")
            if code == "OOM_KILL":
                suggestions.append("建议：增加实例内存或优化应用程序内存使用")
            elif code == "DISK_FULL":
                suggestions.append("建议：清理磁盘空间或扩容存储")
            elif code == "FD_LIMIT":
                suggestions.append("建议：增加文件描述符限制或检查连接泄露")
        
        return suggestions


# 使用示例
if __name__ == "__main__":
    config = {
        "sls_project": "my-project",
        "sls_endpoint": "cn-hangzhou.log.aliyuncs.com"
    }
    
    linkage = MetricsLogsLinkage(config)
    
    # 模拟告警
    alert = {
        "instanceId": "i-bp1xxxxxxxx",
        "metricName": "CPUUtilization",
        "timestamp": int(datetime.now().timestamp()),
        "value": 95.5
    }
    
    result = linkage.correlate(alert)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

## 2. Metrics → Traces 联动规则

### ARMS Trace 与 Metrics 联动

```yaml
# metrics-to-traces-linkage.yaml
linkage:
  name: "metrics-traces-correlation"
  description: "当应用 Metrics 触发告警时，自动查询 ARMS Trace"
  
  # 触发条件
  trigger:
    source: arms
    application: "${application_name}"
    conditions:
      - metric: rt
        threshold: "> 1000"
        duration: 2m
      - metric: error_rate
        threshold: "> 5%"
        duration: 1m
        
  # Trace 查询联动
  trace_query:
    service: "${service_name}"
    time_range: "-10m"
    filters:
      min_duration: 1000ms
      error_only: false
    
  # 分析维度
  analysis:
    - slow_traces        # 慢调用 Trace
    - error_traces       # 错误 Trace
    - dependency_map     # 依赖拓扑
    - flame_graph        # 火焰图
```

### Trace 查询模板

```python
#!/usr/bin/env python3
"""
Metrics → Traces 联动查询模板 (ARMS)
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class MetricsTracesLinkage:
    """Metrics 与 ARMS Trace 联动查询器"""
    
    def __init__(self, arms_client, config: Dict):
        self.arms_client = arms_client
        self.config = config
    
    def investigate_slow_calls(self, metric_alert: Dict) -> Dict:
        """
        根据慢调用告警查询 ARMS Trace
        """
        service = metric_alert.get("service")
        rt_threshold = metric_alert.get("threshold", 1000)
        
        # 构建查询条件
        query = {
            "serviceName": service,
            "startTime": self._get_start_time(10),  # 前10分钟
            "endTime": self._get_end_time(),
            "minDuration": rt_threshold,
            "sort": "duration",
            "order": "desc",
            "limit": 50
        }
        
        # 查询慢 Trace
        slow_traces = self._query_traces(query)
        
        # 分析根因
        analysis = self._analyze_slow_traces(slow_traces)
        
        return {
            "alert": metric_alert,
            "traces": slow_traces,
            "analysis": analysis,
            "recommendations": self._generate_recommendations(analysis)
        }
    
    def investigate_errors(self, metric_alert: Dict) -> Dict:
        """
        根据错误率告警查询 ARMS Trace
        """
        service = metric_alert.get("service")
        
        query = {
            "serviceName": service,
            "startTime": self._get_start_time(10),
            "endTime": self._get_end_time(),
            "statusCode": "5xx,4xx",
            "sort": "startTime",
            "order": "desc",
            "limit": 50
        }
        
        error_traces = self._query_traces(query)
        
        # 错误聚类分析
        analysis = self._analyze_error_traces(error_traces)
        
        return {
            "alert": metric_alert,
            "traces": error_traces,
            "analysis": analysis,
            "recommendations": self._generate_error_recommendations(analysis)
        }
    
    def _analyze_slow_traces(self, traces: List[Dict]) -> Dict:
        """分析慢调用 Trace"""
        analysis = {
            "total_slow_calls": len(traces),
            "duration_stats": self._calc_duration_stats(traces),
            "hot_spots": [],
            "bottleneck_services": set()
        }
        
        for trace in traces[:20]:  # 分析前20条
            # 分析 Span 层次结构
            spans = trace.get("spans", [])
            
            # 找出耗时最长的 Span
            max_span = max(spans, key=lambda s: s.get("duration", 0))
            
            analysis["hot_spots"].append({
                "trace_id": trace.get("traceId"),
                "total_duration": trace.get("duration"),
                "slowest_span": {
                    "service": max_span.get("serviceName"),
                    "operation": max_span.get("operationName"),
                    "duration": max_span.get("duration")
                }
            })
            
            analysis["bottleneck_services"].add(max_span.get("serviceName"))
        
        return analysis
    
    def _analyze_error_traces(self, traces: List[Dict]) -> Dict:
        """分析错误 Trace"""
        analysis = {
            "total_errors": len(traces),
            "error_types": {},
            "error_services": {},
            "stack_traces": []
        }
        
        for trace in traces:
            # 提取错误类型
            error_type = self._extract_error_type(trace)
            analysis["error_types"][error_type] = \
                analysis["error_types"].get(error_type, 0) + 1
            
            # 统计错误服务
            service = trace.get("serviceName")
            analysis["error_services"][service] = \
                analysis["error_services"].get(service, 0) + 1
            
            # 收集堆栈
            stack = trace.get("exceptionStack")
            if stack:
                analysis["stack_traces"].append(stack)
        
        # 排序
        analysis["error_types"] = dict(sorted(
            analysis["error_types"].items(), 
            key=lambda x: x[1], 
            reverse=True
        ))
        
        return analysis
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """生成慢调用优化建议"""
        recommendations = []
        
        hotspots = analysis.get("hot_spots", [])
        bottlenecks = analysis.get("bottleneck_services", set())
        
        if bottlenecks:
            recommendations.append(
                f"性能瓶颈服务: {', '.join(bottlenecks)}，建议优先优化"
            )
        
        if len(hotspots) > 10:
            recommendations.append(
                "慢调用数量较多，建议检查服务容量和依赖健康状态"
            )
        
        # 检查是否存在特定模式
        db_slow = any(
            "db" in str(h.get("slowest_span", {}).get("operation", "")).lower()
            for h in hotspots
        )
        if db_slow:
            recommendations.append(
                "检测到数据库操作耗时较长，建议优化 SQL 或增加连接池"
            )
        
        return recommendations
    
    def _generate_error_recommendations(self, analysis: Dict) -> List[str]:
        """生成错误处理建议"""
        recommendations = []
        
        error_types = analysis.get("error_types", {})
        
        if "TimeoutException" in error_types:
            recommendations.append(
                "存在超时异常，建议增加超时配置或优化接口响应时间"
            )
        
        if "ConnectionRefused" in error_types:
            recommendations.append(
                "存在连接拒绝错误，建议检查下游服务健康状态"
            )
        
        top_service = max(
            analysis.get("error_services", {}).items(),
            key=lambda x: x[1],
            default=(None, 0)
        )
        if top_service[0]:
            recommendations.append(
                f"错误主要集中在服务 {top_service[0]}，建议优先排查"
            )
        
        return recommendations
    
    def _get_start_time(self, minutes: int) -> int:
        """获取开始时间戳"""
        return int((datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000)
    
    def _get_end_time(self) -> int:
        """获取结束时间戳"""
        return int(datetime.now().timestamp() * 1000)
```

## 3. SLS 查询模板

### 常用查询模板库

```yaml
# sls-query-templates.yaml
templates:
  # 系统日志查询
  system_logs:
    high_cpu: |
      __topic__: system_log
      and cpu_usage > 80
      | SELECT 
          date_format(__time__, '%Y-%m-%d %H:%i') as time,
          AVG(cpu_usage) as avg_cpu,
          MAX(cpu_usage) as max_cpu,
          host_ip
      GROUP BY time, host_ip
      ORDER BY time DESC
      LIMIT 100
      
    oom_events: |
      __topic__: system_log
      and (message: "Out of memory" or message: "oom")
      | SELECT 
          __time__,
          host_ip,
          process_name,
          message
      ORDER BY __time__ DESC
      LIMIT 50
      
    disk_full: |
      __topic__: system_log
      and (message: "No space left" or disk_usage > 95)
      | SELECT 
          __time__,
          host_ip,
          mount_point,
          disk_usage,
          disk_available
      ORDER BY disk_usage DESC
      LIMIT 50
  
  # 应用日志查询
  application_logs:
    error_logs: |
      __topic__: app_log
      and level: ERROR
      | SELECT 
          __time__,
          service_name,
          trace_id,
          message,
          stack_trace
      ORDER BY __time__ DESC
      LIMIT 100
      
    slow_requests: |
      __topic__: app_log
      and request_time > 1000
      | SELECT 
          __time__,
          service_name,
          uri,
          request_time,
          status_code
      ORDER BY request_time DESC
      LIMIT 100
      
    exception_analysis: |
      __topic__: app_log
      and exception is not null
      | SELECT 
          exception_type,
          COUNT(*) as count,
          FIRST(message) as sample_message
      GROUP BY exception_type
      ORDER BY count DESC
      LIMIT 20
  
  # 安全日志查询
  security_logs:
    failed_logins: |
      __topic__: security_log
      and event: login_failed
      | SELECT 
          __time__,
          source_ip,
          username,
          COUNT(*) as fail_count
      GROUP BY source_ip, username
      ORDER BY fail_count DESC
      LIMIT 50
      
    suspicious_access: |
      __topic__: security_log
      and (status: denied or risk_score > 70)
      | SELECT 
          __time__,
          source_ip,
          target_resource,
          action,
          risk_score
      ORDER BY risk_score DESC
      LIMIT 100
```

## 4. ARMS Trace 查询模板

```yaml
# arms-trace-templates.yaml
templates:
  # 慢调用查询
  slow_traces:
    query: |
      {
        "serviceName": "${service}",
        "minDuration": ${min_duration},
        "startTime": ${start_time},
        "endTime": ${end_time},
        "limit": 50
      }
    analysis:
      - duration_percentile
      - span_breakdown
      - dependency_analysis
      
  # 错误调用查询
  error_traces:
    query: |
      {
        "serviceName": "${service}",
        "statusCode": "5xx",
        "startTime": ${start_time},
        "endTime": ${end_time},
        "limit": 50
      }
    analysis:
      - error_classification
      - stack_trace_analysis
      - root_cause_identification
      
  # 特定 Trace 详情
  trace_detail:
    query: |
      {
        "traceId": "${trace_id}"
      }
    analysis:
      - span_tree
      - timeline
      - flame_graph
      - dependency_map
```

## 5. 降级策略模板

```yaml
# observability-degradation.yaml
degradation:
  # Metrics 采集降级
  metrics:
    levels:
      - level: normal
        collection_interval: 15s
        enabled_metrics: "*"
        
      - level: warning
        collection_interval: 60s
        enabled_metrics: 
          - cpu
          - memory
          - disk
        disabled_metrics:
          - network_detail
          - io_detail
          
      - level: critical
        collection_interval: 300s
        enabled_metrics:
          - cpu
          - memory
        disabled_metrics: "*"
        
  # 日志采集降级
  logs:
    levels:
      - level: normal
        sampling: 1.0
        log_levels: [DEBUG, INFO, WARN, ERROR]
        
      - level: warning
        sampling: 0.5
        log_levels: [INFO, WARN, ERROR]
        filter_rules:
          - exclude: "health_check"
          - exclude: "metrics_log"
          
      - level: critical
        sampling: 0.1
        log_levels: [WARN, ERROR]
        buffer_size: 1000
        
  # Trace 采样降级
  traces:
    levels:
      - level: normal
        sampling_rate: 1.0
        span_limit: 10000
        
      - level: warning
        sampling_rate: 0.1
        span_limit: 5000
        priority_sampling:
          error_traces: 1.0
          slow_traces: 0.5
          normal_traces: 0.01
          
      - level: critical
        sampling_rate: 0.01
        span_limit: 1000
        priority_sampling:
          error_traces: 0.5
          slow_traces: 0.1
          normal_traces: 0
          
  # 自动降级触发条件
  triggers:
    - condition: "cpu_usage > 90"
      action: "degrade_logs"
      target_level: "warning"
      
    - condition: "memory_usage > 85"
      action: "degrade_traces"
      target_level: "warning"
      
    - condition: "disk_io_wait > 80"
      action: "degrade_all"
      target_level: "critical"
      
  # 恢复策略
  recovery:
    cooldown: 300s
    conditions:
      - resource_usage < 70
      - consecutive_checks: 3
```

### 降级控制器实现

```python
#!/usr/bin/env python3
"""
可观测性降级控制器
"""
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
import time


class DegradationLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricsConfig:
    collection_interval: int
    enabled_metrics: list
    disabled_metrics: list


@dataclass
class LogsConfig:
    sampling: float
    log_levels: list
    filter_rules: list


@dataclass
class TracesConfig:
    sampling_rate: float
    span_limit: int
    priority_sampling: dict


class ObservabilityDegradationController:
    """可观测性降级控制器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.current_level = DegradationLevel.NORMAL
        self.last_change_time = time.time()
        self.consecutive_normal = 0
    
    def check_and_apply(self, metrics: Dict) -> DegradationLevel:
        """
        检查系统状态并应用降级策略
        """
        # 评估当前状态
        level = self._evaluate_level(metrics)
        
        # 检查是否可以升级
        if level == DegradationLevel.NORMAL:
            self.consecutive_normal += 1
        else:
            self.consecutive_normal = 0
        
        # 应用降级
        if level != self.current_level:
            if self._can_change_level(level):
                self._apply_degradation(level)
                self.current_level = level
        
        return self.current_level
    
    def _evaluate_level(self, metrics: Dict) -> DegradationLevel:
        """评估当前降级级别"""
        cpu = metrics.get("cpu_usage", 0)
        memory = metrics.get("memory_usage", 0)
        disk_io = metrics.get("disk_io_wait", 0)
        
        # 检查 critical 条件
        if cpu > 95 or memory > 95 or disk_io > 90:
            return DegradationLevel.CRITICAL
        
        # 检查 warning 条件
        if cpu > 85 or memory > 80 or disk_io > 70:
            return DegradationLevel.WARNING
        
        return DegradationLevel.NORMAL
    
    def _can_change_level(self, new_level: DegradationLevel) -> bool:
        """检查是否允许切换级别"""
        # 冷却期检查
        cooldown = self.config.get("recovery", {}).get("cooldown", 300)
        if time.time() - self.last_change_time < cooldown:
            return False
        
        # 如果是升级 (降级 -> 正常)，需要连续检查通过
        if new_level == DegradationLevel.NORMAL and self.current_level != DegradationLevel.NORMAL:
            required = self.config.get("recovery", {}).get("consecutive_checks", 3)
            return self.consecutive_normal >= required
        
        # 降级可以直接执行
        if new_level.value > self.current_level.value:
            return True
        
        return True
    
    def _apply_degradation(self, level: DegradationLevel):
        """应用降级配置"""
        level_config = self.config.get(level.value, {})
        
        # 应用 Metrics 降级
        metrics_config = level_config.get("metrics", {})
        self._apply_metrics_degradation(metrics_config)
        
        # 应用 Logs 降级
        logs_config = level_config.get("logs", {})
        self._apply_logs_degradation(logs_config)
        
        # 应用 Trace 降级
        traces_config = level_config.get("traces", {})
        self._apply_traces_degradation(traces_config)
        
        self.last_change_time = time.time()
    
    def _apply_metrics_degradation(self, config: Dict):
        """应用 Metrics 降级"""
        print(f"[Degradation] Metrics interval: {config.get('collection_interval')}s")
        print(f"[Degradation] Enabled metrics: {config.get('enabled_metrics', [])}")
    
    def _apply_logs_degradation(self, config: Dict):
        """应用 Logs 降级"""
        print(f"[Degradation] Log sampling: {config.get('sampling')}")
        print(f"[Degradation] Log levels: {config.get('log_levels', [])}")
    
    def _apply_traces_degradation(self, config: Dict):
        """应用 Trace 降级"""
        print(f"[Degradation] Trace sampling: {config.get('sampling_rate')}")
        print(f"[Degradation] Span limit: {config.get('span_limit')}")


# 使用示例
if __name__ == "__main__":
    config = {
        "recovery": {
            "cooldown": 300,
            "consecutive_checks": 3
        }
    }
    
    controller = ObservabilityDegradationController(config)
    
    # 模拟检查
    metrics = {"cpu_usage": 90, "memory_usage": 85}
    level = controller.check_and_apply(metrics)
    print(f"Current degradation level: {level}")
```

## 使用指南

1. **配置联动规则**: 编辑 YAML 配置文件
2. **部署查询模板**: 将模板集成到监控系统中
3. **设置降级策略**: 根据业务需求调整降级参数
4. **测试联动**: 手动触发告警验证联动效果
