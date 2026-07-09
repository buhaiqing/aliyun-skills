# Post-Update Self-Review Checklist for alicloud-eci-ops

## ✅ 2026-06-21 — P3 polling slimming
- `references/polling-patterns.md`: ContainerGroup 状态/删除消失 模板（`aliyun eci` 无 `--waiter`）。
- `SKILL.md`: CreateContainerGroup 内联 60×5s case 分支 → 引用；Polling Strategy + Reference Directory 已含链接。

## Round 1: Structural Checks
- [ ] C1: Clear Boundaries: Trigger/description optimized per agentskills.io (<1024 chars)
- [ ] C2: Structured I/O: {{env.*}}, {{user.*}}, {{output.*}} conventions followed
- [ ] C3: Explicit Steps: Pre-flight → Execute → Validate → Recover for all critical ops
- [ ] C4: Failure Strategies: Error taxonomy (≥10 codes), HALT/retry logic, error separation
- [ ] C5: Single Responsibility: One product, one primary resource; cross-skill dependencies documented
- [ ] C6: CLI Format Verification: All aliyun commands verified, RepeatList/JSON array params correct

## Round 2: Content Checks
- [ ] F1: CLI examples verified via `aliyun --help`
- [ ] F2: Error codes and recovery steps documented
- [ ] F3: Link integrity: All relative links resolve correctly
- [ ] F4: Duplicate content removed: No repeated commands/descriptions across files
- [ ] F5: TODO.md updated for all new/modified features
- [ ] F6: Token Efficiency optimizations applied (no hardcoded values, lazy-loaded advanced content)
- [ ] F7: Well-Architected Framework table included
- [ ] F8: All changes reflected in SKILL.md

## SkillOpt Integration Checks
- [ ] S1: `scripts/skillopt-lib.sh` exists, `references/skillopt-lib.sh` does not
- [ ] S2: Wrapper script sources `scripts/skillopt-lib.sh` correctly
- [ ] S3: Runtime Rules section in SKILL.md mandates wrapper-first execution
- [ ] S4: Langfuse tracing enabled and configured properly
- [ ] S5: Backward compatibility test script passes
