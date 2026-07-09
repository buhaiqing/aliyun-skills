# Runtime Harness Integration for alicloud-advisor-ops

Advisor uses the **shared overlay pattern**: `scripts/harness-lib.sh` (canonical;
legacy `skillopt-lib.sh` symlink) sources
[`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md).

## Self-Repair Capabilities

1. **Throttling** — exponential backoff
2. **Invalid Parameters** — RegionId, JSON params
3. **Resource Not Found** — existence probe
4. **Permission Errors** — RAM hint (`advisor:*`)
5. **Connection Failures** — retry with timeout
6. **Quota Exceeded** — user notification

## Usage

```bash
export HARNESS_ENABLED=true
cd alicloud-advisor-ops
./scripts/advisor-harness-wrapper.sh get-product-list
```

Legacy shim: `./scripts/advisor-skillopt-wrapper.sh` → harness wrapper.

> **CLI form:** Advisor plugin uses **kebab-case** subcommands (`get-product-list`, not `GetProductList`).

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
./scripts/advisor-harness-wrapper.sh get-product-list

# Check local trace
ls -lt .runtime/traces/alicloud-advisor-ops/ | head -3

# Verify in Langfuse UI
# Navigate to https://hai-langfuse-int.hd123.com → Sessions → skill:alicloud-advisor-ops
```


## Reference

- [Integration guide](../../docs/harness-integration-guide.md)
- [Runtime Harness glossary](../../docs/runtime-harness-glossary.md)
