# SAG (Smart Access Gateway) Field Mapping

**Aliyun API**: `smartag DescribeSmartAccessGateways` → `alicloud_sag`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `cidr_block` | `CidrBlock` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`sag:{region}:{smart_ag_id}`

## Note

`CreateTime` is Unix epoch (int) — Phase 3 deferred conversion to ISO format.