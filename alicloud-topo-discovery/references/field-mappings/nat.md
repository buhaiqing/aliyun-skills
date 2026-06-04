# NAT Gateway Field Mapping

**Aliyun API**: `vpc DescribeNatGateways` → `alicloud_nat_gateway`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `description` | `Description` | string | ❌ |
| `nat_type` | `NatType` | string | ✅ |
| `internet_charge_type` | `InternetChargeType` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`nat:{region}:{nat_gateway_id}`