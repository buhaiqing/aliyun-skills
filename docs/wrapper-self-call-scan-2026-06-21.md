# Wrapper Self-Call Scan Report — 2026-06-21

## Background

A bug was discovered on 2026-06-21: `alicloud-slb-ops/scripts/slb-skillopt-wrapper.sh`
hit `[P0] WRAPPER REQUIRED` when the user invoked it from outside the skill
directory. Root cause: `require_skillopt_wrapper` in
`alicloud-skillopt-ops/scripts/skillopt-core-lib.sh` ran unconditionally
on every `aliyun` invocation through `skillopt_run_aliyun`, including those
originating from the wrapper itself (which IS the recommended path per AGENTS.md
§15.8).

## Fix

`require_skillopt_wrapper` now exempts callers whose `FUNCNAME` chain
includes `skillopt_wrap`. This is verified by 4 dedicated test cases in
`alicloud-skillopt-ops/test-skillopt-integration.sh`:

- Case 1: Direct call (no `skillopt_wrap` in chain) → blocked (rc=64)
- Case 2: Call through function literally named `skillopt_wrap` → allowed
- Case 3: `_SKILLOPT_SKIP_WRAPPER_CHECK=1` → allowed (escape hatch for tests)
- Case 4: End-to-end `slb` wrapper with stubbed `aliyun` → reaches API stub

## Scope Verification (this scan)

Nine skills were explicitly checked for the same anti-pattern. Each has a
new `test-wrapper-self-call.sh` that stubs `aliyun`, invokes the wrapper
with a benign read-only op, and asserts:

1. Wrapper does NOT emit `WRAPPER REQUIRED` (no self-block)
2. Wrapper output reaches the stub response

| Skill | Wrapper script | Stub op | Result |
|---|---|---|---|
| alicloud-ecs-ops | `ecs-skillopt-wrapper.sh` | `DescribeInstances` | PASS |
| alicloud-redis-ops | `redis-skillopt-wrapper.sh` | `DescribeInstances` | PASS |
| alicloud-rds-ops | `rds-skillopt-wrapper.sh` | `DescribeDBInstances` | PASS |
| alicloud-polar-mysql-ops | `polardb-mysql-skillopt-wrapper.sh` | `DescribeDBClusters` | PASS |
| alicloud-polar-postgresql-ops | `polardb-postgresql-skillopt-wrapper.sh` | `DescribeDBClusters` | PASS |
| alicloud-mongodb-ops | `mongodb-skillopt-wrapper.sh` | `DescribeDBInstances` | PASS |
| alicloud-elasticsearch-ops | `elasticsearch-skillopt-wrapper.sh` | `ListInstance` | PASS |
| alicloud-vpc-ops | `vpc-skillopt-wrapper.sh` | `DescribeVpcs` | PASS |
| alicloud-nat-ops | `vpc-skillopt-wrapper.sh` (shared) | `DescribeNatGateways` | PASS |

Total: 9/9 wrappers pass the self-call regression test.

## Broader Static Analysis

Across the entire `alicloud-*-ops/scripts/*-skillopt-wrapper.sh` family
(46 wrappers), all wrappers follow the same pattern:

```bash
SUBCMD="$1"; shift
skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
```

Therefore the lib-level `FUNCNAME` exemption transparently protects all
46 wrappers. The 9 listed above were empirically verified; the other 37
inherit the same fix by construction.

## Special Case: alicloud-gcl-runner-ops

`alicloud-gcl-runner-ops/scripts/skillopt-lib.sh` overrides
`skillopt_run_aliyun` with a custom implementation that dispatches
`gcl-runner` to `gcl_runner.py` and other products to `aliyun` directly.
**It does NOT call `require_skillopt_wrapper`**. This is intentional —
the GCL runner is an evaluator that must call `aliyun` directly to
score traces. By design, the P0 self-block guard does not fire here.

If a future maintainer wants to enforce wrapper-first for gcl-runner too,
they would need to add an explicit `require_skillopt_wrapper` call in the
custom `skillopt_run_aliyun` override. Document this decision in
`alicloud-gcl-runner-ops/SKILL.md` if/when made.

## Related Cleanup (same session)

- `strategy-preflight` → `doctor` rename (Makefile, workflow, docs)
- `alicloud-advisor-ops` kebab-case CLI form fix (76 invocations, 7 files)

See `TODO.md` Recent Updates for full audit trail.
