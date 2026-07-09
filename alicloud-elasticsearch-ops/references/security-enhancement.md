# Security Enhancement Guide — Alibaba Cloud Elasticsearch

> **Purpose:** Fine-grained security controls aligned with Alibaba Cloud Well-Architected Framework Security Pillar.
> **Version:** 2.0.0
> **Last Updated:** 2026-05-17
> **Reference:** [阿里云卓越架构 - 安全支柱](https://help.aliyun.com/zh/waf/product-overview/overview)

---

## 1. RAM Policy Templates (Least Privilege)

### 1.1 Read-Only Policy (Recommended for Monitoring)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:DescribeInstance",
        "elasticsearch:ListInstance",
        "elasticsearch:DescribeElasticsearchHealth",
        "elasticsearch:ListSnapshots",
        "elasticsearch:DescribeSnapshot",
        "elasticsearch:ListDiagnoseReport",
        "elasticsearch:DescribeDiagnoseReport",
        "elasticsearch:ListSearchLog"
      ],
      "Resource": [
        "acs:elasticsearch:*:*:instance/${instanceId}",
        "acs:elasticsearch:*:*:snapshot/${snapshotId}"
      ],
      "Condition": {
        "StringEquals": {
          "elasticsearch:InstanceType": ["Standard"]
        }
      }
    }
  ]
}
```

### 1.2 Operator Policy (Recommended for DevOps)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:DescribeInstance",
        "elasticsearch:ListInstance",
        "elasticsearch:RestartInstance",
        "elasticsearch:UpdateInstance",
        "elasticsearch:CreateSnapshot",
        "elasticsearch:DiagnoseInstance"
      ],
      "Resource": "acs:elasticsearch:*:*:instance/${instanceId}",
      "Condition": {
        "StringEquals": {
          "elasticsearch:InstanceType": ["Standard"]
        },
        "IpAddress": {
          "acs:SourceIp": ["${trusted_ip_range}"]
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": [
        "elasticsearch:DeleteInstance",
        "elasticsearch:DeleteSnapshot"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.3 Admin Policy (Restricted Use)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:CreateInstance",
        "elasticsearch:DeleteInstance",
        "elasticsearch:UpgradeEngineVersion",
        "elasticsearch:ModifyWhiteIps",
        "elasticsearch:OpenHttps",
        "elasticsearch:CloseHttps"
      ],
      "Resource": "acs:elasticsearch:*:*:instance/${instanceId}",
      "Condition": {
        "StringEquals": {
          "elasticsearch:InstanceType": ["Standard"]
        },
        "DateLessThan": {
          "acs:CurrentTime": "${expiry_date}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticsearch:DescribeInstance",
        "elasticsearch:ListInstance"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.4 Policy Application Commands

```bash
# Create RAM policy via alicloud-ram-ops skill
# Delegate: alicloud-ram-ops
# Input: policy_name, policy_document, policy_type

# Example delegation:
# 1. Call alicloud-ram-ops: CreatePolicy
# 2. Call alicloud-ram-ops: AttachPolicyToUser
# 3. Validate policy effect via test operation
```

---

## 2. Credential Security (Enhanced Validation)

### 2.1 Credential Format Validation

```go
package main

import (
    "fmt"
    "os"
    "regexp"
)

// Credential validation constants
const (
    AccessKeyIDPattern    = `^LTAI[A-Za-z0-9]{12,20}$`
    AccessKeySecretPattern = `^[A-Za-z0-9+/=]{30,40}$`
    STSTokenPattern       = `^[A-Za-z0-9+/=]{100,400}$`
)

func validateAccessKeyID(ak string) error {
    if len(ak) < 16 || len(ak) > 24 {
        return fmt.Errorf("AccessKeyID length must be 16-24 characters")
    }
    
    matched, _ := regexp.MatchString(AccessKeyIDPattern, ak)
    if !matched {
        return fmt.Errorf("AccessKeyID format invalid (must start with LTAI)")
    }
    
    return nil
}

func validateAccessKeySecret(sk string) error {
    if len(sk) < 30 || len(sk) > 40 {
        return fmt.Errorf("AccessKeySecret length must be 30-40 characters")
    }
    
    matched, _ := regexp.MatchString(AccessKeySecretPattern, sk)
    if !matched {
        return fmt.Errorf("AccessKeySecret contains invalid characters")
    }
    
    return nil
}

func validateSTSToken(token string, expiry int64) error {
    if token == "" {
        return nil // STS optional
    }
    
    matched, _ := regexp.MatchString(STSTokenPattern, token)
    if !matched {
        return fmt.Errorf("STS token format invalid")
    }
    
    // Validate expiration (must be > 5 minutes from now)
    if expiry <= time.Now().Unix() + 300 {
        return fmt.Errorf("STS token expires too soon (< 5 minutes)")
    }
    
    return nil
}

// Safe credential verification (existence + format)
func verifyCredentialsSecurely() error {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    token := os.Getenv("ALIBABA_CLOUD_SECURITY_TOKEN")
    
    if ak == "" {
        return fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_ID not set")
    }
    if sk == "" {
        return fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_SECRET not set")
    }
    
    // Enhanced validation
    if err := validateAccessKeyID(ak); err != nil {
        return fmt.Errorf("AccessKeyID validation failed: %w", err)
    }
    if err := validateAccessKeySecret(sk); err != nil {
        return fmt.Errorf("AccessKeySecret validation failed: %w", err)
    }
    
    // Masked output (NEVER expose full values)
    fmt.Printf("✅ ALIBABA_CLOUD_ACCESS_KEY_ID: %s****\n", ak[:4])
    fmt.Printf("✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET: %s****\n", sk[:4])
    
    if token != "" {
        fmt.Println("✅ ALIBABA_CLOUD_SECURITY_TOKEN: present (STS mode)")
    }
    
    return nil
}
```

### 2.2 Credential Rotation Best Practices

| Practice | Recommendation | Frequency |
|----------|---------------|-----------|
| AK/SK rotation | Rotate every 90 days | Quarterly |
| STS token | Use for automation; short-lived | Per session (1-12 hours) |
| RAM user MFA | Enable for console access | Permanent |
| IP whitelist | Restrict to trusted ranges | Annual review |

---

## 3. Network Security (Zero Trust)

### 3.1 VPC-Only Access (Recommended for Production)

```go
// Disable public network access
request := &elasticsearch.UpdatePublicNetworkRequest{
    InstanceId:        tea.String(instanceId),
    PublicNetwork:     tea.Bool(false),  // Disable public endpoint
}

// Create VPC endpoint for internal access
vpcEndpointRequest := &elasticsearch.CreateVpcEndpointRequest{
    InstanceId:        tea.String(instanceId),
    VpcId:             tea.String(vpcId),
    VswitchId:         tea.String(vswitchId),
}
```

### 3.2 IP Whitelist Management (CIDR Format)

```go
// Recommended whitelist patterns
whitelistPatterns := []string{
    "10.0.0.0/8",      // Internal VPC
    "172.16.0.0/12",   // Internal VPC
    "192.168.0.0/16",  // Internal VPC
    "${office_ip}/32", // Specific office IP
}

request := &elasticsearch.ModifyWhiteIpsRequest{
    InstanceId:     tea.String(instanceId),
    WhiteIpList:    tea.String(strings.Join(whitelistPatterns, ",")),
    ModifyMode:     tea.String("Cover"),  // Replace existing whitelist
}
```

### 3.3 HTTPS Enforcement (Mandatory)

```go
// Check HTTPS status
response, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
    InstanceId: tea.String(instanceId),
})

// Enable HTTPS if not enabled
if !tea.ToBool(response.Body.Result.EnableHttps) {
    fmt.Println("⚠️ HTTPS not enabled. Enabling now...")
    
    request := &elasticsearch.OpenHttpsRequest{
        InstanceId: tea.String(instanceId),
    }
    
    _, err = client.OpenHttps(request)
    if err != nil {
        fmt.Println("❌ Failed to enable HTTPS")
        return err
    }
    
    fmt.Println("✅ HTTPS enabled successfully")
}
```

---

## 4. Data Security (Encryption & Backup)

### 4.1 Disk Encryption Verification

| Storage Type | Encryption | Recommendation |
|--------------|------------|----------------|
| `cloud_ssd` | AES-256 | ✅ Enabled by default |
| `cloud_efficiency` | AES-256 | ✅ Enabled by default |
| `local_ssd` | None | ⚠️ Not encrypted; avoid for sensitive data |

### 4.2 Backup Security

```go
// Create encrypted snapshot with description
request := &elasticsearch.CreateSnapshotRequest{
    InstanceId:    tea.String(instanceId),
    SnapshotName:  tea.String("secure-backup-" + time.Now().Format("20060102")),
    Description:   tea.String("Encrypted backup for compliance audit"),
    // Snapshot data inherits disk encryption
}
```

---

## 5. Audit & Compliance (ActionTrail Integration)

### 5.1 ActionTrail Event Categories

| Event Category | Events Captured | Compliance Relevance |
|----------------|-----------------|----------------------|
| `Management` | Create/Delete/Update/Restart instances | Change tracking |
| `Data` | Snapshot create/delete | Data protection audit |
| `Access` | Whitelist modification | Security audit |

### 5.2 ActionTrail Integration Pattern

```yaml
# Delegate to alicloud-actiontrail-ops skill

Step 1: Enable ActionTrail (alicloud-actiontrail-ops)
  - Execute: CreateTrail
  - Input: trail_name, oss_bucket, event_types
  - Output: {{output.trail_name}}

Step 2: Query Elasticsearch Events (alicloud-actiontrail-ops)
  - Execute: LookupEvents
  - Input: 
    - EventName: ["CreateInstance", "DeleteInstance", "RestartInstance", "ModifyWhiteIps"]
    - ResourceType: "ACS::Elasticsearch::Instance"
    - StartTime: "{{start_time}}"
    - EndTime: "{{end_time}}"
  - Output: {{output.events}}

Step 3: Generate Audit Report
  - Parse events for compliance violations
  - Check: DeleteInstance events outside change window
  - Check: Whitelist modifications by unauthorized users
  - Report: Monthly audit summary
```

### 5.3 Compliance Checklist

| Compliance Requirement | Implementation | Status |
|------------------------|----------------|--------|
| **ISO 27001** | Access control, encryption, audit trails | ✅ Partial |
| **SOC 2** | Data protection, change management | ✅ Partial |
| **GDPR** | Data residency, encryption at rest | ⚠️ Needs region verification |
| **MLPS 2.0** | Network isolation, audit logging | ✅ Supported |

---

## 6. Security Incident Response

### 6.1 Incident Classification

| Severity | Indicators | Response Time |
|----------|------------|---------------|
| **Critical** | Instance deleted, cluster red, data breach | < 15 min |
| **High** | Unauthorized whitelist change, HTTPS disabled | < 1 hour |
| **Medium** | RAM policy drift, credential expiry warning | < 24 hours |
| **Low** | Missing MFA, stale audit trail config | < 7 days |

### 6.2 Incident Response Runbook

```yaml
# Security Incident Response Flow

Phase 1: Detection (0-5 min)
  - Alert from CMS or ActionTrail
  - Identify affected instance(s)
  - Classify severity

Phase 2: Containment (5-15 min)
  - Disable public endpoint if data breach
  - Revoke compromised credentials
  - Restrict whitelist to trusted IPs

Phase 3: Investigation (15-60 min)
  - Query ActionTrail for unauthorized operations
  - Check RAM policy changes
  - Analyze access logs for anomalies

Phase 4: Recovery (60-120 min)
  - Restore from last known good snapshot
  - Re-enable services with enhanced security
  - Update RAM policies

Phase 5: Post-Incident (2-7 days)
  - Document incident timeline
  - Update security controls
  - Conduct root cause analysis
```

---

## 7. Security Assessment Checklist

### P0 — MUST Pass (Critical)

| Check | Status | Evidence |
|-------|--------|----------|
| RAM policy scoped to specific instances | ✅ | Use policy templates §1.1-1.3 |
| Credential masking enforced | ✅ | `verifyCredentialsSecurely()` §2.1 |
| HTTPS enabled for all connections | ✅ | §3.3 HTTPS enforcement |
| IP whitelist configured (not 0.0.0.0/0) | ✅ | §3.2 CIDR whitelist |
| ActionTrail enabled for audit | ⚠️ | §5.2 Integration pattern |

### P1 — SHOULD Pass (Important)

| Check | Status | Evidence |
|-------|--------|----------|
| STS temporary credentials used | ⚠️ | §2.2 Credential rotation |
| VPC-only access (no public endpoint) | ⚠️ | §3.1 VPC-only config |
| Disk encryption verified | ⚠️ | §4.1 Encryption check |
| Security incident runbook exists | ⚠️ | §6.2 Incident response |
| Compliance checklist documented | ⚠️ | §5.3 Compliance matrix |

---

*This guide aligns Elasticsearch operations with Alibaba Cloud Well-Architected Framework Security Pillar best practices.*