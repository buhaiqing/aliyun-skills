# Function Compute (FC) Field Mapping

**Aliyun API**: `fc ListServices` + `fc ListFunctions` → `alicloud_fc_service` + `alicloud_fc_function`

## Mapping Rules (Service)

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `ServiceName` | string | ✅ |
| `description` | `Description` | string | ❌ |
| `role` | `Role` | string | ✅ |

## Block Name

`{service_name_slug}`

## Stable Import ID

`fc-service:{region}:{service_name}`

## Deferred to Phase 4

- `alicloud_fc_function` (separate resource, needs FunctionName path)
- `alicloud_fc_trigger` (function triggers)