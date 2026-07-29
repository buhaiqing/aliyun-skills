# SPEC: Wrapper-First 强制一致性 + 调用追踪体系

> 关联分支: `feature/invocation-tracking`
> 目标: 所有指令（aliyun / 产品 CLI 调用）必须走 Wrapper，产出可观测 trace（4 信号）+ `invocation` 来源块；绕过 Wrapper 的调用必须**可见、可追踪、合并前被拦截**。

## 1. 背景与问题

- 硬性要求：所有对指令的调用都走 Wrapper，生成可观测数据 + 记忆。
- 现状：trace 只由 Wrapper 产生（`skillopt_trace_start` 是唯一入口）。`require_skillopt_wrapper` 守卫会**拒绝**直连 `aliyun`，但只拒绝、不观测——绕过路径在 trace 存储中不可见。
- 缺口：
  1. 库内部 / wrapper fallback 有裸 `aliyun` 调用（`harness-lib.sh:126`、`ecs-harness-wrapper.sh:44`），不经过 `skillopt_run_aliyun`。
  2. 完全未 source harness lib 的外部调用无任何记录。
  3. 缺乏"所有 Skill（含新增）必须合规"的静态强制。

## 2. 目标（成功标准）

1. **追踪完整性**：每一次 `aliyun` 执行（无论经 Wrapper 与否）都产出一条 trace，带 `invocation.entrypoint ∈ {wrapper, direct}`。
2. **可见性**：绕过 Wrapper 的调用产出 `entrypoint: "direct"` trace，落同一存储，可被扫描。
3. **一致性强制**：所有现有 + 未来新增产品 Skill 必须声明 wrapper-first 且存在 `scripts/*-harness-wrapper.sh`；新增 Skill 模板内置该规则；CI 在合并前拦截不合规 Skill。
4. **零误伤**：层 1 静态门禁不校验 `alicloud-runtime-harness-ops` / `alicloud-skillopt-ops`（库自身，不该有 wrapper）。

## 3. 范围边界

- **IN**: 运行时追踪（方案 B' 第 1–3 层）、静态门禁、规范章节、Skill 生成器模板。
- **OUT（本次不做，列为后续）**: 第 4 层 PATH shim（`SKILLOPT_WRAPPER_SHIM`，用于拦截 repo 外 `aliyun` 调用）——仅当确认需要管 repo 外调用时再加。

## 4. 方案架构（三层强制）

### 层 0 — 规范即真理源
- `AGENTS.md` 新增强制章节「Wrapper-First 强制一致性」，定义：`invocation.entrypoint` 约束、必须存在 wrapper 脚本、4 信号 trace。
- `alicloud-skill-generator` 的 SKILL.md 模板内置 wrapper-first 声明 + wrapper 脚本骨架，保证**新增即合规**。

### 层 1 — 静态门禁（CI 合并前拦截）
- 升级 `scripts/validate-wrapper-first-docs.sh`：对每个产品 skill（排除两个库目录）校验：
  - SKILL.md 声明 wrapper-first（已有）；
  - 存在 `scripts/*-harness-wrapper.sh`（新增校验）。
- `Makefile` 的 `test-integration` 已串该脚本；门禁失败 = CI 红 = 不合规 Skill 无法合并。

### 层 2 — 运行时强制 + 追踪（方案 B' 本体）
- **单点收口**：所有 `aliyun` 执行（含 lib 内部调用、wrapper fallback）经 `skillopt_run_aliyun`。
- **`invocation` 字段**：`skillopt_trace_start` 写入
  ```json
  "invocation": {
    "entrypoint": "wrapper",
    "wrapper": "<product>-harness-wrapper.sh",
    "wrapper_version": "<SKILLOPT_HARNESS_LIB_VERSION>",
    "raw_command": null
  }
  ```
- **`direct` trace**：`skillopt_run_aliyun` 在 `require_skillopt_wrapper` 拒绝处，改为**先发射 `entrypoint:"direct"` trace**（带 `raw_command` = 原始 argv），仍返回 64 拒绝。测试上下文（`_SKILLOPT_SKIP_WRAPPER_CHECK=1`）豁免。
- **Langfuse 镜像**：`_skillopt_langfuse_create_trace` 的 `metadata` 增加 `invocation.entrypoint` + `wrapper`。
- **审计脚本** `scripts/audit-wrapper-coverage.sh`：扫 `.runtime/traces/*/trace-*.json`，列出 `entrypoint != "wrapper"`（或缺失 `invocation`），exit 1 若有（CI 闭环）。可选 `--crosscheck-actiontrail` 用现有 `gcl-actiontrail-crosscheck` 校验 `direct` 为真实云事件。

## 5. 数据契约

trace-*.json 顶层新增：
```json
"invocation": {
  "entrypoint": "wrapper" | "direct",
  "wrapper": "string | null",
  "wrapper_version": "string | null",
  "raw_command": "string | null"
}
```

Langfuse trace metadata 新增：`invocation_entrypoint`, `invocation_wrapper`（兼容现有 `app/skill/product/action/user_id`）。

## 6. 验证标准（每步可测）

- V1: wrapper 运行 → trace 含 `invocation.entrypoint == "wrapper"` 且 `wrapper` 非空。
- V2: 强制直连（构造绕过守卫的 `aliyun` 调用）→ 产出 `entrypoint:"direct"` trace，且 `raw_command` 非空。
- V3: `audit-wrapper-coverage.sh` 能捞出 V2 的 direct trace 并 exit 1。
- V4: `validate-wrapper-first-docs.sh` 对 44 产品 skill 全绿；人为移除某 skill 的 wrapper 脚本 → 脚本红。
- V5: `alicloud-skill-generator` 新生成的 Skill 自带 wrapper-first 声明 + wrapper 脚本。
- V6: 全量 `make test-integration` 通过（含新增门禁）。

## 7. 风险

- R1: 收口 `skillopt_run_aliyun` 改变内部 `aliyun` 调用路径 → 需保证 `set -e`/输出捕获不变；测试上下文豁免已存在。
- R2: wrapper fallback（`:44`）改走收口时若 harness-lib 缺失会循环 → 保留 fallback 直连作为 lib 缺失时的最后兜底，仅对"lib 已 source"的调用收口。
- R3: 层 1 门禁误伤库目录 → 已确认需排除 `runtime-harness-ops` / `skillopt-ops`（基线扫描：44 产品 skill 全有 wrapper，仅这 2 个库无）。
