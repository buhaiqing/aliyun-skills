# EIP Field Mapping

**Aliyun API**: `vpc DescribeEipAddresses` → `alicloud_eip`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `bandwidth` | `Bandwidth` | int | ✅ |
| `internet_charge_type` | `InternetChargeType` | string | ✅ |
| `instance_charge_type` | `InstanceChargeType` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`eip:{region}:{allocation_id}`