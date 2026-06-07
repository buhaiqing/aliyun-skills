# Aliyun Skills — Agent Guide

This repository is a Skills Farm for Alibaba Cloud operations — structured, AI-agent-parseable runbooks for cloud resource management.

Every section here is high-signal: agents must follow these patterns or they will produce broken or inconsistent skills.

---

## 1. Repo Layout

```
aliyun-skills/
├── alicloud-[product]-ops/       # One directory per Alibaba Cloud product
│   ├── SKILL.md                  # What to do (triggers, pre-flight, variables, execution overview)
│   ├── references/               # How to do (detailed CLI/SDK scripts, troubleshooting, monitoring)
│   │   ├── rubric.md             # MANDATORY (per skill) when skill is GCL `required`/`recommended` — see §12.3
│   │   └── prompt-templates.md   # MANDATORY (per skill) when skill is GCL `required`/`recommended` — see §12.7
│   ├── assets/                   # Example configs, eval queries
│   │   └── code-snippets/        # SDK-only skills: standalone `go run`-able Go scripts
│   └── scripts/                  # (rare — only redis-ops, topo-discovery)
├── alicloud-skill-generator/     # Meta-skill: generate new skills from OpenAPI specs
│   └── references/
│       ├── gcl-rollout-spec.md        # §12.11 Phase 2 — how to generate GCL files for a new skill
│       └── gcl-orchestrator-agent.md  # §12.11 Phase 2 — pi-subagents agent wrapping gcl_runner.py (legacy; use Delegation Rules instead)
├── alicloud-gcl-runner-ops/          # §12.11 Phase 2 — cross-skill GCL runner (shared skill)
│   └── scripts/
│       ├── gcl_runner.py             # Python 3.10+ standalone CLI; zero external deps
│       ├── gcl_runner_test.py        # unittest suite (60 tests, pure stdlib)
│       └── README.md                 # usage guide
├── audit-results/                # §12.6 — GCL trace storage (GITIGNORED; ephemeral)
├── alicloud-jit-setup.sh         # JIT Go SDK bootstrap (single script)
├── REQUIREMENTS.md               # Full requirements, architecture, technical specs
├── .env.example                  # Template for ALIBABA_CLOUD_ACCESS_KEY_* vars
├── docker-compose.yaml           # Docker sandbox profiles (dev/runtime/interactive)
└── Dockerfile                    # Go 1.24 + Python 3.10 base image
```

**Canonical skill directory structure** (from `alicloud-skill-generator`):

```
alicloud-[product]-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md                 # Architecture, limits, quotas, dependencies
│   ├── api-sdk-usage.md                 # Operation map, request/response, pagination
│   ├── cli-usage.md                     # `aliyun` CLI command map (omit for sdk-only)
│   ├── troubleshooting.md               # Error codes (≥10), diagnostics, recovery
│   ├── integration.md                   # Go bootstrap, env vars, credential rules
│   ├── monitoring.md                    # CMS metrics, dashboards, alarms (if applicable)
│   ├── well-architected-assessment.md   # MANDATORY — five-pillar assessment
│   ├── idempotency-checklist.md         # If retries/automation required
│   └── advanced/                        # Optional — lazy-loaded by Advanced Analytics section
│       ├── aiops-*.md                   #   AIOps: anomaly detection, prediction, auto-remediation
│       ├── finops-*.md                  #   FinOps: cost analysis, optimization
│       └── sql-execution.md             #   Security-Sensitive: SQL file execution (requires user confirmation)
├── assets/
│   ├── example-config.yaml
│   └── eval_queries.json                # MANDATORY — trigger accuracy eval queries
└── scripts/                             # Optional — only redis-ops, topo-discovery have these
```

**`advanced/` linking rule**: Files in `advanced/` referencing sibling files in `references/` MUST use `../` relative paths (e.g. `[CLI Usage](../cli-usage.md)`).

**Note**: Only `alicloud-redis-ops`, `alicloud-topo-discovery`, and `alicloud-gcl-runner-ops` have `scripts/`. `alicloud-elasticsearch-ops` also has `operations/` and `reports/` dirs. New skills follow the canonical structure above.

---

## 2. Content Separation Rule (MANDATORY)

**SKILL.md describes What to do, references/\* describes How to do.**

| File | Responsibility | Content |
|------|---------------|---------|
| `SKILL.md` | What | Triggers, Pre-flight Checks, variable conventions, execution overview, links to references/ |
| `references/*.md` | How | Full commands, scripts, exit code tables, log interpretation, failure recovery |

```markdown
<!-- SKILL.md — correct approach -->
#### Execution
Full script at [references/redis-cli-execution.md](references/redis-cli-execution.md)

| Step | Action | Description |
|------|--------|-------------|
| 1 | `aliyun r-kvstore describe-instance-attribute` | Get connection address |
| 2 | `aliyun ecs RunCommand` | Idempotent check redis-cli |

<!-- Wrong approach: embedding 500-line script in SKILL.md -->
```

---

## 3. Operation Design Pattern

Every operation MUST include these sections (in order):

### Pre-flight Checks
```markdown
| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| {precondition} | {verification command} | {normal value} | HALT — {human action} |
```

### Variable Convention
```markdown
| Variable | Meaning | Source |
|----------|---------|--------|
| `{{user.xxx}}` | User input | Ask once, reuse |
| `{{env.xxx}}` | Environment variable | NEVER ask user, HALT if missing |
| `{{output.xxx}}` | Previous step output | Parse from API response |
```

### Execution → Post-execution Validation → Failure Recovery

Every CLI script MUST include **structured diagnostic logs** (format at [Diagnostic Logging Standard](docs/diagnostic-logging-standard.md)).

All remote scripts use `[HH:MM:SS] [PHASE] key=value` format with phases `DIAG`/`INSTALL`/`EXEC`/`RESULT`/`WARN`/`ERROR`/`SUMMARY`. Errors use `[ERROR] TYPE={category} FIX={action}`. Full spec at [docs/diagnostic-logging-standard.md](docs/diagnostic-logging-standard.md).

---

## 5. Idempotent Provisioning Pattern

For operations requiring tools on target machines, use the idempotent pattern:

```bash
# 1. Probe
if ! command -v redis-cli &>/dev/null; then
  # 2. Install only if missing
  apt-get install -y redis-tools
fi
# 3. Execute (regardless of install outcome)
redis-cli -h host DEL key
```

Do not install unconditionally on every run. Log probe results with DIAG/RESULT phase.

---

## 6. Cross-Skill Composition

When a Skill depends on another Skill's capabilities (e.g. redis-ops needs ecs-ops RunCommand):

**Recommended**: Inline the necessary commands in SKILL.md, document the dependency in comments.

```markdown
# Execution — CLI  (uses aliyun ecs RunCommand; see alicloud-ecs-ops for advanced usage)
aliyun ecs RunCommand --RegionId ... --CommandContent "..."
```

**Not recommended**: Formal import/require of another skill (the agent may not have both loaded). Inline is the more reliable pattern.

---

## 7. Data Plane vs Control Plane

| Plane | Capability | Channel | Example Operations |
|-------|-----------|---------|-------------------|
| **Control Plane** | Instance lifecycle, config management | `aliyun {product}` API | Create/Delete/Describe/Modify instances |
| **Data Plane** | Data read/write, command execution | `redis-cli` / SDK direct | DEL, GET, SET, TTL, EVAL |

When existing APIs cannot cover data-plane operations, use **Cloud Assistant + CLI client** as an indirect approach:

```
redis-ops orchestration → ecs-ops RunCommand → target ECS executes redis-cli
```

---

## 8. Security Constraints

- **Never output credentials**: Replace `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in logs with `****`. JIT Go SDK scripts' `config` structs, `fmt.Println(config)`, and `log.Printf("%+v", ...)` can all leak credentials — prohibit such output.
- **Pass passwords via environment variables**: Use `REDISCLI_AUTH` instead of `-a <password>` to avoid exposure in `ps aux` or command history.
- **Delete operations MUST obtain explicit confirmation**: Include a confirmation row in the Pre-flight Checks table requiring the user to explicitly provide a resource identifier.

---

## 9. Quick Reference — Developer Commands

```bash
# Markdown linting
npx markdownlint-cli2 "alicloud-*/SKILL.md"

# Docker sandbox profiles (see docker-compose.yaml)
docker compose --profile dev up -d      # Development environment
docker compose --profile runtime up -d  # Minimal runtime
docker compose --profile interactive run interactive  # Interactive sandbox

# Generate new skill (use meta-skill)
"Generate alicloud-xyz-ops for product XYZ with operations: create, describe, modify, delete"

# JIT Go SDK setup (single script, runs 'go run' with alibabacloud-go SDKs)
./alicloud-jit-setup.sh
```

`pyproject.toml` declares `markdownlint-cli2` as the only Python dependency (uses `hatchling` build, Python 3.10).

---

## 10. Quality Gates

Every Skill MUST pass these five quality gates:

1. **Clear Boundaries**: SHOULD/SHOULD NOT triggers with delegation rules; trigger description optimized per agentskills.io guidelines (< 1024 chars)
2. **Structured I/O**: `{{env.*}}` (never ask user), `{{user.*}}` (ask once reuse), `{{output.*}}` (parse from API responses)
3. **Explicit Steps**: Pre-flight → Execute → Validate → Recover for **each** critical operation
4. **Failure Strategies**: Error taxonomy (≥10 product-specific codes), HALT vs retry logic, credential vs quota vs business error separation
5. **Single Responsibility**: One product, one primary resource; cross-product delegation documented, not duplicated

Additionally, every skill MUST include a **Well-Architected Framework** table (five pillars: Security, Stability, Cost, Efficiency, Performance) and pass the **P0/P1 checklist** defined in `alicloud-skill-generator/SKILL.md`.

### 10.1 Token Efficiency Requirements (P0 — MANDATORY)

> Minimize token consumption per Skill while preserving agent executability. Full definitions at `alicloud-skill-generator/SKILL.md` §Token Efficiency Requirements.

| Rule | Key Point | Savings |
|------|-----------|---------|
| **TE-1** API query > static table | Use `aliyun` to fetch versions/quotas, no hardcoding | ~200-500/file |
| **TE-2** Omit unnecessary docstrings | Go SDK: `#` comment instead of function-level docstring | ~100-200/func |
| **TE-3** Compact error tables | 1 error code per row, ≤3 columns | ~300-500/file |
| **TE-4** Centralized JSON paths | Declare at file top, don't repeat | ~50-100/file |
| **TE-5** YAML anchors | `example-config.yaml` use `&anchor` to eliminate duplication | ~200-400/file |
| **TE-6** Eliminate cross-file duplication | SKILL.md has full flow, references/ doesn't repeat | Varies |
| **TE-7** Layer professional content | AIOps/FinOps in `references/advanced/`; SQL execution marked Security-Sensitive with explicit confirmation | ~3,000-8,000/file |

**Non-compressible**: Agent-executable commands (params, JSON paths), error recovery logic, safety gates, credential rules, cross-skill orchestration chains.

> **Application-level optimization**: AGENTS.md's own always-loaded optimization strategy (TE-A/TE-B/TE-C) is documented at [docs/token-efficiency-strategy.md](docs/token-efficiency-strategy.md) — includes full audit methodology and checklist for scanning existing skills.

---

## 11. Post-Update Self-Review (MANDATORY)

> **Rule**: After every skill update, auto-run 2 rounds of self-review and fix all discovered issues.
>
> Full spec (check tables, verification scripts, dedup procedures, implementation notes) at [docs/post-update-self-review.md](docs/post-update-self-review.md)

| Round | Scope | Key Checks |
|-------|-------|-----------|
| **R1: Structural** | Frontmatter/Trigger/Variables/Token Efficiency | C1-C6, C6 MUST PASS |
| **R2: Content** | CLI validation/error codes/safety gates/link integrity/dedup/TODO.md sync | F1-F8, F5/F6/F8 MUST PASS |

其中新增 **F8** 检查项：

| 编号 | 检查项 | 说明 | 要求 |
|------|--------|------|------|
| **F8** | TODO.md 同步 | 本次所有新增/修改的功能是否已在 `TODO.md` 中更新为 `✅` | 每次更新必须同步更新 TODO.md |

> **F6（Token Efficiency）和 F8（TODO.md 同步）是强制通过项**，不通过不得提交。

Any issue found → fix one by one → all must pass before finishing.

---

## Key References

| Document | Description |
|----------|-------------|
| `README.md` / `README_CN.md` | Project overview, CLI setup, credential configuration |
| `REQUIREMENTS.md` | Skill requirements, architecture, technical specs |
| `alicloud-skill-generator/SKILL.md` | **Meta Skill generator** — full workflow, P0/P1 checklist, Token Efficiency rules |
| `alicloud-skill-generator/references/governance-and-adversarial-review.md` | Governance & adversarial review — 24+ pre-merge security/resilience/UX scenarios |
| `alicloud-skill-generator/references/alicloud-skill-template.md` | Canonical SKILL.md template |
| `alicloud-skill-generator/references/aiops-best-practices.md` | Multi-round self-review & critical reflection for fault diagnosis |
| `alicloud-skill-generator/references/execution-environment.md` | CLI installation, Go JIT bootstrap, credential configuration |
| `alicloud-skill-generator/references/user-experience-spec.md` | UX compliance requirements for all skills |
| [`docs/gcl-spec.md`](docs/gcl-spec.md) | **GCL full spec** — roles, rubric, loop flow, trace schema, prompt templates, anti-patterns, rollout roadmap, skill classification table |
| [`docs/post-update-self-review.md`](docs/post-update-self-review.md) | **Post-update self-review spec** — check tables, verification scripts, dedup procedures |
| [`docs/diagnostic-logging-standard.md`](docs/diagnostic-logging-standard.md) | **Diagnostic logging standard** — log format, phase prefixes, error types, exit codes |
| [`docs/token-efficiency-strategy.md`](docs/token-efficiency-strategy.md) | **Token efficiency optimization strategy** — always-loaded vs lazy-loaded methodology, audit checklist, use cases |
| `CLAUDE.md` | Entry point (content: `@AGENTS.md`) |

> **When specs conflict, `alicloud-skill-generator/SKILL.md` and its `references/` are the authoritative source.** AGENTS.md is a summary of these specs, not a replacement.

---

## 12. Generator-Critic-Loop (GCL) — Adversarial Quality Gate

> **Full spec**: [`docs/gcl-spec.md`](docs/gcl-spec.md)

**Core concept**: Enforce a Generator ↔ Critic adversarial loop on every cloud operation, scored against a quantified rubric. Complements [Post-Update Self-Review](docs/post-update-self-review.md) — §11 reviews skill authoring quality, §12 reviews runtime execution quality.

### Roles

| Role | Responsibility | Banned |
|------|---------------|--------|
| **Generator (G)** | Execute the cloud operation | Modify rubric, self-score |
| **Hallucination Detector (H)** | Pre-execution structural validity check | Execute API calls, mutate G's output |
| **Critic (C)** | Independently audit G's output | Call `aliyun`/SDK, mutate resources |
| **Orchestrator (O)** | Loop control, termination decision | Execute or score |

> **H role**: Added in GCL v1.5.0 (Phase 6). Catches LLM hallucinations in generated commands/JSON **before** execution.
> Full spec at [`docs/gcl-spec.md#14-hallucination-detection-layer-h`](docs/gcl-spec.md#14-hallucination-detection-layer-h).

### Rubric Dimensions (≥5)

| Dimension | Meaning | When Safety=0 |
|-----------|---------|---------------|
| **Correctness** | Resource ID/state/config matches request | — |
| **Safety** | Destructive operations confirmed or protected | **Immediate ABORT** |
| **Idempotency** | Repeating the call has no side effects | — |
| **Traceability** | Output is auditable (command, params, response) | — |
| **Spec Compliance** | Complies with core-concepts.md constraints | — |

### Termination Conditions (first match wins)

| Condition | Action |
|-----------|--------|
| **PASS** | All dimensions pass → return G's result |
| **MAX_ITER** | Reached max_iter → return best-so-far + unresolved issues |
| **SAFETY_FAIL** | Safety=0 → **ABORT**, no partial result |
| **HALLUCINATION_ABORT** | H detected unresolved hallucinations → **ABORT**, return hallucination report (since v1.5.0) |

### Skill Classification (GCL Level + max_iter)

Full 30+ skill table at [docs/gcl-spec.md §8 Per-Skill Defaults](docs/gcl-spec.md#8-per-skill-defaults):

| Level | max_iter | Skill Count | Key Risk |
|-------|:--------:|:-----------:|----------|
| **required** | 2 | 17 | Data destruction / instance deletion / irreversible operations |
| **recommended** | 3 | 8 | Resource deletion / configuration changes |
| **optional** | 5 | 5 | Read-only audit / diagnostic |

**Anti-Patterns (banned)**: Shared context G+C, subjective scoring, unbounded loop, Critic seeing user request, silently downgrading on Safety fail, trace not persisted, Critic mutating resources, trace leaking secrets.

**Trace audit**: Every GCL run MUST persist a JSON trace to `./audit-results/gcl-trace-*.json` (gitignored).