# API & SDK — ACK

## OpenAPI

- Spec: CS-2015-12-15
- Base path: `https://cs.{region}.aliyuncs.com`
- Documentation: https://www.alibabacloud.com/help/en/ack

## SDK Operations Map

| Goal | API Operation | SDK Method | CLI Equivalent |
|------|---------------|------------|----------------|
| Create cluster | `POST /clusters` | `client.CreateCluster()` | `aliyun cs POST /clusters` |
| List clusters | `GET /clusters` | `client.DescribeClusters()` | `aliyun cs GET /clusters` |
| Describe cluster | `GET /clusters/{id}` | `client.DescribeClusterDetail()` | `aliyun cs GET /clusters/{id}` |
| Delete cluster | `DELETE /clusters/{id}` | `client.DeleteCluster()` | `aliyun cs DELETE /clusters/{id}` |
| List nodes | `GET /clusters/{id}/nodes` | `client.DescribeClusterNodes()` | `aliyun cs GET /clusters/{id}/nodes` |
| Scale out | `POST /clusters/{id}/nodes` | `client.ScaleOutCluster()` | `aliyun cs POST /clusters/{id}/nodes` |
| Create node pool | `POST /clusters/{id}/nodepools` | `client.CreateNodePool()` | `aliyun cs POST /clusters/{id}/nodepools` |
| List node pools | `GET /clusters/{id}/nodepools` | `client.DescribeNodePools()` | `aliyun cs GET /clusters/{id}/nodepools` |
| Delete node pool | `DELETE /clusters/{id}/nodepools/{pool_id}` | `client.DeleteNodePool()` | `aliyun cs DELETE /clusters/{id}/nodepools/{pool_id}` |
| Upgrade cluster | `PUT /clusters/{id}/upgrade` | `client.UpgradeCluster()` | `aliyun cs PUT /clusters/{id}/upgrade` |
| Modify node pool | `PUT /clusters/{id}/nodepools/{pool_id}` | `client.ModifyNodePool()` | `aliyun cs PUT /clusters/{id}/nodepools/{pool_id}` |
| Delete node pool | `DELETE /clusters/{id}/nodepools/{pool_id}` | `client.DeleteNodePool()` | `aliyun cs DELETE /clusters/{id}/nodepools/{pool_id}` |
| Get kubeconfig | `GET /k8s/{id}/user_config` | `client.DescribeClusterUserKubeConfig()` | `aliyun cs GET /k8s/{id}/user_config` |

## SDK Package

```
github.com/alibabacloud-go/cs-20151215/v4/client
```

## Request / Response Notes

- **Required fields for CreateCluster:** `cluster_type`, `name`, `region_id`,
  `vpc_id`, `vswitch_ids`, `worker_instance_types`, `num_of_nodes`
- **Pagination:** List APIs use `page_size` and `page_number` query parameters
- **Long-running operations:** CreateCluster, UpgradeCluster, ScaleOutCluster
  return async task IDs; poll `DescribeClusterDetail` for state transitions
- **Cluster types:** `ManagedKubernetes` (managed), `Kubernetes` (dedicated),
  `Ask` (Serverless)
