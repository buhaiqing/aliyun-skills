# Post-Update Self-Review Checklist for alicloud-sas-ops

## Task Completion
- [✅] 1. Delete duplicate skillopt-lib.sh from references/ directory
- [✅] 2. Fix wrapper script to source scripts/skillopt-lib.sh correctly
- [✅] 3. Create TODO.md with post-update self-review checklist
- [✅] 4. Added mandatory Runtime Rules for SkillOpt wrapper to SKILL.md
- [✅] 5. Copied skillopt-lib.sh to scripts/ directory and made it executable

## Standard Post-Update Checks

### Round 1: Structural
- [ ] C1: Clear Boundaries: SHOULD/SHOULD NOT triggers with delegation rules; trigger description optimized per agentskills.io guidelines (< 1024 chars)
- [ ] C2: Structured I/O: `{{env.*}}` (never ask user), `{{user.*}}` (ask once reuse), `{{output.*}}` (parse from API responses)
- [ ] C3: Explicit Steps: Pre-flight → Execute → Validate → Recover for **each** critical operation
- [ ] C4: Failure Strategies: Error taxonomy (≥10 product-specific codes), HALT vs retry logic, credential vs quota vs business error separation
- [ ] C5: Single Responsibility: One product, one primary resource; cross-product delegation documented, not duplicated
- [ ] C6: CLI Format Verification: All `aliyun` CLI commands MUST use verified parameter formats; RepeatList params require `.N` suffix, JSON arrays require `'["value1","value2"]'` format

### Round 2: Content
- [ ] F1: CLI validation: All commands tested with `aliyun help`
- [ ] F2: Error codes: ≥15 product-specific codes in Failure Recovery
- [ ] F3: Safety gates: Destructive operations require explicit confirmation
- [ ] F4: Link integrity: All markdown links point to valid files
- [ ] F5: Dedup: No duplicate code/commands across sections
- [ ] F6: Token Efficiency: Follow TE-1 to TE-7 rules
- [ ] F7: TODO.md sync: All changes tracked here
- [ ] F8: Langfuse Integration: Follow §15.7 requirements (wrapper-first, tracing, etc.)