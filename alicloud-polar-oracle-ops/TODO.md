# TODO for alicloud-polar-oracle-ops
## ✅ 2026-06-21 — P3 polling slimming
- `references/polling-patterns.md`: 集群状态/删除消失/`--waiter` 三模板；操作参数表。
- `SKILL.md`: CreateDBCluster 内联 60×10s 循环 → 引用；Reference Directory 已增加链接。
## Post-Update Self-Review Checks
1. [x] Structural checks passed
2. [x] Content checks passed
3. [x] Token efficiency optimized
4. [x] TODO.md synced
5. [x] Langfuse integration validated

## ✅ 2026-06-18 — Fix SkillOpt wrapper product naming + DBType auto-inject + lib CMS-template bleed
- `scripts/polar-oracle-skillopt-wrapper.sh`: route to aliyun CLI product `polardb` (aliyun CLI has no `polar-oracle` product); auto-inject `--DBType Oracle` for `Describe*/List*` calls when caller did not pass `--DBType`; preserve backward-compat token aliases (`polar-oracle` / `polardb` / `polardb2`).
- `scripts/skillopt-lib.sh`: replace CMS-template bleed — `SKILLOPT_LOG_LABEL=PolarDB-Oracle-SkillOpt`, `SKILLOPT_SKILL_TAG=alicloud-polar-oracle-ops`, log/runtime file prefix `polar-oracle-skillopt-*`, Forbidden hint `polardb:*`.
- `test-skillopt-backward-compatibility.sh`: Test 2 invokes the new wrapper; Test 3/4 use correct `scripts/` paths; Test 1 uses `DescribeDBClusters`.
- Backward-compat suite: 4/4 ✓
- E2E DescribeDBClusters via wrapper with `SKILLOPT_ENABLED=true`: returns 1 record (`pc-bp13k5754s5p2vcz8`, 恰货铺子-erp-prd-polardb, DBType=Oracle); correctly filters engine type.

## ✅ 2026-06-18 — Remove legacy polardb-skillopt-wrapper.sh
- Deleted `scripts/polardb-skillopt-wrapper.sh` (legacy generic wrapper sourced from the now-missing `../references/skillopt-lib.sh`).
- `references/skillopt-integration.md`: wrapper section now points at the active `./scripts/polar-oracle-skillopt-wrapper.sh DescribeDBClusters` example.
