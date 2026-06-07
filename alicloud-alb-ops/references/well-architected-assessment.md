# Well-Architected Assessment — ALB

> **Purpose:** Five-pillar assessment patterns for ALB operations aligned with Alibaba Cloud Well-Architected Framework (卓越架构).
> **Version:** 1.0.0 | Last Updated: 2026-06-07

---

## 1. Framework Overview

| Pillar | Core Focus | ALB Relevance |
|--------|-----------|---------------|
| **安全 (Security)** | Identity, network, data security | IAM policies, HTTPS/SSL, ACLs, security policies, WAF |
| **稳定 (Stability)** | HA, DR, failure-oriented design | Multi-zone, health checks, connection draining, deletion protection |
| **成本 (Cost)** | Cost visibility, optimization | Edition selection, LCU optimization, idle resource detection |
| **效率 (Efficiency)** | DevOps, automation, incident response | AScript automation, tag-based management, access logs |
| **性能 (Performance)** | Scaling, observability, baselines | QPS monitoring, listener-level metrics, server group tuning |

---

## 2. 安全支柱 (Security)

### 2.1 IAM Requirements

| Operation | Required RAM Action | Resource Scope |
|-----------|--------------------|----------------|
| ListLoadBalancers | `alb:ListLoadBalancers` | `acs:alb:*:*:loadbalancer/*` |
| GetLoadBalancerAttribute | `alb:GetLoadBalancerAttribute` | `acs:alb:*:*:loadbalancer/{lbId}` |
| CreateLoadBalancer | `alb:CreateLoadBalancer` | `acs:alb:*:*:loadbalancer/*` |
| DeleteLoadBalancer | `alb:DeleteLoadBalancer` | `acs:alb:*:*:loadbalancer/{lbId}` |
| CreateListener | `alb:CreateListener` | `acs:alb:*:*:listener/*` |
| DeleteListener | `alb:DeleteListener` | `acs:alb:*:*:listener/{listenerId}` |
| CreateServerGroup | `alb:CreateServerGroup` | `acs:alb:*:*:servergroup/*` |
| AddServersToServerGroup | `alb:AddServersToServerGroup` | `acs:alb:*:*:servergroup/{sgId}` |
| DeleteServerGroup | `alb:DeleteServerGroup` | `acs:alb:*:*:servergroup/{sgId}` |
| CreateAcl | `alb:CreateAcl` | `acs:alb:*:*:acl/*` |
| DeleteAcl | `alb:DeleteAcl` | `acs:alb:*:*:acl/{aclId}` |

### 2.2 Network Security

- **VPC:** ALB requires VPC (no classic network). Ensure VPC network ACLs and security groups allow intended traffic.
- **Internet exposure:** For public ALBs, always enable deletion protection and use ACLs for IP restriction.
- **End-to-end encryption:** Use HTTPS listeners with TLS v1.2+ security policies for production.
- **Security groups:** Use `LoadBalancerJoinSecurityGroup` / `LeaveSecurityGroup` to control network access.

### 2.3 Data Security

- **Access logs:** Enable `EnableLoadBalancerAccessLog` with SLS for audit trail of all requests.
- **Certificate management:** Store SSL certificates in Alibaba Cloud Certificates Service (CAS) for rotation and management.
- **Credential handling:** Never expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in AScript content, logs, or trace output.

---

## 3. 稳定支柱 (Stability)

### 3.1 High Availability

- **Multi-zone:** Deploy ALB with at least 2 zones to survive zone-level failures. Use `UpdateLoadBalancerZones` to add zones.
- **Multi-listener:** Use separate listeners for different application tiers.
- **Multiple server groups:** Use multiple server groups with health checks for canary and blue-green deployments.

### 3.2 Failure-Oriented Design

| Scenario | Mitigation | Implementation |
|----------|-----------|---------------|
| Zone failure | Multi-zone deployment | 2+ ZoneMappings in CreateLoadBalancer |
| Backend server failure | Health checks + multiple servers | ≥ 2 servers per group with health check template |
| Listener failure | Redundant listeners | Secondary listener on different port |
| Traffic surge | Connection queue + Wrr scheduling | Scheduler: Wrr with appropriate weights |

### 3.3 Emergency Recovery

| Phase | Action | Method |
|-------|--------|--------|
| P1 (immediate) | Route traffic to standby server group | Update `UpdateRuleAttribute` to change `ForwardGroup` target |
| P2 (restore) | Restore primary server group health | Fix backend or add back via `AddServersToServerGroup` |
| P3 (verify) | Shift traffic back gradually | Update rule priority/weights |

### 3.4 Deletion Protection

- **Enable deletion protection on all production ALB instances** using `EnableDeletionProtection`.
- **Enable modification protection** to prevent accidental configuration changes.
- **Connection draining:** Configure `ConnectionDrainEnabled = true` with appropriate `ConnectionDrainTimeout` for graceful shutdown.

---

## 4. 成本支柱 (Cost)

### 4.1 Edition Selection

| Edition | Monthly Cost | Best For |
|---------|:-----------:|----------|
| Basic | Lowest | Simple HTTP/HTTPS routing, < 50 listeners, < 50 server groups |
| Standard | Medium | Full features, gRPC/QUIC, advanced routing |
| StandardWithWaf | Highest | WAF-integrated, security-sensitive production |

> **Rule:** Choose the minimum edition that meets feature requirements. Edition upgrades are allowed; downgrades are not.

### 4.2 LCU Optimization

- Monitor `LCUConsumption` metric (if available) or estimate using:
  - New connections/s × 25 connections/LCU
  - Active connections/min × 3,000 connections/LCU
  - Data transfer GB/h × 1 GB/LCU
  - Rule evaluations/s × 1,000 evaluations/LCU
- **Right-sizing:** If LCU consumption is consistently < 20% of provisioned capacity, consider consolidating ALBs.

### 4.3 Idle Resource Detection

| Pattern | Detection | Recommendation |
|---------|-----------|---------------|
| Zero QPS for > 7 days | `RequestCount` = 0 | Consider deleting or stopping listener |
| Low active connections (< 10 avg) | `ActiveConnection` < 10 | Evaluate if ALB is needed |
| Single-server server group | `ListServerGroupServers` returns 1 server | Add more servers for HA or remove server group |
| Unused listeners | `ListListeners` shows inactive listeners | Delete unused listeners |

---

## 5. 效率支柱 (Efficiency)

### 5.1 Automation Patterns

- **Tag all resources** with `Environment`, `Project`, `Owner`, `CostCenter` tags for automated management.
- **Use AScript rules** for custom request/response manipulation without modifying backend code.
- **Batch create rules** with `CreateRules` for efficient multi-rule deployment.

### 5.2 CI/CD Integration

- Use `CreateRules` / `UpdateRulesAttribute` for rule deployment as part of CI/CD pipeline.
- Use `ApplyHealthCheckTemplateToServerGroup` for standardized health checks across environments.
- Export forwarding rules as JSON/Infrastructure as Code before modifications.

### 5.3 Incident Response

- **Access logs** in SLS provide full request tracing for post-incident analysis.
- **CMS alerts** configured on `HealthyHostCount = 0` for immediate incident notification.
- **Diagnostic commands:**
  ```bash
  # Quick health check
  aliyun alb GetLoadBalancerAttribute --LoadBalancerId "{{lb_id}}" | jq '.LoadBalancer.LoadBalancerStatus'
  aliyun alb ListServerGroupServers --ServerGroupId "{{sg_id}}" | jq '.Servers[] | {server: .ServerId, status: .Status}'
  ```

---

## 6. 性能支柱 (Performance)

### 6.1 Key Performance Metrics

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| ResponseLatency P99 | > 2000ms | > 5000ms | Check backend performance |
| QPS per listener | > 80% of capacity | > 95% of capacity | Scale listener or add ALB |
| UnhealthyHostCount | > 20% of total | > 50% of total | Fix backend health |
| ActiveConnection | > 80% max | > 95% max | Scale out or optimize connections |
| NewConnection/s | > 80% of LCU | > 95% of LCU | Upgrade edition or optimize |

### 6.2 Auto-Scaling Recommendations

| Traffic Pattern | Action | Method |
|-----------------|--------|--------|
| Steady traffic increase | Upgrade to Standard edition | `UpdateLoadBalancerEdition` |
| Cyclical traffic spikes | Use Wrr with weights | Adjust server weights during peak |
| Rapid traffic surge | WAF/CDN pre-filtering | Integrate with WAF for DDoS protection |
| New service launch | Blue-green deployment | Create parallel server group, shift rules gradually |

### 6.3 Server Group Performance Tuning

| Scheduler | Best For | Notes |
|-----------|----------|-------|
| Wrr (Weighted Round Robin) | Servers with different capacities | Adjust weights to match server specs |
| Wlc (Weighted Least Connections) | Variable-length requests | Balances load by active connections |
| Sch (Consistent Hash) | Session-persistent workloads | Uses hash key for deterministic routing |

### 6.4 Performance Baseline

Establish baselines using CloudMonitor:

```bash
# Get baseline QPS (past 7 days)
aliyun cms DescribeMetricList --Namespace acs_alb --MetricName QPS \
  --Dimensions "[{\\"LoadBalancerId\\":\\"{{lb_id}}\\"}]" \
  --StartTime "{{7_days_ago}}" --EndTime "{{now}}" | jq '.Datapoints[] | .Average' | sort -n | tail -5

# Get baseline latency
aliyun cms DescribeMetricList --Namespace acs_alb --MetricName ResponseLatency \
  --Dimensions "[{\\"LoadBalancerId\\":\\"{{lb_id}}\\"}]" \
  --StartTime "{{7_days_ago}}" --EndTime "{{now}}" | jq '.Datapoints[] | .Maximum' | sort -n | tail -5
```

---

## 7. Assessment Checklist

- [ ] **IAM:** RAM policies scoped to minimum required operations
- [ ] **Network:** ALB deployed in VPC with proper security groups
- [ ] **Encryption:** HTTPS listeners with TLS v1.2+ security policies for production
- [ ] **Multi-AZ:** ALB deployed in ≥ 2 zones
- [ ] **Health Checks:** Valid health check templates applied to all server groups
- [ ] **Deletion Protection:** Enabled on all production ALB instances
- [ ] **Connection Draining:** Configured for graceful backend removal
- [ ] **Access Logs:** Enabled with SLS for audit trail
- [ ] **Monitoring:** CMS alarms configured for key metrics (HealthyHostCount=0, 5XX rate, latency)
- [ ] **Cost Optimization:** Edition matches workload requirements, idle resources identified
- [ ] **Tagging:** Tags applied for cost allocation and resource management
- [ ] **Backup:** Forwarding rules/config exported as JSON before modifications
- [ ] **Credentials:** Secret access key never appears in logs, commands, or AScript content