# alicloud-ram-ops — TODO

This file tracks open work and recent completions for the
`alicloud-ram-ops` skill, per AGENTS.md §11 F8 (TODO.md sync is a mandatory
post-update check).

> **Convention:** Open items use `- [ ]`; completed items use `- [x]` with
> a short commit / change id.

---

## 2026-06-07 — v2.3.0 Refactor: Second-pass Content Separation (GCL + Variable → references/)

**Why:** Even after v2.2.0, SKILL.md was still 367 lines — the
**Quality Gate (GCL)** chapter (87 lines) and **Variable Convention**
chapter (32 lines) were still inlined, plus the **Reference Directory**
(32 lines) was over-segmented into 4 sub-groups with redundant pointers.

**Change scope:** 2 new files + SKILL.md second-pass rewrite
(367 → 265 lines, additional -28%; combined v2.2.0 + v2.3.0:
1611 → 265 lines, **-84%**).

| # | Status | Item | Notes |
|---|--------|------|-------|
| 1 | ✅ | Create `references/gcl-quality-gate.md` (Scope / Why-RAM / Per-Op Safety Sub-Rules / RAM-Specific Additions / Termination / Trace Persistence / Changelog) | 99 lines; pulled from SKILL.md L269–355 |
| 2 | ✅ | Create `references/variable-convention.md` (placeholder table + collection constraints + credential hygiene) | 57 lines; pulled from SKILL.md L132–163 |
| 3 | ✅ | Rewrite SKILL.md to replace GCL chapter with brief pointer + 1-paragraph summary | L269–355 → 11 lines (saves 76) |
| 4 | ✅ | Rewrite SKILL.md to replace Variable Convention chapter with brief pointer | L132–163 → 7 lines (saves 25) |
| 5 | ✅ | Compress Reference Directory from 4 sub-groups (32 lines) to a single 21-row table (32 lines) — links unchanged in count, removed redundant sub-headings and inline descriptions | Same link coverage, ~30% whitespace reduction |
| 6 | ✅ | Update frontmatter `version` to `2.3.0` | Following metadata convention |
| 7 | ✅ | Verify all 123 internal links (82 file + 41 anchor) resolve | F5 check — all pass after fixing 2 missing `..` prefixes in references/ subdirectory relative paths |

## 2026-06-07 — v2.2.0 Refactor: Content Separation (SKILL.md → references/)

**Why:** The original SKILL.md (1611 lines) violated AGENTS.md §2
Content Separation Rule — ~1100 lines of per-operation Pre-flight /
Execution / Post-execution / Failure Recovery blocks were embedded in
SKILL.md, which should describe only **what** to do. Reference files
should describe **how** to do it.

**Change scope:** New files (7) + SKILL.md rewrite (1611 → 367 lines, -77%).

| # | Status | Item | Notes |
|---|--------|------|-------|
| 1 | ✅ | Create `references/api-response-reference.md` (JSON paths, Response Field Table, error taxonomy, CLI/SDK output notes) | 157 lines; pulled from SKILL.md L47–60, L159–201, L163–165 |
| 2 | ✅ | Create `references/prompt-examples.md` (Common Task Templates + Chinese interaction quick reference + Scenario index) | 143 lines; pulled from SKILL.md L210–294 |
| 3 | ✅ | Create `references/operations/user-operations.md` (User + LoginProfile + AccessKey + MFA + Key Rotation) | 539 lines; pulled from SKILL.md L303–507, L989–1269, L1082–1096 |
| 4 | ✅ | Create `references/operations/group-operations.md` (Create/Get/Add/Remove/Delete Group + ListUsersForGroup + ListGroupsForUser) | 187 lines; pulled from SKILL.md L508–577 |
| 5 | ✅ | Create `references/operations/role-operations.md` (Role + STS AssumeRole + GetCallerIdentity + Trust Policy structure) | 292 lines; pulled from SKILL.md L579–675, L679–755, L1273–1353 |
| 6 | ✅ | Create `references/operations/policy-operations.md` (Policy + Version + Attach/Detach + Policy Document structure) | 345 lines; pulled from SKILL.md L757–988 |
| 7 | ✅ | Create `references/operations/audit-operations.md` (Password Policy + Least-Privilege Audit + Access Key Rotation) | 209 lines; pulled from SKILL.md L1082–1096 (rotation), L1356–1470 (audit / password) |
| 8 | ✅ | Rewrite `SKILL.md` (1611 → 367 lines) | Now serves as navigation + "What" index; all per-operation blocks link to `references/operations/*.md` |
| 9 | ✅ | Update `Variable Convention` to add `{{output.account_id}}` and `{{output.mfa_serial_number}}` placeholders | Pulled from existing operations to make the convention table complete |
| 10 | ✅ | Update `Reference Directory` section to point at the 7 new files | Replaces the pre-refactor list of 10 references |
| 11 | ✅ | Update `Changelog` in SKILL.md Quality Gate section | Added v2.2.0 entry describing the refactor |
| 12 | ✅ | Bump frontmatter `version` to `2.2.0` and `last_updated` to `2026-06-07` | Follows Skill metadata convention |
| 13 | ✅ | Verify all 40 internal anchor links resolve (GitHub-slug rule) | F5 check — passes (1 false-positive in script for AGENTS.md `—` em-dash; verified manually) |
| 14 | ✅ | Re-run markdownlint baseline | Project-wide MD013/MD060 errors are pre-existing across all skills (e.g. `alicloud-ecs-ops/SKILL.md`); not a regression |

## Open / Backlog

| # | Status | Item | Priority | Notes |
|---|--------|------|----------|-------|
| B1 | [x] | Add `references/credential-hygiene.md` (consolidated secret-handling policy) | P2 | Closed in v2.3.0 — covered by `references/variable-convention.md` §3 + cross-references to `api-response-reference.md` §5 and `operations/user-operations.md` |
| B2 | [ ] | Add `assets/eval_queries.json` (trigger-accuracy eval set) | P1 | Required by canonical skill structure (AGENTS.md §1); currently missing in alicloud-ram-ops |
| B3 | [ ] | Add `assets/example-config.yaml` (RAM env / role / policy examples) | P2 | Required by canonical skill structure (AGENTS.md §1) |
| B4 | [ ] | Add `references/monitoring.md` (CMS metrics for RAM — login failures, AK last-used, etc.) | P2 | Only required "if applicable"; RAM has limited CMS surface — evaluate before adding |
| B5 | [ ] | Generate advanced/ subfolder (aiops-, finops- RAM topics) | P3 | No demand yet; defer until specific AIOps / FinOps RAM scenarios are documented elsewhere |
| B6 | [ ] | Promote `references/intelligent-inspection.md` (智能巡检) to be a full advanced/aiops-* doc | P3 | Currently a stub; needs full anomaly-detection / auto-remediation content |
| B7 | [ ] | Reconcile `prompt-examples.md` (intent → action) with `references/intelligent-inspection.md` (security巡检) | P3 | Both touch "audit" intent; cross-link once both are stable |

## Verification

- **F1–F4 (structural, CLI validation, error codes, safety gates):** all preserved 1:1 from original SKILL.md (per-operation blocks migrated verbatim into `references/operations/*.md`).
- **F5 (link integrity):** 40 internal anchor links verified; all resolve to real headings (GitHub-slug rule).
- **F6 (token efficiency):** the refactor is precisely the TE-6 (eliminate cross-file duplication) optimization mandated by AGENTS.md §10.1.
- **F7 (dedup):** `SKILL.md` no longer repeats per-operation execution blocks; `api-response-reference.md` is the single source of truth for JSON paths and error codes.
- **F8 (TODO.md sync):** this file exists and is updated as part of the v2.2.0 refactor.
