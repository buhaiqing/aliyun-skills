# KMS Key Field Mapping

**Aliyun API**: `kms ListKeys` + `DescribeKey` → `alicloud_kms_key`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `description` | `Description` | string | ❌ |
| `key_spec` | `KeySpec` | string | ✅ |
| `usage` | `KeyUsage` | string | ✅ |
| `origin` | `Origin` | string | ✅ |

## Block Name

Uses `KeyId` (key-bp1xxx) since no Name field

## Stable Import ID

`kms:{region}:{key_id}`

## Note

KMS `Origin` field may be absent for default Aliyun-managed keys. Use `required=False` defaults.