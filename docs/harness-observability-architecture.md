# Runtime Harness 可观测性架构

> 本文档描述 Runtime Harness 可观测性体系的整体架构、数据流和实施路线图。
>
> **与记忆层的关系**：[memory-observability-relationship.md](./memory-observability-relationship.md) — Trace 双轨（可观测性 vs 三层记忆）架构复盘。

## 1. 架构概览

Runtime Harness 可观测性体系采用**三位一体**设计，覆盖 Metrics、Logs、Traces 三个维度：

```
┌─────────────────────────────────────────────────────────────┐
│                    SkillOpt 可观测性架构                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Metrics    │  │     Logs     │  │   Traces     │      │
│  │  (Prometheus)│  │ (JSON Lines) │  │  (Langfuse)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │  skillopt-lib   │                        │
│                  │     .sh         │                        │
│                  └────────┬────────┘                        │
│                           │                                 │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐          │
│    │ 熔断器  │      │ 自修复  │      │ 动态优化 │          │
│    └─────────┘      └─────────┘      └─────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 2. 数据流

### 2.1 事件触发点

Runtime Harness 在以下关键节点产生可观测性数据：

| 事件类型 | 触发时机 | 数据内容 |
|---------|---------|---------|
| **API 调用** | 每次 CLI 调用 | 调用参数、耗时、结果状态 |
| **参数优化** | 调用前优化 | 原始参数、优化后参数、优化原因 |
| **错误修复** | 修复流程 | 错误码、修复策略、修复结果 |
| **熔断器状态变化** | 状态转换 | 旧状态、新状态、触发原因 |

### 2.2 数据流向

```
┌─────────────────┐
│  SkillOpt 执行  │
└────────┬────────┘
         │
         ├─► skillopt_log()          ──► JSON Lines 日志文件
         │                              (Filebeat/Promtail 采集)
         │
         ├─► skillopt_update_runtime ──► Prometheus 指标文件
         │   └─► skillopt_export_metrics   (node_exporter 采集)
         │
         └─► skillopt_trace_event    ──► Langfuse API
                                        (Agent 调用链追踪)
```

## 3. 实施阶段

### Phase 1: 基础可观测性 ✅ 已实现

**目标**: 结构化日志 + Prometheus 指标导出

**能力**:
- ✅ JSON Lines 格式日志（机器可解析）
- ✅ Prometheus text format 指标文件
- ✅ 7 个核心指标（调用量、错误率、修复成功率等）
- ✅ 运营报告集成可观测性配置

> **Note on log formats**: SkillOpt uses JSON Lines / plain-text logs. The `[HH:MM:SS] [PHASE] key=value` diagnostic logging standard is for Cloud Assistant data-plane scripts only; see [`diagnostic-logging-standard.md`](./diagnostic-logging-standard.md).

**文档**: [Phase 1 实现文档](./harness-observability-phase1.md)

### Phase 2: Agent 调用链追踪 ✅ 已完成灰度验证

**目标**: Langfuse 集成，实现端到端追踪

**能力**:
- ✅ 追踪事件上报
- ✅ Agent 调用链关联
- ✅ 修复效果分析
- ✅ 9 个代表性 Skill 灰度接入并验证通过
- ✅ 完整验收脚本 `scripts/test-langfuse-gray-skills.sh` (52 PASS, 0 FAIL)

**文档**: [Phase 2 实现文档](./harness-observability-phase2.md)

### Phase 3: 智能告警与可视化 📋 规划中

**目标**: 主动告警 + Grafana 仪表盘

**能力**:
- 📋 Prometheus 告警规则
- 📋 Grafana 仪表盘模板
- 📋 运营报告增强（趋势分析）

**文档**: [Phase 3 设计文档](./harness-observability-phase3.md)

## 4. 配置方式

### 4.1 环境变量

> **核心开关语义**（正交，详见 [Runtime Harness 集成指南 §3.1](./harness-integration-guide.md#31-enable-flags-two-orthogonal-switches)）：
>
> | 变量 | 控制范围 | 默认 |
> |------|----------|------|
> | `SKILLOPT_ENABLED` | 自修复 / 参数优化 / 熔断器 | `false` |
> | `SKILLOPT_LANGFUSE_ENABLED` | Langfuse **远端 HTTP 上报**（不控制本地 trace 是否生成） | `false` |
>
> 本地 trace **每次 wrapper 调用都会写入**（Local-first canonical）；`SKILLOPT_LANGFUSE_ENABLED=true` 时额外镜像到 Langfuse 远端。Trace Judge（LLM/rule_engine）为设计文档中的规划能力，尚未接入 runtime（PR-5 已移除 dead `SKILLOPT_JUDGE_*` 配置）。TTL：`TRACE_KEEP_DAYS`（默认 7）via `make memory-maintain-apply`。

```bash
# Phase 1: 基础可观测性
export SKILLOPT_LOG_FORMAT="json"              # 日志格式: text | json
export SKILLOPT_METRICS_DIR="/path/to/metrics" # Prometheus 指标导出目录
export SKILLOPT_SKILL_TAG="cms"                # Skill 标识（自动设置）

# Phase 2: Langfuse 远端追踪（需 SKILLOPT_LANGFUSE_ENABLED=true + 下方 3 项）
export SKILLOPT_LANGFUSE_ENABLED="true"        # 远端上报开关（与 SKILLOPT_ENABLED 正交）
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export SKILLOPT_SESSION_ID="agent-session-123" # 多 Skill 共享 Session（推荐）
```

### 4.2 命令行参数

```bash
# Phase 1 参数（已实现）
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --skillopt-log-format json \
    --skillopt-metrics-dir /var/lib/node_exporter/textfile \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

## 5. 与现有系统集成

### 5.1 日志系统

| 采集工具 | 配置方式 | 说明 |
|---------|---------|------|
| **Filebeat** | `filebeat.inputs[].type: filestream` | 采集 JSON Lines 日志 |
| **Promtail** | `scrape_configs[].job_name: skillopt` | 采集 JSON Lines 日志 |
| **Fluentd** | `@type tail` | 采集 JSON Lines 日志 |

### 5.2 指标系统

| 组件 | 配置方式 | 说明 |
|-----|---------|------|
| **Prometheus** | `textfile` collector | 读取 `.prom` 文件 |
| **VictoriaMetrics** | `vmagent` | 读取 `.prom` 文件 |
| **Grafana** | Prometheus datasource | 查询指标 |

### 5.3 追踪系统

| 组件 | 集成方式 | 说明 |
|-----|---------|------|
| **Langfuse** | HTTP API | 异步上报追踪事件 |
| **Jaeger** | OpenTelemetry | 未来扩展 |
| **Zipkin** | OpenTelemetry | 未来扩展 |

## 6. 核心指标定义

### 6.1 Prometheus 指标

| 指标名称 | 类型 | 说明 |
|---------|------|------|
| `skillopt_total_calls` | Counter | API 总调用次数 |
| `skillopt_total_failures` | Counter | API 失败次数 |
| `skillopt_error_rate` | Gauge | 错误率（百分比） |
| `skillopt_repair_success` | Counter | 自修复成功次数 |
| `skillopt_query_count` | Counter | 查询执行次数 |
| `skillopt_circuit_breaker_state` | Gauge | 熔断器状态（0=closed, 1=open, 2=half-open） |
| `skillopt_circuit_breaker_failures` | Gauge | 熔断器连续失败次数 |

### 6.2 日志字段

JSON Lines 格式日志包含以下字段：

```json
{
  "timestamp": "2026-01-17T10:30:45.123Z",
  "level": "INFO",
  "skill": "cms",
  "event_type": "api_call",
  "product": "cms",
  "action": "DescribeMetricList",
  "duration_ms": 245,
  "success": true,
  "error_code": null,
  "repair_attempted": false,
  "repair_succeeded": false,
  "circuit_breaker_state": "closed"
}
```

### 6.3 追踪事件

Langfuse 追踪事件类型：

| 事件类型 | 说明 |
|---------|------|
| `api_call` | API 调用 |
| `optimization` | 参数优化 |
| `repair` | 错误修复 |
| `circuit_breaker` | 熔断器状态变化 |

## 7. 部署指南

### 7.1 最小化部署（Phase 1）

```bash
# 1. 启用 JSON 日志
export SKILLOPT_LOG_FORMAT="json"

# 2. 配置指标导出目录（Prometheus node_exporter）
export SKILLOPT_METRICS_DIR="/var/lib/node_exporter/textfile"

# 3. 运行 SkillOpt
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

### 7.2 完整部署（Phase 1 + 2）

```bash
# 1. Phase 1 配置
export SKILLOPT_LOG_FORMAT="json"
export SKILLOPT_METRICS_DIR="/var/lib/node_exporter/textfile"

# 2. Phase 2 配置
export SKILLOPT_LANGFUSE_ENABLED="true"
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."

# 3. Agent 传入追踪上下文
export LANGFUSE_TRACE_ID="agent-session-123"
export LANGFUSE_SESSION_ID="user-456"

# 4. 运行 SkillOpt
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

## 8. 采集配置示例

### 8.1 日志采集

#### Filebeat 配置

```yaml
# filebeat.yml - SkillOpt 日志采集
filebeat.inputs:
  - type: filestream
    id: skillopt-json-logs
    enabled: true
    paths:
      - /path/to/skills/.runtime/logs/alicloud-*-ops/*-skillopt-*.log
    parsers:
      - ndjson:
          target: skillopt
          add_error_key: true
    fields:
      source: skillopt
    fields_under_root: true

processors:
  - rename:
      fields:
        - from: skillopt.ts
          to: "@timestamp"
        - from: skillopt.msg
          to: message
        - from: skillopt.skill
          to: skill
        - from: skillopt.level
          to: level
      ignore_missing: true
  - drop_fields:
      fields: ["skillopt"]

output.elasticsearch:
  hosts: ["https://your-elasticsearch:9200"]
  index: "skillopt-%{+yyyy.MM.dd}"
  username: "${ES_USERNAME}"
  password: "${ES_PASSWORD}"

setup.template:
  name: "skillopt"
  pattern: "skillopt-*"
```

#### Promtail 配置（Loki 采集）

```yaml
# promtail.yml - SkillOpt 日志采集到 Loki
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: skillopt
    static_configs:
      - targets: [localhost]
        labels:
          job: skillopt
          __path__: /path/to/skills/.runtime/logs/alicloud-*-ops/*-skillopt-*.log
    pipeline_stages:
      - json:
          expressions:
            ts: ts
            skill: skill
            level: level
            msg: msg
            pid: pid
      - timestamp:
          source: ts
          format: "2006-01-02T15:04:05-0700"
      - labels:
          skill:
          level:
      - output:
          source: msg
```

#### Fluentd 配置

```xml
# fluentd.conf - SkillOpt 日志采集
<source>
  @type tail
  path /path/to/skills/.runtime/logs/alicloud-*-ops/*-skillopt-*.log
  pos_file /var/log/fluentd/skillopt.pos
  tag skillopt.*
  <parse>
    @type json
    time_key ts
    time_format %Y-%m-%dT%H:%M:%S%z
  </parse>
</source>

<match skillopt.**>
  @type elasticsearch
  host your-elasticsearch
  port 9200
  index_name skillopt
  <buffer>
    flush_interval 5s
  </buffer>
</match>
```

### 8.2 Prometheus 指标采集

#### node_exporter textfile 采集

```bash
# 1. 确保 node_exporter 启用 textfile collector
node_exporter --collector.textfile.directory=/var/lib/node_exporter/textfile

# 2. SkillOpt 指标文件自动写入该目录
export SKILLOPT_METRICS_DIR="/var/lib/node_exporter/textfile"
```

#### Prometheus scrape 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  # node_exporter（含 SkillOpt 指标）
  - job_name: node_exporter
    static_configs:
      - targets: ['localhost:9100']
    file_sd_configs:
      - files:
          - '/var/lib/node_exporter/textfile/*.prom'
        refresh_interval: 30s

  # 独立 SkillOpt 指标（可选，如果有独立 exporter）
  - job_name: skillopt
    static_configs:
      - targets: ['localhost:9101']
    metrics_path: /metrics
```

#### VictoriaMetrics vmagent 配置

```yaml
# vmagent.yml
scrape_configs:
  - job_name: skillopt_node_exporter
    static_configs:
      - targets: ['localhost:9100']
    file_sd_configs:
      - files:
          - '/var/lib/node_exporter/textfile/*.prom'
```

### 8.3 Langfuse 追踪配置（Phase 2）

#### 环境变量配置

```bash
# Langfuse 配置
export SKILLOPT_LANGFUSE_ENABLED="true"
export LANGFUSE_HOST="https://cloud.langfuse.com"  # 或自托管地址
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."

# Agent 传入追踪上下文
export LANGFUSE_TRACE_ID="agent-session-123"
export LANGFUSE_SESSION_ID="user-456"
```

#### Docker Compose 自托管 Langfuse

```yaml
# docker-compose.langfuse.yml
version: '3'
services:
  langfuse:
    image: langfuse/langfuse:2
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/langfuse
      - NEXTAUTH_SECRET=mysecret
      - NEXTAUTH_URL=http://localhost:3000
      - SALT=mysalt
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=langfuse
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 8.4 告警规则配置

#### Prometheus AlertManager 配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: default
  group_by: ['alertname', 'skill']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: critical-alerts
    - match:
        severity: warning
      receiver: warning-alerts

receivers:
  - name: default
    webhook_configs:
      - url: 'http://localhost:5001/webhook'

  - name: critical-alerts
    webhook_configs:
      - url: 'http://localhost:5001/webhook'
    pagerduty_configs:
      - service_key: '<pagerduty-service-key>'

  - name: warning-alerts
    webhook_configs:
      - url: 'http://localhost:5001/webhook'
```

#### Prometheus 告警规则

```yaml
# skillopt-alerts.yml
groups:
  - name: skillopt
    rules:
      - alert: SkillOptHighErrorRate
        expr: skillopt_error_rate > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 错误率过高"
          description: "错误率 {{ $value }}%，持续 5 分钟"

      - alert: SkillOptCircuitBreakerOpen
        expr: skillopt_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 熔断器已触发"
```

### 8.5 Grafana 仪表盘配置

#### 数据源配置

```yaml
# grafana-datasources.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
```

#### 推荐面板查询

```promql
# 调用量趋势
rate(skillopt_total_calls{skill="$skill"}[5m])

# 错误率
skillopt_error_rate{skill="$skill"}

# 修复成功率
sum(skillopt_repair_success{skill="$skill"}) / sum(skillopt_total_failures{skill="$skill"}) * 100

# 熔断器状态
skillopt_circuit_breaker_state{skill="$skill"}
```

## 9. 监控与告警

### 9.1 关键告警规则

```yaml
groups:
  - name: skillopt
    rules:
      # 错误率告警
      - alert: SkillOptHighErrorRate
        expr: skillopt_error_rate > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "SkillOpt 错误率过高"
          description: "Skill {{ $labels.skill }} 错误率 {{ $value }}%"

      # 熔断器触发告警
      - alert: SkillOptCircuitBreakerOpen
        expr: skillopt_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "SkillOpt 熔断器已触发"
          description: "Skill {{ $labels.skill }} 熔断器已打开"
```

### 9.2 Grafana 仪表盘

推荐面板：

1. **调用量趋势** - `rate(skillopt_total_calls[5m])`
2. **错误率** - `skillopt_error_rate`
3. **修复成功率** - `skillopt_repair_success / skillopt_total_failures`
4. **熔断器状态** - `skillopt_circuit_breaker_state`

## 9. 故障排查

### 9.1 日志未生成

**检查点**:
1. `SKILLOPT_LOG_FORMAT` 是否设置为 `json`
2. 日志目录权限是否正确
3. `skillopt_log()` 函数是否被调用

**诊断命令**:
```bash
# 检查日志文件
ls -lh ${ALIBABA_CLOUD_LOG_DIR:-.runtime}/cms-skillopt-*.log

# 查看最新日志
tail -f ${ALIBABA_CLOUD_LOG_DIR:-.runtime}/cms-skillopt-$(date +%Y%m%d).log
```

### 9.2 指标未导出

**检查点**:
1. `SKILLOPT_METRICS_DIR` 是否设置
2. 目录是否存在且可写
3. `skillopt_export_metrics()` 是否被调用

**诊断命令**:
```bash
# 检查指标文件
ls -lh ${SKILLOPT_METRICS_DIR}/skillopt_*.prom

# 查看指标内容
cat ${SKILLOPT_METRICS_DIR}/skillopt_cms.prom
```

### 9.3 追踪未上报

**检查点**:
1. `SKILLOPT_LANGFUSE_ENABLED` 是否为 `true`
2. Langfuse 配置是否正确
3. 网络连接是否正常

**诊断命令**:
```bash
# 检查 Langfuse 连接
curl -H "Authorization: Bearer ${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
     ${LANGFUSE_HOST}/api/public/health
```

## 10. 性能影响

### 10.1 日志写入

- **影响**: 极小（追加写入）
- **优化**: 使用缓冲写入（已实现）

### 10.2 指标导出

- **影响**: 小（每次调用后写入）
- **优化**: 异步写入（已实现）

### 10.3 追踪上报

- **影响**: 小（异步 HTTP 请求）
- **优化**: 批量上报（Phase 2 实现）

## 11. 安全考虑

### 11.1 敏感信息

- ✅ 日志中不包含 API Key/Secret
- ✅ 指标中不包含敏感数据
- ✅ 追踪事件中脱敏处理

### 11.2 访问控制

- 日志文件权限: `600`
- 指标文件权限: `644`
- Langfuse API Key: 环境变量存储

## 12. 未来扩展

### 12.1 OpenTelemetry 集成

计划支持 OpenTelemetry 标准，统一 Metrics/Logs/Traces 导出。

### 12.2 分布式追踪

支持跨 Skill 调用链追踪，实现完整的 Agent 工作流可视化。

### 12.3 智能告警

基于机器学习的异常检测，自动识别异常模式。

---

**文档版本**: v1.0  
**最后更新**: 2026-01-17  
**维护者**: Runtime Harness Team
