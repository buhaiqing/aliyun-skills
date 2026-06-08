# Sprint 10: SLS/ARMS 应用层可观测（P2）

> **状态**: [ ] 0/3
> **业务价值**：打通应用层可观测链路（日志 + APM），实现"基础设施指标 -> 应用日志 -> 调用链"的三层关联分析，支持代码级故障定位
> **交付物**：`references/sls-arms-integration.md` + `_shared.py` SLS/ARMS 查询模块 + 2+ 推理规则
> **前置条件**：SLS 访问权限 + ARMS 应用接入（已有应用接入 ARMS）
> **关联验收项**：Stage 2 D4 (数据完整性：CloudMonitor + DAS + SLS + ARMS)

---

## 一、背景与目标

### 1.1 当前盲区

现有 4 个 runbook 覆盖：
- ✅ CloudMonitor (CMS) 指标：CPU、内存、磁盘、连接数
- ✅ DAS 慢查询：RDS 性能洞察
- ✅ ACK 资源：节点、Pod、Limits
- ❌ **应用日志**：ERROR 日志、业务异常堆栈
- ❌ **调用链**：ARMS 慢调用、依赖超时、SQL 耗时

**痛点场景**：
```
用户反馈: "下单接口超时"
↓
Runbook 检查: SLB/RDS/Redis 指标全部正常
↓
盲区: 应用日志里有 NullPointerException
盲区: ARMS 显示调用下游支付服务 30s 超时
↓
结论: "无问题" (实际漏报)
```

### 1.2 能力目标

| 层级 | 数据源 | 可回答的问题 | 实现难度 |
|------|--------|-------------|----------|
| L1 基础设施 | CloudMonitor | 服务器是否健康 | 已具备 |
| L2 中间件 | DAS + Redis 慢查询 | 数据库是否瓶颈 | 已具备 |
| **L3 应用日志** | **SLS** | **业务 ERROR 是什么** | **本次 Sprint** |
| **L4 调用链** | **ARMS** | **哪段代码慢** | **本次 Sprint** |

---

## 二、SLS 日志服务集成

### 2.1 接入前提

```bash
# 1. 确认 SLS 项目存在
aliyun log getProject --project-name k8s-log-c351xxxx

# 2. 确认日志库存在
aliyun log getLogStore --project-name k8s-log-c351xxxx --logstore-name stdout-logstore

# 3. 测试查询权限
aliyun log getLogs --project-name k8s-log-c351xxxx --logstore-name stdout-logstore --from-time 1717200000 --to-time 1717286400 --query "ERROR"
```

### 2.2 查询封装

```python
# _shared.py 新增

def query_sls_logs(
    project: str,
    logstore: str,
    query: str,
    from_time: int,  # Unix timestamp
    to_time: int,
    limit: int = 100
) -> list[dict]:
    """查询 SLS 日志
    
    Args:
        project: SLS 项目名
        logstore: LogStore 名
        query: SLS 查询语句 (SPL 或简单关键词)
        from_time: 开始时间戳
        to_time: 结束时间戳
        limit: 最大返回条数
        
    Returns:
        日志列表，每条包含 time/source/content/fields
    """
    cmd = [
        "aliyun", "log", "getLogs",
        "--project-name", project,
        "--logstore-name", logstore,
        "--from-time", str(from_time),
        "--to-time", str(to_time),
        "--query", query,
        "--limit", str(limit)
    ]
    result = q(cmd, timeout=30)
    return _parse_sls_response(result)


def query_sls_error_logs(
    project: str,
    logstore: str,
    time_minutes: int = 30,
    keywords: list[str] = None
) -> list[dict]:
    """查询 ERROR 级别日志（简化封装）"""
    keywords = keywords or ["ERROR", "Exception", "Fatal"]
    now = int(time.time())
    query = " OR ".join(keywords)
    return query_sls_logs(project, logstore, query, now - time_minutes*60, now)
```

### 2.3 推理规则示例

```yaml
# inference-rules.md 新增 SLS 规则

rule: APP-ERROR-01
name: 应用异常日志突增
trigger: |
  任意服务在 10 分钟内 ERROR 日志 > 50 条
  且比前一小时均值增长 > 300%
source: SLS
query: |
  service: "order-service" AND (ERROR OR Exception)
  | select count(*) as error_count
action: |
  1. 取最近 5 条 ERROR 日志展示堆栈
  2. 关联 ARMS 调用链（如有）
  3. 建议查看应用监控大屏

rule: APP-SLOW-02
name: 慢查询日志定位
trigger: |
  SLS 中出现 "Slow query" 或执行时间 > 5s 的 SQL
source: SLS + RDS DAS
query: |
  "Slow query" OR "execution time" > 5000
action: |
  1. 提取 SQL 指纹
  2. 关联 DAS 慢查询分析
  3. 建议添加索引或优化 SQL
```

---

## 三、ARMS APM 集成

### 3.1 接入前提

```bash
# 1. 确认 ARMS 应用存在
aliyun arms GetArmsConsolePageUrl --RegionId cn-hangzhou

# 2. 获取应用列表（需确认 API 权限）
aliyun arms SearchTraces --RegionId cn-hangzhou --StartTime 1717200000 --EndTime 1717286400
```

### 3.2 查询封装

```python
# _shared.py 新增

def query_arms_slow_calls(
    region: str,
    app_name: str,
    start_time: int,
    end_time: int,
    min_duration_ms: int = 3000,
    limit: int = 20
) -> list[dict]:
    """查询 ARMS 慢调用
    
    Args:
        region: 地域 ID
        app_name: ARMS 应用名
        start_time: 开始时间戳
        end_time: 结束时间戳
        min_duration_ms: 最小耗时阈值
        limit: 最大返回条数
        
    Returns:
        慢调用列表，包含 trace_id/duration/service/operation
    """
    cmd = [
        "aliyun", "arms", "SearchTraces",
        "--RegionId", region,
        "--StartTime", str(start_time),
        "--EndTime", str(end_time),
        "--Service", app_name,
        "--MinDuration", str(min_duration_ms),
        "--PageSize", str(limit)
    ]
    result = q(cmd, timeout=30)
    return _parse_arms_traces(result)


def query_arms_trace_detail(
    region: str,
    trace_id: str
) -> dict | None:
    """获取单个调用链详情"""
    cmd = [
        "aliyun", "arms", "GetTrace",
        "--RegionId", region,
        "--TraceID", trace_id
    ]
    return q(cmd, timeout=30)
```

### 3.3 推理规则示例

```yaml
rule: TRACE-SLOW-01
name: 下游依赖超时
trigger: |
  ARMS 显示调用下游服务耗时 > 5s
  且错误率 > 10%
source: ARMS
query: |
  service: "order-service" AND callType: "HTTP" AND duration > 5000
action: |
  1. 展示调用链瀑布图
  2. 定位超时发生在哪一跳
  3. 建议检查下游服务健康状态

rule: TRACE-DB-01
name: 数据库调用瓶颈
trigger: |
  ARMS 显示 SQL 执行耗时占比 > 80%
source: ARMS + RDS DAS
query: |
  db.type: "mysql" AND db.statement: "*"
action: |
  1. 提取慢 SQL
  2. 关联 DAS 分析执行计划
  3. 建议优化或扩容
```

---

## 四、任务清单

- [ ] **10.1** 调研并确认 SLS/ARMS API 可用性
  - [ ] 确认 `aliyun log` 子命令可用
  - [ ] 确认 `aliyun arms` 子命令可用（或需 SDK）
  - [ ] 测试查询权限和返回格式
- [ ] **10.2** 在 `_shared.py` 实现 `query_sls_logs()` 和 `query_sls_error_logs()`
  - [ ] 实现基础查询封装
  - [ ] 实现 ERROR 日志简化封装
  - [ ] 添加响应解析和错误处理
- [ ] **10.3** 在 `_shared.py` 实现 `query_arms_slow_calls()` 和 `query_arms_trace_detail()`
  - [ ] 实现慢调用查询
  - [ ] 实现调用链详情查询
  - [ ] 添加响应解析
- [ ] **10.4** 在 `inference-rules.md` 新增 2+ SLS/ARMS 推理规则
  - [ ] APP-ERROR-01: 应用异常日志突增
  - [ ] APP-SLOW-02: 慢查询日志定位
  - [ ] TRACE-SLOW-01: 下游依赖超时
  - [ ] TRACE-DB-01: 数据库调用瓶颈
- [ ] **10.5** 在 `emergency-troubleshoot.py` 中集成 SLS/ARMS 查询（作为 Layer 3/4）
  - [ ] 当 L1/L2 无异常时自动查询 SLS
  - [ ] 发现 ERROR 日志时关联 ARMS 调用链
- [ ] **10.6** 编写 `references/sls-arms-integration.md` 完整规范
  - [ ] API 使用说明
  - [ ] 权限配置指南
  - [ ] 典型查询示例
- [ ] **10.7** TODO.md / stage-status.json 同步

---

## 五、质量门

| 编号 | 检查项 | 验证命令 | 阈值 |
|------|--------|----------|------|
| Q10.1 | SLS API 可用 | `aliyun log getProject --project-name xxx` | 返回项目信息 |
| Q10.2 | `query_sls_logs()` 实现 | `grep -c 'def query_sls_logs' runbooks/scripts/_shared.py` | ≥ 1 |
| Q10.3 | ARMS API 可用 | `aliyun arms SearchTraces --help` | 返回帮助 |
| Q10.4 | `query_arms_slow_calls()` 实现 | `grep -c 'def query_arms_slow_calls' runbooks/scripts/_shared.py` | ≥ 1 |
| Q10.5 | SLS 推理规则 ≥1 | `grep -c 'APP-ERROR' references/inference-rules.md` | ≥ 1 |
| Q10.6 | ARMS 推理规则 ≥1 | `grep -c 'TRACE-' references/inference-rules.md` | ≥ 2 |
| Q10.7 | 集成到 emergency-troubleshoot | `grep -c 'query_sls_error_logs' runbooks/scripts/emergency-troubleshoot.py` | ≥ 1 |
| Q10.8 | `sls-arms-integration.md` 存在 | `test -s references/sls-arms-integration.md` | 通过 |
| Q10.9 | Ruff Lint | `ruff check runbooks/scripts/_shared.py` | 0 错误 |
| Q10.10 | TODO.md 同步 | `grep -c 'Sprint 10.*10/' TODO.md` | ≥ 1 |

---

## 六、与现有文档的关系

| 现有文件 | 关系 |
|----------|------|
| `references/inference-rules.md` | 新增 SLS/ARMS 推理规则 |
| `references/architecture-roadmap.md` | L3/L4 能力补齐 |
| `references/self-assessment-framework.md` | Stage 2 D4 验收项 |
| `runbooks/07-bottleneck-localization.md` | 新增 SLS/ARMS 排查步骤 |
| Sprint 9 (Incident 落地) | SLS/ARMS 发现的异常生成 Incident |
| Sprint 12 (双引擎) | 双引擎决策时可查询 SLS/ARMS 数据 |

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| SLS API 权限不足 | 无法查询日志 | 提前测试 `aliyun log` 命令，如权限不足改为文档说明 |
| ARMS API 返回格式复杂 | 解析困难 | 只提取关键字段（trace_id/duration/operation），其余透传 |
| 日志量过大 | 查询超时 | 限制 `limit=100`，增加 `time_range` 参数 |
| 应用未接入 ARMS | 无法查询调用链 | 检测接入状态，未接入时跳过并提示 |
| 依赖膨胀 | 违背零依赖 | 继续使用 `aliyun` CLI，不引入 SDK |

---

## 八、Sprint 完成判据

- 所有 7 个任务项 `[x]`
- 所有 10 个 Q 检查项 PASS
- SLS/ARMS 查询功能在 `emergency-troubleshoot.py` 中可用
- 至少 2 条新的推理规则写入 `inference-rules.md`
- TODO.md / stage-status.json 同步更新
- Post-Update Self-Review R1 + R2 全部 PASS

---

## 九、决策建议

**问题**：是否立即启动 Sprint 10？

**选项**：
- **A. 立即启动** — 需先确认 SLS/ARMS API 权限可用
- **B. 推迟到 Stage 2 准入后** — 当前 Stage 1 刚闭环，先跑通 Stage 2 基础验收
- **C. 只做调研** — 验证 API 可用性，不实际集成到 runbook

**建议**：**选项 C** — 先完成 Q10.1/Q10.3 验证 API 权限
- 如 API 可用：继续实施 10.2-10.7
- 如 API 不可用：改为纯文档 Sprint，输出 `sls-arms-setup-guide.md` 说明如何配置权限

---

## 十、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0-draft | 2026-06-08 | 初始版本，待 API 验证后实施 |
