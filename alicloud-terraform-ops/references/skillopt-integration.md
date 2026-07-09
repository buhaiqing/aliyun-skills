# Runtime Harness Integration for alicloud-terraform-ops

Shared overlay: `scripts/harness-lib.sh` →
[`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md).

> **IaC skill:** Control plane uses **Python scripts** (`nl2hcl_generator.py`,
> `terraform_executor.py`, HITL modes) and the **`terraform` CLI binary** — not
> `aliyun terraform` (product not in Alibaba Cloud CLI). The harness wrapper
> supports trace consistency and future CLI alignment.

## Self-Repair Capabilities

When routed through `skillopt_wrap()`:

1. **Throttling** — exponential backoff
2. **Invalid Parameters** — JSON / region fixes
3. **Resource Not Found** — registry probe
4. **Permission Errors** — RAM hint (`oss:*` for state bucket)
5. **Connection Failures** — retry with timeout
6. **Quota Exceeded** — user notification

## Usage

```bash
export HARNESS_ENABLED=true
cd alicloud-terraform-ops
# Primary IaC path (not aliyun CLI):
python3 scripts/terraform_executor.py ...
# Harness wrapper (when aliyun terraform subcommands apply):
./scripts/terraform-harness-wrapper.sh <subcommand> [params]
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
./scripts/terraform-harness-wrapper.sh plan

# Check local trace
ls -lt .runtime/traces/alicloud-terraform-ops/ | head -3

# Verify in Langfuse UI
# Navigate to https://hai-langfuse-int.hd123.com → Sessions → skill:alicloud-terraform-ops
```


## Reference

- [Integration guide](../../docs/harness-integration-guide.md)
- [HITL workflow](hitl-workflow.md)
