# ECS Instance Field Mapping

**Aliyun API**: `ecs DescribeInstances` → `alicloud_instance`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required | Notes |
|---------------|---------------|------|----------|-------|
| `instance_name` | `InstanceName` | string | ✅ | Block name derived from this |
| `instance_type` | `InstanceType` | string | ✅ | e.g. `ecs.g7.large` |
| `image_id` | `ImageId` | string | ✅ | OS image |
| `host_name` | `HostName` | string | ❌ | Skipped if absent |
| `password` | `Password` | string | ❌ | **sensitive=true**, masked to `var.ecs_password` |
| `vswitch_id` | `VpcAttributes.VSwitchId` | string | ✅ | Parent ref via VSwitch |
| `security_groups` | `SecurityGroupIds.SecurityGroupId` | list | ✅ | `["sg-xxx"]` |

## Block Name

`{instance_name_slug}` (e.g. `web_01`)

## Stable Import ID

`instance:{region}:{instance_id}`

## Deferred to Phase 3

- Disks (`alicloud_disk` + attachment)
- Network interfaces
- RAM role
- User data / custom metadata
