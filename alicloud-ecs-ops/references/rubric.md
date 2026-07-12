---
name: alicloud-ecs-ops-rubric
description: >-
  GCL (Generator-Critic-Loop) rubric for `alicloud-ecs-ops`. Used by the
  Critic to score Generator execution traces against five core dimensions
  plus three Aliyun-specific extensions. Required by `AGENTS.md` §12 (Phase 1
  pilot). Paired with `prompt-templates.md` in this directory.
license: MIT
metadata:
  skill: alicloud-ecs-ops
  rubric_version: "v1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - ../../../AGENTS.md
---

# ECS GCL Rubric (Pilot — Phase 1)

This rubric is the **single source of truth** the Critic uses to score every
runtime execution of `alicloud-ecs-ops`. It is intentionally aligned with
`AGENTS.md` §12.3 so that future skills can reuse the same dimension names
and thresholds.

> **Hard rule (inherited from `AGENTS.md` §12.3):**
> **Safety = 0 → ABORT immediately**, regardless of total score. No partial /
> "best-effort" return is allowed on a Safety failure.

---

## 1. Core Dimensions (mandatory)

### 1.1 Correctness

**Definition:** The resource id / state / config in `{{output.*}}` actually
matches the user's request.

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Resource id present, target state reached, key fields verified by a second `Describe*` call | Default target for all operations |
| **0.5** | Resource id present, but state not explicitly verified (no poll / no `Describe*` follow-up) | Acceptable for purely idempotent reads (e.g. `DescribeImages`) |
| **0** | Wrong id, wrong region, wrong resource, or `{{output.*}}` missing | Halt and request retry |

**Special requirement (delete / stop / reboot / ReplaceSystemDisk):**
Correctness MUST be **1.0** — verified by post-execution poll until terminal
state. A 0.5 here is treated as 0.

### 1.2 Safety

**Definition:** Destructive operations were confirmed or guarded. The user's
explicit assent and the right pre-conditions are both present in the trace.

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Pre-flight Safety Gate satisfied **and** the destructive command observed | Any `Delete*` / `Stop*` / `Reboot*` / `ReplaceSystemDisk` / `AuthorizeSecurityGroup` with `0.0.0.0/0` / `ResizeDisk` shrinking |
| **0** | Destructive op ran without Safety Gate OR with `0.0.0.0/0` rule on a high-risk port (22, 3389, 3306, 1433, 6379, 27017) | **ABORT — non-negotiable** |

**Per-operation Safety sub-rules for ECS:**

| Operation | Sub-rule (Score 1 requires ALL of the following) |
|---|---|
| `DeleteInstance` | (a) explicit user confirmation of `{{user.instance_id}}` AND `{{user.instance_name}}`; (b) instance state is `Stopped` OR `--Force true` is explicitly justified |
| `DeleteDisk` | (a) explicit user confirmation of `{{user.disk_id}}`; (b) `Status == Available` (detached) |
| `DeleteSnapshot` | (a) explicit user confirmation of `{{user.snapshot_id}}`; (b) snapshot not used as the source of any image (read `DescribeImages` if ambiguous) |
| `ReplaceSystemDisk` | (a) explicit user confirmation; (b) `Status == Stopped`; (c) snapshot of current system disk exists or was created in the same flow |
| `StopInstance` / `RebootInstance` | (a) instance state is `Running` (no-op stop is logged as a warning, not Safety=0) |
| `AuthorizeSecurityGroup` | (a) NO `SourceCidrIp=0.0.0.0/0` on `PortRange` ∈ {`22/22`, `3389/3389`, `3306/3306`, `1433/1433`, `6379/6379`, `27017/27017`}; if such a rule is requested, require an additional explicit user justification entry in the trace |
| `ResizeDisk` (shrink) | (a) explicit user confirmation that data loss is accepted; (b) filesystem already shrunk inside the OS (otherwise Safety=0) |
| `RunCommand` | (a) command content does not include `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `REDISCLI_AUTH`, or any `BEGIN ... PRIVATE KEY` block; (b) command does not `rm -rf /` or equivalent; (c) `Timeout` set to a finite value ≤ 3600s |
| `SendFile` | (a) target file path does not overwrite `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, or systemd unit files under `/etc/systemd/system/`, unless explicitly justified by the user |

**Read-only operations** (Safety gate N/A — no destructive side-effects):

| Operation | Sub-rule (read-only — Safety=1.0 by default; Safety gate not required) |
|---|---|
| `DescribeInstances` | Read-only: returns instance list/detail. No state mutation. Verify `{{user.region}}` is consistent with `--RegionId` and that any returned `InstanceId` is captured before follow-up writes. |
| `DescribeDisks` | Read-only: returns disk list/detail. No state mutation. Same region/account as the calling context. |
| `DescribeImages` | Read-only: returns image list/detail. No state mutation. Used as prerequisite for `ReplaceSystemDisk` / `RunInstances` image selection. |
| `DescribeSnapshots` | Read-only: returns snapshot list/detail. No state mutation. |
| `DescribeSecurityGroups` | Read-only: returns security group list/rule detail. No state mutation. Used as prerequisite for `AuthorizeSecurityGroup` / `RevokeSecurityGroup`. |
| `DescribeVpcs` | Read-only: returns VPC list/detail. No state mutation. |
| `DescribeVSwitches` | Read-only: returns VSwitch list/detail. No state mutation. Used as prerequisite for `CreateInstance` / network-bound ops. |
| `DescribeRegions` | Read-only: returns accessible region list. No state mutation. Used for credential / connectivity diagnostics. |

### 1.3 Idempotency

**Definition:** Retrying the same call will not cause duplicate side-effects.

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | The operation either is naturally idempotent (e.g. `Describe*`, `Start*` on a `Running` instance) OR carries an idempotency token / checks for prior state | Default for non-destructive ops |
| **0.5** | Operation is **not** naturally idempotent, but the trace shows it was preceded by a `Describe*` that would short-circuit a duplicate call | Acceptable for `Create*` with a uniqueness pre-check (e.g. `InstanceName`) |
| **0** | Pure side-effect op with no guard (`CreateInstance` without name uniqueness check, `RunInstances --Amount N` without a dry-run, etc.) | Reject; require retry with idempotency pre-check |

**Idempotency hot-spots for ECS:**

- `CreateInstance` / `RunInstances` — must check `DescribeInstances --InstanceName` before issuing.
- `CreateDisk` — must check `DescribeDisks --DiskName` before issuing.
- `CreateSecurityGroup` — must check `DescribeSecurityGroups --SecurityGroupName` before issuing.
- `AddTags` — natural idempotent (Tags are set, not appended).
- `AttachDisk` — natural idempotent (already attached returns success).

### 1.4 Traceability

**Definition:** Output is auditable. The full command, parameters, raw
response, and any error are captured in `./audit-results/gcl-trace-*.json`.

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Trace contains: full `aliyun` command (with all flags), exit code, raw JSON response (or error code+message), `RequestId`, and sanitized request | Required for destructive ops |
| **0.5** | Command + exit code present, but raw response truncated or `RequestId` missing | Acceptable for read-only `Describe*` |
| **0** | Trace only contains a one-line summary with no command or response | Reject |

**Mandatory trace fields for ECS:**

| Field | Required for | Notes |
|---|---|---|
| `iterations[].generator.command` | ALL | Full `aliyun ecs ...` command line |
| `iterations[].generator.args` | ALL | Map of flag → value (sanitized) |
| `iterations[].generator.exit_code` | ALL | Integer |
| `iterations[].generator.result_excerpt` | ALL | First ≤ 2KB of raw JSON |
| `iterations[].generator.request_id` | ALL `aliyun` calls | For support correlation |
| `iterations[].critic.scores` | ALL | The 5+3 dimension map below |
| `iterations[].critic.suggestions` | ALL retries | ≤ 3 actionable items |
| `iterations[].decision` | ALL | `RETRY` / `PASS` / `ABORT_SAFETY` / `MAX_ITER` |

### 1.5 Spec Compliance

**Definition:** Conforms to `references/core-concepts.md` constraints
(quotas, regions, dependencies, naming).

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Region is in the user's declared `{{user.region}}`; resource type is allowed by quota; cross-product deps (VPC, VSwitch, SG) verified to exist; naming follows `{{project}}-{{env}}-{{role}}-{{seq}}` if a `project` is declared | Default target |
| **0.5** | Region & quota OK, but cross-product deps were **assumed** without verification | Reject for prod; acceptable for dev |
| **0** | Region mismatch, quota would be exceeded, or naming violates a hard rule (e.g. upper-case characters in `{{user.instance_name}}` which ECS forbids) | Halt and request retry |

---

## 2. Aliyun-Specific Extensions (per `AGENTS.md` §12.3)

### 2.1 Region Compliance

**Definition:** The operation targets the region the user declared.

| Score | Meaning |
|:-----:|---------|
| **1** | `--RegionId` matches `{{user.region}}` exactly |
| **0.5** | `--RegionId` omitted but operation is region-agnostic (`DescribeRegions`, global read-only) |
| **0** | `--RegionId` differs from `{{user.region}}` (cross-region side-effect) |

### 2.2 Credential Hygiene

**Definition:** `ALIBABA_CLOUD_ACCESS_KEY_SECRET` (and any other secret) never
appears in any log line, command argument, or persisted trace.

| Score | Meaning |
|:-----:|---------|
| **1** | Trace was scanned; no `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `REDISCLI_AUTH`, `BEGIN.*PRIVATE KEY`, or RAM user password present |
| **0** | Any of the above appears in the trace or stdout |

**Sanitization helper** (suggested, not mandatory):

```bash
# Before writing trace to disk
sed -E 's/(ALIBABA_CLOUD_ACCESS_KEY_SECRET=)[^ ]+/\1<masked>/g' \
    -E 's/(REDISCLI_AUTH=)[^ ]+/\1<masked>/g' \
    -E 's/(Password=)"[^"]+"/\1<masked>/g'
```

### 2.3 Well-Architected (per `references/well-architected-assessment.md`)

**Definition:** The operation does not violate a relevant Well-Architected
pillar. Apply only when the operation is WA-sensitive (cost, security, or
stability).

| Pillar | What to check | Score 1 requires |
|---|---|---|
| **安全 Security** | `AuthorizeSecurityGroup` does not introduce a `0.0.0.0/0` rule on a high-risk port | See §1.2 Safety sub-rule |
| **稳定 Stability** | `DeleteInstance` / `DeleteDisk` not used for cleanup when a snapshot or recycle-bin route exists | Document the chosen path |
| **成本 Cost** | `CreateInstance` / `CreateDisk` not in a region outside the user's declared region (avoids cross-region cost leakage) | See §2.1 Region Compliance |
| **效率 Efficiency** | Batch ops (`RunInstances --Amount N`) preferred over N single `CreateInstance` when N ≥ 2 | Document N |
| **性能 Performance** | Instance type and disk category match the workload (e.g. `cloud_essd` for high-IOPS) | Optional unless user declared a workload profile |


### 2.4 Wrapper Compliance (per `AGENTS.md` §15.8 + GCL §3, §14.2.4)

**Definition:** Every `aliyun <product>` invocation against this skill
MUST be routed through `scripts/<product>-skillopt-wrapper.sh`, not
invoked as a bare CLI call. A direct call is a **silent bypass** that
strips self-repair, Langfuse tracing, and circuit-breaker protection.

| Score | Meaning |
|:-----:|---------|
| **1** | The command was routed through the skillopt wrapper (or a non-aliyun path: SDK / data-plane tool / no-wrapper skill) |
| **0** | The command is a direct `aliyun <product>` call while the skill's `scripts/*-skillopt-wrapper.sh` exists — **WRAPPER_BYPASS** |

**Wrapper-bypass detection rule:**
- If the command starts with `aliyun <product>` and the orchestrator's `PRODUCT_CLI[skill] == product`
  AND `scripts/*-skillopt-wrapper.sh` exists in the skill directory, then
  `wrapper_compliance = 0` and the decision is `WRAPPER_BYPASS` (exit code 6).
- Otherwise, `wrapper_compliance = 1`.

> **Note:** `PRODUCT_CLI` is defined in the GCL orchestrator (see `alicloud-gcl-runner-ops/references/gcl-execution.md`), not in this skill. It maps skill names to their CLI product names.

**Trace field (added in GCL v1.8.0):** `iterations[].generator.execution_path`
records one of `wrapper` | `direct_aliyun` | `sdk_jit` | `data_plane` | `other`.

---

## 3. Termination Thresholds (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All scores ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < `max_iter=2` | **RETRY** — inject Critic suggestions into Generator |
| Other dimension < threshold AND iter = `max_iter` | **MAX_ITER** — return best-so-far + unresolved rubric items |

Per-dimension thresholds (default, overridable per skill):

| Dimension | Threshold |
|---|---|
| Correctness | ≥ 0.5 (1.0 for destructive) |
| Safety | = 1 (absolute) |
| Idempotency | ≥ 0.5 |
| Traceability | ≥ 0.5 |
| Spec Compliance | ≥ 0.5 |
| Region Compliance | ≥ 0.5 |
| Credential Hygiene | = 1 (absolute) |
| Well-Architected | ≥ 0.5 (or N/A if op is not WA-sensitive) |

---

## 4. Worked Examples

> **Per AGENTS.md §8.2: all Examples below use read-only or safe-write ops only.**
> No `Delete*` / `Remove*` / `AuthorizeSecurityGroup 0.0.0.0/0` in any Example.

### Example 1: `DescribeInstances` PASS (read-only listing)

Use case: User asks "list all ECS instances in cn-hangzhou".

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 10",
    "exit_code": 0,
    "result_excerpt": "{\"Instances\":{\"Instance\":[{\"InstanceId\":\"i-bp1xxxx\",\"Status\":\"Running\"}]}}",
    "request_id": "A8E5..."
  },
  "critic": {
    "scores": {
      "correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
      "traceability": 1.0, "spec_compliance": 1.0,
      "region_compliance": 1.0, "credential_hygiene": 1.0,
      "well_architected": 1.0, "wrapper_compliance": 1.0
    },
    "blocking": false
  },
  "decision": "PASS"
}
```

**Why it passes:** `DescribeInstances` is read-only (Safety gate N/A); region matches; response includes `InstanceId` + `Status`; command routed through wrapper (or via SDK); `RequestId` present.

### Example 2: `CreateInstance` PASS (safe-write with PayByTraffic + immediate release)

Use case: User asks "spin up a minimal ECS for a 5-minute smoke test, then tear down".

**Cost guardrails (mandatory in the trace):**
- `InstanceType = ecs.s6-c1m1.small` (minimum spec, ~¥0.05/hr PayByTraffic)
- `RegionId = cn-hangzhou` (matches `{{user.region}}`)
- `ImageId` is verified available via `DescribeImages`
- `InternetChargeType = PayByTraffic` (no fixed monthly bandwidth cost)
- `InternetMaxBandwidthOut = 1` (minimum, caps egress cost)
- `DataDisks` empty (only system disk; no extra persistent cost)
- Plan: release immediately after smoke test via `DeleteInstance --InstanceId <id>` (which DOES require user confirmation per AGENTS.md §8.1)

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun ecs CreateInstance --RegionId cn-hangzhou --ImageId m-bp1xxxx --InstanceType ecs.s6-c1m1.small --InternetChargeType PayByTraffic --InternetMaxBandwidthOut 1 --SecurityGroupId sg-bp1xxxx --VSwitchId vsw-bp1xxxx",
    "exit_code": 0,
    "result_excerpt": "{\"InstanceId\":\"i-bp1newxx\",\"RequestId\":\"C9D4...\"}",
    "request_id": "C9D4..."
  },
  "preflight": {
    "quota_check": "DescribeAccountAttributes → InstanceQuotaCount remaining",
    "image_check": "DescribeImages → image status Available",
    "vpc_check": "DescribeVSwitches → VSwitch exists in target AZ",
    "user_confirmation": "User confirmed: 'spin up minimal ECS for 5-min smoke, will release immediately'"
  },
  "critic": {
    "scores": {
      "correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
      "traceability": 1.0, "spec_compliance": 1.0,
      "region_compliance": 1.0, "credential_hygiene": 1.0,
      "well_architected": 1.0, "wrapper_compliance": 1.0
    },
    "blocking": false
  },
  "decision": "PASS"
}
```

**Why it passes:** Pre-flight calls (`DescribeAccountAttributes` / `DescribeImages` / `DescribeVSwitches`) prevent quota/image/VPC errors; spec is minimal PayByTraffic so cost stays ~¥0.05/hr; user confirmation explicitly recorded; release plan documented.

### Example 3: `CreateInstance` RETRY for missing quota check

Trace (abbreviated):

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun ecs CreateInstance ...",
    "exit_code": 0
  },
  "critic": {
    "scores": {
      "correctness": 0.5, "safety": 1, "idempotency": 0,
      "traceability": 1, "spec_compliance": 0
    },
    "suggestions": [
      "No `DescribeAccountAttributes` call before CreateInstance — quota may have been exceeded",
      "No `DescribeInstances --InstanceName` pre-check — possible duplicate name side-effect"
    ],
    "blocking": true
  },
  "decision": "RETRY"
}
```

---

## 5. Anti-Patterns (banned — inherited from `AGENTS.md` §12.9)

- ❌ Critic scoring on vibes instead of this rubric → reject trace
- ❌ Critic seeing the original user request → reject trace
- ❌ Trace persisting `ALIBABA_CLOUD_ACCESS_KEY_SECRET` unredacted → reject + sanitize
- ❌ Safety=0 returning best-effort output → ABORT, not a retry
- ❌ Loop running > `max_iter=2` → bug, not a feature
- ❌ Critic mutating cloud resources → banned; Critic is read-only

---

## 6. Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Initial ECS GCL rubric (Phase 1 pilot). 5 core + 3 Aliyun-specific dimensions; per-op Safety sub-rules; worked examples. |
