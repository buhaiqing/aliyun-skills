# VPN Connection Field Mapping

**Aliyun API**: `vpc DescribeVpnConnections` → `alicloud_vpn_connection`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `local_subnet` | `LocalSubnet` | string | ✅ |
| `remote_subnet` | `RemoteSubnet` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`vpn:{region}:{vpn_connection_id}`

## Deferred to Phase 4

- `alicloud_vpn_gateway` (separate resource)
- `alicloud_vpn_customer_gateway` (separate resource)
- `alicloud_sag` (Smart Access Gateway)