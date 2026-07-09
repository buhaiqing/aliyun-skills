# TODO for alicloud-redis-ops
## Post-Update Self-Review Checks
1. [x] Structural checks passed
2. [x] Content checks passed
3. [x] Token efficiency optimized — SKILL.md 瘦身：25 个 Go SDK 代码块 + 13 个轮询代码块移至 references/，1611→1422 行 (-12%)
4. [x] TODO.md synced — 记录本次 SKILL.md 瘦身变更
5. [ ] Langfuse integration validated

## 2026-06-18 — SKILL.md Slimming (Content Separation)

✅ **1. Go SDK code blocks → references/api-sdk-usage.md**
   - 25 Go SDK code blocks moved to new `## Go SDK Examples` section
   - SKILL.md now links to `references/api-sdk-usage.md#go-sdk-examples`

✅ **2. Polling patterns → new references/polling-patterns.md**
   - 13 polling code blocks moved to new file with generic template + per-operation parameters table
   - SKILL.md now links to `references/polling-patterns.md`
