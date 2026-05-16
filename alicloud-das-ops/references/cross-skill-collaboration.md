# Cross-Skill Collaboration Protocol

## 1. 跨技能协同触发条件

| 触发条件 | 当前技能 | 目标技能 | 传递数据 | 触发时机 |
|----------|----------|----------|----------|----------|
| InvalidDBInstanceId.NotFound | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | instance_id, engine | 任何 DAS API 返回实例未找到 |
| 连通性诊断失败（安全组/白名单） | alicloud-das-ops | alicloud-vpc-ops | instance_id, src_ip, failure_reason | GetDBInstanceConnectivityDiagnosis 返回 UNREACHABLE |
| 连通性诊断失败（路由） | alicloud-das-ops | alicloud-vpc-ops | instance_id, vpc_id, route_table_id | 路由不可达 |
| 实例状态异常 | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | instance_id, status, engine | OperationDenied.InstanceStatus |
| 账户余额不足 | alicloud-das-ops | alicloud-billing-ops | instance_id, feature_name | InsufficientBalance |
| RAM 权限不足 | alicloud-das-ops | alicloud-ram-ops | instance_id, required_permission | RAM 相关错误 |
| 需要创建/删除实例 | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | engine, region, spec | 用户要求创建底层实例 |

## 2. 跨技能上下文传递格式

```json
{
  "source_skill": "alicloud-das-ops",
  "target_skill": "alicloud-vpc-ops",
  "trigger_reason": "GetDBInstanceConnectivityDiagnosis returned UNREACHABLE",
  "context": {
    "instance_id": "rm-2ze8g2am97624****",
    "engine": "MySQL",
    "region_id": "cn-hangzhou",
    "das_region_id": "cn-shanghai",
    "src_ip": "192.168.1.100",
    "failure_reason": "SecurityGroupRuleNotFound",
    "suggested_actions": ["Check security group rules", "Verify whitelist configuration"],
    "diagnosis_timestamp": "2026-05-14T10:30:00Z",
    "request_id": "B6D17591-B48B-4D31-9CD6-9B9796B2****"
  },
  "expected_outcome": "Fix network connectivity and return result to alicloud-das-ops",
  "callback_api": "GetDBInstanceConnectivityDiagnosis"
}
```

## 3. 跨技能协同流程

```
┌─────────────────┐
│  alicloud-das-ops │
│  执行诊断流程     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 识别到跨技能问题  │
│ (如网络连通性)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 构建上下文包     │
│ (包含所有诊断数据)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 委托目标技能     │
│ (如vpc-ops)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 目标技能执行修复  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 返回修复结果     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ das-ops 验证修复 │
│ (重新执行诊断)   │
└─────────────────┘
```

## 4. 跨技能协同最佳实践

1. **上下文完整性**：委托时必须包含 instance_id、engine、region 等基础信息，以及诊断过程中的关键数据
2. **避免循环委托**：目标技能不应将问题重新委托回源技能，除非明确需要补充信息
3. **结果验证**：源技能在收到目标技能的修复结果后，必须重新验证问题是否解决
4. **错误处理**：若目标技能也无法解决问题，应记录所有尝试过的方案，并建议人工介入
5. **安全传递**：跨技能传递的上下文中不得包含 AccessKey Secret 等敏感信息
