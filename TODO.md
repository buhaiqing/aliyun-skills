# TODO

## Skill Development

- ✅ Add Alibaba Cloud Cloud Enterprise Network (CEN/云企业网) operations skill: `alicloud-cen-ops`
- ✅ Add Alibaba Cloud Performance Testing Service (PTS/性能测试) operations skill: `alicloud-pts-ops` v1.0.0 (dual-path CLI plugin + SDK, SkillOpt, GCL recommended)
- ✅ Add Alibaba Cloud DNS (云解析DNS) operations skill: `alicloud-dns-ops` v1.0.0 (dual-path CLI + SDK, SkillOpt, GCL recommended)

## SkillOpt Integration (Self-Repair Framework)

SkillOpt provides automated self-repair and dynamic parameter optimization for every cloud operation (see [docs/harness-integration-guide.md](docs/harness-integration-guide.md)).

## Microsoft SkillOpt — Artifact Evolution Flywheel (M1/M2/M3)

> Runtime Harness ≠ [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt). Architecture: [runtime-harness-glossary.md §1.1](docs/runtime-harness-glossary.md#11-与-microsoft-skillopt-的架构关系). Plans: [Milestone A](docs/superpowers/plans/2026-06-26-ms-skillopt-milestone-a.md) · [Milestone B](docs/superpowers/plans/2026-06-26-ms-skillopt-milestone-b.md). Operator guide: [scripts/skill_evolution/README.md](scripts/skill_evolution/README.md).

| Milestone | Scope | Status |
|-----------|-------|--------|
| **M1 (A)** | `scripts/skill_evolution/` — export trajectories, trainable seed, dataset; pilot `alicloud-ecs-ops` | ✅ |
| **M2 (B)** | `benchmark/alicloud_ops/` — dataloader + rollout + scorer + `run_milestone_b.sh` | ✅ |
| **M3 (C)** | SkillOpt-Sleep nightly queue + L3 priority + draft PR (human merge) | 📋 |

Operator: `run_milestone_a.sh` · `run_milestone_b.sh` (see [README](scripts/skill_evolution/README.md#three-milestones--what-each-one-delivers)).

### M3 (C) — Sleep / nightly queue (planned)

> **Depends on:** M1 + M2 green. **Non-goals:** auto-merge `SKILL.md`; hot-path wrapper changes.

- [ ] **M3.1** `scripts/skill_evolution/queue_nightly.py` — scan L1 JSONL + L2 `reflexion.json`, rank `(skill, failure_pattern.count, eval_priority)`
- [ ] **M3.2** Integrate `make doctor-weekly-apply` / `docs/strategy-baseline.json` — enqueue high-risk skills from L3
- [ ] **M3.3** `run_milestone_c.sh` — for each queued skill: `run_milestone_b.sh` → optional `skillopt train` (offline) → write `.runtime/skill-evolution/{skill}/best_skill.md` candidate
- [ ] **M3.4** PR drafter — diff `best_skill.md` vs `SKILL.md` selected sections; require `skill-change-critic-gate.sh verify --run` before opening PR
- [ ] **M3.5** Scheduler — local cron or `.github/workflows/skill-evolution-weekly.yml` (git-signal-only GHA branch; runtime queue on maintainer machine per [memory-strategy.md](docs/memory-strategy.md) Local-first)
- [ ] **M3.6** Tests — `scripts/test-skill-evolution-milestone-c.sh` (queue ranking + mock train path, no auto-commit)

### ✅ Fully Integrated (4/4 files) — 40 skills

ack, ask, **actiontrail**, alb, **advisor**, **agentrun**, **bailian**, **billing**, **cen**, cms, **dns**, das, dts, eci, ecs, eip, elasticsearch, ess, fc, kms, mongodb, nas, nat, oss, polar-mysql, polar-oracle, polar-postgresql, **pts**, ram, rds, redis, **resourcemanager**, sas, slb, **sls**, **sms**, **terraform**, vpc, **voice**, waf

**GCL runner** (`alicloud-gcl-runner-ops`) — ✅ full 4/4: Python `gcl_runner.py` wrapper + integration doc + backward-compat test.

### Integration Method

**Preferred (2026-06+)**: Copy `alicloud-ecs-ops/scripts/skillopt-lib.sh` overlay stub — it sources shared core from [`alicloud-skillopt-ops`](../alicloud-skillopt-ops/SKILL.md). Or use the generator:

```bash
# .scripts/gen-skillopt.sh <skill-dir> <log-tag> <cli-product> <product-name> <ram-action> <json-params> <resource-api> <smoke-action> <error-codes> <quota-error>
.scripts/gen-skillopt.sh alicloud-mongodb-ops MongoDB dds MongoDB 'dds:*' \
  'InstanceIds SecurityIpList Tag DBInstanceIds' '' DescribeRegions \
  'ResourceNotFound|InstanceNotFound' QuotaExceeded
```

### Shared Framework + Observability

| Component | Path | Status |
|-----------|------|--------|
| Shared runtime | `alicloud-runtime-harness-ops/` (`harness-core-lib.sh`, `harness-paths.sh`, `harness_runtime.py`); legacy `alicloud-skillopt-ops` shims | ✅ P0/P1 done |
| Multi-skill Langfuse E2E | `scripts/test-multi-skill-session.sh` (full + `--local`) | ✅ 11/11 (cms + ecs + oss) |
| `SKILLOPT_ENABLED` env / `.env` precedence | `skillopt_init()` in shared core | ✅ |
| P2: `skillopt_wrap()` in shared core | `alicloud-skillopt-ops/TODO.md` | ✅ done |
| P2: `gen-skillopt.sh` overlay stub | `alicloud-skillopt-ops/TODO.md` | ✅ done |
| P3: `skillopt_report()` in shared core | `alicloud-skillopt-ops/TODO.md` | ✅ done |

See [docs/harness-integration-guide.md](docs/harness-integration-guide.md) for enable flags, Langfuse, and multi-skill session testing.

## Recent Updates

- ✅ **Harness-lib header comment fix** (2026-06-23): Corrected copy-paste `alicloud-ecs-ops` headers in `alicloud-fc-ops`, `alicloud-polar-mysql-ops`, `alicloud-ram-ops`, `alicloud-sls-ops`, `alicloud-vpc-ops` `scripts/harness-lib.sh`.
- ✅ **Langfuse tracing docs rollout** (2026-06-23): Added standardized Langfuse section to 34 `references/skillopt-integration.md` files; verification examples now use product-appropriate read-only operations instead of generic `DescribeInstances`; added billing dual-wrapper note.
- ✅ **ActionTrail GCL artifacts (Phase 2)** (2026-06-21): `alicloud-actiontrail-ops` — `references/rubric.md` + `references/prompt-templates.md`; SKILL.md Quality Gate section; clears structure-check GCL warnings.
- ✅ **Harness-lib template debt** (2026-06-21): Regenerated 14 overlays (11 CMS + 3 ECS copies) with correct `SKILLOPT_SKILL_TAG` / log paths; `.scripts/regen-harness-lib-only.sh` + `fix-harness-lib-template-debt.sh`.
- ✅ **GCL R5 cross-skill — 5.1 error normalization** (2026-06-18): `normalize_error_pattern()` + `reflexion_store` cli_parameter enrich; `references/cross-skill-patterns.md`; `ErrorNormalizeTests`.
- ✅ **GCL R5 cross-skill — 5.2–5.4 aggregate + tiered retrieve** (2026-06-21): `generalized_cli` store category, `reflexion_aggregate_generalized`, CLI `aggregate-generalized`, `reflexion_retrieve` tier 0/1/2, `memory-maintain-apply` hook, `CrossSkillAggregateTests`.
- ✅ **GCL R6 remediation tracking** (2026-06-21): `remediated` schema, dynamic K confirm window, `remediation_apply_from_trace` in `gcl_runner`, retrieve deprioritization, `RemediationTests`.
- ✅ **Docs sync — memory R2–R6** (2026-06-21): `AGENTS.md` §17, `gcl-spec.md` §15.4.2–15.4.4, `memory-strategy.md`, `memory-preflight.md`, `doctor-review-setup.md`, `gcl-runner-ops/scripts/README.md`.
- ✅ **P1/P2 validation** (2026-06-21): 首次本地 `make doctor-weekly-apply` (`6415886`); `test-harness-integration.sh` 47/47 PASS.
- ✅ **GCL R4 success patterns — template rollout** (2026-06-18): `{{success_patterns}}` in all 39 GCL `prompt-templates.md` + contract test.
- ✅ **GCL R4 success patterns — 4.6 preflight slot** (2026-06-18): `memory_preflight.py` → `success_retrieve` + `{{success_patterns}}`; `apply_memory_preflight_slots`; ecs/rds/redis 试点模板; `SuccessPatternPreflightTests`.
- ✅ **GCL R4 success patterns — 4.4 extract + PASS hook** (2026-06-18): `extract_success_pattern()` in `gcl_runner.py` (HW-1..5 / OR skip / hint); `run_loop` → `trace["success_pattern"]`; `main()` → `success_store()`; `ExtractSuccessPatternTests`.
- ✅ **GCL R4 success patterns — 4.3 store/retrieve** (2026-06-18): `gcl_reflexion.py` — `success_store` / `success_retrieve` / `format_success_patterns` / `compute_command_hash`; atomic `success_patterns.json`; `SuccessPatternStoreTests` + `SuccessPatternRetrieveTests`.
- 🚧 **GCL R4 success patterns — 4.1/4.2 design** (2026-06-21): superseded by 4.1–4.6 ✅.
- ✅ **Runtime Harness Phase 3 — 4/4 completion** (2026-06-21): `advisor`, `agentrun`, `terraform` — fixed CMS-copy `harness-lib.sh`, added `skillopt-integration.md` + `test-skillopt-backward-compatibility.sh`; AGENTS §15.5 + root `TODO.md` → 39 product skills @ 4/4.
- ✅ **CI ruff hardening + GCL path/docs** (2026-06-21): blocking `ruff check` on `alicloud-gcl-runner-ops/scripts/` + `scripts/` (`E9,F821,F822,F823`); full-repo style remains advisory; fix `critique()` LLM param wiring (F821); AGENTS §9/§11.1 + README unittest cwd.
- ✅ **Runtime Harness Strategy B — PR-9c** (2026-06-21): Framework `references/` + `assets/` canonical in `alicloud-runtime-harness-ops`; legacy symlinks in `skillopt-ops`; `validate_all_skills.py` shared-framework rules; harness-first docs (references, integration guide, AGENTS §15).
- ✅ **Runtime Harness Strategy B — CI structure fix** (2026-06-21): `d0fa20c` — move references/assets to runtime-harness-ops; fix `structure-check` 42/42 pass.
- ✅ **Runtime observability centralized layout** (2026-06-22): wrapper traces/sessions/logs/metrics → `${SKILLS_DIR}/.runtime/{traces,sessions,logs,metrics}/<skill-tag>/`; docs synced (harness-integration, token-efficiency-runtime, memory-strategy, session-trace design, product skillopt-integration samples).
- ✅ **Runtime Harness Strategy B — PR-9b** (2026-06-21): 46 harness wrappers source `harness-lib.sh` first (legacy `skillopt-lib.sh` fallback); `migrate-wrappers-harness-lib.sh` + naming contract PR-9b.
- ✅ **Runtime Harness Strategy B — PR-9** (2026-06-21): Overlay lib inversion — `harness-lib.sh` canonical in 40 skills; `skillopt-lib.sh` legacy symlink; fix billing `bssopenapi-harness-wrapper.sh`; `invert-harness-libs.sh` + naming contract PR-9.
- ✅ **Runtime Harness Strategy B — PR-8** (2026-06-21): Framework path inversion — `alicloud-runtime-harness-ops/scripts/{harness-core-lib,harness-paths,harness_runtime.py}` canonical; `alicloud-skillopt-ops` legacy shims; integration test moved to `test-harness-integration.sh`.
- ✅ **Runtime Harness Strategy B — PR-7** (2026-06-21): `HARNESS_*` env + `--harness-*` CLI as user-facing single track; HARNESS wins when both set; legacy `SKILLOPT_*` runtime compat; integration guide / AGENTS / multi-skill test updated.

- ✅ **Runtime Harness Strategy B — PR-6** (2026-06-21): Wrapper inversion — `*-harness-wrapper.sh` holds implementation; `*-skillopt-wrapper.sh` legacy shim; `gen-skillopt.sh` + `gen-skillopt-legacy-shims.sh`; naming contract PR-6 checks.

- ✅ **Runtime Harness Strategy B — PR-5** (2026-06-21): Remove dead Trace Judge config (`SKILLOPT_JUDGE_*`) from 40 product overlays + ECS golden template; drop `.env.example` Judge section; update integration/observability docs and gray-skill static checks.

- ✅ **Runtime Harness Strategy B — PR-4** (2026-06-21): `gen-skillopt.sh` auto-runs `gen-harness-shims.sh`; AGENTS §15.8 prefers `*-harness-wrapper.sh`; CI wrapper-compliance dual glob; critic gate paths updated.

- ✅ **Runtime Harness Strategy B — PR-3** (2026-06-21): `*-harness-wrapper.sh` shims + `harness-lib.sh` symlinks (`.scripts/gen-harness-shims.sh`); `alicloud-runtime-harness-ops` redirect skill; `gcl_memory.py` harness-wrapper op extract.

- ✅ **Runtime Harness Strategy B — PR-2** (2026-06-21): `HARNESS_*` env + `--harness-*` CLI aliases in `skillopt-core-lib.sh`; `harness_wrap()` alias; integration + contract tests.

- ✅ **Runtime Harness Strategy B — PR-1** (2026-06-21): Glossary (`docs/runtime-harness-glossary.md`); AGENTS §15 + integration guide + memory-observability docs use canonical **Runtime Harness** terminology (legacy paths unchanged).

- ✅ **Runtime Harness Strategy B — PR-0** (2026-06-21): Naming contract acceptance tests (`scripts/test-runtime-harness-naming-contract.sh`), shared wrapper discovery lib (`scripts/lib/runtime-harness-discover.sh`), `validate-wrapper-first.sh` dual-glob (`*-skillopt-wrapper.sh` + `*-harness-wrapper.sh`); CI job `runtime-harness-contract`. PR-1..PR-4 follow in worktrees.

- ✅ **`strategy-preflight` → `doctor` rename** (2026-06-21): Makefile targets `doctor`/`doctor-history`/`doctor-weekly`/`doctor-weekly-apply`, vars `DOCTOR_*`, GitHub workflow `doctor-weekly.yml`, docs updated.

- ✅ **Doctor rename 遗留项（选项 B）** (2026-06-21): `DOCTOR_WORK` → `.runtime/doctor/work`（`gcl_strategy.WORK_DIR` 为单一来源）；`DOCTOR_LLM_*` 为主、`STRATEGY_LLM_*` 兼容；`docs/strategy-review-setup.md` → `docs/doctor-review-setup.md`；GHA `doctor-weekly.yml` 路径与 env 同步。Committed 产物名 `docs/strategy-baseline.json` / `strategy-report.md` 保持不变（Layer 3 Strategy Memory 语义）。

### Deferred cleanup (after `strategy-preflight` → `doctor` rename)

- ✅ `DOCTOR_WORK` / `.runtime/doctor/work` — see above
- ✅ `DOCTOR_LLM_*` env vars + legacy `STRATEGY_LLM_*` fallback in `strategy_synthesize.py`
- _(unchanged)_ `docs/strategy-baseline.json` / `docs/strategy-report.md` — committed Layer 3 data files; rename not required
- ✅ `docs/doctor-review-setup.md` (was `strategy-review-setup.md`)
- ✅ PR branch `doctor-review/weekly-$run_id` in `doctor-weekly.yml`
- ✅ **`alicloud-advisor-ops` CLI form fix** (2026-06-21): Root cause of 5× Layer 1 FAILED on `GetProductList` was skill teaching PascalCase CLI subcommand. `aliyun-cli-advisor` plugin (v0.4.0) only accepts kebab-case. Fixed 76 invocations across `SKILL.md`, `references/cli-usage.md`, `references/well-architected-assessment.md`, `references/integration.md`, `references/prompt-templates.md`, `references/troubleshooting.md`, `references/core-concepts.md`. New `test-cli-form.sh` (8 tests, all green) includes global grep regression guard. RAM action names (`advisor:GetProductList`) preserved PascalCase per RAM spec.
- ✅ **CMS SkillOpt test suite + GCL prompt cleanup** (2026-06-21): `test-skillopt-backward-compatibility.sh` sets `_SKILLOPT_SKIP_WRAPPER_CHECK=1` for stub `aliyun` mocks (71/71 green); removed skill-owned `failure_patterns` from ecs/sls/waf `prompt-templates.md` per AGENTS §0.3 / §16.8
- ✅ **AGENTS.md §0 Foundations** (2026-06-21): Instruction priority, Karpathy Guidelines (K1–K4), product skill mission (§0.3); §16.8 deduped to platform memory ownership; §12.x subsection anchors restored (12.1–12.11); generator template synced with Product Skill Mission + C2b checklist
- ✅ **Renamed `alicloud-ack-serverless-ops` → `alicloud-ask-ops`** (2026-06-18): align skill name with user-facing product (ASK = Serverless Kubernetes). CLI command remains `cs`; wrapper renamed to `ask-skillopt-wrapper.sh`. All cross-skill references (ack-ops, eci-ops), GCL mapping tables (`gcl_runner.py` `PRODUCT_CLI` + `SKILL_MAX_ITER`, `gcl_smart_alarm_engine.py` `DEFAULT_SKILL_MAX_ITER`), and docs (AGENTS.md, docs/harness-integration-guide.md, docs/gcl-spec.md, docs/harness-standardization-changelog.md) updated. P0/P1/P2 defenses still pass (GCL 100/100, validate-wrapper-first P0=0).

## SKILL.md Slimming

- ✅ **alicloud-ecs-ops SKILL.md 瘦身**：提取 13 个重复轮询代码块到 `references/polling-patterns.md`，SKILL.md 中替换为紧凑引用链接；JIT Go SDK 引用统一指向 `references/api-sdk-usage.md#go-sdk-examples`；更新 Reference Directory 和 TODO.md
- ✅ **alicloud-redis-ops SKILL.md 瘦身**：提取 25 个内联 Go SDK 代码块到 `references/api-sdk-usage.md#go-sdk-examples`，提取 13 个重复轮询代码块到 `references/polling-patterns.md`；SKILL.md 从 1611 行缩减至 1422 行（-12%）；更新 Reference Directory 和 TODO.md
- ✅ **alicloud-rds-ops SKILL.md 瘦身 (P3)** (2026-06-21): 11 个重复轮询块提取到 `references/polling-patterns.md`；`Polling Strategy` 改为引用链接；更新 Reference Directory 和 `alicloud-rds-ops/TODO.md`
- ✅ **alicloud-slb-ops SKILL.md 瘦身 (P3)** (2026-06-21): 6 个重复轮询块提取到 `references/polling-patterns.md`；更新 Reference Directory 和 `alicloud-slb-ops/TODO.md`
- ✅ **alicloud-polar-mysql-ops SKILL.md 瘦身 (P3)** (2026-06-21): 2 个轮询块提取到 `references/polling-patterns.md`；保留 delete `not_found` 检测模式；`test-skillopt-backward-compatibility.sh` 4/4
- ✅ **alicloud-mongodb-ops polling 瘦身 (P3)** (2026-06-21): `references/polling-patterns.md`；`sharding-ops.md` AddShard 轮询引用化；`test-skillopt-backward-compatibility.sh` + `test-wrapper-self-call.sh` 通过
- ✅ **alicloud-ask/fc/pts/kms polling 瘦身 (P3)** (2026-06-21): 4 个 skill 各建 `references/polling-patterns.md`；FC `deploy-from-source.md` Phase 4 验证轮询引用化；PTS manifest 增加 polling-patterns；既有 Test 2/Test 4 失败为预先存在环境问题（stash 验证）
- ✅ **alicloud-polar-oracle/ack/dts/eci polling 完善 (P3)** (2026-06-21): 复用既有 `references/polling-patterns.md`，SKILL.md 内联循环全部引用化（4/4 → 0），Reference Directory 全部链接，4 个 TODO.md 同步；polar-oracle backward-compat 4/4 ✓，其余 Test 2/Test 4 失败为预先存在环境问题（stash 验证）

## Recent Updates

- ✅ **Doctor rename 遗留项（选项 B）**: `.runtime/doctor/work` canonical path; `DOCTOR_LLM_*` + `STRATEGY_LLM_*` fallback; `docs/doctor-review-setup.md`; GHA workflow env/paths aligned
- ✅ **GCL runner SkillOpt 4/4**: `alicloud-gcl-runner-ops` — Python `skillopt_run_aliyun` override, wrapper → `gcl_runner.py`, `references/skillopt-integration.md`, `test-skillopt-backward-compatibility.sh`; SKILL.md wrapper path fixed
- ✅ **Remove one-time GCL patch scripts**: deleted `.scripts/patch-gcl-critic-test-assessment*.py` (rollout complete; canonical block `docs/gcl-critic-test-assessment-block.md`)
- ✅ **GCL Critic test accuracy in prompt templates**: `AGENTS.md` §12 + `docs/gcl-spec.md` §2.1 — accuracy-over-coverage rule; canonical block `docs/gcl-critic-test-assessment-block.md`; all 34 `references/prompt-templates.md` + `gcl-rollout-spec.md` §5.4 + `alicloud-skill-generator` P0 checklist synced
- ✅ **Langfuse multi-skill E2E (full)**: `bash scripts/test-multi-skill-session.sh` — CMS + ECS + OSS shared session, **11/11** on `hai-langfuse-int.hd123.com`
- ✅ **GCL runner mechanical `test_assessment`**: `gcl_runner.py` evaluates `tests_accurate` / `regression_required` + evidence; CLI `--test-assessment`; `gcl_runner_test.py` +6 tests (93 total)
- ✅ **Skill Change Critic Gate**: `scripts/skill-change-critic-gate.sh` — mechanical regression suite selection + agent `tests_accurate` verdict; RT-6 in AGENTS.md §11.1; CI job `critic-gate` runs `scripts/test-skill-change-critic-gate.sh` on every push/PR
- ✅ **P3 SkillOpt `skillopt_report()` in shared core**: Single implementation in `skillopt-core-lib.sh`; title from `SKILLOPT_LOG_LABEL` (e.g. `ECS-SkillOpt` → `ECS SkillOpt`); removed ~125 lines × 40 overlays
- ✅ **P2 gen-skillopt.sh overlay generator**: `.scripts/gen-skillopt.sh` copies ECS overlay template with product substitutions; emits wrapper, test, integration doc
- ✅ **P2 SkillOpt `skillopt_wrap()` in shared core**: Moved orchestration to `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh`; 40 overlays retain repair/optimize hooks; optional `skillopt_check_and_poll_empty` for cms-group skills
- ✅ **SkillOpt `SKILLOPT_ENABLED` env precedence**: `skillopt_init()` resolves enablement from CLI flags → `SKILLOPT_ENABLED` env / `.env` → default `false`; 40 product overlays no longer hardcode `SKILLOPT_ENABLED=false`; backward-compat tests use `SKILLOPT_ENABLED=true` + wrapper; `.env.example` updated
- ✅ **Langfuse multi-skill E2E**: `scripts/test-multi-skill-session.sh` supports `--local` (trace files only) and `full` (Langfuse HTTP verify); cms + ecs + oss shared `SKILLOPT_SESSION_ID` — **11/11 passed** against `hai-langfuse-int.hd123.com`
- ✅ **SkillOpt shared framework (PR #2)**: `alicloud-skillopt-ops` centralizes `skillopt-core-lib.sh`, `skillopt-paths.sh`, `skillopt_runtime.py`; 40 product overlays source shared core; removed 10 duplicate `skillopt_runtime.py` copies
- ✅ **SkillOpt docs sync + ask lib migration**: Update `docs/harness-integration-guide.md` and `AGENTS.md` §15.5 from stale "9 skills" to 36 fully integrated; move `alicloud-ask-ops/references/skillopt-lib.sh` → `scripts/skillopt-lib.sh`, fix wrapper `source` path, set `SKILLOPT_SKILL_TAG=alicloud-ask-ops`
- ✅ **alicloud-cms-ops v2.5.0**: Completed 4 major SkillOpt optimizations: 1) Implemented progressive polling (10s/20s/30s) for newly created alarm rule propagation delay in `DescribeMetricAlarmList`; 2) Standardized cross-platform UTC ISO 8601 date calculations; 3) Hardened resource existence probe with strict quoting and added support for ACK and NAS; 4) Implemented step-wise Period tuning for high query count scenarios; expanded test suite to 48 tests (100% green).

- ✅ **Pillar 3 GCL Quality Gate Onboarding**: Fully onboarded and completed adversarial quality gate (GCL) coverage for both `alicloud-waf-ops` and `alicloud-sls-ops` (the remaining required-level core skills lacking GCL configurations), authoring complete, structured `rubric.md` and `prompt-templates.md` files customized for domain protection/ACL rules and REST-based log/index/project pipelines.
- ✅ **Pillar 2 Golden Template Scaling**: Successfully promoted and synchronized the v2.4.4 `skillopt-lib.sh` self-repair standards (including multi-product prefix routing for `ResourceNotFound` handling, strict-mode arrays, and stdout passthrough) from `alicloud-cms-ops` to ALL other 28 core and high-priority Alibaba Cloud product skill packages (ECS, RDS, Redis, SLB, MongoDB, VPC, SLS, ESS, etc.).
- ✅ **Pillar 1 Date Command Standardization**: Completed codebase-wide audit and automated hardening of date utilities across all product skill packages (covering `redis`, `ecs`, `mongodb`, `slb`, `rds`, `ack`, `nas`, `aiops-cruise`, `oss`, `ram`, `polar-postgresql`, `polar-mysql`), replacing platform-specific `date` commands with a robust 100% cross-platform compatible dual-branch fallback format.
- ✅ **alicloud-ram-ops v2.4.0**: AIOps content layering — create `references/monitoring.md`, `references/advanced/aiops-ram.md`, promote `intelligent-inspection.md` to `advanced/` with redirect; cross-reference coordination; SKILL.md + TODO.md sync
- ✅ **alicloud-voice-ops v1.1.0**: Add smart outbound (StartRobotTask) and IVR (IvrCall) operations; create `assets/code-snippets/` with 7 Go SDK examples (new SDK `alibabacloud-go/dyvmsapi-20170525/v4`)
- ✅ **SkillOpt P1**: Integrate `alicloud-cen-ops` (cbn) + `alicloud-sls-ops` — 2 core products, 4 files each
- ✅ **SkillOpt P2 Batch**: Integrate 6 skills in one pass — `actiontrail`, `bailian`, `billing`, `resourcemanager`, `sms`, `voice`
  - Note: `agentrun-ops` skipped (sdk-only, no aliyun CLI)
- ✅ **GCL Phase 3-A (LLM-Based Critic) implemented**:
  - Added `--critic-mode` argument (mechanical/llm/hybrid)
  - Added `GCL_CRITIC_MODE`, `GCL_CRITIC_LLM_ENDPOINT`, `GCL_CRITIC_LLM_API_KEY`, `GCL_CRITIC_LLM_MODEL`, `GCL_CRITIC_LLM_TIMEOUT`, `GCL_CRITIC_LLM_FAIL_OPEN` env vars (`.env.example` updated)
  - Implemented `load_critic_template` from skill `prompt-templates.md`
  - Implemented `critique_llm` with OpenAI-compatible HTTP call (pure stdlib `urllib`)
  - Implemented `hybrid` merge (mechanical hard gates + LLM nuanced scoring)
  - Added pre-flight validation for endpoint/api-key on `llm`/`hybrid` modes (fail-open supported)
  - **All 93 existing unit tests pass** (no breaking changes)
  - Updated all docs: `alicloud-gcl-runner-ops/SKILL.md`, `alicloud-gcl-runner-ops/README.md`, `docs/gcl-spec.md` (roadmap + changelog)
- ✅ Token-efficiency optimization for `alicloud-cms-ops/SKILL.md`: compact main
  entrypoint, preserve CLI/SDK paths, safety gates, AIOps/GCL routing, and
  lazy-load detailed references; moved plugin/AI-Mode command details to
  `references/cli-usage.md`
- ✅ **alicloud-cms-ops v2.4.4**: Integrate cross-product `ResourceNotFound` prefix routing (supporting ECS, RDS, Redis, SLB, MongoDB, PolarDB, EIP, VPC); refactor platform-specific `date` commands in guide docs to be 100% cross-platform compatible; expanded backward compatibility test suite to 42 tests (100% green).
- ✅ **alicloud-cms-ops v2.4.3**: Complete P0 (prefer Wrapper in SKILL.md) and P1 (RegionId auto-completion & TimeRange shrinking self-repair) tasks; 39-test suite 100% green; updated generator script
- ✅ **alicloud-cms-ops v2.4.2 SkillOpt hardening**: `.runtime/` artifact paths,
  repair stdout passthrough, `skillopt-self-repair.sh` delegates to wrapper,
  flags/docs accuracy, 32-test suite green
- ✅ alicloud-polar-mysql-ops v1.6.0: Add `assets/scripts/slow-sql-aggregator.py` — multi-dimension slow SQL aggregation tool (DOPS-85809)
- ✅ Refactor `alicloud-redis-ops` redis-cli install layer: extract `references/redis-cli-install.md` as single source of truth; add SUSE/zypper, Aliyun ECS mirror acceleration, offline mode (`REDIS_CLI_BIN_URL`), auto-install build tools for source fallback; unify exit code contract (20/21/22)
- ✅ Add user-friendly configuration guide to `redis-cli-install.md`: 30s decision tree, scenario-driven setup for mirror acceleration & offline mode, 4-step offline binary preparation, side effects & rollback instructions, 6 FAQs; update `.env.example` with `REDIS_CLI_BIN_URL` template and discoverability comments
- ✅ Extract install script to executable `scripts/redis-cli-install.sh` (344 lines); refactor `redis-cli-execution.md` to inline via `cat` (no manual copy-paste); strip redundant 311-line script from `redis-cli-install.md` (now design spec + user guide only); single source of truth verified via grep
- ✅ Post-review P0/P1 bug fixes for `redis-cli-install.sh`: fix `use_aliyun_yum_mirror` sed delimiter conflict (verified by functional test on mock CentOS repo); replace unreliable `BASH_SOURCE` guard with explicit `REDIS_CLI_INSTALL_AUTORUN=1` flag; remove stale "copy from install.md" Step 2 docs in `execution.md`; rewrite merge script with `printf %q` escaping + `<<'BIZ'` quoted here-doc to eliminate shell injection; normalize section anchors

## Runtime LLM Token Observability (TEL)

> Design spec: [docs/token-efficiency-runtime.md](docs/token-efficiency-runtime.md)（MVP 已确认；§6 Deferred 加强方案供后续 RFC）

- ✅ Design approved (2026-06-22): `.runtime/token/{current,history,reports}/`, `coding_agent`+`model`, weekly cross-analysis with trace/memory (read-only join)
- ✅ **Phase 1** (2026-06-22): GCL `critique_llm` → `critic_meta.llm_usage` + `coding_agent`/`model`; `_critic_trace_payload` 持久化；9× `CritiqueLlmUsageTests`；worktree `phase1-gcl-usage`
- ✅ **Phase 2** (2026-06-22): Harness `skillopt_record_llm_usage`, `llm_generations[]`, Prom `harness_llm_*`, Langfuse `generation-create`; `test-harness-token-usage.sh` 8/8
- ✅ **Phase 3** (2026-06-22): Session `llm_usage_total` / `llm_usage_by_agent_model` rollup; `HARNESS_AGENT_TURN_USAGE` ingest; `test-harness-token-usage.sh` 12/12; multi-skill Session 断言
- ✅ **Phase 4** (2026-06-22): IDE hook 模板（Cursor + Claude Code）、sidecar 桥接、`test-ide-agent-turn-bridge.sh` 14/14
- ✅ **Phase 4.5** (2026-06-22): MCP `context_metadata.mcp_*`、五平台 `collect-*.sh`、`test-mcp-context-adapters.sh` + harness bridge
- ✅ **Phase 5** (2026-06-22): `scripts/token_rollup.py`、`make doctor-weekly-apply` 集成、`.runtime/token/` rollup + maintain
- ✅ **TEL X-1** (2026-06-22): L1 默认 join → `by_skill.l1` + `expensive_unstable_ranking`
- ✅ **TEL X-2** (2026-06-22): L2 浪费归因 → `waste_events[]` + `l2_join.by_trap`
- ✅ **TEL X-18** (2026-06-22): MCP rollup `mcp_join` + sidecar + low_utilization_ranking
- ✅ **TEL X-10** (2026-06-22): 增量 rollup — `incremental-state.json` + `cache/normalized-records.jsonl`；`--full` / `--incremental`
- ✅ **TEL X-13** (2026-06-22): W3C `TRACEPARENT` IDE→wrapper；`w3c_trace_context` + sidecar trace-id 关联 agent turn
- ✅ **TEL X-14** (2026-06-22): Cursor native `tokenUsage` → sidecar；pre-tool 跳过 usage env
- ✅ **TEL X-15** (2026-06-22): `agent-turn-by-turn/` + `HARNESS_AGENT_TURN_ID` + rollup `by_turn`
- 📋 **TEL X-7 RFC** (2026-06-22): GCL Critic 降级/恢复成对设计 — 见 `docs/token-efficiency-runtime.md` §6.7；**暂不实现**

---

## Level 3 → 4 智能进化计划 (Gartner AI Maturity)

> 完整计划: [`docs/intelligence-evolution-plan.md`](docs/intelligence-evolution-plan.md)

### Phase A — 反馈闭环从"空壳"变"引擎"

#### A1 — Reflexion 自动填充管道
- [x] **A1.1** GCL trace failure_pattern 在 SAFETY_FAIL / HALLUCINATION_ABORT / MAX_ITER / near-miss PASS 时自动填充
- [x] **A1.2** `gcl_runner.py` 退出前自动调用 `reflexion_extract()` + `reflexion_store()`
- [x] **A1.3** wrapper 失败（非 GCL 路径）通过 `store-wrapper-lite` 写入失败模式
- [x] **A1.4** `gcl_reflexion.py success-store` 子命令：hard-won PASS → 成功模式
- [x] **A1.5** `gcl_reflexion.py report` 双输出：`docs/failure-patterns.md` + `docs/success-patterns.md`
- [x] **A1.6** pattern 添加 `git_commit` 字段

#### A2 — Pre-flight 强制注入
- [ ] **A2.1** `gcl_runner.py --preflight` 自动注入已知失败/成功模式到 Generator prompt
- [ ] **A2.2** 注入预算 ≤ 2KB（top 5 失败 + top 3 成功，单条 ≤ 200 字符）
- [x] **A2.3** `--dry-run-preflight` 标志审查注入质量

#### A3 — TTL 维护自动化
- [x] **A3.1** `make memory-maintain-apply` 正确 prune count < 3 失败模式 + 90 天前成功模式
- [ ] **A3.2** `git_collect.py --dry-run` 展示待清理 pattern
- [x] **A3.3** GHA weekly maintain（dry-run 不 commit）

### Phase B — 从"事后检查"到"事前预判"

#### B1 — 操作风险预评分
- [x] **B1.1** Risk Score (0.0–1.0) = w1*fatal + w2*irreversible + w3*fail_rate + w4*scope
- [x] **B1.2** 四因子来源可追踪（fatal/irreversible/fail_rate/scope）
- [x] **B1.3** risk_score 写入 GCL trace 字段

#### B2 — 动态 max_iter
- [x] **B2.1** Risk ≥ 0.7 → iter=5；0.3–0.7 → iter=3；< 0.3 → iter=1
- [x] **B2.2** 连续 3 次 PASS → 降一级 max_iter
- [x] **B2.3** 最近 1 次 FAIL → 升一级 max_iter

#### B3 — Pass-Rate 异常检测告警
- [x] **B3.1** 3σ 或 50% 相对下降检测
- [x] **B3.2** 异常报告输出到 `.runtime/anomaly/`
- [x] **B3.3** GHA 集成：报告提交为 PR comment

### Phase C — 跨维度智能融合

#### C1 — AIOps 巡检报告融合层
- [x] **C1.1** `scripts/agents/fusion/fusion_report.sh` — 收集 7 感知 Agent 输出
- [x] **C1.2** 统一 schema：`{findings: [{domain, severity, resource_id, description}]}`
- [x] **C1.3** 严重级别归一化（CRITICAL / HIGH / MEDIUM / LOW / INFO）
- [x] **C1.4** 重复发现去重（相同 resource_id + description 合并）

#### C2 — 跨维度根因推理
- [x] **C2.1** 预定义关联规则引擎（初始 5 条规则：闲置暴露/漂移致健康下降/高频变配/大流量前容量不足/策略冲突）
- [x] **C2.2** 推理输出：{root_cause, trigger_finding, correlated_findings, confidence, suggestion}
- [x] **C2.3** `--reload-rules` 热加载

#### C3 — 行动建议自动编排
- [x] **C3.1** ops skill 映射表（ECS→ecs-ops, SLB→slb-ops, RDS→rds-ops 等）
- [x] **C3.2** 输出格式：{suggestion, target_skill, target_operation, estimated_risk}
- [x] **C3.3** 高风险建议标记 `requires_confirmation: true`

### Phase D — 从"被动响应"到"主动运营"

#### D1 — 自动化资源优化巡航
- [x] **D1.1** `scripts/cruise/scheduler.sh` — 每周自动全链路巡检
- [x] **D1.2** high/critical findings 自动生成 Markdown 摘要
- [x] **D1.3** `docs/cruise-reports/` 保留最近 4 周，TTL 滚动清理

#### D2 — 变配预检自动触发
- [x] **D2.1** GCL pre-flight Risk ≥ 0.5 时自动触发 AIOps 目标链路健康检查
- [x] **D2.2** 预检结果注入 Generator prompt 作为 `{{preflight_health}}`
- [x] **D2.3** pre-flight 发现 CRITICAL/HIGH 问题 → 输出警告但不强制阻止

#### D3 — 风险预警自动工单化
- [x] **D3.1** CRITICAL 发现 + pass-rate 异常 → 自动生成工单 JSON
- [x] **D3.2** 工单 schema：{severity, skill, finding, suggested_action, timestamp, git_commit}
- [x] **D3.3** `references/ticket-integration.md` — Jira 集成示例文档
