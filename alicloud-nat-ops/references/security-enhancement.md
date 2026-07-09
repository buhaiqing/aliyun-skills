# Security Enhancement Guide — NAT Gateway

> **Purpose:** Fine-grained security controls aligned with Alibaba Cloud Well-Architected Framework Security Pillar.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-19
> **Reference:** [阿里云卓越架构 - 安全支柱](https://help.aliyun.com/zh/waf/product-overview/overview)

---

## 1. RAM Policy Templates (Least Privilege)

### 1.1 Read-Only Policy (Monitoring & Audit)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "vpc:DescribeNatGateways",
        "vpc:DescribeSnatTableEntries",
        "vpc:DescribeForwardTableEntries",
        "vpc:DescribeFullNatEntries"
      ],
      "Resource": [
        "acs:vpc:*:*:natgateway/*"
      ]
    }
  ]
}
```

### 1.2 Operator Policy (SNAT/DNAT Management)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "vpc:DescribeNatGateways",
        "vpc:DescribeSnatTableEntries",
        "vpc:DescribeForwardTableEntries",
        "vpc:DescribeFullNatEntries",
        "vpc:CreateSnatEntry",
        "vpc:DeleteSnatEntry",
        "vpc:CreateForwardEntry",
        "vpc:DeleteForwardEntry",
        "vpc:ModifyNatGatewayAttribute"
      ],
      "Resource": [
        "acs:vpc:*:*:natgateway/${nat_gateway_id}"
      ],
      "Condition": {
        "IpAddress": {
          "acs:SourceIp": ["${trusted_ip_range}"]
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": [
        "vpc:DeleteNatGateway",
        "vpc:CreateNatGateway",
        "vpc:ModifyNatGatewaySpec"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.3 Admin Policy (Full NAT Lifecycle — Restricted Use)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "vpc:CreateNatGateway",
        "vpc:DeleteNatGateway",
        "vpc:ModifyNatGatewaySpec",
        "vpc:CreateSnatEntry",
        "vpc:DeleteSnatEntry",
        "vpc:CreateForwardEntry",
        "vpc:DeleteForwardEntry",
        "vpc:CreateFullNatEntry",
        "vpc:DeleteFullNatEntry",
        "vpc:ModifyNatGatewayAttribute"
      ],
      "Resource": "acs:vpc:*:*:natgateway/${nat_gateway_id}",
      "Condition": {
        "IpAddress": {
          "acs:SourceIp": ["${trusted_ip_range}"]
        },
        "DateLessThan": {
          "acs:CurrentTime": "${expiry_date}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "vpc:DescribeNatGateways",
        "vpc:DescribeSnatTableEntries",
        "vpc:DescribeForwardTableEntries",
        "vpc:DescribeFullNatEntries"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.4 Policy Application

```bash
# Delegate to alicloud-ram-ops skill
# Step 1: CreatePolicy with above JSON
# Step 2: AttachPolicyToUser / AttachPolicyToRole
# Step 3: Validate via test DescribeNatGateways operation
```

---

## 2. DNAT Exposure Audit

### 2.1 High-Risk Port Detection

**Critical:** DNAT entries expose internal ports to the internet. Each entry is a potential attack surface.

| Risk Level | Port | Service | Risk | Recommendation |
|-----------|------|---------|------|---------------|
| **CRITICAL** | 22 | SSH | Brute force, credential theft | Use VPN/Bastion host instead; if required, restrict source IP |
| **CRITICAL** | 3389 | RDP | Brute force, ransomware | Use VPN/Bastion host instead; never expose directly |
| **CRITICAL** | 3306 | MySQL | Data exfiltration, SQL injection | Use intranet access only; never expose to internet |
| **CRITICAL** | 6379 | Redis | Unauthorized access, data theft | Never expose Redis to internet |
| **CRITICAL** | 27017 | MongoDB | Unauthorized access, data theft | Never expose MongoDB to internet |
| **HIGH** | 23 | Telnet | Cleartext credentials | Disable; use SSH instead |
| **HIGH** | 21 | FTP | Cleartext credentials, data theft | Use SFTP/SCP instead |
| **HIGH** | 445 | SMB | Ransomware, worm propagation | Never expose to internet |
| **MEDIUM** | 80 | HTTP | Unencrypted traffic | Use 443 (HTTPS) instead |
| **LOW** | 443 | HTTPS | Standard web traffic | Acceptable; add WAF protection |
| **LOW** | 8080 | HTTP Alt | Common web app port | Acceptable; restrict source IP if possible |

### 2.2 DNAT Audit Script

```bash
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"
HIGH_RISK_PORTS="22 23 21 3389 3306 6379 27017 445"

for nat_id in $(aliyun vpc DescribeNatGateways --RegionId $REGION --PageSize 100 --output cols=NatGatewayId rows=NatGateways.NatGateway[].NatGatewayId 2>/dev/null | tail -n +2); do
  echo "=== Auditing NAT: $nat_id ==="

  aliyun vpc DescribeForwardTableEntries \
    --RegionId $REGION \
    --NatGatewayId $nat_id \
    --PageSize 100 \
    --output cols=ForwardEntryId,IpProtocol,ExternalIp,ExternalPort,InternalIp,InternalPort rows=ForwardTableEntries.ForwardTableEntry[].{ForwardEntryId:ForwardEntryId,IpProtocol:IpProtocol,ExternalIp:ExternalIp,ExternalPort:ExternalPort,InternalIp:InternalIp,InternalPort:InternalPort} 2>/dev/null | while read entry; do
      port=$(echo "$entry" | awk '{print $4}')
      if echo "$HIGH_RISK_PORTS" | grep -qw "$port"; then
        echo "  🚨 HIGH RISK: $entry (port $port exposed to internet)"
      fi
    done
done
```

### 2.3 DNAT Security Remediation

| Finding | Risk | Remediation | CLI Command |
|---------|------|-------------|-------------|
| SSH (22) exposed | Brute force | Delete DNAT; use Bastion host | `DeleteForwardEntry --ForwardEntryId <id>` |
| Database port exposed | Data breach | Delete DNAT; use intranet/VPC | `DeleteForwardEntry --ForwardEntryId <id>` |
| Any port with 0.0.0.0 source | Unrestricted access | Add source IP restriction via security group | Delegate to `alicloud-ecs-ops` |
| Unused DNAT entries | Attack surface | Delete unused entries | `DeleteForwardEntry --ForwardEntryId <id>` |
| Non-HTTPS web (80) | Unencrypted | Switch to 443 + HTTPS | Modify DNAT + update backend |

---

## 3. SNAT Security Assessment

### 3.1 SNAT Source Scope Audit

| SNAT Mode | Risk Level | Audit Check | Recommendation |
|-----------|-----------|-------------|---------------|
| vSwitch-level | Medium | Is vSwitch scope too broad? | Use CIDR-level for specific subnets |
| CIDR-level (0.0.0.0/0) | **CRITICAL** | Source CIDR is overly permissive | Narrow to specific subnet CIDR |
| CIDR-level (specific /24) | Low | Scope is appropriately limited | Acceptable |

### 3.2 SNAT Audit Script

```bash
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"

for nat_id in $(aliyun vpc DescribeNatGateways --RegionId $REGION --PageSize 100 --output cols=NatGatewayId rows=NatGateways.NatGateway[].NatGatewayId 2>/dev/null | tail -n +2); do
  echo "=== Auditing SNAT on NAT: $nat_id ==="

  aliyun vpc DescribeSnatTableEntries \
    --RegionId $REGION \
    --NatGatewayId $nat_id \
    --PageSize 100 \
    --output cols=SnatEntryId,SnatIp,SourceCIDR rows=SnatTableEntries.SnatTableEntry[].{SnatEntryId:SnatEntryId,SnatIp:SnatIp,SourceCIDR:SourceCIDR} 2>/dev/null | while read entry; do
      cidr=$(echo "$entry" | awk '{print $3}')
      if [ "$cidr" = "0.0.0.0/0" ]; then
        echo "  🚨 CRITICAL: SNAT source is 0.0.0.0/0 — overly permissive: $entry"
      fi
    done
done
```

---

## 4. Network Security Hardening

### 4.1 Security Group Coordination

**Key Principle:** DNAT bypasses ECS security groups for the initial NAT translation. Security groups on the target ECS still apply to the forwarded traffic.

| Traffic Direction | Security Group Effect | Recommendation |
|------------------|----------------------|---------------|
| Internet → EIP → DNAT → ECS | ECS security group applies to forwarded traffic | Restrict inbound rules on ECS security group |
| ECS → SNAT → EIP → Internet | ECS security group applies to outbound | Allow outbound on ECS; restrict unnecessary egress |

### 4.2 Network ACL Layer

| Layer | Scope | Recommendation |
|-------|-------|---------------|
| NAT Gateway | VPC-level | No built-in ACL; rely on SNAT/DNAT scope |
| Security Group | ECS-level | MUST restrict inbound for DNAT targets |
| Network ACL | Subnet-level | Add explicit deny rules for sensitive subnets |

### 4.3 FlowLog Security Monitoring

```bash
# Enable VPC FlowLog for NAT traffic audit (delegate to alicloud-vpc-ops)
# Query DNAT inbound traffic patterns
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "vpc-flowlog" \
  --query "action = ACCEPT AND dst_ip = '{{user.dnat_internal_ip}}' | SELECT src_ip, count(*) as conn_count group by src_ip order by conn_count desc limit 20"
```

---

## 5. Credential Security

### 5.1 Credential Format Validation

| Credential | Format | Validation |
|-----------|--------|-----------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Starts with `LTAI`, 16-24 chars | `^LTAI[A-Za-z0-9]{12,20}$` |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 30-40 chars, base64 | `^[A-Za-z0-9+/=]{30,40}$` |
| `ALIBABA_CLOUD_SECURITY_TOKEN` | STS token, 100-400 chars | Optional; short-lived |

### 5.2 Credential Security Rules

| Rule | Enforcement |
|------|------------|
| NEVER print `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Mask in all output: `LTAI****xxxx` |
| NEVER commit credentials to code | Use environment variables only |
| STS preferred for automation | Token expiry < 12 hours |
| AK/SK rotation every 90 days | Delegate to `alicloud-ram-ops` |
| MFA for console access | Required for interactive operations |

### 5.3 Credential Verification (Safe)

```bash
# Existence check only — NEVER echo values
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "AK: present (${#ALIBABA_CLOUD_ACCESS_KEY_ID} chars)" || echo "AK: MISSING"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "SK: present (masked)" || echo "SK: MISSING"
```

---

## 6. Audit & Compliance

### 6.1 ActionTrail Integration

**Delegate to `alicloud-actiontrail-ops`** for NAT operation audit.

| Event Category | Key NAT Events | Compliance Relevance |
|----------------|---------------|----------------------|
| Management | `CreateNatGateway`, `DeleteNatGateway` | Change tracking |
| Management | `CreateForwardEntry`, `DeleteForwardEntry` | DNAT exposure audit |
| Management | `CreateSnatEntry`, `DeleteSnatEntry` | SNAT scope audit |
| Management | `ModifyNatGatewaySpec` | Billing change audit |

### 6.2 Audit Query Pattern

```yaml
# Delegate to alicloud-actiontrail-ops
Step 1: LookupEvents
  Input:
    EventName: ["CreateForwardEntry", "DeleteForwardEntry", "CreateNatGateway", "DeleteNatGateway"]
    ResourceType: "ACS::VPC::NatGateway"
    StartTime: "{{start_time}}"
    EndTime: "{{end_time}}"
  Output: {{output.events}}

Step 2: Parse events for security violations
  - Check: DeleteNatGateway events outside change window
  - Check: CreateForwardEntry for high-risk ports (22, 3306, 6379)
  - Check: Operations by unauthorized RAM users

Step 3: Generate audit report
  - Summary: Total operations, high-risk operations, policy violations
  - Detail: Per-event analysis with risk classification
```

### 6.3 Compliance Checklist

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| **ISO 27001** | Access control, network segmentation, audit | ✅ Partial |
| **SOC 2** | Change management, access logging | ✅ Partial |
| **MLPS 2.0** | Network isolation, security audit | ✅ Supported |
| **GDPR** | Data residency, access control | ⚠️ Region verification needed |

---

## 7. Security Incident Response

### 7.1 Incident Classification

| Severity | Indicators | Response Time |
|----------|-----------|---------------|
| **Critical** | Database port exposed via DNAT, credential leak | < 15 min |
| **High** | SSH exposed via DNAT, unauthorized DNAT creation | < 1 hour |
| **Medium** | SNAT scope too broad, RAM policy drift | < 24 hours |
| **Low** | Missing MFA, stale audit trail config | < 7 days |

### 7.2 Incident Response Runbook

```yaml
Phase 1: Detection (0-5 min)
  - Alert from DNAT audit or ActionTrail event
  - Identify affected NAT Gateway and DNAT entries
  - Classify severity per §7.1

Phase 2: Containment (5-15 min)
  - Delete high-risk DNAT entries immediately
  - Restrict SNAT source CIDR if overly permissive
  - Verify security group rules on affected ECS

Phase 3: Investigation (15-60 min)
  - Query ActionTrail for unauthorized operations
  - Check FlowLog for data exfiltration indicators
  - Analyze access patterns on exposed ports

Phase 4: Recovery (60-120 min)
  - Reconfigure DNAT with restricted source IPs
  - Update RAM policies to prevent recurrence
  - Enable FlowLog if not already active

Phase 5: Post-Incident (2-7 days)
  - Document incident timeline and root cause
  - Update security controls and DNAT policies
  - Schedule security audit for all NAT Gateways
```

### 7.3 Emergency DNAT Removal

```bash
# Immediately remove a high-risk DNAT entry
aliyun vpc DeleteForwardEntry \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --ForwardEntryId "{{user.forward_entry_id}}"

# Verify removal
aliyun vpc DescribeForwardTableEntries \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --NatGatewayId "{{user.nat_gateway_id}}"
```

---

## 8. Security Assessment Checklist

### P0 — MUST Pass (Critical)

| Check | Status | Evidence |
|-------|--------|----------|
| No high-risk ports (22/3306/6379/3389/27017) exposed via DNAT | ✅ | §2.1 Port risk table + §2.2 Audit script |
| RAM policy scoped to NAT Gateway operations only | ✅ | §1.1-1.3 Policy templates |
| Credential masking enforced (never print secrets) | ✅ | §5.2 Security rules |
| SNAT source CIDR is not 0.0.0.0/0 | ✅ | §3.1 SNAT audit |
| DNAT entries have corresponding security group rules | ✅ | §4.1 Security group coordination |

### P1 — SHOULD Pass (Important)

| Check | Status | Evidence |
|-------|--------|----------|
| STS temporary credentials used for automation | ⚠️ | §5.2 Credential rules |
| FlowLog enabled for NAT traffic audit | ⚠️ | §4.3 FlowLog monitoring |
| ActionTrail enabled for NAT operation audit | ⚠️ | §6.1 ActionTrail integration |
| Security incident runbook documented | ⚠️ | §7.2 Incident response |
| Regular DNAT exposure audit (weekly) | ⚠️ | §2.2 Audit script |
| Compliance checklist documented | ⚠️ | §6.3 Compliance matrix |

### P2 — NICE to Have (Enhancement)

| Check | Status | Evidence |
|-------|--------|----------|
| Automated DNAT security scan (CI/CD) | ⚠️ | §2.2 Script integration |
| Network ACL on NAT subnets | ⚠️ | §4.2 Network ACL |
| Cross-region NAT security consistency | ⚠️ | Multi-region audit |
| WAF/Cloud Firewall in front of DNAT | ⚠️ | Delegate to security skills |

---

## 9. Sensitivity-Aware Security Baselines

### 9.1 Security Requirements by Sensitivity Level

| Security Control | L0 (核心生产) | L1 (生产) | L2 (预发) | L3 (开发/测试) |
|-----------------|-------------|-----------|-----------|---------------|
| DNAT high-risk port audit | **MUST** — daily | **MUST** — weekly | SHOULD — monthly | NICE |
| SNAT source CIDR audit | **MUST** — daily | **MUST** — weekly | SHOULD — monthly | NICE |
| RAM policy scope | **MUST** — per-instance scoped | **MUST** — per-NAT scoped | SHOULD — per-service scoped | MAY — full access |
| Credential method | **MUST** — STS only, MFA required | **MUST** — STS preferred | SHOULD — AK/SK with rotation | MAY — AK/SK |
| FlowLog | **MUST** — real-time + 365d retention | **MUST** — enabled + 90d retention | SHOULD — enabled | NICE |
| ActionTrail | **MUST** — all NAT events + 365d | **MUST** — all NAT events + 90d | SHOULD — enabled | NICE |
| Security group on DNAT targets | **MUST** — explicit allow only | **MUST** — explicit allow only | SHOULD — restrict | MAY — open |
| Network ACL | **MUST** — explicit deny for sensitive subnets | SHOULD — on sensitive subnets | NICE | N/A |
| Incident response | **MUST** — < 15 min response | **MUST** — < 1 hour response | SHOULD — documented | NICE |
| Configuration snapshot before change | **MUST** | **MUST** | SHOULD | NICE |
| Change window compliance | **MUST** — strict | **MUST** — standard | SHOULD | N/A |

### 9.2 L0 Security Hardening (Additional Requirements)

**L0 NAT Gateways MUST additionally:**

1. **No DNAT for databases:** MySQL (3306), Redis (6379), MongoDB (27017) — **NEVER** expose via DNAT, even with source IP restriction. Use VPC peering or private link instead.

2. **SSH access via Bastion only:** DNAT for port 22 is **PROHIBITED** on L0. Use Bastion host or VPN.

3. **DNAT source IP restriction:** All DNAT entries on L0 NAT Gateways **MUST** have source IP restriction via security group. No 0.0.0.0/0 inbound on DNAT target security groups.

4. **Encryption in transit:** All DNAT-exposed services **MUST** use HTTPS/TLS. Port 80 (HTTP) DNAT is **PROHIBITED** on L0 — use 443 only.

5. **Dual-approval for DNAT creation:** Creating any DNAT entry on L0 NAT Gateways requires approval from both the service owner and security team.

6. **Audit log retention:** ActionTrail logs for L0 NAT operations **MUST** be retained for 365 days minimum.

7. **Regular penetration testing:** DNAT entries on L0 NAT Gateways **MUST** be included in quarterly penetration tests.

### 9.3 Industry-Specific Security Controls

| Industry | DNAT Restrictions | Audit Requirements | Encryption |
|----------|------------------|-------------------|-----------|
| 金融 (Finance) | Only 443 allowed; all DB ports prohibited | 180-day audit retention; dual-approval for all changes | TLS 1.2+ mandatory |
| 政务 (Government) | Only approved ports; source IP whitelist mandatory | 365-day audit retention; all changes require approval | 国密算法 preferred |
| 医疗 (Healthcare) | HIS/EMR ports prohibited; 443 only for web | 365-day audit retention; HIPAA compliance | TLS 1.2+ mandatory; PHI encryption |
| 电商 (E-commerce) | Payment system: separate NAT + 443 only | 90-day audit retention; PCI-DSS for payment | TLS 1.2+ for payment flow |

---

*This guide aligns NAT Gateway operations with Alibaba Cloud Well-Architected Framework Security Pillar best practices.*
