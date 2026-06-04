# SecurityGroup Field Mapping

**Aliyun API**: `ecs DescribeSecurityGroups` → `alicloud_security_group`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `SecurityGroupName` | string | ✅ |
| `description` | `Description` | string | ❌ |

## Block Name

`{name_slug}`

## Stable Import ID

`security_group:{region}:{security_group_id}`

## Deferred to Phase 4

- SecurityGroupRule (`alicloud_security_group_rule`)
- vpc_id parent ref