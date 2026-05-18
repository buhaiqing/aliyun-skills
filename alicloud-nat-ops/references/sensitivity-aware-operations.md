# Sensitivity-Aware Operations — NAT Gateway

> **Purpose:** Differentiated operation strategies based on system sensitivity levels. Sensitive systems require stricter change controls, approval gates, rollback plans, and monitoring.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-19
> **Reference:** [阿里云卓越架构 - 安全支柱 & 稳定支柱](https://help.aliyun.com/zh/product/2362200.html)

---

## 1. System Sensitivity Classification

### 1.1 Sensitivity Levels

| Level | Name | Examples | Data Classification | Impact of Outage |
|-------|------|----------|-------------------|-----------------|
| **L0** | 核心生产 (Mission-Critical) | 金融交易、政务核心、医疗HIS | 绝密/机密 | 业务停摆，监管处罚，生命安全 |
| **L1** | 生产 (Production) | 电商、SaaS、企业应用 | 秘密/内部 | 收入损失，客户投诉 |
| **L2** | 预发 (Staging) | UAT 环境、灰度环境 | 内部 | 影响有限，可快速恢复 |
| **L3** | 开发/测试 (Dev/Test) | 开发环境、CI/CD | 公开 | 无业务影响 |

### 1.2 NAT Gateway Sensitivity Tagging

**MUST tag NAT Gateways with sensitivity level:**

```bash
# Tag NAT Gateway with sensitivity level
aliyun vpc TagResources \
  --ResourceType natgateway \
  --ResourceId.1 "{{user.nat_gateway_id}}" \
  --Tag.1.Key="SensitivityLevel" \
  --Tag.1.Value="L0"

# Tag with environment
aliyun vpc TagResources \
  --ResourceType natgateway \
  --ResourceId.1 "{{user.nat_gateway_id}}" \
  --Tag.1.Key="Environment" \
  --Tag.1.Value="production"
```

### 1.3 Query NAT Gateways by Sensitivity

```bash
# List all L0 NAT Gateways
aliyun vpc DescribeNatGateways \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --Tag.1.Key="SensitivityLevel" \
  --Tag.1.Value="L0"
```

---

## 2. Change Control by Sensitivity Level

### 2.1 Operation Risk Matrix

| Operation | L0 | L1 | L2 | L3 |
|-----------|----|----|----|----|
| DescribeNatGateways | ✅ Auto | ✅ Auto | ✅ Auto | ✅ Auto |
| DescribeSnatTableEntries | ✅ Auto | ✅ Auto | ✅ Auto | ✅ Auto |
| DescribeForwardTableEntries | ✅ Auto | ✅ Auto | ✅ Auto | ✅ Auto |
| ModifyNatGatewayAttribute (name) | ⚠️ Change Window | ⚠️ Change Window | ✅ Auto | ✅ Auto |
| ModifyNatGatewaySpec | 🚫 CAB Approval | ⚠️ Change Window | ⚠️ Notify | ✅ Auto |
| CreateSnatEntry | ⚠️ Change Window | ⚠️ Notify | ✅ Auto | ✅ Auto |
| DeleteSnatEntry | 🚫 CAB Approval | ⚠️ Change Window | ⚠️ Notify | ✅ Auto |
| CreateForwardEntry | 🚫 CAB Approval | ⚠️ Change Window | ✅ Auto | ✅ Auto |
| DeleteForwardEntry | 🚫 CAB Approval | ⚠️ Change Window | ⚠️ Notify | ✅ Auto |
| CreateNatGateway | 🚫 CAB Approval | ⚠️ Change Window | ✅ Auto | ✅ Auto |
| DeleteNatGateway | 🚫 CAB Approval + Dual Confirm | 🚫 CAB Approval | ⚠️ Change Window | ✅ Auto |

**Legend:**
- ✅ Auto: Agent can execute directly
- ⚠️ Notify: Notify ops team, proceed after 5 min
- ⚠️ Change Window: Only during approved change window
- 🚫 CAB Approval: Must get Change Advisory Board approval first

### 2.2 Change Window Policy

| Sensitivity | Allowed Change Window | Blackout Period | Emergency Override |
|------------|----------------------|-----------------|-------------------|
| **L0** | Tue-Thu 02:00-05:00 | Mon/Fri/Weekend/Holidays | CTO + on-call approval |
| **L1** | Mon-Fri 22:00-06:00 | Month-end / Campaign days | Team lead + on-call approval |
| **L2** | Any time, notify team | None | N/A |
| **L3** | Any time | None | N/A |

### 2.3 Change Window Validation (Agent-Readable)

```bash
# Check if current time is within change window for L0
CURRENT_HOUR=$(date +%H)
CURRENT_DAY=$(date +%u)  # 1=Mon, 5=Fri

if [ "$CURRENT_DAY" -ge 2 ] && [ "$CURRENT_DAY" -le 4 ] && [ "$CURRENT_HOUR" -ge 2 ] && [ "$CURRENT_HOUR" -lt 5 ]; then
  echo "✅ Within L0 change window"
else
  echo "🚫 Outside L0 change window. HALT operation."
fi
```

---

## 3. Pre-Change Safety Gates

### 3.1 Configuration Snapshot (L0/L1 Mandatory)

Before any modifying operation on L0/L1 NAT Gateways, **MUST** capture a configuration snapshot:

```bash
NAT_ID="{{user.nat_gateway_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
SNAPSHOT_TIME=$(date +%Y%m%d-%H%M%S)

# Snapshot NAT Gateway config
aliyun vpc DescribeNatGateways \
  --RegionId $REGION \
  --NatGatewayId $NAT_ID > "/tmp/nat-snapshot-${NAT_ID}-${SNAPSHOT_TIME}.json"

# Snapshot SNAT entries
aliyun vpc DescribeSnatTableEntries \
  --RegionId $REGION \
  --NatGatewayId $NAT_ID > "/tmp/nat-snat-snapshot-${NAT_ID}-${SNAPSHOT_TIME}.json"

# Snapshot DNAT entries
aliyun vpc DescribeForwardTableEntries \
  --RegionId $REGION \
  --NatGatewayId $NAT_ID > "/tmp/nat-dnat-snapshot-${NAT_ID}-${SNAPSHOT_TIME}.json"
```

### 3.2 Impact Assessment (L0/L1 Mandatory)

Before modifying L0/L1 NAT Gateways, **MUST** assess blast radius:

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| Affected SNAT entries count | DescribeSnatTableEntries | Document count; estimate affected instances |
| Affected DNAT entries count | DescribeForwardTableEntries | Document count; estimate affected services |
| Associated EIP count | DescribeEipAddresses | Document count; estimate cost impact |
| VPC dependency | DescribeVpcs | Identify all VPCs using this NAT |
| Cross-skill dependencies | Check delegation matrix | Identify downstream services |

### 3.3 Approval Gate Template (L0/L1)

```yaml
change_request:
  nat_gateway_id: "{{user.nat_gateway_id}}"
  sensitivity_level: "L0"
  operation: "ModifyNatGatewaySpec"
  change_window: "2026-05-20 02:00-05:00"
  
  impact_assessment:
    affected_snat_entries: 15
    affected_dnat_entries: 8
    affected_eips: 4
    affected_vpcs: ["vpc-prod-001"]
    downstream_services: ["web-app", "api-gateway", "payment-service"]
  
  rollback_plan:
    method: "Restore from snapshot"
    snapshot_files:
      - "/tmp/nat-snapshot-{{nat_id}}-{{timestamp}}.json"
      - "/tmp/nat-snat-snapshot-{{nat_id}}-{{timestamp}}.json"
      - "/tmp/nat-dnat-snapshot-{{nat_id}}-{{timestamp}}.json"
    estimated_rollback_time: "5 min"
  
  approval:
    cab_approved: false
    approver: ""
    approved_at: ""
```

---

## 4. Rollback Procedures by Sensitivity

### 4.1 Rollback Strategy Matrix

| Operation | L0 Rollback | L1 Rollback | L2/L3 Rollback |
|-----------|-------------|-------------|----------------|
| ModifyNatGatewaySpec | Revert spec from snapshot | Revert spec | Revert spec |
| CreateSnatEntry | DeleteSnatEntry | DeleteSnatEntry | DeleteSnatEntry |
| DeleteSnatEntry | Recreate from snapshot | Recreate from snapshot | Recreate from snapshot |
| CreateForwardEntry | DeleteForwardEntry | DeleteForwardEntry | DeleteForwardEntry |
| DeleteForwardEntry | Recreate from snapshot | Recreate from snapshot | Recreate from snapshot |
| DeleteNatGateway | **Irreversible** — MUST have CAB + dual confirm | Recreate + reconfigure from snapshot | Recreate + reconfigure |

### 4.2 L0 Rollback Runbook

```yaml
Phase 1: Detect Failure (0-2 min)
  - Monitor CMS metrics: ActiveConnection, NewConnection, DropConnection
  - If error rate > 5% or connection drop > 10% → trigger rollback
  - Alert on-call team immediately

Phase 2: Execute Rollback (2-5 min)
  - Load snapshot files from pre-change backup
  - For spec change: revert to original spec
    aliyun vpc ModifyNatGatewaySpec --NatSpec "<original_spec>"
  - For deleted SNAT: recreate from snapshot
    aliyun vpc CreateSnatEntry --SourceCIDR "<original_cidr>" --SnatIp "<original_ip>"
  - For deleted DNAT: recreate from snapshot
    aliyun vpc CreateForwardEntry --ExternalIp "<original_eip>" --ExternalPort "<original_port>" ...

Phase 3: Validate Recovery (5-10 min)
  - Verify NAT Gateway status = Available
  - Verify SNAT/DNAT entry count matches snapshot
  - Verify CMS metrics return to baseline
  - Test connectivity: internal → internet (SNAT), internet → internal (DNAT)

Phase 4: Post-Rollback (10-30 min)
  - Document rollback reason and timeline
  - Schedule root cause analysis
  - Update change request with rollback outcome
```

### 4.3 Automated Rollback Trigger (L0)

```bash
# Monitor NAT health after change; auto-rollback if degraded
NAT_ID="{{user.nat_gateway_id}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
BASELINE_DROP=$(cat /tmp/nat-baseline-drop-${NAT_ID}.txt)

# Check current DropConnection rate
CURRENT_DROP=$(aliyun cms QueryMetricList \
  --Namespace acs_nat \
  --MetricName DropConnection \
  --Period 60 \
  --Dimensions "[{\"instanceId\":\"${NAT_ID}\"}]" \
  --output cols=Maximum rows=Datapoints[0].Maximum 2>/dev/null | tail -1)

if [ "${CURRENT_DROP:-0}" -gt "$((BASELINE_DROP * 3))" ]; then
  echo "🚨 ROLLBACK TRIGGERED: DropConnection ${CURRENT_DROP} > 3x baseline ${BASELINE_DROP}"
  # Execute rollback per §4.2
fi
```

---

## 5. Canary / Gradual Rollout (L0/L1)

### 5.1 SNAT Canary Strategy

When adding/modifying SNAT on L0/L1 NAT Gateways, use gradual rollout:

| Step | Action | Scope | Hold Time | Success Criteria |
|------|--------|-------|-----------|-----------------|
| 1 | Create SNAT for single CIDR | /32 (single IP) | 10 min | No connection errors |
| 2 | Expand SNAT to /28 | 16 IPs | 15 min | No connection errors |
| 3 | Expand SNAT to /24 | 256 IPs | 15 min | No connection errors |
| 4 | Full SNAT scope | Target CIDR | — | Stable for 30 min |

### 5.2 DNAT Canary Strategy

When creating DNAT on L0/L1 NAT Gateways:

| Step | Action | Hold Time | Success Criteria |
|------|--------|-----------|-----------------|
| 1 | Create DNAT on non-critical port first | 10 min | External connectivity verified |
| 2 | Create DNAT on target port | 10 min | Service accessible from internet |
| 3 | Monitor traffic for anomalies | 30 min | No error spike, no security alerts |
| 4 | Mark change as complete | — | All checks pass |

### 5.3 Spec Change Canary (L0)

When changing NAT spec on L0:

| Step | Action | Monitor | Rollback Trigger |
|------|--------|---------|-----------------|
| 1 | Change spec during change window | CU utilization, connection count | CU > 90% or connection drop > 5% |
| 2 | Monitor 15 min | All CMS metrics | Any metric > 2x baseline |
| 3 | Monitor 1 hour | All CMS metrics | Any metric > 1.5x baseline |
| 4 | Mark change as stable | — | — |

---

## 6. Monitoring Intensity by Sensitivity

### 6.1 Monitoring Escalation

| Metric | L0 Frequency | L1 Frequency | L2 Frequency | L3 Frequency |
|--------|-------------|-------------|-------------|-------------|
| ActiveConnection | Every 30s | Every 1min | Every 5min | On-demand |
| DropConnection | Every 30s | Every 1min | Every 5min | On-demand |
| OutRatePercent | Every 1min | Every 5min | Every 15min | On-demand |
| InRatePercent | Every 1min | Every 5min | Every 15min | On-demand |
| NewConnection | Every 30s | Every 1min | Every 5min | On-demand |

### 6.2 Alert Escalation

| Sensitivity | Warning Response | Critical Response | Escalation |
|------------|-----------------|------------------|-----------|
| **L0** | < 5 min, on-call page | < 1 min, auto-page + manager | 15 min → CTO |
| **L1** | < 15 min, on-call notify | < 5 min, on-call page | 30 min → Team lead |
| **L2** | < 30 min, team chat | < 15 min, on-call notify | 1 hour → Manager |
| **L3** | Next business day | < 1 hour, team chat | N/A |

### 6.3 Post-Change Monitoring (L0/L1)

After any change on L0/L1 NAT Gateways, **MUST** monitor for:

| Time Window | Metrics to Watch | Alert Threshold |
|-------------|-----------------|-----------------|
| 0-15 min | DropConnection, ActiveConnection, NewConnection | > 2x baseline |
| 15-60 min | All CMS metrics + error rate | > 1.5x baseline |
| 1-24 hours | All CMS metrics | > 1.2x baseline |
| 24-72 hours | All CMS metrics | Return to baseline |

---

## 7. Compliance & Audit for Sensitive Systems

### 7.1 L0/L1 Mandatory Compliance

| Requirement | L0 | L1 | Implementation |
|-------------|----|----|---------------|
| All changes logged to ActionTrail | ✅ | ✅ | Delegate to `alicloud-actiontrail-ops` |
| Configuration snapshots before changes | ✅ | ✅ | §3.1 Snapshot procedure |
| CAB approval for destructive ops | ✅ | ✅ (Delete only) | §2.1 Risk matrix |
| Change window compliance | ✅ | ✅ | §2.2 Change window policy |
| Rollback plan documented | ✅ | ✅ | §4.2 Rollback runbook |
| Post-change monitoring | ✅ | ⚠️ (30 min) | §6.3 Post-change monitoring |
| Dual confirmation for delete | ✅ | ⚠️ (Notify) | §2.1 Risk matrix |
| Incident response runbook | ✅ | ⚠️ | [Security Enhancement §7](security-enhancement.md#7-security-incident-response) |

### 7.2 Regulatory Requirements by Industry

| Industry | Regulation | NAT-Specific Requirements |
|----------|-----------|--------------------------|
| 金融 (Finance) | 等保三级, PCI-DSS | DNAT 禁止暴露数据库端口; 所有 NAT 操作审计保留 180 天; 变更需双人复核 |
| 政务 (Government) | 等保三级, 密码法 | NAT 必须使用国密算法; VPC 隔离; 操作审计保留 365 天 |
| 医疗 (Healthcare) | 等保三级, HIPAA | DNAT 禁止暴露 HIS 端口; 数据传输加密; 审计保留 365 天 |
| 电商 (E-commerce) | 等保二级, PCI-DSS (支付) | DNAT 仅允许 80/443; 支付系统独立 NAT; 操作审计保留 90 天 |

---

## 8. Emergency Override Procedure

### 8.1 When Emergency Override is Needed

Emergency override allows bypassing change window restrictions for critical incidents.

| Trigger | L0 Override Authority | L1 Override Authority |
|---------|----------------------|----------------------|
| NAT Gateway down (all traffic blocked) | On-call + CTO verbal approval | On-call + Team lead approval |
| Security breach (port exposed) | On-call auto-approve, retroactive CAB | On-call auto-approve |
| DNAT/SNAT misconfiguration causing outage | On-call + Manager approval | On-call approval |

### 8.2 Emergency Override Runbook

```yaml
Phase 1: Declare Emergency (0-2 min)
  - Identify severity and sensitivity level
  - Notify required approver (per §8.1)
  - Get verbal/electronic approval
  - Record approval in change request

Phase 2: Execute Emergency Change (2-10 min)
  - Capture snapshot (even in emergency)
  - Execute change with maximum caution
  - Enable enhanced monitoring (L0: 30s interval)

Phase 3: Post-Emergency (10-60 min)
  - Verify change is successful
  - Document emergency change in CAB system
  - Schedule retrospective within 24 hours
  - Update runbook if needed
```

---

## 9. Cross-Skill Delegation for Sensitive Systems

| Scenario | Primary Skill | Delegated Skill | Sensitivity Consideration |
|----------|--------------|-----------------|--------------------------|
| L0 NAT spec change | `alicloud-nat-ops` | `alicloud-eip-ops` | Both skills must respect change window |
| L0 DNAT security incident | `alicloud-nat-ops` | `alicloud-actiontrail-ops` | Audit trail must be preserved |
| L0 NAT deletion | `alicloud-nat-ops` | `alicloud-vpc-ops` | Verify no downstream L0 services affected |
| L1 NAT cost optimization | `alicloud-nat-ops` | `alicloud-eip-ops` | Right-sizing must include rollback plan |

---

*This guide ensures NAT Gateway operations are appropriately controlled based on system sensitivity, aligned with Alibaba Cloud Well-Architected Framework Security and Stability Pillars.*
