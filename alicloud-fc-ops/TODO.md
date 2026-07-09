# TODO for alicloud-fc-ops
## ✅ 2026-06-21 — P3 polling slimming
- `references/polling-patterns.md`: FC 函数状态轮询模板；Create/Update 60×5s。
- `SKILL.md`: CreateFunction 内联轮询 → 引用。
- `references/deploy-from-source.md`: Phase 4 验证轮询 → 引用。

## Post-Update Self-Review Checks
1. [x] Structural checks passed
2. [x] Content checks passed
3. [x] Token efficiency optimized — SKILL.md 瘦身：6 处内联代码块移至 references/，1025→711 行 (-30%)
4. [x] TODO.md synced — 记录本次 SKILL.md 瘦身变更
5. [ ] Langfuse integration validated

## 2026-06-18 — SKILL.md Slimming (Content Separation)

✅ **1. Go SDK CreateFunction → references/api-sdk-usage.md**
   - 37-line Go code block moved to new `## Go SDK Examples` section
   - SKILL.md now links to `references/api-sdk-usage.md#go-sdk-examples`

✅ **2. InvokeFunction SDK Path → references/api-sdk-usage.md**
   - 23-line Go code block moved to same Go SDK Examples section
   - SKILL.md now links to `references/api-sdk-usage.md#go-sdk-examples`

✅ **3. End-to-End Deploy → new references/deploy-from-source.md**
   - ~120 lines (Pre-flight, Phase 1-5, Failure Recovery) moved to new file
   - SKILL.md now links to `references/deploy-from-source.md`

✅ **4. Multi-Metric CLI queries → references/monitoring.md**
   - ~30 lines bash + Recovery table moved to `## CLI Monitoring Integration — Multi-Metric Queries`
   - SKILL.md now links to `references/monitoring.md#cli-monitoring-integration--multi-metric-queries`

✅ **5. Alert-Driven Diagnosis → references/monitoring.md**
   - ~40 lines (decision tree + report schema) moved to `## Alert-Driven Diagnosis`
   - SKILL.md now links to `references/monitoring.md`

✅ **6. GPU execution blocks → references/gpu-inference.md**
   - ~60 lines (Pre-flight, CLI, validation, recovery) moved to `## 12. Quick Reference — GPU Execution Blocks`
   - SKILL.md now links to `references/gpu-inference.md`

✅ **7. Reference Directory updated**
   - Added `references/deploy-from-source.md` entry
