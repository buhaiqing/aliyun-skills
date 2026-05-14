# aliyun CLI Behavioral Reference

> **Purpose:** Verified behavioral notes and invocation patterns for the `aliyun` CLI, derived from source code analysis and empirical testing. Every generated skill MUST follow these conventions.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14

---

## Table of Contents

1. [Default Output is JSON](#1-default-output-is-json)
2. [No `--no-interactive` Flag](#2-no---no-interactive-flag)
3. [Native Environment Variable Support](#3-native-environment-variable-support)
4. [JSON Config File Format](#4-json-config-file-format)
5. [Sandbox Workaround](#5-sandbox-workaround)
6. [Correct CLI Invocation Patterns](#6-correct-cli-invocation-patterns)
7. [Common Mistakes to Avoid](#7-common-mistakes-to-avoid)

---

## 1. Default Output is JSON

The `aliyun` CLI's default `OutputFormat` is `json` (configured in `NewProfile()`). Unlike other CLIs, you do **NOT** need `--output json` for plain JSON output:

```bash
# Works fine — output is JSON by default
aliyun ecs DescribeInstances --RegionId cn-hangzhou

# --output is primarily for JMESPath transformations
aliyun ecs DescribeInstances --output cols=InstanceId,Status rows=Instances.Instance[]

# Using a JMESPath expression to extract specific fields
aliyun ecs DescribeInstances --output cols=InstanceId rows=Instances.Instance[*].InstanceId
```

**Fix for generated skills:** Plain JSON output does NOT require `--output json`. Use `--output cols=...,rows=...` only when tabular extraction is needed.

---

## 2. No `--no-interactive` Flag

The `aliyun` CLI does **not** define `--no-interactive` anywhere. All commands are non-interactive by default:

```bash
# WRONG:
aliyun ecs DescribeInstances --no-interactive

# CORRECT (just omit it):
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

---

## 3. Native Environment Variable Support

The `aliyun` CLI reads credentials from environment variables natively (source: `profile.go::OverwriteWithFlags`):

```go
if cp.AccessKeyId == "" {
    cp.AccessKeyId = util.GetFromEnv(
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABACLOUD_ACCESS_KEY_ID",
        "ALICLOUD_ACCESS_KEY_ID",
        "ACCESS_KEY_ID",
    )
}
```

**Supported env vars (in fallback order):**

| Purpose | Variable Names (Priority Order) |
|---------|--------------------------------|
| Access Key ID | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABACLOUD_ACCESS_KEY_ID`, `ALICLOUD_ACCESS_KEY_ID`, `ACCESS_KEY_ID` |
| Access Key Secret | `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABACLOUD_ACCESS_KEY_SECRET`, `ALICLOUD_ACCESS_KEY_SECRET`, `ACCESS_KEY_SECRET` |
| STS Token | `ALIBABA_CLOUD_SECURITY_TOKEN`, `ALIBABACLOUD_SECURITY_TOKEN`, `ALICLOUD_SECURITY_TOKEN` |
| Region | `ALIBABA_CLOUD_REGION_ID`, `ALIBABACLOUD_REGION_ID`, `ALICLOUD_REGION_ID`, `REGION_ID`, `REGION` |
| Profile | `ALIBABACLOUD_PROFILE`, `ALIBABA_CLOUD_PROFILE`, `ALICLOUD_PROFILE` |
| Endpoint | `ALIBABA_CLOUD_ENDPOINT`, `ALIBABACLOUD_ENDPOINT` |
| Debug | `DEBUG=sdk` (enable HTTP request logging) |

---

## 4. JSON Config File Format

The `aliyun` CLI stores config in `~/.aliyun/config.json` as JSON (not INI):

```json
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "AKID",
      "access_key_secret": "SECRET",
      "region_id": "cn-hangzhou",
      "output_format": "json",
      "language": "en"
    }
  ]
}
```

---

## 5. Sandbox Workaround

For sandboxed/containerized environments:

```bash
# Option A (preferred): Set env vars directly (no file I/O needed)
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Option B: Custom config path with --config-path flag
mkdir -p /tmp/aliyun-home/.aliyun
cat > /tmp/aliyun-home/.aliyun/config.json << 'EOF'
{"current":"default","profiles":[{"name":"default","mode":"AK","access_key_id":"AKID","access_key_secret":"SECRET","region_id":"cn-hangzhou"}]}
EOF
aliyun --config-path /tmp/aliyun-home/.aliyun/config.json ecs DescribeRegions
```

---

## 6. Correct CLI Invocation Patterns

### RPC Style APIs (Most Products)

```bash
aliyun <product> <OperationName> --RegionId <region> --Param1 value1
```

Examples:
```bash
aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 50
aliyun rds DescribeDBInstances --RegionId cn-hangzhou
```

### RESTful Style APIs (Container Service, etc.)

```bash
aliyun cs GET /clusters
aliyun cs POST /clusters --body "$(cat input.json)"
```

### Skip Metadata Validation for Unknown APIs

```bash
aliyun <product> --version 2024-01-01 --endpoint <product>.aliyuncs.com --force
```

### Polling with `--waiter`

```bash
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300 interval=5
```

### Multi-Cloud Credential Namespace Convention

To avoid credential conflicts when mixing cloud providers:

```ini
# Alibaba Cloud — use ALIBABA_CLOUD_* prefix
ALIBABA_CLOUD_ACCESS_KEY_ID=...
ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# JD Cloud — use JDC_* prefix
JDC_ACCESS_KEY=...
JDC_SECRET_KEY=...
JDC_REGION=cn-north-1

# AWS — use AWS_* prefix (standard)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

---

## 7. Common Mistakes to Avoid

### Mistake 1: Adding `--output json`
```bash
# WRONG: --output json is unnecessary (JSON is default)
aliyun ecs DescribeInstances --output json

# CORRECT: Plain JSON output
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

### Mistake 2: Using `--no-interactive`
```bash
# WRONG: Flag does not exist
aliyun ecs DescribeInstances --no-interactive

# CORRECT: Omit the flag (non-interactive by default)
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

### Mistake 3: Incorrect Polling Syntax
```bash
# WRONG: Missing proper JSON array for InstanceIds
aliyun ecs DescribeInstances --InstanceIds i-xxx --waiter ...

# CORRECT: InstanceIds expects JSON string array
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300 interval=5
```

### Mistake 4: Hardcoding Regions
```bash
# WRONG: Hardcoded region
aliyun ecs DescribeInstances --RegionId cn-hangzhou

# CORRECT: Use placeholder (or env var)
aliyun ecs DescribeInstances --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

---

## See Also

- [Alibaba Cloud CLI Source Code](https://github.com/aliyun/aliyun-cli)
- [Execution Environment Setup](execution-environment.md)
- [Enhanced Self-Healing Framework](enhanced-self-healing-framework.md)