# Integration — 下游 Skill 集成指南

> 定义本 Skill 如何与下游产品 Skill 进行集成、委托和结果回传。

---

## 1. 集成架构

```
alicloud-auto-scaling-orch (编排层)
         │
         │  委托调用 (通过 Agent 路由)
         ├────────────────┬───────────────┬────────────────┐
         ▼                ▼               ▼                ▼
  ess-ops           cms-ops          slb-ops/alb-ops   ecs-ops
  ─────────         ─────────        ─────────────     ─────────
  伸缩组管理         指标采集          负载均衡注册      实例操作
  伸缩规则          告警创建          健康检查          云助手执行
  定时任务          事件规则                          快照/镜像
  生命周期
```

---

## 2. 委托协议

### 2.1 通用参数约定

所有委托调用统一使用以下参数：

| 参数 | 来源 | 传递方式 |
|------|------|---------|
| `ALIBABA_CLOUD_REGION_ID` | `{{env.*}}` | 环境变量 |
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | `{{env.*}}` | 环境变量 |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | `{{env.*}}` | 环境变量 |
| `ClientToken` | 自动生成 UUID v4 | 每个写操作参数 |

### 2.2 委托至 ess-ops

| 操作 | ess-ops 接口 | 参数映射 | 前置条件 |
|------|-------------|---------|---------|
| 创建伸缩规则 | `CreateScalingRule` | `ScalingGroupId`, `ScalingRuleType`, `MetricName`, `TargetValue` | 伸缩组已存在 |
| 创建定时任务 | `CreateScheduledTask` | `ScalingGroupId`, `ScheduledAction`, `RecurrenceType`, `LaunchTime` | 伸缩组已激活 |
| 修改伸缩组 | `ModifyScalingGroup` | `ScalingGroupId`, `MaxSize`, `MinSize`, `DesiredCapacity` | 伸缩组存在 |
| 创建告警 | `CreateAlarm` | `ScalingGroupId`, `MetricName`, `Threshold`, `ComparisonOperator` | 伸缩组存在 |
| 查伸缩活动 | `DescribeScalingActivities` | `ScalingGroupId`, `PageNumber`, `PageSize` | — |

### 2.3 委托至 cms-ops

| 操作 | cms-ops 接口 | 参数映射 | 备注 |
|------|-------------|---------|------|
| 查指标 | `DescribeMetricList` / `DescribeMetricLast` | `Namespace`, `MetricName`, `Period`, `StartTime`, `EndTime` | 只读 |
| 创建告警 | `PutResourceMetricRule` | `RuleName`, `Namespace`, `MetricName`, `Threshold`, `ComparisonOperator` | 写操作 |
| 查告警 | `DescribeMetricRuleList` | `RuleName` | 只读 |

### 2.4 委托至 slb-ops / alb-ops

| 操作 | 接口 | 适用场景 | 备注 |
|------|------|---------|------|
| 注册后端 | `AddBackendServers` (SLB) / 服务器组操作 (ALB) | 扩容后新实例加入 | 仅在 ESS 自动注册不可用时 |
| 注销后端 | `RemoveBackendServers` (SLB) | 缩容实例退服 | — |
| 健康检查 | `DescribeHealthStatus` (SLB) | 验证新实例正常运行 | 只读，作为验证环节 |

> **注意**：ESS 创建伸缩组时已关联 SLB/ALB，新实例会自动注册。slb-ops/alb-ops 操作仅作为**验证手段**和**异常补偿**使用。

---

## 3. 输出格式约定

### 3.1 编排计划 (orchestration_plan.json)

```json
{
  "plan_id": "plan-20260607-001",
  "scenario": "metric",
  "scaling_group_id": "asg-xxx",
  "created_at": "2026-06-07T12:30:00Z",
  "steps": [
    {
      "step": 1,
      "action": "create_scaling_rule",
      "skill": "ess-ops",
      "params": { "ScalingRuleType": "TargetTrackingScalingRule", "MetricName": "CpuUtilization", "TargetValue": 60 },
      "depends_on": []
    },
    {
      "step": 2,
      "action": "verify_scaling_rule",
      "skill": "ess-ops",
      "params": {},
      "depends_on": [1]
    }
  ],
  "original_capacity": 3,
  "target_capacity": 4,
  "safety_checks": {
    "within_quota": true,
    "balance_sufficient": true,
    "no_cooling_conflict": true
  },
  "rollback_plan": {
    "trigger": "verification_failed",
    "steps": [
      { "action": "execute_scaling_rule", "skill": "ess-ops", "params": { "adjustment": -1 } }
    ]
  }
}
```

### 3.2 执行摘要 (execution_summary.json)

```json
{
  "plan_id": "plan-20260607-001",
  "status": "success",
  "started_at": "2026-06-07T12:30:05Z",
  "completed_at": "2026-06-07T12:31:20Z",
  "duration_seconds": 75,
  "steps": [
    { "step": 1, "action": "create_scaling_rule", "result": "success", "output": { "scaling_rule_id": "sr-xxx" } },
    { "step": 2, "action": "verify_scaling_rule", "result": "success", "output": { "verified": true } }
  ],
  "verification": {
    "status": "passed",
    "checks": [
      { "name": "activity_completed", "passed": true },
      { "name": "instance_count", "passed": true, "actual": 4, "expected": 4 },
      { "name": "instance_health", "passed": true },
      { "name": "cpu_regression", "passed": true, "current": 45 }
    ]
  },
  "cost_impact": {
    "estimated_daily_increase": "¥13.20",
    "hourly_rate_before": "¥1.65",
    "hourly_rate_after": "¥2.20"
  }
}
```

---

## 4. 跨 Skill 调试指南

### 4.1 委托链路追踪

每次委托调用必须记录：

```
[auto-scaling-orch] → [ess-ops] CreateScalingRule
  TraceID: trace-20260607-001
  Request: {ScalingGroupId: "asg-xxx", ScalingRuleType: "TargetTrackingScalingRule", ...}
  Response: {ScalingRuleId: "sr-yyy"}
  Duration: 1.2s
  Status: success
```

### 4.2 常见委托失败原因

| 错误 | 可能原因 | 排查方法 |
|------|---------|---------|
| `ScalingGroupId.NotFound` | 伸缩组已删除或 ID 错误 | 调用 ess-ops DescribeScalingGroups 确认 |
| `ScalingRule.QuotaExceeded` | 伸缩规则数已达上限 | 调用 ess-ops DescribeLimitation |
| `Throttling` | API 限流 | 等待 30s 后重试 |
| `InvalidParameter` | 参数格式错误 | 检查参数是否符合 OpenAPI 规范 |
| `Forbidden.RAM` | RAM 权限不足 | 检查当前 AK 是否有 ESS/CMS 权限 |