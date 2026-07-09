# TODO for alicloud-sls-ops
## Post-Update Self-Review Checks
### Round 1: Structural Checks
- [ ] Frontmatter valid
- [ ] Trigger/Scope clear
- [ ] Variables correctly defined
- [ ] Token efficiency optimized (TE1-TE7)
- [ ] GCL rubric present
- [ ] All quality gates passed (C1-C6)

### Round 2: Content Checks
- [ ] CLI commands verified (14.1-14.6)
- [ ] Error codes ≥10 present
- [ ] Safety gates in place
- [ ] Link integrity verified
- [ ] No duplicate content
- [ ] TODO.md synced (F8)
- [ ] Langfuse integration validated
- [ ] SkillOpt wrapper configured correctly

## Backlog / Recent Changes

- [x] Add `AnalyzeSlbPerHostTraffic` Runbook
  （按 SLB 子域名 Top N 流量分析；wrapper-first；含 CLB7/ALB 字段适配表；
  rubric.md 增 Safety 子规则；eval_queries.json 增 SLQ-011）
- [ ] 派生 Dashboard 子流程：把 Top N Host 查询固化为 SLS Dashboard widget
- [ ] 在 `alicloud-slb-ops` 侧补对称的 "Enable Access Log to SLS" 前置 Runbook
- [ ] 实跑验证 wrapper 对 SLS REST 风格子命令
  （`GET /logstores/.../logs ...`）的透传兼容性，
  并在 `references/skillopt-integration.md` 留结论
