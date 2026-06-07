# GCL Quality Gate — RAM (Quick Reference)

> This file is the **RAM-specific quick reference** for the
> Generator-Critic-Loop (GCL) adversarial quality gate. The full rubric
> (5 core + 3 Aliyun dimensions, 18 per-op Safety sub-rules, 7-pattern
> privilege-escalation detection, 4 worked examples) lives in
> [`rubric.md`](rubric.md); the Generator/Critic prompt templates live
> in [`prompt-templates.md`](prompt-templates.md). SKILL.md links here
> for GCL Scope, Per-Op Safety Sub-Rules, RAM-Specific Additions,
> Termination, Trace Persistence, and Changelog.

## 1. Scope

This skill is the **fourth rollout** of the Generator-Critic-Loop (GCL)
adversarial quality gate defined in
[`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Every runtime execution of an `alicloud-ram-ops` operation MUST be wrapped
in a GCL loop before the result is returned to the user.

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1 rollout, fourth skill) |
| Default `max_iter` | **2** (inherited from `AGENTS.md` §12.8) |
| Operations covered | ALL operations in this SKILL.md (users, groups, roles, policies, access keys, MFA, password policy, STS AssumeRole) |
| Operations most scrutinized | `DeleteUser` (5-step cascade), `DeletePolicy` / `DetachPolicy` (privilege loss), `CreateAccessKey` (one-shot delivery), `UpdateAccessKey` to `Inactive`, `CreateLoginProfile` / `UpdateLoginProfile` (password hygiene), `BindMFADevice` / `UnbindMFADevice` / `DeleteVirtualMFADevice`, `SetPasswordPolicy` (loosening), `STS AssumeRole` (with `AdministratorAccess`) |

## 2. Why RAM Warrants Stricter GCL Rules

RAM is the **credential-management meta-layer** for the entire Alibaba
Cloud account. A bug here is a bug in *every* downstream skill. Three
consequences are reflected in the rubric and prompt templates:

1. **Credential Hygiene is double-strict** — not only the agent's own
   `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, but also the freshly-issued
   `AccessKeySecret` from `CreateAccessKey` and the `Password` from
   `CreateLoginProfile` / `UpdateLoginProfile`.
2. **`DeleteUser` requires a 5-step dependency cascade** (per
   [`operations/user-operations.md` §DeleteUser](operations/user-operations.md#operation-delete-ram-user)
   Pre-flight): `ListPoliciesForUser` → `DetachPolicyFromUser`,
   `ListGroupsForUser` → `RemoveUserFromGroup`, `ListAccessKeys` →
   `DeleteAccessKey`, `GetLoginProfile` → `DeleteLoginProfile`,
   `GetUserMFAInfo` → `UnbindMFADevice` → `DeleteVirtualMFADevice`.
3. **Privilege-escalation detection** runs across all RAM ops, not
   just `AttachPolicy` — attaching `AdministratorAccess`, modifying
   custom policies to `Action: "*"` + `Resource: "*"`, or setting
   `Trust Policy` with `Principal: {"RAM": ["acs:ram::*:*"]}` all
   require an extra user justification entry in the trace.

## 3. Per-Op Safety Sub-Rules (Quick Reference)

For the **full** sub-rule table (18 operations), see
[`rubric.md` §1.2](rubric.md). Highlights:

| Operation | Hard Safety condition (Score 1 requires) |
|---|---|
| `DeleteUser` | Explicit user confirmation; **5-step dependency cascade completed** |
| `DeletePolicy` | Explicit user confirmation of name + type; **NOT a system-managed policy** |
| `DetachPolicy` / `AttachPolicy` | Explicit user confirmation; **policy is NOT `AdministratorAccess`** without extra justification |
| `CreateAccessKey` | `< 2 keys`; **one-shot delivery**; **`--output json` (not `cols=`/`table`)** |
| `UpdateAccessKey` (to `Inactive`) | Explicit user confirmation; `GetAccessKeyLastUsed` called first |
| `CreateLoginProfile` / `UpdateLoginProfile` | **NOT setting `PasswordResetRequired=false` AND `MFABindRequired=false` simultaneously** |
| `BindMFADevice` | Device serial provided by user interactively |
| `SetPasswordPolicy` (loosening) | Does NOT reduce `MinimumPasswordLength` below 12 |
| `STS AssumeRole` | **Role does NOT have `AdministratorAccess`** without extra justification; `DurationSeconds` ≤ 3600s |

> **One-Shot Delivery Contract** (for `CreateAccessKey`/`CreateLoginProfile`): See [`rubric.md` §1.3](rubric.md).
> **5-Step Dependency Cascade** (for `DeleteUser`): See [`rubric.md` §1.4](rubric.md).
> **Privilege-Escalation Detection** (7 patterns): See [`rubric.md` §1.2.1](rubric.md).

## 4. RAM-Specific Additions

| Dimension | Threshold | Why it matters for RAM |
|---|---|---|
| **Region Compliance** | N/A (RAM is global) | RAM has no `--RegionId`; providing one is a sign the agent confused RAM with a regional service |
| **Credential Hygiene** | = 1 (**absolute, double-strict**) | Trace must contain no leaked `AccessKeySecret`, `Password`, or `SessionToken`. 11 RAM-specific secret patterns in `rubric.md` §2.2 |
| **Well-Architected** | ≥ 0.5 | Security sub-score **must** be ≥ 0.5 or the overall WA score is 0 |

## 5. Termination (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All dimensions ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < 2 | **RETRY** — inject Critic suggestions into next Generator prompt |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** — return best-so-far + unresolved rubric items |

## 6. Trace Persistence (mandatory)

Every GCL run MUST write `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`
with the schema defined in `AGENTS.md` §12.6. Apply RAM-specific sanitization
regex helpers in `rubric.md` §2.2 to scrub all 11 RAM-specific secret patterns.

## 7. Changelog (this section only)

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Fourth rollout: added GCL section + rubric + prompt templates. Default `max_iter=2`. |
| 2.2.0 | 2026-06-07 | Refactored per AGENTS.md §2 Content Separation Rule. Extracted ~1100 lines of per-operation execution detail into `references/operations/*.md` (5 files) + `references/api-response-reference.md` (JSON paths / Response Field Table / error taxonomy) + `references/prompt-examples.md` (Common Task Templates + Chinese interaction quick reference). SKILL.md now serves as a navigation + "What" index. |
| 2.3.0 | 2026-06-07 | Further refactor: GCL chapter extracted to this file. SKILL.md §Quality Gate now points here. |
