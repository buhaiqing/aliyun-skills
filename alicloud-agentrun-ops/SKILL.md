---
name: alicloud-agentrun-ops
description: >-
  Use when the user needs to inspect, manage, or operate Alibaba Cloud AgentRun
  Sandbox resources — templates, sandbox instances, code execution, file system,
  and terminal operations. User mentions "AgentRun", "Sandbox", "Code Interpreter",
  "BrowserTool", "AIO Sandbox", "沙箱", "AgentRun", "代码解释器", or describes
  sandbox-related scenarios (e.g., create sandbox, execute code in sandbox,
  manage sandbox templates, file operations in sandbox, terminal/tty access)
  even without naming the product directly. Not for developing Sidecar middleware
  (use alicloud-sandbox-dev), RAM-only tasks, or billing operations.
license: MIT
compatibility: >-
  HTTP client (curl or Go/Python HTTP library), ACS3-HMAC-SHA256 signing capability,
  valid Alibaba Cloud API credentials (AK/SK or STS), network access to AgentRun
  endpoints. No official CLI or SDK — direct HTTP API calls required.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-18"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  api_profile: "AgentRun 2025-09-10 / https://help.aliyun.com/zh/functioncompute/fc/sandbox-function"
  cli_applicability: "sdk-only"
  cli_support_evidence: >-
    No official `aliyun agentrun` CLI exists. AgentRun APIs require direct HTTP
    calls with ACS3-HMAC-SHA256 signing. Control plane: agentrun.{region}.aliyuncs.com.
    Data plane: {account}.agentrun-data.{region}.aliyuncs.com.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
    - ALIBABA_CLOUD_ACCOUNT_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud AgentRun Sandbox Operations Skill

## Overview

Alibaba Cloud AgentRun is a serverless sandbox service providing isolated execution environments for code interpretation, browser automation, and AI agent tasks. This skill is an **operational runbook** for agents: manage templates, create/stop/delete sandbox instances, execute code, manage files, and access terminal — all via **direct HTTP API calls** with ACS3-HMAC-SHA256 signing.

**Critical Note:** AgentRun has **NO official CLI (`aliyun agentrun`) or SDK**. All operations require:
1. Constructing signed HTTP requests
2. Calling control plane (`agentrun.{region}.aliyuncs.com`) or data plane (`{account}.agentrun-data.{region}.aliyuncs.com`)

> **UX Compliance:** This skill follows the [User Experience Specification](references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: sdk-only`:** AgentRun has no official CLI. All operations use **direct HTTP API** with ACS3-HMAC-SHA256 signing. See [references/api-signing.md](references/api-signing.md) for signing implementation.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use with explicit triggers and delegation to sandbox-dev for middleware development |
| 2 | **Structured I/O** | `{{env.*}}` for credentials; `{{user.*}}` for sandbox/template names; `{{output.*}}` from API responses |
| 3 | **Explicit Actionable Steps** | Pre-flight → Sign Request → Execute HTTP → Validate → Recover for every operation |
| 4 | **Complete Failure Strategies** | 15+ AgentRun error patterns; HALT vs retry per error category |
| 5 | **Absolute Single Responsibility** | AgentRun/Sandbox operations only; Sidecar development → alicloud-sandbox-dev |

### Well-Architected Framework Integration (卓越架构)

| Pillar | AgentRun-Specific Integration | Reference |
|--------|------------------------------|-----------|
| **安全 (Security)** | ACS3-HMAC-SHA256 signing, AK/SK isolation, sandbox resource boundaries | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | 6-hour sandbox lifecycle, idle timeout, session affinity, graceful termination | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Sandbox billing per execution-time, idle detection, template resource optimization | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch sandbox operations, template reuse, concurrent code execution | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | Sandbox startup latency, code execution timeout, resource sizing | `references/well-architected-assessment.md` §2.5 |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "AgentRun", "Sandbox", "Code Interpreter", "BrowserTool", "AIO Sandbox", "沙箱"
- Task involves CRUD operations on **Templates** (create, get, list, update, delete)
- Task involves **Sandbox Instances** (create, get, list, stop, delete)
- Task involves **Code Execution** in sandbox (execute Python/Node.js/Go code)
- Task involves **File System Operations** in sandbox (read, write, list, upload, download)
- Task involves **Terminal/TTY** access to sandbox (run commands, WebSocket TTY)
- Task involves **MCP Service** management (activate/stop MCP on templates)
- Keywords: sandbox, template, execute code, tty, terminal, file system, 沙箱, 代码执行, 模板

### SHOULD NOT Use This Skill When

- Task is developing Sidecar middleware/proxy → delegate to: `alicloud-sandbox-dev`
- Task is RAM permission management → delegate to: `alicloud-ram-ops`
- Task is FC function deployment → delegate to: `alicloud-fc-ops`
- Task is billing/account management → delegate to: billing ops skill
- User wants **console-only** operations → state limitation

### Delegation Rules

| Task | Delegate To | Reason |
|------|-------------|--------|
| Build Sidecar proxy for AgentRun | `alicloud-sandbox-dev` | Development skill for middleware |
| RAM policy for AgentRun permissions | `alicloud-ram-ops` | Permission management |
| FC function hosting sandbox | `alicloud-fc-ops` | Function Compute operations |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Region (e.g., cn-hangzhou) | Use default if unset |
| `{{env.ALIBABA_CLOUD_ACCOUNT_ID}}` | Main account ID for data plane URL | Required for data plane ops |
| `{{user.template_name}}` | Template identifier | Ask once; reuse |
| `{{user.sandbox_id}}` | Sandbox instance ID (ULID) | Ask once; reuse |
| `{{output.sandbox_id}}` | From CreateSandbox response | Parse `.sandboxId` |
| `{{output.template_id}}` | From CreateTemplate response | Parse `.templateId` |

## API Endpoints Overview

### Control Plane
Base: `https://agentrun.{region}.aliyuncs.com/2025-09-10`

| API | Method | Path | Purpose |
|-----|--------|------|---------|
| CreateTemplate | POST | `/templates` | Create sandbox template |
| GetTemplate | GET | `/templates/{templateName}` | Get template details |
| ListTemplates | GET | `/templates` | List templates (paginated) |
| UpdateTemplate | PUT | `/templates/{templateName}` | Update template config |
| DeleteTemplate | DELETE | `/templates/{templateName}` | Delete template |
| StopTemplateMCP | PATCH | `/templates/{templateName}/mcp/stop` | Stop MCP service |
| ActivateTemplateMCP | PATCH | `/templates/{templateName}/mcp/activate` | Enable MCP service |
| CreateSandbox | POST | `/sandboxes` | Create sandbox instance |
| GetSandbox | GET | `/sandboxes/{sandboxId}` | Get sandbox details |
| ListSandboxes | GET | `/sandboxes` | List sandboxes (paginated) |
| StopSandbox | POST | `/sandboxes/{sandboxId}/stop` | Stop sandbox |
| DeleteSandbox | DELETE | `/sandboxes/{sandboxId}` | Delete sandbox |

### Data Plane
Base: `https://{account}.agentrun-data.{region}.aliyuncs.com`

| API | Method | Path | Purpose |
|-----|--------|------|---------|
| CreateContext | POST | `/sandboxes/{sandboxId}/contexts` | Create execution context |
| ListContexts | GET | `/sandboxes/{sandboxId}/contexts` | List contexts |
| DeleteContext | DELETE | `/sandboxes/{sandboxId}/contexts/{contextId}` | Delete context |
| ExecuteCode | POST | `/sandboxes/{sandboxId}/contexts/execute` | Execute code |
| ListFiles | GET | `/sandboxes/{sandboxId}/filesystem` | List directory |
| ReadFile | GET | `/sandboxes/{sandboxId}/files` | Read file content |
| WriteFile | POST | `/sandboxes/{sandboxId}/files` | Write file |
| UploadFile | POST | `/sandboxes/{sandboxId}/filesystem/upload` | Upload file (multipart) |
| DownloadFile | GET | `/sandboxes/{sandboxId}/filesystem/download` | Download file |
| CreateDirectory | POST | `/sandboxes/{sandboxId}/filesystem/mkdir` | Create directory |
| MoveFile | POST | `/sandboxes/{sandboxId}/filesystem/move` | Move/rename |
| RemoveFile | POST | `/sandboxes/{sandboxId}/filesystem/remove` | Delete file/directory |
| ExecCommand | POST | `/sandboxes/{sandboxId}/processes/cmd` | Execute command |
| ListProcesses | GET | `/sandboxes/{sandboxId}/processes` | List processes |
| KillProcess | DELETE | `/sandboxes/{sandboxId}/processes/{pid}` | Kill process |
| HealthCheck | GET | `/sandboxes/{sandboxId}/health` | Health check |
| WebSocketTTY | WS | `/sandboxes/{sandboxId}/processes/tty` | Interactive terminal |

Full API details: [references/api-reference.md](references/api-reference.md)

## Quick Start

### What This Skill Does
Manage Alibaba Cloud AgentRun Sandbox resources — templates, instances, code execution, files, and terminals via direct HTTP API calls.

### Prerequisites
- [ ] Valid AK/SK credentials with AgentRun permissions
- [ ] Region configured (e.g., cn-hangzhou)
- [ ] Account ID for data plane URLs
- [ ] HTTP client (curl, Go, Python, or Node.js)

### Your First Command (Create Template)

**Step 1: Generate Signature with Python Helper**

```python
# sign_helper.py - ACS3-HMAC-SHA256 signing helper
import hashlib, hmac, datetime, json, urllib.parse

def sign_request(method, host, path, query, body, ak, sk, region):
    now = datetime.datetime.utcnow()
    date_time = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    
    body_bytes = body.encode('utf-8') if isinstance(body, str) else body
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    
    # Canonical headers (sorted lowercase)
    headers_str = f"content-type:application/json\nhost:{host}\nx-acs-content-sha256:{body_hash}\nx-acs-date:{date_time}\n"
    signed_headers = "content-type;host;x-acs-content-sha256;x-acs-date"
    
    # Canonical request
    canonical_request = f"{method}\n{path}\n{query}\n{headers_str}\n{signed_headers}\n{body_hash}"
    cr_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
    
    # String to sign
    scope = f"{date}/{region}/agentrun/aliyun_v4_request"
    string_to_sign = f"ACS3-HMAC-SHA256\n{date_time}\n{scope}\n{cr_hash}"
    
    # Signing key derivation
    k_secret = ("ACS3" + sk).encode('utf-8')
    k_date = hmac.new(k_secret, date.encode('utf-8'), hashlib.sha256).digest()
    k_region = hmac.new(k_date, region.encode('utf-8'), hashlib.sha256).digest()
    k_service = hmac.new(k_region, "agentrun".encode('utf-8'), hashlib.sha256).digest()
    k_signing = hmac.new(k_service, "aliyun_v4_request".encode('utf-8'), hashlib.sha256).digest()
    
    # Signature
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return f"ACS3-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"

# Example usage
ak = "${ALIBABA_CLOUD_ACCESS_KEY_ID}"
sk = "${ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
region = "${ALIBABA_CLOUD_REGION_ID}"
host = f"agentrun.{region}.aliyuncs.com"
body = '{"templateName":"my-template","cpu":2,"memory":4096}'
auth = sign_request("POST", host, "/2025-09-10/templates", "", body, ak, sk, region)
print(auth)
```

**Step 2: Execute HTTP Request**

```bash
# Generate authorization header
AUTH=$(python3 sign_helper.py)

# Create template
curl -X POST "https://agentrun.${ALIBABA_CLOUD_REGION_ID}.aliyuncs.com/2025-09-10/templates" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: ${ALIBABA_CLOUD_ACCOUNT_ID}" \
  -H "Authorization: ${AUTH}" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d '{"templateName":"my-template","cpu":2,"memory":4096}'
```

### Next Steps
- [API Signing Guide](references/api-signing.md) — ACS3-HMAC-SHA256 implementation
- [API Reference](references/api-reference.md) — Full endpoint documentation
- [Troubleshooting](references/troubleshooting.md) — Common errors and fixes

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateTemplate | Create sandbox template | Medium | Low |
| GetTemplate/ListTemplates | Query template(s) | Low | None |
| UpdateTemplate | Modify template config | Medium | Medium |
| DeleteTemplate | Delete template | Low | **High** — irreversible |
| CreateSandbox | Create sandbox instance | Medium | Low |
| GetSandbox/ListSandboxes | Query sandbox(es) | Low | None |
| StopSandbox | Stop running sandbox | Low | Medium |
| DeleteSandbox | Delete sandbox | Low | **High** — irreversible |
| ExecuteCode | Run code in sandbox | Medium | Low |
| FileOperations | Read/write/upload/download files | Medium | Low |
| ExecCommand | Run shell commands | Medium | Medium |
| WebSocketTTY | Interactive terminal | High | Medium |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-18 | Initial AgentRun ops skill — template/instance CRUD, code execution, file ops, TTY |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Sign Request → Execute HTTP → Validate → Recover**.

### Operation: Create Template

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | env vars non-empty | AK + SK + Region + Account ID | HALT; configure env |
| Template name valid | Regex check | 1-64 chars, alphanumeric/hyphen/underscore | Ask user for valid name |
| RAM permissions | Check `fc:CreateTemplate` action | Permission granted | HALT; delegate to ram-ops |

#### Execution — HTTP API (Direct Call)

```bash
# Build request body
BODY='{
  "templateName": "{{user.template_name}}",
  "description": "{{user.description|default:""}}",
  "cpu": {{user.cpu|default:2}},
  "memory": {{user.memory|default:4096}},
  "sandboxIdleTimeoutInSeconds": {{user.idle_timeout|default:1800}},
  "networkConfiguration": {
    "networkMode": "{{user.network_mode|default:"PUBLIC"}}"
  }
}'

# Generate signature (see api-signing.md)
SIGNATURE=$(generate_acs3_signature "POST" "/2025-09-10/templates" "" "$BODY")

# Execute request
curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -H "X-Acs-Content-Sha256: $(echo -n "$BODY" | sha256sum | cut -d' ' -f1)" \
  -d "$BODY"
```

#### Post-execution Validation

1. Parse `{{output.template_id}}` from response `.templateId`
2. Verify status: `$.status` should be `READY`
3. If status != READY, poll GetTemplate until READY (interval 5s, max 60s)

#### Failure Recovery

| Error Code | HTTP Status | Max Retries | Agent Action | UX Feedback |
|------------|-------------|-------------|--------------|-------------|
| `InvalidParameter` | 400 | 0 | Fix request body | `[ERROR] InvalidParameter: Check cpu, memory, templateName values.` |
| `TemplateAlreadyExists` | 409 | 0 | Ask reuse vs new name | `[ERROR] Template already exists. Use different name or update existing.` |
| `Forbidden.RAM` | 403 | 0 | HALT; delegate to ram-ops | `[ERROR] Missing fc:CreateTemplate permission. Request RAM policy update.` |
| `QuotaExceeded` | 429 | 0 | HALT | `[ERROR] Template quota exceeded. Request quota increase.` |
| `InternalError` | 500 | 3 | Exponential backoff | `⚠️ Server error. Retrying...` |

### Operation: Create Sandbox

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Template exists | GetTemplate call | status = READY | HALT; create template first |
| Credentials | env vars | AK/SK/Region/Account | HALT; configure env |

#### Execution — HTTP API

```bash
BODY='{"templateName": "{{user.template_name}}"}'

curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -H "X-Acs-Content-Sha256: $(echo -n "$BODY" | sha256sum | cut -d' ' -f1)" \
  -d "$BODY"
```

#### Post-execution Validation

1. Parse `{{output.sandbox_id}}` from response `.sandboxId`
2. Poll GetSandbox until status = `READY` (interval 5s, max 120s)
3. Sandbox lifecycle: **max 6 hours** from creation

### Operation: Execute Code in Sandbox

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Sandbox READY | GetSandbox call | status = READY | HALT; sandbox not ready |
| Account ID | env var | Non-empty | HALT; required for data plane |

#### Execution — Data Plane HTTP API

```bash
BODY='{
  "language": "{{user.language|default:"python"}}",
  "code": "{{user.code}}",
  "timeout": {{user.timeout|default:30}}
}'

curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/contexts/execute" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

#### Response Parsing

| Field | Path | Description |
|-------|------|-------------|
| `results` | `.results[]` | Execution output items |
| `stdout` | `.results[type="stdout"].text` | Standard output |
| `stderr` | `.results[type="stderr"].text` | Standard error |
| `result` | `.results[type="result"].text` | Return value |
| `status` | `.results[type="endOfExecution"].status` | `ok`, `error`, `timeout` |

### Operation: Delete Sandbox (Safety Gate)

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of sandbox `{{user.sandbox_id}}`
- **MUST** warn: all files, contexts, and state will be lost
- **MUST NOT** proceed without clear assent

#### Execution

```bash
# If sandbox is READY, stop first
curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes/{{user.sandbox_id}}/stop" \
  -H "Authorization: $SIGNATURE" ...

# Then delete
curl -X DELETE "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes/{{user.sandbox_id}}" \
  -H "Authorization: $SIGNATURE" ...
```

#### Post-execution Validation

- Poll GetSandbox until 404 or status = TERMINATED (interval 5s, max 60s)

### Operation: Backup Sandbox Files (Stability Pillar)

> **Stability Pillar:** Following Alibaba Cloud Well-Architected Framework §面向风险的应急快恢, every writable skill MUST document backup and recovery operations.

#### When to Use
- Before destructive operations (delete sandbox, upgrade template)
- Scheduled backup for critical sandbox data
- Migration or data transfer prerequisites

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Sandbox READY | GetSandbox call | status = READY | HALT; sandbox not accessible |
| Files exist | ListFiles call | Non-empty entries | Warn user; proceed if confirmed |
| Download quota | Check file count/size | Within limits | HALT; too many/large files |

#### Execution — Data Plane HTTP API

```bash
# Step 1: List files to backup
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem?path=/workspace&depth=2" \
  -H "Authorization: $SIGNATURE" ...

# Step 2: Download each file (batch)
for file in $FILES; do
  curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/download?path=$file" \
    -H "Authorization: $SIGNATURE" \
    -o "./backup/$file"
done
```

#### Post-execution Validation

1. Verify backup integrity: checksum comparison or file size match
2. Record backup metadata: timestamp, file count, total size
3. Store backup location for restore reference

### Operation: Restore Files to Sandbox (Stability Pillar)

> **Stability Pillar — Emergency Recovery:** Restore sandbox files from backup after recreation.

#### Pre-flight (Safety Gate)

- **MUST** confirm: target sandbox `{{user.sandbox_id}}`, backup source path
- **MUST** warn: existing files may be overwritten

#### Execution — Data Plane HTTP API

```bash
# Step 1: Ensure sandbox is READY (create if needed)
# See CreateSandbox operation

# Step 2: Upload backup files
for file in $BACKUP_FILES; do
  curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/upload" \
    -H "Authorization: $SIGNATURE" \
    -F "file=@./backup/$file" \
    -F "path=/workspace/$file"
done
```

#### Post-execution Validation

1. Verify file count matches backup
2. Check file integrity via ListFiles + size comparison
3. Execute test code to verify data accessibility

## Sandbox Lifecycle Constraints

| Constraint | Value | Configurable? |
|------------|-------|---------------|
| Maximum hard lifecycle | **6 hours** | ❌ No |
| Idle timeout (`sandboxIdleTimeoutInSeconds`) | User-defined | ✅ Yes (recommended < 21600) |
| Maximum file upload | 100 MB | ❌ No |
| Code execution timeout | 30 seconds (data plane gateway) | ✅ Per-call (up to 30s) |
| Code execution timeout (context) | User-defined | ✅ In request body |

**State Machine:**
```
CREATING ──► READY ──(idle timeout / 6h hard limit / StopSandbox)──► TERMINATED
```

## Safety Gates

### Destructive Operations

| Operation | Impact | Confirmation Required |
|-----------|--------|----------------------|
| `DeleteTemplate` | **Cannot create** new sandboxes from this template | Yes — confirm templateId and check dependents |
| `DeleteSandbox` | **Permanent loss** of sandbox state, files, contexts | Yes — confirm sandboxId matches |
| `filesystem/remove` | **Deletes** files/directories in sandbox | Verify path is not `/` or critical system path |

### Credential Security

- **NEVER** log AK/SK or Signature values
- **DO** use environment variables for credential injection
- **DO** mask credentials in error messages: `<masked>`
- **PREFER** STS temporary credentials when possible

## Prerequisites

1. **Configure credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
   export ALIBABA_CLOUD_ACCOUNT_ID="{{env.ALIBABA_CLOUD_ACCOUNT_ID}}"
   ```

2. **Implement ACS3-HMAC-SHA256 signing** — see [api-signing.md](references/api-signing.md)

3. **Verify permissions**: RAM policy must include `fc:CreateTemplate`, `fc:CreateSandbox`, etc.

## Reference Directory

- [API Reference](references/api-reference.md) — Full endpoint documentation
- [API Signing Guide](references/api-signing.md) — ACS3-HMAC-SHA256 implementation
- [Core Concepts](references/core-concepts.md) — Sandbox architecture and limits
- [Troubleshooting](references/troubleshooting.md) — Error codes and diagnostics
- [Monitoring Guide](references/monitoring.md) — Observability, metrics, and alerting
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar integration
- [Integration](references/integration.md) — Credential setup and signing workflow