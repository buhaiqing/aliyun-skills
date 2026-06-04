# PolarDB Cluster Field Mapping

**Aliyun API**: `polardb DescribeDBClusters` → `alicloud_polardb_cluster`

## Mapping Rules

| HCL Attribute | API JSON Path | Type | Required |
|---------------|---------------|------|----------|
| `description` | `DBClusterDescription` | string | ✅ |
| `db_type` | `DBType` | string | ✅ |
| `db_version` | `DBVersion` | string | ✅ |
| `db_node_class` | `DBNodeClass` | string | ✅ |
| `db_node_storage` | `DBNodeStorage` | int | ✅ |
| `vswitch_id` | `VSwitchId` | string | ✅ |

## Block Name

`{description_slug}`

## Stable Import ID

`polardb:{region}:{db_cluster_id}`