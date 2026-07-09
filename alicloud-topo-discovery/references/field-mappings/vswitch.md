# VSwitch Field Mapping

**Aliyun API**: `vpc DescribeVSwitches` → `alicloud_vswitch`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required | Notes |
|---------------|---------------|------|----------|-------|
| `vswitch_name` | `VSwitchName` | string | ✅ | Block name derived from this |
| `cidr_block` | `CidrBlock` | string | ✅ | e.g. `10.0.1.0/24` |
| `zone_id` | `ZoneId` | string | ✅ | Availability zone |
| `description` | `Description` | string | ❌ | Skipped if absent |

## Parent Reference

`vpc_id` is set via `parent_ref="VpcId"` in MappingSpec. The dependency inference engine resolves this to the matching VPC block's ID.

## Block Name

`{vswitch_name_slug}_{zone_id_slug}` (e.g. `vsw_prod_web_a`)

## Stable Import ID

`vswitch:{region}:{vswitch_id}`

## Example

Input JSON:
```json
{
  "VSwitchId": "vsw-bp1aevb8sfi8mh1qj5t9",
  "VSwitchName": "vsw-prod-web-a",
  "VpcId": "vpc-bp1aevb8sfi8mh1qj5t8",
  "CidrBlock": "10.0.1.0/24",
  "ZoneId": "cn-beijing-a"
}
```

Output HCL:
```hcl
resource "alicloud_vswitch" "vsw_prod_web_a" {
  vswitch_name = "vsw-prod-web-a"
  cidr_block   = "10.0.1.0/24"
  zone_id      = "cn-beijing-a"
  vpc_id       = alicloud_vpc.prod_vpc_beijing.id
}
```
