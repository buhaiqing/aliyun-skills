# Troubleshooting Alibaba Cloud Redis / Tair (KVStore)

## Enhanced Error Handling (NEW!)

> **CRITICAL:** Before troubleshooting any Redis/Tair issue, run the enhanced pre-flight check to detect environment issues early.

### Pre-flight Check Execution

```bash
bash scripts/preflight-check.sh
```

### Common Environment Errors (NEW!)

| Error Pattern | Root Cause | Solution |
|---------------|------------|----------|
| `Plugin 'aliyun-cli-r-kvstore' is required but not installed` | CLI plugin missing | Run pre-flight check for auto-install or use SDK fallback |
| `ERROR: mkdir ~/.aliyun/plugins: operation not permitted` | Permission restriction (CI environment) | Use SDK fallback or fix permissions |
| `ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set` | Credentials not loaded | Create .env file or set environment variables |
| `cannot use config (variable of type *v2/client.Config) as *client.Config` | Go SDK version mismatch | Use Go 1.21+ and correct import paths |
| `Cannot reach Alibaba Cloud endpoint` | Network connectivity issue | Check firewall/proxy settings |

### CLI Plugin Installation Issues (NEW!)

#### Issue: Plugin Installation Permission Denied

**Symptom:**
```
ERROR: mkdir ~/.aliyun/plugins/aliyun-cli-r-kvstore: operation not permitted
```

**Root Cause:**
- macOS system permission restrictions
- CI environment file system restrictions
- Home directory read-only or limited write access

**Diagnostic Flow:**
```bash
# Step 1: Check plugin directory permissions
ls -la ~/.aliyun/plugins/

# Step 2: Test write permission
touch ~/.aliyun/plugins/test-write && rm ~/.aliyun/plugins/test-write

# Step 3: Check if running in CI environment
if [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ]; then
    echo "Running in CI environment - permission restrictions expected"
fi
```

**Solutions:**

**Option A: Use SDK Fallback (Recommended for CI)**
```bash
cd scripts
go run sdk-fallback.go
```

**Option B: Fix Permissions (Local Environment)**
```bash
chmod 755 ~/.aliyun/plugins
aliyun plugin install --names aliyun-cli-r-kvstore
```

**Option C: Use Temporary Directory**
```bash
export ALIBABA_CLOUD_PLUGIN_DIR=/tmp/aliyun-plugins
mkdir -p "$ALIBABA_CLOUD_PLUGIN_DIR"
aliyun plugin install --names aliyun-cli-r-kvstore --plugin-dir "$ALIBABA_CLOUD_PLUGIN_DIR"
```

#### Issue: Plugin Installation Fails Silently

**Symptom:**
```
Downloading aliyun-cli-r-kvstore 0.2.0...
(no further output, command hangs or fails)
```

**Root Cause:**
- Network connectivity issue
- Plugin repository unavailable
- Download timeout

**Diagnostic Flow:**
```bash
# Step 1: Test network connectivity
ping -c 3 aliyuncli.alicdn.com

# Step 2: Check CLI version
aliyun version

# Step 3: Try with verbose output
aliyun plugin install --names aliyun-cli-r-kvstore --verbose
```

**Solutions:**
```bash
# Use SDK fallback instead
go run scripts/sdk-fallback.go

# Or retry with different network settings
export GOPROXY=https://goproxy.cn,direct
aliyun plugin install --names aliyun-cli-r-kvstore
```

### Credentials Loading Issues (NEW!)

#### Issue: Environment Variables Not Set

**Symptom:**
```
ERROR: ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set
ERROR: ALIBABA_CLOUD_ACCESS_KEY_SECRET is NOT set
ERROR: ALIBABA_CLOUD_REGION_ID is NOT set
```

**Root Cause:**
- .env file not found
- Environment variables not exported
- Shell configuration not loaded

**Diagnostic Flow:**
```bash
# Step 1: Check if .env file exists
ls -la .env

# Step 2: Check environment variables
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "ACCESS_KEY_ID is set" || echo "NOT set"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "SECRET is set" || echo "NOT set"
test -n "$ALIBABA_CLOUD_REGION_ID" && echo "REGION is set" || echo "NOT set"

# Step 3: Check CLI config file
ls -la ~/.aliyun/config.json
```

**Solutions:**

**Option A: Create .env File (Recommended)**
```bash
cat > .env <<EOF
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
EOF

# Pre-flight check will auto-load .env
bash scripts/preflight-check.sh
```

**Option B: Set Environment Variables**
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

**Option C: Use CLI Config**
```bash
aliyun configure
# Follow prompts to enter credentials
```

### Go SDK Compatibility Issues (NEW!)

#### Issue: SDK Version Mismatch

**Symptom:**
```
cannot use config (variable of type *"github.com/alibabacloud-go/darabonba-openapi/v2/client".Config) 
as *"github.com/alibabacloud-go/darabonba-openapi/client".Config value
```

**Root Cause:**
- Go version too old (< 1.21)
- SDK import path version mismatch
- Missing dependencies

**Diagnostic Flow:**
```bash
# Step 1: Check Go version
go version

# Step 2: Check Go version compatibility
GO_MAJOR=$(go version | sed -n 's/go\([0-9]*\).*/\1/p')
GO_MINOR=$(go version | sed -n 's/go[0-9]*\.\([0-9]*\).*/\1/p')
[ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ] && echo "Go version OK" || echo "Go version too old"

# Step 3: Check dependencies
cd scripts
go mod download
go list -m all | grep alibabacloud
```

**Solutions:**

**Option A: Upgrade Go**
```bash
# Install Go 1.24+
curl -fsSL "https://go.dev/dl/go1.24.0.darwin-arm64.tar.gz" | tar -xz -C /tmp
export PATH="/tmp/go/bin:$PATH"
```

**Option B: Use Correct Import Paths**
```go
// Use v1 import path (not v2)
import openapi "github.com/alibabacloud-go/darabonba-openapi/client"

// Use v2 import path for r-kvstore
import rkvstore "github.com/alibabacloud-go/r-kvstore-20150101/v2/client"
```

**Option C: Use Pre-built SDK Fallback Script**
```bash
# Use the provided sdk-fallback.go script
cd scripts
go run sdk-fallback.go
```

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request failed validation | Align body with OpenAPI; check required fields |
| `InvalidInstanceId.NotFound` / 404 | Instance does not exist | Verify InstanceId; check region |
| `InvalidInstanceStatus` / 400 | Instance not in valid state for operation | Wait for instance to reach stable state (`Normal`) |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | User adds RAM policy for `r-kvstore:*` actions |
| `QuotaExceeded.Instance` / 400 | Instance quota exceeded | HALT; user raises quota or deletes unused instances |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT |
| `InstanceAlreadyExists` | Name or config conflict | Ask reuse vs new name |
| `InvalidWhitelist` / 400 | Whitelist format invalid | Verify IP/CIDR format |
| `InvalidPassword` / 400 | Password does not meet complexity requirements | 8-30 chars, mixed case + digits + special chars |
| `DeleteProtectionIsOn` | Deletion protection enabled | Disable via ModifyInstanceAttribute |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After |
| `InternalError` / 5xx | Server-side error | Retry with backoff; then HALT with RequestId |

---

## Symptom-to-Root-Cause Quick Reference

When user reports a problem, use this table to narrow down the investigation path.

| User Symptom | Most Likely Root Cause Category | First Check |
|--------------|----------------------------------|-------------|
| "连接超时" / "Connection timeout" | 白名单未配置或实例状态异常 | 实例状态 + 白名单 |
| "访问被拒绝" / "AUTH failed" | 密码错误或账号被锁定 | 账号状态 + 密码验证 |
| "缓存命中率低" / "Low hit rate" | 缓存策略不当或Key过期过快 | HitRate指标 + 过期策略 |
| "内存使用率突增" | 大Key或热Key导致 | 大Key分析 + 内存指标 |
| "CPU使用率突增" | 热Key或复杂命令 | 热Key分析 + 慢查询 |
| "延迟突增" / "High latency" | 大Key、热Key或慢查询 | 慢查询日志 + 延迟指标 |
| "连接数打满" | 连接泄漏或突发流量 | 连接数指标 + 应用端连接池 |
| "主从延迟大" | 大Key同步或网络问题 | 数据延迟指标 + 网络检查 |
| "备份失败" | 磁盘空间不足或实例负载高 | 备份状态 + 实例负载 |
| "QPS下降" | 实例限流或后端异常 | 限流状态 + 错误指标 |
| "大Key问题" | 数据结构设计不合理 | 大Key分析(DAS) + Key分布 |
| "热Key问题" | 访问热点集中 | 热Key分析 + 读写分离 |
| "慢查询增多" | 命令效率低或索引缺失 | 慢查询日志 + 命令优化 |
| "实例重启后数据丢失" | 持久化配置不当 | AOF/RDB配置 + 备份检查 |
| "规格变更失败" | 资源不足或架构限制 | 可用资源 + 架构类型 |

---

## Scenario-Based Diagnostic Playbooks

### Scenario 1: "连接超时 / 无法连接" (Connection Timeout)

**Symptoms:** Application cannot connect to Redis/Tair instance.

**Diagnostic Flow (execute in order, stop when root cause found):**

```bash
# Step 1: Check if instance exists and is Normal
aliyun r-kvstore describe-instances \
  --RegionId "{{user.region}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=InstanceStatus,ConnectionDomain rows=Instances.KVStoreInstance[0].{InstanceStatus,ConnectionDomain}

# Expected: Status=Normal. If not Normal → wait or investigate.

# Step 2: Check whitelist configuration
aliyun r-kvstore describe-security-ips \
  --InstanceId "{{user.instance_id}}" \
  --output cols=SecurityIpGroupName,SecurityIpList rows=SecurityIpGroups.SecurityIpGroup[].{SecurityIpGroupName,SecurityIpList}

# Expected: Application source IP is in the whitelist.

# Step 3: Check account status
aliyun r-kvstore describe-accounts \
  --InstanceId "{{user.instance_id}}" \
  --output cols=AccountName,AccountStatus rows=Accounts.Account[].{AccountName,AccountStatus}

# Expected: Account is Available. If Unavailable → reset password or recreate.

# Step 4: Check connection usage via CMS
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

**Decision Tree:**
- InstanceStatus != `Normal` → Wait for instance to stabilize or investigate
- Source IP not in whitelist → Add IP to whitelist
- Account status != `Available` → Reset password or recreate account
- ConnectionUsage > 90% → Connection limit reached; scale up or optimize connection pool
- All above normal → Check network path / VPC routing / security group

---

### Scenario 2: "内存使用率突增 / 内存打满" (Memory Spike)

**Symptoms:** Memory usage spikes unexpectedly; keys may be evicted.

**Diagnostic Flow:**

```bash
# Step 1: Check current memory usage
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "MemoryUsage,UsedMemory,EvictedKeys" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: Check for large keys via DAS (if available)
# Delegate to alicloud-das-ops for CreateCacheAnalysisJob

# Step 3: Check maxmemory-policy configuration
aliyun r-kvstore describe-parameters \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ParameterName,ParameterValue rows=RunningParameters.Parameter[?ParameterName=='maxmemory-policy'].{ParameterName,ParameterValue}

# Step 4: Check key count and expiry
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "Keys,ExpiredKeys" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Decision Tree:**
- MemoryUsage > 90% + EvictedKeys > 0 → Memory full; keys being evicted
  - Check `maxmemory-policy`: should be `allkeys-lru` or `volatile-lru` for cache use cases
  - If `noeviction` → writes will fail; change policy immediately
- Large keys detected (via DAS) → Split large keys; use hash/set/list appropriately
- Key count growing fast → Set TTL on keys; review data retention
- MemoryUsage sustained > 75% → Plan vertical scaling

---

### Scenario 3: "延迟突增 / 响应慢" (High Latency)

**Symptoms:** Average response time increases significantly.

**Diagnostic Flow:**

```bash
# Step 1: Check latency metrics
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "AvgRt,MaxRt" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: Check slow logs
aliyun r-kvstore describe-slow-logs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=SQLText,ElapsedTime,ExecuteTime rows=Items.SlowLog[].{SQLText,ElapsedTime,ExecuteTime}

# Step 3: Check CPU usage (hot key indicator)
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60

# Step 4: Check bandwidth usage
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "IntranetInRatio,IntranetOutRatio" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Decision Tree:**
- Slow logs contain complex commands (KEYS, SMEMBERS, LRANGE large range) → Optimize commands
- CpuUsage > 80% + AvgRt high → Hot key suspected; delegate to DAS for hot key analysis
- IntranetInRatio/OutRatio > 80% → Bandwidth limit reached; upgrade or optimize
- Replication delay > 1s → Check network; consider upgrading instance
- No slow logs + low CPU + low bandwidth → Network latency; check client-side

---

### Scenario 4: "CPU使用率突增" (CPU Spike)

**Symptoms:** CPU usage spikes unexpectedly.

**Diagnostic Flow:**

```bash
# Step 1: Check CPU metric trend
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60 \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 2: Check QPS trend
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "UsedQPS" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Step 3: Check slow logs for expensive commands
aliyun r-kvstore describe-slow-logs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Decision Tree:**
- QPS normal + CPU high → Expensive commands (KEYS, SORT, etc.); check slow logs
- QPS high + CPU high → Traffic surge; consider scaling or throttling
- Specific command pattern in slow logs → Optimize application code
- Hot key suspected → Delegate to DAS for hot key analysis

---

### Scenario 5: "备份失败" (Backup Failure)

**Symptoms:** Automated or manual backup fails.

**Diagnostic Flow:**

```bash
# Step 1: Check backup status
aliyun r-kvstore describe-backups \
  --InstanceId "{{user.instance_id}}" \
  --output cols=BackupId,BackupStatus,BackupType,BackupStartTime rows=Backups.Backup[].{BackupId,BackupStatus,BackupType,BackupStartTime}

# Step 2: Check instance load during backup window
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]' \
  --Period 60
```

**Decision Tree:**
- BackupStatus = `Failed` → Check instance load; retry during off-peak
- Instance CPU > 80% during backup → Reschedule backup to off-peak window
- Persistent failure → Contact Alibaba Cloud support with RequestId

---

## Resource-Level Diagnostic Order

### Instance Issues
1. Verify instance exists: `aliyun r-kvstore describe-instances --InstanceId <id>`
2. Check instance status: should be `Normal` for normal operation
3. Verify region and zone configuration
4. Check instance class and capacity
5. Verify network type (CLASSIC / VPC) and VPC configuration

### Connection Issues
1. Check instance status is `Normal`
2. Verify whitelist contains source IP
3. Check account status is `Available`
4. Verify password is correct
5. Check connection usage metrics
6. Verify network path (VPC routing / security group)

### Performance Issues
1. Check CPU, memory, and connection usage metrics
2. Review slow logs for expensive commands
3. Check for large keys or hot keys (via DAS)
4. Verify bandwidth usage
5. Check replication delay (if applicable)
6. Review instance class vs workload requirements

### Backup Issues
1. Check backup status and history
2. Verify instance load during backup window
3. Check disk space (if applicable)
4. Review backup retention policy

---

## One-Shot Diagnostic Scripts

### Script 1: Full Redis/Tair Health Check

```bash
#!/bin/bash
# redis-full-health-check.sh
# Usage: ./redis-full-health-check.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"

echo "=== Instance Status ==="
aliyun r-kvstore describe-instances \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  --output cols=InstanceId,InstanceStatus,InstanceClass,EngineVersion,ConnectionDomain \
  rows=Instances.KVStoreInstance[0].{InstanceId,InstanceStatus,InstanceClass,EngineVersion,ConnectionDomain}

echo ""
echo "=== Key Metrics (Last 15 min) ==="
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Slow Logs (Last 1 hour) ==="
SLOW_START=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
aliyun r-kvstore describe-slow-logs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$SLOW_START" \
  --EndTime "$END_TIME" \
  --PageSize 10

echo ""
echo "=== Whitelist ==="
aliyun r-kvstore describe-security-ips \
  --InstanceId "$INSTANCE_ID"

echo ""
echo "=== Backup Status ==="
aliyun r-kvstore describe-backups \
  --InstanceId "$INSTANCE_ID" \
  --PageSize 5
```

### Script 2: Performance Deep Dive

```bash
#!/bin/bash
# redis-performance-deep-dive.sh
# Usage: ./redis-performance-deep-dive.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"
START_TIME=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "=== CPU Usage ==="
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Memory Usage ==="
aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName MemoryUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Latency (Avg/Max) ==="
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "$INSTANCE_ID" \
  --MonitorKeys "AvgRt,MaxRt" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Cache Hit Rate ==="
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "$INSTANCE_ID" \
  --MonitorKeys "HitRate" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME"

echo ""
echo "=== Slow Logs ==="
aliyun r-kvstore describe-slow-logs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --PageSize 20
```

---

## Diagnostic Order (Standard)

1. **Describe instance** by ID: `aliyun r-kvstore describe-instances --InstanceId <id>`
2. **Check instance status:** `$.Instances.KVStoreInstance[0].InstanceStatus` should be `Normal`
3. **Check key metrics:** CPU, memory, connections via CMS or DescribeHistoryMonitorValues
4. **Check slow logs:** `aliyun r-kvstore describe-slow-logs` for recent slow queries
5. **Check whitelist:** `aliyun r-kvstore describe-security-ips` for IP restrictions
6. **Check accounts:** `aliyun r-kvstore describe-accounts` for account status
7. **Check backups:** `aliyun r-kvstore describe-backups` for backup status
8. **Cross-skill delegation:** If DAS available, delegate cache analysis for large/hot keys