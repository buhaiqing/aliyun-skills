# OpenAPI Verify Checklist — ASK (VERIFIED 2026-06-02)

> **Status: ✅ VERIFIED via `aliyun cs CreateCluster --help` +
> `https://api.aliyun.com/meta/v1/products/CS/versions/2015-12-15/api-docs.json`**

## ✅ Verified Findings (real OpenAPI, training knowledge was partially wrong)

### Major correction: ASK cluster_type is NOT `"Ask"`

The CS 2015-12-15 OpenAPI defines only **three** `cluster_type` values:

| `cluster_type` | Meaning |
|----------------|---------|
| `Kubernetes` | ACK 专有集群 |
| `ManagedKubernetes` | **ACK 托管类集群**（包括 ACK 托管、ACK Serverless、ACK Edge、ACK 灵骏 — **ASK is here**） |
| `ExternalKubernetes` | 注册集群 |

**ASK is identified by `cluster_type=ManagedKubernetes` + `profile=Serverless`**,
NOT by a separate `cluster_type=Ask`. The `profile` field values are:

| `profile` | Meaning |
|-----------|---------|
| `Default` | ACK 托管集群（Pro版、基础版） |
| `Edge` | ACK Edge 集群 |
| **`Serverless`** | **ACK Serverless 集群（ASK）** |
| `Lingjun` | ACK 灵骏集群（Pro版） |

> **Historical note:** Earlier versions of the OpenAPI may have accepted
> `cluster_type=Ask`. As of 2026-06-02, the spec lists only the three values
> above; using `cluster_type=Ask` will fail with `InvalidParameter`.
> If you find an older doc/blog using `cluster_type=Ask`, treat as outdated.

### `cluster_spec` values (ManagedKubernetes + profile=Serverless)

| Value | Meaning |
|-------|---------|
| `ack.standard` | 基础版（default） |
| `ack.pro.small` | Pro 版 |
| `ack.pro.xlarge` | Pro XL |
| `ack.pro.2xlarge` | Pro 2XL |
| `ack.pro.4xlarge` | Pro 4XL（白名单） |

Pro versions of ASK have provisioned control plane and additional capabilities.

### Other verified fields (CreateCluster body)

| Field | Required? | Default | Notes |
|-------|-----------|---------|-------|
| `name` | ✅ | — | 1-63 chars; not starting with `-` |
| `region_id` | ✅ | — | e.g. `cn-beijing` |
| `cluster_type` | (default) | `Kubernetes` | For ASK: `ManagedKubernetes` |
| `profile` | (default) | `Default` | For ASK: `Serverless` |
| `cluster_spec` | (default) | `ack.standard` | For ASK Pro: `ack.pro.small` etc. |
| `kubernetes_version` | (default) | latest | e.g. `1.32.1-aliyun.1` |
| `vpcid` | ✅ if not auto-create | — | Note: field is **`vpcid`**, NOT `vpc_id` |
| `vswitch_ids` | ✅ if not auto-create | — | Array of VSwitch IDs |
| `container_cidr` | Flannel only | — | Pod CIDR (e.g. `172.20.0.0/16`) |
| `service_cidr` | (default) | `172.19.0.0/20` | Service CIDR |
| `security_group_id` | (optional) | auto-create | Existing SG |
| `is_enterprise_security_group` | (default) | `true` | Recommended for Terway |
| `snat_entry` | (default) | `false` | Auto-create NAT + SNAT for outbound |
| `endpoint_public_access` | (default) | `false` | Expose API server via EIP |
| `load_balancer_id` | (optional) | auto-create | Use existing CLB for API server |
| `timezone` | (optional) | system | e.g. `Asia/Shanghai` |
| `tags` | (optional) | (none) | Array of `{key, value}` |
| `resource_group_id` | (optional) | (none) | Resource group |
| `deletion_protection` | (default) | `false` | Block DeleteCluster |
| `controlplane_log_ttl` | (optional) | 30 | Days |
| `controlplane_log_project` | (optional) | auto | SLS project for control plane logs |
| `controlplane_log_components` | (optional) | default set | e.g. `["apiserver","kcm","scheduler"]` |
| `api_audiences` | (optional) | default | For token validation |
| `cluster_domain` | (optional) | `cluster.local` | Cluster local domain |
| `extra_sans` | (optional) | (none) | API server cert SANs |
| `maintenance_window` | (optional) | (none) | Auto-upgrade window |
| `addons` | (optional) | (none) | **Array of addon configs** (see below) |
| `nodepools` | (N/A for ASK) | — | ASK ignores these (no nodes) |
| `auto_mode` | (optional) | (none) | 智能托管模式 |

### `addons` schema (verified)

Each addon entry is an object with these fields:

| Field | Required? | Description |
|-------|-----------|-------------|
| `name` | ✅ | Addon name (e.g. `flannel`, `terway-eniip`, `nginx-ingress-controller`, `csi-plugin`, `csi-provisioner`, `loongcollector`, `ack-node-problem-detector`) |
| `config` | (optional) | Addon-specific config (JSON string) |
| `version` | (optional) | Addon version (e.g. `v1.9.3-aliyun.1`) |
| `disabled` | (default) `false` | Set `true` to skip auto-install |

**Common addons for ASK:**
- Network: `terway-eniip` (default) or `flannel`
- Storage: `csi-plugin`, `csi-provisioner`
- Logging: `loongcollector` (with SLS project config)
- Ingress: `nginx-ingress-controller` (with `IngressSlbNetworkType`)

### Response fields (DescribeClusterDetail)

| JSON path | Description |
|-----------|-------------|
| `$.cluster_id` | Cluster ID |
| `$.name` | Cluster name |
| `$.cluster_type` | `ManagedKubernetes` for ASK |
| `$.profile` | `Serverless` for ASK |
| `$.cluster_spec` | e.g. `ack.standard` |
| `$.state` | `initial` / `running` / `updating` / `deleting` / `failed` |
| `$.region_id` | Region |
| `$.current_version` | K8s version (managed by ACK) |
| `$.vpc_id` | Note: response field is **`vpc_id`**, not `vpcid` |
| `$.vswitch_ids` | VSwitch IDs |
| `$.security_group_id` | SG ID |
| `$.deletion_protection` | Boolean |
| `$.tags` | Resource tags |
| `$.api_server` / `$.api_server.endpoint` | API server URL |
| `$.api_server.intranet_endpoint` | Internal API server URL (VPC-only) |
| `$.created` | ISO 8601 |
| `$.updated` | ISO 8601 |
| `$.resource_group_id` | Resource group |
| `$.control_plane_log` | Control plane log config |
| `$.maintenance_window` | Maintenance window |
| `$.operation_policy` | Auto operation policy |

> **Note:** Response uses `vpc_id` (camelCase, snake case), but **input** uses
> `vpcid` (no separator). This inconsistency is in the real OpenAPI.

### Kubeconfig endpoint (verified)

- Operation: `DescribeClusterUserKubeconfig` (note: **`Kubeconfig` with lowercase `k`**)
- Method: `GET`
- Path: `/k8s/{ClusterId}/user_config`
- Parameters:
  - `ClusterId` (required)
  - `PrivateIpAddress` (boolean, optional, default `false`) — `true` for VPC-only access
  - `TemporaryDurationMinutes` (long, optional, 15-4320 min = 3 days)

### ModifyCluster operations (verified)

| Operation | Method | Path | Purpose |
|-----------|--------|------|---------|
| `ModifyCluster` | PUT | `/api/v2/clusters/{ClusterId}` | Update cluster metadata (note: v2 path) |
| `ModifyClusterTags` | POST | `/clusters/{ClusterId}/tags` | Update tags |
| `UpdateResourcesDeleteProtection` | PUT | `/clusters/{ClusterId}/resources/protection` | Update deletion protection |
| `UpdateControlPlaneLog` | PUT | `/clusters/{ClusterId}/controlplanelog` | Update control plane log config |
| `UpdateKMSEncryption` | PUT | `/clusters/{ClusterId}/kms` | Update KMS encryption |
| `UpdateClusterAuditLogConfig` | PUT | `/clusters/{clusterid}/audit_log` | Update audit log config |
| `InstallClusterAddons` | POST | `/clusters/{ClusterId}/components/install` | Install addon (note: `/components/install`, not `/components`) |
| `UnInstallClusterAddons` | POST | `/clusters/{ClusterId}/components/uninstall` | Uninstall addon |
| `ModifyClusterAddon` | POST | `/clusters/{cluster_id}/components/{component_id}/config` | Update addon config |

### Explicitly unsupported operations (ASK)

| Operation | Reason |
|-----------|--------|
| `UpgradeCluster` | Control plane is Alibaba-managed |
| `ScaleClusterNodePool` | No node pools in ASK |
| `CreateClusterNodePool` | No node pools in ASK |
| `DescribeClusterNodes` | No nodes in ASK (returns empty) |
| `DescribeClusterNodePools` | No node pools (returns empty) |

## When to Re-Verify

| Trigger | Action |
|---------|--------|
| OpenAPI version change (announced by Alibaba) | Re-fetch meta JSON |
| New addon needed for ASK | Verify `ListAddons` + `DescribeAddon` |
| ASK Pro changes (cluster_spec) | Re-verify Pro spec fields |

## Commands Re-Run

To re-verify from scratch:

```bash
# Cluster create parameters
aliyun cs CreateCluster --help

# Meta JSON (canonical schema)
curl -s https://api.aliyun.com/meta/v1/products/CS/versions/2015-12-15/api-docs.json | jq '.apis.CreateCluster'

# All cs operations
aliyun help cs

# Kubeconfig
aliyun cs DescribeClusterUserKubeconfig --help
```
