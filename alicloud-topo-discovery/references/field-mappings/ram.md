# RAM Role Field Mapping

**Aliyun API**: `ram ListRoles` → `alicloud_ram_role`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `RoleName` | string | ✅ |
| `description` | `Description` | string | ❌ |
| `arn` | `Arn` | string | ✅ |
| `assume_role_policy` | `AssumeRolePolicyDocument` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`ram-role:{account_id}:{role_name}`