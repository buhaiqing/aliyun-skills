# Redis Instance Field Mapping

**Aliyun API**: `kvstore DescribeInstances` → `alicloud_redis_instance`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `instance_name` | `InstanceName` | string | ✅ |
| `instance_class` | `InstanceClass` | string | ✅ |
| `engine_version` | `EngineVersion` | string | ✅ |
| `connection_domain` | `ConnectionDomain` | string | ✅ |
| `port` | `Port` | int | ✅ |

## Block Name

`{instance_name_slug}`

## Stable Import ID

`redis:{region}:{instance_id}`