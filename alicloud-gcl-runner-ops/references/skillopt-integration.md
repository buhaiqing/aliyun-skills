# Runtime Harness Integration for alicloud-gcl-runner-ops

Runtime Harness adds **Langfuse tracing**, structured logging, and runtime metrics around
`scripts/gcl_runner.py`. Unlike product skills, this overlay does **not** wrap
`aliyun` CLI — it executes the Python GCL runner directly.

Shared core: [`alicloud-skillopt-ops`](../../alicloud-skillopt-ops/SKILL.md)
(`skillopt-core-lib.sh`, `skillopt-paths.sh`, `skillopt_runtime.py`).

## Capabilities

| Capability | GCL Runner behavior |
|------------|---------------------|
| **Tracing** | Local trace always; optional Langfuse mirror when `SKILLOPT_LANGFUSE_ENABLED=true` |
| **Output capture** | `SKILLOPT_LAST_OUTPUT` from `gcl_runner.py` stdout/stderr |
| **Auto-repair** | Limited: `--max-iter` bump on `MAX_ITER`; rubric hints on pre-flight fail |
| **Safety** | No retry of mutating subprocess commands (GCL runner enforces this internally) |

## Usage

### Wrapper (preferred)

```bash
cd alicloud-gcl-runner-ops
SKILLOPT_ENABLED=true ./scripts/gcl-runner-skillopt-wrapper.sh \
  --skill alicloud-ecs-ops \
  --op DescribeInstances \
  --command "aliyun ecs DescribeInstances --PageSize 1" \
  --dry-run
```

### With Langfuse

```bash
export SKILLOPT_ENABLED=true
export SKILLOPT_LANGFUSE_ENABLED=true
# LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY from repo .env

./scripts/gcl-runner-skillopt-wrapper.sh \
  --skillopt-enable \
  --skillopt-langfuse-enable \
  --skillopt-session-id "sess-gcl-$(date +%s)" \
  --skill alicloud-ecs-ops \
  --op DescribeInstances \
  --command "aliyun ecs DescribeInstances --PageSize 1" \
  --dry-run
```

### Skill Change Critic Gate (RT-6)

When validating skill/script changes, combine with
[`scripts/skill-change-critic-gate.sh`](../../scripts/skill-change-critic-gate.sh)
and `gcl_runner.py --test-assessment` for mechanical test-accuracy critique.

## Fallback

If `skillopt-lib.sh` is missing, the wrapper runs `python3 scripts/gcl_runner.py`
directly (SkillOpt flags stripped).

## Reference

- [Runtime Harness integration guide](../../docs/harness-integration-guide.md)
- [Runtime Harness glossary](../../docs/runtime-harness-glossary.md)
- [GCL execution](gcl-execution.md)
- See also [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) — offline skill-document training, orthogonal to Runtime Harness
