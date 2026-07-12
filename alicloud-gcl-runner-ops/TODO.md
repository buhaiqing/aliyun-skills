# TODO for alicloud-gcl-runner-ops

## Runtime LLM Token Observability (TEL) — Phase 1 ✅

> Spec: [docs/token-efficiency-runtime.md](../docs/token-efficiency-runtime.md) §7.0

- [x] `parse_openai_llm_usage()` / `build_critic_meta()` / `resolve_gcl_coding_agent()`
- [x] `critique_llm()` 解析 API `usage` + `latency_ms`；fail-open 时 `llm_usage: null`
- [x] `critique()` 全模式 `critic_meta` 含 `coding_agent` + `model`
- [x] `_critic_trace_payload()` 写入 `iterations[].critic.critic_meta`
- [x] `gcl_runner_test.CritiqueLlmUsageTests` — 9 tests

## Phase 3-A — LLM-Based Critic (2026-06-18)

- [x] `--critic-mode` argument added to `gcl_runner.py`
- [x] Environment variable parsing for `GCL_CRITIC_MODE`, `GCL_CRITIC_LLM_*`
- [x] Pre-flight validation for endpoint/api-key when in `llm`/`hybrid` modes
- [x] `load_critic_template` extracts `## 2. Critic` from `prompt-templates.md`
- [x] `critique_llm` implemented (OpenAI-compatible, pure stdlib `urllib`)
- [x] `hybrid` mode: keep mechanical 0-scores for hard safety gates, use LLM for other dimensions
- [x] 93 existing unit tests pass (no breaking changes)
- [x] Documentation updated (README.md, gcl-spec.md, SKILL.md)

## §16 — Execution Memory Index (Layer 1) (2026-06-20)

- [x] `scripts/gcl_memory.py` — `memory_store()`, `memory_retrieve()`, `memory_maintain()`, CLI entry
- [x] `scripts/gcl_memory_test.py` — 60 unit tests, all passing
- [x] `gcl_runner.py main()` — `memory_store(trace, trace_path=path)` called after `persist_trace()`, non-fatal
- [x] AGENTS.md §16 — architecture, schema, QGates M1-M6, operation auto-extraction
- [x] docs/gcl-spec.md §16 — full spec with relationship to Reflexion/H layers
- [x] `.env.example` — `MEMORY_KEEP_DAYS` variable
- [x] `alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py` — `--memory-keep-days` + subprocess `gcl_memory.py --maintain`
- [x] `scripts/runtime_cleanup.py` — memory cleanup passthrough

## §15 — Reflexion Memory (Layer 2) — Optimizations

### R1 — 捕获范围拓宽（SAFETY_FAIL → MAX_ITER + near-miss) ✅

- [x] `gcl_runner.py extract_failure_pattern()`: 重写为支持三种模式（SAFETY_FAIL / MAX_ITER / PASS_NEAR_MISS）
- [x] `gcl_runner.py run_loop()`: 在 MAX_ITER 和 PASS 分支中同样调用 `extract_failure_pattern()`
- [x] `gcl_reflexion.py CATEGORY_CONFIG`: 新增 `max_iter` 和 `near_miss` 两个标准类别
- [x] `gcl_reflexion_test.py`: 新增 max_iter 和 near_miss 的提取测试
- [x] **R1 follow-up — MAX_ITER 噪声过滤**: `extract_failure_pattern()` 在 MAX_ITER 时仅当维度 <0.5 才返回 pattern（否则返回 None 跳过存储）

### R3 — 时间衰减（last_seen 追踪) ✅

- [x] `gcl_reflexion.py _time_weighted_score()`: 实现时间加权分数函数
- [x] `gcl_reflexion.py reflexion_maintain()`: 增加 `--decay-days` 参数，双层裁剪（count + time）
- [x] `gcl_reflexion.py reflexion_report()`: 改用 time-weighted score 排序（最近频率优先）
- [x] `gcl_reflexion_test.py`: 新增 TimeWeightedScoreTests (5 tests) + decay maintain tests (2 tests)
- [x] `docs/gcl-spec.md §15`: 更新 capture scope + decay 维护规则
- [x] **R3 follow-up — 自适应衰减窗口**: `reflexion_maintain()` 使用 `decay_days + min(count, 90) * 7` 而非固定 180 天
- [x] **R3 follow-up — --sort-by 参数**: `reflexion_report()` 增加 `--sort-by count|weighted`（默认 weighted）

### R2 — Pre-flight 主动注入闭环 ✅

**状态**: 已实现（2026-06-21）。编排层通过 `memory_preflight.py` + `gcl_runner.py` trace 注入；产品 skill Generator 模板需自行添加 `{{known_traps}}` 等插槽（见 `references/memory-preflight.md`）。

| # | 任务 | 状态 |
|---|------|------|
| 2.1 | `reflexion_retrieve(skill, operation, top_k)` | ✅ |
| 2.2 | `{{known_traps}}` / `{{strategy_hints}}` 插槽协议 | ✅ `memory-preflight.md` |
| 2.3 | 编排层注入 — `gcl_runner.py` → trace + `generator_prompt_with_memory` | ✅ |
| 2.4 | GCL 编排流程文档 | ✅ `gcl-execution.md` + `memory-preflight.md` |
| 2.5 | R2 端到端集成测试 | ✅ `gcl_memory_e2e_test.py` (E2E-M1) |
| 2.6 | 试点 skill Generator 模板三插槽（ecs/rds/redis） | ✅ |

### R4 — 成功模式记忆（正向参考）

**状态**: ✅ R4 4.1–4.6 全部完成（2026-06-18）。

| # | 任务 | 状态 |
|---|------|------|
| 4.1 | 有价值 PASS 判定规则 — hard-won vs ordinary | ✅ [references/success-patterns.md](references/success-patterns.md) |
| 4.2 | 成功模式 schema + `.runtime/reflexion/success_patterns.json` | ✅ 草案（同上） |
| 4.3 | `success_store()` / `success_retrieve()` | ✅ `gcl_reflexion.py` + `SuccessPattern*Tests` |
| 4.4 | `gcl_runner.py` PASS 路径 + `extract_success_pattern()` | ✅ PASS hook + `ExtractSuccessPatternTests` |
| 4.5 | 单元测试 + 可选 `docs/success-patterns.md` 报告 | ✅ `success_report()` + `SuccessReportTests` |
| 4.6 | `memory_preflight.py` → `{{success_patterns}}` 插槽 | ✅ 全量 39 skill `prompt-templates.md` |

**估计（实现阶段）**: ~3 天 | **阻塞**: 无（R2 已完成）

### R5 — 跨 Skill 模式泛化

**状态**: ✅ 5.1–5.4 已完成（2026-06-21）。

| # | 任务 | 状态 |
|---|------|------|
| 5.1 | 错误消息归一化 — `normalize_error_pattern()` | ✅ [references/cross-skill-patterns.md](references/cross-skill-patterns.md) |
| 5.2 | 跨 skill 聚合器 — ≥3 skill 共享 `normalized_key` → `generalized_cli` | ✅ `reflexion_aggregate_generalized` + CLI `aggregate-generalized` |
| 5.3 | 检索优先级 — `specific > generalized_cli > generic` | ✅ `reflexion_retrieve` 三层 tier |
| 5.4 | 单元测试（聚合 + retrieve） | ✅ `ErrorNormalizeTests` + `CrossSkillAggregateTests` |

### R6 — 修正确认与稳定性追踪

**状态**: ✅ 6.1–6.4 已完成（2026-06-21）。

| # | 任务 | 状态 |
|---|------|------|
| 6.1 | Schema 升级 — `remediated` / `remediated_at` / `total_opportunities` / `recent_failures` | ✅ [references/remediation-tracking.md](references/remediation-tracking.md) |
| 6.2 | 动态确认窗口 K — `remediation_confirm_window_k()` | ✅ |
| 6.3 | 修正确认循环 + `gcl_runner` `remediation_apply_from_trace` | ✅ |
| 6.4 | 单元测试 — `RemediationTests` | ✅ |

## Cross-cutting Infrastructure

跨层基础设施，不限于某一 R 阶段，随时可做。

- [x] `scripts/check_log_lint.py` — LOG-M1 格式检查器：验证所有 `_log()` 调用以 `event=` 开头、key=value 格式一致
- [x] `gcl_reflexion.py _log()`: 输出重定向 `print → file=sys.stderr`（修复 stdout 日志污染的 bug）
- [x] `gcl_reflexion.py _log()`: 6 个调用追加 `event=` 前缀（4 个 pre-existing + 2 个 seed CLI print→_log）
- [x] `gcl_runner.py`: 4 个 `print()` 迁移为 `_log()` 调用（pre-flight 错误、adaptive 日志、API key 警告、test-assessment 加载失败）
- [x] `docs/gcl-spec.md §15.7`: 追加并发写入风险 + 损坏恢复 anti-patterns
- [x] `docs/gcl-spec.md §16.7`: 追加 E2E-M1、LOG-M1 质量门
- [x] `CI 集成`: 将 `check_log_lint.py` 加入 CI pipeline（`gcl-test` + `strategy-weekly` jobs）
- [x] `memory_maintain` + `reflexion_maintain` 纳入 weekly GHA + `make memory-maintain-apply` + aiops retention
- [x] **Wrapper → L2（B + C）**: `reflexion_extract_wrapper_lite` / `store-wrapper-lite`（热路径 Allowlist）；`promote-from-memory`（L1 离线 reconcile）；L1 `error_code` 字段；`skillopt-core-lib.sh` 非致命 hook
- [x] **B+C 文档同步**: `gcl-spec.md` §15/§16、`memory-strategy.md`、`AGENTS.md` §16/§17、SkillOpt references、Makefile、`scripts/README.md`
- [x] **maintain 后可选 report**: `GCL_REFLEXION_REPORT_ON_MAINTAIN` + `scripts/test_runtime_cleanup_memory.py`
- [x] **R2 非试点验证**: vpc-ops + slb-ops wrapper-lite → `preflight_retrieve` `{{known_traps}}` 单测
- [x] **Case-table coverage suggest (Phase 1)**: `parse_repair_table_codes` + `is_mapped_in_repair_table` + `unmapped_in_repair` 标记 + `scan_repair_coverage.py scan|show` (suggest-only, threshold 5, never touches overlay). Phase 2 (GitHub Issue) and Phase 3 (weekly workflow) deferred.

## Blocked / Parking Lot

| 项 | 阻塞原因 | 预计解除 |
|----|----------|----------|
| Layer 3 Strategy Memory | ✅ MVP + rollup + GHA cache | 各 skill Generator 模板添加插槽（可选渐进） |
| `_save_store()` 原子写入 | ✅ write-temp + rename | — |
| LOG-M1 CI 集成 | ✅ `ci.yml` gcl-test + strategy-weekly | — |

## 依赖关系一览

```
R2 (pre-flight injection) ✅
   └── R4 (success patterns) — ✅ 4.1–4.6 完成
         ├── R5 (cross-skill) — ✅ 5.1–5.4
         └── R6 (remediation) — ✅ 6.1–6.4
```
