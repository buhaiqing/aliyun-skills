# CLI — ACK (`aliyun cs`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).

## Conventions (Agent Execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are
  non-interactive by default
- ACK uses **REST-style paths** (`GET /clusters`, `POST /clusters`, etc.) rather
  than RPC-style `--ParamName value`

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun cs`? | Notes |
|-----------------------|---------------------------|-------|
| CreateCluster | yes | `POST /clusters` or `aliyun cs CreateCluster` |
| DescribeClusters | yes | `GET /clusters` |
| DescribeClusterDetail | yes | `GET /clusters/{cluster_id}` |
| DescribeClusterNodes | yes | `GET /clusters/{cluster_id}/nodes` |
| DeleteCluster | yes | `DELETE /clusters/{cluster_id}` |
| ScaleOutCluster | yes | `POST /clusters/{cluster_id}/nodes` |
| CreateNodePool | yes | `POST /clusters/{cluster_id}/nodepools` |
| DescribeNodePools | yes | `GET /clusters/{cluster_id}/nodepools` |
| DeleteNodePool | yes | `DELETE /clusters/{cluster_id}/nodepools/{nodepool_id}` |
| UpgradeCluster | yes | `PUT /clusters/{cluster_id}/upgrade` |
| InstallAddon | partial | May require JIT SDK for some addon types |
| DescribeAddons | partial | May require JIT SDK for detailed config |
| ModifyNodePool | yes | `PUT /clusters/{id}/nodepools/{pool_id}` |
| DeleteNodePool | yes | `DELETE /clusters/{id}/nodepools/{pool_id}` |
| GetKubeconfig | yes | `GET /k8s/{id}/user_config` |

## Command Map

| Goal | Example `aliyun` invocation | Notes |
|------|----------------------------|-------|
| List clusters | `aliyun cs GET /clusters` | JSON output by default |
| Describe cluster | `aliyun cs GET /clusters/{cluster_id}` | JSON output by default |
| Create cluster | `aliyun cs POST /clusters --body '{...}'` | REST-style with JSON body |
| Delete cluster | `aliyun cs DELETE /clusters/{cluster_id}` | Requires confirmation |
| List nodes | `aliyun cs GET /clusters/{cluster_id}/nodes` | JSON output by default |
| Scale out | `aliyun cs POST /clusters/{cluster_id}/nodes --body '{...}'` | Add worker nodes |
| List node pools | `aliyun cs GET /clusters/{cluster_id}/nodepools` | JSON output by default |
| Create node pool | `aliyun cs POST /clusters/{cluster_id}/nodepools --body '{...}'` | JSON body with scaling config |
| Upgrade cluster | `aliyun cs PUT /clusters/{cluster_id}/upgrade --body '{...}'` | Specify target version |
| Extract fields | `aliyun cs GET /clusters --output cols=cluster_id,name rows=clusters[].{cluster_id,name}` | JMESPath tabular mode |
| Poll with waiter | `aliyun cs GET /clusters/{id} --waiter expr='state' to=running timeout=1800 interval=30` | Waiter for long-running ops |
| Body from file | `aliyun cs POST /clusters --body file:///tmp/cluster.json` | Avoid inline JSON escaping |

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

