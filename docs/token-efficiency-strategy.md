# Token Efficiency Strategy — Always-Loaded vs Lazy-Loaded Content

## 1. Overview

**Problem**: AGENTS.md is loaded on every agent session, but it contained detailed specifications only needed in specific scenarios. Every line consumes tokens, but most sessions never use most of it.

**AGENTS.md refactoring (validated baseline)**:

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| AGENTS.md lines | 499 | 289 | **-42%** |
| Est. tokens/session | ~9,980 | ~5,780 | **~4,200 tokens** |

**Core insight**: Not everything should be always-loaded. Extract detailed specs to `docs/` for lazy-load — daily sessions skip them, only loaded on explicit reference.

---

## 2. Core Principle — Always-Loaded vs Lazy-Loaded

### Decision Tree

```
Is this content needed in EVERY agent session?
├─ Yes → Keep in AGENTS.md (condensed form, rules only)
│   ├─ Must-have: quality gates, security constraints, variable conventions
│   └─ Condense: full tables → summary table + link to docs/
└─ No → Extract to docs/ + keep link in AGENTS.md
    ├─ Standard/checklist/spec → docs/xxx-standard.md
    └─ Runtime data (skill classification table, etc.) → maintain in existing doc
```

### File Layering

| Layer | File | Load Strategy | Content Type |
|-------|------|---------------|--------------|
| **L0** | `AGENTS.md` | Always-loaded | Rules, patterns, constraints, cross-skill orchestration |
| **L1** | `docs/*.md` | Lazy-load (on reference) | Full specs, checklists, verification scripts |
| **L2** | `skills/` internal `references/` | Lazy-load (per skill) | Product-specific operation details |

---

## 3. Optimization Patterns

### TE-A: Extract detailed specs to docs/

**Scenario**: AGENTS.md contains a complete standard/spec (with tables, examples, code blocks) only needed by specific operation types.

**Case**: §4 Diagnostic Logging Standard (49 lines) → `docs/diagnostic-logging-standard.md`

```markdown
<!-- Before: 49 lines of full spec in AGENTS.md -->
## 4. Diagnostic Logging Standard (MANDATORY for data-plane ops)
...
| PHASE | Meaning | Example |
| ERROR TYPE | Meaning | FIX |
| ExitCode | Meaning | Agent Action |

<!-- After: 3-line summary + link in AGENTS.md -->
All remote scripts use `[HH:MM:SS] [PHASE] key=value` format.
Full spec at [docs/diagnostic-logging-standard.md](docs/diagnostic-logging-standard.md).
```

| Metric | Value |
|--------|-------|
| Tokens saved/session | ~980 (49 lines × 20) |
| When saved | Only loaded on data-plane ops |

---

### TE-B: Eliminate cross-file duplication

**Scenario**: The same data maintained in multiple files, burning tokens on every load.

**Case**: GCL Skill classification table (35 rows) existed in both AGENTS.md and `docs/gcl-spec.md`.

```markdown
<!-- Before: 35-line full table in AGENTS.md + same 35 lines in gcl-spec.md -->
| `alicloud-ecs-ops` | required | 2 | delete/stop/reboot |
| `alicloud-redis-ops` | required | 2 | FLUSHALL / instance delete |

<!-- After: condensed stats + link to gcl-spec.md -->
Full 30+ skill table at [docs/gcl-spec.md §8](docs/gcl-spec.md#8-per-skill-defaults)
| Level | max_iter | Count |
| required | 2 | 17 |
```

| Metric | Value |
|--------|-------|
| Tokens saved/session | ~700 (35 lines × 20) |
| When saved | All sessions referencing gcl-spec |

---

### TE-C: Condense tables to summaries + link

**Scenario**: AGENTS.md contains a full checklist (multi-row, multi-column table), but the agent only needs to know the rounds exist.

**Case**: §11 Post-Update Self-Review full checklist (158 lines) → condensed summary table.

```markdown
<!-- Before: 158 lines of full spec in AGENTS.md -->
### Round 1: Structural Check
| C1 | Frontmatter | ... |
| C2 | Trigger & Scope | ... |
<!-- + C6 Token Efficiency sub-table -->
<!-- + Round 2: F1-F7 -->
<!-- + Self-Review Record -->
<!-- + 11.1 Link Validation (with full script) -->
<!-- + 11.2 Content Deduplication (with full script) -->
<!-- + Implementation Notes -->

<!-- After: 10-line summary + link -->
| Round | Content | Key Checks |
| **R1** | Frontmatter/Trigger/Variables/Token Efficiency | C1-C6 |
| **R2** | CLI validation/error codes/safety gates/links/dedup | F1-F7 |
Full spec at [docs/post-update-self-review.md](docs/post-update-self-review.md)
```

| Metric | Value |
|--------|-------|
| Tokens saved/session | ~3,160 (158 lines × 20) |
| When saved | Only loaded on skill update |

---

### TE-D: API queries over static tables (= TE-1)

> Already documented in `alicloud-skill-generator/SKILL.md`.

Use `aliyun` CLI to fetch versions/quotas instead of hardcoding static tables.

---

### TE-E: Compact error tables (= TE-3)

> Already documented in `alicloud-skill-generator/SKILL.md`.

One error code per row, ≤3 columns, single-line description.

---

### TE-F: Layer professional content (= TE-7)

> Already documented in AGENTS.md §10.1.

AIOps/FinOps → `references/advanced/`; SQL execution → mark as Security-Sensitive.

---

## 4. Audit Methodology — Scanning a Single Skill

### Step-by-Step

| Step | Action | Check Content |
|------|--------|--------------|
| 1 | Scan `SKILL.md` line count | >300 lines? Consider splitting to `references/` |
| 2 | Check all `references/*.md` files | Hardcoded versions/quotas? (TE-1) |
| 3 | Check Go SDK code blocks | Function-level docstrings? (TE-2) |
| 4 | Check error tables | >3 columns? 1 code per row? (TE-3) |
| 5 | Check JSON paths | Declared at file top? (TE-4) |
| 6 | Check YAML config | Duplicate fields that YAML anchors can eliminate? (TE-5) |
| 7 | Check `SKILL.md` vs `references/` | Content duplication? (TE-6) |
| 8 | Check professional content layering | AIOps/FinOps in `references/advanced/`? (TE-7) |
| 9 | Check AGENTS.md cross-references | Can SKILL.md references to AGENTS.md be condensed? |

### Automation Scripts

```bash
# Step 2: Check for hardcoded version numbers
grep -rnP '\d+\.\d+\.\d+' alicloud-{product}-ops/references/ | grep -v 'ALIBABA_CLOUD' | grep -v 'example' | grep -v 'docker'

# Step 3: Check Go docstrings
grep -rnP '^// .*' alicloud-{product}-ops/assets/code-snippets/ | head -20

# Step 4: Check error table column count
grep -rnP '^\|.*\|.*\|.*\|' alicloud-{product}-ops/references/troubleshooting.md

# Step 7: Check SKILL.md vs references/ duplication
for f in $(grep -rl '```bash' alicloud-{product}-ops/references/); do
  grep -oP '```bash\n.*?\n```' alicloud-{product}-ops/SKILL.md > /tmp/skill_code.txt
  grep -oP '```bash\n.*?\n```' "$f" > /tmp/ref_code.txt
  diff /tmp/skill_code.txt /tmp/ref_code.txt && echo "OK: $f" || echo "DUPLICATE: $f"
done

# Step 9: Check AGENTS.md references in SKILL.md
grep -n 'AGENTS.md' alicloud-{product}-ops/SKILL.md
```

---

## 5. Audit Checklist

### P0 — MUST PASS (severe waste, must fix)

| # | Check | Criteria | Fix |
|---|-------|----------|-----|
| P0-1 | Large always-loaded file | >400 lines in always-loaded context | Extract specs to docs/ (TE-A) |
| P0-2 | Cross-file duplicate table | Same table in ≥2 files | Keep one, others reference it (TE-B) |
| P0-3 | Hardcoded version/quotas | `\d+\.\d+\.\d+` version strings | Replace with `aliyun` query (TE-D) |

### P1 — SHOULD PASS (significant waste, recommend fix)

| # | Check | Criteria | Fix |
|---|-------|----------|-----|
| P1-1 | Full checklist in-context | >50 line table/checklist | Condense to summary + link (TE-C) |
| P1-2 | Go docstring | Function-level `/* ... */` comments | Replace with `#` line comments (TE-E) |
| P1-3 | Wide error table | >3 columns or multi-line descriptions | 1 code/row, ≤3 columns (TE-E) |
| P1-4 | Scattered JSON paths | Multiple JSON path strings dispersed | Declare at file top (TE-F) |

### P2 — NICE TO HAVE (minor waste, fix if convenient)

| # | Check | Criteria | Fix |
|---|-------|----------|-----|
| P2-1 | YAML duplication | 3+ occurrences of same fields | Use YAML anchors (TE-G) |
| P2-2 | SKILL.md vs references/ duplicate | Same code block appears twice | Delete copy from references (TE-H) |
| P2-3 | Content not layered | AIOps in references/ root | Move to advanced/ (TE-I) |

---

## 6. Trigger & Use

### Per-Skill Audit

In any session, say:

> "Audit skill X for token efficiency"

The agent will execute the §4 Audit Methodology and produce a report:

```
## Token Efficiency Audit: alicloud-redis-ops
### P0 Items
- [PASS] Cross-file duplication: GCL table already in gcl-spec.md
### P1 Items
- [FAIL] Error table: 6 columns, should be ≤3 → see TE-3
### P2 Items
- [PASS] YAML anchors: config has no duplication
### Score: 6/7 (86%) — Good
```

### Batch Scan

> "Audit all required GCL skills for token efficiency"

The agent will run the audit on all 17 GCL level=required skills and produce a summary report.

---

## 7. Appendix

### AGENTS.md Refactoring Before/After (baseline data)

| Dimension | Before | After | Method |
|-----------|--------|-------|--------|
| Total lines | 499 | 289 | TE-A/B/C |
| §4 Diagnostic Logging | 49 lines inline | 3-line summary + link | TE-A |
| §11 Self-Review | 158 lines inline | 10-line summary + link | TE-C |
| §12 Skill table | 35 lines (duplicate) | 8-line condensed + link | TE-B |
| Key References | 11 entries | 13 entries (added docs/ links) | — |
| Est. tokens/session | ~9,980 | ~5,780 | **-42%** |

### Related Docs

| Document | Description |
|----------|-------------|
| [AGENTS.md](../AGENTS.md) | Agent Guide — always-loaded rules |
| [gcl-spec.md](gcl-spec.md) | GCL full spec + skill classification table |
| [diagnostic-logging-standard.md](diagnostic-logging-standard.md) | Diagnostic log format standard |
| [post-update-self-review.md](post-update-self-review.md) | Post-update self-review spec |
| `alicloud-skill-generator/SKILL.md` | Token Efficiency TE-1~TE-7 definitions |