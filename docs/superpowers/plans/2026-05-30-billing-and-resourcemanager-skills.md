# alicloud-billing-ops + alicloud-resourcemanager-ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate two new Alibaba Cloud operations skills — `alicloud-billing-ops` (BSS billing/financial management) and `alicloud-resourcemanager-ops` (account system, resource groups, tag governance) — following the `alicloud-skill-generator` meta-skill's Evaluation-Driven Workflow.

**Architecture:** Two independent agents run in parallel, each executing the full 7-step generator workflow for one skill. Post-generation, both outputs are verified against the P0/P1 checklist.

**Tech Stack:** `alicloud-skill-generator` v3.0.0 meta-skill, aliyun CLI + JIT Go SDK fallback, Alibaba Cloud BSSOpenApi + ResourceManager + Tag APIs

**Execution Strategy:** Fan-out parallel agents using `dispatching-parallel-agents` skill.

---

## Agent A: Generate `alicloud-billing-ops`

### Task A1: Scaffold & Populate — alicloud-billing-ops

**Product:** BSSOpenApi (aliyun bssopenapi)
**CLI Applicability:** dual-path
**Primary Resources:** Bill Overview, Bill Details, Orders, Account Balance, Savings Plans, Reserved Instances, Resource Packages

**Files to create:**

```
alicloud-billing-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md
│   ├── troubleshooting.md
│   ├── monitoring.md
│   ├── integration.md
│   ├── well-architected-assessment.md
│   └── finops-best-practices.md
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json
```

**Key operations to cover:**
1. Query account balance (`QueryAccountBalance`)
2. Query bill overview (`QueryBillOverview`)
3. Query bill details (`QueryBill`, `QueryInstanceBill`)
4. Query settlement bill (`QuerySettleBill`)
5. Query account bills (`QueryAccountBill`)
6. Query orders (`QueryOrders`, `GetOrderDetail`)
7. Query RI utilization (`QueryRIUtilizationDetail`)
8. Query savings plans (`QuerySavingsPlansInstance`, `QuerySavingsPlansDeductLog`)
9. Query resource packages (`QueryResourcePackageInstances`)
10. Query account transactions (`QueryAccountTransactions`)
11. Query prepaid cards / cash coupons (`QueryPrepaidCards`, `QueryCashCoupons`)
12. Query cost allocation / bill split (`QuerySplitItemBill`)
13. FinOps: cost anomaly detection flow
14. FinOps: budget alert setup flow
15. FinOps: resource expiration warning flow

**Description for SKILL.md frontmatter:**

> Use when the user needs to query, analyze, or manage Alibaba Cloud billing, costs, orders, or account finances — account balance, bill overview/details, instance-level bills, settlement bills, orders, reservations (RI/SCU), savings plans, resource packages, transactions, prepaid cards, vouchers, cost optimization, budget alerts, resource expiration warnings. User mentions "账单", "费用", "账单明细", "账户余额", "订单", "预留实例", "RI", "存储容量包", "SCU", "储蓄计划", "Savings Plan", "资源包", "代金券", "发票", "月账单", "成本优化", "费用分析", "bssopenapi", "billing", "cost", "bill" — even without naming the product explicitly. Not for resource CRUD, permissions, or monitoring.

**Steps:**

- [ ] **A1.1**: Run `aliyun bssopenapi` to verify CLI support and list available APIs
- [ ] **A1.2**: Create `alicloud-billing-ops/` directory with all subdirectories
- [ ] **A1.3**: Populate `SKILL.md` frontmatter with correct metadata (version 1.0.0, dual-path)
- [ ] **A1.4**: Write `SKILL.md` Trigger & Scope (SHOULD/SHOULD NOT use with delegation rules)
- [ ] **A1.5**: Write `SKILL.md` Variable Convention ({{env.*}}, {{user.*}}, {{output.*}})
- [ ] **A1.6**: Write `SKILL.md` API and Response Conventions with verified JSON paths
- [ ] **A1.7**: Write `SKILL.md` Capabilities at a Glance table
- [ ] **A1.8**: Write `SKILL.md` Execution Flows for each operation (Pre-flight → Execute → Validate → Recover)
- [ ] **A1.9**: Write `SKILL.md` Quick Start, Prerequisites, Operational Best Practices
- [ ] **A1.10**: Write `SKILL.md` Five Core Standards table
- [ ] **A1.11**: Write `SKILL.md` Well-Architected Framework integration table
- [ ] **A1.12**: Write `SKILL.md` Token Efficiency Guidelines
- [ ] **A1.13**: Write `SKILL.md` Reference Directory and Changelog
- [ ] **A1.14**: Populate `references/core-concepts.md` (BSS architecture, billing models, dimensions)
- [ ] **A1.15**: Populate `references/api-sdk-usage.md` (API operation map, request/response)
- [ ] **A1.16**: Populate `references/cli-usage.md` (CLI command map, coverage gaps)
- [ ] **A1.17**: Populate `references/troubleshooting.md` (error codes >= 10, diagnostic steps)
- [ ] **A1.18**: Populate `references/monitoring.md` (cost metrics, budget alerts)
- [ ] **A1.19**: Populate `references/integration.md` (Go bootstrap, JIT SDK, env vars)
- [ ] **A1.20**: Populate `references/well-architected-assessment.md` (five-pillar, cost focus)
- [ ] **A1.21**: Populate `references/finops-best-practices.md` (cost optimization patterns)
- [ ] **A1.22**: Create `assets/example-config.yaml`
- [ ] **A1.23**: Create `assets/eval_queries.json` (10 should-trigger + 10 should-not-trigger)
- [ ] **A1.24**: Run Post-Generation Self-Check (C1-C6) and fix any violations
- [ ] **A1.25**: Run Anti-Pattern Checklist and fix any violations

---

## Agent B: Generate `alicloud-resourcemanager-ops`

### Task B1: Scaffold & Populate — alicloud-resourcemanager-ops

**Products:** ResourceManager (aliyun resourcemanager) + Tag (aliyun tag)
**CLI Applicability:** dual-path
**Primary Resources:** ResourceDirectory, Folder, Account, ResourceGroup, Tag, TagPolicy

**Files to create:**

```
alicloud-resourcemanager-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md
│   ├── troubleshooting.md
│   ├── monitoring.md
│   ├── integration.md
│   ├── well-architected-assessment.md
│   └── tag-governance.md
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json
```

**Key operations to cover:**
1. Query resource directory (`GetResourceDirectory`)
2. Enable resource directory (`EnableResourceDirectory`)
3. Query accounts (`ListAccounts`, `GetAccount`)
4. Create resource account (`CreateResourceAccount`)
5. Move account between folders (`MoveAccount`)
6. Remove cloud account (`RemoveCloudAccount`)
7. Query folders (`ListFolders`, `GetFolder`)
8. Create/update/delete folders (`CreateFolder`, `UpdateFolder`, `DeleteFolder`)
9. Query resource groups (`ListResourceGroups`, `GetResourceGroup`)
10. Create/update/delete resource groups (`CreateResourceGroup`, `UpdateResourceGroup`, `DeleteResourceGroup`)
11. Move resources between groups (`MoveResources`)
12. Query/list resources by group (`ListResources`)
13. Control policies (`ListControlPolicies`, `GetControlPolicy`, `AttachControlPolicy`)
14. Account invitations/join (`InviteAccountToResourceDirectory`, `GetHandshake`, `AcceptHandshake`)
15. Tag: list tag keys/values (`ListTagKeys`, `ListTagValues`)
16. Tag: tag/untag resources (`TagResources`, `UntagResources`)
17. Tag: query resources by tag (`ListTagResources`)
18. Tag: create/delete tags (`CreateTags`, `DeleteTag`)
19. Tag: tag policies (`ListTagPolicies`, `CreatePolicy`, `AttachConfigRuleToPolicy`)
20. FinOps: tag-based cost allocation flow
21. FinOps: resource group-based cost allocation flow
22. Governance: least-privilege account structure audit

**Description for SKILL.md frontmatter:**

> Use when the user needs to manage Alibaba Cloud Resource Directory, accounts, folders, resource groups, tags, tag policies, or tag governance — account creation/movement/removal, folder hierarchy management, resource group CRUD and resource movement, control policies, account invitations, tag key/value management, batch resource tagging, tag-based cost allocation, resource group-based cost attribution, tag compliance auditing. User mentions "资源目录", "账号", "子账号", "资源夹", "文件夹", "资源组", "标签", "标签策略", "资源归属", "分账", "成本归属", "resourcemanager", "resource manager", "tag", "标签治理", "tag policy" — even without naming the product explicitly. Not for RAM permissions, billing/queries, or resource CRUD.

**Steps:**

- [ ] **B1.1**: Run `aliyun resourcemanager` and `aliyun tag` to verify CLI support and list available APIs
- [ ] **B1.2**: Create `alicloud-resourcemanager-ops/` directory with all subdirectories
- [ ] **B1.3**: Populate `SKILL.md` frontmatter with correct metadata (version 1.0.0, dual-path)
- [ ] **B1.4**: Write `SKILL.md` Trigger & Scope (SHOULD/SHOULD NOT use with delegation rules)
- [ ] **B1.5**: Write `SKILL.md` Variable Convention ({{env.*}}, {{user.*}}, {{output.*}})
- [ ] **B1.6**: Write `SKILL.md` API and Response Conventions with verified JSON paths
- [ ] **B1.7**: Write `SKILL.md` Capabilities at a Glance table
- [ ] **B1.8**: Write `SKILL.md` Execution Flows for each operation (Pre-flight → Execute → Validate → Recover)
- [ ] **B1.9**: Write `SKILL.md` Quick Start, Prerequisites, Operational Best Practices
- [ ] **B1.10**: Write `SKILL.md` Five Core Standards table
- [ ] **B1.11**: Write `SKILL.md` Well-Architected Framework integration table
- [ ] **B1.12**: Write `SKILL.md` Token Efficiency Guidelines
- [ ] **B1.13**: Write `SKILL.md` Reference Directory and Changelog
- [ ] **B1.14**: Populate `references/core-concepts.md` (Resource Directory architecture, limits, hierarchy)
- [ ] **B1.15**: Populate `references/api-sdk-usage.md` (API operation map for both RM + Tag)
- [ ] **B1.16**: Populate `references/cli-usage.md` (CLI command map, coverage gaps for both products)
- [ ] **B1.17**: Populate `references/troubleshooting.md` (error codes >= 10, diagnostic steps)
- [ ] **B1.18**: Populate `references/monitoring.md` (account activity metrics, tag compliance)
- [ ] **B1.19**: Populate `references/integration.md` (Go bootstrap, JIT SDK, env vars)
- [ ] **B1.20**: Populate `references/well-architected-assessment.md` (five-pillar, security/governance focus)
- [ ] **B1.21**: Populate `references/tag-governance.md` (tag strategy, cost allocation, compliance rules)
- [ ] **B1.22**: Create `assets/example-config.yaml`
- [ ] **B1.23**: Create `assets/eval_queries.json` (10 should-trigger + 10 should-not-trigger)
- [ ] **B1.24**: Run Post-Generation Self-Check (C1-C6) and fix any violations
- [ ] **B1.25**: Run Anti-Pattern Checklist and fix any violations

---

## Post-Generation (After Both Agents Complete)

- [ ] Verify both skills exist with all required files
- [ ] Cross-check delegation rules between billing-ops and resourcemanager-ops
- [ ] Update CLAUDE.md cross-skill delegation table with the two new skills
- [ ] Run markdownlint on all generated files
- [ ] Commit: `feat: add alicloud-billing-ops and alicloud-resourcemanager-ops skills`
