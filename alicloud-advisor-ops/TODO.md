# TODO for alicloud-advisor-ops

## Completed

- ✅ **Runtime Harness 4/4 (Phase 3)** (2026-06-21): Updated `skillopt-integration.md` + backward-compat test (harness-first)
- ✅ CLI kebab-case form fix + `test-cli-form.sh`
- ✅ **Common Runbooks (v1.1.0, 2026-07-14)**: Added 6 end-to-end scenario runbooks (health triage, cost closed loop, post-remediation verification, trigger-and-wait, weekly trend, multi-account aggregation) + 6 composite trigger examples in `eval_queries.json`.
- ✅ **AIOps Cruise 联动增强 (2026-07-14)**: Added cross-reference to `alicloud-aiops-cruise` in Delegation Rules, SHOULD NOT Use, and Runbook 6. Fixed `advisorscan.sh` CLI form (PascalCase→kebab-case, invalid `--Product alicloud`, wrong cost data source). Output structure now aligned to advisor-ops JSON paths.

## Post-Update Self-Review Checks

1. [x] Structural checks passed (Common Runbooks section follows Pre-flight → Execute → Validate → Recover)
2. [x] Content checks passed (all ops reference existing CLI commands; safety gates on `RefreshAdvisor*`)
3. [x] Token efficiency optimized (chain via `{{output.*}}`, no hardcoded tables)
4. [x] TODO.md synced
5. [ ] Langfuse integration validated
