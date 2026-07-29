# PLAN: alicloud-clickhouse-ops — Dual-Path (Enterprise CLI + Classic SDK) Implementation

## Phases

### Phase 1: Foundation Documents
Create the core reference documents in `alicloud-clickhouse-ops/references/`:
- [x] `core-concepts.md` — 架构、规格、配额、限制
- [x] `cli-usage.md` — CLI 命令映射（企业版 2023-05-22）
- [x] `api-sdk-usage.md` — SDK 操作映射（经典版 2019-11-11）
- [x] `monitoring.md` — CMS 指标、告警、看板

### Phase 2: Operations Documents
- [ ] `troubleshooting.md` — ≥10 错误码、诊断、恢复
- [ ] `well-architected-assessment.md` — 五支柱评估
- [ ] `prompt-templates.md` — GCL prompt 模板
- [ ] `prompt-examples.md` — 用户侧 NL prompt 示例
- [ ] `rubric.md` — GCL 评分卡

### Phase 3: Main Skill + Assets
- [ ] `SKILL.md` — 主技能文件（从模板生成）
- [ ] `assets/example-config.yaml` — 示例配置
- [ ] `assets/eval_queries.json` — 20+ 条评估查询

### Phase 4: Integration + Review
- [ ] 更新 `SKILL-MATRIX.md` 添加 ClickHouse 行
- [ ] 运行 R1（结构审查）+ R2（内容审查）
- [ ] 最终验证

## Dependencies
- Phase 1 → Phase 2 → Phase 3 (sequential due to cross-references)
- Phase 4 is independent of 1-3 except SKILL-MATRIX update

## Risk Assessment
| Risk | Mitigation |
|------|-----------|
| 企业版和经典版 API 差异大 | 分版本处理，CLI 文档聚焦企业版，SDK 文档覆盖经典版 |
| 部分 CLI 参数格式未知 | 每个命令前先 `--help` 验证参数格式 |
| SKILL-MATRIX.md 格式 | 读取现有文件，追加一行 |
