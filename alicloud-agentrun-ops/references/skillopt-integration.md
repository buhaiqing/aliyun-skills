# Runtime Harness Integration for alicloud-agentrun-ops

Shared overlay: `scripts/harness-lib.sh` →
[`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md).

> **sdk-only skill:** No official `aliyun agentrun` CLI. Primary execution is
> **HTTP API + ACS3 signing** (see `assets/code-snippets/`). The harness wrapper
> provides trace/metrics plumbing when a CLI path is added or for consistency with
> other product skills.

## Self-Repair Capabilities

Applies when operations route through `skillopt_wrap()` (future CLI or test harness):

1. **Throttling** — exponential backoff
2. **Invalid Parameters** — RegionId, JSON params
3. **Resource Not Found** — cross-product probe
4. **Permission Errors** — RAM hint (`agentrun:*`)
5. **Connection Failures** — retry with timeout
6. **Quota Exceeded** — user notification

## Usage

```bash
export HARNESS_ENABLED=true
cd alicloud-agentrun-ops
# When CLI available:
./scripts/agentrun-harness-wrapper.sh <action> [params]
```

For HTTP API flows, use code snippets in `assets/code-snippets/`; enable
`HARNESS_LANGFUSE_ENABLED` only when wrapping through the shared core.

## Reference

- [Integration guide](../../docs/harness-integration-guide.md)
- [API signing](api-signing.md)
