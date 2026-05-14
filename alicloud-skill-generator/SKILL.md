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
  version: "3.0.0"
  last_updated: "2026-05-14"
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

| Artifact | Description |
|----------|-------------|
| `alicloud-[product]-ops/SKILL.md` | Main skill runbook — triggers, flows, recovery, safety gates |
| `references/core-concepts.md` | Architecture, limits, regions, quotas |
| `references/api-sdk-usage.md` | Operation map, required fields, pagination, request/response snippets |
| `references/cli-usage.md` | `aliyun` CLI cheat sheet (primary path) — when `cli_applicability: dual-path` |
| `references/troubleshooting.md` | Error codes, ordered diagnostics |
| `references/monitoring.md` | Metrics, dashboards, alerts (when monitoring in scope) |
| `references/integration.md` | Go bootstrap, JIT SDK setup, env vars |
| `assets/example-config.yaml` | Example configuration |

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

**Validation checkpoint:** Before proceeding, confirm:
- [ ] All operationIds are real (not invented)
- [ ] JSON paths are from actual response schemas
- [ ] Error codes are documented in OpenAPI or official docs
- [ ] `cli_applicability` is correctly determined (`dual-path` vs `sdk-only`)

---

### Step 3: Scaffold Directory Layout

```text
alicloud-[product]-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md              # Required when cli_applicability: dual-path
│   ├── troubleshooting.md
│   ├── monitoring.md              # When monitoring in scope
│   └── integration.md
├── assets/
│   └── example-config.yaml
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
| `cli_applicability` | `dual-path` (CLI available) or `sdk-only` (JIT Go SDK only) |
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
- [ ] **Each flow** documents **`aliyun` as primary path** and **SDK/API as fallback** (when `cli_applicability: dual-path`)
- [ ] **Failure recovery:** HALT vs retry; throttling with exponential backoff; non-retryable business errors (QuotaExceeded, InsufficientBalance, InvalidParameter)
- [ ] **API fidelity:** Fields and paths traceable to OpenAPI/SDK for the stated version
- [ ] **CLI fidelity:** Default output is JSON (NO `--output json` needed); `--output` used for JMESPath columns only; commands match official CLI docs; JSON paths verified with a real CLI run or official docs
- [ ] **Safety gates** for destructive operations (before **each** documented path: `aliyun` **and** SDK fallback)
- [ ] **Timeouts** for polling and long-running operations (default: 5s interval, 300s max wait)
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
- [ ] **Optimization Awareness:** Skill design considers Fault Diagnosis, Root Cause Localization, and Rapid Resolution dimensions per [optimization-analysis.md](references/optimization-analysis.md)
- [ ] **AIOps Compliance (when skill involves monitoring/alarm/diagnosis):** Skill implements multi-metric correlation, cross-skill diagnosis decision tree, delegation matrix, proactive inspection, and alarm storm handling per [aiops-best-practices.md](references/aiops-best-practices.md)

### P1 — SHOULD PASS

- [ ] **Chaining:** Stable output fields for downstream skills (via `{{output.*}}` placeholders)
- [ ] **Naming:** `alicloud-[product]-ops` consistent with repo conventions
- [ ] **Pinned** SDK/API baseline where drift matters (in metadata or integration.md)
- [ ] **Idempotency** or duplicate-resource behavior documented when automation or retries apply
- [ ] **Adversarial scenarios** considered using the governance doc (when present)
- [ ] **Path preference:** SKILL.md states when to prefer `aliyun` vs SDK fallback if non-obvious
- [ ] **Metadata:** Ops skill frontmatter includes `cli_applicability`, `cli_support_evidence`, `go_version_minimum`, `environment` vars

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
| [assets/eval_queries.json](assets/eval_queries.json) | Eval queries for testing the meta-skill's description trigger accuracy |

### External References

- [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud SDK for Go](https://github.com/alibabacloud-go)
- [Agent Skills Open Specification](https://agentskills.io/specification)