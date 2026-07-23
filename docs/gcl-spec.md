# Generator-Critic-Loop (GCL) — Implementation Spec

> 本文档是 `AGENTS.md` §12 的完整实现规范。AGENTS.md 只保留摘要和入口。
>
> **复利工程要求**：GCL 执行完成后，必须遵守 [AGENTS.md §0.3 复利工程](../AGENTS.md#03-复利工程--compound-engineering-最高优先级) 原则——提取可复用模式、记录设计决策、清理废弃产物。详见 [AGENTS.md §18.5 复利检查清单](../AGENTS.md#185-复利检查清单-每次完成任务后强制执行)。

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
| **Critic (C)** | Independently audit G's output; assess **test accuracy** and regression verification need (see [§2.1](#21-critic-test--regression-assessment-mandatory)) | G's result + trace + rubric + change scope / test inventory | scores + suggestions + test/regression verdict | calling `aliyun` / SDK / mutating anything |
| **Orchestrator (O)** | Loop control, termination, final return | context + C scores + H result + budget | continue / final result | executing or scoring on its own |

**Hard constraint:** G and C MUST live in **isolated prompt contexts** (preferably isolated sessions
or sub-agents, e.g. `pi-subagents`). A shared context is a "pseudo-GCL" and is explicitly banned — see §9.
H is a **deterministic offline check** by default (the Phase 6 mechanical H); it does NOT need isolation
because it never calls cloud APIs. A future LLM-based H would require the same isolation as C.

### 2.1 Critic Test & Regression Assessment (MANDATORY)

> **Core principle — accuracy over coverage**: Do **not** optimize for coverage metrics or test count. Optimize for whether tests **accurately** validate changed behavior and would **reliably catch** real regressions.

On **every** critique iteration, C MUST evaluate two acceptance dimensions **in addition to** the rubric:

| Assessment | C action | On failure |
|------------|----------|------------|
| **Test accuracy** | Judge whether existing tests **correctly** exercise and assert behaviors touched by this change. Ask: *if this change introduced a bug, would these tests fail?* Reject stale tests, wrong contracts, masked failures, or cases that touch code without validating outcomes | `blocking=true`; concrete test fixes/additions in `suggestions`; **RETRY** — no PASS until accurate for the change |
| **Regression verification gate** | Decide whether targeted regression ([AGENTS.md §11.1](../AGENTS.md#111-regression-testing-mandatory)) is required — pick the **smallest accurate suite** for the change and adjacent risk, not blanket runs for coverage theater | If required: name suite(s) and why sufficient; require green runs in trace/summary. If waived: document zero-behavioral-delta rationale |

**Decision posture**: Professional and cautious — when ambiguous, require targeted regression with tests that would actually fail on breakage.

| Change signal | C default |
|---------------|-----------|
| Pure docs/formatting (confirmed zero behavior delta) | Runtime regression optional; document skip rationale |
| Scripts / SkillOpt / execution flow / shared runtime | Run §11.1 suite(s) **only where they accurately exercise the changed path**; fix shallow assertions |
| Cross-skill or generator / `gen-skillopt.sh` | Shared integration + ≥1 representative test that **traverses the changed contract** |
| Refactor or intentional behavior change | Test-first: lock accurate before/after behavior, then applicable suites |

**Banned**: padding test count, chasing coverage %, PASSing on green suites that do not assert the changed behavior.

O treats inaccurate tests or missing required regression evidence like any other blocking C finding.

**Mechanical Critic (`gcl_runner.py`)**: When `test_assessment` is present on the generator trace or via CLI `--test-assessment`, `evaluate_test_assessment()` enforces the same rules; failures yield `RETRY` / `MAX_ITER` (not `SAFETY_FAIL`). See `alicloud-gcl-runner-ops/scripts/README.md`.

**Executing Agent gate (`scripts/skill-change-critic-gate.sh`)**: Before marking any change done, Agents MUST run classify → template (fill `tests_accurate` + `accuracy_rationale`) → `verify --run`. See [AGENTS.md §11.1 Skill Change Critic Gate](../AGENTS.md#skill-change-critic-gate-mandatory--closes-the-loop).

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
| **Wrapper Compliance** | every skill with `scripts/*-skillopt-wrapper.sh` | command was routed through the wrapper, not bare `aliyun <product>` (AGENTS.md §15.8) |

**Wrapper Compliance (MANDATORY for all skills with a wrapper script):**

| Score | Meaning |
|:-----:|---------|
| **1** | Command routed through `scripts/*-skillopt-wrapper.sh` (or a non-aliyun path: SDK / data-plane tool / no-wrapper skill) |
| **0** | Command is a direct `aliyun <product>` call while the skill's wrapper script exists — **WRAPPER_BYPASS**, same severity as `Safety=0` |

See [§14.2.4 Wrapper Compliance (H)](#1424-wrapper-compliance-h-recommended-for-all-skills-with-wrappers) for detection rules and [§9 Anti-Patterns](#9-anti-patterns-banned) for the corresponding banned pattern.

## 4. Loop Flow

```
User Request
     │
     ▼
[0] Pre-flight (Orchestrator)
    - resolve env.* and user.* variables
    - pick skill, load its rubric from references/rubric.md
    - check §8 Security Constraints (no plaintext credentials in scope)
    - [Optional] 检索 failure-patterns.md 中与当前 skill 相关的已知模式
      → 将已知模式注入 Generator 上下文（预防性提示，非强制约束）
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
    - assess test accuracy + regression gate (§2.1)          │
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
| **WRAPPER_BYPASS** | `wrapper_compliance` = 0 → **ABORT**; same severity as `SAFETY_FAIL` (per AGENTS.md §15.8) |

## 6. Trace & Audit (mandatory)

Every GCL run MUST persist a JSON trace under `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`:

```json
{
  "skill": "alicloud-ecs-ops",
  "request": "<sanitized user request>",
  "rubric_version": "v1",
  "skill_version": "2.2.1",
  "version_source": "skill_md",
  "iterations": [
    {
      "iter": 1,
      "generator": {
        "command": "aliyun ecs DeleteInstance ...",
        "args": {...},
        "exit_code": 0,
        "result_excerpt": "...",
        "execution_path": "wrapper",
        "execution_path_skill": "alicloud-ecs-ops"
      },
      "critic": {
        "scores": {
          "correctness": 1, "safety": 1, "idempotency": 0.5,
          "traceability": 1, "spec_compliance": 1,
          "wrapper_compliance": 1
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

**Failure pattern extraction (recommended):** When a GCL iteration fails (SAFETY_FAIL, HALLUCINATION_ABORT, or rubric dimension < threshold), the Orchestrator SHOULD extract a structured failure pattern and append it to the trace:

```json
{
  "failure_pattern": {
    "category": "cli_parameter" | "skill_generation" | "cross_skill" | "runtime" | "token_efficiency",
    "skill": "alicloud-xxx-ops",
    "command": "aliyun xxx ...",
    "error": "MissingParam: ...",
    "fix": "Added .N suffix",
    "reusable": true
  }
}
```

Reusable patterns (reusable=true) are candidates for [failure-patterns.md](failure-patterns.md) — the centralized Reflexion memory. See [§15 Reflexion Integration](#15-reflexion-integration-layer-2--failure-pattern-memory) for details.

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
Must also include the **test accuracy / regression assessment** block from
[`gcl-critic-test-assessment-block.md`](gcl-critic-test-assessment-block.md) (accuracy over coverage — not coverage %).
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
  "test_assessment": {
    "tests_accurate": true|false,
    "accuracy_issues": ["stale/wrong assertion/masked failure/shallow test — concrete fixes"],
    "regression_required": true|false,
    "regression_suites": ["bash alicloud-<product>-ops/test-skillopt-backward-compatibility.sh", "..."],
    "regression_rationale": "why these suites accurately validate the change (or skip reason when regression_required=false)"
  },
  "suggestions": ["≤ 3 concrete, executable improvements"],
  "blocking": true|false
}
```

`blocking=true` when any rubric dimension fails **or** `test_assessment.tests_accurate=false` **or** `regression_required=true` but no green-run evidence is present in the trace/summary.

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
| `alicloud-ask-ops` | recommended | 3 | delete cluster / application |
| `alicloud-fc-ops` | recommended | 3 | delete function / service / trigger |
| `alicloud-eci-ops` | recommended | 3 | delete container group |
| `alicloud-cms-ops` | recommended | 3 | alarm rule delete |
| `alicloud-resourcemanager-ops` | recommended | 3 | resource folder / account move |
| `alicloud-agentrun-ops` | recommended | 3 | delete agent / application |
| `alicloud-oss-ops` | recommended | 3 | `DeleteBucket` / recursive `ossutil rm` / public ACL |
| `alicloud-nas-ops` | recommended | 3 | `DeleteFileSystem` / recycle-bin purge / mount-target delete |
| `alicloud-sms-ops` | recommended | 3 | `SendBatchSms` / delete sign or template |
| `alicloud-voice-ops` | recommended | 3 | batch/robot outbound / delete voice sign or template |
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
- ❌ **H checks skipped for safety-critical ops** — at minimum, parameter existence check is MANDATORY for all
  `required` and `recommended` skills per §8 → banned
- ❌ **Silent wrapper bypass** — When a skill has `scripts/*-skillopt-wrapper.sh` and the Generator
  invokes bare `aliyun <product>` directly, the Critic MUST score `wrapper_compliance = 0` and the
  loop MUST terminate with `WRAPPER_BYPASS` (per AGENTS.md §15.8). Silently passing the dimension or
  downgrading the violation defeats the safety purpose → banned

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
- **Phase 3-A** ✅ — LLM-based Critic implemented (mechanical/llm/hybrid modes, OpenAI-compatible endpoint, reuses existing skill prompt-templates). `gcl_runner.py:critique_llm()` + dispatch + hybrid merge; all 93 existing unit tests pass.
- **Phase 3-B** ✅ — `alicloud-gcl-runner-ops/scripts/gcl_cms_alarm_setup.py` (idempotent alarm creation; reads `crosscheck-report-*.json`; creates/updates 5 phantom alarms: GCL-Phantom-Pass, GCL-Phantom-Fail, GCL-Resource-Mismatch, GCL-Api-Errors, GCL-Timing-Anomaly; dry-run mode). `alicloud-cms-ops/references/rubric.md` enhanced from Phase 5 lean to Phase 3-B full (added §2 Phantom Alarm Schema, §4-5 worked examples). `alicloud-cms-ops/references/prompt-templates.md` enhanced (added Phantom alarm Generator/Critic rules + cross-skill delegation). `alicloud-cms-ops/references/gcl-cms-alarm-guide.md` (architecture, thresholds, cron integration, alert response playbook, dashboard). `alicloud-cms-ops/SKILL.md` bumped 2.1.0 → 2.2.0.
- **Phase 3-C** ✅ — **`alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py`** (cloud-side audit; `LookupEvents` re-verifies each `gcl-trace-*.json`; catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`). `alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck_test.py` (25 unit tests). `alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md`. `alicloud-actiontrail-ops/SKILL.md` bumped 1.0.0 → 1.1.0 with a lightweight `## Quality Gate (GCL)` cross-checker role section.
- **Phase 4** ✅ — wire rubric pass-rate to `alicloud-cms-ops` alarms (real incidents refine thresholds). `alicloud-gcl-runner-ops/scripts/gcl_passrate_reporter.py` (aggregates GCL traces → per-skill + per-dimension pass-rates → `aliyun cms PutCustomMetric` to `acs_custom_gcl` namespace). `alicloud-gcl-runner-ops/scripts/gcl_cms_alarm_setup.py` extended with 3 pass-rate alarms: GCL-Safety-Fail-Rate (P1), GCL-Correctness-Drop (P2), GCL-Traceability-Gap (P3). `alicloud-cms-ops/references/gcl-passrate-metrics-guide.md` (architecture, cron pipeline, alarm thresholds, dashboard). `AGENTS.md` §12.8: DTS added as 14th `required` skill.
- **Phase 5** ✅ — GCL rollout extended to all 8 core `recommended` skills (SLB, ACK, ASK, FC, ECI, CMS, ResourceManager, AgentRun). Each gets lean `references/rubric.md` + `references/prompt-templates.md` + `## Quality Gate (GCL)` section with `max_iter=3`. Meta / read-only skills (`ActionTrail`, `Billing`, `DAS`) remain `optional` per §8.
- **Phase 5 extension** ✅ — GCL rollout extended to 4 messaging/storage skills (`alicloud-oss-ops`, `alicloud-nas-ops`, `alicloud-sms-ops`, `alicloud-voice-ops`). Same artifact pattern (`rubric.md`, `prompt-templates.md`, Delegation Rules, `## Quality Gate (GCL)`); classified `recommended`, `max_iter=3` per §8.
- **Phase 6** ✅ — **Hallucination Detection Layer (H)** shipped. §14 added to spec; `alicloud-gcl-runner-ops/scripts/gcl_runner.py` extended with `--enable-hallucination-check` flag and `hallucination_detect()` function (parameter existence, JSON structure, WAF compliance). `alicloud-gcl-runner-ops/scripts/gcl_runner_test.py` extended with 25 H-specific tests. Every `required`/`recommended` skill now gets a `HALLUCINATION_ABORT` exit path in addition to the existing `SAFETY_FAIL`.
- **Phase 7** ✅ — **Lightweight Reflexion Integration** shipped. §15 added to spec; `docs/failure-patterns.md` created as centralized Reflexion memory; GCL trace schema extended with `failure_pattern` field; Pre-flight updated with optional pattern retrieval; `docs/post-update-self-review.md` extended with Round 3: Lessons Learned. Cross-session failure pattern learning enabled.
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
| 1.7.0 | 2026-06-15 | **Lightweight Reflexion Integration (§15)**: Cross-session failure pattern learning. New `docs/failure-patterns.md` (centralized Reflexion memory). GCL trace schema extended with `failure_pattern` field. Pre-flight updated with optional pattern retrieval. `docs/post-update-self-review.md` extended with Round 3: Lessons Learned. AGENTS.md Key References updated. |
| 1.8.0 | 2026-06-17 | **Wrapper Compliance (Phase 8)**: New `wrapper_compliance` dimension and `WRAPPER_BYPASS` termination condition (exit code 6) enforce AGENTS.md §15.8 at runtime. §14.2.4 adds H-layer check for bare `aliyun <product>` calls against skills with `scripts/*-skillopt-wrapper.sh`. Trace schema extended with `generator.execution_path` (`wrapper` \| `direct_aliyun` \| `sdk_jit` \| `data_plane` \| `other`) and `generator.execution_path_skill` fields. §9 adds anti-pattern: silent wrapper bypass. All 31 `alicloud-*-ops/references/rubric.md` updated with §2.4 Wrapper Compliance section. `alicloud-gcl-runner-ops/scripts/gcl_runner.py` adds `classify_execution_path()` and `_detect_wrapper_bypass()` functions; test suite extended with 5 new wrapper-compliance tests (87 total). |
| 1.9.0 | 2026-06-18 | **Phase 3-A (LLM Critic) implemented**: `--critic-mode` argument added (mechanical/llm/hybrid). `load_critic_template()` extracts template from `prompt-templates.md` with placeholder substitution. `critique_llm()` implements OpenAI-compatible HTTP call and JSON response parsing. `hybrid` mode merges mechanical hard gates (safety/credential/wrapper) with LLM nuanced scoring. Pre-flight validation added for `GCL_CRITIC_LLM_ENDPOINT` and `GCL_CRITIC_LLM_API_KEY`. All 93 existing unit tests pass (no breaking changes). `.env.example` updated with GCL environment variables. `README.md` updated with usage examples and roadmap. |
| 1.10.0 | 2026-06-21 | **Phase 5 extension**: §8 adds `recommended` classification for `alicloud-oss-ops`, `alicloud-nas-ops`, `alicloud-sms-ops`, `alicloud-voice-ops` (12 total `recommended` skills). Each skill ships `references/rubric.md` + `references/prompt-templates.md` + Delegation Rules + `## Quality Gate (GCL)` (`max_iter=3`). |

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

### 14.2.4 Wrapper Compliance (H) — RECOMMENDED for all skills with wrappers

Verify that the generated command is routed through the skill's
`scripts/*-skillopt-wrapper.sh`, not invoked as a bare `aliyun <product>` call.

| Source of Truth | Method | Coverage |
|---|---|---|
| Command string inspection | Look for `*skillopt-wrapper.sh` token OR detect bare `aliyun <product>` prefix | Mechanical, always available |
| Skill's `scripts/` directory | Check whether `*skillopt-wrapper.sh` exists for the targeted skill | Mechanical, file-system lookup |

**Algorithm (mechanical H):**

1. Tokenize command
2. If command contains `*skillopt-wrapper.sh` token → PASS (explicitly wrapper-routed)
3. Else if command starts with `aliyun <product>` and skill's wrapper exists → **FAIL** (`WRAPPER_BYPASS`)
4. Else if command is `data_plane` (redis-cli, mysql, mongosh) or `sdk_jit` (`go run`) → PASS (wrapper doesn't apply)
5. Else → PASS (no wrapper required for this path)

**Priority**: Inspect command string first → file-system lookup for wrapper existence → PASS if neither applies.

**Severity**: Same as destructive-op detection — `wrapper_compliance = 0` blocks the loop and exits with `WRAPPER_BYPASS` (exit code 6).

**Why a separate check from H**: This is structurally different from the other H checks (parameter existence, JSON structure, WAF) — it inspects **how** the command was invoked, not **what** it does. Adding it to the H layer catches bypasses at the earliest point (pre-execution). The Critic dimension `wrapper_compliance` (post-execution) provides a second line of defense.

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

---

## 15. Reflexion Integration (Layer 2 — Failure Pattern Memory)

> **Implementation**: [`alicloud-gcl-runner-ops/scripts/gcl_reflexion.py`](alicloud-gcl-runner-ops/scripts/gcl_reflexion.py)
> **Automation**: Patterns are extracted from (1) **GCL** traces in `gcl_runner.py main()` — **SAFETY_FAIL**, **MAX_ITER**, near-miss **PASS**; (2) **wrapper** allowlisted failures via `store-wrapper-lite` (plan **B**); (3) offline **L1 → L2 promote** via `promote-from-memory` (plan **C**, `make memory-maintain-apply`). See [`memory-strategy.md`](memory-strategy.md).
> **Report**: `docs/failure-patterns.md` is regenerated from the JSON store via `gcl_reflexion.py report`.
> **Three-layer architecture**: See [`docs/memory-strategy.md`](memory-strategy.md).

### 15.1 Motivation

| Gap | Current State | Reflexion Solution |
|-----|---------------|-------------------|
| CLI parameter errors repeat across sessions | §14 documents known patterns, but new patterns aren't auto-captured | Extract from GCL traces → persist in [failure-patterns.md](failure-patterns.md) |
| Skill generation repeats structural issues | Self-Review catches them per-session, but doesn't remember | Record in failure-patterns.md §2 →预防 next generation |
| Cross-skill composition failures | Documented in SKILL.md, but not centralized | Centralize in failure-patterns.md §3 |

### 15.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GCL Execution (per-session)                   │
│   [0] Pre-flight → [1] Generate → [1.5] H → [2] C → [3] Decide │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                     failure_pattern (in trace)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              gcl_reflexion.py (Automated Extraction)             │
│         reflexion_extract() → reflexion_store()                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│       .runtime/reflexion/reflexion.json (Deduped Store)         │
│   CLI Parameter | Skill Generation | Cross-Skill | Runtime | TE │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    reflexion_report() (standalone CLI)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│       docs/failure-patterns.md (Human & AI-readable, ≤200)     │
│   §1 CLI Parameter Errors | §2 Skill Generation | §3 Cross-Skill│
└──────────────────────────┬──────────────────────────────────────┘
                           │
                     Pre-flight retrieval (optional)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Prevention (next session)                           │
│   Inject known patterns into Generator context                  │
│   Agent avoids repeating known mistakes                          │
└─────────────────────────────────────────────────────────────────┘
```

### 15.3 Failure Pattern Schema

Each pattern in `failure-patterns.md` follows this structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | enum | ✅ | `cli_parameter` \| `skill_generation` \| `cross_skill` \| `runtime` \| `token_efficiency` \| `max_iter` \| `near_miss` |
| `skill` | string | ✅ | Skill name (e.g. `alicloud-ecs-ops`) |
| `command` | string | ❌ | The command that failed (for CLI errors) |
| `error` | string | ✅ | Error message or pattern description |
| `fix` | string | ✅ | How to fix or prevent this error |
| `count` | int | ✅ | Frequency count (pruned when < 3) |
| `reusable` | bool | ✅ | Whether this pattern is generalizable |

### 15.4 Maintenance Rules

| Rule | Description |
|------|-------------|
| **Token budget** | `failure-patterns.md` ≤ 200 lines. When exceeded, prune patterns with `count < 3` |
| **Dedup** | Before adding, check if pattern exists (match by `skill` + `command` + `error`). If exists, increment `count` |
| **Source** | GCL trace `failure_pattern`; wrapper plan **B** (`reflexion_extract_wrapper_lite`); plan **C** (`promote-from-memory` from L1); Self-Review Round 3 Lessons Learned |
| **Report sort** | Default is time-weighted score (`--sort-by weighted`). Use `--sort-by count` for raw frequency order |
| **Review** | Patterns are reviewed monthly. Patterns with `count ≥ 10` are candidates for promotion to §14 Hallucination Detection rules |

### 15.4.1 Wrapper → Layer 2 (plans B + C)

| Plan | Trigger | CLI / hook | Notes |
|------|---------|------------|-------|
| **B** | `skillopt_trace_end` failed + allowlisted API error | `gcl_reflexion.py store-wrapper-lite` (from `skillopt-core-lib.sh`) | Denylist: `Throttling`, `CircuitBreakerOpen`, bare `exit_code_*`; non-fatal |
| **C** | `make memory-maintain-apply` | `gcl_reflexion.py promote-from-memory` | Scan L1 `source=skillopt-wrapper` failures with `error_code`; promote when `count ≥ 3`; reconcile when `l1_count > l2_count` |

Optional: `GCL_REFLEXION_REPORT_ON_MAINTAIN=true make memory-maintain-apply` regenerates `docs/failure-patterns.md` after promote (default off). Sort via `GCL_REFLEXION_REPORT_SORT_BY=weighted|count`.

Allowlist (representative): `InvalidParameter`, `Forbidden`, `ResourceNotFound`, `QuotaExceeded`. L1 `memory_store_lite` persists `error_code` (from trace or API `Code`) for C aggregation.

### 15.4.2 Success patterns (R4)

| Item | Detail |
|------|--------|
| **Design** | [`alicloud-gcl-runner-ops/references/success-patterns.md`](alicloud-gcl-runner-ops/references/success-patterns.md) |
| **Store** | `.runtime/reflexion/success_patterns.json` (separate from `reflexion.json`) |
| **API** | `success_store()`, `success_retrieve()`, `success_report()`; `extract_success_pattern()` in `gcl_runner.py` on PASS |
| **Slot** | `{{success_patterns}}` via `memory_preflight.py` |

Only **hard-won PASS** (multi-iter, trap-informed, score recovery, etc.) is stored; ordinary PASS is skipped.

### 15.4.3 Cross-skill generalization (R5)

| Item | Detail |
|------|--------|
| **Design** | [`cross-skill-patterns.md`](alicloud-gcl-runner-ops/references/cross-skill-patterns.md) |
| **Normalize** | `normalize_error_pattern()` enriches `cli_parameter` rows with `normalized_key` |
| **Aggregate** | `reflexion_aggregate_generalized()` → `generalized_cli[]`; CLI `aggregate-generalized`; hooked from `make memory-maintain-apply` |
| **Retrieve** | `reflexion_retrieve()` tier 0 → 1 (`generalized_cli`) → 2 |

Distinct from orchestration `cross_skill` category (source→target chain failures).

### 15.4.4 Remediation tracking (R6)

| Item | Detail |
|------|--------|
| **Design** | [`remediation-tracking.md`](alicloud-gcl-runner-ops/references/remediation-tracking.md) |
| **Schema** | `remediated`, `remediated_at`, `total_opportunities`, `recent_failures`, `consecutive_successes` on tracked categories |
| **Confirm** | Dynamic K (2–5) consecutive PASS after preflight traps → `remediated=True` |
| **Relapse** | `reflexion_store` dedup hit resets streak and clears `remediated` |
| **Hook** | `gcl_runner.py` → `remediation_apply_from_trace(trace)` after success/failure store |

### 15.5 Pre-flight Retrieval (R2 — orchestrator)

During GCL Pre-flight (§4 step [0]) and every `skillopt_wrap()` call, the orchestrator loads unified R2 slots via `memory_preflight.py`:

```bash
# memory_preflight.py → {{recent_executions}} {{known_traps}} {{success_patterns}} {{strategy_hints}}
python3 alicloud-gcl-runner-ops/scripts/memory_preflight.py \
  --skill alicloud-ecs-ops --operation DeleteInstance --format slots
```

Known failure patterns for the current skill (tier 0 skill-specific → tier 1 `generalized_cli` → tier 2 `cross_skill`):

- MissingParam: Use `--InstanceId.1` (not `--InstanceId`) for RepeatList params
- InvalidParameter: Use JSON array format for `SecurityGroupIds`
- redis-cli not found: Add idempotent install probe before execution

**This is a HINT, not a CONSTRAINT** — the Generator should use these patterns to avoid known mistakes, but is not required to follow them if the context differs.

### 15.6 Relationship with Other GCL Layers

| Layer | Timing | Learning Scope | Reflexion Complement |
|-------|--------|----------------|---------------------|
| **GCL (Generator-Critic)** | Per-execution | Within-session | — |
| **H (Hallucination Detector)** | Pre-execution | Structural patterns | Reflexion feeds high-frequency H failures into §14 knowledge base |
| **ActionTrail cross-check** | Post-hoc | Cloud-side verification | Reflexion captures patterns from ActionTrail-detected anomalies |
| **Self-Review (§11)** | Per-update | Skill authoring | Reflexion captures patterns from Self-Review discoveries |
| **Reflexion Memory** | Cross-session | Persistent failure patterns | Aggregates from all above sources |

### 15.7 Anti-Patterns

- ❌ **Reflexion as mandatory gate** — Pattern retrieval is optional, not a blocking gate
- ❌ **Unbounded memory** — Hard cap at 200 lines; prune low-frequency patterns
- ❌ **Subjective pattern extraction** — Patterns must come from structured GCL traces or Self-Review records, not ad-hoc observations
- ❌ **Pattern hoarding** — If a pattern is promoted to §14 Hallucination Detection rules, remove from failure-patterns.md to avoid duplication
- ❌ **Concurrent writes** — `_save_store()` writes directly with `Path.write_text()`. If two `gcl_runner.py` instances run simultaneously, the second writer overwrites the first without merge. Current assumption: **only one runner instance at a time**.
- ❌ **Mid-write corruption** — The store file can be corrupted if a crash/power-loss occurs during `_save_store()`. On next load (`_load_store`), `json.JSONDecodeError` is caught, an empty store is used, and the runner continues with a `[WARN]` log. The corrupted file remains on disk for manual recovery.

### 15.X Time-Decay Maintenance

Patterns in the reflexion store include a `last_seen` timestamp that is updated each time a matching pattern is stored. The `reflexion_maintain()` function supports two-tier pruning:

| Tier | Rule | Parameter | Default |
|------|------|-----------|---------|
| Count-based | Remove patterns with `count < min_count` | `--min-count` | 3 |
| Time-decay | Remove patterns not seen in the **adaptive window** (below) | `--decay-days` | 0 (disabled) |

The time-decay window is **adaptive**: high-frequency patterns get longer retention.

```
waiting_seconds = 86400 × (decay_days + min(count, 90) × 7)
```

A pattern with `count=5` gets `35` extra days beyond `decay_days`. A pattern with `count=100` caps at `90 × 7 = 630` extra days. This prevents frequently-occurring patterns from being pruned during a quiet period.

```bash
# Dry-run with both count and time pruning
python gcl_reflexion.py maintain --min-count 5 --decay-days 90

# Apply: prune patterns with count < 3 OR outside adaptive window
python gcl_reflexion.py maintain --min-count 3 --decay-days 60 --apply
```

The report sort order uses a time-weighted score:

```
score = count × (1 − min(elapsed_days / decay_days, 1) × 0.5)
```

This ensures recent high-frequency patterns appear before older ones in `docs/failure-patterns.md`.

The report supports two sort strategies via `--sort-by`:

```bash
# Default: time-weighted (recency + frequency)
python gcl_reflexion.py report

# Raw frequency order (no recency bias)
python gcl_reflexion.py report --sort-by count
```

### 15.X Capture Scope

Patterns are extracted from three GCL exit statuses:

| Status | Capture Condition | Category | Purpose |
|--------|-----------------|----------|---------|
| `SAFETY_FAIL` | safety = 0 | `cli_parameter` / `runtime` | Destructive operations without confirmation |
| `MAX_ITER` | Iterations exhausted, any score < 0.5 | `max_iter` | Commands that repeatedly fail Critic |
| `PASS` (near-miss) | Any dimension < 0.8 | `near_miss` | Borderline passes with potential risk |

**MAX_ITER noise filter**: If all Critic dimensions are ≥ 0.5 but some are < 0.8, the pattern is **skipped** — this is a borderline pass, not a real failure pattern. Recording it would dilute the signal-to-noise ratio in `failure-patterns.md`. Only MAX_ITER outcomes with at least one dimension below 0.5 produce a `max_iter` pattern.

Previously only `SAFETY_FAIL` was captured. The expanded scope provides richer failure data for pre-flight injection (R2, planned).

---

## 16. Memory Index — Execution Memory Layer

> **Synopsis**: Every GCL trace is automatically indexed into a JSONL-based execution memory (`alicloud-gcl-runner-ops/scripts/gcl_memory.py`) at the end of `gcl_runner.py main()`. This layer serves as the first-tier execution record — grep-able, jq-able, human-tailable — before any database or observability pipeline is involved. **vs SkillOpt observability**: [memory-observability-relationship.md](memory-observability-relationship.md).

### 16.1 Architecture

```
┌───────────────────┐     persist_trace()     ┌──────────────────┐
│  gcl_runner.py    │ ──────────────────────►  │ audit-results/   │
│  (main loop)      │                          │ gcl-trace-*.json │
└────────┬──────────┘                          └──────────────────┘
         │
         │ memory_store(trace)   (non‑fatal)
         ▼
┌─────────────────────────────────────────────────────────┐
│  .runtime/memory/                                        │
│  ├── alicloud-ecs-ops/                                   │
│  │   ├── DescribeInstances.jsonl                          │
│  │   ├── DeleteInstance.jsonl                             │
│  │   └── ...                                              │
│  ├── alicloud-rds-ops/                                    │
│  │   ├── CreateDBInstance.jsonl                            │
│  │   └── ...                                              │
│  └── ...                                                  │
└─────────────────────────────────────────────────────────┘
```

Each JSONL file stores one JSON object per line, keyed by (skill, operation). The file is append-only; readers tail the last N lines for recent context.

### 16.2 Core Functions (gcl_memory.py)

| Function | Purpose | Returns |
|----------|---------|---------|
| `memory_store(trace)` | Index a completed GCL trace into the JSONL file for its (skill, operation) | `0` on success, `non-0` on failure (never raises) |
| `memory_retrieve(skill, operation, top_k)` | Return the most recent `top_k` entries for a skill/operation | `list[dict]` |
| `memory_maintain(memory_root, keep_days, apply)` | Prune entries older than `keep_days`; supports dry-run | `dict` with counts |
| `build_arg_parser()` + `main()` | Standalone CLI for maintenance | Exit code |

### 16.3 Entry Schema

Each JSONL line contains a `memory_entry` with:

| Field | Source | Description |
|-------|--------|-------------|
| `timestamp` | Autogenerated ISO 8601 UTC | When the trace completed |
| `skill` | `trace["skill"]` | e.g. `alicloud-ecs-ops` |
| `operation` | Explicit parameter, trace field, or auto‑extracted from command (falls back to `"unknown"`) | e.g. `DeleteInstance` |
| `trace_path` | Path to the persisted JSON trace | Relative to repo root |
| `gcl_status` | `trace["final"]["status"]` | PASS / MAX_ITER / SAFETY_FAIL / etc. |
| `iterations` | `trace.get("iterations", [])` | Integer count of GCL iterations |
| `rubric_pass` | `trace["final"]["status"] == "PASS"` | Boolean |
| `scores` | Per‑dimension scores from the final iteration | dict |
| `failure_pattern` | `trace.get("failure_pattern")` | Structured failure info (GCL full entries) |

**Wrapper lite entries** (`source="skillopt-wrapper"`, from `memory_store_lite()`): omit `trace_path` / `failure_pattern`; add `exit_code`, `duration_ms`, `execution_path`, `rubric_version="wrapper-lite"`, optional **`error_code`** (API/wrapper code when failed — omitted for `exit_code_*` noise).

### 16.4 Operation Auto-Extraction

The memory layer automatically extracts the operation from the trace or CLI command in this priority:

1. `trace["operation"]` — explicit field (highest priority)
2. `aliyun <product> <operation>` — second token after product
3. `*-skillopt-wrapper.sh <operation>` — first positional arg after wrapper
4. Data-plane tool name (redis-cli, mongosh, mysql, etc.)
5. `"unknown"` — fallback

### 16.5 Integration Points

| Point | File | What happens |
|-------|------|-------------|
| GCL runner | `alicloud-gcl-runner-ops/scripts/gcl_runner.py main()` | `memory_store(trace)` invoked after `persist_trace()`; non‑fatal on failure |
| SkillOpt wrapper | `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh` | `trace_end` → `memory_store_lite` (L1, with `error_code` when failed); plan **B** → `store-wrapper-lite` (L2, allowlist only) |
| Memory maintain | `scripts/runtime_cleanup.py` | `memory_maintain` + `reflexion_maintain` + **`promote-from-memory` (C)** + `success-report` + **`aggregate-generalized`** + trace TTL via `make memory-maintain-apply` |
| TTL cleanup | `alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py` | `--memory-keep-days` flag (default: 30 days) added to existing cleanup |
| Pass‑through | `scripts/runtime_cleanup.py` | `--retain` passes through to aiops-cruise cleanup, including memory TTL |
| CLI maintenance | `gcl_memory.py main()` | Standalone `python gcl_memory.py --maintain --apply` |

### 16.6 Non-Fatal Guarantee

The memory store call **never blocks** the runner's exit code. Failures are logged as `[WARN]`:

```
[WARN] memory_store returned 1 for trace gcl-trace-20260620-124114-0ca5a6.json
[WARN] memory_store failed: [Errno 2] No such file or directory
```

This ensures memory indexing is a best-effort enhancement, not a reliability risk.

### 16.7 Quality Gates

| Check | Criterion | Severity |
|-------|-----------|----------|
| M1 | `gcl_memory.py` exists under `alicloud-gcl-runner-ops/scripts/` | P0 |
| M2 | `gcl_memory_test.py` exists with ≥20 tests covering store/retrieve/maintain | P0 |
| M3 | `memory_store()` is called from `gcl_runner.py main()` after `persist_trace()` | P0 |
| M4 | Memory failures are non-fatal (log as `[WARN]`, never change exit code) | P0 |
| M5 | `memory_maintain()` supports dry-run (`apply=False`) | P1 |
| M6 | TTL cleanup integrated into aiops-cruise `runtime_cleanup.py` | P1 |
| **E2E-M1** | End-to-end integration test exists: `memory_store()` → `reflexion_extract()` → `reflexion_store()` → `reflexion_report()` validates full data flow | P0 |
| **LOG-M1** | All `_log()` output conforms to `[HH:MM:SS] [GCL-RUNNER\|REFLEXION] event=name key=value` format; validated by a format lint check | P1 |

### 16.8 Relationship with Other GCL Layers

| Layer | Timing | Data Source | Memory Complement |
|-------|--------|-------------|-------------------|
| **GCL trace** | Per-execution | Full JSON trace in `audit-results/` | Memory indexes key fields for quick grep/jq |
| **Reflexion Memory (§15)** | Cross-session | Structured failure patterns ≤200 lines | Memory provides full execution history (unbounded, TTL-bound) |
| **Hallucination Detector (§14)** | Pre-execution | Structural checks | Memory provides past execution context for flag tuning |

---

## 17. Strategy Memory — Layer 3 (Weekly Offline Review)

> **Synopsis**: Layer 3 aggregates Git artifact-evolution signals and Layer 1/2 runtime data on a **weekly** cadence only. Outputs `docs/strategy-baseline.json` + `docs/strategy-report.md`. GitHub-native notification: PR body with full report + Issue when `actionable_items > 0`.
> **Implementation**: `gcl_strategy.py`, `git_collect.py`, `strategy_github_notify.py`, `strategy_notify.py`, `strategy_synthesize.py`
> **Schedule**: `.github/workflows/doctor-weekly.yml` (Monday 02:00 UTC)
> **Architecture**: [`docs/memory-strategy.md`](memory-strategy.md) · GHA/Issue 数据流：[`docs/doctor-review-setup.md#github-actions--issue-数据流`](doctor-review-setup.md#github-actions--issue-数据流)

### 17.1 Execution Model

| Layer | Frequency | Trigger |
|-------|-----------|---------|
| Layer 1 / 2 | Per execution / failure | `gcl_runner.py`, wrappers |
| **Layer 3** | **Weekly** | GitHub Actions cron + `workflow_dispatch` |

Layer 3 **MUST NOT** run on the GCL runner hot path.

### 17.2 Core Functions

| Module | Function / CLI | Purpose |
|--------|----------------|---------|
| `git_collect.py` | `collect_git_signals()` | 7d Git commit classification |
| `gcl_strategy.py` | `weekly_aggregate()`, `weekly --apply` | Merge signals + diff baseline |
| `gcl_strategy.py` | `strategy_retrieve(skill, operation)` | R2 read-only `{{strategy_hints}}` |
| `strategy_synthesize.py` | `synthesize()` | Rule proposals (LLM optional) |
| `strategy_github_notify.py` | `github_notify()` | PR body + conditional GitHub Issue |
| `strategy_notify.py` | `build_strategy_ai_brief()` | AI Brief Markdown (shared) |

### 17.3 Quality Gates (L3-M1)

| Check | Criterion | Severity |
|-------|-----------|----------|
| S1 | No hot-path integration in `gcl_runner.py` | P0 |
| S2 | Notify skips when no actionable items | P0 |
| S3 | `gcl_strategy_test.py` ≥15 tests green | P0 |
| S4 | `strategy_retrieve` excludes repo-wide items from per-skill results | P0 |
| S5 | Git log parsing uses non-pipe field separator | P1 |
| S6 | LLM proposals sanitized before baseline write | P1 |

