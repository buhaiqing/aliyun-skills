---
name: gcl-rollout-spec
description: >-
  Specification for rolling out the Generator-Critic-Loop (GCL) adversarial
  quality gate (defined in `AGENTS.md` §12) into a generated or updated
  `alicloud-*-ops` skill. Explains the rubric + prompt-template + SKILL.md
  Quality-Gate-section pattern, per-skill `required` / `recommended` /
  `optional` classification (per `AGENTS.md` §12.8), per-op safety
  sub-rule format, regex hot-spot detection list, and cross-skill
  delegation. Use when generating a new skill that must include GCL,
  retrofitting an existing skill, or running the GCL Rollout workflow
  in `alicloud-skill-generator/SKILL.md`.
license: MIT
metadata:
  type: meta-reference
  applies_to: alicloud-skill-generator
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../AGENTS.md
  related:
    - alicloud-skill-template.md
    - prompt-library.md
    - governance-and-adversarial-review.md
---

# GCL Rollout Specification (Generator-Critic-Loop)

> **Authoritative source for the GCL contract is [`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).**
> This reference explains **how to implement** the contract in a generated
> skill. Read `AGENTS.md` §12 first; this file is the implementation
> playbook.

---

## 1. Why GCL Is Mandatory for Generated Skills

GCL is the adversarial quality gate that catches **silent destructive
failures** that single-shot pre-flight checks miss:

- A `DeleteVpc` that passes pre-flight but has active cross-skill ENIs
  (ECS / RDS / SLB).
- A `dropDatabase` that has a "backup exists" but the backup is 6 months
  old.
- A `DELETE /*` Elasticsearch request that the agent misreads as
  `DELETE /<single-index>`.
- A `GRANT DBA TO user` in PolarDB Oracle that passes the standard
  user confirmation but is a privilege-escalation path.

GCL separates the **Generator** (proposes the operation) from the
**Critic** (re-verifies independently using a different context, blind
to the original `{{user.request}}`). This is the **rubber-stamping
prevention** rule from `AGENTS.md` §12.2.

For destructive / data-plane / irreversible operations, GCL is **P0
must-pass** per `alicloud-skill-generator/SKILL.md` §"Agent-Ready Quality
Checklist" (P0 checks G1–G4 introduced in this rollout).

---

## 2. Classify the Skill — `required` / `recommended` / `optional`

Before generating GCL files, classify the skill using `AGENTS.md` §12.8
Per-Skill Defaults. The default classification:

| Side-effect level | Classification | Default `max_iter` | GCL mandatory? |
|---|---|---|---|
| **High** (delete / stop / RAM / KMS / DDL / drop / shutdown) | `required` | 2 | ✅ Yes (full rubric + prompt + SKILL.md section) |
| **Medium** (delete with dependency / modify) | `recommended` | 3 | ⚠️ Optional but recommended (lighter rubric) |
| **Low** (read-only audit / billing / monitoring) | `optional` | 5 | ❌ Skip (single-shot pre-flight only) |

Reference mapping (extract from `AGENTS.md` §12.8 as a guide):

- `required` examples: ECS, Redis, RDS, RAM, KMS, EIP, DTS, VPC, NAT,
  MongoDB, Elasticsearch, PolarDB×4.
- `recommended` examples: SLB, ACK, ACK-Serverless, FC, ECI, CMS.
- `optional` examples: ActionTrail, Billing, DAS, ResourceManager,
  AgentRun.

**Decision rule:** if the new skill's primary resource has a
`Delete*` / `Remove*` / `Detach*` / `Disable*` / `Drop*` / `Truncate*` /
`FLUSHALL*` / `ScheduleKeyDeletion*` / `Release*` operation, default
to `required`. Otherwise consult the existing table.

---

## 3. File Layout — the 3 GCL Artifacts

For `required` and `recommended` skills, the GCL rollout creates **3
files**:

```
alicloud-<product>-ops/
├── SKILL.md                                          # (existing; modify)
└── references/
    ├── rubric.md                                     # NEW
    └── prompt-templates.md                           # NEW
```

For `optional` skills, **no files are created** — single-shot pre-flight
is sufficient.

---

## 4. `references/rubric.md` Template

Every rubric has **5 core dimensions** + **3 Aliyun-specific extensions**,
inherited from `AGENTS.md` §12.3. The exact structure:

### 4.1 Frontmatter (REQUIRED)

```yaml
---
name: alicloud-<product>-ops-rubric
description: >-
  GCL rubric for `alicloud-<product>--ops` — <one-paragraph summary of
  the skill's destructive surface>. Phase 1 rollout, Nth skill.
license: MIT
metadata:
  skill: alicloud-<product>-ops
  api: <API version, e.g. ECS 2014-05-26>
  cli_applicability: <cli-first | dual-path | cli-only | sdk-only>
  rubric_version: "1.0.0"
  last_updated: "<YYYY-MM-DD>"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
---
```

### 4.2 Body Sections (in order)

1. **Opening rationale** (1 paragraph) — why this skill needs GCL, the
   most dangerous op, the cascade pattern, the data-plane risk class.
2. **Hard rules callout** — Safety = 0 → ABORT; Credential Hygiene = 0
   → ABORT; mandatory backup / confirmation / maintenance window as
   applicable.
3. **§1 Core Dimensions**:
   - §1.1 Correctness (1.0 required for `Delete*`).
   - §1.2 Safety — **per-op sub-rules table** (see §4.3).
   - §1.3 Idempotency.
   - §1.4 Traceability.
   - §1.5 Spec Compliance.
4. **§2 Aliyun-Specific Extensions**:
   - §2.1 Region Compliance (N/A for global services like RAM; mandatory
     for regional like ECS / RDS / VPC).
   - §2.2 Credential Hygiene — 6 standard patterns (ALIBABA_CLOUD_ACCESS_KEY_SECRET/ID,
     --password, --access-key-secret, --secret-key, env vars + value) + skill-specific
     additions (e.g. `AccountPassword`, `KeyMaterial`, `BEGIN PRIVATE KEY`).
   - §2.3 Well-Architected — 5 pillars (Security, Stability, Cost,
     Efficiency, Performance).
5. **§3 Termination Thresholds** — `max_iter` from `AGENTS.md` §12.8; PASS / MAX_ITER / SAFETY_FAIL.
6. **§4 Worked Examples** — at least 2: one PASS, one SAFETY_FAIL. Use
   the trace JSON format from `AGENTS.md` §12.6.
7. **§5 Anti-Patterns** — 4-6 banned patterns with ❌ markers.
8. **§6 Changelog** — 1.0.0 with date and brief summary.

### 4.3 Per-Op Safety Sub-Rules Table (the heart of the rubric)

For **every destructive / data-plane op** in the skill, add a row to
the table:

```markdown
| Operation | Sub-rule (Score 1) |
|---|---|
| `<Verb><Resource>` | (a) explicit user confirmation; (b) ... ; (c) ... |
```

Each row must have **at least 3 sub-rules**. Each sub-rule is a
**verifiable condition** the Critic can check (re-query API, parse trace,
inspect command line).

**Hard gate patterns** (sub-rules that are **absolute** — if violated,
Safety = 0):

- ECS: `AuthorizeSecurityGroup 0.0.0.0/0` on high-risk ports (22, 3389,
  6379, 3306, 5432, 1433, 23, 135, 445).
- Redis: `FLUSHALL` / `FLUSHDB` via data-plane; `KEYS *` in production;
  `DEL cache:*` (mass delete).
- RDS: `DELETE` / `UPDATE` without `WHERE` clause; `DROP DATABASE` /
  `DROP TABLE` without backup.
- RAM: `AdministratorAccess` policy attachment; `Action: "*"` +
  `Resource: "*"` trust policy; `Principal: acs:ram::*:*` trust.
- KMS: `PendingWindowInDays < 7`; key material in trace.
- EIP: `ReleaseEipAddress` on production EIP (5 detection methods).
- VPC: `DeleteVpc` without 4-step dependency cascade.
- NAT: `DeleteNatGateway` without 3-step cascade.
- MongoDB: `dropDatabase` / `dropCollection` without `mongodump`;
  `deleteMany({})` / `updateMany({})` (empty filter); `$out` / `$merge`.
- Elasticsearch: `DELETE /*` or wildcard; `_delete_by_query` with
  `match_all`; `_forcemerge max_num_segments=1`.
- PolarDB: `DeleteDBCluster` without final backup; `VACUUM FULL` /
  `ALTER SYSTEM SET` / `DROP USER ... CASCADE` / `GRANT DBA` per engine.

### 4.4 Data-Plane Command / Request Classification

For skills that have data-plane operations (Redis, MongoDB, ES, RDS,
PolarDB), include a **risk classification table**:

| Risk class | Commands / Endpoints | Sub-rule |
|---|---|---|
| READ-ONLY | `find`, `SELECT`, `GET /_search` | None |
| WRITE-KEY | `insertOne`, `UPDATE ... WHERE` | User confirmation + selective filter |
| WRITE-MANY | `updateMany` (with filter) | User confirmation + non-empty filter |
| DESTRUCTIVE-MASS | `dropDatabase`, `DELETE /*` | **Safety = 0** unless explicit justification |
| FATAL | `shutdownServer`, `_cluster/reroute` (no dry_run) | Hard block |

### 4.5 Detection Regex (for the Critic)

Provide **at least 5-10 regex patterns** the Critic can apply
independently:

```markdown
| Regex | Risk | Examples |
|---|---|---|
| `^drop\s+user\s+\S+\s+cascade` | DESTRUCTIVE-MASS | `DROP USER legacy_app CASCADE;` |
| `^alter\s+system\s+set\b.*scope\s*=\s*spfile` | CONFIG-MUTATION | `ALTER SYSTEM SET ... SCOPE=SPFILE;` |
| `match_all\s*:\s*\{\s*\}` | DESTRUCTIVE-QUERY (in `_delete_by_query`) | `{"query": {"match_all": {}}}` |
```

This is the **mechanical safety net** — the Critic applies the regex
list to every command, then the trace's `result_excerpt` confirms the
match.

---

## 5. `references/prompt-templates.md` Template

### 5.1 Frontmatter (REQUIRED)

```yaml
---
name: alicloud-<product>-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-<product>--ops`. Phase 1 rollout,
  Nth skill. Paired with `rubric.md`.
license: MIT
metadata:
  skill: alicloud-<product>-ops
  api: <API version>
  cli_applicability: <cli-first | dual-path | cli-only | sdk-only>
  rubric_version: "1.0.0"
  last_updated: "<YYYY-MM-DD>"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---
```

### 5.2 Body Sections (in order)

1. **Opening** — "Inherits structure from `AGENTS.md` §12.7 and prior
   pilots. <Skill>-specific additions: <list>."
2. **Generator template** (excerpt) — list hard rules the Generator
   MUST follow, with reference to the rubric's per-op sub-rules.
3. **Critic template** (excerpt) — list the regex list, the
   independent re-query pattern, the rubber-stamping prevention rule
   (Critic MUST NOT see `{{user.request}}`).
4. **Anti-Patterns** — 4-6 banned patterns.
5. **Changelog** — 1.0.0 with date and summary.

### 5.3 Generator Template (canonical form)

```text
You are the Generator in a GCL for Alibaba Cloud <Product>.

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- <op1>: <rule>
- <op2>: <rule>
- <cross-skill delegation>: <which skill to consult>
- All `{{user.*}}` placeholders MUST be resolved interactively.
- For data-plane ops: <engine-specific hot-spots>
```

### 5.4 Critic Template (canonical form)

```text
You are the Critic in a GCL for Alibaba Cloud <Product>. Read-only.

# Checks
- Apply the <N> regex hot-spots from `rubric.md` §<N>. ANY match classifies the op accordingly.
- For <op1>: independently re-query <Describe API> to verify ...
- For <op2>: parse the request to detect ...
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
- Do NOT reference the user's original request (rubber-stamping prevention).
```

---

## 6. `## Quality Gate (GCL)` SKILL.md Section

Insert into the generated SKILL.md between `## Operational Best
Practices` and `## See Also — Meta-Skill Rules` (or at end if no
Operational Best Practices section).

### 6.1 Template (minimal)

```markdown
---

## Quality Gate (GCL)

<Nth> rollout of GCL per [`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, Nth skill) |
| `max_iter` | 2 |
| Most-scrutinized | <op1>, <op2>, <op3> |
| Hard rule | <the single most-important rule> |

### Changelog
1.0.0 | <YYYY-MM-DD> | <Nth> rollout.
```

### 6.2 Frontmatter Bump

Each rollout bumps:

```yaml
  version: "<X.Y.Z+1>"          # increment minor or patch
  last_updated: "<YYYY-MM-DD>"  # today's date
```

### 6.3 Reference Directory Addition

Add 2 rows to the Reference Directory table (or create one if missing):

```markdown
| [GCL Rubric](references/rubric.md) | **Phase 1 rollout** GCL rubric (5 core + 3 Aliyun dimensions, <N> per-op Safety sub-rules, ...) |
| [GCL Prompt Templates](references/prompt-templates.md) | **Phase 1 rollout** Generator & Critic prompt templates (...) |
```

---

## 7. Cross-Skill Delegation Patterns

When the new skill's operations touch other skills' resources, the
rubric MUST delegate to the other skill's GCL rules. Common patterns:

| New skill | Delegates to | For operations |
|---|---|---|
| `alicloud-vpc-ops` | `alicloud-eip-ops` | `AssociateEipAddress` / `UnassociateEipAddress` / `ReleaseEipAddress` |
| `alicloud-vpc-ops` | `alicloud-nat-ops` | `CreateNatGateway` / `DeleteNatGateway` (when skill is split; otherwise in-skill) |
| `alicloud-nat-ops` | `alicloud-eip-ops` | EIP operations on NAT |
| `alicloud-rds-ops` / `alicloud-polar-*-ops` | (shared SQL WHERE-clause rule) | DDL / DML data-plane SQL |
| `alicloud-cms-ops` | (read-only) | alarm rules, dashboards — single-shot pre-flight |
| `alicloud-actiontrail-ops` | (read-only audit) | GCL is **not** required |
| `alicloud-billing-ops` | (read-only billing) | GCL is **not** required |

In the Generator template, add a hard rule:

```text
- EIP operations (`AssociateEipAddress` / `UnassociateEipAddress` /
  `ReleaseEipAddress`) MUST delegate to `alicloud-eip-ops` GCL rules
  (2-step unbind, DNS audit, production-EIP marker, InstanceType cross-check).
```

---

## 8. Worked Example — Generating GCL for `alicloud-slb-ops`

A user asks: "Add a new skill for Alibaba Cloud SLB (Server Load
Balancer)."

### Step 1: Classify

SLB has `DeleteLoadBalancer` / `DeleteListener` / `RemoveBackendServers`
— all destructive. Classify as **`recommended`** (medium side-effect,
default `max_iter=3`).

### Step 2: Create `references/rubric.md`

Open the new `alicloud-slb-ops/references/rubric.md` with:

- Frontmatter: `api: SLB 2014-05-15`, `cli_applicability: cli-first`.
- §1.2 Per-op sub-rules for: `CreateLoadBalancer`, `DeleteLoadBalancer`,
  `CreateListener`, `DeleteListener`, `AddBackendServers`,
  `RemoveBackendServers`, `SetBackendServers`, `ModifyLoadBalancerInternetSpec`.
- Hard gate: `RemoveBackendServers` requires (a) user confirmation of
  each backend server ID; (b) post-execution `DescribeHealthStatus`
  showing the load balancer still has ≥ 1 healthy backend (otherwise
  the LB will return 503 to all clients).
- Cross-skill delegation: `DeleteLoadBalancer` requires EIP unbinding
  (delegate to `alicloud-eip-ops`); ECS backend references (delegate to
  `alicloud-ecs-ops` for instance status check).

### Step 3: Create `references/prompt-templates.md`

Generator template excerpt:

```text
- `DeleteLoadBalancer` MUST verify zero listeners
  (`DescribeLoadBalancerListeners` returns empty) AND zero
  backend servers (`DescribeHealthStatus` shows 0 or 0 healthy)
  BEFORE issuing.
- `RemoveBackendServers` MUST verify the LB still has ≥ 1 healthy
  backend AFTER removal (otherwise 503 to all clients).
- All EIP operations delegate to `alicloud-eip-ops` GCL.
```

Critic template excerpt:

```text
- For `DeleteLoadBalancer`: independently re-query
  `DescribeLoadBalancerListeners` and `DescribeHealthStatus`.
- For `RemoveBackendServers`: verify post-execution
  `DescribeHealthStatus` shows ≥ 1 healthy backend.
```

### Step 4: Insert `## Quality Gate (GCL)` into SKILL.md

Place between `## Operational Best Practices` and `## See Also —
Meta-Skill Rules`. Table:

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 1, Nth skill) |
| `max_iter` | 3 |
| Most-scrutinized | `DeleteLoadBalancer` (cascade: listener + backend + EIP), `RemoveBackendServers` (≥ 1 healthy check) |
| Cross-skill delegation | `alicloud-eip-ops` for EIP; `alicloud-ecs-ops` for backend instance status |

### Step 5: Bump frontmatter

```yaml
  version: "1.0.0"      → "1.1.0"
  last_updated: "<date>" → "2026-06-04"
```

### Step 6: Add Reference Directory entries

Two rows pointing to `rubric.md` and `prompt-templates.md`.

### Step 7: Run 2-round self-review

Per `AGENTS.md` §11 (see [Post-Update Self-Review](../../docs/post-update-self-review.md)):

- **Round 1** (C1–C6): frontmatter, trigger/scope, variables, 5 core
  standards, Well-Architected, Token Efficiency.
- **Round 2** (F1–F6): CLI command verification, OpenAPI precision,
  error handling (≥ 10 codes), security gate, reference integrity,
  cross-skill delegation.

---

## 9. Common Pitfalls

- **❌ "Skip GCL for `recommended` skills."** — Even `recommended` skills
  need a GCL rollout, just with `max_iter=3` (not 2) and a leaner
  rubric. Only `optional` (read-only) skills skip GCL.
- **❌ "Reuse the ECS rubric verbatim."** — Each skill has a unique
  destructive surface. The rubric's per-op sub-rules MUST be skill-
  specific.
- **❌ "Forget to bump frontmatter."** — `version` and `last_updated`
  must be bumped in the SAME commit as the rollout.
- **❌ "Critic sees `{{user.request}}`."** — Rubber-stamping prevention
  rule from `AGENTS.md` §12.2.
- **❌ "GCL section in SKILL.md but no `rubric.md`."** — All 3 artifacts
  must be created together.
- **❌ "Re-classify an `optional` skill to `required` without reason."
  — Follow `AGENTS.md` §12.8; if a new destructive op is added to an
  optional skill, re-classify and create GCL files in a follow-up
  rollout.
- **❌ "Use the same 6 credential patterns for every skill."** — Add
  skill-specific patterns (e.g. `KeyMaterial` for KMS, `BEGIN PRIVATE
  KEY` for KMS, `AccountPassword` for RDS / RAM / PolarDB, `mongodb://user:<masked>@host` for MongoDB).

---

## 10. Changelog
1.0.0 | 2026-06-04 | Initial GCL rollout spec. Covers: classification (§2), file layout (§3), rubric template (§4), prompt-templates template (§5), SKILL.md section template (§6), cross-skill delegation (§7), worked example for SLB (§8), common pitfalls (§9). Bumps alicloud-skill-generator to v3.1.0.
