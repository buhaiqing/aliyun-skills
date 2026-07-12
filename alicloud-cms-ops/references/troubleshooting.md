# Troubleshooting Guide for alicloud-cms-ops

## Common Issues

### Issue 1: Throttling / Rate Limiting

**Symptoms:**
- Error: `Throttling.User` or `Request was denied due to user flow control`
- API calls fail intermittently

**Root Cause:**
- CMS metric query APIs share a quota of **1,000,000 calls/month** (free tier)
- Per-API limit: **50 calls/second** per account

**Resolution:**
1. Implement exponential backoff: 1s → 2s → 4s → max 3 retries
2. Reduce query frequency or batch requests
3. Enable CloudMonitor pay-as-you-go if quota exceeded
4. Use longer Period values (300s instead of 60s) to reduce call volume

**Prevention:**
- Cache metric data when possible
- Use DescribeMetricLast instead of DescribeMetricList for latest values
- Implement client-side rate limiting

---

### Issue 2: No Metric Data Returned

**Symptoms:**
- `DescribeMetricList` returns empty `Datapoints` array
- `Success: true` but no data

**Root Causes & Resolution:**

| Cause | Check | Fix |
|-------|-------|-----|
| Instance not running | Instance state | Start the instance |
| Wrong namespace | `DescribeProjectMeta` | Use correct namespace (e.g., `acs_ecs_dashboard`) |
| Wrong metric name | `DescribeMetricMetaList` | Use valid metric name |
| Wrong dimensions | Dimension format | Use correct JSON format: `[{"instanceId":"i-xxx"}]` |
| Time range too old | Data retention | Period <60s: 7 days; 60s: 31 days; ≥300s: 91 days |
| Instance just created | Data collection delay | Wait 5-10 minutes for first data point |
| Region mismatch | Instance region | Query the correct region |

**Debug Steps:**
```bash
# 1. Verify namespace
aliyun cms DescribeProjectMeta --RegionId cn-hangzhou

# 2. Verify metric exists
aliyun cms DescribeMetricMetaList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard

# 3. Check instance exists and running
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceIds '["i-xxx"]'

# 4. Query with broader time range
aliyun cms DescribeMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Period 300 \
  --StartTime "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"i-xxx"}]'
```

---

### Issue 3: Alarm Rule Not Triggering

**Symptoms:**
- Alarm rule exists but no notifications received
- State shows `OK` when it should be `ALARM`

**Root Causes & Resolution:**

| Cause | Check | Fix |
|-------|-------|-----|
| Evaluation count not met | `--EvaluationCount` | Reduce from 3 to 1 for testing |
| Threshold too high/low | Metric values | Adjust threshold based on actual data |
| Effective interval | `--EffectiveInterval` | Ensure current time is within interval |
| Alarm disabled | `--EnableState` | Set to `true` |
| Contact group empty | `DescribeContactGroupList` | Add contacts to group |
| MNS topic not found | MNS console | Create topic or use correct ARN |
| Silence period | Alarm history | Check if in silence period |

**Debug Steps:**
```bash
# 1. Check alarm rule details
aliyun cms DescribeMetricAlarmList \
  --RegionId cn-hangzhou \
  --AlarmName "your-alarm-name"

# 2. Check current metric values
aliyun cms DescribeMetricLast \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-xxx"}]'

# 3. Verify contact group
aliyun cms DescribeContactGroupList --RegionId cn-hangzhou
```

---

### Issue 4: Permission Denied (Forbidden)

**Symptoms:**
- Error: `Forbidden` or `User not authorized`
- Error: `NoPermission`

**Root Cause:**
- RAM user lacks CloudMonitor permissions

**Resolution:**
1. Attach policy `AliyunCloudMonitorReadOnlyAccess` for read operations
2. Attach policy `AliyunCloudMonitorFullAccess` for write operations
3. For custom policies, ensure these actions are allowed:
   - `cms:DescribeMetricList`
   - `cms:DescribeMetricLast`
   - `cms:PutMetricAlarm`
   - `cms:DescribeMetricAlarmList`
   - `cms:DeleteMetricAlarm`
   - `cms:DescribeMetricMetaList`

**Verify Permissions:**
```bash
aliyun ram ListPoliciesForUser --UserName your-username
```

---

### Issue 5: InvalidParameter Errors

**Symptoms:**
- Error: `InvalidParameter` with various messages

**Common Causes:**

| Parameter | Common Mistake | Correct Format |
|-----------|---------------|----------------|
| Dimensions | Wrong JSON format | `[{"instanceId":"i-xxx"}]` |
| Period | Unsupported value | 15, 60, 300, 900, 3600 |
| Statistics | Wrong value | Average, Minimum, Maximum, Value |
| ComparisonOperator | Wrong format | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| StartTime/EndTime | Wrong format | `2026-05-14T10:00:00Z` |
| ContactGroups | Wrong JSON format | `["group1","group2"]` |
| AlarmActions | Wrong ARN format | `acs:mns:region:account:topics/topic-name` |

---

### Issue 6: CLI Not Found or Outdated

**Symptoms:**
- `command not found: aliyun`
- CLI version too old, missing CMS commands

**Resolution:**
```bash
# Check version
aliyun version

# Update CLI
brew upgrade aliyun-cli  # macOS
# Or re-run installer
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# Verify CMS support
aliyun cms --help
```

---

### Issue 7: SDK Import Errors

**Symptoms:**
- Go build fails with `module not found`
- Import path errors

**Resolution:**
```bash
# Initialize module
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea/tea
go get github.com/alibabacloud-go/cms-20190101/v7/client

# For CloudMonitor 2.0
go get github.com/alibabacloud-go/cms-2024-03-30/v2/client
```

---

### Issue 8: CLI Installation Failure (Enhanced Diagnosis)

**Symptoms:**
- `command not found: aliyun` after install attempt
- Install script exits with errors
- CLI binary exists but fails to execute

**Root Cause Detection:**

Run the full environment diagnosis to identify the root cause:

```bash
# Quick environment check (fast path)
echo "--- OS ---"
uname -a
echo "--- CLI ---"
command -v aliyun && aliyun version || echo "CLI not found"
echo "--- Go ---"
command -v go && go version || echo "Go not found"
echo "--- Download Tool ---"
command -v curl && echo "curl available" || (command -v wget && echo "wget available" || echo "no download tool")
echo "--- Disk Space ---"
df -h /tmp | tail -1
echo "--- PATH ---"
echo "$PATH" | tr ':' '\n'
```

**Detailed Diagnosis by Layer:**

| Layer | Check Command | Expected | Root Cause If Failed |
|-------|--------------|----------|---------------------|
| **Level 1: Environment** | `uname -s && uname -m` | Linux/Darwin + x86_64/arm64 | Unsupported OS/arch |
| | `df -k /tmp \| awk 'NR==2 {print $4}'` | > 51200 KB | Insufficient disk space |
| | `command -v curl \|\| command -v wget` | curl or wget found | Missing download tool |
| | `which aliyun 2>/dev/null \|\| echo not_found` | aliyun in PATH | CLI not installed or PATH misconfigured |
| **Level 2: Dependencies** | `command -v go && go version` | Go 1.21+ found | Go runtime not installed |
| | `echo $GOPATH` | GOPATH set or default ~/go | GOPATH not configured |
| | `echo $PATH \| tr ':' '\\n' \| grep "$(go env GOPATH)/bin"` | GOPATH/bin in PATH | Go binaries not accessible |
| **Level 3: Network** | `host metrics.aliyuncs.com &>/dev/null` | DNS resolves | DNS failure |
| | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://aliyuncli.alicdn.com/install.sh` | HTTP 200 | CLI download server unreachable |
| | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://github.com` | Not timeout | GitHub unreachable (Go mod) |
| **Level 4: Permissions** | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo set` | "set" | AK ID missing |
| | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo set` | "set" | AK Secret missing |
| | `aliyun cms DescribeProjectMeta --RegionId cn-hangzhou 2>&1 \| head -3` | `"Code":"200"` | AK invalid, expired, or no RAM permission |

**Auto-Heal Script:**

```bash
#!/bin/bash
# Automated CLI installation healing
heal_cli_install() {
  local os_type=$(uname -s)
  local os_arch=$(uname -m)

  echo "[HEAL] Installing aliyun CLI on ${os_type}/${os_arch}..."

  case "$os_type" in
    Darwin)
      if command -v brew &>/dev/null; then
        brew install aliyun-cli && echo "[OK] CLI installed via brew" && return 0
      fi
      ;;
  esac

  if command -v curl &>/dev/null; then
    /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)" && \
      echo "[OK] CLI installed via script" && return 0
  elif command -v wget &>/dev/null; then
    /bin/bash -c "$(wget -qO- https://aliyuncli.alicdn.com/install.sh)" && \
      echo "[OK] CLI installed via wget" && return 0
  fi

  echo "[FAIL] Auto-install failed. Manual steps:"
  echo "  1. Download: curl -o /tmp/aliyun-cli.tgz https://aliyuncli.alicdn.com/aliyun-cli-${os_type,,}-${os_arch}.tgz"
  echo "  2. Extract: tar -xzf /tmp/aliyun-cli.tgz -C /usr/local/bin"
  echo "  3. Verify: aliyun version"
  return 1
}

# Invoke if CLI is missing
if ! command -v aliyun &>/dev/null; then
  heal_cli_install
fi
```

**Network Optimization for China Region:**

```bash
# Configure Go proxy for faster SDK downloads
export GOPROXY=https://goproxy.cn,direct

# Use direct binary download (bypass install script)
# macOS ARM64
curl -o /tmp/aliyun-cli-macos-arm64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-macos-arm64.tgz"
# macOS AMD64
curl -o /tmp/aliyun-cli-macosx-amd64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-macosx-amd64.tgz"
# Linux AMD64
curl -o /tmp/aliyun-cli-linux-amd64.tgz \
  "https://aliyuncli.alicdn.com/aliyun-cli-linux-amd64.tgz"
```

**Prevention:**
- Verify environment compatibility before install
- Use package manager where available (brew, apt)
- Configure Go proxy in shell profile
- Keep CLI updated regularly (`aliyun update`)

---

### Issue 9: SDK Build/Resolution Failure (Enhanced Diagnosis)

**Symptoms:**
- `go build` fails with network timeout
- `go get` hangs or fails
- Module checksum mismatch
- CGO-related build errors

**Root Cause Detection:**

```bash
# 1. Check Go version
go version

# 2. Check Go proxy
go env GOPROXY

# 3. Test SDK resolution
cd /tmp && mkdir -p sdk-test && cd sdk-test
go mod init sdk-test
go get github.com/alibabacloud-go/cms-20190101/v7/client 2>&1

# 4. Check module cache
ls -la $(go env GOMODCACHE)/github.com/alibabacloud-go/ 2>/dev/null || echo "No cached modules"
```

**Resolution by Root Cause:**

| Root Cause | Check | Fix |
|-----------|-------|-----|
| Go proxy unreachable | `go env GOPROXY` shows `direct` or unreachable proxy | `export GOPROXY=https://goproxy.cn,direct` |
| Network timeout | Test: `curl -s --connect-timeout 5 https://github.com` | Configure proxy or use VPN |
| CGO dependency | Build error mentions `cgo` or `gcc` | Install build tools: `xcode-select --install` (macOS) or `apt install gcc` (Linux) |
| Module checksum mismatch | `go: checksum mismatch` error | `go clean -modcache && go mod download` |
| Go version too old | `go version` < 1.21 | Upgrade Go: `brew upgrade go` or download from https://go.dev/dl/ |
| Disk space | `df -h $(go env GOMODCACHE)` | Free space: `go clean -modcache` removes cached modules |

**Auto-Heal Script:**

See complete auto-heal scripts in [cli-install-diagnosis.md](cli-install-diagnosis.md), which includes `heal_cli_install()`, `heal_missing_go()`, and `heal_sdk_deps()` with the full SDK dependency resolution logic. Quick summary:

```bash
# Resolve SDK dependencies (full script in cli-install-diagnosis.md)
export GOPROXY=https://goproxy.cn,direct
cd /tmp && mkdir -p sdk-workspace && cd sdk-workspace
[ ! -f "go.mod" ] && go mod init sdk-script
go get github.com/alibabacloud-go/cms-20190101/v7/client
```

**Prevention:**
- Configure `GOPROXY=https://goproxy.cn,direct` in shell profile
- Pre-download SDK packages in CI/CD pipeline
- Use Go module mirror for faster downloads

---

### Issue 10: Credential Validation Failure (Enhanced Diagnosis)

**Symptoms:**
- `Forbidden` error on API calls
- `InvalidAccessKeyId` or `SignatureDoesNotMatch` error
- API returns `Code: "404"` or `Code: "500"` for credential issues

**Root Cause Detection:**

```bash
# 1. Quick credential existence check (NEVER echo the actual secret)
echo "AK_ID: $(test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo '<set>' || echo '<missing>')"
echo "AK_SECRET: $(test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo '<set>' || echo '<missing>')"
echo "REGION: ${ALIBABA_CLOUD_REGION_ID:-<missing>}"

# 2. Dry-run API call to validate credentials
DRY_RUN=$(aliyun cms DescribeProjectMeta \
  --RegionId "${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}" 2>&1 | head -5)

echo "Dry-run response:"
echo "$DRY_RUN"
```

**Credential Error Interpretation:**

| Error in Response | Root Cause | Resolution |
|------------------|-----------|------------|
| `"Code": "200"` with `"Success": true` | Credentials valid | No action needed |
| `Forbidden` or `"Code": "403"` | RAM policy insufficient | Attach `AliyunCloudMonitorReadOnlyAccess` or `AliyunCloudMonitorFullAccess` |
| `InvalidAccessKeyId.NotFound` | AK ID does not exist | Generate new AK in RAM console |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | AK ID/Secret mismatch or expired | Regenerate AK pair |
| `Request was denied due to user flow control` | Rate limited | Wait 5s, retry up to 3 times |
| `"Code": "404"` (not found error) | API endpoint or action wrong | Verify RegionId and API action name |
| Connection timeout / no response | Network issue | Check firewall, DNS, proxy |

**RAM Policy Quick Fix:**

```bash
# Attach read-only policy via CLI (requires admin RAM permissions)
aliyun ram AttachPolicyToUser \
  --UserName "${RAM_USER}" \
  --PolicyName "AliyunCloudMonitorReadOnlyAccess" \
  --PolicyType "System"

# Attach full access policy
aliyun ram AttachPolicyToUser \
  --UserName "${RAM_USER}" \
  --PolicyName "AliyunCloudMonitorFullAccess" \
  --PolicyType "System"
```

**Prevention:**
- Use RAM sub-account with minimal required permissions
- Set up AK rotation policy (90-day expiry)
- Store credentials securely (environment variables, not in code)
- Use STS temporary credentials for automated workflows

---

### Issue 11: Network Connectivity Failure for CLI Operations

**Symptoms:**
- All CLI commands time out
- `curl: (28) Connection timeout` or `Connection refused`
- DNS resolution failures
- Intermittent API failures

**Diagnostic Commands:**

```bash
# DNS Resolution Test
echo "--- DNS Test ---"
host metrics.aliyuncs.com 2>&1 || nslookup metrics.aliyuncs.com 2>&1

# Endpoint Connectivity Test
echo "--- CMS Endpoint ---"
curl -s -o /dev/null -w "CMS: HTTP %{http_code} (%{time_total}s)\n" \
  --connect-timeout 5 https://metrics.aliyuncs.com 2>&1 || echo "CMS: UNREACHABLE"

# CLI Download Server
echo "--- CLI Download ---"
curl -s -o /dev/null -w "CLI: HTTP %{http_code} (%{time_total}s)\n" \
  --connect-timeout 5 https://aliyuncli.alicdn.com/install.sh 2>&1 || echo "CLI: UNREACHABLE"

# GitHub Reachability (for Go module downloads)
echo "--- GitHub ---"
curl -s -o /dev/null -w "GitHub: HTTP %{http_code} (%{time_total}s)\n" \
  --connect-timeout 5 https://github.com 2>&1 || echo "GitHub: UNREACHABLE"

# VPC Internal Endpoint
echo "--- VPC Internal ---"
curl -s -o /dev/null -w "VPC: HTTP %{http_code} (%{time_total}s)\n" \
  --connect-timeout 3 https://metrics-intra.aliyuncs.com 2>&1 || echo "VPC: UNREACHABLE"

# Proxy Detection
echo "--- Proxy ---"
echo "http_proxy: ${http_proxy:-<not set>}"
echo "https_proxy: ${https_proxy:-<not set>}"
echo "no_proxy: ${no_proxy:-<not set>}"
```

**Resolution by Failure Pattern:**

| Failure Pattern | Root Cause | Resolution |
|----------------|-----------|------------|
| All endpoints fail | Network disconnected | Check internet connectivity, VPN status |
| DNS fails + endpoints unreachable | DNS server issue | Add public DNS: `echo "nameserver 8.8.8.8" >> /etc/resolv.conf` |
| CMS endpoint fails, others OK | CMS-specific firewall rule | Allow `metrics.aliyuncs.com` (443) in security group/firewall |
| CLI download fails | CDN/domain blocked | Use alternate download method |
| GitHub fails | Corporate firewall blocks GitHub | Set `GOPROXY=https://goproxy.cn,direct` |
| VPC internal endpoint works | Running inside Alibaba Cloud VPC | Use `metrics-intra.aliyuncs.com` for better performance |
| Proxy required but not configured | Corporate network requires proxy | Set `http_proxy` and `https_proxy` env vars |

**Automatic Endpoint Selection:**

```bash
# Auto-detect optimal endpoint
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 \
  "https://metrics-intra.aliyuncs.com" 2>/dev/null | grep -q "200\|403\|302"; then
  CMS_ENDPOINT="metrics-intra.aliyuncs.com"
  echo "[INFO] Using VPC internal endpoint: ${CMS_ENDPOINT}"
else
  CMS_ENDPOINT="metrics.aliyuncs.com"
  echo "[INFO] Using public endpoint: ${CMS_ENDPOINT}"
fi

export ALIBABA_CLOUD_ENDPOINT="${CMS_ENDPOINT}"
```

**Prevention:**
- Configure corporate proxy in environment
- Use VPC internal endpoints for Alibaba Cloud VPC deployments
- Add Go proxy to shell profile (`export GOPROXY=https://goproxy.cn,direct`)
- Configure DNS fallback in `/etc/resolv.conf`

---

## Diagnostic Commands

### Full System Check (Enhanced)

```bash
#!/bin/bash
# cms-health-check-enhanced.sh — includes 4-layer anomaly detection
# Usage: bash cms-health-check-enhanced.sh
# Output: Structured JSON report + human-readable summary

set -e

echo "============================================="
echo "  CMS Enhanced Health Check v2.1"
echo "============================================="
echo ""

# === Level 1: Environment ===
echo "[Level 1] Environment Check"
echo "----------------------------"
echo "OS: $(uname -s) $(uname -m)"
echo "Shell: ${SHELL:-unknown}"
echo "CLI: $(command -v aliyun &>/dev/null && echo 'installed: '$(aliyun version) || echo 'NOT FOUND')"
echo "Go: $(command -v go &>/dev/null && echo 'installed: '$(go version) || echo 'NOT FOUND')"
echo "Curl: $(command -v curl &>/dev/null && echo 'available' || echo 'NOT FOUND')"
echo "Disk space (/tmp): $(df -h /tmp 2>/dev/null | awk 'NR==2 {print $4}' || echo 'unknown')"

# CLI install auto-heal attempt if missing
if ! command -v aliyun &>/dev/null; then
  echo ""
  echo "[HEAL] CLI missing — attempting auto-install..."
  if command -v brew &>/dev/null; then
    brew install aliyun-cli 2>/dev/null && echo "[HEAL] CLI installed via brew" || echo "[HEAL] Brew install failed"
  elif command -v curl &>/dev/null; then
    /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)" 2>/dev/null && \
      echo "[HEAL] CLI installed via script" || echo "[HEAL] Script install failed"
  fi
fi

echo ""

# === Level 2: Dependencies ===
echo "[Level 2] Dependency Check"
echo "----------------------------"
if command -v go &>/dev/null; then
  echo "GOPATH: $(go env GOPATH)"
  echo "GOPROXY: $(go env GOPROXY)"
  echo "GOMODCACHE: $(go env GOMODCACHE)"
fi

# Go version check
if command -v go &>/dev/null; then
  GO_MAJOR=$(go version | sed -E 's/.*go([0-9]+)\..*/\1/')
  GO_MINOR=$(go version | sed -E 's/.*go[0-9]+\.([0-9]+).*/\1/')
  if [ "$GO_MAJOR" -gt 1 ] || ([ "$GO_MAJOR" -eq 1 ] && [ "$GO_MINOR" -ge 21 ]); then
    echo "Go version: OK (>= 1.21)"
  else
    echo "Go version: WARNING (< 1.21, upgrade recommended)"
  fi
  if [ "$GO_MAJOR" -gt 1 ] || ([ "$GO_MAJOR" -eq 1 ] && [ "$GO_MINOR" -ge 24 ]); then
    echo "Go JIT: OK (>= 1.24)"
  else
    echo "Go JIT: WARNING (< 1.24, JIT SDK fallback may have issues)"
  fi
fi

echo ""

# === Level 3: Network ===
echo "[Level 3] Network Check"
echo "----------------------------"
echo "DNS (metrics.aliyuncs.com): $(host metrics.aliyuncs.com &>/dev/null && echo 'OK' || echo 'FAIL')"

CMS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://metrics.aliyuncs.com" 2>/dev/null || echo 'timeout')
echo "CMS Endpoint: ${CMS_CODE}"

CLI_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://aliyuncli.alicdn.com/install.sh" 2>/dev/null || echo 'timeout')
echo "CLI Download: ${CLI_CODE}"

VPC_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "https://metrics-intra.aliyuncs.com" 2>/dev/null || echo 'timeout')
echo "VPC Internal: ${VPC_CODE}"

echo ""

# === Level 4: Permissions ===
echo "[Level 4] Permission Check"
echo "----------------------------"
echo "AK_ID: $(test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo '<set>' || echo '<missing>')"
echo "AK_SECRET: $(test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo '<set>' || echo '<missing>')"
echo "REGION: ${ALIBABA_CLOUD_REGION_ID:-<missing>}"

if [ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ] && [ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ] && command -v aliyun &>/dev/null; then
  echo -n "API Access: "
  RESULT=$(aliyun cms DescribeProjectMeta --RegionId "${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}" 2>&1 | head -1)
  if echo "$RESULT" | grep -q '"Code": "200"'; then
    echo "OK (credentials valid)"
  elif echo "$RESULT" | grep -qi 'forbidden'; then
    echo "WARNING (RAM policy insufficient)"
  elif echo "$RESULT" | grep -qi 'InvalidAccessKey\|SignatureDoesNotMatch'; then
    echo "FAIL (AK invalid or expired)"
  else
    echo "UNKNOWN ($RESULT)"
  fi
fi

echo ""
echo "============================================="
echo "  Health Check Complete"
echo "============================================="

# Summary
WARNINGS=0
FAILURES=0
command -v aliyun &>/dev/null || ((FAILURES++))
[ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ] || ((WARNINGS++))
[ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ] || ((WARNINGS++))
[ "$CMS_CODE" != "timeout" ] && [ "$CMS_CODE" != "000" ] || ((FAILURES++))

echo "Summary: $([ $FAILURES -eq 0 ] && [ $WARNINGS -eq 0 ] && echo 'HEALTHY' || echo 'DEGRADED')"
echo "Failures: $FAILURES | Warnings: $WARNINGS"

if [ $FAILURES -gt 0 ] || [ $WARNINGS -gt 0 ]; then
  echo ""
  echo "Recommendations:"
  command -v aliyun &>/dev/null || echo "  - Install aliyun CLI (see CLI Install Diagnosis)"
  [ -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" ] || echo "  - Set ALIBABA_CLOUD_ACCESS_KEY_ID"
  [ -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ] || echo "  - Set ALIBABA_CLOUD_ACCESS_KEY_SECRET"
  [ "$CMS_CODE" != "timeout" ] && [ "$CMS_CODE" != "000" ] || echo "  - Check network connectivity to CMS endpoint"
fi
```

---

## Root-Cause Diagnosis Decision Tree (AIOps)

> This section provides **cross-skill root-cause diagnosis flows** triggered by CMS alarms. Each scenario follows the 5-step protocol: Verify → Resource Check → Multi-Metric Correlation → Deep Diagnosis → Report.

---

### Scenario 1: ECS High CPU Alarm

Triggered by: `CPUUtilization >= Threshold` on `acs_ecs_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```
**If metric < threshold:** False positive → Check alarm rule `EvaluationCount` and `Statistics`

#### Step 2: Check Resource Status (Delegate to alicloud-ecs-ops)
```bash
aliyun ecs DescribeInstances \
  --RegionId {{user.region}} \
  --InstanceIds '["{{user.instance_id}}"]'
```
**If status != Running:** Resource stopped → Start instance or investigate

#### Step 3: Multi-Metric Correlation
```bash
for metric in memory_usedutilization DiskUsage LoadAverage InternetInRate InternetOutRate; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} \
    --Namespace acs_ecs_dashboard \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| CPU + Memory both high | Resource exhaustion | Consider scale-up |
| CPU high, Load high, CPU < 50% | IO wait (disk bottleneck) | Check DiskUsage and IOPSUsage |
| CPU spike + Network spike | Traffic surge | Check SLB; consider auto-scaling |
| CPU high alone | Runaway process | Delegate to ECS for process-level diagnosis |

#### Step 4: Deep Diagnosis (Optional)
If pattern indicates deep issue, delegate to DAS for AI diagnosis.

#### Step 5: Compile Report
```markdown
## Diagnosis Report: ECS High CPU
- Resource: {{user.instance_id}}
- Status: (from Step 2)
- CPU Trend: (from Step 1 + 3)
- Correlated Patterns: (from Step 3)
- Root Cause: (synthesized)
- Recommendation: (actionable)
```

---

### Scenario 2: RDS ConnectionUsage Alarm

Triggered by: `ConnectionUsage >= Threshold` on `acs_rds_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_rds_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

#### Step 2: Check Resource Status (Delegate to alicloud-rds-ops)
```bash
aliyun rds DescribeDBInstances \
  --RegionId {{user.region}} \
  --DBInstanceId {{user.instance_id}}
```

#### Step 3: Multi-Metric Correlation
```bash
for metric in CpuUsage MemoryUsage DiskUsage IOPSUsage; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} \
    --Namespace acs_rds_dashboard \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| ConnectionUsage high, CPUUsage low | Sleeping connections / connection leak | Check connection pool; delegate to DAS |
| ConnectionUsage + CPUUsage both high | Active query overload | Delegate to DAS for slow query analysis |
| ConnectionUsage high, IOPSUsage high | Query causing high IO | Check indexes; delegate to DAS |

#### Step 4: Deep Diagnosis (Delegate to alicloud-das-ops — **Recommended**)
```bash
# DAS: GetInstanceInspections (health score)
# DAS: CreateDiagnosticReport (SQL/performance diagnosis)
# DAS: CreateLatestDeadLockAnalysis (deadlock check)
# DAS: GetQueryOptimizeData (query governance)
```

---

### Scenario 3: SLB DropConnection Alarm

Triggered by: `DropConnection > 0` on `acs_slb_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_slb_dashboard \
  --MetricName DropConnection \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

#### Step 2: Check SLB Status (Delegate to alicloud-slb-ops)
```bash
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId {{user.instance_id}}
```

#### Step 3: Check Backend Server Health
```bash
aliyun slb DescribeVServerGroups --LoadBalancerId {{user.instance_id}}
aliyun slb DescribeVServerGroupAttribute --VServerGroupId {{user.vserver_group_id}}
```

#### Step 4: If Backend Unhealthy → Delegate to alicloud-ecs-ops
```bash
aliyun ecs DescribeInstances \
  --RegionId {{user.region}} \
  --InstanceIds '["{{user.backend_server_id}}"]'
```

| Backend Status | Interpretation | Next Action |
|---------------|----------------|-------------|
| ECS Stopped | Backend down | Start ECS or remove from SLB |
| ECS Running but high CPU | Backend overloaded | Follow ECS High CPU scenario |
| ECS healthy but DropConnection persists | SLB config issue | Check listener health check config |

---

### Scenario 4: Redis ConnectionUsage Alarm

Triggered by: `ConnectionUsage >= Threshold` on `acs_kvstore_dashboard`

```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_kvstore_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'

aliyun redis DescribeInstances --RegionId {{user.region}} --InstanceId {{user.instance_id}}

for metric in CpuUsage MemoryUsage UsedConnection QPS; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} --Namespace acs_kvstore_dashboard \
    --MetricName "$metric" --Period 300 \
    --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| ConnectionUsage high, QPS low | Connection leak | Check app for unclosed connections |
| ConnectionUsage + QPS both high | Traffic surge | Consider upgrading instance spec |
| ConnectionUsage high, MemoryUsage high | Large key ops | Check big keys; delegate to DAS cache analysis |

---

### Scenario 5: PolarDB CPUUsage Alarm

Triggered by: `CpuUsage >= Threshold` on `acs_polardb_dashboard`

```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_polardb_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'

aliyun polardb DescribeDBClusters --RegionId {{user.region}} --DBClusterId {{user.instance_id}}

for metric in MemoryUsage ConnectionUsage IOPSUsage DataSize; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} --Namespace acs_polardb_dashboard \
    --MetricName "$metric" --Period 300 \
    --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```
> PolarDB has tight DAS integration; **always recommend DAS diagnosis** for PolarDB alarms.

---

## Escalation Path

| Issue | Self-Service | Escalate To |
|-------|-------------|-------------|
| Rate limiting | Backoff, reduce frequency | Alibaba Cloud support (quota increase) |
| Data missing | Verify instance, namespace, metric | Product team if instance running but no data |
| Alarm not firing | Check threshold, evaluation count | Alibaba Cloud support (backend issue) |
| Permission | Attach RAM policies | Security team (custom policy review) |
| CLI bug | Update CLI, use SDK fallback | Alibaba Cloud CLI GitHub issues |
| SDK bug | Update SDK version | Alibaba Cloud SDK GitHub issues |
| Cross-skill diagnosis failure | Check delegated skill status | Skill owner + Alibaba Cloud support |
| DAS diagnosis unavailable | Check DAS instance registration | DAS support team |
| **CLI install failure** | **Run Level 1-4 diagnosis → auto-heal → degrade to JIT SDK** | **Infrastructure team (OS/network)** |
| **SDK build failure** | **Check Go proxy → clean cache → reinstall deps** | **Platform team (Go toolchain)** |
| **Credential invalid** | **Regenerate AK in RAM console** | **Security team (AK rotation policy)** |
| **Network isolation** | **Configure proxy → switch to VPC endpoint** | **Network team (firewall rules)** |
| **All channels blocked** | **Run `cms-anomaly-analyzer.sh` full diagnosis** | **Infrastructure + Platform teams** |

---

## Phase 3-H: Dynamic Instance-Level Alert Management Troubleshooting

This section covers issues specific to **dynamic instance discovery**, **HITL workflows**, and **auto-correction** capabilities introduced in Phase 3-H.

### Issue: Empty Instance List (0 Instances Match Filter)

**Symptoms:**
- Delegation to product skill returns `instance_count: 0`
- Confidence score drops to 0, triggering HITL
- Filter appears correct but no instances found

**Root Causes & Auto-Correction:**

| Cause | Diagnostic | Auto-Correction | Manual Fix |
|-------|------------|-----------------|------------|
| **Tag case mismatch** | Tag key/value case-sensitive | Suggest correct case | Update filter with exact case |
| **Wrong region** | Instance in different region | Auto-detect correct region | Change `--RegionId` |
| **Status filter too strict** | `status=Running` excludes stopped | Suggest removing status filter | Use broader status or remove |
| **Tag doesn't exist** | `DescribeTags` returns no match | List available tags | Use existing tag key/value |
| **Instance deleted** | `DescribeInstances` returns empty | N/A (genuine empty) | Verify instance existence |
| **Time filter on event** | Event-based rules need event name | Suggest correct event pattern | Use correct event type |

**Auto-Correction Flow:**

```bash
# When instance_count = 0, auto-diagnose:

# Step 1: Check tag existence
aliyun <product> DescribeTags --RegionId <region>
# → If tag not found → Suggest: "Tag 'Env' not found. Did you mean 'env'?"

# Step 2: Check instance status distribution
aliyun <product> DescribeInstances --RegionId <region> | jq '.Instances.Instance[].Status'
# → If all Stopped → Suggest: "Remove status filter to include all states"

# Step 3: Check region
aliyun <product> DescribeInstances --RegionId <other-region>
# → If found in other region → Suggest: "Switch to region cn-beijing?"

# Step 4: List valid values
aliyun <product> DescribeInstances --RegionId <region> --PageSize 100
# → Show sample instances with their tags/status
```

**HITL Prompt when Auto-Correction Fails:**

```
[HITL] No instances matched filter: {"tag:env": "prod", "status": "Running"}

Auto-Diagnosis Results:
❌ Tag 'env' not found on any instances
✓ Found tag 'Environment' on 45 instances
✓ Found instances with status: Running(20), Stopped(15)

Suggested Corrections:
1. Use tag 'Environment' instead of 'env':
   Filter: {"tag:Environment": "prod"}
   Expected matches: 20 instances

2. Remove status filter (optional):
   Filter: {"tag:Environment": "prod"}
   Expected matches: 45 instances

3. View all instances and their tags:
   Run: aliyun ecs DescribeInstances --RegionId cn-hangzhou

Choose action (1-3) or CANCEL: __
```

---

### Issue: Too Many Instances Match (> 100)

**Symptoms:**
- `instance_count: 247` returned
- Confidence score reduced to 0
- HITL triggered due to safety threshold

**Root Causes & Resolution:**

| Cause | Impact | Resolution |
|-------|--------|------------|
| **Broad filter** (`status=Running`) | Affects all running instances | Add specific tags to narrow scope |
| **Missing environment filter** | Cross-environment selection | Add `tag:env` or `tag:project` filter |
| **Wildcard match** (`tag:Name=*`) | Matches everything | Remove wildcard, use explicit values |
| **All instances targeted** | Production risk | Use batch processing (50 per rule) |

**Batch Processing Solution:**

```bash
# When > 100 instances, split into batches:

# 1. Get all instance IDs
INSTANCES=$(aliyun ecs DescribeInstances ... | jq -r '.Instances.Instance[].InstanceId')

# 2. Split into chunks of 50
CHUNKS=$(echo "$INSTANCES" | xargs -n 50)

# 3. Create separate alarm rules per chunk
for i in $(seq 0 $((${#CHUNKS[@]} - 1))); do
  CHUNK="${CHUNKS[$i]}"
  aliyun cms PutResourceMetricRule \
    --RuleName "HighCPU-Batch-$i" \
    --Resources "[{\"instanceId\":\"$(echo $CHUNK | tr ' ' '\",\"instanceId\":\"')\"}]" \
    ...
done

# Result: Multiple rules, each covering ≤ 50 instances
```

**HITL Prompt for Large Scope:**

```
[HITL] Filter matches 247 instances (> 100 safety threshold)

⚠️  This operation will affect 247 instances across:
   - Regions: cn-hangzhou (150), cn-beijing (97)
   - Environments: production (200), staging (47)

Options:
1. [CONFIRM] Proceed with all 247 instances (requires explicit acknowledgment)
2. [BATCH] Split into 5 batches (50 instances each)
3. [NARROW] Add filter to reduce scope
4. [VIEW] Show all matched instances
5. [CANCEL] Abort operation

Recommended: Option 2 (BATCH) for safer rollout
Your choice: __
```

---

### Issue: Cross-Skill Delegation Failure

**Symptoms:**
- Delegation to product skill returns error
- Cannot query instances dynamically
- Fallback to manual instance ID list required

**Common Causes:**

| Error | Cause | Resolution |
|-------|-------|------------|
| `skill not found` | Product skill not installed | Install `alicloud-{product}-ops` skill |
| `permission denied` | RAM policy missing | Grant `ReadOnlyAccess` or product-specific permissions |
| `query_command not returned` | Skill doesn't support dynamic queries | Use static instance ID list |
| `invalid filter format` | Filter JSON malformed | Validate JSON syntax |
| `timeout` | Too many instances | Add pagination or reduce scope |

**Fallback Strategy:**

```bash
# When delegation fails, fallback to manual approach:

# 1. Ask user for product CLI pattern
PRODUCT="ecs"  # or rds, slb, etc.

# 2. Manual instance discovery
aliyun $PRODUCT DescribeInstances \
  --RegionId cn-hangzhou \
  --PageSize 100 \
  --Tag.1.Key env \
  --Tag.1.Value production

# 3. Extract instance IDs manually
INSTANCE_IDS=$(aliyun ... | jq -r '.Instances.Instance[].InstanceId')

# 4. Build Resources JSON
RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c 'split("\n") | map(select(. != "")) | map({"instanceId": .})')

# 5. Use in CMS rule
aliyun cms PutResourceMetricRule \
  --Resources "$RESOURCES" \
  ...
```

---

### Issue: Confidence Score Below Threshold (60-79)

**Symptoms:**
- Calculated confidence: 65
- HITL recommended but not mandatory
- User unsure whether to proceed

**Confidence Breakdown & Improvement:**

```
Current Confidence: 65/100 (HITL_RECOMMENDED)

Breakdown:
✓ Instance count (15/25): 8 instances (acceptable range)
✓ Filter explicit (20/20): Specific tags provided
⚠ Environment (10/20): Production environment detected
✓ Standard operation (15/15): Threshold adjustment
✓ Rollback available (10/10): Delete command exists
⚠ Historical success (5/10): First execution

Recommendations to increase confidence:
1. Switch to staging environment (+10 points)
2. Use broader filter to get 10-50 instances (+10 points)
3. Execute once successfully to build history (+5 points)

Current recommendation: Proceed with caution or use HITL
```

**Decision Matrix:**

| Score Range | Decision | User Guidance |
|-------------|----------|---------------|
| 60-69 | HITL_STRONGLY_RECOMMENDED | Show improvement suggestions |
| 70-79 | HITL_RECOMMENDED | Explain risks, let user decide |
| 80-89 | AUTO_WITH_LOGGING | Proceed but log for audit |
| 90-100 | AUTO_PROCESS | Silent execution |

---

### Issue: Instance Existence Verification Failure

**Symptoms:**
- Generator creates rule successfully
- Critic verification finds instances don't exist
- Score mismatch: `correctness: 0`

**Root Causes:**

| Cause | Explanation | Fix |
|-------|-------------|-----|
| **Instance deleted** | Instance removed after discovery | Re-run discovery before execution |
| **Region mismatch** | Instance in different region than rule | Ensure region consistency |
| **Instance ID typo** | Malformed instance ID | Validate ID format per product |
| **Cross-account** | Instance in different Alibaba account | Verify account ID |
| **Timing issue** | Instance state changed mid-operation | Add retry with fresh query |

**Critic Verification Flow:**

```json
{
  "critic_verification": {
    "step": "verify_instance_existence",
    "requested_instances": ["i-xxx1", "i-xxx2", "i-xxx3"],
    "delegation": {
      "skill": "alicloud-ecs-ops",
      "query": "DescribeInstances",
      "result": {
        "found": ["i-xxx1", "i-xxx2"],
        "not_found": ["i-xxx3"]
      }
    },
    "correctness_score": 0.67,
    "suggestion": "Instance i-xxx3 not found. Update Resources to only include existing instances.",
    "action": "MODIFY_AND_RETRY"
  }
}
```

---

### Issue: HITL Prompt Timeout / No Response

**Symptoms:**
- HITL prompt displayed but user doesn't respond
- Operation hangs waiting for input
- Need automatic timeout handling

**Timeout Strategy:**

| Timeout | Action | Default Behavior |
|---------|--------|------------------|
| 30 seconds | Reminder | Show "Please respond within 2 minutes" |
| 2 minutes | Final warning | "Auto-cancel in 30 seconds" |
| 2.5 minutes | **Auto-cancel** | Abort with reason: "User timeout" |

**Configuration:**

```bash
# Set HITL timeout (optional, default: 150 seconds)
export CMS_HITL_TIMEOUT=300  # 5 minutes

# Set default action on timeout: cancel|continue|schedule
export CMS_HITL_TIMEOUT_ACTION=cancel
```

---

### Issue: Rollback After Failed Operation

**Symptoms:**
- Operation partially succeeded
- Some instances affected, others not
- Need to undo changes

**Rollback Procedures:**

| Operation | Rollback Command | Verification |
|-----------|-----------------|--------------|
| `CreateMetricRuleBlackList` | `DeleteMetricRuleBlackList` | Verify blacklist removed |
| `PutResourceMetricRule` | `DeleteMetricRule` | Verify rule deleted |
| `PutMetricRuleTargets` | `PutMetricRuleTargets` (empty) | Verify contacts removed |
| `PutEventRule` | `DeleteEventRule` | Verify rule deleted |
| `EnableAlarm` | `DisableAlarm` | Verify state=DISABLED |

**Auto-Rollback Flow:**

```bash
# If operation fails mid-way, auto-rollback:

# 1. Track affected resources
AFFECTED_INSTANCES="i-xxx1 i-xxx2 i-xxx3"

# 2. Execute rollback for each
for instance in $AFFECTED_INSTANCES; do
  aliyun cms DeleteMetricRuleBlackList \
    --RegionId cn-hangzhou \
    --RuleName "TempBlacklist-$instance"
done

# 3. Verify rollback
aliyun cms DescribeMetricRuleBlackList \
  --RegionId cn-hangzhou
# → Should not show deleted blacklists
```

---

### Quick Diagnostic Checklist

When troubleshooting Phase 3-H issues, follow this order:

```bash
# 1. Verify CLI works
aliyun version

# 2. Verify credentials
aliyun sts GetCallerIdentity

# 3. Verify product skill delegation works
# (Simulate delegation to target product)
aliyun ecs DescribeRegions  # or rds, slb, etc.

# 4. Test filter manually
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --Tag.1.Key env \
  --Tag.1.Value production

# 5. Verify instance count
count=$(aliyun ... | jq '.Instances.Instance | length')
echo "Matched instances: $count"

# 6. Check confidence factors
# - Instance count in range (10-50)?
# - Filter explicit?
# - Non-critical environment?
# - Rollback available?

# 7. Simulate HITL decision
if [ $count -eq 0 ]; then
  echo "DECISION: HITL_MANDATORY (empty list)"
elif [ $count -gt 100 ]; then
  echo "DECISION: HITL_REQUIRED (too many instances)"
elif [ $confidence -lt 80 ]; then
  echo "DECISION: HITL_RECOMMENDED (low confidence)"
else
  echo "DECISION: AUTO_PROCESS"
fi
```

---

## References

- [CMS API Error Codes](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-cms-2019-01-01-overview)
- [RAM Policies for CMS](https://help.aliyun.com/zh/ram/user-guide/grant-permissions-to-the-ram-user)
- [CMS Quotas and Limits](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/product-overview/quotas)
- [SKILL.md Phase 3-H Summary](../SKILL.md#phase-3-h-dynamic-instance-level-alert-management-new) - Capability overview
- [rubric.md HITL Scoring](rubric.md#3-phase-3-h--hitl-confidence-scoring-framework) - Confidence calculation details
- [prompt-templates.md](prompt-templates.md) - Complete GCL templates for all operations
