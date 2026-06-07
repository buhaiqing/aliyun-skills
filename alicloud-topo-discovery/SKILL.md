---
name: alicloud-topo-discovery
description: >-
  Use this skill to automatically discover and generate Alibaba Cloud network topology and resource inventory reports,
  and export cloud resources as Terraform HCL for declarative infrastructure archives.
  Triggers when the user asks to "scan network resources", "generate topology map", "inventory VPC resources",
  "check cloud resources", or "audit network structure", as well as "export as terraform", "create baseline snapshots",
  "generate HCL", or "audit infrastructure drift" for a specific Alibaba Cloud account.
  Supports both summary (brief) and detailed inventory modes, plus on-demand HCL export and periodic baseline management.
  Keywords: 网络拓扑, 资源清单, VPC 探测, 云资源扫描, 网络审计, Terraform HCL 导出, 基础设施基线,
  配置漂移检测, network topology, resource inventory, VPC scan, terraform export, infra baseline, drift detection.
  Do NOT use for resource creation, modification, deletion, or troubleshooting. Read-only discovery only.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), valid API credentials,
  network access to Alibaba Cloud endpoints. Read-only operations (Describe/List/Get) strictly enforced.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  type: cross-product-discovery
  cli_applicability: cli-only
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Network Topology Discovery Skill

## 🔒 READ-ONLY PRINCIPLE (不可打破)

本 Skill 的核心设计原则是 **Absolute Read-Only**。在执行任何操作前，Agent 必须遵守以下红线：

| 规则 | 说明 |
|------|------|
| **NO Write Operations** | 绝不执行任何 `Create`, `Update`, `Modify`, `Delete`, `Associate`, `Unassociate`, `Authorize`, `Revoke` 操作 |
| **NO State Changes** | 绝不改变任何云资源的状态，包括但不限于实例开关机、安全组规则增删、EIP 绑定等 |
| **NO Credential Exposure** | 绝不输出完整的 AK/Secret，输出中必须掩码为 `AKID******SKRET` 或 `***` |
| **Read-Only API Only** | 仅允许调用 `Describe*`, `List*`, `Get*` 类 API（详见 [安全门规范](references/safety-gate.md)） |

**违反此原则 = 严重安全违规，立即 HALT 并向用户报告。**

## Overview

`alicloud-topo-discovery` 是一个 **跨产品网络发现工具**，用于自动化扫描阿里云账户下的 VPC 网络结构、关联资源（ECS/RDS/SLB/NAT/EIP/ACK/安全组），并生成结构化的网络拓扑图和资源清单报告。

### 核心特性

| 特性 | 说明 |
|------|------|
| **交互式模式选择** | 用户可选择"简报"（VPC/SLB/EIP 摘要）或"详细报告"（全资源清单） |
| **树形拓扑视图** | 按参考模板格式输出 VPC → 交换机 → 资源树形结构 |
| **多格式输出** | 支持 ASCII 树形图 + Mermaid 图 + Markdown 报告 |
| **多文档生成** | 可选生成单文件或拆分多文件（topology / inventory / summary） |
| **独立模板引擎** | 基于 `templates/` 下 `.md` 模板文件，支持变量替换和自定义 |
| **声明式安全门** | 执行前强制命令预检，确保无破坏性操作 |

### 与现有 Skill 的关系

| 关系类型 | 说明 |
|---------|------|
| **不替代** | 本 Skill 不替代任何产品级 Skill（如 `alicloud-ecs-ops`, `alicloud-vpc-ops`） |
| **组合调用** | 本 Skill 通过调用各产品 API 的只读接口，实现跨产品拓扑聚合 |
| **发现 vs 操作** | 本 Skill 负责"发现"，产品 Skill 负责"操作"；若用户发现后需要修改资源，应引导至对应产品 Skill |
| **AIOps 集成** | `alicloud-aiops-cruise` 在巡检中调用本 skill 的 `topo-render.py` 渲染拓扑图，并叠加健康状态覆盖层 |

## Trigger & Scope

### SHOULD Use This Skill When

- User 需要查看/扫描/探测/审计阿里云网络拓扑
- User 需要获取 VPC 下的资源清单/资产列表
- User 需要了解账号下有哪些 VPC/EIP/SLB/ECS
- User 需要生成网络架构图/资源报告
- User 需要将云资源导出为 Terraform HCL (`export-hcl`)
- User 需要创建基础设施基线快照 (`baseline`)
- User 需要比较两次基线间的配置变更 (`baseline-diff`)
- User 需要跨账号扫描资源 (使用 `--assume-role`)
- Keywords: 网络拓扑, VPC 结构, 资源清单, 云资源扫描, Terraform HCL 导出, 基础设施基线
- User 说"扫描一下网络", "看看有哪些资源", "生成拓扑图", "导出 HCL", "创建 baseline"

### SHOULD NOT Use This Skill When

- User 需要创建/修改/删除资源 → 引导至对应产品 Skill
- User 需要排查资源故障/性能问题 → 引导至监控/诊断 Skill
- User 需要查询账单/费用 → 引导至计费 Skill
- User 需要配置安全策略 → 引导至安全相关 Skill
- User 需要通过 `terraform apply` 创建云资源 → 引导至 `alicloud-terraform-ops` (待实现)

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | N/A | 只读操作，不触发 GCL 质量门禁 |

## Quality Gate (GCL)

本 Skill 遵循 AGENTS.md §12 Generator-Critic-Loop 质量门。

### Rubric Dimensions

见 [references/gcl-rubric.md](references/gcl-rubric.md)。

| 维度 | 权重 | 说明 |
|---|---|---|
| **Correctness** | 25% | 拓扑关系和资源清单与实际情况一致 |
| **Safety** | 30% | 纯读操作，任何写操作为 0 |
| **Idempotency** | 15% | 同一输入多次扫描结果一致 |
| **Traceability** | 20% | 报告含完整执行上下文（命令、参数、输出路径） |
| **Spec Compliance** | 10% | 遵循 manifest-schema 和字段映射规范 |

### Sub-Mode Rubric

| Sub-Mode | Correctness 侧重点 | Safety 检查点 |
|----------|-------------------|---------------|
| scan-topo | 输出格式完整、拓扑关系准确 | 只读门禁 |
| export-hcl | 字段映射精度 | 无敏感泄露 |
| baseline | 目录结构完整 | 无数据删除 |
| baseline-diff | Diff 准确度 | 只读 Diff |

### GCL Prompt

Generator → Critic 循环详见 [references/gcl-rubric.md](references/gcl-rubric.md)，遵循 AGENTS.md §12 的标准流程。

## Pre-flight Interaction (用户决策)

在执行扫描前，**必须** 向用户确认以下选项：

```
📋 拓扑扫描配置：

1. 报告模式 (必需):
   [1] 简报版 —— VPC + VSwitch + SLB/EIP + 资源数量统计 (默认)
   [2] 详细版 —— 简报 + 所有 ECS/RDS/ACK/安全组的完整属性和清单

2. 拓扑格式:
   [1] ASCII 树形图 —— 终端友好，直接可读 (默认)
   [2] Mermaid 图 —— 支持流程/渲染，适合文档嵌入
   [3] 两者都要

3. 输出结构:
   [1] 单文件 —— 所有内容写入 report.md (默认)
   [2] 多文件 —— topology.md + inventory.md + summary.md 拆分

4. 项目名称/标识 (可选):
   [输入]: 自定义报告标题前缀 (默认自动从 VPC 名称提取)

5. 输出格式 (可选):
   [a] ASCII 树形图 —— 终端友好 (默认)
   [b] Mermaid 图 —— 可视化拓扑
   [c] 两者都要 (推荐)

6. 健康状态叠加 (可选，与 `alicloud-aiops-cruise` 联动):
   [输入]: 巡检 JSON 报告路径 (自动叠加健康状态到拓扑中)

请回复选项编号或描述，确认后开始扫描。
```

## Variable Convention

| Placeholder | Meaning | Source |
|-------------|---------|--------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | AK ID | From runtime env, NEVER ask user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | AK Secret | From runtime env, NEVER exposed |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Region | From runtime env |
| `{{user.report_mode}}` | 简报/详细 | User decision (step 1) |
| `{{user.topology_format}}` | ASCII/Mermaid | User decision (step 2) |
| `{{user.output_structure}}` | 单文件/多文件 | User decision (step 3) |
| `{{user.project_name}}` | 项目名 | User input or extracted from VPC name |
| `{{output.topology_data}}` | 扫描结果 | From CLI execution |
| `{{output.vpc_name}}` | VPC 名称 | From DescribeVpcs response |

## Execution Flows

### Phase 1: Pre-flight Safety Check

**MANDATORY before any CLI execution:**

1. Verify credentials exist:
   ```bash
   test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "ERROR: Credentials not set"; exit 1; }
   ```

2. Check CLI available:
   ```bash
   command -v aliyun >/dev/null || { echo "ERROR: aliyun CLI not found"; exit 1; }
   ```

3. Verify read-only mode:
   - Scan the planned command list
   - Reject any command matching: `(Create|Update|Modify|Delete|Associate|Unassociate|Authorize|Revoke|Stop|Start|Reboot|Run|Invoke)`
   - If found → HALT and report to user

4. Test API connectivity (read-only):
   ```bash
   aliyun vpc DescribeRegions --RegionId "$ALIBABA_CLOUD_REGION_ID" >/dev/null 2>&1 || { echo "ERROR: API check failed"; exit 1; }
   ```

#### 📊 输出格式 (Token 效率优化)

所有 CLI 命令的 JSON 输出必须用 `jq` 过滤到最小必要字段，避免全量 JSON 输出造成 Token 浪费：

```bash
# 优化前: 输出全量 JSON（可能 100+ 行）
aliyun ecs DescribeInstances --RegionId $REGION_ID

# 优化后: 仅输出 ID + Name + Type + Status
aliyun ecs DescribeInstances --RegionId $REGION_ID \
  | jq '.Instances.Instance[] | {InstanceId, InstanceName, InstanceType, Status}'
```

各 API 的字段过滤规则见 `references/execution-commands.md` 的 JSON 输出路径映射。

### Phase 2: Parallel Data Collection

Execute CLI commands in parallel (background) for speed.

> **注意**：`topo-scan.sh` 中实现了多 VPC 扫描 + 健康状态叠加 + Mermaid 图生成。
> 下面为示意流程，完整实现见 `scripts/topo-scan.sh`。

```bash
# VPC & VSwitch (Foundation) — 先等 VPC 返回再查 VSwitch
aliyun vpc DescribeVpcs --RegionId "$ALIBABA_CLOUD_REGION_ID" > /tmp/topo_vpcs.json &
PID_VPC=$!

# 并行查 SLB/NAT/EIP
aliyun slb DescribeLoadBalancers --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_slbs.json &
aliyun vpc DescribeNatGateways --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 50 > /tmp/topo_nats.json &
aliyun vpc DescribeEipAddresses --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 50 > /tmp/topo_eips.json &

# 等 VPC 返回后查 VSwitch
wait $PID_VPC
FIRST_VPC_ID=$(python3 -c "import json;d=json.load(open('/tmp/topo_vpcs.json'));print(d.get('Vpcs',{}).get('Vpc',[{}])[0].get('VpcId',''))" 2>/dev/null)
if [ -n "$FIRST_VPC_ID" ]; then
  aliyun vpc DescribeVSwitches --RegionId "$ALIBABA_CLOUD_REGION_ID" --VpcId "$FIRST_VPC_ID" --PageSize 50 > /tmp/topo_vswitches.json &
fi

# ECS Instances (Optional for detailed mode)
if [ "$REPORT_MODE" = "detailed" ]; then
  aliyun ecs DescribeInstances --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_ecs.json &
  aliyun ecs DescribeSecurityGroups --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_sgs.json &
  aliyun cs DescribeClustersV1 --page_size 50 > /tmp/topo_ack.json &
  aliyun rds DescribeDBInstances --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_rds.json &
fi

# Wait for remaining background jobs
wait
```

### Phase 3: Topology Generation (Template Rendering)

`topo-render.py` 自动完成：

1. 加载 `/tmp/topo_*.json` 数据
2. 构建 VSwitch → 资源映射（ECS/SLB/RDS 按归属交换机分组）
3. 加载健康状态覆盖层（如果 `--health-json` 传入）
4. 生成输出：
   - **ASCII 树形图**：终端友好，`report.md`
   - **Mermaid 图**：可视化拓扑，支持渲染，`topology.mermaid.md`
5. 写文件到输出目录

> 旧有模板文件 `templates/vpc-topology.md` 保留作参考。完整渲染逻辑由 `topo-render.py` 实现。

### Phase 4: Report Compilation

**Single File Mode:**

支持 **ASCII 树形图 + Mermaid 图** 两种格式，可通过 Pre-flight 选项选择。

- ASCII 树形图：终端友好，直接可读
- Mermaid 图：支持渲染成可视化图表，适合文档嵌入

### Phase 4: Report Compilation

**Single File Mode:**
```markdown
# {{user.project_name}} - 网络拓扑与资源清单

> 生成时间: {{timestamp}}
> 区域: {{env.ALIBABA_CLOUD_REGION_ID}}
> 模式: {{user.report_mode}}

{{topology_output}}

---

{{inventory_output}}

---

{{statistics_output}}
```

**Multi-File Mode:**
- `topology.md`: VPC 树形图 + Mermaid 图
- `inventory.md`: 完整资源清单表
- `summary.md`: 摘要 + 架构分析 + 风险提示

### Phase 5: Post-Execution Verification

1. Verify output file exists and size > 0:
   ```bash
   test -s report.md && echo "Report generated successfully"
   ```

2. Check no credentials leaked:
   ```bash
   grep -E 'LTAI|AKIA|wJalr|SECRET|secret' report.md && { echo "WARNING: Possible credential leak"; exit 1; }
   ```

3. Verify read-only compliance (meta-check, no commands executed):
   - Confirm no write commands were in the execution log

## Failure Recovery

| Error Pattern | Max Retries | Backoff | Agent Action |
|--------------|-------------|---------|--------------|
| `InvalidAccessKeyId` / `InvalidAccessKey.Secret` | 0 | - | HALT. Credentials invalid. User must provide valid AK. |
| `SignatureDoesNotMatch` | 0 | - | HALT. AK/Secret mismatch or time skew. Check credentials. |
| `Forbidden.RAM` | 0 | - | HALT. Insufficient permissions. User needs `AliyunReadOnlyAccess` or custom read-only policy. |
| `Throttling` / 429 | 3 | Exponential | Back off 2s, 4s, 8s. Retry. |
| `InternalError` / 5xx | 3 | 2s fixed | Retry; continue with partial data if persistent. |
| `RegionId.NotExist` | 0 | - | HALT. Check `{{env.ALIBABA_CLOUD_REGION_ID}}`. |
| `InvalidVpcId.NotFound` | 0 | - | Skip VPC, continue scanning. |
| Command Timeout (>30s) | 1 | - | Kill process; log timeout; continue with other resources. |

---

## Well-Architected Assessment (卓越架构)

This skill's operations are evaluated against Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html). Reference this section for security, stability, cost, efficiency, and performance guidance specific to network topology discovery.

### 安全 (Security)

| Area | Guidance |
|------|----------|
| **IAM** | Require: `AliyunReadOnlyAccess` only. Principle: least privilege, read-only access |
| **Credentials** | `{{env.*}}` only. All AK/Secret values in output must be masked (e.g., `LTAI***`) |
| **Data Sensitivity** | VPC IDs, instance IDs, and IP ranges are sensitive infrastructure data. Restrict report distribution |

### 稳定 (Stability)

| Area | Guidance |
|------|----------|
| **面向失败的架构设计** | Skip individual VPCs on error but continue scanning. Partial results are still valuable |
| **面向精细的运维管控** | Regular topology discovery enables change tracking and drift detection |
| **面向风险的应急快恢** | N/A (read-only skill). Use reports as baseline for post-incident infrastructure comparison |

### 成本 (Cost)

This skill uses read-only Describe APIs which are free. Minimal API call volume:
- **Optimization:** Use batch APIs where possible. Set `PageSize` to 50 to minimize calls
- **Waste:** N/A for read-only discovery

### 效率 (Efficiency)

- **Parallel Collection:** ECS/RDS/SLB/VPC APIs can be queried simultaneously
- **CI/CD Integration:** Run in CI pipeline for regular topology drift detection
- **JSON Output:** Compatible with jq for automated analysis

### 性能 (Performance)

| Operation | Expected API Calls | Time Estimate |
|-----------|-------------------|---------------|
| Full scan (all VPCs, multi-region) | ~10-20 Describe calls | < 30s |
| Brief mode | ~5 Describe calls | < 10s |
| + Health overlay | +0 (复用已有数据) | +0s |
| + HCL export | ~10-30 API calls | < 60s |




## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `cli-only`，CLI/SDK 已覆盖，无需 code snippets.
