# NAS FileSystem Field Mapping

**Aliyun API**: `nas DescribeFileSystems` → `alicloud_nas_file_system`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `description` | `Description` | string | ❌ |
| `storage_type` | `StorageType` | string | ✅ |
| `protocol_type` | `ProtocolType` | string | ✅ |

## Block Name

`{description_slug or file_system_id}`

## Stable Import ID

`nas:{region}:{file_system_id}`