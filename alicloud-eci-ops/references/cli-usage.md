# CLI — ECI (`aliyun eci`) — VERIFIED 2026-06-02

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).

## Conventions (Agent Execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI
- ECI parameter style: **two options**:
  - **`--Container.N.*` array parameters** (for simple cases, e.g. single container)
  - **`--body '{...}'`** (for complex cases, multi-container, private registry, etc.)
- Verify exact shape with `aliyun eci <Op> --help`

## CLI Operation Map (verified from `aliyun help eci`)

| Operation | Available via `aliyun eci`? | CLI |
|-----------|----------------------------|-----|
| CreateContainerGroup | ✅ | `aliyun eci CreateContainerGroup` |
| DescribeContainerGroups | ✅ | `aliyun eci DescribeContainerGroups` |
| DescribeContainerGroup (single) | ✅ | `aliyun eci DescribeContainerGroup` |
| DeleteContainerGroup | ✅ | `aliyun eci DeleteContainerGroup` |
| UpdateContainerGroup | ✅ | `aliyun eci UpdateContainerGroup` |
| RestartContainerGroup | ✅ | `aliyun eci RestartContainerGroup` |
| ExecContainerCommand | ✅ | `aliyun eci ExecContainerCommand` |
| DescribeContainerLog | ✅ | `aliyun eci DescribeContainerLog` |
| DescribeContainerGroupStatus (batch) | ✅ | `aliyun eci DescribeContainerGroupStatus` |
| DescribeContainerGroupEvents | ✅ | `aliyun eci DescribeContainerGroupEvents` |
| DescribeContainerGroupMetric | ✅ | `aliyun eci DescribeContainerGroupMetric` |
| DescribeMultiContainerGroupMetric | ✅ | `aliyun eci DescribeMultiContainerGroupMetric` |
| **ListUsage (QUOTA — verified)** | ✅ | `aliyun eci ListUsage --body '{"RegionId":"..."}'` |
| DescribeContainerGroupPrice | ✅ | `aliyun eci DescribeContainerGroupPrice` |
| DescribeAvailableResource | ✅ | `aliyun eci DescribeAvailableResource` |
| ResizeContainerGroupVolume | ✅ | `aliyun eci ResizeContainerGroupVolume` |
| CommitContainer | ✅ | `aliyun eci CommitContainer` |
| CreateImageCache | ✅ | `aliyun eci CreateImageCache` |
| DeleteImageCache / UpdateImageCache / DescribeImageCaches | ✅ | `aliyun eci <Op>` |
| CreateDataCache / DescribeDataCaches / UpdateDataCache / CopyDataCache / DeleteDataCache | ✅ | `aliyun eci <Op>` |
| CreateVirtualNode / DescribeVirtualNodes / UpdateVirtualNode / DeleteVirtualNode | ✅ | `aliyun eci <Op>` |
| TagResources / UntagResources / ListTagResources | ✅ | `aliyun eci <Op>` |
| CreateInstanceOpsTask / DescribeInstanceOpsRecords | ✅ | `aliyun eci <Op>` |

> **CORRECTION:** Earlier training knowledge mentioned
> `DescribeContainerGroupQuota` — that command does **not exist**.
> Use **`ListUsage`** for quota.

## Command Map (verified)

| Goal | Example `aliyun` invocation | Notes |
|------|------------------------------|-------|
| **Check quota (always first)** | `aliyun eci ListUsage --body '{"RegionId":"cn-hangzhou"}'` | Pre-flight critical |
| List ECIs | `aliyun eci DescribeContainerGroups --RegionId cn-hangzhou` | JSON output by default |
| List running ECIs | `aliyun eci DescribeContainerGroups --RegionId cn-hangzhou --Status Running` | Filter by status |
| Describe single ECI | `aliyun eci DescribeContainerGroup --RegionId cn-hangzhou --ContainerGroupId eci-xxx` | Full detail |
| **Create ECI (style 1: array params)** | `aliyun eci CreateContainerGroup --Container.1.Name app --Container.1.Image nginx:1.25 --Cpu 1 --Memory 2 --VSwitchId vsw-xxx --SecurityGroupId sg-xxx` | Single container |
| **Create ECI (style 2: JSON body)** | `aliyun eci CreateContainerGroup --body '{...full body...}'` | Multi-container / private registry / complex |
| Delete ECI | `aliyun eci DeleteContainerGroup --RegionId cn-hangzhou --ContainerGroupId eci-xxx` | Safety gate first |
| **Exec into container (JSON array!)** | `aliyun eci ExecContainerCommand --ContainerGroupId eci-xxx --ContainerName app --Command '["/bin/sh","-c","ls"]' --Sync true` | **Command must be JSON array** |
| Update image | `aliyun eci UpdateContainerGroup --ContainerGroupId eci-xxx --Container.1.Name app --Container.1.Image nginx:1.26` | Forces restart |
| Restart ECI | `aliyun eci RestartContainerGroup --ContainerGroupId eci-xxx` | |
| Get container logs | `aliyun eci DescribeContainerLog --ContainerGroupId eci-xxx --ContainerName app --Since 1h` | (verify exact params) |
| List ECI events | `aliyun eci DescribeContainerGroupEvents --ContainerGroupId eci-xxx` | For diagnosis |

## Verified CLI parameter shapes

### DescribeContainerGroups (verified)

```
--RegionId                 Required, string
--ContainerGroupIds        JSON array, max 20
--ContainerGroupName       string
--Limit                    integer (default 20, max 20)
--NextToken                string (pagination)
--ResourceGroupId          string
--SecurityGroupId          string
--Status                   enum: Pending / Running (more values exist)
--ComputeCategory          string (economy / general)
```

### ExecContainerCommand (verified)

```
--Command          Required, string (JSON array). Example: '["/bin/sh", "-c", "ls"]'
--ContainerGroupId Required, string
--ContainerName    Required, string
--RegionId         Required, string
--Stdin            Boolean, default true
--Sync             Boolean, default false. If true, TTY must be false.
--TTY              Boolean, default false. If Command is /bin/bash, must be true.
```

> **⚠️ Historical bug to avoid:** Earlier training knowledge showed
> `--Command "ls -la"` (string). The CLI requires **JSON array**.
> Use `jq` to build: `--Command "$(echo '["ls","-la"]' | jq -c .)"`

### ListUsage (verified quota command)

```bash
aliyun eci ListUsage --body '{"RegionId":"cn-hangzhou"}'
```

> Response field names need first-use verification (see
> [openapi-verify-checklist.md](openapi-verify-checklist.md)).

## Multi-Container ECI Example (style 2 body)

```bash
aliyun eci CreateContainerGroup --body '{
  "RegionId": "cn-hangzhou",
  "ContainerGroupName": "web-with-sidecar",
  "VSwitchId": "vsw-xxx",
  "SecurityGroupId": "sg-xxx",
  "Cpu": 1.5,
  "Memory": 3,
  "RestartPolicy": "Always",
  "Container": [
    {"Name": "nginx", "Image": "nginx:1.25", "Cpu": 1, "Memory": 2},
    {"Name": "log-shipper", "Image": "logshipper:v1", "Cpu": 0.5, "Memory": 1}
  ],
  "Tags": [
    {"Key": "app", "Value": "web"},
    {"Key": "env", "Value": "prod"}
  ]
}'
```

## Private Registry (ACR) Example

```bash
aliyun eci CreateContainerGroup --body '{
  "RegionId": "cn-hangzhou",
  "ContainerGroupName": "private-app",
  "VSwitchId": "vsw-xxx",
  "SecurityGroupId": "sg-xxx",
  "Cpu": 1, "Memory": 2, "RestartPolicy": "Never",
  "Container": [
    {"Name": "app", "Image": "registry-vpc.cn-hangzhou.aliyuncs.com/myteam/app:v1", "Cpu": 1, "Memory": 2}
  ],
  "ImageRegistryCredential": [
    {
      "Server": "registry-vpc.cn-hangzhou.aliyuncs.com",
      "UserName": "yourusername",
      "Password": "yourpassword"
    }
  ]
}'
```

> **Field names verified:** `Server`, `UserName` (not `Username`),
> `Password`.

## Filter Examples (JMESPath)

### Summarize ECI status distribution
```bash
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --output cols=Status rows=ContainerGroups[].Status \
  | sort | uniq -c
```

### Find failed ECIs
```bash
aliyun eci DescribeContainerGroups --RegionId $REGION --Status Failed \
  --output cols=ContainerGroupId,Name,Status \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,Name:ContainerGroupName,Status:Status}
```

## Pre-Flight One-Liner

```bash
#!/bin/bash
# eci-preflight.sh — quick sanity check before any ECI operation
set -e
: "${ALIBABA_CLOUD_ACCESS_KEY_ID:?not set}"
: "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:?not set}"
: "${ALIBABA_CLOUD_REGION_ID:?not set}"

echo "=== CLI ==="
aliyun version | head -1

echo "=== Credentials (existence only) ==="
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ SK set (length: ${#ALIBABA_CLOUD_ACCESS_KEY_SECRET})"

echo "=== ECI quota (region-level) ==="
aliyun eci ListUsage --body "{\"RegionId\":\"$ALIBABA_CLOUD_REGION_ID\"}"

echo "=== Current ECI count in region ==="
aliyun eci DescribeContainerGroups --RegionId "$ALIBABA_CLOUD_REGION_ID" \
  --output cols=ContainerGroupId rows=ContainerGroups[].ContainerGroupId | wc -l
```

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Missing `VSwitchId` / `SecurityGroupId` | `InvalidParameter` | Pre-create via `alicloud-vpc-ops` |
| VSwitch has no free IP | `InvalidVSwitchId.IpNotEnough` | Expand VSwitch CIDR or pick another |
| ECI quota exhausted | `QuotaExceeded` | Raise quota in ECI console |
| Image from private registry without credentials | `ImagePullError` | Add `ImageRegistryCredential` with `Server`+`UserName`+`Password` |
| `RestartPolicy=Always` + crash | Infinite billing | Use `Never` or `OnFailure` |
| Cpu/Memory not in supported range | `InvalidParameter.CPU.Memory` | Verify spec limits |
| Container spec > ContainerGroup spec | `InvalidParameter.CPU.Memory` | Match container sum ≤ CG total |
| `--Command "ls"` (string) for Exec | CLI error | Use JSON array: `--Command '["ls"]'` |
| Image cache not found | `ImageSnapshot.NotFound` | Create with `CreateImageCache` first |

## Batch Cleanup Script

```bash
#!/bin/bash
# eci-bulk-cleanup.sh — delete ECIs in terminal state older than N hours
REGION="$1"
MAX_AGE_HOURS="$2"
NOW=$(date +%s)

aliyun eci DescribeContainerGroups --RegionId "$REGION" \
  --Status Succeeded --Status Failed \
  --output cols=ContainerGroupId,CreatedTime \
  rows=ContainerGroups[].{ContainerGroupId:ContainerGroupId,CreatedTime:CreatedTime} \
  | while read -r ID CREATED; do
      CREATED_TS=$(date -d "$CREATED" +%s 2>/dev/null || echo 0)
      AGE_HOURS=$(( (NOW - CREATED_TS) / 3600 ))
      if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
        echo "Deleting $ID (age: ${AGE_HOURS}h)"
        aliyun eci DeleteContainerGroup --RegionId "$REGION" --ContainerGroupId "$ID"
      fi
    done
```

> Use with caution. Always log what you delete.

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

