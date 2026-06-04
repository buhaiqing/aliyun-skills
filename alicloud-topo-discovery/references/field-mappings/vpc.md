# VPC Field Mapping

**Aliyun API**: `vpc DescribeVpcs` → `alicloud_vpc`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required | Notes |
|---------------|---------------|------|----------|-------|
| `vpc_name` | `VpcName` | string | ✅ | Block name derived from this |
| `cidr_block` | `CidrBlock` | string | ✅ | e.g. `10.0.0.0/8` |
| `description` | `Description` | string | ❌ | Skipped if absent |

## Block Name

`{vpc_name_slug}` (e.g. `prod_vpc_beijing`)

## Stable Import ID

`vpc:{region}:{vpc_id}` (e.g. `vpc:cn-beijing:vpc-bp1aevb8sfi8mh1qj5t8`)

## Example

Input JSON (DescribeVpcs):
```json
{
  "VpcId": "vpc-bp1aevb8sfi8mh1qj5t8",
  "VpcName": "prod-vpc-beijing",
  "CidrBlock": "10.0.0.0/8",
  "Description": "Production VPC in Beijing"
}
```

Output HCL:
```hcl
resource "alicloud_vpc" "prod_vpc_beijing" {
  vpc_name  = "prod-vpc-beijing"
  cidr_block = "10.0.0.0/8"
  description = "Production VPC in Beijing"
}
```
