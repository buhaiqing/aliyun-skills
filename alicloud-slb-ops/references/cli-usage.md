# CLI — Alibaba Cloud SLB (`aliyun slb`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| CreateLoadBalancer | yes | Full support |
| DescribeLoadBalancers | yes | Full support with pagination |
| DescribeLoadBalancerAttribute | yes | Full support |
| SetLoadBalancerStatus | yes | Full support |
| SetLoadBalancerName | yes | Full support |
| ModifyLoadBalancerInstanceSpec | yes | Full support |
| DeleteLoadBalancer | yes | Full support |
| CreateLoadBalancerTCPListener | yes | Full support |
| CreateLoadBalancerUDPListener | yes | Full support |
| CreateLoadBalancerHTTPListener | yes | Full support |
| CreateLoadBalancerHTTPSListener | yes | Full support |
| DescribeLoadBalancerListeners | yes | Full support |
| DescribeLoadBalancerTCPListenerAttribute | yes | Full support |
| DescribeLoadBalancerUDPListenerAttribute | yes | Full support |
| DescribeLoadBalancerHTTPListenerAttribute | yes | Full support |
| DescribeLoadBalancerHTTPSListenerAttribute | yes | Full support |
| SetLoadBalancerTCPListenerAttribute | yes | Full support |
| SetLoadBalancerUDPListenerAttribute | yes | Full support |
| SetLoadBalancerHTTPListenerAttribute | yes | Full support |
| SetLoadBalancerHTTPSListenerAttribute | yes | Full support |
| DeleteLoadBalancerListener | yes | Full support |
| StartLoadBalancerListener | yes | Full support |
| StopLoadBalancerListener | yes | Full support |
| CreateVServerGroup | yes | Full support |
| DescribeVServerGroups | yes | Full support |
| DescribeVServerGroupAttribute | yes | Full support |
| AddVServerGroupBackendServers | yes | Full support |
| RemoveVServerGroupBackendServers | yes | Full support |
| ModifyVServerGroupBackendServers | yes | Full support |
| SetVServerGroupAttribute | yes | Full support |
| DeleteVServerGroup | yes | Full support |
| AddBackendServers | yes | Full support |
| RemoveBackendServers | yes | Full support |
| SetBackendServers | yes | Full support |
| DescribeHealthStatus | yes | Full support |
| UploadServerCertificate | yes | Full support |
| UploadCACertificate | yes | Full support |
| DescribeServerCertificates | yes | Full support |
| DescribeCACertificates | yes | Full support |
| DeleteServerCertificate | yes | Full support |
| DeleteCACertificate | yes | Full support |
| CreateAccessControlList | yes | Full support |
| DescribeAccessControlLists | yes | Full support |
| DescribeAccessControlListAttribute | yes | Full support |
| AddAccessControlListEntry | yes | Full support |
| RemoveAccessControlListEntry | yes | Full support |
| DeleteAccessControlList | yes | Full support |
| CreateRules | yes | Full support |
| DescribeRules | yes | Full support |
| DescribeRuleAttribute | yes | Full support |
| SetRule | yes | Full support |
| DeleteRules | yes | Full support |
| DescribeRegions | yes | Full support |
| DescribeZones | yes | Full support |
| DescribeAvailableResource | yes | Full support |

> SLB is fully supported by the `aliyun` CLI. No SDK-only operations for basic CRUD.

## Command Map

### Instance Operations

```bash
# Create SLB instance
aliyun slb CreateLoadBalancer \
  --RegionId cn-hangzhou \
  --LoadBalancerName my-slb \
  --AddressType internet \
  --VpcId vpc-bp67acfmxazb4ph*** \
  --VSwitchId vsw-bp67acfmxazb4ph*** \
  --Bandwidth 10 \
  --LoadBalancerSpec slb.s1.small

# Describe all SLB instances
aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou

# Describe specific instance
aliyun slb DescribeLoadBalancers \
  --RegionId cn-hangzhou \
  --LoadBalancerId lb-bp67acfmxazb4ph***

# Extract fields with JMESPath
aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou \
  --output cols=LoadBalancerId,LoadBalancerStatus,Address rows=LoadBalancers.LoadBalancer[].{LoadBalancerId,LoadBalancerStatus,Address}

# Describe instance attribute (detailed)
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId lb-bp67acfmxazb4ph***

# Set instance status
aliyun slb SetLoadBalancerStatus \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --LoadBalancerStatus inactive

# Rename instance
aliyun slb SetLoadBalancerName \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --LoadBalancerName new-name

# Modify instance spec
aliyun slb ModifyLoadBalancerInstanceSpec \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --LoadBalancerSpec slb.s2.small

# Enable deletion protection
aliyun slb SetLoadBalancerDeleteProtection \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --DeleteProtection on

# Delete instance
aliyun slb DeleteLoadBalancer \
  --LoadBalancerId lb-bp67acfmxazb4ph***
```

### Listener Operations

```bash
# Create TCP listener
aliyun slb CreateLoadBalancerTCPListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 443 \
  --BackendServerPort 443 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --HealthCheckType tcp \
  --PersistenceTimeout 3600

# Create HTTP listener
aliyun slb CreateLoadBalancerHTTPListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80 \
  --BackendServerPort 8080 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --StickySession off \
  --HealthCheck on \
  --XForwardedFor on

# Create HTTPS listener
aliyun slb CreateLoadBalancerHTTPSListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 443 \
  --BackendServerPort 8080 \
  --Bandwidth -1 \
  --Scheduler wrr \
  --ServerCertificateId 12315790855291**_166f8204689_1714763408_709595**** \
  --StickySession off \
  --HealthCheck on \
  --XForwardedFor on

# Describe all listeners
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId lb-bp67acfmxazb4ph***

# Describe TCP listener attribute
aliyun slb DescribeLoadBalancerTCPListenerAttribute \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 443

# Start listener
aliyun slb StartLoadBalancerListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80

# Stop listener
aliyun slb StopLoadBalancerListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80

# Delete listener
aliyun slb DeleteLoadBalancerListener \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80
```

### VServer Group Operations

```bash
# Create vserver group
aliyun slb CreateVServerGroup \
  --RegionId cn-hangzhou \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --VServerGroupName web-servers \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Weight":"100","Type":"ecs","Port":"80"}]'

# Describe vserver groups
aliyun slb DescribeVServerGroups \
  --LoadBalancerId lb-bp67acfmxazb4ph***

# Describe vserver group attribute
aliyun slb DescribeVServerGroupAttribute \
  --VServerGroupId rsp-bp67acfmxazb4ph***

# Add backend servers to group
aliyun slb AddVServerGroupBackendServers \
  --VServerGroupId rsp-bp67acfmxazb4ph*** \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Weight":"50","Type":"ecs","Port":"80"}]'

# Remove backend servers from group
aliyun slb RemoveVServerGroupBackendServers \
  --VServerGroupId rsp-bp67acfmxazb4ph*** \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Port":"80"}]'

# Delete vserver group
aliyun slb DeleteVServerGroup \
  --VServerGroupId rsp-bp67acfmxazb4ph***
```

### Backend Server Operations (Default Group)

```bash
# Add backend servers to default group
aliyun slb AddBackendServers \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Weight":"100"}]'

# Remove backend servers
aliyun slb RemoveBackendServers \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --BackendServers '["i-bp67acfmxazb4ph***"]'

# Set backend server weights
aliyun slb SetBackendServers \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Weight":"50"}]'

# Describe health status
aliyun slb DescribeHealthStatus \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80
```

### Certificate Operations

```bash
# Upload server certificate
aliyun slb UploadServerCertificate \
  --RegionId cn-hangzhou \
  --ServerCertificateName my-cert \
  --ServerCertificate "-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWg...\n-----END CERTIFICATE-----" \
  --PrivateKey "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"

# Describe server certificates
aliyun slb DescribeServerCertificates --RegionId cn-hangzhou

# Delete server certificate
aliyun slb DeleteServerCertificate \
  --ServerCertificateId 12315790855291**_166f8204689_1714763408_709595****
```

### ACL Operations

```bash
# Create ACL
aliyun slb CreateAccessControlList \
  --RegionId cn-hangzhou \
  --AclName office-networks

# Describe ACLs
aliyun slb DescribeAccessControlLists --RegionId cn-hangzhou

# Add ACL entries
aliyun slb AddAccessControlListEntry \
  --AclId acl-bp67acfmxazb4ph*** \
  --AclEntrys '[{"entry":"10.0.0.0/8","comment":"office"},{"entry":"172.16.0.0/12","comment":"datacenter"}]'

# Remove ACL entries
aliyun slb RemoveAccessControlListEntry \
  --AclId acl-bp67acfmxazb4ph*** \
  --AclEntrys '[{"entry":"10.0.0.0/8"}]'

# Delete ACL
aliyun slb DeleteAccessControlList \
  --AclId acl-bp67acfmxazb4ph***
```

### Forwarding Rule Operations

```bash
# Create forwarding rules
aliyun slb CreateRules \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80 \
  --RuleList '[{"RuleName":"api-rule","Domain":"api.example.com","Url":"/api/*","VServerGroupId":"rsp-bp67acfmxazb4ph***"}]'

# Describe rules
aliyun slb DescribeRules \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --ListenerPort 80

# Delete rules
aliyun slb DeleteRules \
  --RuleIds '["rule-bp67acfmxazb4ph***"]'
```

### Region/Zone Operations

```bash
# Describe regions
aliyun slb DescribeRegions

# Describe zones
aliyun slb DescribeZones --RegionId cn-hangzhou

# Describe available resources
aliyun slb DescribeAvailableResource --RegionId cn-hangzhou
```

## Polling with Waiter

```bash
# Wait for SLB to be active
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --waiter expr='LoadBalancerStatus' to=active timeout=120 interval=5
```

> **Note:** `--waiter` may not be available in all `aliyun` CLI versions. Use the
> manual polling loop below as a universal fallback:

```bash
# Manual polling for SLB status (universal compatibility)
for i in $(seq 1 24); do
  STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
    --LoadBalancerId lb-bp67acfmxazb4ph*** \
    --output cols=LoadBalancerStatus rows=LoadBalancerStatus)
  echo "Attempt $i: Status=$STATUS"
  [ "$STATUS" = "active" ] && break
  sleep 5
done
```
