# TODO for alicloud-polar-postgresql-ops
## Post-Update Self-Review Checks
1. [x] Structural checks passed
2. [x] Content checks passed
3. [x] Token efficiency optimized
4. [x] TODO.md synced
5. [x] Langfuse integration validated

## ✅ 2026-06-18 — Fix SkillOpt wrapper product naming + DBType auto-inject + lib CMS-template bleed
- `scripts/polar-postgresql-skillopt-wrapper.sh`: route to aliyun CLI product `polardb` (aliyun CLI has no `polar-postgresql` product); auto-inject `--DBType PostgreSQL` for `Describe*/List*` calls when caller did not pass `--DBType`; preserve backward-compat token aliases (`polar-postgresql` / `polardb` / `polardb2`).
- `scripts/skillopt-lib.sh`: replace CMS-template bleed — `SKILLOPT_LOG_LABEL=PolarDB-PostgreSQL-SkillOpt`, `SKILLOPT_SKILL_TAG=alicloud-polar-postgresql-ops`, log/runtime file prefix `polar-postgresql-skillopt-*`, Forbidden hint `polardb:*`.
- `test-skillopt-backward-compatibility.sh`: Test 2 invokes the new wrapper; Test 3/4 use correct `scripts/` paths; Test 1 uses `DescribeDBClusters`.
- Backward-compat suite: 4/4 ✓
- E2E DescribeDBClusters via wrapper with `SKILLOPT_ENABLED=true`: returns 0 records for `--DBType PostgreSQL`; correctly filters engine type.

## ✅ 2026-06-18 — Remove legacy polardb-skillopt-wrapper.sh
- Deleted `scripts/polardb-skillopt-wrapper.sh` (legacy generic wrapper sourced from the now-missing `../references/skillopt-lib.sh`).
- `references/skillopt-integration.md`: wrapper section now points at the active `./scripts/polar-postgresql-skillopt-wrapper.sh DescribeDBClusters` example.
