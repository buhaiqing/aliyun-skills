# alicloud-terraform-ops — 功能点完成跟踪

> 最后更新: 2026-06-08

## ✅ 已完成

### NL2HCL 自然语言生成 Terraform
- [x] 语义解析（意图识别 + 实体抽取）
- [x] HCL 生成（VPC, VSwitch, ECS）
- [x] variables.tf 生成
- [x] terraform.tfvars 生成
- [x] Dry-run 模式（terraform init → validate → plan 白名单）
- [x] GCL 质量门集成
- [x] 交互式向导模式 (`--wizard`)
- [x] 资源映射表（VPC/ECS/RDS/SLB/Redis 等）
- [x] 多环境默认值（dev/staging/prod）

### Reverse Engineering 逆向导入
- [x] 资源发现（8 种类型 via aliyun CLI）
- [x] VPC / VSwitch / ECS HCL 生成
- [x] import.sh 生成
- [x] 关联资源自动发现（VPC → VSwitch, VPC → RouteTable）
- [x] Dry-run 模式（terraform init → validate → plan 白名单）
- [x] Normal 模式自动 validate
- [x] GCL 集成

### GCL 质量门
- [x] Generator Prompt 模板（NL2HCL / Reverse Engineering / Terraform Operation）
- [x] Critic Prompt 模板（通用 / NL2HCL 专用 / Reverse Engineering 专用）
- [x] Hallucination Detector 模板（CLI 参数 / JSON 结构 / WAF）
- [x] Orchestrator 决策逻辑
- [x] Rubric 评分维度（Correctness / Safety / Idempotency / Traceability / Spec Compliance）
- [x] Dry-Run 输出标识规范

### 基础设施
- [x] Eval Queries（20 条评估用例）
- [x] SKILL.md 结构合规（前置检查/变量约定/执行后验证/故障恢复/架构评估）
- [x] 引用链接全部有效
- [x] 章节编号一致性

## ⚠️ 部分完成

- [ ] `scripts/nl2hcl_generator.py` — outputs.tf 仅覆盖 VPC，建议补充 ECS 等资源的输出
- [ ] `scripts/reverse_engineering.py` — RDS/Redis/SLB/EIP/SG 的 HCL 生成函数 `to_hcl()` 返回 TODO，需实现

## ❌ 未实现（仅文档阶段）

- [ ] HITL Mode A: 交互式 CLI — `references/hitl-workflow.md` + `hitl-implementation.md` 有完整 spec，无可执行代码
- [ ] HITL Mode B: PR 式审核 — Git PR 驱动流程有 spec，无实现
- [ ] HITL Mode C: CheckPoint 暂停 — 会话恢复有 spec，无实现
- [ ] Interactive Wizard CLI — `references/interactive-wizard.md` 有完整 spec，`aliyun-terraform wizard` CLI 不存在
- [ ] Reverse Engineering 资源分级（PASS/WARN/SKIP）— spec 中有文档，脚本中无实现
- [ ] Reverse Engineering CheckPoint 会话持久化 — spec 中有文档，脚本中无实现