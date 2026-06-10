# Cross-Skill Collaboration Protocol

## 1. Trigger Conditions

| 触发条件 | 当前技能 | 目标技能 | 传递数据 |
|----------|----------|----------|----------|
| InvalidDBInstanceId.NotFound | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | instance_id, engine |
| 连通性诊断失败（安全组/白名单） | alicloud-das-ops | alicloud-vpc-ops | instance_id, src_ip, failure_reason |
| 连通性诊断失败（路由） | alicloud-das-ops | alicloud-vpc-ops | instance_id, vpc_id, route_table_id |
| 实例状态异常 | alicloud-das-ops | alicloud-rds-ops / engine-specific | instance_id, status, engine |
| 账户余额不足 | alicloud-das-ops | alicloud-billing-ops | instance_id, feature_name |
| RAM 权限不足 | alicloud-das-ops | alicloud-ram-ops | instance_id, required_permission |
| 需要创建/删除实例 | alicloud-das-ops | alicloud-rds-ops / engine-specific | engine, region, spec |

## 2. Context Format

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
    "suggested_actions": ["Check security group rules", "Verify whitelist"],
    "diagnosis_timestamp": "2026-05-14T10:30:00Z",
    "request_id": "B6D17591-B48B-4D31-9CD6-9B9796B2****"
  },
  "expected_outcome": "Fix network connectivity",
  "callback_api": "GetDBInstanceConnectivityDiagnosis"
}
```

## 3. Best Practices

1. **Context completeness**: Include instance_id, engine, region, key diagnostic data
2. **No circular delegation**: Target skill should not re-delegate back
3. **Result verification**: Source skill must re-verify after target fix
4. **Error handling**: Log all attempts, suggest manual intervention if unresolvable
5. **Security**: Never pass AccessKey Secret across skills
