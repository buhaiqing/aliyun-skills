# ACK (Container Service) Field Mapping

**Aliyun API**: `cs DescribeClustersV1` → `alicloud_cs_kubernetes`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `name` | `Name` | string | ✅ |
| `cluster_type` | `ClusterType` | string | ✅ |
| `version` | `Version` | string | ✅ |
| `worker_number` | `WorkerNumber` | int | ✅ |
| `vswitch_ids` | `VSwitchIds.VSwitchId` | list | ✅ |
| `vpc_id` | `VpcId` | string | ✅ |

## Block Name

`{name_slug}`

## Stable Import ID

`cs:{region}:{cluster_id}`

## Note

`master_number` not in Phase 3 spec (deferred to Phase 4).