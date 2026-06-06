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

**Issues found → fix one by one → confirm all resolved before finishing.**

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

## Implementation Notes

- This rule applies to **all types** of updates: new operations, bug fixes, API version bumps, reference file changes, description optimizations.
- Does NOT apply to **pure formatting** changes (markdown linting, whitespace fixes) — lint pass is sufficient.
- Round 1 and Round 2 are independent — even if R1 passes fully, R2 MUST still be executed.
- All fixes MUST be completed within the current session — no deferring to later sessions.