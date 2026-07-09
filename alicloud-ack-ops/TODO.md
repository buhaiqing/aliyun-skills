# TODO for alicloud-ack-ops
## ✅ 2026-06-21 — P3 polling slimming
- `references/polling-patterns.md`: 集群/nodepool 状态 + 删除消失模板；7 行操作参数表。
- `SKILL.md`: CreateCluster 内联 60×30s 循环 → 引用；Reference Directory 已增加链接。
## Post-Update Self-Review Checks
1. [ ] Structural checks passed
2. [ ] Content checks passed
3. [x] Token efficiency optimized — SKILL.md 瘦身：4 个诊断脚本和前置检查脚本移至 references/
4. [x] TODO.md synced — 记录本次 SKILL.md 瘦身变更
5. [ ] Langfuse integration validated
