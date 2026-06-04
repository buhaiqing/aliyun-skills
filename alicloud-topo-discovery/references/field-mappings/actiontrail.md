# ActionTrail Field Mapping

**Aliyun API**: `actiontrail DescribeTrails` → `alicloud_actiontrail`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `oss_bucket_name` | `OssBucketName` | string | ✅ |
| `oss_key_prefix` | `OssKeyPrefix` | string | ❌ |

## Block Name

`{name_slug}`

## Stable Import ID

`actiontrail:{region}:{name}`

## Note

`Status` field is bool (Enabled/Disabled) - mapped as `enabled = true/false` (deferred to Phase 4).