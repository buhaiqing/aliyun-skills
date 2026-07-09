# ActionTrail Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for ActionTrail audit events.

## Metrics → Logs 联动

| ActionTrail 指标异常 | SLS 查询目标 | 目的 |
|---------------------|-------------|------|
| `ApiErrorRateInsight` 突增 | `* WHERE errorMessage != 'success' AND errorCode` | 确认 API 错误来源、用户和资源 |
| `IpInsight` 新 IP | `* WHERE sourceIpAddress = "新的 IP"` | 确认新 IP 的所有操作详情 |
| `ApiCallRateInsight` 突增 | `* WHERE eventTime > time | count(1) by eventName, userIdentity.userName` | 识别调用突增的用户和操作类型 |
| `TrailConcealmentInsight` | `* WHERE eventName LIKE 'DisableTrail' OR eventName LIKE 'DeleteTrail'` | 定位谁在尝试关闭审计 |
| `PolicyChangeInsight` | `* WHERE eventName LIKE 'Create%'Policy' OR eventName LIKE 'Attach%'Policy'` | 确认权限变更详情 |

## Metrics → Traces 联动

ActionTrail 本身不产生传统 Trace，但其事件天然具有"操作链路"：

| ActionTrail 事件 | 操作链路关联 | 目的 |
|-----------------|-------------|------|
| 用户登录 → API 调用 → 资源变更 | 按 userIdentity.sessionContext 关联 | 还原操作全链路 |
| AK 创建后的系列操作 | 按 accessKeyId 关联后续所有 API 事件 | 追踪 AK 使用轨迹 |
| 策略变更后的权限滥用 | 关联 policyChange + subsequent API calls | 检测权限滥用的风险 |

### 操作链路查询

```bash
# 查询用户操作链路
aliyun actiontrail LookupEvents \
  --LookupAttributes '[{"AttributeKey":"AccessKeyId","AttributeValue":"{{user.access_key_id}}"}]' \
  --StartTime "2026-05-15T00:00:00Z" \
  --EndTime "2026-05-16T00:00:00Z"
```

## 降级策略

若 SLS 不可用：
1. 直接使用 `aliyun actiontrail LookupEvents` API 查询最近 90 天事件
2. 检查 ActionTrail 控制台的 Trail 状态
3. 确认事件是否正常投递到 OSS（如启用了 OSS 投递）
