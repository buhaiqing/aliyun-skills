# 主动巡检流程模板

五步闭环主动巡检流程模板。

## 1. 五步闭环模板结构

```
proactive-inspection/
├── config/
│   ├── inspection.yaml       # 巡检配置
│   └── targets.yaml          # 巡检目标清单
├── workflows/
│   ├── discovery.py          # 发现阶段
│   ├── collection.py         # 采集阶段
│   ├── detection.py          # 检测阶段
│   ├── diagnosis.py          # 诊断阶段
│   └── report.py             # 报告阶段
├── scripts/
│   ├── cli_inspection.sh     # CLI 执行脚本
│   └── automation.py         # 自动化脚本
├── reports/
│   └── template.md           # 报告模板
└── README.md
```

## 2. Discovery (发现)

### 资源发现模板

```python
#!/usr/bin/env python3
"""
资源发现模块 - 自动发现待巡检资源
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class Resource:
    """资源对象"""
    resource_id: str
    resource_type: str
    region: str
    name: str
    tags: Dict
    metadata: Dict


class ResourceDiscovery(ABC):
    """资源发现抽象基类"""
    
    @abstractmethod
    def discover(self, filters: Optional[Dict] = None) -> List[Resource]:
        """执行资源发现"""
        pass


class ECSResourceDiscovery(ResourceDiscovery):
    """ECS 资源发现"""
    
    def __init__(self, client):
        self.client = client
    
    def discover(self, filters: Optional[Dict] = None) -> List[Resource]:
        """发现 ECS 实例"""
        resources = []
        
        # 查询所有区域
        regions = self._get_regions()
        
        for region in regions:
            # 构建查询请求
            request = {
                'RegionId': region,
                'PageSize': 100
            }
            
            if filters:
                if 'instance_ids' in filters:
                    request['InstanceIds'] = filters['instance_ids']
                if 'tags' in filters:
                    request['Tag'] = filters['tags']
            
            # 分页查询
            page = 1
            while True:
                request['PageNumber'] = page
                response = self.client.describe_instances(**request)
                
                for instance in response.get('Instances', {}).get('Instance', []):
                    resource = Resource(
                        resource_id=instance['InstanceId'],
                        resource_type='ECS',
                        region=region,
                        name=instance.get('InstanceName', ''),
                        tags={tag['TagKey']: tag['TagValue'] 
                              for tag in instance.get('Tags', {}).get('Tag', [])},
                        metadata={
                            'status': instance.get('Status'),
                            'instance_type': instance.get('InstanceType'),
                            'cpu': instance.get('Cpu'),
                            'memory': instance.get('Memory')
                        }
                    )
                    resources.append(resource)
                
                if len(response.get('Instances', {}).get('Instance', [])) < 100:
                    break
                page += 1
        
        return resources
    
    def _get_regions(self) -> List[str]:
        """获取所有可用区域"""
        response = self.client.describe_regions()
        return [r['RegionId'] for r in response.get('Regions', {}).get('Region', [])]


class RDSResourceDiscovery(ResourceDiscovery):
    """RDS 资源发现"""
    
    def __init__(self, client):
        self.client = client
    
    def discover(self, filters: Optional[Dict] = None) -> List[Resource]:
        """发现 RDS 实例"""
        resources = []
        regions = self._get_regions()
        
        for region in regions:
            request = {
                'RegionId': region,
                'PageSize': 100
            }
            
            response = self.client.describe_db_instances(**request)
            
            for db in response.get('Items', {}).get('DBInstance', []):
                resource = Resource(
                    resource_id=db['DBInstanceId'],
                    resource_type='RDS',
                    region=region,
                    name=db.get('DBInstanceDescription', ''),
                    tags={},
                    metadata={
                        'engine': db.get('Engine'),
                        'status': db.get('DBInstanceStatus'),
                        'instance_type': db.get('DBInstanceClass')
                    }
                )
                resources.append(resource)
        
        return resources


class DiscoveryPipeline:
    """发现流水线"""
    
    def __init__(self):
        self.discoveries: List[ResourceDiscovery] = []
    
    def register(self, discovery: ResourceDiscovery):
        """注册发现器"""
        self.discoveries.append(discovery)
    
    def run(self, filters: Optional[Dict] = None) -> Dict[str, List[Resource]]:
        """执行所有发现"""
        results = {}
        
        for discovery in self.discoveries:
            resources = discovery.discover(filters)
            resource_type = resources[0].resource_type if resources else 'Unknown'
            results[resource_type] = resources
        
        return results
    
    def export_inventory(self, results: Dict, filepath: str):
        """导出资源清单"""
        import json
        
        inventory = {
            'generated_at': datetime.now().isoformat(),
            'total_resources': sum(len(r) for r in results.values()),
            'resources_by_type': {
                rtype: [
                    {
                        'resource_id': r.resource_id,
                        'region': r.region,
                        'name': r.name,
                        'tags': r.tags
                    }
                    for r in resources
                ]
                for rtype, resources in results.items()
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)


# 配置示例
discovery_config = '''
# discovery-config.yaml
discovery:
  # 启用发现的资源类型
  enabled_types:
    - ECS
    - RDS
    - Redis
    - SLB
    - OSS
    
  # 过滤条件
  filters:
    # 只发现特定标签的资源
    tags:
      - Key: Environment
        Value: Production
      - Key: ManagedBy
        Value: Ops
    
    # 排除特定资源
    exclude:
      instance_ids:
        - i-excluded1
        - i-excluded2
      name_patterns:
        - "*test*"
        - "*temp*"
      
  # 区域范围
  regions:
    - cn-hangzhou
    - cn-beijing
    - cn-shanghai
'''
```

## 3. Collection (采集)

### 指标采集模板

```python
#!/usr/bin/env python3
"""
指标采集模块 - 采集资源指标数据
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


@dataclass
class MetricData:
    """指标数据"""
    resource_id: str
    metric_name: str
    timestamp: datetime
    value: float
    unit: str
    labels: Dict[str, str]


@dataclass
class CollectionTask:
    """采集任务"""
    resource: 'Resource'
    metrics: List[str]
    start_time: datetime
    end_time: datetime


class MetricCollector:
    """指标采集器"""
    
    def __init__(self, cloud_monitor_client):
        self.client = cloud_monitor_client
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def collect(self, tasks: List[CollectionTask]) -> Dict[str, List[MetricData]]:
        """
        并行采集指标
        
        Args:
            tasks: 采集任务列表
            
        Returns:
            按资源 ID 组织的指标数据
        """
        results = {}
        
        # 提交所有任务
        futures = {
            self.executor.submit(self._collect_single, task): task
            for task in tasks
        }
        
        # 收集结果
        for future in as_completed(futures):
            task = futures[future]
            try:
                metrics = future.result()
                results[task.resource.resource_id] = metrics
            except Exception as e:
                print(f"采集失败 {task.resource.resource_id}: {e}")
                results[task.resource.resource_id] = []
        
        return results
    
    def _collect_single(self, task: CollectionTask) -> List[MetricData]:
        """采集单个资源的指标"""
        metrics = []
        
        for metric_name in task.metrics:
            try:
                data = self._query_metric(
                    resource=task.resource,
                    metric_name=metric_name,
                    start_time=task.start_time,
                    end_time=task.end_time
                )
                metrics.extend(data)
            except Exception as e:
                print(f"指标 {metric_name} 采集失败: {e}")
        
        return metrics
    
    def _query_metric(self, resource: 'Resource',
                     metric_name: str,
                     start_time: datetime,
                     end_time: datetime) -> List[MetricData]:
        """查询单个指标"""
        # 根据资源类型构建查询
        dimensions = self._build_dimensions(resource)
        
        response = self.client.describe_metric_list(
            Namespace=f'acs_{resource.resource_type.lower()}',
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time.isoformat(),
            EndTime=end_time.isoformat(),
            Period='60'
        )
        
        metrics = []
        for datapoint in response.get('Datapoints', []):
            metrics.append(MetricData(
                resource_id=resource.resource_id,
                metric_name=metric_name,
                timestamp=datetime.fromtimestamp(datapoint['timestamp'] / 1000),
                value=datapoint['Average'],
                unit=datapoint.get('Unit', ''),
                labels={'resource_type': resource.resource_type}
            ))
        
        return metrics
    
    def _build_dimensions(self, resource: 'Resource') -> str:
        """构建维度字符串"""
        dimension_map = {
            'ECS': f'[{{"instanceId": "{resource.resource_id}"}}]',
            'RDS': f'[{{"instanceId": "{resource.resource_id}"}}]',
            'Redis': f'[{{"instanceId": "{resource.resource_id}"}}]',
        }
        return dimension_map.get(resource.resource_type, '[]')


class CollectionPipeline:
    """采集流水线"""
    
    def __init__(self, collector: MetricCollector):
        self.collector = collector
        self.metric_definitions = self._load_metric_definitions()
    
    def _load_metric_definitions(self) -> Dict[str, List[str]]:
        """加载指标定义"""
        return {
            'ECS': [
                'CPUUtilization',
                'memory_usedutilization',
                'DiskReadIOPS',
                'DiskWriteIOPS',
                'InternetInRate',
                'InternetOutRate',
                'LoadAverage'
            ],
            'RDS': [
                'CpuUsage',
                'MemoryUsage',
                'IOPSUsage',
                'ConnectionUsage',
                'DataDelay'
            ],
            'Redis': [
                'UsedMemory',
                'CpuUsage',
                'IntranetIn',
                'IntranetOut',
                'ConnectionUsage'
            ]
        }
    
    def create_tasks(self, resources: List['Resource'],
                    time_range_minutes: int = 60) -> List[CollectionTask]:
        """创建采集任务"""
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        
        tasks = []
        for resource in resources:
            metrics = self.metric_definitions.get(resource.resource_type, [])
            if metrics:
                tasks.append(CollectionTask(
                    resource=resource,
                    metrics=metrics,
                    start_time=start_time,
                    end_time=end_time
                ))
        
        return tasks
    
    def collect_with_retry(self, tasks: List[CollectionTask],
                          max_retries: int = 3) -> Dict[str, List[MetricData]]:
        """带重试的采集"""
        results = {}
        failed_tasks = []
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"第 {attempt} 次重试，任务数: {len(failed_tasks)}")
                tasks = failed_tasks
                failed_tasks = []
                time.sleep(2 ** attempt)  # 指数退避
            
            batch_results = self.collector.collect(tasks)
            
            for resource_id, metrics in batch_results.items():
                if metrics:
                    results[resource_id] = metrics
                else:
                    # 找到对应的任务
                    task = next((t for t in tasks if t.resource.resource_id == resource_id), None)
                    if task:
                        failed_tasks.append(task)
            
            if not failed_tasks:
                break
        
        if failed_tasks:
            print(f"最终失败任务数: {len(failed_tasks)}")
        
        return results


# 采集配置
collection_config = '''
# collection-config.yaml
collection:
  # 并发配置
  concurrency:
    max_workers: 10
    requests_per_second: 50
    
  # 时间范围
  time_range:
    minutes: 60  # 采集最近60分钟数据
    
  # 重试配置
  retry:
    max_retries: 3
    backoff: exponential
    
  # 指标配置
  metrics:
    ECS:
      - CPUUtilization
      - memory_usedutilization
      - LoadAverage
    RDS:
      - CpuUsage
      - MemoryUsage
      - ConnectionUsage
    Redis:
      - UsedMemory
      - CpuUsage
'''
```

## 4. Detection (检测)

### 异常检测模板

```python
#!/usr/bin/env python3
"""
异常检测模块 - 检测资源指标异常
"""
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import statistics


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """异常检测结果"""
    resource_id: str
    resource_type: str
    metric_name: str
    level: AlertLevel
    message: str
    current_value: float
    threshold: float
    timestamp: datetime
    suggestions: List[str]


class DetectionRule:
    """检测规则"""
    
    def __init__(self, name: str, metric: str,
                 check_func: Callable[[List[float]], tuple],
                 level: AlertLevel = AlertLevel.WARNING):
        self.name = name
        self.metric = metric
        self.check_func = check_func
        self.level = level


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self):
        self.rules: List[DetectionRule] = []
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认检测规则"""
        
        # CPU 使用率检测
        self.add_rule(DetectionRule(
            name="CPU使用率过高",
            metric="CPUUtilization",
            check_func=self._check_threshold(threshold=80, duration=3),
            level=AlertLevel.WARNING
        ))
        
        self.add_rule(DetectionRule(
            name="CPU使用率严重过高",
            metric="CPUUtilization",
            check_func=self._check_threshold(threshold=95, duration=3),
            level=AlertLevel.CRITICAL
        ))
        
        # 内存使用率检测
        self.add_rule(DetectionRule(
            name="内存使用率过高",
            metric="memory_usedutilization",
            check_func=self._check_threshold(threshold=85, duration=3),
            level=AlertLevel.WARNING
        ))
        
        # 负载检测
        self.add_rule(DetectionRule(
            name="系统负载过高",
            metric="LoadAverage",
            check_func=self._check_load_average(),
            level=AlertLevel.WARNING
        ))
        
        # 突发检测
        self.add_rule(DetectionRule(
            name="CPU使用率突增",
            metric="CPUUtilization",
            check_func=self._check_spike(threshold=30, window=5),
            level=AlertLevel.WARNING
        ))
    
    def add_rule(self, rule: DetectionRule):
        """添加检测规则"""
        self.rules.append(rule)
    
    def detect(self, resource: 'Resource',
               metrics: List['MetricData']) -> List[Anomaly]:
        """
        检测资源异常
        
        Args:
            resource: 资源对象
            metrics: 指标数据列表
            
        Returns:
            异常列表
        """
        anomalies = []
        
        # 按指标分组
        metrics_by_name = {}
        for m in metrics:
            if m.metric_name not in metrics_by_name:
                metrics_by_name[m.metric_name] = []
            metrics_by_name[m.metric_name].append(m.value)
        
        # 应用规则检测
        for rule in self.rules:
            if rule.metric not in metrics_by_name:
                continue
            
            values = metrics_by_name[rule.metric]
            is_anomaly, details = rule.check_func(values)
            
            if is_anomaly:
                anomaly = Anomaly(
                    resource_id=resource.resource_id,
                    resource_type=resource.resource_type,
                    metric_name=rule.metric,
                    level=rule.level,
                    message=rule.name,
                    current_value=values[-1] if values else 0,
                    threshold=details.get('threshold', 0),
                    timestamp=datetime.now(),
                    suggestions=self._generate_suggestions(rule.name, details)
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _check_threshold(self, threshold: float, duration: int):
        """阈值检测"""
        def check(values: List[float]) -> tuple:
            if len(values) < duration:
                return False, {}
            
            # 检查最近 duration 个值是否都超过阈值
            recent = values[-duration:]
            if all(v > threshold for v in recent):
                return True, {'threshold': threshold, 'values': recent}
            
            return False, {}
        
        return check
    
    def _check_spike(self, threshold: float, window: int):
        """突变检测"""
        def check(values: List[float]) -> tuple:
            if len(values) < window * 2:
                return False, {}
            
            # 计算前后窗口平均值
            prev_window = values[-window*2:-window]
            curr_window = values[-window:]
            
            prev_avg = statistics.mean(prev_window)
            curr_avg = statistics.mean(curr_window)
            
            # 检查是否超过阈值
            if prev_avg > 0 and (curr_avg - prev_avg) / prev_avg * 100 > threshold:
                return True, {
                    'threshold': threshold,
                    'prev_avg': prev_avg,
                    'curr_avg': curr_avg,
                    'increase_pct': (curr_avg - prev_avg) / prev_avg * 100
                }
            
            return False, {}
        
        return check
    
    def _check_load_average(self):
        """负载检测"""
        def check(values: List[float]) -> tuple:
            if not values:
                return False, {}
            
            # 简单判断：负载超过 CPU 核心数的 2 倍
            current_load = values[-1]
            threshold = 2.0  # 假设 1 核
            
            if current_load > threshold:
                return True, {'threshold': threshold}
            
            return False, {}
        
        return check
    
    def _generate_suggestions(self, rule_name: str, details: Dict) -> List[str]:
        """生成建议"""
        suggestions = []
        
        if "CPU" in rule_name:
            suggestions.append("检查是否有高 CPU 消耗的进程")
            suggestions.append("考虑扩容或优化应用代码")
        
        if "内存" in rule_name:
            suggestions.append("检查内存泄漏")
            suggestions.append("考虑增加实例内存")
        
        if "负载" in rule_name:
            suggestions.append("检查运行进程数量")
            suggestions.append("优化应用性能或增加实例")
        
        if "突增" in rule_name:
            suggestions.append("检查是否有突发流量")
            suggestions.append("查看应用日志定位原因")
        
        return suggestions


class DetectionPipeline:
    """检测流水线"""
    
    def __init__(self, detector: AnomalyDetector):
        self.detector = detector
        self.anomaly_history: List[Anomaly] = []
    
    def run(self, resources: List['Resource'],
           metrics_map: Dict[str, List['MetricData']]) -> List[Anomaly]:
        """执行检测"""
        all_anomalies = []
        
        for resource in resources:
            metrics = metrics_map.get(resource.resource_id, [])
            if not metrics:
                continue
            
            anomalies = self.detector.detect(resource, metrics)
            all_anomalies.extend(anomalies)
        
        # 保存历史
        self.anomaly_history.extend(all_anomalies)
        
        return all_anomalies
    
    def get_summary(self, anomalies: List[Anomaly]) -> Dict:
        """获取异常摘要"""
        summary = {
            'total': len(anomalies),
            'by_level': {},
            'by_resource_type': {},
            'by_metric': {}
        }
        
        for anomaly in anomalies:
            # 按级别统计
            level = anomaly.level.value
            summary['by_level'][level] = summary['by_level'].get(level, 0) + 1
            
            # 按资源类型统计
            rtype = anomaly.resource_type
            summary['by_resource_type'][rtype] = summary['by_resource_type'].get(rtype, 0) + 1
            
            # 按指标统计
            metric = anomaly.metric_name
            summary['by_metric'][metric] = summary['by_metric'].get(metric, 0) + 1
        
        return summary
```

## 5. Diagnosis (诊断)

### 根因分析模板

```python
#!/usr/bin/env python3
"""
根因诊断模块 - 分析异常根因
"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class RootCauseType(Enum):
    """根因类型"""
    RESOURCE_EXHAUSTION = "资源耗尽"
    CONFIGURATION_ERROR = "配置错误"
    DEPENDENCY_FAILURE = "依赖故障"
    TRAFFIC_SPIKE = "流量突增"
    CODE_DEFECT = "代码缺陷"
    EXTERNAL_FACTOR = "外部因素"
    UNKNOWN = "未知"


@dataclass
class DiagnosisResult:
    """诊断结果"""
    resource_id: str
    anomaly: 'Anomaly'
    root_cause: RootCauseType
    confidence: float
    details: Dict
    evidence: List[str]
    recommendations: List[str]


class RootCauseAnalyzer:
    """根因分析器"""
    
    def __init__(self, log_client=None, trace_client=None):
        self.log_client = log_client
        self.trace_client = trace_client
        self.diagnosis_rules = self._init_rules()
    
    def _init_rules(self) -> List[Dict]:
        """初始化诊断规则"""
        return [
            {
                'name': 'OOM诊断',
                'condition': lambda a: '内存' in a.message,
                'analyzer': self._diagnose_oom
            },
            {
                'name': 'CPU诊断',
                'condition': lambda a: 'CPU' in a.message,
                'analyzer': self._diagnose_cpu
            },
            {
                'name': '负载诊断',
                'condition': lambda a: '负载' in a.message,
                'analyzer': self._diagnose_load
            }
        ]
    
    def diagnose(self, resource: 'Resource', 
                anomaly: 'Anomaly',
                context: Optional[Dict] = None) -> DiagnosisResult:
        """
        诊断异常根因
        
        Args:
            resource: 资源对象
            anomaly: 异常对象
            context: 上下文信息
            
        Returns:
            诊断结果
        """
        # 查找匹配的 diagnostic 规则
        for rule in self.diagnosis_rules:
            if rule['condition'](anomaly):
                return rule['analyzer'](resource, anomaly, context)
        
        # 默认诊断
        return self._default_diagnosis(resource, anomaly)
    
    def _diagnose_oom(self, resource: 'Resource', 
                     anomaly: 'Anomaly',
                     context: Optional[Dict]) -> DiagnosisResult:
        """OOM 诊断"""
        evidence = []
        details = {}
        
        # 查询系统日志
        if self.log_client:
            logs = self._query_system_logs(
                resource.resource_id,
                keywords=['Out of memory', 'oom', 'killed']
            )
            evidence.extend([f"日志: {log}" for log in logs[:5]])
        
        # 分析内存趋势
        if context and 'metrics' in context:
            mem_metrics = [m for m in context['metrics'] 
                          if m.metric_name == 'memory_usedutilization']
            if mem_metrics:
                values = [m.value for m in mem_metrics]
                details['memory_trend'] = 'increasing' if values[-1] > values[0] else 'stable'
                details['peak_memory'] = max(values)
        
        # 确定根因
        if evidence and 'killed' in str(evidence).lower():
            root_cause = RootCauseType.RESOURCE_EXHAUSTION
            confidence = 0.9
        else:
            root_cause = RootCauseType.CODE_DEFECT
            confidence = 0.6
        
        recommendations = [
            "检查应用程序内存泄漏",
            "考虑增加实例内存配置",
            "优化应用内存使用"
        ]
        
        return DiagnosisResult(
            resource_id=resource.resource_id,
            anomaly=anomaly,
            root_cause=root_cause,
            confidence=confidence,
            details=details,
            evidence=evidence,
            recommendations=recommendations
        )
    
    def _diagnose_cpu(self, resource: 'Resource',
                     anomaly: 'Anomaly',
                     context: Optional[Dict]) -> DiagnosisResult:
        """CPU 诊断"""
        evidence = []
        details = {}
        
        # 查询进程信息
        if context and 'process_info' in context:
            top_processes = context['process_info'].get('top_cpu_processes', [])
            if top_processes:
                evidence.append(f"CPU 消耗最高的进程: {top_processes[0]}")
                details['top_process'] = top_processes[0]
        
        # 分析是否为流量突增
        if context and 'traffic' in context:
            traffic = context['traffic']
            if traffic.get('qps_increase', 0) > 50:
                root_cause = RootCauseType.TRAFFIC_SPIKE
                confidence = 0.85
                evidence.append(f"QPS 增长: {traffic['qps_increase']:.1f}%")
            else:
                root_cause = RootCauseType.CODE_DEFECT
                confidence = 0.7
        else:
            root_cause = RootCauseType.UNKNOWN
            confidence = 0.5
        
        recommendations = [
            "检查高 CPU 消耗进程",
            "分析应用代码性能瓶颈",
            "考虑扩容或优化代码"
        ]
        
        return DiagnosisResult(
            resource_id=resource.resource_id,
            anomaly=anomaly,
            root_cause=root_cause,
            confidence=confidence,
            details=details,
            evidence=evidence,
            recommendations=recommendations
        )
    
    def _diagnose_load(self, resource: 'Resource',
                      anomaly: 'Anomaly',
                      context: Optional[Dict]) -> DiagnosisResult:
        """负载诊断"""
        evidence = []
        
        # 检查进程数量
        if context and 'process_count' in context:
            count = context['process_count']
            if count > 500:
                evidence.append(f"运行进程过多: {count}")
                root_cause = RootCauseType.RESOURCE_EXHAUSTION
                confidence = 0.8
            else:
                root_cause = RootCauseType.CODE_DEFECT
                confidence = 0.6
        else:
            root_cause = RootCauseType.UNKNOWN
            confidence = 0.5
        
        recommendations = [
            "检查僵尸进程",
            "优化应用线程使用",
            "检查是否有进程泄露"
        ]
        
        return DiagnosisResult(
            resource_id=resource.resource_id,
            anomaly=anomaly,
            root_cause=root_cause,
            confidence=confidence,
            details={'load': anomaly.current_value},
            evidence=evidence,
            recommendations=recommendations
        )
    
    def _default_diagnosis(self, resource: 'Resource',
                          anomaly: 'Anomaly') -> DiagnosisResult:
        """默认诊断"""
        return DiagnosisResult(
            resource_id=resource.resource_id,
            anomaly=anomaly,
            root_cause=RootCauseType.UNKNOWN,
            confidence=0.3,
            details={},
            evidence=["无法确定根因，需要进一步调查"],
            recommendations=["收集更多信息", "查看详细日志"]
        )
    
    def _query_system_logs(self, resource_id: str, 
                          keywords: List[str]) -> List[str]:
        """查询系统日志"""
        if not self.log_client:
            return []
        
        # 构建 SLS 查询
        query = f"""
            __topic__: system_log
            and instance_id: {resource_id}
            and ({' or '.join([f'message: "{k}"' for k in keywords])})
            | SELECT message
            ORDER BY __time__ DESC
            LIMIT 10
        """
        
        # 执行查询
        try:
            result = self.log_client.get_logs(query=query)
            return [log.get('message', '') for log in result]
        except Exception as e:
            return [f"查询失败: {e}"]


class DiagnosisPipeline:
    """诊断流水线"""
    
    def __init__(self, analyzer: RootCauseAnalyzer):
        self.analyzer = analyzer
        self.results: List[DiagnosisResult] = []
    
    def run(self, resources: List['Resource'],
           anomalies: List['Anomaly'],
           context_map: Optional[Dict] = None) -> List[DiagnosisResult]:
        """执行诊断"""
        results = []
        context_map = context_map or {}
        
        for anomaly in anomalies:
            # 找到对应的资源
            resource = next(
                (r for r in resources if r.resource_id == anomaly.resource_id),
                None
            )
            
            if not resource:
                continue
            
            # 获取上下文
            context = context_map.get(anomaly.resource_id, {})
            
            # 执行诊断
            result = self.analyzer.diagnose(resource, anomaly, context)
            results.append(result)
        
        self.results.extend(results)
        return results
    
    def get_summary(self) -> Dict:
        """获取诊断摘要"""
        summary = {
            'total_diagnosed': len(self.results),
            'by_root_cause': {},
            'high_confidence': 0
        }
        
        for result in self.results:
            cause = result.root_cause.value
            summary['by_root_cause'][cause] = summary['by_root_cause'].get(cause, 0) + 1
            
            if result.confidence > 0.8:
                summary['high_confidence'] += 1
        
        return summary
```

## 6. Report (报告)

### 报告生成模板

```markdown
# 主动巡检报告

## 基本信息

| 项目 | 值 |
|------|-----|
| 巡检时间 | {{inspection_time}} |
| 巡检范围 | {{resource_count}} 个资源 |
| 资源类型 | {{resource_types}} |
| 巡检时长 | {{duration}} 分钟 |

## 执行概况

### 五步闭环状态

| 阶段 | 状态 | 耗时 | 结果 |
|------|------|------|------|
| Discovery | ✅ 完成 | {{discovery_time}}s | 发现 {{discovered_count}} 个资源 |
| Collection | ✅ 完成 | {{collection_time}}s | 采集 {{metrics_count}} 条指标 |
| Detection | ✅ 完成 | {{detection_time}}s | 发现 {{anomaly_count}} 个异常 |
| Diagnosis | ✅ 完成 | {{diagnosis_time}}s | 完成 {{diagnosed_count}} 个诊断 |
| Report | ✅ 完成 | {{report_time}}s | 生成完整报告 |

## 资源概览

### 按类型分布

| 资源类型 | 数量 | 占比 |
|----------|------|------|
{{resource_type_table}}

### 按区域分布

| 区域 | ECS | RDS | Redis | 合计 |
|------|-----|-----|-------|------|
{{region_table}}

## 异常摘要

### 概览

- **总异常数**: {{total_anomalies}}
- **严重级别**: {{critical_count}} 个
- **警告级别**: {{warning_count}} 个
- **信息级别**: {{info_count}} 个

### 异常分布

#### 按资源类型

{{anomaly_by_resource_type}}

#### 按指标类型

{{anomaly_by_metric}}

## 详细异常

{{anomaly_details}}

## 诊断结果

### 根因分布

| 根因类型 | 数量 | 置信度 |
|----------|------|--------|
{{root_cause_table}}

### 高置信度诊断

{{high_confidence_diagnoses}}

## 优化建议

{{recommendations}}

## 附录

### A. 巡检配置

```yaml
{{config_yaml}}
```

### B. 原始数据

- [指标数据](./data/metrics.json)
- [异常数据](./data/anomalies.json)
- [诊断数据](./data/diagnoses.json)

---

*报告由主动巡检系统自动生成*
```

### 报告生成器

```python
#!/usr/bin/env python3
"""
巡检报告生成器
"""
from datetime import datetime
from typing import List, Dict
import json


class InspectionReportGenerator:
    """巡检报告生成器"""
    
    def __init__(self, template_path: str):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()
    
    def generate(self, 
                resources: List['Resource'],
                metrics: Dict,
                anomalies: List['Anomaly'],
                diagnoses: List['DiagnosisResult'],
                timings: Dict,
                config: Dict) -> str:
        """生成报告"""
        
        # 构建替换数据
        data = {
            'inspection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'resource_count': len(resources),
            'resource_types': ', '.join(set(r.resource_type for r in resources)),
            'duration': sum(timings.values()) // 60,
            
            # 五步闭环状态
            'discovery_time': timings.get('discovery', 0),
            'discovered_count': len(resources),
            'collection_time': timings.get('collection', 0),
            'metrics_count': sum(len(m) for m in metrics.values()),
            'detection_time': timings.get('detection', 0),
            'anomaly_count': len(anomalies),
            'diagnosis_time': timings.get('diagnosis', 0),
            'diagnosed_count': len(diagnoses),
            'report_time': timings.get('report', 0),
            
            # 异常统计
            'total_anomalies': len(anomalies),
            'critical_count': sum(1 for a in anomalies if a.level.value == 'critical'),
            'warning_count': sum(1 for a in anomalies if a.level.value == 'warning'),
            'info_count': sum(1 for a in anomalies if a.level.value == 'info'),
            
            # 表格数据
            'resource_type_table': self._generate_resource_type_table(resources),
            'anomaly_details': self._generate_anomaly_details(anomalies, diagnoses),
            'root_cause_table': self._generate_root_cause_table(diagnoses),
            'recommendations': self._generate_recommendations(diagnoses),
            
            # 配置
            'config_yaml': json.dumps(config, indent=2, ensure_ascii=False)
        }
        
        # 替换模板
        report = self.template
        for key, value in data.items():
            report = report.replace(f'{{{{{key}}}}}', str(value))
        
        return report
    
    def _generate_resource_type_table(self, resources: List['Resource']) -> str:
        """生成资源类型表格"""
        counts = {}
        for r in resources:
            counts[r.resource_type] = counts.get(r.resource_type, 0) + 1
        
        total = len(resources)
        lines = []
        for rtype, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100 if total > 0 else 0
            lines.append(f"| {rtype} | {count} | {pct:.1f}% |")
        
        return '\n'.join(lines)
    
    def _generate_anomaly_details(self, anomalies: List['Anomaly'],
                                  diagnoses: List['DiagnosisResult']) -> str:
        """生成异常详情"""
        lines = []
        
        for i, anomaly in enumerate(anomalies, 1):
            # 找到对应的诊断
            diagnosis = next(
                (d for d in diagnoses if d.anomaly == anomaly),
                None
            )
            
            lines.append(f"### {i}. {anomaly.message}")
            lines.append('')
            lines.append(f"- **资源**: {anomaly.resource_id} ({anomaly.resource_type})")
            lines.append(f"- **级别**: {anomaly.level.value}")
            lines.append(f"- **当前值**: {anomaly.current_value:.2f}")
            lines.append(f"- **阈值**: {anomaly.threshold}")
            lines.append('')
            
            if diagnosis:
                lines.append(f"**诊断结果**:")
                lines.append(f"- 根因: {diagnosis.root_cause.value}")
                lines.append(f"- 置信度: {diagnosis.confidence:.1%}")
                if diagnosis.evidence:
                    lines.append(f"- 证据: {'; '.join(diagnosis.evidence[:3])}")
            
            lines.append('')
        
        return '\n'.join(lines)
    
    def _generate_root_cause_table(self, diagnoses: List['DiagnosisResult']) -> str:
        """生成根因表格"""
        counts = {}
        for d in diagnoses:
            cause = d.root_cause.value
            if cause not in counts:
                counts[cause] = {'count': 0, 'confidence_sum': 0}
            counts[cause]['count'] += 1
            counts[cause]['confidence_sum'] += d.confidence
        
        lines = []
        for cause, data in sorted(counts.items(), key=lambda x: x[1]['count'], reverse=True):
            avg_confidence = data['confidence_sum'] / data['count'] if data['count'] > 0 else 0
            lines.append(f"| {cause} | {data['count']} | {avg_confidence:.1%} |")
        
        return '\n'.join(lines)
    
    def _generate_recommendations(self, diagnoses: List['DiagnosisResult']) -> str:
        """生成建议"""
        all_recommendations = []
        for d in diagnoses:
            all_recommendations.extend(d.recommendations)
        
        # 去重并排序
        unique_recommendations = list(set(all_recommendations))
        
        lines = []
        for i, rec in enumerate(unique_recommendations[:20], 1):
            lines.append(f"{i}. {rec}")
        
        return '\n'.join(lines)
    
    def save(self, report: str, filepath: str):
        """保存报告"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
```

## 7. CLI 执行示例

```bash
#!/bin/bash
# cli_inspection.sh - 主动巡检 CLI 执行脚本

set -e

# 配置
INSPECTION_NAME=${INSPECTION_NAME:-"$(date +%Y%m%d-%H%M%S)"}
OUTPUT_DIR=${OUTPUT_DIR:-"./reports/${INSPECTION_NAME}"}
CONFIG_FILE=${CONFIG_FILE:-"./config/inspection.yaml"}

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 步骤 1: Discovery
log "Step 1/5: Discovery - 发现资源..."
python3 -c "
from workflows.discovery import DiscoveryPipeline, ECSResourceDiscovery, RDSResourceDiscovery

pipeline = DiscoveryPipeline()
# 注册发现器
pipeline.register(ECSResourceDiscovery(client))
pipeline.register(RDSResourceDiscovery(client))

# 执行发现
results = pipeline.run()

# 导出资源清单
pipeline.export_inventory(results, '${OUTPUT_DIR}/inventory.json')
print(f'发现资源: {sum(len(r) for r in results.values())} 个')
"

# 步骤 2: Collection
log "Step 2/5: Collection - 采集指标..."
python3 -c "
from workflows.collection import CollectionPipeline, MetricCollector

collector = MetricCollector(cloud_monitor_client)
pipeline = CollectionPipeline(collector)

# 加载资源
import json
with open('${OUTPUT_DIR}/inventory.json') as f:
    inventory = json.load(f)

# 创建采集任务
tasks = pipeline.create_tasks(resources, time_range_minutes=60)

# 执行采集
metrics = pipeline.collect_with_retry(tasks)

# 保存指标
with open('${OUTPUT_DIR}/metrics.json', 'w') as f:
    json.dump(metrics, f)

print(f'采集指标: {sum(len(m) for m in metrics.values())} 条')
"

# 步骤 3: Detection
log "Step 3/5: Detection - 检测异常..."
python3 -c "
from workflows.detection import DetectionPipeline, AnomalyDetector

detector = AnomalyDetector()
pipeline = DetectionPipeline(detector)

# 加载数据
import json
with open('${OUTPUT_DIR}/inventory.json') as f:
    inventory = json.load(f)
with open('${OUTPUT_DIR}/metrics.json') as f:
    metrics = json.load(f)

# 执行检测
anomalies = pipeline.run(resources, metrics)

# 保存结果
with open('${OUTPUT_DIR}/anomalies.json', 'w') as f:
    json.dump([a.__dict__ for a in anomalies], f)

print(f'发现异常: {len(anomalies)} 个')
"

# 步骤 4: Diagnosis
log "Step 4/5: Diagnosis - 诊断根因..."
python3 -c "
from workflows.diagnosis import DiagnosisPipeline, RootCauseAnalyzer

analyzer = RootCauseAnalyzer(log_client)
pipeline = DiagnosisPipeline(analyzer)

# 加载数据
import json
with open('${OUTPUT_DIR}/inventory.json') as f:
    inventory = json.load(f)
with open('${OUTPUT_DIR}/anomalies.json') as f:
    anomalies = json.load(f)

# 执行诊断
diagnoses = pipeline.run(resources, anomalies)

# 保存结果
with open('${OUTPUT_DIR}/diagnoses.json', 'w') as f:
    json.dump([d.__dict__ for d in diagnoses], f)

print(f'完成诊断: {len(diagnoses)} 个')
"

# 步骤 5: Report
log "Step 5/5: Report - 生成报告..."
python3 -c "
from workflows.report import InspectionReportGenerator

generator = InspectionReportGenerator('reports/template.md')

# 加载所有数据
# ...

# 生成报告
report = generator.generate(resources, metrics, anomalies, diagnoses, timings, config)
generator.save(report, '${OUTPUT_DIR}/report.md')

print(f'报告已保存: ${OUTPUT_DIR}/report.md')
"

log "巡检完成！报告: ${OUTPUT_DIR}/report.md"
```

## 8. 配置模板

```yaml
# inspection-config.yaml
inspection:
  name: "daily-production-inspection"
  description: "生产环境每日巡检"
  
  # 调度配置
  schedule:
    enabled: true
    cron: "0 2 * * *"  # 每天凌晨2点
    timezone: "Asia/Shanghai"
  
  # 资源范围
  scope:
    regions:
      - cn-hangzhou
      - cn-beijing
    resource_types:
      - ECS
      - RDS
      - Redis
    filters:
      tags:
        Environment: Production
      exclude:
        name_patterns:
          - "*test*"
          - "*dev*"
  
  # 采集配置
  collection:
    time_range: 60  # 分钟
    metrics:
      ECS: [CPUUtilization, memory_usedutilization, LoadAverage]
      RDS: [CpuUsage, MemoryUsage, ConnectionUsage]
      Redis: [UsedMemory, CpuUsage]
  
  # 检测配置
  detection:
    rules:
      - name: "CPU高"
        metric: CPUUtilization
        threshold: 80
        level: warning
      - name: "CPU严重高"
        metric: CPUUtilization
        threshold: 95
        level: critical
  
  # 通知配置
  notification:
    enabled: true
    channels:
      - type: webhook
        url: "https://hooks.example.com/inspection"
      - type: email
        recipients:
          - ops@example.com
    conditions:
      - anomaly_count > 0
```

## 使用指南

1. **配置资源范围**: 编辑 `targets.yaml`
2. **调整检测规则**: 修改 `inspection.yaml` 中的 detection 配置
3. **运行巡检**: 执行 `cli_inspection.sh`
4. **查看报告**: 检查 `reports/` 目录下的 Markdown 报告
