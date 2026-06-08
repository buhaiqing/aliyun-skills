# alicloud-terraform-ops — 功能点完成跟踪

> 最后更新: 2026-06-09

## ✅ 已完成

### NL2HCL 自然语言生成 Terraform
- [x] Module-first 编排（`module_catalog.py` + `modules/` 可复用模块库）
- [x] 语义解析（regex 意图识别 + 实体抽取：资源/数量/规格/可用区/数据盘）
- [x] HCL 生成（VPC, VSwitch, ECS, RDS, Redis, SLB, NAT, EIP, 路由表, 独立云盘）
- [x] variables.tf / outputs.tf / terraform.tfvars / provider.tf 生成
- [x] Dry-run 模式默认离线生成 HCL + lint；`--with-validate` / `--with-plan` 显式启用 Terraform 步骤
- [x] GCL 质量门集成（`--gcl-check` → `gcl_runner.py`）
- [x] 交互式向导（`wizard_cli.py` / `terraform_ops.py wizard`）
- [x] 统一 CLI 入口（`terraform_ops.py`）
- [x] 多环境默认值（dev/staging/prod/int/uat/performance）
- [x] `intent_to_hitl_resources()` — NL2HCL 意图 → HITL 资源清单
- [x] `terraform_ops create`（非 dry-run）生成产物并注入 HITL Mode A 检查点

### Reverse Engineering 逆向导入
- [x] 资源发现（8+ 类型 via aliyun CLI）
- [x] VPC / VSwitch / ECS / RDS / Redis / SLB / EIP / Security Group HCL 生成
- [x] import.sh 生成
- [x] 关联资源自动发现（VPC → VSwitch, VPC → RouteTable）
- [x] Dry-run 模式（terraform init → validate → plan 白名单）
- [x] Resource Registry + PreFlight 渐进式资源支持（`resource_registry.py`）
- [x] GCL 集成
- [x] 同批次资源引用关联（`ResourceReferenceRegistry`：vpc/vswitch/rds/slb/sg/nat 等自动 `alicloud_*.xxx.id`）
- [x] HCL resource 块名称与 import.sh 统一（`make_tf_name()`）

### HITL 多模式工作流
- [x] Mode A: 交互式 CLI（CP1–CP5、五级环境策略、检查点持久化）— `hitl_mode_a.py`
- [x] Mode A CP3: 真实 `terraform init/validate/plan`（`terraform_plan_runner.py`）；失败降级为资源估算
- [x] `test_hitl_mode_a.py` — Mode A 策略/CP3/检查点持久化单测
- [x] Mode B: PR 式审核（LocalGitProvider、评论指令、PLAN.md）— `hitl_mode_b.py`
- [x] Mode C: CheckPoint 暂停（资源分级 PASS/WARN/SKIP、漂移检测、会话恢复）— `hitl_mode_c.py`
- [x] 共享层：审计/通知/熔断/升级 — `hitl_common.py`（钉钉/飞书/企微）

### GCL 质量门
- [x] Generator / Critic / Hallucination Detector Prompt 模板
- [x] Rubric 评分维度（Correctness / Safety / Idempotency / Traceability / Spec Compliance）
- [x] Dry-Run 输出标识规范
- [x] 执行轨迹持久化（`execution_trace.py` → `audit-results/gcl-trace-*.json`）

### 测试与文档
- [x] 单元/集成测试（170+ cases，`unittest discover -p 'test_*.py'`）
- [x] Eval Queries（20 条，`assets/eval_queries.json`）
- [x] SKILL.md 结构合规（前置检查/变量约定/执行后验证/故障恢复/架构评估）
- [x] Terraform 模块库已纳入版本控制（`modules/`）
- [x] `.gitignore` 覆盖 generated/、tfstate、.terraform/ 等 IaC 运行时产物

## ⚠️ 部分完成

- [ ] HITL Mode B — 仅 `LocalGitProvider`；GitHub/GitLab/Gitee API 未实现
- [ ] NL2HCL — `parse_intent()` 为规则引擎，复杂/模糊自然语言需 Agent 预处理或 Wizard 补全
- [ ] Reverse Engineering — 批次外依赖仍保留字面量 ID；ECS↔SG、Disk attachment 等待扩展
- [ ] SKILL §5 `environments/` 目录结构 — 文档有描述，仓库未预置脚手架
- [ ] `terraform apply` / `destroy` — 安全门与确认流程有 spec/CP5，脚本层未自动调用 terraform binary
- [ ] `terraform_ops import` — 尚未像 `create` 一样注入 HITL 检查点

## ❌ 未实现

- [ ] GitHub/GitLab/Gitee Git Provider（`hitl_mode_b.create_git_provider` 非 local 抛 NotImplementedError）
- [ ] `docs/gcl-spec.md` 技能分类表注册
- [ ] Canonical skill 可选 references（`well-architected-assessment.md`、`troubleshooting.md` 等独立文件）
- [ ] OpenAPI 驱动的 HCL 映射自动生成
