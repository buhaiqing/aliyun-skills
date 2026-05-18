# Security Enhancement Guide — AgentRun Sandbox

> **Purpose:** Fine-grained security controls aligned with Alibaba Cloud Well-Architected Framework Security Pillar.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-19
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
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:GetSandbox",
        "fc:ListSandboxes"
      ],
      "Resource": [
        "acs:agentrun:*:*:template/*",
        "acs:agentrun:*:*:sandbox/*"
      ]
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
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:CreateTemplate",
        "fc:UpdateTemplate",
        "fc:GetSandbox",
        "fc:ListSandboxes",
        "fc:CreateSandbox",
        "fc:StopSandbox",
        "fc:ExecuteSandboxCode"
      ],
      "Resource": [
        "acs:agentrun:*:*:template/*",
        "acs:agentrun:*:*:sandbox/*"
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
        "fc:DeleteTemplate",
        "fc:DeleteSandbox"
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
        "fc:CreateTemplate",
        "fc:DeleteTemplate",
        "fc:UpdateTemplate",
        "fc:ActivateTemplateMCP",
        "fc:StopTemplateMCP"
      ],
      "Resource": "acs:agentrun:*:*:template/${templateName}",
      "Condition": {
        "DateLessThan": {
          "acs:CurrentTime": "${expiry_date}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "fc:DeleteSandbox"
      ],
      "Resource": "acs:agentrun:*:*:sandbox/${sandboxId}",
      "Condition": {
        "StringEquals": {
          "agentrun:SandboxStatus": ["TERMINATED"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:GetSandbox",
        "fc:ListSandboxes"
      ],
      "Resource": "*"
    }
  ]
}
```

### 1.4 Data Plane Only Policy (For Code Execution Agents)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fc:ExecuteSandboxCode",
        "fc:GetSandbox"
      ],
      "Resource": "acs:agentrun:*:*:sandbox/${sandboxId}"
    }
  ]
}
```

### 1.5 Policy Application

```bash
# Delegate to alicloud-ram-ops skill
# 1. Call alicloud-ram-ops: CreatePolicy with policy document above
# 2. Call alicloud-ram-ops: AttachPolicyToUser
# 3. Validate policy effect via test operation (e.g., ListTemplates)
```

---

## 2. Credential Security (Enhanced Validation)

### 2.1 Credential Format Validation

```python
import re
import os

ACCESS_KEY_ID_PATTERN = r'^LTAI[A-Za-z0-9]{12,20}$'
ACCESS_KEY_SECRET_PATTERN = r'^[A-Za-z0-9+/=]{30,40}$'
STS_TOKEN_PATTERN = r'^[A-Za-z0-9+/=]{100,400}$'

def validate_access_key_id(ak: str) -> tuple[bool, str]:
    if not ak:
        return False, "ALIBABA_CLOUD_ACCESS_KEY_ID is empty"
    if len(ak) < 16 or len(ak) > 24:
        return False, f"AccessKeyID length {len(ak)} out of range (16-24)"
    if not re.match(ACCESS_KEY_ID_PATTERN, ak):
        return False, "AccessKeyID format invalid (must start with LTAI)"
    return True, "OK"

def validate_access_key_secret(sk: str) -> tuple[bool, str]:
    if not sk:
        return False, "ALIBABA_CLOUD_ACCESS_KEY_SECRET is empty"
    if len(sk) < 30 or len(sk) > 40:
        return False, f"AccessKeySecret length {len(sk)} out of range (30-40)"
    if not re.match(ACCESS_KEY_SECRET_PATTERN, sk):
        return False, "AccessKeySecret contains invalid characters"
    return True, "OK"

def validate_sts_token(token: str, expiry_epoch: int) -> tuple[bool, str]:
    if not token:
        return True, "STS token not provided (optional)"
    if not re.match(STS_TOKEN_PATTERN, token):
        return False, "STS token format invalid"
    import time
    if expiry_epoch <= int(time.time()) + 300:
        return False, "STS token expires too soon (< 5 minutes)"
    return True, "OK"

def verify_credentials_securely() -> tuple[bool, str]:
    ak = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
    sk = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
    token = os.getenv("ALIBABA_CLOUD_SECURITY_TOKEN", "")

    ok, msg = validate_access_key_id(ak)
    if not ok:
        return False, f"AccessKeyID: {msg}"

    ok, msg = validate_access_key_secret(sk)
    if not ok:
        return False, f"AccessKeySecret: {msg}"

    if token:
        ok, msg = validate_sts_token(token, 0)
        if not ok:
            return False, f"STS Token: {msg}"

    masked_ak = f"{ak[:4]}***{ak[-2:]}" if len(ak) >= 6 else "***"
    print(f"✅ ALIBABA_CLOUD_ACCESS_KEY_ID: {masked_ak}")
    print("✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET: <masked>")
    if token:
        print("✅ ALIBABA_CLOUD_SECURITY_TOKEN: present (STS mode)")
    return True, "All credentials valid"
```

### 2.2 Credential Rotation Best Practices

| Practice | Recommendation | Frequency |
|----------|---------------|-----------|
| AK/SK rotation | Rotate every 90 days | Quarterly |
| STS token | Use for automation; short-lived | Per session (1-12 hours) |
| RAM user MFA | Enable for console access | Permanent |
| IP whitelist | Restrict to trusted ranges | Annual review |

---

## 3. Input Validation Specification

### 3.1 Parameter Validation Rules

| Parameter | Pattern / Range | Error Message |
|-----------|----------------|---------------|
| `templateName` | `^[a-zA-Z0-9_-]{1,64}$` | "templateName: 1-64 chars, alphanumeric/hyphen/underscore only" |
| `sandboxId` | `^[0-9A-Z]{26}$` (ULID) | "sandboxId: must be 26-char ULID format" |
| `cpu` | `1-8` (integer) | "cpu: must be integer 1-8" |
| `memory` | `1024-16384` (integer, MB) | "memory: must be integer 1024-16384 MB" |
| `diskSize` | `1024-102400` (integer, MB) | "diskSize: must be integer 1024-102400 MB" |
| `idleTimeout` | `60-21600` (integer, seconds) | "idleTimeout: must be integer 60-21600 seconds" |
| `language` | `python \| nodejs \| go` | "language: must be python, nodejs, or go" |
| `networkMode` | `PUBLIC \| PRIVATE` | "networkMode: must be PUBLIC or PRIVATE" |
| `path` (file) | No `..` traversal, no leading `.` | "path: must not contain '..' or hidden file prefix" |
| `command` | See §3.2 dangerous command list | "command: contains restricted pattern" |

### 3.2 Dangerous Command Detection

```python
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/',
    r'rm\s+-rf\s+~',
    r':\(\)\{.*;\}',
    r'curl\s+.*\|\s*(ba)?sh',
    r'wget\s+.*\|\s*(ba)?sh',
    r'mkfs\.',
    r'dd\s+if=.*of=/dev/',
    r'chmod\s+777\s+/',
    r'chown\s+.*\s+/',
    r'>\s*/dev/sd',
    r'shutdown',
    r'reboot',
    r'init\s+[06]',
]

def validate_command_safety(command: str) -> tuple[bool, str]:
    import re
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Command contains dangerous pattern: {pattern}"
    return True, "OK"
```

### 3.3 Path Traversal Protection

```python
def validate_path_safety(path: str) -> tuple[bool, str]:
    if '..' in path:
        return False, "Path must not contain '..' (traversal risk)"
    parts = path.split('/')
    for part in parts:
        if part.startswith('.') and part != '.':
            return False, f"Hidden file/directory not allowed: {part}"
    if not path.startswith('/'):
        return False, "Path must be absolute"
    return True, "OK"
```

---

## 4. Safety Gates (Destructive Operations)

### 4.1 Safety Gate Matrix

| Operation | Risk Level | Safety Gate Required | Confirmation Message |
|-----------|-----------|---------------------|---------------------|
| DeleteTemplate | **High** | ✅ Yes | "⚠️ Delete template '{name}'? All dependent sandboxes will be affected. This is IRREVERSIBLE." |
| DeleteSandbox | **High** | ✅ Yes | "⚠️ Delete sandbox '{id}'? All files, contexts, and state will be lost. This is IRREVERSIBLE." |
| ExecCommand | **Medium** | ⚠️ Conditional | "⚠️ Execute command in sandbox '{id}'? Review command for safety." |
| WebSocketTTY | **Medium** | ⚠️ Conditional | "⚠️ Open interactive terminal to sandbox '{id}'? Full shell access granted." |
| StopSandbox | **Medium** | ⚠️ Conditional | "⚠️ Stop sandbox '{id}'? Running processes will be terminated." |
| UpdateTemplate | **Medium** | ⚠️ Conditional | "⚠️ Update template '{name}'? Running sandboxes may be affected on next creation." |

### 4.2 Safety Gate Implementation

```python
def confirm_destructive_operation(operation: str, resource_id: str, details: str = "") -> bool:
    message = SAFETY_GATE_MESSAGES.get(operation, f"Confirm {operation} on {resource_id}?")
    if details:
        message += f"\n  Details: {details}"

    print(f"\n{'='*60}")
    print(f"  ⚠️  SAFETY GATE: {operation}")
    print(f"  {message}")
    print(f"{'='*60}")

    response = input("  Type 'YES' to proceed: ").strip()
    return response == "YES"

def pre_flight_safety_check(operation: str, **kwargs) -> tuple[bool, str]:
    if operation == "DeleteTemplate":
        template_name = kwargs.get("template_name", "")
        if not template_name:
            return False, "templateName required"

        sandboxes = list_sandboxes(templateName=template_name, status="READY")
        if sandboxes:
            return False, f"Template has {len(sandboxes)} active sandboxes. Stop and delete them first."

    elif operation == "ExecCommand":
        command = kwargs.get("command", "")
        safe, msg = validate_command_safety(command)
        if not safe:
            return False, f"Dangerous command detected: {msg}"

    elif operation == "WebSocketTTY":
        sandbox_id = kwargs.get("sandbox_id", "")
        sandbox = get_sandbox(sandbox_id)
        if sandbox["status"] != "READY":
            return False, f"Sandbox status is {sandbox['status']}, must be READY"

    return True, "OK"
```

---

## 5. Network Security

### 5.1 PRIVATE Network Mode (Recommended for Production)

```json
{
  "networkConfiguration": {
    "networkMode": "PRIVATE",
    "vpcId": "{{user.vpc_id}}",
    "securityGroupId": "{{user.security_group_id}}",
    "vSwitchId": "{{user.vswitch_id}}"
  }
}
```

**Benefits**:
- Sandbox runs inside VPC, no public internet exposure
- Can access internal services (RDS, Redis, OSS VPC endpoint)
- Security group controls inbound/outbound traffic

### 5.2 Endpoint Security

| Plane | Endpoint | Security Measure |
|-------|----------|-----------------|
| Control Plane | `agentrun.{region}.aliyuncs.com` | HTTPS only (TLS 1.2+) |
| Data Plane | `{account}.agentrun-data.{region}.aliyuncs.com` | HTTPS only (TLS 1.2+) |
| WebSocket TTY | `wss://{account}.agentrun-data.{region}.aliyuncs.com` | WSS (TLS 1.2+) |

### 5.3 Firewall Requirements

| Endpoint | Port | Protocol | Direction |
|----------|------|----------|-----------|
| Control Plane | 443 | HTTPS | Outbound |
| Data Plane | 443 | HTTPS | Outbound |
| WebSocket TTY | 443 | WSS | Outbound |

---

## 6. STS Temporary Credential Flow

### 6.1 STS Integration

```bash
# STS temporary credentials (recommended for automation)
export ALIBABA_CLOUD_ACCESS_KEY_ID="<STS_AK>"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="<STS_SK>"
export ALIBABA_CLOUD_SECURITY_TOKEN="<STS_TOKEN>"
```

### 6.2 STS Signing Headers

When using STS, add `X-Acs-Security-Token` header to all requests:

```bash
curl -X POST "https://agentrun.${REGION}.aliyuncs.com/2025-09-10/templates" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: ${ACCOUNT}" \
  -H "X-Acs-Security-Token: ${ALIBABA_CLOUD_SECURITY_TOKEN}" \
  -H "Authorization: ${SIGNATURE}" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d "$BODY"
```

### 6.3 Python STS Signing

```python
def sign_request_with_sts(method, host, path, query, body, ak, sk, region, security_token=""):
    headers = sign_request(method, host, path, query, body, ak, sk, region)

    if security_token:
        headers["X-Acs-Security-Token"] = security_token

    return headers
```

### 6.4 STS Role Assumption Pattern

```yaml
# Delegate to alicloud-ram-ops skill
Step 1: AssumeRole (alicloud-ram-ops)
  - Input: role_arn, session_name, duration_seconds=3600
  - Output: STS AK/SK/Token

Step 2: Set environment variables
  - ALIBABA_CLOUD_ACCESS_KEY_ID = {{output.sts_ak}}
  - ALIBABA_CLOUD_ACCESS_KEY_SECRET = {{output.sts_sk}}
  - ALIBABA_CLOUD_SECURITY_TOKEN = {{output.sts_token}}

Step 3: Execute AgentRun operations with STS credentials
  - All API calls include X-Acs-Security-Token header
```

---

## 7. Audit & Compliance (ActionTrail Integration)

### 7.1 AgentRun Event Categories

| Event Category | Events Captured | Compliance Relevance |
|----------------|-----------------|----------------------|
| `Management` | CreateTemplate, DeleteTemplate, UpdateTemplate | Change tracking |
| `Management` | CreateSandbox, StopSandbox, DeleteSandbox | Lifecycle audit |
| `Management` | ActivateTemplateMCP, StopTemplateMCP | MCP service audit |
| `Data` | ExecuteCode, ExecCommand, WriteFile | Data access audit |

### 7.2 ActionTrail Integration Pattern

```yaml
# Delegate to alicloud-actiontrail-ops skill

Step 1: Enable ActionTrail (alicloud-actiontrail-ops)
  - Execute: CreateTrail
  - Input: trail_name, oss_bucket, event_types
  - Output: {{output.trail_name}}

Step 2: Query AgentRun Events (alicloud-actiontrail-ops)
  - Execute: LookupEvents
  - Input:
    - EventName: ["CreateTemplate", "DeleteTemplate", "CreateSandbox", "DeleteSandbox"]
    - ResourceType: "ACS::AgentRun::*"
    - StartTime: "{{start_time}}"
    - EndTime: "{{end_time}}"
  - Output: {{output.events}}

Step 3: Generate Audit Report
  - Parse events for compliance violations
  - Check: DeleteTemplate events without prior sandbox cleanup
  - Check: CreateSandbox bursts (potential abuse)
  - Check: ExecuteCode from unexpected source IPs
  - Report: Monthly audit summary
```

### 7.3 Compliance Checklist

| Compliance Requirement | Implementation | Status |
|------------------------|----------------|--------|
| **ISO 27001** | Access control, encryption, audit trails | ✅ Supported |
| **SOC 2** | Data protection, change management | ✅ Supported |
| **MLPS 2.0** | Network isolation, audit logging | ✅ Supported |

---

## 8. Security Incident Response

### 8.1 Incident Classification

| Severity | Indicators | Response Time |
|----------|------------|---------------|
| **Critical** | Sandbox executing malicious code, credential leak | < 15 min |
| **High** | Unauthorized template creation, RAM policy drift | < 1 hour |
| **Medium** | Suspicious command execution, unexpected sandbox creation | < 24 hours |
| **Low** | Missing MFA, stale audit trail config | < 7 days |

### 8.2 Incident Response Runbook

```yaml
# Security Incident Response Flow

Phase 1: Detection (0-5 min)
  - Alert from ActionTrail or monitoring
  - Identify affected sandbox/template
  - Classify severity

Phase 2: Containment (5-15 min)
  - StopSandbox if executing malicious code
  - Revoke compromised credentials via RAM
  - Switch to PRIVATE network mode if public exposure

Phase 3: Investigation (15-60 min)
  - Query ActionTrail for unauthorized operations
  - Check RAM policy changes
  - Analyze ExecCommand history for anomalies

Phase 4: Recovery (60-120 min)
  - Delete compromised sandbox
  - Create new sandbox with hardened template
  - Update RAM policies with tighter restrictions

Phase 5: Post-Incident (2-7 days)
  - Document incident timeline
  - Update security controls
  - Conduct root cause analysis
  - Rotate AK/SK if credential exposure suspected
```

---

## 9. Security Assessment Checklist

### P0 — MUST Pass (Critical)

| Check | Status | Evidence |
|-------|--------|----------|
| RAM policy scoped to specific resources | ✅ | Use policy templates §1.1-1.4 |
| Credential masking enforced | ✅ | `verify_credentials_securely()` §2.1 |
| HTTPS enforced for all connections | ✅ | TLS 1.2+ for all endpoints |
| Safety gates for destructive operations | ✅ | §4 Safety Gate Matrix |
| Input validation before API calls | ✅ | §3 Validation Specification |

### P1 — SHOULD Pass (Important)

| Check | Status | Evidence |
|-------|--------|----------|
| STS temporary credentials used | ✅ | §6 STS Credential Flow |
| PRIVATE network mode for sensitive workloads | ✅ | §5.1 PRIVATE Mode |
| Dangerous command detection | ✅ | §3.2 Command Safety |
| Path traversal protection | ✅ | §3.3 Path Safety |
| ActionTrail enabled for audit | ✅ | §7 Audit Integration |
| Security incident runbook exists | ✅ | §8 Incident Response |

---

*This guide aligns AgentRun operations with Alibaba Cloud Well-Architected Framework Security Pillar best practices.*
