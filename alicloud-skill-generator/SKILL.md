---
name: alicloud-skill-generator
description: >-
  Use when the user needs to create or update an Alibaba Cloud Agent Skill
  (`alicloud-*-ops`) in this repository — even if they don't explicitly ask for
  scaffolding or generation. Triggers include: user wants to "add a skill for
  product X", "regenerate from OpenAPI", or "fix gaps found during review".
  Also use when an existing skill needs realignment after API doc changes or
  fails a governance/adversarial review. Not for executing live changes against
  cloud accounts or for one-off debugging with no intent to maintain.
license: MIT
compatibility: >-
  Access to Alibaba Cloud official documentation, OpenAPI/Swagger for the product,
  `alicloud-skill-generator/references/alicloud-skill-template.md`,
  `references/evaluation-driven-workflow.md`,
  `references/governance-and-adversarial-review.md` (when present),
  `references/prompt-library.md` (structured prompt repository),
  `references/optimization-analysis.md` (three-dimensional optimization framework),
  `references/user-experience-spec.md` (mandatory UX requirements for generated skills),
  `references/execution-environment.md` (CLI + Go SDK setup details),
  `references/cli-behavior.md` (verified aliyun CLI behavioral notes),
  and agentskills.io frontmatter conventions.
metadata:
  author: alicloud
  version: "3.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  type: meta-skill
  guidance_freedom_level: medium
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
---

# Alibaba Cloud Skill Generator (Meta-Skill)

## Quick Start

### What This Skill Does
Scaffolds new or updates existing `alicloud-[product]-ops` skills in this repository, based on official Alibaba Cloud OpenAPI specs. This is a **meta-skill** — it generates runbooks for agents, not operational execution against cloud accounts.

### Prerequisites
- [ ] Access to OpenAPI/Swagger spec for the target Alibaba Cloud product
- [ ] Read access to this repository's template files
- [ ] Network access to Alibaba Cloud documentation URLs

### Your First Generation
```
Input: "Generate alicloud-ecs-ops for ECS instances, disks, and snapshots"
Output: alicloud-ecs-ops/ directory with SKILL.md and references/
```

### Next Steps
- [Generation Workflow](#evaluation-driven-generation-workflow) — Step-by-step generation process
- [Anti-Pattern Checklist](#anti-pattern-checklist) — Common mistakes to avoid
- [P0/P1 Checklist](#p0--must-pass) — Quality gates for generated skills

---

## Overview

This **meta-skill** defines **how** to author a new **product-scoped** operational skill (e.g. `alicloud-ecs-ops`) **inside this repo**. It does **not** perform maintenance against a user's cloud account. Live work uses the generated `alicloud-[product]-ops` skills (official `aliyun` CLI with **JIT Go SDK fallback**).

### Guidance Freedom Level: Medium (Provide Templates)

This meta-skill operates at **Medium** guidance level: it provides **templates and frameworks** ([alicloud-skill-template.md](references/alicloud-skill-template.md), prompt library, UX spec) while allowing the agent to adapt based on product-specific context. Low-level scripts (CLI installation, Go runtime JIT download) are detailed in [references/execution-environment.md](references/execution-environment.md).

### Core Principle

Generated skills are **agent-readable runbooks**: triggers, env vs user placeholders, pre-flight → execute → validate → recover, safety gates, and outputs **grounded in OpenAPI and verified CLI behavior**, not guessed.

### Technology Stack
- **CLI:** `aliyun` (Go binary, static, no dependencies) — primary execution path
- **SDK:** Alibaba Cloud Go SDK (`github.com/alibabacloud-go/<product>`) — JIT fallback
- **JIT execution:** `go run` (script mode, dynamic generation)

### Repository Scope
All generated layout and policies apply **only** to the `aliyun-skills` monorepo unless explicitly stated elsewhere.

---

## Role Boundary (Agent-Readable)

| This meta-skill **does** | This meta-skill **does not** |
|--------------------------|------------------------------|
| Choose **extend** vs **new** `alicloud-[product]-ops` | Replace deep product knowledge already in an existing ops skill |
| Scaffold `SKILL.md`, `references/*`, `assets/*` from the template | Call Alibaba Cloud APIs on behalf of the user |
| Enforce naming, frontmatter, P0/P1, delegation, and **governance** hooks | Invent request/response fields or CLI flags without official doc verification |
| Point authors to **adversarial review** before merge (when governance doc exists) | Store or echo real credentials |

If the user wants **operational execution** (e.g. "create a resource"), load the appropriate `alicloud-*-ops` skill for that product — not this generator.

---

## When to Use / Not Use

### Use When
- A new Alibaba Cloud product needs a **first** ops skill in **this repo**
- An existing skill lacks P0 elements (triggers, placeholders, flows, recovery, destructive gates)
- OpenAPI or official docs changed; the skill should be **realigned** (bump version/changelog)
- A contributor needs the **standard directory layout** for a new `alicloud-[product]-ops`

### Do NOT Use When
- One-off debugging with no intent to maintain a reusable skill
- Non–Alibaba-Cloud application work
- You only need billing/IAM execution — use dedicated ops skills when they exist

---

## Input / Output Structure

### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.name` | string | Yes | English product name (e.g., ECS, RDS) |
| `product.slug` | string | Yes | CLI product slug (e.g., ecs, rds) — verify via `aliyun help <slug>` |
| `product.chinese_name` | string | No | Chinese name for trigger matching |
| `primary_resource` | string | Yes | Primary resource type (e.g., Instance, DBInstance) |
| `api_service_id` | string | Yes | API service identifier from OpenAPI tags or SDK package |
| `openapi_url` | string | Recommended | OpenAPI/Swagger URL or path — required for API-accurate fields |
| `operation_list` | string[] | Yes | List of operations (create, describe, modify, delete, list, product-specific) |
| `doc_urls` | string[] | Recommended | Official documentation URLs |
| `cli_support_evidence` | string | Yes | Confirmation that `aliyun` exposes this product (or JIT SDK fallback needed) |

### Output

| Artifact | Description | Required When |
|----------|-------------|---------------|
| `alicloud-[product]-ops/SKILL.md` | Main skill runbook — triggers, flows, recovery, safety gates, Well-Architected assessment | Always |
| `references/core-concepts.md` | Architecture, limits, regions, quotas, dependency graph, SPOF analysis | Always |
| `references/api-sdk-usage.md` | Operation map, required fields, pagination, request/response snippets | Always |
| `references/cli-usage.md` | `aliyun` CLI command map, coverage gap table, invocation patterns | `cli_applicability: cli-first` / `dual-path` / `cli-only` |
| `references/troubleshooting.md` | Error codes (≥ 10), ordered diagnostics, multi-round diagnosis | Always |
| `references/monitoring.md` | Metrics, dashboards, alerts, cost & performance metrics | Product has CMS metrics |
| `references/integration.md` | JIT SDK setup, env vars, cross-skill delegation matrix | Always |
| `references/well-architected-assessment.md` | Five-pillar assessment: Security, Stability, Cost, Efficiency, Performance | Always |
| `references/enhanced-self-healing-framework.md` | Self-healing patterns for installation flows | Always (referenced) |
| `references/knowledge-base.md` | Fault pattern library for diagnostic skills | AIOps/diagnosis skills |
| `references/observability.md` | Metrics→Logs→Traces linkage | Monitoring/AIOps skills |
| `references/idempotency-checklist.md` | Idempotent behavior for retries/automation | Automation-heavy products |
| `assets/example-config.yaml` | Example configuration with UX and optimization settings | Always |
| `assets/eval_queries.json` | Trigger accuracy evaluation queries for the generated skill | Always |
| `assets/code-snippets/<verb>_<resource>.go` + `go.mod` + `README.md` | 可直接 `go run` 的 Go SDK 代码片段（每 operation 一文件 + 独立 module） | `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式) |

---

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Reference them throughout the generation workflow.

### Standard 1: Clear Boundaries (边界明确)
- **SHOULD use** conditions: precise, with keywords and intent matching
- **SHOULD NOT use** conditions: explicit negative cases that prevent misfire
- **Delegation rules**: clear pointers to related skills

### Standard 2: Structured I/O (输入输出结构化)
- Input parameters defined with types and sources (`{{env.*}}`, `{{user.*}}`)
- Output fields defined with JSON paths from OpenAPI response schemas
- Placeholder conventions: `{{env.*}}` (from runtime, NEVER ask user), `{{user.*}}` (interactive collect), `{{output.*}}` (from API response)

### Standard 3: Explicit Actionable Steps (步骤明确可执行)
- Every operation: Pre-flight → Execute → Validate → Recover
- Steps are numbered, imperative, specific — not descriptive summaries
- CLI and SDK paths documented separately when both apply

### Standard 4: Complete Failure Strategies (失败策略完备)
- Error taxonomy with product-specific error codes (≥ 10)
- Each error pattern: max retries, backoff strategy, agent action, UX feedback
- HALT vs retry distinction; credential, quota, and business errors clearly separated

### Standard 5: Absolute Single Responsibility (职责绝对单一)
- One skill = one product = one primary resource model
- Cross-product delegation: document in Trigger & Scope, do NOT duplicate full flows
- Naming: `alicloud-[product]-ops` (lowercase, hyphenated)

---

## Post-Generation Self-Check (生成后自检 — 宪章执行)

> **机制：生成完成后自动执行，不符合则循环修复直到通过。**
> **参考：** `references/governance-and-adversarial-review.md` §0 Charter

### Self-Check Flowchart

```
生成完成 → 执行宪章检查 (C1-C5)
  ↓
C1-C6 全通过？
  ↓ YES          ↓ NO
报告成功    → HALT + 报告违规项
  ↓              ↓
结束        → 自动修复（填充模板内容）
                 ↓
              → 重新执行宪章检查
                 ↓
              → 循环直到通过
```

### Charter Compliance Checklist (强制执行)

| # | Check | Command | Pass Criteria | Auto-Fix Template |
|---|-------|---------|--------------|-------------------|
| C1 | Frontmatter | `head -3 SKILL.md | grep "^---"` | Starts with `---`, has `name`, `description`, `license`, `compatibility`, `metadata` | Use `alicloud-skill-template.md` frontmatter |
| C2 | SHOULD/SHOULD NOT | `grep -c "SHOULD Use" SKILL.md` | ≥ 1 match for each | Add Trigger & Scope section from template |
| C3 | Five Core Standards | `grep -c "Five Core Standards" SKILL.md` | ≥ 1 match | Add Five Core Standards table from template |
| C4 | Well-Architected | `grep -c "Well-Architected Framework" SKILL.md` | ≥ 1 match | Add Well-Architected Framework table |
| C5 | Variables | `grep -c "^## Variables" SKILL.md` | ≥ 1 match | Add Variables section with `{{env.*}}`/`{{user.*}}`/`{{output.*}}` |
| **C6** | **Token Efficiency** | See §Token Efficiency Requirements in meta-skill | All 6 TE rules applied | Fix per TE guidelines below |

### Self-Remediation Template (自动修复模板)

当检测到违规时，使用以下模板内容自动填充：

```yaml
# C1: Frontmatter template (填充到文件开头)
---
name: alicloud-[product]-ops
description: >-
  Use when the user needs to [trigger description]...
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`), Go 1.21+ runtime...
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "YYYY-MM-DD"
  runtime: Harness AI Agent, Claude Code, Cursor...
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "[API version — doc link]"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    [CLI operation evidence]
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---
```

```markdown
# C2-C5: Missing sections (填充到 Overview 之后)

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When
- [Product triggers — match template format]

### SHOULD NOT Use This Skill When
- [Negative cases → delegate to other skills]

## Variables

| Variable | Source | Description | Example |
|----------|--------|-------------|---------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Environment | Alibaba Cloud AK | `LTAI...` |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Environment | Alibaba Cloud SK | `***` (masked) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Environment | Region code | `cn-hangzhou` |
| `{{user.*}}` | User | [interactive placeholders] | ... |
| `{{output.*}}` | API Response | [response capture] | ... |
```

> **原则：自解优先于人工介入。Agent 必须在报告问题前尝试自动修复。**

---

## Anti-Pattern Checklist

Before and during generation, check against these common anti-patterns:

| # | Anti-Pattern | How It Manifests | Correction |
|---|-------------|-----------------|------------|
| 1 | **Skill = Prompt** | Writing conversational instructions instead of executable steps | Use imperative numbered steps; define I/O; separate triggers from execution |
| 2 | **Skill = Human Doc** | Explaining concepts instead of instructing the agent | Use model-parsable structured language; define behavior boundaries |
| 3 | **Feature Bundling** | One skill tries to do everything (create + monitor + backup + billing) | Split into single-responsibility skills; delegate to existing skills |
| 4 | **API Hallucination** | Inventing field names, JSON paths, or CLI flags not in official docs | Cross-reference every field against OpenAPI or verified CLI output |
| 5 | **Credential Leaking** | Printing, logging, or echoing secret values in any execution path | Mask all credentials with `***` / `<masked>`; check existence only |
| 6 | **No Safety Gate** | Destructive operations (delete, stop, release) without explicit confirmation | Add confirmation step before every destructive path (CLI + SDK) |
| 7 | **Hardcoded Values** | Regions, timeouts, or limits baked into instructions | Use `{{env.*}}` / `{{user.*}}` placeholders; document defaults separately |
| 8 | **Missing Failure Path** | Only documenting the success path; no error handling | Add failure recovery table with error codes, retry logic, HALT conditions |
| 9 | **Over-Engineering** | Adding advanced features before core flow works | Follow evaluation-driven approach: start minimal, expand step by step |
| 10 | **Redundant Redundancy** | Repeating the same info across SKILL.md and references | SKILL.md is entry point; references provide depth — no duplication |

---

## Token Efficiency Requirements (P0 — 强制)

> 目标：在保持 Agent 可执行性的前提下，最小化每个生成技能的 Token 消耗。

### TE-1: 用 API 查询替代硬编码静态数据
```markdown
# ❌ BAD: 硬编码引擎版本/配额表（50+ 行）
| Engine | Port |
|--------|------|
| MySQL | 3306 |
| PostgreSQL | 5432 |

# ✅ GOOD: 用 API 可查 + 精简表
## Supported Engines (Use API for latest)
aliyun [product] Describe[EngineVersions]
| Engine | Port |
|--------|------|
| MySQL | 3306 |
| PostgreSQL | 5432 |
```
**预计算约**: ~200-500 Token

### TE-2: 省略不必要的文档说明
Alibaba Cloud 使用 Go SDK，用 `#` 注释代替函数级 docstring：
```go
// ❌ BAD
func createResource(client *ecs.Client) (*ecs.CreateInstanceResponse, error) {
    /* Create a new ECS instance with specified parameters.
     * Args: client - ECS client
     * Returns: response - instance details
     */
}

// ✅ GOOD: inline comment only
func createResource(client *ecs.Client) (*ecs.CreateInstanceResponse, error) {
    // Create instance with required params from OpenAPI
}
```
**预计算约**: ~100-200 Token/函数

### TE-3: 错误表 → 紧凑格式
```markdown
# ❌ BAD: 每个错误 8-15 行描述
#### InvalidParameter
Cause: ...
Resolution: ...

# ✅ GOOD: 紧凑表格，每行 1 个错误
| Error Code | Agent Action |
|------------|-------------|
| InvalidParameter | FIX — align with OpenAPI |
| QuotaExceeded | HALT — request increase |
```
**预计算约**: ~300-500 Token/文件

### TE-4: JSON paths 集中声明（不重复）
```markdown
# ❌ BAD: 每个操作后单独列 JSON paths
## Create
JSON path: $.ResourceId
## Describe
JSON path: $.Status

# ✅ GOOD: 文件顶部集中声明
# Common JSON Paths:
# Create: $.ResourceId
# Describe: $.{Status,ResourceId,RegionId}
```
**预计算约**: ~50-100 Token/文件

### TE-5: YAML anchors 消除重复字段
```yaml
# ❌ BAD: Dev/Prod 各写 15 行重复字段
# ✅ GOOD: 共享 anchors
x-prod: &prod
  region: "cn-hangzhou"
  zone_id: "cn-hangzhou-f"
  internet_charge_type: "PayByTraffic"

instance:
  <<: *prod
  instance_name: "prod-web-01"
```
**预计算约**: ~200-400 Token/文件

### TE-6: 消除跨文件重复流程
- SKILL.md 已有完整 Pre-flight → Execute → Validate → Recover
- `assets/example-config.yaml` 中的完整流程示例和 SDK 文件中的 Complete Setup 函数是重复内容 → 删除

### TE 边界 — 不可压缩的内容
| 可压缩 | 不可压缩 |
|--------|---------|
| DocStrings、静态表格、重复流程 | Agent 可执行命令本身（参数、JSON paths） |
| 长篇架构描述 | 错误恢复逻辑、安全门、Credential 规则 |
| 多个示例变体（保留 1-2 个核心） | 跨技能编排链、AIOps/Well-Architected 场景定义 |

---

## Evaluation-Driven Generation Workflow

This workflow follows the **"fail first, evaluate first"** principle: define what "good" looks like before generating. At each critical node, validate the output and loop back for corrections.

> **Copy the checklist below before starting, and mark each step as you complete it.**

### Workflow Checklist

```
[ ] Step 1: Define Evaluation Targets — What does success look like?
[ ] Step 2: Analyze Sources — Extract operations, fields, errors from OpenAPI
    ↓ [Feedback Loop: Sources complete? If gaps found → research, then return]
[ ] Step 3: Scaffold Layout — Create directory from template
[ ] Step 4: Populate SKILL.md — Fill template with verified data
    ↓ [Feedback Loop: Five core standards satisfied? If not → fix and re-verify]
[ ] Step 5: Fill Reference Files — Complete all references/
    ↓ [Feedback Loop: All files populated? If gaps → fix]
[ ] Step 6: Verify & Review — P0/P1 checklist + adversarial review
    ↓ [Feedback Loop: Any failures? → return to Step 4 or 5; re-verify after fix]
[ ] Step 7: Final Anti-Pattern Check — Run anti-pattern checklist above
```

---

### Step 1: Define Evaluation Targets

Before generating anything, define **3-5 evaluation cases** for the target skill. Each case has a clear PASS/FAIL criterion.

**Template:**
```markdown
| ID | Scenario | Expected Behavior | PASS Condition |
|----|----------|-----------------|----------------|
| E1 | User asks to create a resource with minimal input | Skill prompts for required fields, uses smart defaults for optional | ≤ 2 prompts before execution |
| E2 | User asks to delete a resource | Skill asks for explicit confirmation with resource identifier | Confirmation step present |
| E3 | API returns QuotaExceeded | Skill returns clear error message with remediation steps | Error follows `[ERROR] code → explanation → fix → next step` |
| E4 | User asks about a non-existent resource | Skill checks existence first, returns "not found" with list suggestion | Resource existence check in pre-flight |
| E5 | User asks for a related product operation (e.g., VPC when using ECS) | Skill delegates to the correct skill or documents the limitation | Delegation rule present in Trigger & Scope |
| E6 | Backup before destructive operation | Skill reminds user to backup or validates existing backup | Pre-backup reminder in Delete/Modify flows |
| E7 | Cost optimization suggestion | Skill detects idle resource pattern and recommends right-sizing | Cost assessment section present in skill |
| E8 | Well-Architected security check | Skill documents minimum RAM permissions for operations | IAM section in `well-architected-assessment.md` |
```

**Purpose:** These cases anchor the generation process. Every feature in the generated skill must trace back to at least one evaluation case.

---

### Step 2: Analyze Sources

Extract from OpenAPI and official docs:

- **Operations**: OperationIds grouped by resource tag
- **Parameters**: Required vs optional, types, enums, defaults
- **Response schemas**: JSON paths, terminal states, pagination
- **Error codes**: Product-specific error taxonomy (≥ 10 codes)
- **Async behavior**: Polling intervals, terminal state names
- **CLI coverage**: Which operations `aliyun` supports vs SDK-only
- **API version drift** (updating existing skills): Compare current OpenAPI against `metadata.api_profile`; flag changed signatures, deprecations, new parameters

**Validation checkpoint:** Before proceeding, confirm:
- [ ] All operationIds are real (not invented)
- [ ] JSON paths are from actual response schemas
- [ ] Error codes are documented in OpenAPI or official docs
- [ ] `cli_applicability` is correctly determined (`cli-first` / `dual-path` / `sdk-only` / `cli-only` for read-only skills)
- [ ] API version drift report generated (if updating existing skill)

---

### Step 3: Scaffold Directory Layout

```text
alicloud-[product]-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md              # Required when cli_applicability: cli-first or dual-path
│   ├── troubleshooting.md
│   ├── monitoring.md              # When monitoring in scope
│   ├── integration.md
│   ├── well-architected-assessment.md  # MANDATORY: five-pillar assessment
│   └── idempotency-checklist.md  # When retries/automation required
├── assets/
│   ├── example-config.yaml
│   ├── eval_queries.json         # MANDATORY: trigger accuracy eval queries
│   └── code-snippets/            # MANDATORY when cli_applicability: sdk-only
│       ├── go.mod                # 独立 module，便于单独编译运行
│       ├── main.go               # 公共 Client 工厂
│       ├── <verb>_<resource>.go  # 每个 operation 一个独立 .go 文件
│       └── README.md             # 使用说明
```

Add `references/idempotency-checklist.md` when retries or automation require idempotent behavior.

---

### Step 4: Populate SKILL.md

Base: [alicloud-skill-template.md](references/alicloud-skill-template.md).

Replace all `[Placeholder]` with product-specific content derived from Step 2. Every field, JSON path, and CLI command MUST be traceable to OpenAPI or verified CLI output.

**Frontmatter requirements:**
| Field | Rule |
|-------|------|
| `name` | `alicloud-[product]-ops` — lowercase, hyphens, ≤ 64 chars |
| `description` | Third person, triggers only (per OpenSpec) |
| `cli_applicability` | `cli-first` (CLI covers most APIs, SDK for edges), `dual-path` (both paths required per operation), `sdk-only` (JIT Go SDK only), or `cli-only` (read-only/discovery skills) |
| `cli_support_evidence` | Cite confirmation via `aliyun help <product>` or official docs |

**Validation checkpoint (Five Core Standards):**
- [ ] **Boundary**: SHOULD/SHOULD NOT use conditions complete?
- [ ] **I/O**: All placeholders (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) correctly typed?
- [ ] **Steps**: Every operation has Pre-flight → Execute → Validate → Recover?
- [ ] **Failure**: Error taxonomy ≥ 10 codes, each with recovery action?
- [ ] **Single Responsibility**: One product, one resource model, clear delegation?

**If any standard fails → FIX before proceeding to Step 5.**

---

### Step 5: Fill Reference Files

| File | Content | Source |
|------|---------|--------|
| `core-concepts.md` | Architecture, limits, regions, quotas, resource relationships | Official docs |
| `api-sdk-usage.md` | Operation map, required fields, pagination, request/response snippets | OpenAPI |
| `cli-usage.md` | `aliyun` command map, coverage gap table, JSON output paths | Verified CLI output |
| `troubleshooting.md` | Error code table, ordered diagnostic steps, product-specific patterns | OpenAPI + experience |
| `monitoring.md` | Metrics, dashboards, alarms, anomaly patterns | CMS docs |
| `integration.md` | Go bootstrap, JIT SDK setup, dependency config | Execution environment |

**Validation checkpoint:** All reference files populated with real content (not template placeholders)?

---

### Step 5.5: Generate Code Snippets (when `sdk-only`)

> **触发条件：** `cli_applicability: sdk-only`（CLI 不暴露该 product，或暴露但不足以覆盖完整功能）
> **模板：** [templates/code-snippets.md](templates/code-snippets.md)
> **输出位置：** `assets/code-snippets/`

**为什么需要这一步：**
当 CLI 不能完整覆盖 product 操作时，Agent 在沙箱里需要 **直接可执行** 的 Go SDK 脚本。
把代码片段沉淀到 `assets/code-snippets/`，而不是让 Agent 每次现编，可以：

1. **稳定性** — 同一份代码反复使用，结构一致、参数正确
2. **可审计** — 评审 PR 时可以 review 这批 snippet 而非散落在对话中的一次性脚本
3. **可复用** — 用户可独立 `go run` 触发，无需走完整 SKILL.md 流程

**生成步骤：**

1. **解析 OpenAPI** 提取 `operations[]`，对每个 Operation 确定：
   `OperationId` / SDK `<RequestType>` / `<MethodName>` / 必填参数 / Response 关键 JSON path
2. **创建 `assets/code-snippets/`**：
   - `go.mod` — 独立 module，依赖 `darabonba-openapi` / `tea` / `<product-package>/<version>`（版本必须与 `references/integration.md` 一致）
   - `main.go` — 公共 `NewClient(endpoint) (*client.Client, error)` 工厂，从 `os.Getenv` 读 AK/SK，**禁止任何 SK 回显**
3. **遍历 `operations[]` 生成 `<verb>_<resource>.go`**：
   - 命名：小写 + 下划线，动词对齐 OpenAPI（Create/Describe/Modify/Delete/List/Get/Start/Stop/Restart/Upgrade）
   - 头部注释：`<OperationId>` / SDK Method / `CLI Support: sdk-only` / OpenAPI doc URL
   - Request 构造：必填参数 + 1-2 个常用可选参数
   - 末尾注释：列出关键输出 JSON path（如 `// $.DBInstanceId -> 新建实例 ID`）
4. **生成 `README.md`**：前置条件（Go 版本 + 3 个环境变量）+ Snippet 列表 + 运行示例 + 安全约束
5. **验证（沙箱可用时强制）**：
   ```bash
   cd assets/code-snippets
   go mod tidy && go vet ./...
   ```
   - 失败 → 修复 `go.mod` 版本号或 import 路径，重试
   - 成功 → 在 `SKILL.md` Reference Directory 添加 `assets/code-snippets/README.md` 链接

**关键约束（违反即 P0 失败）：**
- ❌ `cli-first` / `dual-path` skill 也生成 snippets → ✅ 仅 `sdk-only` 触发
- ❌ 多 operation 挤在一个 `main.go` → ✅ 每 operation 一独立 `.go`
- ❌ snippet 硬编码 AK/SK 或在日志打印 SK → ✅ 始终 `os.Getenv` + 禁止 SK 回显
- ❌ snippet 缺少 `go.mod` → ✅ 必须有独立 module 便于 `go run`

---

### Step 6: Verify & Review

Run the [P0/P1 Checklist](#p0--must-pass) below against the generated skill. Run the [Adversarial Review](references/governance-and-adversarial-review.md) scenarios (when present).

**For any failure:**
1. Identify the gap
2. Return to Step 4 (SKILL.md) or Step 5 (references)
3. Fix the gap
4. Re-verify the full checklist

**Re-verify after fixes — do not skip re-runs.**

---

### Step 7: Final Anti-Pattern Check

Run the [Anti-Pattern Checklist](#anti-pattern-checklist) above against the generated skill. Every item must pass.

**If an anti-pattern is detected:**
- Document the instance
- Fix according to the "Correction" column
- Re-run the P0/P1 checklist

---

## Description Optimization (Trigger Accuracy)

The `description` field in frontmatter is the sole trigger mechanism for skill activation. An under-specified description means the skill won't load when it should; an over-broad one means it loads when it shouldn't. Optimize it systematically:

### Write an Effective Description

Follow these principles from the [agentskills.io specification](https://agentskills.io/skill-creation/optimizing-descriptions):

| Principle | Guideline | Example |
|-----------|-----------|---------|
| **Imperative phrasing** | Frame as instruction to agent: "Use when..." | `Use when the user needs to...` |
| **Focus on user intent** | Describe what user is trying to achieve, not skill mechanics | Focus on problems user solves, not CLI/SDK internals |
| **Err on the side of pushy** | Include implicit trigger scenarios explicitly | `even when the user doesn't explicitly mention [product]` |
| **Negative boundaries** | State what the skill is NOT for | `Not for billing, RAM, or related products` |
| **Keep concise** | Under 1024 character hard limit | Aim for 300–700 characters |

### Create Eval Queries

Create an `assets/eval_queries.json` file with ~20 queries (10 should-trigger, 10 should-not-trigger):

```json
[
  { "query": "I need to create an [product] instance", "should_trigger": true },
  { "query": "Check my account bill", "should_trigger": false }
}
```

**Query design tips:**
- **Should-trigger**: Vary phrasing (formal/casual/typos), explicitness (names product vs describes need), detail level (terse vs context-heavy)
- **Should-not-trigger**: Focus on **near-misses** — queries sharing keywords but needing different skills (e.g., "Create an ECS instance" for a generator skill — shares "create" and "ECS" but is operational, not skill generation)
- **Realism**: Include file paths (`~/Downloads/`), personal context (`"my manager asked..."`), casual language, abbreviations

### Optimization Loop

1. **Evaluate**: Run each query through the agent with the skill installed; compute trigger rate (fraction of runs where skill was invoked)
2. **Identify failures**: Which should-trigger queries didn't trigger? Which should-not-trigger did?
3. **Revise**: If too narrow — broaden scope or add trigger context. If too broad — add specificity or negative boundaries. Avoid adding specific keywords from failed queries (overfitting).
4. **Repeat**: 5 iterations max. Use a 60/40 train/validation split to avoid overfitting.

### Apply the Result

- Update `description` in SKILL.md frontmatter
- Verify under 1024 characters
- Test with 5–10 fresh queries as sanity check
- See `assets/eval_queries.json` for the meta-skill's own eval queries

---

## Before You Generate: Decisions

### Extend vs New Directory
- **Extend** same product and resource model (new operation section, paths, troubleshooting rows)
- **New** `alicloud-[product]-ops` when the **service/API surface** or **primary resource** is distinct

### Naming
- Pattern: `alicloud-[product]-ops` (lowercase, hyphenated)
- Search the repo for collisions before creating

### Dependencies
- Cross-product chains: document **delegation** in Trigger & Scope
- Avoid duplicating another product's full flows

### Sources of Truth
- **OpenAPI + official docs** beat forums and chat logs
- Pin an API/SDK profile in skill `metadata` or `references/integration.md`

### Secrets
- Only `{{env.*}}` **names** and documentation; never real keys or customer data
- Credential masking is MANDATORY — see [references/execution-environment.md](references/execution-environment.md#credential-security)

### CLI-First with JIT Go SDK Fallback
- Primary path: `aliyun` CLI (static Go binary, covers 90%+ APIs)
- Fallback path: JIT Go SDK (dynamic script + `go run`)
- Execution environment details: [references/execution-environment.md](references/execution-environment.md)

---

## Governance (Expert Recommendation)

**Minimal adversarial review** gives high return for low cost: it catches destructive-action shortcuts, credential leaks in instructions, and API hallucination **before** merge. Treat [governance-and-adversarial-review.md](references/governance-and-adversarial-review.md) (when present) as the **reviewer companion** to this meta-skill.

Optional later improvements: PR template checkbox linking to that doc; periodic check that CLI-documented skills stay aligned with OpenAPI when APIs change.

---

## Agent-Ready Quality Checklist

### P0 — MUST PASS

- [ ] **Trigger & Scope** with SHOULD-use / SHOULD-NOT-use and delegation rules
- [ ] **Variables:** `{{env.*}}` vs `{{user.*}}`; no secret literals; `{{env.*}}` never collected from user
- [ ] **Flows:** Pre-flight → Execute → Validate → Recover for **each** critical operation
- [ ] **Each flow** documents the correct primary path per `cli_applicability` (`cli-first`/`dual-path` → `aliyun` primary + SDK fallback; `sdk-only` → SDK only; `cli-only` → CLI read-only)
- [ ] **Failure recovery:** HALT vs retry; throttling with exponential backoff; non-retryable business errors (QuotaExceeded, InsufficientBalance, InvalidParameter)
- [ ] **API fidelity:** Fields and paths traceable to OpenAPI/SDK for the stated version
- [ ] **CLI fidelity:** Default output is JSON (NO `--output json` needed); `--output` used for JMESPath columns only; commands match official CLI docs; JSON paths verified with a real CLI run or official docs
- [ ] **Safety gates** for destructive operations (before **each** documented path: `aliyun` **and** SDK fallback)
- [ ] **Timeouts** for polling and long-running operations (default: 5s interval, 300s max wait)
- [ ] **[TE] Token Efficiency applied** — see §Token Efficiency Requirements below
- [ ] **Self-Healing Framework:** All installation flows follow [enhanced-self-healing-framework.md](references/enhanced-self-healing-framework.md) with pre-flight checks, error classification, multi-path recovery, health verification, and graceful degradation
- [ ] **Self-Healing Coverage:** CLI install, Go runtime JIT, dependency download all have ≥ 3 self-healing paths per error type (network, permission, resource, configuration)
- [ ] **Self-Healing Metrics:** Health score ≥ 8/10, self-healing duration < 30s, user intervention rate < 20% documented as success criteria
- [ ] **UX Onboarding:** Quick Start section present; first-time user can execute first command within 60 seconds per [user-experience-spec.md](references/user-experience-spec.md) Section 2.1
- [ ] **UX Interaction:** Common operations require ≤ 3 prompts; smart defaults documented; destructive operations have explicit confirmation per [user-experience-spec.md](references/user-experience-spec.md) Section 3
- [ ] **UX Feedback:** Success/failure messages follow standardized format; progress shown for operations > 5s per [user-experience-spec.md](references/user-experience-spec.md) Section 4
- [ ] **UX Error Handling:** Error messages follow `[ERROR] code: summary → explanation → fix → next step` format per [user-experience-spec.md](references/user-experience-spec.md) Section 5
- [ ] **Prompt Library Alignment:** Generation process uses structured prompts from [prompt-library.md](references/prompt-library.md) with effectiveness tracking where applicable
- [ ] **Description Optimization:** Generated skill's `description` field follows agentskills.io optimization principles — imperative phrasing, user-intent focused, implicit trigger scenarios, negative boundaries, under 1024 chars
- [ ] **Eval Queries:** `assets/eval_queries.json` created or updated with should-trigger/should-not-trigger queries for the generated skill
- [ ] **Code Snippets (when `sdk-only`):** `assets/code-snippets/` contains `go.mod` + `main.go` (Client factory) + one `<verb>_<resource>.go` per operation + `README.md`; no hardcoded credentials; no SK echo; snippets pass `go vet ./...` per [templates/code-snippets.md](templates/code-snippets.md)
- [ ] **Optimization Awareness:** Skill design considers Fault Diagnosis, Root Cause Localization, and Rapid Resolution dimensions per [optimization-analysis.md](references/optimization-analysis.md)
- [ ] **AIOps Compliance (when skill involves monitoring/alarm/diagnosis):** Skill implements multi-metric correlation, cross-skill diagnosis decision tree, delegation matrix, proactive inspection, and alarm storm handling per [aiops-best-practices.md](references/aiops-best-practices.md)
- [ ] **Well-Architected — Security Pillar:** Minimum RAM permissions documented; credential masking enforced; VPC endpoint recommendation present per [well-architected-assessment.md](references/well-architected-assessment.md) §2.1
- [ ] **Well-Architected — Stability Pillar:** Backup/recovery operations documented with RTO/RPO; DR runbook included; explicit confirmation on all destructive operations per [well-architected-assessment.md](references/well-architected-assessment.md) §2.2
- [ ] **Well-Architected — Cost Pillar:** Billing model comparison table present; idle resource detection pattern documented per [well-architected-assessment.md](references/well-architected-assessment.md) §2.3
- [ ] **Well-Architected — Performance Pillar:** Key performance metrics with thresholds documented; auto-scaling trigger table present per [well-architected-assessment.md](references/well-architected-assessment.md) §2.5
- [ ] **Well-Architected Reference:** SKILL.md links to `well-architected-assessment.md` for pillar-specific assessment patterns

- [ ] **[GCL] Rubric present (when `required` or `recommended` per `AGENTS.md` §12.8):** `references/rubric.md` exists with 5 core dimensions + 3 Aliyun-specific extensions, per-op Safety sub-rules table (≥ 3 sub-rules per destructive op), detection regex list (≥ 5 patterns for data-plane skills), ≥ 2 worked examples (one PASS, one SAFETY_FAIL), and changelog with 1.0.0 entry per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §4
- [ ] **[GCL] Prompt templates present (when `required` or `recommended`):** `references/prompt-templates.md` exists with Generator template (hard rules list referencing rubric's per-op sub-rules) AND Critic template (independent re-query pattern, regex application, **Critic MUST NOT see `{{user.request}}`** for rubber-stamping prevention per `AGENTS.md` §12.2) per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §5
- [ ] **[GCL] Quality Gate section in SKILL.md (when `required` or `recommended`):** `## Quality Gate (GCL)` section inserted between `## Operational Best Practices` and `## See Also — Meta-Skill Rules`, with classification table (Required? / `max_iter` / Most-scrutinized ops), `Changelog` line at 1.0.0, and links to both `references/rubric.md` AND `references/prompt-templates.md` per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §6
- [ ] **[GCL] Cross-skill delegation documented (when skill touches other products):** Generator template hard rules list explicit delegation to other skills' GCL rules (e.g. VPC → `alicloud-eip-ops` for EIP ops; NAT → `alicloud-eip-ops`; PolarDB → `alicloud-rds-ops` for shared SQL WHERE-clause) per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §7

### P1 — SHOULD PASS

- [ ] **Chaining:** Stable output fields for downstream skills (via `{{output.*}}` placeholders)
- [ ] **Naming:** `alicloud-[product]-ops` consistent with repo conventions
- [ ] **Pinned** SDK/API baseline where drift matters (in metadata or integration.md)
- [ ] **Idempotency** or duplicate-resource behavior documented when automation or retries apply
- [ ] **Adversarial scenarios** considered using the governance doc (when present)
- [ ] **Path preference:** SKILL.md states when to prefer `aliyun` vs SDK fallback if non-obvious
- [ ] **Metadata:** Ops skill frontmatter includes `cli_applicability`, `cli_support_evidence`, `go_version_minimum`, `environment` vars
- [ ] **Well-Architected — Multi-AZ:** Cross-AZ/region deployment recommendation present per [well-architected-assessment.md](references/well-architected-assessment.md) §2.2.1
- [ ] **Well-Architected — Right-Sizing:** Resource utilization → recommendation mapping documented per [well-architected-assessment.md](references/well-architected-assessment.md) §2.3.2
- [ ] **Well-Architected — Batch:** Batch operation pattern documented for ≥ 3 resources per [well-architected-assessment.md](references/well-architected-assessment.md) §2.4.1

- [ ] **[GCL] Frontmatter coherence on GCL rollout:** When GCL files are added/modified, `version` (minor or patch bump) AND `last_updated` are updated in the SAME commit; `rubric_version` in `references/rubric.md` frontmatter matches `1.0.0` for the first rollout per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §6.2
- [ ] **[GCL] Classification matches destructive surface:** Skill's GCL classification (`required` / `recommended` / `optional`) matches `AGENTS.md` §12.8 defaults OR provides explicit justification for any deviation; if the new skill has a `Delete*` / `Drop*` / `FLUSHALL*` / `ScheduleKeyDeletion*` op, it MUST be classified as `required` per [gcl-rollout-spec.md](references/gcl-rollout-spec.md) §2

---

## Example Request

> Add an Alibaba Cloud skill for ECS in this repo: instances, disks, snapshots. Docs: `https://help.aliyun.com/zh/ecs`. OpenAPI: [https://help.aliyun.com/zh/ecs/developer-reference/api-ecs-2014-05-26-overview](https://help.aliyun.com/zh/ecs/developer-reference/api-ecs-2014-05-26-overview). Go SDK (JIT fallback).

**Expected output:** `alicloud-ecs-ops` tree with **real** operationIds, Go SDK types, response paths, **and** matching `aliyun` commands (primary path), plus JIT Go SDK fallback documentation.

---

## Reference Directory

| File | Purpose |
|------|---------|
| [alicloud-skill-template.md](references/alicloud-skill-template.md) | Base template for generated SKILL.md |
| [execution-environment.md](references/execution-environment.md) | CLI install, Go JIT download, credential config, verification **(progressive disclosure)** |
| [cli-behavior.md](references/cli-behavior.md) | Verified `aliyun` CLI behavioral notes (output format, env vars, patterns) **(progressive disclosure)** |
| [enhanced-self-healing-framework.md](references/enhanced-self-healing-framework.md) | **MANDATORY** self-healing patterns for installation flows |
| [governance-and-adversarial-review.md](references/governance-and-adversarial-review.md) | (when present) Adversarial review scenarios and governance checklist |
| [prompt-library.md](references/prompt-library.md) | Structured prompts for the generation lifecycle |
| [optimization-analysis.md](references/optimization-analysis.md) | Three-dimensional optimization framework |
| [user-experience-spec.md](references/user-experience-spec.md) | Mandatory UX requirements for all generated skills |
| [aiops-best-practices.md](references/aiops-best-practices.md) | Mandatory AIOps patterns for monitoring/diagnosis skills |
| [gcl-rollout-spec.md](references/gcl-rollout-spec.md) | **NEW** Generator-Critic-Loop (GCL) rollout playbook — how to generate `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section in SKILL.md for a new `alicloud-*-ops` skill; covers `required` / `recommended` / `optional` classification, per-op Safety sub-rule format, regex hot-spot detection, cross-skill delegation, and SLB worked example. Mandatory reference for any new or updated `required` / `recommended` skill per `AGENTS.md` §12. |
| [gcl-orchestrator-agent.md](references/gcl-orchestrator-agent.md) | **NEW** `pi-subagents` custom agent definition (`gcl-orchestrator`) that wraps `scripts/gcl_runner.py` for the parent pi session. Install by copying the spec to `.pi/agents/gcl-orchestrator.md` (project scope) or `~/.pi/agent/agents/gcl-orchestrator.md` (user scope). `context: fork` future-proofs for Phase 3 LLM-based Critic. |
| [gcl-actiontrail-crosscheck-spec.md](references/gcl-actiontrail-crosscheck-spec.md) | **NEW** GCL ↔ ActionTrail cross-check spec (Phase 3-C). For each `gcl-trace-*.json`, an independent `LookupEvents` call verifies the op actually happened in the cloud; catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY` findings. Companion to `scripts/gcl_actiontrail_crosscheck.py`. |
| [well-architected-assessment.md](references/well-architected-assessment.md) | **NEW** Alibaba Cloud Well-Architected Framework five-pillar assessment integration |
| [assets/eval_queries.json](assets/eval_queries.json) | Eval queries for testing the meta-skill's description trigger accuracy |
| [templates/code-snippets.md](templates/code-snippets.md) | **sdk-only skill 专用** — `assets/code-snippets/` 目录结构、Client 工厂、operation 模板、go.mod/README 模板、生成流程与反模式 |

### External References

- [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud SDK for Go](https://github.com/alibabacloud-go)
- [Agent Skills Open Specification](https://agentskills.io/specification)