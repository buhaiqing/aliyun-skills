# Runtime Harness 可观测性 Phase 3：智能告警与可视化

> **状态**: 📋 规划中  
> **架构文档**: [harness-observability-architecture.md](./harness-observability-architecture.md)

## 1. 概述

Phase 3 将实现智能告警和可视化能力，包括：

- **Prometheus 告警规则**：基于 Runtime Harness 指标的主动告警
- **Grafana 仪表盘**：多维度可视化 Runtime Harness 运行状态
- **运营报告增强**：趋势分析、历史对比、智能建议

## 2. Prometheus 告警规则

### 2.1 告警规则配置

```yaml
# skillopt-alerts.yaml
groups:
  - name: skillopt
    interval: 30s
    rules:
      # 错误率告警
      - alert: SkillOptHighErrorRate
        expr: skillopt_error_rate > 20
        for: 5m
        labels:
          severity: warning
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 错误率过高"
          description: "Skill {{ $labels.skill }} 错误率 {{ $value }}%，持续 5 分钟"
          runbook_url: "https://wiki.example.com/skillopt-error-rate"

      # 严重错误率告警
      - alert: SkillOptCriticalErrorRate
        expr: skillopt_error_rate > 50
        for: 2m
        labels:
          severity: critical
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 错误率严重"
          description: "Skill {{ $labels.skill }} 错误率 {{ $value }}%，持续 2 分钟"
          runbook_url: "https://wiki.example.com/skillopt-critical-error"

      # 熔断器触发告警
      - alert: SkillOptCircuitBreakerOpen
        expr: skillopt_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 熔断器已触发"
          description: "Skill {{ $labels.skill }} 熔断器已打开，连续失败 {{ $labels.failures }} 次"
          runbook_url: "https://wiki.example.com/skillopt-circuit-breaker"

      # 熔断器半开告警
      - alert: SkillOptCircuitBreakerHalfOpen
        expr: skillopt_circuit_breaker_state == 2
        for: 1m
        labels:
          severity: warning
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 熔断器半开"
          description: "Skill {{ $labels.skill }} 熔断器处于半开状态，正在探测恢复"

      # 自修复失败率告警
      - alert: SkillOptRepairFailureHigh
        expr: |
          (skillopt_total_failures - skillopt_repair_success) / skillopt_total_failures > 0.5
        for: 10m
        labels:
          severity: warning
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 自修复失败率过高"
          description: "Skill {{ $labels.skill }} 自修复失败率 {{ $value | humanizePercentage }}，持续 10 分钟"

      # 调用量异常告警
      - alert: SkillOptCallVolumeSpike
        expr: |
          rate(skillopt_total_calls[5m]) > 2 * rate(skillopt_total_calls[1h])
        for: 5m
        labels:
          severity: warning
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 调用量异常"
          description: "Skill {{ $labels.skill }} 调用量激增，当前速率是 1 小时平均的 {{ $value }} 倍"

      # 无调用告警（可能服务中断）
      - alert: SkillOptNoCalls
        expr: |
          rate(skillopt_total_calls[15m]) == 0
        for: 15m
        labels:
          severity: warning
          component: skillopt
        annotations:
          summary: "SkillOpt {{ $labels.skill }} 无调用"
          description: "Skill {{ $labels.skill }} 15 分钟内无调用，可能服务中断"
```

### 2.2 告警级别定义

| 级别 | 颜色 | 响应时间 | 通知方式 |
|------|------|---------|---------|
| `critical` | 🔴 红色 | 5 分钟内 | 电话 + 短信 + 钉钉 |
| `warning` | 🟡 黄色 | 30 分钟内 | 钉钉 + 邮件 |
| `info` | 🔵 蓝色 | 工作时间 | 邮件 |

### 2.3 告警路由配置

```yaml
# alertmanager.yaml
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
      continue: true
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
        send_resolved: true
    pagerduty_configs:
      - service_key: '<pagerduty-service-key>'
  
  - name: warning-alerts
    webhook_configs:
      - url: 'http://localhost:5001/webhook'
        send_resolved: true
```

## 3. Grafana 仪表盘

### 3.1 仪表盘概览

创建 4 个维度的仪表盘：

1. **Runtime Harness Overview** - 全局概览
2. **Runtime Harness Error Analysis** - 错误分析
3. **Runtime Harness Repair Analysis** - 修复分析
4. **Runtime Harness Circuit Breaker** - 熔断器状态

### 3.2 Runtime Harness Overview 仪表盘

**面板布局**:

```
┌─────────────────────────────────────────────────────────────┐
│                    SkillOpt Overview                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Total Calls  │  │ Error Rate   │  │ Repair Rate  │      │
│  │   1,234      │  │    4.5%      │  │    85.2%     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Call Volume Trend (by Skill)                │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  📈 Line Chart                              │   │   │
│  │  │  - cms: ████████████████                    │   │   │
│  │  │  - ecs: ████████████                        │   │   │
│  │  │  - rds: ████████                            │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Error Rate Trend (by Skill)                 │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  📈 Line Chart                              │   │   │
│  │  │  - cms: ▁▁▂▁▁▃▂▁                          │   │   │
│  │  │  - ecs: ▁▁▁▁▂▁▁▁                          │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**面板配置**:

```json
{
  "dashboard": {
    "title": "SkillOpt Overview",
    "panels": [
      {
        "title": "Total Calls",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(skillopt_total_calls)",
            "legendFormat": "Total"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {"mode": "thresholds"},
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 1000},
                {"color": "red", "value": 5000}
              ]
            }
          }
        }
      },
      {
        "title": "Error Rate",
        "type": "gauge",
        "targets": [
          {
            "expr": "avg(skillopt_error_rate)",
            "legendFormat": "Avg Error Rate"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 5},
                {"color": "red", "value": 20}
              ]
            }
          }
        }
      },
      {
        "title": "Repair Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(skillopt_repair_success) / sum(skillopt_total_failures) * 100",
            "legendFormat": "Repair Rate"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 70},
                {"color": "green", "value": 90}
              ]
            }
          }
        }
      },
      {
        "title": "Call Volume Trend",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(skillopt_total_calls[5m])",
            "legendFormat": "{{skill}}"
          }
        ]
      },
      {
        "title": "Error Rate Trend",
        "type": "timeseries",
        "targets": [
          {
            "expr": "skillopt_error_rate",
            "legendFormat": "{{skill}}"
          }
        ]
      }
    ]
  }
}
```

### 3.3 Runtime Harness Error Analysis 仪表盘

**面板布局**:

```
┌─────────────────────────────────────────────────────────────┐
│              SkillOpt Error Analysis                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Error Distribution (by Error Code)          │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  📊 Pie Chart                               │   │   │
│  │  │  - Throttling.User: 45%                     │   │   │
│  │  │  - InvalidParameter: 30%                    │   │   │
│  │  │  - ResourceNotFound: 15%                    │   │   │
│  │  │  - Other: 10%                               │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Top 10 Errors (Table)                       │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  Error Code          │ Count │ Trend        │   │   │
│  │  │  Throttling.User     │ 123   │ ↑ 15%        │   │   │
│  │  │  InvalidParameter    │ 89    │ ↓ 5%         │   │   │
│  │  │  ResourceNotFound    │ 45    │ → 0%         │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**关键查询**:

```promql
# 错误分布（按错误码）
sum by (error_code) (skillopt_total_failures)

# Top 10 错误
topk(10, sum by (error_code) (skillopt_total_failures))

# 错误趋势
rate(skillopt_total_failures[1h])
```

### 3.4 Runtime Harness Repair Analysis 仪表盘

**面板布局**:

```
┌─────────────────────────────────────────────────────────────┐
│              SkillOpt Repair Analysis                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Repair Rate  │  │ Avg Retries  │  │ Success Time │      │
│  │    85.2%     │  │    2.3       │  │    3.5s      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      Repair Success Rate by Error Code              │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  📊 Bar Chart                               │   │   │
│  │  │  - Throttling.User: 95% ██████████████████  │   │   │
│  │  │  - InvalidParameter: 80% ███████████████     │   │   │
│  │  │  - ResourceNotFound: 70% █████████████       │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**关键查询**:

```promql
# 修复成功率
sum(skillopt_repair_success) / sum(skillopt_total_failures) * 100

# 按错误码的修复成功率
sum by (error_code) (skillopt_repair_success) / 
sum by (error_code) (skillopt_total_failures) * 100

# 平均重试次数
avg(skillopt_retry_count)
```

### 3.5 Runtime Harness Circuit Breaker 仪表盘

**面板布局**:

```
┌─────────────────────────────────────────────────────────────┐
│            SkillOpt Circuit Breaker Status                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Circuit Breaker State (by Skill)            │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  🟢 cms: Closed                             │   │   │
│  │  │  🟢 ecs: Closed                             │   │   │
│  │  │  🔴 rds: Open (45s remaining)               │   │   │
│  │  │  🟡 redis: Half-Open                        │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         State Transition Timeline                   │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │  📈 State Timeline                          │   │   │
│  │  │  rds: ▁▁▁▂▃▃▃▂▁▁▁▁▁▁▁▁▁                  │   │   │
│  │  │       Closed → Open → Half-Open → Closed    │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**关键查询**:

```promql
# 熔断器状态
skillopt_circuit_breaker_state

# 状态转换历史
changes(skillopt_circuit_breaker_state[1h])

# 连续失败次数
skillopt_circuit_breaker_failures
```

## 4. 运营报告增强

### 4.1 趋势分析

在运营报告中添加趋势分析章节：

```markdown
## 趋势分析

### 错误率趋势（过去 7 天）

| 日期 | 错误率 | 趋势 | 说明 |
|------|--------|------|------|
| 2026-01-17 | 4.5% | ↓ | 较昨日下降 1.2% |
| 2026-01-16 | 5.7% | ↑ | 较前日上升 0.8% |
| 2026-01-15 | 4.9% | → | 基本持平 |

### 修复成功率趋势

| 日期 | 修复成功率 | 趋势 | 说明 |
|------|-----------|------|------|
| 2026-01-17 | 85.2% | ↑ | 较昨日提升 3.5% |
| 2026-01-16 | 81.7% | ↓ | 较前日下降 2.1% |
| 2026-01-15 | 83.8% | → | 基本持平 |

### 熔断器事件

| 时间 | Skill | 事件 | 持续时间 | 原因 |
|------|-------|------|---------|------|
| 2026-01-16 14:30 | rds | Open → Closed | 45s | Throttling 恢复 |
| 2026-01-15 09:15 | redis | Open → Closed | 30s | 网络恢复 |
```

### 4.2 历史对比

添加与历史数据的对比：

```markdown
## 历史对比

### 与上周同期对比

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
| 总调用量 | 12,345 | 11,234 | ↑ 9.9% |
| 错误率 | 4.5% | 5.2% | ↓ 0.7% |
| 修复成功率 | 85.2% | 82.1% | ↑ 3.1% |

### 与上月同期对比

| 指标 | 本月 | 上月 | 变化 |
|------|------|------|------|
| 总调用量 | 45,678 | 42,345 | ↑ 7.9% |
| 错误率 | 4.8% | 6.1% | ↓ 1.3% |
| 修复成功率 | 84.5% | 80.2% | ↑ 4.3% |
```

### 4.3 智能建议

基于数据分析生成智能建议：

```markdown
## 智能建议

### 高优先级

1. **RDS 熔断器频繁触发**
   - 问题：过去 7 天触发 3 次
   - 建议：检查 RDS 连接池配置，考虑增加连接数限制
   - 预期效果：减少 60% 的熔断器触发

2. **Throttling 错误上升**
   - 问题：Throttling.User 错误较上周增加 15%
   - 建议：启用请求限流，增加请求间隔
   - 预期效果：减少 40% 的 Throttling 错误

### 中优先级

3. **InvalidParameter 修复率偏低**
   - 问题：InvalidParameter 修复成功率仅 70%
   - 建议：优化参数验证逻辑，增加参数预检查
   - 预期效果：提升修复成功率至 85%

### 低优先级

4. **Redis 调用量下降**
   - 问题：Redis 调用量较上周下降 20%
   - 建议：检查是否有业务变更或配置问题
   - 预期效果：恢复正常的调用量
```

## 5. 实施计划

### Phase 3.1：告警规则

- [ ] 编写 Prometheus 告警规则 YAML
- [ ] 配置 AlertManager 路由
- [ ] 测试告警触发和通知
- [ ] 编写告警响应手册

### Phase 3.2：Grafana 仪表盘

- [ ] 创建 4 个核心仪表盘
- [ ] 配置数据源和变量
- [ ] 设置仪表盘权限
- [ ] 编写仪表盘使用文档

### Phase 3.3：运营报告增强

- [ ] 实现趋势分析功能
- [ ] 实现历史对比功能
- [ ] 实现智能建议生成
- [ ] 集成到 `skillopt_report()`

### Phase 3.4：自动化运维

- [ ] 实现告警自动恢复
- [ ] 实现仪表盘自动刷新
- [ ] 实现报告自动生成和推送

## 6. 依赖关系

### 6.1 基础设施依赖

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Prometheus | >= 2.30 | 指标存储和告警 |
| AlertManager | >= 0.23 | 告警路由和通知 |
| Grafana | >= 8.0 | 可视化仪表盘 |
| node_exporter | >= 1.3 | textfile collector |

### 6.2 配置依赖

```bash
# Prometheus 配置
prometheus:
  scrape_configs:
    - job_name: node_exporter
      static_configs:
        - targets: ['localhost:9100']
      file_sd_configs:
        - files:
          - '/var/lib/node_exporter/textfile/*.prom'

# AlertManager 配置
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

# Grafana 配置
datasources:
  - name: Prometheus
    type: prometheus
    url: http://localhost:9090
    access: proxy
```

## 7. 性能考虑

### 7.1 告警规则性能

- 告警评估间隔：30 秒
- 告警保持时间：根据严重程度配置
- 告警分组：按 `alertname` 和 `skill` 分组

### 7.2 仪表盘性能

- 数据点限制：每个面板最多 1000 个数据点
- 时间范围：默认 1 小时，最大 30 天
- 刷新间隔：根据面板重要性配置（5s - 5m）

### 7.3 报告生成性能

- 趋势分析：查询过去 7 天数据
- 历史对比：查询过去 30 天数据
- 智能建议：基于规则引擎生成

## 8. 安全考虑

### 8.1 告警通知安全

- 使用 HTTPS 发送告警通知
- 告警内容不包含敏感信息
- 告警接收人权限控制

### 8.2 仪表盘安全

- 仪表盘访问权限控制
- 数据源认证
- 仪表盘版本管理

### 8.3 报告安全

- 报告文件权限：600
- 报告传输加密
- 报告归档策略

## 9. 测试验证

### 9.1 告警规则测试

```bash
# 使用 promtool 验证规则
promtool check rules skillopt-alerts.yaml

# 使用 amtool 验证 AlertManager 配置
amtool check-config alertmanager.yaml
```

### 9.2 仪表盘测试

```bash
# 使用 Grafana API 验证仪表盘
curl -H "Authorization: Bearer $GRAFANA_TOKEN" \
     http://localhost:3000/api/dashboards/uid/skillopt-overview
```

### 9.3 报告测试

```bash
# 生成测试报告
./scripts/cms-skillopt-wrapper.sh report --skillopt-report

# 验证报告内容
grep "趋势分析" report.md
grep "历史对比" report.md
grep "智能建议" report.md
```

## 10. 运维手册

### 10.1 告警响应

| 告警 | 响应步骤 | 预期恢复时间 |
|------|---------|-------------|
| `SkillOptHighErrorRate` | 1. 检查错误日志<br>2. 分析错误类型<br>3. 调整修复策略 | 30 分钟 |
| `SkillOptCircuitBreakerOpen` | 1. 检查 API 状态<br>2. 验证网络连接<br>3. 手动重置熔断器 | 15 分钟 |
| `SkillOptRepairFailureHigh` | 1. 分析失败原因<br>2. 优化修复逻辑<br>3. 更新 SkillOpt 配置 | 1 小时 |

### 10.2 仪表盘维护

- 每周检查仪表盘性能
- 每月更新仪表盘布局
- 每季度归档旧仪表盘

### 10.3 报告维护

- 每日自动生成报告
- 每周发送周报
- 每月生成月报

---

**文档版本**: v0.1 (Draft)  
**最后更新**: 2026-01-17  
**维护者**: Runtime Harness Team
