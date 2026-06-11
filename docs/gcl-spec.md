# Generator-Critic-Loop (GCL) — Implementation Spec

> 本文档是 `AGENTS.md` §12 的完整实现规范。AGENTS.md 只保留摘要和入口。

---

## 1. Purpose

Apply an adversarial **Generator ↔ Critic** loop with a quantitative rubric to every **runtime** skill execution.
Most valuable in **high-side-effect cloud operations** (delete, stop, restore, RAM/KMS/DDL) where a single
mistake is unrecoverable. This complements the static P0/P1 checklist in `alicloud-skill-generator/SKILL.md` by
catching what static review cannot — wrong arguments, missing pre-checks, silent partial failures, etc.

| GAN (real) | GCL (this spec) |
|---|---|
| Discriminator learns sample distribution | Critic scores an **explicit rubric** |
| No termination condition | Must terminate: **PASS / MAX_ITER / SAFETY_FAIL** |
| G and D train in parallel | G and C run **sequentially** |
| Goal: "fool the D" | Goal: "pass the rubric threshold" |

## 2. Roles

| Role | Job | Input | Output | Forbidden |
|---|---|---|---|---|
| **Generator (G)** | Execute the cloud operation | user request + previous Critic feedback | result + execution trace | modifying the rubric; self-scoring |
| **Hallucination Detector (H)** | Pre-execution structural validity check | G's generated command / JSON + skill's reference knowledge base | pass/fail signal + hallucination report | executing API calls (read-only offline check only); modifying G's output |
| **Critic (C)** | Independently audit G's output | G's result + trace + rubric | scores + suggestions | calling `aliyun` / SDK / mutating anything |
| **Orchestrator (O)** | Loop control, termination, final return | context + C scores + H result + budget | continue / final result | executing or scoring on its own |

**Hard constraint:** G and C MUST live in **isolated prompt contexts** (preferably isolated sessions
or sub-agents, e.g. `pi-subagents`). A shared context is a "pseudo-GCL" and is explicitly banned — see §9.
H is a **deterministic offline check** by default (the Phase 6 mechanical H); it does NOT need isolation
because it never calls cloud APIs. A future LLM-based H would require the same isolation as C.

## 3. Rubric (mandatory per skill)

Each `SKILL.md` MUST declare its skill-specific rubric under `## Quality Gate (GCL)`, **referencing**
`references/rubric.md` (which holds the full dimension table and scoring details — to keep `SKILL.md` terse
per §2 Content Separation Rule). Minimum 5 dimensions, identical to JD Cloud GCL for cross-farm consistency:

| Dimension | Meaning | Scale | Default threshold |
|---|---|---|---|
| **Correctness** | Resource id / state / config actually matches the request | 0 / 0.5 / 1 | ≥ 0.5 (1.0 required for `delete` / `stop` / RAM / KMS / DDL) |
| **Safety** | Destructive op (`delete` / `stop` / `restore` / RAM / KMS / DDL) was confirmed or guarded | 0 / 1 | = 1 |
| **Idempotency** | Retrying the same call will not cause duplicate side-effects | 0 / 0.5 / 1 | ≥ 0.5 |
| **Traceability** | Output is auditable: command, params, raw response, errors all captured | 0 / 0.5 / 1 | ≥ 0.5 |
| **Spec Compliance** | Conforms to the skill's `core-concepts.md` constraints (quotas, regions, dependencies) | 0 / 0.5 / 1 | ≥ 0.5 |

**Safety = 0 → ABORT immediately, regardless of total score.** This is a hard non-negotiable gate.

**Aliyun-specific extension dimensions** (optional per skill):

| Dimension | When to add | Example |
|---|---|---|
| **Region Compliance** | cross-region operations | `--RegionId` matches the user's declared region in `{{user.region_id}}` |
| **Credential Hygiene** | long-running or multi-step ops | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` never appears in any log line |
| **Well-Architected** | cost / security / stability-sensitive ops | operation does not violate a relevant WA pillar (e.g. disable deletion protection in prod) |

## 4. Loop Flow

```
User Request
     │
     ▼
[0] Pre-flight (Orchestrator)
    - resolve env.* and user.* variables
    - pick skill, load its rubric from references/rubric.md
    - check §8 Security Constraints (no plaintext credentials in scope)
     │
     ▼
[1] Generate (G)
    - generate command / JSON payload (DO NOT execute yet) ──┐
    - pass command + skill context to H                      │
     │                                                       │
     ▼                                                       │
[1.5] Hallucination Detection (H)                           │
    - check CLI parameter existence                          │
    - check JSON structure against OpenAPI schema            │
    - check WAF compliance (offline rubric)                  │
     │                                                       │
     ├── PASS → [1a] Execute (run the command)               │
     ├── FAIL → [1b] Regenerate (H retriggers G with         │
     │               hallucination report; max 1 retry)      │
     │         still FAIL → HALT with "HALLUCINATION_ABORT"  │
     │                                                       │
     ▼                                                       │
[2] Critique (C)                                            │
    - isolated prompt context                                │
    - score every rubric dimension                           │
    - emit ≤ 3 actionable suggestions                        │
     │                                                       │
     ▼                                                       │
[3] Decide (Orchestrator)                                   │
    - HALLUCINATION_ABORT → ABORT (no partial)               │
    - Safety=0  → ABORT (no partial)                         │
    - all pass  → RETURN                                     │
    - else & iter<max → inject                               │
       suggestions into G                                    │
    - else → RETURN best + unresolved                        │
       rubric items                                          │
     └───────────────────────────────────────────────────────┘
```

## 5. Termination (first match wins)

| Condition | Behavior |
|---|---|
| **PASS** | Every rubric dimension meets its threshold → return G's result |
| **MAX_ITER** | Reached `max_iterations` (default per skill class — see §8) → return **best-so-far** + unresolved rubric items |
| **SAFETY_FAIL** | Safety = 0 → **ABORT**; never return partial or "best-effort" output |

## 6. Trace & Audit (mandatory)

Every GCL run MUST persist a JSON trace under `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`:

```json
{
  "skill": "alicloud-ecs-ops",
  "request": "<sanitized user request>",
  "rubric_version": "v1",
  "iterations": [
    {
      "iter": 1,
      "generator": { "command": "aliyun ecs DeleteInstance ...", "args": {...}, "exit_code": 0, "result_excerpt": "..." },
      "critic": {
        "scores": {
          "correctness": 1, "safety": 1, "idempotency": 0.5,
          "traceability": 1, "spec_compliance": 1
        },
        "suggestions": ["..."],
        "blocking": false
      },
      "decision": "RETRY"
    }
  ],
  "final": { "status": "PASS", "iter": 2, "output": "..." }
}
```

**Sanitization rule (mandatory):** the `request` field MUST NOT contain `ALIBABA_CLOUD_ACCESS_KEY_SECRET`,
Redis/RDS passwords, KMS plaintext key material, RAM user passwords, or any other secret enumerated in
AGENTS.md §8. Use `<masked>` or redacted tokens before writing to disk.

**Directory:** add `./audit-results/` to `.gitignore` (or treat traces as ephemeral; do not commit).

## 7. Prompt Templates (mandatory per skill)

Each pilot/required skill MUST contain two references:

- `references/rubric.md` — the full dimension table, scoring rules, and **per-operation safety sub-rules** (e.g. for `alicloud-rds-ops`, what counts as "DDL" and what confirmation is required).
- `references/prompt-templates.md` — **Generator Prompt Template** and **Critic Prompt Template**, each declaring its `{{...}}` placeholders.

Placeholders MUST follow the repository-wide convention (see AGENTS.md §3 Operation Design Pattern):
`{{env.*}}` / `{{user.*}}` / `output.*`. Bare `{...}` placeholders are NOT allowed in skill prompt templates.

**Critic prompt must hide the raw user request** to prevent "answer-aligned" rubber-stamping.
Recommended skeleton:

```text
You are an independent Alibaba Cloud operation auditor.
You will see one execution result and its trace. Score it STRICTLY against the rubric below.
Do NOT consider the original user request — judge only what was actually done.

rubric: {{output.rubric}}
generator_output: {{output.generator_output}}
trace: {{output.trace}}

Return strict JSON:
{
  "scores": { "correctness": 0|0.5|1, "safety": 0|0.5|1, "idempotency": 0|0.5|1,
              "traceability": 0|0.5|1, "spec_compliance": 0|0.5|1 },
  "suggestions": ["≤ 3 concrete, executable improvements"],
  "blocking": true|false
}
```

## 8. Per-Skill Defaults

GCL is **only required** on high-side-effect skills. Default `max_iter` is **2** for required skills
(balances safety against latency cost). Read-only / meta skills are **optional** with higher `max_iter`.

| Skill | GCL | max_iter | Notes |
|---|---|---|---|
| `alicloud-ecs-ops` | required | 2 | delete/stop/reboot are destructive |
| `alicloud-redis-ops` | required | 2 | FLUSHALL / instance delete / backup delete |
| `alicloud-rds-ops` | required | 2 | DROP / DELETE / TRUNCATE / instance delete |
| `alicloud-polar-mysql-ops` | required | 2 | DDL via Data API / cluster delete |
| `alicloud-polar-postgresql-ops` | required | 2 | DDL / cluster delete |
| `alicloud-polar-oracle-ops` | required | 2 | DDL / cluster delete |
| `alicloud-mongodb-ops` | required | 2 | dropDatabase / instance delete |
| `alicloud-elasticsearch-ops` | required | 2 | delete index / cluster / `_delete_by_query` |
| `alicloud-ram-ops` | required | 2 | detach policy / delete user / rotate AccessKey |
| `alicloud-kms-ops` | required | 2 | schedule key deletion is irreversible |
| `alicloud-eip-ops` | required | 2 | release EIP can break production |
| `alicloud-dts-ops` | required | 2 | delete / reset / stop DTS job (irreversible) |
| `alicloud-vpc-ops` | required | 2 | delete VPC / vSwitch / NAT / SG |
| `alicloud-nat-ops` | required | 2 | delete NAT gateway / SNAT / DNAT |
| `alicloud-waf-ops` | required | 2 | delete domain / access control / defense rule |
| `alicloud-sls-ops` | required | 2 | delete logstore / index / alert / dashboard |
| `alicloud-terraform-ops` | required | 2 | `terraform destroy` / `apply` / state import; NL2HCL with destructive plan |
| `alicloud-slb-ops` | recommended | 3 | listener / backend server delete |
| `alicloud-ack-ops` | recommended | 3 | delete node / cluster / namespace |
| `alicloud-ack-serverless-ops` | recommended | 3 | delete cluster / application |
| `alicloud-fc-ops` | recommended | 3 | delete function / service / trigger |
| `alicloud-eci-ops` | recommended | 3 | delete container group |
| `alicloud-cms-ops` | recommended | 3 | alarm rule delete |
| `alicloud-resourcemanager-ops` | recommended | 3 | resource folder / account move |
| `alicloud-agentrun-ops` | recommended | 3 | delete agent / application |
| `alicloud-actiontrail-ops` | optional | 5 | read-only audit |
| `alicloud-billing-ops` | optional | 5 | read-only billing |
| `alicloud-das-ops` | optional | 5 | mostly read-only diagnostics |
| `alicloud-sas-ops` | optional | 5 | mostly read-only security posture |
| `alicloud-topo-discovery` | optional | 5 | read-only |
| `alicloud-skill-generator` | optional | 3 | meta operation (no cloud mutation) |

Each skill may override `max_iter` in its own `SKILL.md` (under `## Quality Gate (GCL)`), with a written
justification (e.g. `alicloud-elasticsearch-ops` may set 3 because `_delete_by_query` retried scans
are common and a second pass is cheap).

## 9. Anti-Patterns (banned)

- ❌ **Shared context G+C** — defeats independence → banned (use `pi-subagents` fork context or equivalent)
- ❌ **Subjective scoring** — Critic must use the rubric, not "vibes" → banned
- ❌ **Unbounded loop** — always hard-cap iterations → banned
- ❌ **Critic sees the user request** — encourages rubber-stamping → banned
- ❌ **Silently downgrade on Safety fail** — must ABORT visibly with full trace → banned
- ❌ **Trace not persisted** — no post-mortem possible → banned
- ❌ **Critic mutates resources** — Critic is read-only by definition → banned
- ❌ **Trace leaks secrets** — `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, Redis/RDS passwords, etc. must be sanitized
  per §6 → banned
- ❌ **H executes cloud API calls** — H is an offline structural check; calling `aliyun` (or any API) from H
  risks side-effects and contradicts its stateless design → banned
- ❌ **H rewrites G's command** — H must flag hallucinations, not mutate the command. Fixes come from G
  (re-generation) or the Orchestrator (HALT → manual intervention) → banned
- ❌ **H checks skipped for safety-critical ops** — at minimum, parameter existence check is MANDATORY for
  all `required` and `recommended` skills per §8 → banned

## 10. Relationship with Post-Update Self-Review (AGENTS.md)

| Aspect | Post-Update Self-Review ([docs/post-update-self-review.md](post-update-self-review.md)) | §12 GCL |
|---|---|---|
| When | After a `SKILL.md` / `references/*` is **edited** | During **runtime execution** of that skill |
| Who | The author Agent (single context) | Generator + Critic (isolated contexts) + Orchestrator |
| Input | The diff / new content | A live user request + skill rubric |
| Output | Self-review record (in-session only) | Persisted JSON trace under `./audit-results/` |
| Failure mode caught | Wrong frontmatter, missing sections, broken links | Wrong arguments, missing pre-checks, silent partial failures, missed idempotency |
| Cadence | Per skill update | Per execution |

**Both gates are mandatory for the skills marked "required" in §8** — a skill can be §11-compliant
(structurally sound) yet §12-failing (dangerous at runtime). The two together close the static-vs-runtime
quality gap.

## 11. Aliyun-Specific Differences vs. JD Cloud GCL

| Aspect | JD Cloud GCL | Aliyun GCL (this doc) |
|---|---|---|
| Primary CLI | `jdc` (Python 3.10, INI config only) | `aliyun` (Go static binary, env-var creds) |
| Credential path | `~/.jdc/config` | env: `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| Meta-skill | `jdcloud-skill-generator` | `alicloud-skill-generator` |
| Destructive workload map | VM, Redis, MySQL, PG, Mongo, ES, IAM, KMS, EIP | ECS, Redis, RDS, PolarDB×4, Mongo, ES, RAM, KMS, EIP, VPC, NAT, … |
| Optional / read-only map | audit / tag / alert intelligence | actiontrail, billing, das, sas, topo-discovery, skill-generator |
| Pilot | `jdcloud-vm-ops` | `alicloud-ecs-ops` |

The semantic model (roles, rubric dimensions, termination, anti-patterns) is **identical** by design,
so future cross-farm tooling (e.g. a shared `alicloud-gcl-runner-ops/scripts/gcl_runner.py`) can be reused with minimal adaptation.

## 12. Rollout Roadmap

- **Phase 1** ✅ — GCL spec added to `AGENTS.md`; piloted on `alicloud-ecs-ops` and extended to **14 `required` skills** (ECS, Redis, RDS, RAM, KMS, EIP, **DTS**, VPC, NAT, MongoDB, ES, PolarDB×4). Each has `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section. `alicloud-skill-generator` P0 checklist updated with 4 GCL + 2 GCL-P1 mandatory items; `references/gcl-rollout-spec.md` added.
- **Phase 2** ✅ — `alicloud-gcl-runner-ops/scripts/gcl_runner.py` (mechanical regex-based Critic, subprocess Generator, JSON trace per §6); `alicloud-gcl-runner-ops/scripts/gcl_runner_test.py` (60 unit tests, ~0.02s). `alicloud-gcl-runner-ops/scripts/README.md` + `alicloud-skill-generator/references/gcl-orchestrator-agent.md` (pi-subagents integration).
- **Phase 3-A** ✅ — LLM-based Critic (designed; not yet implemented; `critique()` interface is forward-compatible).
- **Phase 3-B** ✅ — `alicloud-gcl-runner-ops/scripts/gcl_cms_alarm_setup.py` (idempotent alarm creation; reads `crosscheck-report-*.json`; creates/updates 5 phantom alarms: GCL-Phantom-Pass, GCL-Phantom-Fail, GCL-Resource-Mismatch, GCL-Api-Errors, GCL-Timing-Anomaly; dry-run mode). `alicloud-cms-ops/references/rubric.md` enhanced from Phase 5 lean to Phase 3-B full (added §2 Phantom Alarm Schema, §4-5 worked examples). `alicloud-cms-ops/references/prompt-templates.md` enhanced (added Phantom alarm Generator/Critic rules + cross-skill delegation). `alicloud-cms-ops/references/gcl-cms-alarm-guide.md` (architecture, thresholds, cron integration, alert response playbook, dashboard). `alicloud-cms-ops/SKILL.md` bumped 2.1.0 → 2.2.0.
- **Phase 3-C** ✅ — **`alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py`** (cloud-side audit; `LookupEvents` re-verifies each `gcl-trace-*.json`; catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`). `alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck_test.py` (25 unit tests). `alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md`. `alicloud-actiontrail-ops/SKILL.md` bumped 1.0.0 → 1.1.0 with a lightweight `## Quality Gate (GCL)` cross-checker role section.
- **Phase 4** ✅ — wire rubric pass-rate to `alicloud-cms-ops` alarms (real incidents refine thresholds). `alicloud-gcl-runner-ops/scripts/gcl_passrate_reporter.py` (aggregates GCL traces → per-skill + per-dimension pass-rates → `aliyun cms PutCustomMetric` to `acs_custom_gcl` namespace). `alicloud-gcl-runner-ops/scripts/gcl_cms_alarm_setup.py` extended with 3 pass-rate alarms: GCL-Safety-Fail-Rate (P1), GCL-Correctness-Drop (P2), GCL-Traceability-Gap (P3). `alicloud-cms-ops/references/gcl-passrate-metrics-guide.md` (architecture, cron pipeline, alarm thresholds, dashboard). `AGENTS.md` §12.8: DTS added as 14th `required` skill.
- **Phase 5** ✅ — GCL rollout extended to all 8 `recommended` skills (SLB, ACK, ASK, FC, ECI, CMS, ResourceManager, AgentRun). Each gets lean `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section with `max_iter=3`. Meta / read-only skills (`ActionTrail`, `Billing`, `DAS`) remain `optional` per §8.
- **Phase 6** ✅ — **Hallucination Detection Layer (H)** shipped. §14 added to spec; `alicloud-gcl-runner-ops/scripts/gcl_runner.py` extended with `--enable-hallucination-check` flag and `hallucination_detect()` function (parameter existence, JSON structure, WAF compliance). `alicloud-gcl-runner-ops/scripts/gcl_runner_test.py` extended with 25 H-specific tests. Every `required`/`recommended` skill now gets a `HALLUCINATION_ABORT` exit path in addition to the existing `SAFETY_FAIL`.
- **Migration to shared skill** ✅ — GCL scripts migrated from top-level `scripts/` to `alicloud-gcl-runner-ops/scripts/`. All skills now delegate GCL execution via `## Delegation Rules` in SKILL.md instead of inline Phase 1 templates. `alicloud-gcl-runner-ops` created as a shared framework skill.

## 13. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial GCL specification added to `AGENTS.md`. Ported from `jdcloud-skills/AGENTS.md` with Aliyun adaptations: `aliyun` CLI, env-var credentials, Aliyun product mapping in §8, alignment with §11 Self-Review via §10. Pilot scoped to `alicloud-ecs-ops`. |
| 1.1.0 | 2026-06-04 | **Phase 2 shipped**: `alicloud-gcl-runner-ops/scripts/gcl_runner.py` (mechanical regex-based Critic, subprocess Generator, JSON trace persistence per §6); `alicloud-gcl-runner-ops/scripts/gcl_runner_test.py` (60 pure-stdlib `unittest` tests); `alicloud-gcl-runner-ops/scripts/README.md`; `alicloud-skill-generator/references/gcl-orchestrator-agent.md` (pi-subagents agent spec). Added 4 P0 + 2 P1 GCL checks to `alicloud-skill-generator/SKILL.md` checklist; added `references/gcl-rollout-spec.md`. GCL rollout extended to 8 additional skills (VPC, NAT, MongoDB, ES, 4×PolarDB). |
| 1.2.0 | 2026-06-04 | **Phase 3-C shipped**: `alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py` (cloud-side audit); `alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck_test.py` (25 unit tests). `alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md`. `alicloud-actiontrail-ops/SKILL.md` bumped 1.0.0 → 1.1.0. `alicloud-gcl-runner-ops/scripts/README.md` extended. §12.11 Roadmap updated. |
| 1.3.0 | 2026-06-04 | **Phase 5 shipped**: GCL rollout extended to all 8 `recommended` skills (SLB, ACK, ASK, FC, ECI, CMS, ResourceManager, AgentRun). Total Phase 5 artifacts: 16 new files (~14 KB rubric + ~10 KB prompt templates across 8 skills). |
| 1.5.0 | 2026-06-07 | **Phase 6 shipped — Hallucination Detection Layer (H)**: New pre-execution structural validity check. Roles table updated with H role. Loop flow updated to include step [1.5] H gate. New §14 with parameter existence, JSON structure, and WAF compliance checks. Anti-patterns updated with 3 H-specific banned patterns. |
| 1.6.0 | 2026-06-07 | **Migration to shared skill**: GCL scripts migrated from top-level `scripts/` to `alicloud-gcl-runner-ops/scripts/`. All skills now delegate GCL execution via `## Delegation Rules` in SKILL.md. `alicloud-gcl-runner-ops` created as shared framework skill. `gcl-orchestrator-agent.md` deprecated. |

---

## 14. Hallucination Detection Layer (H)

> **Purpose**: Catch LLM-generated commands, JSON payloads, and architecture suggestions that
> contain structurally invalid elements **before** they reach the cloud API. This is a
> **pre-execution** gate placed between G's generation and actual API execution, filling a
> blind spot the Critic (post-execution) and ActionTrail cross-check (cloud-side verification)
> cannot cover.

### 14.1 Motivation

LLM agents frequently hallucinate when generating Alibaba Cloud CLI commands:

| Hallucination Type | Example | Consequence |
|---|---|---|
| **Non-existent parameter** | `--InstanceName` instead of `--InstanceName` (correct) or `--InstanceId` used on a `DescribeRegions` call (wrong context) | API rejects with InvalidParameter → wasted call + latency |
| **Wrong parameter name** | `--Zone` instead of `--ZoneId` | Silent ignore (CLI parses only known flags) → wrong behavior |
| **Non-existent JSON field** | `"Status": "running"` in a response field that should be `"DBInstanceStatus"` | Downstream parse failure |
| **Wrong JSON structure** | Flattened nested objects into a flat map | API rejects or silently ignores fields |
| **WAF-violating pattern** | Disabling deletion protection without checking instance type | Production risk |

These are **different from execution errors** caught by the Critic — they are structural
hallucinations that either fail immediately (wasted API call) or, worse, produce a success
response with unintended side effects because a wrong parameter was silently ignored.

### 14.2 Three-Category Check

#### 14.2.1 CLI Parameter Existence (MANDATORY for all `required`/`recommended` skills)

Verify every `--flag` in the generated command exists in that operation's parameter set.

| Source of Truth | Method | Coverage |
|---|---|---|
| `aliyun <product> <operation> --help` | Parse the `--Parameters` section | Production-grade; runnable in CI |
| Skill's `references/api-sdk-usage.md` | Operation map table | Always available offline |
| Built-in parameter knowledge base | Pre-compiled dict in `gcl_runner.py` (`PARAMETER_KNOWLEDGE`) | Default; 300+ operations |

**Algorithm (mechanical H):**

1. Tokenize command into `--flag value` pairs
2. For each `--flag`, look up `(product, operation, flag)` in parameter knowledge base
3. Unrecognized flag → record hallucination
4. All recognized → PASS

**Priority**: Offline knowledge base first → `aliyun help` fallback (if CLI available) → PASS
if neither source can confirm (conservative default).

#### 14.2.2 JSON Structure Compliance (RECOMMENDED for JSON-heavy operations)

For operations that pass a JSON payload (e.g. `aliyun ecs RunInstances --RegionId ... --ParameterJson '{...}'`):

| Check | Rule |
|---|---|
| **Field existence** | Every field in the JSON matches a known OpenAPI field for that operation |
| **Field nesting** | Nested objects match the OpenAPI schema's hierarchy (no flattening) |
| **Type correctness** | Values match expected types: string, integer, boolean, array |
| **Enum membership** | Enum fields (e.g. `PayType`, `InstanceChargeType`) use valid values |

**Source of truth**: Skill's `references/api-sdk-usage.md` operation response tables OR a
pre-compiled field map in `gcl_runner.py`.

**Fallback**: If no JSON payload is present in the command, this check passes automatically.

#### 14.2.3 WAF Compliance — Offline Check (RECOMMENDED for destructive / cost-sensitive ops)

Compare the generated operation against the skill's `references/well-architected-assessment.md`:

| WAF Pillar | Check |
|---|---|
| **Security** | Does the command disable protection features (deletion protection, SSL, encryption)? |
| **Stability** | Does the command operate on a production resource without backup? |
| **Cost** | Does the command provision resources without considering billing model? |
| **Efficiency** | Does the command use deprecated API versions or non-standard parameters? |
| **Performance** | Does the command set performance-related parameters to unsafe values? |

**Implementation**: A lightweight regex-based pattern matcher against the command text,
loaded from the skill's `references/rubric.md` §WAF section if present. If no WAF section
exists, this check passes automatically.

### 14.3 Termination

| Condition | Exit Code | Action |
|---|---|---|
| **H_PASS** | — | Continue to [1a] Execute |
| **H_FAIL → Regenerate** | — | Inject hallucination report into G; max 1 regeneration attempt |
| **HALLUCINATION_ABORT** | 5 | HALT — structural hallucinations persist after regeneration; return unresolved report |

### 14.4 Trace Integration

The H result is embedded in the GCL trace JSON under `iterations[].hallucination_detector`:

```json
{
  "iterations": [
    {
      "iter": 1,
      "hallucination_detector": {
        "status": "FAIL",
        "checks": {
          "cli_parameters": {
            "total": 4,
            "recognized": 3,
            "unrecognized": ["--Zone"],
            "status": "FAIL"
          },
          "json_structure": {
            "status": "PASS",
            "note": "no JSON payload in command"
          },
          "waf_compliance": {
            "status": "PASS",
            "note": "no WAF patterns matched"
          }
        },
        "report": "Unrecognized CLI parameter: --Zone (expected alternatives: --ZoneId)"
      },
      "regenerated": true,
      "generator": { ... },
      "critic": { ... }
    }
  ]
}
```

### 14.5 Per-Skill Defaults

Hallucination Detection is **recommended** for all skills, but levels vary:

| GCL Level | Hallucination Check | H Required Dimensions |
|---|---|---|
| **required** | **MANDATORY** | CLI parameter existence + JSON structure (if applicable) |
| **recommended** | **MANDATORY** | CLI parameter existence |
| **optional** | OPTIONAL | None |

### 14.6 Anti-Patterns (H-specific)

See §9 for the full anti-pattern list. H-specific additions:

- H executes cloud API calls — H is an offline structural check; calling `aliyun` (or any API) from H
  risks side-effects and contradicts its stateless design
- H rewrites G's command — H must flag hallucinations, not mutate the command. Fixes come from G
  (re-generation) or the Orchestrator (HALT → manual intervention)
- H checks skipped for safety-critical ops — parameter existence is MANDATORY for all `required`
  and `recommended` skills; skipping it for destructive ops defeats the purpose

### 14.7 Relationship with Other GCL Layers

| Layer | Timing | What It Catches | Complementary to H |
|---|---|---|---|
| **H (Hallucination Detector)** | Pre-execution | Structural invalidity (fake params, wrong JSON, WAF violations) | — |
| **C (Critic)** | Post-execution | Wrong values, missing pre-checks, silent partial failures | H prevents execution of structurally invalid G output; C validates the actual result |
| **ActionTrail cross-check** | Post-hoc (cloud-side) | Phantom ops, resource mismatches, timing anomalies | H prevents bad commands from ever running; ActionTrail confirms what did run |
| **GCL pass-rate metrics** | Aggregated | Trend analysis per skill/dimension | H failures feed into pass-rate metrics under a new `structural_validity` dimension |

All four layers together form a **four-wall defense**:

```
User Request
  |
  v
[0] Pre-flight (O)
  |
  v
[1] Generate (G) ------------------------------+
  |                                             |
  v                                             |
[1.5] Hallucination Detection (H)  <- Phase 6  |
  |   (structural validity pre-check)           |
  +-- PASS -> [1a] Execute                      |
  +-- FAIL -> Regenerate (x1) -> still FAIL? -> |
  |             HALLUCINATION_ABORT             |
  v                                             |
[2] Critique (C)                                |
  |   (post-execution rubric audit)             |
  v                                             |
[2b] ActionTrail Cross-check (C3)               |
  |   (cloud-side verification)                 |
  v                                             |
[3] Decide (O)                                  |
  |   (loop + termination)                      |
  +---------------------------------------------+
  |
  v
[4] Pass-rate metrics (aggregated)
      -> CMS alarms if thresholds breached
```

### 14.8 Prompt Template Extension (for LLM-based H)

When an LLM-based H is used instead of the mechanical H (Phase 6 default):

```text
You are an Alibaba Cloud CLI hallucination detector.
You will see a generated command. Check it STRICTLY against the knowledge base below.

DO NOT execute the command. DO NOT consider the user's original intent.
Only judge structural validity.

skill: {{output.skill}}
operation: {{output.operation}}
command: {{output.generated_command}}
known_parameters: {{output.known_parameters}}
json_payload: {{output.json_payload}}
waf_rules: {{output.waf_rules}}

Return strict JSON:
{
  "cli_parameters": {
    "status": "PASS"|"FAIL",
    "unrecognized_flags": ["..."],
    "suggestion": "..."
  },
  "json_structure": {
    "status": "PASS"|"FAIL",
    "issues": ["..."]
  },
  "waf_compliance": {
    "status": "PASS"|"FAIL",
    "violations": ["..."]
  },
  "overall": "PASS"|"FAIL",
  "report": "..."
}
```

This template follows the same isolation principle as the Critic prompt (§7):
**H must NOT see the user's original request** to prevent answer-alignment bias.
