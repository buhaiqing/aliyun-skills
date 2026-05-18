# FinOps Optimization — NAT Gateway

> **Purpose:** Cost optimization patterns, idle resource detection, right-sizing, and billing mode decisions for Alibaba Cloud NAT Gateway.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-19
> **Reference:** [阿里云卓越架构 - 成本支柱](https://help.aliyun.com/zh/product/2362200.html)

---

## 1. NAT Gateway Cost Structure

### 1.1 Cost Components

| Component | Billing Basis | When Charged | Optimization Lever |
|-----------|--------------|--------------|-------------------|
| **NAT Instance Fee** | Spec × Hour (PayBySpec) or CU × Hour (PayByActualUsage) | While NAT exists | Right-size spec; switch billing mode |
| **CU Fee** (PayByActualUsage) | Per Connection Unit consumed | While NAT processes traffic | Optimize connection usage; reduce idle connections |
| **EIP Instance Fee** | Per EIP × Hour | While EIP allocated | Remove unused EIPs; share via bandwidth plan |
| **EIP Bandwidth Fee** | PayByBandwidth (fixed) or PayByTraffic (per GB) | While EIP exists | Match billing to traffic pattern; use bandwidth plan |
| **Common Bandwidth Package** | Per bandwidth × Hour | While package exists | Share across multiple EIPs; right-size bandwidth |

### 1.2 Enhanced NAT Spec Pricing (Reference)

| Spec | CU Limit | Approx. Hourly Rate (PayBySpec) | Best For |
|------|----------|--------------------------------|----------|
| Small | 1,000 CU | ¥0.5/h | Dev/test, low traffic |
| Medium | 5,000 CU | ¥1.5/h | Small production |
| Large | 10,000 CU | ¥3.0/h | Medium production |
| XLarge | 50,000 CU | ¥8.0/h | High-traffic production |

> **Note:** Actual pricing varies by region. Use `aliyun vpc DescribeNatGateways` to verify current spec and billing.

---

## 2. Billing Mode Decision Tree

### 2.1 PayBySpec vs PayByActualUsage

```
Is NAT traffic predictable and steady (> 60% CU utilization)?
├── YES → PayBySpec (fixed hourly rate, cost-predictable)
│   └── Choose spec based on peak CU demand
└── NO → Is NAT traffic bursty or low-average?
    ├── Low average (< 30% CU), occasional bursts → PayByActualUsage (pay per CU)
    ├── Moderate (30-60% CU), steady → PayBySpec (more predictable)
    └── Very low traffic, dev/test only → PayByActualUsage + Small spec
```

### 2.2 Decision Matrix

| Scenario | CU Utilization | Recommended Billing | Rationale |
|----------|---------------|-------------------|-----------|
| Production web services | 60-90% sustained | PayBySpec (Medium/Large) | Fixed cost, predictable |
| Batch processing (nightly) | < 20% avg, 80% peak | PayByActualUsage | Pay only during bursts |
| Dev/test environment | < 10% avg | PayByActualUsage + Small | Minimize idle cost |
| Multi-service shared NAT | 40-70% sustained | PayBySpec (Large/XLarge) | Better per-CU rate at scale |
| Temporary project | Variable, short-lived | PayByActualUsage | No commitment, pay-as-go |

### 2.3 Switch Billing Mode

```bash
aliyun vpc ModifyNatGatewaySpec \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --BillingMethod "PayByActualUsage" \
  --AutoPay true
```

> **Warning:** Billing mode switch takes effect in the next billing cycle. No service interruption.

---

## 3. Idle Resource Detection

### 3.1 Idle NAT Gateway Detection

**Definition:** A NAT Gateway is "idle" if it has **zero SNAT entries AND zero DNAT entries for 7+ days**.

```bash
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"

for nat_id in $(aliyun vpc DescribeNatGateways --RegionId $REGION --PageSize 100 --output cols=NatGatewayId rows=NatGateways.NatGateway[].NatGatewayId 2>/dev/null | tail -n +2); do
  snat_count=$(aliyun vpc DescribeSnatTableEntries --RegionId $REGION --NatGatewayId $nat_id --output cols=TotalCount rows=TotalCount 2>/dev/null | tail -1)
  dnat_count=$(aliyun vpc DescribeForwardTableEntries --RegionId $REGION --NatGatewayId $nat_id --output cols=TotalCount rows=TotalCount 2>/dev/null | tail -1)

  if [ "${snat_count:-0}" = "0" ] && [ "${dnat_count:-0}" = "0" ]; then
    echo "IDLE: $nat_id (SNAT=0, DNAT=0)"
  fi
done
```

### 3.2 Underutilized NAT Gateway Detection

**Definition:** A NAT Gateway is "underutilized" if **CU utilization < 20% for 7+ consecutive days**.

```bash
aliyun cms QueryMetricList \
  --Namespace acs_nat \
  --MetricName MaxConnection \
  --Period 86400 \
  --StartTime "$(date -u -d '7 days ago' +%Y-%m-%d\ %H:%M:%S)" \
  --EndTime "$(date -u +%Y-%m-%d\ %H:%M:%S)" \
  --Dimensions "[{\"instanceId\":\"{{user.nat_gateway_id}}\"}]" \
  --output cols=Maximum,Timestamp rows=Datapoints[]
```

### 3.3 Orphaned EIP Detection

**Definition:** An EIP is "orphaned" if allocated but **not associated with any resource for 7+ days**.

```bash
aliyun vpc DescribeEipAddresses \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --Status Available \
  --PageSize 100 \
  --output cols=AllocationId,IpAddress,Name rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Name:Name}
```

> **Action:** Orphaned EIPs (Status=Available, not bound) incur instance fees. Release via `alicloud-eip-ops`.

### 3.4 Idle Detection Summary

| Resource | Idle Criteria | Detection Method | Estimated Waste |
|----------|--------------|-----------------|-----------------|
| NAT Gateway | 0 SNAT + 0 DNAT for 7d | CLI scan (§3.1) | ¥0.5-8.0/h per NAT |
| NAT Gateway | CU < 20% for 7d | CMS metric query (§3.2) | Spec downgrade savings |
| EIP (bound to NAT) | No traffic for 7d | CMS metric + DescribeEipAddresses | ¥0.02-0.1/h per EIP |
| EIP (unbound) | Status=Available for 7d | DescribeEipAddresses (§3.3) | ¥0.02-0.1/h per EIP |
| Bandwidth Package | Bandwidth < 30% for 7d | CMS metric | Downgrade bandwidth |

---

## 4. Right-Sizing Guide

### 4.1 Spec-to-Workload Mapping

| Workload Profile | Concurrent Connections | Bandwidth Need | Recommended Spec | Billing |
|-----------------|----------------------|----------------|-----------------|---------|
| Dev/test (1-5 ECS) | < 1,000 | < 10 Mbps | Small | PayByActualUsage |
| Small web app (5-20 ECS) | 1,000-5,000 | 10-50 Mbps | Small/Medium | PayBySpec |
| Medium web app (20-100 ECS) | 5,000-20,000 | 50-200 Mbps | Medium | PayBySpec |
| Large web app (100-500 ECS) | 20,000-100,000 | 200-500 Mbps | Large | PayBySpec |
| Enterprise (500+ ECS) | > 100,000 | > 500 Mbps | XLarge | PayBySpec |

### 4.2 Right-Sizing Decision Flow

```
1. Query current CU utilization (7-day average)
   aliyun cms QueryMetricList --Namespace acs_nat --MetricName MaxConnection

2. Compare against spec limits:
   - Small: 1,000 CU → if avg > 800 CU → upgrade to Medium
   - Medium: 5,000 CU → if avg > 4,000 CU → upgrade to Large
   - Large: 10,000 CU → if avg > 8,000 CU → upgrade to XLarge
   - XLarge: 50,000 CU → if avg > 40,000 CU → add second NAT + EIP pool

3. Check bandwidth utilization:
   - If OutRatePercent > 80% sustained → upgrade EIP bandwidth or add EIPs

4. Execute right-sizing:
   aliyun vpc ModifyNatGatewaySpec --NatSpec "<new_spec>"
```

### 4.3 Downgrade Safety Check

Before downgrading spec, verify:

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| Peak CU < 60% of new spec limit | CMS 7-day max | Max CU < new_limit × 0.6 |
| Peak bandwidth < 60% of new spec | CMS 7-day max | Max bandwidth < new_limit × 0.6 |
| No upcoming traffic events | Business calendar | No planned campaigns |
| SNAT connection count stable | CMS ActiveConnection | No upward trend |

```bash
aliyun vpc ModifyNatGatewaySpec \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --NatSpec "Small" \
  --AutoPay true
```

---

## 5. EIP Cost Optimization

### 5.1 Common Bandwidth Package (CBWP) Strategy

**When to use CBWP:** When you have **3+ EIPs** attached to NAT Gateways.

| Scenario | Without CBWP | With CBWP | Savings |
|----------|-------------|-----------|---------|
| 5 EIPs × 10 Mbps each | 5 × ¥0.5/h bandwidth | 1 × 50 Mbps CBWP = ¥2.0/h | ~20% |
| 10 EIPs × 5 Mbps each | 10 × ¥0.3/h bandwidth | 1 × 50 Mbps CBWP = ¥2.0/h | ~33% |
| 20 EIPs × 5 Mbps each | 20 × ¥0.3/h bandwidth | 1 × 100 Mbps CBWP = ¥3.5/h | ~42% |

### 5.2 EIP Billing Mode Optimization

| Traffic Pattern | Current Mode | Recommended Mode | Savings |
|----------------|-------------|-----------------|---------|
| Steady outbound, predictable | PayByTraffic | PayByBandwidth | Up to 50% |
| Bursty, low average | PayByBandwidth | PayByTraffic | Pay only for actual usage |
| Multi-EIP on NAT | Individual EIP bandwidth | CBWP + PayByTraffic | 20-40% |

### 5.3 EIP Count Optimization

**Rule:** Each EIP supports ~30K concurrent connections. Scale EIP count based on actual need.

| Current EIP Count | Avg Connection per EIP | Action |
|-------------------|----------------------|--------|
| 4 EIPs | < 5K per EIP | Reduce to 2 EIPs (still 60K capacity) |
| 2 EIPs | 25K per EIP | Add 1 more EIP (avoid hitting 30K limit) |
| 1 EIP | 28K | Add 1 more EIP immediately (near limit) |

---

## 6. FinOps Inspection Workflow

### 6.1 Weekly Cost Review

```bash
# Step 1: List all NAT Gateways with specs and billing
aliyun vpc DescribeNatGateways \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --PageSize 100 \
  --output cols=NatGatewayId,Name,Spec,BillingMethod,VpcId rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Spec:Spec,BillingMethod:BillingMethod,VpcId:VpcId}

# Step 2: For each NAT, check SNAT/DNAT entry counts
# (Use idle detection script from §3.1)

# Step 3: Check CU utilization (7-day average)
aliyun cms QueryMetricList \
  --Namespace acs_nat \
  --MetricName MaxConnection \
  --Period 86400 \
  --Dimensions "[{\"instanceId\":\"{{user.nat_gateway_id}}\"}]"

# Step 4: Check associated EIPs
aliyun vpc DescribeEipAddresses \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --AssociatedInstanceType Nat \
  --AssociatedInstanceId "{{user.nat_gateway_id}}"
```

### 6.2 Monthly Cost Optimization Report

| Metric | Query | Target |
|--------|-------|--------|
| Idle NAT Gateways | §3.1 detection | 0 idle NATs |
| Underutilized specs | CU < 20% for 30d | Right-size or delete |
| Orphaned EIPs | §3.3 detection | 0 orphaned EIPs |
| CBWP coverage | EIP count vs CBWP count | All multi-EIP NATs use CBWP |
| Billing mode fit | CU utilization vs billing mode | Correct mode per §2.2 |

### 6.3 Cost Anomaly Detection

| Anomaly | Detection | Action |
|---------|-----------|--------|
| NAT cost spike > 30% MoM | Billing API comparison | Check CU spike, EIP additions |
| EIP count growing | DescribeEipAddresses count | Audit new EIPs, release unused |
| Bandwidth over-provisioned | OutRatePercent < 30% for 30d | Downgrade bandwidth |
| PayBySpec with low CU | CU < 20% for 30d | Switch to PayByActualUsage |

---

## 7. Cost Estimation Templates

### 7.1 New NAT Gateway Cost Estimate

```yaml
estimate_new_nat:
  nat_instance:
    spec: "Medium"
    billing: "PayBySpec"
    monthly_cost: "¥1.5/h × 730h ≈ ¥1,095/month"

  eip_costs:
    count: 2
    instance_fee: "2 × ¥0.02/h × 730h ≈ ¥29/month"
    bandwidth: "2 × 10Mbps PayByBandwidth ≈ ¥146/month"

  total_estimate: "¥1,095 + ¥29 + ¥146 ≈ ¥1,270/month"
```

### 7.2 Migration Cost Comparison

| From | To | Monthly Savings | Migration Risk |
|------|----|----------------|---------------|
| Small PayBySpec + 4 individual EIPs | Medium PayBySpec + CBWP | ~25% | Low (spec upgrade is seamless) |
| Large PayBySpec (low CU) | Medium PayByActualUsage | ~40% | Low (billing switch, no restart) |
| 2 NAT Gateways (same VPC) | 1 NAT Gateway + more EIPs | ~50% | Medium (consolidate SNAT/DNAT) |

---

## 8. Cross-Skill FinOps Delegation

| Cost Issue | Primary Skill | Delegated Skill | Action |
|-----------|--------------|-----------------|--------|
| Orphaned EIPs | `alicloud-nat-ops` | `alicloud-eip-ops` | Release unused EIPs |
| CBWP optimization | `alicloud-nat-ops` | `alicloud-eip-ops` | Create/modify bandwidth plan |
| NAT spec right-sizing | `alicloud-nat-ops` | — | ModifyNatGatewaySpec |
| VPC with multiple NATs | `alicloud-nat-ops` | `alicloud-vpc-ops` | Consolidate NAT Gateways |
| Billing mode switch | `alicloud-nat-ops` | — | ModifyNatGatewaySpec --BillingMethod |

---

## 9. Sensitivity-Aware Cost Optimization

### 9.1 Cost Optimization Risk by Sensitivity Level

| Optimization Action | L0 Risk | L1 Risk | L2 Risk | L3 Risk |
|--------------------|---------|---------|---------|---------|
| Delete idle NAT Gateway | 🚫 CAB required | ⚠️ Change window | ✅ Auto | ✅ Auto |
| Downgrade NAT spec | 🚫 CAB + rollback plan | ⚠️ Change window + snapshot | ✅ Notify | ✅ Auto |
| Switch billing mode | ⚠️ Change window | ⚠️ Notify | ✅ Auto | ✅ Auto |
| Release orphaned EIP | 🚫 CAB required (may be DR standby) | ⚠️ Verify no DR role | ✅ Auto | ✅ Auto |
| Create CBWP | ⚠️ Change window | ✅ Auto | ✅ Auto | ✅ Auto |
| Consolidate NAT Gateways | 🚫 CAB + full impact assessment | 🚫 CAB required | ⚠️ Notify | ✅ Auto |

### 9.2 L0/L1 Cost Optimization Constraints

**L0 (核心生产) cost optimization MUST:**
1. Never delete NAT without CAB approval — even idle NATs may be DR standby
2. Never downgrade spec without 30-day CU trend analysis + rollback plan
3. Never release EIPs without verifying they are not part of DR architecture
4. Always perform right-sizing during change window only
5. Always capture configuration snapshot before cost optimization changes

**L1 (生产) cost optimization MUST:**
1. Verify idle NAT is not a failover/DR NAT before deletion
2. Capture snapshot before spec changes
3. Perform right-sizing during change window
4. Monitor for 1 hour after billing mode switch

### 9.3 DR-Aware Cost Optimization

**Critical:** Do NOT treat idle NAT Gateways as waste if they serve DR purposes.

| NAT Role | Idle Detection | Cost Action |
|----------|---------------|-------------|
| Primary NAT (active) | Normal idle detection | Delete if truly idle |
| DR/Standby NAT | Tag: `Role=DR` → skip idle detection | Keep; cost is DR insurance |
| Blue-Green NAT | Tag: `Role=BlueGreen` → skip idle detection | Keep; cost is deployment insurance |
| Test NAT (temporary) | Normal idle detection | Delete after 7d idle |

```bash
# Before deleting idle NAT, check for DR tag
aliyun vpc DescribeNatGateways \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --NatGatewayId "{{user.nat_gateway_id}}" \
  --output cols=Tags rows=Tags.Tag[].{Key:Key,Value:Value}

# If Tag contains Role=DR or Role=BlueGreen → DO NOT DELETE
```

---

*This guide aligns NAT Gateway operations with Alibaba Cloud Well-Architected Framework Cost Pillar best practices.*
