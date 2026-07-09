# Post-Update Self-Review Checklist for alicloud-kms-ops

## ✅ 2026-06-21 — P3 polling slimming
- `references/polling-patterns.md`: KMS KeyState 轮询模板；Disable/Enable/ScheduleDeletion。
- `SKILL.md`: DisableKey 内联轮询 → 引用；Reference Directory 已更新。

## Round 1: Structural Checks
- [ ] C1: Clear Boundaries: SHOULD/SHOULD NOT triggers with delegation rules; trigger description optimized per agentskills.io guidelines (< 1024 chars)
- [ ] C2: Structured I/O: `{{env.*}}` (never ask user), `{{user.*}}` (ask once reuse), `{{output.*}}` (parse from API responses)
- [ ] C3: Explicit Steps: Pre-flight → Execute → Validate → Recover for **each** critical operation
- [ ] C4: Failure Strategies: Error taxonomy (≥10 product-specific codes), HALT vs retry logic, credential vs quota vs business error separation
- [ ] C5: Single Responsibility: One product, one primary resource; cross-product delegation documented, not duplicated
- [ ] C6: CLI Format Verification: All `aliyun` CLI commands MUST use verified parameter formats; RepeatList params require `.N` suffix, JSON arrays require `'[