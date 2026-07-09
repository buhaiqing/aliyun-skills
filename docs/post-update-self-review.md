# Post-Update Self-Review (MANDATORY)

> Extracted from `AGENTS.md` §11 — detailed specification.

**Rule**: Every time a skill file is updated, auto-run 2 rounds of self-review and fix all discovered issues.

Triggered by any change under `alicloud-[product]-ops/` (SKILL.md, references/*, assets/*).

---

## Round 1: Structural Check

Audit against the [P0 — MUST PASS checklist](../alicloud-skill-generator/SKILL.md#p0--must-pass) in `alicloud-skill-generator/SKILL.md`. **Focus:**

| # | Check | Content |
|---|-------|---------|
| C1 | Frontmatter | `name`, `description`, `license`, `compatibility`, `metadata` complete? `description` < 1024 chars? |
| C2 | Trigger & Scope | `SHOULD Use` / `SHOULD NOT Use` present? Trigger conditions precise? |
| C3 | Variables | `{{env.*}}` vs `{{user.*}}` correctly classified? Any hardcoded secrets? |
| C4 | Five Core Standards | Quality gates table present and complete? |
| C5 | Well-Architected | Five-pillar table present? |
| C6 | Token Efficiency | **MUST PASS**: TE-1~TE-7 all satisfied? Else **BLOCK** |

### Token Efficiency Verification (C6 sub-check — strict)

C6 is a **MUST PASS** gate, not a suggestion. Verify each rule:

| TE Rule | Check Method | On Failure |
|---------|-------------|------------|
| TE-1 | Hardcoded version/quotas in references/? | Replace with `aliyun` query command |
| TE-2 | Function-level docstrings in Go SDK blocks? | Delete docstring, use `#` line comment |
| TE-3 | Error table > 3 columns? | Merge columns, 1 code per row |
| TE-4 | JSON paths scattered across file? | Declare at file top in one block |
| TE-5 | Duplicate fields in example-config.yaml? | Use YAML anchors |
| TE-6 | Content duplicated between SKILL.md and references/? | Delete from references, keep authoritative copy in SKILL.md |
| TE-7 | AIOps/FinOps not in `references/advanced/`? SQL execution not marked Security-Sensitive? | Move to `advanced/` + add Advanced Analytics section + Security-Sensitive subsection |

**Violation found → fix immediately → re-check until all pass.**

---

## Round 2: Content & Functional Check

| # | Check | Content |
|---|-------|---------|
| F1 | CLI command validation | `aliyun {product} help` confirms product exists? Command params match real API? |
| F2 | OpenAPI accuracy | All operationIds, field names, JSON paths traceable to OpenAPI or official docs? |
| F3 | Error handling | ≥10 error codes? Each has a recovery action? Retry vs HALT boundaries clear? |
| F4 | Safety gates | All delete/destroy operations have explicit confirmation? Credentials masked in all execution paths? |
| F5 | Link integrity | **MUST PASS**: All links in `references/`, `advanced/`, `assets/` valid? No dead links? **See Link Validation below. Broken links → BLOCK** |
| F6 | Content deduplication | **MUST PASS**: Any duplicated content between SKILL.md and references/? Duplicate → delete from references, keep SKILL.md as authoritative |
| F7 | Cross-skill delegation | Operations involving other products document delegation path instead of duplicating full flow? |
| F8 | TODO.md sync | **MUST PASS**: All new/changed features marked `✅` in skill or repo `TODO.md`? |
| F9 | Regression testing | **MUST PASS** (when behavior/scripts change): Applicable suites run and green? See [Regression Testing](#regression-testing-mandatory) below; RT-1–RT-5 |

> **F6、F8、F9 为强制通过项**（F9 在纯文档/格式修改时可跳过运行时测试）。不通过不得提交。

**Issues found → fix one by one → confirm all resolved before finishing.**

---

## Round 3: Lessons Learned (Recommended — Reflexion Memory)

> **Purpose**: Extract reusable failure patterns from this session to populate [failure-patterns.md](failure-patterns.md),
> enabling cross-session learning (Lightweight Reflexion). See [GCL §15 Reflexion Integration](gcl-spec.md#15-reflexion-integration-layer-2--failure-pattern-memory).

| # | Check | Content |
|---|-------|---------|
| L1 | Failure pattern extraction | 本次发现的问题是否可复用？→ 追加到 `failure-patterns.md` 对应章节 |
| L2 | Pattern dedup | 是否与已有模式重复？→ 去重后合并（匹配 `skill` + `command` + `error`，重复则 `count++`） |
| L3 | Token budget | `failure-patterns.md` 是否超过 200 行？→ 超过则精简 `count < 3` 的低频模式 |

### Extraction Rules

| Source | Pattern Category | Extraction Method |
|--------|------------------|-------------------|
| R1 Structural issues | `skill_generation` | Record issue type + fix pattern |
| R2 CLI parameter errors | `cli_parameter` | Record command + error + fix |
| R2 Link failures | `skill_generation` | Record broken link pattern |
| R2 Cross-skill issues | `cross_skill` | Record source → target failure |
| GCL trace failures | `runtime` | Extract from `failure_pattern` field in trace |

### When to Skip

- **Pure formatting changes** (markdown linting, whitespace) → Skip R3
- **No new failure patterns discovered** → Skip R3 (document "No new patterns" in record)
- **failure-patterns.md already at 200 lines** → Prune first, then add

---

## Self-Review Record

After each review, output a brief record in the current session:

```
## Review Record
### Round 1: Structural
- [found/ok] {check item}: {description}
- fix: {what was done}

### Round 2: Content
- [found/ok] {check item}: {description}
- fix: {what was done}

### Round 2: Regression (F9)
- [run/skipped] {suite}: {command}
- result: {pass/fail — list failures if any}

### Round 2: Critic gate (RT-6)
- [run] skill-change-critic-gate.sh verify --run
- tests_accurate: {true/false + one-line rationale}
- regression_required: {true/false}; suites: {list}
- result: {PASS/FAIL}

### Round 3: Lessons Learned
- [extracted/skipped] {pattern category}: {description}
- action: {appended to failure-patterns.md / dedup merged / pruned / no new patterns}
```

This record is session-only (no file write), but MUST be visible as evidence of completed review.

---

## Link Validation (MANDATORY)

**Rule**: Every documentation change affecting links MUST be followed by link integrity checking.

### Triggers

Link validation is required when:
- Adding or deleting `.md` files
- Moving files to a different directory (e.g. into `advanced/`)
- Modifying any markdown link in any file

### Verification Method

```bash
# Verify all links in a single skill
for f in alicloud-{product}-ops/**/*.md; do
  grep -oE '\[.*?\]\(([^)#]+\.md[^)]*)\)' "$f" | while read -r match; do
    target=$(echo "$match" | grep -oE '\(([^)]+)\)' | tr -d '()')
    target=$(echo "$target" | sed 's/#.*//')  # strip anchor
    if [ -n "$target" ]; then
      echo "$target" | grep -q "^http" && continue  # skip external links
      dir=$(dirname "$f")
      resolved="$dir/$target"
      if [ ! -f "$resolved" ]; then
        echo "BROKEN: $f → $target"
      fi
    fi
  done
done
```

### Scope

| File Type | Check Content |
|-----------|--------------|
| `SKILL.md` | All links to `references/`, `advanced/`, `assets/` |
| `references/*.md` | All links to sibling files |
| `references/advanced/*.md` | All links to parent directory `../` |
| `assets/*.md` | All links to `references/` |

### On Failure

Broken link found → **fix immediately** → re-verify until all pass.

---

## Content Deduplication (MANDATORY)

**Rule**: No duplicate content between SKILL.md and references/.

### Principles

- **SKILL.md = authoritative source**: execution overview, variable conventions, Pre-flight Checks tables
- **references/ = detailed implementation**: full scripts, error code tables, log interpretation
- **Maintain each fact in one place**: if SKILL.md already has the full flow, references/ MUST NOT repeat it

### Check Method

```bash
# Check for duplicate code blocks between SKILL.md and references/
# 1. Extract code blocks from SKILL.md
grep -oP '```bash\n.*?\n```' alicloud-{product}-ops/SKILL.md > /tmp/skill_code.txt
# 2. Extract code blocks from references/
grep -rl '```bash' alicloud-{product}-ops/references/ | xargs grep -oP '```bash\n.*?\n```' > /tmp/ref_code.txt
# 3. Compare
diff /tmp/skill_code.txt /tmp/ref_code.txt
```

### On Failure

Duplicate found → **delete the copy in references/** → re-verify

---

## Regression Testing (MANDATORY)

> Canonical summary: [AGENTS.md §11.1](../AGENTS.md#111-regression-testing-mandatory). F9 in Round 2.

**Rule**: Every skill change MUST be validated by regression tests before the task is marked done. Pure documentation edits (typos, link fixes with no behavior change) may skip runtime tests — any change to scripts, wrappers, CLI examples, SkillOpt libs, or execution flows requires tests.

### Default workflow (any skill update)

1. Identify which tests cover the changed skill or shared component.
2. Run the applicable suite(s) **after** the change (fix failures before finishing).
3. Record commands and pass/fail in the [Self-Review Record](#self-review-record).

### Test-first workflow (refactors & intentional behavior changes)

When changing or extracting behavior (refactor, shared-core extraction, repair/optimize semantics):

1. **Add or extend test cases first** — lock current behavior, or the new contract if intentionally changing.
2. **Refactor / implement**.
3. **All affected tests MUST pass** — no “done” on partial green runs.

**Banned**: large refactors with zero test updates and no post-hoc regression run.

### Regression suites by change type

| Change touches | Run (minimum) |
|----------------|---------------|
| Any `alicloud-*-ops` skill with SkillOpt | `bash alicloud-<product>-ops/test-skillopt-backward-compatibility.sh` |
| `alicloud-skillopt-ops/` shared runtime | `export ALIYUN_SKILLS_ROOT="$PWD" && bash alicloud-skillopt-ops/test-skillopt-integration.sh` |
| SkillOpt cross-skill / Langfuse | `bash scripts/test-multi-skill-session.sh --local` (`full` when `.env` + Langfuse available) |
| SkillOpt-heavy refactor (cms golden) | `bash alicloud-cms-ops/test-skillopt-backward-compatibility.sh` |
| `.scripts/gen-skillopt.sh` | Shared integration test + `bash -n` on one generated overlay |
| `alicloud-gcl-runner-ops/scripts/gcl_runner.py` | `python3 scripts/check_py310_compat.py` then `cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test gcl_strategy_test strategy_github_integration_test` |
| `SKILL.md` only (substantive) | `npx markdownlint-cli2 "alicloud-<product>-ops/SKILL.md"` |

Multi-skill changes (e.g. `skillopt-core-lib.sh`): run **shared integration test + one representative product test per overlay pattern** (e.g. ecs + cms).

### Agent checklist (RT-1–RT-5)

| # | Check |
|---|--------|
| RT-1 | Tests identified for this change type |
| RT-2 | Tests executed (not only `bash -n`) |
| RT-3 | Failures fixed or explicitly scoped with user approval |
| RT-4 | New behavior covered by new/updated tests when behavior changed |
| RT-5 | Completion summary lists test commands and results |
| RT-6 | Critic gate: `skill-change-critic-gate.sh verify --run` green; verdict has `tests_accurate` + `accuracy_rationale` |

### Skill Change Critic Gate (RT-6)

Same workflow as [AGENTS.md §11.1 Skill Change Critic Gate](../AGENTS.md#skill-change-critic-gate-mandatory--closes-the-loop):

```bash
bash scripts/skill-change-critic-gate.sh classify
bash scripts/skill-change-critic-gate.sh template
# Agent edits .runtime/audit/skill-change-verdict.json
bash scripts/skill-change-critic-gate.sh verify --verdict .runtime/audit/skill-change-verdict.json --run
```

Record in [Self-Review Record](#self-review-record) under **Round 2: Critic gate (RT-6)**.

### On failure

Test failure → **fix or revert** → re-run until green (or get explicit user scope reduction) → re-verify.

---

## Implementation Notes

- This rule applies to **all types** of updates: new operations, bug fixes, API version bumps, reference file changes, description optimizations.
- Does NOT apply to **pure formatting** changes (markdown linting, whitespace fixes) — lint pass is sufficient; F9 runtime tests may be skipped.
- Round 1 and Round 2 are independent — even if R1 passes fully, R2 MUST still be executed (including F9 when applicable).
- All fixes MUST be completed within the current session — no deferring to later sessions.