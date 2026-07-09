---
name: alicloud-actiontrail-ops-rubric
description: >-
  GCL (Generator-Critic-Loop) rubric for `alicloud-actiontrail-ops`. Used by
  the Critic to score Generator execution traces. Also defines cross-checker
  fidelity when verifying other skills' GCL traces via ActionTrail events.
  Required by `AGENTS.md` §12. Paired with `prompt-templates.md`.
license: MIT
metadata:
  skill: alicloud-actiontrail-ops
  api: Actiontrail 2020-07-06
  cli_applicability: dual-path
  gcl_level: optional
  max_iter: 5
  rubric_version: "v1.0.0"
  last_updated: "2026-06-21"
  parent: ../../AGENTS.md
  references:
    - prompt-templates.md
    - gcl-crosscheck.md
    - ../../AGENTS.md
---

# ActionTrail GCL Rubric

This rubric scores **ActionTrail product operations** (trail lifecycle,
event lookup, delivery config) and **GCL cross-check runs** that call
`gcl_actiontrail_crosscheck.py` against `./audit-results/gcl-trace-*.json`.

> **GCL classification** (`docs/gcl-spec.md` §8): `optional`, `max_iter=5`.
> **Safety = 0 → ABORT immediately** (inherited from `AGENTS.md` §12.3).
> **Dual role:** Most invocations are read-only (`LookupEvents`, `DescribeTrails`).
> `DeleteTrail` is the primary Safety-critical operation. Cross-checker runs
> must not mutate cloud resources — only read ActionTrail events.

---

## 1. Core Dimensions (mandatory)

### 1.1 Correctness

**Definition:** Trail state / event results in `{{output.*}}` match the user's request.

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Target trail or event set verified by follow-up `DescribeTrails` / paginated `LookupEvents` | Default for mutating ops |
| **0.5** | Read-only query returned plausible JSON but no explicit field validation | Acceptable for broad `LookupEvents` scans |
| **0** | Wrong trail name, wrong time window, empty result when events expected, or missing `{{output.*}}` | Halt and retry |

**Special requirement (`DeleteTrail`):** Correctness MUST be **1.0** — post-delete
`DescribeTrails` confirms trail absent. A 0.5 is treated as 0.

### 1.2 Safety

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Pre-flight Safety Gate satisfied for destructive ops; cross-check runs are read-only | Default |
| **0** | `DeleteTrail` / `DeleteDataEventSelector` without explicit user confirmation; cross-check script invoked with mutating side effects | **ABORT** |

**Per-operation Safety sub-rules:**

| Operation | Sub-rule (Score 1 requires ALL) |
|---|---|
| `DeleteTrail` | (a) explicit user confirmation naming `{{user.trail_name}}`; (b) `DescribeTrails` pre-check confirms trail exists; (c) user warned that audit delivery stops for that trail |
| `DeleteDataEventSelector` | (a) explicit user confirmation; (b) `DescribeTrails` shows selector present |
| `StopLogging` | (a) explicit user confirmation; (b) user warned that new events will not be delivered |
| `LookupEvents` / cross-check | Read-only — Safety = 1 if no mutating `aliyun` commands in trace |
| `gcl_actiontrail_crosscheck.py` | MUST NOT pass flags that mutate resources; `--trace` / `--trace-dir` only |

### 1.3 Idempotency

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Naturally idempotent (`Describe*`, `LookupEvents`, `GetTrailStatus`) OR pre-check short-circuits duplicate | Default for reads |
| **0.5** | `CreateTrail` preceded by `DescribeTrails` name-uniqueness check | Acceptable |
| **0** | `CreateTrail` without checking 5-trail-per-region quota / existing name | Reject |

**Hot-spots:**

- `CreateTrail` — check `DescribeTrails` for name collision and quota (max 5 trails/region).
- `StartLogging` — idempotent if already logging; verify via `GetTrailStatus`.

### 1.4 Traceability

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Full `aliyun actiontrail ...` command, exit code, `RequestId`, result excerpt (≤ 2KB) | Required for `DeleteTrail` and cross-check reports |
| **0.5** | Command + exit code; truncated response acceptable for large `LookupEvents` pages | Read-only queries |
| **0** | Summary only, no command line | Reject |

**Mandatory trace fields:**

- `iterations[].generator.command` — full CLI with filters (`--StartTime`, `--EventName`, etc.)
- `iterations[].generator.request_id` — from ActionTrail / OpenAPI response
- Cross-check: path to input `gcl-trace-*.json` and finding list (`PHANTOM_PASS`, etc.)

### 1.5 Spec Compliance

| Score | Meaning | When to apply |
|:-----:|---------|---------------|
| **1** | Trail naming (6–36 chars, lowercase start), ISO 8601 UTC timestamps, region rules followed | Default |
| **0.5** | Non-standard time format but parseable; user confirmed | Minor deviation |
| **0** | Trail name violates limits; `LookupEvents` window > 90 days without trail delivery path | Reject |

---

## 2. Aliyun-Specific Extensions

### 2.1 Time Range Compliance (`LookupEvents`)

- **Score 1:** `--StartTime` / `--EndTime` use cross-platform ISO 8601 UTC (see `AGENTS.md` §14.6 dual-branch `date` pattern).
- **Score 0:** Single-platform `date -d` only (breaks macOS) or missing bounds on large scans.

### 2.2 Credential Hygiene

- **Score 1:** No `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in commands, logs, or traces; AccessKey IDs in filters are expected and allowed.
- **Score 0:** Secret exposed anywhere in the GCL lifecycle.

### 2.3 Wrapper Compliance

Per `AGENTS.md` §15.8 — prefer `actiontrail-harness-wrapper.sh`.

| Score | Meaning |
|:-----:|---------|
| **1** | Routed through harness/skillopt wrapper (or SDK JIT fallback documented) |
| **0** | Direct `aliyun actiontrail` while wrapper exists — **WRAPPER_BYPASS** |

### 2.4 Cross-Check Fidelity (when running `gcl_actiontrail_crosscheck.py`)

| Score | Meaning |
|:-----:|---------|
| **1** | Script exit 0; report lists each trace with verdict; `PHANTOM_*` findings include event evidence or explicit `API_ERROR` |
| **0.5** | Partial trace dir scan; some traces skipped with documented reason |
| **0** | Cross-check claimed PASS while script stderr shows LookupEvents failure |

---

## 3. Pass Threshold

| Context | Rule |
|---------|------|
| Product ops (read-only) | All dimensions ≥ 0.5; Safety = 1 |
| Product ops (`DeleteTrail`) | Correctness = 1, Safety = 1, others ≥ 0.5 |
| Cross-checker run | Cross-check fidelity ≥ 0.5; Safety = 1; no mutating commands |

---

*Aligned with `AGENTS.md` §12.3 and [`gcl-crosscheck.md`](gcl-crosscheck.md).*
