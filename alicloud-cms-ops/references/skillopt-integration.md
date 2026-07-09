# Runtime Harness Integration for alicloud-cms-ops

This document describes **Runtime Harness** integration for the `alicloud-cms-ops` skill.
The integration adds **self-repair** and **dynamic configuration optimization**
to CMS CLI operations via a shell wrapper library.

> **Note**: This is **Runtime Harness** (runtime CLI wrapper, traces, optional self-repair) —
> **not** [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) offline skill-document
> training (rollout / reflect / edit / validate). See
> [Runtime Harness glossary](../../docs/runtime-harness-glossary.md).

---

## Architecture

```
User / Agent
     │
     ▼
cms-skillopt-wrapper.sh          ← entry point (strips --skillopt-* flags)
     │
     ▼
scripts/skillopt-lib.sh
  ├── skillopt_init()            ← parse flags, set SKILLOPT_ENABLED
  ├── skillopt_optimize_params() ← pre-execution: raise Period, retries
  ├── skillopt_report()          ← --skillopt-report: output Markdown ops summary
  ├── [aliyun cms ...]           ← native CLI call
  └── skillopt_repair_error()    ← on failure: classify error → repair → retry
       └── skillopt_update_runtime() ← persist metrics to .runtime/metrics/<skill-tag>/
```

Runtime metrics are written to:
- Log: `${ALIBABA_CLOUD_LOG_DIR:-<skill>/.runtime}/cms-skillopt-YYYYMMDD.log`
- JSON: `${ALIBABA_CLOUD_RUNTIME_DIR:-${SKILLS_DIR}/.runtime/metrics/alicloud-cms-ops}/cms-skillopt-runtime.json`

(`<skill>` = `alicloud-cms-ops` directory; override via env vars.)

---

## Self-Repair Capabilities

| Error Code / Scenario | Repair Action | Auto-retry? |
|---|---|---|
| `Throttling.User` / `Throttling` | Exponential backoff (1s/2s/4s); add `--Period 300` | Yes |
| `InvalidParameter` / `InvalidJSON` | Compact and re-validate `--Dimensions` JSON via `jq`; standardize cross-platform UTC ISO 8601 date calculations | Yes |
| `ResourceNotFound` | Verify resource existence via product-specific Describe APIs (supports ECS, RDS, Redis, SLB, MongoDB, PolarDB, EIP, VPC, ACK, NAS); retry if found | Yes |
| Propagation Delay (Empty list on query) | Detect query filters (e.g. `--AlarmName`, `--RuleId`, `--BlackListId`) on read-only list actions (e.g. `DescribeMetricAlarmList`) returning empty; apply progressive polling (10s/20s/30s) to wait for rule propagation | Yes |
| `Forbidden` / `NoPermission` | Log RAM policy hint (`cms:*`); no auto-retry (requires human action) | No |
| `QuotaExceeded` | Log guidance; no auto-retry | No |

---

## Dynamic Optimization

Two layers run before command execution when SkillOpt is enabled:

**Pre-execution (静态优化)**
- If runtime `error_rate > 5%`: increase `SKILLOPT_RETRIES` by 1.
- If runtime `query_count > 1000`:
  - If `--Period` is not set: add `--Period 300`.
  - If `--Period` is set and its value is less than 120: raise it to `120` (step-wise Period tuning to reduce API load while preserving data resolution).

**Post-failure (动态修复)**
- Error extraction from aliyun CLI JSON output (`Code` field) or text (`Error code: ...`).
- Error-specific repair applied; result recorded to runtime JSON.

---

## Usage

### Option 1 — Wrapper Script (recommended)

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Period 60 \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

### Option 2 — Shell Alias (persistent sessions)

```bash
export SKILLS_DIR="$HOME/opensource/git/aliyun-skills"
alias aliyun-cms='source "$SKILLS_DIR/alicloud-cms-ops/scripts/skillopt-lib.sh" && skillopt_wrap cms'

# Then use normally:
aliyun-cms DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

### Option 3 — Source library directly

```bash
source scripts/skillopt-lib.sh
skillopt_wrap cms DescribeMetricList \
    --skillopt-enable \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

### Disabling SkillOpt

Omit `--skillopt-enable` or pass `--skillopt-disable` to run native aliyun with
zero wrapper overhead.

```bash
aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

---

## Circuit Breaker Pattern

To prevent cascading failures and API abuse during widespread outages, SkillOpt implements a circuit breaker pattern that monitors consecutive failures and temporarily blocks requests when a threshold is exceeded.

### How It Works

The circuit breaker has three states:

1. **Closed (正常)**: Normal operation. Failures are counted but requests proceed.
2. **Open (断开)**: After `SKILLOPT_CB_THRESHOLD` consecutive failures, the circuit opens and blocks all requests for `SKILLOPT_CB_COOLDOWN` seconds.
3. **Half-Open (半开)**: After cooldown expires, one probe request is allowed. If it succeeds, the circuit closes. If it fails, the circuit reopens.

### Configuration

Enable the circuit breaker with `--skillopt-cb-enable` and configure thresholds:

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList \
    --skillopt-enable \
    --skillopt-cb-enable \
    --skillopt-cb-threshold 5 \
    --skillopt-cb-cooldown 60 \
    --Namespace acs_ecs_dashboard \
    --MetricName CPUUtilization
```

**Flags:**

| Flag | Description | Default |
|---|---|---|
| `--skillopt-cb-enable` | Enable circuit breaker | `false` |
| `--skillopt-cb-disable` | Disable circuit breaker | — |
| `--skillopt-cb-threshold N` | Consecutive failures before opening circuit | `5` |
| `--skillopt-cb-cooldown SECS` | Seconds to wait before allowing probe | `60` |

### Behavior

When the circuit is open:
- All requests are blocked immediately (no API call made)
- Error message returned: `CircuitBreakerOpen` with remaining cooldown time
- Log entry: `cb: circuit open, Xs remaining before probe`
- Bypass with `--skillopt-cb-disable` if needed

When cooldown expires:
- Circuit transitions to half-open state
- Next request is allowed as a probe
- Success → circuit closes, failure counter resets
- Failure → circuit reopens, cooldown timer resets

### Manual Reset

If you need to manually reset the circuit breaker (e.g., after fixing an outage):

```bash
source scripts/skillopt-lib.sh
skillopt_cb_reset
```

This sets the circuit to closed state and resets the failure counter.

### Runtime JSON Fields

Circuit breaker state is persisted in `${SKILLS_DIR}/.runtime/metrics/alicloud-cms-ops/cms-skillopt-runtime.json`:

```json
{
  "cb_state": "closed",
  "cb_consecutive_failures": 0,
  "cb_opened_at": 0
}
```

- `cb_state`: `"closed"`, `"open"`, or `"half-open"`
- `cb_consecutive_failures`: Current consecutive failure count
- `cb_opened_at`: Unix timestamp when circuit was opened (0 if closed)

---

## Available Flags

| Flag | Description | Default |
|---|---|---|
| `--skillopt-enable` | Enable self-repair and optimization | `false` |
| `--skillopt-disable` | Explicitly disable | — |
| `--skillopt-report` | Output Markdown operations summary (no CLI call) | `false` |
| `--skillopt-log-file PATH` | Override log path | `~/.aliyun/logs/skillopt-YYYYMMDD.log` |
| `--skillopt-retries N` | Max repair retry attempts | `3` |
| `--skillopt-backoff "1 2 4"` | Backoff intervals in seconds | `"1 2 4"` |

---

## Viewing Runtime Metrics

### Operations Summary Report

Generate a Markdown-formatted operations summary with health status, call statistics, and actionable recommendations:

```bash
# Output to stdout
./scripts/cms-skillopt-wrapper.sh report --skillopt-report

# Or source the library and call directly
source scripts/skillopt-lib.sh
skillopt_report

# Save to file
skillopt_report "/path/to/report.md"
```

**Report Contents:**
- **Health Status**: Overall system health (Healthy/Warning/Critical) based on error rate
- **Call Statistics**: Total calls, failures, repair success rate
- **Optimization Status**: Current retry count, backoff strategy, Period tuning
- **Recommendations**: Actionable suggestions based on current metrics
- **Log File Info**: Path and size of today's log file

**Health Thresholds:**
- 🟢 **Healthy**: error_rate ≤ 5%
- 🟡 **Warning**: 5% < error_rate ≤ 20%
- 🔴 **Critical**: error_rate > 20%

### Raw Metrics

```bash
# Pretty-print runtime counters
jq '.' "${SKILLS_DIR}/.runtime/metrics/alicloud-cms-ops/cms-skillopt-runtime.json"

# Tail today's log
tail -f "${SKILLS_DIR}/.runtime/logs/alicloud-cms-ops/cms-skillopt-$(date +%Y%m%d).log"
```

---

## Dependencies

| Tool | Required | Purpose |
|---|---|---|
| `bash` >= 4.x | Yes | Associative arrays, `[[ ]]` |
| `jq` | Yes | JSON parse/validation |
| `aliyun` CLI >= 3.3.15 | Yes | Cloud API calls |
| `awk` | Yes | Float comparison in optimization |

---

## Backward Compatibility

The `aliyun` CLI is always called directly when SkillOpt is disabled (default).
No `--skillopt-*` flags are passed to `aliyun`; the wrapper strips them before
delegating. Native CLI behavior is therefore unchanged.

Run `test-skillopt-backward-compatibility.sh` to verify.

---

## Langfuse Tracing

When `SKILLOPT_LANGFUSE_ENABLED=true`, all wrapper executions are automatically traced to Langfuse.

### Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `SKILLOPT_LANGFUSE_ENABLED` | Enable/disable Langfuse tracing | `true` |
| `LANGFUSE_HOST` | Langfuse server URL | `https://hai-langfuse-int.hd123.com` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | `sk-lf-...` |

### What Gets Traced

- **Session**: One session per agent conversation (auto-generated or explicit via `--harness-session-id`)
- **Trace**: One trace per wrapper invocation (skill name + product + action)
- **Spans**: Optimization, execution, and repair spans within each trace
- **Metadata**: Resource dimensions, execution path, error codes

### Verification

```bash
# Run wrapper with Langfuse enabled
source .env
export ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET ALIBABA_CLOUD_REGION_ID
export SKILLOPT_LANGFUSE_ENABLED=true LANGFUSE_HOST LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY
./scripts/cms-harness-wrapper.sh DescribeMetricMetaList

# Check local trace
ls -lt .runtime/traces/alicloud-cms-ops/ | head -3

# Verify in Langfuse UI
# Navigate to https://hai-langfuse-int.hd123.com → Sessions → skill:alicloud-cms-ops
```


## Reference

- [SkillOpt Project Page](https://microsoft.github.io/SkillOpt/)
- [Alibaba Cloud CMS API](https://api.aliyun.com/product/Cms)
- [skillopt-lib.sh](../scripts/skillopt-lib.sh) — core library source
- [cms-skillopt-wrapper.sh](../scripts/cms-skillopt-wrapper.sh) — entry point
