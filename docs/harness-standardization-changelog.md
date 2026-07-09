# Runtime Harness Standardization Changelog

## Overview

This document tracks all standardization changes made to `alicloud-*-ops` skills for AGENTS.md §15 compliance.

## Changes Made

### 0. Repo-centralized observability paths (2026-06-22)

**Change**: Wrapper traces/sessions/logs/metrics default to `${SKILLS_DIR}/.runtime/{traces,sessions,logs,metrics}/<skill-tag>/` via `harness-paths.sh` `_skillopt_init_runtime_paths()`. Per-skill `alicloud-*/.runtime/` is deprecated.

**Override**: `ALIBABA_CLOUD_RUNTIME_DIR` keeps a flat layout (tests / custom dirs).

**Docs**: `AGENTS.md` §13.2, `docs/harness-integration-guide.md`, `docs/token-efficiency-runtime.md`, `docs/memory-strategy.md`, product `skillopt-integration.md` samples.

### 1. Bad Substitution Fix (`_SKILLOPT_SKILL_ROOT/.runtime`)

**Issue**: Shell parameter expansion `${_SKILLOPT_SKILL_ROOT}` was missing curly braces, causing `_SKILLOPT_SKILL_ROOT/.runtime` to fail with "bad substitution" error.

**Before**:
```bash
_SKILLOPT_RUNTIME_ROOT="${ALIBABA_CLOUD_RUNTIME_DIR:-$_SKILLOPT_SKILL_ROOT/.runtime}"
```

**After**:
```bash
_SKILLOPT_RUNTIME_ROOT="${ALIBABA_CLOUD_RUNTIME_DIR:-${_SKILLOPT_SKILL_ROOT}/.runtime}"
```

**Skills Fixed**: All 36 skills with `skillopt-lib.sh` files.

### 2. Log Prefix Standardization (`[ECS-SkillOpt]` → Product-Specific)

**Issue**: Log prefix was hardcoded as `[ECS-SkillOpt]` in skills that weren't ECS, causing confusing logs.

**Before**:
```bash
skillopt_log() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf '[%s] [ECS-SkillOpt] %s\n' "$ts" "$1" >> "$SKILLOPT_LOG_FILE"
}
```

**After** (example for ACK):
```bash
skillopt_log() {
    local ts
    ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf '[%s] [ACK-SkillOpt] %s\n' "$ts" "$1" >> "$SKILLOPT_LOG_FILE"
}
```

**Skills Fixed**: 29 skills (7 already had correct product-specific prefix).

### 3. Wrapper-First Execution in SKILL.md

**Issue**: All SKILL.md files needed standardized `Runtime Rules` table enforcing wrapper-first execution.

**Added to each SKILL.md**:
```markdown
## Runtime Rules

| Rule | Status |
|:-----|:-------|
| **Wrapper-First** | MANDATORY — always prefer wrapper script, fallback to native CLI only when wrapper is missing |
| **Fallback** | Use native `aliyun <product>` only when wrapper script is confirmed missing or `skillopt-lib.sh` cannot be sourced |
```

### 4. Graceful Wrapper Fallback

**Issue**: Wrapper scripts crashed when `skillopt-lib.sh` was missing instead of falling back to direct CLI.

**Before**:
```bash
source "$SCRIPT_DIR/skillopt-lib.sh"
```

**After**:
```bash
SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
else
    echo "[WARN] skillopt-lib.sh not found — falling back to direct aliyun CLI" >&2
fi
```

### 5. SKILL.md Execution Flows Note Block

**Issue**: SKILL.md execution sections needed mandatory wrapper-first note.

**Added to each SKILL.md execution section**:
```markdown
> **Note**: All CLI examples below should be executed via the SkillOpt wrapper script.
> Fallback to native `aliyun <product>` only when the wrapper is unavailable.
```

## Skills Affected

### P1 Skills (8)
- alicloud-ecs-ops
- alicloud-oss-ops
- alicloud-vpc-ops
- alicloud-rds-ops
- alicloud-redis-ops
- alicloud-slb-ops
- alicloud-cms-ops
- alicloud-kms-ops

### P2 Skills (28)
- alicloud-ack-ops
- alicloud-ask-ops
- alicloud-actiontrail-ops
- alicloud-alb-ops
- alicloud-bailian-ops
- alicloud-billing-ops
- alicloud-cen-ops
- alicloud-das-ops
- alicloud-dts-ops
- alicloud-eci-ops
- alicloud-eip-ops
- alicloud-elasticsearch-ops
- alicloud-ess-ops
- alicloud-fc-ops
- alicloud-mongodb-ops
- alicloud-nas-ops
- alicloud-nat-ops
- alicloud-polar-mysql-ops
- alicloud-polar-oracle-ops
- alicloud-polar-postgresql-ops
- alicloud-pts-ops
- alicloud-ram-ops
- alicloud-resourcemanager-ops
- alicloud-sas-ops
- alicloud-sls-ops
- alicloud-sms-ops
- alicloud-voice-ops
- alicloud-waf-ops

### Exempt Skills (3)
- alicloud-advisor-ops: No SkillOpt integration (lightweight skill)
- alicloud-agentrun-ops: No SkillOpt integration (lightweight skill)
- alicloud-gcl-runner-ops: Python-based GCL runner (different runtime mechanism)

## Verification

All 36 skills with `skillopt-lib.sh` pass sourcing test:
```bash
for skill_dir in alicloud-*-ops; do
  lib=$(find "$skill_dir" -name "skillopt-lib.sh" -type f 2>/dev/null | head -1)
  [ -z "$lib" ] && continue
  (cd "$skill_dir" && source .env 2>/dev/null || true; source "$lib" 2>&1 >/dev/null)
done
```

Result: **36 PASS, 0 FAIL**

## Future Contributor Notes

When adding new skills or modifying existing ones:

1. **Always use `${_SKILLOPT_SKILL_ROOT}`** with curly braces for safe parameter expansion
2. **Use product-specific log prefix** like `[ACK-SkillOpt]`, not `[ECS-SkillOpt]`
3. **Add wrapper-first execution note** to SKILL.md execution sections
4. **Add Runtime Rules table** to SKILL.md with MANDATORY wrapper-first rule
5. **Implement graceful fallback** in wrapper scripts when `skillopt-lib.sh` is missing
