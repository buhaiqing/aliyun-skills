# 统一诊断报告 Schema 强制化

> **Purpose:** 标准化所有 Skill 的诊断报告格式，确保报告完整性和可比性
> **Version:** 1.0.0
> **Last Updated:** 2026-05-20
> **Status:** P0 - 高优先级

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [Schema 定义](#2-schema-定义)
3. [字段规范](#3-字段规范)
4. [报告生成流程](#4-报告生成流程)
5. [验证机制](#5-验证机制)
6. [报告模板](#6-报告模板)
7. [跨 Skill 关联](#7-跨-skill-关联)
8. [实现示例](#8-实现示例)
9. [度量与验证](#9-度量与验证)

---

## 1. 执行摘要

### 1.1 目标

| 指标 | 当前状态 | 目标状态 |
|------|----------|----------|
| 报告格式统一性 | 各 Skill 自定义 | 100% Schema 合规 |
| 字段完整性 | 50% | 100% |
| 跨 Skill 可比性 | 差 | 高 |
| 自动化验证 | 无 | 强制验证 |

### 1.2 Schema 版本

```yaml
Schema 信息:
  version: "1.0.0"
  name: "UnifiedDiagnosisReport"
  format: "Markdown + YAML Frontmatter"
  required_fields: 15
  optional_fields: 8
```

---

## 2. Schema 定义

### 2.1 文件规范

```yaml
报告文件规范:
  存储位置: ~/.cache/aliyun-skills/reports/
  文件名格式: "{resource_id}-{timestamp}-diagnosis.md"
  文件名示例:
    - "i-bp67acfmxazb4p-20260520120000-diagnosis.md"
    - "rm-2ze8g6nm93j0-20260520120000-diagnosis.md"
    - "lb-2ze8g6nm93j0-20260520120000-diagnosis.md"
```

### 2.2 Schema 结构

```yaml
UnifiedDiagnosisReport:
  # === 基础信息 (Required) ===
  report_id:          string  # 报告唯一标识 (UUID)
  timestamp:          string  # ISO 8601 格式时间戳
  alarm_source:       string  # 告警来源 (CMS/DAS/User/Manual)
  
  # === 资源信息 (Required) ===
  resource_id:        string  # 资源唯一标识
  resource_type:      string  # 资源类型 (ECS/RDS/SLB/...)
  resource_status:    string  # 资源状态 (Running/Stopped/Abnormal/...)
  
  # === 指标信息 (Required) ===
  metric_name:        string  # 指标名称
  metric_value:       float   # 指标当前值
  metric_threshold:   float   # 告警阈值
  metric_trend:       string  # 趋势 (rising/falling/stable)
  
  # === 诊断信息 (Required) ===
  anomaly_patterns:   array   # 检测到的异常模式
  deep_diagnosis:     object  # 深度诊断结果
  
  # === 关联信息 (Required) ===
  correlated_alarms:  array   # 关联告警列表
  correlated_events:  array   # 关联事件列表
  
  # === 根因与建议 (Required) ===
  root_cause:         string  # 根因分析
  recommendation:     array   # 修复建议列表
  
  # === Skill 委托信息 (Required) ===
  delegated_skills:   array   # 委托的其他 Skill 列表
  
  # === 质量评分 (Required) ===
  confidence_score:   float   # 诊断置信度 (0.0-1.0)
  
  # === 可选信息 (Optional) ===
  region:             string  # 地域
  zone:               string  # 可用区
  tags:               object  # 资源标签
  cost_impact:        object  # 成本影响评估
  sla_impact:         object  # SLA 影响评估
  recovery_time_estimate: int  # 预估恢复时间(秒)
  similar_incidents:  array   # 历史相似事件
```

---

## 3. 字段规范

### 3.1 基础信息字段

```yaml
report_id:
  type: string
  format: uuid
  description: "报告唯一标识符"
  example: "550e8400-e29b-41d4-a716-446655440000"

timestamp:
  type: string
  format: date-time (ISO 8601)
  description: "报告生成时间戳"
  example: "2026-05-20T12:00:00Z"

alarm_source:
  type: string
  enum: ["CMS", "DAS", "CloudMonitor", "User", "Manual", "AutoInspection"]
  description: "告警触发来源"
  example: "CMS"
```

### 3.2 资源信息字段

```yaml
resource_id:
  type: string
  description: "阿里云资源唯一标识"
  examples:
    - "i-bp67acfmxazb4p"      # ECS
    - "rm-2ze8g6nm93j0"       # RDS
    - "lb-2ze8g6nm93j0"       # SLB
    - "r-2ze8g6nm93j0"        # Redis

resource_type:
  type: string
  enum: ["ECS", "RDS", "SLB", "Redis", "ACK", "OSS", "KMS", "VPC", "PolarDB", "MongoDB"]
  description: "资源类型"

resource_status:
  type: string
  description: "资源当前状态"
  examples:
    ECS: ["Running", "Stopped", "Starting", "Stopping", "Abnormal"]
    RDS: ["Running", "Creating", "Deleting", "Rebooting", "Abnormal"]
```

### 3.3 指标信息字段

```yaml
metric_name:
  type: string
  description: "触发告警的指标名称"
  examples:
    - "CPUUtilization"
    - "MemoryUsage"
    - "DiskUsage"
    - "ConnectionUsage"

metric_value:
  type: number
  description: "指标当前值"
  example: 95.5

metric_threshold:
  type: number
  description: "告警阈值"
  example: 80.0

metric_trend:
  type: string
  enum: ["rising", "falling", "stable", "fluctuating"]
  description: "指标变化趋势"
```

### 3.4 异常模式字段

```yaml
anomaly_patterns:
  type: array
  items:
    type: object
    properties:
      pattern_type:
        type: string
        enum:
          - "cpu_memory_high"      # CPU-Memory 双高
          - "disk_io_bottleneck"   # 磁盘-IO 瓶颈
          - "connection_spike"       # 连接数突增
          - "latency_spike"          # 延迟突增
          - "throughput_drop"        # 吞吐量下降
          - "load_cpu_mismatch"      # Load-CPU 不匹配
          - "mutation"               # 突变
          - "seasonal_anomaly"       # 季节性异常
          - "correlation_break"      # 相关性断裂
      confidence:
        type: number
        minimum: 0.0
        maximum: 1.0
      severity:
        type: string
        enum: ["critical", "high", "medium", "low"]
      description:
        type: string
      indicators:
        type: array
        items:
          type: string
  example:
    - pattern_type: "cpu_memory_high"
      confidence: 0.92
      severity: "critical"
      description: "CPU 和内存同时高于 90%，持续 5 分钟"
      indicators:
        - "cpu > 90%"
        - "memory > 90%"
        - "duration > 5min"
```

### 3.5 深度诊断字段

```yaml
deep_diagnosis:
  type: object
  required:
    - summary
    - findings
  properties:
    summary:
      type: string
      description: "诊断摘要"
    findings:
      type: array
      items:
        type: object
        properties:
          category:
            type: string
            enum: ["resource", "configuration", "workload", "dependency", "security"]
          finding:
            type: string
          evidence:
            type: array
            items:
              type: string
          severity:
            type: string
            enum: ["critical", "high", "medium", "low", "info"]
    cross_resource_analysis:
      type: object
      description: "跨资源分析结果"
    historical_comparison:
      type: object
      description: "历史对比分析"
```

### 3.6 关联信息字段

```yaml
correlated_alarms:
  type: array
  items:
    type: object
    properties:
      alarm_id:
        type: string
      resource_id:
        type: string
      resource_type:
        type: string
      metric_name:
        type: string
      metric_value:
        type: number
      timestamp:
        type: string
      correlation_score:
        type: number
        minimum: 0.0
        maximum: 1.0
  example:
    - alarm_id: "alarm-12345"
      resource_id: "i-bp67acfmxazb4p"
      resource_type: "ECS"
      metric_name: "MemoryUsage"
      metric_value: 92.3
      timestamp: "2026-05-20T11:58:00Z"
      correlation_score: 0.89

correlated_events:
  type: array
  items:
    type: object
    properties:
      event_id:
        type: string
      event_type:
        type: string
        enum: ["Deployment", "ConfigurationChange", "Scaling", "Backup", "Maintenance"]
      timestamp:
        type: string
      description:
        type: string
      correlation_score:
        type: number
  example:
    - event_id: "evt-67890"
      event_type: "Deployment"
      timestamp: "2026-05-20T11:55:00Z"
      description: "应用版本升级 v2.1.0 -> v2.2.0"
      correlation_score: 0.85
```

### 3.7 根因与建议字段

```yaml
root_cause:
  type: string
  description: "根因分析描述"
  example: "应用内存泄漏导致 OOM，触发 ECS 实例异常重启"

recommendation:
  type: array
  items:
    type: object
    properties:
      priority:
        type: integer
        minimum: 1
        maximum: 5
      action:
        type: string
        description: "建议操作"
      rationale:
        type: string
        description: "建议理由"
      automated:
        type: boolean
        description: "是否可自动化执行"
      skill:
        type: string
        description: "执行所需的 Skill"
      estimated_time:
        type: integer
        description: "预估执行时间(秒)"
      risk_level:
        type: string
        enum: ["low", "medium", "high", "critical"]
  example:
    - priority: 1
      action: "重启应用进程释放内存"
      rationale: "快速缓解内存压力，避免实例重启"
      automated: true
      skill: "ecs-ops"
      estimated_time: 30
      risk_level: "low"
    - priority: 2
      action: "分析应用内存泄漏根因"
      rationale: "定位内存泄漏代码位置"
      automated: false
      skill: "das-ops"
      estimated_time: 300
      risk_level: "medium"
```

### 3.8 Skill 委托字段

```yaml
delegated_skills:
  type: array
  items:
    type: object
    properties:
      skill_name:
        type: string
      reason:
        type: string
      trigger_condition:
        type: string
      status:
        type: string
        enum: ["pending", "in_progress", "completed", "failed", "skipped"]
      result:
        type: string
  example:
    - skill_name: "das-ops"
      reason: "深度数据库诊断"
      trigger_condition: "RDS 资源 CPU > 80%"
      status: "completed"
      result: "发现慢查询，已生成优化建议"
    - skill_name: "cms-ops"
      reason: "关联指标分析"
      trigger_condition: "默认触发"
      status: "completed"
      result: "确认应用层指标异常"
```

### 3.9 置信度评分字段

```yaml
confidence_score:
  type: number
  minimum: 0.0
  maximum: 1.0
  description: "诊断结果的置信度评分"
  interpretation:
    "0.9-1.0": "极高置信度 - 可直接执行修复"
    "0.7-0.89": "高置信度 - 建议人工复核"
    "0.5-0.69": "中等置信度 - 需要更多证据"
    "0.3-0.49": "低置信度 - 建议深入调查"
    "0.0-0.29": "极低置信度 - 信息不足"
```

---

## 4. 报告生成流程

### 4.1 标准流程

```
┌─────────────────────────────────────────────────────────────┐
│                    诊断报告生成流程                          │
└─────────────────────────────────────────────────────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    ▼                       ▼                       ▼
┌──────────┐          ┌──────────┐          ┌──────────┐
│ 数据收集  │          │ 异常检测  │          │ 根因分析  │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│                    报告组装阶段                            │
│  1. 基础信息填充                                         │
│  2. 指标数据填充                                          │
│  3. 异常模式填充                                          │
│  4. 关联信息填充                                          │
│  5. 诊断建议填充                                          │
└─────────────────────────┬─────────────────────────────────┘
                          ▼
               ┌──────────────────┐
               │   Schema 验证     │
               │   (强制检查)      │
               └────────┬─────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
        通过         警告         失败
           │            │            │
           ▼            ▼            ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ 生成报告  │  │ 补充信息  │  │ 报错终止  │
    └──────────┘  └──────────┘  └──────────┘
```

### 4.2 验证流程

```go
// file: pkg/report/validator.go
package report

import (
    "fmt"
    "reflect"
)

// Validator Schema 验证器
type Validator struct {
    requiredFields []string
    enums          map[string][]string
}

// ValidationResult 验证结果
type ValidationResult struct {
    Valid   bool     `json:"valid"`
    Errors  []string `json:"errors"`
    Warnings []string `json:"warnings"`
}

// Validate 验证报告
func (v *Validator) Validate(report *UnifiedDiagnosisReport) *ValidationResult {
    result := &ValidationResult{
        Valid:    true,
        Errors:   []string{},
        Warnings: []string{},
    }
    
    // 验证必填字段
    for _, field := range v.requiredFields {
        if !v.fieldExists(report, field) {
            result.Errors = append(result.Errors, 
                fmt.Sprintf("必填字段缺失: %s", field))
            result.Valid = false
        }
    }
    
    // 验证枚举值
    for field, allowed := range v.enums {
        value := v.getFieldValue(report, field)
        if value != "" && !v.contains(allowed, value) {
            result.Errors = append(result.Errors,
                fmt.Sprintf("字段 %s 的值 %s 不在允许列表中", field, value))
            result.Valid = false
        }
    }
    
    // 验证置信度范围
    if report.ConfidenceScore < 0.0 || report.ConfidenceScore > 1.0 {
        result.Errors = append(result.Errors,
            "confidence_score 必须在 0.0-1.0 之间")
        result.Valid = false
    }
    
    // 警告: 置信度过低
    if report.ConfidenceScore < 0.5 {
        result.Warnings = append(result.Warnings,
            "置信度评分低于 0.5，建议补充更多证据")
    }
    
    // 警告: 无关联告警
    if len(report.CorrelatedAlarms) == 0 {
        result.Warnings = append(result.Warnings,
            "无关联告警信息，可能影响根因分析准确性")
    }
    
    return result
}

// 预定义验证器实例
var DefaultValidator = &Validator{
    requiredFields: []string{
        "report_id",
        "timestamp",
        "alarm_source",
        "resource_id",
        "resource_type",
        "resource_status",
        "metric_name",
        "metric_value",
        "anomaly_patterns",
        "deep_diagnosis",
        "correlated_alarms",
        "correlated_events",
        "root_cause",
        "recommendation",
        "delegated_skills",
        "confidence_score",
    },
    enums: map[string][]string{
        "alarm_source":      {"CMS", "DAS", "CloudMonitor", "User", "Manual", "AutoInspection"},
        "resource_type":     {"ECS", "RDS", "SLB", "Redis", "ACK", "OSS", "KMS", "VPC", "PolarDB", "MongoDB"},
        "metric_trend":      {"rising", "falling", "stable", "fluctuating"},
    },
}
```

---

## 5. 验证机制

### 5.1 强制验证规则

```yaml
验证规则:
  必填检查:
    - report_id: 必须存在且为有效 UUID
    - timestamp: 必须存在且为有效 ISO 8601 格式
    - resource_id: 必须存在且符合阿里云资源 ID 格式
    - confidence_score: 必须存在且在 0.0-1.0 范围内
    - root_cause: 必须存在且长度 >= 10 字符
    - recommendation: 必须存在且至少包含 1 条建议
  
  格式检查:
    - resource_type: 必须在预定义枚举列表中
    - alarm_source: 必须在预定义枚举列表中
    - metric_trend: 必须在预定义枚举列表中
    - timestamp: 必须是 UTC 时间或带时区的时间
  
  一致性检查:
    - resource_type 必须与 resource_id 前缀匹配
    - timestamp 不能是未来时间
    - confidence_score 与 anomaly_patterns 数量应正相关
    - recommendation 的 priority 必须唯一且连续
  
  警告规则:
    - confidence_score < 0.5: 低置信度警告
    - correlated_alarms 为空: 关联信息缺失警告
    - recommendation 数量 < 2: 建议数量不足警告
```

### 5.2 验证命令

```bash
#!/bin/bash
# file: ~/.local/bin/skill-validate-report

validate_report() {
    local report_file=$1
    
    echo "=== 诊断报告验证 ==="
    echo "文件: $report_file"
    echo ""
    
    # 检查文件存在
    if [[ ! -f "$report_file" ]]; then
        echo "❌ 错误: 文件不存在"
        return 1
    fi
    
    # 提取 YAML Frontmatter
    local frontmatter=$(sed -n '/^---$/,/^---$/p' "$report_file" | sed '1d;$d')
    
    # 检查必填字段
    local required_fields=(
        "report_id"
        "timestamp"
        "alarm_source"
        "resource_id"
        "resource_type"
        "resource_status"
        "metric_name"
        "metric_value"
        "confidence_score"
        "root_cause"
    )
    
    local missing=()
    for field in "${required_fields[@]}"; do
        if ! echo "$frontmatter" | grep -q "^${field}:"; then
            missing+=("$field")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ 必填字段缺失:"
        printf '  - %s\n' "${missing[@]}"
        return 1
    fi
    
    echo "✅ 所有必填字段存在"
    
    # 检查置信度范围
    local confidence=$(echo "$frontmatter" | grep "^confidence_score:" | awk '{print $2}')
    if [[ -n "$confidence" ]]; then
        if (( $(echo "$confidence < 0.0 || $confidence > 1.0" | bc -l) )); then
            echo "❌ confidence_score 超出有效范围 (0.0-1.0)"
            return 1
        fi
        
        if (( $(echo "$confidence < 0.5" | bc -l) )); then
            echo "⚠️  警告: confidence_score 低于 0.5 (当前: $confidence)"
        else
            echo "✅ confidence_score 有效: $confidence"
        fi
    fi
    
    echo ""
    echo "=== 验证通过 ==="
    return 0
}

# 主入口
validate_report "$1"
```

---

## 6. 报告模板

### 6.1 标准 Markdown 模板

```markdown
---
# YAML Frontmatter - 机器可读
report_id: "{{report_id}}"
timestamp: "{{timestamp}}"
alarm_source: "{{alarm_source}}"

resource_id: "{{resource_id}}"
resource_type: "{{resource_type}}"
resource_status: "{{resource_status}}"
region: "{{region}}"
zone: "{{zone}}"

metric_name: "{{metric_name}}"
metric_value: {{metric_value}}
metric_threshold: {{metric_threshold}}
metric_trend: "{{metric_trend}}"

anomaly_patterns:
{{#anomaly_patterns}}
  - pattern_type: "{{pattern_type}}"
    confidence: {{confidence}}
    severity: "{{severity}}"
    description: "{{description}}"
    indicators:
{{#indicators}}
      - "{{.}}"
{{/indicators}}
{{/anomaly_patterns}}

deep_diagnosis:
  summary: "{{deep_diagnosis.summary}}"
  findings:
{{#deep_diagnosis.findings}}
    - category: "{{category}}"
      finding: "{{finding}}"
      severity: "{{severity}}"
      evidence:
{{#evidence}}
        - "{{.}}"
{{/evidence}}
{{/deep_diagnosis.findings}}

correlated_alarms:
{{#correlated_alarms}}
  - alarm_id: "{{alarm_id}}"
    resource_id: "{{resource_id}}"
    resource_type: "{{resource_type}}"
    metric_name: "{{metric_name}}"
    metric_value: {{metric_value}}
    timestamp: "{{timestamp}}"
    correlation_score: {{correlation_score}}
{{/correlated_alarms}}

correlated_events:
{{#correlated_events}}
  - event_id: "{{event_id}}"
    event_type: "{{event_type}}"
    timestamp: "{{timestamp}}"
    description: "{{description}}"
    correlation_score: {{correlation_score}}
{{/correlated_events}}

root_cause: "{{root_cause}}"

recommendation:
{{#recommendation}}
  - priority: {{priority}}
    action: "{{action}}"
    rationale: "{{rationale}}"
    automated: {{automated}}
    skill: "{{skill}}"
    estimated_time: {{estimated_time}}
    risk_level: "{{risk_level}}"
{{/recommendation}}

delegated_skills:
{{#delegated_skills}}
  - skill_name: "{{skill_name}}"
    reason: "{{reason}}"
    trigger_condition: "{{trigger_condition}}"
    status: "{{status}}"
    result: "{{result}}"
{{/delegated_skills}}

confidence_score: {{confidence_score}}
---

# 诊断报告: {{resource_type}} 资源异常

> **报告 ID:** {{report_id}}  
> **生成时间:** {{timestamp}}  
> **告警来源:** {{alarm_source}}  
> **置信度:** {{confidence_score}} ({{confidence_level}})

---

## 资源信息

| 属性 | 值 |
|------|-----|
| 资源 ID | `{{resource_id}}` |
| 资源类型 | {{resource_type}} |
| 当前状态 | {{resource_status}} |
| 地域 | {{region}} |
| 可用区 | {{zone}} |

---

## 指标异常

### 触发指标

| 指标名称 | 当前值 | 阈值 | 趋势 |
|----------|--------|------|------|
| {{metric_name}} | {{metric_value}} | {{metric_threshold}} | {{metric_trend_icon}} {{metric_trend}} |

### 异常模式检测

{{#anomaly_patterns}}
#### {{pattern_type}}

- **置信度:** {{confidence}} ({{severity}})
- **描述:** {{description}}
- **指标:**
{{#indicators}}
  - {{.}}
{{/indicators}}

{{/anomaly_patterns}}

---

## 深度诊断

### 诊断摘要

{{deep_diagnosis.summary}}

### 诊断发现

{{#deep_diagnosis.findings}}
**[{{severity}}]** {{finding}}

- **类别:** {{category}}
- **证据:**
{{#evidence}}
  - {{.}}
{{/evidence}}

{{/deep_diagnosis.findings}}

---

## 关联分析

### 关联告警

| 告警 ID | 资源 | 指标 | 值 | 时间 | 相关性 |
|---------|------|------|-----|------|--------|
{{#correlated_alarms}}
| {{alarm_id}} | {{resource_type}}/{{resource_id}} | {{metric_name}} | {{metric_value}} | {{timestamp}} | {{correlation_score}} |
{{/correlated_alarms}}

### 关联事件

| 事件 ID | 类型 | 描述 | 时间 | 相关性 |
|---------|------|------|------|--------|
{{#correlated_events}}
| {{event_id}} | {{event_type}} | {{description}} | {{timestamp}} | {{correlation_score}} |
{{/correlated_events}}

---

## 根因分析

{{root_cause}}

---

## 修复建议

{{#recommendation}}
### {{priority}}. {{action}}

- **理由:** {{rationale}}
- **自动化:** {{#automated}}✅ 可自动执行{{/automated}}{{^automated}}❌ 需人工操作{{/automated}}
- **所需 Skill:** {{skill}}
- **预估时间:** {{estimated_time}} 秒
- **风险等级:** {{risk_level}}

{{/recommendation}}

---

## Skill 委托记录

| Skill | 委托原因 | 触发条件 | 状态 | 结果 |
|-------|----------|----------|------|------|
{{#delegated_skills}}
| {{skill_name}} | {{reason}} | {{trigger_condition}} | {{status}} | {{result}} |
{{/delegated_skills}}

---

*本报告由阿里云 Skill 自动生成，遵循统一诊断报告 Schema v1.0.0*
```

---

## 7. 跨 Skill 关联

### 7.1 关联规则

```yaml
跨 Skill 关联矩阵:
  ECS:
    delegates_to:
      - skill: "cms-ops"
        condition: "需要指标数据"
      - skill: "das-ops"
        condition: "需要深度诊断"
  
  RDS:
    delegates_to:
      - skill: "das-ops"
        condition: "CPU > 80%"
      - skill: "cms-ops"
        condition: "需要监控数据"
  
  SLB:
    delegates_to:
      - skill: "ecs-ops"
        condition: "后端 ECS 异常"
      - skill: "cms-ops"
        condition: "流量异常"
```

### 7.2 委托记录格式

```yaml
delegated_skills:
  - skill_name: "string"      # 委托的 Skill 名称
    reason: "string"          # 委托原因
    trigger_condition: "string" # 触发条件
    status: "string"          # 执行状态 (pending/in_progress/completed/failed/skipped)
    result: "string"          # 执行结果摘要
    report_path: "string"     # 子报告路径 (可选)
    confidence_delta: float   # 置信度变化 (可选)
```

---

## 8. 实现示例

### 8.1 Go 代码示例

```go
// file: pkg/report/generator.go
package report

import (
    "fmt"
    "os"
    "path/filepath"
    "text/template"
    "time"
)

// Generator 报告生成器
type Generator struct {
    outputDir string
    template  *template.Template
    validator *Validator
}

// NewGenerator 创建生成器
func NewGenerator(outputDir string) (*Generator, error) {
    tmpl, err := template.ParseFiles("templates/diagnosis-report.md")
    if err != nil {
        return nil, err
    }
    
    return &Generator{
        outputDir: outputDir,
        template:  tmpl,
        validator: DefaultValidator,
    }, nil
}

// Generate 生成报告
func (g *Generator) Generate(report *UnifiedDiagnosisReport) (string, error) {
    // 1. 验证报告
    result := g.validator.Validate(report)
    if !result.Valid {
        return "", fmt.Errorf("报告验证失败: %v", result.Errors)
    }
    
    // 2. 生成文件名
    filename := fmt.Sprintf("%s-%s-diagnosis.md",
        report.ResourceID,
        report.Timestamp.Format("%Y%m%d%H%M%S"))
    
    filepath := filepath.Join(g.outputDir, filename)
    
    // 3. 生成报告内容
    f, err := os.Create(filepath)
    if err != nil {
        return "", err
    }
    defer f.Close()
    
    if err := g.template.Execute(f, report); err != nil {
        return "", err
    }
    
    return filepath, nil
}

// UnifiedDiagnosisReport 统一诊断报告结构
type UnifiedDiagnosisReport struct {
    ReportID          string              `yaml:"report_id"`
    Timestamp         time.Time           `yaml:"timestamp"`
    AlarmSource       string              `yaml:"alarm_source"`
    ResourceID        string              `yaml:"resource_id"`
    ResourceType      string              `yaml:"resource_type"`
    ResourceStatus    string              `yaml:"resource_status"`
    Region            string              `yaml:"region"`
    Zone              string              `yaml:"zone"`
    MetricName        string              `yaml:"metric_name"`
    MetricValue       float64             `yaml:"metric_value"`
    MetricThreshold   float64             `yaml:"metric_threshold"`
    MetricTrend       string              `yaml:"metric_trend"`
    AnomalyPatterns   []AnomalyPattern    `yaml:"anomaly_patterns"`
    DeepDiagnosis     DeepDiagnosis       `yaml:"deep_diagnosis"`
    CorrelatedAlarms  []CorrelatedAlarm   `yaml:"correlated_alarms"`
    CorrelatedEvents  []CorrelatedEvent   `yaml:"correlated_events"`
    RootCause         string              `yaml:"root_cause"`
    Recommendation    []Recommendation    `yaml:"recommendation"`
    DelegatedSkills   []DelegatedSkill    `yaml:"delegated_skills"`
    ConfidenceScore   float64             `yaml:"confidence_score"`
}

// 子结构定义...
type AnomalyPattern struct {
    PatternType string   `yaml:"pattern_type"`
    Confidence  float64  `yaml:"confidence"`
    Severity    string   `yaml:"severity"`
    Description string   `yaml:"description"`
    Indicators  []string `yaml:"indicators"`
}

type DeepDiagnosis struct {
    Summary            string     `yaml:"summary"`
    Findings           []Finding  `yaml:"findings"`
}

type Finding struct {
    Category string   `yaml:"category"`
    Finding  string   `yaml:"finding"`
    Severity string   `yaml:"severity"`
    Evidence []string `yaml:"evidence"`
}

// ... 其他结构体定义
```

---

## 9. 度量与验证

### 9.1 合规检查清单

```yaml
Schema 合规检查清单:
  基础信息:
    - [ ] report_id 为有效 UUID
    - [ ] timestamp 为 ISO 8601 格式
    - [ ] alarm_source 在预定义列表中
  
  资源信息:
    - [ ] resource_id 符合阿里云格式
    - [ ] resource_type 在预定义列表中
    - [ ] resource_status 有明确值
  
  指标信息:
    - [ ] metric_name 不为空
    - [ ] metric_value 为数字
    - [ ] metric_trend 在预定义列表中
  
  诊断信息:
    - [ ] anomaly_patterns 至少包含 1 项
    - [ ] deep_diagnosis.summary 不为空
    - [ ] deep_diagnosis.findings 至少包含 1 项
  
  关联信息:
    - [ ] correlated_alarms 已定义 (可为空)
    - [ ] correlated_events 已定义 (可为空)
  
  根因与建议:
    - [ ] root_cause 长度 >= 10 字符
    - [ ] recommendation 至少包含 1 项
  
  Skill 委托:
    - [ ] delegated_skills 已定义 (可为空)
  
  质量评分:
    - [ ] confidence_score 在 0.0-1.0 范围内
    - [ ] confidence_score >= 0.3 (警告阈值)
```

### 9.2 自动化测试

```bash
#!/bin/bash
# file: test-diagnosis-schema.sh

echo "=== 统一诊断报告 Schema 测试 ==="

TEST_DIR="/tmp/diagnosis-reports-test"
mkdir -p "$TEST_DIR"

# 测试 1: 完整报告生成
echo "测试 1: 生成完整报告..."
cat > "$TEST_DIR/complete-report.yaml" << 'EOF'
report_id: "550e8400-e29b-41d4-a716-446655440000"
timestamp: "2026-05-20T12:00:00Z"
alarm_source: "CMS"
resource_id: "i-bp67acfmxazb4p"
resource_type: "ECS"
resource_status: "Running"
metric_name: "CPUUtilization"
metric_value: 95.5
metric_threshold: 80.0
metric_trend: "rising"
anomaly_patterns:
  - pattern_type: "cpu_memory_high"
    confidence: 0.92
    severity: "critical"
deep_diagnosis:
  summary: "CPU 使用率异常高"
  findings: []
correlated_alarms: []
correlated_events: []
root_cause: "应用程序负载突增"
recommendation:
  - priority: 1
    action: "扩容实例"
    rationale: "增加 CPU 资源"
    automated: false
    skill: "ecs-ops"
    estimated_time: 60
    risk_level: "low"
delegated_skills: []
confidence_score: 0.85
EOF

skill-validate-report "$TEST_DIR/complete-report.yaml"
echo ""

# 测试 2: 缺失必填字段
echo "测试 2: 缺失必填字段检测..."
cat > "$TEST_DIR/incomplete-report.yaml" << 'EOF'
report_id: "550e8400-e29b-41d4-a716-446655440000"
timestamp: "2026-05-20T12:00:00Z"
# 缺少 resource_id, resource_type 等
EOF

skill-validate-report "$TEST_DIR/incomplete-report.yaml" && echo "❌ 应该失败" || echo "✅ 正确检测到缺失字段"
echo ""

# 清理
rm -rf "$TEST_DIR"

echo "=== 测试完成 ==="
```

---

## 附录 A: 相关文档

- [optimization-analysis-enhanced.md](optimization-analysis-enhanced.md) - 三维优化分析
- [aiops-best-practices.md](aiops-best-practices.md) - AIOps 最佳实践

---

*文档版本: v1.0.0 | 最后更新: 2026-05-20*
