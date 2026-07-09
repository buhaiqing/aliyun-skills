# Runtime Harness Integration for alicloud-slb-ops

This skill uses the **shared overlay pattern**: `scripts/harness-lib.sh` (canonical;
legacy `skillopt-lib.sh` symlink) sources
[`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md).

## Self-Repair Capabilities

1. **Throttling** (`Throttling.User`) — exponential backoff & reduced frequency
2. **Invalid Parameters** (`InvalidParameter`) — fixes JSON syntax
3. **Resource Not Found** (`ResourceNotFound`) — verifies resource existence
4. **Permission Errors** (`Forbidden`/`NoPermission`) — suggests RAM policy
5. **Connection Failures** (`ConnectionTimeout`) — retries with increased timeout
6. **Quota Exceeded** (`QuotaExceeded`) — notifies user of limits

## Usage

### Direct Command
```bash
aliyun slb DescribeInstances --skillopt-enable --RegionId cn-hangzhou
```

### Wrapper Script
```bash
cd $(pwd)/alicloud-slb-ops
./scripts/slb-skillopt-wrapper.sh DescribeInstances --RegionId cn-hangzhou
```

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
./scripts/slb-harness-wrapper.sh DescribeLoadBalancers --RegionId cn-hangzhou

# Check local trace
ls -lt .runtime/traces/alicloud-slb-ops/ | head -3

# Verify in Langfuse UI
# Navigate to https://hai-langfuse-int.hd123.com → Sessions → skill:alicloud-slb-ops
```

## Reference

- [Runtime Harness integration guide](../../docs/harness-integration-guide.md)
- [Runtime Harness glossary](../../docs/runtime-harness-glossary.md)
- See also [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) — offline skill-document training, orthogonal to Runtime Harness

