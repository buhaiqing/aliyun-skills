# PLAN: Wrapper-First 强制一致性 + 调用追踪

> 分支: `feature/invocation-tracking` | SPEC: `docs/spec-invocation-tracking.md`
> 流程: GCL（多子 Agent：1 Generator + ≥2 Critics，≤3 轮） | 测试: TDD

## 步骤拆解

### P1 — 运行时核心：单点收口 + `invocation` 字段（层 2 主干）
- [ ] `harness-core-lib.sh` 增加 `SKILLOPT_HARNESS_LIB_VERSION` 常量（如 `0.1.0`）。
- [ ] `skillopt_trace_start`（~L883 jq 块）写入 `invocation: {entrypoint:"wrapper", wrapper:"<product>-harness-wrapper.sh", wrapper_version:"$SKILLOPT_HARNESS_LIB_VERSION", raw_command:null}`。
- [ ] `skillopt_run_aliyun`（L1549）：守卫拒绝处（L1557-1560）改为：非测试上下文 → 先 `_skillopt_emit_direct_trace "$product" "$action" "$@"`（新函数，写 `entrypoint:"direct"` + `raw_command`），再 `return 64`。测试上下文（`_SKILLOPT_SKIP_WRAPPER_CHECK=1`）维持原行为。
- [ ] 新增 `_skillopt_emit_direct_trace`：在 `_SKILLOPT_TRACE_DIR` 写最小 direct trace（复用 trace_id 命名 + 4 信号骨架，缺 skill 解析则填 `<unknown>`）。
- **验证 V1/V2**: wrapper 运行 trace 含 `entrypoint:wrapper`；构造直连 → 产出 `entrypoint:direct` + `raw_command` 非空。

### P2 — 内部 / fallback 调用收口（层 2 收口）
- [ ] `harness-lib.sh` 内部裸 `aliyun`（如 L126 `DescribeRegions`）改走 `skillopt_run_aliyun`（保持输出捕获语义）。
- [ ] `ecs-harness-wrapper.sh:44` fallback 直连：仅当 harness-lib **未 source** 时保留直连兜底；已 source 时改走 `skillopt_run_aliyun`（避免循环：函数内检测 `FUNCNAME` 含自身则直连）。
- **验证**: 库内部调用仍正常产出 trace；无循环。

### P3 — Langfuse 镜像（层 2 导出）
- [ ] `_skillopt_langfuse_create_trace`（L1271 jq）：`metadata` 增加 `invocation_entrypoint` + `invocation_wrapper`。
- **验证**: Langfuse gate（`test-langfuse-reporting.sh`）仍 4/4，且 metadata 含新字段。

### P4 — 审计脚本（层 2 闭环）
- [ ] 新增 `scripts/audit-wrapper-coverage.sh`：扫 `.runtime/traces/*/trace-*.json`，列 `entrypoint != "wrapper"` 或缺失 `invocation`，exit 1 若有。支持 `--crosscheck-actiontrail` 可选。
- [ ] `Makefile` `test-integration` 追加该审计步骤。
- **验证 V3**: 能捞出 P1 的 direct trace 并 exit 1。

### P5 — 静态门禁（层 1 强制）
- [ ] 升级 `scripts/validate-wrapper-first-docs.sh`：每个产品 skill（排除 `alicloud-runtime-harness-ops` / `alicloud-skillopt-ops`）校验存在 `scripts/*-harness-wrapper.sh`；缺 → 红。
- **验证 V4**: 44 产品 skill 全绿；人为移除某 skill wrapper 脚本 → 红。

### P6 — 规范即真理源（层 0）
- [ ] `AGENTS.md` 新增「Wrapper-First 强制一致性」章节，引用 SPEC 数据契约；明确两个库目录豁免。
- [ ] `alicloud-skill-generator` SKILL.md 模板内置 wrapper-first 声明 + wrapper 脚本骨架（保证新增即合规）。
- **验证 V5**: 新生成 Skill 自带声明 + 脚本，过 P5 门禁。

### P7 — 测试 + GCL + 合并
- [ ] bash 单测：`invocation` 字段 schema、direct trace 发射、守卫豁免。
- [ ] 集成门禁：扩展 `test-wrapper-first-integration.sh` 或新增 `test-invocation-tracking.sh`，覆盖 V1/V2/V3。
- [ ] GCL：Generator 实现 → ≥2 Critics 并行评审（正确性 / 安全 / 一致性 / 测试覆盖）→ ≤3 轮。
- [ ] `make test-integration` 全绿（wrapper-first 4/4、doc 44/44、golden G1-G6、Langfuse 4/4、audit-coverage）。
- [ ] 提交 feature 分支 → merge `--no-ff` 到 main → 删除 worktree + 分支。
- **验证 V6**: 全量绿。

## 依赖
- P1 → P2/P3 依赖 P1 的字段与 direct 函数。
- P5 依赖基线结论（已扫：44 产品 skill 全有 wrapper，仅 2 库无 → 门禁排除这 2 个）。
- P7 依赖 P1–P6 全部完成。

## 不做（后续）
- 第 4 层 PATH shim（`SKILLOPT_WRAPPER_SHIM`）——仅当需管 repo 外 `aliyun` 调用时再加。
