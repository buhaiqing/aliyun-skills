# Troubleshooting — 扩缩容编排故障排查

> 覆盖 12+ 常见错误场景，按诊断流程组织。

---

## 1. 快速诊断流程

```
扩缩容执行失败
    │
    ├── 是 API 错误?
    │      ├── 429 Throttling → 等待 + 重试
    │      ├── 4xx InvalidParameter → 检查参数
    │      ├── 403 Forbidden → 检查 RAM 权限
    │      └── 5xx InternalError → 重试 3 次
    │
    ├── 是决策错误?
    │      ├── 容量计算超出边界 → 截断 + 警告
    │      ├── 冷却未到 → 排队等待
    │      └── 熔断触发 → 等待恢复 + 分析
    │
    ├── 是执行超时?
    │      ├── 伸缩活动未完成 → 延长等待
    │      └── 实例创建慢 → 检查实例规格可用性
    │
    └── 是验证失败?
           ├── 实例不健康 → 自动替换
           ├── 容量不对 → 回滚或补执行
           └── 指标未回归 → 继续扩容/调整
```

---

## 2. 错误码对照表

### 2.1 API 错误

| 错误码 | HTTP | 原因 | 自动恢复 | 手动操作 |
|--------|:----:|------|:-------:|---------|
| `Throttling` | 429 | API 调用频率超限 | 等待 30s 重试，最多 3 次 | 评估是否需要限流优化 |
| `InvalidParameter` | 400 | 请求参数格式错误 | 否 | 对照 OpenAPI 文档修正 |
| `Forbidden.RAM` | 403 | AK 权限不足 | 否 | 检查 RAM 策略是否包含 ess/cms 权限 |
| `InternalError` | 500 | 服务端内部错误 | 重试 3 次 (2s/4s/8s) | 超过 3 次后 HALT，提供 RequestId |
| `ServiceUnavailable` | 503 | 服务暂时不可用 | 等待 60s 重试 1 次 | HALT + 通知 |
| `QuotaExceeded.ScalingGroup` | 400 | 伸缩组配额上限 | 否 | 申请提升配额 |
| `QuotaExceeded.ScalingRule` | 400 | 伸缩规则数达上限 | 否 | 清理无用规则或申请配额 |
| `InvalidScalingGroupId.NotFound` | 404 | 伸缩组不存在 | 否 | 用 ess-ops DescribeScalingGroups 确认 |

### 2.2 编排逻辑错误

| 错误码 | 原因 | 触发场景 | 自动恢复 |
|--------|------|---------|:-------:|
| `DECISION_CAPACITY_OUT_OF_BOUNDS` | 计算容量超出 MinSize/MaxSize | S1, S4, S5 | 截断到边界 |
| `DECISION_COOLDOWN_ACTIVE` | 冷却时间内重复触发 | S1 | 排队等待剩余冷却时间 |
| `DECISION_FUSE_TRIGGERED` | 熔断条件触发 | 所有场景 | 熔断 1h + 报告 |
| `DECISION_DIRECTION_REVERSAL` | 1h 内方向反转 > 3 次 | S1 | 熔断 + 分析 |
| `EXECUTION_BALANCE_INSUFFICIENT` | 账户余额不足 | S5 (大促) | HALT |
| `EXECUTION_ACTIVITY_IN_PROGRESS` | 当前有未完成伸缩活动 | 所有场景 | 排队等待 |
| `VERIFICATION_INSTANCE_UNHEALTHY` | 新实例健康检查失败 | 扩容验证 | 自动替换 (ess-ops) |
| `VERIFICATION_METRIC_NOT_RECOVERED` | 扩缩后指标未回归目标 | 验证环节 | 继续扩容或回滚 |
| `VERIFICATION_QUOTA_WARNING` | 地域配额即将用尽 (>80%) | 所有场景 | 警告 + 建议申请配额 |

---

## 3. 场景级故障恢复

### S1 CPU 指标驱动

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 告警未创建 | 无告警规则 | 委托 cms-ops 检查已有规则，重新创建 |
| 规则未关联告警 | 有告警但不触发伸缩 | 检查 ess-ops AlarmTaskId 是否正确关联 |
| 扩容后 CPU 不降 | 扩容但负载继续上升 | 继续扩容直到熔断条件，同时通知用户 |
| 缩容后 CPU 飙升 | 缩完立刻反弹 | 取消缩容 → 紧急扩容回缩容前容量 + 告警 |

### S2 定时任务

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 定时任务未触发 | 到了时间没扩/缩 | 检查 RecurrenceType + LaunchTime 是否正确 |
| 时区偏差 | 提前/推迟 1h | 确认 TimeZone 参数 (默认 Asia/Shanghai) |
| 内容冲突 | 扩容/缩容定时同时触发 | 检查 ScheduledAction 内容是否互斥 |

### S3 预测性扩缩

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 预测不准确 | 实际负载与预测偏差大 | 检查历史数据是否完整 (最少 14 天) |
| 预测模式错误 | 选择了 PredictOnly | 改为 PredictAndScale |
| Buffer 不合理 | 资源浪费或不足 | 调整 PredictiveValueBuffer (默认 20) |

### S4 复合指标

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 仅单指标触发 | 复合条件未生效 | 检查 CMS 告警是否配置了 AND 条件 |
| Step 跳级 | 直接跳到高档扩容 | 检查 StepAdjustments 区间是否有重叠 |
| 告警风暴 | 双指标同时告警导致重复触发 | 增加冷却时间或合并为一个告警 |

### S5 大促

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 预扩容失败 | 活动开始时容量不足 | 手动执行 ess-ops ExecuteScalingRule |
| MaxSize 未恢复 | 活动后 MaxSize 仍为临时值 | 手动执行 ess-ops ModifyScalingGroup |
| 渐缩失败 | 活动结束后未缩容 | 手动执行缩容或清理定时任务 |

### S6 闲置回收

| 失败点 | 症状 | 恢复步骤 |
|--------|------|---------|
| 误判 | 非闲置环境被回收 | 回滚 → 调整闲置阈值 (从 5% 调至 3%) |
| 回收后业务恢复 | 缩容后负载上升 | 触发保护告警 → 自动扩容 |
| 用户未确认 | 24h 通知后无响应 | 发送再次通知 + 记录待处理 |

---

## 4. 常见网络/环境问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `aliyun: command not found` | aliyun CLI 未安装 | 运行 `alicloud-jit-setup.sh` |
| `connect: connection refused` | 网络不通 | 检查网络代理/防火墙设置 |
| `Request expired` | 系统时间偏差 | 运行 `ntpdate` 同步时间 |
| `SignatureDoesNotMatch` | AK 不正确 | 检查 `ALIBABA_CLOUD_ACCESS_KEY_*` 环境变量 |