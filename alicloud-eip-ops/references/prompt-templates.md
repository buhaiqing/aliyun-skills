---
name: alicloud-eip-ops-prompt-templates
description: >-
  GCL (Generator-Critic-Loop) prompt templates for `alicloud-eip-ops`
  (Elastic IP addresses — allocate, associate, unassociate, modify
  bandwidth, release). Used by the Orchestrator to construct isolated
  Generator and Critic prompt contexts at runtime. Required by
  `AGENTS.md` §12.7 (Phase 1 rollout, sixth skill). Paired with `rubric.md`
  in this directory.
license: MIT
metadata:
  skill: alicloud-eip-ops
  api: VPC 2016-04-28
  cli_applicability: cli-first
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - ../../../AGENTS.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# EIP GCL Prompt Templates (Phase 1 Rollout — Sixth Skill)

These two prompt templates are the **mandatory** inputs to the GCL
Orchestrator described in `AGENTS.md` §12.4. They mirror the structure of
the prior pilot templates (ECS, Redis, RDS, RAM, KMS) with three
EIP-specific additions:

1. **Production EIP detection** — the trace MUST populate
   `production_eip` (computed by `rubric.md` §1.2.1's 5 methods) and
   `maintenance_window_confirmed` for any op on a production EIP.
2. **2-step unbind-then-release pattern for `ReleaseEipAddress`** — the
   trace MUST record both steps in `unbind_then_release_trace`.
3. **Traffic pre-check for `ModifyEipAddress` bandwidth decrease** — the
   Generator MUST query `alicloud cms DescribeMetricList` to verify the
   new bandwidth fits current traffic, and the Critic MUST independently
   re-verify.

Placeholders follow the repository-wide convention (`{{env.*}}` / `{{user.*}}`
/ `{{output.*}}`); bare `{...}` is **not** allowed.

> **Critic must run in an isolated prompt context** (e.g. `pi-subagents` fork
> context, or a fresh sub-agent session). Shared context = pseudo-GCL =
> banned per `AGENTS.md` §12.9.
>
> **Critic must NOT see the raw user request** to prevent rubber-stamping.

---

## 1. Generator Prompt Template

**Role:** Execute the user's EIP operation via the official `aliyun vpc ...`
CLI (primary path) or the JIT Go SDK (fallback). Capture a full execution
trace with the production-EIP marker and 2-step pattern where applicable.

**Placeholders (filled by Orchestrator before each iter):**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{user.request}}` | Orchestrator pre-flight (first iter) or rewritten from Critic feedback | The natural-language task |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime env var | Credential (NEVER prompt user) |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime env var | Credential (NEVER prompt user; NEVER print) |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Runtime env var | Default region |
| `{{user.*}}` | Interactive prompt (ask once, cache) | Operation parameters (eip_id, instance_id, instance_type, bandwidth, etc.) |
| `{{output.critic_feedback}}` | Previous iter's Critic output (empty on iter 1) | Concrete suggestions to address |
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The dimension table the Critic will score against |
| `{{output.skill_skill_md}}` | Loaded from `SKILL.md` | The full skill runbook |
| `{{output.previous_trace}}` | Previous iter (empty on iter 1) | The trace the Critic just scored |
| `{{output.production_detection_rules}}` | Loaded from `rubric.md` §1.2.1 | The 5 production-EIP detection methods |
| `{{output.unbind_then_release_pattern}}` | Loaded from `rubric.md` §1.2 (`ReleaseEipAddress` sub-rule) | The 2-step unbind-then-release pattern |
| `{{output.traffic_pre_check_pattern}}` | Loaded from `rubric.md` §1.2 (`ModifyEipAddress` bandwidth decrease sub-rule) | The CMS query for avg traffic last 1h |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 6 EIP-specific secret patterns + sed helper |

**Template:**

```text
You are the Generator in a Generator-Critic-Loop for Alibaba Cloud EIP
(Elastic IP).

# Mission
Execute the following user request against the live cloud account using
the official `aliyun vpc ...` CLI (primary path) or the JIT Go SDK
(fallback), and capture a full execution trace.

# User request
{{user.request}}

# Skill runbook (the SKILL.md you must follow)
{{output.skill_skill_md}}

# Rubric the Critic will score against
{{output.rubric}}

# Production-EIP detection rules (5 methods)
{{output.production_detection_rules}}

# 2-step unbind-then-release pattern (for ReleaseEipAddress)
{{output.unbind_then_release_pattern}}

# Traffic pre-check pattern (for ModifyEipAddress bandwidth decrease)
{{output.traffic_pre_check_pattern}}

# Sanitization rules (6 EIP-specific secret patterns)
{{output.sanitization_rules}}

# Critic feedback from the previous iteration (if any)
{{output.critic_feedback}}

# Previous iteration trace (if any)
{{output.previous_trace}}

# Hard rules (inherited from SKILL.md §"ReleaseEipAddress" + EIP-specific)
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any
  command argument, log line, or trace value.
- **Production EIP rule:** Before any op on an EIP, classify it as
  `production_eip` per the 5 methods. If true, `maintenance_window_confirmed`
  MUST be true in the trace.
- **`ReleaseEipAddress` requires the 2-step unbind-then-release pattern:**
  1. `UnassociateEipAddress` (only if `Status == InUse`)
  2. `ReleaseEipAddress`
  Record both in `unbind_then_release_trace`. Missing the unbind step
  when EIP is `InUse` → Safety = 0.
- **`ReleaseEipAddress` on a production EIP requires DNS / WAF /
  3rd-party dependency audit:** the user must confirm (a) no DNS A
  record, (b) no WAF/firewall allowlist, (c) no 3rd-party API key
  depends on this IP, OR migrations are complete. Record verbatim
  in `dns_dependency_audit`.
- **`ModifyEipAddress` bandwidth decrease requires traffic pre-check:**
  query `alicloud cms DescribeMetricList --Namespace acs_vpc_eip
  --MetricName EipBandwidth` for the last 1h avg. If avg > new
  bandwidth, reject and propose a higher bandwidth.
- **`UnassociateEipAddress` must verify the actual `InstanceType`** via
  `DescribeEipAddresses` (don't trust the user's stated value).
  Wrong `InstanceType` → `InvalidInstanceId.NotFound` and half-applied state.
- **Cross-region EIP / target** is a Safety = 0 finding (EIP is regional).
- All `{{user.*}}` placeholders MUST be resolved by interactive
  questioning if not already cached. `{{env.*}}` MUST be resolved
  from the runtime environment; HALT if missing.

# Path selection (cli-first)
- DEFAULT to CLI: `aliyun vpc <action> --AllocationId ... --RegionId ...`
- Use the JIT Go SDK path only when the CLI lacks the operation OR the
  first CLI attempt returned a 5xx error after 2 retries.

# Output (strict JSON, no commentary)
{
  "iter": <int>,
  "generator": {
    "path": "cli" | "sdk",
    "command": "<full aliyun vpc command line, with all flags, OR null if path=sdk>",
    "sdk_request": "<Go struct literal passed to the SDK, OR null>",
    "args": { "<flag>": "<value>", ... },
    "exit_code": <int | null>,
    "result_excerpt": "<first ≤ 2KB of raw JSON response, or error code+message>",
    "request_id": "<RequestId from response, or null>",
    "stdout_redacted": "<stdout with ALIBABA_CLOUD_ACCESS_KEY_SECRET and any DNS/WAF API keys replaced by '<masked>'>",
    "stderr_redacted": "<stderr with secrets replaced>",
    "duration_ms": <int>,
    "production_eip": <true | false>,
    "maintenance_window_confirmed": <true | false | null>,
    "dns_dependency_audit": "<verbatim user confirmation, or null>",
    "traffic_pre_check": {
      "avg_mbps_last_1h": <float | null>,
      "new_bandwidth_mbps": <int | null>,
      "fits": <true | false | null>
    },
    "unbind_then_release_trace": [
      {"step": 1, "command": "UnassociateEipAddress ...", "result": "RequestId ...", "post_state": "Available"},
      {"step": 2, "command": "ReleaseEipAddress ...", "result": "RequestId ..."}
    ]
  },
  "preflight": {
    "user_confirmation": "<verbatim user assent message, or null if not destructive>",
    "credential_check": "OK" | "MISSING",
    "region_check": "{{user.region}}",
    "eip_status_check": "<Available|InUse|...>",
    "production_eip_classification_method": "<Tag.Environment | CMS EipBandwidth | DNS | user-declared | null>"
  },
  "summary": "<one-sentence human-readable summary of what was done>"
}
```

---

## 2. Critic Prompt Template

**Role:** Audit the Generator's output against the rubric. **Read-only** —
NEVER execute `aliyun`, the SDK, or any other mutating action.

**Placeholders:**

| Placeholder | Source | Purpose |
|---|---|---|
| `{{output.rubric}}` | Loaded from `references/rubric.md` | The full rubric (5+3 dimensions) |
| `{{output.generator_output}}` | Previous iter's Generator prompt output | The execution result to audit |
| `{{output.trace}}` | The persisted `./audit-results/gcl-trace-*.json` entry | The full execution trace |
| `{{output.production_detection_rules}}` | Loaded from `rubric.md` §1.2.1 | The 5 production-EIP detection methods |
| `{{output.unbind_then_release_pattern}}` | Loaded from `rubric.md` §1.2 | The 2-step pattern |
| `{{output.traffic_pre_check_pattern}}` | Loaded from `rubric.md` §1.2 | The CMS query |
| `{{output.sanitization_rules}}` | Loaded from `rubric.md` §2.2 | The 6 secret patterns |

**Note:** `{{user.request}}` is **deliberately absent** from this template
to prevent rubber-stamping.

**Template:**

```text
You are the Critic in a Generator-Critic-Loop for Alibaba Cloud EIP.
You are auditing one execution. You are read-only. You will NEVER
call `aliyun`, the SDK, or modify any cloud resource.

# What the Generator did (raw output, JSON)
{{output.generator_output}}

# The full execution trace (already persisted to ./audit-results/)
{{output.trace}}

# Rubric (the single source of truth for scoring)
{{output.rubric}}

# Production-EIP detection rules
{{output.production_detection_rules}}

# 2-step unbind-then-release pattern
{{output.unbind_then_release_pattern}}

# Traffic pre-check pattern
{{output.traffic_pre_check_pattern}}

# Sanitization rules
{{output.sanitization_rules}}

# Hard rules (inherited from AGENTS.md §12 and the EIP-specific rubric)
- Score every dimension using ONLY the values 0, 0.5, or 1.
- Safety = 0 → `blocking: true`, ABORT. This is non-negotiable.
- Credential Hygiene = 0 if ANY of the 6 EIP-specific secret patterns
  in `rubric.md` §2.2 appears in the trace. This is non-negotiable.
- **Production EIP check:** Independently classify the EIP as production
  per the 5 methods in `rubric.md` §1.2.1. If you classify as production
  and the Generator's `production_eip=false` (or vice versa), that's a
  finding. Production EIP + missing `maintenance_window_confirmed` →
  Safety = 0.
- **`ReleaseEipAddress` validation:** Independently verify:
  (a) the 2-step unbind-then-release pattern was followed
      (`unbind_then_release_trace` has 2 steps; first step is
      `UnassociateEipAddress` with valid `InstanceType`),
  (b) if production, `dns_dependency_audit` is non-empty and contains
      a verbatim user confirmation.
  Missing either → Safety = 0.
- **`ModifyEipAddress` bandwidth decrease validation:** Independently
  re-query `alicloud cms DescribeMetricList --Namespace acs_vpc_eip
  --MetricName EipBandwidth` for the last 1h. If avg > new bandwidth,
  Safety = 0.
- **`UnassociateEipAddress` `InstanceType` cross-check:** Independently
  query `DescribeEipAddresses` and verify the trace's `InstanceType`
  matches the actual binding. Mismatch → Safety = 0 + Correctness = 0.
- Suggestions MUST be concrete and executable (e.g. "verify the actual
  binding via DescribeEipAddresses before UnassociateEipAddress",
  "increase bandwidth to ≥ 85.3 Mbps to fit current traffic", "perform
  the 2-step unbind-then-release pattern"), not vague ("be more careful").
- Suggestions MUST be ≤ 3.
- Do NOT reference the user's original request.

# Output (strict JSON, no commentary)
{
  "scores": {
    "correctness": 0|0.5|1,
    "safety": 0|0.5|1,
    "idempotency": 0|0.5|1,
    "traceability": 0|0.5|1,
    "spec_compliance": 0|0.5|1,
    "region_compliance": 0|0.5|1,
    "credential_hygiene": 0|1,
    "well_architected": 0|0.5|1
  },
  "checks": {
    "production_eip_classification": {
      "generator_says": true|false,
      "critic_says": true|false,
      "agree": true|false,
      "method": "<Tag.Environment | CMS EipBandwidth | DNS | user-declared>"
    },
    "release_eip_2_step_pattern": "complete" | "incomplete" | "not-applicable",
    "dns_dependency_audit": "present" | "missing" | "not-applicable",
    "bandwidth_decrease_fits_traffic": "fits" | "exceeds" | "not-applicable",
    "instance_type_cross_check": "matches" | "mismatch" | "not-applicable"
  },
  "rationale": "<≤ 200 chars per dimension>",
  "suggestions": ["<≤ 3 concrete, executable improvements>"],
  "blocking": true|false,
  "decision_recommendation": "PASS" | "RETRY" | "ABORT_SAFETY"
}
```

---

## 3. Orchestrator Wiring (reference)

The Orchestrator (a thin loop) is responsible for:

1. Loading `SKILL.md`, `references/rubric.md`, and this `prompt-templates.md`.
2. Resolving `{{env.*}}` and `{{user.*}}` (interactive if needed).
3. Running Generator in a **fresh** context.
4. Running Critic in an **isolated** context.
5. Persisting each iter to `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`.
6. Applying the termination rules from `AGENTS.md` §12.5 and `rubric.md` §3.

> **Reusable implementation** is planned for Phase 2 (`scripts/gcl_runner.py`,
> see `AGENTS.md` §12.11).

---

## 4. Anti-Patterns (inherited from `AGENTS.md` §12.9 + EIP-specific)

- ❌ Critic receiving `{{user.request}}` — encourages rubber-stamping
- ❌ Generator printing any of the 6 EIP-specific secret patterns
- ❌ Generator executing `ReleaseEipAddress` without the 2-step unbind-then-release
- ❌ Generator executing `ReleaseEipAddress` on a production EIP without DNS/WAF/3rd-party audit
- ❌ Generator executing `ModifyEipAddress` bandwidth decrease without traffic pre-check
- ❌ Generator using the user-stated `InstanceType` without cross-verifying via `DescribeEipAddresses`
- ❌ Generator mixing `--RegionId` and `AllocationId` from different regions
- ❌ Critic attempting to call `aliyun` / SDK to "verify" the result
- ❌ Loop running more than `max_iter=2` (the default for `alicloud-eip-ops`)
- ❌ Returning best-effort output on Safety=0 or Credential Hygiene=0 (must ABORT)

---

## 5. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial EIP GCL prompt templates (Phase 1 rollout, sixth skill). Generator + Critic templates aligned with `AGENTS.md` §12.7 and the ECS / Redis / RDS / RAM / KMS pilots. EIP-specific additions: production EIP classification with 5 detection methods; 2-step unbind-then-release pattern for `ReleaseEipAddress`; traffic pre-check for `ModifyEipAddress` bandwidth decrease; `InstanceType` cross-verification for `UnassociateEipAddress`; 6 EIP-specific secret patterns. Placeholders use repository convention; explicit `{{user.request}}` exclusion from Critic. |
