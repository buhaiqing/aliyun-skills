---
name: incident-schema
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# Incident Schema — 巡检发现标准化数据结构

> **目的**：将所有 runbook 输出的"finding / 巡检发现"统一为标准化的 Incident 数据结构。下游消费方（自动化工单、Post-Mortem 复盘、ML 训练、跨客户聚合）有可依赖的契约。
>
> **生命周期**：v1.0 草案 -> 安全/数据团队评审 -> v1.0 正式 -> 不可破坏性更新（仅追加可选字段）

---

## 一、设计原则

| 原则 | 说明 |
|------|------|
| **稳定性** | 字段集变化必须有版本号；破坏性变更必须 major bump |
| **可追溯** | 每个 Incident 必须能从 `trace.commands_executed` 还原产生过程 |
| **可检索** | 必填字段覆盖 (customer, resource_type, level, rule_id, timestamp) 五维度，便于建索引 |
| **可关联** | 必填字段 `dedup_key` 决定同源 Incident 是否合并（同一资源同一天同一规则 -> 1 条） |
| **可消费** | 字段命名 snake_case；类型严格化（不接受 string 表达数字） |
| **可扩展** | 所有必填外字段允许 `null` 或缺失；保留 `metadata` 自由扩展位 |

---

## 二、字段定义

### 2.1 核心标识（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `incident_id` | string (UUIDv4) | Incident 全局唯一 ID，由生成端在产生时分配 |
| `schema_version` | string (semver) | 本 schema 遵循的版本，例：`1.0.0` |
| `customer` | string | 客户标识（资源组名 / 标签值 / 客户名） |
| `timestamp` | string (ISO8601) | Incident 产生时间（含时区） |
| `run_id` | string (UUIDv4) | 所属 runbook 执行的 run_id（用于反查整次巡检） |

### 2.2 严重度（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `level` | enum | `CRITICAL` / `WARNING` / `INFO` 三档 |
| `score` | float [0.0, 1.0] | 异常评分（动态基线 Z-Score 经 sigmoid 归一化），可空 |

### 2.3 资源定位（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `resource_type` | enum | `ECS` / `SLB` / `RDS` / `Redis` / `MongoDB` / `PolarDB` / `NAT` / `EIP` / `VPC` / `SG` / `ACK` / `OSS` / `NAS` / `OTHER` |
| `resource_id` | string | 资源主键（阿里云实例 ID） |
| `resource_name` | string | 资源展示名（可空） |
| `region` | string | 资源所在 Region，例：`cn-hangzhou` |

### 2.4 规则与归因（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `rule_id` | string | 推理规则 ID，命名规范见 §三 |
| `rule_version` | string (semver) | 规则版本，便于规则迭代时回溯 |
| `title` | string | 人类可读标题，例：`RDS 磁盘使用率超标` |
| `dedup_key` | string | 去重键，规则见 §四 |

### 2.5 指标数据（条件必填，规则触发时必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `metric` | string | 监控指标名，例：`DiskUsage` |
| `current_value` | number | 当前值 |
| `threshold_critical` | number | Critical 阈值（可空，纯规则型 finding 无此字段） |
| `threshold_warning` | number | Warning 阈值（可空） |
| `baseline_mean` | number | 历史均值（动态基线，可空） |
| `baseline_std` | number | 历史标准差（可空） |
| `z_score` | number | 偏离程度（可空） |

### 2.6 业务影响与建议（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `impact` | string | 影响描述（人类可读，1-3 句话） |
| `suggestion` | string | 处置建议（人类可读） |
| `fix_commands` | array[string] | 可执行 CLI 命令列表，**必须**带前置标记：`[READONLY]` / `[SUGGESTED]` / `[AUTO-QUIET]` / `[AUTO-NOTIFY]` |

### 2.7 生命周期（选填，落地系统填充）

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | enum | `open` / `acknowledged` / `in_progress` / `resolved` / `suppressed` |
| `assignee` | string | 处理人（主账号 / 邮箱） |
| `acknowledged_at` | string (ISO8601) | 认领时间 |
| `resolved_at` | string (ISO8601) | 解决时间 |
| `ttl_hours` | integer | 存活期（默认 168 = 7 天） |
| `parent_incident_id` | string (UUIDv4) | 父 Incident（聚合多子发现时用） |
| `related_incidents` | array[UUIDv4] | 关联 Incident 列表（同链路上下游） |

### 2.8 可追溯（必填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace` | object | 见 §六 |

### 2.9 扩展位（选填）

| 字段 | 类型 | 说明 |
|------|------|------|
| `tags` | array[string] | 自由标签，便于聚合检索 |
| `metadata` | object | 任意 K-V 扩展，schema 不校验内容 |

---

## 三、`rule_id` 命名规范

> **格式**：`<PRODUCT>-<NUMBER>`，全大写、连字符分隔
> **归属**：每个 `rule_id` 必须在 `references/inference-rules.md` 中有完整定义

| 示例 | 含义 |
|------|------|
| `SLB-ECS-01` | SLB->ECS 链路第 1 条规则 |
| `RDS-04` | RDS 第 4 条规则 |
| `ACK-LIMITS-02` | ACK Limits 超分第 2 条规则 |
| `SG-01` | 安全组第 1 条规则 |

`rule_version` 独立于 schema 版本，用于规则自身迭代。

---

## 四、`dedup_key` 生成规则

> **目的**：同一资源同一天同一规则只产生 1 条 Incident（避免运行时重复发现刷屏）

**格式**：

```
{customer}:{resource_type}:{resource_id}:{rule_id}:{date_bucket}
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `customer` | 客户标识（与 §2.1 一致） | `rg-acfmvyfsd4znnoi` |
| `resource_type` | 资源类型 | `RDS` |
| `resource_id` | 实例 ID | `rm-bp1xxxxxxxx` |
| `rule_id` | 规则 ID | `RDS-04` |
| `date_bucket` | 日期桶，格式 `YYYY-MM-DD`（按客户时区） | `2026-06-06` |

**示例**：
```
rg-acfmvyfsd4znnoi:RDS:rm-bp1xxxxxxxx:RDS-04:2026-06-06
```

**特殊规则**：
- 巡检模式为 `emergency` 时：`date_bucket` 改为小时桶 `YYYY-MM-DDTHH`，允许同一小时内升级
- `INFO` 级别 Incident 不进 dedup 池

---

## 五、`level` 判定语义

| Level | 含义 | GCL 行为 | 用户通知 |
|-------|------|---------|---------|
| `CRITICAL` | 必须立即处理（数据丢失/安全/容量即将耗尽） | GCL 必须列出 + Safety 不允许忽略 | 钉钉/短信/电话 |
| `WARNING` | 需要关注但非紧急 | GCL 列出 + 可标记需复核 | 钉钉 |
| `INFO` | 信息性发现（无明确风险） | GCL 列出但不阻塞 | 邮件/日报 |

`level` 与现有 `references/inference-rules.md` 中的级别标识完全对齐（CRITICAL / WARNING / INFO）。

---

## 六、`trace` 子结构

> **目的**：Incident 的"出生证明"——记录产生它的命令、参数、原始响应片段

```json
{
  "trace": {
    "runbook_id": "01-daily-health-check",
    "runbook_version": "1.0.0",
    "scenario": "daily_check",
    "commands_executed": [
      {
        "command": "aliyun cms DescribeMetricList",
        "params": {"Namespace": "acs_rds_dashboard", "MetricName": "DiskUsage", ...},
        "response_excerpt": "{\"Datapoints\":[{\"Timestamp\":\"...\",\"Average\":97.3}]}",
        "duration_ms": 312
      }
    ],
    "total_api_calls": 12,
    "detection_method": "z-score | percentile | stl | static-threshold",
    "report_path": "audit-results/json/cruise-rg-xxx-2026-06-06.json"
  }
}
```

---

## 七、完整 JSON Schema 草案

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://aliyun-skills.local/schemas/incident-v1.json",
  "title": "aiops-cruise Incident",
  "description": "AIOps Cruise runbook 输出的标准 Incident 结构 v1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "incident_id", "schema_version", "customer", "timestamp", "run_id",
    "level", "resource_type", "resource_id", "region",
    "rule_id", "title", "dedup_key", "impact", "suggestion", "trace"
  ],
  "properties": {
    "incident_id":           { "type": "string", "format": "uuid" },
    "schema_version":        { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$" },
    "customer":              { "type": "string", "minLength": 1 },
    "timestamp":             { "type": "string", "format": "date-time" },
    "run_id":                { "type": "string", "format": "uuid" },

    "level": {
      "type": "string",
      "enum": ["CRITICAL", "WARNING", "INFO"]
    },
    "score":                 { "type": ["number", "null"], "minimum": 0, "maximum": 1 },

    "resource_type": {
      "type": "string",
      "enum": ["ECS", "SLB", "RDS", "Redis", "MongoDB", "PolarDB",
               "NAT", "EIP", "VPC", "SG", "ACK", "OSS", "NAS", "OTHER"]
    },
    "resource_id":           { "type": "string", "minLength": 1 },
    "resource_name":         { "type": ["string", "null"] },
    "region":                { "type": "string", "minLength": 1 },

    "rule_id":               { "type": "string", "pattern": "^[A-Z]+-[A-Z0-9-]+$" },
    "rule_version":          { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$" },
    "title":                 { "type": "string", "minLength": 1 },
    "dedup_key":             { "type": "string", "minLength": 1 },

    "metric":                { "type": ["string", "null"] },
    "current_value":         { "type": ["number", "null"] },
    "threshold_critical":    { "type": ["number", "null"] },
    "threshold_warning":     { "type": ["number", "null"] },
    "baseline_mean":         { "type": ["number", "null"] },
    "baseline_std":          { "type": ["number", "null"] },
    "z_score":               { "type": ["number", "null"] },

    "impact":                { "type": "string", "minLength": 1 },
    "suggestion":            { "type": "string", "minLength": 1 },
    "fix_commands": {
      "type": "array",
      "items": { "type": "string" }
    },

    "status": {
      "type": "string",
      "enum": ["open", "acknowledged", "in_progress", "resolved", "suppressed"]
    },
    "assignee":              { "type": ["string", "null"] },
    "acknowledged_at":       { "type": ["string", "null"], "format": "date-time" },
    "resolved_at":           { "type": ["string", "null"], "format": "date-time" },
    "ttl_hours":             { "type": ["integer", "null"], "minimum": 1, "maximum": 8760 },
    "parent_incident_id":    { "type": ["string", "null"], "format": "uuid" },
    "related_incidents": {
      "type": "array",
      "items": { "type": "string", "format": "uuid" }
    },

    "trace": {
      "type": "object",
      "required": ["runbook_id", "scenario", "commands_executed", "report_path"],
      "additionalProperties": false,
      "properties": {
        "runbook_id":          { "type": "string" },
        "runbook_version":     { "type": "string" },
        "scenario": {
          "type": "string",
          "enum": ["daily_check", "emergency", "capacity", "pre_launch"]
        },
        "commands_executed": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["command"],
            "properties": {
              "command":         { "type": "string" },
              "params":          { "type": "object" },
              "response_excerpt":{ "type": "string" },
              "duration_ms":     { "type": "integer", "minimum": 0 }
            }
          }
        },
        "total_api_calls":     { "type": "integer", "minimum": 0 },
        "detection_method":    {
          "type": "string",
          "enum": ["z-score", "percentile", "stl", "static-threshold", "hybrid"]
        },
        "report_path":         { "type": "string" }
      }
    },

    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "metadata":              { "type": "object" }
  }
}
```

---

## 八、filled 示例

### 8.1 CRITICAL — RDS 磁盘超标

```json
{
  "incident_id": "f1a7d2b3-4e5c-4a8b-9c0d-1e2f3a4b5c6d",
  "schema_version": "1.0.0",
  "customer": "rg-acfmvyfsd4znnoi",
  "timestamp": "2026-06-06T15:23:41+08:00",
  "run_id": "9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e",
  "level": "CRITICAL",
  "score": 0.93,
  "resource_type": "RDS",
  "resource_id": "rm-bp1xxxxxxxxxxxx",
  "resource_name": "prod-mysql-primary",
  "region": "cn-hangzhou",
  "rule_id": "RDS-04",
  "rule_version": "1.2.0",
  "title": "RDS 磁盘使用率超标 97%",
  "dedup_key": "rg-acfmvyfsd4znnoi:RDS:rm-bp1xxxxxxxxxxxx:RDS-04:2026-06-06",
  "metric": "DiskUsage",
  "current_value": 97.3,
  "threshold_critical": 90.0,
  "threshold_warning": 75.0,
  "baseline_mean": 62.4,
  "baseline_std": 4.8,
  "z_score": 7.27,
  "impact": "RDS 实例 prod-mysql-primary 磁盘使用率 97.3%，已超过 Critical 阈值 90%，数据库可能进入只读模式，所有写入业务将失败。",
  "suggestion": "方案A: 立即扩容存储 (ModifyDBInstanceSpec --DBInstanceStorage 200)；方案B: 清理已消费 binlog (CALL mysql.rds_cycle_binlog())；方案C: 归档历史大表。",
  "fix_commands": [
    "[SUGGESTED] aliyun rds ModifyDBInstanceSpec --DBInstanceId rm-bp1xxxxxxxxxxxx --DBInstanceStorage 200",
    "[AUTO-NOTIFY] aliyun rds InvokeDBAction --DBInstanceId rm-bp1xxxxxxxxxxxx --Command 'CALL mysql.rds_cycle_binlog();'",
    "[READONLY] aliyun cms DescribeMetricList --Namespace acs_rds_dashboard --MetricName DiskUsage --DBInstanceId rm-bp1xxxxxxxxxxxx"
  ],
  "status": "open",
  "ttl_hours": 168,
  "trace": {
    "runbook_id": "01-daily-health-check",
    "runbook_version": "1.0.0",
    "scenario": "daily_check",
    "commands_executed": [
      {
        "command": "aliyun cms DescribeMetricList",
        "params": {
          "Namespace": "acs_rds_dashboard",
          "MetricName": "DiskUsage",
          "DBInstanceId": "rm-bp1xxxxxxxxxxxx",
          "Period": 300
        },
        "response_excerpt": "{\"Datapoints\":[{\"Timestamp\":\"2026-06-06T15:20:00Z\",\"Average\":97.3}]}",
        "duration_ms": 312
      }
    ],
    "total_api_calls": 3,
    "detection_method": "static-threshold",
    "report_path": "audit-results/json/cruise-rg-acfmvyfsd4znnoi-2026-06-06.json"
  },
  "tags": ["capacity", "rds", "production"],
  "metadata": {
    "instance_class": "rds.mysql.s3.large",
    "engine_version": "8.0"
  }
}
```

### 8.2 WARNING — 安全组端口暴漏

```json
{
  "incident_id": "a2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6e",
  "schema_version": "1.0.0",
  "customer": "rg-acfmvyfsd4znnoi",
  "timestamp": "2026-06-06T15:25:12+08:00",
  "run_id": "9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e",
  "level": "WARNING",
  "score": 0.78,
  "resource_type": "SG",
  "resource_id": "sg-bp1yyyyyyyyyyyy",
  "resource_name": "ops-jump-host-sg",
  "region": "cn-hangzhou",
  "rule_id": "SG-01",
  "rule_version": "1.0.0",
  "title": "安全组 ops-jump-host-sg 22 端口对 0.0.0.0/0 开放",
  "dedup_key": "rg-acfmvyfsd4znnoi:SG:sg-bp1yyyyyyyyyyyy:SG-01:2026-06-06",
  "metric": null,
  "current_value": null,
  "impact": "安全组对 0.0.0.0/0 开放 22 端口，SSH 服务存在被暴力破解和数据泄露风险。",
  "suggestion": "将来源 IP 收窄到堡垒机出口 IP 段，或通过阿里云堡垒机统一访问入口。",
  "fix_commands": [
    "[SUGGESTED] aliyun ecs RevokeSecurityGroup --SecurityGroupId sg-bp1yyyyyyyyyyyy --SourceCidrIp 0.0.0.0/0 --PortRange 22/22 --IpProtocol tcp",
    "[READONLY] aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId sg-bp1yyyyyyyyyyyy"
  ],
  "status": "open",
  "ttl_hours": 168,
  "trace": {
    "runbook_id": "01-daily-health-check",
    "runbook_version": "1.0.0",
    "scenario": "daily_check",
    "commands_executed": [
      {
        "command": "aliyun ecs DescribeSecurityGroupAttribute",
        "params": { "SecurityGroupId": "sg-bp1yyyyyyyyyyyy", "RegionId": "cn-hangzhou" },
        "response_excerpt": "{\"Permissions\":[{\"SourceCidrIp\":\"0.0.0.0/0\",\"PortRange\":\"22/22\",\"IpProtocol\":\"TCP\"}]}",
        "duration_ms": 218
      }
    ],
    "total_api_calls": 1,
    "detection_method": "static-threshold",
    "report_path": "audit-results/json/cruise-rg-acfmvyfsd4znnoi-2026-06-06.json"
  },
  "tags": ["security", "sg"],
  "metadata": { "vpc_id": "vpc-bp1zzzzzzzzzzz" }
}
```

### 8.3 INFO — 全链路健康（无 finding 时的占位）

```json
{
  "incident_id": "b3c4d5e6-f7a8-4b9c-0d1e-2f3a4b5c6d7f",
  "schema_version": "1.0.0",
  "customer": "rg-acfmvyfsd4znnoi",
  "timestamp": "2026-06-06T16:00:00+08:00",
  "run_id": "9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e",
  "level": "INFO",
  "score": 0.0,
  "resource_type": "OTHER",
  "resource_id": "fleet:ECS",
  "resource_name": "ECS Fleet",
  "region": "cn-hangzhou",
  "rule_id": "FULL-01",
  "rule_version": "1.0.0",
  "title": "ECS 全链路巡检完成",
  "dedup_key": null,
  "impact": "本次巡检覆盖 5 个 ECS 实例，全部指标正常。",
  "suggestion": "无需处置。",
  "fix_commands": [],
  "status": "open",
  "ttl_hours": 24,
  "trace": {
    "runbook_id": "01-daily-health-check",
    "runbook_version": "1.0.0",
    "scenario": "daily_check",
    "commands_executed": [],
    "total_api_calls": 8,
    "detection_method": "static-threshold",
    "report_path": "audit-results/json/cruise-rg-acfmvyfsd4znnoi-2026-06-06.json"
  },
  "tags": ["fleet-summary"]
}
```

---

## 九、与现有文档的关系

| 现有文件 | 集成方式 |
|----------|---------|
| `references/delivery-standards.md` | JSON 报告结构中追加 `incidents` 数组字段，本 schema 即其元素契约 |
| `references/inference-rules.md` | 每个规则的 `rule_id` 即本 schema 中的 `rule_id`（如 `RDS-04`） |
| `references/rubric.md` | Traceability 维度追加子项："Incident 是否符合 schema" |
| `SKILL.md` Safety Gates | 引用本文件，约定"所有 finding 必须符合 incident-schema v1.0.0" |
| Sprint 9 (Incident 落地) | 直接消费本 schema 作为持久化契约 |
| Sprint 11 (ML 升级) | 依赖本 schema 训练/推理 |

---

## 十、版本策略

| 版本 | 兼容性 | 变更范围 |
|------|--------|---------|
| v1.0.x | 向后兼容 | 仅追加可选字段；调整示例；修正描述 |
| v1.x.0 | 向后兼容 | 调整必填字段约束（放宽）；新增可选字段 |
| v2.0.0 | 破坏性 | 必填字段变更；字段重命名；类型变更 |

**强制**：所有消费方代码（落地系统、GCL、Agent）必须先检查 `schema_version` 字段再决定是否解析。

---

## 十一、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-06 | 初始版本（Stage 1 -> Sprint 7 闭环 S1-D5） |
