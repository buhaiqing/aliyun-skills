# Runtime Harness 可观测性 Phase 1：结构化日志 + Prometheus 指标

> **状态**: ✅ 已实现（2026-01-17）  
> **架构文档**: [harness-observability-architecture.md](./harness-observability-architecture.md)

## 1. 概述

Phase 1 实现了 Runtime Harness 的基础可观测性能力，包括：

- **结构化日志**：JSON Lines 格式，便于日志采集系统（Filebeat/Promtail）直接解析
- **Prometheus 指标导出**：text format `.prom` 文件，供 `node_exporter` textfile collector 采集
- **运营报告集成**：`skillopt_report()` 输出可观测性配置信息

## 2. 结构化日志

### 2.1 配置

```bash
# 环境变量
export SKILLOPT_LOG_FORMAT="json"  # text | json（默认 text）
```

### 2.2 JSON Lines 格式

每行一个 JSON 对象：

```json
{"ts":"2026-01-17T10:30:45+0800","skill":"cms","level":"info","msg":"init: enabled=true retries=3 cb_enabled=false","pid":12345}
{"ts":"2026-01-17T10:30:46+0800","skill":"cms","level":"info","msg":"repair[Throttling]: exponential backoff + raise Period","pid":12345}
{"ts":"2026-01-17T10:30:47+0800","skill":"cms","level":"info","msg":"cb: threshold reached (5 >= 5), opening circuit","pid":12345}
```

### 2.3 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts` | string | ISO 8601 时间戳（含时区） |
| `skill` | string | Skill 标识（cms/ecs/rds/...） |
| `level` | string | 日志级别（info/warn/error） |
| `msg` | string | 日志消息（已转义） |
| `pid` | number | 进程 ID |

### 2.4 日志文件路径

```
${ALIBABA_CLOUD_LOG_DIR:-<skill>/.runtime}/<cli>-skillopt-YYYYMMDD.log
```

### 2.5 日志采集配置

**Filebeat**:
```yaml
filebeat.inputs:
  - type: filestream
    id: skillopt
    paths:
      - /path/to/skills/.runtime/logs/alicloud-*-ops/*-skillopt-*.log
    parsers:
      - ndjson:
          target: skillopt
```

**Promtail**:
```yaml
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
      - labels:
          skill:
          level:
```

## 3. Prometheus 指标导出

### 3.1 配置

```bash
# 环境变量
export SKILLOPT_METRICS_DIR="/var/lib/node_exporter/textfile"
```

当 `SKILLOPT_METRICS_DIR` 为空时，不导出指标（默认行为）。

### 3.2 指标文件

每个 Skill 生成独立的 `.prom` 文件：

```
${SKILLOPT_METRICS_DIR}/skillopt_<skill_tag>.prom
```

例如：`skillopt_cms.prom`、`skillopt_ecs.prom`

### 3.3 指标定义

| 指标名称 | 类型 | 标签 | 说明 |
|---------|------|------|------|
| `skillopt_total_calls` | Counter | `skill` | API 总调用次数 |
| `skillopt_total_failures` | Counter | `skill` | API 失败次数 |
| `skillopt_error_rate` | Gauge | `skill` | 错误率（百分比） |
| `skillopt_repair_success` | Counter | `skill` | 自修复成功次数 |
| `skillopt_query_count` | Counter | `skill` | 查询执行次数 |
| `skillopt_circuit_breaker_state` | Gauge | `skill` | 熔断器状态 |
| `skillopt_circuit_breaker_failures` | Gauge | `skill` | 熔断器连续失败次数 |

### 3.4 熔断器状态值

| 值 | 状态 | 说明 |
|----|------|------|
| 0 | closed | 正常（允许请求） |
| 1 | open | 断开（阻止请求） |
| 2 | half-open | 半开（探测中） |

### 3.5 指标文件示例

```prom
# HELP skillopt_total_calls Total API calls made through SkillOpt
# TYPE skillopt_total_calls counter
skillopt_total_calls{skill="cms"} 142

# HELP skillopt_total_failures Total failed API calls
# TYPE skillopt_total_failures counter
skillopt_total_failures{skill="cms"} 7

# HELP skillopt_error_rate Current error rate percentage
# TYPE skillopt_error_rate gauge
skillopt_error_rate{skill="cms"} 4.93

# HELP skillopt_repair_success Total successful self-repairs
# TYPE skillopt_repair_success counter
skillopt_repair_success{skill="cms"} 5

# HELP skillopt_query_count Total queries executed
# TYPE skillopt_query_count counter
skillopt_query_count{skill="cms"} 142

# HELP skillopt_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half-open)
# TYPE skillopt_circuit_breaker_state gauge
skillopt_circuit_breaker_state{skill="cms"} 0

# HELP skillopt_circuit_breaker_failures Consecutive failures in circuit breaker
# TYPE skillopt_circuit_breaker_failures gauge
skillopt_circuit_breaker_failures{skill="cms"} 0
```

### 3.6 Prometheus 采集配置

`node_exporter` 需要启用 `textfile collector`，并指定 `.prom` 文件所在目录：

```bash
node_exporter \
  --web.listen-address=":9100" \
  --collector.textfile \
  --collector.textfile.directory="/var/lib/node_exporter/textfile_collector"
```

Runtime Harness 将指标文件写入该目录，例如：

```text
/var/lib/node_exporter/textfile_collector/skillopt.prom
```

Prometheus 只需要抓取 `node_exporter` 的 `/metrics` 端点：

```yaml
scrape_configs:
  - job_name: node_exporter_textfile
    scrape_interval: 15s
    static_configs:
      - targets:
          - 'localhost:9100'
        labels:
          role: skillopt-host
```

采集链路：

```text
SkillOpt -> *.prom 文件 -> node_exporter textfile collector -> Prometheus scrape -> 时序数据
```

注意：`node_exporter` 不是主动定时扫描历史数据；Prometheus 每次 scrape 时，`node_exporter` 会读取 textfile 目录下当前的 `.prom` 指标快照。

验证方式：

```bash
curl -s http://localhost:9100/metrics | grep skillopt
curl -s http://localhost:9100/metrics | grep node_textfile
```

重点关注：

```prometheus
node_textfile_scrape_error 0
node_textfile_mtime_seconds{file="/var/lib/node_exporter/textfile_collector/skillopt.prom"} <timestamp>
```

### 3.7 自动导出时机

指标在以下时机自动导出：

- 每次 `skillopt_update_runtime()` 调用后（即每次 API 调用后）
- 导出失败不影响主流程（`2>/dev/null || true`）

## 4. 运营报告集成

### 4.1 报告中的可观测性章节

`skillopt_report()` 输出包含可观测性配置：

```markdown
## 可观测性配置

| 参数 | 值 |
|:---|:---|
| 日志格式 | json |
| 指标导出目录 | /var/lib/node_exporter/textfile |
| Skill 标识 | cms |
```

### 4.2 生成报告

```bash
# 输出到 stdout
./scripts/cms-skillopt-wrapper.sh report --skillopt-report

# 保存到文件
source scripts/skillopt-lib.sh
skillopt_report "/path/to/report.md"
```

## 5. 覆盖范围

Phase 1 已覆盖所有 36 个 agent skills：

| Skill | 状态 |
|-------|------|
| alicloud-cms-ops | ✅ |
| alicloud-ecs-ops | ✅ |
| alicloud-rds-ops | ✅ |
| alicloud-redis-ops | ✅ |
| alicloud-slb-ops | ✅ |
| alicloud-ack-ops | ✅ |
| alicloud-oss-ops | ✅ |
| alicloud-vpc-ops | ✅ |
| ...（共 36 个） | ✅ |

## 6. 测试验证

### 6.1 单元测试

```bash
# 向后兼容测试（50 个用例）
cd alicloud-cms-ops && bash test-skillopt-backward-compatibility.sh
```

### 6.2 集成测试

```bash
# 可观测性集成测试（8 个场景）
cd alicloud-cms-ops && ./test-observability-integration.sh
```

测试覆盖：
- ✅ 配置变量默认值
- ✅ Text 格式日志
- ✅ JSON Lines 格式日志
- ✅ Prometheus 指标导出
- ✅ 熔断器状态映射
- ✅ update_runtime 集成
- ✅ 报告集成
- ✅ 指标导出禁用

## 7. 生成脚本

`.scripts/gen-skillopt.sh` 已更新，新生成的 skill 自动包含可观测性功能。

批量更新脚本：`.scripts/batch-add-observability.py`

---

**文档版本**: v1.0  
**最后更新**: 2026-01-17  
**维护者**: Runtime Harness Team
