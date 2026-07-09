# Troubleshooting Alibaba Cloud SLB

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request failed validation | Align body with OpenAPI; check required fields |
| `InvalidParameter.RegionId` | Invalid region ID | Call DescribeRegions for valid regions |
| `InvalidParameter.VpcId` | VPC not found or not in region | Verify VPC via `alicloud-vpc-ops` |
| `InvalidParameter.VSwitchId` | VSwitch not found or not in VPC | Verify VSwitch via `alicloud-vpc-ops` |
| `LoadBalancerNotFound` / 404 | SLB instance does not exist | Verify LoadBalancerId; check region |
| `ListenerNotFound` / 404 | Listener does not exist | Verify ListenerPort and LoadBalancerId |
| `VServerGroupNotFound` / 404 | VServer group does not exist | Verify VServerGroupId |
| `CertificateNotFound` / 404 | Certificate does not exist | Verify ServerCertificateId |
| `AclNotFound` / 404 | ACL does not exist | Verify AclId |
| `RuleNotFound` / 404 | Forwarding rule does not exist | Verify RuleId |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | User adds RAM policy for slb:* actions |
| `Forbidden.LoadBalancerNotFound` | No permission on this SLB | Check RAM policy resource scope |
| `QuotaExceeded.LoadBalancer` | SLB instance quota exceeded | HALT; user raises quota or deletes unused |
| `QuotaExceeded.Listener` | Listener quota exceeded | HALT; user deletes unused listeners |
| `QuotaExceeded.VServerGroup` | VServer group quota exceeded | HALT; user deletes unused groups |
| `QuotaExceeded.Certificate` | Certificate quota exceeded | HALT; user deletes unused certificates |
| `QuotaExceeded.Acl` | ACL quota exceeded | HALT; user deletes unused ACLs |
| `LoadBalancerAlreadyExists` | Name or config conflict | Ask reuse vs new name |
| `ListenerAlreadyExists` | Port already in use | Use different port or modify existing |
| `ResourceInUse` | Resource is referenced by another | Remove dependencies first |
| `ResourceInUse.VServerGroup` | Group referenced by listener | Remove listener reference first |
| `ResourceInUse.Certificate` | Certificate referenced by HTTPS listener | Remove listener reference first |
| `ResourceInUse.Acl` | ACL referenced by listener | Remove listener reference first |
| `DeleteProtectionIsOn` | Deletion protection enabled | Disable via SetLoadBalancerDeleteProtection |
| `ModificationProtectionIsOn` | Modification protection enabled | Disable via SetLoadBalancerModificationProtection |
| `InvalidCertificate` | Certificate format invalid | Verify PEM format; check certificate chain |
| `InvalidPrivateKey` | Private key format invalid | Verify PEM format; check key matches certificate |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT; user adds funds |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After |
| `InternalError` / 5xx | Server-side error | Retry with backoff; then HALT with RequestId |
| `ServiceUnavailable` / 503 | Service temporarily unavailable | Retry after 10s; then HALT |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "无法访问网站" / "Connection refused" | Listener stopped or missing | Listener status + port |
| "502 Bad Gateway" | All backend servers unhealthy | DescribeHealthStatus |
| "504 Gateway Timeout" | Backend response too slow | Backend server performance + health check timeout |
| "HTTPS 证书错误" / "CERT_INVALID" | Certificate expired or mismatched | Certificate expiry + domain match |
| "SSL 握手失败" / "Handshake failed" | Certificate chain incomplete or protocol mismatch | Certificate chain + TLS version |
| "流量只打到一台服务器" | Weight imbalance or session persistence | Backend weights + StickySession |
| "部分用户无法访问" | ACL blocking or regional issue | ACL entries + source IP |
| "访问被拒绝" / "403 Forbidden" | ACL deny or backend auth issue | Listener ACL status + backend auth |
| "高延迟" / "响应慢" | Instance spec too small or backend slow | Instance spec + backend RT |
| "连接数突增后失败" | Connection limit exceeded | Instance spec + MaxConnection metric |
| "UDP 包丢失" | UDP health check failing | DescribeHealthStatus for UDP |
| "转发规则不生效" | Rule priority or URL pattern mismatch | Rule order + URL wildcard |
| "SLB IP ping 不通" | Intranet type or ICMP blocked | AddressType + network ACL |
| "后端服务器收不到真实 IP" | XForwardedFor disabled | Listener XForwardedFor setting |
| "证书即将过期告警" | Certificate expiry < 30 days | Certificate ExpireTime |
| "删除 SLB 失败" | DeleteProtection or dependencies | DeleteProtection + listener count |
| "修改配置失败" | ModificationProtection enabled | ModificationProtectionStatus |
| "新加的后端服务器没流量" | Weight=0 or health check failing | Weight + HealthStatus |
| "VServer Group 删除失败" | Referenced by listener | Listener VServerGroupId |
| "跨 VPC 访问不通" | VPC peering or routing missing | VPC route table + peering |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "用户无法访问服务" (Service Unreachable)

**Symptoms:** Browser/Client cannot connect to SLB IP:Port.

**Diagnostic Flow (execute in order, stop when root cause found):**

```bash
# Step 1: Check if SLB instance exists and is active
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --output cols=LoadBalancerStatus,Address,AddressType rows='{LoadBalancerStatus,Address,AddressType}'

# Expected: Status=active. If inactive → check if intentionally stopped.
# Expected: AddressType=internet for public access. If intranet → public cannot reach.

# Step 2: Check if listener exists and is running
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --output cols=ListenerPort,Protocol,Status rows=Listeners.Listener[].{ListenerPort,Protocol,Status}

# Expected: Status=running for the target port. If stopped → start listener.
# Expected: ListenerPort matches user access port.

# Step 3: Check backend server health
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=ServerId,Port,HealthStatus rows=BackendServers.BackendServer[].{ServerId,Port,HealthStatus}

# Expected: All backends show "normal". If "abnormal" → investigate backend.

# Step 4: Check if ACL is blocking
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --output cols=AclStatus,AclId rows=Listeners.Listener[].{AclStatus,AclId}

# If AclStatus=on → check ACL entries contain user's source IP.
```

**Decision Tree:**
- SLB status != `active` → Start SLB or investigate why stopped
- AddressType = `intranet` but user accesses from internet → Explain intranet limitation
- Listener status != `running` → Start listener
- All backends `abnormal` → Backend server issue (delegate to `alicloud-ecs-ops`)
- ACL blocking → Add user's IP to ACL or disable ACL
- All above normal → Check DNS / network path / security groups

---

### Scenario 2: "502 Bad Gateway / 504 Gateway Timeout"

**Symptoms:** HTTP status 502 or 504 from SLB.

**Diagnostic Flow:**

```bash
# Step 1: Check backend health status
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"

# Step 2: Check listener health check configuration
aliyun slb DescribeLoadBalancerHTTPListenerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=HealthCheck,HealthCheckDomain,HealthCheckURI,HealthCheckTimeout,HealthCheckInterval rows='{HealthCheck,HealthCheckDomain,HealthCheckURI,HealthCheckTimeout,HealthCheckInterval}'

# Step 3: Check backend server response time via CloudMonitor (if available)
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceUpstreamRt \
  --Dimensions '{"instanceId":"{{user.load_balancer_id}}","port":"{{user.listener_port}}","protocol":"http"}' \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Decision Tree:**
- All backends `abnormal` with 502 → Backend service crashed or port not listening
- HealthCheck=off with 502 → Backend may be intermittently failing; enable health check
- HealthCheckTimeout too low with 504 → Increase timeout; backend is slow
- Backend RT > 5000ms → Backend performance issue (delegate to `alicloud-ecs-ops`)
- Mixed normal/abnormal → Partial backend failure; investigate abnormal ones

---

### Scenario 3: "HTTPS 证书错误 / SSL 握手失败"

**Symptoms:** Browser shows certificate warning; SSL handshake fails.

**Diagnostic Flow:**

```bash
# Step 1: Check certificate details
aliyun slb DescribeServerCertificates \
  --RegionId "{{user.region}}" \
  --ServerCertificateId "{{user.certificate_id}}" \
  --output cols=ServerCertificateName,CommonName,ExpireTime,Fingerprint rows=ServerCertificates.ServerCertificate[].{ServerCertificateName,CommonName,ExpireTime,Fingerprint}

# Step 2: Check if certificate is expired
date -u +%s  # Current timestamp
# Compare with ExpireTime (convert to epoch)

# Step 3: Check listener certificate binding
aliyun slb DescribeLoadBalancerHTTPSListenerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=ServerCertificateId,CACertificateId rows='{ServerCertificateId,CACertificateId}'

# Step 4: Check if domain matches certificate CN
# User-provided domain vs CommonName from Step 1
```

**Decision Tree:**
- ExpireTime < now() → Certificate expired; upload new certificate
- CommonName != user domain → Certificate domain mismatch; upload correct cert
- ServerCertificateId on listener != expected → Wrong certificate bound
- Missing intermediate CA → Upload complete certificate chain

---

### Scenario 4: "流量不均 / 部分服务器无流量"

**Symptoms:** Traffic concentrated on subset of backends; some backends receive zero traffic.

**Diagnostic Flow:**

```bash
# Step 1: Check backend weights
aliyun slb DescribeVServerGroupAttribute \
  --VServerGroupId "{{user.vserver_group_id}}" \
  --output cols=ServerId,Weight,Port rows=BackendServers.BackendServer[].{ServerId,Weight,Port}

# Step 2: Check if session persistence causes stickiness
aliyun slb DescribeLoadBalancerHTTPListenerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=StickySession,StickySessionType,CookieTimeout rows='{StickySession,StickySessionType,CookieTimeout}'

# Step 3: Check backend health (unhealthy backends get no traffic)
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=ServerId,HealthStatus rows=BackendServers.BackendServer[].{ServerId,HealthStatus}

# Step 4: Check CloudMonitor for backend QPS distribution
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName BackendServerQps \
  --Dimensions '{"instanceId":"{{user.load_balancer_id}}","port":"{{user.listener_port}}","protocol":"http","backendServer":"{{user.backend_server_id}}"}'
```

**Decision Tree:**
- Weight=0 for some backends → Set weight > 0
- StickySession=on with few clients → Expected behavior; sticky sessions cause uneven distribution
- Some backends `abnormal` → Fix backend health; unhealthy backends receive no traffic
- All normal + wrr + StickySession=off → Check if backend count changed recently (new backends need time)

---

### Scenario 5: "高延迟 / 响应慢"

**Symptoms:** Slow response times; high RTT.

**Diagnostic Flow:**

```bash
# Step 1: Check SLB instance spec (may be undersized)
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --output cols=LoadBalancerSpec,Bandwidth rows='{LoadBalancerSpec,Bandwidth}'

# Step 2: Check connection metrics
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceMaxConnection \
  --Dimensions '{"instanceId":"{{user.load_balancer_id}}"}'

# Step 3: Check backend response time
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceUpstreamRt \
  --Dimensions '{"instanceId":"{{user.load_balancer_id}}","port":"{{user.listener_port}}","protocol":"http"}'

# Step 4: Check for connection drops
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceDropConnection \
  --Dimensions '{"instanceId":"{{user.load_balancer_id}}"}'
```

**Decision Tree:**
- Instance spec = slb.s1.small + high traffic → Upgrade spec
- Bandwidth < actual traffic → Increase bandwidth or switch to pay-by-traffic
- InstanceMaxConnection near spec limit → Upgrade spec or add more SLB instances
- InstanceUpstreamRt high → Backend performance issue
- InstanceDropConnection > 0 → Overload or backend rejecting connections

---

### Scenario 6: "新配置不生效 / 转发规则异常"

**Symptoms:** URL/domain routing not working as expected.

**Diagnostic Flow:**

```bash
# Step 1: Check forwarding rules
aliyun slb DescribeRules \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=RuleId,RuleName,Domain,Url,VServerGroupId rows=Rules.Rule[].{RuleId,RuleName,Domain,Url,VServerGroupId}

# Step 2: Check rule target vserver group
aliyun slb DescribeVServerGroupAttribute \
  --VServerGroupId "{{user.vserver_group_id}}" \
  --output cols=VServerGroupId,BackendServers rows='{VServerGroupId,BackendServers}'

# Step 3: Check if default listener config overrides rules
aliyun slb DescribeLoadBalancerHTTPListenerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --output cols=VServerGroupId rows='{VServerGroupId}'

# Step 4: Verify URL pattern matching
# Rules are evaluated in order; first match wins
# URL supports wildcards: /api/* matches /api/users, /api/orders, etc.
```

**Decision Tree:**
- Rule URL pattern doesn't match request → Correct URL pattern
- Rule Domain doesn't match Host header → Correct domain or use wildcard
- Rules evaluated in order; later rules shadowed → Reorder rules
- VServerGroupId in rule points to empty group → Add backends to target group
- Listener has VServerGroupId (default) + rules → Default group used when no rule matches

---

## Resource-Level Diagnostic Order

### SLB Instance Issues

1. Verify instance exists: `aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId <id>`
2. Check instance status: should be `active` for normal operation
3. Verify region and zone configuration
4. Check deletion/modification protection status
5. Verify VPC and VSwitch configuration

### Listener Issues

1. Verify listener exists: `aliyun slb DescribeLoadBalancerListeners --LoadBalancerId <id>`
2. Check listener status: should be `running`
3. Verify port is not conflicting with existing listeners
4. Check protocol-specific attributes (e.g., ServerCertificateId for HTTPS)
5. Verify health check configuration

### Backend Server Issues

1. Check backend server health status: `aliyun slb DescribeHealthStatus --LoadBalancerId <id> --ListenerPort <port>`
2. Verify backend servers are in the same region/VPC
3. Check security group rules allow traffic from SLB
4. Verify backend server ports are listening
5. Check backend server weights (0 = no traffic)

### Certificate Issues

1. Verify certificate exists: `aliyun slb DescribeServerCertificates --RegionId <region>`
2. Check certificate is not expired
3. Verify certificate and private key match
4. Ensure certificate is in valid PEM format
5. Check certificate is uploaded to the correct region

### ACL Issues

1. Verify ACL exists: `aliyun slb DescribeAccessControlLists --RegionId <region>`
2. Check ACL entries are valid IP/CIDR format
3. Verify ACL is associated with the correct listener
4. Check listener access control status is enabled

### High Latency / Connection Issues

1. Check instance spec — consider upgrading for high traffic
2. Verify bandwidth settings are not throttling
3. Check backend server response times
4. Review health check intervals (too frequent = overhead)
5. Consider enabling connection draining (if supported)

---

## One-Shot Diagnostic Scripts

### Script 1: Full SLB Health Check

Run this to get a comprehensive health overview of an SLB instance:

```bash
#!/bin/bash
# full-slb-health-check.sh
# Usage: ./full-slb-health-check.sh <LoadBalancerId> <RegionId>

LB_ID="$1"
REGION="$2"

echo "=== SLB Instance Status ==="
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "$LB_ID" \
  --output cols=LoadBalancerId,LoadBalancerStatus,Address,AddressType,LoadBalancerSpec,Bandwidth rows='{LoadBalancerId,LoadBalancerStatus,Address,AddressType,LoadBalancerSpec,Bandwidth}'

echo ""
echo "=== Listeners ==="
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=ListenerPort,Protocol,Status,Scheduler rows=Listeners.Listener[].{ListenerPort,Protocol,Status,Scheduler}

echo ""
echo "=== Backend Health (per listener) ==="
for port in $(aliyun slb DescribeLoadBalancerListeners --LoadBalancerId "$LB_ID" --output cols=ListenerPort rows=Listeners.Listener[].ListenerPort | tr ',' '\n'); do
  echo "-- Listener Port: $port --"
  aliyun slb DescribeHealthStatus \
    --LoadBalancerId "$LB_ID" \
    --ListenerPort "$port" \
    --output cols=ServerId,Port,HealthStatus rows=BackendServers.BackendServer[].{ServerId,Port,HealthStatus}
done

echo ""
echo "=== VServer Groups ==="
aliyun slb DescribeVServerGroups \
  --LoadBalancerId "$LB_ID" \
  --output cols=VServerGroupId,VServerGroupName rows=VServerGroups.VServerGroup[].{VServerGroupId,VServerGroupName}

echo ""
echo "=== Certificates ==="
aliyun slb DescribeServerCertificates \
  --RegionId "$REGION" \
  --output cols=ServerCertificateId,ServerCertificateName,ExpireTime rows=ServerCertificates.ServerCertificate[].{ServerCertificateId,ServerCertificateName,ExpireTime}
```

### Script 2: Listener Deep Inspection

Run this to inspect a specific listener in detail:

```bash
#!/bin/bash
# listener-deep-inspect.sh
# Usage: ./listener-deep-inspect.sh <LoadBalancerId> <ListenerPort>

LB_ID="$1"
PORT="$2"

echo "=== Listener Attribute ==="
# Try HTTP first, fallback to TCP
aliyun slb DescribeLoadBalancerHTTPListenerAttribute \
  --LoadBalancerId "$LB_ID" \
  --ListenerPort "$PORT" \
  --output cols=ListenerPort,Status,BackendServerPort,Bandwidth,Scheduler,StickySession,HealthCheck,XForwardedFor rows='{ListenerPort,Status,BackendServerPort,Bandwidth,Scheduler,StickySession,HealthCheck,XForwardedFor}' 2>/dev/null || \
aliyun slb DescribeLoadBalancerTCPListenerAttribute \
  --LoadBalancerId "$LB_ID" \
  --ListenerPort "$PORT" \
  --output cols=ListenerPort,Status,BackendServerPort,Bandwidth,Scheduler,PersistenceTimeout,HealthCheckType rows='{ListenerPort,Status,BackendServerPort,Bandwidth,Scheduler,PersistenceTimeout,HealthCheckType}'

echo ""
echo "=== Backend Health ==="
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "$LB_ID" \
  --ListenerPort "$PORT" \
  --output cols=ServerId,Port,HealthStatus rows=BackendServers.BackendServer[].{ServerId,Port,HealthStatus}

echo ""
echo "=== Forwarding Rules (HTTP/HTTPS only) ==="
aliyun slb DescribeRules \
  --LoadBalancerId "$LB_ID" \
  --ListenerPort "$PORT" \
  --output cols=RuleId,RuleName,Domain,Url,VServerGroupId rows=Rules.Rule[].{RuleId,RuleName,Domain,Url,VServerGroupId}
```

### Script 3: Certificate Expiry Audit

Run this to find certificates expiring soon:

```bash
#!/bin/bash
# cert-expiry-audit.sh
# Usage: ./cert-expiry-audit.sh <RegionId> [DaysThreshold]

REGION="$1"
DAYS="${2:-30}"
THRESHOLD=$(date -u -v+"${DAYS}"d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "+${DAYS} days" +%Y-%m-%dT%H:%M:%SZ)

echo "=== Certificates Expiring Within $DAYS Days ==="
aliyun slb DescribeServerCertificates \
  --RegionId "$REGION" \
  --output cols=ServerCertificateId,ServerCertificateName,CommonName,ExpireTime rows=ServerCertificates.ServerCertificate[].{ServerCertificateId,ServerCertificateName,CommonName,ExpireTime} | \
  awk -v threshold="$THRESHOLD" '
    BEGIN { FS="|"; print "ID|Name|CN|ExpireTime|Status" }
    NR>1 {
      if ($4 <= threshold) print $0 "|EXPIRING_SOON"
      else print $0 "|OK"
    }
  '
```

---

## Cross-Product Diagnostic Dependencies

When SLB troubleshooting requires checking other products:

| SLB Symptom | Cross-Product Check | Delegate To |
|-------------|---------------------|-------------|
| Backend `abnormal` | ECS instance status, security group | `alicloud-ecs-ops` |
| VPC/VSwitch not found | VPC configuration | `alicloud-vpc-ops` |
| Certificate upload fails | KMS or certificate service | `alicloud-kms-ops` (if present) |
| Metrics unavailable | CloudMonitor setup | `alicloud-cms-ops` |
| Access logs missing | OSS bucket configuration | `alicloud-oss-ops` |
| DNS resolution fails | DNS configuration | `alicloud-dns-ops` (if present) |

---

## RAM Policy Requirements

Minimal RAM policy for SLB operations:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "slb:Describe*",
        "slb:CreateLoadBalancer",
        "slb:DeleteLoadBalancer",
        "slb:SetLoadBalancer*",
        "slb:ModifyLoadBalancer*",
        "slb:CreateLoadBalancer*Listener",
        "slb:SetLoadBalancer*ListenerAttribute",
        "slb:DeleteLoadBalancerListener",
        "slb:StartLoadBalancerListener",
        "slb:StopLoadBalancerListener",
        "slb:CreateVServerGroup",
        "slb:DeleteVServerGroup",
        "slb:DescribeVServerGroup*",
        "slb:AddVServerGroupBackendServers",
        "slb:RemoveVServerGroupBackendServers",
        "slb:ModifyVServerGroupBackendServers",
        "slb:SetVServerGroupAttribute",
        "slb:AddBackendServers",
        "slb:RemoveBackendServers",
        "slb:SetBackendServers",
        "slb:DescribeHealthStatus",
        "slb:UploadServerCertificate",
        "slb:DeleteServerCertificate",
        "slb:DescribeServerCertificates",
        "slb:CreateAccessControlList",
        "slb:DeleteAccessControlList",
        "slb:DescribeAccessControlLists",
        "slb:AddAccessControlListEntry",
        "slb:RemoveAccessControlListEntry",
        "slb:CreateRules",
        "slb:DeleteRules",
        "slb:DescribeRules",
        "slb:SetRule"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Common CLI Errors

### `aliyun slb` command not found

```bash
# Verify CLI installation
aliyun version

# Reinstall if needed
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

### Authentication failures

```bash
# Verify credentials are set (existence check only, NEVER echo the actual value)
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "✅ AK ID is set" || echo "❌ AK ID is missing"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ Secret is set" || echo "❌ Secret is missing"
echo "Region: ${ALIBABA_CLOUD_REGION_ID}"
```

### JSON parsing errors

```bash
# Verify output is valid JSON
aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou | jq .

# If jq is not available, use Python
aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou | python3 -m json.tool
```