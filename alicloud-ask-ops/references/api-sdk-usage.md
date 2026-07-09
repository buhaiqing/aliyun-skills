# API & SDK — ASK (VERIFIED 2026-06-02)

> **Status: ✅ Fields verified via meta JSON
> (`https://api.aliyun.com/meta/v1/products/CS/versions/2015-12-15/api-docs.json`)
> and `aliyun cs CreateCluster --help`**

## OpenAPI

- Spec: **CS-2015-12-15** (verified)
- Base path: `https://cs.{region}.aliyuncs.com`
- Documentation: https://www.alibabacloud.com/help/en/ack
- **ASK identifier:** `cluster_type=ManagedKubernetes` + `profile=Serverless`
  (NOT `cluster_type=Ask` — that's outdated)

## SDK Operations Map (verified from `aliyun help cs`)

| Goal | CLI Operation | Path |
|------|---------------|------|
| Create ASK cluster | `aliyun cs CreateCluster` | `POST /clusters` |
| List clusters | `aliyun cs DescribeClustersV1` | `GET /api/v2/clusters` (or `DescribeClusters`) |
| Describe cluster | `aliyun cs DescribeClusterDetail` | `GET /clusters/{ClusterId}` |
| Modify cluster | `aliyun cs ModifyCluster` | `PUT /api/v2/clusters/{ClusterId}` (note: v2) |
| Delete cluster | `aliyun cs DeleteCluster` | `DELETE /clusters/{ClusterId}` |
| Get kubeconfig | `aliyun cs DescribeClusterUserKubeconfig` | `GET /k8s/{ClusterId}/user_config` |
| Update tags | `aliyun cs ModifyClusterTags` | `POST /clusters/{ClusterId}/tags` |
| Update deletion protection | `aliyun cs UpdateResourcesDeleteProtection` | `PUT /clusters/{ClusterId}/resources/protection` |
| Install addon | `aliyun cs InstallClusterAddons` | `POST /clusters/{ClusterId}/components/install` |
| Uninstall addon | `aliyun cs UnInstallClusterAddons` | `POST /clusters/{ClusterId}/components/uninstall` |
| List addons | `aliyun cs ListAddons` | `GET /addons` |
| **UpgradeCluster** | `aliyun cs UpgradeCluster` | `POST /api/v2/clusters/{ClusterId}/upgrade` — **DO NOT USE for ASK** |
| **Node pool operations** | (cluster node pool APIs) | **DO NOT USE for ASK** |

## SDK Package

```
github.com/alibabacloud-go/cs-20151215/v4/client
```

## CreateCluster (ASK) — VERIFIED Field Reference

> **Body shape** (verified from meta JSON):

```json
{
  "cluster_type": "ManagedKubernetes",
  "profile": "Serverless",
  "cluster_spec": "ack.standard",
  "name": "my-ask-cluster",
  "region_id": "cn-beijing",
  "vpcid": "vpc-xxxxxxxxx",
  "vswitch_ids": ["vsw-xxxxxxxxxa", "vsw-xxxxxxxxxb"],
  "container_cidr": "172.20.0.0/16",
  "service_cidr": "172.21.0.0/20",
  "is_enterprise_security_group": true,
  "snat_entry": true,
  "endpoint_public_access": false,
  "deletion_protection": true,
  "tags": [
    {"key": "env", "value": "prod"},
    {"key": "owner", "value": "platform"}
  ],
  "addons": [
    {
      "name": "terway-eniip",
      "config": ""
    },
    {
      "name": "csi-plugin",
      "config": ""
    },
    {
      "name": "csi-provisioner",
      "config": ""
    },
    {
      "name": "nginx-ingress-controller",
      "config": "{\"IngressSlbNetworkType\":\"internet\"}"
    }
  ],
  "controlplane_log_ttl": "30",
  "controlplane_log_components": ["apiserver", "kcm", "scheduler"],
  "kubernetes_version": "1.32.1-aliyun.1"
}
```

### Required (high confidence, verified)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Cluster name, 1-63 chars, not starting with `-` |
| `region_id` | string | e.g. `cn-beijing` |
| `vpcid` | string | VPC ID (**note: input field is `vpcid`, no separator**) |
| `vswitch_ids` | array of string | VSwitch IDs (recommend ≥ 2 for multi-AZ) |

### Cluster identity (for ASK, set these together)

| Field | Value | Required for ASK? |
|-------|-------|-------------------|
| `cluster_type` | `ManagedKubernetes` | **Yes — must be `ManagedKubernetes`** |
| `profile` | `Serverless` | **Yes — must be `Serverless` to identify ASK** |
| `cluster_spec` | `ack.standard` (default) or `ack.pro.small` / `ack.pro.xlarge` etc. | Optional, default `ack.standard` |

### Network (verified)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vswitch_ids` | array | — | **Required if not auto-creating VPC** |
| `container_cidr` | string | (Flannel) | Pod CIDR. **Flannel clusters must set this**; Terway ignores |
| `service_cidr` | string | `172.19.0.0/20` | Service CIDR |
| `security_group_id` | string | auto | Existing SG (mutually exclusive with `is_enterprise_security_group=true`) |
| `is_enterprise_security_group` | boolean | `true` | **Recommended for Terway** (default true) |
| `snat_entry` | boolean | `false` | **Set `true` if Pods need internet access** (auto-creates NAT + SNAT) |
| `zone_ids` | array | — | For auto-creating VPC across multiple AZs |
| `ip_stack` | enum | `ipv4` | `ipv4` or `dual` (IPv4/IPv6 dual stack) |
| `pod_vswitch_ids` | array | (deprecated) | ⚠️ **DEPRECATED** per OpenAPI spec — use `vswitch_ids` for Terway |

> **Network field for Terway-eniip (ASK default):** pass `vswitch_ids` only;
> do **NOT** pass `container_cidr` (Terway doesn't use it). The CLI's
> old `pod_vswitch_ids` field is marked deprecated in the OpenAPI spec.

### API server access (verified)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `endpoint_public_access` | boolean | `false` | Expose API server via EIP (default: VPC-only) |
| `load_balancer_id` | string | auto-create | Use existing CLB for API server |
| `control_plane_endpoints_config.internal_dns_config.bind_vpcs` | array | (current VPC) | Internal DNS resolution scope |
| `ssh_flags` | boolean | `false` | Public SSH to master (专有版 only; **N/A for ASK托管**) |

### Tags and metadata (verified)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tags` | array of `{key, value}` | (none) | Up to 20 tags |
| `resource_group_id` | string | default | Resource group |
| `deletion_protection` | boolean | `false` | **Recommended `true` for production** |
| `timezone` | string | system | e.g. `Asia/Shanghai` |
| `cluster_domain` | string | `cluster.local` | Cluster local domain |

### Addons (verified — array of objects)

```json
"addons": [
  { "name": "terway-eniip", "config": "" },
  { "name": "csi-plugin", "config": "" },
  { "name": "csi-provisioner", "config": "" },
  { "name": "nginx-ingress-controller", "config": "{\"IngressSlbNetworkType\":\"internet\"}" }
]
```

| Field | Required? | Description |
|-------|-----------|-------------|
| `name` | ✅ | Addon name (e.g. `terway-eniip`, `csi-plugin`, `nginx-ingress-controller`, `loongcollector`, `flannel`, `csi-provisioner`, `ack-node-problem-detector`) |
| `config` | (optional) | Addon-specific config (JSON string) |
| `version` | (optional) | Addon version (e.g. `v1.9.3-aliyun.1`) |
| `disabled` | (default) `false` | Set `true` to skip auto-install |

**Common addons for ASK:**
- **Network:** `terway-eniip` (default) or `flannel`
- **Storage:** `csi-plugin`, `csi-provisioner`
- **Logging:** `loongcollector` (with `sls_project_name` config)
- **Ingress:** `nginx-ingress-controller` (with `IngressSlbNetworkType`: `internet` / `intranet`)

### Security & audit (verified)

| Field | Type | Description |
|-------|------|-------------|
| `audit_log_config.enabled` | boolean | Enable K8s audit log |
| `audit_log_config.sls_project_name` | string | SLS project for audit logs (default `k8s-log-{clusterid}`) |
| `encryption_provider_key` | string | KMS key ID for data disk encryption |
| `rrsa_config.enabled` | boolean | RRSA功能 |
| `api_audiences` | string | Valid token audiences (comma-separated) |
| `extra_sans` | array | Custom API server cert SANs |
| `controlplane_log_ttl` | string | Days to retain control plane logs |
| `controlplane_log_project` | string | SLS project for control plane logs |
| `controlplane_log_components` | array | Components to collect (default: `apiserver`, `kcm`, `scheduler`, `ccm`) |

### Maintenance (verified)

| Field | Type | Description |
|-------|------|-------------|
| `maintenance_window.enable` | boolean | Enable maintenance window |
| `maintenance_window.maintenance_time` | string | RFC3339 start time |
| `maintenance_window.duration` | string | Duration (1-24h, default 3h) |
| `maintenance_window.weekly_period` | string | Days of week (default Thursday) |
| `operation_policy.cluster_auto_upgrade.enabled` | boolean | Auto-upgrade |
| `operation_policy.cluster_auto_upgrade.channel` | enum | `patch` / `stable` / `rapid` |

### Advanced (verified)

| Field | Type | Description |
|-------|------|-------------|
| `user_data` | (deprecated) | Custom node data (deprecated; **N/A for ASK**) |
| `runtime` | (deprecated) | Container runtime (deprecated; **N/A for ASK**) |
| `nodepools` | (N/A) | Node pools (**N/A for ASK**) |
| `control_plane_config` | (N/A) | Control plane config (专有版 only) |

## DescribeClusterDetail (ASK) — VERIFIED Response Fields

| JSON path | Type | Description |
|-----------|------|-------------|
| `$.cluster_id` | string | Cluster ID |
| `$.name` | string | Cluster name |
| `$.cluster_type` | string | `ManagedKubernetes` for ASK |
| `$.profile` | string | `Serverless` for ASK |
| `$.cluster_spec` | string | `ack.standard` etc. |
| `$.state` | enum | `initial` / `running` / `updating` / `deleting` / `failed` / `deleted` |
| `$.region_id` | string | Region |
| `$.current_version` | string | K8s version (managed by ACK) |
| `$.vpc_id` | string | **Note: response uses `vpc_id`** (camelCase), different from input `vpcid` |
| `$.vswitch_ids` | array | VSwitch IDs |
| `$.security_group_id` | string | SG ID |
| `$.is_enterprise_security_group` | boolean | Enterprise SG |
| `$.tags` | array | Resource tags |
| `$.deletion_protection` | boolean | Delete lock |
| `$.api_server.endpoint` | string | Public API server URL |
| `$.api_server.intranet_endpoint` | string | Internal API server URL |
| `$.api_server.api_server_eip_id` | string | Bound EIP for public access |
| `$.created` | string (ISO 8601) | Creation time |
| `$.updated` | string (ISO 8601) | Last update time |
| `$.resource_group_id` | string | Resource group |
| `$.control_plane_log` | object | Control plane log config |
| `$.maintenance_window` | object | Maintenance window |
| `$.operation_policy` | object | Auto operation policy |
| `$.cluster_domain` | string | Local domain |

> **Inconsistency to remember:** Input uses `vpcid`; response uses `vpc_id`.

## State Transitions

| Operation | Initial | Target | Poll Interval | Max Wait |
|-----------|---------|--------|---------------|----------|
| CreateCluster | — | `running` | 30s | 1800s (30min) |
| DeleteCluster | any stable | absent / 404 | 30s | 1800s (30min) |
| ModifyCluster (tags) | `running` | `running` | 5s | 60s |

## JIT Go SDK Pattern

```go
// Pseudocode — adapt to exact SDK method signatures after
// `go get github.com/alibabacloud-go/cs-20151215/v4/client`
package main

import (
    "fmt"
    "os"
    "github.com/alibabacloud-go/tea/tea"
    cs "github.com/alibabacloud-go/cs-20151215/v4/client"
    "github.com/alibabacloud-go/tea-openapi/service"
)

func newClient() (*cs.Client, error) {
    config := &service.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    return cs.NewClient(config)
}

func createASKCluster(c *cs.Client, name, vpcId string, vswitchIds []string) (string, error) {
    body := map[string]interface{}{
        "name":         name,
        "region_id":    os.Getenv("ALIBABA_CLOUD_REGION_ID"),
        "cluster_type": "ManagedKubernetes",   // <-- NOT "Ask"
        "profile":      "Serverless",          // <-- KEY field for ASK
        "vpcid":        vpcId,                 // <-- input field name
        "vswitch_ids":  vswitchIds,
        "deletion_protection": true,
        "snat_entry":   true,                  // <-- for Pod internet
        "addons": []map[string]interface{}{
            {"name": "terway-eniip", "config": ""},
            {"name": "csi-plugin", "config": ""},
            {"name": "csi-provisioner", "config": ""},
        },
    }
    resp, err := c.CreateCluster(body)
    if err != nil {
        return "", err
    }
    return *resp.Body.ClusterId, nil
}
```

> **Never log the SK or print the full config struct.**

## Pagination

`DescribeClustersV1` (and `DescribeClusters`) uses pagination. Page size
and page number parameters — verify exact names in your CLI version.

## Long-Running Operations

CreateCluster and DeleteCluster are async; poll `DescribeClusterDetail` for
state transitions.
