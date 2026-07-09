# End-to-End Deploy (Package → Upload OSS → Deploy → Invoke)

**When to use:** Deploy function code from local source directory to FC in one flow. This is the complete lifecycle: local pack → OSS upload → create/update function → verify → trigger execute.

**Why OSS first:** FC 3.0 code package MUST be in OSS (direct upload via API limited to 50MB; SDK has same limits). The OSS path supports up to 500MB packages.

## Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Source directory exists | `ls {{user.source_dir}}` | Exit 0 | HALT; verify source path |
| CLI + OSS plugin available | `aliyun version && aliyun oss ls oss://` | Exit 0 | Install CLI |
| OSS bucket accessible | `aliyun oss ls oss://{{user.oss_bucket}}` | Bucket listed | HALT; check OSS permissions |
| Execution role | RAM role ARN | Valid `fc:InvokeFunction` | Delegate to `alicloud-ram-ops` |

## Phase 1: Package

```bash
# Navigate to source directory
cd {{user.source_dir}}

# Exclude non-essential files, create zip
# Note: zip -x patterns need quotes and proper glob syntax
zip -r /tmp/{{user.function_name}}-code.zip . \
  -x ".git/*" ".github/*" "node_modules/*" "__pycache__/*" ".DS_Store" "*.swp" "*.log" "*.lock"

# Verify package size (FC limit: 500MB via OSS)
du -h /tmp/{{user.function_name}}-code.zip
```

## Phase 2: Upload to OSS

```bash
# Upload code package to OSS
aliyun oss cp /tmp/{{user.function_name}}-code.zip \
  oss://{{user.oss_bucket}}/{{user.oss_prefix}}/{{user.function_name}}-code.zip \
  --force

# Verify upload
aliyun oss ls oss://{{user.oss_bucket}}/{{user.oss_prefix}}/ \
  --marker "{{user.function_name}}-code.zip"
```

## Phase 3: Create or Update Function

```bash
# Step 3a: Check if function exists
# FC API returns .functionName only on success; error responses have .code + .message
RESULT=$(aliyun fc-open GET /2023-03-30/functions/{{user.function_name}} 2>/dev/null)

if echo "$RESULT" | jq -e '.functionName' > /dev/null 2>&1; then
  # Function exists → Update code only
  echo "Function exists. Updating code..."
  aliyun fc-open PUT /2023-03-30/functions/{{user.function_name}} --body "$(cat <<EOF
  {
    "code": {
      "ossBucketName": "{{user.oss_bucket}}",
      "ossObjectName": "{{user.oss_prefix}}/{{user.function_name}}-code.zip"
    }
  }
  EOF
  )"
else
  # Function does not exist → Create new
  echo "Creating new function..."
  aliyun fc-open POST /2023-03-30/functions --body "$(cat <<EOF
  {
    "functionName": "{{user.function_name}}",
    "runtime": "{{user.runtime}}",
    "handler": "{{user.handler}}",
    "memorySize": {{user.memory_mb|default:512}},
    "timeout": {{user.timeout|default:60}},
    "code": {
      "ossBucketName": "{{user.oss_bucket}}",
      "ossObjectName": "{{user.oss_prefix}}/{{user.function_name}}-code.zip"
    },
    "role": "{{user.ram_role_arn}}",
    "environmentVariables": {{user.env_vars|default:{}}}
  }
  EOF
  )"
fi
```

## Phase 4: Validate

```bash
# Wait for function to become ACTIVE（60×5s 模板见 ../polling-patterns.md）

# If state is FAILED, report
[ "$STATE" != "ACTIVE" ] && echo "Function in state: $STATE"
```

## Phase 5: Trigger Execution (Test)

```bash
# Synchronous invocation with test payload
aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/invocations \
  --body '{"test": true, "action": "health_check"}' \
  --header "x-fc-invocation-type=Sync"
```

## Failure Recovery

| Phase | Error | Agent Action |
|-------|-------|-------------|
| Package | Source dir empty | HALT; verify source has code files |
| Upload | OSS AccessDenied | Check ram:PutObject on bucket |
| Upload | BucketNotFound | Create bucket first or use existing |
| Create/Update | ResourceLimitExceeded | HALT; request quota increase |
| Create/Update | RoleAccessDenied | Verify role trust policy |
| Validation | State=FAILED after 300s | Check `stateReason` + `stateReasonCode` |
| Trigger | Invocation Timeout | Increase function timeout; check downstream |
