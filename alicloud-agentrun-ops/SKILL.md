---
name: alicloud-agentrun-ops
description: >-
  Use when the user needs to inspect, manage, or operate Alibaba Cloud AgentRun
  Sandbox resources — templates, sandbox instances, code execution, file system,
  and terminal operations. User mentions "AgentRun", "Sandbox", "Code Interpreter",
  "BrowserTool", "AIO Sandbox", "沙箱", "AgentRun", "代码解释器", or describes
  sandbox-related scenarios (e.g., create sandbox, execute code in sandbox,
  manage sandbox templates, file operations in sandbox, terminal/tty access,
  MCP enabledTools, OSS-mounted custom Skills, Agent & Skills, Skill Hub vs OSS,
  Sandbox GPU support)
  even without naming the product directly. Not for developing Sidecar middleware
  (use alicloud-sandbox-dev), RAM-only tasks, or billing operations.
license: MIT
compatibility: >-
  HTTP client (curl or Go/Python HTTP library), ACS3-HMAC-SHA256 signing capability,
  valid Alibaba Cloud API credentials (AK/SK or STS), network access to AgentRun
  endpoints. No official CLI or SDK — direct HTTP API calls required.
metadata:
  author: alicloud
  version: "1.3.0"
  last_updated: "2026-05-19"
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
    - ALIBABA_CLOUD_SECURITY_TOKEN
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud AgentRun Sandbox Operations Skill

## Overview

Alibaba Cloud AgentRun is a serverless sandbox service providing isolated execution environments for code interpretation, browser automation, and AI agent tasks. This skill is an **operational runbook** for agents: manage templates, create/stop/delete sandbox instances, execute code, manage files, and access terminal — all via **direct HTTP API calls** with ACS3-HMAC-SHA256 signing.

> **Product knowledge** (MCP 双路径、20 个 `enabledTools`、OSS/Skill 加载语义、Tool Hub 对比): 见 [references/knowledge-base.md](references/knowledge-base.md).

**Critical Note:** AgentRun has **NO official CLI (`aliyun agentrun`) or SDK**. All operations require:
1. Constructing signed HTTP requests
2. Calling control plane (`agentrun.{region}.aliyuncs.com`) or data plane (`{account}.agentrun-data.{region}.aliyuncs.com`)

> **UX Compliance:** This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

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
- Task involves **MCP Service** management (activate/stop MCP on templates, `enabledTools`)
- Task involves **OSS-mounted custom Skills**, `enableAgent`, or whether OSS changes hot-reload
- Keywords: sandbox, template, execute code, tty, terminal, file system, MCP, OSS, skills, 沙箱, 代码执行, 模板, 动态挂载

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
| `{{env.ALIBABA_CLOUD_SECURITY_TOKEN}}` | STS temporary credential (optional) | Add `X-Acs-Security-Token` header if set |
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
| PauseSandbox | POST | `/sandboxes/{sandboxId}/pause` | Deep hibernation — pause session |
| ResumeSandbox | POST | `/sandboxes/{sandboxId}/resume` | Deep hibernation — resume session |

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
| DeleteTemplate | Delete template | Low | **High** — irreversible, Safety Gate |
| CreateSandbox | Create sandbox instance | Medium | Low |
| GetSandbox/ListSandboxes | Query sandbox(es) | Low | None |
| StopSandbox | Stop running sandbox | Low | Medium |
| DeleteSandbox | Delete sandbox | Low | **High** — irreversible, Safety Gate |
| ExecuteCode | Run code in sandbox | Medium | Low |
| FileOperations | Read/write/upload/download/mkdir/move/remove files | Medium | Low-Medium |
| ExecCommand | Run shell commands | Medium | **Medium** — Safety Gate, dangerous pattern check |
| WebSocketTTY | Interactive terminal | High | **High** — Safety Gate, unrestricted access |
| ActivateTemplateMCP | Enable MCP service on template | Medium | Low |
| StopTemplateMCP | Disable MCP service on template | Low | Medium |
| ManageContexts | Create/list/delete execution contexts | Low | Low |
| HealthCheck | Check sandbox health | Low | None |
| ProcessManagement | List/kill processes in sandbox | Low | Medium — KillProcess Safety Gate |
| DeepHibernation | Pause/resume sandbox sessions | Medium | Low — cost optimization, state preserved |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.3.0 | 2026-05-19 | Docs: Add references/knowledge-base.md (AgentRun 定位, MCP 双路径, 20 enabledTools, 内置 Skills, OSS 三层加载与「非热更新」语义, Tool Hub vs OSS vs find_agent_on_skills, **Sandbox 不支持 GPU**). Expand core-concepts MCP/OSS/GPU sections; trigger keywords for OSS/Skills. |
| 1.2.0 | 2026-05-19 | F24: Add Deep Hibernation (Pause/Resume) execution flow, add templateType/diskSize/containerConfiguration/PRIVATE network params to CreateTemplate/UpdateTemplate, add HIBERNATED state to state machine, add PauseSandbox/ResumeSandbox to API endpoints. Security2: Add ALIBABA_CLOUD_SECURITY_TOKEN env var, STS X-Acs-Security-Token header in Prerequisites, fix user-experience-spec.md dead link, add templateType/diskSize/networkMode/idleTimeout to Input Validation table. Eval: Add 10 new trigger test cases (021-030) for UpdateTemplate/DeleteTemplate/MCP/Context/DeepHibernation/HealthCheck/ProcessManagement/Mkdir/MoveFile |
| 1.1.0 | 2026-05-19 | Security2: Add security-enhancement.md, fix RAM Policy Resource scoping, credential masking, Safety Gates for DeleteTemplate/ExecCommand/TTY/KillProcess, input validation, STS credential flow. F24: Add execution flows for UpdateTemplate, DeleteTemplate, MCP operations, Context Management, File System operations, ExecCommand, Process Management, HealthCheck, WebSocket TTY, List Resources pagination, example-config.yaml |
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
  "templateType": "{{user.template_type|default:"CodeInterpreter"}}",
  "cpu": {{user.cpu|default:2}},
  "memory": {{user.memory|default:4096}},
  "diskSize": {{user.disk_size|default:10240}},
  "sandboxIdleTimeoutInSeconds": {{user.idle_timeout|default:1800}},
  "networkConfiguration": {
    "networkMode": "{{user.network_mode|default:"PUBLIC"}}"
  }
}'

# PRIVATE network mode (for VPC-isolated sandboxes):
# "networkConfiguration": {
#   "networkMode": "PRIVATE",
#   "vpcId": "{{user.vpc_id}}",
#   "securityGroupId": "{{user.security_group_id}}",
#   "vSwitchId": "{{user.vswitch_id}}"
# }

# Custom container image (optional):
# "containerConfiguration": {
#   "image": "{{user.container_image}}",
#   "port": {{user.container_port|default:5000}}
# }

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

### Operation: Update Template

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Template exists | GetTemplate call | status = READY | HALT; template not found |
| Credentials | env vars non-empty | AK + SK + Region + Account | HALT; configure env |
| Input validation | cpu 1-8, memory 1024-16384 | Valid ranges | HALT; fix parameters |

#### Execution — HTTP API

```bash
BODY='{
  "cpu": {{user.cpu|default:2}},
  "memory": {{user.memory|default:4096}},
  "diskSize": {{user.disk_size|default:10240}},
  "sandboxIdleTimeoutInSeconds": {{user.idle_timeout|default:1800}},
  "networkConfiguration": {
    "networkMode": "{{user.network_mode|default:"PUBLIC"}}"
  }
}'

# PRIVATE network mode (for VPC-isolated sandboxes):
# "networkConfiguration": {
#   "networkMode": "PRIVATE",
#   "vpcId": "{{user.vpc_id}}",
#   "securityGroupId": "{{user.security_group_id}}",
#   "vSwitchId": "{{user.vswitch_id}}"
# }

# Custom container image (optional):
# "containerConfiguration": {
#   "image": "{{user.container_image}}",
#   "port": {{user.container_port|default:5000}}
# }

curl -X PUT "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates/{{user.template_name}}" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -H "X-Acs-Content-Sha256: $(echo -n "$BODY" | sha256sum | cut -d' ' -f1)" \
  -d "$BODY"
```

#### Post-execution Validation

1. Parse response, verify `status` = `READY`
2. Call GetTemplate to confirm changes applied
3. Note: existing sandboxes are NOT affected; only new sandboxes use updated config

#### Failure Recovery

| Error Code | HTTP Status | Agent Action |
|------------|-------------|--------------|
| `InvalidParameter` | 400 | Fix request body values |
| `TemplateNotFound` | 404 | HALT; create template first |
| `Forbidden.RAM` | 403 | HALT; delegate to ram-ops |

### Operation: Delete Template (Safety Gate)

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of template `{{user.template_name}}`
- **MUST** check for dependent sandboxes: call ListSandboxes(templateName) first
- **MUST** warn: all dependent sandboxes must be stopped/deleted first
- **MUST NOT** proceed without clear assent

#### Execution — HTTP API

```bash
# Step 1: Check for dependent sandboxes
curl -X GET "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes?templateName={{user.template_name}}&status=READY" \
  -H "Authorization: $SIGNATURE" ...

# Step 2: If dependent sandboxes exist → HALT
# "⚠️ Cannot delete template: N active sandboxes depend on it. Stop them first."

# Step 3: Delete template (only if no dependents)
curl -X DELETE "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates/{{user.template_name}}" \
  -H "Authorization: $SIGNATURE" ...
```

#### Post-execution Validation

- Call GetTemplate → expect 404 (template deleted)
- Verify no orphaned resources

#### Failure Recovery

| Error Code | HTTP Status | Agent Action |
|------------|-------------|--------------|
| `TemplateDependencyExists` | 409 | HALT; list and delete dependent sandboxes first |
| `TemplateNotFound` | 404 | Already deleted; no action needed |
| `Forbidden.RAM` | 403 | HALT; delegate to ram-ops |

### Operation: Activate Template MCP

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Template exists | GetTemplate call | status = READY | HALT; template not found |
| MCP not already active | Check template config | No active MCP | Warn; may re-activate |
| enabledTools valid | Validate tool names | Known tool names | Fix tool list |

#### Execution — HTTP API

```bash
BODY='{
  "enabledTools": {{user.enabled_tools|default:["health","run_code","read_file","write_file","file_system_list","process_exec_cmd"]}},
  "transport": "{{user.transport|default:"streamable-http"}}"
}'

curl -X PATCH "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates/{{user.template_name}}/mcp/activate" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d "$BODY"
```

#### Post-execution Validation

1. Verify MCP endpoint is accessible
2. Test MCP health tool
3. Confirm mcp-session-id and SandboxID mapping

#### Available MCP Tools

| Tool | Description | Risk Level |
|------|-------------|------------|
| `health` | Health check | None |
| `run_code` | Execute code | Low |
| `list_contexts` / `create_context` / `get_context` / `delete_context` | Context management | Low |
| `read_file` / `write_file` | File read/write | Low |
| `file_system_list` / `file_system_stat` / `file_system_download` | File system info | Low |
| `file_system_mkdir` / `file_system_move` / `file_system_remove` | File system modify | Medium |
| `file_system_upload` | File upload | Medium |
| `process_exec_cmd` | Execute command | **Medium** — Safety Gate recommended |
| `process_tty` | Interactive terminal | **High** — Safety Gate required |
| `process_list` / `process_stat` / `process_kill` | Process management | Medium |

### Operation: Stop Template MCP

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Template exists | GetTemplate call | status = READY | HALT; template not found |
| MCP active | Check template config | Active MCP | Warn; already stopped |

#### Execution — HTTP API

```bash
curl -X PATCH "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates/{{user.template_name}}/mcp/stop" \
  -H "Authorization: $SIGNATURE" ...
```

#### Post-execution Validation

1. Verify MCP endpoint returns 404/unavailable
2. Note: MCP resources are deleted, MCP endpoint no longer accessible

### Operation: Manage Execution Contexts

#### Create Context

```bash
BODY='{
  "language": "{{user.language|default:"python"}}",
  "cwd": "{{user.cwd|default:"/home/user"}}"
}'

curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/contexts" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

**Response**: Parse `{{output.context_id}}` from response `.id`

#### List Contexts

```bash
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/contexts" \
  -H "Authorization: $SIGNATURE" ...
```

#### Delete Context

```bash
curl -X DELETE "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/contexts/{{user.context_id}}" \
  -H "Authorization: $SIGNATURE" ...
```

**When to use**: Clean up stale contexts to free resources; switch between isolated execution environments.

### Operation: File System Operations

#### Read File

```bash
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/files?path={{user.file_path}}" \
  -H "Authorization: $SIGNATURE" ...
```

**Pre-flight**: Validate path — no `..` traversal, no hidden files (`.` prefix)

#### Write File

```bash
BODY='{
  "path": "{{user.file_path}}",
  "content": "{{user.file_content}}",
  "encoding": "utf-8"
}'

curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/files" \
  -H "Content-Type: application/json" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

**Constraints**: No hidden files, auto-creates parent dirs, default permission 0644

#### Upload File (Multipart)

```bash
curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/upload" \
  -H "Authorization: $SIGNATURE" \
  -F "file=@{{user.local_file_path}}" \
  -F "path={{user.target_path}}"
```

**Constraint**: Max 100MB per file

#### Download File

```bash
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/download?path={{user.file_path}}" \
  -H "Authorization: $SIGNATURE" \
  -o "{{user.local_save_path}}"
```

#### Create Directory

```bash
BODY='{"path": "{{user.dir_path}}"}'
curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/mkdir" \
  -H "Content-Type: application/json" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

#### Move / Rename File

```bash
BODY='{"source": "{{user.source_path}}", "destination": "{{user.dest_path}}"}'
curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/move" \
  -H "Content-Type: application/json" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

#### Remove File / Directory

```bash
BODY='{"path": "{{user.target_path}}"}'
curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/filesystem/remove" \
  -H "Content-Type: application/json" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

**Pre-flight (Safety Gate)**: Verify path is not `/` or critical system path

### Operation: Execute Command in Sandbox (Safety Gate)

#### Pre-flight (Safety Gate)

- **MUST** validate command against dangerous pattern list (see [security-enhancement.md](references/security-enhancement.md) §3.2)
- **SHOULD** warn user for commands with medium/high risk patterns
- **MUST NOT** execute commands matching critical dangerous patterns (e.g., `rm -rf /`, `curl | bash`)

#### Execution — Data Plane HTTP API

```bash
BODY='{
  "command": "{{user.command}}",
  "cwd": "{{user.cwd|default:"/home/user"}}"
}'

curl -X POST "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/processes/cmd" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -d "$BODY"
```

**Hard Timeout**: 30 seconds (data plane gateway enforced)

#### Response Parsing

| Field | Path | Description |
|-------|------|-------------|
| `executionId` | `.executionId` | Execution identifier |
| `exitCode` | `.result.exitCode` | 0 = success |
| `stdout` | `.result.stdout` | Standard output |
| `stderr` | `.result.stderr` | Standard error |
| `cwd` | `.result.cwd` | Working directory after execution |

#### Failure Recovery

| Error Code | HTTP Status | Agent Action |
|------------|-------------|--------------|
| `SandboxNotReady` | 400 | HALT; wait for sandbox READY |
| `SandboxTerminated` | 400 | Create new sandbox |
| `ExecutionTimeout` | 400 | Reduce command complexity |

### Operation: Process Management

#### List Processes

```bash
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/processes" \
  -H "Authorization: $SIGNATURE" ...
```

#### Kill Process (Safety Gate)

- **MUST** confirm: killing PID `{{user.pid}}` in sandbox `{{user.sandbox_id}}`
- **MUST** warn: process will receive SIGTERM, then SIGKILL if unresponsive

```bash
curl -X DELETE "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/processes/{{user.pid}}" \
  -H "Authorization: $SIGNATURE" ...
```

### Operation: Health Check

```bash
curl -X GET "https://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/health" \
  -H "Authorization: $SIGNATURE" ...
```

**Expected Response**:
```json
{"status": "ok", "service": "sandbox-code-interpreter", "version": "v1"}
```

**When to use**: Before ExecuteCode, before file operations, periodic monitoring

### Operation: WebSocket TTY (Safety Gate)

#### Pre-flight (Safety Gate)

- **MUST** warn: interactive terminal provides full shell access to sandbox
- **MUST** confirm: user explicitly requests TTY access
- **MUST** verify sandbox status = READY

#### Connection

```
wss://{{env.ALIBABA_CLOUD_ACCOUNT_ID}}.agentrun-data.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/sandboxes/{{user.sandbox_id}}/processes/tty?protocol=json&tenantId={{env.ALIBABA_CLOUD_ACCOUNT_ID}}
```

**Authentication**: ACS3-HMAC-SHA256 signing via query parameters or initial HTTP upgrade headers

**Protocol**: JSON-based message framing over WebSocket

#### Safety Considerations

- TTY provides **unrestricted shell access** — treat as high-risk operation
- All TTY commands bypass the ExecCommand dangerous pattern detection
- Recommend: prefer ExecCommand over TTY when possible for auditability
- Log all TTY session metadata (start time, duration, sandbox ID) for audit

### Operation: List Resources (Pagination)

#### List Templates

```bash
curl -X GET "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/templates?pageSize=20&pageNumber=1&status=READY" \
  -H "Authorization: $SIGNATURE" ...
```

**Pagination**: Use `pageNumber` + `pageSize`; iterate until `items` is empty

#### List Sandboxes

```bash
curl -X GET "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes?maxResults=100&nextToken=&status=READY" \
  -H "Authorization: $SIGNATURE" ...
```

**Pagination**: Use `nextToken` cursor; continue while `nextToken` is non-empty

#### Full Pagination Pattern

```python
def list_all_sandboxes(status=None):
    all_items = []
    next_token = ""
    while True:
        params = {"maxResults": 100, "nextToken": next_token}
        if status:
            params["status"] = status
        response = call_api("GET", "/sandboxes", params=params)
        all_items.extend(response["data"]["items"])
        next_token = response["data"].get("nextToken", "")
        if not next_token:
            break
    return all_items
```

### Operation: Deep Hibernation (Pause/Resume Session)

> **Stability Pillar — Cost Optimization:** Pause sandbox sessions to release compute resources while preserving file system state. Resume later without recreating the sandbox.

#### When to Use
- Long idle periods between task bursts (> 30 min)
- Cost optimization: pause instead of paying for idle compute
- Session persistence: preserve file system state across pauses

#### Pause Session

**Pre-flight Checks**

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Sandbox exists | GetSandbox call | status = READY | HALT; sandbox not ready |
| No active executions | Check processes | No running code | Warn; stop processes first |

```bash
# Pause session — releases compute, preserves file system
curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes/{{user.sandbox_id}}/pause" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d '{}'
```

**Post-pause**: Sandbox status changes to `HIBERNATED`. File system is preserved; compute resources released.

#### Resume Session

```bash
# Resume session — re-allocates compute, restores file system + execution environment
curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes/{{user.sandbox_id}}/resume" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d '{}'
```

**Post-resume**: Poll GetSandbox until status = `READY` (interval 5s, max 120s). File system and execution environment fully restored.

#### File System Only Recovery

```bash
# Resume file system only — restores files but NOT execution environment (contexts lost)
curl -X POST "https://agentrun.{{env.ALIBABA_CLOUD_REGION_ID}}.aliyuncs.com/2025-09-10/sandboxes/{{user.sandbox_id}}/resume" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: {{env.ALIBABA_CLOUD_ACCOUNT_ID}}" \
  -H "Authorization: $SIGNATURE" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -d '{"fileSystemOnly": true}'
```

**When to use**: When execution context is not needed, only file data. Faster resume, lower cost.

#### State Machine (Extended)

```
CREATING ──► READY ──(pause)──► HIBERNATED ──(resume)──► READY
                │                                         │
                └──(idle timeout / 6h hard limit / stop)──► TERMINATED
```

#### Failure Recovery

| Error Code | HTTP Status | Agent Action |
|------------|-------------|--------------|
| `SandboxNotReady` | 400 | HALT; sandbox must be READY to pause |
| `SandboxNotHibernated` | 400 | HALT; sandbox must be HIBERNATED to resume |
| `SandboxTerminated` | 400 | Create new sandbox; cannot resume TERMINATED |
| `InternalError` | 500 | Retry with exponential backoff (max 3) |

**Reference**: [暂停与恢复会话](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session) | [仅恢复文件系统](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-sleep-file-system-only-recovery)

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
CREATING ──► READY ──(pause)──► HIBERNATED ──(resume)──► READY
                │                                         │
                └──(idle timeout / 6h hard limit / stop)──► TERMINATED
```

## Safety Gates

### Destructive Operations

| Operation | Impact | Confirmation Required |
|-----------|--------|----------------------|
| `DeleteTemplate` | **Cannot create** new sandboxes from this template | Yes — confirm templateName, check dependent sandboxes first |
| `DeleteSandbox` | **Permanent loss** of sandbox state, files, contexts | Yes — confirm sandboxId matches |
| `ExecCommand` | **Arbitrary shell execution** in sandbox | Conditional — validate against dangerous patterns (see [security-enhancement.md](references/security-enhancement.md) §3.2) |
| `WebSocketTTY` | **Unrestricted interactive terminal** access | Yes — warn full shell access, confirm user intent |
| `KillProcess` | **Force-stop** running process (SIGTERM/SIGKILL) | Yes — confirm PID and sandbox |
| `filesystem/remove` | **Deletes** files/directories in sandbox | Verify path is not `/` or critical system path |
| `UpdateTemplate` | **Modifies** template config (affects new sandboxes) | Conditional — warn impact scope |

### Input Validation

All operations MUST validate inputs before API calls. See [security-enhancement.md](references/security-enhancement.md) §3 for full specification.

| Parameter | Validation Rule | On Failure |
|-----------|----------------|------------|
| `templateName` | Regex `^[a-zA-Z0-9_-]{1,64}$` | HALT; invalid name |
| `sandboxId` | ULID format `^[0-9A-Z]{26}$` | HALT; invalid ID |
| `templateType` | Enum `CodeInterpreter \| Browser \| AIO` | HALT; invalid type |
| `cpu` | Integer 1-8 | HALT; out of range |
| `memory` | Integer 1024-16384 | HALT; out of range |
| `diskSize` | Integer 1024-102400 | HALT; out of range |
| `networkMode` | Enum `PUBLIC \| PRIVATE` | HALT; invalid mode |
| `idleTimeout` | Integer 60-21600 | HALT; out of range |
| `path` | No `..` traversal, no `.` prefix | HALT; unsafe path |
| `command` | Dangerous pattern check | HALT or warn per severity |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## Prerequisites

1. **Configure credentials**:
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
   export ALIBABA_CLOUD_ACCOUNT_ID="{{env.ALIBABA_CLOUD_ACCOUNT_ID}}"
   # Optional: STS temporary credentials (recommended for automation)
   # export ALIBABA_CLOUD_SECURITY_TOKEN="{{env.ALIBABA_CLOUD_SECURITY_TOKEN}}"
   ```
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

2. **Implement ACS3-HMAC-SHA256 signing** — see [api-signing.md](references/api-signing.md)

3. **STS credential support**: When `ALIBABA_CLOUD_SECURITY_TOKEN` is set, add `X-Acs-Security-Token` header to ALL API requests:
   ```bash
   # Add to every curl call when using STS:
   -H "X-Acs-Security-Token: ${ALIBABA_CLOUD_SECURITY_TOKEN}"
   ```
   See [security-enhancement.md](references/security-enhancement.md) §6 for full STS flow.

4. **Verify permissions**: RAM policy must include `fc:CreateTemplate`, `fc:CreateSandbox`, etc.

## Reference Directory

- [Knowledge Base](references/knowledge-base.md) — AgentRun/Sandbox 产品知识：MCP、Skills、OSS 加载、Tool Hub（**优先查阅概念性问题**）
- [API Reference](references/api-reference.md) — Full endpoint documentation
- [API Signing Guide](references/api-signing.md) — ACS3-HMAC-SHA256 implementation
- [Core Concepts](references/core-concepts.md) — Sandbox architecture and limits
- [Security Enhancement](references/security-enhancement.md) — RAM policies, credential validation, safety gates, incident response
- [Troubleshooting](references/troubleshooting.md) — Error codes and diagnostics
- [Monitoring Guide](references/monitoring.md) — Observability, metrics, and alerting
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar integration
- [Integration](references/integration.md) — Credential setup and signing workflow