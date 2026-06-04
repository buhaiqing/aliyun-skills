# Diagnostic Report Schema — Alibaba Cloud Elasticsearch

> **Purpose:** Unified diagnostic report format for AIOps automation and incident tracking.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Report Schema Overview

### 1.1 Schema Version

```yaml
schema_version: "1.0.0"
format: "JSON"
compatible_with: ["AIOps Platform", "Incident Management", "Audit Trail"]
```

### 1.2 Report Categories

| Category | Purpose | Trigger |
|----------|---------|---------|
| **Instance Diagnostic** | Single instance health check | DescribeInstance, DiagnoseInstance |
| **Cluster Diagnostic** | Multi-node cluster analysis | Cluster health degradation |
| **Incident Diagnostic** | Root cause investigation | Error occurrence |
| **Proactive Inspection** | Scheduled health monitoring | Daily/Weekly inspection |
| **Alarm Storm Analysis** | Alarm flood handling | Storm threshold breach |

---

## 2. Core Report Schema

### 2.1 Full Diagnostic Report Schema (JSON)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Elasticsearch Diagnostic Report",
  "type": "object",
  "required": ["report_id", "timestamp", "instance_id", "report_type", "overall_status"],
  "properties": {
    "report_id": {
      "type": "string",
      "description": "Unique report identifier",
      "pattern": "^ES-DIAG-[0-9]{8}-[0-9]{6}-[A-Z0-9]{8}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Report generation timestamp (ISO 8601)"
    },
    "instance_id": {
      "type": "string",
      "description": "Elasticsearch instance ID",
      "pattern": "^es-cn-[a-z0-9]+$"
    },
    "region_id": {
      "type": "string",
      "description": "Alibaba Cloud region"
    },
    "report_type": {
      "type": "string",
      "enum": ["instance_diagnostic", "cluster_diagnostic", "incident_diagnostic", "proactive_inspection", "alarm_storm"],
      "description": "Type of diagnostic report"
    },
    "overall_status": {
      "type": "string",
      "enum": ["healthy", "warning", "critical", "failed"],
      "description": "Overall health assessment"
    },
    "severity": {
      "type": "string",
      "enum": ["info", "warning", "critical", "emergency"],
      "description": "Highest severity among findings"
    },
    "findings": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/finding"
      },
      "description": "List of diagnostic findings"
    },
    "metrics": {
      "$ref": "#/definitions/metrics",
      "description": "Key performance metrics snapshot"
    },
    "root_cause": {
      "$ref": "#/definitions/root_cause",
      "description": "Identified root cause (if applicable)"
    },
    "remediation_actions": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/remediation_action"
      },
      "description": "Recommended or executed remediation actions"
    },
    "correlation_analysis": {
      "$ref": "#/definitions/correlation",
      "description": "Multi-metric correlation analysis"
    },
    "cross_skill_dependencies": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/cross_skill_dep"
      },
      "description": "Dependencies on other skills identified"
    },
    "self_reflection": {
      "$ref": "#/definitions/self_reflection",
      "description": "Multi-round self-reflection results"
    },
    "request_id": {
      "type": "string",
      "description": "API RequestId for traceability"
    },
    "links": {
      "$ref": "#/definitions/links",
      "description": "Related resources and documentation"
    }
  },
  "definitions": {
    "finding": {
      "type": "object",
      "required": ["category", "severity", "message"],
      "properties": {
        "finding_id": {
          "type": "string",
          "pattern": "^F-[0-9]{3}$"
        },
        "category": {
          "type": "string",
          "enum": ["instance_status", "cluster_health", "jvm", "disk", "network", "snapshot", "performance", "security", "cost", "configuration"]
        },
        "severity": {
          "type": "string",
          "enum": ["info", "warning", "critical"]
        },
        "message": {
          "type": "string",
          "maxLength": 500
        },
        "detail": {
          "type": "object",
          "additionalProperties": true
        },
        "threshold": {
          "type": "object",
          "properties": {
            "metric_name": {"type": "string"},
            "current_value": {"type": "number"},
            "threshold_value": {"type": "number"},
            "unit": {"type": "string"}
          }
        },
        "timestamp": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "instance_cpu_utilization": {"type": "number", "minimum": 0, "maximum": 100},
        "instance_memory_utilization": {"type": "number", "minimum": 0, "maximum": 100},
        "instance_disk_utilization": {"type": "number", "minimum": 0, "maximum": 100},
        "jvm_heap_used_percent": {"type": "number", "minimum": 0, "maximum": 100},
        "jvm_gc_collection_count": {"type": "integer"},
        "jvm_gc_collection_time_ms": {"type": "integer"},
        "search_latency_ms": {"type": "number"},
        "indexing_latency_ms": {"type": "number"},
        "search_qps": {"type": "number"},
        "indexing_qps": {"type": "number"},
        "cluster_health": {"type": "string", "enum": ["green", "yellow", "red"]},
        "node_count": {"type": "integer"},
        "shard_count": {"type": "integer"},
        "unassigned_shards": {"type": "integer"}
      }
    },
    "root_cause": {
      "type": "object",
      "required": ["hypothesis", "confidence"],
      "properties": {
        "hypothesis": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "category": {"type": "string", "enum": ["resource_exhaustion", "configuration_error", "network_issue", "dependency_failure", "software_bug", "unknown"]},
        "evidence": {
          "type": "array",
          "items": {"type": "string"}
        },
        "diagnosis_rounds": {"type": "integer", "minimum": 1}
      }
    },
    "remediation_action": {
      "type": "object",
      "required": ["action", "status"],
      "properties": {
        "action_id": {"type": "string"},
        "action": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed", "skipped"]},
        "automated": {"type": "boolean"},
        "result": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "cross_skill": {"type": "boolean"},
        "delegate_skill": {"type": "string"}
      }
    },
    "correlation": {
      "type": "object",
      "properties": {
        "pattern_name": {"type": "string"},
        "pattern_type": {"type": "string"},
        "correlated_metrics": {
          "type": "array",
          "items": {"type": "string"}
        },
        "correlation_strength": {"type": "number"}
      }
    },
    "cross_skill_dep": {
      "type": "object",
      "properties": {
        "skill_name": {"type": "string"},
        "dependency_type": {"type": "string", "enum": ["required", "optional", "fallback"]},
        "status": {"type": "string", "enum": ["resolved", "pending", "not_applicable"]}
      }
    },
    "self_reflection": {
      "type": "object",
      "properties": {
        "round_count": {"type": "integer"},
        "satisfaction_status": {"type": "string", "enum": ["satisfied", "needs_iteration", "escalate"]},
        "findings_per_round": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "round": {"type": "integer"},
              "findings_count": {"type": "integer"},
              "new_findings": {"type": "integer"},
              "resolved_findings": {"type": "integer"}
            }
          }
        },
        "final_conclusion": {"type": "string"}
      }
    },
    "links": {
      "type": "object",
      "properties": {
        "instance_console_url": {"type": "string", "format": "uri"},
        "monitoring_dashboard": {"type": "string", "format": "uri"},
        "troubleshooting_guide": {"type": "string", "format": "uri"},
        "support_channel": {"type": "string", "format": "uri"}
      }
    }
  }
}
```

---

## 3. Report Generation Templates

### 3.1 Instance Diagnostic Report Example

```json
{
  "report_id": "ES-DIAG-20260517-143025-A1B2C3D4",
  "timestamp": "2026-05-17T14:30:25Z",
  "instance_id": "es-cn-abc123",
  "region_id": "cn-hangzhou",
  "report_type": "instance_diagnostic",
  "overall_status": "warning",
  "severity": "warning",
  "findings": [
    {
      "finding_id": "F-001",
      "category": "instance_status",
      "severity": "info",
      "message": "Instance running normally",
      "detail": {"status": "Normal"},
      "timestamp": "2026-05-17T14:30:25Z"
    },
    {
      "finding_id": "F-002",
      "category": "cluster_health",
      "severity": "warning",
      "message": "Cluster health yellow, 2 unassigned shards",
      "detail": {"health": "yellow", "unassigned_shards": 2},
      "threshold": {
        "metric_name": "unassigned_shards",
        "current_value": 2,
        "threshold_value": 0,
        "unit": "count"
      },
      "timestamp": "2026-05-17T14:30:26Z"
    },
    {
      "finding_id": "F-003",
      "category": "jvm",
      "severity": "warning",
      "message": "JVM heap usage high (82%)",
      "threshold": {
        "metric_name": "jvm_heap_used_percent",
        "current_value": 82,
        "threshold_value": 80,
        "unit": "percent"
      },
      "timestamp": "2026-05-17T14:30:27Z"
    },
    {
      "finding_id": "F-004",
      "category": "disk",
      "severity": "info",
      "message": "Disk usage normal (65%)",
      "threshold": {
        "metric_name": "instance_disk_utilization",
        "current_value": 65,
        "threshold_value": 80,
        "unit": "percent"
      },
      "timestamp": "2026-05-17T14:30:28Z"
    }
  ],
  "metrics": {
    "instance_cpu_utilization": 45.2,
    "instance_memory_utilization": 78.5,
    "instance_disk_utilization": 65.0,
    "jvm_heap_used_percent": 82.0,
    "jvm_gc_collection_count": 12,
    "jvm_gc_collection_time_ms": 350,
    "search_latency_ms": 85.5,
    "indexing_latency_ms": 42.3,
    "search_qps": 150.2,
    "indexing_qps": 80.5,
    "cluster_health": "yellow",
    "node_count": 5,
    "shard_count": 150,
    "unassigned_shards": 2
  },
  "root_cause": {
    "hypothesis": "Shard allocation imbalance causing unassigned shards and JVM pressure",
    "confidence": 0.75,
    "category": "configuration",
    "evidence": [
      "Node 3 has higher disk usage than others",
      "Shard allocation settings may restrict rebalancing"
    ],
    "diagnosis_rounds": 2
  },
  "remediation_actions": [
    {
      "action_id": "RA-001",
      "action": "ShardReassignment",
      "status": "pending",
      "automated": true,
      "cross_skill": false
    },
    {
      "action_id": "RA-002",
      "action": "JVMTuning",
      "status": "pending",
      "automated": false
    }
  ],
  "correlation_analysis": {
    "pattern_name": "Cluster-Shard-Anomaly",
    "pattern_type": "multi_metric",
    "correlated_metrics": ["cluster_health", "unassigned_shards", "jvm_heap"],
    "correlation_strength": 0.85
  },
  "cross_skill_dependencies": [],
  "self_reflection": {
    "round_count": 2,
    "satisfaction_status": "satisfied",
    "findings_per_round": [
      {"round": 1, "findings_count": 4, "new_findings": 4, "resolved_findings": 0},
      {"round": 2, "findings_count": 4, "new_findings": 0, "resolved_findings": 0}
    ],
    "final_conclusion": "Root cause identified with high confidence, remediation actions defined"
  },
  "request_id": "E1F2G3H4-I5J6-K7L8-M9N0-O1P2Q3R4",
  "links": {
    "instance_console_url": "https://elasticsearch.console.aliyun.com/instance/es-cn-abc123",
    "monitoring_dashboard": "https://grafana.internal/d/es-health",
    "troubleshooting_guide": "references/troubleshooting.md#cluster_health",
    "support_channel": "https://workorder.console.aliyun.com/"
  }
}
```

---

## 4. Markdown Report Template

### 4.1 Human-Readable Format

```markdown
# Elasticsearch Diagnostic Report

**Report ID:** {{report_id}}
**Timestamp:** {{timestamp}}
**Instance:** {{instance_id}} ({{region_id}})
**Type:** {{report_type}}
**Overall Status:** {{overall_status}} 🔴/⚠️/✅

---

## Summary

| Category | Severity | Message |
|----------|----------|---------|
{{#each findings}}
| {{category}} | {{severity}} | {{message}} |
{{/each}}

---

## Key Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
{{#each metrics}}
| {{name}} | {{value}}{{unit}} | {{threshold}} | {{status}} |
{{/each}}

---

## Root Cause Analysis

**Hypothesis:** {{root_cause.hypothesis}}
**Confidence:** {{root_cause.confidence}}%
**Category:** {{root_cause.category}}

**Evidence:**
{{#each root_cause.evidence}}
- {{.}}
{{/each}}

**Diagnosis Rounds:** {{root_cause.diagnosis_rounds}}

---

## Correlation Analysis

**Pattern Detected:** {{correlation_analysis.pattern_name}}
**Correlated Metrics:** {{correlation_analysis.correlated_metrics}}
**Correlation Strength:** {{correlation_analysis.correlation_strength}}

---

## Remediation Actions

| Action ID | Action | Status | Automated |
|-----------|--------|--------|-----------|
{{#each remediation_actions}}
| {{action_id}} | {{action}} | {{status}} | {{automated}} |
{{/each}}

---

## Self-Reflection

**Rounds:** {{self_reflection.round_count}}
**Status:** {{self_reflection.satisfaction_status}}

| Round | Findings | New | Resolved |
|-------|----------|-----|----------|
{{#each self_reflection.findings_per_round}}
| {{round}} | {{findings_count}} | {{new_findings}} | {{resolved_findings}} |
{{/each}}

**Conclusion:** {{self_reflection.final_conclusion}}

---

## Resources

- [Instance Console]({{links.instance_console_url}})
- [Monitoring Dashboard]({{links.monitoring_dashboard}})
- [Troubleshooting Guide]({{links.troubleshooting_guide}})
- [Support Channel]({{links.support_channel}}

---

*RequestId: {{request_id}}*
```

---

## 5. Alarm Storm Report Example

### 5.1 Alarm Storm Diagnostic Report

```json
{
  "report_id": "ES-DIAG-20260517-153000-STORM01",
  "timestamp": "2026-05-17T15:30:00Z",
  "instance_id": "es-cn-abc123",
  "region_id": "cn-hangzhou",
  "report_type": "alarm_storm",
  "overall_status": "critical",
  "severity": "emergency",
  "findings": [
    {
      "finding_id": "F-001",
      "category": "performance",
      "severity": "critical",
      "message": "Alarm storm detected: 35 alerts in 5 minutes",
      "detail": {
        "storm_type": "APIRateLimitStorm",
        "alarm_count": 35,
        "window_seconds": 300,
        "affected_instances": 5
      },
      "timestamp": "2026-05-17T15:30:00Z"
    },
    {
      "finding_id": "F-002",
      "category": "performance",
      "severity": "warning",
      "message": "API throttling affecting multiple instances",
      "detail": {
        "error_code": "Throttling",
        "occurrence_count": 28,
        "suppressed_count": 19
      },
      "timestamp": "2026-05-17T15:30:05Z"
    },
    {
      "finding_id": "F-003",
      "category": "cluster_health",
      "severity": "warning",
      "message": "Cluster health yellow due to API latency",
      "detail": {
        "health": "yellow",
        "cause": "API throttling causing operation delays"
      },
      "timestamp": "2026-05-17T15:30:10Z"
    }
  ],
  "metrics": {
    "instance_cpu_utilization": 45.2,
    "search_latency_ms": 250.5,
    "search_qps": 50.2,
    "cluster_health": "yellow",
    "node_count": 5
  },
  "root_cause": {
    "hypothesis": "API rate limit exceeded due to burst of concurrent operations",
    "confidence": 0.95,
    "category": "resource_exhaustion",
    "evidence": [
      "28 Throttling errors in last 5 minutes",
      "Concurrent batch operations exceeded quota",
      "No infrastructure issues detected"
    ],
    "diagnosis_rounds": 2
  },
  "remediation_actions": [
    {
      "action_id": "RA-001",
      "action": "ImplementExponentialBackoff",
      "status": "completed",
      "automated": true,
      "result": "Backoff strategy applied to API calls",
      "timestamp": "2026-05-17T15:32:00Z",
      "cross_skill": false
    },
    {
      "action_id": "RA-002",
      "action": "SuppressDuplicateAlarms",
      "status": "completed",
      "automated": true,
      "result": "19 duplicate alarms suppressed",
      "timestamp": "2026-05-17T15:32:05Z",
      "cross_skill": false
    },
    {
      "action_id": "RA-003",
      "action": "ReduceBatchConcurrency",
      "status": "in_progress",
      "automated": false,
      "cross_skill": false
    }
  ],
  "correlation_analysis": {
    "pattern_name": "API-Throttling-Cascade",
    "pattern_type": "alarm_storm",
    "correlated_metrics": ["api_call_rate", "throttling_count", "cluster_health"],
    "correlation_strength": 0.92
  },
  "cross_skill_dependencies": [],
  "self_reflection": {
    "round_count": 2,
    "satisfaction_status": "satisfied",
    "findings_per_round": [
      {"round": 1, "findings_count": 3, "new_findings": 3, "resolved_findings": 0},
      {"round": 2, "findings_count": 3, "new_findings": 0, "resolved_findings": 0}
    ],
    "final_conclusion": "Alarm storm root cause identified (API throttling), remediation in progress"
  },
  "request_id": "STORM-E1F2G3H4-I5J6",
  "links": {
    "instance_console_url": "https://elasticsearch.console.aliyun.com/instance/es-cn-abc123",
    "monitoring_dashboard": "https://grafana.internal/d/es-health",
    "troubleshooting_guide": "../operations/alarm-storm-handling.md",
    "support_channel": "https://workorder.console.aliyun.com/"
  }
}
```

### 5.2 Alarm Storm Markdown Report

```markdown
# Elasticsearch Alarm Storm Report

**Report ID:** ES-DIAG-20260517-153000-STORM01
**Timestamp:** 2026-05-17T15:30:00Z
**Type:** alarm_storm
**Status:** 🚨 Critical (Emergency)

---

## Storm Summary

| Metric | Value |
|--------|-------|
| Total Alarms | 35 in 5 minutes |
| Storm Type | APIRateLimitStorm |
| Affected Instances | 5 |
| Suppressed Duplicates | 19 |

---

## Storm Pattern Classification

**Pattern:** API-Throttling-Cascade
**Dominant Error:** Throttling (28 occurrences)
**Severity:** Emergency

---

## Root Cause Analysis

**Hypothesis:** API rate limit exceeded due to burst of concurrent operations
**Confidence:** 95%
**Category:** Resource Exhaustion

**Evidence:**
- 28 Throttling errors in last 5 minutes
- Concurrent batch operations exceeded quota
- No infrastructure issues detected

---

## Remediation Actions

| Action | Status | Automated | Result |
|--------|--------|-----------|--------|
| ImplementExponentialBackoff | ✅ Completed | Yes | Backoff applied |
| SuppressDuplicateAlarms | ✅ Completed | Yes | 19 suppressed |
| ReduceBatchConcurrency | 🔄 In Progress | No | Manual adjustment |

---

## Alarm Storm Checklist Status

```
Detection:
✅ Alarm count exceeds threshold (>30/5min)
✅ Storm pattern classified (APIRateLimitStorm)
✅ Root cause identified

Suppression:
✅ Duplicate alarms suppressed (19 alarms)
✅ Storm aggregated into single actionable alert
✅ Maintenance windows checked

Resolution:
🔄 Remediation in progress
✅ Exponential backoff implemented
⏳ Batch concurrency reduction pending
```

---

## Related Operations

- [Alarm Storm Handling Guide](../operations/alarm-storm-handling.md)
- [Proactive Inspection](../operations/proactive-inspection.md)
- [Monitoring Configuration](../references/monitoring.md)

---

*RequestId: STORM-E1F2G3H4-I5J6*
```

---

## 5. Report Generation Implementation

### 5.1 Report Generator Code

```go
func generateDiagnosticReport(instanceId, reportType string, findings []Finding) *DiagnosticReport {
    report := &DiagnosticReport{
        ReportId:      generateReportId(),
        Timestamp:     time.Now(),
        InstanceId:    instanceId,
        RegionId:      os.Getenv("ALIBABA_CLOUD_REGION_ID"),
        ReportType:    reportType,
        OverallStatus: calculateOverallStatus(findings),
        Severity:      calculateHighestSeverity(findings),
        Findings:      findings,
        Metrics:       collectMetrics(instanceId),
        RequestId:     lastRequestId,
    }
    
    // Root cause analysis
    report.RootCause = identifyRootCause(findings)
    
    // Correlation analysis
    report.CorrelationAnalysis = analyzeCorrelations(findings, report.Metrics)
    
    // Remediation actions
    report.RemediationActions = generateRemediationActions(report)
    
    // Links
    report.Links = generateLinks(instanceId)
    
    return report
}

func generateReportId() string {
    return fmt.Sprintf("ES-DIAG-%s-%s",
        time.Now().Format("20060102"),
        time.Now().Format("150405"),
        generateRandomSuffix(8))
}

func calculateOverallStatus(findings []Finding) string {
    for _, f := range findings {
        if f.Severity == "critical" {
            return "critical"
        }
    }
    for _, f := range findings {
        if f.Severity == "warning" {
            return "warning"
        }
    }
    return "healthy"
}

func (r *DiagnosticReport) ToJSON() string {
    data, _ := json.MarshalIndent(r, "", "  ")
    return string(data)
}

func (r *DiagnosticReport) ToMarkdown() string {
    // Generate markdown from template
    return renderMarkdownTemplate(r)
}
```

---

## 6. Report Storage and Retrieval

### 6.1 Storage Schema

```yaml
Storage Location: /reports/diagnostic/{{instance_id}}/{{date}}/

File Naming:
  - JSON: {{report_id}}.json
  - Markdown: {{report_id}}.md

Retention Policy:
  - Critical reports: 90 days
  - Warning reports: 30 days
  - Info reports: 7 days

Indexing:
  - By instance_id
  - By report_type
  - By timestamp
  - By overall_status
```

### 6.2 Report Query Interface

```go
func queryDiagnosticReports(filters ReportFilters) []DiagnosticReport {
    // Query stored reports by filters
    // Filters: instance_id, date_range, report_type, status
    
    reports := []DiagnosticReport{}
    
    // Load from storage
    files := listReportFiles(filters.InstanceId, filters.StartDate, filters.EndDate)
    
    for _, file := range files {
        report := loadReport(file)
        
        // Apply filters
        if filters.ReportType != "" && report.ReportType != filters.ReportType {
            continue
        }
        if filters.Status != "" && report.OverallStatus != filters.Status {
            continue
        }
        
        reports = append(reports, report)
    }
    
    return reports
}

type ReportFilters struct {
    InstanceId string
    StartDate  time.Time
    EndDate    time.Time
    ReportType string
    Status     string
}
```

---

## 7. Integration with AIOps Platform

### 7.1 Report API Interface

```yaml
Endpoints:

POST /reports/diagnostic
  - Generate new diagnostic report
  - Input: instance_id, report_type, trigger_reason
  - Output: report JSON

GET /reports/diagnostic/{report_id}
  - Retrieve specific report
  - Output: report JSON or Markdown

GET /reports/diagnostic/search
  - Query reports by filters
  - Input: instance_id, status, date_range
  - Output: list of reports

POST /reports/diagnostic/{report_id}/remediation
  - Execute remediation actions
  - Input: action_ids
  - Output: remediation results
```

---

## 8. Report Usage Patterns

### 8.1 Incident Tracking Integration

```yaml
Incident Creation from Report:

Trigger: report.overall_status == "critical"
Action:
  1. Create incident with report details
  2. Attach report_id to incident
  3. Link remediation actions to incident timeline
  
Incident Fields:
  - Title: "{{report_type}} - {{instance_id}}"
  - Severity: "{{report.severity}}"
  - Description: "{{root_cause.hypothesis}}"
  - Evidence: "{{report.findings}}"
  - Remediation: "{{remediation_actions}}"
```

### 8.2 Audit Trail Integration

```yaml
Audit Trail Entry:

Event: DiagnosticReportGenerated
Fields:
  - report_id
  - instance_id
  - overall_status
  - severity
  - findings_count
  - remediation_actions_count
  - automated_remediation_count
```

---

*This diagnostic report schema provides unified format for AIOps automation and incident management.*