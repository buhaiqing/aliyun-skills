# SLB Field Mapping

**Aliyun API**: `slb DescribeLoadBalancers` → `alicloud_slb`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required | Notes |
|---------------|---------------|------|----------|-------|
| `name` | `LoadBalancerName` | string | ✅ | Block name derived from this |
| `specification` | `LoadBalancerSpec` | string | ✅ | e.g. `slb.s2.small` |
| `address_type` | `AddressType` | string | ✅ | `internet` / `intranet` |
| `internet_charge_type` | `InternetChargeType` | string | ✅ | `paybytraffic` / `paybybandwidth` |
| `bandwidth` | `Bandwidth` | int | ✅ | Mbps |
| `vswitch_id` | `VSwitchId` | string | ✅ | Parent ref via VSwitch |

## Block Name

`{name_slug}` (e.g. `prod_web_lb`)

## Stable Import ID

`slb:{region}:{lb_id}`

## Deferred to Phase 3

- Listeners (`alicloud_slb_listener`)
- Server certificates
- Health check configs
- Backend server groups
