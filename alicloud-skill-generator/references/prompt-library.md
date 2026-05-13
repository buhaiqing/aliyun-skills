# Prompt Library — Alibaba Cloud Skill Generator

> **Purpose:** Centralized, structured repository of all prompts used during the skill generation lifecycle. Each entry includes content, usage context, parameters, and effectiveness evaluation criteria.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14

---

## Table of Contents

1. [Meta-Prompts (Generator-Level)](#1-meta-prompts-generator-level)
2. [Scaffolding Prompts](#2-scaffolding-prompts)
3. [Analysis Prompts](#3-analysis-prompts)
4. [Validation Prompts](#4-validation-prompts)
5. [User Experience Prompts](#5-user-experience-prompts)
6. [Prompt Effectiveness Tracking](#6-prompt-effectiveness-tracking)

---

## 1. Meta-Prompts (Generator-Level)

### P1: Skill Generation Initiator

**ID:** `meta-initiate`
**Usage Context:** Triggered when user requests creation of a new `alicloud-[product]-ops` skill.
**Trigger Conditions:**
- User mentions "add skill for [product]"
- User mentions "generate alicloud-[product]-ops"
- Existing skill lacks P0 elements and needs regeneration

**Prompt Content:**
```
You are the Alibaba Cloud Skill Generator. Your task is to scaffold a new operational skill for Alibaba Cloud product: {{product.name}}.

Before generating, you MUST:
1. Confirm the product slug via `aliyun help {{product.slug}}` or official docs
2. Verify OpenAPI spec availability at {{openapi.url}}
3. Decide: extend existing skill vs create new directory
4. Collect from user: product name, primary resource type, API service identifier, official doc URLs, operation list

Follow the generation process in SKILL.md Step 0–6 exactly.
Output: structured directory tree with populated SKILL.md and references/.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.name` | string | Yes | English product name (e.g., ECS, RDS) |
| `product.slug` | string | Yes | CLI product slug (e.g., ecs, rds) |
| `openapi.url` | string | Strongly recommended | OpenAPI/Swagger URL |
| `product.chinese_name` | string | No | Chinese name for trigger matching |

**Effectiveness Evaluation:**
- **Success Metric:** Generated skill passes P0 checklist ≥ 95% items
- **Failure Mode:** Missing OpenAPI source → API hallucination risk
- **Optimization:** Auto-detect product slug from `aliyun help` output

---

### P2: Extend vs New Decision

**ID:** `meta-extend-vs-new`
**Usage Context:** Before Step 1 of generation process.
**Trigger Conditions:** Product name matches existing directory pattern.

**Prompt Content:**
```
Analyze whether to EXTEND existing skill `alicloud-{{product}}-ops` or CREATE new directory.

Decision rules:
- EXTEND if: same product, same resource model, adding operations or fixing gaps
- NEW if: distinct service/API surface, different primary resource, or product is genuinely separate (e.g., ECS vs VPC)

Check existing directory for:
1. Directory presence: alicloud-{{product}}-ops/
2. SKILL.md version and last_updated
3. Missing P0 elements (triggers, placeholders, flows, recovery, safety gates)

Output: decision (EXTEND or NEW) with justification.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product identifier |

**Effectiveness Evaluation:**
- **Success Metric:** Correct decision in 100% of cases (wrong decision causes skill fragmentation)
- **Failure Mode:** Creating duplicate skills for same product
- **Optimization:** Maintain product-to-skill mapping registry

---

## 2. Scaffolding Prompts

### P3: Directory Layout Scaffold

**ID:** `scaffold-layout`
**Usage Context:** Step 2 of generation process.
**Trigger Conditions:** Decision made to create new skill directory.

**Prompt Content:**
```
Create the standard directory layout for `alicloud-{{product}}-ops`:

```
alicloud-{{product}}-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md              # required when cli_applicability: dual-path
│   ├── troubleshooting.md
│   ├── monitoring.md
│   ├── integration.md
│   └── idempotency-checklist.md  # when retries/automation required
└── assets/
    └── example-config.yaml
```

Populate each file from templates in `alicloud-skill-generator/references/`.
Replace all [Placeholders] with product-specific content derived from OpenAPI.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product identifier |
| `cli_applicability` | enum | Yes | `dual-path` or `sdk-only` |

**Effectiveness Evaluation:**
- **Success Metric:** All P0-required files present; no missing references/
- **Failure Mode:** Missing cli-usage.md for dual-path skills
- **Optimization:** Automated template substitution with OpenAPI parsing

---

### P4: SKILL.md Population

**ID:** `scaffold-skill-md`
**Usage Context:** Step 3 of generation process.
**Trigger Conditions:** Directory layout created, OpenAPI source available.

**Prompt Content:**
```
Populate `SKILL.md` from `alicloud-skill-generator/references/alicloud-skill-template.md`.

Replace placeholders with verified data:
- [Product Name] → {{product.name}}
- [Product Chinese Name] → {{product.chinese_name}}
- [Resource Type] → {{product.primary_resource}}
- API operations → verified operationIds from {{openapi.url}}
- JSON paths → verified from actual API responses or official docs
- CLI commands → verified via `aliyun help {{product.slug}}`

CRITICAL: Do NOT invent fields, flags, or response paths. Every item MUST be traceable to OpenAPI or verified CLI output.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.name` | string | Yes | Product name |
| `product.chinese_name` | string | No | Chinese name |
| `product.primary_resource` | string | Yes | Primary resource type |
| `openapi.url` | string | Strongly recommended | OpenAPI spec URL |
| `product.slug` | string | Yes | CLI slug |

**Effectiveness Evaluation:**
- **Success Metric:** Zero hallucinated fields; all operationIds exist in OpenAPI
- **Failure Mode:** Invented JSON paths cause runtime failures
- **Optimization:** Integrate OpenAPI parser for automatic field extraction

---

## 3. Analysis Prompts

### P5: OpenAPI Source Analysis

**ID:** `analyze-openapi`
**Usage Context:** Step 1 of generation process.
**Trigger Conditions:** OpenAPI URL or spec provided.

**Prompt Content:**
```
Analyze the OpenAPI spec for Alibaba Cloud product {{product.name}}.

Extract:
1. All operationIds (grouped by tag/resource)
2. Request parameters (required vs optional, types, enums)
3. Response schemas (field names, types, nested paths)
4. Error codes and their meanings
5. Async behavior indicators (polling fields, terminal states)
6. Pagination patterns

Output: structured JSON or markdown table for each category.
Flag any operations that appear deprecated or experimental.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.name` | string | Yes | Product name |
| `openapi.spec` | string | Yes | Raw OpenAPI spec content or URL |

**Effectiveness Evaluation:**
- **Success Metric:** 100% of operations documented; no missing required params
- **Failure Mode:** Missing pagination pattern → broken list operations
- **Optimization:** Automated spec diff tracking for API updates

---

### P6: CLI Coverage Analysis

**ID:** `analyze-cli-coverage`
**Usage Context:** Step 1, parallel with OpenAPI analysis.
**Trigger Conditions:** Determining `cli_applicability` value.

**Prompt Content:**
```
Analyze `aliyun` CLI coverage for product {{product.slug}}.

Run: `aliyun help {{product.slug}}` and capture output.

Determine:
1. Does `aliyun` expose this product? (yes/no/partial)
2. Which operations are available via CLI?
3. Which operations are SDK-only?
4. Are there parameter gaps (CLI supports fewer flags than API)?

Output: coverage gap table with columns:
| Operation (API) | Available via aliyun? | Notes |

Set `cli_applicability` accordingly:
- `dual-path` if CLI covers core operations
- `sdk-only` if CLI does not expose this product
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.slug` | string | Yes | CLI product slug |

**Effectiveness Evaluation:**
- **Success Metric:** Accurate `cli_applicability` assignment
- **Failure Mode:** Marking `dual-path` when CLI lacks product → broken flows
- **Optimization:** Cache `aliyun help` output per product version

---

## 4. Validation Prompts

### P7: P0 Checklist Validation

**ID:** `validate-p0`
**Usage Context:** Step 6 of generation process.
**Trigger Conditions:** Skill scaffolding complete.

**Prompt Content:**
```
Validate generated skill `alicloud-{{product}}-ops` against P0 checklist.

Check each item:
- [ ] Trigger & Scope with SHOULD-use / SHOULD-NOT-use and delegation
- [ ] Variables: {{env.*}} vs {{user.*}}; no secret literals
- [ ] Flows: Pre-flight → Execute → Validate → Recover for each critical operation
- [ ] Each flow documents `aliyun` as primary path and SDK/API as fallback
- [ ] Failure recovery: HALT vs retry; throttling; non-retryable business errors
- [ ] API fidelity: Fields and paths traceable to OpenAPI/SDK for stated version
- [ ] aliyun-first with fallback: references/cli-usage.md present as primary path
- [ ] CLI fidelity: Default output is JSON (NO --output json needed)
- [ ] Safety gates for destructive operations (before each documented path)
- [ ] Timeouts for polling and long-running operations

For each FAILED item:
1. Describe the gap
2. Provide fix instruction
3. Re-run validation after fix

Output: PASS / FAIL with detailed report.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product identifier |
| `skill.content` | string | Yes | Full SKILL.md content |

**Effectiveness Evaluation:**
- **Success Metric:** 100% P0 items pass before merge
- **Failure Mode:** Missing safety gate → destructive action without confirmation
- **Optimization:** Automated checklist runner with regex validation

---

### P8: Adversarial Review

**ID:** `validate-adversarial`
**Usage Context:** Step 6, after P0 validation.
**Trigger Conditions:** Before merge or release.

**Prompt Content:**
```
Run adversarial scenarios against `alicloud-{{product}}-ops`.

Scenarios:
1. Destructive without confirmation — Does any delete/destroy flow lack explicit user consent?
2. Credential echo — Does any instruction print, log, or echo secret values?
3. API hallucination — Are all operationIds, fields, and paths traceable to OpenAPI?
4. Idempotency gap — What happens if the same create runs twice?
5. Throttling blindness — Are rate limits and backoff documented?
6. Region drift — Are regions hardcoded or properly templated?
7. Error recovery gap — Are QuotaExceeded / InsufficientBalance handled?

For each scenario:
- Result: PASS / FAIL
- Evidence: quote from skill content
- Fix: specific instruction if FAILED
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product identifier |
| `skill.content` | string | Yes | Full skill content |
| `openapi.spec` | string | Yes | Reference OpenAPI spec |

**Effectiveness Evaluation:**
- **Success Metric:** Zero critical security gaps
- **Failure Mode:** Credential leak in generated skill
- **Optimization:** Automated static analysis for secret patterns

---

## 5. User Experience Prompts

### P9: Onboarding Guide Generation

**ID:** `ux-onboarding`
**Usage Context:** Embedded in generated skill's SKILL.md.
**Trigger Conditions:** Every skill generation.

**Prompt Content:**
```
Generate an onboarding section for `alicloud-{{product}}-ops` SKILL.md.

Include:
1. **Quick Start (30 seconds):**
   - What this skill does (one sentence)
   - Prerequisites (credential env vars)
   - First command example

2. **Core Capabilities:**
   - List 3–5 primary operations with one-line descriptions
   - Link to full execution flows below

3. **When to Use / Not Use:**
   - 3 bullet points each
   - Delegation pointers to other skills

4. **Getting Help:**
   - How to check if credentials are set
   - How to verify CLI installation
   - Link to troubleshooting.md

Tone: concise, actionable, no jargon. Assume user knows Alibaba Cloud basics but not this product's specifics.
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product.name` | string | Yes | Product name |
| `product.primary_resource` | string | Yes | Primary resource |
| `operations` | array | Yes | List of primary operations |

**Effectiveness Evaluation:**
- **Success Metric:** New user can execute first command within 60 seconds
- **Failure Mode:** Missing prerequisites → user stuck at first step
- **Optimization:** Include copy-paste ready command blocks

---

### P10: Interactive Flow Design

**ID:** `ux-interactive-flow`
**Usage Context:** Execution flow sections in SKILL.md.
**Trigger Conditions:** Each operation flow (create, describe, delete, etc.).

**Prompt Content:**
```
Design the user interaction pattern for operation: {{operation.name}} on {{product.name}}.

Requirements:
1. **Minimal prompts:** Ask only for information that cannot be inferred or defaulted
2. **Smart defaults:** Suggest common values (e.g., region from env, name with timestamp)
3. **Confirmation for destructive actions:** Explicit yes/no with resource identifier
4. **Progress indication:** Show current step (e.g., "Step 2/4: Validating region...")
5. **Output formatting:** Human-readable summary + raw JSON path for programmatic use

Anti-patterns to avoid:
- Do not ask for credentials (use {{env.*}})
- Do not present raw JSON as primary output
- Do not chain more than 3 prompts without showing progress
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `operation.name` | string | Yes | Operation name |
| `product.name` | string | Yes | Product name |
| `operation.destructive` | boolean | Yes | Whether operation is destructive |

**Effectiveness Evaluation:**
- **Success Metric:** User completes flow with ≤ 3 interactive prompts
- **Failure Mode:** Excessive prompting → user abandonment
- **Optimization:** Pre-fill from environment and previous context

---

### P11: Error Message Design

**ID:** `ux-error-messages`
**Usage Context:** Failure recovery and troubleshooting sections.
**Trigger Conditions:** Every error handling pattern.

**Prompt Content:**
```
Design user-friendly error messages for `alicloud-{{product}}-ops`.

For each error category:

**Format:**
```
[ERROR] {{error.code}}: {{error.human_readable}}

What happened: {{error.explanation}}
How to fix: {{error.remediation}}
Next step: {{error.next_action}}
```

**Categories to cover:**
- Credential missing/invalid
- Region not supported
- Resource not found
- Quota exceeded
- Throttling / rate limit
- Invalid parameter
- Internal server error
- Network timeout

Rules:
- Never expose secret values
- Always suggest a concrete next action
- Include request ID when available for support escalation
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product identifier |
| `error.code` | string | Yes | API error code |

**Effectiveness Evaluation:**
- **Success Metric:** User can self-resolve ≥ 80% of errors without external help
- **Failure Mode:** Cryptic error → user escalation
- **Optimization:** Link to specific troubleshooting.md sections

---

### P12: Feedback Loop Design

**ID:** `ux-feedback-loop`
**Usage Context:** Post-execution sections.
**Trigger Conditions:** After each operation execution.

**Prompt Content:**
```
Design feedback mechanisms for operation: {{operation.name}}.

Include:
1. **Success feedback:**
   - What was accomplished (resource ID, state change)
   - Time taken
   - Suggested next actions

2. **Failure feedback:**
   - What went wrong (human-readable)
   - Whether retry is safe
   - How to recover or escalate

3. **Progress feedback (for long-running ops):**
   - Current state
   - Estimated time remaining
   - Polling interval

4. **Implicit feedback:**
   - State changes visible in subsequent describe calls
   - Resource status transitions
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `operation.name` | string | Yes | Operation name |
| `operation.duration` | enum | Yes | `instant`, `seconds`, `minutes` |

**Effectiveness Evaluation:**
- **Success Metric:** User always knows system state after any action
- **Failure Mode:** Silent failure → user uncertainty
- **Optimization:** Structured output with machine-readable status fields

---

## 6. Prompt Effectiveness Tracking

### Tracking Methodology

Each prompt entry above includes an **Effectiveness Evaluation** section. Use the following tracking process:

1. **After each skill generation**, record:
   - Prompt ID used
   - Success/failure of resulting skill
   - User feedback (if any)
   - Time to complete generation

2. **Monthly review:**
   - Calculate success rate per prompt
   - Identify prompts with > 10% failure rate
   - Iterate and update prompt content

3. **Continuous improvement:**
   - Add new prompts as new scenarios emerge
   - Deprecate prompts with < 50% success rate after 10 uses
   - Version all prompt changes

### Effectiveness Dashboard (Template)

| Prompt ID | Uses | Success Rate | Avg Generation Time | Last Review | Status |
|-----------|------|--------------|---------------------|-------------|--------|
| meta-initiate | 0 | — | — | 2026-05-14 | active |
| scaffold-skill-md | 0 | — | — | 2026-05-14 | active |
| validate-p0 | 0 | — | — | 2026-05-14 | active |
| ux-onboarding | 0 | — | — | 2026-05-14 | active |

### Prompt Versioning

- Format: `prompt-id@v<major>.<minor>.<patch>`
- Major: structural change or new parameter
- Minor: content improvement, new example
- Patch: typo fix, clarification

---

## Appendix: Prompt Usage Quick Reference

| Generation Step | Primary Prompts | Validation Prompts |
|-----------------|-----------------|-------------------|
| Step 0: Environment | — | — |
| Step 1: Analyze | `analyze-openapi`, `analyze-cli-coverage` | — |
| Step 2: Layout | `scaffold-layout` | — |
| Step 3: Populate | `scaffold-skill-md`, `ux-onboarding` | — |
| Step 4: References | `scaffold-layout` (reference files) | — |
| Step 5: Versioning | `meta-initiate` (frontmatter) | — |
| Step 6: Verify | — | `validate-p0`, `validate-adversarial` |
| UX Integration | `ux-interactive-flow`, `ux-error-messages`, `ux-feedback-loop` | `validate-p0` (UX items) |

---

*This prompt library is a living document. Update it whenever new generation patterns emerge or existing prompts show suboptimal effectiveness.*
