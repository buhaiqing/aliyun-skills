# Runtime Harness Shared Integration

## Architecture (canonical)

```
alicloud-[product]-ops/scripts/harness-lib.sh   ← product overlay (repair, wrap, report)
    │
    ├─ source alicloud-runtime-harness-ops/scripts/harness-paths.sh
    └─ source alicloud-runtime-harness-ops/scripts/harness-core-lib.sh
            ├─ skillopt_init / log / metrics / local trace (always) / Langfuse mirror / circuit breaker
            └─ scripts/harness_runtime.py (Langfuse span-create when enabled)
```

**Legacy**: `skillopt-lib.sh` symlink and `alicloud-skillopt-ops/scripts/skillopt-{paths,core-lib}.sh` shims delegate to the paths above.

## Product Overlay Requirements

Before sourcing shared core, set:

| Variable | Example |
|----------|---------|
| `_SKILLOPT_SKILL_ROOT` | `$(dirname scripts)/..` |
| `SKILLOPT_SKILL_TAG` | `alicloud-ecs-ops` |
| `SKILLOPT_LOG_LABEL` | `ECS-SkillOpt` |
| `SKILLOPT_LOG_FILE` | `${SKILLS_DIR}/.runtime/logs/alicloud-ecs-ops/ecs-skillopt-YYYYMMDD.log` |
| `SKILLOPT_RUNTIME_DATA` | `${SKILLS_DIR}/.runtime/metrics/alicloud-ecs-ops/ecs-skillopt-runtime.json` |

## Source Block (canonical — PR-8)

```bash
if [[ -z "${_SKILLOPT_SKILLS_ROOT:-}" ]]; then
    _SKILLOPT_SKILLS_ROOT="${ALIYUN_SKILLS_ROOT:-$(git -C "$_SKILLOPT_SKILL_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$_SKILLOPT_SKILL_ROOT")}"
fi
_HARNESS_SHARED_ROOT="${HARNESS_SHARED_ROOT:-${_SKILLOPT_SKILLS_ROOT}/alicloud-runtime-harness-ops}"
source "${_HARNESS_SHARED_ROOT}/scripts/harness-paths.sh"
source "${_HARNESS_SHARED_ROOT}/scripts/harness-core-lib.sh"
```

## Legacy source block (still works via shims)

```bash
_SKILLOPT_SHARED_ROOT="${SKILLOPT_SHARED_ROOT:-${_SKILLOPT_SKILLS_ROOT}/alicloud-skillopt-ops}"
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-paths.sh"
source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-core-lib.sh"
```

## Multi-Skill Session Test

```bash
cd "${ALIYUN_SKILLS_ROOT:-$(git rev-parse --show-toplevel)}"
./scripts/test-multi-skill-session.sh
```

## Integration Test (shared framework)

```bash
export ALIYUN_SKILLS_ROOT="$(git rev-parse --show-toplevel)"
bash alicloud-runtime-harness-ops/test-harness-integration.sh
# Expected: all [PASS], exit 0 (47 checks; subshell counter shows 20 — known quirk)
```
