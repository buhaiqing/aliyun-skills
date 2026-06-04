# CLI — ASK (`aliyun cs` with `cluster_type=ManagedKubernetes + profile=Serverless`)

> **VERIFIED 2026-06-02 via `aliyun help cs` and meta JSON**

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars
  `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR
  `~/.aliyun/config.json` (JSON format).

## Conventions (Agent Execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI
- ACK uses **REST-style paths** (`POST /clusters`, `GET /clusters/{id}`, etc.)

## CLI Operation Map (VERIFIED)

| Goal | CLI command | Path |
|------|-------------|------|
| Create cluster | `aliyun cs POST /clusters` | `POST /clusters` |
| List clusters (v2) | `aliyun cs GET /api/v2/clusters` | `GET /api/v2/clusters` |
| List clusters (v1) | `aliyun cs GET /clusters` | `GET /clusters` |
| Describe cluster | `aliyun cs GET /clusters/{id}` | `GET /clusters/{ClusterId}` |
| Modify cluster | `aliyun cs PUT /api/v2/clusters/{id}` | `PUT /api/v2/clusters/{ClusterId}` |
| Delete cluster | `aliyun cs DELETE /clusters/{id}` | `DELETE /clusters/{ClusterId}` |
| Get kubeconfig | `aliyun cs GET /k8s/{id}/user_config` (or `DescribeClusterUserKubeconfig`) | `GET /k8s/{ClusterId}/user_config` |
| Update tags | `aliyun cs POST /clusters/{id}/tags` | `POST /clusters/{ClusterId}/tags` |
| Toggle deletion protection | `aliyun cs PUT /clusters/{id}/resources/protection` | `PUT /clusters/{ClusterId}/resources/protection` |
| Install addon | `aliyun cs POST /clusters/{id}/components/install` | `POST /clusters/{ClusterId}/components/install` |
| Uninstall addon | `aliyun cs POST /clusters/{id}/components/uninstall` | `POST /clusters/{ClusterId}/components/uninstall` |
| List addons | `aliyun cs GET /addons` | `GET /addons` |
| **UpgradeCluster** | `aliyun cs POST /api/v2/clusters/{id}/upgrade` | **DO NOT USE for ASK** |
| **Node pool operations** | various | **DO NOT USE for ASK** |

> **REST path vs operation name:** Both work. REST path is shorter
> (e.g. `POST /clusters/{id}/tags`) but operation name is more readable
> (e.g. `ModifyClusterTags`). Pick one and stick to it.

## Command Map (ASK-specific)

| Goal | Example `aliyun` invocation | Notes |
|------|------------------------------|-------|
| **List ONLY Ask clusters** | `aliyun cs GET /api/v2/clusters --output cols=... rows=...` (filter on `profile=Serverless`) | Filter via JMESPath |
| Describe cluster | `aliyun cs GET /clusters/{cluster_id}` | JSON output by default |
| Create ASK cluster | `aliyun cs POST /clusters --body '{...profile:"Serverless"...}'` | See SKILL.md for full body |
| Delete cluster | `aliyun cs DELETE /clusters/{cluster_id}` | Safety gate first |
| Get kubeconfig (public) | `aliyun cs GET /k8s/{id}/user_config` | Public endpoint |
| Get kubeconfig (internal) | `aliyun cs GET /k8s/{id}/user_config --PrivateIpAddress true` | VPC-only; default for ASK |
| Get temp kubeconfig (1h) | `aliyun cs GET /k8s/{id}/user_config --TemporaryDurationMinutes 60` | Validity 15-4320 min |
| Update tags | `aliyun cs POST /clusters/{id}/tags --body '{"tags":[...]}'` | ModifyClusterTags |
| Install addon | `aliyun cs POST /clusters/{id}/components/install --body '{"name":"nginx-ingress-controller","config":"..."}'` | InstallClusterAddons |
| Toggle deletion protection | `aliyun cs PUT /clusters/{id}/resources/protection --body '{"deletion_protection":true}'` | UpdateResourcesDeleteProtection |
| Poll for `running` | `aliyun cs GET /clusters/{id} --waiter expr='state' to=running timeout=1800 interval=30` | Waiter for long-running ops |
| Body from file | `aliyun cs POST /clusters --body file:///tmp/ask-cluster.json` | Avoid inline JSON escaping |

## Filter Examples (JMESPath)

### Find all ASK clusters in a region

```bash
aliyun cs GET /api/v2/clusters --RegionId $REGION \
  --output cols=cluster_id,name,state,profile,current_version \
  rows='[?profile==`Serverless`].{cluster_id:cluster_id,name:name,state:state,profile:profile,current_version:current_version}'
```

> **Note:** Filter `profile="Serverless"` identifies ASK. Older
> clusters may use `cluster_type="Ask"` but new ones use
> `cluster_type="ManagedKubernetes" + profile="Serverless"`.

### Find ASK clusters NOT in `running` state

```bash
aliyun cs GET /api/v2/clusters --RegionId $REGION \
  --output cols=cluster_id,name,state \
  rows='[?profile==`Serverless` && state!=`running`].{cluster_id:cluster_id,name:name,state:state}'
```

### Summarize cluster types + profiles in a region

```bash
aliyun cs GET /api/v2/clusters --RegionId $REGION \
  --output cols=cluster_type,profile \
  rows='[].{cluster_type:cluster_type,profile:profile}'
```

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Including `cluster_type="Ask"` | `InvalidParameter` (outdated) | Use `cluster_type=ManagedKubernetes + profile=Serverless` |
| Including `num_of_nodes` / `worker_instance_types` | `InvalidParameter` | Remove; ASK has no worker nodes |
| Including `vpc_id` in body | Field silently ignored | Use `vpcid` (input field name) |
| Passing `container_cidr` with Terway | May error or be ignored | For Terway (default), pass `vswitch_ids` only |
| Passing `pod_vswitch_ids` | **Deprecated** per OpenAPI spec | Use `vswitch_ids` |
| `endpoint_public_access_enabled` | Field doesn't exist | Use `endpoint_public_access` (no `_enabled` suffix) |
| Trying `POST /clusters/{id}/nodes` to "scale" | `InvalidParameter` | Use HPA/CronHPA instead |
| Calling `UpgradeCluster` | Will fail or be rejected | **NEVER** call; ASK doesn't support user upgrades |
| Missing NAT (Pods can't reach internet) | Pods fail to pull external images | Set `snat_entry=true` or pre-create NAT via `alicloud-nat-ops` |
| Addon config wrong format | Addon install fails | Pass config as **JSON string**, not nested object |

## Pre-Flight One-Liner

```bash
#!/bin/bash
# ask-preflight.sh — quick sanity check before any ASK operation
set -e
: "${ALIBABA_CLOUD_ACCESS_KEY_ID:?not set}"
: "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:?not set}"
: "${ALIBABA_CLOUD_REGION_ID:?not set}"

echo "=== CLI ==="
aliyun version | head -1

echo "=== Credentials (existence only) ==="
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ SK set (length: ${#ALIBABA_CLOUD_ACCESS_KEY_SECRET})"

echo "=== Region reachable ==="
aliyun cs GET /api/v2/clusters --RegionId "$ALIBABA_CLOUD_REGION_ID" \
  --output cols=cluster_id rows=cluster_id 2>/dev/null | wc -l

echo "=== Ask cluster count in region ==="
aliyun cs GET /api/v2/clusters --RegionId "$ALIBABA_CLOUD_REGION_ID" \
  --output cols=cluster_id \
  rows='[?profile==`Serverless`].cluster_id' 2>/dev/null | wc -l

echo "=== ECI quota (use alicloud-eci-ops) ==="
echo "Use: aliyun eci ListUsage --RegionId $ALIBABA_CLOUD_REGION_ID"
```

## Multi-Cluster Cleanup Script

```bash
#!/bin/bash
# ask-bulk-cleanup.sh — delete ASK clusters matching a name pattern
PATTERN="$1"  # e.g. "test-ask-"
REGION="$2"

aliyun cs GET /api/v2/clusters --RegionId "$REGION" \
  --output cols=cluster_id,name,state \
  rows='[?profile==`Serverless` && starts_with(name, `'"$PATTERN"'`)].{cluster_id:cluster_id,name:name,state:state}' \
  | while read -r ID NAME STATE; do
      if [ "$STATE" = "running" ]; then
        echo "Deleting $ID ($NAME)..."
        aliyun cs DELETE /clusters/$ID
      else
        echo "Skip $ID ($NAME) — state=$STATE"
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

