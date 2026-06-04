# OSS Bucket Field Mapping

**Aliyun API**: `oss GetBucketInfo` → `alicloud_oss_bucket`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `bucket` | `Name` | string | ✅ |
| `storage_class` | `StorageClass` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`oss-bucket:{region}:{bucket_name}`

## Note

OSS API differs from other Aliyun APIs (no `Describe*` endpoint). Use
`ossutil` or call `GetBucketInfo` via aliyun CLI.