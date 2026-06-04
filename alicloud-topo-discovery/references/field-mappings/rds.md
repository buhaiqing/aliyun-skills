# RDS Instance Field Mapping

**Aliyun API**: `rds DescribeDBInstances` → `alicloud_db_instance`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required | Notes |
|---------------|---------------|------|----------|-------|
| `instance_name` | `DBInstanceDescription` | string | ✅ | Block name derived from this |
| `engine` | `Engine` | string | ✅ | e.g. `MySQL` |
| `engine_version` | `EngineVersion` | string | ✅ | e.g. `8.0` |
| `instance_type` | `DBInstanceClass` | string | ✅ | e.g. `rds.mysql.s3.large` |
| `instance_storage` | `DBInstanceStorage` | int | ✅ | GB |
| `port` | `Port` | int | ✅ | e.g. `3306` |
| `vswitch_id` | `VSwitchId` | string | ✅ | Parent ref via VSwitch |
| `password` | `AccountPassword` | string | ❌ | **sensitive=true**, masked to `var.rds_password` |

## Block Name

`{description_slug}` (e.g. `prod_mysql`)

## Stable Import ID

`db_instance:{region}:{db_instance_id}`

## Deferred to Phase 3

- Backup policy
- Parameter groups
- Read replicas
- Monitoring / performance insights
